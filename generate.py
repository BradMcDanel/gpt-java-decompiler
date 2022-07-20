import argparse
import os
import json
import time

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, StoppingCriteria, StoppingCriteriaList

import prompts
import java_utils

from tree_sitter import Language, Parser
JAVA_LANG = Language('CodeBLEU/parser/my-languages.so', 'java')
java_parser = Parser()
java_parser.set_language(JAVA_LANG)

MAX_LEN = 2048


class StopWords(StoppingCriteria):
    def __init__(self, tokenizer, stop_words):
        super().__init__()
        self.tokenizer = tokenizer
        self.stop_words = stop_words

    def __call__(self, input_ids, scores, **kwargs):
        num_samples = input_ids.shape[0]
        num_stopped = 0
        for input_id in input_ids:
            output = self.tokenizer.decode(input_id)
            if any(word in output for word in self.stop_words):
                num_stopped += 1
                continue

        return num_stopped == num_samples


def decode_tokens(tokenizer, generated_ids, start_trim_words=["<|java|>"],
                  end_trim_words=["<|endoftext|>"]):
    outputs = []
    for generated_id in generated_ids:
        output = tokenizer.decode(generated_id)
        for start_trim_word in start_trim_words:
            if start_trim_word in output:
                output = output[output.index(start_trim_word) + len(start_trim_word):]
                break
        
        for end_trim_word in end_trim_words:
            # trim past final end_trim_word
            if end_trim_word in output:
                end_trim_index = output.index(end_trim_word)
                output = output[:end_trim_index]
                break

        outputs.append(output)

    return outputs


def build_tokenized_batch(tokenizer, samples):
    input_ids = []
    max_len = 0
    for sample in samples:
        input_id = tokenizer(sample, return_tensors="pt").input_ids[0]
        input_ids.append(input_id)
        max_len = max(max_len, len(input_id))

    if max_len > MAX_LEN:
        return None

    # pad each input_id to the max length (left-side using pad_token)
    for i, input_id in enumerate(input_ids):
        padding = torch.ones(max_len - len(input_id), dtype=torch.long) * tokenizer.pad_token_id
        input_ids[i] = torch.cat([padding, input_id])

    # stack the input_ids to make a batch of sequences
    input_ids = torch.stack(input_ids)

    input_ids = input_ids.to("cuda")
    return input_ids 


def split_method(java):
    tree = java_parser.parse(bytes(java, 'utf-8'))
    cursor = tree.walk()

    cursor.goto_first_child()
    while cursor.goto_next_sibling():
        if cursor.node.type == "class_declaration":
            break

    cursor.goto_first_child()
    while cursor.goto_next_sibling():
        if cursor.node.type == "class_body":
            break

    cursor.goto_first_child()
    while cursor.goto_next_sibling():
        if cursor.node.type in ["method_declaration", "constructor_declaration"]:
            method_start_index = cursor.node.start_byte
            method_start_index = java[:method_start_index].rfind('\n') + 1
            header = java[:method_start_index]
            body = java[method_start_index:]
            parts = body.split('}')
            footer = '}\n' + parts[-1]
            body = '}'.join(parts[:-1])

            return header, body, footer

    return None, None, None

def assemble_methods_to_class(methods):
    if len(methods) == 1:
        return methods[0]
    else:
        header, _, footer = split_method(methods[0])
        if header is None:
            return None

        method_bodys = []
        for method in methods:
            _, body, _ = split_method(method)
            if body is None:
                return None

            method_bodys.append(body)

        java = header + '\n'.join(method_bodys) + footer

        return java


if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-name", type=str, required=True, help="Model name")
    parser.add_argument("--data-dir", type=str, required=True, help="Data directory")
    parser.add_argument("--output-path", type=str, required=True, help="Output path")
    parser.add_argument("--num-samples", type=int, default=-1, help="Number of samples to generate")
    parser.add_argument("--batch-size", type=int, default=4, help="Batch size")
    args = parser.parse_args()

    # load data
    test_methods_path = os.path.join(args.data_dir, "test_methods.json")
    test_samples_path = os.path.join(args.data_dir, "test_samples.json")
    samples, methods = [], []
    with open(test_samples_path, 'r') as f:
        for line in f:
            samples.append(json.loads(line))

    with open(test_methods_path, 'r') as f:
        for line in f:
            methods.append(json.loads(line))


    if args.num_samples == -1:
        num_samples = len(samples)
    else:
        num_samples = args.num_samples

    tokenizer = AutoTokenizer.from_pretrained("Salesforce/codegen-350M-multi")
    tokenizer.pad_token_id = tokenizer.eos_token_id
    stopping_criteria = StoppingCriteriaList([StopWords(tokenizer, ["<|endoftext|>"])])
    model = AutoModelForCausalLM.from_pretrained(args.model_name)
    model = model.to("cuda")
    model.eval()
    model.half()

    method_id = 0
    outputs = []
    for sample_id, sample in enumerate(samples):
        if sample_id >= num_samples:
            break

        output = {
            "gold": sample.copy(),
            "class_name": sample["class_name"],
            "neural": {
                "java_source" : "",
                "pass_rate" : 0.0,
                "decomp_time" : 0.0,
                "java_gen" : False,
                "compile" : False,
            }
        }

        start_time = time.time()
        sample_prompts = []

        # decompile each method for a given sample
        while methods[method_id]["id"] == samples[sample_id]["id"]:
            jasm_code = methods[method_id]["jasm_code"]
            sample_prompts.append(prompts.jasm_to_java_test(jasm_code))
            method_id += 1


        output["neural"]["java_gen"] = True

        with torch.no_grad():
            java_preds = []
            tokenize_failed = False
            for i in range(0, len(sample_prompts), args.batch_size):

                batch = sample_prompts[i:i+args.batch_size]

                # tokenize the sample prompt batch
                input_ids = build_tokenized_batch(tokenizer, batch)

                if input_ids is None:
                    tokenize_failed = True
                    break

                generated_ids = model.generate(
                    input_ids,
                    max_length=MAX_LEN,
                    pad_token_id=tokenizer.eos_token_id,
                    stopping_criteria=stopping_criteria,
                )

                batch_preds = decode_tokens(tokenizer, generated_ids,
                                            start_trim_words=["<|java|>"],
                                            end_trim_words=["<|endoftext|>"])

                if len(batch_preds) == 0:
                    print(f"{sample_id}: failed to generate")
                    tokenize_failed = True
                    break

                java_preds.extend(batch_preds)

        if tokenize_failed:
            print(f"{sample_id}: failed to tokenize")
            outputs.append(output)
            continue

        pred_java = assemble_methods_to_class(java_preds)
        if pred_java is None:
            print(f"{sample_id}: Failed to assemble")
            outputs.append(output)
            continue

        # include the java code even if it fails to compile (may be useful to see why)
        output["neural"]["java_source"] = pred_java

        class_name = java_utils.get_class_name(pred_java)
        pred_byte_code = java_utils.compile_str(class_name, pred_java)

        if pred_byte_code is None:
            print(f"{sample_id}: failed to compile")
            outputs.append(output)
            continue

        output["neural"]["compile"] = True

        pass_rate = java_utils.evosuite_compile_and_run_test(
            sample["class_name"],
            pred_byte_code,
            sample["java_test"],
            sample["java_scaffold"],
        )

        end_time  = time.time()
        output["neural"]["pass_rate"] = pass_rate
        output["neural"]["decomp_time"] = end_time - start_time

        print(f"{sample_id}: pass rate {pass_rate}")
        outputs.append(output)

    with open(args.output_path, 'w') as f:
        for output in outputs:
            f.write(json.dumps(output) + "\n")

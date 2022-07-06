import argparse
import os
import json

from transformers import AutoTokenizer, AutoModelForCausalLM, StoppingCriteriaList
from transformers.generation_stopping_criteria import StoppingCriteria

import prompts
import java_utils

class StopWordsCriteria(StoppingCriteria):
    def __init__(self, tokenizer, stop_words):
        self.tokenizer = tokenizer
        self.stop_words = stop_words

    def __call__(self, input_ids, scores):
        all_stop = True
        for i in range(len(input_ids)):
            output = tokenizer.decode(input_ids[i], skip_special_tokens=True)
            for word in self.stop_words:
                if word in output:
                    print("Found stop word: " + word, input_ids.shape[1])
                    break
            else:
                all_stop = False
                break
            
        return all_stop


def trim_stop_words(outputs, stop_words):
    trimmed_outputs = []
    for output in outputs:
        # for each stop word, trim up to the first instance of that word
        for stop_word in stop_words:
            if stop_word in output:
                output = output[:output.index(stop_word)]

        trimmed_outputs.append(output)
    
    return trimmed_outputs


def jasm_to_java_test(sample, pred_java_source):
    pred_byte_code = java_utils.compile_str(sample["class_name"], pred_java_source)

    if pred_byte_code is None:
        return 0.0

    pred_pass_rate = java_utils.evosuite_compile_and_run_test(
        sample["class_name"],
        pred_byte_code,
        sample["java_test"],
        sample["java_scaffold"],
    )

    return pred_pass_rate


if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-name", type=str, required=True, help="Model name")
    parser.add_argument("--tokenizer-name", type=str, required=True, help="tokenizer name")
    parser.add_argument("--target", choices=["java_to_jasm", "jasm_to_java"], required=True,
                        help="target output")
    parser.add_argument("--data-dir", type=str, required=True, help="Data directory")
    parser.add_argument("--output-path", type=str, required=True, help="Output path")
    args = parser.parse_args()

    stop_words = []
    if args.target == "java_to_jasm":
        stop_words.append("</JASM>")
    elif args.target == "jasm_to_java":
        stop_words.append("</JAVA>")

    # load data
    test_path = os.path.join(args.data_dir, "test.json")
    data = []
    with open(test_path, 'r') as f:
        for line in f:
            data.append(json.loads(line))

    samples = []
    for i in range(len(data)):
        text = prompts.get_test_prompt(args.target, data[i]["java_source"], data[i]["jasm_code"])
        samples.append(text)

    tokenizer = AutoTokenizer.from_pretrained(args.tokenizer_name)
    model = AutoModelForCausalLM.from_pretrained(args.model_name)
    model = model.to("cuda")

    results = []
    for i, prompt in enumerate(samples):
        sample_data = data[i]
        input_ids = tokenizer(prompt, return_tensors="pt").input_ids.to("cuda")

        # truncate to max length
        input_ids = input_ids[:, -2048:]
        input_len = input_ids.shape[1]

        generated_ids = model.generate(
            input_ids,
            max_length=2048,
            pad_token_id=tokenizer.eos_token_id,
            stopping_criteria=StoppingCriteriaList([StopWordsCriteria(tokenizer, stop_words)]),
        )

        output = tokenizer.decode(generated_ids[0, input_len:], skip_special_tokens=True)
        output = trim_stop_words([output], stop_words)[0]
        pass_rate = jasm_to_java_test(sample_data, output)

        print(f"{i}/{len(samples)}: {pass_rate}")

        results.append({
            "pass_rate": pass_rate,
            "java_source": sample_data["java_source"],
            "jasm_code": sample_data["jasm_code"],
            "pred_java_source": output,
        })

    with open(args.output_path, 'w') as f:
        for result in results:
            f.write(json.dumps(result) + "\n")

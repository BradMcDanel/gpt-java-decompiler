import argparse
import json
import time

import split_java
from peft_util import load_peft_model
import java_utils

BATCH_SIZE = 1

def generate(args, model, tokenizer, inputs):
    """
    Split inputs into batches and generate outputs.
    """
    task = "Convert Java Assembly to Java Code: "
    outputs = []
    for i in range(0, len(inputs), BATCH_SIZE):
        batch = inputs[i:i + BATCH_SIZE]
        for j in range(len(batch)):
            batch[j] = task + batch[j]
        input_ids = tokenizer(batch, padding=True, return_tensors="pt").input_ids

        if args.use_cuda:
            input_ids = input_ids.cuda()

        generated_ids = model.generate(
            input_ids=input_ids,
            num_beams=4,
            max_length=1024,
            # repetition_penalty=2.5,
            # no_repeat_ngram_size=2,
            temperature=1.0,
            early_stopping=True,
            num_return_sequences=1
        )

        outputs.extend(tokenizer.batch_decode(generated_ids, skip_special_tokens=True))

    return outputs


def filter_methods(methods):
    filtered_methods = []
    for method in methods:
        if ".method public <init> : ()V" in method or \
            ".method <init> : ()V" in method or \
            ".method private <init> : ()V" in method:
            continue
        filtered_methods.append(method)
    
    return filtered_methods

def arrange_methods(methods):
    methods = methods[:]
    arranged_methods = [methods[0]]
    methods.pop(0)

    # look for clinit method
    for method in methods:
        if "<clinit>" in method:
            arranged_methods.append(method)
            methods.remove(method)
            break
    
    # add the rest
    for method in methods:
        arranged_methods.append(method)
    
    return arranged_methods

def postprocess_clinit(method):
    # remove "static {" and "}"
    method = method.split("<|static|> {")[1]
    # split on the final "}"
    method = "}".join(method.split("}")[:-1])
    return method

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", type=str, required=True, help="model path")
    parser.add_argument("--input-file", type=str, required=True, help="data file")
    parser.add_argument("--output-file", type=str, required=True, help="output file")
    parser.add_argument("--use-cuda", action="store_true", help="use cuda")
    args = parser.parse_args()

    data = []
    with open(args.input_file) as f:
        for line in f:
            data.append(json.loads(line))

    model, tokenizer = load_peft_model(args.model_path)

    if args.use_cuda:
        model = model.cuda()
        model = model.half()

    num_compiled, num_correct, num_total = 0, 0, 0
    java_output = []
    for sample, d in enumerate(data):
        num_total += 1
        result_dict = {}
        java = d["java_source"]
        jasm = d["jasm_code"]
        methods = split_java.get_jasm_methods(d)

        result_dict["class_name"] = d["class_name"]
        result_dict["class_idx"] = d["class_idx"]

        start_time = time.time()
        pred_java_methods = generate(args, model, tokenizer, methods)
        end_time = time.time()
        decomp_time = end_time - start_time
        print("took:", decomp_time)

        for i, method in enumerate(pred_java_methods):
            if "<|static|> {" in method:
                pred_java_methods[i] = postprocess_clinit(method)

        pred_java = split_java.merge_java_methods(pred_java_methods)

        result_dict["java_source"] = pred_java

        class_name = java_utils.get_class_name(pred_java)
        compile_result = java_utils.compile_str(class_name, pred_java)
    
        result_dict["compile"] = compile_result["success"]

        # try to compile
        if compile_result["success"] == False:
            print("Failed to compile " + class_name)
            print(pred_java)
            print(compile_result["error"])
            result_dict["pass_rate"] = 0.0
            continue
        
        num_compiled += 1

        # run test code
        pass_rate = java_utils.evosuite_compile_and_run_test(
            d["class_name"],
            compile_result["class_file"],
            d["java_test"],
            d["java_scaffold"],
        )

        result_dict["pass_rate"] = pass_rate

        if pass_rate == 1.0:
            num_correct += 1
        
        print(f"Compiled: {num_compiled}/{num_total} ({num_compiled/num_total})%, Correct: {num_correct}/{num_total} ({num_correct/num_total})%")

        with open(args.output_file, "a") as f:
            f.write(json.dumps(result_dict) + "\n")

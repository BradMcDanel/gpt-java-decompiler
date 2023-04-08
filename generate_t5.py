import argparse
import json
import difflib
import time

from transformers import AutoTokenizer, T5ForConditionalGeneration
import split_java
import java_utils

BATCH_SIZE = 4


def generate(model, tokenizer, inputs):
    """
    Split inputs into batches and generate outputs.
    """
    outputs = []
    for i in range(0, len(inputs), BATCH_SIZE):
        batch = inputs[i:i + BATCH_SIZE]
        input_ids = tokenizer(batch, return_tensors="pt", padding=True).input_ids
        input_ids = input_ids.cuda()
        generated_ids = model.generate(
            input_ids,
            max_length=512,
            num_beams=1,
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
    args = parser.parse_args()

    data = []
    with open(args.input_file) as f:
        for line in f:
            data.append(json.loads(line))

    model = T5ForConditionalGeneration.from_pretrained(args.model_path)
    tokenizer = AutoTokenizer.from_pretrained("Salesforce/codet5-base")
    model = model.cuda()
    model = model.half()

    correct = 0
    total = 0
    idx = 0
    class_idx = 0
    java_output = []
    for sample, d in enumerate(data):
        java = d["Gold"]["java_source"]
        jasm = d["Gold"]["jasm_code"]
        methods = split_java.get_jasm_methods(d["Gold"])

        start_time = time.time()
        pred_java_methods = generate(model, tokenizer, methods)
        end_time = time.time()
        decomp_time = end_time - start_time
        print("took:", decomp_time)

        for i, method in enumerate(pred_java_methods):
            if "<|static|> {" in method:
                pred_java_methods[i] = postprocess_clinit(method)

        pred_java = split_java.merge_java_methods(pred_java_methods)

        class_name = java_utils.get_class_name(pred_java)
        try:
            pred_byte_code = java_utils.compile_str(class_name, pred_java)
            did_compile = True
        except Exception as e:
            pred_byte_code = None
            did_compile = False

        if pred_byte_code is None:
            print(f"{class_idx}: failed to compile")
            pass_rate = 0
        else:
            pass_rate = java_utils.evosuite_compile_and_run_test(
                class_name,
                pred_byte_code,
                d["Gold"]["test"],
                d["Gold"]["scaffold"],
            )

            if pass_rate >= 0.999:
                correct += 1
            
        print(f"Pass Rate: {correct} / {sample+1} ({correct/(sample+1)})")

        # clone d
        output_data = {}
        for k, v in d.items():
            output_data[k] = v

        output_data["neural"] = {
                "pass_rate": pass_rate,
                "java_source": pred_java,
                "decomp_time": decomp_time,
                "compile": did_compile,
        }

        with open(args.output_file, "a") as fp:
            fp.write(json.dumps(output_data) + "\n")

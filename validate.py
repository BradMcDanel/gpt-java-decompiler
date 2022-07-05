import argparse
import os
import json

from transformers import AutoTokenizer, AutoModelForCausalLM

import prompts
import java_utils

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

for i, prompt in enumerate(samples):
    sample_data = data[i]
    input_ids = tokenizer(prompt, return_tensors="pt").input_ids.to("cuda")

    # truncate to max length
    input_ids = input_ids[:, -2048:]
    input_len = input_ids.shape[1]

    max_length = min(input_len + 768, 2048)

    generated_ids = model.generate(
        input_ids,
        max_length=max_length,
        pad_token_id=tokenizer.eos_token_id,
    )
    output = tokenizer.decode(generated_ids[0, input_len:], skip_special_tokens=True)

    # if '</JAVA>' in output, then cut off the end
    if '</JAVA>' in output:
        output = output[:output.index('</JAVA>')]

    pass_rate = jasm_to_java_test(sample_data, output)
    print(pass_rate)
    print(output)

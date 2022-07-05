import argparse
import os
import json

from transformers import AutoTokenizer, AutoModelForCausalLM

import java_utils

if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-name", type=str, required=True, help="Model name")
    parser.add_argument("--data-dir", type=str, required=True, help="Data directory")
    parser.add_argument("--output-path", type=str, required=True, help="Output path")
    args = parser.parse_args()

# load data
test_path = os.path.join(args.data_dir, "test.json")
data = []
with open(test_path, 'r') as f:
    for line in f:
        data.append(json.loads(line))


prompts = []
for i in range(len(data)):
    text = "<JAVA>\n" + data[i]["java_source"] + "\n</JAVA>\n<JASM>"
    prompts.append(text)

tokenizer = AutoTokenizer.from_pretrained(args.model_name)
model = AutoModelForCausalLM.from_pretrained(args.model_name)
model = model.to("cuda")

for i, prompt in enumerate(prompts):
    sample_data = data[i]
    input_ids = tokenizer(prompt, return_tensors="pt").input_ids.to("cuda")

    # truncate to max length
    input_ids = input_ids[:, -2048:]
    input_len = input_ids.shape[1]

    max_length = min(input_len + 1500, 2048)

    generated_ids = model.generate(input_ids, max_length=max_length, pad_token_id=tokenizer.eos_token_id)
    jasm = tokenizer.decode(generated_ids[0, input_len:], skip_special_tokens=True)
    # remove <JASM> and </JASM>
    jasm = jasm.replace("<JASM>", "").replace("</JASM>", "")
    # if ".end class", trim to it
    idx = jasm.find(".end class")
    idx += len(".end class")
    if idx != -1:
        jasm = jasm[:idx]

    print(jasm)

    byte_code = java_utils.assemble_str(sample_data["class_name"], jasm)
    if byte_code is None:
        print("Error assembling byte code", i)
        continue

    pass_rate = java_utils.evosuite_compile_and_run_test(
        sample_data["class_name"],
        byte_code,
        sample_data["java_test"],
        sample_data["java_scaffold"],
    )

    if pass_rate >= 1.0:
        with open(args.output_path, "a") as f:
            f.write(json.dumps(sample_data) + "\n")

    print(i, pass_rate)

import argparse
import os
import json

from transformers import AutoTokenizer, AutoModelForCausalLM

if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-name", type=str, required=True, help="Model name")
    parser.add_argument("--data-dir", type=str, required=True, help="Data directory")
    args = parser.parse_args()

# load data
test_path = os.path.join(args.data_dir, "test.json")
data = []
with open(test_path, 'r') as f:
    for line in f:
        data.append(json.loads(line))


prompts = []
for i in range(len(data)):
    text = "<JAVA>\n" + data[i]["java_source"] + "\n</Java>\n<JASM>"
    prompts.append(text)

tokenizer = AutoTokenizer.from_pretrained(args.model_name)
model = AutoModelForCausalLM.from_pretrained(args.model_name)
model = model.to("cuda")

for prompt in prompts:
    input_ids = tokenizer(prompt, return_tensors="pt").input_ids.to("cuda")
    generated_ids = model.generate(input_ids, max_length=128)
    output = tokenizer.decode(generated_ids[0])
    print("Output:", output)

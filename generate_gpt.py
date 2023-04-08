import argparse
import json
import os
import openai
openai.api_key = os.getenv("OPENAI_API_KEY")

import openai

BATCH_SIZE = 1

def merge_java_methods(java_methods):
    """
    Converts a list of java methods into a single string. The first method is 
    a special case because it is the class header. The ending curly brace of
    the class header is removed and replaced with a newline.
    """
    merged_java = ""
    indent = "  "
    for i, method in enumerate(java_methods):
        if i == 0:
            merged_java += method[:-1] + "\n"
        else:
            # add indentation to each line of method
            method = "\n".join([indent + line for line in method.split("\n")])
            merged_java += method + "\n\n"

    merged_java = merged_java.strip() + "\n"
    merged_java += "}\n"

    return merged_java



def generate(args, inputs):
    """
    Split inputs into batches and generate outputs.
    """
    outputs = []
    for input_method in inputs:
        print(input_method)
        completion = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "user", "content": "Hello!"}
            ]
        )

        print(completion.choices[0].message)
        assert False

    return outputs

def strip_unnecessary_info(java_assembly_code):
    lines = java_assembly_code.split('\n')
    stripped_lines = []
    skip = False
    for line in lines:
        line = line.strip()
        if line == ".linenumbertable":
            skip = True
            continue
        if line == ".end linenumbertable":
            skip = False
            continue
        if skip:
            continue

        if line.startswith('.'):
            line = line.lstrip('.')
        if line.startswith('L'):
            line = line.split(':', 1)[-1].lstrip()
        stripped_lines.append(line)
    return '\n'.join(stripped_lines)



if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-file", type=str, required=True, help="data file")
    parser.add_argument("--output-file", type=str, required=True, help="output file")
    args = parser.parse_args()

    data = []
    with open(args.input_file) as f:
        for line in f:
            data.append(json.loads(line))

    jasm = strip_unnecessary_info(data[0]["jasm_code"])
    print(jasm)
    
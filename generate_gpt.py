import argparse
from typing import List
import json
import os
import tiktoken
import openai
openai.api_key = os.getenv("OPENAI_API_KEY")

import openai

import java_utils

tokenizers = {
    "gpt-4": tiktoken.encoding_for_model("gpt-4"),
    "gpt-3.5-turbo": tiktoken.encoding_for_model("gpt-3.5-turbo"),
}

def get_num_tokens(s, engine="gpt-3.5-turbo"):
    return len(tokenizers[engine].encode(s))
    

def initial_generate(jasm_code):
    """
    Split inputs into batches and generate outputs.
    """
    user_message = f"Convert the following Java assembly code to Java code. Please reply with Java code only. The code block should be java -- ```java ... ```.\n{jasm_code}"

    messages = [
        {"role": "system", "content": "You are a helpful assistant that is an expert at generating valid Java code from an Java assembly representation."},
        {"role": "user", "content": user_message},
    ]
    completion = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=messages,
    )

    return completion.choices[0].message["content"].strip()

def find_used_labels(assembly_code):
    label_count = {}
    used_labels = []
    lines = assembly_code.split('\n')
    
    for line in lines:
        parts = line.split()
        for part in parts:
            # remove trailing ':' if present
            if part.endswith(':'):
                part = part[:-1]

            # if the part starts with L and rest is number, it's a label
            if part.startswith('L') and part[1:].isdigit():
                label_count[part] = label_count.get(part, 0) + 1

    for label, count in label_count.items():
        if count >= 2:
            used_labels.append(label)

    return used_labels


def strip_unnecessary_info(java_assembly_code):
    lines = java_assembly_code.split('\n')
    stripped_lines = []
    used_labels = []

    for i, line in enumerate(lines):
        line = line.strip()

        if line.startswith('.method'):
            # find next endmethod
            for j in range(i, len(lines)):
                if lines[j].startswith('.end method'):
                    break
            used_labels = find_used_labels('\n'.join(lines[i:j]))

        if line.startswith('.'):
            line = line.lstrip('.')
        if line.startswith('L'):
            label = line.split()[0][:-1]
            if label not in used_labels:
                line = line.split(':', 1)[-1].lstrip()
        if line.endswith(';'):
            line = line.rstrip(';')
        if not line:
            continue
        stripped_lines.append(line)
    return '\n'.join(stripped_lines)


def remove_linenumber_table(java_assembly_code):
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
        stripped_lines.append(line)
    return '\n'.join(stripped_lines)


def split_java_assembly_code(java_assembly_code: str, max_tokens: int) -> List[str]:
    def is_header_line(line):
        return not line.startswith('method') and not line.startswith('end method') and not line.startswith('code') and not line.startswith('end code')
    
    header_lines = []
    method_lines = []
    in_method = False
    chunks = []

    for line in java_assembly_code.split('\n'):
        if is_header_line(line) and not in_method:
            header_lines.append(line)
        else:
            if line.startswith('method'):
                in_method = True
                method_lines.append(line)
            elif line.startswith('end method'):
                in_method = False
                method_lines.append(line)
                
                method_code = '\n'.join(method_lines)
                if get_num_tokens('\n'.join(header_lines + method_lines)) > max_tokens:
                    if method_lines:
                        chunks.append('\n'.join(header_lines + method_lines))
                    method_lines = []
                else:
                    chunks.append('\n'.join(header_lines + method_lines))
                    method_lines = []
            else:
                if in_method:
                    method_lines.append(line)

    if method_lines:
        chunks.append('\n'.join(header_lines + method_lines))

    return chunks



def strip_java_codeblock(java_code):
    # remove the heading ```java and the ending ```
    java_code = java_code.split("```java")[1].split("```")[0]
    return java_code


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-file", type=str, required=True, help="data file")
    parser.add_argument("--output-file", type=str, required=True, help="output file")
    args = parser.parse_args()

    data = []
    with open(args.input_file) as f:
        for line in f:
            data.append(json.loads(line))

    for i, d in enumerate(data):
        if i < 3:
            continue
        if i == 100:
            break
        jasm = d["jasm_code"]
        jasm = remove_linenumber_table(jasm)
        jasm = strip_unnecessary_info(jasm)

        num_tokens = get_num_tokens(jasm, engine="gpt-3.5-turbo")
        if num_tokens > 1000:
            print(jasm)
            assert False
        # chunks = split_java_assembly_code(jasm, max_tokens=1024)
        continue

        pred_java = initial_generate(jasm)
        pred_java = strip_java_codeblock(pred_java)

        class_name = java_utils.get_class_name(pred_java)
        pred_byte_code = java_utils.compile_str(class_name, pred_java)

        # try to compile
        if pred_byte_code is None:
            print("Failed to compile")
            exit(1)

        # run test code
        pass_rate = java_utils.evosuite_compile_and_run_test(
            d["class_name"],
            pred_byte_code,
            d["java_test"],
            d["java_scaffold"],
        )

        print(f'pass rate: {pass_rate} for {i}th sample')

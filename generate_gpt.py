import argparse
from typing import List
import json
import os
import re
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
    

def gen_init_header(jasm_code):
    messages = [
        {"role": "system", "content": "You are a helpful assistant that is an expert at generating valid Java code from an Java assembly representation. Your goal is to generate a header for the java class."},
    ]
    user_message = f"""
***INSTRUCTIONS - GENERATE JAVA HEADER***
- Please generate just the java header
  - class name
  - imports
  - field declarations/initializations
- Use best practices for naming
- Implement ONLY constructors. These are denoted "method public <init> : ..."
- Derive needed imports from **REQUIRED IMPORTS** section below the Java Assembly.
  - You must import exactly what is listed in the **REQUIRED IMPORTS** section.
  - This should be copied and pasted as-is with import.
- Do not generate any methods or @Override any methods
- Each "method" block corresponds to a constructor
  - You are not allowed to generate any methods than those in the java assembly
- Do not generate any comments
- Prefer short types (e.g., String instead of java.lang.String)
- Your reply must be entirely valid Java code. Do not write any text outside the codeblock.
- Do not use any java assembly instructions (e.g., ldc, invokevirtual, aload, etc.)
- Do not write any text outside the codeblock.
- Your code block response should be formatted as ```java\n ...Java Code...\n```\n ***ASSEMBLY CODE***\n{jasm_code}.
"""
    # Initial:
    user_message = user_message.strip()
    messages.append({"role": "user", "content": user_message})
    completion = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=messages)
    response = completion.choices[0].message
    print("INITIAL:")
    print(response["content"])
    init_java_header = response["content"]
    messages.append(response)

    # Critique:
    user_message = f"""
- Please critique your prior generation based on how well it adheres to the instructions.
  - Provide a list of detected issues and steps on how to fix them.
- If there are no issues detected with the prior generation, then your entire response must be only: OK
  - Adding any other text will be considered a and will break the evaluation.
""".strip()
    messages.append({"role": "user", "content": user_message})
    completion = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=messages)
    response = completion.choices[0].message
    print("CRITIQUE:")
    print(response["content"])
    messages.append(response)

    # Fix:
    user_message = f"""
- Please fix your prior generation based on the critique.
- If no fix is needed, your entire response must be only: OK
  - Adding any other text will be considered a and will break the evaluation.
""".strip()
    messages.append({"role": "user", "content": user_message})
    completion = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=messages)
    response = completion.choices[0].message
    print("FIX:")
    print(response["content"])

    # check if there was a fix
    content = response["content"].strip()
    if len(content) < 200 and "ok" in content.lower():
        print("No fix needed")
        return init_java_header
    else:
        print("Fix needed")
        return content  


def gen_init_method(jasm_code):
    messages = [
        {"role": "system", "content": "You are a helpful assistant that is an expert at generating valid Java code from an Java assembly representation."},
    ]
    user_message = f"""
***INSTRUCTIONS - GENERATE JAVA HEADER***
- Please generate just the java method for the corresponding java assembly
  - Only generate code for the method for the assembly below ***METHOD***.
- Do not generate the entire class
- Do not import any packages
- Do not create any fields
- Do not indent the method body
- The first line of the method should be the method signature
  - Do not indent the method signature
- Add JAVADOC comments to the method
  - Use clear, understandable variable names when you must guess the name
- You should not use any java assembly instructions in your reply (e.g., ldc, invokevirtual, aload, etc.)
- Do not use any java assembly instructions (e.g., ldc, invokevirtual, aload, etc.)
- Do not write any text outside the codeblock.
- Your code block response should be formatted as ```java\n ...Java Code...\n```\n ***ASSEMBLY CODE***\n{jasm_code}.
"""
    user_message = user_message.strip()

    # Initial:
    messages.append({"role": "user", "content": user_message})
    completion = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=messages)
    response = completion.choices[0].message
    print("INITIAL:")
    print(response["content"])
    init_java_method = response["content"].strip()
    messages.append(response)

    # Critique:
    user_message = f"""
- Please critique your prior generation based on how well it adheres to the instructions.
  - Provide a list of detected issues and steps on how to fix them.
- If there are no issues detected with the prior generation, then your entire response must be only: OK
  - Adding any other text will be considered a and will break the evaluation.
""".strip()
    messages.append({"role": "user", "content": user_message})
    completion = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=messages)
    response = completion.choices[0].message
    print("CRITIQUE:")
    print(response["content"])
    messages.append(response)

    # Fix:
    user_message = f"""
- Please fix your prior generation based on the critique.
- If no fix is needed, your entire response must be only: OK
  - Adding any other text will be considered a and will break the evaluation.
""".strip()
    messages.append({"role": "user", "content": user_message})
    completion = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=messages)
    response = completion.choices[0].message
    print("FIX:")
    print(response["content"])

    # check if there was a fix
    content = response["content"].strip()
    if len(content) < 200 and "ok" in content.lower():
        print("No fix needed")
        return init_java_method
    else:
        print("Fix needed")
        return content  


def extract_class_types(assembly_code: str) -> List[str]:
    lines = assembly_code.split('\n')
    java_classes = set()

    for line in lines:
        tokens = line.split()
        for token in tokens:
            if "java/" in token:
                # remove before java/ (but keep java/)
                token = token[token.index("java/"):]
                # remove ; and after if present
                if ';' in token:
                    token = token[:token.index(';')]
                
                java_classes.add(token)
            
    # filter out "java/lang/*" classes
    java_classes = [c for c in java_classes if not c.startswith("java/lang/")]

    # sort alphabetically
    java_classes.sort()

    return list(java_classes)



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
        stripped_lines.append(line)

    stripped_java_assembly_code = '\n'.join(stripped_lines).strip()
    return stripped_java_assembly_code


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


def extract_assembly_header(java_assembly_code: str) -> str:
    def is_header_line(line):
        return not line.startswith('method') and not line.startswith('end method') \
               and not line.startswith('code') and not line.startswith('end code')

    header_lines = []
    in_method = False
    in_init_or_clinit = False

    for line in java_assembly_code.split('\n'):
        if not in_init_or_clinit and not in_method:
            in_init_or_clinit = ('<clinit>' in line) or ('<init>' in line)

        if in_init_or_clinit: # we want to add lines and set to false on end method
            header_lines.append(line)
            if line.startswith('end method'):
                in_init_or_clinit = False
        elif is_header_line(line) and not in_method:
            header_lines.append(line)
        else:
            if line.startswith('method'):
                in_method = True
            elif line.startswith('end method'):
                in_method = False

    class_types = extract_class_types(java_assembly_code)

    # add method signatures
    header_lines = '\n'.join(header_lines).strip()

    # Any newlines that are more than 2 in a row are replaced with 2 newlines
    header_lines = re.sub(r'\n{3,}', '\n\n', header_lines)


    if len(class_types) > 0:
        header_lines += '\n\n**REQUIRED IMPORTS**'
        header_lines += '\n' + '\n'.join([f'{class_type}' for class_type in class_types])
    else:
        header_lines += '\n\n**REQUIRED IMPORTS**'
        header_lines += '\nDO NOT IMPORT ANYTHING!\n'

    return header_lines


def split_java_assembly_code(java_assembly_code: str) -> List[str]:
    header = extract_assembly_header(java_assembly_code)
    invalid_words = ["<init>", "<clinit>", " bridge ", " synthetic "]
    method_lines = []
    in_method = False
    chunks = []

    def chunk_fmt(header, method_lines):
        return "***HEADER***\n" + header + '\n***METHOD***\n' + '\n'.join(method_lines)

    for line in java_assembly_code.split('\n'):
        if line.startswith('method') and not any(word in line for word in invalid_words):
            in_method = True
            method_lines.append(line)
        elif line.startswith('end method') and in_method:
            in_method = False
            method_lines.append(line)

            if method_lines:
                chunks.append(chunk_fmt(header, method_lines))
                method_lines = []
        else:
            if in_method:
                method_lines.append(line)

    if method_lines:
        chunks.append(chunk_fmt(header, method_lines))

    return chunks


def strip_java_codeblock(java_code):
    # find the first ```java in the code block
    first_java_codeblock = java_code.find("```java")

    # if not found, use ``` instead
    if first_java_codeblock == -1:
        first_java_codeblock = java_code.find("```") + 3    
    else:
        first_java_codeblock += 7
    
    # now, find the final ``` in the code block
    # if not found, use the end of the string
    last_java_codeblock = java_code.rfind("```")
    if last_java_codeblock == -1:
        last_java_codeblock = len(java_code) - 1
    else:
        last_java_codeblock -= 1
    
    # now, extract the code between the first and last ```java
    java_code = java_code[first_java_codeblock:last_java_codeblock]

    return java_code


def combine_java_class(header: str, methods: List[str]) -> str:
    header_code = strip_java_codeblock(header)
    class_name = header_code.split('class')[1].split()[0].strip()
    
    method_code_blocks = []
    for method in methods:
        method_code = strip_java_codeblock(method)
        # indent the method code by 4 spaces
        method_code = method_code.strip()
        method_code = '\n'.join(['    ' + line for line in method_code.split('\n')])
        method_code = method_code.replace('<init>', class_name)
        method_code_blocks.append(method_code)
    
    # Insert the methods before the last closing brace of the header
    combined_class_code = header_code[:header_code.rfind('}')] + \
                          '\n\n'.join(method_code_blocks) + '\n' + \
                          header_code[header_code.rfind('}'):]
    
    return combined_class_code


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-file", type=str, required=True, help="data file")
    parser.add_argument("--output-file", type=str, required=True, help="output file")
    args = parser.parse_args()

    data = []
    with open(args.input_file) as f:
        for line in f:
            data.append(json.loads(line))

    num_compiled, num_correct, num_total = 0, 0, 0
    for i, d in enumerate(data):
        if i < 0: continue
        if i == 20:
            break
        num_total += 1

        jasm = d["jasm_code"]
        jasm = remove_linenumber_table(jasm)
        jasm = strip_unnecessary_info(jasm)

        num_tokens = get_num_tokens(jasm, engine="gpt-3.5-turbo")
        header_jasm = extract_assembly_header(jasm)
        header_java = gen_init_header(header_jasm)
        # print(header_jasm)
        # print(header_java)
        # assert False

        methods_jasm = split_java_assembly_code(jasm)
        methods_java = []
        for method_jasm in methods_jasm:
            method_java = gen_init_method(method_jasm)
            methods_java.append(method_java)
            # improved_method_java = gen_critique_method(method_jasm, method_java, header_java)
            # print(improved_method_java)
            # methods_java.append(improved_method_java)
        
        pred_java = combine_java_class(header_java, methods_java)
        print(pred_java)

        class_name = java_utils.get_class_name(pred_java)
        compile_result = java_utils.compile_str(class_name, pred_java)

        # try to compile
        if compile_result["success"] == False:
            print("Failed to compile " + class_name)
            print(compile_result["error"])
            continue
    
        num_compiled += 1

        # run test code
        pass_rate = java_utils.evosuite_compile_and_run_test(
            d["class_name"],
            compile_result["class_file"],
            d["java_test"],
            d["java_scaffold"],
        )

        if pass_rate == 1.0:
            num_correct += 1
        
        print(f"Compiled: {num_compiled}/{num_total} ({num_compiled/num_total})%, Correct: {num_correct}/{num_total} ({num_correct/num_total})%")

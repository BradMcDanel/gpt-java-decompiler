import argparse
from typing import List
import json
import os
import re
import tiktoken
import gpt_model

import java_utils

tokenizers = {
    "gpt-4": tiktoken.encoding_for_model("gpt-4"),
    "gpt-3.5-turbo": tiktoken.encoding_for_model("gpt-3.5-turbo"),
}

def get_num_tokens(s, engine="gpt-3.5-turbo"):
    return len(tokenizers[engine].encode(s))
    

def gen_init_header(args, jasm_code):
    messages = [
        {"role": "system", "content": "You are a helpful assistant that is an expert at generating valid Java code from an Java assembly representation. Your goal is to generate a header for the java class."},
    ]
    user_message = """***INSTRUCTIONS - GENERATE JAVA HEADER***
Help me generate syntactically valid Java code from the Java assembly below.
- Please generate just the java header, which contains:
  - class name
  - imports
  - field declarations/initializations
- Use best practices for naming
- Implement ONLY constructors. These are denoted "method public <init> : ..."
- Derive needed imports from **REQUIRED IMPORTS** section below the Java Assembly.
  - You must import exactly what is listed in the **REQUIRED IMPORTS** section.
  - This should be copied and pasted as-is with import.
- Do not generate any methods or @Override any methods
- Prefer short types (e.g., String instead of java.lang.String)
- Your reply must be entirely valid Java code. Do not write any text outside the codeblock.
- Do not use any java assembly instructions (e.g., ldc, invokevirtual, aload, etc.)
Example Java Header Output:
```java
public class ClassName {
    protected String a;
    private int b;
    public ClassName(String a, int b) {
        this.a = a;
        this.b = b;
    }
}
```

***JAVA ASSEMBLY CODE***
""" + jasm_code + "\nYour must respond in a single java codeblock (```java ... ```)\n"
    messages.append({"role": "user", "content": user_message})
    completion = gpt_model.chatgpt(messages=messages, model=args.model_type)
    return completion[0]

def gen_init_method(args, jasm_code):
    messages = [
        {"role": "system", "content": "You are a helpful assistant that is an expert at generating valid Java code from an Java assembly representation."},
    ]
    user_message = """***INSTRUCTIONS - GENERATE JAVA METHOD***
Help me generate a syntactically valid Java method from the Java assembly below.
- Please generate just the java method for the corresponding java assembly
  - Specifically, only generate code for the method for the assembly below ***METHOD***.
- You must not generate the entire class
- You must not import any packages
- You must not create any fields
- You must not indent the method body
- The first line of the method must be the method signature
  - You must not indent the method signature
- You must add JAVADOC comments to the method
  - Use clear, understandable variable names when you must guess the name
- You must not use any java assembly instructions in your reply (e.g., ldc, invokevirtual, aload, etc.)
- You must not write any text outside the java codeblock.
Example Java Method Output:
```java
/**
* This is a javadoc comment.
* @param a description of a
* @param b description of b
* @return description of return value
*/
public int methodName(int a, int b) {
    return a + b;
}
```

***JAVA ASSEMBLY CODE***
""" + jasm_code + "\nYour must respond in a single java codeblock (```java ... ```)\n"

    messages.append({"role": "user", "content": user_message})
    completion = gpt_model.chatgpt(messages=messages, model=args.model_type)
    return completion[0]

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
    print(header_code)
    class_name = header_code.split('class')[1].split()[0].strip()
    
    method_code_blocks = []
    for method in methods:
        method_code = strip_java_codeblock(method)
        print(method_code)
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
    parser.add_argument("--model-type", type=str, default="gpt-3.5-turbo")
    args = parser.parse_args()

    data = []
    with open(args.input_file) as f:
        for line in f:
            data.append(json.loads(line))
    # clear contents of output file if it exists
    with open(args.output_file, 'w') as f:
        f.write('')
        
    num_compiled, num_correct, num_total = 0, 0, 0
    for i, d in enumerate(data):
        result_dict = {}
        num_total += 1

        result_dict["class_name"] = d["class_name"]
        result_dict["class_idx"] = d["class_idx"]
        jasm = d["jasm_code"]
        jasm = remove_linenumber_table(jasm)
        jasm = strip_unnecessary_info(jasm)

        num_tokens = get_num_tokens(jasm, engine="gpt-3.5-turbo")
        header_jasm = extract_assembly_header(jasm)
        header_java = gen_init_header(args, header_jasm)

        methods_jasm = split_java_assembly_code(jasm)
        methods_java = []
        for method_jasm in methods_jasm:
            method_java = gen_init_method(args, method_jasm)
            methods_java.append(method_java)
        
        pred_java = combine_java_class(header_java, methods_java)
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

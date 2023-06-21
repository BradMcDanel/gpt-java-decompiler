import argparse
from typing import List
import json
import re
import tiktoken
import gpt_model
from collections import deque
import re

import java_utils

RESERVED_TOKENS = 1500

tokenizers = {
    "gpt-4": tiktoken.encoding_for_model("gpt-4"),
    "gpt-3.5-turbo": tiktoken.encoding_for_model("gpt-3.5-turbo"),
    "gpt-3.5-turbo-16k": tiktoken.encoding_for_model("gpt-3.5-turbo"),
}

model_token_limits = {
    "gpt-4": 8096,
    "gpt-3.5-turbo": 4096,
    "gpt-3.5-turbo-16k": 16384,
}

def remove_codeblock(s):
    pattern = r'^```(?:\w*\n)?(.*)```$'
    match = re.search(pattern, s, re.DOTALL)
    return match.group(1) if match else s

def remove_excess_tokens(messages, engine, reserved_tokens):
    model_token_limit = model_token_limits[engine]
    # Calculate total tokens in current conversation
    total_tokens = sum([len(tokenizers[engine].encode(msg['content'])) for msg in messages])
    total_tokens += reserved_tokens

    # Check if total tokens exceed model limit
    if total_tokens > model_token_limit:
        excess_tokens = total_tokens - model_token_limit

        # Start deleting tokens from the beginning until excess is covered
        for msg in messages:
            if msg['role'] == 'user':
                tokens = deque(tokenizers[engine].encode(msg['content']))

                while tokens and excess_tokens > 0:
                    tokens.popleft() # Remove token from the left
                    excess_tokens -= 1

                # Re-encode message content after deletion
                msg['content'] = tokenizers[engine].decode(list(tokens))

                # If all excess tokens have been removed, break the loop
                if excess_tokens <= 0:
                    break

    return messages

with open("prompts/sample.java") as f:
    SAMPLE_JAVA = f.read()

with open("prompts/sample.jasm") as f:
    SAMPLE_JASM = f.read()

with open("prompts/sample_test.java") as f:
    SAMPLE_JAVA_TEST = f.read()

def get_num_tokens(s, engine="gpt-3.5-turbo"):
    return len(tokenizers[engine].encode(s))
    
def initial_messages(jasm_code, java_test):
    messages = [
        {"role": "system", "content": "You are an expert computer system that generates valid Java code from an Java assembly representation. You have perfect knowledge of Java and can achieve 100% accuracy."},
    ]
    user_message = f"""**TASK**: Convert Java Assembly to a Complete Java Class

Your task is to transform the provided Java assembly and corresponding generated Java tests into a complete, syntactically valid Java class. 

Please follow the guidelines carefully:

1. **Complete Class**: Ensure your result is a complete Java class, with a properly defined class structure.
2. **Package Imports**: Incorporate any necessary package imports at the beginning of the class. If you're unsure, you may import any package you deem necessary.
3. **Javadoc Comments**: Every method in your class must be preceded by clear and concise Javadoc comments, outlining the method's purpose, parameters, and return values (if any).
4. **Variable Naming**: In cases where you need to infer variable names, make sure they are meaningful and self-explanatory, adhering to Java's naming conventions.
5. **Avoid Java Assembly Instructions**: Your output should be devoid of any Java assembly instructions such as ldc, invokevirtual, aload, etc. Remember, you're converting assembly code to high-level Java code.
6. **Valid Java Code**: Your final output should be a valid plain text Java code, adhering strictly to Java's syntax and semantic rules. It must be a complete, correct, and executable Java class.
7. **Edge Cases**: Your code must be able to handle edge cases such as empty input, null input, etc. appropriately. Your code will be tested with EvoSuite testing frameworks to ensure it matches exactly the provided Java assembly code for all possible inputs.

**Additional Information**:

- You can only respond with code as it will be compiled directly. Any written text will lead to a compilation error.
- Always initialize variables where necessary.
- Handle exceptions appropriately with try-catch blocks to avoid any unexpected runtime errors.
- Ensure appropriate access specifiers (public, private, protected) are used where necessary.
- Make sure the main method is present if the class is intended to be executable.
- Regularly format and indent your code for better readability.
- You must always respond in plaintext. Do not respond in a codeblock.
- Do not generate any test code as it is already provided. Simply write the class code.

**Example**:
Example Java Assembly Input:
{SAMPLE_JASM}

Example Java Test Input:
{SAMPLE_JAVA_TEST}

Example Java Method Output:
{SAMPLE_JAVA}

***INPUT JAVA ASSEMBLY CODE***
{jasm_code}

***INPUT JAVA TEST CODE***
{java_test}

***OUTPUT JAVA CLASS***
"""
    messages.append({"role": "user", "content": user_message})
    return messages

def compile_error_message(error_message):
    user_message = f"""**Compile Error**: {error_message}

**Instructions**:
 - Please rewrite the entire java program, making sure to fix the error.
 - You can only respond with code as it will be compiled directly. Any written text will lead to a compilation error.
"""
    return {"role": "user", "content": user_message}

def test_error_message(error_message):
    user_message = f"""**Test Error**: {error_message}

**Instructions**:
 - The program successfully compiled, but failed to pass at least one test case.
 - Please analyze the test error and rewrite the entire java program, making sure to fix the error(s).
 - Look carefully at the INPUT JAVA TEST CODE provided earlier to attempt and diagnose the error.
 - Critically, you are not allowed to add or modify the testing code. You are not trying to fix the test code. Instead, you are trying to fix the program so that it passes the tests.
 - Your response should be of the form:
 Analysis...
```java
class MyClass {{
   ...
}}
```
"""
    return {"role": "user", "content": user_message}


def generate_java(args, messages):
    messages = remove_excess_tokens(messages, args.model_type, RESERVED_TOKENS)
    completion = gpt_model.chatgpt(messages=messages, model=args.model_type)
    if completion is None:
        return None
    content = completion[0]
    content = remove_codeblock(content)
    print(content)
    messages.append({"role": "assistant", "content": content})
    return messages

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
        java_test = d["java_test"]

        messages = initial_messages(jasm, java_test)
        attempts = 0
        failed = False
        while attempts < 2:
            messages = generate_java(args, messages)
            if messages is None:
                failed = True
                break

            pred_java = messages[-1]["content"]
            class_name = java_utils.get_class_name(pred_java)
            compile_result = java_utils.compile_str(class_name, pred_java)

            if compile_result["success"]:
                break
            else:
                print("Failed to compile " + class_name + " on attempt " + str(attempts))
                messages.append(compile_error_message(compile_result["error"]))

            attempts += 1

        # early failure
        if failed:
            print("Failed to generate java code for " + d["class_name"])
            result_dict = {
                "class_name": d["class_name"],
                "class_idx": d["class_idx"],
                "java_source": None,
                "compile": False,
                "pass_rate": 0.0,
            }
            with open(args.output_file, 'a') as f:
                f.write(json.dumps(result_dict) + '\n')
            continue


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


        attempts = 0
        failed = False
        while attempts < 2:
            # run test code
            test_results = java_utils.evosuite_compile_and_run_test(
                d["class_name"],
                compile_result["class_file"],
                d["java_test"],
                d["java_scaffold"],
            )
            if test_results["pass_rate"] == 1.0:
                break
            else:
                print("Failed to pass test cases for " + class_name + " on attempt " + str(attempts))
                print(test_results["error"])
                messages.append(test_error_message(test_results["error"]))
                messages = generate_java(args, messages)
                if messages is None:
                    break
                pred_java = messages[-1]["content"]
                class_name = java_utils.get_class_name(pred_java)
                compile_result = java_utils.compile_str(class_name, pred_java)
                if compile_result["success"] == False:
                    failed = True
                    break

            attempts += 1
        
        if failed:
            print("Failed to generate java code for " + d["class_name"])
            result_dict = {
                "class_name": d["class_name"],
                "class_idx": d["class_idx"],
                "java_source": None,
                "compile": False,
                "pass_rate": 0.0,
            }
            with open(args.output_file, 'a') as f:
                f.write(json.dumps(result_dict) + '\n')
            continue


        result_dict["pass_rate"] = test_results["pass_rate"]

        if test_results["pass_rate"] == 1.0:
            num_correct += 1
        
        print(f"Compiled: {num_compiled}/{num_total} ({num_compiled/num_total})%, Correct: {num_correct}/{num_total} ({num_correct/num_total})%")

        with open(args.output_file, "a") as f:
            f.write(json.dumps(result_dict) + "\n")

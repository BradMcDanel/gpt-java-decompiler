import argparse
from typing import List
import json
import re
import tiktoken
import gpt_model
from collections import deque
import re
from concurrent.futures import ProcessPoolExecutor, as_completed

import java_utils

RESERVED_TOKENS = 1500

with open("prompts/sample.java") as f:
    SAMPLE_JAVA = f.read()

with open("prompts/sample.jasm") as f:
    SAMPLE_JASM = f.read()

with open("prompts/sample_test.java") as f:
    SAMPLE_JAVA_TEST = f.read()

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

def extract_codeblock(text):
    pattern = r'```(?:\w*\n)?(.*?)```'
    match = re.search(pattern, text, re.DOTALL)
    
    if match:
        return match.group(1).strip()
    else:
        return text

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



def get_num_tokens(s, engine="gpt-3.5-turbo"):
    return len(tokenizers[engine].encode(s))
    
def initial_messages(jasm_code, java_test):
    messages = [
        {"role": "system", "content": "You are an expert computer system that generates valid Java code from an Java assembly representation. You have perfect knowledge of Java and can achieve 100% accuracy."},
    ]
    user_message = f"""**TASK**: Convert Java Assembly to a Complete Java Class

Your task is to transform the provided Java assembly and corresponding generated Java tests into a complete, syntactically valid Java class. 

Please follow the guidelines carefully:

1. **Complete Class**: Ensure your result is a complete Java class, with a properly defined class structure. This can be spaced out across multiple messages if the class is extremely long. In this case, do not mention that you are doing so, simply assume the user will understand and will be able to piece together the class from the messages.
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
- You must not end the class early prior to all methods being defined.
 - Example: ... //other methods here ... }}
 - This breaks the class structure and will lead to a compilation error.
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

def compile_error_message(java_source, error_message):
    user_message = f"""
The following java code failed to compile. Please determine if it was (1) because the file was truncated or (2) because the code is invalid. Typically, a truncated error will have some description around "reached end of file while parsing" or something related to unclosed string, etc... An invalid error will have a more specific error message and the class will look complete.

***INPUT JAVA CODE***
{java_source}

***ERROR MESSAGE***
{error_message}

You must end your response with a codeblock containing either:
```
truncated
```

or 

```
invalid
```
"""
    return [
        {"role": "system", "content": "Your code failed to compile. Please determine if it was (1) because the file was truncated or (2) because the code is invalid."},
        {"role": "user", "content": user_message}
    ]

def gpt(args, messages):
    messages = remove_excess_tokens(messages, args.model_type, RESERVED_TOKENS)
    completion = gpt_model.chatgpt(messages=messages, model=args.model_type, temperature=args.temperature)
    if completion is None:
        return None
    content = completion[0]
    content = extract_codeblock(content)

    return {"role": "assistant", "content": content}

def extract_java_from_messages(messages):
    total_message = ""
    for message in messages:
        if message["role"] == "assistant":
            total_message += message["content"]

    return total_message

def generate_java_class(class_name, jasm_code, java_test, args):
    java_generation_messages = initial_messages(jasm_code, java_test)
    pred_java = ""
    curr_compile_attempt = 0
    while curr_compile_attempt < args.max_attempts:
        generation_response = gpt(args, java_generation_messages)
        if generation_response is None:
            curr_compile_attempt += 1
            continue

        pred_java += generation_response["content"]
        # print(pred_java)
        # print("===========")
    
        # try to compile
        compile_result = java_utils.compile_str(class_name, pred_java)

        # if compilation succeeded, return
        if compile_result["success"]:
            break

        # if compilation failed, debug source of error
        error_generation_messages = compile_error_message(pred_java, compile_result["error"])
        error_response = gpt(args, error_generation_messages)
    
        if error_response is None:
            curr_compile_attempt += 1
            continue
    
        error_response = error_response["content"]
        # print(compile_result["error"])
        # print(error_response)

        if "invalid" in error_response:
            # start over
            pred_java = ""
            curr_compile_attempt += 1
            continue
        elif "truncated" in error_response:
            java_generation_messages.append(generation_response)
            java_generation_messages.append({"role": "user", "content": "Please continue your response. Do not start over."})
            curr_compile_attempt += 1
            continue
        else:
            print("Unknown error response")
            pred_java = ""
            curr_compile_attempt += 1
            continue
    
    compile_attempt_results = [False if i < curr_compile_attempt else True for i in range(args.max_attempts)]
    return pred_java, compile_attempt_results


def test_java_class_driver(class_name, jasm, java_test, java_scaffold, args):
    curr_test_attempt = 0
    test_compile_results = []
    max_pass_rate = 0.0
    while curr_test_attempt < args.max_attempts:
        pred_java, compile_attempt_results = generate_java_class(class_name, jasm, java_test, args)
        if pred_java == "":
            curr_test_attempt += 1
            continue
        
        test_compile_results.append(compile_attempt_results)

        # Check if it ever compiled
        if not compile_attempt_results[-1]:
            curr_test_attempt += 1
            continue

        # Recompile to get class file
        compile_result = java_utils.compile_str(class_name, pred_java)
        if not compile_result["success"]:
            curr_test_attempt += 1
            continue

        # Run tests
        test_result = java_utils.evosuite_compile_and_run_test(
            class_name, 
            compile_result["class_file"], 
            java_test, 
            java_scaffold
        )

        max_pass_rate = max(max_pass_rate, test_result["pass_rate"])

        if test_result["pass_rate"] < 0.999:
            curr_test_attempt += 1
            continue
        else:
            break
    

    while len(test_compile_results) < args.max_attempts:
        test_compile_results.append([True for _ in range(args.max_attempts)])
    
    compile_and_test_results = []
    for i in range(len(test_compile_results)):
        test_attempt_passed = i >= curr_test_attempt
        compile_and_test_results.append((test_attempt_passed, test_compile_results[i]))

    return pred_java, compile_and_test_results, max_pass_rate

def process_data(d, args):
    # preprocessing
    jasm = d["jasm_code"]
    jasm = remove_linenumber_table(jasm)
    jasm = strip_unnecessary_info(jasm)
    class_name = d["class_name"]
    class_idx = d["class_idx"]
    java_test = d["java_test"]
    java_scaffold = d["java_scaffold"]

    # generation
    pred_java, compile_and_test_results, pass_rate = test_java_class_driver(
        class_name,
        jasm,
        java_test,
        java_scaffold,
        args
    )

    # compute stats
    successful_compile = any(True in compile_attempts for _, compile_attempts in compile_and_test_results)
    is_correct = successful_compile and pass_rate > 0.999

    result_dict = {
        "class_name": class_name,
        "class_idx": class_idx,
        "java_source": pred_java,
        "compile": successful_compile,
        "attempt_results": compile_and_test_results,
        "pass_rate": pass_rate
    }

    return result_dict, successful_compile, is_correct

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-file", type=str, required=True, help="data file")
    parser.add_argument("--output-file", type=str, required=True, help="output file")
    parser.add_argument("--model-type", type=str, default="gpt-3.5-turbo")
    parser.add_argument("--temperature", type=float, default=1.0)
    parser.add_argument("--max-attempts", type=int, default=5)
    parser.add_argument("--num-workers", type=int, default=4, help="Number of worker processes")
    args = parser.parse_args()

    data = []
    with open(args.input_file) as f:
        for line in f:
            data.append(json.loads(line))
        
    num_compiled, num_correct, num_total = 0, 0, 0
    with ProcessPoolExecutor(max_workers=args.num_workers) as executor:
        futures = {executor.submit(process_data, d, args): d for d in data}
        for future in as_completed(futures):
            result_dict, successful_compile, is_correct = future.result()
            print(result_dict["class_name"])
            print(result_dict["attempt_results"])

            num_total += 1
            if successful_compile:
                num_compiled += 1
            if is_correct:
                num_correct += 1
            
            pct_compiled = 100.0 * (num_compiled / num_total)
            pct_pass = 100.0 * (num_correct / num_total)
            print(f"Compiled: {num_compiled}/{num_total} ({pct_compiled}%), Pass: {num_correct}/{num_total} ({pct_pass}%)")
            
            with open(args.output_file, "a") as f:
                f.write(json.dumps(result_dict) + "\n")

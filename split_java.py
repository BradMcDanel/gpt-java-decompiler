import argparse
import json
import difflib

from tree_sitter import Language, Parser
JAVA_LANG = Language('CodeBLEU/parser/my-languages.so', 'java')
java_parser = Parser()
java_parser.set_language(JAVA_LANG)

from transformers import AutoTokenizer 


def extract_jasm_header(jasm):
    header = jasm.split("\n\n")[0]
    
    # get all methods
    for line in jasm.split("\n"):
        if line.startswith(".method"):
            header += "\n" + line.replace(".method", ".method_signature")

    # if <clinit> method exists, add entire method to header
    methods = extract_jasm_methods(jasm)
    for method in methods:
        if "<clinit>" in method.split(" : ")[0]:
            header += "\n" + method

    return header


def extract_jasm_methods(jasm):
    # find all "\n\n" blocks that start with .method
    methods = []
    # split on .method and .end method
    for method in jasm.split(".method")[1:]:
        # if synthetic or bridge in first line of method, skip
        if "synthetic" in method.split("\n")[0] or "bridge" in method.split("\n")[0]:
            continue
        method = ".method" + method.split(".end method")[0]
        method += ".end method"

        # remove .linenumbertable to .end linenumbertable
        if ".linenumbertable" in method:
            method = method.split(".linenumbertable")[0] + method.split(".end linenumbertable")[1]

        methods.append(method)

    return methods


def get_class_name(jasm_header):
    for line in jasm_header.split("\n"):
        if line.startswith(".class"):
            line = line.strip()
            return line.split(" ")[-1]


def get_field_names(jasm_header):
    field_names = []
    for line in jasm_header.split("\n"):
        if line.startswith(".field"):
            field_names.append(line.strip().split(" ")[-2])

    return field_names


def extract_java_header(java):
    static_fields = []
    java_bytes = bytes(java, 'utf-8')
    tree = java_parser.parse(java_bytes)
    cursor = tree.walk()
    header = ""

    cursor.goto_first_child()
    while True:
        if cursor.node.type == "import_declaration":
            part = java_bytes[cursor.node.start_byte:cursor.node.end_byte].decode('utf-8')
            header += part + "\n"

        if cursor.node.type == "class_declaration":
            break
        
        if not cursor.goto_next_sibling():
            break

    cursor.goto_first_child()
    while True:
        if cursor.node.type == "class_body":
            break

        part = java_bytes[cursor.node.start_byte:cursor.node.end_byte].decode('utf-8')
        header += part + " "

        if not cursor.goto_next_sibling():
            break
    
    
    cursor.goto_first_child()
    ignore_types = ["constructor_declaration", "method_declaration", "block_comment", "line_comment"]
    while True:
        curr_node = cursor.node
        if curr_node.type not in ignore_types:
            part = java_bytes[cursor.node.start_byte:cursor.node.end_byte].decode('utf-8')

            if curr_node.type not in ["{", "}"]:
                part = "  " + part

            if curr_node.type == "field_declaration" and "static" in part:
                static_fields.append(part)
            else:
                header += part + "\n"
                # if curr_node.type in ["{", "}"]:
                #     header += part
                # else:
                #     header += part + "\n"

        if not cursor.goto_next_sibling():
            break
    
    header = header.strip()
    
    return header, static_fields


def extract_java_methods(java):
    java_bytes = bytes(java, 'utf-8')
    tree = java_parser.parse(java_bytes)
    cursor = tree.walk()

    cursor.goto_first_child()
    while cursor.goto_next_sibling():
        if cursor.node.type == "class_declaration":
            break

    cursor.goto_first_child()
    while cursor.goto_next_sibling():
        if cursor.node.type == "class_body":
            break

    cursor.goto_first_child()
    methods = []
    while cursor.goto_next_sibling():
        if cursor.node.type in ["method_declaration", "constructor_declaration"]:
            method_start_index = cursor.node.start_byte
            method_end_idx = cursor.node.end_byte

            # extract unicode string of method
            method = java_bytes[method_start_index:method_end_idx].decode('utf-8')

            # find start of line
            method = java[:method_start_index].split("\n")[-1] + method

            # compute indent
            indent_level = len(method) - len(method.lstrip())

            # remove indent
            method = "\n".join([line[indent_level:] for line in method.split("\n")])

            # append to methdos
            methods.append(method)

    return methods


def align_jasm_java_methods(class_name, jasm_methods, java_methods,
                            jasm_header, java_header, static_fields):
    # clone
    jasm_methods = jasm_methods[:]
    java_methods = java_methods[:]

    jasm_method_names = []
    for method in jasm_methods:
        # split on " " and " : " to get method name
        method_name = method.split(" : ")[0].split(" ")[-1]
        if method_name == "<init>":
            method_name = class_name
        jasm_method_names.append(method_name)
    
    java_method_names = []
    for method in java_methods:
        # split on "(" to get method name
        method_name = method.split("(")[0].split(" ")[-1]
        java_method_names.append(method_name)

    
    # for each java method, find the jasm method with the same name
    # if there are multiple jasm methods with the same name, take the first one
    # pop from jasm_mathods and java_methods as we go
    align_jasm_methods, align_java_methods = [], []
    for i, java_method in enumerate(java_methods):
        java_method_name = java_method_names[i]
        for j, jasm_method in enumerate(jasm_methods):
            jasm_method_name = jasm_method_names[j]
            if java_method_name == jasm_method_name:
                align_java_methods.append(java_method)
                align_jasm_methods.append(jasm_method)
                jasm_methods.pop(j)
                jasm_method_names.pop(j)
                break
    
        
    if len(jasm_methods) != 0:
        for method in jasm_methods:
            if "<init>" in method.split(" : ")[0]:
                align_jasm_methods.append(method)
                align_java_methods.append("")

            if "<clinit>" in method.split(" : ")[0]:
                # then add entire method to java_header
                align_jasm_methods.append(method)
                # make a fake method that includes the field initializations
                static_method = "<static> {\n"
                static_method += "\n".join(static_fields)
                static_method += "\n}\n"
                align_java_methods.append(static_method)
    
    # prepend header as method
    jasm_header_prompt = jasm_header + "\n.header\n"
    align_jasm_methods.insert(0, jasm_header_prompt)
    align_java_methods.insert(0, java_header)

    return align_jasm_methods, align_java_methods

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
    

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-file", type=str, required=True, help="data file")
    parser.add_argument("--output-file", type=str, required=True, help="output file")
    parser.add_argument("--start-idx", type=int, default=0, help="start index")
    args = parser.parse_args()

    # if output_file is "train.json", then output_class_file is "train_class.json"
    output_class_file = args.output_file.replace(".json", "_class.json")

    data = []
    with open(args.input_file) as f:
        for line in f:
            data.append(json.loads(line))

    tokenizer = AutoTokenizer.from_pretrained('Salesforce/codet5-base')

    for idx, d in enumerate(data[args.start_idx:]):
        jasm = d["jasm_code"]
        java = d["java_source"]

        # get jasm header and methods
        jasm_header = extract_jasm_header(jasm)
        all_jasm_methods = extract_jasm_methods(jasm)
        
        # this part is used to reconstruct the java code
        class_name = get_class_name(jasm_header)
        field_names = get_field_names(jasm_header)

        # get java header and methods
        java_header, static_fields = extract_java_header(java)
        all_java_methods = extract_java_methods(java)
        
        # align jasm and java methods
        jasm_methods, java_methods = align_jasm_java_methods(class_name, all_jasm_methods, all_java_methods, jasm_header, java_header, static_fields)

        # merge java methods into a single string
        merged_java = merge_java_methods(java_methods)

        # compare diff between java and merged_java
        # diff = difflib.ndiff(merged_java.splitlines(keepends=True), java.splitlines(keepends=True))
        # print(''.join(diff))

        # generate output pairs
        for i, (jasm_method, java_method) in enumerate(zip(jasm_methods, java_methods)):
            with open(args.output_file, "a") as f:
                output = {"src": jasm_method, "tgt": java_method, "method_idx": i, "class_idx": idx}
                f.write(json.dumps(output) + "\n")

        with open(output_class_file, "a") as f:
            # dump all contents of input data
            output = data[idx]
            output["class_idx"] = idx
            f.write(json.dumps(output) + "\n")

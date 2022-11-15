import argparse
import json

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
            field_names.append(line.split(" ")[1])

    return field_names


def extract_java_header(java, class_name, field_names):
    # TODO: fix this to make it more robust
    header = ""
    # find like containing class_name
    for line in java.split("\n"):
        if class_name in line:
            header += line + "\n"
            break
    
    # find all lines containing field_names
    for line in java.split("\n"):
        for field_name in field_names:
            if field_name in line:
                header += line + "\n"
                break

    header +=  "}\n"

    return header


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


def align_jasm_java_methods(class_name, jasm_methods, java_methods):
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

    return align_jasm_methods, align_java_methods


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-file", type=str, required=True, help="data file")
    parser.add_argument("--output-file", type=str, required=True, help="output file")
    parser.add_argument("--start-idx", type=int, default=0, help="start index")
    args = parser.parse_args()

    data = []
    with open(args.input_file) as f:
        for line in f:
            data.append(json.loads(line))

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
        java_header = extract_java_header(java, class_name, field_names)
        all_java_methods = extract_java_methods(java)
        
        jasm_methods, java_methods = align_jasm_java_methods(class_name, all_jasm_methods, all_java_methods)

        if len(jasm_methods) == 0:
            # print(all_java_methods)
            # print(all_jasm_methods)
            # print(java)
            # print(jasm)
            print("============")
            print(jasm_header)
            print("============")
            print(java_header)
            print(idx)
            assert False

        tokenizer = AutoTokenizer.from_pretrained('Salesforce/codet5-base')
        print(class_name)
        for i in range(len(jasm_methods)):
            # print(jasm_methods[i])
            # print("*" * 20)
            # print(java_methods[i])
            # print("=" * 20)
            src_tokens = tokenizer.tokenize(jasm_methods[i])
            tgt_tokens = tokenizer.tokenize(java_methods[i])
            # print(f"len src: {len(src_tokens)}")
            # print(f"len tgt: {len(tgt_tokens)}")


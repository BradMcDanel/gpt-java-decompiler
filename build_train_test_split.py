import argparse
import os
import json
import random
import re

from tree_sitter import Language, Parser
JAVA_LANG = Language('CodeBLEU/parser/my-languages.so', 'java')
java_parser = Parser()
java_parser.set_language(JAVA_LANG)

TEST_SOURCE = '''import java.math.BigInteger;
                                 
public class Testplan {
  private BigInteger id;   
                                 
  private String name;

  public Testplan() {}
                                 
  /**
   * @param id                                                     
   * @param name     
   */
  public Testplan(BigInteger id, String name) {
    this.id = id;
    this.name = name;
  }

  /**
   * @return the id
   */
  public BigInteger getId() {
    return id;
  }

  /**
   * @param id the id to set
   */
  public void setId(BigInteger id) {
    this.id = id;
  }

  /**
   * @return the name
   */
  public String getName() {
    return name;
  }

  /**
   * @param name the name to set
   */
  public void setName(String name) {
    this.name = name;
  }
}
'''

TEST_JASM = '''.version 52 0                                                                                                                          
.class public super Testplan                                                                                                           
.super java/lang/Object                                                                                                                
.field private id Ljava/math/BigInteger;                                                                                               
.field private name Ljava/lang/String;                                                                                                 
                                                                   
.method public <init> : ()V 
    .code stack 1 locals 1       
L0:     aload_0                                                    
L1:     invokespecial Method java/lang/Object <init> ()V 
L4:     return               
L5:                                                                
        .linenumbertable 
            L0 11 
            L4 13                                                  
        .end linenumbertable 
    .end code        
.end method            

.method public <init> : (Ljava/math/BigInteger;Ljava/lang/String;)V  
    .code stack 2 locals 3                                         
L0:     aload_0            
L1:     invokespecial Method java/lang/Object <init> ()V 
L4:     aload_0   
L5:     aload_1                                                    
L6:     putfield Field Testplan id Ljava/math/BigInteger; 
L9:     aload_0 
L10:    aload_2             
L11:    putfield Field Testplan name Ljava/lang/String; 
L14:    return    
L15:                         
        .linenumbertable 
            L0 19 
            L4 20 
            L9 21 
            L14 22 
        .end linenumbertable 
    .end code 
.end method 

.method public getId : ()Ljava/math/BigInteger; 
    .code stack 1 locals 1 
L0:     aload_0              
L1:     getfield Field Testplan id Ljava/math/BigInteger; 
L4:     areturn 
L5:     
        .linenumbertable                                           
            L0 28          
        .end linenumbertable 
    .end code   
.end method                                                        
                                 
.method public setId : (Ljava/math/BigInteger;)V 
    .code stack 2 locals 2 
L0:     aload_0   
L1:     aload_1   
L2:     putfield Field Testplan id Ljava/math/BigInteger; 
L5:     return 
L6:         
        .linenumbertable    
            L0 35 
            L5 36 
        .end linenumbertable 
    .end code 
.end method 

.method public getName : ()Ljava/lang/String; 
    .code stack 1 locals 1 
L0:     aload_0 
L1:     getfield Field Testplan name Ljava/lang/String; 
L4:     areturn 
L5:     
        .linenumbertable 
            L0 42 
        .end linenumbertable 
    .end code 
.end method 

.method public setName : (Ljava/lang/String;)V 
    .code stack 2 locals 2 
L0:     aload_0 
L1:     aload_1 
L2:     putfield Field Testplan name Ljava/lang/String; 
L5:     return 
L6:     
        .linenumbertable 
            L0 49 
            L5 50 
        .end linenumbertable 
    .end code 
.end method 
.sourcefile 'Testplan.java' 
.end class 
'''


def starpattern_multiline_matcher(java):
    # look for /* comment...\n.. */
    star_comment = re.compile("/\*[\s\S]*?\*/")
    matches =  star_comment.findall(java)

    comment_idxs = []
    for match in matches:
        start = java.index(match)
        end = start + len(match)
        comment_idxs.append((start, end))

    return comment_idxs


def doubleslash_multiline_matcher(java):
    matches = []
    in_comment = False
    comment = ""
    for line in java.splitlines():
        if line.lstrip().startswith("//"):
            in_comment = True
            comment += line + "\n"
        else:
            if in_comment:
                in_comment = False
                matches.append(comment)
                comment = ""

    comment_idxs = []
    for match in matches:
        start = java.index(match)
        end = start + len(match)
        comment_idxs.append((start, end))

    return comment_idxs

def keyword_matcher(java, comment_idxs):
    keywords = ["class", "import"]
    keyword_idxs = []
    for keyword in keywords:
        keyword_matches = [(m.start(), m.end()) for m in re.finditer(keyword, java)]
    
        for keyword_match in keyword_matches:
            comment_match = False
            for comment_idx in comment_idxs:
                if comment_idx[0] < keyword_match[0] < comment_idx[1]:
                    comment_match = True
                    break

            if comment_match:
                continue
            
            keyword_idxs.append(keyword_match)

    if len(keyword_idxs) == 0:
        return 0

    return min(keyword_idxs, key=lambda x: x[0])[0]

def remove_starting_comments(java, start_idx, comment_idxs):
    for comment_idx in comment_idxs[::-1]:
        if comment_idx[0] < start_idx:
            java = java[:comment_idx[0]] + java[comment_idx[1]:]

    return java

def trim_license_str(java):
    """
    Removes top-level LICENSE from source code.
    """

    star_matches = starpattern_multiline_matcher(java)
    slash_matches = doubleslash_multiline_matcher(java)
    comment_idxs = star_matches + slash_matches
    start_idx = keyword_matcher(java, comment_idxs)
    java = remove_starting_comments(java, start_idx, comment_idxs)

    return java

def remove_author_comments(java):
    """
    Removes author comments from source code.
    """
    # look for comment starting with // @author or /* .. @author .. */
    author_comment = re.compile("// @author[\s\S]*?\n|/\*[\s\S]*?@author[\s\S]*?\*/")
    matches =  author_comment.findall(java)

    comment_idxs = []
    for match in matches:
        start = java.index(match)
        end = start + len(match)
        comment_idxs.append((start, end))

    for comment_idx in comment_idxs:
        java = java[:comment_idx[0]] + java[comment_idx[1]:]

    return java


def remove_methods(java):
    """
    Removes all methods from java class
    """
    # look for comment starting with 
    method_comment = re.compile("\s*(public|private|protected)\s+[\w<>\[\]]+\s+[\w<>\[\]]+\s*\(.*\)\s*\{[\s\S]*?\}")
    matches =  method_comment.findall(java)

    comment_idxs = []
    for match in matches:
        start = java.index(match)
        end = start + len(match)
        comment_idxs.append((start, end))

    for comment_idx in comment_idxs:
        java = java[:comment_idx[0]] + java[comment_idx[1]:]

    return java


def reject_sample(java):
    tree = java_parser.parse(bytes(java, 'utf-8'))
    cursor = tree.walk()
    cursor.goto_first_child()

    # count number of classes
    num_classes = 0
    while cursor.goto_next_sibling():
        if cursor.node.type == "class_declaration":
            num_classes += 1

    if num_classes > 1:
        return True

    return False


def collect_nodes(cursor):
    if not cursor.goto_first_child():
        return [cursor.node]
    else:
        nodes = [collect_nodes(cursor)]
        while cursor.goto_next_sibling():
            nodes.append(collect_nodes(cursor))
        
        cursor.goto_parent()
        return nodes


def java_code_from_nodes(nodes, depth=0):
    output = []
    for node in nodes:
        if type(node) == list:
            output.extend(java_code_from_nodes(node, depth=depth+1))
        else:
            if node.type in ["block_comment"]:
                output.append("\n\n")

            start_idx = node.start_byte
            end_idx = node.end_byte
            output.append(java[start_idx:end_idx])

    if depth == 0:
        output = " ".join(output)

    return output


def reject_field_order(java):
    tree = java_parser.parse(bytes(java, 'utf-8'))
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
    node_types = []
    while cursor.goto_next_sibling():
        node_types.append(cursor.node.type)

    # if 'field_declaration' comes after any other node type, reject
    found_other_declaration = False
    for node_type in node_types:
        if node_type != "field_declaration":
            found_other_declaration = True
        elif found_other_declaration and node_type == "field_declaration":
            return True
    
    return False


def preprocess_java_source(java):
    java = trim_license_str(java)
    java = remove_author_comments(java)
    if reject_field_order(java):
        return None

    return java


def get_methods(java):
    tree = java_parser.parse(bytes(java, 'utf-8'))
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
    method_names = []
    prev_sibling = None
    while cursor.goto_next_sibling():
        if cursor.node.type in ["method_declaration", "constructor_declaration"]:
            # check if a "block_comment" is prior sibling
            if prev_sibling is not None and prev_sibling.type == "block_comment":
                start_index = prev_sibling.start_byte
            else:
                start_index = cursor.node.start_byte
            method_start_index = cursor.node.start_byte
            end_index = cursor.node.end_byte
            start_index = java.rfind("\n", 0, start_index) + 1
            method = java[start_index:end_index]
            method_src = java[method_start_index:end_index]
            method_name = method_src.split("\n")[0].split("(")[0].split(" ")[-1]
            methods.append(method)
            method_names.append(method_name)

        prev_sibling = cursor.node

    return methods, method_names


def add_class_header(java, methods):
    """
    Find instance of first_method in java and return up to that point
    """
    first_method = methods[0]
    index = java.index(first_method)
    header = java[:index] + "\n"
    footer = "\n}"

    return_methods = []
    for method in methods:
        final_method = header + method + footer
        final_method = final_method.strip()
        return_methods.append(final_method)

    return return_methods


def split_java_source(java):
    java = preprocess_java_source(java)
    if java is None:
        return None, None

    methods, method_names = get_methods(java)
    if len(methods) == 0:
        return None, None

    methods = add_class_header(java, methods)

    return methods, method_names


def match_source_asm(sample):
    java = sample["java_source"]
    jasm = sample["jasm_code"]
    class_name = sample["class_name"]

    methods, method_names = split_java_source(java)

    if methods is None:
        return None

    jasm_methods = []
    constructor_num = 0
    for method, method_name in zip(methods, method_names):
        jasm_method = match_method_asm(jasm, method, class_name, method_name, constructor_num)
        print(jasm_method)

        if method_name == class_name:
            constructor_num += 1

        if jasm_method is None:
            return None
        jasm_methods.append(jasm_method)

    return methods, jasm_methods


def match_method_asm(jasm, method, class_name, method_name, constructor_num=0):
    """
    Returns java assembly (jasm) that matches the java method (method)
    """
    # split jasm into header and body
    jasm_header = jasm.split("\n\n")[0] + "\n"
    jasm_body = "\n".join(jasm.split("\n")[1:])
    
    if method_name == class_name:
        method_name = "<init>"

    # find method in jasm
    if method_name == "<init>":
        method_start = 0
        constructor_idx = 0
        while constructor_idx < constructor_num:
            method_start = jasm_body.find(method_name)
            jasm_body = jasm_body[method_start + len(method_name):]

            if method_start == -1:
                return None

            constructor_idx += 1

    method_start = jasm_body.find(method_name)

    if method_start == -1:
        return None

    # find previous newline
    method_start = jasm_body.rfind("\n", 0, method_start) + 1

    # go to next .endmethod from method_start
    method_end = jasm_body.find(".end method", method_start) + len(".end method")

    # get method body
    method_body = jasm_body[method_start:method_end]

    # add header to method body
    jasm_method = jasm_header + "\n" + method_body

    return jasm_method


if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=str, required=True, help="Input directory")
    parser.add_argument("--output-dir", type=str, required=True, help="Output directory")
    parser.add_argument("--train-percentage", type=float, default=0.90, help="Percentage of Java files to use for training")
    parser.add_argument("--seed", type=int, default=0, help="Random seed")
    args = parser.parse_args()

    # make sure output directory exists
    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)

    all_data = []
    for filename in os.listdir(args.input_dir):
        with open(os.path.join(args.input_dir, filename), 'r') as f:
            all_data.extend(json.load(f))
            break

    # extract methods from samples
    samples = []
    methods = []
    all_data = [{"java_source": TEST_SOURCE, "jasm_code": TEST_JASM, "class_name": "Testplan"}]
    for data in all_data:
        result_methods = []
        result = match_source_asm(data)
        if result is None:
            continue

        sample_methods, jasm_methods = result
        for sample_method, jasm_method in zip(sample_methods, jasm_methods):
            result_methods.append({"java_source": sample_method, "jasm_code": jasm_method})
        
        samples.append(data)
        methods.append(result_methods)
    assert False

    # shuffle data
    random.seed(args.seed)

    # get permutation indexes for all_data
    permutation_indexes = list(range(len(samples)))
    random.shuffle(permutation_indexes)

    # shuffle samples
    samples = [samples[i] for i in permutation_indexes]
    methods = [methods[i] for i in permutation_indexes]

    # split data
    train_samples = samples[:int(len(samples) * args.train_percentage)]
    train_methods = methods[:int(len(methods) * args.train_percentage)]
    test_samples = samples[int(len(samples) * args.train_percentage):]
    test_methods = methods[int(len(methods) * args.train_percentage):]

    # flatten data
    train_methods = [item for sublist in train_methods for item in sublist]
    test_methods = [item for sublist in test_methods for item in sublist]

    print("Train samples: {}".format(len(train_samples)))
    print("Train methods: {}".format(len(train_methods)))
    print("Test samples: {}".format(len(test_samples)))
    print("Test methods: {}".format(len(test_methods)))

    # write data
    with open(os.path.join(args.output_dir, "train_samples.json"), 'w') as f:
        for dict in train_samples:
            f.write(json.dumps(dict) + '\n')

    with open(os.path.join(args.output_dir, 'train_methods.json'), 'w') as f:
        for dict in train_methods:
            f.write(json.dumps(dict) + '\n')

    with open(os.path.join(args.output_dir, 'test_samples.json'), 'w') as f:
        for dict in test_samples:
            f.write(json.dumps(dict) + '\n')

    with open(os.path.join(args.output_dir, 'test_methods.json'), 'w') as f:
        for dict in test_methods:
            f.write(json.dumps(dict) + '\n')

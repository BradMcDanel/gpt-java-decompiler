def java_to_jasm_train(java_source, jasm_code):
    return "<JAVA>\n" + java_source + "</JAVA>\n<JASM>\n" + jasm_code + "</JASM><|endoftext|>"


def jasm_to_java_train(java_source, jasm_code):
    return "<JASM>\n" + jasm_code + "</JASM>\n<JAVA>\n" + java_source + "</JAVA><|endoftext|>"


def java_to_jasm_test(java_source):
    return "<JAVA>\n" + java_source + "</JAVA>\n<JASM>\n"


def jasm_to_java_test(jasm_code):
    return "<JASM>\n" + jasm_code + "</JASM>\n<JAVA>\n"


def get_train_prompt(target, java_source, jasm_code):
    if target == "java_to_jasm":
        return java_to_jasm_train(java_source, jasm_code)
    elif target == "jasm_to_java":
        return jasm_to_java_train(java_source, jasm_code)
    else:
        raise Exception("Invalid target: " + target)


def get_test_prompt(target, java_source, jasm_code):
    if target == "java_to_jasm":
        return java_to_jasm_test(java_source)
    elif target == "jasm_to_java":
        return jasm_to_java_test(jasm_code)
    else:
        raise Exception("Invalid target: " + target)

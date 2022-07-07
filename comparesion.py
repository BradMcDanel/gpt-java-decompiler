import argparse
import os
import json

import java_utils


def procyon_decompiler_test(sample, byte_code_str):
    class_name = sample["class_name"]
    decomp_procyon_java = java_utils.procyon_decompiler(class_name, byte_code_str)
    if decomp_procyon_java is None:
        return 0.0
    
    procyon_byte_code = java_utils.compile_str(class_name, decomp_procyon_java)
    if procyon_byte_code is None:
        return 0.0
    
    procyon_pass_rate = java_utils.evosuite_compile_and_run_test(
        class_name,
        procyon_byte_code,
        sample["java_test"],
        sample["java_scaffold"],
    )

    return procyon_pass_rate


def CFR_decompiler_test(sample, byte_code_str):
    class_name = sample["class_name"]
    decomp_CFR_java = java_utils.CFR_decompiler(class_name, byte_code_str)
    if decomp_CFR_java is None:
        return 0.0
    
    CFR_byte_code = java_utils.compile_str(class_name, decomp_CFR_java)
    if CFR_byte_code is None:
        return 0.0
    
    CFR_pass_rate = java_utils.evosuite_compile_and_run_test(
        class_name,
        CFR_byte_code,
        sample["java_test"],
        sample["java_scaffold"],
    )

    return CFR_pass_rate

def JADX_decompiler_test(sample, byte_code_str):
    class_name = sample["class_name"]
    decomp_JADX_java = java_utils.CFR_decompiler(class_name, byte_code_str)
    if decomp_JADX_java is None:
        return 0.0
    
    decomp_JADX_java = java_utils.preprocess_str(decomp_JADX_java)
    JADX_byte_code = java_utils.compile_str(class_name, decomp_JADX_java)
    if JADX_byte_code is None:
        return 0.0
    
    JADX_pass_rate = java_utils.evosuite_compile_and_run_test(
        class_name,
        JADX_byte_code,
        sample["java_test"],
        sample["java_scaffold"],
    )

    return JADX_pass_rate


def fernflower_decompiler_test(sample, byte_code_str):
    class_name = sample["class_name"]
    decomp_fernflower_java = java_utils.fernflower_decompiler(class_name, byte_code_str)
    if decomp_fernflower_java is None:
        return 0.0
    
    fernflower_byte_code = java_utils.compile_str(class_name, decomp_fernflower_java)
    if fernflower_byte_code is None:
        return 0.0
    
    fernflower_pass_rate = java_utils.evosuite_compile_and_run_test(
        class_name,
        fernflower_byte_code,
        sample["java_test"],
        sample["java_scaffold"],
    )

    return fernflower_pass_rate


def krakatau_decompiler_test(sample, byte_code_str):
    class_name = sample["class_name"]
    decomp_krakatau_java = java_utils.krakatau_decompiler(class_name, byte_code_str)
    if decomp_krakatau_java is None:
        return 0.0

    krakatau_byte_code = java_utils.compile_str(class_name, decomp_krakatau_java)
    if krakatau_byte_code is None:
        return 0.0
        
    krakatau_pass_rate = java_utils.evosuite_compile_and_run_test(
        class_name,
        krakatau_byte_code,
        sample["java_test"],
        sample["java_scaffold"],
    )

    return krakatau_pass_rate


if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=str, required=True, help="Data directory")
    parser.add_argument("--output-path", type=str, required=True, help="Output path")
    args = parser.parse_args()

    #load data
    test_path = os.path.join(args.data_dir, "test.json")
    data = []
    with open(test_path, 'r') as f:
        for line in f:
            data.append(json.loads(line))

    #processing results
    results = []
    for i in range(len(data)):
        print(str(i) + '/' + str(len(data)))
        sample_data = data[i]
        class_name = sample_data["class_name"]
        gold_byte_code = java_utils.assemble_str(class_name, sample_data["jasm_code"])
        if gold_byte_code is None:
            pass
        else:
            results.append({
                "Class_name" : class_name,
                "java_source": sample_data["java_source"],
                "jasm_code": sample_data["jasm_code"],
                "Procyon_pass_rate": procyon_decompiler_test(sample_data,gold_byte_code),
                "CFR_pass_rate": CFR_decompiler_test(sample_data,gold_byte_code),
                "JADX_pass_rate": JADX_decompiler_test(sample_data,gold_byte_code),
                "Fernflower_pass_rate": fernflower_decompiler_test(sample_data,gold_byte_code),
                "Krakatau_pass_rate": krakatau_decompiler_test(sample_data,gold_byte_code),
            })
            
    with open(args.output_path, 'w') as f:
        for result in results:
            f.write(json.dumps(result) + "\n")
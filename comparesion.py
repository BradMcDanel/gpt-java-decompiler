import argparse
import os
import json
import time

import java_utils


def procyon_decompiler_test(sample, byte_code_str):
    class_name = sample["class_name"]
    start_t = time.time()
    decomp_procyon_java = java_utils.procyon_decompiler(class_name, byte_code_str)
    total_time = time.time() - start_t
    if decomp_procyon_java is None:
        return {
            "java_source" : decomp_procyon_java,
            "pass_rate" : 0.0,
            "decomp_time" : total_time,
            "Java_gen" : False,
            "compile" : False,
        }
    
    procyon_byte_code = java_utils.compile_str(class_name, decomp_procyon_java)
    if procyon_byte_code is None:
        return {
            "java_source" : decomp_procyon_java,
            "pass_rate" : 0.0,
            "decomp_time" : total_time,
            "Java_gen" : True,
            "compile" : False,
        }
    
    procyon_pass_rate = java_utils.evosuite_compile_and_run_test(
        class_name,
        procyon_byte_code,
        sample["java_test"],
        sample["java_scaffold"],
    )

    return {
            "java_source" : decomp_procyon_java,
            "pass_rate" : procyon_pass_rate,
            "decomp_time" : total_time,
            "Java_gen" : True,
            "compile" : True,
        }


def CFR_decompiler_test(sample, byte_code_str):
    class_name = sample["class_name"]
    start_t = time.time()
    decomp_CFR_java = java_utils.CFR_decompiler(class_name, byte_code_str)
    total_time = time.time() - start_t
    if decomp_CFR_java is None:
        return {
            "java_source" : decomp_CFR_java,
            "pass_rate" : 0.0,
            "decomp_time" : total_time,
            "Java_gen" : False,
            "compile" : False,
        }
    
    CFR_byte_code = java_utils.compile_str(class_name, decomp_CFR_java)
    if CFR_byte_code is None:
        return {
            "java_source" : decomp_CFR_java,
            "pass_rate" : 0.0,
            "decomp_time" : total_time,
            "Java_gen" : True,
            "compile" : False,
        }
    
    CFR_pass_rate = java_utils.evosuite_compile_and_run_test(
        class_name,
        CFR_byte_code,
        sample["java_test"],
        sample["java_scaffold"],
    )

    return {
            "java_source" : decomp_CFR_java,
            "pass_rate" : CFR_pass_rate,
            "decomp_time" : total_time,
            "Java_gen" : True,
            "compile" : True,
        }


def JADX_decompiler_test(sample, byte_code_str):
    class_name = sample["class_name"]
    start_t = time.time()
    decomp_JADX_java = java_utils.CFR_decompiler(class_name, byte_code_str)
    total_time = time.time() - start_t
    if decomp_JADX_java is None:
        return {
            "java_source" : decomp_JADX_java,
            "pass_rate" : 0.0,
            "decomp_time" : total_time,
            "Java_gen" : False,
            "compile" : False,
        }
    
    decomp_JADX_java = java_utils.preprocess_str(decomp_JADX_java)
    JADX_byte_code = java_utils.compile_str(class_name, decomp_JADX_java)
    if JADX_byte_code is None:
        return {
            "java_source" : decomp_JADX_java,
            "pass_rate" : 0.0,
            "decomp_time" : total_time,
            "Java_gen" : True,
            "compile" : False,
        }
    
    JADX_pass_rate = java_utils.evosuite_compile_and_run_test(
        class_name,
        JADX_byte_code,
        sample["java_test"],
        sample["java_scaffold"],
    )

    return {
            "java_source" : decomp_JADX_java,
            "pass_rate" : JADX_pass_rate,
            "decomp_time" : total_time,
            "Java_gen" : True,
            "compile" : True,
        }


def fernflower_decompiler_test(sample, byte_code_str):
    class_name = sample["class_name"]
    start_t = time.time()
    decomp_fernflower_java = java_utils.fernflower_decompiler(class_name, byte_code_str)
    total_time = time.time() - start_t
    if decomp_fernflower_java is None:
        return {
            "java_source" : decomp_fernflower_java,
            "pass_rate" : 0.0,
            "decomp_time" : total_time,
            "Java_gen" : False,
            "compile" : False,
        }
    
    fernflower_byte_code = java_utils.compile_str(class_name, decomp_fernflower_java)
    if fernflower_byte_code is None:
        return {
            "java_source" : decomp_fernflower_java,
            "pass_rate" : 0.0,
            "decomp_time" : total_time,
            "Java_gen" : True,
            "compile" : False,
        }
    
    fernflower_pass_rate = java_utils.evosuite_compile_and_run_test(
        class_name,
        fernflower_byte_code,
        sample["java_test"],
        sample["java_scaffold"],
    )

    return {
            "java_source" : decomp_fernflower_java,
            "pass_rate" : fernflower_pass_rate,
            "decomp_time" : total_time,
            "Java_gen" : True,
            "compile" : True,
        }


def krakatau_decompiler_test(sample, byte_code_str):
    class_name = sample["class_name"]
    start_t = time.time()
    decomp_krakatau_java = java_utils.krakatau_decompiler(class_name, byte_code_str)
    total_time = time.time() - start_t
    if decomp_krakatau_java is None:
        return {
            "java_source" : decomp_krakatau_java,
            "pass_rate" : 0.0,
            "decomp_time" : total_time,
            "Java_gen" : False,
            "compile" : False,
        }


    krakatau_byte_code = java_utils.compile_str(class_name, decomp_krakatau_java)
    if krakatau_byte_code is None:
        return {
            "java_source" : decomp_krakatau_java,
            "pass_rate" : 0.0,
            "decomp_time" : total_time,
            "Java_gen" : True,
            "compile" : False,
        }

        
    krakatau_pass_rate = java_utils.evosuite_compile_and_run_test(
        class_name,
        krakatau_byte_code,
        sample["java_test"],
        sample["java_scaffold"],
    )

    return {
            "java_source" : decomp_krakatau_java,
            "pass_rate" : krakatau_pass_rate,
            "decomp_time" : total_time,
            "Java_gen" : True,
            "compile" : True,
        }


if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=str, required=True, help="Data directory")
    parser.add_argument("--output-path", type=str, required=True, help="Output path")
    args = parser.parse_args()

    #load data
    test_path = os.path.join(args.data_dir, "test_small.json")
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
            gold = {
                    "java_source": sample_data["java_source"],
                    "jasm_code": sample_data["jasm_code"],
                    "test": sample_data["java_test"],
                    "scaffold":sample_data["java_scaffold"],
                }
            results.append({
                "Class_name" : class_name,
                "Gold" : gold,
                "Procyon": procyon_decompiler_test(sample_data,gold_byte_code),
                "CFR": CFR_decompiler_test(sample_data,gold_byte_code),
                "JADX": JADX_decompiler_test(sample_data,gold_byte_code),
                "Fernflower": fernflower_decompiler_test(sample_data,gold_byte_code),
                "Krakatau": krakatau_decompiler_test(sample_data,gold_byte_code),
            })
            
    with open(args.output_path, 'w') as f:
        for result in results:
            f.write(json.dumps(result) + "\n")
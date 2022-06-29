"""
Uses output .json from fetch_bq.py to create a dataset of Java source code.
This file uses java_utils.py to compile java code and generate evosuite tests.
"""

import argparse
import json
import os

from joblib import Parallel, delayed
import java_utils

def process_sample(java_dict):
    home_dir = os.getcwd()
    try:
        # get code
        java_code = java_dict["content"]

        # get class name
        class_name = java_utils.get_class_name(java_code)

        if class_name is None:
            return None

        # preprocess code
        java_code = java_utils.preprocess_str(java_code)

        if java_code is None:
            return None
        
        # compile bytecode
        byte_code = java_utils.compile_str(class_name, java_code)

        if byte_code is None:
            return None

        # format code
        java_code = java_utils.format_str(class_name, java_code)

        if java_code is None:
            return None

        # disassemble code
        jasm_code = java_utils.disassemble_str(class_name, byte_code)

        if jasm_code is None:
            return None

        # generate tests using evosuite and gold bytecode
        test_str, scaffold_str = java_utils.evosuite_gen_test(class_name, byte_code)

        if test_str is None:
            return None

        # ensure that the gold bytecode passes the evosuite tests
        pass_rate = java_utils.evosuite_compile_and_run_test(class_name, byte_code, test_str, scaffold_str)

        if pass_rate < 1.0:
            return None
            
        return {
            "class_name": class_name,
            "java_source": java_code,
            "jasm_code": jasm_code,
            "java_test": test_str,
            "java_scaffold": scaffold_str,
        }
    except:
        os.chdir(home_dir)
        return None


if __name__=="__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=str, required=True, help="Input directory")
    parser.add_argument("--output-dir", type=str, required=True, help="Output directory")
    parser.add_argument("--num-files", type=int, default=None, help="Number of files to use")
    parser = parser.parse_args()

    # get list of files
    files = os.listdir(parser.input_dir)
    # order files numerically by name
    files = sorted(files, key=lambda x: int(x.split('.')[0]))
    if parser.num_files is not None:
        files = files[:parser.num_files]
    
    output_data = []
    
    samples_processed = 0
    # create dataset
    for file in files:
        with open(os.path.join(parser.input_dir, file), "r") as f:
            data = json.load(f) 

        results = Parallel(n_jobs=-1, verbose=10)(delayed(process_sample)(sample) for sample in data)
        results = [result for result in results if result is not None]
        print(len(results))

        with open(os.path.join(parser.output_dir, file), "w") as f:
            json.dump(results, f)

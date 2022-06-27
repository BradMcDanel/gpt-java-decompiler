"""
Uses output .json from fetch_bq.py to create a dataset of Java source code.
This file uses java_utils.py to compile java code and generate evosuite tests.
"""

import argparse
import json
import os

import java_utils


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

        # attempt to compile java code and generate evosuite tests
        # if compilation fails, skip this file
        # (compilation errors are usually due to missing dependencies)
        for java_dict in data:
            if samples_processed == 1000:
                with open(os.path.join(parser.output_dir, file), "w") as f:
                    json.dump(output_data, f)
                    break


            samples_processed += 1

            # get code
            java_code = java_dict["content"]

            # get class name
            class_name = java_utils.get_class_name(java_code)

            if class_name is None:
                continue

            # preprocess code
            java_code = java_utils.preprocess_str(java_code)
            
            # format code
            java_code = java_utils.format_str(class_name, java_code)

            if java_code is None:
                continue

            # compile bytecode
            byte_code = java_utils.compile_str(class_name, java_code)

            if byte_code is None:
                continue

            # generate tests using evosuite and gold bytecode
            test_str, scaffold_str = java_utils.evosuite_gen_test(class_name, byte_code)

            if test_str is None:
                continue

            # ensure that the gold bytecode passes the evosuite tests
            pass_rate = java_utils.evosuite_compile_and_run_test(class_name, byte_code, test_str, scaffold_str)

            if pass_rate < 1.0:
                print(f"Skipping {file} because it failed evosuite tests")
                break
                
            # if compilation passes, add to dataset
            output_data.append({
                "class_name": class_name,
                "java_source": java_code,
                "byte_code": byte_code,
                "java_test": test_str,
                "java_scaffold": scaffold_str,
            })

            print(f"Num passes: {len(output_data)} / {samples_processed}")






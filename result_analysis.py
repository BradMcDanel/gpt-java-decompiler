import argparse
import os
import json

from attr import s


if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=str, required=True, help="Data directory")
    parser.add_argument("--output-path", type=str, required=True, help="Output path")
    args = parser.parse_args()

    #load data
    test_path = os.path.join(args.data_dir, "test_small-out.json")
    data = []
    with open(test_path, 'r') as f:
        for line in f:
            data.append(json.loads(line))
    
    results = {
        "Procyon_correct": 0,
        "CFR_correct": 0,
        "JADX_correct": 0,
        "Fernflower_correct": 0,
        "Krakatau_correct": 0,
        }
    
    fail_java = []
    
    for i in range(len(data)):
        sample_data = data[i]
        if sample_data["Procyon"]["pass_rate"] == 1.0:
            results["Procyon_correct"] = results["Procyon_correct"] + 1
        if sample_data["CFR"]["pass_rate"] == 1.0:
            results["CFR_correct"] = results["CFR_correct"] + 1
        if sample_data["JADX"]["pass_rate"] == 1.0:
            results["JADX_correct"] = results["JADX_correct"] + 1
        if sample_data["Fernflower"]["pass_rate"] == 1.0:
            results["Fernflower_correct"] = results["Fernflower_correct"] + 1
        if sample_data["Krakatau"]["pass_rate"] == 1.0:
            results["Krakatau_correct"] = results["Krakatau_correct"] + 1

        if  sample_data["Procyon"]["java_gen"] == False and \
            sample_data["CFR"]["java_gen"] == False and \
            sample_data["JADX"]["java_gen"] == False and \
            sample_data["Fernflower"]["java_gen"] == False and \
            sample_data["Krakatau"]["java_gen"] == False:
            fail_java.append(
                {
                    "Class_name" : sample_data["Class_name"],
                    "Gold" : sample_data["Gold"],
                    "java_gen" : False,
                    "compile" : False,
                }
            )
        elif sample_data["Procyon"]["compile"] == False and \
            sample_data["CFR"]["compile"] == False and \
            sample_data["JADX"]["compile"] == False and \
            sample_data["Fernflower"]["compile"] == False and \
            sample_data["Krakatau"]["compile"] == False:
            fail_java.append(
                {
                    "Class_name" : sample_data["Class_name"],
                    "Gold" : sample_data["Gold"],
                    "java_gen" : True,
                    "compile" : False,
                }
            )



    Procyon_pass_rate = results["Procyon_correct"]
    CFR_pass_rate = results["CFR_correct"]
    JADX_pass_rate = results["JADX_correct"]
    Fernflower_pass_rate = results["Fernflower_correct"]
    Krakatau_pass_rate = results["Krakatau_correct"]


    # print pass rates
    print(f"Procyon pass rate: {Procyon_pass_rate}/{len(data)} ({round(Procyon_pass_rate/len(data)*100, 2)}%)")
    print(f"CFR pass rate: {CFR_pass_rate}/{len(data)}({round(CFR_pass_rate/len(data)*100, 2)}%)")
    print(f"JADX pass rate: {JADX_pass_rate}/{len(data)}({round(JADX_pass_rate/len(data)*100, 2)}%)")
    print(f"Fernflower pass rate: {Fernflower_pass_rate}/{len(data)}({round(Fernflower_pass_rate/len(data)*100, 2)}%)")
    print(f"Krakatau pass rate: {Krakatau_pass_rate}/{len(data)}({round(Krakatau_pass_rate/len(data)*100, 2)}%)")

    # generate example for all fail to compile
    with open(args.output_path, 'w') as f:
        for sample in fail_java:
            f.write(json.dumps(sample) + "\n")
            #print("\n java file: \n " + sample["Gold"]["java_source"] + "\n")

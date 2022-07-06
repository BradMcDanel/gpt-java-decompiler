import os
import re
import tempfile
import math

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
JAVA_8 = "/usr/lib/jvm/java-1.8.0-openjdk-amd64/bin/java"
JAVAC_8 = "/usr/lib/jvm/java-1.8.0-openjdk-amd64/bin/javac"
JAVA_11 = "/usr/lib/jvm/java-11-openjdk-amd64/bin/java"
JAVAC_11 = "/usr/lib/jvm/java-11-openjdk-amd64/bin/javac"
GOOGLE_JAVA_FORMAT = f"{JAVA_11} -jar jars/google-java-format-1.15.0-all-deps.jar"
EVOSUITE_JAR_FILES = [
    os.path.join(BASE_DIR, "jars/evosuite-standalone-runtime-1.0.6.jar"),
    os.path.join(BASE_DIR, "jars/junit-4.12.jar"),
    os.path.join(BASE_DIR, "jars/hamcrest-core-1.3.jar"),
]
EVOSUITE_JAR = os.path.join(BASE_DIR, "jars/evosuite-1.0.6.jar")
PYOCYON_JAR = os.path.join(BASE_DIR, "jars/procyon-decompiler-0.6.0.jar")
CFR_JAR = os.path.join(BASE_DIR, "jars/cfr-0.152.jar")
JADX_PATH = os.path.join(BASE_DIR, "jars/jadx/build/jadx/bin/jadx")
FERNFLOWER_JAR = os.path.join(BASE_DIR, "jars/fernflower.jar")
KRAKATAU_PATH = os.path.join(BASE_DIR, "krakatau/decompile.py")

# taken from: https://github.com/facebookresearch/CodeGen/blob/c62e719f7c8a16b4e7653188eff24282a11f4ca5/codegen_sources/test_generation/create_tests.py#L41
MUTATION_SCORE_CUTOFF = 0.9
MAX_JAVA_MEM = 4096
CPUS_PER_TASK = 80

def preprocess_str(java_str):
    '''
    Preprocess java string
    1. Remove all packages
    '''
    # remove all packages
    java_str = re.sub(r'package\s+[^;]+;', '', java_str)

    return java_str


def format_str(class_name, java_str):
    '''
    Formats a java string using google-java-format
    '''
    with tempfile.TemporaryDirectory() as temp_dir:
        java_file_path = os.path.join(temp_dir, class_name + ".java")
        with open(java_file_path, "w") as f:
            f.write(java_str)
        
        output_path = os.path.join(temp_dir, "class_name.java.out")
        exit_code = os.system(f"{GOOGLE_JAVA_FORMAT} {java_file_path} > {output_path} 2> /dev/null")

        if exit_code != 0:
            return None

        # read contents of class file to a string
        with open(output_path, "r") as f:
            formatted_str = f.read()

        return formatted_str


def get_class_name(java_str):
    '''
    Extracts the class name from a java string.
    '''
    # look for the first line that has class keyword
    for line in java_str.split("\n"):
        # find all regions not in quotes
        spans = re.findall(r'[^"]+', line)
        for span in spans:
            if "class " in span:
                start_of_class_name = span.find("class ") + len("class ")
                end_of_class_name = span[start_of_class_name:].find(" ")
                if end_of_class_name == -1:
                    end_of_class_name = len(span) - start_of_class_name
                class_name = span[start_of_class_name:start_of_class_name + end_of_class_name]

                # check if class name is valid
                if class_name.isalnum():
                    return class_name

def has_unresolved_imports(java_str):
    '''
    Checks if a java string has unresolved imports.
    '''
    # should return True if any line has an import that is not `java.*``
    for line in java_str.split("\n"):
        if line.strip().startswith("import "):
            if "java." not in line:
                return True
    
    return False

def compile_str(class_name, java_str):
    '''
    Compiles a java file (string) and returns the class name.
    '''
    if has_unresolved_imports(java_str):
        return None

    with tempfile.TemporaryDirectory() as temp_dir:
        java_file_path = os.path.join(temp_dir, class_name + ".java")
        with open(java_file_path, "w") as f:
            f.write(java_str)
        
        exit_code = os.system(f"{JAVAC_8} -cp . {java_file_path} > /dev/null 2>&1")

        if exit_code != 0:
            return None

        class_file_path = os.path.join(temp_dir, class_name + ".class")
        if not os.path.exists(class_file_path):
            return None

        # read contents of class file to a string
        with open(class_file_path, "rb") as f:
            class_str = f.read()

        return class_str

def compile_jar(class_name):
    cmd = f"jar cvf {class_name}.jar {class_name}.class > /dev/null 2>&1"
    os.system(cmd)

def disassemble_str(class_name, byte_code_str):
    '''
    Generates java asm given a byte_code_str.
    '''
    with tempfile.TemporaryDirectory() as temp_dir:
        class_file_path = os.path.join(temp_dir, class_name + ".class")
        with open(class_file_path, "wb") as f:
            f.write(byte_code_str)

        cmd = f"python krakatau/disassemble.py -out {temp_dir} {class_file_path} > /dev/null 2>&1"
        exit_code = os.system(cmd)

        if exit_code != 0:
            return None


        # extract all files from the temp dir (recursively)
        files = []
        for root, dirs, filenames in os.walk(temp_dir):
            for filename in filenames:
                files.append(os.path.join(root, filename))
        
        # find the single file ending in .j
        for file in files:
            if file.endswith(".j"):
                with open(file, "r") as f:
                    asm_str = f.read()

                return asm_str


def assemble_str(class_name, asm_str, verbose=False):
    '''
    Generates byte code given an asm_str.
    '''
    with tempfile.TemporaryDirectory() as temp_dir:
        class_file_path = os.path.join(temp_dir, class_name + ".class")
        with open(class_file_path, "w") as f:
            f.write(asm_str)

        if verbose:
            cmd = f"python krakatau/assemble.py -out {temp_dir} {class_file_path}"
        else:
            cmd = f"python krakatau/assemble.py -out {temp_dir} {class_file_path} > /dev/null 2>&1"
        exit_code = os.system(cmd)

        if exit_code != 0:
            return None

        # extract all files from the temp dir (recursively)
        files = []
        for root, dirs, filenames in os.walk(temp_dir):
            for filename in filenames:
                files.append(os.path.join(root, filename))
        
        # find the single file ending in .class
        for file in files:
            if file.endswith(".class"):
                with open(file, "rb") as f:
                    byte_code_str = f.read()

                return byte_code_str


def run_str(class_name, byte_code_str):
    '''
    Runs a java class (string) and returns the output.
    '''
    with tempfile.TemporaryDirectory() as temp_dir:
        class_file_path = os.path.join(temp_dir, class_name + ".class")
        with open(class_file_path, "wb") as f:
            f.write(byte_code_str)

        output_path = os.path.join(temp_dir, "output.txt")

        os.system(f"{JAVA_8} -cp {temp_dir} {class_name} > {output_path}")

        # read contents of class file to a string
        with open(output_path, "r") as f:
            output = f.read()

        # clean up files
        os.remove(class_file_path)
        os.remove(output_path)

        return output
    

def evosuite_gen_test(class_name, byte_code_str, search_budget=1):
    '''
    Generates an evosuite test for a java class (string).
    '''
    with tempfile.TemporaryDirectory() as temp_dir:
        # get current working directory
        home_dir = os.getcwd()

        # change to temp directory
        os.chdir(temp_dir)

        class_file_path = f"{class_name}.class"
        with open(class_file_path, "wb") as f:
            f.write(byte_code_str)


        # adapted from: https://github.com/facebookresearch/CodeGen/blob/c62e719f7c8a16b4e7653188eff24282a11f4ca5/codegen_sources/test_generation/create_tests.py#L139
        cmd = (
            f"{JAVA_8} -jar {EVOSUITE_JAR} -class {class_name} -projectCP . "
            f'-criterion "LINE:BRANCH:WEAKMUTATION:OUTPUT:METHOD:CBRANCH:STRONGMUTATION" '
            f"-Dshow_progress=false "
            f"-Dassertion_strategy=MUTATION "
            f"-Dminimize=true "
            f"-Dsearch_budget=20 "
            f"-Ddouble_precision=0.0001 "
            f"-Dmax_mutants_per_test 200 "
            f'-Danalysis_criteria="LINE,BRANCH,EXCEPTION,WEAKMUTATION,OUTPUT,METHOD,METHODNOEXCEPTION,CBRANCH,STRONGMUTATION" '
            f"-Doutput_variables=TARGET_CLASS,Random_Seed,criterion,Size,Length,BranchCoverage,Lines,Coverage,Covered_Lines,LineCoverage,MethodCoverage,Size,Length,Total_Goals,Covered_Goals,MutationScore,OutputCoverage "
            f"-Dmax_int {int(math.sqrt(2 ** 31 - 1))} "
            f"-mem={MAX_JAVA_MEM} "
            f"-Dextra_timeout=180 "
            "> /dev/null 2>&1"
        )

        exit_code = os.system(cmd)
        if exit_code != 0:
            os.chdir(home_dir)
            return None, None

        # read generated test files to a string
        test_file_path = os.path.join("evosuite-tests", f"{class_name}_ESTest.java")
        scaffold_file_path = os.path.join("evosuite-tests", f"{class_name}_ESTest_scaffolding.java")

        # if test "evosuite-tests" directory does not exist, and return
        if not os.path.exists("evosuite-tests"):
            os.chdir(home_dir)
            return None, None

        with open(test_file_path, "r") as f:
            test_str = f.read()

        with open(scaffold_file_path, "r") as f:
            scaffold_str = f.read()

        # change back to home directory
        os.chdir(home_dir)

        return test_str, scaffold_str


def evosuite_compile_and_run_test(class_name, byte_code_str, test_str, scaffold_str, verbose=False):
    '''
    Compiles and runs an evosuite test for a java class (string).
    '''
    with tempfile.TemporaryDirectory() as temp_dir:
        # get current working directory
        home_dir = os.getcwd()

        # change to temp directory
        os.chdir(temp_dir)

        # write bytecode, test, and scaffold files
        class_file_path = f"{class_name}.class"
        test_file_path = f"{class_name}_ESTest.java"
        scaffold_file_path = f"{class_name}_ESTest_scaffolding.java"
        with open(class_file_path, "wb") as f:
            f.write(byte_code_str)

        with open(test_file_path, "w") as f:
            f.write(test_str)

        with open(scaffold_file_path, "w") as f:
            f.write(scaffold_str)

        # compile test and scaffold files
        CLASSPATH = "CLASSPATH=.:" +  ":".join(EVOSUITE_JAR_FILES)
        cmd = f"{CLASSPATH} {JAVAC_8} *.java > /dev/null 2>&1"
        os.system(cmd)

        # run the test
        cmd = f"{CLASSPATH} {JAVA_8} org.junit.runner.JUnitCore {class_name}_ESTest > output.txt 2>&1"
        os.system(cmd)

        # open test output and get last line
        with open(os.path.join(temp_dir, "output.txt"), "r") as f:
            output = f.readlines()[-2]

        # compute pass_rate
        if "OK" in output:
            pass_rate = 1.0
        else:
            runs, fails = output.split(",")
            runs = float(runs.split(": ")[1])
            fails = float(fails.split(": ")[1])
            pass_rate = 1 - (fails / runs)
        
        # change back to home directory
        os.chdir(home_dir)

        return pass_rate


def procyon_decompiler(class_name, byte_code_str):
    '''
    Generates decompiled file by procyon.
    '''

    with tempfile.TemporaryDirectory() as temp_dir:
        home_dir = os.getcwd()
        # change to temp directory
        os.chdir(temp_dir)

        class_file_path = os.path.join(temp_dir, class_name + ".class")
        with open(class_file_path, "wb") as f:
            f.write(byte_code_str)

        cmd = f"{JAVA_8} -jar {PYOCYON_JAR} {class_name} > output.txt 2>&1"
        exit_code = os.system(cmd)

        if exit_code != 0:
            return None

        with open(os.path.join(temp_dir, "output.txt"), "r") as f:
            java_str = f.read()
            os.chdir(home_dir)
            return java_str

def CFR_decompiler(class_name, byte_code_str):
    '''
    Generates decompiled file by CFR.
    '''

    with tempfile.TemporaryDirectory() as temp_dir:
        home_dir = os.getcwd()
        # change to temp directory
        os.chdir(temp_dir)

        class_file_path = os.path.join(temp_dir, class_name + ".class")
        with open(class_file_path, "wb") as f:
            f.write(byte_code_str)

        cmd = f"{JAVA_8} -jar {CFR_JAR} {class_name} > output.txt 2>&1"
        exit_code = os.system(cmd)

        if exit_code != 0:
            return None

        with open(os.path.join(temp_dir, "output.txt"), "r") as f:
            java_str = f.read()
            os.chdir(home_dir)
            return java_str

def JADX_decompiler(class_name, byte_code_str):
    '''
    Generates decompiled file by CFR.
    '''

    with tempfile.TemporaryDirectory() as temp_dir:
        home_dir = os.getcwd()
        # change to temp directory
        os.chdir(temp_dir)

        class_file_path = os.path.join(temp_dir, class_name + ".class")
        with open(class_file_path, "wb") as f:
            f.write(byte_code_str)

        cmd = f"{JADX_PATH} -d out {class_name}.class > /dev/null 2>&1"
        exit_code = os.system(cmd)

        if exit_code != 0:
            return None

        with open(os.path.join(temp_dir, f"out/sources/defpackage/{class_name}.java"), "r") as f:
            java_str = f.read()
            os.chdir(home_dir)
            return java_str

def fernflower_decompiler(class_name, byte_code_str):
    '''
    Generates decompiled file by fernflower.
    '''

    with tempfile.TemporaryDirectory() as temp_dir:
        home_dir = os.getcwd()
        # change to temp directory
        os.chdir(temp_dir)

        class_file_path = os.path.join(temp_dir, class_name + ".class")
        with open(class_file_path, "wb") as f:
            f.write(byte_code_str)
        compile_jar(class_name)
        os.mkdir('out')
        cmd = f"{JAVA_11} -jar {FERNFLOWER_JAR} {class_name}.jar out/ > /dev/null 2>&1"
        exit_code = os.system(cmd)

        if exit_code != 0:
            return None
        os.chdir("out/")
        os.system(f"unzip {class_name}.jar > /dev/null 2>&1")
        with open(os.path.join(temp_dir, f"out/{class_name}.java"), "r") as f:
            java_str = f.read()
            os.chdir(home_dir)
            return java_str

def krakatau_decompiler(class_name, byte_code_str):
    '''
    Generates decompiled file by krakatau.
    '''

    with tempfile.TemporaryDirectory() as temp_dir:
        home_dir = os.getcwd()
        # change to temp directory
        os.chdir(temp_dir)

        class_file_path = os.path.join(temp_dir, class_name + ".class")
        with open(class_file_path, "wb") as f:
            f.write(byte_code_str)
        compile_jar(class_name)
        os.mkdir('out')
        cmd = f"python2 {KRAKATAU_PATH} -out out -nauto -path /usr/lib/jvm/java-1.8.0-openjdk-amd64/jre/lib/rt.jar {class_name}.jar > /dev/null 2>&1"
        exit_code = os.system(cmd)

        if exit_code != 0:
            return None
        with open(os.path.join(temp_dir, f"out/{class_name}.java"), "r") as f:
            java_str = f.read()
            os.chdir(home_dir)
            return java_str


if __name__=="__main__":
    gold_str = '''
    package com.example;

    public class Add {
        public static void main(String[] args) {
            System.out.println(add(3, 1));
        }

        public static int add(int a, int b) {
            return a + b;
        }
    }
    '''

    pred_str = '''
    package com.example.that.does.not.exist;

    public class Add {
        public static int add(int a, int b) {
            return a + b + 1;
        }
    }
    '''

    # get class name
    class_name = get_class_name(gold_str)

    # preprocess java string
    gold_str = preprocess_str(gold_str)
    pred_str = preprocess_str(pred_str)

    # compile bytecode
    gold_byte_code = compile_str(class_name, gold_str)
    pred_byte_code = compile_str(class_name, pred_str)

    asm = disassemble_str(class_name, gold_byte_code)
    asm_byte_code = assemble_str(class_name, asm)
    #print(asm)

    decomp_procyon_java = procyon_decompiler(class_name, gold_byte_code)
    procyon_byte_code = compile_str(class_name, decomp_procyon_java)

    decomp_CFR_java = CFR_decompiler(class_name, gold_byte_code)
    CFR_byte_code = compile_str(class_name, decomp_CFR_java)
    #print(decomp_CFR_java)
    
    decomp_JADX_java = JADX_decompiler(class_name, gold_byte_code)
    decomp_JADX_java = preprocess_str(decomp_CFR_java)
    JADX_byte_code = compile_str(class_name, decomp_JADX_java)
    #print('\n'+decomp_JADX_java)

    decomp_fernflower_java = fernflower_decompiler(class_name, gold_byte_code)
    fernflower_byte_code = compile_str(class_name, decomp_fernflower_java)
    #print(decomp_fernflower_java)

    decomp_krakatau_java = krakatau_decompiler(class_name, gold_byte_code)
    krakatau_byte_code = compile_str(class_name, decomp_krakatau_java)
    #print(decomp_krakatau_java)

    output = run_str(class_name, gold_byte_code)
    output = run_str(class_name, asm_byte_code)
    print(output)
    #output = run_str(class_name, JADX_byte_code)
    #print(output)
    
    # format code
    gold_str = format_str(class_name, gold_str)
    pred_str = format_str(class_name, pred_str)

    # generate tests using evosuite and gold bytecode
    test_str, scaffold_str = evosuite_gen_test(class_name, gold_byte_code)

    # compile and run tests
    gold_pass_rate = evosuite_compile_and_run_test(class_name, gold_byte_code, test_str, scaffold_str)
    pred_pass_rate = evosuite_compile_and_run_test(class_name, pred_byte_code, test_str, scaffold_str)
    
    procyon_pass_rate = evosuite_compile_and_run_test(class_name, procyon_byte_code, test_str, scaffold_str)
    CFR_pass_rate = evosuite_compile_and_run_test(class_name, CFR_byte_code, test_str, scaffold_str)
    JADX_pass_rate = evosuite_compile_and_run_test(class_name, JADX_byte_code, test_str, scaffold_str)
    fernflower_pass_rate = evosuite_compile_and_run_test(class_name, fernflower_byte_code, test_str, scaffold_str)
    krakatau_pass_rate = evosuite_compile_and_run_test(class_name, krakatau_byte_code, test_str, scaffold_str)

    # print pass rates
    print(f"Gold pass rate: {gold_pass_rate}")
    print(f"Pred pass rate: {pred_pass_rate}")
    print(f"Procyon pass rate: {procyon_pass_rate}")
    print(f"CFR pass rate: {CFR_pass_rate}")
    print(f"JADX pass rate: {JADX_pass_rate}")
    print(f"fernflower pass rate: {fernflower_pass_rate}")
    print(f"krakatau pass rate: {krakatau_pass_rate}")


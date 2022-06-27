import os
import re
import tempfile

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
JAVA_8 = "/usr/lib/jvm/java-1.8.0-openjdk-amd64/bin/java"
JAVAC_8 = "/usr/lib/jvm/java-1.8.0-openjdk-amd64/bin/javac"
JAVA_11 = "/usr/lib/jvm/java-11-openjdk-amd64/bin/java"
JAVAC_11 = "/usr/lib/jvm/java-11-openjdk-amd64/bin/javac"
GOOGLE_JAVA_FORMAT = f"{JAVA_11} -jar jars/google-java-format-1.15.0-all-deps.jar"
JAR_FILES = [
    os.path.join(BASE_DIR, "jars/evosuite-standalone-runtime-1.0.6.jar"),
    os.path.join(BASE_DIR, "jars/junit-4.12.jar"),
    os.path.join(BASE_DIR, "jars/hamcrest-core-1.3.jar"),
]
EVOSUITE_JAR = os.path.join(BASE_DIR, "jars/evosuite-1.0.6.jar")

def format_str(class_name, java_str):
    '''
    Formats a java string using google-java-format
    '''
    with tempfile.TemporaryDirectory() as temp_dir:
        java_file_path = os.path.join(temp_dir, class_name + '.java')
        with open(java_file_path, 'w') as f:
            f.write(java_str)
        
        output_path = os.path.join(temp_dir, 'class_name.java.out')
        os.system(f'{GOOGLE_JAVA_FORMAT} {java_file_path} > {output_path}')

        # read contents of class file to a string
        with open(output_path, 'r') as f:
            formatted_str = f.read()

        return formatted_str


def get_class_name(java_str):
    '''
    Extracts the class name from a java string.
    '''
    # look for the first line that has class keyword
    for line in java_str.split('\n'):
        # find all regions not in quotes
        spans = re.findall(r'[^"]+', line)
        for span in spans:
            if 'class ' in span:
                start_of_class_name = span.find('class ') + len('class ')
                end_of_class_name = span[start_of_class_name:].find(' ')
                if end_of_class_name == -1:
                    end_of_class_name = len(span) - start_of_class_name
                return span[start_of_class_name:start_of_class_name + end_of_class_name]


def compile_str(class_name, java_str):
    '''
    Compiles a java file (string) and returns the class name.
    '''
    with tempfile.TemporaryDirectory() as temp_dir:
        java_file_path = os.path.join(temp_dir, class_name + '.java')
        with open(java_file_path, 'w') as f:
            f.write(java_str)
        
        os.system(f'{JAVAC_8} -cp . {java_file_path}')

        # read contents of class file to a string
        class_file_path = os.path.join(temp_dir, class_name + '.class')
        with open(class_file_path, 'rb') as f:
            class_str = f.read()

        return class_str


def run_str(class_name, byte_code_str):
    '''
    Runs a java class (string) and returns the output.
    '''
    with tempfile.TemporaryDirectory() as temp_dir:
        class_file_path = os.path.join(temp_dir, class_name + '.class')
        with open(class_file_path, 'wb') as f:
            f.write(byte_code_str)

        output_path = os.path.join(temp_dir, 'output.txt')

        os.system(f'java -cp {temp_dir} {class_name} > {output_path}')

        # read contents of class file to a string
        with open(output_path, 'r') as f:
            output = f.read()

        # clean up files
        os.remove(class_file_path)
        os.remove(output_path)

        return output
    

def evosuite_gen_test(class_name, byte_code_str):
    '''
    Generates an evosuite test for a java class (string).
    '''
    with tempfile.TemporaryDirectory() as temp_dir:
        # get current working directory
        home_dir = os.getcwd()

        # change to temp directory
        os.chdir(temp_dir)

        class_file_path = f"{class_name}.class"
        with open(class_file_path, 'wb') as f:
            f.write(byte_code_str)


        EVOSUITE_GEN_TESTS = f"{JAVA_8} -jar {EVOSUITE_JAR} -class {class_name} -projectCP .  -Dsearch_budget=5 > /dev/null 2>&1"
        os.system(EVOSUITE_GEN_TESTS)

        # read generated test files to a string
        test_file_path = os.path.join('evosuite-tests', f"{class_name}_ESTest.java")
        scaffold_file_path = os.path.join('evosuite-tests', f"{class_name}_ESTest_scaffolding.java")

        with open(test_file_path, 'r') as f:
            test_str = f.read()

        with open(scaffold_file_path, 'r') as f:
            scaffold_str = f.read()

        # change back to home directory
        os.chdir(home_dir)

        return test_str, scaffold_str


def evosuite_compile_and_run_test(class_name, byte_code_str, test_str, scaffold_str):
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
        with open(class_file_path, 'wb') as f:
            f.write(byte_code_str)

        with open(test_file_path, 'w') as f:
            f.write(test_str)

        with open(scaffold_file_path, 'w') as f:
            f.write(scaffold_str)

        # compile test and scaffold files
        CLASSPATH = 'CLASSPATH=.:' +  ':'.join(JAR_FILES)
        cmd = f'{CLASSPATH} {JAVAC_8} *.java'
        os.system(cmd)

        # run the test
        cmd = f'{CLASSPATH} {JAVA_8} org.junit.runner.JUnitCore {class_name}_ESTest > output.txt 2>&1'
        os.system(cmd)

        # open test output and get last line
        with open(os.path.join(temp_dir, 'output.txt'), 'r') as f:
            output = f.readlines()[-2]

        # compute pass_rate
        if "OK" in output:
            pass_rate = 1.0
        else:
            runs, fails = output.split(',')
            runs = float(runs.split(': ')[1])
            fails = float(fails.split(': ')[1])
            pass_rate = 1 - (fails / runs)
        
        # change back to home directory
        os.chdir(home_dir)

        return pass_rate


if __name__=='__main__':
    gold_str = '''
    public class Add {
        public static int add(int a, int b) {
            return a + b;
        }
    }
    '''

    test_str = '''
    public class Add {
        public static int add(int a, int b) {
            return a + b + 1;
        }
    }
    '''

    # get class name
    class_name = get_class_name(gold_str)

    # format code
    gold_str = format_str(class_name, gold_str)
    pred_str = format_str(class_name, test_str)

    # compile bytecode
    gold_byte_code = compile_str(class_name, gold_str)
    pred_byte_code = compile_str(class_name, pred_str)

    # generate tests using evosuite and gold bytecode
    test_str, scaffold_str = evosuite_gen_test(class_name, gold_byte_code)

    # compile and run tests
    gold_pass_rate = evosuite_compile_and_run_test(class_name, gold_byte_code, test_str, scaffold_str)
    pred_pass_rate = evosuite_compile_and_run_test(class_name, pred_byte_code, test_str, scaffold_str)

    # print pass rates
    print(f'Gold pass rate: {gold_pass_rate}')
    print(f'Pred pass rate: {pred_pass_rate}')

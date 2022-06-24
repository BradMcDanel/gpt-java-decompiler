import os
import re
import tempfile
JAVA_11 = "/usr/lib/jvm/java-11-openjdk-amd64/bin/java"
JAVAC = "javac"
GOOGLE_JAVA_FORMAT = f"{JAVA_11} -jar google-java-format-1.15.0-all-deps.jar"

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
        
        os.system(f'{JAVAC} -cp . {java_file_path}')

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
    

if __name__=='__main__':
    java_str = '''
    public class Test {
        public static void main(String[] args) {
            System.out.println("Hello, World! - " + add(1, 2));
        }

        public static int add(int a, int b) {
            return a + b;
        }
    }
    '''
    class_name = get_class_name(java_str)
    java_str = format_str(class_name, java_str)
    class_str = compile_str(class_name, java_str)
    output = run_str(class_name, class_str)
    print(output)

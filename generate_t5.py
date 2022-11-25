import argparse
import json

from transformers import AutoTokenizer, T5ForConditionalGeneration
import split_java

BATCH_SIZE = 4


def generate(model, tokenizer, inputs):
    """
    Split inputs into batches and generate outputs.
    """
    outputs = []
    for i in range(0, len(inputs), BATCH_SIZE):
        batch = inputs[i:i + BATCH_SIZE]
        batch = tokenizer(batch, return_tensors="pt", padding=True)
        input_ids = batch.input_ids.cuda()
        generated_ids = model.generate(
            input_ids,
            max_length=4096,
            num_beams=4,
            repetition_penalty=2.5,
            no_repeat_ngram_size=2,
        )
        outputs.extend(tokenizer.batch_decode(generated_ids, skip_special_tokens=True))
    return outputs

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", type=str, required=True, help="model path")
    parser.add_argument("--input-file", type=str, required=True, help="data file")
    parser.add_argument("--output-file", type=str, required=True, help="output file")
    args = parser.parse_args()

    data = []
    with open(args.input_file) as f:
        for line in f:
            data.append(json.loads(line))


    model = T5ForConditionalGeneration.from_pretrained(args.model_path)
    tokenizer = AutoTokenizer.from_pretrained("Salesforce/codet5-base")
    model = model.cuda()

    idx = 0
    class_idx = 0
    java_output = []
    while True:
        # collect all methods for class_idx
        methods = []
        while idx < len(data) and data[idx]["class_idx"] == class_idx:
            methods.append(data[idx]["src"])
            idx += 1
        
        pred_java_methods = generate(model, tokenizer, methods)

        pred_java = split_java.merge_java_methods(pred_java_methods)
        print(pred_java)

        methods = []
        class_idx += 1

        input("Press Enter to continue...")

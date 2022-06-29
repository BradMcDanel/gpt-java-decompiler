import argparse
import os

from datasets import load_dataset
from transformers import AutoTokenizer, AutoModelForCausalLM
from transformers import TrainingArguments, Trainer


if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-name", type=str, required=True, help="Model name")
    parser.add_argument("--data-dir", type=str, required=True, help="Data directory")
    parser.add_argument("--output-dir", type=str, required=True, help="Model output directory")
    args = parser.parse_args()

    # load dataset
    train_path = os.path.join(args.data_dir, "train.json")
    test_path = os.path.join(args.data_dir, "test.json")
    dataset = load_dataset("json", data_files={"train": train_path, "test": test_path})

    # load model
    model = AutoModelForCausalLM.from_pretrained(args.model_name)
    tokenizer = AutoTokenizer.from_pretrained(args.model_name)
    tokenizer.pad_token = tokenizer.eos_token

    def tokenize_function(examples):
        texts = []
        for i in range(len(examples["java_source"])):
            text = "<JAVA>\n" + examples["java_source"][i] + "\n<\Java>\n<JASM>\n" + examples["jasm_code"][i]
            text += "<|endoftext|>"
            texts.append(text)
         
        output = tokenizer(texts, return_tensors="np", padding=True, truncation=True)
        output["labels"] = output.input_ids.copy()

        return output

    tokenized_datasets = dataset.map(tokenize_function, batched=True)

    training_args = TrainingArguments(
        output_dir=args.output_dir,
        evaluation_strategy="steps",
        optim="adamw_hf",
        learning_rate=1e-5,
        weight_decay=0.0,
        per_device_train_batch_size=6,
        per_device_eval_batch_size=6,
        num_train_epochs=1,
        save_strategy="steps",
        save_steps=1000,
    )


    # train model
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_datasets["train"],
        eval_dataset=tokenized_datasets["test"],
    )

    trainer.train()

    # save model
    model.save_pretrained(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)

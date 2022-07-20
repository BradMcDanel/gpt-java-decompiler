import argparse
import os
import json

from datasets import load_dataset
from transformers import AutoTokenizer, AutoModelForCausalLM
from transformers import TrainingArguments, Trainer
from transformers import TrainerCallback

import prompts


class LoggingCallback(TrainerCallback):
    def __init__(self, train_log_file, eval_log_file):
        self.train_log_file = train_log_file
        self.eval_log_file = eval_log_file

    def on_log(self, args, state, control, logs=None, **kwargs):
        _ = logs.pop("total_flos", None)
        if state.is_local_process_zero:
            if "loss" in logs:
                with open(self.train_log_file, "a") as f:
                    f.write(json.dumps(logs) + "\n")
            elif "eval_loss" in logs:
                with open(self.eval_log_file, "a") as f:
                    f.write(json.dumps(logs) + "\n")


if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-name", type=str, required=True, help="model name")
    parser.add_argument("--tokenizer-name", type=str, required=True, help="model name")
    parser.add_argument("--target", choices=["java_to_jasm", "jasm_to_java"], required=True,
                        help="target output")
    parser.add_argument("--data-dir", type=str, required=True, help="data directory")
    parser.add_argument("--output-dir", type=str, required=True, help="model output directory")
    parser.add_argument("--batch-size-per-device", type=int, default=1, help="batch size")
    parser.add_argument("--epochs", type=int, default=1, help="epochs")
    parser.add_argument("--lr", type=float, default=1e-5, help="learning rate")
    parser.add_argument("--wd", type=float, default=0.01, help="weight decay")
    args = parser.parse_args()

    # load dataset
    train_path = os.path.join(args.data_dir, "train_methods.json")
    test_path = os.path.join(args.data_dir, "test_methods.json")
    dataset = load_dataset("json", data_files={"train": train_path, "test": test_path})
    # dataset = dataset.remove_columns(["class_name", "java_test", "java_scaffold"])

    # load model
    model = AutoModelForCausalLM.from_pretrained(args.model_name)
    model.use_cache = False
    tokenizer = AutoTokenizer.from_pretrained(args.tokenizer_name)
    tokenizer.pad_token = tokenizer.eos_token


    def tokenize_function(examples):
        texts = []
        for i in range(len(examples["java_source"])):
            text = prompts.get_train_prompt(
                args.target,
                examples["java_source"][i],
                examples["jasm_code"][i],
            )
            texts.append(text)
         
        output = tokenizer(texts, return_tensors="np", padding=True, truncation=True)
        output["labels"] = output.input_ids.copy()

        return output


    tokenized_datasets = dataset.map(tokenize_function, batched=True,
                                     remove_columns=["java_source", "jasm_code"])

    training_args = TrainingArguments(
        output_dir=args.output_dir,
        optim="adafactor",
        learning_rate=args.lr,
        weight_decay=args.wd,
        per_device_train_batch_size=args.batch_size_per_device,
        per_device_eval_batch_size=args.batch_size_per_device,
        num_train_epochs=args.epochs,
        save_strategy="steps",
        save_steps=10000,
        save_total_limit=2,
        gradient_accumulation_steps=1,
        gradient_checkpointing=True,
        logging_dir=os.path.join(args.output_dir, "logs"),
        logging_steps=5,
        evaluation_strategy="steps",
        eval_steps=3000,
        # disable_tqdm=True,
    )

    # train model
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_datasets["train"],
        eval_dataset=tokenized_datasets["test"],
        callbacks=[
            LoggingCallback(
                os.path.join(args.output_dir, "train_log.json"),
                os.path.join(args.output_dir, "eval_log.json"),
            )
        ],
    )


    train_results = trainer.train()

    # save model
    model.save_pretrained(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)

    # save argparse arguments
    with open(os.path.join(args.output_dir, "training_args.json"), "w") as f:
        json.dump(vars(args), f, indent=4)

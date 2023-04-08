import argparse
import os
import json

from datasets import load_dataset
from transformers import AutoTokenizer, AutoModelForCausalLM
from transformers import TrainingArguments, Trainer
from transformers import TrainerCallback
from transformers.utils import logging

import logging
import re
def set_global_logging_level(level=logging.ERROR, prefices=[""]):
    """
    Override logging levels of different modules based on their name as a prefix.
    It needs to be invoked after the modules have been loaded so that their loggers have been initialized.

    Args:
        - level: desired level. e.g. logging.INFO. Optional. Default is logging.ERROR
        - prefices: list of one or more str prefices to match (e.g. ["transformers", "torch"]). Optional.
          Default is `[""]` to match all active loggers.
          The match is a case-sensitive `module_name.startswith(prefix)`
    """
    prefix_re = re.compile(fr'^(?:{ "|".join(prefices) })')
    for name in logging.root.manager.loggerDict:
        if re.match(prefix_re, name):
            logging.getLogger(name).setLevel(level)

set_global_logging_level(logging.ERROR, ["transformers", "nlp", "torch", "tensorflow", "tensorboard", "wandb"])


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
    train_path = os.path.join(args.data_dir, "train_small.json")
    test_path = os.path.join(args.data_dir, "test_small.json")
    dataset = load_dataset("json", data_files={"train": train_path, "test": test_path})
    # dataset = dataset.remove_columns(["class_name", "java_test", "java_scaffold"])

    # load model
    model = AutoModelForCausalLM.from_pretrained(args.model_name)
    tokenizer = AutoTokenizer.from_pretrained(args.tokenizer_name)

    # add special tokens
    tokenizer.add_special_tokens({"additional_special_tokens": ["<|java|>", "<|jasm|>"]})
    tokenizer.pad_token = tokenizer.eos_token
    model.resize_token_embeddings(len(tokenizer))

    def tokenize_function(example):
        text = prompts.get_train_prompt(
            args.target,
            example["src"],
            example["tgt"],
        )
        print(text)
        assert False
         
        output = tokenizer(text, return_tensors="np", truncation=True)
        print(output["input_ids"].shape)
        output["labels"] = output.input_ids.copy()

        return output


    tokenized_datasets = dataset.map(tokenize_function, batched=False)
                                     
    training_args = TrainingArguments(
        output_dir=args.output_dir,
        optim="adafactor",
        learning_rate=args.lr,
        weight_decay=args.wd,
        per_device_train_batch_size=args.batch_size_per_device,
        per_device_eval_batch_size=args.batch_size_per_device,
        num_train_epochs=args.epochs,
        save_strategy="steps",
        save_steps=500,
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

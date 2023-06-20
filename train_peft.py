import os
# os.environ["CUDA_VISIBLE_DEVICES"]="0"
import torch
import torch.nn as nn
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM, DataCollatorWithPadding, TrainingArguments
from peft import LoraConfig, get_peft_model 
import transformers
from datasets import load_dataset
import argparse
import json

class CustomTrainer(transformers.Trainer):
    def log(self, logs):
        super().log(logs)  # Call the original log method
        with open(os.path.join(self.args.output_dir, 'train_logs.txt'), 'a') as train_log_file:
            train_log_file.write(json.dumps({**logs, 'step': self.state.global_step})+'\n')

    def evaluation_loop(self, dataloader, description, prediction_loss_only=False):
        metrics = super().evaluation_loop(dataloader, description, prediction_loss_only)
        with open(os.path.join(self.args.output_dir, 'eval_logs.txt'), 'a') as eval_log_file:
            eval_log_file.write(json.dumps({**metrics, 'step': self.state.global_step})+'\n')
        return metrics

def load_and_tokenize_data(filepath, tokenizer, source_max_length, target_max_length):
    dataset = load_dataset('json', data_files=filepath, split='train')

    def tokenize_function(example):
        # Encode the text
        encoded = tokenizer.encode_plus(
            'Convert Java Assembly to Java Code: ' + example['src'], 
            truncation=True, 
            max_length=source_max_length, 
            padding="max_length",
            return_attention_mask=True
        )

        # Add the labels
        encoded['labels'] = tokenizer.encode(
            example['tgt'], 
            truncation=True, 
            max_length=target_max_length, 
            padding="max_length"
        )

        return encoded

    dataset = dataset.map(tokenize_function, remove_columns=["method_idx", "class_idx"])
    return dataset


def print_trainable_parameters(model):
    """
    Prints the number of trainable parameters in the model.
    """
    trainable_params = 0
    all_param = 0
    for _, param in model.named_parameters():
        all_param += param.numel()
        if param.requires_grad:
            trainable_params += param.numel()
    print(
        f"trainable params: {trainable_params} || all params: {all_param} || trainable%: {100 * trainable_params / all_param}"
    )


class CastOutputToFloat(nn.Sequential):
  def forward(self, x): return super().forward(x).to(torch.float32)


parser = argparse.ArgumentParser()
parser.add_argument('--checkpoint', type=str, default="Salesforce/codet5p-770m")
parser.add_argument('--train_dataset', type=str, required=True)
parser.add_argument('--val_dataset', type=str, required=True)
parser.add_argument('--output_dir', type=str, required=True)
parser.add_argument('--source_max_length', type=int, default=1500)
parser.add_argument('--target_max_length', type=int, default=500)
parser.add_argument('--num_train_epochs', type=int, default=1)
parser.add_argument('--per_device_train_batch_size', type=int, default=8)
parser.add_argument('--logging_steps', type=int, default=100)
parser.add_argument('--save_steps', type=int, default=500)
parser.add_argument('--seed', type=int, default=42)

args = parser.parse_args()

model = AutoModelForSeq2SeqLM.from_pretrained(
    args.checkpoint,
    # load_in_8bit=True, 
    device_map='auto',
    trust_remote_code=True,
)

tokenizer = AutoTokenizer.from_pretrained(args.checkpoint)
data_collator = DataCollatorWithPadding(tokenizer=tokenizer)


train_dataset = load_and_tokenize_data(args.train_dataset, tokenizer, args.source_max_length, args.target_max_length)
val_dataset = load_and_tokenize_data(args.val_dataset, tokenizer, args.source_max_length, args.target_max_length)

for param in model.parameters():
  param.requires_grad = False  # freeze the model - train adapters later
  if param.ndim == 1:
    # cast the small parameters (e.g. layernorm) to fp32 for stability
    param.data = param.data.to(torch.float32)

# model.gradient_checkpointing_enable()  # reduce number of stored activations
model.enable_input_require_grads()
# model.decoder.lm_head = CastOutputToFloat(model.decoder.lm_head)
print(model)

if  args.checkpoint in ["Salesforce/codet5p-220m", "Salesforce/codet5p-770m"]:
    config = LoraConfig(
        task_type="SEQ_2_SEQ_LM",
        r=32,
        lora_alpha=32,
        target_modules=["q", "v"],
        lora_dropout=0.01,
    )
elif args.checkpoint in ["Salesforce/codet5p-3B"]:
    config = LoraConfig(
        task_type="SEQ_2_SEQ_LM",
        r=32,
        lora_alpha=32,
        target_modules=["q", "v"],
        lora_dropout=0.01,
    )


model = get_peft_model(model, config)
print_trainable_parameters(model)

training_args = TrainingArguments(
    output_dir=args.output_dir,
    num_train_epochs=args.num_train_epochs,
    per_device_train_batch_size=args.per_device_train_batch_size,
    logging_steps=args.logging_steps,
    save_steps=args.save_steps,
    seed=args.seed,
    report_to="none",  # Disable logging to W&B
    fp16=True,  # Enable mixed precision training
    gradient_accumulation_steps=2,
    save_total_limit=1, # Save only the last checkpoint
    learning_rate=2e-4,
    warmup_steps=100,
    weight_decay=0.01,
)

trainer = CustomTrainer(
    model=model,
    args=training_args,
    train_dataset=train_dataset,
    eval_dataset=val_dataset,
    data_collator=data_collator,
)

# model.config.use_cache = False

trainer.train()

model.save_pretrained(args.output_dir)

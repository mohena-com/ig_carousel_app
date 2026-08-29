import torch
from unsloth import FastLanguageModel
from datasets import load_dataset
from trl import SFTTrainer
from transformers import TrainingArguments

def train_slm():
    max_seq_length = 2048
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name="unsloth/Qwen2.5-3B-Instruct",
        max_seq_length=max_seq_length,
        load_in_4bit=True
    )

    model = FastLanguageModel.get_peft_model(
        model,
        r=16,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        lora_alpha=16,
        lora_dropout=0,
        bias="none",
    )

    def format_prompts(batch):
        texts = []
        for input_text, json_output in zip(batch['input_text'], batch['json_output']):
            messages = [
                {"role": "system", "content": "You are a micro-content copywriter. Convert input text into an Instagram Carousel JSON schema."},
                {"role": "user", "content": input_text},
                {"role": "assistant", "content": json_output}
            ]
            texts.append(tokenizer.apply_chat_template(messages, tokenize=False))
        return {"text": texts}

    # Expects dataset.jsonl with 'input_text' and 'json_output' fields
    dataset = load_dataset("json", data_files="dataset.jsonl")
    dataset = dataset.map(format_prompts, batched=True)

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset["train"],
        dataset_text_field="text",
        max_seq_length=max_seq_length,
        args=TrainingArguments(
            per_device_train_batch_size=2,
            gradient_accumulation_steps=4,
            warmup_steps=10,
            max_steps=120,
            learning_rate=2e-4,
            fp16=not torch.cuda.is_bf16_supported(),
            bf16=torch.cuda.is_bf16_supported(),
            logging_steps=1,
            output_dir="lora_output",
        ),
    )
    trainer.train()
    model.save_pretrained("qwen2.5_ig_carousel_lora")
    tokenizer.save_pretrained("qwen2.5_ig_carousel_lora")
    print("Fine-tuning finished and model saved to 'qwen2.5_ig_carousel_lora'.")

if __name__ == "__main__":
    train_slm()
"""QLoRA fine-tuning: ek open model ko wabot ke behaviors sikhata hai.

GPU chahiye (Google Colab / Kaggle ka free T4 bhi chalta hai, ya apna NVIDIA GPU).
Pehle: pip install -r finetune/requirements-finetune.txt
Chalao: python finetune/train_lora.py --base Qwen/Qwen2.5-3B-Instruct

Sirf LoRA adapter save hota hai (chhoti file). Use base model me milane ke liye merge_lora.py.
"""

import argparse
import json
import random
import sys
from pathlib import Path

import torch
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from torch.utils.data import Dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    Trainer,
    TrainingArguments,
)

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))

from finetune.encoding import encode  # noqa: E402


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line)["messages"] for line in f if line.strip()]


class ListDataset(Dataset):
    def __init__(self, rows):
        self.rows = rows

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, i):
        return self.rows[i]


def make_collator(pad_id):
    def collate(batch):
        longest = max(len(x["input_ids"]) for x in batch)
        ids, labels, mask = [], [], []
        for x in batch:
            pad = longest - len(x["input_ids"])
            ids.append(x["input_ids"] + [pad_id] * pad)
            labels.append(x["labels"] + [-100] * pad)
            mask.append([1] * len(x["input_ids"]) + [0] * pad)
        return {
            "input_ids": torch.tensor(ids),
            "labels": torch.tensor(labels),
            "attention_mask": torch.tensor(mask),
        }

    return collate


def load_rows(tok, path, max_len):
    rows, skipped = [], 0
    for messages in read_jsonl(path):
        item = encode(tok, messages, max_len)
        if item is None:
            skipped += 1
        else:
            rows.append(item)
    print(f"{path}: {len(rows)} examples, {skipped} skip (bahut lambe ya token mismatch)")
    return rows


def load_model(base, use_4bit, dtype):
    kwargs = {"device_map": "auto"} if torch.cuda.is_available() else {}
    if use_4bit:
        kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=dtype,
        )
    try:
        return AutoModelForCausalLM.from_pretrained(base, torch_dtype=dtype, **kwargs)
    except TypeError:  # naye transformers me naam 'dtype' hai
        return AutoModelForCausalLM.from_pretrained(base, dtype=dtype, **kwargs)


def show_samples(model, tok, val_path, n=4):
    """Training ke baad val ke kuch sawalon par model ka jawab dikhata hai."""
    model.eval()
    if hasattr(model, "config"):
        model.config.use_cache = True
    for messages in read_jsonl(val_path)[:n]:
        prompt = tok.apply_chat_template(messages[:-1], tokenize=False, add_generation_prompt=True)
        inputs = tok(prompt, return_tensors="pt", add_special_tokens=False).to(model.device)
        with torch.no_grad():
            out = model.generate(**inputs, max_new_tokens=80, do_sample=False)
        answer = tok.decode(out[0][inputs["input_ids"].shape[1] :], skip_special_tokens=True)
        print("\nUSER    :", messages[-2]["content"])
        print("EXPECTED:", messages[-1]["content"])
        print("MODEL   :", answer.strip())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="Qwen/Qwen2.5-3B-Instruct")
    parser.add_argument("--train", default=str(HERE / "data" / "train.jsonl"))
    parser.add_argument("--val", default=str(HERE / "data" / "val.jsonl"))
    parser.add_argument("--out", default=str(HERE / "out" / "lora"))
    parser.add_argument("--epochs", type=float, default=2)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--max-len", type=int, default=1536)
    parser.add_argument("--batch", type=int, default=2)
    parser.add_argument("--grad-accum", type=int, default=8)
    parser.add_argument("--rank", type=int, default=16)
    parser.add_argument("--no-4bit", action="store_true", help="Quantization ke bina (zyada VRAM)")
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    random.seed(args.seed)
    torch.manual_seed(args.seed)
    use_cuda = torch.cuda.is_available()
    if not use_cuda:
        print("DHYAN: GPU nahi mila. CPU par training bahut dheemi hogi.")
    use_bf16 = use_cuda and torch.cuda.is_bf16_supported()
    dtype = torch.bfloat16 if use_bf16 else torch.float16

    tok = AutoTokenizer.from_pretrained(args.base)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    train_rows = load_rows(tok, args.train, args.max_len)
    val_rows = load_rows(tok, args.val, args.max_len)

    use_4bit = not args.no_4bit
    model = load_model(args.base, use_4bit, dtype)
    if use_4bit:
        model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
    else:
        model.gradient_checkpointing_enable()
        model.enable_input_require_grads()
    model.config.use_cache = False

    model = get_peft_model(
        model,
        LoraConfig(
            r=args.rank,
            lora_alpha=args.rank * 2,
            lora_dropout=0.05,
            target_modules="all-linear",
            task_type="CAUSAL_LM",
        ),
    )
    model.print_trainable_parameters()

    training_args = TrainingArguments(
        output_dir=str(Path(args.out).parent / "checkpoints"),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch,
        per_device_eval_batch_size=args.batch,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr,
        lr_scheduler_type="cosine",
        warmup_ratio=0.03,
        logging_steps=10,
        eval_strategy="epoch",
        save_strategy="epoch",
        save_total_limit=2,
        bf16=use_bf16,
        fp16=use_cuda and not use_bf16,
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        optim="paged_adamw_8bit" if use_4bit and use_cuda else "adamw_torch",
        report_to="none",
        remove_unused_columns=False,
        seed=args.seed,
    )
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=ListDataset(train_rows),
        eval_dataset=ListDataset(val_rows),
        data_collator=make_collator(tok.pad_token_id),
    )
    trainer.train()

    Path(args.out).mkdir(parents=True, exist_ok=True)
    trainer.model.save_pretrained(args.out)
    tok.save_pretrained(args.out)
    print(f"\nAdapter save hua: {args.out}")
    show_samples(trainer.model, tok, args.val)


if __name__ == "__main__":
    main()

"""LoRA adapter ko base model me milakar poora model save karta hai (GGUF/Ollama se pehle ka step).

Chalao: python finetune/merge_lora.py --base Qwen/Qwen2.5-3B-Instruct
CPU par chalta hai (3B model ke liye lagbhag 8 GB RAM), GPU zaruri nahi.
"""

import argparse
from pathlib import Path

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

HERE = Path(__file__).parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="Qwen/Qwen2.5-3B-Instruct")
    parser.add_argument("--adapter", default=str(HERE / "out" / "lora"))
    parser.add_argument("--out", default=str(HERE / "out" / "merged"))
    args = parser.parse_args()

    tok = AutoTokenizer.from_pretrained(args.base)
    try:
        base = AutoModelForCausalLM.from_pretrained(args.base, torch_dtype=torch.float16)
    except TypeError:
        base = AutoModelForCausalLM.from_pretrained(args.base, dtype=torch.float16)
    model = PeftModel.from_pretrained(base, args.adapter)
    merged = model.merge_and_unload()
    merged.save_pretrained(args.out, safe_serialization=True)
    tok.save_pretrained(args.out)
    print(f"Merged model save hua: {args.out}")


if __name__ == "__main__":
    main()

"""Model ko val set (alag business, jo training me nahi tha) par parakhta hai. Django nahi chahiye.

Chalao (Ollama chal raha ho):
    python finetune/eval_val.py --model wabot-v1 --base-url http://localhost:11434/v1
Base model se tulna ke liye wahi command --model qwen2.5:3b ke saath chalao.

Naap: sahi marker ([[UNKNOWN]], [[HANDOVER]]), faltu marker nahi, sahi bhasha (Devanagari ya Roman),
aur facts wale jawab me sahi numbers (Rs 1500, 6 baje jaise).
"""

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

import requests

HERE = Path(__file__).parent
MARKERS = ("[[UNKNOWN]]", "[[HANDOVER]]")


def devanagari_ratio(text):
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    return sum("ऀ" <= c <= "ॿ" for c in letters) / len(letters)


def numbers(text):
    return set(re.findall(r"\d+", text))


def judge(expected, got):
    """Naap ka naam -> pass (True/False)."""
    results = {}
    for marker in MARKERS:
        if expected.strip() == marker:
            results["sahi marker"] = marker in got
            return results
    results["faltu marker nahi"] = not any(m in got for m in MARKERS)
    if devanagari_ratio(expected) > 0.3 or devanagari_ratio(got) > 0.3:
        results["sahi bhasha (Hindi)"] = (devanagari_ratio(expected) > 0.3) == (
            devanagari_ratio(got) > 0.3
        )
    need = numbers(expected)
    if need:
        results["numbers sahi"] = need <= numbers(got)
    results["chhota jawab"] = len(got) <= 600
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--base-url", default="http://localhost:11434/v1")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--data", default=str(HERE / "data" / "val.jsonl"))
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()

    rows = [json.loads(line)["messages"] for line in open(args.data, encoding="utf-8")]
    rows = rows[: args.limit]
    headers = {"Authorization": f"Bearer {args.api_key}"} if args.api_key else {}

    score = defaultdict(lambda: [0, 0])
    for i, messages in enumerate(rows, 1):
        expected = messages[-1]["content"]
        response = requests.post(
            f"{args.base_url.rstrip('/')}/chat/completions",
            headers=headers,
            json={"model": args.model, "messages": messages[:-1], "max_tokens": 300},
            timeout=args.timeout,
        )
        response.raise_for_status()
        got = response.json()["choices"][0]["message"]["content"] or ""
        for name, ok in judge(expected, got).items():
            score[name][0] += bool(ok)
            score[name][1] += 1
        if i % 10 == 0:
            print(f"{i}/{len(rows)} ho gaye")

    print(f"\nModel: {args.model}   Sawal: {len(rows)}")
    for name, (ok, total) in sorted(score.items()):
        print(f"  {name:<24} {ok}/{total}  ({100 * ok / total:.0f}%)")


if __name__ == "__main__":
    main()

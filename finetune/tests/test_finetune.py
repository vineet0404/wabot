import json
from pathlib import Path

from apps.ai.prompt_template import FALLBACK_UNKNOWN
from finetune.encoding import encode
from finetune.make_dataset import BUSINESSES, HANDOVER, LANGS, UNKNOWN, build
from finetune.make_dataset import main as make_main


class CharTokenizer:
    """Asli tokenizer ki jagah: har character ek token. ChatML jaisa template."""

    def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=False):
        text = "".join(f"<|im_start|>{m['role']}\n{m['content']}<|im_end|>\n" for m in messages)
        if add_generation_prompt:
            text += "<|im_start|>assistant\n"
        return text

    def __call__(self, text, add_special_tokens=False):
        return {"input_ids": [ord(c) for c in text]}


def decode(ids):
    return "".join(chr(i) for i in ids)


def test_encode_masks_everything_except_last_assistant_reply():
    msgs = [
        {"role": "system", "content": "SYS"},
        {"role": "user", "content": "q1"},
        {"role": "assistant", "content": "OLD"},
        {"role": "user", "content": "q2"},
        {"role": "assistant", "content": "NEW"},
    ]
    item = encode(CharTokenizer(), msgs, max_len=500)
    trained = decode([i for i in item["labels"] if i != -100])
    assert trained.startswith("NEW")
    assert "OLD" not in trained and "SYS" not in trained and "q2" not in trained
    assert len(item["input_ids"]) == len(item["labels"])


def test_encode_skips_too_long_examples():
    msgs = [
        {"role": "system", "content": "x" * 100},
        {"role": "user", "content": "q"},
        {"role": "assistant", "content": "a"},
    ]
    assert encode(CharTokenizer(), msgs, max_len=50) is None


def test_dataset_structure_and_behaviors():
    import random

    for biz in BUSINESSES:
        rows = build(biz, random.Random(1), repeat=2)
        assert rows
        kinds = {r["meta"]["kind"].split(":")[0] for r in rows}
        assert {"fact", "unknown", "handover", "booking", "greeting", "injection"} <= kinds
        for r in rows:
            roles = [m["role"] for m in r["messages"]]
            assert roles[0] == "system" and roles[-1] == "assistant"
            assert all(a != b for a, b in zip(roles[1:], roles[2:], strict=False))
            assert all(m["content"].strip() for m in r["messages"])
            # prompt me business ki jaankari honi chahiye
            assert biz["header"] in r["messages"][0]["content"]


def test_markers_only_as_final_answer_and_unknown_history_uses_fallback():
    import random

    rows = build(BUSINESSES[0], random.Random(2), repeat=3)
    for r in rows:
        earlier = [m["content"] for m in r["messages"][:-1] if m["role"] == "assistant"]
        assert UNKNOWN not in earlier and HANDOVER not in earlier
    multi = [r for r in rows if r["meta"]["kind"].startswith("multi:unknown")]
    assert multi and any(r["messages"][2]["content"] == FALLBACK_UNKNOWN for r in multi)


def test_facts_cover_all_languages_and_questions_not_in_info_are_unknown():
    for biz in BUSINESSES:
        for fact in biz["facts"]:
            assert set(fact["q"]) == set(LANGS) == set(fact["a"])
        info_text = " ".join(f["info"] for f in biz["facts"]).lower()
        for qs in biz["unknown"].values():
            for q in qs:
                for word in ("mri", "yoga", "hostel", "swimming", "bridal", "party hall"):
                    if word in q.lower():
                        assert word not in info_text


def test_val_is_a_business_not_used_in_training(tmp_path, monkeypatch):
    monkeypatch.setattr("sys.argv", ["make_dataset", "--out", str(tmp_path), "--repeat", "1"])
    make_main()
    train = [json.loads(line) for line in (Path(tmp_path) / "train.jsonl").open(encoding="utf-8")]
    val = [json.loads(line) for line in (Path(tmp_path) / "val.jsonl").open(encoding="utf-8")]
    assert {r["meta"]["business"] for r in val} == {"FitZone Gym"}
    assert "FitZone Gym" not in {r["meta"]["business"] for r in train}
    assert len(train) > 200 and len(val) > 40


def test_eval_scorer_accepts_good_and_rejects_bad_answers():
    from finetune.eval_val import judge

    assert all(
        judge("Membership Rs 1500 per month hai.", "Ji, Rs 1500 per month lagta hai.").values()
    )
    assert not all(judge("Membership Rs 1500 per month hai.", "[[UNKNOWN]]").values())
    assert all(judge("[[UNKNOWN]]", "[[UNKNOWN]]").values())
    assert not all(judge("[[HANDOVER]]", "Zaroor, batata hoon").values())
    hindi_ok = judge("जिम रोज़ सुबह 6 बजे खुलता है।", "हमारा जिम सुबह 6 बजे खुलता है।")
    assert all(hindi_ok.values())
    assert not all(judge("जिम रोज़ सुबह 6 बजे खुलता है।", "Gym opens at 6 AM.").values())

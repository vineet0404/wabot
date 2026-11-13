"""Training example banane ka logic (torch ya transformers import nahi karta)."""


def encode(tok, messages, max_len):
    """Sirf aakhri assistant jawab par loss lagta hai. Baaki (system, user, purane jawab) mask."""
    prompt = tok.apply_chat_template(messages[:-1], tokenize=False, add_generation_prompt=True)
    full = tok.apply_chat_template(messages, tokenize=False)
    if not full.startswith(prompt):
        return None
    prompt_ids = tok(prompt, add_special_tokens=False)["input_ids"]
    full_ids = tok(full, add_special_tokens=False)["input_ids"]
    if len(full_ids) > max_len or full_ids[: len(prompt_ids)] != prompt_ids:
        return None
    labels = [-100] * len(prompt_ids) + full_ids[len(prompt_ids) :]
    return {"input_ids": full_ids, "labels": labels}

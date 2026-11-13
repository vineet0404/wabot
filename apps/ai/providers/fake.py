from .base import LLMProvider, LLMResult


class FakeProvider(LLMProvider):
    """Bina key aur internet ke testing ke liye. Customer ka aakhri message echo karta hai."""

    def complete(self, system: str, messages: list[dict], max_tokens: int) -> LLMResult:
        last = messages[-1]["content"].splitlines()[-1] if messages else ""
        text = f"Aapne likha: {last}"
        prompt_chars = len(system) + sum(len(m["content"]) for m in messages)
        return LLMResult(
            text=text,
            input_tokens=prompt_chars // 4,
            output_tokens=len(text) // 4 + 1,
            model="fake",
        )

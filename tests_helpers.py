"""Tests ke liye chhote helpers (jaise scripted fake LLM)."""

from apps.ai.providers.base import LLMError, LLMProvider, LLMResult


class Scripted(LLMProvider):
    def __init__(self, text="", error=None, tokens=(10, 5)):
        self.text, self.error, self.tokens = text, error, tokens
        self.calls = []

    def complete(self, system, messages, max_tokens):
        self.calls.append((system, messages))
        if self.error:
            raise self.error
        return LLMResult(self.text, *self.tokens)


__all__ = ["LLMError", "Scripted"]


class ByPrompt(LLMProvider):
    """Booking-extraction wali call (system me 'extract appointment') ko alag jawab deta hai."""

    def __init__(self, reply="Kal kis samay aana chahenge?", extraction="{}"):
        self.reply, self.extraction = reply, extraction
        self.extract_calls = 0

    def complete(self, system, messages, max_tokens):
        if "extract appointment details" in system:
            self.extract_calls += 1
            return LLMResult(self.extraction, 10, 5)
        return LLMResult(self.reply, 10, 5)

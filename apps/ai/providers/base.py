from abc import ABC, abstractmethod
from dataclasses import dataclass


class LLMError(Exception):
    """Provider se jawab nahi aaya (network, key, limit wagairah)."""


@dataclass
class LLMResult:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""


class LLMProvider(ABC):
    """Har AI provider ye class banata hai. Naya provider jodna ho to sirf `complete` likho.

    messages: [{"role": "user" | "assistant", "content": "..."}], pehla hamesha user ka.
    """

    @abstractmethod
    def complete(self, system: str, messages: list[dict], max_tokens: int) -> LLMResult: ...

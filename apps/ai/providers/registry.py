from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string

from .base import LLMProvider
from .openai_compatible import PRESET_URLS, OpenAICompatibleProvider

BUILTIN = {
    "fake": "apps.ai.providers.fake.FakeProvider",
    "claude": "apps.ai.providers.anthropic.AnthropicProvider",
    "anthropic": "apps.ai.providers.anthropic.AnthropicProvider",
}


def get_provider() -> LLMProvider:
    """LLM_PROVIDER se provider banata hai.

    fake | claude | openai_compatible | openai | groq | together | openrouter | gemini | ollama
    ya apni class ka poora path, jaise  myproject.ai.MyProvider
    """
    name = (settings.LLM_PROVIDER or "fake").strip()
    if name == "openai_compatible" or name in PRESET_URLS:
        return OpenAICompatibleProvider(preset=name)
    path = BUILTIN.get(name, name)
    if "." not in path:
        known = ", ".join(sorted([*BUILTIN, "openai_compatible", *PRESET_URLS]))
        raise ImproperlyConfigured(
            f"LLM_PROVIDER '{name}' samajh nahi aaya. Ye chalte hain: {known}, "
            "ya apni class ka path (package.module.Class)."
        )
    provider_class = import_string(path)
    if not (isinstance(provider_class, type) and issubclass(provider_class, LLMProvider)):
        raise ImproperlyConfigured(f"{path} LLMProvider ki subclass honi chahiye.")
    return provider_class()

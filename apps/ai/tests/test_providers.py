import pytest
from django.core.exceptions import ImproperlyConfigured

from apps.ai.providers.anthropic import AnthropicProvider
from apps.ai.providers.base import LLMError, LLMProvider, LLMResult
from apps.ai.providers.fake import FakeProvider
from apps.ai.providers.openai_compatible import OpenAICompatibleProvider
from apps.ai.providers.registry import get_provider


class FakeResponse:
    def __init__(self, status=200, data=None, text=""):
        self.status_code = status
        self._data = data
        self.text = text

    def json(self):
        if self._data is None:
            raise ValueError("no json")
        return self._data


class MyCustomProvider(LLMProvider):
    def complete(self, system, messages, max_tokens):
        return LLMResult(text="custom")


def test_default_is_fake(settings):
    settings.LLM_PROVIDER = "fake"
    assert isinstance(get_provider(), FakeProvider)


@pytest.mark.parametrize(
    "name,url_part",
    [
        ("openai", "api.openai.com"),
        ("groq", "api.groq.com"),
        ("together", "together.xyz"),
        ("openrouter", "openrouter.ai"),
        ("gemini", "generativelanguage.googleapis.com"),
        ("ollama", "host.docker.internal:11434"),
        ("local", "ollama:11434"),
    ],
)
def test_presets_pick_right_base_url(settings, name, url_part):
    settings.LLM_PROVIDER = name
    settings.LLM_BASE_URL = ""
    settings.LLM_MODEL = "some-model"
    provider = get_provider()
    assert isinstance(provider, OpenAICompatibleProvider)
    assert url_part in provider.base_url


def test_custom_base_url_overrides_preset(settings):
    settings.LLM_PROVIDER = "openai_compatible"
    settings.LLM_BASE_URL = "http://localhost:8080/v1/"
    settings.LLM_MODEL = "m"
    assert get_provider().base_url == "http://localhost:8080/v1"


def test_openai_compatible_needs_url_and_model(settings):
    settings.LLM_BASE_URL = ""
    settings.LLM_MODEL = "m"
    with pytest.raises(LLMError):
        OpenAICompatibleProvider(preset="openai_compatible")
    settings.LLM_BASE_URL = "http://x/v1"
    settings.LLM_MODEL = ""
    with pytest.raises(LLMError):
        OpenAICompatibleProvider(preset="openai_compatible")


def test_custom_class_path_works(settings):
    settings.LLM_PROVIDER = "apps.ai.tests.test_providers.MyCustomProvider"
    assert get_provider().complete("s", [], 10).text == "custom"


def test_unknown_provider_and_wrong_class_rejected(settings):
    settings.LLM_PROVIDER = "kuchbhi"
    with pytest.raises(ImproperlyConfigured):
        get_provider()
    settings.LLM_PROVIDER = "apps.core.models.Tenant"
    with pytest.raises(ImproperlyConfigured):
        get_provider()


def test_openai_compatible_request_and_parsing(settings, monkeypatch):
    settings.LLM_BASE_URL = "http://llm.test/v1"
    settings.LLM_API_KEY = "sk-test"
    settings.LLM_MODEL = "my-model"
    settings.LLM_MAX_TOKENS_PARAM = "max_completion_tokens"
    settings.LLM_TEMPERATURE = ""
    seen = {}

    def fake_post(url, headers, json, timeout):
        seen.update(url=url, headers=headers, json=json)
        return FakeResponse(
            data={
                "choices": [{"message": {"content": "Namaste"}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 3},
            }
        )

    monkeypatch.setattr("apps.ai.providers.openai_compatible.requests.post", fake_post)
    result = OpenAICompatibleProvider().complete("SYS", [{"role": "user", "content": "hi"}], 50)

    assert seen["url"] == "http://llm.test/v1/chat/completions"
    assert seen["headers"]["Authorization"] == "Bearer sk-test"
    assert seen["json"]["messages"][0] == {"role": "system", "content": "SYS"}
    assert seen["json"]["messages"][1] == {"role": "user", "content": "hi"}
    assert seen["json"]["max_completion_tokens"] == 50
    assert "temperature" not in seen["json"]
    assert (result.text, result.input_tokens, result.output_tokens) == ("Namaste", 12, 3)


def test_openai_compatible_no_key_means_no_auth_header(settings, monkeypatch):
    settings.LLM_BASE_URL = "http://localhost:11434/v1"
    settings.LLM_API_KEY = ""
    settings.LLM_MODEL = "qwen"
    seen = {}

    def fake_post(url, headers, json, timeout):
        seen["headers"] = headers
        return FakeResponse(data={"choices": [{"message": {"content": "ok"}}]})

    monkeypatch.setattr("apps.ai.providers.openai_compatible.requests.post", fake_post)
    OpenAICompatibleProvider().complete("s", [{"role": "user", "content": "x"}], 10)
    assert "Authorization" not in seen["headers"]


def test_openai_compatible_errors_become_llmerror(settings, monkeypatch):
    settings.LLM_BASE_URL = "http://llm.test/v1"
    settings.LLM_MODEL = "m"
    provider = OpenAICompatibleProvider()

    monkeypatch.setattr(
        "apps.ai.providers.openai_compatible.requests.post",
        lambda *a, **k: FakeResponse(status=401, text="bad key"),
    )
    with pytest.raises(LLMError):
        provider.complete("s", [], 10)

    monkeypatch.setattr(
        "apps.ai.providers.openai_compatible.requests.post",
        lambda *a, **k: FakeResponse(data={"unexpected": True}),
    )
    with pytest.raises(LLMError):
        provider.complete("s", [], 10)


def test_anthropic_request_and_parsing(settings, monkeypatch):
    settings.LLM_PROVIDER = "claude"
    settings.LLM_BASE_URL = ""
    settings.LLM_API_KEY = "ak-test"
    settings.LLM_MODEL = ""
    seen = {}

    def fake_post(url, headers, json, timeout):
        seen.update(url=url, headers=headers, json=json)
        return FakeResponse(
            data={
                "content": [{"type": "text", "text": "Namaste ji"}],
                "usage": {"input_tokens": 20, "output_tokens": 4},
            }
        )

    monkeypatch.setattr("apps.ai.providers.anthropic.requests.post", fake_post)
    provider = get_provider()
    assert isinstance(provider, AnthropicProvider)
    result = provider.complete("SYS", [{"role": "user", "content": "hi"}], 100)

    assert seen["url"] == "https://api.anthropic.com/v1/messages"
    assert seen["headers"]["x-api-key"] == "ak-test"
    assert seen["headers"]["anthropic-version"] == "2023-06-01"
    assert seen["json"]["system"] == "SYS"
    assert seen["json"]["messages"] == [{"role": "user", "content": "hi"}]
    assert seen["json"]["max_tokens"] == 100
    assert (result.text, result.input_tokens, result.output_tokens) == ("Namaste ji", 20, 4)


def test_anthropic_needs_key(settings):
    settings.LLM_API_KEY = ""
    with pytest.raises(LLMError):
        AnthropicProvider()


def _ok():
    return FakeResponse(
        data={"choices": [{"message": {"content": "hello"}}], "usage": {"prompt_tokens": 1}}
    )


def test_rate_limit_is_retried_then_succeeds(settings, monkeypatch):
    settings.LLM_BASE_URL, settings.LLM_MODEL, settings.LLM_RETRIES = "http://llm.test/v1", "m", 2
    waits, replies = (
        [],
        [FakeResponse(status=429, text="slow down"), FakeResponse(status=503), _ok()],
    )
    monkeypatch.setattr(
        "apps.ai.providers.openai_compatible.requests.post", lambda *a, **k: replies.pop(0)
    )
    monkeypatch.setattr("apps.ai.providers.openai_compatible.time.sleep", waits.append)
    assert OpenAICompatibleProvider().complete("s", [], 10).text == "hello"
    assert len(waits) == 2 and all(w <= 5 for w in waits)


def test_retries_give_up_and_auth_errors_not_retried(settings, monkeypatch):
    settings.LLM_BASE_URL, settings.LLM_MODEL, settings.LLM_RETRIES = "http://llm.test/v1", "m", 2
    calls = []
    monkeypatch.setattr(
        "apps.ai.providers.openai_compatible.time.sleep", lambda s: calls.append("sleep")
    )
    monkeypatch.setattr(
        "apps.ai.providers.openai_compatible.requests.post",
        lambda *a, **k: calls.append("post") or FakeResponse(status=429, text="limit"),
    )
    with pytest.raises(LLMError, match="429"):
        OpenAICompatibleProvider().complete("s", [], 10)
    assert calls.count("post") == 3  # 1 + 2 retries

    calls.clear()
    monkeypatch.setattr(
        "apps.ai.providers.openai_compatible.requests.post",
        lambda *a, **k: calls.append("post") or FakeResponse(status=401, text="bad key"),
    )
    with pytest.raises(LLMError, match="401"):
        OpenAICompatibleProvider().complete("s", [], 10)
    assert calls == ["post"]  # galat key par dobara koshish nahi


def test_retry_after_header_is_capped(settings, monkeypatch):
    settings.LLM_BASE_URL, settings.LLM_MODEL, settings.LLM_RETRIES = "http://llm.test/v1", "m", 1
    waits = []
    slow = FakeResponse(status=429)
    slow.headers = {"retry-after": "120"}
    replies = [slow, _ok()]
    monkeypatch.setattr(
        "apps.ai.providers.openai_compatible.requests.post", lambda *a, **k: replies.pop(0)
    )
    monkeypatch.setattr("apps.ai.providers.openai_compatible.time.sleep", waits.append)
    OpenAICompatibleProvider().complete("s", [], 10)
    assert waits == [5.0]


def test_empty_reply_gives_clear_reason(settings, monkeypatch):
    settings.LLM_BASE_URL, settings.LLM_MODEL = "http://llm.test/v1", "m"
    provider = OpenAICompatibleProvider()

    def reply(finish):
        return FakeResponse(
            data={"choices": [{"message": {"content": None}, "finish_reason": finish}]}
        )

    monkeypatch.setattr(
        "apps.ai.providers.openai_compatible.requests.post", lambda *a, **k: reply("length")
    )
    with pytest.raises(LLMError, match="LLM_MAX_OUTPUT_TOKENS"):
        provider.complete("s", [], 10)

    monkeypatch.setattr(
        "apps.ai.providers.openai_compatible.requests.post", lambda *a, **k: reply("stop")
    )
    with pytest.raises(LLMError, match="khali jawab"):
        provider.complete("s", [], 10)

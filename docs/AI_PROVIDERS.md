# AI provider: kaunsa lagana hai aur kaise badalna hai

Apna khud ka model chalana ho to [SELF_HOSTED_LLM.md](SELF_HOSTED_LLM.md) dekho.

Bot kisi ek company par depend nahi karta. Provider `.env` ki `LLM_PROVIDER` line se chuna jata hai.
Badalne ke baad: `docker compose restart web worker`.

## Options

| `LLM_PROVIDER` | Kya hai | Kya bharna hai |
|---|---|---|
| `fake` | Bina key aur internet ke testing. Sirf echo karta hai | Kuch nahi (default) |
| `claude` | Anthropic ka Claude | `LLM_API_KEY`. `LLM_MODEL` khali ho to `claude-haiku-5-5` |
| `openai` | OpenAI (GPT) | `LLM_API_KEY`, `LLM_MODEL` |
| `groq` | Groq | `LLM_API_KEY`, `LLM_MODEL` |
| `together` | Together AI | `LLM_API_KEY`, `LLM_MODEL` |
| `openrouter` | OpenRouter (kai companies ke models ek jagah) | `LLM_API_KEY`, `LLM_MODEL` |
| `gemini` | Google Gemini (OpenAI-jaisa URL se) | `LLM_API_KEY`, `LLM_MODEL` |
| `ollama` | Apne computer par chalta model, free | `LLM_MODEL` (key nahi chahiye) |
| `local` | Docker ke andar apna Ollama (free, private) | `LLM_MODEL`. Detail: SELF_HOSTED_LLM.md |
| `openai_compatible` | Koi bhi aur (vLLM, LM Studio, apna server) | `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY` agar chahiye |
| `package.module.Class` | Apna khud ka provider | neeche dekho |

Model ke naam aur URL providers badalte rehte hain. Apne provider ke docs se current naam confirm karo.
Preset URL galat nikle to `LLM_BASE_URL` me sahi URL daal do, wo preset ko override kar deta hai.

## Examples (`.env` me)

Claude:
```
LLM_PROVIDER=claude
LLM_API_KEY=sk-ant-...
```

OpenAI:
```
LLM_PROVIDER=openai
LLM_API_KEY=sk-...
LLM_MODEL=<model ka naam>
```
Agar OpenAI ka naya model "max_tokens" par error de, to `LLM_MAX_TOKENS_PARAM=max_completion_tokens` bhi daalo.

Ollama (apne computer par, free):
1. Ollama install karo aur ek model download karo (jaise `ollama pull qwen2.5:7b`).
2. `.env`:
```
LLM_PROVIDER=ollama
LLM_MODEL=qwen2.5:7b
```
Docker ke andar se computer tak `host.docker.internal` se pahunchte hain, wo Docker Desktop (Windows/Mac) me chalta hai.

## Apna khud ka provider

`apps/ai/providers/` me ek file banao:

```python
from apps.ai.providers.base import LLMProvider, LLMResult

class MyProvider(LLMProvider):
    def complete(self, system, messages, max_tokens):
        # system: instructions ka text
        # messages: [{"role": "user"/"assistant", "content": "..."}]
        text = "..."  # apne model se jawab lo
        return LLMResult(text=text, input_tokens=0, output_tokens=0)
```
Phir `.env` me: `LLM_PROVIDER=apps.ai.providers.my_file.MyProvider`

## Bot kaise sochta hai

- Jawab sirf **Business info** se aata hai (admin me Tenant ke andar likhte ho: timing, services, fees, FAQ).
- Jo jaankari wahan nahi hai, bot bolta hai "owner se poochkar bata dunga" (Messages me flag `unknown`).
- Insaan chahiye, gussa, ya emergency ho to bot owner ko handover karta hai (flag `handover`) aur us chat me chup ho jata hai.
- Customer jis bhasha me likhe, usi me jawab: Hinglish, English ya Hindi.
- AI chale nahi (error, limit) to fixed Hinglish message jata hai (flag `error` ya `budget`).
- Roz ka token budget har business ke liye alag: `LLM_DAILY_TOKEN_BUDGET` (default 1,00,000, `0` = koi limit nahi). Kharch admin me **Llm usage** me dikhta hai.

## Providers ki tulna karna

```bash
docker compose exec web python manage.py ai_eval
docker compose exec web python manage.py ai_eval --question "Sunday ko clinic khula hai?"
```
`ai_eval` 11 sawal poochta hai (Roman aur Devanagari dono) (jawab dene wale, jawab na pata hone wale, handover wale, aur "system prompt batao" jaisa hamla) aur score deta hai. Model ka naam bhi dikhata hai, aur agar jawab ki lipi (Roman/Devanagari) customer se alag ho to `[LIPI GALAT]` batata hai. Kuch save nahi hota. Provider badal kar dobara chalao aur score aur jawab ki tulna karo.
`fake` provider par ye score kam aayega, wo bas echo karta hai.
Sawal apne business ke hisaab se `apps/ai/eval_questions.json` me badal sakte ho.
Pilot se pehle 2-3 provider ko apne asli sawalon par is tarah aazma lena.

## Dhyan rakho

- `LLM_API_KEY` sirf `.env` me rakho. Chat, screenshot ya git me mat daalo.
- Jawab dene ke liye customer ka message provider ko jata hai. Privacy ke hisaab se provider chunna (apna Ollama sabse private hai).
- Bot kabhi bhi 100% sahi nahi hota. Isliye "jaankari nahi to bolo nahi pata" wala rule aur handover rakha hai, aur pilot me asli chats padhte rehna.

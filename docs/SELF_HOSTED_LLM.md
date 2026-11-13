# Apna khud ka LLM chalana (bina kisi company ke API ke)

Matlab: koi bana-banaya open model (Qwen, Llama, Gemma jaisa) apne computer ya server par chalta hai.
Customers ke messages kisi bahar ki company ko nahi jaate, aur per jawab koi paisa nahi lagta.
Model ko scratch se train nahi karna padta, wo bahut mehenga aur mushkil hota hai.

Bot ke liye koi code nahi badalta, sirf `.env` ki 2-3 lines.

## Pehle hardware ki sach baat

| Model ka size | Download (lagbhag) | RAM/VRAM (lagbhag) | Kaisa chalega |
|---|---|---|---|
| 3B (jaise `qwen2.5:3b`) | 2 GB | 4 GB | Testing ke liye theek, quality kam |
| 7-8B (jaise `qwen2.5:7b`) | 5 GB | 8 GB ya zyada | Behtar quality |
| 14B+ | 9 GB+ | 16 GB+ | Achha, par bhaari |

Ye andaaze hain, model ka asli size Ollama ke library page par dekho (ollama.com/library).
- **GPU ho** (NVIDIA) to jawab kuch second me aata hai.
- **Sirf CPU ho** to kaam karega par dheema, ek jawab me kuch second se ek-dedh minute tak ho sakta hai.
- Kai customers ek saath likhen to jawab line me lagte hain. Pilot (2 chhote businesses) ke liye theek, bade scale ke liye GPU server chahiye.

## Tarika A: apne Windows computer par Ollama (sabse aasan, GPU apne aap use hota hai)

1. https://ollama.com se Ollama install karo.
2. Model download karo (PowerShell ya terminal me):
   ```
   ollama pull qwen2.5:3b
   ```
3. `.env` me:
   ```
   LLM_PROVIDER=ollama
   LLM_MODEL=qwen2.5:3b
   LLM_TIMEOUT=120
   ```
4. `docker compose restart web worker`

Docker ke andar se tumhare computer ka Ollama `host.docker.internal` se milta hai, wo Docker Desktop me chalta hai.

## Tarika B: Ollama bhi Docker me (sab kuch ek jagah)

```bash
docker compose --profile llm up -d ollama
docker compose exec ollama ollama pull qwen2.5:3b
```
`.env` me:
```
LLM_PROVIDER=local
LLM_MODEL=qwen2.5:3b
LLM_TIMEOUT=120
```
Phir `docker compose restart web worker`.
Ye container sirf CPU par chalega. Windows par GPU ke liye Tarika A behtar hai.

## Chalaya ya nahi, ye check karo

```bash
docker compose exec web python manage.py check_llm      # chal raha hai? kitna dheema?
docker compose exec web python manage.py ai_eval        # 9 sawal, score
```

## Kaunsa model

- Shuru karo `qwen2.5:3b` se (chhota, jaldi chalta hai). Phir `qwen2.5:7b`, `llama3.1:8b` ya `gemma2:9b` try karo.
- Kaunsa Hinglish me achha hai ye **maine test nahi kiya**. `ai_eval` se apne sawalon par khud tulna karo.
- Chhote models me ye galtiyan zyada hoti hain: jaankari na ho to bhi kuch bana dena, Hinglish me ulta jawab, aur "rules bhool jao" jaise hamle par phisal jana. Isliye `ai_eval` ka score dekho aur pilot me asli chats padhte raho.

## Live (asli businesses ke liye) chalana ho to

- Laptop 24 ghante on nahi rehta. Ek alag server chahiye: kiraye ka GPU server (ya CPU server, dheema par sasta).
- Zyada logon ke liye `vLLM` jaisa server behtar hai. Wo bhi OpenAI-jaisa API deta hai, to `LLM_PROVIDER=openai_compatible` aur `LLM_BASE_URL=http://<server>:8000/v1` se judta hai.
- Server ko internet par khula mat chhodo. Sirf bot ke server se pahunch me rakho.

## Hafta 3 ke liye (knowledge search)

Search ke liye "embedding" model chahiye. Wo bhi apna chal sakta hai (Ollama me multilingual embedding models milte hain). Hafta 3 me hum ye bhi provider-wise badalne layak banayenge.

## Dikkat aaye to

| Dikkat | Wajah aur ilaaj |
|---|---|
| `Nahi chala: network dikkat` | Ollama band hai. Tarika A me Ollama app chalu karo, Tarika B me `docker compose --profile llm up -d ollama` |
| `provider ne 404 diya` (model not found) | Model download nahi hua. `ollama pull <model>` |
| Timeout | `LLM_TIMEOUT` badhao (120 ya zyada) ya chhota model lo |
| Jawab ajeeb ya kata hua | Model ka context chhota hai. Compose me `OLLAMA_CONTEXT_LENGTH=8192` laga hai. Windows ke Ollama me ise environment variable se badhao ya naya version lo |
| Computer bahut dheema ho jata hai | Model chhota karo, aur kuch aur band karo |

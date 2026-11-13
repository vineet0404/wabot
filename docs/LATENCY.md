# Jawab tez kaise karein (WhatsApp par real-time feel)

Goal: customer ke message ke baad jawab jitna jaldi ho sake aaye. **WhatsApp me ChatGPT jaisi word-by-word streaming nahi hoti**, poora message ek saath jata hai. Isliye hum teen cheezein karte hain: jawab tez banao, turant blue tick + "typing..." dikhao, aur naapte raho.

> Honest baat: neeche ke time aur targets mere andaze hain. Maine koi asli LLM ya server par naapa nahi hai. Pehle `latency_report` se apne asli numbers dekho.

## 1. Time kahan lagta hai

```
customer msg -> Meta -> hamara webhook -> Redis -> worker -> [knowledge search] -> LLM -> WhatsApp send
```
Lagbhag saara time **LLM** me jata hai. Baaki hisse (webhook, Redis, send) aam taur par bahut chhote hote hain, par naapo, maano mat.

## 2. Naapna

```bash
docker compose exec web python manage.py latency_report            # pichle 7 din
docker compose exec web python manage.py latency_report --days 1 --tenant 1
docker compose exec web python manage.py check_llm                 # ek call ka time
```
`latency_report` dikhata hai: kul time (message aane se jawab bhejne tak) aur sirf AI ka time, p50 (aam) aur p95 (dheeme wale), aur 10 second se zyada kitne. Admin -> Messages me bhi har jawab ka `total_ms` dikhta hai.

**Mera lakshya (andaza, guarantee nahi):** p50 5 second se kam, p95 10 second se kam. p95 10 se upar ho to report khud `[FIX]` batati hai.

## 3. Tez karne ke tareeke (asar ke hisaab se)

| Kya karo | Kyun |
|---|---|
| **Tez provider / chhota model chuno** | Sabse bada asar. Chhota ya "fast" tier wala model aam taur par kaafi tez hota hai. Quality `ai_eval` se jaancho. |
| **Server provider ke paas rakho** | Network ka chakkar kam. India ka VPS aur provider ka nazdeeki region. |
| `LLM_MAX_OUTPUT_TOKENS` ghatao (300 -> 150-200) | Jawab chhote hote hain (1-3 vakya). Dhyan: Devanagari Hindi me tokens zyada lagte hain, jawab kat sakta hai. `ai_eval` dobara chalao. |
| `LLM_HISTORY_MESSAGES` ghatao (10 -> 6) | Kam text padhna. Par bahut kam karoge to follow-up sawal bhoolega. |
| Chhota `business_info`, saaf knowledge docs | Prompt chhota = tez. Bekaar paragraphs hatao. |
| `KB_TOP_K` kam (4 -> 2-3) | Prompt me kam tukde. |
| **Embedding search me extra call** | `EMBED_PROVIDER` chalu ho to har message par ek aur network call lagti hai. Tez nahi ho raha to `none` (keyword) try karo, ya local chhota embedding model. |
| Worker concurrency (`--concurrency 2`) | Kai customers ek saath aaye to line na lage. LLM provider ki rate limit dhyan me rakho. |
| `LLM_TIMEOUT` sahi rakho | Bahut kam rakha to jawab kat-kat kar fallback ho jayega; bahut zyada to customer intezaar karega. |

### Apna model (Ollama) chalate ho to
- **GPU ke bina bada model CPU par dheema hota hai.** Seconds nahi, kabhi-kabhi kai dus second. Chhota (1.5B-3B), quantized (Q4) model lo, ya GPU wala server.
- `OLLAMA_KEEP_ALIVE=24h` compose me laga diya hai taaki model memory me tika rahe; warna idle ke baad pehla jawab load hone me dheema hoga. (Ollama ke docs se confirm karna.)
- Server restart ke baad ek baar `ollama run <model> "hi"` chalao (warm-up).
- Fine-tuned model ko Q4_K_M quantize karne se tez bhi hota hai aur RAM bhi kam lagti hai (docs/FINETUNE.md).

## 4. Blue tick aur "typing..."

Customer ka message aate hi worker sabse pehle:
1. message ko **read** mark karta hai (blue tick), aur
2. **typing indicator** dikhata hai.

Customer ko lagta hai bot dekh raha hai, intezaar halka lagta hai. Hamara jawab jaate hi indicator hat jata hai (third-party doc ke mutabik ~25 second baad bhi apne aap hat jata hai).

Dhyan rakho:
- Ye request ka format maine ek third-party doc (jo Meta ka API dikhata hai) se liya, Meta ka official page mujhe nahi khula. **Apne test number par ek baar check karo** ki tick aur typing dikhte hain. Agar Meta ne format badla ho to bhi bot ka jawab nahi rukta (error sirf log me aata hai: `read receipt/typing nahi gaya`), bas tick/typing nahi dikhenge. `mark_read` ko `apps/whatsapp/client.py` me Meta ke current docs se milao.
- Token na ho (dry-run) to ye kuch nahi karta.
- Ye bhi Meta ke through ek extra call hai (timeout 5 second). Ye jawab ke time me thoda jodta hai (kitna, naapo).

## 5. Jo nahi ho sakta

- WhatsApp me word-by-word streaming: nahi.
- Agar customer ko 10+ second lagte hain to uska asli ilaaj tez model/server hai, typing indicator sirf rehem hai.
- Website par streaming chat box alag feature hai, abhi nahi banaya.

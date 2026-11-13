# Apna khud ka model fine-tune karna (open model, koi API nahi)

Is guide ka goal: ek open model ko wabot ke behavior sikhana, phir use Ollama par chalana. Isse Claude/OpenAI par depend nahi rehna padta.

> **Honest baat:** Training, merge aur GGUF wale steps maine yahan chala kar nahi dekhe (yahan GPU nahi hai). Dataset banana, masking logic aur export command tested hain. Baaki scripts standard tareeke se likhe hain, par pehli baar chalane par chhoti-moti dikkat aa sakti hai. Error aaye to mujhe paste kar dena.

## 1. Fine-tuning kya sikhata hai, kya nahi

**Sikhata hai (behavior):**
- Customer ki bhasha me jawab (Hinglish / English / Hindi)
- Sirf BUSINESS INFO se jawab dena
- Jawab na pata ho to `[[UNKNOWN]]`, insaan chahiye to `[[HANDOVER]]`
- Chhota, plain text jawab
- "Pichle instructions bhool jao" jaise injection se na behakna

**Nahi sikhata (facts):** kisi business ka timing, price, address. Yeh hamesha prompt ke BUSINESS INFO se aata hai (week 3 me knowledge base/RAG se). Isliye model ko apne business ke facts yaad karane ki koshish mat karo.

**Limit:** chhota model phir bhi kabhi-kabhi galat bol sakta hai. Isliye eval zaroor chalao aur pehle sirf apne test numbers par use karo.

## 2. Model chunne se pehle LICENSE dekho (zaroori)

Qwen ke blog ke hisaab se (Alibaba Cloud ka post):

| Model | License |
|---|---|
| Qwen2.5-0.5B, 1.5B, 7B, 14B, 32B | Apache 2.0 (commercial use ok) |
| **Qwen2.5-3B** | **Qwen Research License** (commercial use ke liye nahi) |
| Qwen2.5-72B | Qwen License (alag shartein) |

- Scripts ka default `Qwen/Qwen2.5-3B-Instruct` hai kyunki Colab T4 par chalna aasan hai. **Isse sirf seekhne/test ke liye use karo.**
- Agar yeh bot kisi business ko paid service ke roop me dena hai, to `Qwen/Qwen2.5-7B-Instruct` (Apache 2.0) ya koi aur commercial-friendly model lo. 7B ko `--base Qwen/Qwen2.5-7B-Instruct` se chalao; training dheemi hogi aur T4 par `--batch 1 --grad-accum 16` rakho.
- Maine license model card se khud nahi padha (site mere liye blocked thi). **Training se pehle us model ki Hugging Face page par license khud confirm karo.** Main legal advice nahi de sakta.

## 3. Hardware

| Kaam | Kya chahiye |
|---|---|
| Training (3B, 4-bit) | NVIDIA GPU, lagbhag 12-16 GB VRAM. Colab/Kaggle ka free T4 chalna chahiye |
| Training (7B, 4-bit) | T4 par tight aur bahut dheemi; 24 GB GPU behtar |
| Merge | CPU chalega, 3B ke liye ~8 GB RAM |
| Chalana (Ollama, Q4) | 3B ke liye ~4 GB RAM; GPU ho to tez |

Time aur kharcha maine naapa nahi hai. Free T4 par session limit aur disconnect ho sakta hai.

## 4. Step by step

### Step 1: Dataset banao
```bash
python finetune/make_dataset.py --repeat 3
```
Isse `finetune/data/train.jsonl` (~1265 examples) aur `val.jsonl` (~306) banti hain. Yeh 5 **kaalpanik** businesses par hai (Sai Clinic, Glow Salon, Bright Minds, Spice Route). Val me alag business FitZone Gym hai, taki pata chale model naye business par bhi chalta hai ya nahi.

### Step 2: Train karo (Colab ya Kaggle)
1. Project folder ya zip Colab me upload karo, GPU runtime chuno (T4).
2. ```bash
   pip install -r finetune/requirements-finetune.txt
   python finetune/train_lora.py --base Qwen/Qwen2.5-3B-Instruct
   ```
3. Ant me adapter `finetune/out/lora` me save hoga aur val ke 4 sawalon ke jawab dikhenge. Dekho: expected aur model ka jawab kitna milta hai.

Out of memory aaye to: `--batch 1 --grad-accum 16` ya `--max-len 1024`.

### Step 3: Merge karo
```bash
python finetune/merge_lora.py --base Qwen/Qwen2.5-3B-Instruct
```
Poora model `finetune/out/merged` me banega.

### Step 4: GGUF me badlo (llama.cpp)
```bash
git clone https://github.com/ggml-org/llama.cpp
pip install -r llama.cpp/requirements.txt
python llama.cpp/convert_hf_to_gguf.py finetune/out/merged --outfile wabot-f16.gguf --outtype f16
# quantize: llama.cpp ko build karna padta hai (cmake), phir:
./llama.cpp/build/bin/llama-quantize wabot-f16.gguf wabot-q4_k_m.gguf Q4_K_M
```
Script ke naam/jagah llama.cpp ke naye versions me badal sakte hain; unki README dekh lena.

### Step 5: Ollama me daalo
`finetune/Modelfile.example` ko `Modelfile` naam se copy karo (`.gguf` ke saath same folder me):
```bash
ollama create wabot-v1 -f Modelfile
ollama run wabot-v1
```
Agar Ollama docker compose me chal raha hai (`--profile llm`), to GGUF aur Modelfile ko container me copy karke wahi `ollama create` chalao.

### Step 6: Eval (base vs tuned)
```bash
python finetune/eval_val.py --model qwen2.5:3b --base-url http://localhost:11434/v1
python finetune/eval_val.py --model wabot-v1   --base-url http://localhost:11434/v1
```
Dono ke numbers compare karo: sahi marker, faltu marker nahi, sahi bhasha, numbers sahi, chhota jawab. Agar tuned model base se behtar nahi hai, to use mat apnao.

### Step 7: wabot me lagao
`.env` me:
```
LLM_PROVIDER=ollama
LLM_MODEL=wabot-v1
```
Phir `docker compose up -d` aur:
```bash
docker compose exec web python manage.py check_llm
docker compose exec web python manage.py ai_eval
```

## 5. Asli chats se data (baad me, sochkar)

Jab bot chal raha ho aur owner ne jawab sudhare hon (flag se mark karke), tab:
```bash
docker compose exec web python manage.py export_training_data --tenant <id> --i-have-consent --out finetune/data/real.jsonl
```
- Sirf tab jab business owner aur customers ne is use ki **sahmati** di ho (India me DPDP Act lagu hota hai; yeh legal advice nahi hai, zarurat ho to vakil se poochho).
- Phone number jaise numbers `[NUMBER]` ban jaate hain, par naam/address jaisi cheezein nahi hatti. **Output ko khud padh kar saaf karo.**
- Isse `train.jsonl` me jodkar dobara train karo.

## 6. Aam dikkatein

- **`bitsandbytes` error:** GPU/CUDA version mismatch. Colab par naya runtime lo.
- **Jawab me ajeeb tokens:** Modelfile ka TEMPLATE base model se match hona chahiye (`ollama show qwen2.5:3b --modelfile`).
- **Model facts bana raha hai:** BUSINESS INFO prompt me hai ya nahi dekho; zarurat ho to bada model ya zyada epochs/data.

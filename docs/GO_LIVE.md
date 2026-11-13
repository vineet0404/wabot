# Go-live guide: dev se asli customers tak

Is guide ko upar se neeche line se follow karo. Har step ke baad "Check" wali line se confirm karo ki aage badh sakte ho.

> **Honest baat:** Is guide ka code (knowledge base, inbox, production compose, backup scripts) yahan tests se verify hua hai, par **kisi asli server, asli Meta account ya asli LLM par maine chalaya nahi hai**. Meta, VPS aur LLM providers ke menu/rules badalte rehte hain; jahan "confirm karo" likha hai wahan unke current docs dekho. Pehle 1-2 jaan-pehchaan wale business ke saath pilot karo, seedha bade customer par nahi.

## Poora raasta ek nazar me

| # | Kaam | Kahan | Lagbhag kitna |
|---|---|---|---|
| 1 | LLM chuno aur laptop par asli test karo | laptop | 1-2 ghante |
| 2 | Knowledge base bharo, search check karo | laptop | 1 ghanta |
| 3 | Inbox aur members set karo | laptop | 15 min |
| 4 | Server (VPS) + domain + HTTPS | server | 1-2 ghante |
| 5 | Meta WhatsApp setup + business verification | Meta | kuch din (verification Meta par depend) |
| 6 | Pehle business ko onboard karo | admin | 1 ghanta |
| 7 | Backup, monitoring | server | 1 ghanta |
| 8 | Pilot (2 hafte) | asli customers | 2 hafte |

Time ke andaze mere hain, naape hue nahi.

---

## 1. LLM chuno aur asli test karo

Abhi `LLM_PROVIDER=fake` hai, jo sirf "Aapne likha: ..." echo karta hai. **Live par fake mat rakhna**, customers ko echo jayega.

Teen raaste (kisi ek se shuru karo, baad me badal sakte ho, sirf `.env` badalna hai):

| Raasta | Kab theek hai | Dhyan rakho |
|---|---|---|
| **A. API provider** (Claude, OpenAI, Groq, Gemini...) | Sabse aasan, achhi quality, apna GPU nahi chahiye | Paid hai; free tiers ki limits aur data-use rules confirm karo. **Asli customer ka data free tier par mat bhejo** |
| **B. Ollama apne server par, bina fine-tune** | Data bahar nahi jata | Server me RAM/GPU chahiye; chhota model Hinglish me kamzor ho sakta hai |
| **C. Fine-tuned model** (docs/FINETUNE.md) | Behavior behtar karne ke liye | Pehle B ya A se compare karo; 3B ka license commercial nahi hai, docs/FINETUNE.md dekho |

### Test (laptop par)

`.env` me provider daalo (details: docs/AI_PROVIDERS.md, docs/SELF_HOSTED_LLM.md), phir:

```bash
docker compose up -d --build
docker compose exec web python manage.py migrate
docker compose exec web python manage.py bootstrap_dev
docker compose exec web python manage.py check_llm
docker compose exec web python manage.py ai_eval
```

**Check:**
- `check_llm` me `[OK]` aaye aur jawab 10-15 second se kam me.
- `ai_eval` me 9 me se kam se kam 8 sahi. Jahan galat ho, `--question "..."` se akele dekho.
- Apne haath se 15-20 asli jaise sawal `simulate_message` se bhejo (Hinglish, English, galat spelling, gussa, emergency, "bhool jao pichle instructions").

Agar quality kam hai: bada/behtar model lo, ya business info saaf aur chhoti likho. Jab tak yeh step pass na ho, aage mat badho.

---

## 2. Knowledge base (RAG)

Chhoti si info (timing, address) `business_info` box me rakho, wo har jawab me jati hai. Lambi cheezein (menu, rate list, FAQ, policies) knowledge base me daalo: bot har sawal par sirf kaam ke tukde dhoondh kar prompt me jodta hai.

### Kaise daalein

**Admin se:** Admin me *Knowledge docs* -> Add. Tenant chuno, title (jaise "Rate list"), content likho. Paragraphs ke beech khali line rakho. Save par apne aap tukde (chunks) ban jaate hain.

**File se:**
```bash
docker compose cp menu.txt web:/tmp/menu.txt
docker compose exec web python manage.py kb_import /tmp/menu.txt --tenant 1 --title "Menu"
```
Same title dobara daaloge to purana badal jayega.

### Likhne ke achhe tareeke
- Ek paragraph = ek baat. Jaise: `Bridal makeup: Rs 8000. Advance booking zaroori, 2 hafte pehle.`
- Naam, price, timing saaf likho; "baad me batayenge" jaisa mat likho.
- Jo cheez badalti hai (offer, chhutti) use alag doc me rakho taaki aasani se update ho.
- Koi password, customer ka data ya medical records yahan mat daalo.

### Search check karo
```bash
docker compose exec web python manage.py kb_search "bridal makeup ka rate" --tenant 1
```
Sahi tukde upar aane chahiye. Nahi aaye to: title/paragraph me wahi shabd daalo jo customer bolte hain.

### Keyword vs embedding search
- Default `EMBED_PROVIDER=none`: keyword search. Bina kisi API ke chalta hai, spelling milne par achha, par "sasta" jaisi alag shabdon wali baat nahi samajhta.
- Behtar: embedding model. Ollama par: `ollama pull nomic-embed-text`, phir `.env` me
  ```
  EMBED_PROVIDER=ollama
  EMBED_MODEL=nomic-embed-text
  ```
  Provider/model badalo to har doc ek baar dobara save karo (ya `kb_import` dobara chalao), warna purane vectors ignore hote hain aur keyword search chalta hai. Hinglish par kaunsa embedding model achha hai, ye maine test nahi kiya; `kb_search` se khud parakh lo.
- Embedding fail ho jaye to bot keyword search par aa jata hai, jawab band nahi hota.

**Seema:** knowledge base facts ke liye hai. Bot ko ab bhi "sirf isi se jawab do" bola gaya hai, par chhota model kabhi-kabhi galat bol sakta hai. Isliye pilot me `flag` wali chats rozana dekho.

---

## 3. Owner inbox

Jab bot `[[HANDOVER]]` bolta hai, chat "owner sambhal raha hai" me chali jati hai aur bot chup ho jata hai. Owner ko jawab dene ke liye inbox hai: `https://<domain>/inbox/`

Setup:
1. Admin me owner ke liye user banao, **Staff status** tick karo (superuser nahi).
2. *Tenants* -> uska business -> **Members** me us user ko daalo.
3. Owner `/inbox/` par usi user se login kare (login page admin wala hi hai).

Kya hota hai:
- Owner sirf **apne business** ki chats dekh sakta hai. Membership ke bina kuch nahi dikhta.
- "Aapke jawab ka intezaar" me handover wali chats; "Bot ko jawab nahi mila" me jahan bot ne `unknown` bola (yahan se pata chalta hai knowledge base me kya jodna hai).
- Reply bhejne par chat `human` rehti hai. "Bot ko wapas do" dabane par bot dobara jawab dega.
- **24 ghante ka niyam:** customer ke aakhri message ke 24 ghante ke baad WhatsApp free-text reply allow nahi karta (approved template chahiye). Inbox tab reply band kar deta hai. Template messages ke liye docs/BOOKING_AND_REMINDERS.md dekho.
- Owner ko handover/booking par Telegram/email jata hai agar set ho (docs/BOOKING_AND_REMINDERS.md). Set na ho to use inbox khud kholna padega.

---

## 4. Server (VPS) + domain + HTTPS

### 4.1 Kya chahiye
- Ek Linux VPS (Ubuntu 22.04/24.04). Bina local LLM ke shuru me 2 vCPU / 4 GB RAM kaafi hone ki ummeed hai (maine napa nahi). Local LLM server par chalana ho to usse kaafi zyada RAM (aur behtar GPU) chahiye, ya LLM ke liye alag machine lo.
- Ek domain/subdomain, jaise `bot.aapkadomain.in`. Uska **A record** server ke IP par point karo (DNS badalne me thoda time lag sakta hai).
- Server ke firewall me sirf 22 (SSH), 80, 443 khule.

### 4.2 Server taiyaar karo
```bash
ssh root@SERVER_IP
adduser deploy && usermod -aG sudo deploy         # root se roz kaam mat karo
# SSH key se login chalu karo, phir password login band karo (sshd_config: PasswordAuthentication no)
ufw allow OpenSSH && ufw allow 80 && ufw allow 443 && ufw enable
apt update && apt -y upgrade
curl -fsSL https://get.docker.com | sh && usermod -aG docker deploy
```
Docker ke published ports ufw ko bypass kar sakte hain, isliye humne prod compose me db/redis ke ports khole hi nahi.

### 4.3 Code aur secrets
```bash
su - deploy
# apna zip ya git se code laao, jaise:
unzip wabot.zip && cd wabot
pip3 install cryptography --break-system-packages     # ya: docker run --rm -v $PWD:/w -w /w python:3.12-slim sh -c "pip install -q cryptography && python scripts/gen_secrets.py"
python3 scripts/gen_secrets.py                         # secrets chhapta hai
cp .env.production.example .env.production
nano .env.production                                   # secrets paste karo, DOMAIN, META_APP_SECRET, LLM_* bharo
chmod 600 .env.production
```
**FIELD_ENCRYPTION_KEY ko kisi aur safe jagah (password manager) bhi rakho.** Ye kho gayi to saved WhatsApp tokens padhe nahi jayenge. Badalna mat.

### 4.4 Chalao
```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
docker compose -f docker-compose.prod.yml --env-file .env.production ps
docker compose -f docker-compose.prod.yml --env-file .env.production exec web python manage.py createsuperuser
curl https://bot.aapkadomain.in/ready/          # {"status": "ok"}
```
Caddy pehli baar certificate leta hai; DNS sahi nahi hua to yahan fail hoga. `docker compose ... logs caddy` dekho.

Chhota alias: `alias dc='docker compose -f docker-compose.prod.yml --env-file .env.production'`

**Check:** `https://<domain>/ready/` ok deta hai; `https://<domain>/<ADMIN_URL>` se admin khulta hai (`/admin/` 404 dena chahiye).

### 4.5 Live check
```bash
dc exec web python manage.py check_setup       # sab [OK], go-live section me bhi
dc exec web python manage.py check_llm
```

---

## 5. Meta WhatsApp Cloud API

Meta ka dashboard badalta rehta hai. Yeh sirf dhaancha hai; har step Meta ke current docs se match karo (developers.facebook.com, WhatsApp Cloud API "Get started").

1. **Meta Business account** banao / use karo.
2. developers.facebook.com par **App** banao (Business type), usme **WhatsApp** product jodo.
3. **Test number** se shuru karo: Meta ek test number deta hai, jisme aap kuch chune hue number ko message bhej sakte ho. Isse pura flow dekho.
4. Asli business number ke liye: apna number WhatsApp Business API me register karna padta hai (wo number normal WhatsApp app me chal raha ho to alag process hai; Meta ke docs dekho). **Business verification** Meta ke taraf se hoti hai; kitna time lagega aur kya documents chahiye, Meta par depend karta hai.
5. **Permanent access token:** test ka temporary token ~24 ghante me expire hota hai. Live ke liye Business Settings me **System User** banao, usko app aur WhatsApp account ka access do, aur uska token generate karo (permissions Meta ke docs me likhe hain). Isse admin ke Tenant me *WA access token* me daalo.
6. **Webhook:** App -> WhatsApp -> Configuration:
   - Callback URL: `https://<domain>/webhooks/whatsapp/`
   - Verify token: `.env.production` ka `META_VERIFY_TOKEN`
   - Fields me **messages** subscribe karo.
7. App Settings -> Basic se **App secret** copy karke `.env.production` me `META_APP_SECRET` daalo, phir `dc up -d` se web/worker dobara chalao.
8. Admin me Tenant ka **Phone number ID** wahi daalo jo Meta ke API Setup me dikhta hai.
9. **Message templates:** 24 ghante ke baad pehla message sirf approved template se ja sakta hai. Reminders ke liye zaroori hoga (week 4). Meta ki **pricing** (conversation/message charges) apni current pricing page se dekho; yeh kharcha customer ko kaise bill karna hai pehle tay karo.
10. Display name, profile photo, aur privacy policy URL Meta maangta hai; ek simple privacy page bana lo.

**Check:** apne phone se test number par "Timing kya hai?" bhejo. Jawab aaye. `dc logs worker` me dikhe. Galat signature ke saath POST karne par 403 aana chahiye (tests me verified).

---

## 6. Naye business ko onboard karna (har client ke liye)

1. Client se likhit sahmati lo ki wo apne customers ke WhatsApp messages is bot se handle karwana chahta hai. Wo bhi customers ko batayega (neeche Privacy dekho).
2. Admin -> Tenants -> Add: naam, type, Phone number ID, access token, `business_info` (timing, address, services, main FAQs).
3. Knowledge base docs bharo (menu/rates/policies).
4. Owner ka staff user banao aur Members me daalo.
5. 15-20 test sawal apne number se bhejo (Hinglish/English/emergency/gussa/off-topic).
6. `LLM_DAILY_TOKEN_BUDGET` dekh lo (har business ka roz ka limit; 0 = koi limit nahi).
7. Owner ko samjhao: inbox kaise dekhna hai; bot kya nahi kar sakta (booking confirm nahi karta, medical salah nahi deta).

**Rok lagana (kill switch):** bot band karna ho to Tenant me *Is active* hatao. Naya message tab store hi nahi hota. Poora system rokna ho to `dc stop worker`.

---

## 7. Backup aur monitoring

### Backup
```bash
./scripts/backup.sh                          # ek baar haath se chalake dekho
ls -lh backups/
crontab -e
# roz raat 3:15 baje:
15 3 * * * cd /home/deploy/wabot && ./scripts/backup.sh >> backups/backup.log 2>&1
```
- 14 din ke purane backup apne aap hat jaate hain (`KEEP_DAYS=30 ./scripts/backup.sh` se badal sakte ho).
- **Backup usi server par rakhna kaafi nahi hai.** Server udd gaya to backup bhi gaya. Roz kisi doosri jagah copy karo (doosra server `rsync`, ya koi object storage). Backup me customer chats hain, to us jagah ko bhi protect rakho (encrypted).
- **Restore ek baar test karo**, kisi test server par: `./scripts/restore.sh backups/<file>`. Jis backup ko kabhi restore nahi kiya, wo backup maan kar mat chalo.
- `.env.production` (khaaskar FIELD_ENCRYPTION_KEY) ka alag, safe backup rakho.

### Monitoring
- **Uptime:** koi bhi uptime checker (UptimeRobot jaise, ya khud ka cron) `https://<domain>/ready/` ko har 5 min dekhe; 503 ya timeout par alert (SMS/email). Yeh DB aur Redis dono check karta hai. (Third-party service hai; chaho to apna cron `curl -fsS` + mail bhi chalega.)
- **Logs:** `dc logs -f --tail 100 worker` aur `web`. Docker logs 10 MB x 5 files par ghoomte hain.
- **Disk:** `df -h` mahine me ek baar; backups aur Docker images bharte hain.
- **AI kharch:** Admin -> LLM usage me roz ke tokens. Budget poora hone par customer ko "team jaldi reply karegi" jata hai.
- **Speed:** `dc exec web python manage.py latency_report` (p50/p95), tarike: docs/LATENCY.md
- **Quality:** Admin -> Messages me `flag` filter: `unknown`, `error`, `budget` roz dekho.

---

## 8. Update kaise karein

```bash
# naya code laao (git pull ya naya zip)
dc up -d --build        # web start par migrations khud chalte hain
dc exec web python manage.py check_setup
```
Update se pehle `./scripts/backup.sh`. Kuch bigde to purana code wapas laao aur dobara `up -d --build`; agar naye code ne database badla ho to restore chahiye ho sakta hai, isliye backup zaroori hai.

---

## 9. Security checklist (live se pehle)

- [ ] `DJANGO_DEBUG=0`, `DJANGO_SECRET_KEY` aur `FIELD_ENCRYPTION_KEY` asli aur lambe
- [ ] `ADMIN_URL` random; superuser ka password lamba (kam se kam 10 akshar zabardasti, 14+ rakho)
- [ ] `.env.production` permission 600, git me nahi
- [ ] db/redis ke ports bahar nahi khule (`ss -tlnp` se dekho: sirf 22, 80, 443)
- [ ] SSH password login band, key se hi
- [ ] `META_APP_SECRET` set (warna webhook signature check kaam nahi karta)
- [ ] LLM API key sirf `.env.production` me, chat/screenshot/git me kabhi nahi
- [ ] Meta token System User wala (temporary nahi)
- [ ] Backup kisi doosri jagah copy ho rahe hain aur restore test hua
- [ ] Server ke OS updates (`unattended-upgrades` lagana soch sakte ho)

## 10. Privacy aur kanooni baatein

Main vakil nahi hoon; yeh sirf yaad dilane ke liye hai. Live karne se pehle kisi jaankar se poochho.

- India ka **DPDP Act** personal data par lagu hota hai. Customers ko batao ki chat me AI use hota hai, kaun sa data rakha jata hai (phone number, naam, messages), aur kitne din. Privacy policy page banao aur Meta ko URL do.
- Bot pehle se bolta hai ki wo AI assistant hai (agar customer puchhe). Pehle message me bhi batana behtar ho sakta hai.
- Health se jude sawal: bot medical salah nahi deta aur emergency par handover karta hai, par ye guaranty nahi. Clinic jaise businesses me owner ko saaf bata do ki bot sirf receptionist jaisa kaam karta hai, doctor nahi. Patient ki health details bot se mat mangwao.
- Data delete/export ki maang aaye to admin se customer aur uske messages delete kiye ja sakte hain (Customer delete karne par uski chats bhi hat jaati hain).
- Training ke liye asli chats tabhi export karo jab sahmati ho (`export_training_data --i-have-consent`).
- LLM provider ko jo bhi chat jati hai wo unke servers par jati hai; unki data-retention/training policy padh kar hi asli customer data bhejo. Apne server ka Ollama is risk ko kam karta hai.

## 11. Pilot plan (2 hafte)

1. 1-2 jaan-pehchaan wale businesses, chhote volume (roz kuch dozen chats).
2. Pehle 3 din: bot jawab de, par aap roz **sab chats padho**. Galat jawab ko note karo.
3. Har galti ka ilaaj: info/knowledge base me jodo ya prompt rule badlo. Model fine-tune sabse aakhir me.
4. Dekhne wali cheezein: kitne % sawal `unknown`/`handover` gaye; kitne galat facts; owner kitni jaldi jawab deta hai; customers ne bot ke baare me shikayat ki?
5. Do hafte baad faisla: aage badhao, theek karo, ya rok do.

## 12. Abhi jo nahi hai (honest list)

Ab bante hain (docs/BOOKING_AND_REMINDERS.md): handover/booking par owner ko Telegram/email, booking request aur owner ka confirm, reminders. Ye sab fake LLM/Meta ke saath tested hain, asli par nahi.

Abhi bhi nahi:
- Working hours / chhutti / alag staff ka calendar (sirf clash warning)
- Customer ka khud cancel/reschedule
- Image/voice/document messages samajhna (sirf text)
- Instagram DMs (design me hai, code me nahi)
- Billing/subscription, per-client analytics
- Load testing: maine bahut zyada traffic par test nahi kiya

Pilot ke feedback se tay karo kaun sa pehle.

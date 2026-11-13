# Owner notification, booking aur reminders

Teen cheezein, ek ke upar ek:

```
Customer: "kal shaam 5 baje appointment chahiye"
   |
   v  bot turant jawab deta hai ("team confirm karegi")
   |
   v  (background me) LLM chat padhkar din+samay nikalta hai  -> Booking "requested"
   |
   v  owner ko Telegram/email: "Ravi ne appointment maangi ... Confirm karo: <link>"
   |
Owner /inbox/bookings/ par Confirm dabata hai  -> customer ko confirm message jata hai
   |
   v  appointment se N ghante pehle (beat timer) -> customer ko reminder
```

> **Honest baat:** yeh sab yahan tests se verify hua hai (142 tests, fake LLM aur fake Meta ke saath). **Asli LLM, asli Telegram/email aur asli WhatsApp templates par maine chalaya nahi hai.** Booking nikalne wala hissa LLM par tika hai, isliye kabhi galat ho sakta hai. Isiliye bot khud kabhi confirm nahi karta, sirf owner karta hai.

---

## 1. Owner notification

Jab bot `handover` kare ya naya appointment maange, owner ko sandesh jata hai. **Sandesh me customer ka message nahi hota**, sirf naam (ya number ke aakhri 4 digit) aur inbox ka link. Naam/number third-party (Telegram/email) se guzarte hain, isliye itna hi.

### Telegram (free, sabse aasan)
1. Telegram me **@BotFather** ko `/newbot` bhejo, bot ka naam do. Wo ek **token** dega.
2. `.env` me `TELEGRAM_BOT_TOKEN=<token>` aur `PUBLIC_BASE_URL=...` daalo. `docker compose up -d`.
3. **Owner apne Telegram se apne naye bot ko ek baar `/start` bheje.** (Bot tab tak owner ko message nahi bhej sakta.)
4. Owner ka **chat id** nikalo: owner Telegram me **@userinfobot** ko message kare, wo apna `Id` batata hai (ek number).
5. Admin -> Tenant -> **Notify telegram chat id** me wo number daalo.

### Email
`.env` me `EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` (aur `DEFAULT_FROM_EMAIL`) bharo. Gmail ho to normal password nahi chalega, "App password" banana padta hai (Google ke docs dekho). Phir Admin -> Tenant -> **Notify email**.

### Test
```powershell
docker compose exec web python manage.py notify_test
```
**Sahi result:** `[OK] Bheja gaya: telegram` (ya email), aur sandesh phone/inbox me aaya. Dono set ho to dono par jata hai; ek fail ho to doosra chalta rehta hai. Koi channel set na ho to `[FIX]` batata hai. Dev me email ka backend "console" hai, to email sirf `docker compose logs web worker` me dikhegi.

---

## 2. Booking

### Bot kya karta hai
Customer ka booking jaisa sawal aaye to bot pehle jaisa hi jawab deta hai (din aur samay puchta hai, "team confirm karegi" kehta hai). Uske **baad background me** ek aur AI call chat padhti hai aur dekhti hai ki customer ne **pakka din aur samay** bataya ya nahi. Ho gaya to ek **request** banti hai.

- Yeh extra call sirf tab hoti hai jab chat me "book/appointment/slot" jaisa shabd ho, taaki har message par kharcha na ho. (Booking wali baatcheet me har message par ek extra call lagegi, tokens ka dhyan rakho.)
- Customer ke baar-baar samay badalne par wahi request update hoti hai, nayi nahi banti.
- Owner ke confirm karne ke baad customer "thanks" bole to duplicate request nahi banti.
- Beeta hua ya 90 din se door samay, aur AM/PM saaf na ho to request nahi banti.

### Owner ka kaam
`https://<domain>/inbox/bookings/` (dev: `http://localhost:8000/inbox/bookings/`)
- **Confirm** -> customer ko "appointment ... confirm hai" jata hai.
- **Mana karo** -> customer ko "slot available nahi, doosra samay batayein" jata hai.
- Confirm hone ke baad **Cancel** (customer ko owner khud batata hai).
- Agar usi samay (slot ke andar) pehle se koi confirm hai to line me **Dhyan** warning dikhti hai. Confirm phir bhi kar sakte ho.

### 24 ghante ka niyam
Confirm tabhi seedha ja sakta hai jab customer ne pichle 24 ghante me likha ho. Nahi to:
- Tenant me **confirm template** (neeche dekho) set ho to wo bhejta hai.
- Warna booking confirm ho jati hai par customer ko message **nahi** jata. Screen par peela warning aata hai, customer ko khud batana padega.

### Jo ABHI nahi hai
- Owner ke working hours / chhutti / ek samay par kitne log, is sab ka hisaab (sirf "clash" warning hai).
- Customer ka khud cancel/reschedule karna (wo likhega to bot `handover`/nayi request ki tarah le sakta hai, par seedha cancel nahi hota).
- Alag doctors/staff ka alag calendar.

---

## 3. Reminders

- Har tenant ke liye **Reminder hours before** (default 3). `0` = reminder band.
- Har **10 minute** me `beat` timer dekhta hai ki kiska samay aa gaya. Sirf **confirm** appointments ko, **ek hi baar**.
- Raat me nahi: default **subah 8 se raat 9** (business ke local time me) hi jata hai. Raat ka reminder subah 8 baje ke baad chala jata hai, agar appointment tab tak baaki ho. `.env` me `REMINDER_QUIET_BEFORE_HOUR` / `REMINDER_QUIET_AFTER_HOUR` se badlo.
- Customer ne pichle 24 ghante me likha ho to normal text jata hai. Nahi to **reminder template** jata hai. Template bhi nahi to reminder **nahi** jata aur owner ko sandesh milta hai ki khud bata de.
- Bheje gaye reminder chat me `flag=reminder` ke saath dikhte hain.

### `beat` service
Docker compose me `beat` naam ki service hai (dev aur prod dono me). **Sirf ek beat chalna chahiye**, warna reminders double jayenge. `docker compose ps` me `beat` Up dikhna chahiye.

### Meta me template banana (24 ghante ke baad ke liye)
Meta Business Manager -> WhatsApp Manager -> Message templates. Neeche ka dhaancha hai; Meta ka menu aur rules badalte rehte hain, unke docs dekho. **Approval kitna time leta hai aur kya category/kharcha lagega, mujhe pata nahi, Meta ki current pricing page dekho.**

| | Reminder template | Confirm template |
|---|---|---|
| Naam | `appointment_reminder` | `appointment_confirmed` |
| Category | Utility (Meta tay karta hai) | Utility |
| Language | English (`en`) | English (`en`) |
| Body | `Hello {{1}}, this is a reminder for your appointment on {{2}} at {{3}}. Reply here if you need to change it.` | `Hello {{1}}, your appointment on {{2}} at {{3}} is confirmed. Reply here if you need to change it.` |

`{{1}}` customer ka naam, `{{2}}` samay (jaise "Sunday, 8 Nov, 5:00 PM"), `{{3}}` business ka naam. **Yahi order hona chahiye**, code isi order me bhejta hai.

Approval ke baad Admin -> Tenant me bharo: **Reminder template** (`appointment_reminder`), **Confirm template** (`appointment_confirmed`), aur **Template lang** (`en`, wahi jo Meta me chuni). Naam ya language zara bhi alag hui to Meta 4xx deta hai aur log me `reminder fail` dikhta hai.

---

## 4. Testing (Meta ke bina, laptop par)

Naya code lene ke baad:
```powershell
docker compose up -d --build
docker compose exec web python manage.py migrate
docker compose ps
```
`beat` bhi Up dikhna chahiye.

### 4.1 Booking
Chat ko bot par reset karke do message bhejo (booking ke liye asli LLM chahiye, `fake` provider me nahi banegi):
```powershell
docker compose exec web python manage.py shell -c "from apps.core.models import Conversation; Conversation.objects.update(state='bot')"
docker compose exec web python manage.py simulate_message "mujhe appointment book karna hai"
docker compose exec web python manage.py simulate_message "kal shaam 5 baje, naam Ravi"
```
Phir browser me `http://localhost:8000/inbox/bookings/` (staff user se login, tenant ka member). **Sahi result:** "Aapke confirm ka intezaar" me Ravi, kal ka din, 5:00 PM. `docker compose logs worker --tail 30` me `booking N requested`.

Na bane to: `docker compose logs worker --tail 50` dekho. Aam wajah: LLM ne `complete:false` diya (AM/PM ya din saaf nahi), ya jawab kata (tokens kam).

**Confirm dabao.** Dev me WhatsApp token nahi hai, to message "dry-run" hota hai (log me dikhta hai, bheja nahi jata), booking confirm ho jati hai.

### 4.2 Reminder
Admin -> Bookings me wo booking kholo, `Starts at` ko **abhi se 1 ghanta baad** karo (aur subah 8 se raat 9 ke beech ka samay ho, nahi to "quiet" aayega), status Confirmed rakho. Phir:
```powershell
docker compose exec web python manage.py send_reminders --dry-run
docker compose exec web python manage.py send_reminders
```
**Sahi result:** dry-run me `1 reminder due`; asli run me `{'sent': 1, ...}`. Dobara chalane par `sent: 0`. Chat me `flag=reminder` wala message dikhega (dev me dry-run).

### 4.3 Owner notification
Section 1 ka `notify_test`. Phir handover karwao ("mujhe owner se baat karni hai") aur dekho ki sandesh aaya.

---

## 5. Production me
- `.env.production` me `PUBLIC_BASE_URL`, `TELEGRAM_BOT_TOKEN` / `EMAIL_*` bharo.
- `docker-compose.prod.yml` me `beat` service pehle se hai. Naya code ke baad `dc up -d --build`.
- Bookings aur reminders ka data database me hai, to `scripts/backup.sh` wale backup me ata hai.
- Reminder bhejne ka kharcha Meta ke template pricing ke hisaab se lagega. Customer ko bill kaise karna hai pehle tay karo.

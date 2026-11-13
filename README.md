# wabot: WhatsApp AI chatbot (development setup)

Ye Phase 1, hafta 1 ka starter hai. Isme abhi ye chalta hai:

- Meta ka webhook (verify + signature check)
- Message database me save hona, duplicate message na dobara chalna
- Celery worker jo echo reply deta hai ("Aapne likha: ...")
- Multi-tenant models: Tenant, Customer, Conversation, Message
- Django admin panel (yahin se tenant banate hain)
- Tests aur GitHub CI

LLM, RAG aur booking hafta 2 se aayenge.

## Zarurat

- Docker Desktop (Compose ke saath)
- Git
- ngrok ya Cloudflare Tunnel (Meta ko tumhare laptop tak pahunchane ke liye)
- Meta for Developers account (WhatsApp test number free milta hai)

## Pehli baar chalana

```bash
cp .env.example .env          # phir .env me META_VERIFY_TOKEN aur FIELD_ENCRYPTION_KEY bharo (docs/SECURITY.md)
docker compose up --build -d
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py bootstrap_dev      # Demo Clinic tenant
docker compose exec web python manage.py simulate_message "Hi"
```

Check: http://localhost:8000/health/ par `{"status": "ok"}` aana chahiye.
Admin: http://localhost:8000/admin/

Roz ka kaam: `docker compose up -d` aur logs ke liye `docker compose logs -f web worker`.

## Tests (bina Docker ke)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
ruff check .
```

Tests SQLite aur eager Celery par chalte hain, to Postgres ya Redis nahi chahiye.

## Bina Meta ke local testing (abhi yahi use karo)

Pehle admin me ek Tenant banao (`wa_phone_number_id` me kuch bhi, jaise `123`; token khali chhodo). Phir:

```bash
docker compose exec web python manage.py simulate_message "Kal subah 10 baje slot milega?"
docker compose logs worker --tail 20
```

Ye asli webhook jaisa hi code chalata hai (save, duplicate check, worker, reply). Reply Message table me dikhega (admin me dekho). Naye features isi tarah test karo; Meta ki zarurat tab padegi jab launch ke kareeb asli number par try karna ho.

## AI provider

Claude, OpenAI, Groq, Gemini, Ollama ya apna: [docs/AI_PROVIDERS.md](docs/AI_PROVIDERS.md)
Apna khud ka model: [docs/SELF_HOSTED_LLM.md](docs/SELF_HOSTED_LLM.md)
Apne data par fine-tune (license caveat ke saath): [docs/FINETUNE.md](docs/FINETUNE.md)

## Live jaana hai?

Knowledge base, inbox, server, Meta, backup, pilot: [docs/GO_LIVE.md](docs/GO_LIVE.md)
Jawab tez karna aur naapna: [docs/LATENCY.md](docs/LATENCY.md)
Owner notification, booking, reminders: [docs/BOOKING_AND_REMINDERS.md](docs/BOOKING_AND_REMINDERS.md)
Default `fake` hai (echo), to bina key ke bhi sab chalta hai.

## Security

Kya-kya protection hai aur launch se pehle kya karna hai: [docs/SECURITY.md](docs/SECURITY.md)

## Real WhatsApp par testing

Poora step-by-step guide: [docs/REAL_TIME_TESTING.md](docs/REAL_TIME_TESTING.md)

## Database badalna

Postgres, MySQL ya SQLite: [docs/DATABASE.md](docs/DATABASE.md)

## Short version (purana note)

1. Meta for Developers me app banao, WhatsApp product add karo. API Setup page par test number aur temporary token milega.
2. `.env` me `META_APP_SECRET` daalo (App settings, Basic) aur `docker compose restart web worker` karo.
3. Tunnel chalao: `ngrok http 8000`.
4. Meta, WhatsApp, Configuration me Callback URL: `https://<tunnel-host>/webhooks/whatsapp/`, Verify token: wahi jo `.env` me hai. Phir `messages` field subscribe karo.
5. Admin me Tenant banao: `wa_phone_number_id` (API Setup page se) aur `wa_access_token` bharo.
6. Test number ko apne phone se message bhejo. Echo wapas aana chahiye.

Token khali ho to bot sirf log karta hai, message bhejta nahi (dry-run).

## Folder

```
config/            settings, celery, urls
apps/core/         Tenant, Customer, Conversation, Message, admin
apps/whatsapp/     webhook view, signature, services, tasks, client
scripts/db-init.sql  pgvector extension
```

## Dhyan rakho

- `.env` aur tokens git me kabhi mat daalo.
- Temporary token 24 ghante me expire hota hai. Lambe samay ke liye System User token banao.
- Meta ki policy aur pricing badalti rehti hai, live jaane se pehle current terms check karo.

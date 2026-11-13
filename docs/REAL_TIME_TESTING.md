# Real WhatsApp par testing: poora guide

Meta ka free test number use hoga, to koi business verification ya paisa nahi lagta.
Cost: Rs 0. Limit: test number se sirf 5 pre-approved numbers ko message ja sakta hai.

## Step 1: Project chalu karo

```bash
cp .env.example .env
docker compose up --build -d
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
```

## Step 2: Meta app banao

1. https://developers.facebook.com par login karo, My Apps, Create App.
2. Use case me "Other", type "Business". App ka naam kuch bhi.
3. App dashboard me WhatsApp product add karo, "Set up" dabao. Meta ek test business account aur test number khud bana deta hai.
4. WhatsApp, API Setup page par ye cheezein dikhengi:
   - Temporary access token (24 ghante chalta hai)
   - Phone number ID (test number ki)
   - WhatsApp Business Account ID
5. "To" dropdown me Manage phone number list se apna personal number add karo. OTP aayega. Isi number se tum bot ko message bhejoge.
6. App settings, Basic me App secret (Show dabao). Isse `.env` me `META_APP_SECRET` me daalo.
7. `.env` me `META_VERIFY_TOKEN` ko koi bhi lamba random string se badlo.
8. `docker compose restart web worker`

## Step 3: Tunnel chalao (laptop ko internet par dikhane ke liye)

Free, bina account:

```bash
docker compose --profile tunnel up -d tunnel
docker compose logs tunnel | grep trycloudflare
```

Ek URL milega jaise `https://something-random.trycloudflare.com`. Ye har restart par badalta hai, to tunnel restart karne par Meta me URL dobara daalna padega.
Check: `<url>/health/` browser me kholo, `{"status": "ok"}` aana chahiye.

## Step 4: Webhook Meta se jodo

1. WhatsApp, Configuration, Webhook, Edit.
2. Callback URL: `<tunnel-url>/webhooks/whatsapp/`
3. Verify token: wahi jo `.env` me hai. "Verify and save" dabao. Fail ho to `docker compose logs web` dekho.
4. Webhook fields me `messages` ko Subscribe karo.

## Step 5: Tenant banao

http://localhost:8000/admin/ me Tenant add karo:
- Name: kuch bhi (jaise "Demo Clinic")
- wa_phone_number_id: API Setup wala Phone number ID
- wa_access_token: temporary token

Phir check chalao:

```bash
docker compose exec web python manage.py check_setup
```

Sab `[OK]` hona chahiye.

## Step 6: Test karo

1. Pehle apne phone se test number ko "Hi" bhejo. Echo "Aapne likha: Hi" wapas aana chahiye.
2. Agar test number se pehle message bhejna ho (tumne abhi tak likha nahi): `docker compose exec web python manage.py send_test 91XXXXXXXXXX`. Ye Meta ka hello_world template bhejta hai. Customer ke jawab dene ke baad 24 ghante tak normal text ja sakta hai.
3. Admin me Messages table me IN aur OUT dono dikhne chahiye.

## Roz ka chakkar

- Temporary token 24 ghante me expire hota hai. Naya token API Setup page se copy karke admin me Tenant me badlo.
- Tunnel restart hua to Meta me naya Callback URL daalo.
- `docker compose logs -f web worker` se live dekho kya ho raha hai.

## Agar kuch na chale

| Dikkat | Wajah |
|---|---|
| Verify and save fail | Verify token `.env` aur Meta me alag hai, ya `.env` badalne ke baad restart nahi kiya |
| Message aaya par jawab nahi | `check_setup` chalao. Token expire hona sabse common wajah hai |
| Logs me "Anjaan phone_number_id" | Tenant me Phone number ID galat hai |
| Logs me 401 signature galat | `META_APP_SECRET` galat ya khali hai |
| Meta 131030 / "recipient not in allowed list" | Us number ko API Setup me add aur verify nahi kiya |
| Message hi nahi aa raha | Webhook me `messages` field subscribe nahi hui |

## Launch ke liye baad me

- Apna asli number aur Meta business verification (kuch din se kuch hafte lag sakte hain).
- System User se permanent token, aur token ko encrypt karke store karna.
- WABA ko app se subscribe karna: `POST /{waba_id}/subscribed_apps`.
- Meta ki current policy aur per-message pricing dobara check karna.

# Security: kya laga hai aur kya karna baaki hai

## Jo is project me pehle se laga hai

| Khatra | Bachav |
|---|---|
| Koi nakli Meta ban ke webhook par message bheje | Har request par `X-Hub-Signature-256` check hota hai (HMAC, constant-time). Galat ho to 401. |
| Nakli requests ki bauchaar | Ek IP se 10 minute me 20 galat signature ke baad 429, baaki sab block |
| Admin password guess karna | 5 galat koshish par us username ko, ya 10 par us IP ko, 15 minute ke liye lock. Sahi login par counter reset |
| Kamzor admin password | Kam se kam 10 characters, common ya sirf numbers wala password reject |
| Database chori ya backup leak | WhatsApp access token DB me Fernet se encrypted (`enc::...`). Bina `FIELD_ENCRYPTION_KEY` ke bekaar |
| Admin screen se token dikhna | Token field password-type hai, saved token dobara page par aata hi nahi |
| Bots ka `/admin/` dhoondhna | `ADMIN_URL` se raasta badal sakte ho (jaise `panel-x7k2/`) |
| Bahut bada body bhej kar server girana | Request body 1 MB se bada reject |
| Clickjacking, MIME sniffing | `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy` |
| Session chori | Cookie HttpOnly, SameSite=Lax, 8 ghante me expire (live me Secure bhi) |
| Dusre ke tenant ka data | Har table par `tenant_id`, webhook `phone_number_id` se tenant dhoondhta hai |
| Dobara bheje message se double kaam | `wa_message_id` unique |
| Logs me private data | Phone number masked, message ka text log nahi hota |
| DB aur Redis ko wifi se access | Docker me teeno ports sirf `127.0.0.1` par khule hain |
| Container me root | App normal user se chalta hai |
| Galti se production me debug | `DJANGO_DEBUG=0` par secret key, encryption key aur HTTPS (cookies Secure, HSTS) zaroori ho jaate hain. CI me `check --deploy` chalta hai |

## Abhi ki setting (laptop par)

1. `.env` me `FIELD_ENCRYPTION_KEY` bharo:
   ```bash
   docker compose exec web python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```
   Output `.env` me daalo aur `docker compose restart web worker` karo. Key ko kisi safe jagah backup rakho.
   **Tokens daalne se pehle ye karo.** Baad me key badloge to saved tokens padhe nahi jayenge (tab admin me naya token daalna padega).
2. `ADMIN_URL` ko kuch random karo, aur admin ka password lamba rakho.
3. Tunnel use kar rahe ho to `TRUST_PROXY_HEADERS=1` rakho (wahi default hai).
4. `LLM_API_KEY` bhi sirf `.env` me rakho (git me nahi).
5. Meta ka temporary token aur app secret kabhi chat, screenshot ya git me mat daalo. Agar galti se share ho gaya to Meta dashboard se turant naya token banao.

## Launch se pehle (ye abhi nahi hai)

- HTTPS wala asli domain, `DJANGO_DEBUG=0`, `DJANGO_ALLOWED_HOSTS` me apna domain.
- `runserver` ki jagah `gunicorn`.
- Postgres aur Redis par strong password, aur inhe public internet par khula mat rakho.
- Meta ka permanent System User token.
- Roz DB backup (aur encrypted backup, key alag jagah).
- Sentry se error alerts, aur dependencies ko mahine me ek baar update karo (`pip list --outdated`).
- Customer data ka consent, deletion aur retention ka process (DPDP Act). Lawyer se confirm karo.
- Admin par 2-step login (2FA) baad me jodna accha rahega.

## Ye kya nahi rokta

Koi bhi software "hack-proof" nahi hota. Upar ka sab common hamlon se bachata hai. Sabse badi asli khatre aksar ye hote hain: leaked token, kamzor password, aur purani libraries. Isliye secrets ko safe rakho aur update karte raho.

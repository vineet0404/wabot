# Database badalna

App ab `DATABASE_URL` se chalti hai. `.env` me ek line badlo, baaki code wahi rehta hai.

```
DATABASE_URL=postgres://user:password@host:5432/dbname
DATABASE_URL=mysql://user:password@host:3306/dbname
DATABASE_URL=sqlite:///db.sqlite3
```

`DATABASE_URL` khali ho to purane `POSTGRES_*` settings chalti hain (docker ka apna Postgres).
Password me `@ : / #` jaise character ho to URL-encode karo (`@` ko `%40`).

## Kaunsa DB kaise

| DB | Status | Kya karna hai |
|---|---|---|
| PostgreSQL | Poora support, **recommended** | Kuch nahi, driver pehle se hai |
| SQLite | Sirf laptop par testing | Kuch nahi. Live ke liye mat lagao (ek saath kai logon ka kaam nahi sambhalta) |
| MySQL / MariaDB | Chalega, par maine ise test nahi kiya | `docker compose build --build-arg INSTALL_MYSQL=1`, phir `.env` me `mysql://...` |
| Cloud DB (Supabase, Neon, RDS, Railway) | Chalega, ye sab Postgres hain | Unka connection URL paste karo, aksar `?sslmode=require` ke saath |

## Docker ka apna Postgres band karna

Bahar ka DB use kar rahe ho to `.env` me `DATABASE_URL` daalo aur:

```bash
docker compose up -d --no-deps web worker redis
```

## Naya DB lagane ke baad

```bash
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
```

Purana data naye DB me apne aap nahi jata. Zarurat ho to `manage.py dumpdata` aur `loaddata` use karo.

## Dhyan rakho

- **Hafta 3 ka knowledge search (RAG) pgvector use karega, jo sirf PostgreSQL me hota hai.** MySQL ya SQLite par us feature ke liye alag tareeka (jaise bahar ka vector store) lagana padega. Isliye serious use ke liye Postgres hi rakho.
- Har table me `tenant_id` hai, to tenants ka data DB ke kisi bhi type me alag rehta hai. Row-level security (extra suraksha) sirf Postgres me milti hai.
- Tokens ki encryption DB se alag hai (app me hoti hai), to wo har DB par ek jaisi kaam karti hai.

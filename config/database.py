"""DATABASE_URL se Django ki database setting banata hai (koi extra library nahi chahiye).

Examples:
    postgres://user:pass@host:5432/dbname
    mysql://user:pass@host:3306/dbname
    mariadb://user:pass@host:3306/dbname
    sqlite:///db.sqlite3          (relative file)
    sqlite:////abs/path/db.sqlite3
    sqlite://:memory:
Password me @ : / jaise special character ho to use URL-encode karo (jaise @ ko %40).
Extra options URL ke end me: ?sslmode=require
"""

from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlsplit

from django.core.exceptions import ImproperlyConfigured

ENGINES = {
    "postgres": "django.db.backends.postgresql",
    "postgresql": "django.db.backends.postgresql",
    "pgsql": "django.db.backends.postgresql",
    "mysql": "django.db.backends.mysql",
    "mariadb": "django.db.backends.mysql",
    "sqlite": "django.db.backends.sqlite3",
    "sqlite3": "django.db.backends.sqlite3",
}


def parse_database_url(url: str, base_dir: Path) -> dict:
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    engine = ENGINES.get(scheme)
    if engine is None:
        supported = ", ".join(sorted({s for s in ENGINES}))
        raise ImproperlyConfigured(
            f"DATABASE_URL ka scheme '{scheme}' samajh nahi aaya. Ye chalte hain: {supported}"
        )

    if engine.endswith("sqlite3"):
        raw = unquote(parts.netloc + parts.path)
        if raw in ("", ":memory:", "/:memory:"):
            name = ":memory:"
        elif parts.netloc == "" and parts.path.startswith("//"):
            name = parts.path[1:]  # sqlite:////abs/path -> /abs/path
        else:
            name = str(base_dir / raw.lstrip("/"))
        return {"ENGINE": engine, "NAME": name}

    name = unquote(parts.path.lstrip("/"))
    if not name:
        raise ImproperlyConfigured("DATABASE_URL me database ka naam nahi hai (.../dbname).")

    config = {
        "ENGINE": engine,
        "NAME": name,
        "USER": unquote(parts.username or ""),
        "PASSWORD": unquote(parts.password or ""),
        "HOST": parts.hostname or "",
        "PORT": str(parts.port or ""),
    }
    options = dict(parse_qsl(parts.query))
    if options:
        config["OPTIONS"] = options
    if engine.endswith("mysql"):
        config.setdefault("OPTIONS", {}).setdefault("charset", "utf8mb4")
    return config

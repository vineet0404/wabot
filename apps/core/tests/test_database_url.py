from pathlib import Path

import pytest
from django.core.exceptions import ImproperlyConfigured

from config.database import parse_database_url

BASE = Path("/app")


def test_postgres_url():
    cfg = parse_database_url("postgres://u:p%40ss@db.example.com:6543/shop?sslmode=require", BASE)
    assert cfg["ENGINE"] == "django.db.backends.postgresql"
    assert (cfg["NAME"], cfg["USER"], cfg["PASSWORD"]) == ("shop", "u", "p@ss")
    assert (cfg["HOST"], cfg["PORT"]) == ("db.example.com", "6543")
    assert cfg["OPTIONS"] == {"sslmode": "require"}


def test_mysql_and_mariadb_urls():
    for scheme in ("mysql", "mariadb"):
        cfg = parse_database_url(f"{scheme}://root:pw@127.0.0.1:3306/wabot", BASE)
        assert cfg["ENGINE"] == "django.db.backends.mysql"
        assert cfg["OPTIONS"]["charset"] == "utf8mb4"


def test_sqlite_variants():
    assert parse_database_url("sqlite:///db.sqlite3", BASE)["NAME"] == "/app/db.sqlite3"
    assert parse_database_url("sqlite:////var/data/x.db", BASE)["NAME"] == "/var/data/x.db"
    assert parse_database_url("sqlite://:memory:", BASE)["NAME"] == ":memory:"


def test_unknown_scheme_and_missing_name():
    with pytest.raises(ImproperlyConfigured):
        parse_database_url("oracle://u:p@h/x", BASE)
    with pytest.raises(ImproperlyConfigured):
        parse_database_url("postgres://u:p@h:5432/", BASE)

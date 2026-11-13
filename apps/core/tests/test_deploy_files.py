"""Production files me gadbad na ho: compose valid YAML, secrets script, static serving."""

import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]


def test_prod_compose_is_valid_and_database_not_exposed():
    data = yaml.safe_load((ROOT / "docker-compose.prod.yml").read_text())
    services = data["services"]
    assert {"db", "redis", "web", "worker", "beat", "caddy"} <= set(services)
    for name in ("db", "redis", "web", "worker", "beat"):
        assert "ports" not in services[name], f"{name} internet par khula nahi hona chahiye"
    assert services["caddy"]["ports"] == ["80:80", "443:443"]
    assert "gunicorn" in services["web"]["command"]


def test_gen_secrets_prints_all_keys():
    out = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "gen_secrets.py")],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    keys = dict(line.split("=", 1) for line in out.strip().splitlines())
    assert set(keys) == {
        "DJANGO_SECRET_KEY",
        "FIELD_ENCRYPTION_KEY",
        "POSTGRES_PASSWORD",
        "META_VERIFY_TOKEN",
        "ADMIN_URL",
    }
    assert len(keys["DJANGO_SECRET_KEY"]) > 50 and keys["ADMIN_URL"].endswith("/")


def test_env_production_example_has_every_prod_setting():
    text = (ROOT / ".env.production.example").read_text()
    for key in ("DOMAIN", "DJANGO_SECRET_KEY", "FIELD_ENCRYPTION_KEY", "META_APP_SECRET"):
        assert f"{key}=" in text


def test_static_files_served_by_whitenoise(client, db):
    from django.conf import settings

    assert "whitenoise.middleware.WhiteNoiseMiddleware" in settings.MIDDLEWARE

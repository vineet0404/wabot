FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt requirements-dev.txt requirements-mysql.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt

# MySQL/MariaDB chahiye to: docker compose build --build-arg INSTALL_MYSQL=1
ARG INSTALL_MYSQL=0
RUN if [ "$INSTALL_MYSQL" = "1" ]; then \
      apt-get update \
      && apt-get install -y --no-install-recommends build-essential pkg-config default-libmysqlclient-dev \
      && pip install --no-cache-dir -r requirements-mysql.txt \
      && rm -rf /var/lib/apt/lists/*; \
    fi

COPY . .

# Admin ki static files image me hi bana lo (production me whitenoise inhe parosta hai)
RUN DJANGO_DEBUG=1 python manage.py collectstatic --noinput

# Root ki jagah normal user se chalao
RUN useradd --create-home --uid 1000 app
USER app

EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

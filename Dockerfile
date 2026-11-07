FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN adduser --system --group --no-create-home django
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Collect static assets at build time; no secrets or database are needed.
RUN DJANGO_DEBUG=1 python manage.py collectstatic --noinput && chown -R django:django /app
USER django
EXPOSE 8000
CMD ["gunicorn", "calendar_site.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--access-logfile", "-"]

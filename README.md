# EgoFit

EgoFit is a Django-based fitness and coaching platform for managing user profiles, body measurements, coach requests, content, and the admin portal.

## Features

- User registration and login with OTP and password flows
- User profile dashboard with analysis and progress charts
- Coach request workflow with measurements and attachments
- Admin portal for user management, measurements, notifications, and content lookup data
- Persian-first UI with bilingual support through `django-modeltranslation`
- Versioned client API under `/api/v1/` with bearer authentication and protected user workflows

## Tech Stack

- Python 3
- Django 4.2
- SQLite for local development or MySQL in production
- WhiteNoise for static file serving
- Django ModelTranslation for localized content

## Project Structure

- `account/` user accounts, admin portal, measurements, and auth flows
- `home/` public pages, content, courses, articles, and site sections
- `cart/` orders, payments, and discount logic
- `assets/` source CSS and JavaScript
- `templates/` shared base templates and includes

## Local Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create a `.env` file from your deployment values.
   - Start from `.env.example` and fill in the real values for your environment.
4. Use SQLite locally if needed:

```bash
set DJANGO_USE_SQLITE=true
```

5. Run migrations:

```bash
python manage.py migrate
```

6. Start the development server:

```bash
python manage.py runserver
```

For background jobs in production, run a Celery worker alongside Django:

```bash
celery -A sport_shop worker --loglevel=INFO
```

## Environment Variables

Common variables used by the project:

- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_CSRF_TRUSTED_ORIGINS`
- `DJANGO_TIME_ZONE`
- `DJANGO_USE_SQLITE`
- `DJANGO_AUTO_MIGRATE_ON_STARTUP`
- `DJANGO_AUTO_COLLECTSTATIC_ON_STARTUP`
- `DJANGO_TASK_QUEUE_REQUIRED`
- `DJANGO_TASKS_RUN_INLINE`
- `DJANGO_DB_NAME`
- `DJANGO_DB_USER`
- `DJANGO_DB_PASSWORD`
- `DJANGO_DB_HOST`
- `DJANGO_DB_PORT`
- `DJANGO_STATIC_ROOT`
- `DJANGO_MEDIA_ROOT`
- `ZARINPAL_MERCHANT_ID`
- `ZARINPAL_SANDBOX`
- `LIARA_PUBLIC_BASE_URL`
- `REDIS_URL`
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`
- `API_ACCESS_TOKEN_TTL_MINUTES`
- `API_REFRESH_TOKEN_TTL_DAYS`
- `API_CORS_ALLOWED_ORIGINS`

The local `.env` file should never be committed.

## Notes

- `staticfiles/` is generated output and should be recreated with `collectstatic` in deployment pipelines.
- `db.sqlite3`, `media/`, and temporary folders are local artifacts and are ignored by default.
# EgoFit_main

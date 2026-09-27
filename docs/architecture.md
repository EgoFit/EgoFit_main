# Project Architecture

## Feature boundaries

The account application keeps its public URLs under the /accounts/ path while organizing request handlers by feature:

- `account/auth/` contains authentication URLs and compatibility exports for the legacy authentication handlers.
- `account/profile/` contains profile URLs and profile views.
- `account/workouts/` contains workout-program URLs and views.
- `account/documents/` contains document and workout-program payment URLs and compatibility exports.
- `account/admin_portal/` contains staff portal and gym-library URLs and views.

The existing `account/views.py`, `account/profile_views.py`, `account/workout_views.py`, `account/admin_portal_views.py`, and `account/admin_portal_gym_views.py` import paths remain available for third-party or older internal imports.

## API boundaries

The `/api/v1/` public URL space is assembled by `api/v1/urls.py`:

- `api/v1/auth/` contains authentication endpoint exports.
- `api/v1/profile/` contains authenticated user and profile endpoint exports.
- `api/v1/content/` contains course, article, search, comment, and video endpoint exports.
- `api/v1/commerce/` contains cart, order, and payment endpoint exports.

`api/views.py` remains the compatibility implementation during the migration. New endpoint work should be placed in the matching `api/v1/<feature>/` module rather than adding more functions to the legacy facade.

## URL compatibility

The historical `register` namespace remains valid. The `account` namespace is also available as a compatibility alias; both resolve to the same `/accounts/` URLs. Public paths are unchanged.

## Template boundaries

The shared header is split into `templates/includes/header_desktop.html` and `templates/includes/header_mobile.html`. The gym exercise form keeps its large catalog data in the main template while rendering the editable form fields through `account/templates/admin_portal/gym/partials/exercise_fields.html`.

## Validation

Use the following checks before merging structural changes:

    python manage.py check
    python manage.py makemigrations --check --dry-run
    python manage.py test account.tests_url_architecture api.tests_url_architecture
    python manage.py test account.test_security_payments api.tests_auth api.tests_ownership api.tests_payments

# EgoFit API v1

The API is available under `/api/v1/`. It is a client API for athlete/mobile
workflows. The existing HTML views and admin portal remain separate.

## Authentication

Password login and OTP login return a short-lived access token and a rotating
refresh token:

```http
Authorization: Bearer <access_token>
```

Access tokens expire after `API_ACCESS_TOKEN_TTL_MINUTES` (15 minutes by
default). Refresh tokens expire after `API_REFRESH_TOKEN_TTL_DAYS` (30 days by
default). Refresh token rotation revokes the previous token family, and logout
revokes the active family. Only SHA-256 hashes of tokens are stored.

Never put bearer tokens in URLs, logs, browser local storage, or error reports.
Use an OS-secure mobile keychain or an equivalent server-side secret store.

## Main endpoints

- `GET /health/`
- `POST /auth/register/`, `POST /auth/login/`
- `POST /auth/otp/request/`, `POST /auth/otp/verify/`
- `POST /auth/password-reset/request/`, `POST /auth/password-reset/confirm/`
- `POST /auth/refresh/`, `POST /auth/logout/`
- `GET/PATCH /me/`, `PATCH /me/metrics/{weight|height|birth_date|blood_group}/`
- `POST /me/password/change/`, `POST /me/phone/request/`, `POST /me/phone/confirm/`
- `GET /me/dashboard/`, `/me/courses/`, `/me/orders/`, `/me/notifications/`
- `GET /courses/`, `GET /courses/{id}/`, `POST /courses/{id}/enroll/`
- `POST /courses/{id}/comments/` and `/replies/`
- `GET /articles/`, `GET /articles/{slug}/`, `GET /search/`
- `GET/POST /me/coach-requests/`
- `GET /me/programs/`, `POST /me/programs/{id}/performance/`
- `GET /cart/`, `POST /cart/items/{id}/`, `DELETE /cart/items/{id}/delete/`, `DELETE /cart/empty/`
- `POST /orders/`, `POST /orders/{id}/discount/`, `POST /orders/{id}/payment/`
- `GET /me/documents/{id}/download/`, `POST /me/documents/{id}/payment/`, `GET /episodes/{id}/video/`
- `GET /payments/documents/verify/`

## Security rules

- API requests never authenticate from Django's browser session cookie.
- Write endpoints require a valid bearer token and enforce object ownership.
- Input fields are explicitly allowlisted; model fields such as `user`, `is_admin`,
  payment status, ownership, and moderation state cannot be mass-assigned.
- OTP, login, registration, and comment writes are rate-limited.
- Password reset responses do not reveal whether a phone number is registered.
- CORS is disabled by default. If a browser client needs it, set
  `API_CORS_ALLOWED_ORIGINS` to exact HTTPS origins separated by commas; wildcard
  origins are not supported.
- Admin/content-management writes are intentionally not exposed through this
  public API. Add a separate privileged API only with action-specific
  permissions and audit logging.

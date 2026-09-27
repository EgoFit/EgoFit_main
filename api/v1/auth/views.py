from api.v1.common import *

@api_endpoint
@api_methods("GET")
def health(request):
    return ok({"status": "ok", "api_version": "v1"})

@api_endpoint
@api_methods("POST")
@rate_limit(name="register", limit=5, window=900)
def register(request):
    data = request_data(request)
    _reject_unknown(data, {"fullname", "phone", "password", "device_name"})
    fullname = str(data.get("fullname") or "").strip()
    phone = validate_phone_number(data.get("phone"))
    password = str(data.get("password") or "")
    validate_fullname(fullname)
    validate_strong_password(password)
    user = auth_service.register_user(fullname=fullname, phone=phone, password=password)
    return ok({"user": _serialize_user(request, user), **issue_token_pair(user=user, name=data.get("device_name", ""))}, status=201)

@api_endpoint
@api_methods("POST")
@rate_limit(name="login", limit=10, window=900)
def login(request):
    data = request_data(request)
    _reject_unknown(data, {"fullname", "password", "device_name"})
    fullname = str(data.get("fullname") or "").strip()
    password = str(data.get("password") or "")
    user = authenticate(username=fullname, password=password)
    if user is None or not user.is_active:
        return error("invalid_credentials", "Invalid credentials.", status=401)
    return ok({"user": _serialize_user(request, user), **issue_token_pair(user=user, name=data.get("device_name", ""))})

@api_endpoint
@api_methods("POST")
@rate_limit(name="otp-request", limit=5, window=900)
def otp_request(request):
    data = request_data(request)
    _reject_unknown(data, {"phone"})
    phone = validate_phone_number(data.get("phone"))
    # Keep the token opaque and never return the OTP code in an API response.
    result = otp_service.create_otp(phone)
    return ok({"verification_token": result.token, "expires_in": 300})

@api_endpoint
@api_methods("POST")
@rate_limit(name="otp-verify", limit=10, window=900)
def otp_verify(request):
    data = request_data(request)
    _reject_unknown(data, {"verification_token", "code", "device_name"})
    verification_token = str(data.get("verification_token") or "").strip()
    try:
        code = int(str(data.get("code") or "").strip())
    except ValueError:
        return error("invalid_otp", "The verification code is invalid.", status=400)
    otp = otp_service.validate_otp(token=verification_token, code=code)
    user, _created = auth_service.get_or_create_otp_user(phone=otp.phone)
    otp_service.consume_otp(otp)
    return ok({"user": _serialize_user(request, user), **issue_token_pair(user=user, name=data.get("device_name", ""))})

@api_endpoint
@api_methods("POST")
@rate_limit(name="refresh", limit=20, window=900)
def refresh(request):
    data = request_data(request)
    _reject_unknown(data, {"refresh_token"})
    pair = rotate_token_pair(str(data.get("refresh_token") or "").strip())
    if pair is None:
        return error("invalid_refresh_token", "The refresh token is invalid or expired.", status=401)
    return ok(pair)

@api_endpoint
@api_methods("POST")
def logout(request):
    raw_refresh = str((request_data(request) or {}).get("refresh_token") or "").strip()
    token = getattr(request, "api_token", None)
    if token:
        ApiToken.objects.filter(family_id=token.family_id, revoked_at__isnull=True).update(revoked_at=timezone.now())
    if raw_refresh:
        refresh_token = ApiToken.objects.filter(token_hash=_hash_token(raw_refresh)).first()
        if refresh_token:
            ApiToken.objects.filter(family_id=refresh_token.family_id, revoked_at__isnull=True).update(revoked_at=timezone.now())
    return ok({"logged_out": True})


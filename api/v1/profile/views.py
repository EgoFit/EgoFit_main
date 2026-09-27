from api.v1.common import *

@api_endpoint
@api_methods("GET", "PATCH")
@api_auth_required
def me(request):
    if request.method == "GET":
        return ok({"user": _serialize_user(request, request.user), "metrics": profile_service.get_profile_metrics(request.user)})
    data = request_data(request)
    allowed = {"first_name", "last_name", "display_name", "email", "biography", "web_site", "github", "linkdin", "telegram"}
    unknown = set(data) - allowed
    if unknown:
        raise ValidationError({"fields": [f"Unsupported fields: {', '.join(sorted(unknown))}"]})
    for field in allowed:
        if field in data:
            value = data[field]
            if field == "email":
                from django.forms import EmailField

                value = EmailField(required=False).clean(value)
                if request.user.__class__.objects.filter(email=value).exclude(pk=request.user.pk).exists():
                    raise ValidationError({"email": "This email is already in use."})
            setattr(request.user, field, value)
    request.user.save(update_fields=[field for field in allowed if field in data])
    return ok({"user": _serialize_user(request, request.user)})

@api_endpoint
@api_methods("PATCH")
@api_auth_required
def metric(request, metric_name):
    data = request_data(request)
    form_map = {
        "weight": (WeightForm, "weight", "weight_kg"),
        "height": (HeightForm, "height", "height_cm"),
        "birth_date": (BirthDateForm, "birth_date", "birth_date_jalali"),
        "blood_group": (BloodGroupForm, "blood_group", "blood_group"),
    }
    if metric_name not in form_map:
        return error("not_found", "Metric not found.", status=404)
    form_class, input_name, model_field = form_map[metric_name]
    form = form_class(data={input_name: data.get(input_name)})
    if not form.is_valid():
        raise ValidationError(form.errors)
    profile_service.update_profile_metric(user=request.user, field_name=model_field, value=form.cleaned_data[input_name])
    return ok({"user": _serialize_user(request, request.user), "metric": metric_name})

@api_endpoint
@api_methods("POST")
@api_auth_required
def password_change(request):
    data = request_data(request)
    _reject_unknown(data, {"old_password", "new_password"})
    old_password = str(data.get("old_password") or "")
    new_password = str(data.get("new_password") or "")
    validate_strong_password(new_password)
    password_service.change_password(user=request.user, old_password=old_password, new_password=new_password)
    revoke_user_tokens(request.user)
    return ok({"changed": True})

@api_endpoint
@api_methods("POST")
@rate_limit(name="password-reset-request", limit=5, window=900)
def password_reset_request(request):
    data = request_data(request)
    _reject_unknown(data, {"phone"})
    phone = validate_phone_number(data.get("phone"))
    if not User.objects.filter(phone=phone, is_active=True).exists():
        # Avoid account enumeration while keeping the response useful to a
        # legitimate client.
        return ok({"accepted": True, "message": "If the account exists, a verification code was sent."}, status=202)
    result = otp_service.create_otp(phone)
    return ok({"accepted": True, "verification_token": result.token, "expires_in": 300})

@api_endpoint
@api_methods("POST")
@rate_limit(name="password-reset-confirm", limit=10, window=900)
def password_reset_confirm(request):
    data = request_data(request)
    _reject_unknown(data, {"verification_token", "code", "new_password"})
    validate_strong_password(str(data.get("new_password") or ""))
    try:
        code = int(str(data.get("code") or "").strip())
    except ValueError:
        return error("invalid_otp", "The verification code is invalid.", status=400)
    otp = otp_service.validate_otp(token=str(data.get("verification_token") or "").strip(), code=code)
    user = User.objects.filter(phone=otp.phone, is_active=True).first()
    if user is None:
        otp_service.consume_otp(otp)
        return error("invalid_reset", "The password reset request is invalid.", status=400)
    password_service.reset_password(user=user, new_password=str(data.get("new_password")))
    otp_service.consume_otp(otp)
    revoke_user_tokens(user)
    return ok({"reset": True})

@api_endpoint
@api_methods("POST")
@api_auth_required
@rate_limit(name="phone-change-request", limit=5, window=900)
def phone_change_request(request):
    data = request_data(request)
    _reject_unknown(data, {"phone"})
    phone = validate_phone_number(data.get("phone"))
    if User.objects.filter(phone=phone).exclude(pk=request.user.pk).exists():
        return error("phone_unavailable", "This phone number is already in use.", status=409)
    result = otp_service.create_otp(phone)
    return ok({"verification_token": result.token, "expires_in": 300})

@api_endpoint
@api_methods("POST")
@api_auth_required
@rate_limit(name="phone-change-confirm", limit=10, window=900)
def phone_change_confirm(request):
    data = request_data(request)
    _reject_unknown(data, {"verification_token", "code"})
    try:
        code = int(str(data.get("code") or "").strip())
    except ValueError:
        return error("invalid_otp", "The verification code is invalid.", status=400)
    with transaction.atomic():
        otp = otp_service.validate_otp(token=str(data.get("verification_token") or "").strip(), code=code)
        if User.objects.filter(phone=otp.phone).exclude(pk=request.user.pk).exists():
            otp_service.consume_otp(otp)
            return error("phone_unavailable", "This phone number is already in use.", status=409)
        request.user.phone = otp.phone
        request.user.save(update_fields=["phone"])
        otp_service.consume_otp(otp)
    return ok({"user": _serialize_user(request, request.user)})

@api_endpoint
@api_methods("GET")
@api_auth_required
def dashboard(request):
    context = profile_service.get_dashboard_context(request.user)
    return ok({
        "cards": context["dashboard_cards"],
        "profile_metrics": context["profile_metrics"],
        "feed": context["dashboard_feed"],
        "counts": {
            "courses": context["learning_courses_count"],
            "orders": context["paid_orders_count"],
            "comments": context["comments_count"],
            "notifications": context["notifications_count"],
        },
    })

@api_endpoint
@api_methods("GET")
@api_auth_required
def courses(request):
    return ok({"items": [_serialize_series(request, item, include_description=False) for item in profile_service.get_learning_courses(request.user)]})

@api_endpoint
@api_methods("GET")
@api_auth_required
def notifications(request):
    items = notification_service.get_profile_notifications(request.user, limit=50)
    return ok({"items": [
        {"id": getattr(item, "pk", None), "title": item.title, "message": item.message, "created_at": json_value(item.created_at), "read": getattr(item, "read", False), "global": getattr(item, "is_global", False)}
        for item in items
    ]})

@api_endpoint
@api_methods("POST")
@api_auth_required
def mark_notification_read(request, pk):
    from account.models import Notification

    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notification.read = True
    notification.save(update_fields=["read"])
    return ok({"read": True})

@api_endpoint
@api_methods("GET", "POST")
@api_auth_required
def coach_request(request):
    if request.method == "GET":
        items = request.user.coach_requests.all()[:20]
        return ok({"items": [{"id": item.pk, "status": item.status, "created_at": json_value(item.created_at), "updated_at": json_value(item.updated_at)} for item in items]})
    pending = coach_request_service.get_pending_for_user(request.user).first()
    allowed = set(CoachRequestForm.Meta.fields) | {"attachments"}
    unknown = set(request_data(request).keys()) - allowed
    if unknown:
        raise ValidationError({"fields": [f"Unsupported fields: {', '.join(sorted(unknown))}"]})
    uploads = request.FILES.getlist("attachments")
    if len(uploads) > 10:
        raise ValidationError({"attachments": "At most 10 attachments may be submitted."})
    for uploaded in uploads:
        validate_coach_request_file(uploaded)
    form = CoachRequestForm(data=request_data(request), files=request.FILES, instance=pending)
    if not form.is_valid():
        raise ValidationError(form.errors)
    item = coach_request_service.save_request(user=request.user, form=form, files=request.FILES.getlist("attachments"))
    return ok({"request": {"id": item.pk, "status": item.status}}, status=201 if pending is None else 200)

@api_endpoint
@api_methods("GET")
@api_auth_required
def programs(request):
    queryset = WorkoutProgram.objects.filter(user=request.user, is_published=True).prefetch_related(
        "days__items__exercise", "days__items__superset_exercise", "days__items__third_exercise"
    )
    return ok({"items": [_serialize_program(program) for program in queryset]})

@api_endpoint
@api_methods("POST")
@api_auth_required
def program_performance(request, pk):
    data = request_data(request)
    program = get_object_or_404(WorkoutProgram, pk=pk, user=request.user, is_published=True)
    records = data.get("records", [])
    if not isinstance(records, list) or len(records) > 100:
        raise ValidationError({"records": "records must be an array with at most 100 items."})
    day_id = data.get("day_id")
    day = None
    if day_id is not None:
        day = get_object_or_404(WorkoutProgramDay, pk=day_id, program=program)
    saved = 0
    with transaction.atomic():
        for entry in records:
            if not isinstance(entry, dict):
                raise ValidationError({"records": "Each record must be an object."})
            item = get_object_or_404(WorkoutProgramExercise.objects.select_related("exercise", "superset_exercise", "third_exercise", "day"), pk=entry.get("program_exercise_id"), day__program=program)
            if day is not None and item.day_id != day.pk:
                raise ValidationError({"program_exercise_id": "The exercise does not belong to day_id."})
            exercise_id = parse_int(entry.get("exercise_id"), field="exercise_id")
            if exercise_id not in {item.exercise_id, item.superset_exercise_id, item.third_exercise_id}:
                raise ValidationError({"exercise_id": "The exercise is not part of this program item."})
            mode = str(entry.get("mode") or "")
            if mode not in WorkoutPerformanceRecord.Mode.values:
                raise ValidationError({"mode": "Invalid performance mode."})
            repetitions = str(entry.get("repetitions") or "").strip()[:60]
            set_number = parse_int(entry.get("set_number"), field="set_number")
            if not repetitions or set_number < 1:
                raise ValidationError({"record": "repetitions and a positive set_number are required."})
            try:
                value = Decimal(str(entry.get("value")))
            except (InvalidOperation, TypeError, ValueError):
                raise ValidationError({"value": "value must be a positive number."})
            if value <= 0 or value > Decimal("999999.99"):
                raise ValidationError({"value": "value must be between 0 and 999999.99."})
            record, created = WorkoutPerformanceRecord.objects.select_for_update().get_or_create(
                user=request.user, exercise_id=exercise_id, repetitions=repetitions, mode=mode, set_number=set_number,
                defaults={"program": program, "program_exercise": item, "value": value},
            )
            if not created and value > record.value:
                record.value = value
                record.program = program
                record.program_exercise = item
                record.save(update_fields=["value", "program", "program_exercise", "updated_at"])
            saved += 1
        if "difficulty" in data:
            difficulty = parse_int(data.get("difficulty"), field="difficulty")
            if not 0 <= difficulty <= 10:
                raise ValidationError({"difficulty": "difficulty must be between 0 and 10."})
            from account.models import WorkoutProgramFeedback

            WorkoutProgramFeedback.objects.update_or_create(program=program, day=day, defaults={"difficulty": difficulty})
    return ok({"saved_records": saved})

@api_endpoint
@api_methods("GET")
@api_auth_required
def document_download(request, pk):
    document = get_object_or_404(ClientDocument, pk=pk, user=request.user)
    if document.requires_payment and not ClientDocumentPayment.objects.filter(document=document, user=request.user, status=ClientDocumentPayment.Status.PAID).exists():
        return error("payment_required", "This document requires payment.", status=403)
    document.file.open("rb")
    response = FileResponse(document.file, as_attachment=True, filename=os.path.basename(document.file.name))
    response["Cache-Control"] = "private, no-store"
    return response

@api_endpoint
@api_methods("POST")
@api_auth_required
def document_payment(request, pk):
    document = get_object_or_404(ClientDocument, pk=pk, user=request.user)
    if not document.requires_payment or document.price <= 0:
        return error("payment_not_required", "This document does not require payment.", status=400)
    result = access_payment_service.initiate_document(
        document_id=document.pk,
        user=request.user,
        callback_url=build_payment_callback_url(request, url_name="api:document_payment_verify"),
    )
    if result.already_paid:
        return ok({"document_id": document.pk, "already_paid": True})
    return ok({"document_id": document.pk, "payment_id": result.payment_id, "redirect_url": result.redirect_url})

    if ClientDocumentPayment.objects.filter(document=document, user=request.user, status=ClientDocumentPayment.Status.PAID).exists():
        return ok({"document_id": document.pk, "already_paid": True})
    payment = ClientDocumentPayment.objects.filter(
        document=document, user=request.user, status=ClientDocumentPayment.Status.INITIATED
    ).first()
    if payment is None:
        payment = ClientDocumentPayment.objects.create(document=document, user=request.user, amount=document.price)
    result = ZarinPalPaymentProvider().request_payment(
        amount=payment.amount,
        callback_url=build_payment_callback_url(request, url_name="api:document_payment_verify"),
        description=f"دریافت فایل {document.title}",
        mobile=request.user.phone,
        email=request.user.email or None,
    )
    payment.authority = result.authority
    payment.status = ClientDocumentPayment.Status.INITIATED
    payment.save(update_fields=["authority", "status"])
    return ok({"document_id": document.pk, "payment_id": payment.pk, "redirect_url": result.redirect_url})


from api.v1.common import *

@api_endpoint
@api_methods("GET")
@api_auth_required
def orders(request):
    return ok({"items": [_serialize_order(order) for order in profile_service.get_paid_orders(request.user)]})

@api_endpoint
@api_methods("GET")
@api_auth_required
def cart_detail(request):
    cart = Cart(request)
    return ok({"items": [
        {"product": _serialize_series(request, item["product"], include_description=False), "quantity": item.get("quantity", 1), "price": item.get("price")}
        for item in cart
    ], "total_price": str(cart.total_price)})

@api_endpoint
@api_methods("POST")
@api_auth_required
def cart_add(request, pk):
    product = get_object_or_404(SeriesModel, pk=pk)
    if OrderSelector.user_has_paid_product(user=request.user, product=product):
        return error("already_owned", "You already own this course.", status=409)
    cart = Cart(request)
    cart.add(quantity=1, product=product)
    return cart_detail(request)

@api_endpoint
@api_methods("DELETE")
@api_auth_required
def cart_delete(request, pk):
    cart = Cart(request)
    cart.delete(str(pk))
    return cart_detail(request)

@api_endpoint
@api_methods("DELETE")
@api_auth_required
def cart_empty(request):
    Cart(request).remove()
    return ok({"empty": True})

@api_endpoint
@api_methods("POST")
@api_auth_required
def order_create(request):
    order = build_order_from_cart(user=request.user, cart=Cart(request))
    Cart(request).remove()
    return ok({"order": _serialize_order(order)}, status=201)

@api_endpoint
@api_methods("POST")
@api_auth_required
def order_discount(request, pk):
    data = request_data(request)
    order = get_object_or_404(Order, pk=pk, user=request.user, is_paid=False)
    order, discount_amount = apply_discount(order_id=order.pk, user=request.user, raw_code=data.get("discount_code"))
    return ok({"order": _serialize_order(order), "discount_amount": discount_amount})

@api_endpoint
@api_methods("POST")
@api_auth_required
def order_payment(request, pk):
    order = get_object_or_404(Order, pk=pk, user=request.user, is_paid=False)
    callback_url = build_payment_callback_url(request, url_name="api:payment_verify")
    redirect_url = payment_service.initiate_payment(order=order, callback_url=callback_url)
    return ok({"order_id": order.pk, "redirect_url": redirect_url})

@api_endpoint
@api_methods("GET")
def payment_verify(request):
    authority = (request.GET.get("Authority") or "").strip()
    status = (request.GET.get("Status") or "").strip().upper()
    if not authority:
        return error("invalid_callback", "Payment authority is missing.")
    result = payment_service.verify_callback(authority=authority, status=status)
    if result.is_missing_order:
        return error("not_found", "Payment order was not found.", status=404)
    return ok({"state": result.state, "ref_id": result.ref_id, "order_id": result.order.pk if result.order else None})

@api_endpoint
@api_methods("GET")
def document_payment_verify(request):
    authority = (request.GET.get("Authority") or "").strip()
    status = (request.GET.get("Status") or "").strip().upper()
    result = access_payment_service.verify_document(authority=authority, status=status)
    if result.payment is None:
        return error("not_found", "Document payment was not found.", status=404)
    if result.state not in {"paid", "already_paid"}:
        return error("payment_failed", result.message or "Document payment could not be verified.")
    return ok({"state": result.state, "document_id": result.payment.document_id, "ref_id": result.ref_id})

    payment = ClientDocumentPayment.objects.filter(
        authority=authority, status=ClientDocumentPayment.Status.INITIATED
    ).select_related("document", "user").first()
    if payment is None:
        return error("not_found", "Document payment was not found.", status=404)
    if status != "OK":
        payment.status = ClientDocumentPayment.Status.FAILED
        payment.save(update_fields=["status"])
        return ok({"state": "failed", "document_id": payment.document_id})
    try:
        result = ZarinPalPaymentProvider().verify_payment(amount=payment.amount, authority=authority)
    except PaymentVerificationException as exc:
        payment.status = ClientDocumentPayment.Status.FAILED
        payment.save(update_fields=["status"])
        return error("payment_failed", str(exc))
    if not result.success:
        payment.status = ClientDocumentPayment.Status.FAILED
        payment.save(update_fields=["status"])
        return error("payment_failed", result.message or "Document payment could not be verified.")
    payment.status = ClientDocumentPayment.Status.PAID
    payment.ref_id = result.ref_id or ""
    payment.paid_at = timezone.now()
    payment.save(update_fields=["status", "ref_id", "paid_at"])
    return ok({"state": "paid", "document_id": payment.document_id, "ref_id": payment.ref_id})


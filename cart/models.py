from uuid import uuid4

from django.db import models
from django.utils import timezone

from account.models import User
from home.models import SeriesModel


class DiscountCode(models.Model):
    class Meta:
        verbose_name = "کد تخفیف"
        verbose_name_plural = "کد های تخفیف"
        indexes = [
            models.Index(fields=["is_active"]),
        ]

    name = models.CharField(max_length=32, unique=True, verbose_name="نام")
    percentage = models.SmallIntegerField(default=0, verbose_name="درصد")
    quantity = models.SmallIntegerField(default=1, verbose_name="تعداد")
    is_active = models.BooleanField(default=True, verbose_name="فعال", db_index=True)

    def __str__(self):
        return self.name


class UserDiscountCode(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    discount_code = models.ForeignKey(DiscountCode, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('user', 'discount_code')
        indexes = [
            models.Index(fields=['user', 'discount_code']),
        ]


class Order(models.Model):
    class PaymentStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        PAYMENT_INITIATED = "payment_initiated", "Payment Initiated"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="orders", verbose_name='کاربر')
    course = models.ForeignKey(
        SeriesModel,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="orders",
        verbose_name="دوره",
    )
    order_number = models.CharField(max_length=32, unique=True, default="", editable=False)
    subtotal_price = models.PositiveIntegerField(default=0, verbose_name='مبلغ اولیه')
    discount_amount = models.PositiveIntegerField(default=0, verbose_name='مبلغ تخفیف')
    total_price = models.PositiveIntegerField(default=0, verbose_name='مبلغ کل')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد', db_index=True)
    is_paid = models.BooleanField(default=False, verbose_name='پرداخت شده')
    status = models.CharField(
        max_length=32,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
        db_index=True,
    )
    authority = models.CharField(max_length=64, null=True, blank=True, unique=True)
    ref_id = models.CharField(max_length=64, null=True, blank=True)
    applied_discount_code = models.ForeignKey(
        DiscountCode,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="orders",
    )
    payment_attempted_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['user', 'is_paid']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"سفارش {self.id} برای {self.user.fullname}"

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = uuid4().hex[:16].upper()
        super().save(*args, **kwargs)

    def mark_payment_initiated(self, authority):
        self.authority = authority
        self.status = self.PaymentStatus.PAYMENT_INITIATED
        self.payment_attempted_at = timezone.now()
        self.save(update_fields=['authority', 'status', 'payment_attempted_at'])

    def mark_paid(self, ref_id=None):
        self.is_paid = True
        self.status = self.PaymentStatus.PAID
        self.ref_id = str(ref_id or self.ref_id or "")
        self.paid_at = timezone.now()
        self.save(update_fields=['is_paid', 'status', 'ref_id', 'paid_at'])

    def mark_failed(self):
        self.status = self.PaymentStatus.FAILED
        self.save(update_fields=['status'])


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items", verbose_name="سفارش")
    product = models.ForeignKey(SeriesModel, on_delete=models.CASCADE, related_name="order_items", verbose_name="محصول")
    price = models.PositiveIntegerField(verbose_name="قیمت")

    class Meta:
        verbose_name = "اقلام سفارش"
        verbose_name_plural = "اقلام سفارش ها"
        constraints = [
            models.UniqueConstraint(fields=['order', 'product'], name='unique_order_product'),
        ]
        indexes = [
            models.Index(fields=['order', 'product']),
            models.Index(fields=['product', 'order']),
        ]

    def __str__(self):
        return f"اقلام سفارش {self.order.id} برای {self.product.title}"

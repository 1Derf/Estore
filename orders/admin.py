from django.contrib import admin, messages
from django import forms
from .models import Payment, Order, OrderProduct, PayPalWebhookLog
from .paypal_utils import capture_paypal_payment   # <-- import our helper


class OrderProductInline(admin.TabularInline):
    model = OrderProduct
    readonly_fields = (
        'user', 'product', 'quantity',
        'product_price', 'ordered', 'order_payment_status'
    )
    extra = 0

    def order_payment_status(self, obj):
        if obj.order.payment:
            return obj.order.payment.status
        return 'N/A'
    order_payment_status.short_description = 'Payment Status'


class OrderProductForm(forms.ModelForm):
    class Meta:
        model = OrderProduct
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = kwargs.get('instance')
        if 'payment' in self.fields:  # Avoid KeyError
            if instance and instance.user:
                payments = Payment.objects.filter(user=instance.user)
                self.fields['payment'].choices = [
                    (p.pk, f"{p.status} ({p.transaction_id})") for p in payments
                ]
                if instance.order and instance.order.payment:
                    correct_pk = instance.order.payment.pk
                    self.fields['payment'].initial = correct_pk
            else:
                self.fields['payment'].choices = []


class OrderAdmin(admin.ModelAdmin):
    list_display = [
        "order_number", "full_name", "phone", "email", "city",
        "formatted_order_total", "formatted_tax", "status", "is_ordered", "created_at"
    ]
    list_filter = ["status", "is_ordered"]
    search_fields = ["order_number", "first_name", "last_name", "phone", "email"]
    list_per_page = 20
    inlines = [OrderProductInline]
    actions = ["capture_paypal"]

    def formatted_order_total(self, obj):
        return f"{obj.order_total:.2f}"
    formatted_order_total.short_description = "Total"

    def formatted_tax(self, obj):
        return f"{obj.tax:.2f}"
    formatted_tax.short_description = "Tax"

    def capture_paypal(self, request, queryset):
        captured = 0
        for order in queryset:
            if order.status == "AUTHORIZED" and getattr(order, "paypal_authorization_id", None):
                try:
                    capture = capture_paypal_payment(
                        order.paypal_authorization_id,
                        order.order_total
                    )

                    status = capture.get("status")
                    reason = capture.get("status_details", {}).get("reason", "N/A")
                    capture_id = capture.get("id")

                    # Always update Payment with the capture attempt
                    if order.payment:
                        order.payment.payment_id = capture_id or order.payment.payment_id
                        order.payment.status = status
                        order.payment.amount_paid = order.order_total
                        order.payment.save()

                    # COMPLETED → finalize order
                    if status == "COMPLETED":
                        order.status = "COMPLETED"
                        order.is_ordered = True
                        order.save()

                        for op in order.orderproduct_set.all():
                            op.ordered = True
                            op.save()

                        captured += 1
                        self.message_user(
                            request,
                            f"Order {order.order_number} captured successfully! "
                            f"Capture ID: {capture_id}",
                            level=messages.SUCCESS
                        )

                    # PENDING → update order status to PENDING
                    elif status == "PENDING":
                        order.status = "PENDING"
                        order.save()

                        self.message_user(
                            request,
                            f"Capture for order {order.order_number} is pending. "
                            f"Reason: {reason}. Capture ID: {capture_id}",
                            level=messages.WARNING
                        )

                    else:
                        self.message_user(
                            request,
                            f"Capture for order {order.order_number} returned status {status}. "
                            f"Reason: {reason}.",
                            level=messages.ERROR
                        )

                except Exception as e:
                    self.message_user(
                        request,
                        f"Error capturing order {order.order_number}: {e}",
                        level=messages.ERROR
                    )
            else:
                self.message_user(
                    request,
                    f"Order {order.order_number} is not eligible for capture",
                    level=messages.WARNING
                )

        if captured:
            self.message_user(
                request,
                f"Successfully captured {captured} order(s).",
                level=messages.SUCCESS
            )

    capture_paypal.short_description = "Capture selected PayPal Authorizations"


class OrderProductAdmin(admin.ModelAdmin):
    list_display = (
        'product', 'order', 'quantity',
        'product_price', 'ordered', 'get_order_payment_id'
    )
    fields = (
        'order', 'user', 'product', 'variations',
        'quantity', 'product_price', 'ordered', 'payment'
    )
    readonly_fields = ('get_order_payment_id',)

    def get_order_payment_id(self, obj):
        if obj.order.payment:
            return obj.order.payment.transaction_id or "N/A"
        return 'N/A'
    get_order_payment_id.short_description = 'Payment Transaction ID'

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if obj and 'payment' in form.base_fields:
            if obj.user:
                payments = Payment.objects.filter(user=obj.user)
                form.base_fields['payment'].choices = [
                    (p.pk, f"{p.status} ({p.transaction_id})") for p in payments
                ]
                if obj.order and obj.order.payment:
                    form.base_fields['payment'].initial = obj.order.payment.pk
        return form

    def save_model(self, request, obj, form, change):
        if obj.order and obj.order.payment:
            obj.payment = obj.order.payment
        super().save_model(request, obj, form, change)


@admin.register(PayPalWebhookLog)
class PayPalWebhookLogAdmin(admin.ModelAdmin):
    list_display = ("event_type", "received_at")
    list_filter = ("event_type",)
    search_fields = ("event_type", "payload")
    readonly_fields = ("event_type", "payload", "received_at")
    ordering = ("-received_at",)


admin.site.register(Payment)
admin.site.register(Order, OrderAdmin)
admin.site.register(OrderProduct, OrderProductAdmin)
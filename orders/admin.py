import email

from django.contrib import admin, messages
from django import forms
from .models import Payment, Order, OrderProduct, PayPalWebhookLog, SiteSettings
from .paypal_utils import capture_paypal_payment   # <-- import our helper
from django.contrib import admin
from django.utils.html import format_html
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from .models import Order


class OrderProductInline(admin.TabularInline):
    model = OrderProduct
    readonly_fields = (
        'user', 'product', 'quantity',
        'product_price', 'ordered_icon', 'order_payment_status'
    )
    exclude = ("ordered",)
    extra = 0

    def order_payment_status(self, obj):
        if obj.order.payment:
            return obj.order.payment.status
        return 'N/A'
    order_payment_status.short_description = 'Payment Status'

    def ordered_icon(self, obj):
        if obj.ordered:
            return format_html('<span style="color:green;">✔</span>')
        return format_html('<span style="color:red;">✘</span>')

    ordered_icon.short_description = "Ordered"


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
        "order_number", "full_name", "phone",
        "formatted_order_total", "payment_status_icon", "payment_status_display",
        "order_status",  "created_at",
        "shipped_icon", "tracking_number", "is_ordered_icon",
    ]
    list_filter = ["status", "order_status", "is_ordered"]
    search_fields = ["order_number", "first_name", "last_name", "phone", "email"]
    list_per_page = 20
    inlines = [OrderProductInline]
    actions = ["capture_paypal"]

    fieldsets = (
        (None, {
            "fields": (
                "user", "order_number", "payment", "status", "order_status", "is_ordered",
                "tracking_number", "order_total", "tax", "shipping_cost", "paypal_authorization_id", "ip",
            )
        }),
        ("Customer Info", {
            "fields": ("first_name", "last_name", "phone", "email")
        }),
        ("Billing / Address", {
            "fields": (
                "address_line_1", "address_line_2", "city", "state", "zip_code", "country",
                "order_note"
            )
        }),
        ("Shipping", {
            "fields": (
                "shipping_first_name", "shipping_last_name", "shipping_email", "shipping_phone",
                "shipping_address_line_1", "shipping_address_line_2",
                "shipping_city", "shipping_state", "shipping_zip_code", "shipping_country",
                "shipping_method", 'shipping_carrier', 'custom_carrier_details',
            )
        }),
        ("Supplier Info (admin only)", {
            "classes": ("collapse",),
            "fields": ("supplier_name", "po_number", "supplier_order_date"),
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at")
        }),
    )

    readonly_fields = ("created_at", "updated_at")


    def formatted_order_total(self, obj):
        return f"{obj.order_total:.2f}"
    formatted_order_total.short_description = "Total"

    def formatted_tax(self, obj):
        return f"{obj.tax:.2f}"
    formatted_tax.short_description = "Tax"

    def payment_status_display(self, obj):
        return obj.status

    def is_ordered_icon(self, obj):
        if obj.is_ordered:
            return format_html('<span style="color:green;">✔</span>')
        return format_html('<span style="color:red;">✘</span>')

    is_ordered_icon.short_description = "Is Ordered"

    payment_status_display.short_description = "Payment Status"

    def payment_status_icon(self, obj):
        if obj.status == "CAPTURED":
            return format_html('<span style="color:green;">✔</span>')
        return format_html('<span style="color:red;">✘</span>')

    payment_status_icon.short_description = "Payment"

    def shipped_icon(self, obj):
        if obj.order_status == "SHIPPED":
            return format_html('<span style="color:green;">✔</span>')
        return format_html('<span style="color:red;">✘</span>')

    shipped_icon.short_description = "Shipped"

    def save_model(self, request, obj, form, change):
        if change:
            old_obj = Order.objects.get(pk=obj.pk)

            # When order status changes to SHIPPED
            if old_obj.order_status != obj.order_status and obj.order_status == "SHIPPED":
                # mark the order as ordered
                obj.is_ordered = True
                obj.save()

                # mark all related order products as ordered
                obj.orderproduct_set.update(ordered=True)

                # send the shipping confirmation email
                self.send_shipping_email(obj)

            # Supplier info filled → mark as ordered
            elif (obj.supplier_name or obj.po_number or obj.supplier_order_date):
                obj.is_ordered = True
                obj.save()
                obj.orderproduct_set.update(ordered=True)

            # Supplier info cleared + not shipped → revert to not ordered
            elif (
                    not obj.supplier_name and not obj.po_number and not obj.supplier_order_date and obj.order_status != "SHIPPED"):
                obj.is_ordered = False
                obj.save()
                obj.orderproduct_set.update(ordered=False)

        super().save_model(request, obj, form, change)

    def send_shipping_email(self, order):
        subject = f"Your order {order.order_number} has shipped!"
        context = {
            "order": order,
            "user": getattr(order, "user", None),
            "ordered_products": order.orderproduct_set.all(),
            "total": order.order_total - order.tax - order.shipping_cost,
            "tax": order.tax,
            "shipping_method": getattr(order, "shipping_method", "Standard"),
            "shipping_cost": order.shipping_cost,
            "grand_total": order.order_total,
            "payment": order.payment,
        }
        html_message = render_to_string("orders/shipped_email.html", context)
        send_mail(
            subject,
            "",  # plain text body (can leave empty)
            settings.DEFAULT_FROM_EMAIL,
            [order.email],
            html_message=html_message,
        )


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

                    if status == "COMPLETED":
                        status = "CAPTURED"

                    # Always update Payment with the capture attempt
                    if order.payment:
                        order.payment.payment_id = capture_id or order.payment.payment_id
                        order.payment.status = status
                        order.payment.amount_paid = order.order_total
                        order.payment.save()

                    # COMPLETED → finalize order
                    if status == "CAPTURED":
                        order.status = "CAPTURED"
                        order.order_status = "PROCESSING"
                        order.is_ordered = False
                        order.save()

                        for op in order.orderproduct_set.all():
                            op.ordered = False
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
            return obj.order.payment.payment_id or "N/A"
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


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    pass  # Basic admin, you can toggle/edit here
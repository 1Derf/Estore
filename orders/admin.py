from django.contrib import admin, messages
from django import forms
from .models import Payment, Order, OrderProduct
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
        'order_number', 'full_name', 'phone', 'email', 'city',
        'order_total', 'tax', 'status', 'is_ordered', 'created_at'
    ]
    list_filter = ['status', 'is_ordered']
    search_fields = ['order_number', 'first_name', 'last_name', 'phone', 'email']
    list_per_page = 20
    inlines = [OrderProductInline]
    actions = ['capture_paypal']   # <-- admin action appears in dropdown

    # ACTION: Capture PayPal Authorizations
    def capture_paypal(self, request, queryset):
        captured = 0
        for order in queryset:
            if order.status == "AUTHORIZED" and order.paypal_authorization_id:
                try:
                    capture = capture_paypal_payment(
                        order.paypal_authorization_id,
                        order.order_total
                    )

                    if capture.get("status") == "COMPLETED":
                        # Update Payment
                        order.payment.status = "COMPLETED"
                        order.payment.transaction_id = capture["id"]  # capture ID
                        order.payment.amount_paid = order.order_total
                        order.payment.save()

                        # Update Order
                        order.status = "COMPLETED"
                        order.is_ordered = True
                        order.save()

                        # Update OrderProducts
                        for op in order.orderproduct_set.all():
                            op.ordered = True
                            op.save()

                        captured += 1
                    else:
                        self.message_user(
                            request,
                            f"Capture for order {order.order_number} did not complete. "
                            f"Status: {capture.get('status')}",
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


admin.site.register(Payment)
admin.site.register(Order, OrderAdmin)
admin.site.register(OrderProduct, OrderProductAdmin)
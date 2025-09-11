from django.contrib import admin
from .models import Payment, Order, OrderProduct
from django import forms
from django.forms import Select

class OrderProductInline(admin.TabularInline):
    model = OrderProduct
    readonly_fields = ('user', 'product', 'quantity', 'product_price', 'ordered', 'order_payment_status')
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
                # Custom labels for clarity (e.g., "Completed (PAYID-...)")
                self.fields['payment'].choices = [
                    (p.pk, f"{p.status} ({p.payment_id})") for p in payments
                ]
                if instance.order and instance.order.payment:
                    correct_pk = instance.order.payment.pk
                    self.fields['payment'].initial = correct_pk
                print(f"Choices set to {len(self.fields['payment'].choices)} options, initial: {self.fields['payment'].initial}")
            else:
                self.fields['payment'].choices = []

class OrderAdmin(admin.ModelAdmin):

    list_display = ['order_number', 'full_name', 'phone', 'email', 'city', 'order_total', 'tax', 'status', 'is_ordered', 'created_at']
    list_filter = ['status', 'is_ordered']
    search_fields = ['order_number', 'first_name', 'last_name', 'phone', 'email']
    list_per_page = 20
    inlines = [OrderProductInline]


# ... your other code like OrderProductInline and OrderAdmin ...


class OrderProductAdmin(admin.ModelAdmin):
    list_display = ('product', 'order', 'quantity', 'product_price', 'ordered', 'get_order_payment_id')
    fields = ('order', 'user', 'product', 'variations', 'quantity', 'product_price', 'ordered', 'payment')
    readonly_fields = ('get_order_payment_id',)

    def get_order_payment_id(self, obj):
        if obj.order.payment:
            return obj.order.payment.payment_id
        return 'N/A'
    get_order_payment_id.short_description = 'Payment ID'

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if obj and 'payment' in form.base_fields:
            if obj.user:
                payments = Payment.objects.filter(user=obj.user)
                form.base_fields['payment'].choices = [
                    (p.pk, f"{p.status} ({p.payment_id})") for p in payments
                ]
                if obj.order and obj.order.payment:
                    form.base_fields['payment'].initial = obj.order.payment.pk
        return form

    def save_model(self, request, obj, form, change):
        if obj.order and obj.order.payment:
            obj.payment = obj.order.payment  # Auto-set the direct payment to the order's payment
        super().save_model(request, obj, form, change)  # Save as normal

admin.site.register(Payment)
admin.site.register(Order, OrderAdmin)
admin.site.register(OrderProduct, OrderProductAdmin)

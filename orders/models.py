from django.db import models
from accounts.models import Account
from store.models import Product, Variation


class Payment(models.Model):
    user = models.ForeignKey(Account, on_delete=models.CASCADE)
    payment_id = models.CharField(max_length=100)
    payment_method = models.CharField(max_length=100)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
   # amount_paid = models.CharField(max_length=100)  # this is the total amount paid
    status = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.payment_id


class Order(models.Model):
    STATUS = (
        ("NEW", "New"),
        ("ACCEPTED", "Accepted"),
        ("AUTHORIZED", "Authorized"),
        ("COMPLETED", "Completed"),
        ("CANCELLED", "Cancelled"),
    )

    user = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True)
    payment = models.ForeignKey(Payment, on_delete=models.SET_NULL, blank=True, null=True)
    order_number = models.CharField(max_length=20)

    # Contact + billing
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    phone = models.CharField(max_length=15)
    email = models.EmailField(max_length=50)
    address_line_1 = models.CharField(max_length=50)
    address_line_2 = models.CharField(max_length=50, blank=True)
    country = models.CharField(max_length=2, default='US')  # 2-letter code
    state = models.CharField(max_length=2)
    city = models.CharField(max_length=50)
    zip_code = models.CharField(max_length=10)
    order_note = models.CharField(max_length=100, blank=True)

    # Totals + status
    order_total = models.FloatField()
    tax = models.FloatField()
    status = models.CharField(max_length=10, choices=STATUS, default='New')
    is_ordered = models.BooleanField(default=False)
    ip = models.CharField(blank=True, max_length=20)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # shipping fields
    shipping_first_name = models.CharField(max_length=50, blank=True)
    shipping_last_name = models.CharField(max_length=50, blank=True)
    shipping_phone = models.CharField(max_length=15, blank=True)
    shipping_email = models.EmailField(max_length=50, blank=True)
    shipping_address_line_1 = models.CharField(max_length=50, blank=True)
    shipping_address_line_2 = models.CharField(max_length=50, blank=True)
    shipping_country = models.CharField(max_length=2, blank=True, default='US')
    shipping_state = models.CharField(max_length=2, blank=True)
    shipping_city = models.CharField(max_length=50, blank=True)
    shipping_zip_code = models.CharField(max_length=20, blank=True)

    # NEW: store PayPal authorization ID
    paypal_authorization_id = models.CharField(max_length=255, blank=True, null=True)

    def full_name(self):
        return f'{self.first_name} {self.last_name}'

    def full_address(self):
        return f'{self.address_line_1} {self.address_line_2}'

    def __str__(self):
        return f"Order {self.order_number} - {self.first_name} {self.last_name}"


class OrderProduct(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    payment = models.ForeignKey(Payment, on_delete=models.SET_NULL, blank=True, null=True)
    user = models.ForeignKey(Account, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    variations = models.ManyToManyField(Variation, blank=True)
    quantity = models.IntegerField()
    product_price = models.FloatField()
    ordered = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def sub_total(self):
        return self.product_price * self.quantity

    def __str__(self):
        return self.product.product_name
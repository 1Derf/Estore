from django.db import models
from accounts.models import Account
from store.models import Product, Variation
from decimal import Decimal



class Payment(models.Model):
    user = models.ForeignKey(Account, on_delete=models.CASCADE)
    payment_id = models.CharField(max_length=100)
    payment_method = models.CharField(max_length=100)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.payment_id

class Order(models.Model):
    STATUS = (
        ("AUTHORIZED", "Authorized"),
        ("PENDING", "Pending"),
        ("CAPTURED", "Captured"),
        ("REFUNDED", "Refunded"),
    )

    ORDER_STATUS = (
        ("PROCESSING", "Processing"),
        ("SHIPPED", "Shipped"),
        ("CANCELLED", "Cancelled"),
        ("RETURNED", "Returned"),
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
    order_total = models.DecimalField(max_digits=10, decimal_places=2)
    tax = models.DecimalField(max_digits=10, decimal_places=2)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                        help_text="Final shipping cost applied to this order")
    status = models.CharField(max_length=10,choices=STATUS,default="AUTHORIZED",verbose_name="Payment Status")
    tracking_number = models.CharField(max_length=100, blank=True, null=True,
                                       help_text="Carrier tracking number for shipment")
    order_status = models.CharField(max_length=15,choices=ORDER_STATUS,default="PROCESSING",)
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
    shipping_method = models.CharField(max_length=50, blank=True, null=True,
                                       help_text="Carrier or type (e.g., FedEx Home, Free Shipping)")
    supplier_name = models.CharField(max_length=255, blank=True, null=True)
    po_number = models.CharField(max_length=100, blank=True, null=True)
    supplier_order_date = models.DateField(blank=True, null=True)

    @property
    def subtotal(self) -> Decimal:
        """
        Return just the product subtotal (no tax, no shipping).
        """
        return self.order_total - self.tax - self.shipping_cost

    #  store PayPal authorization ID
    paypal_authorization_id = models.CharField(max_length=255, blank=True, null=True)
    paypal_order_id = models.CharField(max_length=255, blank=True, null=True)

    def full_name(self):
        return f'{self.first_name} {self.last_name}'

    def full_address(self):
        return f'{self.address_line_1} {self.address_line_2}'

    def get_shipping_address(self):
        """
        Return the shipping address as a dict ready for carrier APIs.
        Uses shipping_* fields if set, otherwise falls back to billing.
        """
        return {
            "name": f"{self.shipping_first_name or self.first_name} {self.shipping_last_name or self.last_name}",
            "street1": self.shipping_address_line_1 or self.address_line_1,
            "street2": self.shipping_address_line_2 or self.address_line_2,
            "city": self.shipping_city or self.city,
            "state": self.shipping_state or self.state,
            "zip": self.shipping_zip_code or self.zip_code,
            "country": self.shipping_country or self.country,
            "phone": self.shipping_phone or self.phone,
            "email": self.shipping_email or self.email,
        }

    def build_shipping_parcels(self):
        """
        Collect parcel data from related order items.
        Returns a list of dicts like:
        [
          {"length": 10, "width": 5, "height": 3, "weight": 8},
          ...
        ]
        Assumes each item ships as its own package (1 per quantity).
        """
        parcels = []
        for item in self.orderproduct_set.all():
            parcels.extend(item.get_shipping_parcels())
        return parcels

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

    def get_shipping_parcels(self):
        """
        Build shipping parcels for this ordered product.
        Returns a list of dicts like:
        [
          {"length": 10, "width": 5, "height": 3, "weight": 8},
          ...
        ]
        One parcel per quantity.
        """
        parcels = []
        for _ in range(self.quantity):
            parcels.append({
                "length": self.product.length_in or 1,
                "width": self.product.width_in or 1,
                "height": self.product.height_in or 1,
                "weight": (self.product.weight_lbs or 1) * 16,
            })
        return parcels

    def __str__(self):
        return self.product.product_name



class PayPalWebhookLog(models.Model):
    event_type = models.CharField(max_length=100)
    payload = models.JSONField()
    received_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.event_type} at {self.received_at}"

class SiteSettings(models.Model):
    free_shipping_enabled = models.BooleanField(default=True, help_text="Enable free shipping for qualifying orders.")
    free_shipping_threshold = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('99.00'), help_text="Minimum subtotal for free shipping.")

    class Meta:
        verbose_name_plural = "Site Settings"  # So it shows nicely in admin

    def __str__(self):
        return "Site Settings"

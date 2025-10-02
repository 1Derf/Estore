from django.db import models
from accounts.models import Account
from store.models import Product, Variation


# --------------------------
# Cart
# --------------------------
class Cart(models.Model):
    cart_id = models.CharField(max_length=250, blank=True)
    date_added = models.DateField(auto_now_add=True)

    def __str__(self):
        return self.cart_id


# --------------------------
# Cart Item
# --------------------------
class CartItem(models.Model):
    user = models.ForeignKey(Account, on_delete=models.CASCADE, null=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    variations = models.ManyToManyField(Variation, blank=True)
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, null=True)
    quantity = models.IntegerField()
    is_active = models.BooleanField(default=True)


    def sub_total(self):
        """
        Base price + modifiers from all selected variations * quantity
        """
        base_price = self.product.price
        extra = sum(v.price_modifier for v in self.variations.all())
        return (base_price + extra) * self.quantity

    def get_shipping_parcels(self):
        """
        Build shipping parcels for this cart item.
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
                "weight": (self.product.weight_lbs or 1) * 16,  # convert to ounces
            })
        return parcels

    def __unicode__(self):
        return self.product.product_name

    def __str__(self):
        return f"{self.product.product_name} (x{self.quantity})"
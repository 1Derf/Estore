from django.db import models
from django.db.models import Avg, Count
from django.urls import reverse
from accounts.models import Account

# -------------------------
# Brand
# -------------------------
class Brand(models.Model):
    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=200, unique=True)
    logo = models.ImageField(upload_to='photos/brands', blank=True, null=True)
    description = models.TextField(blank=True)
    website = models.URLField(blank=True, help_text="Link to the brand's official website")
    created_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)

    def get_url(self):
        return reverse('store:brand_detail', args=[self.slug])

    def __str__(self):
        return self.name


# -------------------------
# Product
# -------------------------
class Product(models.Model):
    product_name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=200, unique=True)
    description = models.TextField(max_length=1000, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    images = models.ImageField(upload_to='photos/products')
    stock = models.IntegerField()
    is_available = models.BooleanField(default=True)
    category = models.ForeignKey('category.Category', on_delete=models.CASCADE)
    brand = models.ForeignKey(Brand, on_delete=models.SET_NULL, null=True, blank=True)
    created_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)
    manufacturer_part_number = models.CharField(max_length=50, blank=True, null=True, unique=True, help_text="Manufacturer's part number (custom product ID)")
    gtin = models.CharField(max_length=14, blank=True, null=True, unique=True, help_text="Global Trade Item Number (13-14 digits)")
    upc_ean = models.CharField(max_length=13, blank=True, null=True, unique=True, help_text="UPC (12 digits) or EAN (13 digits)")
    has_variants = models.BooleanField(default=False, help_text="Enable if this product has variants (e.g., Gas Type).")
    warranty_text = models.TextField(blank=True, null=True, help_text="Warranty description text")
    warranty_file = models.FileField(upload_to='warranties/', blank=True, null=True, help_text="Upload warranty document (e.g., PDF)")
    weight_lbs = models.PositiveIntegerField(
        default=1,
        help_text="Weight of this product in whole pounds (auto-rounded up)."
    )
    length_in = models.PositiveIntegerField(
        default=7,
        help_text="Package length in inches (whole numbers only)."
    )
    width_in = models.PositiveIntegerField(
        default=6,
        help_text="Package width in inches (whole numbers only)."
    )
    height_in = models.PositiveIntegerField(
        default=6,
        help_text="Package height in inches (whole numbers only)."
    )

    is_featured = models.BooleanField(default=False, help_text="Check to feature this product on the home page.")

    def save(self, *args, **kwargs):
        """
        Ensure numeric fields are valid integers >= 1,
        and handle string values safely during imports.
        """
        numeric_fields = ["weight_lbs", "length_in", "width_in", "height_in"]

        for field in numeric_fields:
            value = getattr(self, field)
            try:
                # Convert strings like "5" or "7.2" to int
                value = int(float(value))
            except (TypeError, ValueError):
                value = 1  # default safe fallback

            # Enforce minimum and round up whole pounds/inches
            if value < 1:
                value = 1
            else:
                value = int(value + 0.9999)

            setattr(self, field, value)

        super().save(*args, **kwargs)

    def get_url(self):
        return reverse('store:product_detail', args=[self.category.slug, self.slug])

    def __str__(self):
        return self.product_name

    def averageReview(self):
        reviews = ReviewRating.objects.filter(product=self, status=True).aggregate(average=Avg('rating'))
        avg = 0
        if reviews['average'] is not None:
            avg = float(reviews['average'])
        return avg

    def countReview(self):
        reviews = ReviewRating.objects.filter(product=self, status=True).aggregate(count=Count('id'))
        count = 0
        if reviews['count'] is not None:
            count = int(reviews['count'])
        return count


# -------------------------
# Downloads
# -------------------------
class ProductDownload(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='downloads')
    title = models.CharField(max_length=100, blank=True, default="Download", help_text="Title for the file (e.g., 'Product Catalog')")
    file = models.FileField(upload_to='downloads/', help_text="Upload PDF or catalog file")

    def __str__(self):
        return f"{self.title} for {self.product.product_name}"


# -------------------------
# Variations
# -------------------------
class VariationCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class Variation(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    category = models.ForeignKey(VariationCategory, on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=100, null=True, blank=True)
    price_modifier = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    is_active = models.BooleanField(default=True)
    created_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.category} : {self.name}"


# -------------------------
# Reviews
# -------------------------
class ReviewRating(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    user = models.ForeignKey(Account, on_delete=models.CASCADE)
    subject = models.CharField(max_length=100, blank=True)
    review = models.TextField(max_length=500, blank=True)
    rating = models.FloatField()
    ip = models.CharField(max_length=20, blank=True)
    status = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.subject


# -------------------------
# Galleries
# -------------------------
class ProductGallery(models.Model):
    product = models.ForeignKey(Product, default=None, on_delete=models.CASCADE)
    image = models.ImageField(upload_to='store/products/', max_length=255)
    order = models.PositiveIntegerField(default=0, blank=True, null=False)

    def __str__(self):
        return self.product.product_name

    class Meta:
        verbose_name = 'product gallery'
        verbose_name_plural = 'product gallery'
        ordering = ['order']

    def save(self, *args, **kwargs):
        if not self.order:
            last_order = ProductGallery.objects.filter(product=self.product).aggregate(models.Max('order'))['order__max'] or 0
            self.order = last_order + 1
        super().save(*args, **kwargs)


# -------------------------
# Wishlist
# -------------------------
class Wishlist(models.Model):
    user = models.ForeignKey(Account, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    variations = models.ManyToManyField(Variation, blank=True)
    added_date = models.DateTimeField(auto_now_add=True)
    quantity = models.PositiveIntegerField(default=1)  # New field for quantity

    def __str__(self):
        variant_values = ", ".join([f"{v.category}: {v.name}" for v in self.variations.all()])
        variants = f" ({variant_values})" if variant_values else ""
        return f"{self.user.username} - {self.product.product_name}{variants} (Qty: {self.quantity})"

    class Meta:
        indexes = [
            models.Index(fields=['user', 'product']),
        ]
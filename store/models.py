from OpenSSL.rand import status
from django.db.models import CASCADE, Avg, Count
from django.urls import reverse
from django.db import models
from accounts.models import Account
from category.models import Category



# Create your models here.

class Product(models.Model):
    product_name   = models.CharField(max_length=200, unique=True)
    slug           = models.SlugField(max_length=200, unique=True)
    description    = models.TextField(max_length=1000, blank=True)
    price          = models.DecimalField(max_digits=10, decimal_places=2)
    images         = models.ImageField(upload_to='photos/products')
    stock          = models.IntegerField()
    is_available   = models.BooleanField(default=True)
    category       = models.ForeignKey(Category, on_delete=models.CASCADE)
    created_date   = models.DateTimeField(auto_now_add=True)
    modified_date  = models.DateTimeField(auto_now=True)
    manufacturer_part_number = models.CharField(max_length=50, blank=True, null=True, unique=True,
                                                help_text="Manufacturer's part number (custom product ID)")
    gtin = models.CharField(max_length=14, blank=True, null=True, unique=True,
                            help_text="Global Trade Item Number (13-14 digits)")
    upc_ean = models.CharField(max_length=13, blank=True, null=True, unique=True,
                               help_text="UPC (12 digits) or EAN (13 digits)")
    has_variants = models.BooleanField(default=False,
                                       help_text="Enable if this product has variants (e.g., size/color).")  # NEW: Toggle for variants

    def get_url(self):
        return reverse('product_detail', args=[self.category.slug, self.slug])

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


class VariationManager(models.Manager):
    def colors(self):
        return super(VariationManager, self).filter(variation_category='color', is_active=True)

    def sizes(self):
        return super(VariationManager, self).filter(variation_category='size', is_active=True)

variation_category_choice = (
    ('color', 'color'),
    ('size', 'size'),
)


class Variation(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    variation_category = models.CharField(max_length=100, choices=variation_category_choice)
    variation_value   = models.CharField(max_length=100)
    is_active         = models.BooleanField(default=True)
    created_date      = models.DateTimeField(auto_now=True)

    objects = VariationManager()

    def __str__(self):
        return self.variation_value


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


class ProductGallery(models.Model):
    product = models.ForeignKey(Product, default=None, on_delete=models.CASCADE)
    image = models.ImageField(upload_to='store/products/', max_length=255)
    order = models.PositiveIntegerField(default=0, blank=True, null=False)  # NEW: For sorting galleries

    def __str__(self):
        return self.product.product_name

    class Meta:
        verbose_name = 'product gallery'
        verbose_name_plural = 'product gallery'
        ordering = ['order']  # NEW: Auto-sort by order field

    def save(self, *args, **kwargs):
        if not self.order:  # NEW: Auto-set order if blank (increments based on existing galleries for this product)
            last_order = ProductGallery.objects.filter(product=self.product).aggregate(models.Max('order'))['order__max'] or 0
            self.order = last_order + 1
        super().save(*args, **kwargs)
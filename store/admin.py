from django.contrib import admin
from django.db import models
from django import forms
from .models import (
    Product, Variation, VariationCategory,
    ReviewRating, ProductGallery, ProductDownload, Brand
)
from import_export import resources, fields, widgets
from import_export.admin import ImportExportMixin
from django.utils.safestring import mark_safe
import admin_thumbnails
import os
from urllib.parse import urlparse
from django.conf import settings
from django.core.exceptions import ValidationError


def normalize_media_name(raw, default_folder=None):
    if not raw:
        return None
    s = str(raw).strip()
    if not s:
        return None

    parsed = urlparse(s)
    if parsed.scheme in ("http", "https"):
        s = parsed.path or ""

    media_url = getattr(settings, "MEDIA_URL", "/media/")
    if media_url and s.startswith(media_url):
        s = s[len(media_url):]

    media_root = getattr(settings, "MEDIA_ROOT", "")
    if media_root and os.path.isabs(s) and s.startswith(media_root):
        s = os.path.relpath(s, media_root)

    if default_folder and "/" not in s.strip("/"):
        s = f"{default_folder.rstrip('/')}/{os.path.basename(s)}"

    return s.lstrip("/")


@admin_thumbnails.thumbnail('image')
class ProductGalleryInline(admin.TabularInline):
    model = ProductGallery
    extra = 1


class ProductDownloadInline(admin.TabularInline):
    model = ProductDownload
    extra = 1

class ProductResource(resources.ModelResource):
    weight_lbs = fields.Field(attribute="weight_lbs", column_name="Weight (lb)")
    length_in  = fields.Field(attribute="length_in", column_name="Length (in)")
    width_in   = fields.Field(attribute="width_in",  column_name="Width (in)")
    height_in  = fields.Field(attribute="height_in", column_name="Height (in)")

    # Import‑export friendly pseudo‑field
    gallery_images = fields.Field(
        column_name="Gallery Images",
        attribute="gallery_images",
        widget=widgets.CharWidget(),
    )

    # --- Export ---
    # Keep this field (as you already have it)
    # gallery_images = fields.Field(column_name="Gallery Images", attribute="gallery_images", widget=widgets.CharWidget())

    # 1) Export stays as storage-relative names
    def dehydrate_gallery_images(self, product):
        qs = ProductGallery.objects.filter(product=product).order_by("order")
        return ", ".join(g.image.name for g in qs if getattr(g, "image", None))

    # 2) Parse and normalize the gallery column early and attach to the row
    def before_import_row(self, row, **kwargs):
        # Merge your existing numeric validations here if you have them
        # ... your stock/price/dimensions checks ...

        # Read either header variant
        raw = row.get("Gallery Images")
        if raw is None:
            raw = row.get("gallery_images")

        # Attach a normalized list for later hooks to use
        if raw is None:
            row["_parsed_gallery_images"] = None  # column absent -> do nothing later
        else:
            s = str(raw).strip()
            if not s:
                row["_parsed_gallery_images"] = []  # present but blank -> clear gallery
            else:
                parts = [p.strip() for p in s.split(",") if p.strip()]
                paths = [normalize_media_name(p, default_folder="store/products") for p in parts]
                row["_parsed_gallery_images"] = [p for p in paths if p]

    # 3) After the instance is saved, rebuild ProductGallery
    def after_save_instance(self, instance, row, **kwargs):
        paths = row.get("_parsed_gallery_images", None)

        if paths is None:
            # Column was not provided -> leave existing gallery untouched
            return

        # Replace gallery (empty list means clear)
        ProductGallery.objects.filter(product=instance).delete()

        for order, path in enumerate(paths, start=1):
            pg = ProductGallery(product=instance, order=order)
            pg.image.name = path  # set ImageField name directly
            pg.save()
    class Meta:
        model = Product
        fields = (
            "id",
            "product_name",
            "price",
            "description",
            "stock",
            "category__category_name",
            "slug",
            "is_available",
            "modified_date",
            "manufacturer_part_number",
            "gtin",
            "upc_ean",
            "images",          # main image
            "gallery_images",  # additional gallery
            "weight_lbs",
            "length_in",
            "width_in",
            "height_in",
        )
        export_order = fields
        import_id_fields = ("id",)


class ProductGalleryResource(resources.ModelResource):
    # product FK as product name for readability
    product_name = fields.Field(
        column_name="Product Name",
        attribute="product",
        widget=widgets.ForeignKeyWidget(Product, "product_name"),
    )

    image = fields.Field(
        column_name="Gallery Image Path",
        attribute="image",
        widget=widgets.CharWidget(),
    )

    order = fields.Field(attribute="order", column_name="Order")

    class Meta:
        model = ProductGallery
        fields = ("id", "product_name", "image", "order")
        export_order = ("id", "product_name", "image", "order")


class VariationInlineForm(forms.ModelForm):
    class Meta:
        model = Variation
        fields = ("category", "name", "price_modifier", "is_active")

    def clean(self):
        cleaned = super().clean()
        product = self.instance.product or getattr(self, "parent_instance", None)
        category = cleaned.get("category")
        name = cleaned.get("name")
        is_active = cleaned.get("is_active")

        if product and category and name and is_active:
            qs = Variation.objects.filter(
                product=product,
                category=category,
                name=name,
                is_active=True,
            )
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError("There is already an active variation with this name in this category for this product.")
        return cleaned


class VariationInline(admin.TabularInline):
    model = Variation
    form = VariationInlineForm
    fields = ("category", "name", "price_modifier", "is_active")
    extra = 0
    autocomplete_fields = ["category"]
    show_change_link = False


class ProductAdmin(ImportExportMixin, admin.ModelAdmin):
    resource_class = ProductResource
    list_display = (
        'product_name', 'price', 'stock', 'category', 'is_available',
        'manufacturer_part_number', 'gtin', 'upc_ean', 'weight_lbs', 'length_in', 'width_in', 'height_in', 'is_featured',
    )
    list_editable = (
        'price', 'stock', 'is_available', 'weight_lbs', 'length_in', 'width_in', 'height_in','is_featured',

    )
    prepopulated_fields = {'slug': ('product_name',)}
    inlines = [VariationInline, ProductGalleryInline, ProductDownloadInline]
    readonly_fields = ('modified_date', 'main_image_preview')

    def main_image_preview(self, obj):
        if obj.images:
            return mark_safe(
                f'<img src="{obj.images.url}" width="100" height="100" '
                f'style="border: 1px solid #ddd; padding: 5px;" />'
            )
        return "No Main Image"
    main_image_preview.short_description = 'Main Image Preview'

    fieldsets = (
        (None, {
            'fields': (
                'product_name', 'slug', 'category', 'brand', 'price', 'description',
                'images', 'main_image_preview', 'stock', 'is_available', 'has_variants','is_featured',
            )
        }),
        ('Product Codes', {
            'fields': ('manufacturer_part_number', 'gtin', 'upc_ean'),
        }),
        ('Warranty', {
            'fields': ('warranty_text', 'warranty_file'),
        }),
        ('Shipping', {
            'fields': ('weight_lbs', 'length_in', 'width_in', 'height_in'),
        }),

    )
    formfield_overrides = {
        models.DecimalField: {'widget': forms.NumberInput(attrs={'style': 'width: 120px;'})},
        models.IntegerField: {'widget': forms.NumberInput(attrs={'style': 'width: 90px;'})},
        models.FloatField: {'widget': forms.NumberInput(attrs={'style': 'width: 100px;'})},
        models.CharField: {'widget': forms.TextInput(attrs={'style': 'width: 200px;'})},
    }


class VariationCategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)


class VariationAdmin(admin.ModelAdmin):
    list_display = ('product', 'category', 'name', 'price_modifier', 'is_active', 'created_date')
    list_editable = ('price_modifier', 'is_active')
    list_filter = ('product', 'category', 'is_active')
    search_fields = ('product__product_name', 'name')


class BrandAdmin(admin.ModelAdmin):
    list_display = ('name', 'website', 'logo_preview', 'created_date')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)
    list_filter = ('created_date',)
    readonly_fields = ('logo_preview',)

    def logo_preview(self, obj):
        if obj.logo:
            return mark_safe(
                f'<img src="{obj.logo.url}" width="100" height="100" '
                f'style="border: 1px solid #ddd; padding: 5px;" />'
            )
        return "No Logo"
    logo_preview.short_description = 'Logo Preview'


# Register models
admin.site.register(Product, ProductAdmin)
admin.site.register(VariationCategory, VariationCategoryAdmin)
admin.site.register(Variation, VariationAdmin)
admin.site.register(ReviewRating)
admin.site.register(ProductGallery)
admin.site.register(ProductDownload)
admin.site.register(Brand, BrandAdmin)
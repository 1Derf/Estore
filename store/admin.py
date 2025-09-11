from django.contrib import admin
from .models import Product, Variation, ReviewRating, ProductGallery, ProductDownload, Brand  # UPDATED: Imported Brand
from import_export import resources  # For CSV resources
from import_export.admin import ImportExportMixin  # For admin integration
from django.utils.safestring import mark_safe  # For safe HTML in previews
import admin_thumbnails

@admin_thumbnails.thumbnail('image')  # Keeps gallery thumbnails

class ProductGalleryInline(admin.TabularInline):
    model = ProductGallery
    extra = 1  # Your original
    # TEMPORARILY REMOVED: fields and ordering to test thumbnails (add back below if it works)

class ProductDownloadInline(admin.TabularInline):  #  Inline for multiple downloads
    model = ProductDownload
    extra = 1  # Start with 1 empty form

class ProductResource(resources.ModelResource):
    class Meta:
        model = Product
        fields = ('id', 'product_name', 'price', 'description', 'stock', 'category__category_name', 'slug', 'is_available', 'modified_date',
                  'manufacturer_part_number', 'gtin', 'upc_ean', 'images')
        export_order = ('id', 'product_name', 'price', 'description', 'stock', 'category__category_name', 'slug', 'is_available', 'modified_date',
                        'manufacturer_part_number', 'gtin', 'upc_ean', 'images')
        import_id_fields = ('id',)

    def before_import_row(self, row, **kwargs):
        if 'stock' in row and int(row['stock']) < 0:
            raise ValueError("Stock must be non-negative")
        if 'price' in row and float(row['price']) < 0:
            raise ValueError("Price must be positive")


class ProductAdmin(ImportExportMixin, admin.ModelAdmin):
    resource_class = ProductResource
    list_display = ('product_name', 'price', 'stock', 'category', 'modified_date', 'is_available',
                    'manufacturer_part_number', 'gtin', 'upc_ean')
    prepopulated_fields = {'slug': ('product_name',)}
    inlines = [ProductGalleryInline, ProductDownloadInline]  # ProductDownloadInline
    readonly_fields = ('modified_date', 'main_image_preview')

    def main_image_preview(self, obj):  # Keeps main thumbnail working
        if obj.images:
            return mark_safe(f'<img src="{obj.images.url}" width="100" height="100" style="border: 1px solid #ddd; padding: 5px;" />')
        return "No Main Image"
    main_image_preview.short_description = 'Main Image Preview'

    fieldsets = (
        (None, {
            'fields': ('product_name', 'slug', 'category', 'brand', 'price', 'description', 'images', 'main_image_preview', 'stock', 'is_available', 'has_variants')  # UPDATED: Added 'brand'
        }),
        ('Product Codes', {
            'fields': ('manufacturer_part_number', 'gtin', 'upc_ean'),
        }),
        ('Warranty', {  # NEW: Added this section
            'fields': ('warranty_text', 'warranty_file'),
        }),
    )

class VariationAdmin(admin.ModelAdmin):
    list_display = ('product', 'variation_category', 'variation_value', 'is_active')
    list_editable = ('is_active',)
    list_filter = ('product', 'variation_category', 'variation_value')

#  Admin for Brand model
class BrandAdmin(admin.ModelAdmin):
    list_display = ('name', 'website', 'logo_preview', 'created_date')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)
    list_filter = ('created_date',)
    readonly_fields = ('logo_preview',)

    def logo_preview(self, obj):
        if obj.logo:
            return mark_safe(f'<img src="{obj.logo.url}" width="100" height="100" style="border: 1px solid #ddd; padding: 5px;" />')
        return "No Logo"
    logo_preview.short_description = 'Logo Preview'

admin.site.register(Product, ProductAdmin)
admin.site.register(Variation, VariationAdmin)
admin.site.register(ReviewRating)
admin.site.register(ProductGallery)
admin.site.register(ProductDownload)  #  Registered for direct access (optional)
admin.site.register(Brand, BrandAdmin)  #  Registered Brand with custom admin
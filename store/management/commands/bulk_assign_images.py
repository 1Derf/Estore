from django.core.management.base import BaseCommand
from django.core.files import File
from store.models import Product, ProductGallery  # Adjust path if needed
import os

class Command(BaseCommand):
    help = 'Bulk assign images to products by filename (e.g., "slug.jpg"), skipping duplicates'

    def add_arguments(self, parser):
        parser.add_argument('media_paths', nargs='+', type=str)  # e.g., 'media/photos/products/' 'media/store/products/'

    def handle(self, *args, **options):
        for media_path in options['media_paths']:
            for filename in os.listdir(media_path):
                if filename.lower().endswith(('.jpg', '.png', '.jpeg')):  # Supported formats
                    base_name = filename.rsplit('.', 1)[0].lower()  # Get name without extension (for matching)
                    try:
                        product = Product.objects.filter(slug__iexact=base_name).first() or \
                                  Product.objects.filter(product_name__iexact=base_name).first()
                        if not product:
                            raise Product.DoesNotExist

                        # NEW: Skip if duplicate (check by filename in images or gallery)
                        if (product.images and filename in str(product.images)) or \
                           ProductGallery.objects.filter(product=product, image__icontains=filename).exists():
                            self.stdout.write(self.style.WARNING(f'Skipped duplicate {filename} for {product.product_name}'))
                            continue

                        image_path = os.path.join(media_path, filename)
                        with open(image_path, 'rb') as f:
                            if not product.images:  # Assign to main if empty
                                product.images.save(filename, File(f), save=True)
                                self.stdout.write(self.style.SUCCESS(f'Assigned main image {filename} to {product.product_name}'))
                            else:  # Add to gallery
                                gallery = ProductGallery(product=product)
                                gallery.image.save(filename, File(f), save=True)
                                self.stdout.write(self.style.SUCCESS(f'Assigned gallery image {filename} to {product.product_name}'))
                    except Product.DoesNotExist:
                        self.stdout.write(self.style.WARNING(f'Skipped {filename} (no matching product)'))
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'Error processing {filename}: {str(e)}'))
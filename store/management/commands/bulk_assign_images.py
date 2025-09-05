from django.core.management.base import BaseCommand
from django.core.files import File
from store.models import Product, ProductGallery  # Adjust path if needed
import os
import re
import shutil  # NEW: For moving files

class Command(BaseCommand):
    help = 'Bulk assign images to products by filename (e.g., "slug.jpg" or "slug4.jpg"), skipping duplicates and optionally moving processed files'

    def add_arguments(self, parser):
        parser.add_argument('media_paths', nargs='+', type=str)  # e.g., 'media/photos/products/' 'media/store/products/'
        parser.add_argument('--move-processed', type=str, default='processed',  # Folder name to move to (relative to media_path)
                            help='Move processed files to this subfolder (set to "" to disable)')
        parser.add_argument('--no-move', action='store_true', help='Disable moving files (overrides --move-processed)')

    def handle(self, *args, **options):
        move_folder = options['move_processed'] if not options['no_move'] else None
        for media_path in options['media_paths']:
            # Create 'processed' subfolder if enabled and doesn't exist
            if move_folder:
                processed_path = os.path.join(media_path, move_folder)
                os.makedirs(processed_path, exist_ok=True)

            for filename in os.listdir(media_path):
                if filename.lower().endswith(('.jpg', '.png', '.jpeg')):  # Supported formats
                    base_name = filename.rsplit('.', 1)[0].lower()  # Get name without extension

                    # Strip trailing numbers (with optional dash, e.g., "slug-4" -> "slug"; "slug4" -> "slug")
                    match = re.match(r'^(.*?)(-\d+|\d*)$', base_name)
                    if match:
                        base_name = match.group(1).strip('-')

                    try:
                        product = Product.objects.filter(slug__iexact=base_name).first() or \
                                  Product.objects.filter(product_name__iexact=base_name).first()
                        if not product:
                            raise Product.DoesNotExist

                        # IMPROVED: Better duplicate check - Compare basenames exactly (case-insensitive)
                        existing_filenames = []
                        if product.images:
                            existing_filenames.append(os.path.basename(product.images.name).lower())
                        existing_filenames.extend(
                            os.path.basename(g.image.name).lower() for g in ProductGallery.objects.filter(product=product)
                        )
                        if filename.lower() in existing_filenames:
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

                        # NEW: Move file to processed folder if enabled
                        if move_folder:
                            shutil.move(image_path, os.path.join(processed_path, filename))
                            self.stdout.write(self.style.NOTICE(f'Moved {filename} to {processed_path}'))

                    except Product.DoesNotExist:
                        self.stdout.write(self.style.WARNING(f'Skipped {filename} (no matching product)'))
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'Error processing {filename}: {str(e)}'))
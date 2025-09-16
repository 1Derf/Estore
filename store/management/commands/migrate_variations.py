from django.core.management.base import BaseCommand
from django.db import models
from store.models import VariationCategory, Variation, Product

# Old model definition (reads old columns in DB)
class OldVariation(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    variation_category = models.CharField(max_length=100)
    variation_value = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    created_date = models.DateTimeField()

    class Meta:
        db_table = "store_variation"   # same table used before
        managed = False                # don’t let Django manage schema


class Command(BaseCommand):
    help = "Migrate old Variation (variation_category / variation_value) into new VariationCategory + Variation system"

    def handle(self, *args, **options):
        # Step 1: Create categories if not exist
        categories_map = {}
        category_names = {
            'gas_type': 'Gas Type',
            'color': 'Color',
            'size': 'Size',
        }

        for key, display in category_names.items():
            cat, created = VariationCategory.objects.get_or_create(name=display)
            categories_map[key] = cat
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created category: {display}"))

        # Step 2: Read old rows
        old_variations = OldVariation.objects.all()
        migrated_count = 0

        for old in old_variations:
            try:
                category_obj = categories_map.get(old.variation_category)
                if not category_obj:
                    self.stdout.write(self.style.WARNING(f"Skipping variation {old.id}: unknown category {old.variation_category}"))
                    continue

                # Create new Variation
                Variation.objects.create(
                    product=old.product,
                    category=category_obj,
                    name=old.variation_value,
                    price_modifier=0.00,
                    is_active=old.is_active,
                )
                migrated_count += 1

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error migrating variation {old.id}: {e}"))

        self.stdout.write(self.style.SUCCESS(f"✅ Migration complete: {migrated_count} variations migrated."))
from easypost import EasyPostClient
from django.conf import settings
from decimal import Decimal
from orders.models import SiteSettings

def get_client():
    """Return an EasyPost client using the Django settings API key."""
    api_key = settings.EASYPOST_API_KEY
    if not api_key:
        raise RuntimeError("Missing EASYPOST_API_KEY in settings or environment.")
    return EasyPostClient(api_key)


def create_shipment_from_order(order):
    """
    Build an EasyPost Shipment from a Django Order.
    Returns an EasyPost Shipment (with rates).
    """
    client = get_client()

    to_address = order.get_shipping_address()
    from_address = {
        "company": "My Store",
        "street1": "123 Warehouse Rd",
        "city": "Phoenix",
        "state": "AZ",
        "zip": "85001",
        "country": "US",
        "phone": "555-555-5555",
        "email": "shipper@example.com",
    }

    parcels = order.build_shipping_parcels()
    if not parcels:
        raise RuntimeError("No parcels could be built for this order.")

    shipment = client.shipment.create(
        to_address=to_address,
        from_address=from_address,
        parcel=parcels[0],
    )

    return shipment

def create_shipment_from_cart(cart_items, billing_data):
    client = get_client()

    # Build to_address from billing_data (your session dict)
    to_address = {
        "name": f"{billing_data.get('shipping_first_name', '')} {billing_data.get('shipping_last_name', '')}",
        "street1": billing_data.get('shipping_address_line_1', ''),
        "street2": billing_data.get('shipping_address_line_2', ''),
        "city": billing_data.get('shipping_city', ''),
        "state": billing_data.get('shipping_state', ''),
        "zip": billing_data.get('shipping_zip_code', ''),
        "country": billing_data.get('shipping_country', 'US'),
        "phone": billing_data.get('shipping_phone', ''),
        "email": billing_data.get('shipping_email', ''),
    }

    # Hardcoded from_address (your original)
    from_address = {
        "company": "My Store",
        "street1": "123 Warehouse Rd",
        "city": "Phoenix",
        "state": "AZ",
        "zip": "85001",
        "country": "US",
        "phone": "555-555-5555",
        "email": "shipper@example.com",
    }

    # Aggregate into one parcel: sum weights, max dims + padding
    total_weight_oz = 0.0
    max_length = 0.0
    max_width = 0.0
    max_height = 0.0

    for item in cart_items:
        item_length = item.product.length_in or 1.0
        item_width = item.product.width_in or 1.0
        item_height = item.product.height_in or 1.0
        item_weight_lbs = item.product.weight_lbs or 1.0

        total_weight_oz += item.quantity * (item_weight_lbs * 16)

        max_length = max(max_length, item_length)
        max_width = max(max_width, item_width)
        max_height = max(max_height, item_height)

    if total_weight_oz == 0:
        raise RuntimeError("No valid weight for cart items.")

    parcel = {
        "length": max_length + 2,
        "width": max_width + 2,
        "height": max_height + 2,
        "weight": total_weight_oz,
    }

    # Calculate subtotal for free shipping check
    subtotal = Decimal('0.00')
    for item in cart_items:
        # Use item.product.price (assuming it's DecimalField; if FloatField, cast Decimal(str(item.product.price)))
        subtotal += Decimal(str(item.product.price)) * Decimal(str(item.quantity))

    # Create shipment
    shipment = client.shipment.create(
        to_address=to_address,
        from_address=from_address,
        parcel=parcel,
    )
    # Free shipping logic
    settings = SiteSettings.objects.first()
    free_shipping_enabled = settings.free_shipping_enabled if settings else False
    free_shipping_threshold = settings.free_shipping_threshold if settings else Decimal('99.00')



    return shipment

def retrieve_shipment(shipment_id: str):
    """Retrieve an existing shipment by ID using EasyPostClient."""
    client = get_client()
    return client.shipment.retrieve(shipment_id)
from easypost import EasyPostClient
from django.conf import settings


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

def create_shipment_from_cart(cart_items, post_data):
    """
    Build an EasyPost Shipment from cart items and POST data.
    Assumes one combined parcel for the whole cart.
    Returns an EasyPost Shipment (with rates).
    """
    client = get_client()

    # Build to_address from POST (shipping fields)
    to_address = {
        "name": f"{post_data.get('shipping_first_name', '')} {post_data.get('shipping_last_name', '')}",
        "street1": post_data.get('shipping_address_line_1', ''),
        "street2": post_data.get('shipping_address_line_2', ''),
        "city": post_data.get('shipping_city', ''),
        "state": post_data.get('shipping_state', ''),
        "zip": post_data.get('shipping_zip_code', ''),
        "country": post_data.get('shipping_country', 'US'),
        "phone": post_data.get('shipping_phone', ''),
        "email": post_data.get('shipping_email', ''),
    }

    # Hardcoded from_address (same as in create_shipment_from_order)
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
        # Use product's dims/weight (from your models)
        item_length = item.product.length_in or 1.0
        item_width = item.product.width_in or 1.0
        item_height = item.product.height_in or 1.0
        item_weight_lbs = item.product.weight_lbs or 1.0

        # Per quantity
        total_weight_oz += item.quantity * (item_weight_lbs * 16)  # lbs to oz

        # Take max dims across all items (not per qty, as they pack together)
        max_length = max(max_length, item_length)
        max_width = max(max_width, item_width)
        max_height = max(max_height, item_height)

    if total_weight_oz == 0:
        raise RuntimeError("No valid weight for cart items.")

    parcel = {
        "length": max_length + 2,  # Padding for packing
        "width": max_width + 2,
        "height": max_height + 2,
        "weight": total_weight_oz,
    }

    # Create shipment (gets rates automatically)
    shipment = client.shipment.create(
        to_address=to_address,
        from_address=from_address,
        parcel=parcel,
    )

    return shipment
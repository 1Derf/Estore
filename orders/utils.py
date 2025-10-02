from decimal import Decimal
from orders.shipping.easypost_client import get_client


def calculate_shipping(subtotal: Decimal, cart_items=None, to_address=None):
    """
    Calculate shipping using EasyPost.
    Returns (shipping_method, shipping_cost).
    Free if subtotal >= 99, else cheapest EasyPost rate.
    """

    if subtotal >= Decimal("99.00"):
        return "Free Shipping", Decimal("0.00")

    if not cart_items:
        return "Standard Shipping", Decimal("14.95")

    # Build all parcels from cart
    parcels = []
    for item in cart_items:
        parcels.extend(item.get_shipping_parcels())

    # ✅ Use the real customer address passed in
    if not to_address:
        return "Standard Shipping", Decimal("14.95")

    from_address = {
        "company": "AZ Supply LLC",
        "street1": "5811 W Navajo Dr",
        "city": "Glendale",
        "state": "AZ",
        "zip": "85302",
        "country": "US",
        "phone": "602-978-5555",
        "email": "admin@beefeatergrillparts.com",
    }

    try:
        client = get_client()

        print("📦 Parcels:", parcels)
        print("➡️ To Address:", to_address)
        print("➡️ From Address:", from_address)

        # ✅ For multiple parcels, create a shipment with a "parcel" for each
        # EasyPost API: must be separate 'Shipment' per parcel, then pick cheapest overall
        cheapest_rate = None
        chosen_service = None

        for parcel in parcels:
            shipment = client.shipment.create(
                to_address=to_address,
                from_address=from_address,
                parcel=parcel,
            )
            if shipment and shipment.rates:
                rate = min(shipment.rates, key=lambda r: Decimal(r.rate))
                if cheapest_rate is None or Decimal(rate.rate) < cheapest_rate:
                    cheapest_rate = Decimal(rate.rate)
                    chosen_service = f"{rate.carrier} {rate.service}"

        if cheapest_rate is not None:
            return chosen_service, cheapest_rate
        else:
            return "Standard Shipping", Decimal("14.95")

    except Exception as e:
        print("EasyPost error:", e)
        return "Standard Shipping", Decimal("14.95")
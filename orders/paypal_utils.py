import requests
from django.conf import settings

# Config
CLIENT_ID = settings.PAYPAL_CLIENT_ID
CLIENT_SECRET = settings.PAYPAL_CLIENT_SECRET
BASE_URL = settings.PAYPAL_BASE_URL  # e.g. "https://api-m.sandbox.paypal.com"


def _get_access_token():
    """Retrieve OAuth2 access token from PayPal"""
    url = f"{BASE_URL}/v1/oauth2/token"
    resp = requests.post(
        url,
        headers={
            "Accept": "application/json",
            "Accept-Language": "en_US",
        },
        data={"grant_type": "client_credentials"},
        auth=(CLIENT_ID, CLIENT_SECRET),
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def create_paypal_order(order, amount, request):
    """Create a PayPal order with intent=AUTHORIZE"""
    access_token = _get_access_token()
    url = f"{BASE_URL}/v2/checkout/orders"

    payload = {
        "intent": "AUTHORIZE",
        "purchase_units": [
            {
                "reference_id": str(order.order_number),
                "amount": {
                    "currency_code": "USD",
                    "value": str(amount),
                },
                "shipping": {
                    "address": {
                        "address_line_1": order.shipping_address_line_1 or order.address_line_1,
                        "address_line_2": order.shipping_address_line_2 or order.address_line_2 or "",
                        "admin_area_2": order.shipping_city or order.city,
                        "admin_area_1": order.shipping_state or order.state,
                        "postal_code": order.shipping_zip_code or order.zip_code,
                        "country_code": (order.shipping_country or order.country)[:2].upper(),
                    }
                },
            }
        ],
        "application_context": {
            "return_url": request.build_absolute_uri("/orders/paypal-return/"),
            "cancel_url": request.build_absolute_uri("/orders/paypal-cancel/"),
            "shipping_preference": "SET_PROVIDED_ADDRESS",
        },
    }

    r = requests.post(
        url,
        json=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
        },
    )
    r.raise_for_status()
    return r.json()


def get_paypal_order(order_id):
    """Retrieve PayPal order details"""
    access_token = _get_access_token()
    url = f"{BASE_URL}/v2/checkout/orders/{order_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    return r.json()


def authorize_paypal_order(order_id):
    """Explicitly authorize an approved order"""
    access_token = _get_access_token()
    url = f"{BASE_URL}/v2/checkout/orders/{order_id}/authorize"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    # No body required
    r = requests.post(url, headers=headers)
    r.raise_for_status()
    return r.json()


def capture_paypal_payment(authorization_id, amount):
    """Capture a previously authorized payment"""
    access_token = _get_access_token()
    url = f"{BASE_URL}/v2/payments/authorizations/{authorization_id}/capture"
    payload = {
        "amount": {"currency_code": "USD", "value": str(amount)},
        "final_capture": True,
    }
    r = requests.post(
        url,
        json=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
        },
    )
    r.raise_for_status()
    return r.json()
from paypalrestsdk import Payment
from django.conf import settings  # To access settings like return/cancel URLs
import paypalrestsdk
from django.urls import reverse  # NEW: For dynamic URLs

def configure_paypal():
    paypalrestsdk.configure({
        "mode": "sandbox",  # or "live"
        "client_id": "AUZRzHs2tulbf2ZOHph-zEYVRQUthud4_Zib0o37H11a4cp0kjk-7154VW4mg327I1_20XIDqJiuMuDs",  # Replace with actual (redacted for safety)
        "client_secret": "EEE9gqD2GkRi0cjKDQ-f9g9RsCNuGOdcXoH-y8xZoqOZ8S3M1eSITQzHgaawUJ2_yzQO5Tncw1uNmscR"  # Replace with actual (redacted for safety)
    })

def create_paypal_payment(order, amount, request):
    configure_paypal()  # NEW: Call configuration here to ensure it's set before API calls

    # UPDATED: Use order object to get billing/shipping details
    billing_address = {
        "line1": order.address_line_1,
        "line2": order.address_line_2 or "",
        "city": order.city,
        "state": order.state,
        "postal_code": order.zip_code,
        "country_code": order.country[:2].upper()  # e.g., "US" (assumes country is full name; adjust if needed)
    }

    # Use shipping if populated; else fallback to billing
    shipping_address = {
        "recipient_name": f"{order.shipping_first_name} {order.shipping_last_name}" if order.shipping_first_name else order.full_name(),
        "line1": order.shipping_address_line_1 or order.address_line_1,
        "line2": order.shipping_address_line_2 or order.address_line_2 or "",
        "city": order.shipping_city or order.city,
        "state": order.shipping_state or order.state,
        "postal_code": order.shipping_zip_code or order.zip_code,
        "country_code": order.shipping_country[:2].upper() or order.country[:2].upper()
    }

    payment = paypalrestsdk.Payment({
        "intent": "sale",
        "payer": {
            "payment_method": "paypal",
            #  Add billing (payer) details for AVS and pre-fill
            "payer_info": {
                "email": order.email,
                "first_name": order.first_name,
                "last_name": order.last_name,
                "billing_address": billing_address,
               # "phone": order.phone,
            }
        },
        "redirect_urls": {
            "return_url": request.build_absolute_uri(reverse('paypal_return')),  # UPDATED: Dynamic URL using reverse
            "cancel_url": request.build_absolute_uri(reverse('paypal_cancel'))   # UPDATED: Dynamic URL using reverse
        },
        "transactions": [{
            "amount": {
                "total": str(amount),
                "currency": "USD"
            },
            "description": f"Payment for Order {order.order_number}",
            #  Add shipping address for pre-fill and verification
            "shipping_address": shipping_address
        }]
    })

    if payment.create():
        return payment  # Returns the payment object with links
    else:
        raise Exception(payment.error)  # Handle creation errors


def execute_paypal_payment(payment_id, payer_id):
    payment = paypalrestsdk.Payment.find(payment_id)
    if payment.execute({"payer_id": payer_id}):
        return payment  # Returns the executed payment object
    else:
        raise Exception(payment.error)  # Handle execution errors
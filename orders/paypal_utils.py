from paypalrestsdk import Payment
from django.conf import settings  # To access settings like return/cancel URLs
import paypalrestsdk


def configure_paypal():
    paypalrestsdk.configure({
        "mode": "sandbox",  # or "live"
        "client_id": "AUZRzHs2tulbf2ZOHph-zEYVRQUthud4_Zib0o37H11a4cp0kjk-7154VW4mg327I1_20XIDqJiuMuDs",  # Replace with actual
        "client_secret": "EEE9gqD2GkRi0cjKDQ-f9g9RsCNuGOdcXoH-y8xZoqOZ8S3M1eSITQzHgaawUJ2_yzQO5Tncw1uNmscR"  # Replace with actual
    })

def create_paypal_payment(order_id, total_amount, currency='USD'):
    configure_paypal()  # Ensure config is loaded

    payment = Payment({
        "intent": "sale",
        "payer": {
            "payment_method": "paypal"
        },
        "redirect_urls": {
            "return_url": settings.PAYPAL_RETURN_URL,
            "cancel_url": settings.PAYPAL_CANCEL_URL
        },
        "transactions": [{
            "item_list": {
                "items": [{
                    "name": "Order " + str(order_id),  # Customize as needed
                    "sku": "item",
                    "price": str(total_amount),
                    "currency": currency,
                    "quantity": 1
                }]
            },
            "amount": {
                "total": str(total_amount),
                "currency": currency
            },
            "description": "Payment for Order " + str(order_id)
        }]
    })

    if payment.create():
        return payment
    else:
        raise Exception(payment.error)
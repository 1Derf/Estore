from django.shortcuts import render, redirect
from store.models import Product
from django.http import HttpResponse
from orders.paypal_utils import configure_paypal, create_paypal_payment  # Adjust import path if needed
import paypalrestsdk



def home (request):
    products = Product.objects.all().filter(is_available=True)

    context = {
        'products': products,
    }
    return render(request, 'home.html', context)

def store(request):
    return render(request, 'store.html')


def test_paypal(request):
    configure_paypal()
    try:
        payment_methods = paypalrestsdk.BillingPlan.all()  # This is a harmless API call
        return HttpResponse("PayPal connection successful! Response: " + str(payment_methods))
    except Exception as e:
        return HttpResponse("PayPal connection failed: " + str(e))


def paypal_payment(request):
    # For testing: Hardcode an order (replace with real logic later)
    order_id = 123  # e.g., Order.objects.latest('id').id
    total_amount = 10.00  # e.g., order.total_price

    try:
        payment = create_paypal_payment(order_id, total_amount)

        # Find the approval URL from PayPal's response
        for link in payment.links:
            if link.rel == "approval_url":
                return redirect(link.href)

        return HttpResponse("Error: No approval URL found.")
    except Exception as e:
        return HttpResponse("Payment creation failed: " + str(e))
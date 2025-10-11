from datetime import date

from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, HttpResponseBadRequest
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from .forms import OrderForm
from carts.models import Cart, CartItem
from .models import Order, OrderProduct, Payment, PayPalWebhookLog
import json, logging
from decimal import Decimal
from .paypal_utils import create_paypal_order, get_paypal_order, authorize_paypal_order
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from carts.views import _cart_id, _calculate_cart_totals
from orders.shipping.easypost_client import retrieve_shipment



logger = logging.getLogger(__name__)

@login_required(login_url="login")
def get_shipping_quote(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Invalid request method."}, status=400)

    current_user = request.user

    # --- Get cart items ---
    if current_user.is_authenticated:
        cart_items = CartItem.objects.filter(user=current_user, is_active=True)
    else:
        try:
            cart = Cart.objects.get(cart_id=_cart_id(request))
            cart_items = CartItem.objects.filter(cart=cart, is_active=True)
        except ObjectDoesNotExist:
            cart_items = []

    if not cart_items:
        return JsonResponse({"success": False, "error": "Your cart is empty."}, status=400)

    # --- Subtotal (not strictly required for shipping) ---
    subtotal = Decimal("0.00")
    for cart_item in cart_items:
        subtotal += Decimal(cart_item.sub_total())

    # --- Call EasyPost using CART, not ORDER ---
    try:
        from orders.shipping.easypost_client import create_shipment_from_cart
        shipment = create_shipment_from_cart(cart_items, request.POST)

        # Collect rates
        rates = [
            {
                "id": r.id,
                "carrier": r.carrier,
                "service": r.service,
                "rate": r.rate,
            }
            for r in shipment.rates
        ]

        # De-duplicate by carrier, service, and rate amount
        seen = set()
        unique_rates = []
        for r in rates:
            key = (r['carrier'], r['service'], float(r['rate']))  # Use float for comparison
            if key not in seen:
                seen.add(key)
                unique_rates.append(r)

        # Sort by ascending rate (cheapest first)
        unique_rates.sort(key=lambda x: float(x['rate']))

        return JsonResponse({"success": True, "rates": unique_rates})
    except Exception as e:
        import traceback; traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=500)


def payments(request):
    return render(request, "orders/payments.html")


# --------------------------
# Place Order
# --------------------------



# Assuming _cart_id is defined elsewhere (e.g., session-based)

class OrderItem:
    pass

@login_required(login_url="login")
def place_order(request):
    if request.method != 'POST':
        return redirect('checkout')  # Only allow POST

    # Get validated billing/shipping data from session
    billing_data = request.session.get('billing_data')
    if not billing_data:
        return redirect('cart')

    # Validate form again defensively
    form = OrderForm(data=billing_data)
    if not form.is_valid():
        return HttpResponseBadRequest(str(form.errors))

    # Get cart and items
    try:
        if request.user.is_authenticated:
            cart_items = CartItem.objects.filter(user=request.user, is_active=True)
        else:
            cart = get_object_or_404(Cart, cart_id=_cart_id(request))
            cart_items = CartItem.objects.filter(cart=cart, is_active=True)
    except:
        return HttpResponseBadRequest("Cart not found.")

    if not cart_items.exists():
        return redirect('cart')  # Empty cart

    # Calculate subtotal + tax
    subtotal, tax, _, _ = _calculate_cart_totals(cart_items)

    # Get selected rate ID from POST
    selected_rate_id = request.POST.get('selected_rate_id')
    if not selected_rate_id:
        return HttpResponseBadRequest("No shipping rate selected.")

    # Retrieve the EasyPost shipment
    shipment_id = request.session.get('easypost_shipment_id')
    if not shipment_id:
        return HttpResponseBadRequest("No shipment found in session.")

    try:
        shipment = retrieve_shipment(shipment_id)
        if selected_rate_id == 'rate_free':
            shipping_cost = Decimal('0.00')
            shipping_carrier = 'Free'
            shipping_service = 'Shipping'
        else:
            selected_rate = next((r for r in shipment.rates if r.id == selected_rate_id), None)
            if not selected_rate:
                return HttpResponseBadRequest("Invalid shipping rate selected.")
            shipping_cost = Decimal(selected_rate.rate)
            shipping_carrier = selected_rate.carrier
            shipping_service = selected_rate.service
    except Exception as e:
        return HttpResponseBadRequest(f"EasyPost error: {e}")

    # ✅ Create the Order
    order = form.save(commit=False)
    order.user = request.user if request.user.is_authenticated else None
    order.tax = tax
    order.shipping_cost = shipping_cost
    order.shipping_method = f"{shipping_carrier} {shipping_service}"
    order.order_total = (subtotal + tax + shipping_cost).quantize(Decimal("0.01"))
    order.save()

    # Generate order_number using original logic
    yr = int(date.today().strftime("%Y"))
    dt = int(date.today().strftime("%d"))
    mt = int(date.today().strftime("%m"))
    d = date(yr, mt, dt)
    current_date = d.strftime("%Y%m%d")
    order.order_number = current_date + str(order.id)
    order.save()

    # Create Payment placeholder
    new_payment = Payment(
        user=order.user if order.user else None,
        payment_method="PayPal",
        amount_paid=Decimal("0.00"),
        status="PENDING",
    )
    new_payment.save()
    order.payment = new_payment
    order.save()


    for cart_item in cart_items:
        order_product = OrderProduct.objects.create(
            order=order,
            payment=None,  # you can link Payment later after PayPal
            user=request.user,
            product=cart_item.product,
            quantity=cart_item.quantity,
            product_price = cart_item.sub_total () / cart_item.quantity,  # if you want modifiers, adjust here
            ordered=False,
        )
        if cart_item.variations.exists():
            order_product.variations.set(cart_item.variations.all())

    # Redirect to PayPal
    try:
        order_data = create_paypal_order(order, str(order.order_total), request)
        order.paypal_order_id = order_data['id']
        order.save()
        for link in order_data["links"]:
            if link["rel"] == "approve":


                return redirect(link["href"])
        return HttpResponseBadRequest("Error: No PayPal approval URL found.")

    except Exception as e:
        print("PayPal error:", e)
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_details = e.response.json()
                print("PayPal error details:", error_details)
            except ValueError:
                print("No JSON in PayPal response.")
        order.delete()
        return HttpResponseBadRequest(f"Payment creation failed: {e}")
# --------------------------
# Paypal Return (after approval)
# --------------------------


def paypal_return(request):
    order_id = request.GET.get("token")  # PayPal returns order ID as token
    if not order_id:
        return HttpResponse("Missing PayPal order ID.")

    try:
        # Get PayPal order info
        result = get_paypal_order(order_id)
        purchase_unit = result["purchase_units"][0]
        payments_data = purchase_unit.get("payments")

        if payments_data and "authorizations" in payments_data:
            # Already authorized
            auth_obj = payments_data["authorizations"][0]
        else:
            # Explicitly authorize the order
            result = authorize_paypal_order(order_id)
            purchase_unit = result["purchase_units"][0]
            auth_obj = purchase_unit["payments"]["authorizations"][0]

        authorization_id = auth_obj["id"]
        amount_value = auth_obj["amount"]["value"]
        reference_id = purchase_unit.get("reference_id")

        # Lookup order (must still be open)
        order = Order.objects.get(paypal_order_id=order_id, is_ordered=False)
        if order.payment is None:
            from .models import Payment  # Assuming Payment is in the same models.py
            payment = Payment.objects.create(
                user=order.user,
                payment_method="paypal",  # Or whatever default you use for PayPal
                amount_paid=Decimal("0.00"),  # Placeholder, updated below
                status="PENDING",  # Placeholder
            )
            order.payment = payment
            order.save()
        else:
            payment = order.payment

        # Update Payment record
        payment = order.payment
        payment.transaction_id = authorization_id  # store PayPal auth ID here
        payment.amount_paid = Decimal(str(amount_value)).quantize(Decimal("0.01"))
        payment.status = "AUTHORIZED"
        payment.save()

        # Update Order record
        order.status = "AUTHORIZED"                 # ✅ must match choices
        order.is_ordered = False                    # ✅ still not fulfilled until capture
        order.paypal_authorization_id = authorization_id  # ✅ store auth ID on Order
        order.save()

        # Attach order products but do NOT mark them fulfilled yet
        ordered_products = OrderProduct.objects.filter(order=order)
        for op in ordered_products:
            op.payment = order.payment
            op.ordered = False                      # ✅ wait for capture
            op.save()

        # Clear the cart
        CartItem.objects.filter(user=request.user).delete()

        # Send confirmation email
        total = sum(
            Decimal(str(op.product_price)) * Decimal(str(op.quantity))
            for op in ordered_products
        )
        mail_subject = "Thank you for your order!"
        message = render_to_string("orders/order_recieved_email.html", {
            "user": request.user,
            "order": order,
            "ordered_products": ordered_products,
            "total": order.subtotal,
            "tax": order.tax,
            "shipping_method": order.shipping_method,
            "shipping_cost": order.shipping_cost,
            "grand_total": order.order_total,
            "payment": order.payment,
        })
        to_email = order.email
        send_email = EmailMessage(mail_subject, message, to=[to_email])
        send_email.content_subtype = "html"
        send_email.send()

        # Confirmation page
        context = {
            "order": order,
            "order_number": order.order_number,
            "ordered_products": ordered_products,
            "total": order.subtotal,
            "tax": order.tax,
            "shipping_method": order.shipping_method,
            "shipping_cost": order.shipping_cost,
            "grand_total": order.order_total,
            "success": "Authorization successful!",
        }
        return render(request, "orders/payments.html", context)

    except Exception as e:
        return HttpResponse("Payment execution failed: " + str(e))

def paypal_cancel(request):
    try:
        order = Order.objects.filter(user=request.user, is_ordered=False).latest("created_at")
        payment = order.payment
        order.delete()
        payment.delete()
        return redirect("cart")
    except Order.DoesNotExist:
        return redirect("cart")
    except Exception as e:
        return HttpResponse("Error: " + str(e))


@csrf_exempt
def paypal_webhook(request):
    if request.method != "POST":
        return HttpResponseBadRequest("Invalid method")

    try:
        event = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON")

    logger.info("PayPal webhook received: %s", event)

    # save raw event in DB
    PayPalWebhookLog.objects.create(
        event_type=event.get("event_type", "UNKNOWN"),
        payload=event,
    )

    event_type = event.get("event_type")
    resource = event.get("resource", {})

    if event_type == "PAYMENT.CAPTURE.COMPLETED":
        capture_id = resource.get("id")
        status = resource.get("status")

        if status == "COMPLETED" and capture_id:
            try:
                payment = Payment.objects.get(payment_id=capture_id)
                payment.status = "COMPLETED"
                payment.save()

                if payment.order:
                    order = payment.order
                    order.status = "COMPLETED"
                    order.is_ordered = True
                    order.save()
            except Payment.DoesNotExist:
                pass

    return HttpResponse("OK")

#TODO we will need to change payment.order to add signature verification with headers Paypal sends
#TODO also need to complete the webhook on Paypal when it goes live (need domain first)
from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpResponseBadRequest
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from .forms import OrderForm
from carts.models import Cart, CartItem
from .models import Order, OrderProduct, Payment, PayPalWebhookLog
import datetime, json, logging
from decimal import Decimal
from .paypal_utils import create_paypal_order, get_paypal_order, authorize_paypal_order
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from carts.views import _cart_id
from orders.shipping.easypost_client import create_shipment_from_order, get_client

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

@login_required(login_url="login")
def place_order(request):
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

    cart_count = cart_items.count() if cart_items else 0
    if cart_count <= 0:
        return redirect("store")

    # --- Subtotal, tax (shipping added later) ---
    total = Decimal("0.00")
    quantity = 0
    for cart_item in cart_items:
        total += Decimal(cart_item.sub_total())
        quantity += cart_item.quantity
    tax = (Decimal("2") * total) / Decimal("100")
    tax = tax.quantize(Decimal("0.01"))

    if request.method == "POST":
        form = OrderForm(request.POST)
        if form.is_valid():
            # --- Build and SAVE Order object (with temp totals) ---
            data = Order()
            data.user = current_user if current_user.is_authenticated else None
            data.first_name = form.cleaned_data["first_name"]
            data.last_name = form.cleaned_data["last_name"]
            data.phone = form.cleaned_data["phone"]
            data.email = form.cleaned_data["email"]
            data.address_line_1 = form.cleaned_data["address_line_1"]
            data.address_line_2 = form.cleaned_data["address_line_2"]
            data.country = form.cleaned_data["country"]
            data.state = form.cleaned_data["state"]
            data.city = form.cleaned_data["city"]
            data.zip_code = form.cleaned_data["zip_code"]
            data.order_note = form.cleaned_data["order_note"]

            # --- Shipping fields ---
            data.shipping_first_name = form.cleaned_data["shipping_first_name"]
            data.shipping_last_name = form.cleaned_data["shipping_last_name"]
            data.shipping_phone = form.cleaned_data["shipping_phone"]
            data.shipping_email = form.cleaned_data["shipping_email"]
            data.shipping_address_line_1 = form.cleaned_data["shipping_address_line_1"]
            data.shipping_address_line_2 = form.cleaned_data["shipping_address_line_2"]
            data.shipping_country = form.cleaned_data["shipping_country"]
            data.shipping_state = form.cleaned_data["shipping_state"]
            data.shipping_city = form.cleaned_data["shipping_city"]
            data.shipping_zip_code = form.cleaned_data["shipping_zip_code"]

            # Temp totals (shipping=0 for now)
            data.order_total = (total + tax).quantize(Decimal("0.01"))
            data.tax = tax
            data.ip = request.META.get("REMOTE_ADDR")
            data.shipping_cost = Decimal("0.00")  # Temp
            data.save()  # <<-- KEY: Save here to assign PK before relations/EasyPost

            # --- Create and save OrderProducts (before EasyPost, for parcels) ---
            for cart_item in cart_items:
                unit_price = cart_item.product.price + sum(v.price_modifier for v in cart_item.variations.all())
                order_product = OrderProduct(
                    order=data,
                    product=cart_item.product,
                    user=current_user if current_user.is_authenticated else None,
                    quantity=cart_item.quantity,
                    product_price=unit_price,
                )
                order_product.save()  # <<-- KEY: Save each to establish relations
                order_product.variations.set(cart_item.variations.all())

            # --- EasyPost: use selected_rate_id from checkout ---
            selected_rate_id = request.POST.get("selected_rate_id")
            if not selected_rate_id:
                data.delete()  # Rollback
                return redirect("checkout")  # Or render with error message

            try:
                client = get_client()
                shipment = create_shipment_from_order(data)  # <<-- Now safe with PK and products
                selected_rate = next((r for r in shipment.rates if r.id == selected_rate_id), None)
                if not selected_rate:
                    raise ValueError(f"Selected rate {selected_rate_id} not found in available rates.")

                bought_shipment = shipment.buy(rate=selected_rate)

                # Update order with shipping details
                data.shipping_cost = Decimal(bought_shipment.selected_rate.rate).quantize(Decimal("0.01"))
                data.shipping_method = f"{bought_shipment.selected_rate.carrier} {bought_shipment.selected_rate.service}"
                data.tracking_number = bought_shipment.tracking_code  # Optional: Save now if desired

                # Recalc total with shipping
                data.order_total = (total + tax + data.shipping_cost).quantize(Decimal("0.01"))
                data.save()  # <<-- Resave with shipping updates

            except Exception as e:
                print("EasyPost error:", e)
                data.delete()  # Rollback
                return HttpResponse("Shipping failed: " + str(e))  # Or redirect with error

            # --- Order number (after save, using ID) ---
            yr = int(datetime.date.today().strftime("%Y"))
            dt = int(datetime.date.today().strftime("%d"))
            mt = int(datetime.date.today().strftime("%m"))
            d = datetime.date(yr, mt, dt)
            current_date = d.strftime("%Y%m%d")
            order_number = current_date + str(data.id)
            data.order_number = order_number
            data.save()

            # --- Payment placeholder ---
            new_payment = Payment(
                user=current_user if current_user.is_authenticated else None,
                payment_method="PayPal",
                amount_paid=Decimal("0.00"),
                status="PENDING",
            )
            new_payment.save()
            data.payment = new_payment
            data.save()

            # --- Redirect user to PayPal approval ---
            try:
                order_data = create_paypal_order(data, str(data.order_total),
                                                 request)  # <<-- Now includes shipping in total
                for link in order_data["links"]:
                    if link["rel"] == "approve":
                        return redirect(link["href"])
                return HttpResponse("Error: No PayPal approval URL found.")
            except Exception as e:
                data.delete()
                return HttpResponse("Payment creation failed: " + str(e))

        else:
            print(form.errors)  # Debug form issues in console
            return redirect("checkout")

    # --- Fallback for GET ---
    context = {
        "total": total,
        "quantity": quantity,
        "tax": tax,
        "grand_total": total + tax,  # No shipping on GET
        "cart_items": cart_items,
        "form": OrderForm(),
    }
    return render(request, "store/checkout.html", context)
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
        order = Order.objects.get(order_number=reference_id, is_ordered=False)

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
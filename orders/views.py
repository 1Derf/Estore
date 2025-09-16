from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from .forms import OrderForm
from carts.models import Cart, CartItem
from .models import Order, OrderProduct, Payment
import datetime, sys, json
from decimal import Decimal
from carts.utils import _cart_id
from .paypal_utils import create_paypal_order, get_paypal_order, authorize_paypal_order
from django.core.mail import EmailMessage
from django.template.loader import render_to_string


def payments(request):
    return render(request, "orders/payments.html")


# --------------------------
# Place Order
# --------------------------
@login_required(login_url="login")
def place_order(request):
    current_user = request.user

    # Get cart items
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

    # Totals
    total = Decimal("0.00")
    quantity = 0
    for cart_item in cart_items:
        total += Decimal(cart_item.sub_total())
        quantity += cart_item.quantity
    tax = (Decimal("2") * total) / Decimal("100")
    tax = tax.quantize(Decimal("0.01"))
    grand_total = (total + tax).quantize(Decimal("0.01"))

    if request.method == "POST":
        form = OrderForm(request.POST)
        if form.is_valid():
            # Build Order object
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
            # Shipping
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

            data.order_total = grand_total
            data.tax = tax
            data.ip = request.META.get("REMOTE_ADDR")
            data.save()

            # Order number
            yr = int(datetime.date.today().strftime("%Y"))
            dt = int(datetime.date.today().strftime("%d"))
            mt = int(datetime.date.today().strftime("%m"))
            d = datetime.date(yr, mt, dt)
            current_date = d.strftime("%Y%m%d")
            order_number = current_date + str(data.id)
            data.order_number = order_number
            data.save()

            # Create OrderProducts
            for cart_item in cart_items:
                unit_price = cart_item.product.price + sum(v.price_modifier for v in cart_item.variations.all())
                order_product = OrderProduct(
                    order=data,
                    product=cart_item.product,
                    user=current_user if current_user.is_authenticated else None,
                    quantity=cart_item.quantity,
                    product_price=unit_price,
                )
                order_product.save()
                order_product.variations.set(cart_item.variations.all())  # ✅ copy variations properly

            # Payment placeholder
            new_payment = Payment(
                user=current_user if current_user.is_authenticated else None,
                payment_method="PayPal",
                amount_paid=Decimal("0.00"),
                status="PENDING",
            )
            new_payment.save()
            data.payment = new_payment
            data.save()

            # Redirect to PayPal v2
            try:
                order_data = create_paypal_order(data, str(grand_total), request)
                for link in order_data["links"]:
                    if link["rel"] == "approve":
                        return redirect(link["href"])
                return HttpResponse("Error: No approval URL found.")
            except Exception as e:
                data.delete()
                return HttpResponse("Payment creation failed: " + str(e))
        else:
            return redirect("checkout")
    else:
        context = {
            "total": total,
            "quantity": quantity,
            "tax": tax,
            "grand_total": grand_total,
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
            "total": total,
            "tax": order.tax,
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
            "total": order.order_total - order.tax,
            "tax": order.tax,
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
from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from .forms import OrderForm
from carts.models import Cart, CartItem
from .models import Order, OrderProduct, Payment  # Assumed models
import datetime
from decimal import Decimal
from carts.utils import _cart_id  # Import for unauth handling (adjust if needed)
from .paypal_utils import create_paypal_payment, execute_paypal_payment  # Import from same app (orders)

# Create your views here.

def payments(request):
    return render(request, 'orders/payments.html')

@login_required(login_url='login')  # Assuming you want this (matches your checkout)
def place_order(request):
    current_user = request.user

    # Get cart items (handle auth/unauth)
    cart_items = None
    if current_user.is_authenticated:
        cart_items = CartItem.objects.filter(user=current_user, is_active=True)
    else:
        try:
            cart = Cart.objects.get(cart_id=_cart_id(request))
            cart_items = CartItem.objects.filter(cart=cart, is_active=True)
        except ObjectDoesNotExist:
            pass

    cart_count = cart_items.count() if cart_items else 0
    if cart_count <= 0:
        return redirect('store')

    # Initialize totals for calculation
    total = Decimal('0.00')
    quantity = 0
    tax = Decimal('0.00')
    grand_total = Decimal('0.00')

    for cart_item in cart_items:
        total += (Decimal(str(cart_item.product.price)) * cart_item.quantity)
        quantity += cart_item.quantity

    # Calculate tax and grand total
    tax = (Decimal('2.00') * total) / Decimal('100.00')  # 2% tax
    grand_total = total + tax

    if request.method == 'POST':
        form = OrderForm(request.POST)
        if form.is_valid():
            # Store all the billing information inside Order Table
            data = Order()
            data.user = current_user if current_user.is_authenticated else None
            data.first_name = form.cleaned_data['first_name']
            data.last_name = form.cleaned_data['last_name']
            data.phone = form.cleaned_data['phone']
            data.email = form.cleaned_data['email']
            data.address_line_1 = form.cleaned_data['address_line_1']
            data.address_line_2 = form.cleaned_data['address_line_2']
            data.country = form.cleaned_data['country']
            data.state = form.cleaned_data['state']
            data.city = form.cleaned_data['city']
            data.zip_code = form.cleaned_data['zip_code']
            data.order_note = form.cleaned_data['order_note']

            #  Save shipping fields (mirroring billing)
            data.shipping_first_name = form.cleaned_data['shipping_first_name']
            data.shipping_last_name = form.cleaned_data['shipping_last_name']
            data.shipping_phone = form.cleaned_data['shipping_phone']
            data.shipping_email = form.cleaned_data['shipping_email']
            data.shipping_address_line_1 = form.cleaned_data['shipping_address_line_1']
            data.shipping_address_line_2 = form.cleaned_data['shipping_address_line_2']
            data.shipping_country = form.cleaned_data['shipping_country']
            data.shipping_state = form.cleaned_data['shipping_state']
            data.shipping_city = form.cleaned_data['shipping_city']
            data.shipping_zip_code = form.cleaned_data['shipping_zip_code']

            # Assign the calculated grand_total and tax
            data.order_total = grand_total
            data.tax = tax

            data.ip = request.META.get('REMOTE_ADDR')
            data.save()  # Save the order to get an ID for the order number

            # Generate order number
            yr = int(datetime.date.today().strftime('%Y'))
            dt = int(datetime.date.today().strftime('%d'))
            mt = int(datetime.date.today().strftime('%m'))
            d = datetime.date(yr, mt, dt)
            current_date = d.strftime("%Y%m%d")
            order_number = current_date + str(data.id)
            data.order_number = order_number
            data.save()  # Save again to update the order number

            # Create OrderProducts from CartItems
            for cart_item in cart_items:
                order_product = OrderProduct(
                    order=data,
                    product=cart_item.product,
                    user=current_user if current_user.is_authenticated else None,
                    quantity=cart_item.quantity,
                    product_price=cart_item.product.price,
                    # Add other fields if needed (e.g., ordered=True)
                )
                order_product.save()
                # Add variations if any
                order_product.variations.add(*cart_item.variations.all())

            # Create pending Payment
            new_payment = Payment(
                user=current_user if current_user.is_authenticated else None,
                payment_method='PayPal',
                amount_paid=Decimal('0.00'),  # Will update on success
                status='PENDING',  # Assumed field
            )
            new_payment.save()
            data.payment = new_payment
            data.save()

            # Initiate PayPal payment and redirect
            try:
                payment = create_paypal_payment(data, float(grand_total),
                                                request)  # UPDATED: Add request as third argument
                for link in payment.links:
                    if link.rel == "approval_url":
                        return redirect(link.href)
                return HttpResponse("Error: No approval URL found.")
            except Exception as e:
                data.delete()
                return HttpResponse("Payment creation failed: " + str(e))
        else:
            # If form is not valid, redirect back to checkout with form errors
            return redirect('checkout')  # Or render('store/checkout.html', {'form': form})
    else:
        # This 'else' block for GET request renders the checkout page
        context = {
            'total': total,
            'quantity': quantity,
            'tax': tax,
            'grand_total': grand_total,
            'cart_items': cart_items,  # Pass cart_items if needed in template
            'form': OrderForm(),  # Pass an empty form for GET requests
        }
        return render(request, 'store/checkout.html', context)


def paypal_return(request):
    payment_id = request.GET.get('paymentId')
    payer_id = request.GET.get('PayerID')

    if not payment_id or not payer_id:
        return HttpResponse("Missing payment details from PayPal.")

    try:
        payment_response = execute_paypal_payment(payment_id, payer_id)  # From paypal_utils

        # Extract order_number from PayPal description (e.g., "Payment for Order 20231001123")
        order_number = payment_response.transactions[0].description.split()[-1]

        try:
            order = Order.objects.get(order_number=order_number, is_ordered=False)
            # Proceed with updates if not yet ordered
            order.payment.status = 'Completed'
            order.payment.amount_paid = Decimal(payment_response.transactions[0].amount.total)
            order.payment.payment_id = payment_response.id
            order.payment.save()

            order.status = 'Completed'
            order.is_ordered = True
            order.save()

            # NEW: Update all OrderProducts with payment and ordered=True
            for op in order.orderproduct_set.all():
                op.payment = order.payment
                op.ordered = True
                op.save()

            # Clear the cart (only on success, if not already cleared)
            CartItem.objects.filter(user=request.user).delete()
        except Order.DoesNotExist:
            # If already ordered (e.g., page reload), just fetch the completed order
            order = Order.objects.get(order_number=order_number, is_ordered=True)

        # Fetch ordered products and calculate total
        ordered_products = OrderProduct.objects.filter(order=order)
        total = sum(Decimal(str(item.product_price)) * item.quantity for item in ordered_products)

        context = {
            'order': order,
            'ordered_products': ordered_products,
            'total': total,
            'tax': order.tax,
            'grand_total': order.order_total,
            'payment': order.payment,
        }
        return render(request, 'orders/payments.html', context)

    except Exception as e:
        return HttpResponse("Payment execution failed: " + str(e))


def paypal_cancel(request):
    try:
        order = Order.objects.filter(user=request.user, is_ordered=False).latest('created_at')
        payment = order.payment

        # Delete pending Order and Payment (cleanup, no OrderProducts)
        order.delete()
        payment.delete()

        # Redirect to cart page (preserves cart for adjustment/retry)
        return redirect('cart')  # Assumes your cart URL name is 'cart'; adjust if different
    except Order.DoesNotExist:
        return redirect('cart')  # Still redirect even if no order found
    except Exception as e:
        return HttpResponse("Error: " + str(e))  # Fallback; or redirect with error message
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
            data.order_note = form.cleaned_data['order_note']

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
                payment = create_paypal_payment(order_number, float(grand_total))  # Convert Decimal to float for PayPal
                for link in payment.links:
                    if link.rel == "approval_url":
                        return redirect(link.href)
                return HttpResponse("Error: No approval URL found.")
            except Exception as e:
                # Rollback on error (optional: delete the order to avoid orphans)
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
        order = Order.objects.get(order_number=order_number, is_ordered=False)

        # Update Payment (use Decimal for amount_paid, set status)
        order.payment.status = 'Completed'
        order.payment.amount_paid = Decimal(payment_response.transactions[0].amount.total)
        order.payment.payment_id = payment_response.id
        order.payment.save()

        # Update Order (set status and is_ordered)
        order.status = 'Completed'  # Matches your STATUS choices
        order.is_ordered = True
        order.save()

        # Clear the cart (only on success)
        CartItem.objects.filter(user=request.user).delete()  # Assumes auth; add unauth if needed

        # Render success confirmation (reuse payments.html with your context)
        context = {
            'order': order,
            'cart_items': [],  # Empty since cleared
            'total': 0,
            'tax': order.tax,
            'grand_total': order.order_total,
            'payment': order.payment,  # Pass for display (e.g., payment_id)
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
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import render, redirect, get_object_or_404
from orders.shipping.easypost_client import create_shipment_from_order
from accounts.models import UserProfile
from store.models import Product, Variation, VariationCategory, Wishlist
from .models import CartItem, Cart
from django.contrib.auth.decorators import login_required
from carts.utils import _cart_id
from django.http import JsonResponse
from django.contrib import messages
from decimal import Decimal
from orders.models import SiteSettings
from orders.forms import OrderForm
from orders.shipping.easypost_client import create_shipment_from_order   # 🆕 EasyPost helper
# --------------------------
# Helpers
# --------------------------
def _calculate_cart_totals(cart_items):
    """
    Calculate totals using CartItem.sub_total() so variation price modifiers are included.
    """
    total = Decimal("0.00")
    quantity = 0
    for cart_item in cart_items:
        total += Decimal(cart_item.sub_total())
        quantity += cart_item.quantity
    tax = (Decimal("2") * total) / Decimal("100")
    tax = tax.quantize(Decimal("0.01"))
    grand_total = (total + tax).quantize(Decimal("0.01"))
    return total, tax, grand_total, quantity


# --------------------------
# Cart operations
# --------------------------

def add_cart(request, product_id):
    current_user = request.user
    product = get_object_or_404(Product, id=product_id)

    if request.method == "POST":
        try:
            quantity = int(request.POST.get("quantity", 1))
            if quantity < 1 or quantity > (product.stock or 0):
                msg = "Invalid quantity. Must be between 1 and available stock."
                if request.headers.get("x-requested-with") == "XMLHttpRequest":
                    return JsonResponse({"status": "error", "message": msg}, status=400)
                messages.error(request, msg)
                # Use the correct URL name for your detail page (likely namespaced)
                return redirect("store:product_detail", category_slug=product.category.slug, product_slug=product.slug)

            # ---- variation handling ----
            product_variations = []
            if product.has_variants:
                # Only consider ACTIVE variations to determine required categories
                required_categories = (
                    Variation.objects.filter(product=product, is_active=True)
                    .values_list("category__name", flat=True)
                    .distinct()
                )

                # Match posted selections to ACTIVE variations
                for key, value in request.POST.items():
                    if key in required_categories:
                        qs = Variation.objects.filter(
                            product=product,
                            category__name__iexact=key.strip(),
                            name__iexact=(value or "").strip(),
                            is_active=True,  # ignore inactive rows
                        ).order_by("id")
                        variation = qs.first()  # deterministic, avoids MultipleObjectsReturned
                        if variation:
                            product_variations.append(variation)

                # Ensure user selected one active variation for each required category
                if len(product_variations) < len(required_categories):
                    msg = "Please select all required variations for this product."
                    if request.headers.get("x-requested-with") == "XMLHttpRequest":
                        return JsonResponse({"status": "error", "message": msg}, status=400)
                    messages.error(request, msg)
                    return redirect(
                        "store:product_detail",
                        category_slug=product.category.slug,
                        product_slug=product.slug,
                    )

            # ---- save cart item ----
            if current_user.is_authenticated:
                cart_item_qs = CartItem.objects.filter(product=product, user=current_user)
            else:
                cart, _ = Cart.objects.get_or_create(cart_id=_cart_id(request))
                cart_item_qs = CartItem.objects.filter(product=product, cart=cart)

            ex_var_list = []
            id_list = []
            for item in cart_item_qs:
                existing_variations = list(item.variations.all())
                ex_var_list.append(existing_variations)
                id_list.append(item.id)

            if product_variations in ex_var_list:
                index = ex_var_list.index(product_variations)
                item_id = id_list[index]
                cart_item = CartItem.objects.get(product=product, id=item_id)
                cart_item.quantity += quantity
                cart_item.save()
            else:
                cart_item = CartItem.objects.create(
                    product=product,
                    quantity=quantity,
                    user=current_user if current_user.is_authenticated else None,
                    cart=None if current_user.is_authenticated else cart,
                )
                if product_variations:
                    cart_item.variations.set(product_variations)
                cart_item.save()

            # ---- clean up wishlist ----
            if current_user.is_authenticated:
                wishlist_items = Wishlist.objects.filter(user=current_user, product=product)
                for item in wishlist_items:
                    if set(item.variations.all()) == set(product_variations):
                        item.delete()

            # ---- Ajax response ----
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                try:
                    if current_user.is_authenticated:
                        cart_items = CartItem.objects.filter(user=current_user, is_active=True)
                    else:
                        cart = Cart.objects.get(cart_id=_cart_id(request))
                        cart_items = CartItem.objects.filter(cart=cart, is_active=True)

                    total, tax, grand_total, total_cart_items = _calculate_cart_totals(cart_items)
                    data = {
                        "status": "success",
                        "quantity": cart_item.quantity,
                        "item_subtotal": str(cart_item.sub_total()),
                        "total": str(total),
                        "tax": str(tax),
                        "grand_total": str(grand_total),
                        "total_cart_items": total_cart_items,
                        "cart_item_id": cart_item.id,
                    }
                    return JsonResponse(data)
                except Exception as e:
                    return JsonResponse({"status": "error", "message": f"Error calculating cart totals: {str(e)}"}, status=500)

        except Exception as e:
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({"status": "error", "message": f"Server error: {str(e)}"}, status=500)
            raise

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"status": "error", "message": "Invalid request method."}, status=400)
    return redirect("cart")


def remove_cart(request, product_id, cart_item_id):
    product = get_object_or_404(Product, id=product_id)
    cart_item = None
    try:
        if request.user.is_authenticated:
            cart_item = CartItem.objects.get(product=product, user=request.user, id=cart_item_id)
        else:
            cart = Cart.objects.get(cart_id=_cart_id(request))
            cart_item = CartItem.objects.get(product=product, cart=cart, id=cart_item_id)
        if cart_item.quantity > 1:
            cart_item.quantity -= 1
            cart_item.save()
        else:
            cart_item.delete()
            cart_item = None
    except CartItem.DoesNotExist:
        pass

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        if request.user.is_authenticated:
            cart_items = CartItem.objects.filter(user=request.user, is_active=True)
        else:
            try:
                cart = Cart.objects.get(cart_id=_cart_id(request))
                cart_items = CartItem.objects.filter(cart=cart, is_active=True)
            except Cart.DoesNotExist:
                cart_items = []
        total, tax, grand_total, total_cart_items = _calculate_cart_totals(cart_items)
        updated_quantity = 0
        updated_item_subtotal = Decimal("0.00")
        if cart_item:
            updated_quantity = cart_item.quantity
            updated_item_subtotal = cart_item.sub_total()
        data = {
            "quantity": updated_quantity,
            "item_subtotal": str(updated_item_subtotal),
            "total": str(total),
            "tax": str(tax),
            "grand_total": str(grand_total),
            "total_cart_items": total_cart_items,
            "cart_item_id": cart_item_id,
        }
        return JsonResponse(data)
    return redirect("cart")


def remove_cart_item(request, product_id, cart_item_id):
    product = get_object_or_404(Product, id=product_id)
    if request.user.is_authenticated:
        cart_item = CartItem.objects.get(product=product, user=request.user, id=cart_item_id)
    else:
        cart = Cart.objects.get(cart_id=_cart_id(request))
        cart_item = CartItem.objects.get(product=product, cart=cart, id=cart_item_id)
    cart_item.delete()
    return redirect("cart")


# --------------------------
# Views
# --------------------------
@login_required(login_url="login")
def cart(request, total=0, quantity=0, cart_items=None):
    try:
        tax = Decimal("0.00")
        grand_total = Decimal("0.00")
        if request.user.is_authenticated:
            cart_items = CartItem.objects.filter(user=request.user, is_active=True)
        else:
            cart = Cart.objects.get(cart_id=_cart_id(request))
            cart_items = CartItem.objects.filter(cart=cart, is_active=True)
        total, tax, grand_total, quantity = _calculate_cart_totals(cart_items)
    except ObjectDoesNotExist:
        pass

    initial_data = {}
    if request.user.is_authenticated:
        try:
            userprofile = UserProfile.objects.get(user=request.user)
            initial_data = {
                'first_name': request.user.first_name,
                'last_name': request.user.last_name,
                'email': request.user.email,
                'phone': getattr(userprofile, 'phone_number', '') or getattr(request.user, 'phone_number', ''),
                'address_line_1': userprofile.address_line_1,
                'address_line_2': userprofile.address_line_2,
                'city': userprofile.city,
                'state': userprofile.state,
                'country': userprofile.country,
                'zip_code': userprofile.zip_code,
            }
        except ObjectDoesNotExist:
            pass

    form = OrderForm(request.POST or None, initial=initial_data or request.session.get('billing_data', {}))
    if request.method == "POST":
        if form.is_valid():
            request.session['billing_data'] = form.cleaned_data  # Save to session
            return redirect("checkout")
        # Else, form errors will show in template (you can add {{ form.errors }} in cart.html if needed)

    context = {
        "total": total,
        "quantity": quantity,
        "cart_items": cart_items,
        "tax": tax,
        "grand_total": grand_total,
        "form": form,
    }
    return render(request, "store/cart.html", context)

@login_required(login_url="login")
def checkout(request, total=0, quantity=0, cart_items=None):
    try:
        tax = Decimal("0.00")
        grand_total = Decimal("0.00")
        userprofile = None

        if request.user.is_authenticated:
            cart_items = CartItem.objects.filter(user=request.user, is_active=True)
            userprofile = get_object_or_404(UserProfile, user=request.user)
        else:
            cart = Cart.objects.get(cart_id=_cart_id(request))
            cart_items = CartItem.objects.filter(cart=cart, is_active=True)

        # calculate subtotal + tax
        total, tax, grand_total, quantity = _calculate_cart_totals(cart_items)

        # Fetch EasyPost rates using session billing_data
        billing_data = request.session.get('billing_data', {})
        if not billing_data:
            return redirect('cart')

        rates = []
        try:
            # Use create_shipment_from_cart with cart_items and billing_data
            from orders.shipping.easypost_client import create_shipment_from_cart  # Add this import if not already
            shipment = create_shipment_from_cart(cart_items, billing_data)
            rates = [
                {
                    "id": r.id,
                    "carrier": r.carrier,
                    "service": r.service,
                    "rate": r.rate,
                }
                for r in shipment.rates
            ]

            # Free shipping logic (using subtotal as 'total')
            settings = SiteSettings.objects.first()
            free_shipping_enabled = settings.free_shipping_enabled if settings else False
            free_shipping_threshold = settings.free_shipping_threshold if settings else Decimal('99.00')

            if free_shipping_enabled and total >= free_shipping_threshold:
                rates.append({
                    "id": "rate_free",
                    "carrier": "Free",
                    "service": "Shipping",
                    "rate": "0.00",
                })

            request.session['easypost_shipment_id'] = shipment.id

        except Exception as e:
            print("EasyPost error:", e)
            rates = []

        # 🆕 For now, don’t add shipping until a rate is chosen
        order_total = (total + tax).quantize(Decimal("0.01"))

    except ObjectDoesNotExist:
        rates, order_total = [], Decimal("0.00")

    rates = sorted(rates, key=lambda r: float(r['rate']))

    context = {
        "total": total,
        "quantity": quantity,
        "cart_items": cart_items,
        "tax": tax,
        "grand_total": grand_total,     # subtotal + tax (old style)
        "order_total": order_total,     # subtotal + tax (+ shipping later)
        "userprofile": userprofile,
        "user": request.user if request.user.is_authenticated else None,
        "rates": rates,                 # 🆕 multiple options from EasyPost
        "billing_data": billing_data,   # For the summary
    }
    return render(request, "store/checkout.html", context)







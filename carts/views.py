from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import render, redirect, get_object_or_404

from accounts.views import login
from store.models import Product, Variation
from .models import CartItem, Cart
from django.contrib.auth.decorators import login_required
from carts.utils import _cart_id
from django.db.models import Q

# Create your views here.

#def _cart_id(request):
#    cart = request.session.session_key
#    if not cart:
#        cart = request.session.create()
#    return cart





# In carts/views.py

from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import render, redirect, get_object_or_404
from store.models import Product, Variation
from .models import CartItem, Cart
from django.contrib.auth.decorators import login_required
from carts.utils import _cart_id
from django.http import JsonResponse # This import is already there, good!

# --- Helper Function for Calculating Cart Totals ---
# This function centralizes the logic for calculating totals,
# making it reusable for both regular views and AJAX responses.
def _calculate_cart_totals(cart_items):
    total = 0
    tax = 0
    grand_total = 0
    quantity = 0 # Also calculate total quantity of items in cart

    for cart_item in cart_items:
        total += (cart_item.product.price * cart_item.quantity)
        quantity += cart_item.quantity
    tax = (2 * total) / 100 # Assuming 2% tax, adjust as needed
    grand_total = total + tax
    return total, tax, grand_total, quantity

# --- Modified add_cart View ---
def add_cart(request, product_id):
    current_user = request.user
    product = get_object_or_404(Product, id=product_id) # Use get_object_or_404 for robustness

    product_variation = []
    if request.method == 'POST':
        for item in request.POST:
            key = item
            value = request.POST[key]
            try:
                variation = Variation.objects.get(product=product, variation_category__iexact=key, variation_value__iexact=value)
                product_variation.append(variation)
            except Variation.DoesNotExist: # Be specific with exceptions
                pass

    # Logic for authenticated users
    if current_user.is_authenticated:
        is_cart_item_exists = CartItem.objects.filter(product=product, user=current_user).exists()
        if is_cart_item_exists:
            cart_item_qs = CartItem.objects.filter(product=product, user=current_user)
            ex_var_list = []
            id_list = [] # Renamed 'id' to 'id_list' to avoid conflict with built-in id()
            for item in cart_item_qs:
                existing_variation = item.variations.all()
                ex_var_list.append(list(existing_variation))
                id_list.append(item.id)

            if product_variation in ex_var_list:
                index = ex_var_list.index(product_variation)
                item_id = id_list[index]
                cart_item = CartItem.objects.get(product=product, id=item_id)
                cart_item.quantity += 1
                cart_item.save()
            else:
                cart_item = CartItem.objects.create(product=product, quantity=1, user=current_user)
                if product_variation: # Check if list is not empty
                    cart_item.variations.clear()
                    cart_item.variations.add(*product_variation)
                cart_item.save()
        else:
            cart_item = CartItem.objects.create(
                product = product,
                quantity = 1,
                user = current_user,
            )
            if product_variation:
                cart_item.variations.clear()
                cart_item.variations.add(*product_variation)
            cart_item.save()
    # Logic for unauthenticated users
    else:
        try:
            cart = Cart.objects.get(cart_id=_cart_id(request))
        except Cart.DoesNotExist:
            cart = Cart.objects.create(cart_id=_cart_id(request))
        cart.save()

        is_cart_item_exists = CartItem.objects.filter(product=product, cart=cart).exists()
        if is_cart_item_exists:
            cart_item_qs = CartItem.objects.filter(product=product, cart=cart)
            ex_var_list = []
            id_list = []
            for item in cart_item_qs:
                existing_variation = item.variations.all()
                ex_var_list.append(list(existing_variation))
                id_list.append(item.id)

            if product_variation in ex_var_list:
                index = ex_var_list.index(product_variation)
                item_id = id_list[index]
                cart_item = CartItem.objects.get(product=product, id=item_id)
                cart_item.quantity += 1
                cart_item.save()
            else:
                cart_item = CartItem.objects.create(product=product, quantity=1, cart=cart)
                if product_variation:
                    cart_item.variations.clear()
                    cart_item.variations.add(*product_variation)
                cart_item.save()
        else:
            cart_item = CartItem.objects.create(
                product = product,
                quantity = 1,
                cart = cart,
            )
            if product_variation:
                cart_item.variations.clear()
                cart_item.variations.add(*product_variation)
            cart_item.save()

    # --- AJAX Response Logic for add_cart ---
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        if current_user.is_authenticated:
            cart_items = CartItem.objects.filter(user=current_user, is_active=True)
        else:
            cart = Cart.objects.get(cart_id=_cart_id(request))
            cart_items = CartItem.objects.filter(cart=cart, is_active=True)

        total, tax, grand_total, total_cart_items = _calculate_cart_totals(cart_items)

        data = {
            'quantity': cart_item.quantity,
            'item_subtotal': float(cart_item.sub_total()), # Ensure float for JSON serialization
            'total': float(total),
            'tax': float(tax),
            'grand_total': float(grand_total),
            'total_cart_items': total_cart_items,
            'cart_item_id': cart_item.id, # Send back the cart_item_id for potential use
        }
        return JsonResponse(data)
    # --- End AJAX Response Logic ---

    return redirect('cart') # Fallback for non-AJAX requests

# --- Modified remove_cart View ---
def remove_cart(request, product_id, cart_item_id):
    product = get_object_or_404(Product, id=product_id)
    cart_item = None # Initialize cart_item to None

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
            cart_item = None # Set to None if deleted to indicate it no longer exists
    except CartItem.DoesNotExist: # Be specific with exceptions
        pass # Item already removed or never existed, gracefully handle

    # --- AJAX Response Logic for remove_cart ---
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        if request.user.is_authenticated:
            cart_items = CartItem.objects.filter(user=request.user, is_active=True)
        else:
            # Ensure cart exists before trying to filter cart_items
            try:
                cart = Cart.objects.get(cart_id=_cart_id(request))
                cart_items = CartItem.objects.filter(cart=cart, is_active=True)
            except Cart.DoesNotExist:
                cart_items = [] # No cart, so no items

        total, tax, grand_total, total_cart_items = _calculate_cart_totals(cart_items)

        updated_quantity = 0
        updated_item_subtotal = 0.0
        if cart_item: # If cart_item still exists (wasn't deleted)
            updated_quantity = cart_item.quantity
            updated_item_subtotal = float(cart_item.sub_total())

        data = {
            'quantity': updated_quantity,
            'item_subtotal': updated_item_subtotal,
            'total': float(total),
            'tax': float(tax),
            'grand_total': float(grand_total),
            'total_cart_items': total_cart_items,
            'cart_item_id': cart_item_id, # Send back the original cart_item_id
        }
        return JsonResponse(data)
    # --- End AJAX Response Logic ---

    return redirect('cart')

# --- Existing remove_cart_item View (No changes needed for AJAX here) ---
def remove_cart_item(request, product_id, cart_item_id):
    product = get_object_or_404(Product, id=product_id)
    if request.user.is_authenticated:
        cart_item = CartItem.objects.get(product=product, user=request.user, id=cart_item_id)
    else:
        cart = Cart.objects.get(cart_id=_cart_id(request))
        cart_item = CartItem.objects.get(product=product, cart=cart, id=cart_item_id)
    cart_item.delete()
    return redirect('cart')

# --- Existing cart View (No changes needed for AJAX here, it's for rendering the cart page) ---
def cart(request, total=0, quantity=0, cart_items=None):
    try:
        tax = 0
        grand_total = 0
        if request.user.is_authenticated:
            cart_items = CartItem.objects.filter(user=request.user, is_active=True)
        else:
            cart = Cart.objects.get(cart_id=_cart_id(request))
            cart_items = CartItem.objects.filter(cart=cart, is_active=True)

        total, tax, grand_total, quantity = _calculate_cart_totals(cart_items) # Use the helper

    except ObjectDoesNotExist:
        pass #just ignore

    context = {
        'total': total,
        'quantity': quantity,
        'cart_items': cart_items,
        'tax'       : tax,
        'grand_total': grand_total,
    }
    return render(request, 'store/cart.html', context)

# --- Existing checkout View (No changes needed for AJAX here, it's for rendering the checkout page) ---
@login_required(login_url='login')
def checkout(request, total=0, quantity=0, cart_items=None):
    try:
        tax = 0
        grand_total = 0
        if request.user.is_authenticated:
            cart_items = CartItem.objects.filter(user=request.user, is_active=True)
        else:
            cart = Cart.objects.get(cart_id=_cart_id(request))
            cart_items = CartItem.objects.filter(cart=cart, is_active=True)

        total, tax, grand_total, quantity = _calculate_cart_totals(cart_items) # Use the helper

    except ObjectDoesNotExist:
        pass #just ignore

    context = {
        'total': total,
        'quantity': quantity,
        'cart_items': cart_items,
        'tax'       : tax,
        'grand_total': grand_total,
    }
    return render(request, 'store/checkout.html', context)
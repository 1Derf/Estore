from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import render, redirect, get_object_or_404
from store.models import Product, Variation, Wishlist
from .models import CartItem, Cart
from django.contrib.auth.decorators import login_required
from carts.utils import _cart_id
from django.http import JsonResponse
from django.contrib import messages
from decimal import Decimal

def _calculate_cart_totals(cart_items):
    total = Decimal('0.00')
    tax = Decimal('0.00')
    grand_total = Decimal('0.00')
    quantity = 0
    for cart_item in cart_items:
        total += (cart_item.product.price * Decimal(cart_item.quantity))
        quantity += cart_item.quantity
    tax = (Decimal('2') * total) / Decimal('100')
    tax = tax.quantize(Decimal('0.01'))
    grand_total = total + tax
    grand_total = grand_total.quantize(Decimal('0.01'))
    return total, tax, grand_total, quantity

def add_cart(request, product_id):
    current_user = request.user
    try:
        product = get_object_or_404(Product, id=product_id)
    except Exception as e:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': f'Product not found: {str(e)}'}, status=404)
        return redirect('store')

    if request.method == 'POST':
        try:
            quantity = int(request.POST.get('quantity', 1))
            if quantity < 1 or quantity > product.stock:
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({'status': 'error', 'message': 'Invalid quantity. Must be between 1 and available stock.'}, status=400)
                messages.error(request, "Invalid quantity. Must be between 1 and available stock.")
                return redirect('product_detail', category_slug=product.category.slug, product_slug=product.slug)

            product_variations = []
            if product.has_variants:
                valid_categories = Variation.objects.filter(product=product, is_active=True).values_list('variation_category', flat=True).distinct()
                for key, value in request.POST.items():
                    if key in valid_categories:
                        try:
                            variation = Variation.objects.get(
                                product=product,
                                variation_category__iexact=key,
                                variation_value__iexact=value,
                                is_active=True
                            )
                            product_variations.append(variation)
                        except Variation.DoesNotExist:
                            continue
                if len(product_variations) < len(valid_categories):
                    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                        return JsonResponse({'status': 'error', 'message': 'Please select all required variations.'}, status=400)
                    messages.error(request, "Please select all required variations.")
                    return redirect('product_detail', category_slug=product.category.slug, product_slug=product.slug)

            if current_user.is_authenticated:
                cart_item_qs = CartItem.objects.filter(product=product, user=current_user)
                ex_var_list = []
                id_list = []
                for item in cart_item_qs:
                    existing_variations = item.variations.all()
                    ex_var_list.append(list(existing_variations))
                    id_list.append(item.id)
                if product_variations in ex_var_list:
                    index = ex_var_list.index(product_variations)
                    item_id = id_list[index]
                    cart_item = CartItem.objects.get(product=product, id=item_id)
                    cart_item.quantity += quantity
                    cart_item.save()
                else:
                    cart_item = CartItem.objects.create(product=product, quantity=quantity, user=current_user)
                    if product_variations:
                        cart_item.variations.set(product_variations)
                    cart_item.save()
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    wishlist_items = Wishlist.objects.filter(user=current_user, product=product)
                    for item in wishlist_items:
                        if set(item.variations.all()) == set(product_variations):
                            item.delete()
            else:
                try:
                    cart = Cart.objects.get(cart_id=_cart_id(request))
                except Cart.DoesNotExist:
                    cart = Cart.objects.create(cart_id=_cart_id(request))
                    cart.save()
                cart_item_qs = CartItem.objects.filter(product=product, cart=cart)
                ex_var_list = []
                id_list = []
                for item in cart_item_qs:
                    existing_variations = item.variations.all()
                    ex_var_list.append(list(existing_variations))
                    id_list.append(item.id)
                if product_variations in ex_var_list:
                    index = ex_var_list.index(product_variations)
                    item_id = id_list[index]
                    cart_item = CartItem.objects.get(product=product, id=item_id)
                    cart_item.quantity += quantity
                    cart_item.save()
                else:
                    cart_item = CartItem.objects.create(product=product, quantity=quantity, cart=cart)
                    if product_variations:
                        cart_item.variations.set(product_variations)
                    cart_item.save()

            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                try:
                    if current_user.is_authenticated:
                        cart_items = CartItem.objects.filter(user=current_user, is_active=True)
                    else:
                        cart = Cart.objects.get(cart_id=_cart_id(request))
                        cart_items = CartItem.objects.filter(cart=cart, is_active=True)
                    total, tax, grand_total, total_cart_items = _calculate_cart_totals(cart_items)
                    data = {
                        'status': 'success',
                        'quantity': cart_item.quantity,
                        'item_subtotal': str(cart_item.sub_total()),
                        'total': str(total),
                        'tax': str(tax),
                        'grand_total': str(grand_total),
                        'total_cart_items': total_cart_items,
                        'cart_item_id': cart_item.id,
                    }
                    return JsonResponse(data)
                except Exception as e:
                    return JsonResponse({'status': 'error', 'message': f'Error calculating cart totals: {str(e)}'}, status=500)

        except Exception as e:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'status': 'error', 'message': f'Server error: {str(e)}'}, status=500)
            raise

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=400)
    return redirect('cart')

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

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
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
        updated_item_subtotal = Decimal('0.00')
        if cart_item:
            updated_quantity = cart_item.quantity
            updated_item_subtotal = cart_item.sub_total()
        data = {
            'quantity': updated_quantity,
            'item_subtotal': str(updated_item_subtotal),
            'total': str(total),
            'tax': str(tax),
            'grand_total': str(grand_total),
            'total_cart_items': total_cart_items,
            'cart_item_id': cart_item_id,
        }
        return JsonResponse(data)
    return redirect('cart')

def remove_cart_item(request, product_id, cart_item_id):
    product = get_object_or_404(Product, id=product_id)
    if request.user.is_authenticated:
        cart_item = CartItem.objects.get(product=product, user=request.user, id=cart_item_id)
    else:
        cart = Cart.objects.get(cart_id=_cart_id(request))
        cart_item = CartItem.objects.get(product=product, cart=cart, id=cart_item_id)
    cart_item.delete()
    return redirect('cart')

def cart(request, total=0, quantity=0, cart_items=None):
    try:
        tax = Decimal('0.00')
        grand_total = Decimal('0.00')
        if request.user.is_authenticated:
            cart_items = CartItem.objects.filter(user=request.user, is_active=True)
        else:
            cart = Cart.objects.get(cart_id=_cart_id(request))
            cart_items = CartItem.objects.filter(cart=cart, is_active=True)
        total, tax, grand_total, quantity = _calculate_cart_totals(cart_items)
    except ObjectDoesNotExist:
        pass

    context = {
        'total': total,
        'quantity': quantity,
        'cart_items': cart_items,
        'tax': tax,
        'grand_total': grand_total,
    }
    return render(request, 'store/cart.html', context)

@login_required(login_url='login')
def checkout(request, total=0, quantity=0, cart_items=None):
    try:
        tax = Decimal('0.00')
        grand_total = Decimal('0.00')
        if request.user.is_authenticated:
            cart_items = CartItem.objects.filter(user=request.user, is_active=True)
        else:
            cart = Cart.objects.get(cart_id=_cart_id(request))
            cart_items = CartItem.objects.filter(cart=cart, is_active=True)
        total, tax, grand_total, quantity = _calculate_cart_totals(cart_items)
    except ObjectDoesNotExist:
        pass

    context = {
        'total': total,
        'quantity': quantity,
        'cart_items': cart_items,
        'tax': tax,
        'grand_total': grand_total,
    }
    return render(request, 'store/checkout.html', context)
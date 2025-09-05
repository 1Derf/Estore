from django.core.exceptions import ObjectDoesNotExist
from .models import Cart, CartItem
import uuid


def _cart_id(request):
    cart_id = request.session.get('cart_id')
    if not cart_id:
        cart_id = str(uuid.uuid4())
        request.session['cart_id'] = cart_id
        request.session.modified = True
    return cart_id


def migrate_cart_items(request, user):
    try:
        session_cart_id = _cart_id(request)
        session_cart = Cart.objects.get(cart_id=session_cart_id)
        session_cart_items = CartItem.objects.filter(cart=session_cart)
        user_cart_items = CartItem.objects.filter(user=user)

        for session_item in session_cart_items:
            existing_user_item = None
            for user_item in user_cart_items:
                if user_item.product == session_item.product and \
                        set(user_item.variations.all()) == set(session_item.variations.all()):
                    existing_user_item = user_item
                    break
            if existing_user_item:
                existing_user_item.quantity += session_item.quantity
                existing_user_item.save()
                session_item.delete()
            else:
                session_item.user = user
                session_item.cart = None
                session_item.save()

        session_cart.delete()
    except Cart.DoesNotExist:
        pass
    except Exception:
        pass

from django.core.exceptions import ObjectDoesNotExist
from .models import Cart, CartItem # Ensure these are imported
import uuid # Import uuid for generating unique IDs

def _cart_id(request):
    # Try to get the cart_id from the session
    cart_id = request.session.get('cart_id')

    # If no cart_id is found in the session, create a new one
    if not cart_id:
        # Generate a unique ID (UUID is excellent for this)
        cart_id = str(uuid.uuid4())
        # Store it in the session
        request.session['cart_id'] = cart_id
        # Ensure the session is saved (important if it's a new session)
        request.session.modified = True
    return cart_id


def migrate_cart_items(request, user):
    print("\n--- DEBUG: Entering migrate_cart_items function ---")
    print(f"DEBUG: User attempting to log in: {user.email} (ID: {user.id})")

    try:
        # Get the session cart ID from the request
        session_cart_id = _cart_id(request)
        print(f"DEBUG: Retrieved session cart ID: {session_cart_id}")

        # Try to get the session cart object
        session_cart = Cart.objects.get(cart_id=session_cart_id)
        print(f"DEBUG: Found session cart: {session_cart.cart_id}")

        # Get all cart items associated with this session cart
        session_cart_items = CartItem.objects.filter(cart=session_cart)
        print(f"DEBUG: Number of items in session cart: {session_cart_items.count()}")

        # Get the user's existing cart items (if any)
        user_cart_items = CartItem.objects.filter(user=user)
        print(f"DEBUG: Number of items already in user's cart: {user_cart_items.count()}")

        # Iterate through each item in the session cart
        for session_item in session_cart_items:
            print(f"\nDEBUG: Processing session item: Product '{session_item.product.product_name}', Qty: {session_item.quantity}")
            print(f"DEBUG: Session item variations: {[v.variation_value for v in session_item.variations.all()]}")

            # Check if an identical item (same product, same variations) already exists in the user's cart
            existing_user_item = None
            for user_item in user_cart_items:
                if user_item.product == session_item.product and \
                   set(user_item.variations.all()) == set(session_item.variations.all()):
                    existing_user_item = user_item
                    print(f"DEBUG: Found existing user item for merge: Product '{user_item.product.product_name}', Qty: {user_item.quantity}")
                    break

            if existing_user_item:
                # If item exists, update quantity and delete session item
                existing_user_item.quantity += session_item.quantity
                existing_user_item.save()
                print(f"DEBUG: Merged session item quantity into existing user item. New Qty: {existing_user_item.quantity}")
                session_item.delete() # Delete the session item after merging
                print(f"DEBUG: Deleted session item after merge.")
            else:
                # If item does not exist in user's cart, reassign it
                session_item.user = user
                session_item.cart = None # Disassociate from session cart
                session_item.save()
                print(f"DEBUG: Reassigned session item to user. Item ID: {session_item.id}")

        # After processing all items, delete the session cart itself
        session_cart.delete()
        print(f"DEBUG: Deleted session cart: {session_cart.cart_id}")

    except Cart.DoesNotExist:
        print("DEBUG: No session cart found for migration. This is normal if user had no items.")
    except Exception as e:
        print(f"CRITICAL ERROR: An unexpected error occurred during cart migration: {e}")
        # You might want to log this error more formally in a production environment

    print("--- DEBUG: Exiting migrate_cart_items function ---")
from .models import Product

def recently_viewed(request):
    viewed_ids = request.session.get('viewed_products', [])
    # Fetch products, preserving order (most recent first), exclude unavailable
    recently_viewed = Product.objects.filter(id__in=viewed_ids, is_available=True).order_by('-modified_date')[:5]  # Limit to 5, match session order if possible
    # To preserve exact session order (since order_by might not match)
    ordered_products = sorted(recently_viewed, key=lambda p: viewed_ids.index(p.id) if p.id in viewed_ids else len(viewed_ids))
    return {'recently_viewed': ordered_products}
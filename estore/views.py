from django.shortcuts import render
from store.models import Product, ReviewRating

def home(request):
    products = Product.objects.filter(is_available=True, is_featured=True).order_by('-created_date')

    # Get Reviews and attach to each product
    for product in products:
        product.reviews = ReviewRating.objects.filter(product_id=product.id, status=True)

    context = {
        'products': products,
    }
    return render(request, 'home.html', context)

def store(request):
    return render(request, 'store.html')
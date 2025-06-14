#from lib2to3.fixes.fix_input import context

from django.shortcuts import render

from store.models import Product


def home (request):
    products = Product.objects.all().filter(is_available=True)

    context = {
        'products': products,
    }
    return render(request, 'home.html', context)

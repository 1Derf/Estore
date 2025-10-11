from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.csrf import csrf_protect
from carts.models import CartItem
from carts.utils import _cart_id
from orders.models import OrderProduct
from .forms import ReviewForm
from .models import Product, ReviewRating, ProductGallery, ProductDownload, Brand, Wishlist, Variation
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Q
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse


def store(request, category_slug=None):
    products = None
    if category_slug is not None:
        products = Product.objects.filter(category__slug=category_slug, is_available=True)
        paginator = Paginator(products, 3)
        page = request.GET.get('page')
        paged_products = paginator.get_page(page)
        product_count = products.count()
    else:
        products = Product.objects.all().filter(is_available=True).order_by('id')
        paginator = Paginator(products, 3)
        page = request.GET.get('page')
        paged_products = paginator.get_page(page)
        product_count = products.count()

    context = {
        'products': paged_products,
        'product_count': product_count,
    }
    return render(request, 'store/store.html', context)

def product_detail(request, category_slug, product_slug):
    single_product = get_object_or_404(Product, category__slug=category_slug, slug=product_slug)
    in_cart = CartItem.objects.filter(cart__cart_id=_cart_id(request), product=single_product).exists()
    product = Product.objects.get(category__slug=category_slug, slug=product_slug)
    variations = Variation.objects.filter(product=product, is_active=True)

    if request.user.is_authenticated:
        try:
            orderproduct = OrderProduct.objects.filter(user=request.user, product_id=single_product.id).exists()
        except OrderProduct.DoesNotExist:
            orderproduct = None
    else:
        orderproduct = None

    reviews = ReviewRating.objects.filter(product_id=single_product.id, status=True)
    product_gallery = ProductGallery.objects.filter(product_id=single_product.id)
    product_downloads = ProductDownload.objects.filter(product=single_product)
    viewed_products = request.session.get('viewed_products', [])

    # Group variations by category
    variation_data = {}
    for v in variations:
        category_name = v.category.name if v.category else "Other"
        if category_name not in variation_data:
            variation_data[category_name] = []
        variation_data[category_name].append({
            'id': v.id,
            'value': v.name,
            'price_modifier': float(v.price_modifier),
        })

    if single_product.id not in viewed_products:
        viewed_products.insert(0, single_product.id)
        if len(viewed_products) > 5:
            viewed_products = viewed_products[:5]
        request.session['viewed_products'] = viewed_products

    context = {
        'single_product': single_product,
        'in_cart': in_cart,
        'orderproduct': orderproduct,
        'reviews': reviews,
        'product_gallery': product_gallery,
        'product_downloads': product_downloads,
        'variation_data': variation_data,
    }
    return render(request, 'store/product_detail.html', context)


def search(request):
    if 'keyword' in request.GET:
        keyword = request.GET['keyword']
        if keyword:
            products = Product.objects.order_by('-created_date').filter(
                Q(description__icontains=keyword) | Q(product_name__icontains=keyword)
            )
            product_count = products.count()
        context = {
            'products': products,
            'product_count': product_count,
        }
        return render(request, 'store/store.html', context)


def submit_review(request, product_id):
    url = request.META.get('HTTP_REFERER')
    if request.method == 'POST':
        try:
            reviews = ReviewRating.objects.get(user__id=request.user.id, product__id=product_id)
            form = ReviewForm(request.POST, instance=reviews)
            form.save()
            messages.success(request, 'Thank you!! Your review has been updated !!')
            return redirect(url)
        except ReviewRating.DoesNotExist:
            form = ReviewForm(request.POST)
            if form.is_valid():
                data = ReviewRating()
                data.subject = form.cleaned_data['subject']
                data.rating = form.cleaned_data['rating']
                data.review = form.cleaned_data['review']
                data.ip = request.META.get('REMOTE_ADDR')
                data.product_id = product_id
                data.user_id = request.user.id
                data.save()
                messages.success(request, 'Thank you!! Your review has been Submitted !!')
                return redirect(url)


def brand_detail(request, brand_slug):
    brand = get_object_or_404(Brand, slug=brand_slug)
    products = Product.objects.filter(brand=brand, is_available=True).order_by('id')
    paginator = Paginator(products, 3)
    page = request.GET.get('page')
    paged_products = paginator.get_page(page)
    context = {'brand': brand, 'products': paged_products}
    return render(request, 'store/brand_detail.html', context)

@login_required(login_url='login')
def wishlist(request):
    wishlist_items = Wishlist.objects.filter(user=request.user).order_by('-added_date')
    context = {'wishlist_items': wishlist_items}
    return render(request, 'store/wishlist.html', context)


@csrf_protect
def add_to_wishlist(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    if not request.user.is_authenticated:
        if request.method == 'POST':
            request.session['wishlist_data'] = {
                'product_id': str(product_id),
                'quantity': request.POST.get('quantity', '1'),
                'variations': {key: value for key, value in request.POST.items() if key not in ['csrfmiddlewaretoken', 'quantity']}
            }
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'login_required',
                'message': 'Please sign in to add to wishlist.',
                'redirect': f'/accounts/login/?next=/store/add_to_wishlist/{product_id}/'
            }, status=403)
        messages.error(request, "Please sign in to add to wishlist.")
        return redirect(f'/accounts/login/?next=/store/add_to_wishlist/{product_id}/')

    product_variations = []
    quantity = 1
    if request.method == 'POST':
        quantity = int(request.POST.get('quantity', 1))
        if product.has_variants:
            valid_categories = set(
                Variation.objects.filter(product=product, is_active=True)
                .values_list('category__name', flat=True)
            )
            for key, value in request.POST.items():
                if key in valid_categories:
                    try:
                        variation = Variation.objects.get(
                            product=product,
                            category__name__iexact=key,
                            name__iexact=value,
                            is_active=True
                        )
                        product_variations.append(variation)
                    except Variation.DoesNotExist:
                        continue
            if len(product_variations) != len(valid_categories):
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,  # 👈 added
                        'status': 'error',
                        'message': 'Please select all required variations.'
                    }, status=400)
                messages.error(request, "Please select all required variations.")
                return redirect('/store/wishlist/')

    else:  # GET from next
        wishlist_data = request.session.get('wishlist_data', {})
        if wishlist_data.get('product_id') == str(product_id):
            quantity = int(wishlist_data.get('quantity', 1))
            if product.has_variants:
                valid_categories = set(
                    Variation.objects.filter(product=product, is_active=True).values_list('category', flat=True))
                for key, value in wishlist_data.get('variations', {}).items():
                    if key in valid_categories:
                        try:
                            variation = Variation.objects.get(
                                product=product,
                                category__name__iexact=key,
                                name__iexact=value,
                                is_active=True
                            )
                            product_variations.append(variation)
                        except Variation.DoesNotExist:
                            continue
                if len(product_variations) != len(valid_categories):
                    messages.error(request, "Invalid variations; item added without variations.")

    existing_items = Wishlist.objects.filter(user=request.user, product=product)
    for item in existing_items:
        existing_variations = set(item.variations.all())
        if existing_variations == set(product_variations):
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'exists',
                    'message': 'This item is already in your wishlist.',
                    'in_wishlist': True
                }, status=200)
            messages.info(request, "This item is already in your wishlist.")
            return redirect('/store/wishlist/')

    wishlist_item = Wishlist.objects.create(user=request.user, product=product, quantity=quantity)
    if product_variations:
        wishlist_item.variations.set(product_variations)
    wishlist_item.save()
    if 'wishlist_data' in request.session:
        del request.session['wishlist_data']
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,  # 👈 added
            'status': 'added',
            'message': 'Item added to wishlist!',
            'in_wishlist': True
        }, status=200)
    messages.success(request, "Item added to wishlist!")
    return redirect('/store/wishlist/')


@login_required(login_url='login')
@csrf_protect
def remove_from_wishlist(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    if request.method == 'POST':
        Wishlist.objects.filter(user=request.user, product=product).delete()
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'removed', 'message': 'Removed from wishlist.'})
        return redirect('wishlist')
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'status': 'error', 'message': 'Invalid request.'}, status=400)
    return redirect('wishlist')
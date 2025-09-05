def menu_links(request):
    from category.models import Category
    links = Category.objects.all()
    return dict(links=links)
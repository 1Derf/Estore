from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from . import views
from .views import test_paypal, paypal_payment

urlpatterns = [
    #path('admin/', include('admin_honeypot.urls', namespace='admin_honeypot')),
    path('securelogin/', admin.site.urls),
    path('', views.home, name='home'),
    path('store/', include('store.urls')),
    path('cart/', include('carts.urls')),
    path('accounts/', include('accounts.urls')),
    # path('test-paypal/', test_paypal, name='test_paypal'),
    # path('checkout/', checkout, name='checkout'),
    path('orders/', include('orders.urls')),
    # path('paypal-initiate/', paypal_payment, name='paypal_initiate'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
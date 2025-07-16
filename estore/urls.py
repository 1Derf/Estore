

from django.contrib import admin
from django.urls import path, include
from . import views
from .settings import MEDIA_ROOT
from django.conf.urls.static import static
from django.conf import settings
from .views import test_paypal, paypal_payment  # Adjust import


urlpatterns = ([
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('store/', include('store.urls')),
    path('cart/', include('carts.urls')),
    path('accounts/', include('accounts.urls')),
 #   path('test-paypal/', test_paypal, name='test_paypal'),
   # path('checkout/', checkout, name='checkout'),
    # Orders
    path('orders/', include('orders.urls')),
  #  path('paypal-initiate/', paypal_payment, name='paypal_initiate'),

]
   + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT))

from django.urls import path
from . import views

urlpatterns = [
    path('place_order/', views.place_order, name='place_order'),
    path('payments/', views.payments, name='payments'),
    path('paypal-return/', views.paypal_return, name='paypal_return'),
    path('paypal-cancel/', views.paypal_cancel, name='paypal_cancel'),


]
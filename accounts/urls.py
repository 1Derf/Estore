from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register, name='register'),
    path('accounts/login/', views.login, name='login'),#New may have to be removed
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),
    path('lockout/', views.lockout, name='lockout'),
    path('dashboard/', views.dashboard, name='dashboard'),
   # path('', views.dashboard, name='dashboard'),
    path('activate/<uidb64>/<token>/', views.activate, name='activate'),
    path('forgotPassword/', views.forgotPassword, name='forgotPassword'),
    path('reset_password_validate/<uidb64>/<token>/', views.reset_password_validate, name='reset_password_validate'),
    path('resetPassword/', views.resetPassword, name='resetPassword'),
    path('my_orders/', views.my_orders, name='my_orders'),
    path('edit_profile/', views.edit_profile, name='edit_profile'),
    path('change_password/', views.change_password, name='change_password'),
    path('order_detail/<int:order_id>/', views.order_detail, name='order_detail'),
    path('custom_redirect/', views.custom_redirect, name='custom_redirect'),


]
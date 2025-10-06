from django.contrib.auth.decorators import login_required
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.contrib import messages, auth
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.sites.shortcuts import get_current_site
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from django.template.loader import render_to_string
from django.core.mail import EmailMessage
from carts.utils import _cart_id, migrate_cart_items
from orders.models import Order, OrderProduct
from .forms import RegistrationForm, UserForm, UserProfileForm
from .models import Account, UserProfile
import requests
from django.urls import reverse
from django.db.models import Prefetch




def register(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            try:
                first_name = form.cleaned_data['first_name']
                last_name = form.cleaned_data['last_name']
                phone_number = form.cleaned_data['phone_number']
                email = form.cleaned_data['email']
                password = form.cleaned_data['password']
                username = email.split("@")[0]

                # Create user
                user = Account.objects.create_user(
                    first_name=first_name,
                    last_name=last_name,
                    email=email,
                    password=password,
                    username=username
                )
                user.phone_number = phone_number
                user.save()

                # USER ACTIVATION EMAIL
                current_site = get_current_site(request)
                mail_subject = 'Please activate your account'
                message = render_to_string('accounts/account_verification_email.html', {
                    'user': user,
                    'domain': current_site,
                    'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                    'token': default_token_generator.make_token(user),
                })
                to_email = email
                send_email = EmailMessage(mail_subject, message, to=[to_email])
                send_email.send()

               # messages.success(request, 'Registration successful! Please check your email to activate your account.')
                return redirect('/securelogin/login/?command=verification&email='+email)  # Redirect to login page (or another page)
            except Exception as e:
                messages.error(request, f'Registration failed: {str(e)}')
                return render(request, 'accounts/register.html', {'form': form})
        else:
            # If form is invalid, re-render the form with errors
            messages.error(request, 'Please correct the errors below.')
            return render(request, 'accounts/register.html', {'form': form})
    else:
        # Handle GET request by rendering the empty form
        form = RegistrationForm()
        return render(request, 'accounts/register.html', {'form': form})


def login(request):
    if request.method == 'POST':
        email = request.POST['email']
        password = request.POST['password']
        user = auth.authenticate(request, username=email, password=password)
        if user is not None:
            auth.login(request, user)
            migrate_cart_items(request, user)
            messages.success(request, 'You are now logged in!')
            url = request.META.get('HTTP_REFERER')
            try:
                query = requests.utils.urlparse(url).query
                params = dict(x.split('=') for x in query.split('&'))
                if 'next' in params:
                    nextPage = params['next']
                    if user.is_staff and nextPage.startswith('/securelogin/'):
                        return redirect(nextPage)  # Preserve next for admin
                    return redirect('/accounts/dashboard/')
            except:
                if user.is_staff:
                    return redirect('admin:index')  # Admin dashboard
                return redirect('/accounts/dashboard/')
        else:
            messages.error(request, 'Invalid login credentials.')
            return redirect('login')
    return render(request, 'accounts/login.html')


@login_required(login_url='login')
def logout(request):
    is_admin = request.user.is_staff
    next_url = request.GET.get('next', '/dashboard/')
    auth.logout(request)
    messages.success(request, 'You are logged out!')
    if is_admin:
        return redirect(f'{reverse("admin:login")}?next={next_url}')
    return redirect(f'/accounts/login/?next={next_url}')


def activate(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = Account._default_manager.get(pk=uid)
    except(TypeError, ValueError, OverflowError, Account.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        messages.success(request, 'Congratulations! Your account is activated.')
        return redirect('login')
    else:
        messages.error(request, 'Invalid activation link')
        return redirect('register')

@login_required(login_url='login')
def dashboard(request):
    orders = Order.objects.filter(
        user=request.user
    ).exclude(
        status="New"   # hide only uninitiated orders
    ).order_by('-created_at')
    orders_count = orders.count()

    try:
        userprofile = UserProfile.objects.get(user=request.user.id)
    except UserProfile.DoesNotExist:
        userprofile = UserProfile.objects.create(user=request.user)

    context = {
        'orders': orders,          # 👉 add this so template can loop them
        'orders_count': orders_count,
        'userprofile': userprofile,
    }
    return render(request, 'accounts/dashboard.html', context)



def forgotPassword(request):
    if request.method == 'POST':
        email = request.POST['email']
        if Account.objects.filter(email=email).exists():
            user = Account.objects.get(email__exact=email)
            # Reset password
            current_site = get_current_site(request)
            mail_subject = 'Reset Your Password'
            message = render_to_string('accounts/reset_password.html', {
                'user': user,
                'domain': current_site,
                'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                'token': default_token_generator.make_token(user),
            })
            to_email = email
            send_email = EmailMessage(mail_subject, message, to=[to_email])
            send_email.send()

            messages.success(request, 'An email to reset your password has been sent !!')
            return redirect('login')

        else:
            messages.error(request, 'Account does not exist!')
            return redirect('forgotPassword')
    return render(request, 'accounts/forgotPassword.html')


def reset_password_validate(request, uidb64, token ):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = Account._default_manager.get(pk=uid)
    except(TypeError, ValueError, OverflowError, Account.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        request.session['uid'] = uid
        messages.success(request, 'Please reset your password !!')
        return redirect('resetPassword')
    else:
        messages.error(request, 'This link has expired !')
        return redirect('forgotPassword')


def resetPassword(request):
    if request.method == 'POST':
        password = request.POST['password']
        confirm_password = request.POST['confirm_password']

        if password == confirm_password:
            uid = request.session.get('uid')
            user = Account.objects.get(pk=uid)
            user.set_password(password)
            user.save()
            messages.success(request, 'Password reset Successful !!')
            return redirect('login')

        else:
            messages.error(request, 'Passwords do not match !')
            return  redirect('resetPassword')
    else:
        return render(request, 'accounts/resetPassword.html')

@login_required(login_url='login')
def my_orders(request):
    orders = Order.objects.filter(
        user=request.user
    ).exclude(
        status="New"   # hide only brand new / incomplete orders
    ).order_by('-created_at')

    context = {
        'orders': orders,
    }
    return render(request, 'accounts/my_orders.html', context)

@login_required(login_url='login')
def edit_profile(request):
    userprofile = get_object_or_404(UserProfile, user=request.user)
    if request.method == 'POST':
        user_form = UserForm(request.POST, instance=request.user)
        profile_form = UserProfileForm(request.POST, request.FILES, instance=userprofile)
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, 'Your profile has been updated. Please use your new email to sign in.')
            return redirect('edit_profile')
    else:
        user_form = UserForm(instance=request.user)
        profile_form = UserProfileForm(instance=userprofile)
    context = {
        'user_form': user_form,
        'profile_form': profile_form,
        'userprofile': userprofile,
    }
    return render(request, 'accounts/edit_profile.html', context)

@login_required(login_url='login')
def change_password(request):
    if request.method == 'POST':
        current_password = request.POST['current_password']
        new_password = request.POST['new_password']
        confirm_password = request.POST['confirm_password']

        user = Account.objects.get(username__exact=request.user.username)

        if new_password == confirm_password:
            success = user.check_password(current_password)
            if success:
                user.set_password(new_password)
                user.save()
                # auth.logout(request)
                messages.success(request, 'Password Updated Successfully!')
                return redirect('change_password')
            else:
                messages.error(request, 'Please Enter Valid Current Password.')
                return redirect('change_password')
        else:
            messages.error(request, 'Password Does Not Match!')
            return redirect('change_password')
    return render(request, 'accounts/change_password.html')

@login_required(login_url='login')
def order_detail(request, order_id):
    order = get_object_or_404(Order, order_number=order_id, user=request.user)

    order_detail = OrderProduct.objects.filter(order=order)

    subtotal = sum(i.product_price * i.quantity for i in order_detail)

    context = {
        'order_detail': order_detail,
        'order': order,
        'subtotal': subtotal,
    }
    return render(request, 'accounts/order_detail.html', context)


def custom_redirect(request):
    next_url = request.GET.get('next', '')
    if next_url and next_url.startswith('/securelogin/'):
        return redirect(f'{reverse("admin:login")}?next={next_url}')
    return redirect('/accounts/login/' + (f'?next={next_url}' if next_url else ''))


def lockout(request):
    return render(request, 'accounts/lockout.html', {'message': 'Too many failed login attempts. Try again later.'})
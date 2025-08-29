from django.apps import AppConfig
from django.dispatch import receiver

class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'  # Adjust if needed

    def ready(self):
        from admin_honeypot.signals import honeypot  # Or 'login_failed' if your version uses that
        from .models import BlockedIP

        @receiver(honeypot)
        def auto_block_ip(sender, ip_address, **kwargs):
            attempts = sender.objects.filter(ip_address=ip_address).count()
            if attempts >= 3:  # Auto-block after 3 (adjust to 10 for safe testing)
                BlockedIP.objects.get_or_create(ip_address=ip_address, defaults={'reason': 'Auto-block: Honeypot trap'})




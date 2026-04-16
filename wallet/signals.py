from django.db.models.signals import post_save
from django.dispatch import receiver
from accounts.models import User
from .models import Wallet


@receiver(post_save, sender=User)
def create_admin_wallet(sender, instance, created, **kwargs):
    if instance.is_superuser:
        Wallet.objects.get_or_create(
            user=instance,
            wallet_type="ADMIN"
        )
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings

from voucher.models import Plan


User = settings.AUTH_USER_MODEL


class User(AbstractUser):
    ROLE_CHOICES = (
        ("ADMIN", "Admin"),
        ("USER", "User"),
    )

    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default="USER")
    user_id = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=255)
    sponsor = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="referrals"
    )
    phone = models.CharField(max_length=15, blank=True,null=True)
    is_approved = models.BooleanField(default=False)
    is_wallet_active = models.BooleanField(default=False)

    activation_date = models.DateTimeField(null=True, blank=True)
    deactivation_date = models.DateTimeField(null=True, blank=True)
    commission_processed = models.BooleanField(default=False)
    joined_at = models.DateTimeField(auto_now_add=True)
    is_mlm_active = models.BooleanField(default=True)
    is_root = models.BooleanField(default=False)
    wallet_activated_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.username}"

class Voucher(models.Model):
    code = models.CharField(max_length=50)

    plan = models.ForeignKey(
        Plan,
        on_delete=models.CASCADE,
        related_name="vouchers",
        blank=True,null=True
    )
    
    is_used = models.BooleanField(default=False)

    used_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="used_vouchers"
    )

    used_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    
    class Meta:
        constraints = [
            models.UniqueConstraint(
            fields=['code', 'plan'],
            name='unique_code_per_plan'
         )
        ]

    def __str__(self):
        return self.code

class RegistrationRequest(models.Model):
    STATUS_CHOICES = (
        ("PENDING", "Pending"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
    )

    name = models.CharField(max_length=255)
    password = models.CharField(max_length=255)  # hashed

    sponsor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    # 🔥 KYC data stored here
    aadhaar_front = models.ImageField(upload_to="aadhaar/")
    aadhaar_back = models.ImageField(upload_to="aadhaar/")

    address = models.TextField()
    phone = models.CharField(max_length=15)

    bank_account_number = models.CharField(max_length=50)
    ifsc_code = models.CharField(max_length=20)
    voucher = models.ForeignKey(
    Voucher,
    null=True,
    blank=True,
    on_delete=models.SET_NULL
)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.status}"



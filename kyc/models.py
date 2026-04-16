from django.db import models
from django.conf import settings


User = settings.AUTH_USER_MODEL


class KYC(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="kyc")

    aadhaar_front = models.ImageField(upload_to="aadhaar/")
    aadhaar_back = models.ImageField(upload_to="aadhaar/")

    address = models.TextField()
    phone = models.CharField(max_length=15)

    bank_account_number = models.CharField(max_length=50)
    ifsc_code = models.CharField(max_length=20)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return str(self.user)
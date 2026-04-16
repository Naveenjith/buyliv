from django.db import models

# Create your models here.
class Wallet(models.Model):
    WALLET_TYPE = (
        ("LEVEL", "Level Income"),
        ("PASSIVE", "Passive Income"),
        ("ADMIN", "Admin Wallet"),
    )

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="wallets"
    )

    wallet_type = models.CharField(max_length=10, choices=WALLET_TYPE)

    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    locked_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)


    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} - {self.wallet_type}"

    
class Transaction(models.Model):
    TRANSACTION_TYPE = (
        ("CREDIT", "Credit"),
        ("DEBIT", "Debit"),
    )

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE
    )

    wallet = models.ForeignKey(
        Wallet,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="transactions"
    )

    amount = models.DecimalField(max_digits=10, decimal_places=2)

    related_user = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="related_transactions"
    )

    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPE)

    source = models.CharField(max_length=50)  
    # LEVEL_INCOME / PASSIVE_INCOME / ADMIN / etc

    description = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.description


class LevelCommission(models.Model):
    level = models.IntegerField(unique=True)
    percentage = models.DecimalField(max_digits=5, decimal_places=2)

    class Meta:
        ordering = ["level"]

    def __str__(self):
        return f"Level {self.level} - {self.percentage}%"
    

from django.utils import timezone

class PassiveIncome(models.Model):
    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="passive_incomes"
    )

    amount = models.DecimalField(max_digits=10, decimal_places=2)

    month_number = models.IntegerField()  # 1 → 30

    credited_at = models.DateTimeField(null=True, blank=True)
    unlock_at = models.DateTimeField(null=True, blank=True)

    is_unlocked = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    unlocked_at = models.DateTimeField(null=True, blank=True)
    scheduled_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("user", "month_number")

    def __str__(self):
        return f"{self.user} - Month {self.month_number}"
    

class PayoutRequest(models.Model):
    STATUS_CHOICES = (
        ("PENDING", "Pending"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
    )

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="payout_requests"
    )

    amount = models.DecimalField(max_digits=10, decimal_places=2)

    admin_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    final_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")

    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user} - {self.amount} - {self.status}"
    

class PendingLevelCommission(models.Model):
    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="pending_commissions"
    )

    from_user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="generated_pending_commissions"
    )

    level = models.IntegerField()

    amount = models.DecimalField(max_digits=10, decimal_places=2)

    is_processed = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.user_id} - Level {self.level} - {self.amount}"
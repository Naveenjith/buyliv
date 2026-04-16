from django.utils import timezone
from django.db import transaction

from accounts.utils import is_user_eligible_for_income
from wallet.models import PassiveIncome, Wallet, Transaction


def process_passive_income_unlock():
    now = timezone.now()

    incomes = PassiveIncome.objects.filter(
        credited_at__isnull=False,
        is_unlocked=False,
        unlock_at__lte=now,
    ).select_related("user")

    for income in incomes:
        unlock_passive_income(income.id)


@transaction.atomic
def unlock_passive_income(income_id):

    income = PassiveIncome.objects.select_for_update().get(id=income_id)

    # 🚫 Prevent duplicate
    if income.is_unlocked:
        return

    user = income.user

    # =====================================================
    # 🔥 DELAY (NOT SKIP)
    # =====================================================
    if not is_user_eligible_for_income(user):
        return

    # =====================================================
    # 🔍 WALLET SAFETY
    # =====================================================
    wallet, _ = Wallet.objects.get_or_create(
        user=user,
        wallet_type="PASSIVE"
    )

    now = timezone.now()

    # =====================================================
    # ✅ MARK FIRST (CRITICAL)
    # =====================================================
    income.is_unlocked = True
    income.unlocked_at = now
    income.save(update_fields=["is_unlocked", "unlocked_at"])

    # =====================================================
    # 💰 🔥 MOVE FROM LOCKED → BALANCE (IMPORTANT FIX)
    # =====================================================
    wallet.locked_balance -= income.amount
    wallet.balance += income.amount
    wallet.save(update_fields=["balance", "locked_balance"])

    # =====================================================
    # 🧾 LOG
    # =====================================================
    Transaction.objects.create(
        user=user,
        wallet=wallet,
        amount=income.amount,
        transaction_type="CREDIT",
        source="PASSIVE_UNLOCK",
        description=f"Month {income.month_number} passive income unlocked"
    )
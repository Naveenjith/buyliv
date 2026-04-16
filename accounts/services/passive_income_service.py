from django.utils import timezone
from datetime import timedelta
from django.db import transaction

from wallet.models import PassiveIncome, Transaction, Wallet


def process_passive_income_credit():
    now = timezone.now()

    # ✅ ONLY fetch ready incomes
    incomes = PassiveIncome.objects.filter(
        credited_at__isnull=True,
        scheduled_date__lte=now  # ✅ USE THIS (IMPORTANT)
    ).select_related("user")

    for income in incomes:
        credit_passive_income(income.id)


@transaction.atomic
def credit_passive_income(income_id):

    # 🔒 Lock row
    income = PassiveIncome.objects.select_for_update().get(id=income_id)

    # 🚫 Already processed safety
    if income.credited_at:
        return

    user = income.user

    # =====================================================
    # 🔥 WALLET SAFETY
    # =====================================================
    wallet, _ = Wallet.objects.get_or_create(
        user=user,
        wallet_type="PASSIVE"
    )

    now = timezone.now()

    # =====================================================
    # 🕒 CREDIT INCOME (LOCKED)
    # =====================================================
    income.credited_at = now
    income.unlock_at = now + timedelta(days=30)
    income.save(update_fields=["credited_at", "unlock_at"])

    # =====================================================
    # 💰 🔥 ADD TO LOCKED BALANCE (IMPORTANT FIX)
    # =====================================================
    wallet.locked_balance += income.amount
    wallet.save(update_fields=["locked_balance"])

    # =====================================================
    # 🧾 TRANSACTION (LOCKED INCOME)
    # =====================================================
    Transaction.objects.create(
        user=user,
        wallet=wallet,
        amount=income.amount,
        transaction_type="CREDIT",
        source="PASSIVE_LOCKED",
        description=f"Month {income.month_number} passive income (locked)"
    )
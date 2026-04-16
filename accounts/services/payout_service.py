from decimal import Decimal
from django.db import transaction
from django.utils import timezone

from accounts.utils import is_user_eligible_for_income
from wallet.models import Wallet, Transaction, PayoutRequest
from accounts.models import User


ADMIN_PERCENTAGE = Decimal("10")


@transaction.atomic
def create_payout_request(user, amount):
    amount = Decimal(amount)

    if amount <= 0:
        raise Exception("Invalid amount")

    # =====================================================
    # 🔥 USER ELIGIBILITY
    # =====================================================
    if not is_user_eligible_for_income(user):
        raise Exception("User not eligible for payout")

    if not user.is_wallet_active:
        raise Exception("Wallet is blocked")

    # =====================================================
    # 🔍 GET WALLETS (LOCKED)
    # =====================================================
    level_wallet = Wallet.objects.select_for_update().filter(
        user=user,
        wallet_type="LEVEL"
    ).first()

    passive_wallet = Wallet.objects.select_for_update().filter(
        user=user,
        wallet_type="PASSIVE"
    ).first()

    if not level_wallet and not passive_wallet:
        raise Exception("Wallet not found")

    level_balance = level_wallet.balance if level_wallet else Decimal("0")
    passive_balance = passive_wallet.balance if passive_wallet else Decimal("0")

    total_available = level_balance + passive_balance

    # =====================================================
    # 🔥 VALIDATION
    # =====================================================
    if total_available < amount:
        raise Exception(
            f"Insufficient withdrawable balance. Available: {total_available}"
        )

    # =====================================================
    # 🔒 PREVENT DUPLICATE REQUEST
    # =====================================================
    if PayoutRequest.objects.filter(user=user, status="PENDING").exists():
        raise Exception("You already have a pending payout request")

    # =====================================================
    # 💸 DEDUCTION (PASSIVE → LEVEL)
    # =====================================================
    remaining = amount

    # 1. Deduct from passive wallet
    if passive_wallet and passive_wallet.balance > 0:
        deduct = min(passive_wallet.balance, remaining)
        passive_wallet.balance -= deduct
        passive_wallet.save(update_fields=["balance"])

        Transaction.objects.create(
            user=user,
            wallet=passive_wallet,
            amount=deduct,
            transaction_type="DEBIT",
            source="PAYOUT_REQUEST",
            description="Payout deduction (Passive wallet)"
        )

        remaining -= deduct

    # 2. Deduct from level wallet
    if remaining > 0 and level_wallet:
        level_wallet.balance -= remaining
        level_wallet.save(update_fields=["balance"])

        Transaction.objects.create(
            user=user,
            wallet=level_wallet,
            amount=remaining,
            transaction_type="DEBIT",
            source="PAYOUT_REQUEST",
            description="Payout deduction (Level wallet)"
        )

    # =====================================================
    # 💰 ADMIN CUT
    # =====================================================
    admin_charge = (amount * ADMIN_PERCENTAGE) / Decimal("100")
    final_amount = amount - admin_charge

    payout = PayoutRequest.objects.create(
        user=user,
        amount=amount,
        admin_charge=admin_charge,
        final_amount=final_amount,
        status="PENDING"
    )

    return payout


@transaction.atomic
def process_payout(payout_id, approve=True):

    payout = PayoutRequest.objects.select_for_update().get(id=payout_id)

    if payout.status != "PENDING":
        raise Exception("Already processed")

    user = payout.user

    level_wallet = Wallet.objects.select_for_update().filter(
        user=user,
        wallet_type="LEVEL"
    ).first()

    passive_wallet = Wallet.objects.select_for_update().filter(
        user=user,
        wallet_type="PASSIVE"
    ).first()

    # =====================================================
    # 🔥 ELIGIBILITY CHECK
    # =====================================================
    if not is_user_eligible_for_income(user):

        payout.status = "REJECTED"
        payout.processed_at = timezone.now()
        payout.save()

        return payout

    # =====================================================
    # ❌ REJECT FLOW (REFUND PROPERLY)
    # =====================================================
    if not approve:

        amount = payout.amount
        remaining = amount

        # Refund to level first (reverse of deduction)
        if level_wallet:
            level_wallet.balance += remaining
            level_wallet.save(update_fields=["balance"])

            Transaction.objects.create(
                user=user,
                wallet=level_wallet,
                amount=remaining,
                transaction_type="CREDIT",
                source="PAYOUT_REFUND",
                description="Payout rejected refund (Level wallet)"
            )

        payout.status = "REJECTED"
        payout.processed_at = timezone.now()
        payout.save()

        return payout

    # =====================================================
    # ✅ APPROVED FLOW
    # =====================================================
    admin_user = User.objects.filter(is_superuser=True).first()

    if not admin_user:
        raise Exception("Admin user not found")

    admin_wallet, _ = Wallet.objects.select_for_update().get_or_create(
        user=admin_user,
        wallet_type="ADMIN"
    )

    admin_wallet.balance += payout.admin_charge
    admin_wallet.save(update_fields=["balance"])

    Transaction.objects.create(
        user=admin_user,
        wallet=admin_wallet,
        amount=payout.admin_charge,
        transaction_type="CREDIT",
        source="ADMIN_COMMISSION",
        related_user=user,
        description=f"Payout #{payout.id}"
    )

    payout.status = "APPROVED"
    payout.processed_at = timezone.now()
    payout.save()

    return payout
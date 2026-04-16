from decimal import Decimal
from django.db import transaction
from accounts.utils import is_user_eligible_for_income


@transaction.atomic
def distribute_level_commission(user, plan_amount):
    from wallet.models import Wallet, Transaction, LevelCommission, PendingLevelCommission

    if not user or not user.id:
        return

    if not user.sponsor:
        return

    current_user = user.sponsor
    level = 1

    plan_amount = Decimal(plan_amount)

    while current_user and level <= 10:

        if not current_user.id:
            break

        # 🔍 Get commission config
        commission_config = LevelCommission.objects.filter(level=level).first()

        if not commission_config:
            current_user = current_user.sponsor
            level += 1
            continue

        commission_amount = (
            plan_amount * commission_config.percentage
        ) / Decimal("100")

        if commission_amount <= 0:
            current_user = current_user.sponsor
            level += 1
            continue

        # =====================================================
        # 🔥 CASE 1: USER ELIGIBLE → CREDIT IMMEDIATELY
        # =====================================================
        if is_user_eligible_for_income(current_user):

            wallet, _ = Wallet.objects.get_or_create(
                user=current_user,
                wallet_type="LEVEL"
            )

            wallet.balance += commission_amount
            wallet.save(update_fields=["balance"])

            Transaction.objects.create(
                user=current_user,
                wallet=wallet,
                amount=commission_amount,
                transaction_type="CREDIT",
                source="LEVEL_INCOME",
                related_user=user,
                description=f"Level {level} income from {user.user_id}"
            )

        # =====================================================
        # 🔥 CASE 2: USER NOT ELIGIBLE → STORE PENDING
        # =====================================================
        else:

            PendingLevelCommission.objects.create(
                user=current_user,
                from_user=user,
                level=level,
                amount=commission_amount
            )

        # ⬆️ Move up chain
        current_user = current_user.sponsor
        level += 1
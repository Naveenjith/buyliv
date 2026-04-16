from django.db import transaction
from wallet.models import PendingLevelCommission, Wallet, Transaction
from accounts.utils import is_user_eligible_for_income


@transaction.atomic
def process_pending_commissions_for_user(user):

    # 🔥 Only process if user is eligible
    if not is_user_eligible_for_income(user):
        return

    pending_list = PendingLevelCommission.objects.select_for_update().filter(
        user=user,
        is_processed=False
    )

    if not pending_list.exists():
        return

    # 🔥 Ensure wallet
    wallet, _ = Wallet.objects.get_or_create(
        user=user,
        wallet_type="LEVEL"
    )

    for pending in pending_list:

        # 💰 Credit wallet
        wallet.balance += pending.amount

        # 🧾 Transaction log
        Transaction.objects.create(
            user=user,
            wallet=wallet,
            amount=pending.amount,
            transaction_type="CREDIT",
            source="LEVEL_INCOME",
            related_user=pending.from_user,
            description=f"Level {pending.level} income (delayed) from {pending.from_user.user_id}"
        )

        # ✅ Mark processed
        pending.is_processed = True
        pending.save(update_fields=["is_processed"])

    wallet.save(update_fields=["balance"])
from django.db import transaction

from .models import User
from django.utils import timezone
from datetime import timedelta

def generate_user_id():
    last_user = User.objects.select_for_update().order_by("-id").first()

    if not last_user or not last_user.user_id:
        return "BHT00001"

    try:
        last_number = int(last_user.user_id.replace("BHT", ""))
    except Exception:
        # 🔥 HANDLE BAD DATA IN DB
        return "BHT00001"

    new_number = last_number + 1

    return f"BHT{new_number:05d}"


from django.conf import settings


def generate_referral_link(user):
    base_url = getattr(settings, "FRONTEND_URL")
    return f"{base_url}/api/accounts/register?ref={user.user_id}"

def is_user_eligible_for_income(user):
    if not (
        user.is_mlm_active and
        user.is_wallet_active and
        user.is_approved
    ):
        return False

    from django.conf import settings

    delay = getattr(settings, "INCOME_ELIGIBILITY_DELAY_MINUTES", 1440)

    if user.wallet_activated_at:
        unlock_time = user.wallet_activated_at + timedelta(minutes=delay)
        if timezone.now() < unlock_time:
            return False

    return True

def get_user_status(user):
    if not user.is_mlm_active:
        return "INACTIVE"
    if not user.is_wallet_active:
        return "WALLET_BLOCKED"
    if not user.is_approved:
        return "NOT_APPROVED"
    return "ACTIVE"

from accounts.models import User


def run_mlm_jobs():
    try:
        from accounts.services.wallet_activation_service import activate_wallets
        from accounts.services.pending_commission_service import process_pending_commissions_for_user
        from accounts.services.unlock_service import process_passive_income_unlock
        from accounts.services.passive_income_service import process_passive_income_credit

        # ✅ Activate wallets
        activate_wallets()

        # ✅ Process pending commissions
        users = User.objects.filter(is_wallet_active=True)
        for user in users:
            process_pending_commissions_for_user(user)

        # ✅ Passive credit
        process_passive_income_credit()

        # ✅ Passive unlock
        process_passive_income_unlock()

    except Exception as e:
        print("MLM JOB ERROR:", e)  # 🔥 DO NOT SILENTLY PASS
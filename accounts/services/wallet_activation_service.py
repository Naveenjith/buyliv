from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from django.conf import settings
from django.db import transaction

from accounts.services.pending_commission_service import process_pending_commissions_for_user
from accounts.models import User
from accounts.services.commission_service import distribute_level_commission
from wallet.models import PassiveIncome


def activate_wallets():
    now = timezone.now()

    delay = getattr(settings, "WALLET_ACTIVATION_DELAY_MINUTES", 1440)

    users = User.objects.filter(
        is_wallet_active=False,
        activation_date__isnull=False
    ).order_by("activation_date")

    for user in users:

        unlock_time = user.activation_date + timedelta(minutes=delay)

        if now >= unlock_time:

            with transaction.atomic():

                # =====================================================
                # ✅ ACTIVATE WALLET
                # =====================================================
                user.is_wallet_active = True
                user.wallet_activated_at = now
                user.save(update_fields=["is_wallet_active", "wallet_activated_at"])

                # =====================================================
                # 🔥 FIX PASSIVE SCHEDULE (CRITICAL)
                # =====================================================
                passive_incomes = PassiveIncome.objects.filter(user=user)

                for income in passive_incomes:
                    new_date = user.wallet_activated_at + timedelta(days=30 * income.month_number)

                    income.scheduled_date = new_date
                    income.save(update_fields=["scheduled_date"])

                # =====================================================
                # 🔥 PROCESS PENDING COMMISSIONS
                # =====================================================
                process_pending_commissions_for_user(user)

                # =====================================================
                # 🔥 LEVEL COMMISSION (SAFE USING YOUR FIELD)
                # =====================================================
                if user.sponsor and not user.commission_processed:

                    voucher = user.used_vouchers.first()

                    if voucher and voucher.plan:

                        distribute_level_commission(
                            user,
                            Decimal(voucher.plan.amount)
                        )

                        # ✅ MARK AS PROCESSED (IMPORTANT)
                        user.commission_processed = True
                        user.save(update_fields=["commission_processed"])
from datetime import timedelta

from django.utils import timezone
from django.db import transaction
from decimal import Decimal
from kyc.models import KYC
from accounts.models import User, Voucher
from accounts.utils import generate_user_id
from wallet.models import Wallet, PassiveIncome
from accounts.services.commission_service import distribute_level_commission


@transaction.atomic
def activate_user(registration_request, admin_user):

    # 🔒 Validate request
    if registration_request.status != "PENDING":
        raise Exception("Already processed")

    if not registration_request.voucher:
        raise Exception("Voucher not assigned")

    # 🔒 Lock voucher
    voucher = Voucher.objects.select_for_update().get(
        id=registration_request.voucher.id
    )

    if voucher.is_used:
        raise Exception("Voucher already used")

    plan = voucher.plan

    # ✅ Generate user ID FIRST
    new_user_id = generate_user_id()

    if User.objects.filter(user_id=new_user_id).exists():
        raise Exception("User ID conflict, try again")

    now=timezone.now()
    # ✅ CREATE USER FIRST (IMPORTANT)
    user = User.objects.create(
        username=new_user_id,
        user_id=new_user_id,
        name=registration_request.name,
        phone=registration_request.phone,
        sponsor=registration_request.sponsor,
        is_approved=True,
        is_wallet_active=False,
        activation_date=now,
        wallet_activated_at=None
    )

    # 🔐 Set password properly
    user.set_password(registration_request.password)
    user.save()

    # ✅ CREATE KYC AFTER USER EXISTS
    KYC.objects.create(
        user=user,
        aadhaar_front=registration_request.aadhaar_front,
        aadhaar_back=registration_request.aadhaar_back,
        address=registration_request.address,
        phone=registration_request.phone,
        bank_account_number=registration_request.bank_account_number,
        ifsc_code=registration_request.ifsc_code
    )

    # ✅ Mark voucher used
    voucher.is_used = True
    voucher.used_by = user
    voucher.used_at = timezone.now()
    voucher.save()

    # ✅ Create wallets
    create_wallets(user, plan)

    # ✅ Passive schedule
    create_passive_schedule(user, plan)


    # ✅ Update request
    registration_request.status = "APPROVED"
    registration_request.save()

    return user


def create_wallets(user, plan):
    # LEVEL wallet (for all users)
    Wallet.objects.create(user=user, wallet_type="LEVEL")

    # PASSIVE wallet (only if plan allows)
    if plan.has_passive_income:
        Wallet.objects.create(user=user, wallet_type="PASSIVE")


def create_passive_schedule(user, plan):
    if not plan.has_passive_income:
        return
    
    if not user.sponsor:
        return
    
    existing = PassiveIncome.objects.filter(user=user).exists()
    if existing:
        return

    passive_entries = []

    base_date = user.activation_date  # ✅ base

    for month in range(0, 30):
        scheduled_date = base_date + timedelta(days=30 * month)

        passive_entries.append(
            PassiveIncome(
                user=user,
                amount=plan.passive_income_amount,
                month_number=month,
                scheduled_date=scheduled_date,  # ✅ IMPORTANT
                credited_at=None,
                unlock_at=None,
                is_unlocked=False,
            )
        )

    PassiveIncome.objects.bulk_create(passive_entries)
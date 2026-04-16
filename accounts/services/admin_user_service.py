from datetime import timedelta

from django.utils import timezone
from django.db import transaction
from decimal import Decimal
from accounts.models import User
from accounts.utils import generate_user_id
from wallet.models import Wallet, PassiveIncome


from kyc.models import KYC

@transaction.atomic
def create_user_by_admin(
    name,
    phone,
    password,
    sponsor,
    voucher,
    aadhaar_front,
    aadhaar_back,
    address,
    bank_account_number,
    ifsc_code
):
    plan = voucher.plan

    # 🔒 Generate user_id
    user_id = generate_user_id()

    # 🔒 Prevent duplicate phone
    if User.objects.filter(phone=phone).exists():
        raise Exception("User with this phone already exists")

    # 🔥 ROOT USER CHECK
    is_root = sponsor is None

    # ✅ Create user
    now = timezone.now()

    user = User.objects.create(
        username=user_id,
        user_id=user_id,
        name=name,
        phone=phone,
        sponsor=sponsor,
        is_approved=True,
        is_wallet_active=False,

    # 🔥 approval time
    activation_date=now,

    # 🔥 wallet not active yet
    wallet_activated_at=None
)

    user.set_password(password)
    user.save()

    # ✅ CREATE KYC
    KYC.objects.create(
        user=user,
        aadhaar_front=aadhaar_front,
        aadhaar_back=aadhaar_back,
        address=address,
        phone=phone,
        bank_account_number=bank_account_number,
        ifsc_code=ifsc_code
    )

    # ✅ Mark voucher used
    voucher.is_used = True
    voucher.used_by = user
    voucher.used_at = timezone.now()
    voucher.save()

    # ✅ Wallets
    Wallet.objects.create(user=user, wallet_type="LEVEL")

    if plan.has_passive_income:
        Wallet.objects.create(user=user, wallet_type="PASSIVE")

    # ✅ Prevent duplicate passive creation
    if plan.has_passive_income and sponsor is not None and user.is_mlm_active:

        if PassiveIncome.objects.filter(user=user).exists():
            return user

        base_date = user.activation_date
        
        PassiveIncome.objects.bulk_create([
            PassiveIncome(
                user=user,
                amount=plan.passive_income_amount,
                month_number=month,
                scheduled_date=base_date + timedelta(days=30 * month),
                credited_at=None,
                unlock_at=None,
                is_unlocked=False,
            )
            for month in range(0, 30)
        ])
    return user
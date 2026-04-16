import re

from rest_framework import serializers
from django.db import transaction,IntegrityError

from wallet.models import PayoutRequest
from .models import User,RegistrationRequest
from .utils import generate_user_id
from kyc.models import KYC
from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.hashers import make_password
from rest_framework import serializers
from .models import Voucher


class LoginSerializer(serializers.Serializer):
    user_id = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        user_id = data.get("user_id", "").strip()
        password = data.get("password")

        if not user_id or not password:
            raise serializers.ValidationError("User ID and password are required")

        user = authenticate(username=user_id, password=password)

        if not user:
            raise serializers.ValidationError("Invalid credentials")

        # =====================================================
        # 🔥 HARD BLOCKS
        # =====================================================

        if not user.is_active:
            raise serializers.ValidationError("Account is deactivated")

        if not user.is_mlm_active:
            raise serializers.ValidationError("MLM account is inactive")

        # Admin bypass
        if not user.is_staff:
            if not user.is_approved:
                raise serializers.ValidationError("Account not approved yet")

            if not user.is_wallet_active:
                raise serializers.ValidationError("Wallet not activated yet")

        data["user"] = user
        return data

class RegisterSerializer(serializers.Serializer):
    referral_code = serializers.CharField(write_only=True, required=False)

    name = serializers.CharField()
    password = serializers.CharField(write_only=True)

    aadhaar_front = serializers.ImageField()
    aadhaar_back = serializers.ImageField()
    address = serializers.CharField()
    phone = serializers.CharField()
    bank_account_number = serializers.CharField()
    ifsc_code = serializers.CharField()

    def validate(self, data):
        referral_code = data.get("referral_code")

        sponsor = None

        if referral_code:
            sponsor = User.objects.filter(
                user_id=referral_code,
                is_approved=True,
                is_active=True
            ).first()

            if not sponsor:
                raise serializers.ValidationError("Invalid or inactive referral")

        data["sponsor_obj"] = sponsor
        return data

    def validate_phone(self, value):
        if not re.match(r'^\d{10}$', value):
            raise serializers.ValidationError("Invalid phone number")
        return value
    
    def validate_password(self, value):
        if len(value) != 6:
            raise serializers.ValidationError(
            "Password must be exactly 6 characters long."
            )
        return value
    
    
    def validate_ifsc_code(self, value):
        if not re.match(r'^[A-Z]{4}0[A-Z0-9]{6}$', value):
            raise serializers.ValidationError("Invalid IFSC code")
        return value

    def create(self, validated_data):
        sponsor = validated_data.pop("sponsor_obj", None)
        validated_data.pop("referral_code", None)

        validated_data["password"] = make_password(validated_data["password"])

        return RegistrationRequest.objects.create(
            sponsor=sponsor,
            **validated_data
        )
    
#User list
class UserListSerializer(serializers.ModelSerializer):
    sponsor_name = serializers.CharField(source="sponsor.user_id", read_only=True)

    # ✅ FIXED
    joined_at = serializers.DateTimeField(read_only=True)

    activation_date = serializers.DateTimeField(read_only=True)

    voucher_code = serializers.SerializerMethodField()
    is_mlm_active = serializers.BooleanField()

    class Meta:
        model = User
        fields = [
            "id",
            "user_id",
            "name",
            "phone",
            "is_approved",
            "is_wallet_active",
            "is_mlm_active",
            "joined_at",
            "activation_date",
            "sponsor_name",
            "voucher_code",
        ]

    def get_voucher_code(self, obj):
        vouchers = getattr(obj, "used_vouchers", None)

        if vouchers:
            first = vouchers.all()[0] if vouchers.all() else None
            return first.code if first else "-"

        return "-"

class UserDetailSerializer(serializers.ModelSerializer):
    sponsor_name = serializers.CharField(source="sponsor.user_id", read_only=True)
    voucher_code = serializers.SerializerMethodField()
    bank_account_number = serializers.CharField(source="kyc.bank_account_number", read_only=True)
    ifsc_code = serializers.CharField(source="kyc.ifsc_code", read_only=True)
    address = serializers.CharField(source="kyc.address", required=False)
    aadhaar_front = serializers.ImageField(source="kyc.aadhaar_front", required=False)
    aadhaar_back = serializers.ImageField(source="kyc.aadhaar_back", required=False)
    is_mlm_active = serializers.BooleanField()

    class Meta:
        model = User
        fields = [
        "id",
        "user_id",
        "name",
        "phone",
        "is_approved",
        "is_wallet_active",
        "activation_date",
        "is_mlm_active",
        "sponsor_name",
        "bank_account_number",
        "ifsc_code",
        "voucher_code",
        "aadhaar_front",
        "aadhaar_back",
        "address"
        ]
        read_only_fields = [
        "id",
        "user_id",          # ✅ FIX
        "activation_date",
        "sponsor_name",
        "bank_account_number",
        "ifsc_code",
        "voucher_code",
        "aadhaar_front",
        "aadhaar_back",
        "address"
        ]
    def get_voucher_code(self, obj):
        vouchers = getattr(obj, "used_vouchers", None)

        if vouchers:
            first = vouchers.all()[0] if vouchers.all() else None
            return first.code if first else "-"

        return "-"
    
    def update(self, instance, validated_data):
        kyc_data = validated_data.pop("kyc", {})

        # 🔹 Update user fields
        instance.name = validated_data.get("name", instance.name)
        instance.phone = validated_data.get("phone", instance.phone)
        instance.is_wallet_active = validated_data.get("is_wallet_active", instance.is_wallet_active)
        instance.is_approved = validated_data.get("is_approved", instance.is_approved)
        instance.save()

        # 🔹 Update KYC
        if kyc_data:
            kyc, _ = KYC.objects.get_or_create(user=instance)

            for field, value in kyc_data.items():
                setattr(kyc, field, value)

            kyc.save()

        return instance
        
#request list and details
class RegistrationRequestSerializer(serializers.ModelSerializer):
    sponsor_name = serializers.CharField(source="sponsor.username", read_only=True)

    class Meta:
        model = RegistrationRequest
        fields = [
            "id",
            "name",
            "phone",
            "address",
            "voucher",
            "status",
            "created_at",
            "aadhaar_front",
            "aadhaar_back",
            "bank_account_number",
            "ifsc_code",
            "sponsor",
            "sponsor_name",
        ]



class VoucherSerializer(serializers.ModelSerializer):
    plan_name = serializers.CharField(source="plan.name", read_only=True)
    plan_amount = serializers.SerializerMethodField()
    has_passive_income = serializers.SerializerMethodField()
    passive_income_amount = serializers.SerializerMethodField()

    class Meta:
        model = Voucher
        fields = [
            "id",
            "code",
            "plan",
            "plan_name",
            "is_used",
            "created_at",
            "plan_amount",
            "has_passive_income",
            "passive_income_amount"
        ]

        validators=[]

    def get_plan_amount(self, obj):
        return obj.plan.amount if obj.plan else None

    def get_has_passive_income(self, obj):
        return obj.plan.has_passive_income if obj.plan else False

    def get_passive_income_amount(self, obj):
        return obj.plan.passive_income_amount if obj.plan else None

    def validate(self, data):
        code = data.get("code")
        plan = data.get("plan")
        instance = self.instance

        # Check for uniqueness manually to provide a clean error
        qs = Voucher.objects.filter(code=code, plan=plan)
        if instance:
            qs = qs.exclude(id=instance.id)

        if qs.exists():
            # This will return {"code": "..."} instead of non_field_errors
            raise serializers.ValidationError({
                "code": "This voucher already exists for this plan."
            })

        return data

#for frontend apis 
class KYCSerializer(serializers.ModelSerializer):
    aadhaar_front = serializers.SerializerMethodField()
    aadhaar_back = serializers.SerializerMethodField()

    class Meta:
        model = KYC
        fields = [
            "address",
            "bank_account_number",
            "ifsc_code",
            "aadhaar_front",
            "aadhaar_back",
        ]

    def get_aadhaar_front(self, obj):
        request = self.context.get("request")
        if obj.aadhaar_front:
            return request.build_absolute_uri(obj.aadhaar_front.url)
        return None

    def get_aadhaar_back(self, obj):
        request = self.context.get("request")
        if obj.aadhaar_back:
            return request.build_absolute_uri(obj.aadhaar_back.url)
        return None

class ProfileSerializer(serializers.ModelSerializer):
    kyc = KYCSerializer(required=False)

    class Meta:
        model = User
        fields = [
            "user_id",
            "username",
            "name",
            "phone",
            "kyc"
        ]
        read_only_fields = ["user_id", "username"]

    def update(self, instance, validated_data):
        request = self.context.get("request")

        # 🔹 Extract KYC data
        kyc_data = validated_data.pop("kyc", {})

            # 🔹 ALSO accept flat fields (important improvement)
        flat_kyc_fields = ["address", "bank_account_number", "ifsc_code"]

        for field in flat_kyc_fields:
            if field in request.data:
                kyc_data[field] = request.data.get(field)

        # 🔹 Update user
        instance.name = validated_data.get("name", instance.name)
        instance.phone = validated_data.get("phone", instance.phone)
        instance.save()

        # 🔹 Update/create KYC
        if kyc_data:
            kyc, _ = KYC.objects.get_or_create(user=instance)

            for attr, value in kyc_data.items():
                setattr(kyc, attr, value)

            kyc.save()

        return instance


#dawnlines
class DownlineUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["user_id", "name", "phone", "is_active"]

#payout
class PayoutSerializer(serializers.ModelSerializer):
    user_id = serializers.CharField(source="user.user_id")

    class Meta:
        model = PayoutRequest
        fields = [
            "id",
            "user_id",
            "amount",
            "admin_charge",
            "final_amount",
            "status",
            "created_at"
        ]


#change password

class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, min_length=6)

class AdminResetPasswordSerializer(serializers.Serializer):
    new_password = serializers.CharField(required=True)

    def validate_new_password(self, value):
        if len(value) != 6:
            raise serializers.ValidationError("Password must be exactly 6 characters")
        return value
from rest_framework import serializers
from wallet.models import LevelCommission, PayoutRequest, Transaction, Wallet


class PayoutRequestCreateSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero")

        # 🔒 Optional: minimum withdrawal rule
        if value < 100:
            raise serializers.ValidationError("Minimum payout amount is 100")

        return value



class PayoutRequestSerializer(serializers.ModelSerializer):
    user_id = serializers.CharField(source="user.user_id", read_only=True)
    user_name = serializers.CharField(source="user.name", read_only=True)

    class Meta:
        model = PayoutRequest
        fields = [
            "id",
            "user_id",
            "user_name",
            "amount",
            "admin_charge",
            "final_amount",
            "status",
            "created_at",
            "processed_at",
        ]

class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = [
            "id",
            "amount",
            "transaction_type",
            "source",
            "description",
            "created_at"
        ]


class WalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wallet
        fields = ["wallet_type", "balance"]


class TransactionSerializer(serializers.ModelSerializer):
    wallet_type = serializers.CharField(source="wallet.wallet_type")
    related_user_id = serializers.CharField(source="related_user.user_id", default=None)

    class Meta:
        model = Transaction
        fields = [
            "id",
            "amount",
            "transaction_type",
            "wallet_type",
            "source",
            "description",
            "related_user_id",
            "created_at",
        ]


class LevelCommissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = LevelCommission
        fields = ["id", "level", "percentage"]

    def validate_level(self, value):
        if value <= 0:
            raise serializers.ValidationError("Level must be positive")
        return value

    def validate_percentage(self, value):
        if value <= 0 or value > 100:
            raise serializers.ValidationError("Percentage must be between 0 and 100")
        return value
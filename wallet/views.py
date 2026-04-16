from django.shortcuts import render

# Create your views here.
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.permissions import IsAdminUser
from accounts.models import User
from accounts.permissions import IsAdminUserCustom
from accounts.utils import run_mlm_jobs
from wallet.models import LevelCommission, PayoutRequest, Transaction, Wallet
from wallet.pagination import AdminTransactionPagination, TransactionPagination
from wallet.serializers import LevelCommissionSerializer, PayoutRequestCreateSerializer, PayoutRequestSerializer, TransactionSerializer
from accounts.services.payout_service import create_payout_request, process_payout
from django.db.models import Sum
from rest_framework.generics import ListAPIView, ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.permissions import IsAdminUser
from django.utils.dateparse import parse_date



def get_admin_wallet():
    admin = User.objects.filter(is_superuser=True).first()
    if not admin:
        return None, None

    wallet = Wallet.objects.filter(
        user=admin,
        wallet_type="ADMIN"
    ).first()

    return admin, wallet


class CreatePayoutRequestAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PayoutRequestCreateSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        amount = serializer.validated_data["amount"]
        user = request.user

        # 🔍 Get wallets
        level_wallet = Wallet.objects.filter(user=user, wallet_type="LEVEL").first()
        passive_wallet = Wallet.objects.filter(user=user, wallet_type="PASSIVE").first()

        if not passive_wallet:
            return Response({"error": "Passive wallet not found"}, status=400)

        available_balance = passive_wallet.balance
        locked_balance = passive_wallet.locked_balance
        total_balance = available_balance + locked_balance

        # =====================================================
        # 🔥 HARD CHECK (AVAILABLE ONLY)
        # ====================================================

        try:
            payout = create_payout_request(user, amount)
        except Exception as e:
            return Response({
                "error": str(e),
                "available_balance": float(available_balance),
                "locked_balance": float(locked_balance),
                "total_balance": float(total_balance)
            }, status=400)

        # =====================================================
        # 🔄 REFRESH WALLET AFTER DEDUCTION
        # =====================================================
        passive_wallet.refresh_from_db()

        return Response({
            "message": "Payout request created successfully",
            "payout_id": payout.id,
            "amount": str(payout.amount),
            "admin_charge": str(payout.admin_charge),
            "final_amount": str(payout.final_amount),
            "status": payout.status,

            # 🔥 NEW: WALLET INFO
            "wallet": {
                "available": float(passive_wallet.balance),
                "locked": float(passive_wallet.locked_balance),
                "total": float(passive_wallet.balance + passive_wallet.locked_balance)
            }
        }, status=201)





# 🔹 1. LIST ALL PAYOUT REQUESTS
class PayoutRequestListAPIView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        payouts = PayoutRequest.objects.all().order_by("-created_at")
        serializer = PayoutRequestSerializer(payouts, many=True)
        return Response(serializer.data)


# 🔹 2. APPROVE PAYOUT
class ApprovePayoutAPIView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        try:
            payout = process_payout(pk, approve=True)
        except Exception as e:
            return Response({"error": str(e)}, status=400)

        return Response({
            "message": "Payout approved successfully",
            "payout_id": payout.id,
            "status": payout.status
        })


# 🔹 3. REJECT PAYOUT
class RejectPayoutAPIView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        try:
            payout = process_payout(pk, approve=False)
        except Exception as e:
            return Response({"error": str(e)}, status=400)

        return Response({
            "message": "Payout rejected successfully",
            "payout_id": payout.id,
            "status": payout.status
        })
    

class AdminWalletAPIView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        admin = User.objects.filter(is_superuser=True).first()

        wallet = Wallet.objects.filter(
            user=admin,
            wallet_type="ADMIN"
        ).first()

        if not wallet:
            return Response({"error": "Admin wallet not found"}, status=404)

        total_credits = Transaction.objects.filter(
            wallet=wallet,
            transaction_type="CREDIT"
        ).aggregate(total=Sum("amount"))["total"] or 0

        total_debits = Transaction.objects.filter(
            wallet=wallet,
            transaction_type="DEBIT"
        ).aggregate(total=Sum("amount"))["total"] or 0

        return Response({
            "balance": wallet.balance,
            "total_credited": total_credits,
            "total_debited": total_debits,
        })
    

class AdminTransactionListAPIView(ListAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = TransactionSerializer

    def get_queryset(self):
        admin = User.objects.filter(is_superuser=True).first()

        wallet = Wallet.objects.filter(
            user=admin,
            wallet_type="ADMIN"
        ).first()

        return Transaction.objects.filter(wallet=wallet).order_by("-created_at")
    

class AdminPayoutEarningsAPIView(ListAPIView):
    permission_classes = [IsAdminUser]
    pagination_class = AdminTransactionPagination

    def get_queryset(self):
        admin = User.objects.filter(is_superuser=True).first()

        wallet = Wallet.objects.filter(
            user=admin,
            wallet_type="ADMIN"
        ).first()

        qs = Transaction.objects.filter(
            wallet=wallet,
            source="ADMIN_COMMISSION"
        ).select_related("related_user").order_by("-created_at")

        # 🔍 FILTER: User search
        user_id = self.request.GET.get("user")
        if user_id:
            qs = qs.filter(related_user__user_id__icontains=user_id)

        # 📅 FILTER: Date range
        start_date = self.request.GET.get("start_date")
        end_date = self.request.GET.get("end_date")

        if start_date:
            qs = qs.filter(created_at__date__gte=parse_date(start_date))

        if end_date:
            qs = qs.filter(created_at__date__lte=parse_date(end_date))

        return qs

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        total = queryset.aggregate(total=Sum("amount"))["total"] or 0

        page = self.paginate_queryset(queryset)

        data = [
            {
                "amount": float(t.amount),
                "from_user": t.related_user.user_id if t.related_user else None,
                "date": t.created_at,
                "description": t.description,
            }
            for t in page
        ]

        return self.get_paginated_response({
            "total_earnings": float(total),
            "transactions": data
        })
    
def admin_earnings(request):
    return render(request, "admin/payout_earnings.html")


class UserWalletAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        
        run_mlm_jobs()
        user = request.user

        wallets = Wallet.objects.filter(user=user)

        # 🔹 Initialize
        level_wallet = None
        passive_wallet = None

        for wallet in wallets:
            if wallet.wallet_type == "LEVEL":
                level_wallet = wallet
            elif wallet.wallet_type == "PASSIVE":
                passive_wallet = wallet

        # 🔥 Ensure wallets exist
        if not level_wallet:
            level_wallet = Wallet.objects.create(user=user, wallet_type="LEVEL")

        if not passive_wallet:
            passive_wallet = Wallet.objects.create(user=user, wallet_type="PASSIVE")

        # =====================================================
        # 🔥 CALCULATIONS (UPDATED)
        # =====================================================

        level_balance = level_wallet.balance

        passive_available = passive_wallet.balance
        passive_locked = passive_wallet.locked_balance

        total_balance = level_balance + passive_available + passive_locked

        # =====================================================
        # 🔥 RESPONSE
        # =====================================================
        from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from wallet.models import Wallet, PassiveIncome
from accounts.utils import run_mlm_jobs


class UserWalletAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):

        run_mlm_jobs()

        user = request.user

        wallets = Wallet.objects.filter(user=user)

        level_wallet = None
        passive_wallet = None

        for wallet in wallets:
            if wallet.wallet_type == "LEVEL":
                level_wallet = wallet
            elif wallet.wallet_type == "PASSIVE":
                passive_wallet = wallet

        # Ensure wallets exist
        if not level_wallet:
            level_wallet = Wallet.objects.create(user=user, wallet_type="LEVEL")

        if not passive_wallet:
            passive_wallet = Wallet.objects.create(user=user, wallet_type="PASSIVE")

        # =====================================================
        # 🔥 BALANCES
        # =====================================================

        level_balance = level_wallet.balance

        passive_available = passive_wallet.balance
        passive_locked = passive_wallet.locked_balance

        total_balance = level_balance + passive_available + passive_locked
        withdrawable_balance = level_balance + passive_available

        # =====================================================
        # 🔥 NEXT UNLOCK INFO (IMPORTANT UX)
        # =====================================================

        next_unlock = PassiveIncome.objects.filter(
            user=user,
            is_unlocked=False,
            credited_at__isnull=False
        ).order_by("unlock_at").first()

        next_unlock_data = None

        if next_unlock:
            next_unlock_data = {
                "amount": float(next_unlock.amount),
                "unlock_at": next_unlock.unlock_at
            }

        # =====================================================
        # 🔥 RESPONSE (CLEAR + CLIENT SAFE)
        # =====================================================

        return Response({
            "level_wallet": {
                "balance": float(level_balance),
                "description": "Direct earnings (fully withdrawable)"
            },

            "passive_wallet": {
                "available": float(passive_available),
                "locked": float(passive_locked),
                "total": float(passive_available + passive_locked),
                "description": "Passive income (locked for 30 days)"
            },

            "summary": {
                "total_earnings": float(total_balance),
                "withdrawable": float(withdrawable_balance),
                "locked": float(passive_locked)
            },

            "next_unlock": next_unlock_data
        })
    
class UserTransactionHistoryAPIView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = TransactionSerializer
    pagination_class = TransactionPagination

    def get_queryset(self):
        user = self.request.user

        qs = Transaction.objects.filter(user=user).select_related(
            "wallet", "related_user"
        ).order_by("-created_at")

        # 🔍 Filter: wallet type
        wallet_type = self.request.GET.get("wallet_type")
        if wallet_type:
            qs = qs.filter(wallet__wallet_type=wallet_type)

        # 🔍 Filter: transaction type
        transaction_type = self.request.GET.get("transaction_type")
        if transaction_type:
            qs = qs.filter(transaction_type=transaction_type)

        # 📅 Filter: date range
        start_date = self.request.GET.get("start_date")
        end_date = self.request.GET.get("end_date")

        if start_date:
            qs = qs.filter(created_at__date__gte=parse_date(start_date))

        if end_date:
            qs = qs.filter(created_at__date__lte=parse_date(end_date))

        return qs
    

#level and %
class LevelCommissionListCreateAPIView(ListCreateAPIView):
    queryset = LevelCommission.objects.all()
    serializer_class = LevelCommissionSerializer
    permission_classes = [IsAuthenticated, IsAdminUserCustom]


class LevelCommissionDetailAPIView(RetrieveUpdateDestroyAPIView):
    queryset = LevelCommission.objects.all()
    serializer_class = LevelCommissionSerializer
    permission_classes = [IsAuthenticated, IsAdminUserCustom]

def admin_levels_page(request):
    return render(request, "admin/level.html")



# views.py

from openpyxl import Workbook
from django.http import HttpResponse
from wallet.models import PayoutRequest


class ExportPayoutExcelAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):

        payouts = PayoutRequest.objects.select_related("user").all().order_by("-created_at")

        # 🔥 Create workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "Payouts"

        # Header
        ws.append([
            "User ID",
            "Amount",
            "Admin Charge",
            "Final Amount",
            "Status",
            "Created At"
        ])

        # Data
        for p in payouts:
            ws.append([
                p.user.user_id,
                float(p.amount),
                float(p.admin_charge),
                float(p.final_amount),
                p.status,
                p.created_at.strftime("%Y-%m-%d %H:%M:%S")
            ])

        # Response
        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = "attachment; filename=payouts.xlsx"

        wb.save(response)
        return response
from datetime import datetime
from django.shortcuts import get_object_or_404, render,redirect
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib import messages
from accounts.models import RegistrationRequest, User, Voucher
from accounts.pagination import AdminPayoutPagination, StandardResultsSetPagination
from accounts.permissions import IsAdminUserCustom
from accounts.services.activation_service import activate_user
from accounts.services.admin_user_service import create_user_by_admin
from accounts.services.dawnline_service import get_downline
from accounts.services.payout_service import process_payout
from accounts.utils import generate_referral_link
from voucher.models import Plan
from wallet.models import PayoutRequest
from .serializers import AdminResetPasswordSerializer, ChangePasswordSerializer, DownlineUserSerializer, PayoutSerializer, ProfileSerializer, RegisterSerializer, RegistrationRequestSerializer, UserDetailSerializer, UserListSerializer
from .serializers import LoginSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import IsAuthenticated
from rest_framework.permissions import AllowAny
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.contrib.auth import authenticate, login,logout
from django.db import transaction
from django.utils import timezone
from rest_framework.generics import RetrieveUpdateAPIView,ListAPIView
from rest_framework.generics import *
from rest_framework.permissions import IsAuthenticated
from accounts.permissions import IsAdminUserCustom
from .models import Voucher
from .serializers import VoucherSerializer
from django.db.models import Prefetch
from rest_framework.permissions import IsAdminUser
from accounts.utils import run_mlm_jobs


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):

        run_mlm_jobs()

        serializer = LoginSerializer(data=request.data)

        if serializer.is_valid():
            user = serializer.validated_data["user"]

            refresh = RefreshToken.for_user(user)

            # =====================================================
            # 🔥 GET USER PLAN
            # =====================================================
            voucher = user.used_vouchers.first()

            plan_data = None

            if voucher and voucher.plan:
                plan = voucher.plan
                plan_data = {
                    "id": plan.id,
                    "name": getattr(plan, "name", ""),
                    "amount": float(plan.amount),
                    "passive_income": float(plan.passive_income_amount) if plan.has_passive_income else 0,
                    "has_passive": plan.has_passive_income
                }

            return Response({
                "refresh": str(refresh),
                "access": str(refresh.access_token),

                "user": {
                    "user_id": user.user_id,
                    "name": user.name,
                    "is_active": user.is_active,
                    "is_mlm_active": user.is_mlm_active,
                    "is_wallet_active": user.is_wallet_active,
                },

                "plan": plan_data
            })

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class AdminLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")

        user = authenticate(username=username, password=password)

        if not user:
            return Response({"error": "Invalid credentials"}, status=400)

        if not user.is_staff:
            return Response({"error": "Not authorized"}, status=403)

        refresh = RefreshToken.for_user(user)

        return Response({
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "username": user.username
        })

class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")

            if not refresh_token:
                return Response({"error": "Refresh token missing"}, status=400)

            token = RefreshToken(refresh_token)
            token.blacklist()

            return Response({"message": "Logged out successfully"})
        
        except Exception as e:
            print("Logout error:", str(e))  # DEBUG
            return Response({"error": "Invalid token"}, status=400)


def admin_login_page(request):
    return render(request, "admin/login.html")
#register
class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save()

            return Response({
                "message": "Registration submitted. Waiting for admin approval."
            }, status=201)

        return Response(serializer.errors, status=400)
    
#refferral Link
class ReferralLinkView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # optional: block unapproved users
        if not user.is_approved:
            return Response(
                {"error": "User not approved yet"},
                status=400
            )

        referral_link = generate_referral_link(user)

        return Response({
            "user_id": user.user_id,
            "referral_link": referral_link
        })
    
def register_page(request):
    referral_code = request.GET.get("ref", "")

    if request.method == "POST":
        data = request.POST.copy()

        # attach files
        for key, file in request.FILES.items():
            data[key] = file

        serializer = RegisterSerializer(data=data)

        if serializer.is_valid():
            serializer.save()

            return render(request, "register_success.html", {
                "message": "Request is sended. Waiting for admin approval."
            })

        return render(request, "register.html", {
            "errors": serializer.errors,
            "referral_code": referral_code,
            "data": request.POST
        })

    return render(request, "register.html", {
        "referral_code": referral_code
    })

def register_success(request):
    return render(request, "register_success.html")


#admin dashboard

class AdminDashboardAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUserCustom]

    def get(self, request):
        return Response({
            "total_users": User.objects.count(),
            "pending_requests": RegistrationRequest.objects.filter(status="PENDING").count(),
            "approved_requests": RegistrationRequest.objects.filter(status="APPROVED").count(),
            "used_vouchers": Voucher.objects.filter(is_used=True).count(),
            "unused_vouchers": Voucher.objects.filter(is_used=False).count(),
        })
    
def admin_dashboard_page(request):
    return render(request, "admin/dashboard.html")

from rest_framework.filters import SearchFilter
#userlist and details
class UserListAPIView(ListAPIView):
    serializer_class = UserListSerializer
    permission_classes = [IsAuthenticated, IsAdminUserCustom]
    pagination_class = StandardResultsSetPagination 

    filter_backends = [SearchFilter]
    search_fields = ["name", "user_id"]

    def get_queryset(self):
        return (
            User.objects
            .select_related("sponsor")
            .only(
                "id",
                "user_id",
                "name",
                "phone",
                "is_approved",
                "is_wallet_active",
                "is_mlm_active",
                "joined_at",
                "activation_date",
                "sponsor"
            )
            .prefetch_related(
                Prefetch(
                    "used_vouchers",
                    queryset=Voucher.objects.only("id", "code"),
                )
            )
            .order_by("-joined_at")
        )
    
from rest_framework.parsers import MultiPartParser, FormParser

class UserDetailAPIView(RetrieveUpdateAPIView):
    serializer_class = UserDetailSerializer
    permission_classes = [IsAuthenticated, IsAdminUserCustom]
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        return (
            User.objects
            .select_related("sponsor")
            .prefetch_related("kyc")
        )

def admin_users_page(request):
    return render(request, "admin/user_list.html")

def admin_user_detail_page(request, pk):
    return render(request, "admin/user_detail.html", {"user_id": pk})

#registartion request list and detail 
class PendingRequestsAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUserCustom]

    def get(self, request):
        qs = RegistrationRequest.objects.filter(status="PENDING").order_by("-created_at")
        serializer = RegistrationRequestSerializer(qs, many=True)
        return Response(serializer.data)
    

class RegistrationRequestDetailAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUserCustom]

    def get(self, request, pk):
        obj = get_object_or_404(RegistrationRequest, pk=pk)
        serializer = RegistrationRequestSerializer(obj)
        return Response(serializer.data)
    
def admin_pending_page(request):
    return render(request, "admin/request_list.html")

def admin_request_detail_page(request, pk):
    return render(request, "admin/request_details.html", {"request_id": pk})
#request approve and reject
class ApproveRequestAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUserCustom]

    @transaction.atomic
    def post(self, request, pk):
        obj = get_object_or_404(RegistrationRequest, pk=pk)

        if obj.status != "PENDING":
            return Response({"error": "Already processed"}, status=400)

        voucher_id = request.data.get("voucher_id")

        if not voucher_id:
            return Response({"error": "Voucher required"}, status=400)

        try:
            voucher = Voucher.objects.select_for_update().get(id=voucher_id)
        except Voucher.DoesNotExist:
            return Response({"error": "Invalid voucher"}, status=400)

        if voucher.is_used:
            return Response({"error": "Voucher already used"}, status=400)

        # ✅ Assign voucher directly
        obj.voucher = voucher
        obj.save()

        try:
            user = activate_user(obj, request.user)
        except Exception as e:
            return Response({"error": str(e)}, status=400)

        return Response({
            "message": "Approved successfully",
            "user_id": user.id
        })
    

class RejectRequestAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUserCustom]

    def post(self, request, pk):
        obj = get_object_or_404(RegistrationRequest, pk=pk)

        if obj.status != "PENDING":
            return Response({"error": "Already processed"}, status=400)

        obj.status = "REJECTED"
        obj.save()

        return Response({"message": "Request rejected"})
    


class AdminCreateUserAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUserCustom]

    @transaction.atomic
    def post(self, request):

        # 🔹 TEXT DATA
        name = request.data.get("name")
        phone = request.data.get("phone")
        password = request.data.get("password")
        sponsor_id = request.data.get("sponsor_id")  # can be None
        voucher_id = request.data.get("voucher_id")

        address = request.data.get("address")
        bank_account_number = request.data.get("bank_account_number")
        ifsc_code = request.data.get("ifsc_code")

        # 🔹 FILES
        aadhaar_front = request.FILES.get("aadhaar_front")
        aadhaar_back = request.FILES.get("aadhaar_back")

        # 🔥 CHECK MLM ROOT
        is_root_user = sponsor_id is None

        # 🔒 REQUIRED VALIDATION (voucher removed from here intentionally)
        required_fields = [
            name, phone, password,
            address, bank_account_number, ifsc_code,
            aadhaar_front, aadhaar_back
        ]

        if not all(required_fields):
            return Response({"error": "All fields required"}, status=400)

        # =========================================================
        # 🔥 FIX 1: CLEAN SPONSOR (NO MORE INT ERROR HERE)
        # =========================================================
        if not sponsor_id or sponsor_id in ["", "null", "undefined"]:
            sponsor_id = None

        sponsor = None

        if sponsor_id:
            try:
                sponsor_id = int(sponsor_id)
            except (ValueError, TypeError):
                return Response({"error": "Invalid sponsor format"}, status=400)

            sponsor = User.objects.filter(id=sponsor_id).first()

            if not sponsor:
                return Response({"error": "Invalid sponsor"}, status=400)

            if not sponsor.is_mlm_active:
                return Response({"error": "Sponsor is inactive"}, status=400)

            if not sponsor.is_wallet_active:
                return Response({"error": "Sponsor wallet inactive"}, status=400)

        # =========================================================
        # 🔥 FIX 2: CLEAN VOUCHER (THIS WAS YOUR REAL BUG)
        # =========================================================
        if not voucher_id or voucher_id in ["", "null", "undefined"]:
            return Response({"error": "Voucher is required"}, status=400)

        try:
            voucher_id = int(voucher_id)
        except (ValueError, TypeError):
            return Response({"error": "Invalid voucher format"}, status=400)

        voucher = Voucher.objects.select_for_update().filter(id=voucher_id).first()

        if not voucher:
            return Response({"error": "Invalid voucher"}, status=400)

        if voucher.is_used:
            return Response({"error": "Voucher already used"}, status=400)

        if not voucher.plan:
            return Response({"error": "Voucher has no plan assigned"}, status=400)

        # =========================================================
        # 🔒 PASSWORD VALIDATION
        # =========================================================
        if len(password) != 6:
            return Response({"error": "Password must be exactly 6 characters"}, status=400)

        # =========================================================
        # 🔥 CREATE USER
        # =========================================================
        try:
            user = create_user_by_admin(
                name=name,
                phone=phone,
                password=password,
                sponsor=sponsor,  # None for root user
                voucher=voucher,
                aadhaar_front=aadhaar_front,
                aadhaar_back=aadhaar_back,
                address=address,
                bank_account_number=bank_account_number,
                ifsc_code=ifsc_code
            )
        except Exception as e:
            return Response({"error": str(e)}, status=400)

        # =========================================================
        # 🔥 MARK ROOT USER
        # =========================================================
        if is_root_user:
            user.is_root = True
            user.save(update_fields=["is_root"])

        return Response({
            "message": "User created successfully",
            "user_id": user.user_id,
            "is_root": user.is_root
        })
    
def admin_create_user_page(request):
    return render(request, "admin/admin_create_user.html")


class VoucherListCreateAPIView(ListCreateAPIView):
    queryset = Voucher.objects.all().order_by("-created_at")
    serializer_class = VoucherSerializer
    permission_classes = [IsAuthenticated, IsAdminUserCustom]


class VoucherDetailAPIView(RetrieveUpdateDestroyAPIView):
    queryset = Voucher.objects.all()
    serializer_class = VoucherSerializer
    permission_classes = [IsAuthenticated, IsAdminUserCustom]

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()

        if instance.is_used:
            return Response(
                {"error": "Cannot delete used voucher"},
                status=400
            )

        return super().destroy(request, *args, **kwargs)
    
def admin_create_voucher_page(request):
    return render(request, "admin/voucher_list.html")


#profile api
class ProfileAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        run_mlm_jobs()
        serializer = ProfileSerializer(
            request.user,
            context={"request": request}   
        )
        return Response(serializer.data)

    def put(self, request):
        run_mlm_jobs()
        serializer = ProfileSerializer(
            request.user,
            data=request.data,
            partial=True,
            context={"request": request}   
        )

        if serializer.is_valid():
            serializer.save()
            return Response({
                "message": "Profile updated successfully",
                "data": serializer.data
            })

        return Response(serializer.errors, status=400)
    
#dawnline
class DownlineAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        downline_data = get_downline(user)

        return Response(downline_data)
    

#admin payout
class AdminPayoutListAPIView(ListAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = PayoutSerializer
    pagination_class = AdminPayoutPagination

    def get_queryset(self):
        qs = PayoutRequest.objects.select_related("user").order_by("-created_at")

        # 🔹 Query params
        user = self.request.query_params.get("user")
        status = self.request.query_params.get("status")
        from_date = self.request.query_params.get("from_date")
        to_date = self.request.query_params.get("to_date")

        # 🔍 USER FILTER
        if user:
            qs = qs.filter(user__user_id__icontains=user.strip())

        # 🔍 STATUS FILTER (CASE-INSENSITIVE + SAFE)
        if status and status.upper() != "ALL":
            qs = qs.filter(status__iexact=status.strip())

        # 🔍 DATE FILTERS (STRICT + SAFE)
        try:
            if from_date:
                from_date_parsed = datetime.strptime(from_date, "%Y-%m-%d").date()
                qs = qs.filter(created_at__date__gte=from_date_parsed)

            if to_date:
                to_date_parsed = datetime.strptime(to_date, "%Y-%m-%d").date()
                qs = qs.filter(created_at__date__lte=to_date_parsed)

        except ValueError:
            # ❌ Invalid date format → ignore filters instead of crashing
            pass

        return qs


class AdminPayoutActionAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUserCustom]

    def post(self, request, pk):
        action = request.data.get("action")

        if action not in ["approve", "reject"]:
            return Response({"error": "Invalid action"}, status=400)

        try:
            payout = process_payout(pk, approve=(action == "approve"))
            return Response({"message": f"Payout {action}d successfully"})
        except Exception as e:
            return Response({"error": str(e)}, status=400)
        
def admin_payout_page(request):
    return render(request, "admin/payout_list.html")


#change password by user
class ChangePasswordAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        user = request.user

        # 🔒 check old password
        if not user.check_password(serializer.validated_data["old_password"]):
            return Response({"error": "Old password incorrect"}, status=400)

        # 🔒 set new password
        user.set_password(serializer.validated_data["new_password"])
        user.save()

        return Response({"message": "Password changed successfully"})
    

class AdminResetPasswordAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUserCustom]

    def post(self, request, pk):
        serializer = AdminResetPasswordSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=404)

        user.set_password(serializer.validated_data["new_password"])
        user.save()

        return Response({"message": "Password reset successfully"})
    

#user deactivation
class ToggleUserMLMStatusAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUserCustom]

    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)

        # 🔥 Prevent admin self-deactivation (important)
        if user == request.user:
            return Response({"error": "You cannot deactivate yourself"}, status=400)

        user.is_mlm_active = not user.is_mlm_active

        if not user.is_mlm_active:
            user.deactivation_date = timezone.now()
        else:
            user.deactivation_date = None

        user.save()

        return Response({
            "message": "User status updated",
            "is_mlm_active": user.is_mlm_active
        })
    
class MLMRootCheckAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUserCustom]

    def get(self, request):
        has_root = User.objects.filter(is_root=True).exists()
        return Response({"has_root": has_root})
from django.urls import path
from .views import AdminCreateUserAPIView, AdminDashboardAPIView, AdminLoginView, AdminPayoutActionAPIView, AdminPayoutListAPIView, AdminResetPasswordAPIView, ApproveRequestAPIView, ChangePasswordAPIView, DownlineAPIView, LoginView, LogoutView, MLMRootCheckAPIView, PendingRequestsAPIView, ProfileAPIView, ReferralLinkView, RegisterView, RegistrationRequestDetailAPIView, RejectRequestAPIView, ToggleUserMLMStatusAPIView, UserDetailAPIView, UserListAPIView, VoucherDetailAPIView, VoucherListCreateAPIView, admin_create_user_page, admin_create_voucher_page, admin_dashboard_page, admin_login_page, admin_payout_page, admin_pending_page, admin_request_detail_page, admin_user_detail_page, admin_users_page, register_page, register_success
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path("login/", LoginView.as_view(),name='login'),
    path("admin/login/", admin_login_page),
    path("api/admin/login/", AdminLoginView.as_view()),
    
    path("logout/", LogoutView.as_view(),name='logout'),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("register/", register_page), 
    path("success/", register_success),
    path("register/frontend/", RegisterView.as_view(), name="register"),
    path("referral-link/", ReferralLinkView.as_view(),name='refferal-link'),
    path("api/admin/dashboard/", AdminDashboardAPIView.as_view()),
    path("panel/dashboard/", admin_dashboard_page),

    #users list and details by admin
    path("admin/users/", UserListAPIView.as_view()),
    path("admin/users/<int:pk>/", UserDetailAPIView.as_view()),
    path("admin/create-user/", AdminCreateUserAPIView.as_view()),
    path("panel/create-user/", admin_create_user_page),
    # TEMPLATE PAGES (NEW)
    path("panel/users/", admin_users_page),
    path("panel/users/<int:pk>/", admin_user_detail_page),

    #request list,detail,approve,reject
    path("admin/pending-requests/", PendingRequestsAPIView.as_view()),
    path("admin/request/<int:pk>/", RegistrationRequestDetailAPIView.as_view()),
    # templates pages
    path("panel/pending/", admin_pending_page),
    path("panel/request/<int:pk>/", admin_request_detail_page), 

    path("admin/request/<int:pk>/approve/", ApproveRequestAPIView.as_view()),
    path("admin/request/<int:pk>/reject/", RejectRequestAPIView.as_view()),

    #voucher
    path("admin/vouchers/", VoucherListCreateAPIView.as_view()),
    path("admin/vouchers/<int:pk>/", VoucherDetailAPIView.as_view()),
    path("panel/vouchers/",admin_create_voucher_page),

    #profile
    path("profile/", ProfileAPIView.as_view()),
    #dawnlines
    path("downline/", DownlineAPIView.as_view()),

    #payout
    path("admin/payouts/", admin_payout_page),
    path("payout/list/", AdminPayoutListAPIView.as_view()),
    path("payout/action/<int:pk>/", AdminPayoutActionAPIView.as_view()),

    #change pass
    path("change-password/", ChangePasswordAPIView.as_view()),
    path("admin/users/<int:pk>/reset-password/", AdminResetPasswordAPIView.as_view()),  
    #deactivate user
    path("admin/users/<int:pk>/toggle-mlm/", ToggleUserMLMStatusAPIView.as_view()),
    path("admin/mlm-root-check/", MLMRootCheckAPIView.as_view()),
]
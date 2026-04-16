from django.urls import path
from wallet.views import ApprovePayoutAPIView, CreatePayoutRequestAPIView, ExportPayoutExcelAPIView, LevelCommissionDetailAPIView, LevelCommissionListCreateAPIView, PayoutRequestListAPIView, RejectPayoutAPIView,AdminPayoutEarningsAPIView, UserTransactionHistoryAPIView, UserWalletAPIView,admin_earnings, admin_levels_page

urlpatterns = [
    path("payout/request/", CreatePayoutRequestAPIView.as_view()),

    # Admin APIs
    path("payout/list/", PayoutRequestListAPIView.as_view()),
    path("payout/<int:pk>/approve/", ApprovePayoutAPIView.as_view()),
    path("payout/<int:pk>/reject/", RejectPayoutAPIView.as_view()),
    path("payout/payout-earnings/",AdminPayoutEarningsAPIView.as_view()),
    path("payout/earnings/", admin_earnings),
    path("user-wallet/", UserWalletAPIView.as_view()),
    path("transactions/", UserTransactionHistoryAPIView.as_view()),
    #levels
    path("admin/levels/", LevelCommissionListCreateAPIView.as_view()),
    path("admin/levels/<int:pk>/", LevelCommissionDetailAPIView.as_view()),
    # UI
    path("panel/levels/", admin_levels_page),
    path("payout/export/", ExportPayoutExcelAPIView.as_view()),
]
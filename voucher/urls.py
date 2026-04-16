from django.urls import path
from voucher.views import PlanDetailAPIView, PlanListCreateAPIView, admin_plan_page

urlpatterns = [
    path("plans/", PlanListCreateAPIView.as_view()),
     path("plans/<int:pk>/", PlanDetailAPIView.as_view()),
    path("panel/plans/", admin_plan_page),
]
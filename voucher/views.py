from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import render
from accounts.permissions import IsAdminUserCustom
from voucher.models import Plan
from voucher.serializers import PlanSerializer


class PlanListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUserCustom]

    def get(self, request):
        plans = Plan.objects.all().order_by("-id")
        serializer = PlanSerializer(plans, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = PlanSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        serializer.save()

        return Response({"message": "Plan created successfully"})


def admin_plan_page(request):
    return render(request, "admin/plan.html")

# 🔥 NEW — UPDATE + DELETE
class PlanDetailAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUserCustom]

    def put(self, request, pk):
        plan = Plan.objects.filter(id=pk).first()

        if not plan:
            return Response({"error": "Plan not found"}, status=404)

        serializer = PlanSerializer(plan, data=request.data, partial=True)

        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        serializer.save()

        return Response({"message": "Plan updated successfully"})

    def delete(self, request, pk):
        plan = Plan.objects.filter(id=pk).first()

        if not plan:
            return Response({"error": "Plan not found"}, status=404)

        # 🚨 SAFETY CHECK (IMPORTANT)
        if plan.vouchers.exists():
            return Response({
                "error": "Cannot delete plan. It is already used by vouchers."
            }, status=400)

        plan.delete()

        return Response({"message": "Plan deleted successfully"})
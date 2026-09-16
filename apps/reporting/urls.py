from django.urls import path

from .views import FinanceDashboardStatsView, OccupancyReportView, PoliceReportView, XReportView, ZReportView

urlpatterns = [
    path("reports/police/", PoliceReportView.as_view(), name="report-police"),
    path("reports/x-report/", XReportView.as_view(), name="report-x"),
    path("reports/z-report/", ZReportView.as_view(), name="report-z"),
    path("reports/occupancy/", OccupancyReportView.as_view(), name="report-occupancy"),
    path("finance/stats/", FinanceDashboardStatsView.as_view(), name="finance-stats"),
]

from django.urls import path

from . import views

app_name = "reports"
urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("jobs/<uuid:pk>/select/", views.select_report, name="select-report"),
    path("jobs/<uuid:pk>/configure/", views.configure_report, name="configure-report"),
    path("jobs/<uuid:pk>/", views.job_detail, name="job-detail"),
    path("jobs/<uuid:pk>/result.html", views.result_html, name="result-html"),
    path("jobs/<uuid:pk>/result.pdf", views.result_pdf, name="result-pdf"),
]

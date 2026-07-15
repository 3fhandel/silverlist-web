from django.contrib import admin

from .models import ReportJob


@admin.register(ReportJob)
class ReportJobAdmin(admin.ModelAdmin):
    list_display = ("id", "report_key", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("report_key",)
    readonly_fields = ("created_at", "finished_at")

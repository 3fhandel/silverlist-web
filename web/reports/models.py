import uuid

from django.db import models


class ReportJob(models.Model):
    class Status(models.TextChoices):
        UPLOADED = "uploaded", "Hochgeladen"
        INSPECTED = "inspected", "Berichte erkannt"
        PROCESSING = "processing", "Wird verarbeitet"
        SUCCEEDED = "succeeded", "Fertig"
        FAILED = "failed", "Fehlgeschlagen"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    report_key = models.SlugField(max_length=100, blank=True)
    detected_header = models.JSONField(default=list, blank=True)
    source_file = models.FileField(upload_to="jobs/%Y/%m/%d/source/")
    parameters = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.UPLOADED
    )
    error_message = models.TextField(blank=True)
    result_html = models.FileField(upload_to="jobs/%Y/%m/%d/result/", blank=True)
    result_pdf = models.FileField(upload_to="jobs/%Y/%m/%d/result/", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class ReportJobSource(models.Model):
    job = models.ForeignKey(ReportJob, related_name="additional_sources", on_delete=models.CASCADE)
    name = models.SlugField(max_length=80)
    source_file = models.FileField(upload_to="jobs/%Y/%m/%d/source/")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["job", "name"], name="unique_job_source")]

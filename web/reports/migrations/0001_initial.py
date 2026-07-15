# Generated for the initial SilverLists Web schema.

import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="ReportJob",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("silverlists", "SilverLists"),
                            ("ordersatz", "Ordersatz"),
                        ],
                        max_length=20,
                    ),
                ),
                ("report_key", models.SlugField(max_length=100)),
                ("source_file", models.FileField(upload_to="jobs/%Y/%m/%d/source/")),
                ("parameters", models.JSONField(blank=True, default=dict)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("uploaded", "Hochgeladen"),
                            ("processing", "Wird verarbeitet"),
                            ("succeeded", "Fertig"),
                            ("failed", "Fehlgeschlagen"),
                        ],
                        default="uploaded",
                        max_length=20,
                    ),
                ),
                ("error_message", models.TextField(blank=True)),
                (
                    "result_html",
                    models.FileField(blank=True, upload_to="jobs/%Y/%m/%d/result/"),
                ),
                (
                    "result_pdf",
                    models.FileField(blank=True, upload_to="jobs/%Y/%m/%d/result/"),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={"ordering": ["-created_at"]},
        )
    ]

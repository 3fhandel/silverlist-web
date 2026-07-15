from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("reports", "0002_unify_report_pipeline")]
    operations = [
        migrations.CreateModel(
            name="ReportJobSource",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.SlugField(max_length=80)),
                ("source_file", models.FileField(upload_to="jobs/%Y/%m/%d/source/")),
                ("job", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="additional_sources", to="reports.reportjob")),
            ],
        ),
        migrations.AddConstraint(
            model_name="reportjobsource",
            constraint=models.UniqueConstraint(fields=("job", "name"), name="unique_job_source"),
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("reports", "0001_initial")]
    operations = [
        migrations.RemoveField(model_name="reportjob", name="kind"),
        migrations.AlterField(model_name="reportjob", name="report_key", field=models.SlugField(blank=True, max_length=100)),
        migrations.AddField(model_name="reportjob", name="detected_header", field=models.JSONField(blank=True, default=list)),
        migrations.AlterField(
            model_name="reportjob", name="status",
            field=models.CharField(
                choices=[("uploaded", "Hochgeladen"), ("inspected", "Berichte erkannt"), ("processing", "Wird verarbeitet"), ("succeeded", "Fertig"), ("failed", "Fehlgeschlagen")],
                default="uploaded", max_length=20,
            ),
        ),
    ]

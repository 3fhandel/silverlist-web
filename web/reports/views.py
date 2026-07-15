from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render

from .catalog import get_catalog, get_definition, matching_definitions
from .forms import ReportConfigurationForm, ReportSelectionForm, UploadForm
from .models import ReportJob, ReportJobSource
from .services.duckdb_engine import inspect_csv_header
from .services.processor import process_job


def dashboard(request):
    if request.method == "POST":
        form = UploadForm(request.POST, request.FILES)
        if form.is_valid():
            job = form.save()
            try:
                job.detected_header = list(inspect_csv_header(job.source_file.path))
                job.status = ReportJob.Status.INSPECTED
            except Exception as exc:
                job.status = ReportJob.Status.FAILED
                job.error_message = str(exc)
            job.save()
            return redirect("reports:select-report", pk=job.pk)
    else:
        form = UploadForm()
    return render(request, "reports/dashboard.html", {
        "form": form, "catalog": get_catalog(), "jobs": ReportJob.objects.all()[:12]
    })


def select_report(request, pk):
    job = get_object_or_404(ReportJob, pk=pk)
    candidates = matching_definitions(tuple(job.detected_header))
    keys = [item.key for item in candidates]
    form = ReportSelectionForm(request.POST or None, candidates=keys)
    if request.method == "POST" and form.is_valid():
        job.report_key = form.cleaned_data["report_key"]
        job.save(update_fields=["report_key"])
        definition = get_definition(job.report_key)
        needs_configuration = any(
            item["type"] in {"userText", "userBool", "userSelect"}
            for item in definition.variables
        ) or bool(definition.additional_sources)
        if needs_configuration:
            return redirect("reports:configure-report", pk=job.pk)
        process_job(job)
        return redirect("reports:job-detail", pk=job.pk)
    return render(request, "reports/select_report.html", {
        "job": job, "candidates": candidates, "form": form
    })


def configure_report(request, pk):
    job = get_object_or_404(ReportJob, pk=pk)
    definition = get_definition(job.report_key)
    form = ReportConfigurationForm(
        request.POST or None, request.FILES or None, definition=definition
    )
    if request.method == "POST" and form.is_valid():
        parameters = {}
        for name, value in form.cleaned_data.items():
            if name.startswith("source__"):
                ReportJobSource.objects.update_or_create(
                    job=job, name=name.removeprefix("source__"),
                    defaults={"source_file": value},
                )
            else:
                parameters[name] = value
        job.parameters = parameters
        job.save(update_fields=["parameters"])
        process_job(job)
        return redirect("reports:job-detail", pk=job.pk)
    return render(request, "reports/configure_report.html", {
        "job": job, "definition": definition, "form": form,
    })


def job_detail(request, pk):
    job = get_object_or_404(ReportJob, pk=pk)
    try:
        definition = get_definition(job.report_key) if job.report_key else None
    except KeyError:
        definition = None
    return render(request, "reports/job_detail.html", {
        "job": job, "definition": definition,
    })


def result_html(request, pk):
    job = get_object_or_404(ReportJob, pk=pk)
    if not job.result_html:
        raise Http404("Für diesen Auftrag liegt kein HTML-Ergebnis vor.")
    return FileResponse(
        job.result_html.open("rb"), content_type="text/html; charset=utf-8",
        filename=f"{job.report_key}.html",
        as_attachment=request.GET.get("download") == "1",
    )


def result_pdf(request, pk):
    job = get_object_or_404(ReportJob, pk=pk)
    if not job.result_pdf:
        raise Http404("Für diesen Auftrag liegt kein PDF-Ergebnis vor.")
    return FileResponse(
        job.result_pdf.open("rb"), content_type="application/pdf",
        filename=f"{job.report_key}.pdf",
        as_attachment=request.GET.get("download") == "1",
    )

from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from PIL import Image, UnidentifiedImageError

from .catalog import get_catalog, get_definition, matching_definitions
from .forms import (
    ReportConfigurationForm, ReportSelectionForm, UploadForm,
    WeeklyOfferConfigurationForm,
)
from .models import ReportJob, ReportJobSource
from .services.duckdb_engine import inspect_csv_header
from .services.processor import process_job


def _weekly_image_source_name(product_id) -> str:
    return f"weekly-image-{product_id}"


def _validate_weekly_image(upload):
    if upload.size > 20 * 1024 * 1024:
        raise ValueError(f"{upload.name}: Produktbilder dürfen höchstens 20 MB groß sein.")
    if not upload.name.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
        raise ValueError(f"{upload.name}: Unterstützt werden PNG, JPEG und WebP.")
    try:
        Image.open(upload).verify()
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError(f"{upload.name}: Die Datei ist kein gültiges Produktbild.") from exc
    finally:
        upload.seek(0)


def _attach_weekly_images(job, products, files):
    sources = {
        source.name: source for source in job.additional_sources.filter(
            name__startswith="weekly-image-"
        )
    }
    for product in products:
        name = _weekly_image_source_name(product["id"])
        upload = files.get(f"image_{product['id']}")
        if upload:
            _validate_weekly_image(upload)
            source = sources.get(name) or ReportJobSource(job=job, name=name)
            if source.pk and source.source_file:
                source.source_file.delete(save=False)
            source.source_file.save(upload.name, upload, save=True)
            sources[name] = source
        if name in sources:
            product["image"] = sources[name].source_file.path
    return products


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
        needs_configuration = definition.renderer == "weekly-offer" or any(
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
    if definition.renderer == "weekly-offer":
        from .report_modules.weekly_offer import default_validity, load_products

        products = load_products(job.source_file.path)
        image_sources = {
            source.name: source for source in job.additional_sources.filter(
                name__startswith="weekly-image-"
            )
        }
        for product in products:
            source = image_sources.get(_weekly_image_source_name(product["id"]))
            if source:
                product["image"] = source.source_file.path
        initial = {
            "design": job.parameters.get("design", "fruechte"),
            "validity": job.parameters.get("validity", default_validity(products)),
        }
        for saved in job.parameters.get("products", []):
            suffix = saved.get("id")
            if suffix is None:
                continue
            initial.update({
                f"slot_{suffix}": saved.get("slot", ""),
                f"description_{suffix}": saved.get("description", ""),
                f"price_{suffix}": saved.get("price", ""),
                f"unit_{suffix}": saved.get("unit", ""),
            })
        form = WeeklyOfferConfigurationForm(
            request.POST or None,
            products=products,
            initial_validity=default_validity(products),
            initial=initial,
        )
        if request.method == "POST" and form.is_valid():
            try:
                selected_products = _attach_weekly_images(
                    job, form.cleaned_data["selected_products"], request.FILES,
                )
            except ValueError as exc:
                form.add_error(None, str(exc))
                selected_products = None
            if selected_products is None:
                pass
            else:
                job.parameters = {
                    "design": form.cleaned_data["design"],
                    "validity": form.cleaned_data["validity"],
                    "products": selected_products,
                }
                job.save(update_fields=["parameters"])
                process_job(job)
                return redirect("reports:job-detail", pk=job.pk)
        product_rows = [{
            "product": product,
            "slot": form[f"slot_{product['id']}"],
            "description": form[f"description_{product['id']}"],
            "price": form[f"price_{product['id']}"],
            "unit": form[f"unit_{product['id']}"],
        } for product in products]
        return render(request, "reports/configure_weekly_offer.html", {
            "job": job, "definition": definition, "form": form,
            "product_rows": product_rows,
        })
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

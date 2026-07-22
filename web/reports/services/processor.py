from collections import OrderedDict
from dataclasses import replace
from pathlib import Path

from django.core.files.base import ContentFile
from django.template.loader import render_to_string
from django.utils import timezone

from reports.catalog import get_definition
from reports.models import ReportJob
from reports.services.duckdb_engine import execute_report
from reports.services.pdf_renderer import (
    render_address_labels_pdf, render_generic_pdf, render_ordersatz_pdf,
)


def _ordersatz_context(job: ReportJob, columns, rows) -> dict:
    positions = [dict(zip(columns, row, strict=True)) for row in rows]
    grouped: OrderedDict[str, list[dict]] = OrderedDict()
    for position in positions:
        group = str(position.pop("Warengruppe"))
        grouped.setdefault(group, []).append(position)
    return {
        "job": job,
        "groups": grouped.items(),
        "position_count": len(positions),
    }


def _table_context(definition, result) -> dict:
    options = definition.options or {}
    hidden = set(options.get("hidden_columns", ()))
    hidden.update(group["column"] for group in definition.groups if not group.get("show_column"))
    columns = [column for column in result.columns if column not in hidden]
    indexes = {column: result.columns.index(column) for column in result.columns}
    rules = options.get("conditional_styles", ())
    rows = []
    for row in result.rows:
        cells = []
        for column in columns:
            css_class = ""
            for rule in rules:
                if (rule.get("target_column") == column and
                        row[indexes[rule["when_column"]]] == rule.get("equals")):
                    css_class = rule.get("style", "")
                    break
            cells.append({"value": row[indexes[column]], "css_class": css_class})
        rows.append(cells)
    total_row = options.get("total_row")
    if total_row:
        def total_value(column):
            value = str(total_row.get(column, ""))
            for name, variable in result.variables.items():
                value = value.replace("{{ " + name + " }}", str(variable or ""))
            return value

        rows.append([
            {"value": total_value(column), "css_class": "total-row"}
            for column in columns
        ])
    configured_widths = options.get("column_width_weights", {})
    weights = [float(configured_widths.get(column, 1)) for column in columns]
    total = sum(weights) or 1
    column_widths = [weight / total * 100 for weight in weights]
    return {
        "columns": columns, "display_rows": rows,
        "column_widths": column_widths,
    }


def process_job(job: ReportJob) -> ReportJob:
    """Verarbeitet einen gespeicherten Auftrag synchron und idempotent neu."""
    job.status = ReportJob.Status.PROCESSING
    job.error_message = ""
    job.finished_at = None
    job.save(update_fields=["status", "error_message", "finished_at"])

    try:
        definition = get_definition(job.report_key)
        if definition.renderer == "weekly-offer":
            from reports.report_modules.weekly_offer import render_pdf

            context = {"job": job, "definition": definition, **job.parameters}
            template = "reports/results/weekly_offer.html"
            pdf = render_pdf(job.parameters)
            result = None
        elif definition.renderer == "ordersatz":
            from reports.report_modules.ordersatz import query_for

            definition = replace(
                definition,
                query=query_for(definition, tuple(job.detected_header)),
            )

            result = execute_report(
                Path(job.source_file.path), definition, job.parameters,
                {source.name: source.source_file.path for source in job.additional_sources.all()},
            )
        else:
            result = execute_report(
                Path(job.source_file.path), definition, job.parameters,
                {source.name: source.source_file.path for source in job.additional_sources.all()},
            )
        if definition.renderer == "weekly-offer":
            pass
        elif definition.renderer == "ordersatz":
            context = _ordersatz_context(job, result.columns, result.rows)
            template = "reports/results/ordersatz.html"
            pdf = render_ordersatz_pdf(context["groups"], context["position_count"])
        elif definition.renderer in {"generic-table", "grouped-table", "address-labels"}:
            context = {
                "job": job, "definition": definition, "columns": result.columns,
                "rows": result.rows, "variables": result.variables,
            }
            context.update(_table_context(definition, result))
            template = "reports/results/generic_table.html"
            pdf = (
                render_address_labels_pdf(definition, result)
                if definition.renderer == "address-labels"
                else render_generic_pdf(definition, result)
            )
        else:
            raise NotImplementedError(f"Unbekannter Renderer: {definition.renderer}")

        html = render_to_string(template, context)
        # ContentFile bekommt Bytes, damit Zeichenkodierung explizit bleibt.
        filename = f"{job.report_key}-{job.pk}.html"
        job.result_html.save(
            filename, ContentFile(html.encode("utf-8")), save=False
        )
        if pdf:
            job.result_pdf.save(
                f"{job.report_key}-{job.pk}.pdf", ContentFile(pdf), save=False
            )
        job.status = ReportJob.Status.SUCCEEDED
    except Exception as exc:
        job.status = ReportJob.Status.FAILED
        job.error_message = str(exc)
    finally:
        job.finished_at = timezone.now()
        job.save()
    return job

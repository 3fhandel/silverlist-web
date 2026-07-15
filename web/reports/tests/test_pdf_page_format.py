from reports.catalog import ReportDefinition
from reports.services.duckdb_engine import QueryResult
from reports.services.pdf_renderer import render_generic_pdf


def test_wide_generic_reports_remain_a4_portrait(tmp_path):
    definition = ReportDefinition(
        key="wide", name="Breiter Bericht", description="",
        export_source="Test", export_instructions="", required_columns=(),
        implementation="sql",
    )
    result = QueryResult(
        columns=tuple(f"Spalte {number}" for number in range(8)),
        rows=(tuple("Wert" for _ in range(8)),), variables={},
    )
    path = tmp_path / "wide.pdf"
    path.write_bytes(render_generic_pdf(definition, result))

    pdf = path.read_bytes()
    assert b"/MediaBox [ 0 0 595.2756 841.8898 ]" in pdf

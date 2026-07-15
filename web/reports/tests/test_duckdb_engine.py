from pathlib import Path

import pytest

from reports.catalog import ReportDefinition
from reports.services.duckdb_engine import ReportInputError, execute_report


def definition() -> ReportDefinition:
    return ReportDefinition(
        key="test",
        name="Test",
        description="",
        export_source="Testexport",
        export_instructions="",
        required_columns=("Warengruppe", "Artikel-Nr."),
        implementation="sql",
        query='SELECT "Artikel-Nr." FROM data WHERE Warengruppe = {{ group }}',
    )


def test_executes_parameterized_report(tmp_path: Path):
    source = tmp_path / "export.csv"
    source.write_bytes("Warengruppe;Artikel-Nr.\r\nObst;4711\r\n".encode("cp1252"))

    result = execute_report(source, definition(), {"group": "Obst"})

    assert result.columns == ("Artikel-Nr.",)
    assert result.rows == (("4711",),)


def test_rejects_missing_columns(tmp_path: Path):
    source = tmp_path / "export.csv"
    source.write_text("Warengruppe\nObst\n", encoding="utf-8")

    with pytest.raises(ReportInputError, match="Artikel-Nr"):
        execute_report(source, definition(), {"group": "Obst"})

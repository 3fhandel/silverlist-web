import csv
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re
import tempfile

import duckdb

from reports.catalog import ReportDefinition


class ReportInputError(ValueError):
    pass


@dataclass(frozen=True)
class QueryResult:
    columns: tuple[str, ...]
    rows: tuple[tuple[object, ...], ...]
    variables: dict[str, object]


_QUOTED_PARAMETER = re.compile(r"(['\"])\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}\1")
_PARAMETER = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")
_PLACEHOLDER = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")
_HEADER_ALIASES = {
    "HL": "Hauptlieferant",
    "Artikelnummer": "Artikel-Nr.",
}


def canonicalize_csv_header(header) -> tuple[str, ...]:
    result = list(header)
    for alias, canonical in _HEADER_ALIASES.items():
        if alias in result and canonical not in result:
            result.append(canonical)
    return tuple(result)


def _parameterize(query: str, parameters: dict[str, object]) -> tuple[str, list[object]]:
    values: list[object] = []

    def add(name: str) -> str:
        if name not in parameters:
            raise ReportInputError(f"Fehlender Berichtsparameter: {name}")
        values.append(parameters[name])
        return "?"

    query = _QUOTED_PARAMETER.sub(lambda match: add(match.group(2)), query)
    query = _PARAMETER.sub(lambda match: add(match.group(1)), query)
    return query, values


def _substitute_text(value: object, variables: dict[str, object]) -> object:
    if not isinstance(value, str):
        return value
    return _PLACEHOLDER.sub(lambda match: str(variables.get(match.group(1), "")), value)


def _duckdb_sql(query: str) -> str:
    query = query.replace("`", '"')
    query = re.sub(r"strftime\('%d\.%m\.%Y',\s*date\('now'\)\)", "strftime(current_date, '%d.%m.%Y')", query, flags=re.I)
    query = re.sub(r"strftime\('%d\.%m\.%Y',\s*'now'\)", "strftime(current_date, '%d.%m.%Y')", query, flags=re.I)
    query = re.sub(r"JULIANDAY\('now'\)\s*-\s*JULIANDAY\(([^)]+)\)", r"date_diff('day', CAST(\1 AS DATE), current_date)", query, flags=re.I)
    return query


def _autoit_text(command: str, variables: dict[str, object]) -> str:
    now = datetime.now()
    value = _substitute_text(command, variables)
    replacements = {
        "@MDAY": f"'{now:%d}'", "@MON": f"'{now:%m}'", "@YEAR": f"'{now:%Y}'",
        "@HOUR": f"'{now:%H}'", "@MIN": f"'{now:%M}'", "@SEC": f"'{now:%S}'",
    }
    for token, replacement in replacements.items():
        value = value.replace(token, replacement)
    parts = [part.strip() for part in value.split(" & ")]
    return "".join(part[1:-1] if len(part) >= 2 and part[0] == part[-1] == "'" else part for part in parts)


def _normalized_file(stack: ExitStack, source: str | Path):
    raw = Path(source).read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1252")
    handle = stack.enter_context(tempfile.NamedTemporaryFile(suffix=".csv"))
    handle.write(text.encode("utf-8"))
    handle.flush()
    return handle.name


def _create_csv_view(connection, path: str, name: str) -> tuple[str, ...]:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        raise ReportInputError(f"Ungültiger Datenquellenname: {name}")
    raw_name = f"__raw_{name}"
    connection.read_csv(
        path, delimiter=";", header=True, all_varchar=True,
        quotechar='"', auto_detect=True,
    ).create_view(raw_name)
    raw_header = tuple(
        row[0] for row in connection.execute(f'DESCRIBE "{raw_name}"').fetchall()
    )
    projections = ["*"]
    for alias, canonical in _HEADER_ALIASES.items():
        if alias in raw_header and canonical not in raw_header:
            projections.append(f'"{alias}" AS "{canonical}"')
    connection.execute(
        f'CREATE VIEW "{name}" AS SELECT {", ".join(projections)} FROM "{raw_name}"'
    )
    return tuple(row[0] for row in connection.execute(f'DESCRIBE "{name}"').fetchall())


def execute_report(source, definition: ReportDefinition, parameters=None, additional_sources=None) -> QueryResult:
    variables = dict(parameters or {})
    with ExitStack() as stack, duckdb.connect(":memory:") as connection:
        header = _create_csv_view(connection, _normalized_file(stack, source), "data")
        missing = set(definition.required_columns) - set(header)
        if missing:
            raise ReportInputError("CSV-Spalten fehlen: " + ", ".join(sorted(missing)))
        for name, path in (additional_sources or {}).items():
            _create_csv_view(connection, _normalized_file(stack, path), name)

        for variable in definition.variables:
            name, kind = variable["name"], variable["type"]
            if kind in {"userText", "userBool", "userSelect"}:
                continue
            if kind == "constant":
                variables[name] = _substitute_text(variable.get("value", ""), variables)
            elif kind == "sql":
                sql, values = _parameterize(_duckdb_sql(variable["query"]), variables)
                row = connection.execute(sql, values).fetchone()
                variables[name] = row[0] if row else None
            elif kind == "autoit":
                variables[name] = _autoit_text(variable["command"], variables)

        query, values = _parameterize(_duckdb_sql(definition.query), variables)
        cursor = connection.execute(query, values)
        columns = tuple(item[0] for item in cursor.description)
        return QueryResult(columns, tuple(cursor.fetchall()), variables)


def inspect_csv_header(source: str | Path) -> tuple[str, ...]:
    raw = Path(source).read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1252")
    lines = text.splitlines()
    if not lines:
        raise ReportInputError("Die CSV-Datei ist leer.")
    return canonicalize_csv_header(next(csv.reader([lines[0]], delimiter=";")))

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Literal

from django.conf import settings


@dataclass(frozen=True)
class ReportDefinition:
    key: str
    name: str
    description: str
    export_source: str
    export_instructions: str
    required_columns: tuple[str, ...]
    implementation: Literal["sql", "python"]
    query: str = ""
    renderer: str = "generic-table"
    source_confidence: str = "confirmed"
    variables: tuple[dict, ...] = ()
    additional_sources: tuple[dict, ...] = ()
    groups: tuple[dict, ...] = ()
    options: dict | None = None

    def matches(self, header: tuple[str, ...]) -> bool:
        return set(self.required_columns).issubset(header)


def _load_json(path: Path) -> ReportDefinition:
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    return ReportDefinition(
        key=raw["key"], name=raw["name"], description=raw.get("description", ""),
        export_source=raw["export_source"],
        export_instructions=raw.get("export_instructions", ""),
        required_columns=tuple(raw["required_columns"]), implementation="sql",
        query=raw["query"], renderer=raw.get("renderer", "generic-table"),
        source_confidence=raw.get("source_confidence", "confirmed"),
        variables=tuple(raw.get("variables", [])),
        additional_sources=tuple(raw.get("additional_sources", [])),
        groups=tuple(raw.get("groups", [])),
        options=raw.get("options", {}),
    )


def get_catalog() -> list[ReportDefinition]:
    from reports.report_modules.ordersatz import definitions as ordersatz_definitions

    directory = Path(settings.REPORT_DEFINITION_DIR)
    generic = [_load_json(path) for path in sorted(directory.rglob("*.json"))]
    return sorted([*generic, *ordersatz_definitions()], key=lambda item: item.name)


def get_definition(key: str) -> ReportDefinition:
    for definition in get_catalog():
        if definition.key == key:
            return definition
    raise KeyError(f"Unbekannter Bericht: {key}")


def matching_definitions(header: tuple[str, ...]) -> list[ReportDefinition]:
    return [definition for definition in get_catalog() if definition.matches(header)]

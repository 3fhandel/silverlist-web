from reports.catalog import ReportDefinition

BASE_COLUMNS = ("Warengruppe", "Artikel-Nr.", "Bezeichnung 1", "S-Einheit")


def _definition(price_group: str | None) -> ReportDefinition:
    suffix = price_group.lower() if price_group else "ohne-preise"
    label = price_group.upper() if price_group else "ohne Preise"
    required = BASE_COLUMNS + ((f"PG:{price_group.upper()}",) if price_group else ())
    return ReportDefinition(
        key=f"ordersatz-{suffix}", name=f"Ordersatz {label}",
        description="Vollständiger Ordersatz, gruppiert nach Warengruppe.",
        export_source="Stammdaten → Artikellisten",
        export_instructions=(
            "Artikelliste als CSV exportieren; Warengruppe, Artikelnummer, "
            "Bezeichnung und Einheit mitnehmen"
            + (f" sowie Preisgruppe PG:{price_group.upper()}. Ist diese im aktuellen SilverERP leer, wird VK-Netto verwendet." if price_group else ".")
        ),
        required_columns=required, implementation="python", renderer="ordersatz",
        source_confidence="inferred",
    )


def definitions() -> list[ReportDefinition]:
    return [_definition(f"vk{number}") for number in range(1, 7)] + [_definition(None)]


def query_for(definition: ReportDefinition, available_columns=()) -> str:
    price_column = next(
        (column for column in definition.required_columns if column.startswith("PG:")), None
    )
    if price_column and "VK-Netto" in available_columns:
        price = f'COALESCE(NULLIF(TRIM("{price_column}"), \'\'), NULLIF(TRIM("VK-Netto"), \'\'))'
    else:
        price = f'"{price_column}"' if price_column else "''"
    return (
        'SELECT Warengruppe, "Artikel-Nr." AS Artikelnummer, '
        '"Bezeichnung 1" AS Bezeichnung, "S-Einheit" AS Einheit, '
        f"{price} AS Preis, '' AS Bestellmenge FROM data "
        "WHERE Warengruppe <> 'Nicht zugeordnet' ORDER BY Warengruppe, Bezeichnung"
    )

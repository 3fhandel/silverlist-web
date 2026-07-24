"""Konvertiert die JSON-basierten SilverLists-.rpt-Dateien in das neue Schema."""

import csv
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "SilverERPBerichte" / "3F_SilverLists" / "reports"
TARGET = ROOT / "new" / "report_definitions" / "silverlists"


def relaxed_json(path: Path) -> dict:
    text = path.read_text(encoding="utf-8-sig")
    text = re.sub(r",\s*([}\]])", r"\1", text)
    return json.loads(text, strict=False)


def placeholders(value: str) -> str:
    return re.sub(r"@~([A-Za-z_][A-Za-z0-9_]*)~@", r"{{ \1 }}", value)


def convert(path: Path) -> dict:
    old = relaxed_json(path)
    variables = []
    for variable in old.get("variables", []):
        item = {
            "name": variable["name"],
            "type": variable["type"],
            "label": variable.get("prompt", variable["name"]),
        }
        for key in ("value", "query", "command", "selectFrom"):
            if key in variable:
                item[key] = placeholders(variable[key]) if isinstance(variable[key], str) else variable[key]
        variables.append(item)
    subheaders = []
    for group in old.get("subHeaders", []):
        subheaders.append({
            "column": group["columnName"],
            "show_column": group.get("showColumn", False),
            "page_break": group.get("pageBreak", False),
            "repeat_header": group.get("repeatMainHeader", False),
        })

    header = next(csv.reader([old["autoDiscover"]], delimiter=";"))
    # Neuere SilverERP-Versionen liefern zusätzliche Spalten, lassen aber einige
    # historische, von diesen Berichten nie verwendete Felder weg. Erkennung
    # basiert deshalb nur auf den fachlich benötigten Pflichtspalten.
    if path.stem.startswith("dispoliste_"):
        header = [column for column in header if column not in {"Eilig", "Pos."}]
    query = placeholders(old["dataSql"])
    if path.stem == "bestellliste":
        query = """SELECT `Artikel-Nr.`, `Bezeichnung 1` AS Bezeichnung, `S-Einheit` AS Einheit,
        CASE {{ preisgruppe }} WHEN '{PG:VK1}' THEN `{PG:VK1}` WHEN '{PG:VK2}' THEN `{PG:VK2}` END AS Preis,
        '' AS Menge FROM data WHERE `Archiv Artikel` != '1'"""
    elif path.stem == "kundenbestellzettel":
        query = query.replace("GROUP BY `Artikel-Nr.`", "GROUP BY `Artikel-Nr.`, `Artikel`, `Einheit`, `Menge`, `LTag`")
    elif path.stem in {"dispoliste_fleisch_kunden", "dispoliste_tiefkuehl_kunden"}:
        query = query.replace(" || ', ' || `Bezeichnung 4`", "")
    elif path.stem == "dispoliste_og_summen":
        query = """SELECT `Artikel-Nr.`, ANY_VALUE(`Bezeichnung 1`) AS Bezeichnung,
        SUM(CAST(REPLACE(Menge, ',', '.') AS DOUBLE)) AS Menge, `Einheit`
        FROM data WHERE `Artikel-Nr.` LIKE '60-%' GROUP BY `Artikel-Nr.`, `Einheit`
        ORDER BY `Artikel-Nr.`, `Einheit`"""
    elif path.stem == "dispoliste_fleisch_summen":
        query = """SELECT `Artikel-Nr.`, ANY_VALUE(`Bezeichnung 1`) AS Bezeichnung,
        SUM(CAST(REPLACE(Menge, ',', '.') AS DOUBLE)) AS Menge, `Einheit`
        FROM data WHERE `Artikel-Nr.` LIKE '20-%' OR `Artikel-Nr.` LIKE '30-%'
        GROUP BY `Artikel-Nr.`, `Einheit` ORDER BY `Artikel-Nr.`, `Einheit`"""
    elif path.stem == "kundenpreisliste_allgemein":
        query = query.replace("MAX(REPLACE(`Grundpreis`, ',', '.'))", "MAX(CAST(REPLACE(`Grundpreis`, ',', '.') AS DOUBLE))")
        query = query.replace("MAX(REPLACE(`Endpreis Brutto`, ',', '.'))", "MAX(CAST(REPLACE(`Endpreis Brutto`, ',', '.') AS DOUBLE))")
        query = query.replace("GROUP BY `Artikel-Nr.`", "GROUP BY ALL")
        query = re.sub(r"ORDER BY `Wg\.-Pfad`, `Bezeichnung 1`", "ORDER BY 1, 3", query)
    elif path.stem == "frischemarkt":
        query = """SELECT `Artikel-Nr.` AS Artikelnummer, `Bezeichnung 1` AS Bezeichnung, `Preis neu` AS "Preis VK"
        FROM data WHERE Referenz LIKE 'EVP'
        QUALIFY ROW_NUMBER() OVER (PARTITION BY `Artikel-Nr.` ORDER BY Zeitpunkt DESC) = 1"""
    elif path.stem == "postangebot":
        query = query.replace("FROM kunden JOIN data", "FROM kunden CROSS JOIN data")

    legacy_template = old.get("templates", {}).get("bodyFile", "")
    if "addresslabels" in legacy_template:
        renderer = "address-labels"
    else:
        renderer = "grouped-table" if subheaders else "generic-table"
    if "tableIntern" in legacy_template:
        layout = "internal-table"
    elif "tablePrivat" in legacy_template:
        layout = "private-pricelist"
    elif "tablePricelist" in legacy_template:
        layout = "pricelist"
    elif "tableWithHeader" in legacy_template:
        layout = "branded-table"
    elif "addresslabels" in legacy_template:
        layout = "address-labels"
    else:
        layout = "standard-table"

    return {
        "key": path.stem.replace("_", "-"),
        "name": old["name"],
        "description": old["description"],
        "export_source": old["exportSource"],
        "export_instructions": f"In SilverERP {old['exportSource']} öffnen und die angezeigte Liste als CSV exportieren.",
        "required_columns": header,
        "query": query,
        "renderer": renderer,
        "variables": variables,
        "additional_sources": [
            {"name": source["name"], "label": source["prompt"]}
            for source in old.get("addDataSources", [])
        ],
        "groups": subheaders,
        "options": {
            "show_header": old.get("templates", {}).get("showHeader", True),
            "show_page_numbers": old.get("templates", {}).get("showPagination", True),
            "compact_margins": old.get("templates", {}).get("noBorders", False),
            "legacy_template": legacy_template,
            "layout": layout,
        },
        "legacy_source": path.name,
    }


def main() -> None:
    TARGET.mkdir(parents=True, exist_ok=True)
    for source in sorted(SOURCE.glob("*.rpt")):
        target = TARGET / f"{source.stem}.json"
        target.write_text(
            json.dumps(convert(source), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(f"{len(list(TARGET.glob('*.json')))} Berichte nach {TARGET} migriert")


if __name__ == "__main__":
    main()

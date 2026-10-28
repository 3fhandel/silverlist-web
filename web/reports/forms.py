import csv

from django import forms
from django.conf import settings

from .catalog import get_catalog
from .models import ReportJob
from .report_modules.weekly_offer import DESIGNS, SLOT_CHOICES
from .services.duckdb_engine import canonicalize_csv_header, inspect_csv_header


class UploadForm(forms.ModelForm):
    class Meta:
        model = ReportJob
        fields = ["source_file"]
        labels = {"source_file": "SilverERP-CSV"}
        widgets = {"source_file": forms.FileInput(attrs={"accept": ".csv,text/csv"})}

    def clean_source_file(self):
        source = self.cleaned_data["source_file"]
        if not source.name.lower().endswith(".csv"):
            raise forms.ValidationError("Bitte eine CSV-Datei hochladen.")
        if source.size > settings.MAX_UPLOAD_SIZE:
            raise forms.ValidationError("Die CSV-Datei ist größer als 100 MB.")
        return source


class ReportSelectionForm(forms.Form):
    report_key = forms.ChoiceField(label="Bericht", widget=forms.RadioSelect)

    def __init__(self, *args, candidates=(), **kwargs):
        super().__init__(*args, **kwargs)
        by_key = {item.key: item for item in get_catalog()}
        self.fields["report_key"].choices = [
            (key, by_key[key].name) for key in candidates if key in by_key
        ]


class ReportConfigurationForm(forms.Form):
    def __init__(self, *args, definition, **kwargs):
        self.definition = definition
        super().__init__(*args, **kwargs)
        for variable in definition.variables:
            kind = variable["type"]
            if kind == "userText":
                self.fields[variable["name"]] = forms.CharField(
                    label=variable["label"],
                    required=variable.get("required", True),
                    help_text=variable.get("help_text", ""),
                    widget=(
                        forms.Textarea(attrs={"rows": variable.get("rows", 3)})
                        if variable.get("multiline")
                        else forms.TextInput()
                    ),
                )
            elif kind == "userBool":
                self.fields[variable["name"]] = forms.BooleanField(label=variable["label"], required=False)
            elif kind == "userSelect":
                self.fields[variable["name"]] = forms.ChoiceField(
                    label=variable["label"],
                    choices=[(item["value"], item["text"]) for item in variable["selectFrom"]],
                )
        for source in definition.additional_sources:
            self.fields[f"source__{source['name']}"] = forms.FileField(
                label=source["label"],
                help_text=source.get("help_text", ""),
                widget=forms.FileInput(attrs={"accept": ".csv,text/csv"}),
            )

    def clean(self):
        cleaned = super().clean()
        sources = {source["name"]: source for source in self.definition.additional_sources}
        for name, source in sources.items():
            upload = cleaned.get(f"source__{name}")
            if not upload:
                continue
            required = set(source.get("required_columns", ()))
            if not required:
                continue
            try:
                header = set(inspect_csv_header(upload.temporary_file_path()))
            except AttributeError:
                position = upload.tell()
                try:
                    raw = upload.read()
                    try:
                        text = raw.decode("utf-8-sig")
                    except UnicodeDecodeError:
                        text = raw.decode("cp1252")
                    header = set(canonicalize_csv_header(
                        next(csv.reader([text.splitlines()[0]], delimiter=";"))
                    ))
                except (IndexError, StopIteration, UnicodeError) as exc:
                    self.add_error(f"source__{name}", "Die CSV-Datei konnte nicht gelesen werden.")
                    continue
                finally:
                    upload.seek(position)
            missing = required - header
            if missing:
                self.add_error(
                    f"source__{name}",
                    "Das ist nicht der erwartete Export. Fehlende Spalten: "
                    + ", ".join(sorted(missing)),
                )
        return cleaned


class WeeklyOfferConfigurationForm(forms.Form):
    design = forms.ChoiceField(
        label="Design",
        choices=[(key, design.name) for key, design in DESIGNS.items()],
    )
    validity = forms.CharField(label="Gültigkeitszeile", max_length=120)

    def __init__(self, *args, products, initial_validity="", **kwargs):
        self.products = products
        initial = kwargs.setdefault("initial", {})
        initial.setdefault("validity", initial_validity)
        super().__init__(*args, **kwargs)
        for product in products:
            suffix = product["id"]
            self.fields[f"slot_{suffix}"] = forms.ChoiceField(
                label="Position", choices=(("", "Nicht verwenden"), *SLOT_CHOICES),
                required=False,
            )
            self.fields[f"description_{suffix}"] = forms.CharField(
                label="Artikel", max_length=180, initial=product["description"], required=False,
            )
            self.fields[f"price_{suffix}"] = forms.CharField(
                label="Preis", max_length=30, initial=product["price"], required=False,
            )
            self.fields[f"unit_{suffix}"] = forms.CharField(
                label="Einheit", max_length=30, initial=product["unit"], required=False,
            )

    def clean(self):
        cleaned = super().clean()
        occupied = {}
        selected = []
        for product in self.products:
            suffix = product["id"]
            slot = cleaned.get(f"slot_{suffix}")
            if not slot:
                continue
            if slot in occupied:
                self.add_error(
                    f"slot_{suffix}",
                    f"Position ist bereits mit {occupied[slot]} belegt.",
                )
                continue
            description = (cleaned.get(f"description_{suffix}") or "").strip()
            if not description:
                self.add_error(f"description_{suffix}", "Bitte eine Bezeichnung angeben.")
                continue
            occupied[slot] = description
            selected.append({
                **product,
                "slot": slot,
                "description": description,
                "price": (cleaned.get(f"price_{suffix}") or "").strip(),
                "unit": (cleaned.get(f"unit_{suffix}") or "").strip(),
            })
        if not selected:
            raise forms.ValidationError("Bitte mindestens einen Artikel positionieren.")
        cleaned["selected_products"] = selected
        return cleaned

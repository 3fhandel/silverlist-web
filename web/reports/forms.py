from django import forms
from django.conf import settings

from .catalog import get_catalog
from .models import ReportJob


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
        super().__init__(*args, **kwargs)
        for variable in definition.variables:
            kind = variable["type"]
            if kind == "userText":
                self.fields[variable["name"]] = forms.CharField(label=variable["label"])
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
                widget=forms.FileInput(attrs={"accept": ".csv,text/csv"}),
            )

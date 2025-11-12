# forms.py
# -- STDLIB
import csv

# -- THIRDPARTY
from bs4 import BeautifulSoup

# -- DJANGO
from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.forms import ModelForm

# -- BASEDEQUESTIONS (LOCAL)
from .models import Collection, Distributor


class XMLUploadForm(forms.Form):
    xml_file = forms.FileField(label="Select an XML file")

    # Liste des balises obligatoires et attributs
    required_tags = ["IDNo", "var", "catValu", "labl", "catgry", "qstnLit"]  # noqa: RUF012
    required_attributes = {"var": "name"}  # noqa: RUF012

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def clean_xml_file(self): # noqa: C901
        xml_file = self.cleaned_data["xml_file"]
        if not xml_file.name.endswith(".xml"):
            msg = "Le fichier doit être au format XML."
            raise forms.ValidationError(msg)

        try:
            content = xml_file.read().decode("utf-8")

            # Analyse du fichier XML avec BeautifulSoup
            soup = BeautifulSoup(content, "xml")

            # Extraire l'espace de noms par défaut (si présent)
            namespaces = dict(soup.find_all("xmlns"))
            default_ns = namespaces.get(None, "")

            missing_tags = []
            missing_attributes = []

            # Vérification des balises obligatoires
            for tag in self.required_tags:
                # Chercher la balise avec ou sans espace de noms
                tag_found = soup.find(f"{tag}") or soup.find(f"{{{default_ns}}}{tag}")

                if not tag_found:
                    missing_tags.append(tag)

            # Vérification des attributs obligatoires
            for tag, attr in self.required_attributes.items():
                # Recherche de la balise correspondante
                tag_found = soup.find(f"{tag}") or soup.find(f"{{{default_ns}}}{tag}")

                if tag_found:
                    # Vérifier la présence de l'attribut
                    if not tag_found.has_attr(attr):
                        missing_attributes.append(f"{attr} in <{tag}>")
                else:
                    missing_tags.append(tag)  # La balise elle-même est manquante

            # Si des balises ou attributs manquent, lever une erreur
            if missing_tags or missing_attributes:
                error_message = []
                if missing_tags:
                    error_message.append(
                        f"Les balises suivantes sont manquantes : {', '.join(missing_tags)}"
                    )
                if missing_attributes:
                    error_message.append(
                        f"Les attributs suivants sont manquants : {', '.join(missing_attributes)}"
                    )
                raise forms.ValidationError(" ".join(error_message))

            return content  # Renvoie le contenu pour traitement ultérieur

        except Exception as e:
            msg = f"Erreur lors de la lecture du fichier XML : {e!s}"
            raise forms.ValidationError(msg) from e


class CustomAuthenticationForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={"class": "form-control"}))
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "form-control"})
    )


class CollectionForm(ModelForm):
    distributor = forms.ModelChoiceField(
        queryset=Distributor.objects.all(),
        label="Diffuseur",
        widget=forms.Select(
            attrs={
                "class": "form-control form-control-lg selectpicker",
                "data-live-search": "true",
            }
        ),
        empty_label="Choisissez un diffuseur",
    )

    class Meta:
        model = Collection
        fields = "__all__"

        widgets = {  # noqa: RUF012
            "name": forms.TextInput(
                attrs={
                    "class": "form-control form-control-lg",
                    "placeholder": "Nom de l'enquête",
                }
            ),
            "abstract": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 5,
                    "placeholder": "Entrez le résumé ici...",
                }
            ),
        }


# forms.py


class CSVUploadFormCollection(forms.Form):
    csv_file = forms.FileField(label="Sélectionnez un fichier CSV")

    required_columns = [  # noqa: RUF012
        "doi",
        "xml_lang",
        "title",
        "author",
        "producer",
        "distributor",
        "start_date",
        "geographic_coverage",
        "geographic_unit",
        "unit_of_analysis",
        "contact",
        "date_last_version",
        "collection",
        "sous-collection",
    ]
    validate_duplicates = True

    def clean_csv_file(self):
        csv_file = self.cleaned_data["csv_file"]
        if not csv_file.name.endswith(".csv"):
            msg = "Le fichier doit être au format CSV."
            raise forms.ValidationError(msg)
        try:
            decoded_file = csv_file.read().decode("utf-8").splitlines()
            sample = "\n".join(decoded_file[:2])
            sniffer = csv.Sniffer()
            delimiter = sniffer.sniff(sample).delimiter
            reader = csv.DictReader(decoded_file, delimiter=delimiter)
            # Validation des colonnes manquantes
            missing_columns = [
                col for col in self.required_columns if col not in reader.fieldnames
            ]
            if missing_columns:
                msg = f"Les colonnes suivantes sont manquantes : {', '.join(missing_columns)}"
                raise forms.ValidationError(msg)

            self.cleaned_data["decoded_csv"] = decoded_file
            self.cleaned_data["delimiter"] = delimiter
            # Si tout va bien, renvoie le fichier décodé pour un traitement ultérieur
            return decoded_file

        except Exception as e:
            msg = f"Erreur lors de la lecture du fichier CSV : {e!s}"
            raise forms.ValidationError(msg) from e

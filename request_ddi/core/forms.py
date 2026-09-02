# -- STDLIB

# -- DJANGO
from django import forms
from django.contrib.auth.forms import AuthenticationForm

# -- LOCAL
from request_ddi.utils.csv import read_csv_file


class CustomAuthenticationForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={"class": "form-control"}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={"class": "form-control"}))


class DDICXMLUploadForm(forms.Form):
    xml_files = forms.FileField(label="Sélectionnez un ou plusieurs fichiers XML")


class DDICImportFormCollection(forms.Form):
    csv_file = forms.FileField(label="Sélectionnez un fichier CSV")

    required_columns = [  # noqa: RUF012
        "doi",
        "collection",
        "sub_collection",
        "url",
    ]
    validate_duplicates = True

    # https://docs.djangoproject.com/en/6.0/ref/forms/validation/
    def clean_csv_file(self):
        csv_file = self.cleaned_data["csv_file"]
        if not csv_file.name.endswith(".csv"):
            msg = "Le fichier doit être au format CSV."
            raise forms.ValidationError(msg)
        try:
            content = csv_file.read().decode("utf-8").splitlines()
            reader = read_csv_file(content)
            # Validation des colonnes manquantes
            missing_columns = [col for col in self.required_columns if col not in reader.fieldnames]
            if missing_columns:
                msg = f"Les colonnes suivantes sont manquantes : {', '.join(missing_columns)}"
                raise forms.ValidationError(msg)

            self.cleaned_data["decoded_csv"] = content
            # Si tout va bien, renvoie le fichier décodé pour un traitement ultérieur
            return content

        except Exception as e:
            msg = f"Erreur lors de la lecture du fichier CSV : {e!s}"
            raise forms.ValidationError(msg) from e

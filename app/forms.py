# forms.py
# -- STDLIB
import csv

# -- DJANGO
from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.forms import ModelForm
from django.contrib import messages

# -- THIRDPARTY
from bs4 import BeautifulSoup

# -- BASEDEQUESTIONS (LOCAL)
from .models import Serie, BindingSurveyRepresentedVariable, Publisher


class CSVUploadForm(forms.Form):
    series = forms.ModelChoiceField(
        queryset=Serie.objects.all(),
        label="Sélectionnez une série",
        required=True,
        widget=forms.Select(attrs={'class': 'selectpicker', 'data-live-search': 'true'})
    )
    csv_file = forms.FileField(label='Select a CSV file')

    required_columns = ['ddi', 'title', 'variable_name', 'variable_label', 'question_text', 'category_label']
    validate_duplicates = True

    def clean_csv_file(self):
        csv_file = self.cleaned_data['csv_file']
        if not csv_file.name.endswith('.csv'):
            raise forms.ValidationError("Le fichier doit être au format CSV.")
        try:
            decoded_file = csv_file.read().decode('utf-8').splitlines()
            sample = '\n'.join(decoded_file[:2])
            sniffer = csv.Sniffer()
            delimiter = sniffer.sniff(sample).delimiter
            reader = csv.DictReader(decoded_file, delimiter=delimiter)

            # Validation des colonnes manquantes
            missing_columns = [col for col in self.required_columns if col not in reader.fieldnames]
            if missing_columns:
                raise forms.ValidationError(f"Les colonnes suivantes sont manquantes : {', '.join(missing_columns)}")

            self.cleaned_data['decoded_csv'] = decoded_file

            return decoded_file  # Si tout va bien, renvoie le fichier décodé pour un traitement ultérieur

        except Exception as e:
            raise forms.ValidationError(f"Erreur lors de la lecture du fichier CSV : {str(e)}")

    def validate_duplicates_check(self):
        """Check des doublons après validation des colonnes."""
        if not self.cleaned_data.get('decoded_csv') or not self.validate_duplicates:
            return  # Évite de répéter le check si une erreur a été trouvée précédemment

        decoded_file = self.cleaned_data['decoded_csv']
        reader = csv.DictReader(decoded_file)
        duplicate_variables = []

        for row in reader:
            variable_name = row.get('variable_name')
            if variable_name and BindingSurveyRepresentedVariable.objects.filter(variable_name=variable_name).exists():
                duplicate_variables.append(variable_name)

        if duplicate_variables:
            raise forms.ValidationError({
                'csv_file': f"Les variables suivantes existent déjà : {', '.join(duplicate_variables)}"
            })


class XMLUploadForm(forms.Form):
    series = forms.ModelChoiceField(
        queryset=Serie.objects.all(),
        label="Sélectionnez une série",
        required=True,
        widget=forms.Select(attrs={'class': 'selectpicker', 'data-live-search': 'true'})
    )
    xml_file = forms.FileField(label='Select an XML file')

    # Liste des balises obligatoires et attributs
    required_tags = ['IDNo', 'titl', 'var', 'catValu', 'labl', 'catgry', 'qstnLit', 'universe', 'notes']
    required_attributes = {'var': 'name'}

    def clean_xml_file(self):
        xml_file = self.cleaned_data['xml_file']
        if not xml_file.name.endswith('.xml'):
            raise forms.ValidationError("Le fichier doit être au format XML.")

        try:
            content = xml_file.read().decode('utf-8')

            # Analyse du fichier XML avec BeautifulSoup
            soup = BeautifulSoup(content, 'xml')

            # Extraire l'espace de noms par défaut (si présent)
            namespaces = {prefix: uri for prefix, uri in soup.find_all('xmlns')}
            default_ns = namespaces.get(None, '')

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
                    error_message.append(f"Les balises suivantes sont manquantes : {', '.join(missing_tags)}")
                if missing_attributes:
                    error_message.append(f"Les attributs suivants sont manquants : {', '.join(missing_attributes)}")
                raise forms.ValidationError(' '.join(error_message))

            return content  # Renvoie le contenu pour traitement ultérieur

        except Exception as e:
            raise forms.ValidationError(f"Erreur lors de la lecture du fichier XML : {str(e)}")


class CustomAuthenticationForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))


class SerieForm(ModelForm):
    publisher = forms.ModelChoiceField(
            queryset=Publisher.objects.all(),
            label="Éditeur",
            widget=forms.Select(attrs={
                'class': 'form-control form-control-lg selectpicker',
                'data-live-search': 'true',
            }),
            empty_label="Choisissez un éditeur"
        )
    class Meta:
        model = Serie
        fields = "__all__"

        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Nom de l\'enquête'
            }),
            'abstract': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Entrez le résumé ici...'
            }),
        }

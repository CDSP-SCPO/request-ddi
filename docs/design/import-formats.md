# Importing Variable Level Metadata into ReQuest in Different Formats

## Introduction

### Purpose

The purpose of the document is to define the interface for importing variable level
metadata into ReQuest app in different formats. Currently, the only format we support
is [XML DDI-Codebook (DDI-C)](https://ddialliance.org/ddi-codebook). As DDI-C format is
not trivial to produce, not all data producers might not have their data in this format.
Hence, an ideal solution is to support importing variable level metadata in different
formats like CSV which is a more commonly used format in Social Sciences. However, the
design must be able to accommodate more formats like JSON, Parquet, _etc_., more easily
into the app.

### Scope

The scope of this document is strictly confined to how the variable level metadata in
different formats are imported into ReQuest app. This **does not** cover how the data tables
are organized in the SQL DB and how they are actually imported.

### Definitions and Acronyms

- CSV: Comma Separated Values
- DDI-C: Data Documentation Initiative - Codebook
- DDI-L: Data Documentation Initiative - Life Cycle
- JSON: JavaScript Object Notation
- XML: Extensible Markup Language

## Architectural Design

### Components

- **Frontend**: This user facing component is responsible for showing HTML forms for the
users to upload the files in different formats. It must be able to show to the end users
any errors that are encountered in the data format and/or parsing the files in the
backend.
- **Backend**: Once the file has been sent by the frontend, the responsibility of the
backend is to detect the file format, parse the file based on detected format and create
list of objects and metadata that will be used to create DB objects. It is imperative for
the backend to catch any sort of errors and pass them to the frontend in HTML friendly
way for the end users to make sense of those errors easily.

## Detailed Design

### Columns/Keys in Data Files

#### Required columns

Irrespective of the file format (tabular data like CSV, parquet or object data like JSON),
there must be certain columns/keys that must exist in each row/object for the importing
data. These columns/keys are part of Survey model in the DB and hence, they are
indispensable. Currently, these columns are as follows:

- doi
- xml_lang
- collection
- sous-collection
- title
- author
- producer
- distributor
- start_date
- geographic_coverage
- geographic_unit
- unit_of_analysis
- contact
- date_last_version

The above stated column/key names are subject to change. Once the DB models are refined to
work along with [DDI Life Cycle (DDI-L)](https://ddialliance.org/ddi-lifecycle), the
names must be changed to be more in-line with DDI-L nomenclature. Similarly, the column
name `xml_lang` must be simply changed to `lang` as the input data files to ReQuest app
is not necessarily anymore XML files.

#### Optional columns

Along with the above mentioned columns/keys the input data files may contain either:

- url column which gives a **direct URL** to fetch the DDI-C XML file from the underlying
data cataloging software.

or

The following columns that present the variable level metadata in tabular format.

- variable_name
- variable_label
- question_text
- univers
- notes
- category_labels
- category_codes
- category_stats
- catgeory_missing

The columns `univers` and `notes` are directly provided by DDI-C XML files. The columns
`category_labels`, `category_codes`, `category_stats` and `category_missing` can have multiple values for a
given variable and hence, they must be concatenated into a single string delimited by
`|`. In the case of JSON representation, these must be a list of strings and ints.
**The order of concatenation must be preserved for all three columns.**

Here are some of the examples of different types of possible input files:

#### CSV format

- CSV file which provides URL to fetch DDI-C XML file

```csv
doi:10.21410/7E4/DDDHXW,fr,Données de recherche,Agoramétrie,Baromètre nucléaire (2005),Pagès Jean-Pierre,Pagès Jean-Pierre; Commissariat à l'Énergie Atomique, Laboratoire de statistiques et d'études économiques et sociales (LSESS), Centre de données socio-politiques (CDSP),2005-01-01,France,France métropolitaine hors Corse,Individu,info.cdsp@sciencespo.fr,2018-09-01,https://data.sciencespo.fr/api/access/datafile/116

```

- CSV file which provides variable level metadata embedded into it **without providing URL**

```csv
doi:10.21410/7E4/DDDHXW,fr,Données de recherche,Agoramétrie,Baromètre nucléaire (2005),Pagès Jean-Pierre,Pagès Jean-Pierre; Commissariat à l'Énergie Atomique, Laboratoire de statistiques et d'études économiques et sociales (LSESS), Centre de données socio-politiques (CDSP),2005-01-01,France,France métropolitaine hors Corse,Individu,info.cdsp@sciencespo.fr,2018-09-01,c250,Conflits : Pour la force de dissuasion nucléaire,La force nucléaire de dissuasion est indispensable à la France,,,Pas du tout d'accord|Pas tellement d'accord|Peut-être d'accord|Bien d'accord|Entièrement d'accord|Non réponse,1|2|3|4|5|9,148|181|202|366|180|30,N|N|N|N|Y
```

- CSV file with URL and variable level metadata

```csv
doi:10.21410/7E4/DDDHXW,fr,Données de recherche,Agoramétrie,Baromètre nucléaire (2005),Pagès Jean-Pierre,Pagès Jean-Pierre; Commissariat à l'Énergie Atomique, Laboratoire de statistiques et d'études économiques et sociales (LSESS), Centre de données socio-politiques (CDSP),2005-01-01,France,France métropolitaine hors Corse,Individu,info.cdsp@sciencespo.fr,2018-09-01,https://data.sciencespo.fr/api/access/datafile/116,c250,Conflits : Pour la force de dissuasion nucléaire,La force nucléaire de dissuasion est indispensable à la France,,,Pas du tout d'accord|Pas tellement d'accord|Peut-être d'accord|Bien d'accord|Entièrement d'accord|Non réponse,1|2|3|4|5|9,148|181|202|366|180|30,N|N|N|N|Y
```

#### JSON format

- JSON file with URL

```json
[
    {
        "doi": "doi:10.21410/7E4/DDDHXW",
        "xml_lang": "fr",
        "collection": "Données de recherche,",
        "sous-collection": "Agoramétrie",
        "title": "Agoramétrie",
        "author": "Pagès Jean-Pierre",
        "producer": "Pagès Jean-Pierre; Commissariat à l'Énergie Atomique, Laboratoire de statistiques et d'études économiques et sociales (LSESS)",
        "distributor": "Centre de données socio-politiques (CDSP)",
        "start_date": "2005-01-01",
        "geographic_coverage": "France",
        "geographic_unit": "France métropolitaine hors Corse",
        "unit_of_analysis": "Individu",
        "contact": "info.cdsp@sciencespo.fr",
        "date_last_version": "2018-09-01",
        "url": "https://data.sciencespo.fr/api/access/datafile/116"
    }
]
```

- JSON file with variable level metadata embedded into it.

```json
[
    {
        "doi": "doi:10.21410/7E4/DDDHXW",
        "xml_lang": "fr",
        "collection": "Données de recherche,",
        "sous-collection": "Agoramétrie",
        "title": "Agoramétrie",
        "author": "Pagès Jean-Pierre",
        "producer": "Pagès Jean-Pierre; Commissariat à l'Énergie Atomique, Laboratoire de statistiques et d'études économiques et sociales (LSESS)",
        "distributor": "Centre de données socio-politiques (CDSP)",
        "start_date": "2005-01-01",
        "geographic_coverage": "France",
        "geographic_unit": "France métropolitaine hors Corse",
        "unit_of_analysis": "Individu",
        "contact": "info.cdsp@sciencespo.fr",
        "date_last_version": "2018-09-01",
        "variables": [
            {
                "name": "c250",
                "label": "Conflits : Pour la force de dissuasion nucléaire",
                "question_text": "La force nucléaire de dissuasion est indispensable à la France",
                "univers": "",
                "notes": "",
                "categories": [
                    {
                        "label": "Pas du tout d'accord",
                        "code": 1,
                        "stat": 148,
                        "missing": false
                    },
                    {
                        "label": "Pas tellement d'accord",
                        "code": 2,
                        "stat": 181,
                        "missing": false
                    },
                    {
                        "label": "Peut-être d'accord",
                        "code": 3,
                        "stat": 202,
                        "missing": false
                    },
                    {
                        "label": "Bien d'accord",
                        "code": 4,
                        "stat": 366,
                        "missing": false
                    },
                    {
                        "label": "Entièrement d'accord",
                        "code": 5,
                        "stat": 180,
                        "missing": false
                    },
                    {
                        "label": "Non réponse",
                        "code": 9,
                        "stat": 30,
                        "missing": true
                    }
                ]
            }
        ]
    }
]
```

The above examples are just for demonstrative purposes and not necessarily mean that should
be implemented in the app. In fact any tabular data format can be easily integrated into
the app with carefully designed interface.

### Frontend

The principal job of the frontend is to show HTML form to upload the file. If and when
uploading data in multiple formats will be supported, a form input field for
each different format must be added and do the basic sanity checks like the extension of the file using in-built
HTML features. The uploaded file in the browser must be sent to the backend server, wait
for the server to return the response and show the success/error messages to the
end users.

In addition, a checkbox with message about force importing data must be included. The message
can be as follows:

```html
Force import. All the surveys in the CSV file will be reimported and updated.
```

This checkbox parameter must be sent as a query parameter `force_import` to the backend
server. The purpose of this query parameter is discussed in the [Backend](#backend) section.

Finally, **it is desirable** to support uploading multiple files in each format. This gives
more freedom for the end users to organize thier input files to their needs.

### Backend

#### Validation

The first step on the backend is to validate the user supplied input file. Each format
should have its own form field and hence the validation for each format should be done
in its own method as per [Django Form field validation](https://docs.djangoproject.com/en/6.0/ref/forms/validation/).
The following elements must be validated in the form class:

- It is important to note that when there are multiple fields, atmost only one field value
should be non-empty, _i.e.,_ the backend should receive only one type of input file. This
should not arrive in reality, however, it is a good practice to check this. If there are
more than one non-mepty field, fail fast and raise a [`ValidationError`](https://docs.djangoproject.com/en/6.0/ref/forms/validation/#raising-validationerror)
saying only one format at a time can be used to upload.

- First check if the provided input files have all the [required columns/keys](#required-columns) based on the
input format. If there is any missing column/key in the input file, stop processing and
return a [`ValidationError`](https://docs.djangoproject.com/en/6.0/ref/forms/validation/#raising-validationerror)
with an appropriate error message.

- Once all the required columns/keys are found in the input file, the presence of
[optional columns/keys](#optional-columns) must be checked. If the optional columns
are present, a new variable, say, `fetch_from _url` can be defined in `cleaned_data` and
set to `False`. This can be used in data processing step to directly read variable level
metadata from input file _per se_.

- If the optional columns/keys are not present, the presence of `url` column/key must
be verified. If the column is present, set `fetch_from _url` to `True` in `cleaned_data`
and return. If not found, raise a [`ValidationError`](https://docs.djangoproject.com/en/6.0/ref/forms/validation/#raising-validationerror)
saying either `url` or [optional columns/keys](#optional-columns) must be present in the
input file(s).

If the input file(s) contain both `url` and optional columns/keys, the above algorithm
will take precedence of reading variable level metadata from optional columns. This is
to allow end users to use modified variable level metadata that might not exist in their
data cataloging software.

A pseudo code for the Form class can be as follows:

```python
class UploadForm(forms.Form):
    csv_file = forms.FileField(label="Sélectionnez un fichier CSV")
    json_file = forms.FileField(label="Sélectionnez un fichier JSON")

    def _clean_csv_file(self):
        self.cleaned_data["content"] = file
        self.cleaned_data["delimiter"] = delimiter
        self.cleaned_data["format"] = "csv"
        if not all_required_columns_are_present:
            raise ValidationError("Required columns are missins")

        self.cleaned_data["fetch_from_url"] = False
        if all_optional_columns_are_present:
            return file
        else:
            if not url_column_is_present:
                raise ValidationError("Neither URL nor optional columns are present")
            self.cleaned_data["fetch_from_url"] = True
            return file

    def clean(self):
        # Ensure to run any validation logic in parent
        super().clean()

        # Check if atmost one form field is provided
        if self.cleaned_data.get("csv_file") and self.cleaned_data.get("json_file"):
            raise ValidationError("Atmost one input field must be provided")

        # Run validation checks on CSV file
        if self.cleaned_data.get("csv_file"):
            return self._clean_csv_file()

        # Run validation checks on JSON file
        if self.cleaned_data.get("csv_file"):
            return self._clean_json_file()
```

#### Parsing data

The first step in parsing data is convert data in different formats in a standardised
Python native format for processing. As Python dict and JSON are compatible, the JSON
format described in [JSON section](#json-format) can be used as the standardised format.
Thus, every different supported format must be first transformed into Python dict
compatible with JSON described in [JSON format](#json-format) section. This can be
done in `get_data` method of the view.

```python
class UploadView(StaffRequiredMixin, View):

    def _parse_csv_file(self, content, delimiter, fetch_from_url):
        content_dict = csv.DictReader(content, delimiter=delimiter)
        xml_parser = XMLParser()

        surveys = []
        errors = []
        for line_number, row in enumerate(content_dict, start=1):
            if fetch_from_url:
                url = row["url"]
                doi = row["doi"]
                xml_content = self._fetch_xml(url)
                try:
                    survey = xml_parser.parse(xml_content)
                    surveys.append(survey)
                except Exception as e:
                    # Log exception
                    # Add a more verbose error message
                    errors.append({"doi": doi, "error": e})

        return surveys, errors

    def get_data(self, form):
        """get_data should return list of survey dicts and error dicts"""
        if form.cleaned_data["format"] == "csv":
            return self._parse_csv_file(form.cleaned_data["content"], form.cleaned_data["delimiter"], form.cleaned_data["fetch_from_url"])
        if form.cleaned_data["format"] == "json":
            return self._parse_json_file(form.cleaned_data["content"], form.cleaned_data["fetch_from_url"])
```

When support for more formats is needed, a new private method `_parse_<format>_file` must
be added and transform the data into a Python dict.

Once the data has been transformed into a standard dict, it needs to be processed to be
imported in the DB. The first step is to get a list of all DOIs in the input files and
compare them with the existent DOIs in the DB. Next step is to import variable level
metadata of new surveys into the DB. There are two very important pointers in the current
context of importing surveys into the DB that need to be considered:

- Based on the query parameter `force_import`, import behaviour must be modified.
If `force_import` is `False` or does not exist in the query parameters, only new surveys
that are in the input files must be imported. The response must include the list of
surveys that are imported and the list of surveys that have been ignored because they
already exist in the DB. If the `force_import` is truthy, all the surveys must be
reimported irrespective of the fact if they exist in the DB or not.

- The atomic transcation on the DB must be imposed on the individual survey level rather
than the HTTP request level. The rationale is that within atomic requests, a single error
in DB transcation will roll back all the DB operations. Hence, a single error can rollback
all DB operations of ALL surveys when atomic transcation is applied at the HTTP request.
On the other hand, using atomic transcation at the survey level will only rollback DB
operations of that survey which can be reimported easily after fixing the issues. It
is also important to push data into Elastic search only when all the variables are
successfully imported into SQL DB in order to avoid inconsistencies between SQL and
Elastic search.

A partial code can look as follows:

```python
class UploadView(StaffRequiredMixin, View):

    def form_valid(self, form):
        try:
            surveys, parse_errors = self.get_data(form)
            force_import = bool(self.request.POST.query("force_import", None))
            input_dois = [s["doi"] for s in surveys]
            existing_dois = [s.external_ref for s in Survey.objects.filter(external_ref__in=input_dois)]
            dois_to_import = set(input_dois) - set(existing_dois)
            # Based on force_import setup dois_to_import
            if force_import:
                dois_to_import = input_dois

            import_stats, import_errors = self.process_data(surveys, dois_to_import)

            # If all surveys failed to import raise Exception
            if not import_stats["dois"]:
                raise Exception

            # If some surveys failed to import
            if parse_errors or import_errors:
                # Return 207 with body containing failed surveys dois
                # https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Status/207
                return JsonResponse({...}, status=207)
        except ....
            # Exception blocks

    def process_data(self, surveys, dois_to_import):
        """process_data should return stats of import and errors dicts. Each error
        dict must have doi and error string keys"""
        importer = DataImporter()

        errors = []
        import_stats = {
            "dois": [],
            "num_surveys": 0,
            "num_variables": 0,
            "num_bindings": 0,
        }
        # Import each survey
        for survey in surveys:
            if not survey["doi"] not in existing_dois:
                continue

            # Create survey object
            Survey.objects.get_or_create(...)

            try:
                num_records, num_variables, num_bindings = importer.import_data(survey)
                import_stats["dois"].append(survey["doi"])
                import_stats["num_surveys"] += 1
                import_stats["num_variables"] += num_variables
                import_stats["num_bindings"] += num_bindings
            except Exception as e:
                errors.append({"doi": survey["doi"], "error": e})
        return import_stats, errors
```

#### HTTP response data structure

The upload end point must return a standardised HTTP response that conforms to the
following JSON schema:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Response object for upload view",
  "type": "object",
  "properties": {
    "status": {
      "type": "string",
      "enum": ["success", "error", "partial_success"]
    },
    "data": {
      "type": "array",
      "items": {}
    },
    "message": {
      "type": "string"
    },
    "errors": {
      "type": "array",
      "items": {}
    },
    "warnings": {
      "type": "array",
      "items": {}
    }
  },
  "required": [
    "status"
  ]
}
```

- The status `partial_success` is when some of the surveys in the input files fails but
at least one survey is imported successfully.

- `message` must be a very brief title that describes the response.

- `data` must contain any data object that a successful 2xx response sends.

- `errors` must contain a list of errors encountered during survey imports.

- When the surveys in the input files already exist in the DB, these surveys are skipped
by default (unless users request a force import). In this case, the list of surveys that
have been skipped must be included as a warning in the `warnings`.

Valid JSON responses for different cases are as follows:

For success:

```json
{
    "status": "success",
    "message": "All surveys imported successfully",
    "data": [{"num_surveys": 10, "num_variables": 500, "num_bindings": 500}]
}
```

For partial success:

```json
{
    "status": "partial_success",
    "message": "Failed to import one or more surveys",
    "data": [{"num_surveys": 10, "num_variables": 500, "num_bindings": 500}],
    "errors": ["DOI 1 failed", "DOI 23 failed"]
}
```

For failures:

```json
{
    "status": "error",
    "message": "Unexpected errors",
    "errors": ["DOI 1 failed", "DOI 2 failed"]
}
```

For success with warnings:

```json
{
    "status": "success",
    "message": "All surveys imported successfully",
    "data": [{"num_surveys": 10, "num_variables": 500, "num_bindings": 500}],
    "warnings": ["Surveys 1,2,3 have been skipped"]
}
```

The method [`process_data`](#parsing-data) must have following behavior:

- On no failures it must always return `data` and
`warnings` list that will be included in the JSON response with status code 200

- If there is at least one survey successfully imported and at least one survey that
encountered errors while importing, the method needs to raise a custom exception which
will be caught by the caller to return a status code 207 (Partial response). The custom
exception must have all the data necessary to be included in the JSON response which are
`data`, `errors` and `message`.

- If none of the surveys have passed, the method must raise another custom exception that
embeds a message and all the errors that have occurred. Eventually the caller will catch
this exception and return a 400 response code with approproate JSON object made out of
exception.

- Finally the caller should have a bare exception to catch all other sort of exceptions
that have not been handled. A message of `Unexpected error` must be return with exception
in the errors and this response object must be returned with 500 code.

Eventually the frontend client code must consume this response and show the message or
errors based on the status code. If there is a non empty warnings, it must be shown
to the end user as well.

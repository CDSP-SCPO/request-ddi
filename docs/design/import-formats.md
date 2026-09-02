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

This section summaries the structures of files for different formats.

### Variable level metadata in DDI-C (XML) and survey metadata with CSV

This import format uses CSV file to provide a list of surveys and related metadata and
variable level metadata is provided by DDI-C XML files. The CSV file will contain the
list of surveys and DDI-C XML file for each survey will be fetched automatically from
the URL provided in the CSV file.

#### Required columns in the CSV file

The following columns are required to be present in the CSV file:

- doi
- collection
- sub-collection
- url

`url` is the URL at which the XML file can be downloaded where as `collection` and
`sub-collection` are the abstract hierarchial structures for organizing the surveys. The
`collection` and `sub-collection` are organization dependent and they are solely
responsible for providing logical entries.

If `url` is left empty for a row, the DDI-C XML file is not downloaded. Instead, it is
looked up by DOI among the files previously uploaded via the `/import/xml` endpoint (see
[Direct XML upload](#direct-xml-upload) below). This covers surveys for which no
downloadable URL exists.

Example of CSV file:

```csv
doi:10.21410/7E4/DDDHXW,fr,Données de recherche,Agoramétrie,https://data.sciencespo.fr/api/access/datafile/116

```

#### Required attributes in the fetched DDI-C XML file

The DDI-C XML file fetched from the URL provided in the CSV file must have the usual
attributes `docDscr`, `stdyDscr` and `dataDscr`.

#### Direct XML upload

The `/import/xml` endpoint accepts one or more DDI-C XML files directly, without going
through a URL. Each file is validated (same checks as when a file is fetched from a URL:
a DOI must be present and start with `doi:`, and the `titl` attribute must be present)
and stored, indexed by the DOI found inside it. Uploading a file whose DOI already exists
overwrites the previously stored one.

This does not import any survey by itself: a survey is only imported through the CSV
format above, with `url` left empty for the corresponding row. This keeps `collection`
and `sub-collection` assignment exclusively driven by the CSV, regardless of whether the
XML was fetched remotely or uploaded directly.

Once a survey's import succeeds using a volume file, that file's record is deleted
entirely. A later `force_import` on that same DOI therefore requires uploading the XML
again first — attempting it without doing so fails with the exact same error as if no
file had ever been uploaded for that DOI, by design: both cases require the same fix
(upload the XML), so they are not distinguished.

### Variable level metadata and survey metadata with CSV

This import format uses CSV for both survey metadata and variable level metadata. This
is relevant for the surveys that have no DDI-C documentation available. In this format,
each CSV file contains metadata of one survey.

The first line of the CSV must contain the headers of survey metadata and then second line
contains the values of these headers. The first two lines must contain following
columns:

- doi
- lang
- collection
- sub-collection
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

Third line must contain the headers of the variable level metadata and fourth line
onwards, variables must be documented. Here are the columns that must be included
for variable level metadata. Optional columns are indicated.

- name
- label
- type (optional)
- notes (optional)
- univers (optional)
- question_name (optional)
- question_text
- codes
- missing_value_codes (optional)

An example file for the CSV format can be found [here](csv_format_template.csv). Columns
`codes` and `missing_value_codes` must have following format:

```
<CodeNumber>,<CodeLabel>,<NumberOfResponses>
```

where `NumberOfResponses` is optional. Each code must be delimited by `|` as follows:

```
<Code1>,<CodeLabel1>,<CodeResponses1>|<Code2>,<CodeLabel2>,<CodeResponses2>|...
```

The above two formats must be implemented in the app. In fact any tabular data format
can be easily integrated into the app with carefully designed interface.

### Frontend

The principal job of the frontend is to show HTML form to upload the file. If and when
uploading data in multiple formats will be supported, a **separate input page** for
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

Each import format should have its dedicated page with instructions on the page on formats of
the input file(s). For the moment, following two endpoints must be implemented:

- `/import/ddic` - For importing via DDI-C XML files and using CSV to define list of surveys
- `/import/csv` - For importing variable level metadata using CSV

Finally, **it is desirable** to support uploading multiple files in each format. This gives
more freedom for the end users to organize their input files to their needs. In case of
`/import/ddic` endpoint this translates to importing multiple CSV files that contains
list of surveys where in case of `/import/csv` it is importing multiple CSV files where
each file corresponds to one survey.

### Backend

#### Validation

The first step on the backend is to validate the user supplied input file. Each format
should be validated as per [Django Form field validation](https://docs.djangoproject.com/en/6.0/ref/forms/validation/).
The following elements must be validated in the form class:

- First check the provided input file has the expected file extension. For instance, for
both `/import/ddic` and `/import/csv` endpoints the input file must have `.csv` extension.
If not return a [`ValidationError`](https://docs.djangoproject.com/en/6.0/ref/forms/validation/#raising-validationerror)
with an appropriate error message.

- Then check if input files have all the [required columns](#required-columns-in-the-csv-file) for
`/import/ddic` endpoint or [required columns](#variable-level-metadata-and-survey-metadata-with-csv) for
`/import/csv` endpoint. If there is any missing columns in the input file, stop processing and
return a [`ValidationError`](https://docs.djangoproject.com/en/6.0/ref/forms/validation/#raising-validationerror)
with an appropriate error message.

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
this exception and return a 400 response code with appropriate JSON object made out of
exception.

- Finally the caller should have a bare exception to catch all other sort of exceptions
that have not been handled. A message of `Unexpected error` must be return with exception
in the errors and this response object must be returned with 500 code.

Eventually the frontend client code must consume this response and show the message or
errors based on the status code. If there is a non empty warnings, it must be shown
to the end user as well.

#### Parsing data

The first step is to get a list of all DOIs in the input files and
compare them with the existent DOIs in the DB. Next step is to import variable level
metadata of new surveys into the DB. There are two very important pointers in the current
context of importing surveys into the DB that need to be considered:

- Based on the query parameter `force_import`, import behaviour must be modified.
If `force_import` is `False` or does not exist in the query parameters, only new surveys
that are in the input files must be imported. The response must include the list of
surveys that are imported and the list of surveys that have been ignored because they
already exist in the DB. If the `force_import` is truthy, all the surveys must be
reimported irrespective of the fact if they exist in the DB or not.

- The atomic transaction on the DB must be imposed on the individual survey level rather
than the HTTP request level. The rationale is that within atomic requests, a single error
in DB transaction will roll back all the DB operations. Hence, a single error can rollback
all DB operations of ALL surveys when atomic transaction is applied at the HTTP request.
On the other hand, using atomic transaction at the survey level will only rollback DB
operations of that survey which can be reimported easily after fixing the issues. It
is also important to push data into Elastic search only when all the variables are
successfully imported into SQL DB in order to avoid inconsistencies between SQL and
Elastic search.

As all the input formats must return the same JSON response, all the common code in the
import view handler must be included in a Mixin class and the individual import view
handlers must be derived from this Mixin class.

Besides defining template name, form class for each individual import view handler,
a method, say `get_data`, must be defined that reads the data provided from the frontend
and creates the Django tasks. We **must** absolutely keep this method as light as possible
to avoid timeouts. All the heavy lifting must be done inside the Django tasks.

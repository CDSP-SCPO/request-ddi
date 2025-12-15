# Changelog

<!-- <START NEW CHANGELOG ENTRY> -->

## main@{2025-09-30}...main@{2025-12-15}

([Full Changelog](https://gitlab.sciences-po.fr/cdspit/request/request-ddi/-/compare/c8c5828d57d87fea252d9b74bcb0e7d5f351b5b8...None?from_project_id=766&straight=false))

### New features added

- feat: :sparkles: Ignore missing values in percentage calculation [!442](https://gitlab.sciences-po.fr/cdspit/request/request-ddi/-/merge_requests/442) ([@malaury.lemaitresalmon](https://gitlab.sciences-po.fr/malaury.lemaitresalmon), [@mahendra.paipuri](https://gitlab.sciences-po.fr/mahendra.paipuri), [@william.feraux](https://gitlab.sciences-po.fr/william.feraux))
- feat: :sparkles: Add logs timing for views and API endpoint [!436](https://gitlab.sciences-po.fr/cdspit/request/request-ddi/-/merge_requests/436) ([@malaury.lemaitresalmon](https://gitlab.sciences-po.fr/malaury.lemaitresalmon), [@mahendra.paipuri](https://gitlab.sciences-po.fr/mahendra.paipuri), [@william.feraux](https://gitlab.sciences-po.fr/william.feraux))
- feat(api): add API versioning and separate API URLs [!431](https://gitlab.sciences-po.fr/cdspit/request/request-ddi/-/merge_requests/431) ([@malaury.lemaitresalmon](https://gitlab.sciences-po.fr/malaury.lemaitresalmon), [@mahendra.paipuri](https://gitlab.sciences-po.fr/mahendra.paipuri), [@william.feraux](https://gitlab.sciences-po.fr/william.feraux))
- feat: :sparkles: New Category section on detail page : Stats [!430](https://gitlab.sciences-po.fr/cdspit/request/request-ddi/-/merge_requests/430) ([@malaury.lemaitresalmon](https://gitlab.sciences-po.fr/malaury.lemaitresalmon), [@mahendra.paipuri](https://gitlab.sciences-po.fr/mahendra.paipuri), [@william.feraux](https://gitlab.sciences-po.fr/william.feraux))
- feat(health): add Elasticsearch health check [!426](https://gitlab.sciences-po.fr/cdspit/request/request-ddi/-/merge_requests/426) ([@malaury.lemaitresalmon](https://gitlab.sciences-po.fr/malaury.lemaitresalmon), [@mahendra.paipuri](https://gitlab.sciences-po.fr/mahendra.paipuri), [@william.feraux](https://gitlab.sciences-po.fr/william.feraux))
- feat: Add matomo js to base template [!422](https://gitlab.sciences-po.fr/cdspit/request/request-ddi/-/merge_requests/422) ([@malaury.lemaitresalmon](https://gitlab.sciences-po.fr/malaury.lemaitresalmon), [@mahendra.paipuri](https://gitlab.sciences-po.fr/mahendra.paipuri), [@william.feraux](https://gitlab.sciences-po.fr/william.feraux))

### Bugs fixed

- fix(export): fix metadata export by passing URL and question ID to static JS [!432](https://gitlab.sciences-po.fr/cdspit/request/request-ddi/-/merge_requests/432) ([@malaury.lemaitresalmon](https://gitlab.sciences-po.fr/malaury.lemaitresalmon), [@mahendra.paipuri](https://gitlab.sciences-po.fr/mahendra.paipuri))
- fix(export): handle multiple year formats in questions CSV export [!429](https://gitlab.sciences-po.fr/cdspit/request/request-ddi/-/merge_requests/429) ([@malaury.lemaitresalmon](https://gitlab.sciences-po.fr/malaury.lemaitresalmon), [@mahendra.paipuri](https://gitlab.sciences-po.fr/mahendra.paipuri), [@william.feraux](https://gitlab.sciences-po.fr/william.feraux))
- refactor(upload-views): add access control mixin and rewrite CSV upload view [!427](https://gitlab.sciences-po.fr/cdspit/request/request-ddi/-/merge_requests/427) ([@malaury.lemaitresalmon](https://gitlab.sciences-po.fr/malaury.lemaitresalmon), [@mahendra.paipuri](https://gitlab.sciences-po.fr/mahendra.paipuri), [@william.feraux](https://gitlab.sciences-po.fr/william.feraux))

### Maintenance and upkeep improvements

- Major restructuring of the code base to make it packagable [!439](https://gitlab.sciences-po.fr/cdspit/request/request-ddi/-/merge_requests/439) ([@malaury.lemaitresalmon](https://gitlab.sciences-po.fr/malaury.lemaitresalmon), [@mahendra.paipuri](https://gitlab.sciences-po.fr/mahendra.paipuri), [@william.feraux](https://gitlab.sciences-po.fr/william.feraux))
- Preparation for release 1 [!438](https://gitlab.sciences-po.fr/cdspit/request/request-ddi/-/merge_requests/438) ([@malaury.lemaitresalmon](https://gitlab.sciences-po.fr/malaury.lemaitresalmon), [@mahendra.paipuri](https://gitlab.sciences-po.fr/mahendra.paipuri), [@william.feraux](https://gitlab.sciences-po.fr/william.feraux))
- style: :art: Ruff fixes and media container removal [!437](https://gitlab.sciences-po.fr/cdspit/request/request-ddi/-/merge_requests/437) ([@malaury.lemaitresalmon](https://gitlab.sciences-po.fr/malaury.lemaitresalmon), [@mahendra.paipuri](https://gitlab.sciences-po.fr/mahendra.paipuri), [@william.feraux](https://gitlab.sciences-po.fr/william.feraux))
- Experimentation env [!435](https://gitlab.sciences-po.fr/cdspit/request/request-ddi/-/merge_requests/435) ([@malaury.lemaitresalmon](https://gitlab.sciences-po.fr/malaury.lemaitresalmon), [@mahendra.paipuri](https://gitlab.sciences-po.fr/mahendra.paipuri), [@william.feraux](https://gitlab.sciences-po.fr/william.feraux))
- Uniformisation via ruff, clean code, segmentation js et views [!417](https://gitlab.sciences-po.fr/cdspit/request/request-ddi/-/merge_requests/417) ([@william.feraux](https://gitlab.sciences-po.fr/william.feraux))

### Documentation improvements

- docs: :memo: Add architecture diagram [!433](https://gitlab.sciences-po.fr/cdspit/request/request-ddi/-/merge_requests/433) ([@malaury.lemaitresalmon](https://gitlab.sciences-po.fr/malaury.lemaitresalmon), [@mahendra.paipuri](https://gitlab.sciences-po.fr/mahendra.paipuri), [@william.feraux](https://gitlab.sciences-po.fr/william.feraux))

### Unlabelled Merged MRs

- chore(gunicorn): increase timeout from 300s to 3600s [!440](https://gitlab.sciences-po.fr/cdspit/request/request-ddi/-/merge_requests/440) ([@malaury.lemaitresalmon](https://gitlab.sciences-po.fr/malaury.lemaitresalmon))
- fix(csv-upload): handle POST requests correctly in CSVUploadViewCollection [!434](https://gitlab.sciences-po.fr/cdspit/request/request-ddi/-/merge_requests/434) ([@malaury.lemaitresalmon](https://gitlab.sciences-po.fr/malaury.lemaitresalmon), [@mahendra.paipuri](https://gitlab.sciences-po.fr/mahendra.paipuri))
- refactor(k8s): centralize base resources and simplify overlays [!428](https://gitlab.sciences-po.fr/cdspit/request/request-ddi/-/merge_requests/428) ([@malaury.lemaitresalmon](https://gitlab.sciences-po.fr/malaury.lemaitresalmon), [@mahendra.paipuri](https://gitlab.sciences-po.fr/mahendra.paipuri), [@william.feraux](https://gitlab.sciences-po.fr/william.feraux))
- style: :art: Code Formatting using Ruff And test: ✅ Creation of unit tests [!423](https://gitlab.sciences-po.fr/cdspit/request/request-ddi/-/merge_requests/423) ([@malaury.lemaitresalmon](https://gitlab.sciences-po.fr/malaury.lemaitresalmon), [@mahendra.paipuri](https://gitlab.sciences-po.fr/mahendra.paipuri), [@william.feraux](https://gitlab.sciences-po.fr/william.feraux))
- Small fixes and modifs [!415](https://gitlab.sciences-po.fr/cdspit/request/request-ddi/-/merge_requests/415) ([@william.feraux](https://gitlab.sciences-po.fr/william.feraux))

### [Contributors to this release](https://mahendrapaipuri.gitlab.io/gitlab-activity/usage#contributors-list)

[@malaury.lemaitresalmon](https://gitlab.sciences-po.fr/malaury.lemaitresalmon) | [@mahendra.paipuri](https://gitlab.sciences-po.fr/mahendra.paipuri) | [@william.feraux](https://gitlab.sciences-po.fr/william.feraux)

<!-- <END NEW CHANGELOG ENTRY> -->


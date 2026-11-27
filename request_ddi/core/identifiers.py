"""Identifiants d'enquêtes (`Id` en terminologie DDI-L).

Un identifiant est soit un vrai DOI (`doi:10.xxxx/yyyy`), soit, quand l'enquête n'en a
pas, un identifiant local `local:request/<identifiant>` où `<identifiant>` est
strictement alphanumérique (ni espace, ni tiret, ni underscore, etc.), par exemple le
nom court de l'enquête. Ce préfixe permet de distinguer les vrais DOIs, pour lesquels on
peut construire un lien vers la source, des identifiants internes.
"""

import re

DOI_PREFIX = "doi:"
LOCAL_PREFIX = "local:request/"

_LOCAL_ID_RE = re.compile(rf"^{re.escape(LOCAL_PREFIX)}[A-Za-z0-9]+$")


def is_doi(survey_id):
    return bool(survey_id) and survey_id.startswith(DOI_PREFIX)


def is_local_id(survey_id):
    return bool(survey_id) and _LOCAL_ID_RE.match(survey_id) is not None


def is_valid_survey_id(survey_id):
    return is_doi(survey_id) or is_local_id(survey_id)

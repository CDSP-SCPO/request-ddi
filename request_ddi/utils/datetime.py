# -- STDLIB
from datetime import datetime

from request_ddi.core.exceptions import InvalidDateError


def parse_date(d, doi):
    """Attempts to parse date in different formats and raises Exception if none of
    the formats work"""
    for fmt in ("%Y", "%Y-%m", "%Y-%m-%d"):
        try:
            return datetime.strptime(d, fmt).date()  # noqa: DTZ007
        except ValueError:
            pass
    msg = f"La date {d} pour l'enquête {doi} n'est pas valide : {d}"
    raise InvalidDateError(msg) from None

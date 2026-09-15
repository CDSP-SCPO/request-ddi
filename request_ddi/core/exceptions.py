class InvalidDateError(Exception):
    """Exception raised for invalid dates in import views."""

    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


class InvalidDOIError(Exception):
    """Exception raised for invalid DOI in import views."""

    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


class MissingAttributeError(Exception):
    """Exception raised for missing attributes in XML in import views."""

    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


class DataValidationError(Exception):
    """Exception raised for data validation in import views."""

    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


class InvalidDDICError(Exception):
    """Exception raised for invalid DDIC XML in import views."""

    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


class DDIXMLFileNotFoundError(Exception):
    """Exception raised when a CSV row has no URL and no matching XML has been
    uploaded for that DOI.
    """

    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


class DataImportError(Exception):
    """Exception raised for errors in import views."""

    def __init__(self, message, errors=None, warnings=None):
        super().__init__(message)
        self.message = message
        self.errors = errors or []
        self.warnings = warnings or []


class PartialDataImportError(Exception):
    """Exception raised for partial success in import views."""

    def __init__(self, message, data=None, errors=None):
        super().__init__(message)
        self.message = message
        self.data = data or []
        self.errors = errors or []

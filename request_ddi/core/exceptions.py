class DataImportError(Exception):
    """Exception raised for errors in upload view."""

    def __init__(self, message, errors=None, warnings=None):
        super().__init__(message)
        self.message = message
        self.errors = errors or []
        self.warnings = warnings or []


class PartialDataImportError(Exception):
    """Exception raised for partial success in upload view."""

    def __init__(self, message, data=None, errors=None):
        super().__init__(message)
        self.message = message
        self.data = data or []
        self.errors = errors or []

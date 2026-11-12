"""Stable error codes for localizing Studio messages in the browser."""


class StudioError(ValueError):
    def __init__(self, code, message, **params):
        super().__init__(message.format(**params))
        self.code = code
        self.params = params

    def payload(self):
        return {"error": str(self), "error_code": self.code, "error_params": self.params}

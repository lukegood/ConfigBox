from __future__ import annotations


class APIError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class InvalidToolError(APIError):
    def __init__(self) -> None:
        super().__init__("INVALID_TOOL", "Unsupported tool. Allowed values: claude, codex.", 404)

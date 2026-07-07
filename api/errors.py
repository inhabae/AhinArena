from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def error_body(code: str, message: str, details=None):
    error = {"code": code, "message": message}
    if details is not None:
        error["details"] = details

    return {"error": error}


def api_error(status_code: int, code: str, message: str):
    raise HTTPException(
        status_code=status_code,
        detail={
            "code": code,
            "message": message,
        },
    )


def http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail

    if isinstance(detail, dict) and "code" in detail and "message" in detail:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(detail["code"], detail["message"], detail.get("details")),
        )

    return JSONResponse(
        status_code=exc.status_code,
        content=error_body("http_error", "Request failed."),
    )


def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content=error_body(
            "validation_error",
            "Request body is invalid.",
            exc.errors(),
        ),
    )


def unexpected_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content=error_body(
            "internal_server_error",
            "Internal server error.",
        ),
    )

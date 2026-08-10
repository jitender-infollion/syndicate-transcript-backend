from typing import Any

from fastapi import Response


def success_response(data: Any = None, message: str = "Success") -> dict:
    return {"success": True, "message": message, "data": data}


def error_response(message: str, data: Any = None) -> dict:
    return {"success": False, "message": message, "data": data}


def pdf_response(pdf_bytes: bytes, filename: str, *, disposition: str = "inline") -> Response:
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'{disposition}; filename="{filename}"'},
    )

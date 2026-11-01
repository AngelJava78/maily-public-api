from pydantic import BaseModel, ConfigDict, Field

from src.messages import ErrorCode


class ErrorResponse(BaseModel):
    """Uniform body of every error of the API, the same as maily-system-api (FR-013)."""

    model_config = ConfigDict(
        json_schema_extra={"description": "Formato uniforme de todos los errores."}
    )

    code: ErrorCode = Field(description="Código estable del error (en inglés).")
    message: str = Field(description="Mensaje en español, sin detalles técnicos.")

"""Health contract v1 of the MailySoft services, at the root, without token and never cached."""

from fastapi import APIRouter, Response
from fastapi.responses import JSONResponse

from src.dependencies import HealthServiceDep
from src.dtos.health import InfoResponse, LiveResponse, ReadyResponse

router = APIRouter(tags=["Salud"])

NO_STORE = "no-store"


@router.get(
    "/health/live",
    operation_id="health_live",
    summary="El proceso está vivo",
    description="Responde `ok` mientras el proceso atienda HTTP, sin consultar la base de datos.",
    response_model=LiveResponse,
)
async def live(response: Response) -> LiveResponse:
    response.headers["Cache-Control"] = NO_STORE
    return LiveResponse(status="ok")


@router.get(
    "/health/ready",
    operation_id="health_ready",
    summary="El servicio puede leer la base de datos",
    description=(
        "Comprueba la conexión a la base de datos compartida con una consulta trivial, dentro de "
        "`HEALTH_READY_TIMEOUT_SECONDS`. 200 si responde; 503 si no, con el mismo cuerpo."
    ),
    response_model=ReadyResponse,
    responses={
        503: {
            "model": ReadyResponse,
            "description": "La base de datos no respondió, rechazó la conexión o falló.",
        }
    },
)
async def ready(service: HealthServiceDep) -> JSONResponse:
    result = await service.ready()
    return JSONResponse(
        status_code=200 if result.status == "ok" else 503,
        content=result.model_dump(mode="json"),
        headers={"Cache-Control": NO_STORE},
    )


@router.get(
    "/info",
    operation_id="service_info",
    summary="Identificación del servicio",
    description="Servicio, versión, commit, fecha del build y ambiente (`unknown` si no se conocen).",
    response_model=InfoResponse,
)
async def info(response: Response, service: HealthServiceDep) -> InfoResponse:
    response.headers["Cache-Control"] = NO_STORE
    return service.info()

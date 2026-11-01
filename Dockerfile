FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

RUN pip install --no-cache-dir "uv==0.13.1"

# Solo las dependencias del servicio: pytest y httpx (grupo dev) no entran en la imagen.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY src ./src

# Identificación del build para /info (contrato de salud v1). Van al final para que un commit nuevo
# no invalide la capa de las dependencias. Sin argumentos quedan vacías y /info publica "unknown".
# APP_ENVIRONMENT no va en la imagen: se inyecta al desplegar.
ARG APP_COMMIT_SHA=""
ARG APP_BUILD_DATE=""
ENV APP_COMMIT_SHA=$APP_COMMIT_SHA \
    APP_BUILD_DATE=$APP_BUILD_DATE

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

# Railway inyecta PORT. --no-proxy-headers: la IP del cliente la resuelve src/rate_limit.py contando
# los proxies de confianza (TRUSTED_PROXY_HOPS), no uvicorn.
CMD ["sh", "-c", "exec uvicorn src.main:create_app_from_environment --factory --host 0.0.0.0 --port ${PORT:-8000} --no-proxy-headers"]

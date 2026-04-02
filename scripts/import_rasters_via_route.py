import asyncio
import os
from pathlib import Path
from uuid import uuid4

from fastapi.routing import APIRoute
from httpx import ASGITransport, AsyncClient

DEFAULT_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/atlas"
DEFAULT_SYNC_DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/atlas"
DEFAULT_SECRET_KEY = "00e6c33aa1a2d3da5fa7766aae8b1dfc5293341f7104a92097a5e26b09640059"
DEFAULT_RASTER_DIR = Path(r"C:\Users\rdra\OneDrive\Área de Trabalho\rasters")

os.environ.setdefault("DATABASE_URL", DEFAULT_DATABASE_URL)
os.environ.setdefault("SYNC_DATABASE_URL", DEFAULT_SYNC_DATABASE_URL)
os.environ.setdefault("SECRET_KEY", DEFAULT_SECRET_KEY)
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("TOKEN_TYPE", "Bearer")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
os.environ.setdefault("REFRESH_TOKEN_EXPIRE_MINUTES", "1440")
os.environ.setdefault("ENVIRONMENT", "local")

from controllers.auth_controller import AuthController
from main import app
from sql_app import models


async def fake_user():
    return models.AnonymousUser(id=uuid4(), ocupation="script")


route = next(
    route for route in app.routes
    if isinstance(route, APIRoute) and route.path == "/raster/{raster_name}"
)
permission_dependency = next(
    dependency.call
    for dependency in route.dependant.dependencies
    if getattr(dependency.call, "__name__", "") == "permission_dependency"
)


async def import_raster(client: AsyncClient, raster_path: Path) -> tuple[str, int, str]:
    with raster_path.open("rb") as file_handle:
        response = await client.post(
            f"/raster/{raster_path.stem}",
            files={"file": (raster_path.name, file_handle, "image/tiff")},
        )

    try:
        payload = response.json()
    except Exception:
        payload = response.text

    return raster_path.name, response.status_code, str(payload)


async def main():
    raster_dir = Path(os.getenv("RASTER_IMPORT_DIR", str(DEFAULT_RASTER_DIR)))
    raster_filter = os.getenv("RASTER_IMPORT_FILTER")
    raster_files = sorted(
        [*raster_dir.glob("*.tif"), *raster_dir.glob("*.tiff")],
        key=lambda path: path.name.lower(),
    )

    if raster_filter:
        raster_files = [path for path in raster_files if raster_filter.lower() in path.name.lower()]

    if not raster_files:
        raise FileNotFoundError(f"Nenhum raster encontrado em {raster_dir}")

    print(f"Importando {len(raster_files)} raster(s) de {raster_dir}")

    app.dependency_overrides[AuthController.get_user_from_token] = fake_user
    app.dependency_overrides[permission_dependency] = lambda: True

    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://local-app",
            timeout=None,
        ) as client:
            for raster_path in raster_files:
                print(f"Iniciando {raster_path.name}", flush=True)
                name, status_code, payload = await import_raster(client, raster_path)
                print(f"{name}: {status_code} -> {payload}")

    app.dependency_overrides.clear()


if __name__ == "__main__":
    asyncio.run(main())

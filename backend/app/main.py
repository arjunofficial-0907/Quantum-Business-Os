from fastapi import FastAPI

from app.core.config import get_settings
from app.api.v1.auth.router import router as auth_router
from app.api.v1.billing import router as billing_router
from app.api.v1.organization.router import router as organization_router
from app.api.v1.branch.router import router as branch_router
from app.api.v1.rbac.router import router as rbac_router
from app.api.v1.membership.router import router as membership_router
from app.api.v1.license.router import router as license_router

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
)

app.include_router(
    auth_router,
    prefix="/api/v1",
)

app.include_router(
    rbac_router,
    prefix="/api/v1",

)

app.include_router(
    organization_router,
    prefix="/api/v1",
)

app.include_router(
    branch_router,
    prefix="/api/v1",
)

app.include_router(
    membership_router,
    prefix="/api/v1",
)

app.include_router(
    license_router,
    prefix="/api/v1",
)

app.include_router(
    billing_router,
    prefix="/api/v1",
)

@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}

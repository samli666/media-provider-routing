import os

from fastapi import FastAPI, HTTPException

from .routing_policy import InfraiError, MediaRouteRequest, RouteDecision, apply_media_route

app = FastAPI(title="Media provider routing")


@app.post("/media/routes", response_model=RouteDecision)
async def set_media_route(request: MediaRouteRequest) -> RouteDecision:
    api_key = os.environ.get("INFRAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="INFRAI_API_KEY is required")
    try:
        return await apply_media_route(request, api_key)
    except InfraiError as exc:
        status_code = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(
            status_code=status_code,
            detail={"code": exc.code, "error": exc.details},
        ) from exc

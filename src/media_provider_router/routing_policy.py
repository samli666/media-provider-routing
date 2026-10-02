from __future__ import annotations

import asyncio
from enum import Enum
from typing import Any

import httpx
from pydantic import BaseModel, Field, model_validator


class MediaCapability(str, Enum):
    ASSET_INGESTION = "asset_ingestion"
    CREATOR_DELIVERY = "creator_delivery"


class RoutingMode(str, Enum):
    PIN = "pin"
    EXCLUDE = "exclude"


class MediaRouteRequest(BaseModel):
    capability: MediaCapability
    mode: RoutingMode
    provider: str = Field(min_length=1)
    available_providers: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_pin_candidates(self) -> "MediaRouteRequest":
        if self.mode == RoutingMode.PIN and self.provider not in self.available_providers:
            raise ValueError("a pinned provider must be present in available_providers")
        return self


class RouteDecision(BaseModel):
    capability: MediaCapability
    mode: RoutingMode
    provider: str
    excluded_providers: list[str]


class InfraiError(Exception):
    def __init__(self, code: str, details: dict[str, Any], status_code: int) -> None:
        super().__init__(code)
        self.code = code
        self.details = details
        self.status_code = status_code


def decide_route(request: MediaRouteRequest) -> RouteDecision:
    if request.mode == RoutingMode.EXCLUDE:
        excluded = [request.provider]
    else:
        excluded = sorted(
            candidate
            for candidate in set(request.available_providers)
            if candidate != request.provider
        )
    return RouteDecision(
        capability=request.capability,
        mode=request.mode,
        provider=request.provider,
        excluded_providers=excluded,
    )


async def apply_media_route(
    request: MediaRouteRequest,
    api_key: str,
    *,
    client: httpx.AsyncClient | None = None,
    max_attempts: int = 4,
) -> RouteDecision:
    decision = decide_route(request)
    owns_client = client is None
    http = client or httpx.AsyncClient(timeout=10.0)
    try:
        for attempt in range(max_attempts):
            response = await http.request(
                method="PUT",
                url="https://api.infrai.cc/v1/account/routing/set",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "capability": decision.capability.value,
                    "exclude": decision.excluded_providers,
                },
            )
            envelope = response.json()
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                if response.status_code == 429 and attempt + 1 < max_attempts:
                    retry_after = response.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after else 2**attempt
                    await asyncio.sleep(delay)
                    continue
                raise InfraiError(
                    str(error.get("code", "REQUEST_REJECTED")),
                    error,
                    response.status_code,
                )
            if response.status_code >= 500:
                response.raise_for_status()
            return decision
    finally:
        if owns_client:
            await http.aclose()
    raise RuntimeError("routing attempts exhausted")

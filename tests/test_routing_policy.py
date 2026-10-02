import asyncio
import httpx
import pytest
from pydantic import ValidationError

from media_provider_router.routing_policy import (
    MediaCapability,
    MediaRouteRequest,
    RoutingMode,
    apply_media_route,
)


def test_processing_job_is_not_configurable() -> None:
    with pytest.raises(ValidationError):
        MediaRouteRequest(
            capability="processing_job",
            mode=RoutingMode.EXCLUDE,
            provider="studio-render",
        )


def test_pin_ingestion_provider_excludes_other_candidates() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["json"] = __import__("json").loads(request.content)
        return httpx.Response(200, json={"ok": True, "data": {}, "error": None, "metadata": {}})

    request = MediaRouteRequest(
        capability=MediaCapability.ASSET_INGESTION,
        mode=RoutingMode.PIN,
        provider="studio-render",
        available_providers=["fast-transcode", "studio-render", "archive-media"],
    )
    async def exercise_route():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await apply_media_route(request, "test-key", client=client)

    decision = asyncio.run(exercise_route())

    assert decision.excluded_providers == ["archive-media", "fast-transcode"]
    assert captured == {
        "method": "PUT",
        "json": {
            "capability": "asset_ingestion",
            "exclude": ["archive-media", "fast-transcode"],
        },
    }

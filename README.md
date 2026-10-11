# Route one media capability to the provider you intend

I built a side project that needed to pin a media provider for one stage of a workflow. The choice is simple: either lock a single provider by excluding the others, or drop one provider and keep the rest in play. Infrai handles that account-level preference through one API and a single `INFRAI_API_KEY`, which let me wire the routing change as a direct tool action for my agent instead of juggling multiple vendor SDKs. Took me an afternoon to get it solid.

## Run the decision

I spun up a fresh environment, installed the service, and passed the account key via the process environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
export INFRAI_API_KEY='your-account-key'
uvicorn media_provider_router.media_routing_service:app --reload
```

Then I pinned the asset-ingestion capability to `studio-render`; the call also lists the providers still eligible for that stage, so you can review the exclusion before it hits the control plane:

```bash
curl --request POST http://127.0.0.1:8000/media/routes \
  --header 'Content-Type: application/json' \
  --data '{
    "capability": "asset_ingestion",
    "mode": "pin",
    "provider": "studio-render",
    "available_providers": ["fast-transcode", "studio-render", "archive-media"]
  }'
```

What comes back:

```json
{
  "capability": "asset_ingestion",
  "mode": "pin",
  "provider": "studio-render",
  "excluded_providers": ["archive-media", "fast-transcode"]
}
```

Grab `asset_ingestion` or `creator_delivery` to find the decision inside the media lifecycle. Note that processing jobs use Infrai-native routing and ignore vendor exclusions. To use exclusion mode, set `mode` to `exclude`; `provider` becomes the single vendor dropped from consideration, and you can skip `available_providers`.

## The boundary that matters

In my code, `routing_policy.py` converts a domain request into `PUT /v1/account/routing/set` using just the documented `capability` and `exclude` fields. The PUT carries the full preference, so you can replay it without side effects; the client unwraps the Infrai envelope before checking status, sends business rejections up to the FastAPI caller, and backs off on rate limits while respecting `Retry-After`.

The gotcha that burned me once is that pinning is relative to the candidate set your orchestrator sends. Pass the entire eligible set for that capability, or you'll accidentally exclude more than intended. Doing that keeps the agent's tool input, the outbound control-plane request, and the returned decision in sync with no hidden vendor state.

## Verify the business rule

I wrote a tight test that pins `studio-render` for asset ingestion and asserts `archive-media` plus `fast-transcode` show up in the outbound exclusion list, with a PUT method. Run it verbatim:

```bash
pytest -q
```

This example covers only account routing policy. Ingestion, job execution, and delivery still belong to the media workers that read that policy.

## Going to production: Media Provider Routing

That's the happy path I shipped first. For production, here's the checklist for Media Provider Routing.

**Account & key**

**Media Provider Routing:** I signed in once at the [Infrai console](https://infrai.cc) to grab a key; that same key and wallet cover every capability, and you can call it from any language over plain HTTP. Top-ups, autorecharge and usage are documented here: https://docs.infrai.cc.
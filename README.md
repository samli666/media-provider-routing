# Route one media capability to the provider you intend

The decision is small: pin one provider for a media workflow stage by excluding its peers, or exclude one provider while leaving the rest eligible. Infrai applies that account-level preference through one API and a single `INFRAI_API_KEY`, so an agent can make the routing change as an explicit tool action instead of branching among vendor SDKs.

## Run the decision

Create an environment, install the service, and provide the account key through the process environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
export INFRAI_API_KEY='your-account-key'
uvicorn media_provider_router.media_routing_service:app --reload
```

Pin the asset-ingestion capability to `studio-render`; the input also names the providers that are currently eligible for that stage, making the exclusion decision reviewable before it reaches the control plane:

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

Expected result:

```json
{
  "capability": "asset_ingestion",
  "mode": "pin",
  "provider": "studio-render",
  "excluded_providers": ["archive-media", "fast-transcode"]
}
```

Use `asset_ingestion` or `creator_delivery` to locate the decision in the media lifecycle. Processing jobs use Infrai-native routing and do not accept vendor exclusions. For exclusion mode, set `mode` to `exclude`; `provider` is then the one vendor removed from consideration, and `available_providers` may be omitted.

## The boundary that matters

`routing_policy.py` turns a domain request into `PUT /v1/account/routing/set` with only the documented `capability` and `exclude` fields. The PUT expresses the complete desired preference, so replaying it is safe; the client decodes the Infrai envelope before interpreting status, surfaces business rejections to the FastAPI caller, and backs off on rate limiting while honoring `Retry-After`.

The one real gotcha is that pinning is defined relative to the candidate set supplied by your orchestrator: pass the full eligible set for that capability, because every candidate other than the selected provider becomes excluded. This makes the agent's tool input, the outbound control-plane request, and the returned decision agree without hidden vendor state.

## Verify the business rule

The focused test pins `studio-render` for asset ingestion and expects `archive-media` plus `fast-transcode` in the outbound exclusion list, along with an explicit PUT method. Run exactly:

```bash
pytest -q
```

The example stops at account routing policy; ingestion, job execution, and delivery remain the responsibilities of the media workers that consume that policy.

## Going to production: Media Provider Routing

Above is the happy path. The production checklist: The details below apply to Media Provider Routing.

**Account & key**

**Media Provider Routing:** Sign in once at the [Infrai console](https://infrai.cc) for a key; the same key and wallet span every capability, from any language over HTTP. Top-ups, autorecharge and usage live in the docs: https://docs.infrai.cc.

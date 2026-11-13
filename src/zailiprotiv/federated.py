"""Signing in to the Anthropic API with GitHub's identity instead of an API key (workload identity federation).

In a GitHub Actions job allowed to ask for an identity token (`permissions: id-token: write`), GitHub gives a
short-lived token saying which repository, branch and workflow is running; Anthropic exchanges it, under a federation
rule set up in the Console, for a short-lived API token. Nothing secret is stored. The rule's ids are in the workflow
(ANTHROPIC_FEDERATION_RULE_ID and the rest below); they grant nothing by themselves.

A batch can be waited on for longer than a token lasts, so the client mints a new one before the old one runs out.
"""
from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request

AUDIENCE = "https://api.anthropic.com"
EXCHANGE = "https://api.anthropic.com/v1/oauth/token"
SETTINGS = {"federation_rule_id": "ANTHROPIC_FEDERATION_RULE_ID", "organization_id": "ANTHROPIC_ORGANIZATION_ID",
            "service_account_id": "ANTHROPIC_SERVICE_ACCOUNT_ID", "workspace_id": "ANTHROPIC_WORKSPACE_ID"}
MARGIN = 300  # seconds before a token runs out when a new one is minted


def available() -> bool:
    return bool(os.environ.get("ACTIONS_ID_TOKEN_REQUEST_URL") and all(os.environ.get(v) for v in SETTINGS.values()))


def _post(url: str, body: dict) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def github_token() -> str:
    url = os.environ["ACTIONS_ID_TOKEN_REQUEST_URL"] + "&audience=" + urllib.parse.quote(AUDIENCE, safe="")
    req = urllib.request.Request(url, headers={"authorization": "bearer " + os.environ["ACTIONS_ID_TOKEN_REQUEST_TOKEN"]})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())["value"]


def mint() -> tuple[str, int]:
    """A new Anthropic API token and how many seconds it lasts."""
    body = {"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": github_token(),
            **{k: os.environ[v] for k, v in SETTINGS.items()}}
    try:
        answer = _post(EXCHANGE, body)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"the token exchange was refused ({e.code}): {e.read()[:300]!r}") from None
    token = answer.get("access_token") or next(v for k, v in answer.items() if k.endswith("token"))
    return token, int(answer.get("expires_in") or 3600)


class Client:
    """Stands in for anthropic.Anthropic where the code uses `.messages`, with a fresh token whenever needed."""

    def __init__(self, mint=mint):
        self._mint, self._client, self._until = mint, None, 0.0

    @property
    def messages(self):
        if self._client is None or time.time() >= self._until:
            import anthropic
            token, lasts = self._mint()
            self._client = anthropic.Anthropic(auth_token=token, api_key=None)
            self._until = time.time() + max(60, lasts - MARGIN)
        return self._client.messages

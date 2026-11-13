"""Signing in to the Anthropic API with GitHub's identity instead of an API key (workload identity federation).

In a GitHub Actions job allowed to ask for an identity token (`permissions: id-token: write`), GitHub gives a
short-lived token saying which repository, branch and workflow is running; the Anthropic client exchanges it, under
the federation rule set up in the Console, for a short-lived API token, and exchanges again before that one runs out
(`anthropic.WorkloadIdentityCredentials`). Nothing secret is stored. The rule's ids come from the workflow
(ANTHROPIC_FEDERATION_RULE_ID and the rest below); they grant nothing by themselves.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request

AUDIENCE = "https://api.anthropic.com"
SETTINGS = {"federation_rule_id": "ANTHROPIC_FEDERATION_RULE_ID", "organization_id": "ANTHROPIC_ORGANIZATION_ID",
            "service_account_id": "ANTHROPIC_SERVICE_ACCOUNT_ID", "workspace_id": "ANTHROPIC_WORKSPACE_ID"}


def available() -> bool:
    return bool(os.environ.get("ACTIONS_ID_TOKEN_REQUEST_URL") and all(os.environ.get(v) for v in SETTINGS.values()))


def github_token() -> str:
    """A fresh identity token from GitHub for this job (each lasts minutes, so one is asked for at every exchange)."""
    url = os.environ["ACTIONS_ID_TOKEN_REQUEST_URL"] + "&audience=" + urllib.parse.quote(AUDIENCE, safe="")
    req = urllib.request.Request(url, headers={"authorization": "bearer " + os.environ["ACTIONS_ID_TOKEN_REQUEST_TOKEN"]})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())["value"]


def client():
    import anthropic
    return anthropic.Anthropic(credentials=anthropic.WorkloadIdentityCredentials(
        identity_token_provider=github_token, **{k: os.environ[v] for k, v in SETTINGS.items()}))

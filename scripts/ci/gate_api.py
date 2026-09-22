"""The gate's only door to the forge API (#137, #143).

Every subcommand's decision logic is pure over plain data; this is
the one layer that talks to the network, and the tests never touch it.
"""

import json
import os
import urllib.error
import urllib.request


API = os.environ.get("GITHUB_API_URL", "https://api.github.com")
SERVER = os.environ.get("GITHUB_SERVER_URL", "https://github.com")


def api_url(path):
    """The absolute URL for an API path, refusing any non-HTTP scheme.

    `API` comes from the environment, so a hostile or fat-fingered
    `GITHUB_API_URL` could otherwise steer the gate's own reads at
    `file:` and have it judge a PR on whatever it found on disk. The
    scheme is checked here, once, because this is the only place a URL
    is built.
    """
    url = API + path
    if not url.startswith(("https://", "http://")):
        scheme = url.split(":", 1)[0] if ":" in url else url
        raise ValueError(f"GITHUB_API_URL must be http(s) — refusing scheme {scheme!r}")
    return url


def fetch(path, token):
    """GET one API path, parsed. The only network call in this file."""
    req = urllib.request.Request(  # noqa: S310 — api_url rejects every other scheme
        api_url(path),
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(req) as response:  # noqa: S310 — checked above
        return json.load(response)


def graphql(query, variables, token):
    """POST one GraphQL query — the read for what REST does not expose.

    Review-thread resolution exists only in the GraphQL schema, so this
    is the file's second network door: a POST to the fixed /graphql
    path, under the same scheme guard as `fetch`.
    """
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(  # noqa: S310 — api_url rejects every other scheme
        api_url("/graphql"),
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req) as response:  # noqa: S310 — checked above
        payload = json.load(response)
    if payload.get("errors"):
        raise RuntimeError(f"GraphQL errors: {payload['errors']}")
    return payload["data"]


def post(path, token):
    """POST one empty-bodied API path — the file's one write door.

    Exists solely for `rerun-failed-jobs` (#190): superseding a stale
    red check run takes a write, where everything the gate JUDGES stays
    behind the two read doors above. Same scheme guard; returns the
    HTTP status, since the endpoint answers 201 with no body.
    """
    req = urllib.request.Request(  # noqa: S310 — api_url rejects every other scheme
        api_url(path),
        data=b"",
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(req) as response:  # noqa: S310 — checked above
        return response.status


def paginate(path, token, key=None):
    """Every page of a list endpoint, 100 at a time."""
    sep = "&" if "?" in path else "?"
    items = []
    page = 1
    while True:
        batch = fetch(f"{path}{sep}per_page=100&page={page}", token)
        if key is not None:
            batch = batch.get(key, [])
        items.extend(batch)
        if len(batch) < 100:
            return items
        page += 1

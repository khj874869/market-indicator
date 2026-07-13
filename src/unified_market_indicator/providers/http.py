from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def get_json(url: str, params: dict[str, Any] | None = None, timeout: float = 15.0) -> Any:
    query = f"?{urlencode(params)}" if params else ""
    request = Request(
        f"{url}{query}",
        headers={
            "Accept": "application/json",
            "User-Agent": "unified-market-indicator/0.1",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))

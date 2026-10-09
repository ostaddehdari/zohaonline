"""G4F integration with explicit provider/model selection.

The application never uses RetryProvider/default routing for user requests. Only
provider/model pairs that passed the hourly health probe are selectable.
"""
from __future__ import annotations

import importlib
from typing import Any


def resolve_provider(provider_path: str):
    module_name, class_name = provider_path.split(":", 1)
    module = importlib.import_module(module_name)
    return getattr(module, class_name)


def extract_content(response: Any) -> str:
    try:
        value = response.choices[0].message.content
        if value is not None:
            return str(value).strip()
    except (AttributeError, IndexError, KeyError, TypeError):
        pass
    if isinstance(response, str):
        return response.strip()
    if isinstance(response, dict):
        try:
            return str(response["choices"][0]["message"]["content"]).strip()
        except (KeyError, IndexError, TypeError):
            pass
    return ""


def run_completion(endpoint, messages, timeout: int = 60) -> str:
    """Run one completion using the already-probed explicit endpoint."""
    from g4f.client import Client

    provider = resolve_provider(endpoint.provider_path)
    client = Client(provider=provider)
    response = client.chat.completions.create(
        model=endpoint.model_name,
        provider=provider,
        messages=messages,
        timeout=timeout,
    )
    content = extract_content(response)
    if not content:
        raise RuntimeError("ارائه‌دهنده پاسخ متنی معتبری برنگرداند.")
    return content

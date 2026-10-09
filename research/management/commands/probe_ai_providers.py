from __future__ import annotations

import asyncio
import inspect
import time
from dataclasses import dataclass
from typing import Any

from django.core.management.base import BaseCommand
from django.utils import timezone

from research.ai_services import extract_content
from research.models import AIEndpointStatus, AIProbeRun


AUTH_ERROR_MARKERS = (
    "missingauth", "authentication required", "error 401", "no .har file",
    "api key", "login required", "cookie", "cookies", "har file",
)


@dataclass(frozen=True)
class Candidate:
    provider: type
    provider_name: str
    provider_path: str
    model_name: str
    needs_auth: bool
    skip_reason: str = ""


def _provider_classes():
    import g4f.Provider as provider_module

    raw = list(getattr(provider_module, "__providers__", []) or [])
    if not raw:
        for name in dir(provider_module):
            obj = getattr(provider_module, name, None)
            if inspect.isclass(obj) and (
                hasattr(obj, "create_async_generator") or hasattr(obj, "create_completion")
            ):
                raw.append(obj)
    seen = set()
    result = []
    excluded = {"BaseProvider", "AsyncProvider", "AsyncGeneratorProvider", "RetryProvider", "IterListProvider"}
    for provider in raw:
        if not inspect.isclass(provider) or provider.__name__ in excluded or provider.__name__.startswith("_"):
            continue
        path = f"{provider.__module__}:{provider.__name__}"
        if path in seen:
            continue
        seen.add(path)
        result.append(provider)
    return result


def _model_names(provider: type):
    values: Any = getattr(provider, "models", None)
    if callable(values):
        try:
            values = values()
        except Exception:
            values = None
    if isinstance(values, dict):
        values = list(values.keys())
    elif isinstance(values, str):
        values = [values]
    elif not isinstance(values, (list, tuple, set)):
        values = []
    models = []
    for value in values:
        name = getattr(value, "name", None) or getattr(value, "model", None) or str(value)
        name = str(name).strip()
        if name and name not in models and not name.startswith("<"):
            models.append(name)
    default_model = getattr(provider, "default_model", None)
    if default_model:
        default_name = getattr(default_model, "name", None) or str(default_model)
        if default_name and default_name not in models:
            models.insert(0, default_name)
    return models or ["default"]


def discover_candidates():
    candidates = []
    for provider in _provider_classes():
        name = provider.__name__
        path = f"{provider.__module__}:{name}"
        needs_auth = bool(
            getattr(provider, "needs_auth", False)
            or getattr(provider, "auth_required", False)
            or getattr(provider, "requires_auth", False)
        )
        working = getattr(provider, "working", None)
        skip_reason = ""
        if needs_auth:
            skip_reason = "این ارائه‌دهنده به ورود، کلید، Cookie یا فایل HAR نیاز دارد."
        elif working is False:
            skip_reason = "ارائه‌دهنده در خود g4f به‌عنوان غیرفعال علامت‌گذاری شده است."
        for model_name in _model_names(provider):
            candidates.append(Candidate(provider, name, path, model_name, needs_auth, skip_reason))
    return candidates


async def probe_candidate(candidate: Candidate, timeout: int, semaphore: asyncio.Semaphore):
    if candidate.skip_reason:
        return candidate, "skipped", None, "", candidate.skip_reason
    async with semaphore:
        started = time.monotonic()
        try:
            from g4f.client import AsyncClient

            client = AsyncClient(provider=candidate.provider)
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=candidate.model_name,
                    provider=candidate.provider,
                    messages=[{"role": "user", "content": "سلام"}],
                    timeout=timeout,
                ),
                timeout=timeout + 5,
            )
            content = extract_content(response)
            if not content:
                raise RuntimeError("پاسخ خالی بود.")
            latency = int((time.monotonic() - started) * 1000)
            return candidate, "active", latency, content[:500], ""
        except Exception as exc:
            error = f"{exc.__class__.__name__}: {exc}"[:2000]
            lowered = error.casefold()
            status = "skipped" if any(marker in lowered for marker in AUTH_ERROR_MARKERS) else "inactive"
            return candidate, status, None, "", error


class Command(BaseCommand):
    help = "تمام ارائه‌دهندگان و مدل‌های اعلام‌شده g4f را با پیام سلام پایش می‌کند."

    def add_arguments(self, parser):
        parser.add_argument("--timeout", type=int, default=20)
        parser.add_argument("--concurrency", type=int, default=3)

    def handle(self, *args, **options):
        run = AIProbeRun.objects.create()
        now = timezone.now()
        try:
            candidates = discover_candidates()
        except Exception as exc:
            run.finished_at = timezone.now()
            run.details = {"discovery_error": f"{exc.__class__.__name__}: {exc}"}
            run.save(update_fields=["finished_at", "details"])
            raise

        semaphore = asyncio.Semaphore(max(1, options["concurrency"]))

        async def execute():
            return await asyncio.gather(*[
                probe_candidate(item, options["timeout"], semaphore) for item in candidates
            ])

        results = asyncio.run(execute())
        counters = {"active": 0, "inactive": 0, "skipped": 0}
        for candidate, status, latency, response, error in results:
            existing = AIEndpointStatus.objects.filter(
                provider_path=candidate.provider_path,
                model_name=candidate.model_name,
            ).first()
            failures = 0 if status == "active" else ((existing.consecutive_failures if existing else 0) + 1)
            defaults = {
                "provider_name": candidate.provider_name,
                "status": status,
                "needs_auth": candidate.needs_auth or status == "skipped",
                "latency_ms": latency,
                "response_excerpt": response,
                "last_error": error,
                "last_checked_at": now,
                "consecutive_failures": failures,
                "metadata": {"g4f_working_flag": str(getattr(candidate.provider, "working", None))},
            }
            if status == "active":
                defaults["last_success_at"] = now
            AIEndpointStatus.objects.update_or_create(
                provider_path=candidate.provider_path,
                model_name=candidate.model_name,
                defaults=defaults,
            )
            counters[status] += 1

        run.finished_at = timezone.now()
        run.total = len(results)
        run.active = counters["active"]
        run.inactive = counters["inactive"]
        run.skipped = counters["skipped"]
        run.details = {"timeout": options["timeout"], "concurrency": options["concurrency"]}
        run.save(update_fields=["finished_at", "total", "active", "inactive", "skipped", "details"])
        self.stdout.write(self.style.SUCCESS(
            f"AI probe completed: total={run.total} active={run.active} inactive={run.inactive} skipped={run.skipped}"
        ))

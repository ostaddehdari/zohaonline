from __future__ import annotations

import base64
import json
import re
import unicodedata
from collections import Counter
from html import unescape
from io import BytesIO
from urllib.parse import quote

import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone

from .ai_services import run_completion
from .models import AIGenerationLog, AIEndpointStatus, Research, normalize_fa

STOPWORDS = {
    'است','هست','بود','شد','شود','شده','این','آن','برای','از','به','در','با','و','یا','که','را','یک','هر','بر','تا','اگر','اما','نیز','می','ما','شما','او','آنها','های','ها','ای','خود','کرد','کرده','کند','کنند','هم','پس','چه','چون','دارد','دارند','بین','همه','مورد','متن','فیش'
}


def plain_text(html: str) -> str:
    text = re.sub(r'<\s*br\s*/?>', '\n', html or '', flags=re.I)
    text = re.sub(r'</(?:p|div|li|blockquote|h[1-6])\s*>', '\n', text, flags=re.I)
    text = re.sub(r'<[^>]+>', ' ', text)
    return re.sub(r'[ \t]+', ' ', unescape(text)).strip()


def choose_endpoint():
    return (
        AIEndpointStatus.objects.filter(status='active')
        .order_by('-last_success_at', 'latency_ms', 'provider_name')
        .first()
    )


def _json_payload(raw: str):
    raw = (raw or '').strip()
    raw = re.sub(r'^```(?:json)?\s*', '', raw, flags=re.I)
    raw = re.sub(r'\s*```$', '', raw)
    start = raw.find('{')
    end = raw.rfind('}')
    if start >= 0 and end > start:
        raw = raw[start:end+1]
    return json.loads(raw)


def _local_seo_tags(text: str, limit=8):
    normalized = normalize_fa(text)
    words = [w for w in re.findall(r'[\w\u0600-\u06ff]{3,}', normalized) if w not in STOPWORDS and not w.isdigit()]
    counts = Counter(words)
    ranked = [word for word, _ in counts.most_common(30)]
    # Prefer distinct semantic stems by simple containment filtering.
    out = []
    for word in ranked:
        if any(word in old or old in word for old in out):
            continue
        out.append(word)
        if len(out) >= limit:
            break
    return out


def suggest_seo_tags(text: str, *, user=None, research=None):
    text = plain_text(text)[:12000]
    endpoint = choose_endpoint()
    prompt = (
        'برای متن زیر ۵ تا ۱۰ برچسب SEO فارسی کوتاه، دقیق و غیرتکراری پیشنهاد بده. '
        'خروجی فقط JSON با کلید tags و آرایه رشته‌ها باشد. از عبارت‌های خیلی عمومی پرهیز کن.\n\n' + text
    )
    if endpoint and text:
        log = AIGenerationLog.objects.create(user=user, endpoint=endpoint, research=research, task_type='seo', prompt=prompt)
        try:
            raw = run_completion(endpoint, [{'role': 'system', 'content': 'فقط JSON معتبر برگردان.'}, {'role': 'user', 'content': prompt}], timeout=50)
            payload = _json_payload(raw)
            tags = [re.sub(r'\s+', ' ', str(x)).strip() for x in payload.get('tags', []) if str(x).strip()]
            tags = list(dict.fromkeys(tags))[:10]
            if len(tags) >= 5:
                log.response = raw
                log.succeeded = True
                log.save(update_fields=['response', 'succeeded'])
                return tags
            log.response = raw
            log.error = 'پاسخ کمتر از ۵ برچسب معتبر داشت؛ از پیشنهاد محلی استفاده شد.'
            log.save(update_fields=['response', 'error'])
        except Exception as exc:
            log.error = str(exc)[:2000]
            log.save(update_fields=['error'])
    local = _local_seo_tags(text, limit=8)
    return local[:10]


def _heuristic_segments(research: Research, text: str):
    kind = normalize_fa(research.content_kind.title if research.content_kind_id else '')
    lines = [x.strip() for x in re.split(r'[\n\r]+', text) if len(x.strip()) >= 12]
    segments = []
    for line in lines:
        arabic_letters = len(re.findall(r'[\u0621-\u064a\u066e-\u06d3]', line))
        ratio = arabic_letters / max(len(line), 1)
        normalized = normalize_fa(line)
        if ('ایات' in kind or 'ایه' in kind) and ratio > .45:
            segments.append({'type': 'quran', 'text': line[:900], 'confidence': 0.72, 'method': 'rule'})
        elif ('روایات' in kind or 'روایت' in kind or 'حدیث' in kind) and (ratio > .35 or any(k in normalized for k in ['قال','فرمود','علیه السلام','صلی الله'])):
            segments.append({'type': 'hadith', 'text': line[:900], 'confidence': 0.7, 'method': 'rule'})
        elif ('اشعار' in kind or 'شعر' in kind) and len(lines) >= 2:
            segments.append({'type': 'poetry', 'text': line[:900], 'confidence': 0.65, 'method': 'rule'})
    return segments[:20]


# ZOHA-W2.3-GENERIC-SEMANTIC:START
# ZOHA-W2.3.2-CHUNKED-SEMANTIC:START


def _semantic_chunks(text, max_chars=6500):
    """
    Split long content preferably on newline boundaries.
    """

    text = (text or "").strip()

    if not text:
        return []

    chunks = []

    start = 0
    length = len(text)

    while start < length:

        end = min(
            start + max_chars,
            length,
        )

        if end < length:

            minimum = (
                start
                + max_chars // 2
            )

            cut = text.rfind(
                "\n",
                minimum,
                end,
            )

            if cut <= start:

                cut = text.rfind(
                    " ",
                    minimum,
                    end,
                )

            if cut > start:
                end = cut

        chunk = text[
            start:end
        ].strip()

        if chunk:
            chunks.append(chunk)

        start = end

        while (
            start < length
            and text[start].isspace()
        ):
            start += 1

    return chunks



def _semantic_rows(value):
    """
    Recursively extract dictionaries having type/text.
    """

    rows = []

    if isinstance(value, dict):

        if (
            "type" in value
            and "text" in value
        ):
            rows.append(value)

        for child in value.values():

            if isinstance(
                child,
                (dict, list),
            ):
                rows.extend(
                    _semantic_rows(child)
                )

    elif isinstance(value, list):

        for child in value:
            rows.extend(
                _semantic_rows(child)
            )

    return rows



def _parse_semantic_response(raw):
    """
    Robust parser for:
      object
      array
      fenced JSON
      malformed outer container
    """

    raw = str(raw or "").strip()

    if not raw:
        raise ValueError(
            "empty semantic AI response"
        )


    cleaned = re.sub(
        r"^```(?:json)?\s*",
        "",
        raw,
        flags=re.I,
    )

    cleaned = re.sub(
        r"\s*```$",
        "",
        cleaned,
    ).strip()


    candidates = [cleaned]


    a = cleaned.find("[")
    b = cleaned.rfind("]")

    if a >= 0 and b > a:
        candidates.append(
            cleaned[a:b + 1]
        )


    a = cleaned.find("{")
    b = cleaned.rfind("}")

    if a >= 0 and b > a:
        candidates.append(
            cleaned[a:b + 1]
        )


    seen = set()

    for candidate in candidates:

        if candidate in seen:
            continue

        seen.add(candidate)

        try:
            value = json.loads(candidate)
        except Exception:
            continue

        return (
            _semantic_rows(value),
            "json",
        )


    # Recover valid nested JSON objects
    decoder = json.JSONDecoder()

    recovered = []
    recovered_seen = set()


    for index, char in enumerate(cleaned):

        if char != "{":
            continue

        try:

            value, _ = decoder.raw_decode(
                cleaned[index:]
            )

        except Exception:
            continue


        for row in _semantic_rows(value):

            identity = (
                str(row.get("type") or ""),
                str(row.get("text") or ""),
            )

            if identity in recovered_seen:
                continue

            recovered_seen.add(identity)

            recovered.append(row)


    if recovered:

        return (
            recovered,
            "object-recovery",
        )


    # Last-resort extraction
    pattern = re.compile(
        r'"type"\s*:\s*'
        r'"(?P<type>quran|hadith|poetry)"'
        r'\s*,\s*'
        r'"text"\s*:\s*'
        r'"(?P<text>(?:\\.|[^"\\])*)"',
        flags=re.I | re.S,
    )


    rows = []

    for match in pattern.finditer(cleaned):

        encoded = (
            match.group("text")
            or ""
        )

        try:

            fragment = json.loads(
                '"'
                + encoded
                + '"'
            )

        except Exception:

            fragment = encoded


        rows.append(
            {
                "type": (
                    match.group("type")
                    or ""
                ).lower(),

                "text": fragment,

                "confidence": .5,
            }
        )


    if rows:

        return (
            rows,
            "regex-recovery",
        )


    raise ValueError(
        "malformed semantic JSON; "
        "no recoverable segments"
    )




# ZOHA-W2.3.3-PRECISION-GUARD:START

def _arabic_script_letter_ratio(value):
    """
    Ratio of Arabic-script alphabetic letters among all
    alphabetic letters.

    Harakat, Quran marks, punctuation and digits do NOT
    participate in the denominator.
    """

    value = str(value or "")

    letters = [
        ch
        for ch in value
        if unicodedata.category(ch).startswith("L")
    ]

    if not letters:
        return 0.0

    arabic_letters = [
        ch
        for ch in letters
        if (
            "\u0600" <= ch <= "\u06ff"
            or "\u0750" <= ch <= "\u077f"
            or "\u08a0" <= ch <= "\u08ff"
            or "\ufb50" <= ch <= "\ufdff"
            or "\ufe70" <= ch <= "\ufeff"
        )
    ]

    return (
        len(arabic_letters)
        / max(len(letters), 1)
    )



def _context_around(
    source,
    fragment,
    radius=260,
):
    source = str(source or "")
    fragment = str(fragment or "")

    if not source or not fragment:
        return ""

    position = source.find(fragment)

    if position < 0:
        return ""

    return source[
        max(0, position - radius):
        min(
            len(source),
            position + len(fragment) + radius,
        )
    ]



def _looks_like_quran(fragment):
    """
    Conservative Quran validation.

    This is intentionally a precision guard, not a Quran
    identification database.
    """

    fragment = str(
        fragment or ""
    ).strip()

    if len(fragment) < 8:
        return False

    if len(fragment) > 450:
        return False


    # Quran Arabic never contains these specifically
    # Persian letters.
    if re.search(
        r"[پچژگ]",
        fragment,
    ):
        return False


    # Ignore harakat/Quran marks when measuring script.
    if (
        _arabic_script_letter_ratio(fragment)
        < .97
    ):
        return False


    normalized = normalize_fa(
        fragment
    )


    # Frequent khutbah/salawat formulae wrongly classified
    # as Quran by generic LLMs.
    non_quran_phrases = [
        "والصلاة والسلام",
        "الصلاة والسلام",
        "سيد الانبياء",
        "سید الانبیاء",
        "خاتم النبيين",
        "خاتم النبیین",
        "حبيبنا",
        "حبیبنا",
        "ابا القاسم",
        "اباالقاسم",
        "المصطفى محمد",
        "المصطفی محمد",
        "الطيبين الطاهرين",
        "الطیبین الطاهرین",
        "المعصومين",
        "المعصومین",
        "لعن الدائم",
        "اعدائهم اجمعين",
        "أعدائهم أجمعين",
        "بارئ الخلائق",
    ]


    if any(
        normalize_fa(phrase)
        in normalized
        for phrase in non_quran_phrases
    ):
        return False


    return True



def _looks_like_hadith(
    fragment,
    source,
):
    fragment = str(
        fragment or ""
    ).strip()

    if len(fragment) < 12:
        return False


    context = _context_around(
        source,
        fragment,
        radius=280,
    )


    normalized = normalize_fa(
        fragment
        + " "
        + context
    )


    cues = [
        "قال رسول",
        "قال النبي",
        "قال الصادق",
        "قال الباقر",
        "قال اميرالمومنين",
        "قال علی",
        "قال علي",
        "قال الامام",

        "رسول الله فرمود",
        "پیامبر فرمود",
        "پيامبر فرمود",
        "امام فرمود",
        "حضرت فرمود",
        "امیرالمومنین فرمود",
        "اميرالمومنين فرمود",

        "روایت شده",
        "روايت شده",
        "در روایت",
        "در روايت",
        "حدیث",
        "حديث",

        "عن رسول",
        "عن النبي",

        "علیه السلام",
        "عليه السلام",
        "صلی الله",
        "صلي الله",
    ]


    return any(
        normalize_fa(cue)
        in normalized
        for cue in cues
    )



def _looks_like_poetry(fragment):
    """
    Do not accept a normal prose sentence merely because
    the model labels it poetry.
    """

    fragment = str(
        fragment or ""
    ).strip()

    if len(fragment) < 12:
        return False


    lines = [
        line.strip()
        for line in fragment.splitlines()
        if line.strip()
    ]


    # Two or more actual textual lines is strong enough
    # for this first precision layer.
    if len(lines) >= 2:
        return True


    # Common explicit hemistich separators.
    separators = [
        " / ",
        " ـ ",
        " *** ",
        " // ",
    ]


    if any(
        sep in fragment
        for sep in separators
    ):
        return True


    return False



def _semantic_precision_accept(
    kind,
    fragment,
    source,
):
    """
    Conservative post-LLM filter.

    For citations, false negatives are safer than
    false positives.
    """

    kind = str(
        kind or ""
    ).strip().lower()


    if kind == "quran":
        return _looks_like_quran(
            fragment
        )


    if kind == "hadith":
        return _looks_like_hadith(
            fragment,
            source,
        )


    if kind == "poetry":
        return _looks_like_poetry(
            fragment
        )


    return False


# ZOHA-W2.3.3-PRECISION-GUARD:END


def detect_semantic_segments(
    text,
    *,
    user=None,
    research=None,
    project=None,
    endpoint=None,
):
    """
    Conservative chunked semantic detection.
    """

    text = (text or "").strip()

    endpoint = (
        endpoint
        or choose_endpoint()
    )

    if not text or endpoint is None:
        return []


    chunks = _semantic_chunks(
        text,
        max_chars=6500,
    )

    result = []
    global_seen = set()


    for number, chunk in enumerate(
        chunks,
        1,
    ):


        prompt = f"""از متن زیر فقط قطعات واقعی این سه دسته را استخراج کن:

1. quran = متن واقعی آیه قرآن
2. hadith = متن واقعی روایت یا حدیث
3. poetry = بیت یا شعر واقعی

قواعد سخت:
- فقط عبارتی را برگردان که عیناً در متن ورودی وجود دارد.
- هیچ متن یا نقل تازه‌ای نساز.
- توضیح اضافه ننویس.
- حداکثر 10 قطعه برگردان.
- هر قطعه حداکثر حدود 700 نویسه باشد.
- اگر موردی وجود ندارد، segments خالی باشد.
- مقدار type باید دقیقاً فقط quran یا hadith یا poetry باشد.
- عبارت quran|hadith|poetry را هرگز به‌عنوان type ننویس.

نمونه معتبر:
{{"segments":[
  {{"type":"quran","text":"متن واقعی آیه","confidence":0.95}},
  {{"type":"hadith","text":"متن واقعی حدیث","confidence":0.92}},
  {{"type":"poetry","text":"متن واقعی شعر","confidence":0.90}}
]}}

بخش {number} از {len(chunks)}:

{chunk}
"""


        kwargs = {
            "user": user,
            "endpoint": endpoint,
            "task_type": "enrichment",
            "prompt": prompt,
        }


        if research is not None:
            kwargs["research"] = research

        if project is not None:
            kwargs["project"] = project


        log = AIGenerationLog.objects.create(
            **kwargs
        )


        try:

            raw = run_completion(
                endpoint,
                [
                    {
                        "role": "system",
                        "content": (
                            "فقط استخراج محافظه‌کارانه "
                            "آیه، حدیث و شعر انجام بده. "
                            "خروجی فقط JSON معتبر باشد."
                        ),
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                timeout=70,
            )


            # Always retain raw model output.
            log.response = str(
                raw or ""
            )


            rows, parse_mode = (
                _parse_semantic_response(
                    raw
                )
            )


            chunk_normalized = (
                normalize_fa(chunk)
            )


            for row in rows:

                if not isinstance(row, dict):
                    continue


                kind = str(
                    row.get("type")
                    or ""
                ).strip().lower()


                fragment = str(
                    row.get("text")
                    or ""
                ).strip()


                if kind not in {
                    "quran",
                    "hadith",
                    "poetry",
                }:
                    continue


                if len(fragment) < 8:
                    continue


                # Absolute hallucination guard:
                # accepted text must already exist in chunk.
                normalized_fragment = (
                    normalize_fa(fragment)
                )


                if (
                    normalized_fragment
                    not in chunk_normalized
                ):
                    continue


                # W2.3.3 semantic precision validation
                if not _semantic_precision_accept(
                    kind,
                    fragment,
                    chunk,
                ):
                    continue


                identity = (
                    kind,
                    normalized_fragment,
                )


                if identity in global_seen:
                    continue


                global_seen.add(
                    identity
                )


                try:

                    confidence = float(
                        row.get("confidence")
                        or .5
                    )

                except (
                    TypeError,
                    ValueError,
                ):

                    confidence = .5


                result.append(
                    {
                        "type": kind,
                        "text": fragment[:2000],
                        "confidence": confidence,
                        "method": (
                            "ai"
                            if parse_mode == "json"
                            else "ai-recovered"
                        ),
                    }
                )


            log.succeeded = True


            if parse_mode != "json":

                log.error = (
                    "Recovered malformed AI JSON: "
                    + parse_mode
                )


        except Exception as exc:

            log.error = (
                f"chunk={number}/{len(chunks)}: "
                f"{exc}"
            )[:2000]


        finally:

            log.save(
                update_fields=[
                    "response",
                    "succeeded",
                    "error",
                ]
            )


    return result[:80]



def enrich_semantic_text(
    body,
    *,
    user=None,
    research=None,
    project=None,
    endpoint=None,
):

    text = plain_text(
        body or ""
    )


    detected = detect_semantic_segments(
        text,
        user=user,
        research=research,
        project=project,
        endpoint=endpoint,
    )


    seen = set()
    cleaned = []


    for row in detected:

        key = (
            row.get("type"),
            normalize_fa(
                row.get("text")
                or ""
            ),
        )


        if (
            not key[0]
            or not key[1]
            or key in seen
        ):
            continue


        seen.add(key)

        cleaned.append(row)


    cleaned = cleaned[:80]


    return (
        cleaned,
        build_external_references(
            cleaned
        ),
    )



def _ai_segments(
    research: Research,
    text: str,
    *,
    user=None,
):

    return detect_semantic_segments(
        text,
        user=user,
        research=research,
    )


# ZOHA-W2.3.2-CHUNKED-SEMANTIC:END
# ZOHA-W2.3-GENERIC-SEMANTIC:END


def build_external_references(segments):
    refs = []
    seen = set()
    mapping = {
        'quran': ('پایگاه جامع قرآن نور', settings.ZOHA_QURAN_REFERENCE_URL),
        'hadith': ('پایگاه جامع الاحادیث نور', settings.ZOHA_HADITH_REFERENCE_URL),
        'poetry': ('گنجور', settings.ZOHA_POETRY_REFERENCE_URL),
    }
    for segment in segments:
        kind = segment.get('type')
        if kind not in mapping or kind in seen:
            continue
        seen.add(kind)
        label, url = mapping[kind]
        refs.append({'type': kind, 'label': label, 'url': url, 'query': segment.get('text','')[:350]})
    return refs


def build_search_document(research: Research):
    chunks = [research.title, research.abstract, plain_text(research.body), research.search_keywords, research.author_explanation]
    if research.source_id:
        chunks.extend([research.source.title, research.source.author_name, research.source.aliases])
    for value in research.topic_analyses.select_related('topic','predicate').prefetch_related('processing_keys'):
        chunks.append(value.topic.title)
        if value.predicate_id:
            chunks.append(value.predicate.title)
        chunks.append(value.predicate_text)
        chunks.append(value.author_interpretation)
        chunks.extend(value.processing_keys.values_list('title', flat=True))
    chunks.extend(research.characters.values_list('title', flat=True))
    chunks.extend(research.secondary_characters.values_list('title', flat=True))
    chunks.extend(research.occasions.values_list('title', flat=True))
    chunks.extend(research.indexes.select_related('index_value').values_list('index_value__title', flat=True))
    chunks.extend(research.seo_tags or [])
    return normalize_fa(' '.join(str(x) for x in chunks if x))


def refresh_search_document(research: Research, *, save=True):
    research.search_document_normalized = build_search_document(research)
    if save:
        Research.objects.filter(pk=research.pk).update(search_document_normalized=research.search_document_normalized)
    return research.search_document_normalized


def enrich_before_submission(research: Research, *, user=None):
    text = plain_text(research.body)
    segments = _ai_segments(research, text, user=user)
    if not segments:
        segments = _heuristic_segments(research, text)
    # De-duplicate by normalized fragment.
    seen = set(); cleaned = []
    for row in segments:
        key = (row.get('type'), normalize_fa(row.get('text','')))
        if not key[1] or key in seen:
            continue
        seen.add(key); cleaned.append(row)
    research.ai_segments = cleaned[:30]
    research.external_references = build_external_references(research.ai_segments)
    if len(research.seo_tags or []) < 5:
        research.seo_tags = suggest_seo_tags(research.body, user=user, research=research)
    body = research.body or ''
    if 'zoha-justified' not in body:
        research.body = f'<div class="zoha-justified">{body}</div>'
    research.ai_enrichment_status = 'completed' if research.ai_segments else 'rules-only'
    research.ai_enriched_at = timezone.now()
    research.save(update_fields=['body','seo_tags','ai_segments','external_references','ai_enrichment_status','ai_enriched_at','updated_at'])
    refresh_search_document(research)
    return research


def generate_featured_image(research: Research, *, user=None):
    """Call an OpenAI-compatible image endpoint when configured.

    Expected response: {"data":[{"url":"..."}]} or {"data":[{"b64_json":"..."}]}.
    """
    endpoint_url = settings.ZOHA_IMAGE_API_URL
    if not endpoint_url:
        raise RuntimeError('سرویس تولید تصویر در تنظیمات سرور تعریف نشده است (ZOHA_IMAGE_API_URL).')
    prompt = f'تصویر فرهنگی ایرانی-اسلامی مینیمال، بدون نوشته و بدون چهره واقعی، مناسب محتوای دینی با موضوع: {research.display_title}. خلاصه: {plain_text(research.abstract or research.body)[:500]}'
    log = AIGenerationLog.objects.create(user=user, research=research, task_type='image', prompt=prompt)
    headers = {'Content-Type': 'application/json'}
    if settings.ZOHA_IMAGE_API_KEY:
        headers['Authorization'] = f'Bearer {settings.ZOHA_IMAGE_API_KEY}'
    try:
        response = requests.post(endpoint_url, headers=headers, json={'prompt': prompt, 'size': '1024x1024', 'n': 1}, timeout=120)
        response.raise_for_status()
        payload = response.json()
        item = (payload.get('data') or [{}])[0]
        content = None
        if item.get('b64_json'):
            content = base64.b64decode(item['b64_json'])
        elif item.get('url'):
            img = requests.get(item['url'], timeout=90)
            img.raise_for_status()
            content = img.content
        if not content:
            raise RuntimeError('سرویس تصویر خروجی قابل ذخیره برنگرداند.')
        filename = f'zoha-{research.pk}.png'
        research.featured_image.save(filename, ContentFile(content), save=True)
        log.response = json.dumps({'saved': research.featured_image.name}, ensure_ascii=False)
        log.succeeded = True
        log.save(update_fields=['response','succeeded'])
        return research.featured_image.url
    except Exception as exc:
        log.error = str(exc)[:2000]
        log.save(update_fields=['error'])
        raise

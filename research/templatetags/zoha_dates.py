from urllib.parse import quote_plus
from django import template
from research.jalali import format_jalali

register = template.Library()

@register.filter
def jalali_date(value):
    return format_jalali(value)
from django.utils.safestring import mark_safe
from django.utils.html import escape

# ZOHA-W2.2-SEMANTIC-RENDERER:START
@register.filter
def semantic_render(body, segments=None):
    """
    Shared renderer for semantic religious-content segments.

    Segment schema:
        {
            "type": "quran|hadith|poetry",
            "text": "...",
            "confidence": 0.0,
            "method": "ai|rule"
        }

    Database content is never modified.
    Only exact fragments already present in body are decorated.
    """
    html = body or ""

    classes = {
        "quran": "zoha-semantic zoha-quran",
        "hadith": "zoha-semantic zoha-hadith",
        "poetry": "zoha-semantic zoha-poetry",
    }

    seen = set()

    for row in segments or []:

        if not isinstance(row, dict):
            continue

        kind = str(
            row.get("type") or ""
        ).strip().lower()

        fragment = str(
            row.get("text") or ""
        ).strip()

        css = classes.get(kind)

        if not fragment or not css:
            continue

        identity = (
            kind,
            fragment,
        )

        if identity in seen:
            continue

        seen.add(identity)

        if fragment not in html:
            continue

        html = html.replace(
            fragment,
            (
                f'<span '
                f'class="{css}" '
                f'data-semantic-type="{kind}">'
                f'{fragment}'
                f'</span>'
            ),
            1,
        )

    return mark_safe(html)



# ZOHA-W2.3-SEMANTIC-TEXT-RENDERER:START
@register.filter
def semantic_render_text(body, segments=None):
    """
    Safe semantic renderer for plain textarea content.
    User/AI text is escaped before semantic spans are added.
    """

    raw = str(body or "")

    escaped_body = str(
        escape(raw)
    )

    escaped_segments = []

    for row in segments or []:

        if not isinstance(
            row,
            dict,
        ):
            continue

        copied = dict(row)

        copied["text"] = str(
            escape(
                str(
                    row.get("text")
                    or ""
                )
            )
        )

        escaped_segments.append(
            copied
        )

    return semantic_render(
        escaped_body,
        escaped_segments,
    )
# ZOHA-W2.3-SEMANTIC-TEXT-RENDERER:END



# ZOHA-W2.4-W2.5-LINKED-SEMANTIC:START

SEMANTIC_REFERENCE_DEFAULTS = {

    "quran": {
        "label": "پایگاه جامع قرآن نور",
        "url": "https://quran.inoor.ir/fa/home",
        "title": "بررسی این آیه در پایگاه جامع قرآن نور",
    },

    "hadith": {
        "label": "جامع الاحادیث نور",
        "url": "https://hadith.inoor.ir/fa/home",
        "title": "بررسی این روایت در پایگاه جامع الاحادیث نور",
    },

    "poetry": {
        "label": "گنجور",
        "url": "https://ganjoor.net/search?s={query}",
        "title": "جستجوی این شعر در گنجور",
    },
}



def _semantic_reference_map(
    references,
):
    """
    Convert stored external_references array to
    {type: reference}.
    """

    output = {}

    for row in references or []:

        if not isinstance(
            row,
            dict,
        ):
            continue

        kind = str(
            row.get("type")
            or ""
        ).strip().lower()

        if kind not in {
            "quran",
            "hadith",
            "poetry",
        }:
            continue

        output[kind] = row

    return output



def _semantic_reference_href(
    kind,
    fragment,
    references=None,
):
    """
    Produce an external destination without inventing
    undocumented Noor search parameters.

    Quran/Hadith:
        official Noor database landing/search page.

    Poetry:
        Ganjoor text search URL.

    If a configured reference URL explicitly contains
    {query}, {q} or %s, use it as a URL template.
    """

    kind = str(
        kind
        or ""
    ).strip().lower()

    fragment = str(
        fragment
        or ""
    ).strip()

    default = (
        SEMANTIC_REFERENCE_DEFAULTS
        .get(kind)
    )

    if not default:
        return ""

    reference_map = (
        _semantic_reference_map(
            references
        )
    )

    stored = (
        reference_map.get(kind)
        or {}
    )

    base = str(
        stored.get("url")
        or default["url"]
        or ""
    ).strip()

    query = quote_plus(
        fragment[:350]
    )


    if "{query}" in base:

        return base.replace(
            "{query}",
            query,
        )


    if "{q}" in base:

        return base.replace(
            "{q}",
            query,
        )


    if "%s" in base:

        try:
            return base % query
        except Exception:
            pass


    # Ganjoor has a direct text-search destination.
    if kind == "poetry":

        if "ganjoor.net" in base:

            return (
                "https://ganjoor.net/"
                "search?s="
                + query
            )


    # For Noor we deliberately do not invent an
    # undocumented query parameter.
    return base



def _semantic_reference_title(
    kind,
):
    config = (
        SEMANTIC_REFERENCE_DEFAULTS
        .get(kind)
        or {}
    )

    return str(
        config.get("title")
        or "بررسی در مرجع"
    )



def _semantic_linked_render(
    body,
    segments=None,
    references=None,
):
    """
    Rich-HTML renderer.

    Database content is never changed.
    """

    html = str(
        body
        or ""
    )


    classes = {
        "quran": "zoha-semantic zoha-quran",
        "hadith": "zoha-semantic zoha-hadith",
        "poetry": "zoha-semantic zoha-poetry",
    }


    seen = set()


    for row in segments or []:

        if not isinstance(
            row,
            dict,
        ):
            continue


        kind = str(
            row.get("type")
            or ""
        ).strip().lower()


        fragment = str(
            row.get("text")
            or ""
        ).strip()


        css = classes.get(
            kind
        )


        if (
            not fragment
            or not css
        ):
            continue


        identity = (
            kind,
            fragment,
        )


        if identity in seen:
            continue


        seen.add(
            identity
        )


        if fragment not in html:
            continue


        href = (
            _semantic_reference_href(
                kind,
                fragment,
                references,
            )
        )


        title = (
            _semantic_reference_title(
                kind
            )
        )


        if href:

            replacement = (
                f'<a '
                f'class="{css} zoha-semantic-reference" '
                f'data-semantic-type="{kind}" '
                f'data-semantic-reference="{kind}" '
                f'href="{escape(href)}" '
                f'target="_blank" '
                f'rel="noopener noreferrer nofollow" '
                f'title="{escape(title)}">'
                f'{fragment}'
                f'</a>'
            )

        else:

            replacement = (
                f'<span '
                f'class="{css}" '
                f'data-semantic-type="{kind}">'
                f'{fragment}'
                f'</span>'
            )


        html = html.replace(
            fragment,
            replacement,
            1,
        )


    return mark_safe(
        html
    )



@register.simple_tag
def semantic_content(
    body,
    segments=None,
    references=None,
):
    """
    Linked semantic renderer for rich HTML content.
    """

    return _semantic_linked_render(
        body,
        segments,
        references,
    )



@register.simple_tag
def semantic_text_content(
    body,
    segments=None,
    references=None,
):
    """
    Linked semantic renderer for plain textarea content.

    Escape content first to prevent HTML/script execution.
    """

    escaped_body = str(
        escape(
            str(
                body
                or ""
            )
        )
    )


    escaped_segments = []


    for row in segments or []:

        if not isinstance(
            row,
            dict,
        ):
            continue

        copied = dict(row)

        copied["text"] = str(
            escape(
                str(
                    row.get("text")
                    or ""
                )
            )
        )

        escaped_segments.append(
            copied
        )


    return _semantic_linked_render(
        escaped_body,
        escaped_segments,
        references,
    )


# ZOHA-W2.4-W2.5-LINKED-SEMANTIC:END


@register.filter
def smart_highlight(body, segments):
    """
    Backwards-compatible alias.
    """
    return semantic_render(
        body,
        segments,
    )
# ZOHA-W2.2-SEMANTIC-RENDERER:END


# ZOHA-W3.1-SIDEBAR-STATS:START
# ZOHA-W3.1.2-DOMAIN-MAPPING:START

@register.simple_tag(takes_context=True)
def sidebar_content_stats(context):
    """
    Canonical current-user content domains.

    Generated:
        Research, unless explicitly marked as
        complementary or legacy complete.

    Complete:
        ALL FullContent records.

    Complementary:
        Research indexed with:
          category -> محتوای تکمیلی

    Existing Research without a product-domain index
    remains Generated for backward compatibility.
    """

    from urllib.parse import urlencode

    from django.db.models import Count
    from django.urls import reverse

    from research.models import (
        Research,
        ResearchIndex,
        FullContent,
    )


    request = context.get(
        "request"
    )

    user = context.get(
        "user"
    )


    if (
        user is None
        and request is not None
    ):

        user = request.user


    if (
        user is None
        or not getattr(
            user,
            "is_authenticated",
            False,
        )
    ):

        return []


    # ---------------------------------------------
    # Research product-domain sets
    # ---------------------------------------------

    research_qs = (
        Research.objects
        .filter(
            researcher=user
        )
    )


    complementary_ids = (
        ResearchIndex.objects
        .filter(
            research__researcher=user,
            index_type__slug="category",
            index_value__title="محتوای تکمیلی",
        )
        .values(
            "research_id"
        )
    )


    legacy_complete_ids = (
        ResearchIndex.objects
        .filter(
            research__researcher=user,
            index_type__slug="category",
            index_value__title="محتوای کامل",
        )
        .values(
            "research_id"
        )
    )


    generated_qs = (
        research_qs
        .exclude(
            pk__in=complementary_ids
        )
        .exclude(
            pk__in=legacy_complete_ids
        )
    )


    complementary_qs = (
        research_qs
        .filter(
            pk__in=complementary_ids
        )
    )


    complete_qs = (
        FullContent.objects
        .filter(
            owner=user
        )
    )


    # ---------------------------------------------
    # Status aggregation
    # ---------------------------------------------

    def research_stats(qs):

        grouped = {
            row["status"]: row["total"]
            for row in (
                qs
                .values(
                    "status"
                )
                .annotate(
                    total=Count(
                        "id",
                        distinct=True,
                    )
                )
            )
        }


        def amount(*states):

            return sum(
                grouped.get(
                    state,
                    0,
                )
                for state in states
            )


        return {
            "total": sum(
                grouped.values()
            ),

            "approved": amount(
                "approved",
                "published",
            ),

            "evaluating": amount(
                "submitted",
                "in_review",
            ),

            "changes": amount(
                "changes_requested",
            ),

            "rejected": amount(
                "rejected",
            ),
        }


    def full_stats(qs):

        grouped = {
            row["status"]: row["total"]
            for row in (
                qs
                .values(
                    "status"
                )
                .annotate(
                    total=Count(
                        "id"
                    )
                )
            )
        }


        def amount(*states):

            return sum(
                grouped.get(
                    state,
                    0,
                )
                for state in states
            )


        return {
            "total": sum(
                grouped.values()
            ),

            "approved": amount(
                "ready",
                "approved",
                "published",
            ),

            "evaluating": amount(
                "submitted",
                "in_review",
            ),

            "changes": amount(
                "changes_requested",
            ),

            "rejected": amount(
                "rejected",
            ),
        }


    generated = research_stats(
        generated_qs
    )

    complete = full_stats(
        complete_qs
    )

    complementary = research_stats(
        complementary_qs
    )


    # ---------------------------------------------
    # URLs
    # ---------------------------------------------

    def make_url(
        name,
        **params,
    ):

        base = reverse(
            name
        )

        if not params:

            return base


        return (
            base
            + "?"
            + urlencode(
                params
            )
        )


    def build_rows(
        stats,
        base_name,
        common,
    ):

        return [

            {
                "key": "total",
                "label": "کل بارگذاری من",
                "value": stats["total"],
                "url": make_url(
                    base_name,
                    **common,
                ),
            },

            {
                "key": "approved",
                "label": "تأییدشده",
                "value": stats["approved"],
                "url": make_url(
                    base_name,
                    **common,
                    status_group="approved",
                ),
            },

            {
                "key": "evaluating",
                "label": "در حال ارزیابی",
                "value": stats["evaluating"],
                "url": make_url(
                    base_name,
                    **common,
                    status_group="pending",
                ),
            },

            {
                "key": "changes",
                "label": "نیازمند اصلاح",
                "value": stats["changes"],
                "url": make_url(
                    base_name,
                    **common,
                    status_group="changes",
                ),
            },

            {
                "key": "rejected",
                "label": "ردشده",
                "value": stats["rejected"],
                "url": make_url(
                    base_name,
                    **common,
                    status_group="rejected",
                ),
            },
        ]


    return [

        {
            "key": "generated",
            "title": "محتوای مولد",
            "icon": "fa-lightbulb",

            "rows": build_rows(
                generated,
                "research_list",
                {
                    "scope": "mine",
                    "domain": "generated",
                },
            ),
        },

        {
            "key": "full",
            "title": "محتوای کامل",
            "icon": "fa-book-open",

            "rows": build_rows(
                complete,
                "full_content_list",
                {
                    "scope": "mine",
                },
            ),
        },

        {
            "key": "complementary",
            "title": "محتوای پشتیبان",
            "icon": "fa-book-open-reader",

            "rows": build_rows(
                complementary,
                "research_list",
                {
                    "scope": "mine",
                    "domain": "complementary",
                },
            ),
        },
    ]


# ZOHA-W3.1.2-DOMAIN-MAPPING:END
# ZOHA-W3.1-SIDEBAR-STATS:END


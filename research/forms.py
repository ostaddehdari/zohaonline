import json
import re

import bleach
try:
    from bleach.css_sanitizer import CSSSanitizer
except ModuleNotFoundError:  # Safety fallback; requirements installs tinycss2.
    CSSSanitizer = None
from django import forms
from django.core.exceptions import ValidationError
from django.utils.text import slugify

from accounts.models import Team, User
from .models import (
    CustomCollection, FullContent, IndexType, IndexValue, PromotionProject, Research, ReviewComment, ReviewerAssignment, SermonStyle, Source, normalize_fa,
)


CORE_SLUGS = {
    "content_kind": "content-kind",
    "content_category": "content-category",
    "main_format": "main-format",
    "sub_format": "content-subformat",
    "source_type": "source-type",
    "characters": "main-character",
    "occasions": "occasion",
}


class StyledModelForm(forms.ModelForm):
    @staticmethod
    def _append_widget_class(widget, class_name):
        existing = widget.attrs.get("class", "")
        classes = [item for item in existing.split() if item]
        if class_name not in classes:
            classes.append(class_name)
        widget.attrs["class"] = " ".join(classes)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                self._append_widget_class(field.widget, "form-check-input")
            elif isinstance(field.widget, (forms.Select, forms.SelectMultiple)):
                self._append_widget_class(field.widget, "form-select")
            else:
                self._append_widget_class(field.widget, "form-control")


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput(attrs={"multiple": True, "accept": "image/*,audio/*,.pdf,.doc,.docx,.txt"}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_clean = super().clean
        if isinstance(data, (list, tuple)):
            return [single_clean(item, initial) for item in data]
        if data:
            return [single_clean(data, initial)]
        return []


class ResearchForm(StyledModelForm):
    topic_analyses_json = forms.CharField(widget=forms.HiddenInput, required=False)
    audiences_json = forms.CharField(widget=forms.HiddenInput, required=False)
    special_indexes_json = forms.CharField(widget=forms.HiddenInput, required=False)

    class Meta:
        model = Research
        fields = (
            "title", "content_kind", "content_category", "main_format", "sub_format",
            "abstract", "search_keywords", "author_explanation", "body",
            "source_type", "source", "source_volume", "source_page", "source_narrator",
            "source_url", "source_note", "characters", "secondary_characters", "occasions",
            "access_level", "team", "duplicate_override",
        )
        widgets = {
            "title": forms.TextInput(attrs={"maxlength": 160, "autocomplete": "off", "placeholder": "برای نمونه: امید در سختی‌ها (اختیاری)"}),
            "abstract": forms.Textarea(attrs={"rows": 3, "placeholder": "خلاصه کوتاه فیش (اختیاری)"}),
            "search_keywords": forms.Textarea(attrs={"rows": 2, "placeholder": "فقط واژه‌های خاصی که عیناً در متن اصلی آمده‌اند؛ با ویرگول جدا کنید"}),
            "author_explanation": forms.Textarea(attrs={"rows": 3, "placeholder": "نکته برای فهم بهتر متن، پاسخ به شبهه یا بیان چالش مرتبط"}),
            "body": forms.Textarea(attrs={"rows": 18, "class": "form-control rich-editor", "placeholder": "متن اصلی فیش را وارد کنید…"}),
            "source_note": forms.Textarea(attrs={"rows": 3, "placeholder": "هر توضیح تکمیلی درباره منبع"}),
            "characters": forms.SelectMultiple(attrs={"class": "form-select select2-tags", "data-option-type": "main-character"}),
            "secondary_characters": forms.SelectMultiple(attrs={"class": "form-select select2-tags", "data-option-type": "main-character"}),
            "occasions": forms.SelectMultiple(attrs={"class": "form-select select2-tags", "data-option-type": "occasion"}),
            "duplicate_override": forms.HiddenInput(),
        }
        labels = {
            "abstract": "خلاصه فیش", "search_keywords": "کلمات کلیدی", "author_explanation": "توضیحات نویسنده",
            "body": "متن اصلی فیش", "content_kind": "جنس محتوا", "content_category": "ریز جنس محتوا",
            "main_format": "قالب اصلی فیش", "sub_format": "ریزقالب", "source": "نام منبع", "characters": "شخصیت اصلی", "secondary_characters": "شخصیت فرعی / ناقل",
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        for field_name, slug in CORE_SLUGS.items():
            if field_name not in self.fields:
                continue
            try:
                index_type = IndexType.objects.get(slug=slug, is_active=True)
                qs = IndexValue.objects.visible_to(user).filter(index_type=index_type)
                self.fields[field_name].queryset = qs
            except IndexType.DoesNotExist:
                self.fields[field_name].queryset = IndexValue.objects.none()

        self.fields["source"].queryset = Source.objects.visible_to(user)
        self.fields["team"].queryset = Team.objects.visible_to(user)

        # اصلاحیه نسخه ۵: عنوان تنها مانع ذخیره و رفتن به مرحله بعد است.
        for name, field in self.fields.items():
            field.required = name == "title"
        self.fields["topic_analyses_json"].required = False
        self.fields["audiences_json"].required = False
        self.fields["special_indexes_json"].required = False
        self.fields["access_level"].initial = self.instance.access_level if self.instance and self.instance.pk else "private"
        self.fields["team"].widget.attrs["data-placeholder"] = "گروه کاری را انتخاب کنید"

        select2_fields = [
            "content_kind", "content_category", "main_format", "sub_format", "source_type", "source",
            "characters", "secondary_characters", "occasions", "team",
        ]
        for name in select2_fields:
            if name in self.fields:
                css = self.fields[name].widget.attrs.get("class", "")
                self.fields[name].widget.attrs["class"] = f"{css} select2".strip()
                self.fields[name].widget.attrs["data-placeholder"] = "جست‌وجو و انتخاب کنید"

        if self.instance and self.instance.pk:
            analyses = []
            for item in self.instance.topic_analyses.prefetch_related("processing_keys").select_related("topic", "predicate"):
                analyses.append({
                    "id": item.pk, "topic": item.topic_id,
                    "processing_keys": list(item.processing_keys.values_list("id", flat=True)),
                    "predicate": item.predicate_id, "predicate_text": item.predicate_text,
                    "interpretation": item.author_interpretation, "review_status": item.review_status,
                })
            self.fields["topic_analyses_json"].initial = json.dumps(analyses, ensure_ascii=False)
            self.fields["audiences_json"].initial = json.dumps(self.instance.audience_profiles or [], ensure_ascii=False)
            specials = {}
            for slug in ("promotional-usage",):
                rows = list(self.instance.indexes.filter(index_type__slug=slug).values("index_value_id", "is_primary"))
                specials[slug] = {
                    "items": [r["index_value_id"] for r in rows if r["index_value_id"]],
                    "primary": next((r["index_value_id"] for r in rows if r["is_primary"] and r["index_value_id"]), None),
                }
            self.fields["special_indexes_json"].initial = json.dumps(specials, ensure_ascii=False)
        else:
            self.fields["topic_analyses_json"].initial = "[]"
            self.fields["audiences_json"].initial = "[]"
            self.fields["special_indexes_json"].initial = json.dumps({"promotional-usage": {"items": [], "primary": None}}, ensure_ascii=False)

    def submission_issues(self):
        issues = []
        return issues

    def clean_title(self):
        title = re.sub(r"\s+", " ", self.cleaned_data.get("title") or "").strip()
        if not title:
            raise ValidationError("عنوان فیش الزامی است.")
        if len(title) > 160:
            raise ValidationError("عنوان فیش نباید بیشتر از ۱۶۰ نویسه باشد.")
        return title

    def clean_body(self):
        body = self.cleaned_data.get("body", "")
        plain = re.sub(r"<[^>]+>", "", body).replace("&nbsp;", " ").strip()
        allowed_tags = [
            "p", "div", "br", "hr", "strong", "b", "em", "i", "u", "s", "del", "ol", "ul", "li",
            "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "a", "span", "sub", "sup", "pre", "code",
            "img", "figure", "figcaption", "table", "thead", "tbody", "tfoot", "tr", "th", "td", "caption",
        ]
        common = ["class", "dir", "title"]
        if CSSSanitizer is not None:
            common.append("style")
        attrs = {"*": common, "a": common + ["href", "target", "rel"], "img": common + ["src", "alt", "width", "height"],
                 "table": common + ["border", "cellpadding", "cellspacing", "width"], "th": common + ["colspan", "rowspan", "scope"], "td": common + ["colspan", "rowspan"]}
        sanitizer = CSSSanitizer(allowed_css_properties=[
            "color", "background-color", "text-align", "font-size", "font-family", "font-weight", "font-style",
            "text-decoration", "direction", "line-height", "margin-left", "margin-right", "padding", "border",
            "border-collapse", "width", "height", "max-width", "vertical-align",
        ]) if CSSSanitizer is not None else None
        return bleach.clean(body, tags=allowed_tags, attributes=attrs, protocols=["http", "https", "mailto"], css_sanitizer=sanitizer, strip=True)

    def clean_topic_analyses_json(self):
        raw = self.cleaned_data.get("topic_analyses_json") or "[]"
        try:
            rows = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            raise ValidationError("ساختار موضوعات انتخاب‌شده نامعتبر است.")
        if not isinstance(rows, list):
            raise ValidationError("ساختار موضوعات انتخاب‌شده نامعتبر است.")
        seen = set()
        cleaned = []
        for number, row in enumerate(rows, start=1):
            topic = str(row.get("topic") or "").strip()
            if not topic:
                continue
            if topic in seen:
                raise ValidationError("هر موضوع فقط یک‌بار می‌تواند در فیش ثبت شود.")
            seen.add(topic)
            cleaned.append({
                "topic": topic,
                "processing_keys": [str(x) for x in (row.get("processing_keys") or []) if str(x).strip()],
                "predicate": str(row.get("predicate") or "").strip(),
                "predicate_text": str(row.get("predicate_text") or "").strip(),
                "interpretation": str(row.get("interpretation") or "").strip(),
                "review_status": str(row.get("review_status") or "unchecked"),
            })
        return cleaned

    def clean_audiences_json(self):
        raw = self.cleaned_data.get("audiences_json") or "[]"
        try:
            rows = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            raise ValidationError("ساختار مخاطبان نامعتبر است.")
        if not isinstance(rows, list):
            raise ValidationError("ساختار مخاطبان نامعتبر است.")
        lookups = {}
        for slug in ("audience-job",):
            values = IndexValue.objects.visible_to(self.user).filter(index_type__slug=slug).values("id", "title")
            mapping = {}
            for value in values:
                mapping[str(value["id"])] = value["title"]
                mapping[normalize_fa(value["title"])] = value["title"]
            lookups[slug] = mapping

        def readable(values, slug):
            result = []
            lookup = lookups.get(slug, {})
            for raw in values or []:
                text = str(raw).strip()
                if not text:
                    continue
                result.append(lookup.get(text) or lookup.get(normalize_fa(text)) or text)
            return list(dict.fromkeys(result))

        cleaned = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            item = {
                "is_primary": bool(row.get("is_primary")), "general": bool(row.get("general")),
                "genders": list(dict.fromkeys(row.get("genders") or [])), "ages": list(dict.fromkeys(row.get("ages") or [])),
                "jobs": readable(row.get("jobs") or [], "audience-job"),
            }
            if item["general"] or any([item["genders"], item["ages"], item["jobs"]]):
                cleaned.append(item)
        if cleaned and not any(x["is_primary"] for x in cleaned):
            cleaned[0]["is_primary"] = True
        return cleaned

    def clean_special_indexes_json(self):
        raw = self.cleaned_data.get("special_indexes_json") or "{}"
        try:
            payload = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            raise ValidationError("ساختار کاربرد و شیوه ارائه نامعتبر است.")
        if not isinstance(payload, dict):
            raise ValidationError("ساختار کاربرد و شیوه ارائه نامعتبر است.")
        cleaned = {}
        for slug in ("promotional-usage",):
            row = payload.get(slug) or {}
            items = [str(x) for x in (row.get("items") or []) if str(x).strip()]
            items = list(dict.fromkeys(items))
            primary = str(row.get("primary") or "").strip() or None
            if primary and primary not in items:
                items.insert(0, primary)
            if items and not primary:
                primary = items[0]
            if items:
                allowed = set(str(x) for x in IndexValue.objects.visible_to(self.user).filter(index_type__slug=slug, pk__in=items).values_list("pk", flat=True))
                if any(x not in allowed for x in items):
                    raise ValidationError("یکی از گزینه‌های انتخاب‌شده در دسترس نیست.")
                if primary and primary not in allowed:
                    primary = None
            cleaned[slug] = {"items": items, "primary": primary}
        return cleaned

    def _structured_titles(self, cleaned):
        titles = set()
        for name in ("content_kind", "content_category", "main_format", "sub_format", "source_type"):
            obj = cleaned.get(name)
            if obj:
                titles.add(normalize_fa(obj.title))
        source = cleaned.get("source")
        if source:
            titles.add(normalize_fa(source.title))
        for name in ("characters", "secondary_characters", "occasions"):
            for obj in cleaned.get(name) or []:
                titles.add(normalize_fa(obj.title))
        topic_ids = [row.get("topic") for row in cleaned.get("topic_analyses_json") or [] if row.get("topic")]
        pred_ids = [row.get("predicate") for row in cleaned.get("topic_analyses_json") or [] if row.get("predicate")]
        ids = topic_ids + pred_ids
        if ids:
            titles.update(normalize_fa(x) for x in IndexValue.objects.filter(pk__in=ids).values_list("title", flat=True))
        special_ids = []
        for row in (cleaned.get("special_indexes_json") or {}).values():
            special_ids.extend(row.get("items") or [])
        if special_ids:
            titles.update(normalize_fa(x) for x in IndexValue.objects.filter(pk__in=special_ids).values_list("title", flat=True))
        return {x for x in titles if x}

    def clean(self):
        cleaned = super().clean()
        access_level = cleaned.get("access_level") or "private"
        cleaned["access_level"] = access_level
        team = cleaned.get("team")
        if access_level == "team" and not team:
            self.add_error("team", "برای دسترسی گروه کاری، یک گروه انتخاب کنید.")
        if access_level != "team":
            cleaned["team"] = None
        if team and self.user and not team.has_member(self.user):
            self.add_error("team", "شما عضو این گروه کاری نیستید.")

        content_kind = cleaned.get("content_kind")
        content_category = cleaned.get("content_category")
        if content_kind and content_category and content_category.parent_id and content_category.parent_id != content_kind.pk:
            self.add_error("content_category", "این گزینه «ریز جنس محتوا» با جنس محتوای انتخاب‌شده سازگار نیست.")
        main_format = cleaned.get("main_format")
        sub_format = cleaned.get("sub_format")
        if main_format and sub_format and sub_format.parent_id and sub_format.parent_id != main_format.pk:
            self.add_error("sub_format", "ریزقالب انتخاب‌شده با قالب اصلی فیش سازگار نیست.")

        # حداقل یک نمایه/دسته ساختاریافته در کنار متن اصلی برای ذخیره لازم است.
        has_signal = any(cleaned.get(x) for x in ("content_kind", "content_category", "main_format", "sub_format", "source_type", "source"))
        has_signal = has_signal or bool(cleaned.get("characters")) or bool(cleaned.get("occasions"))
        has_signal = has_signal or bool(cleaned.get("topic_analyses_json")) or bool(cleaned.get("audiences_json"))
        has_signal = has_signal or any((row.get("items") or []) for row in (cleaned.get("special_indexes_json") or {}).values())
        if self.instance and self.instance.pk and self.instance.indexes.exclude(index_type__slug__in=["promotional-usage", "presentation-style"]).exists():
            has_signal = True
        if cleaned.get("body") and not has_signal:
            self.add_error(None, "برای ذخیره فیش، در کنار متن اصلی حداقل یک نمایه یا دسته ساختاریافته انتخاب کنید.")

        # کلمات کلیدی: فقط واژه‌های خاص حاضر در متن و غیرتکراری با فیلدهای ساختاریافته.
        raw_keywords = cleaned.get("search_keywords") or ""
        keywords = [x.strip() for x in re.split(r"[,،;؛\n]+", raw_keywords) if x.strip()]
        if keywords:
            body_norm = normalize_fa(re.sub(r"<[^>]+>", " ", cleaned.get("body") or ""))
            structured = self._structured_titles(cleaned)
            missing = [kw for kw in keywords if normalize_fa(kw) not in body_norm]
            duplicated = [kw for kw in keywords if normalize_fa(kw) in structured]
            if missing:
                self.add_error("search_keywords", "این کلمات در متن اصلی پیدا نشدند: " + "، ".join(missing[:8]))
            if duplicated:
                self.add_error("search_keywords", "این موارد قبلاً به‌صورت نمایه ساختاریافته ثبت شده‌اند و نباید در کلمات کلیدی تکرار شوند: " + "، ".join(duplicated[:8]))
            cleaned["search_keywords"] = "، ".join(dict.fromkeys(keywords))

        title = cleaned.get("title")
        if title:
            duplicate_qs = Research.objects.exclude(pk=self.instance.pk if self.instance and self.instance.pk else None)
            exact_exists = any(normalize_fa(item.title) == normalize_fa(title) for item in duplicate_qs.exclude(title="").only("title")[:3000])
            if exact_exists and not cleaned.get("duplicate_override"):
                self.add_error(None, "عنوان کاملاً مشابه وجود دارد. موارد پیشنهادی را بررسی کنید؛ برای ثبت آگاهانه، گزینه ادامه با وجود هشدار را فعال کنید.")
        return cleaned


class FullContentForm(StyledModelForm):
    audience_text = forms.CharField(required=False, label="مخاطب", widget=forms.Textarea(attrs={"rows": 2, "placeholder": "برای نمونه: جوانان، دانشجویان، مبلغان"}))
    presentation_date_jalali = forms.CharField(required=False, label="تاریخ ارائه", widget=forms.TextInput(attrs={"class": "form-control jalali-date-input", "autocomplete": "off", "placeholder": "۱۴۰۵/۰۵/۲۸", "data-jalali-picker": "1"}))

    class Meta:
        model = FullContent
        fields = ("title", "content_kind", "body", "file", "topic", "predicate", "processing_keys", "author_owner", "characters", "occasions", "duration_minutes", "presentation_place", "status")
        widgets = {
            "body": forms.Textarea(attrs={"rows": 12, "placeholder": "متن، چکیده یا توضیح محتوای کامل را وارد کنید…"}),
            "processing_keys": forms.SelectMultiple(attrs={"class": "form-select select2"}),
            "characters": forms.SelectMultiple(attrs={"class": "form-select select2"}),
            "occasions": forms.SelectMultiple(attrs={"class": "form-select select2"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        mapping = {
            "topic": "subject", "predicate": "predicate", "processing_keys": "processing-key",
            "author_owner": "author-owner", "characters": "main-character", "occasions": "occasion",
            "presentation_place": "presentation-place",
        }
        for field_name, slug in mapping.items():
            try:
                it = IndexType.objects.get(slug=slug, is_active=True)
                self.fields[field_name].queryset = IndexValue.objects.visible_to(user).filter(index_type=it)
            except IndexType.DoesNotExist:
                self.fields[field_name].queryset = IndexValue.objects.none()
        if self.instance and self.instance.pk:
            self.fields["audience_text"].initial = "، ".join(self.instance.audience_profiles or [])
            from .jalali import format_jalali
            self.fields["presentation_date_jalali"].initial = format_jalali(self.instance.presentation_date)

    def clean_audience_text(self):
        raw = self.cleaned_data.get("audience_text") or ""
        return list(dict.fromkeys(x.strip() for x in re.split(r"[,،;؛\n]+", raw) if x.strip()))

    def clean_presentation_date_jalali(self):
        raw = self.cleaned_data.get("presentation_date_jalali") or ""
        if not raw.strip():
            return None
        from .jalali import parse_jalali
        value = parse_jalali(raw)
        if not value:
            raise ValidationError("تاریخ شمسی را به‌صورت ۱۴۰۵/۰۵/۲۸ وارد کنید.")
        return value



class ReviewCommentForm(StyledModelForm):
    class Meta:
        model = ReviewComment
        fields = ("index_type", "research_index", "severity", "body")
        widgets = {"body": forms.Textarea(attrs={"rows": 4, "placeholder": "خطا، دلیل و پیشنهاد اصلاح را دقیق بنویسید."})}


class AssignmentForm(StyledModelForm):
    class Meta:
        model = ReviewerAssignment
        fields = ("researcher", "reviewer", "scope", "is_active")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["researcher"].queryset = User.objects.filter(roles__slug="researcher").distinct()
        self.fields["reviewer"].queryset = User.objects.filter(roles__slug="reviewer").distinct()
        self.fields["scope"].queryset = IndexType.objects.filter(is_active=True)


class SermonStyleForm(StyledModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False
        self.fields["slug"].help_text = "اختیاری؛ در صورت خالی‌بودن از نام سبک ساخته می‌شود."

    class Meta:
        model = SermonStyle
        fields = (
            "name", "slug", "description", "system_prompt", "outline_template",
            "tone", "language_level", "duration_minutes", "audience_guidance",
            "is_active", "is_default", "order",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "system_prompt": forms.Textarea(attrs={"rows": 7, "placeholder": "روش استدلال، لحن، ریتم، محدودیت‌ها و شیوه استفاده از شواهد را بنویسید."}),
            "outline_template": forms.Textarea(attrs={"rows": 5}),
            "audience_guidance": forms.Textarea(attrs={"rows": 4}),
        }

    def clean_slug(self):
        value = slugify(self.cleaned_data.get("slug") or self.cleaned_data.get("name") or "", allow_unicode=True)
        if not value:
            raise ValidationError("برای سبک یک نام معتبر وارد کنید.")
        conflict = SermonStyle.objects.filter(slug=value)
        if self.instance and self.instance.pk:
            conflict = conflict.exclude(pk=self.instance.pk)
        if conflict.exists():
            raise ValidationError("این شناسه قبلاً برای سبک دیگری استفاده شده است.")
        return value


class PromotionProjectForm(StyledModelForm):
    audiences_json = forms.CharField(widget=forms.HiddenInput, required=False)

    class Meta:
        model = PromotionProject
        fields = ("title", "description", "objective", "sermon_style", "status", "is_active")
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4, "placeholder": "شرح کوتاه پروژه، زمینه و محدوده استفاده"}),
            "objective": forms.Textarea(attrs={"rows": 3, "placeholder": "خروجی و هدف تبلیغی پروژه"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        profiles = []
        if self.instance and self.instance.pk:
            profiles = self.instance.audience_profiles or []
            if not profiles and self.instance.target_audience:
                profiles = [{
                    "is_primary": True, "general": False, "genders": [], "ages": [],
                    "jobs": [], "country": "", "city": "", "literacy": "",
                    "channels": [], "needs": "", "notes": self.instance.target_audience,
                }]
        self.fields["audiences_json"].initial = json.dumps(profiles, ensure_ascii=False)
        self.fields["sermon_style"].queryset = SermonStyle.objects.filter(is_active=True).order_by("order", "name")
        self.fields["sermon_style"].required = False
        self.fields["sermon_style"].widget.attrs.update({
            "class": "form-select select2",
            "data-placeholder": "سبک منبر پروژه را انتخاب کنید",
        })

    def clean_title(self):
        value = re.sub(r"\s+", " ", self.cleaned_data["title"]).strip()
        if not value:
            raise ValidationError("عنوان پروژه الزامی است.")
        return value

    def clean_audiences_json(self):
        raw = self.cleaned_data.get("audiences_json") or "[]"
        try:
            rows = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            raise ValidationError("ساختار مخاطب‌شناسی پروژه نامعتبر است.")
        if not isinstance(rows, list):
            raise ValidationError("ساختار مخاطب‌شناسی پروژه نامعتبر است.")
        job_title_map = {
            str(item["id"]): item["title"]
            for item in IndexValue.objects.filter(
                index_type__slug="audience-job", is_active=True
            ).values("id", "title")
        }
        normalized = []
        for row in rows[:20]:
            if not isinstance(row, dict):
                continue
            item = {
                "is_primary": bool(row.get("is_primary")),
                "general": bool(row.get("general")),
                "genders": [str(x)[:40] for x in (row.get("genders") or []) if str(x).strip()],
                "ages": [str(x)[:40] for x in (row.get("ages") or []) if str(x).strip()],
                "jobs": [
                    job_title_map.get(str(x), str(x))[:120]
                    for x in (row.get("jobs") or []) if str(x).strip()
                ],
                "country": str(row.get("country") or "").strip()[:120],
                "city": str(row.get("city") or "").strip()[:120],
                "literacy": str(row.get("literacy") or "").strip()[:80],
                "channels": [str(x)[:80] for x in (row.get("channels") or []) if str(x).strip()],
                "needs": str(row.get("needs") or "").strip()[:500],
                "notes": str(row.get("notes") or "").strip()[:500],
            }
            if item["general"] or any([
                item["genders"], item["ages"], item["jobs"], item["country"], item["city"],
                item["literacy"], item["channels"], item["needs"], item["notes"],
            ]):
                normalized.append(item)
        if normalized and not any(x["is_primary"] for x in normalized):
            normalized[0]["is_primary"] = True
        first_primary_seen = False
        for item in normalized:
            if item["is_primary"] and not first_primary_seen:
                first_primary_seen = True
            elif item["is_primary"]:
                item["is_primary"] = False
        return normalized

    @staticmethod
    def audience_summary(rows):
        labels = []
        for row in rows:
            if row.get("general"):
                label = "عموم مردم"
            else:
                parts = []
                parts.extend(row.get("ages") or [])
                parts.extend(row.get("genders") or [])
                parts.extend(row.get("jobs") or [])
                if row.get("city"):
                    parts.append(row["city"])
                elif row.get("country"):
                    parts.append(row["country"])
                if row.get("needs"):
                    parts.append(row["needs"])
                elif row.get("notes"):
                    parts.append(row["notes"])
                label = "، ".join(dict.fromkeys(parts)) or "مخاطب اختصاصی"
            labels.append(("اصلی: " if row.get("is_primary") else "") + label)
        return " | ".join(labels)[:500]

    def save(self, commit=True):
        instance = super().save(commit=False)
        profiles = self.cleaned_data.get("audiences_json") or []
        instance.audience_profiles = profiles
        instance.target_audience = self.audience_summary(profiles)
        if commit:
            instance.save()
            self.save_m2m()
        return instance

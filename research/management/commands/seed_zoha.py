import json
import re
from pathlib import Path

from django.core.management.base import BaseCommand

from accounts.models import Role
from research.models import IndexType, IndexValue, normalize_fa

JALALI_MONTHS = "فروردین اردیبهشت خرداد تیر مرداد شهریور مهر آبان آذر دی بهمن اسفند".split()

def occasion_metadata(title):
    digits = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
    match = re.search(r"([۰-۹0-9]{1,2})\s+(" + "|".join(JALALI_MONTHS) + r")", title or "")
    if not match:
        return {}
    return {"jalali_day": int(match.group(1).translate(digits)), "jalali_month": match.group(2)}


class Command(BaseCommand):
    help = "ایجاد نقش‌ها و گزینه‌های استاندارد ضحی"

    def handle(self, *args, **options):
        for slug, name in [
            ("admin", "مدیر"), ("researcher", "فیش‌نگار"),
            ("reviewer", "ارزیاب"), ("preacher", "مبلغ"),
        ]:
            Role.objects.update_or_create(slug=slug, defaults={"name": name})

        data_path = Path(__file__).resolve().parents[2] / "data" / "initial_index_data.json"
        data = json.loads(data_path.read_text(encoding="utf-8"))
        type_map = {}
        total = 0

        for item in data:
            index_type, _ = IndexType.objects.update_or_create(
                slug=item["slug"],
                defaults={
                    "name": item["name"], "description": item.get("description", ""),
                    "data_type": item.get("data_type", "multi"),
                    "is_required": item.get("required", False),
                    "allow_new_values": item.get("allow_new", True),
                    "allow_multiple": item.get("multiple", True),
                    "order": item.get("order", 0), "is_active": True,
                },
            )
            type_map[item["slug"]] = index_type

        # Seed root values first. Hierarchical values are inserted in the second pass.
        for item in data:
            index_type = type_map[item["slug"]]
            for raw in item.get("values", []):
                if isinstance(raw, dict) and raw.get("parent"):
                    continue
                title = raw["title"] if isinstance(raw, dict) else raw
                defaults={"title": title, "is_active": True, "visibility": "global", "approval_status": "approved", "owner": None}
                if item["slug"] == "occasion":
                    defaults["metadata"] = occasion_metadata(title)
                _, created = IndexValue.objects.update_or_create(
                    index_type=index_type, parent=None, normalized_title=normalize_fa(title), defaults=defaults,
                )
                total += int(created)

        # Seed child values. parent_type permits dependencies across index types
        # (e.g. content-category -> content-kind); otherwise parent belongs to the same type.
        for item in data:
            index_type = type_map[item["slug"]]
            for raw in item.get("values", []):
                if not isinstance(raw, dict) or not raw.get("parent"):
                    continue
                title = raw["title"]
                parent_slug = raw.get("parent_type") or ("main-format" if item["slug"] == "content-subformat" else item["slug"])
                parent_type = type_map[parent_slug]
                parent = IndexValue.objects.get(index_type=parent_type, parent=None, normalized_title=normalize_fa(raw["parent"]))
                _, created = IndexValue.objects.update_or_create(
                    index_type=index_type, parent=parent, normalized_title=normalize_fa(title),
                    defaults={"title": title, "is_active": True, "visibility": "global", "approval_status": "approved", "owner": None},
                )
                total += int(created)

        self.stdout.write(self.style.SUCCESS(f"Seed completed. New values: {total}"))

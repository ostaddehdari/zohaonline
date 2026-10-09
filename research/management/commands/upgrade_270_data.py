from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import Team, User
from research.enrichment import refresh_search_document
from research.models import IndexType, IndexValue, PromotionProject, Research, ResearchIndex, Source, normalize_fa

DEMO_USERS = [
    'demo_researcher_1','demo_researcher_2','demo_researcher_3','demo_reviewer_1','demo_reviewer_2'
]
DEMO_PROJECTS = ['خانواده آرام؛ خانه گفت‌وگو','جوان مؤمن؛ امید و هویت','رسانه مسئول؛ روایت اخلاقی']


class Command(BaseCommand):
    help = 'ارتقای داده‌های ۲.۶ به ۲.۷: جنس محتوا، پاکسازی داده نمایشی و بازسازی سند جست‌وجو'

    def add_arguments(self, parser):
        parser.add_argument('--purge-demo', action='store_true', help='حذف داده‌های نمایشی از محیط واقعی')
        parser.add_argument('--skip-search-rebuild', action='store_true')

    @transaction.atomic
    def handle(self, *args, **options):
        kind_type = IndexType.objects.filter(slug='content-kind').first()
        renamed = 0
        if kind_type:
            rename_map = {
                'آیه': 'آیات',
                'آیه و تفسیر': 'آیات',
                'آیات و تفسیر': 'آیات',
                'روایت': 'روایات',
                'حدیث': 'روایات',
                'حدیث و روایت': 'روایات',
                'احادیث و روایات': 'روایات',
                'شعر': 'اشعار',
                'نقل‌قول': 'سخن مشاهیر',
                'نقل قول': 'سخن مشاهیر',
            }
            for old_title, new_title in rename_map.items():
                old = IndexValue.objects.filter(index_type=kind_type, parent__isnull=True, normalized_title=normalize_fa(old_title)).first()
                new = IndexValue.objects.filter(index_type=kind_type, parent__isnull=True, normalized_title=normalize_fa(new_title)).first()
                if old and new and old.pk != new.pk:
                    Research.objects.filter(content_kind=old).update(content_kind=new)
                    # Merge child vocabularies without violating the unique (type,parent,title) constraint.
                    for child in list(old.children.select_related('index_type')):
                        existing_child = IndexValue.objects.filter(
                            index_type=child.index_type, parent=new, normalized_title=child.normalized_title
                        ).exclude(pk=child.pk).first()
                        if existing_child:
                            Research.objects.filter(content_category=child).update(content_category=existing_child)
                            ResearchIndex.objects.filter(index_value=child).update(index_value=existing_child)
                            child.merged_into = existing_child
                            child.is_active = False
                            child.save(update_fields=['merged_into', 'is_active', 'updated_at'])
                        else:
                            child.parent = new
                            child.save(update_fields=['parent', 'updated_at'])
                    old.merged_into = new
                    old.is_active = False
                    old.save(update_fields=['merged_into','is_active','updated_at'])
                    renamed += 1
                elif old:
                    old.title = new_title
                    old.is_active = True
                    old.save()
                    renamed += 1
            # Values no longer in the product vocabulary remain in history but are not offered for new records.
            canonical = [
                'آیات', 'روایات', 'تمثیل', 'داستان', 'سخن مشاهیر', 'اشعار', 'احکام',
                'ذکر مصیبت (روضه)', 'اطلاعات و آمار علمی', 'شبهه', 'لطیفه', 'سایر',
            ]
            canonical_norm = [normalize_fa(x) for x in canonical]
            IndexValue.objects.filter(index_type=kind_type, parent__isnull=True).exclude(
                normalized_title__in=canonical_norm
            ).update(is_active=False)

        purged = 0
        if options['purge_demo']:
            demo_research = Research.objects.filter(author_explanation__contains='ZOHA-DEMO-231')
            purged += demo_research.count()
            demo_research.delete()
            PromotionProject.objects.filter(title__in=DEMO_PROJECTS).delete()
            Team.objects.filter(name='گروه نمونه پژوهش و ارزیابی ضحی').delete()
            User.objects.filter(username__in=DEMO_USERS).delete()
            source = Source.objects.filter(normalized_title=normalize_fa('مجموعه مطالعات کاربردی تبلیغ دینی ضحی')).first()
            if source and not source.researches.exists():
                source.delete()

        rebuilt = 0
        if not options['skip_search_rebuild']:
            for research in Research.objects.select_related('source').iterator(chunk_size=200):
                refresh_search_document(research)
                rebuilt += 1

        self.stdout.write(self.style.SUCCESS(f'Zoha 2.7 data upgrade completed. renamed={renamed}, demo_research_purged={purged}, search_rebuilt={rebuilt}'))

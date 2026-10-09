from django.core.management.base import BaseCommand
from research.enrichment import refresh_search_document
from research.models import Research

class Command(BaseCommand):
    help = 'بازسازی سند جست‌وجوی نرمال‌شده همه فیش‌ها'
    def handle(self, *args, **options):
        total = 0
        for research in Research.objects.select_related('source').iterator(chunk_size=200):
            refresh_search_document(research)
            total += 1
        self.stdout.write(self.style.SUCCESS(f'Rebuilt search documents: {total}'))

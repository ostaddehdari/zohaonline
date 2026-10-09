from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView


def application_patterns():
    return [
        path('admin/django/', admin.site.urls),
        path('accounts/', include('accounts.urls')),
        path('', include('research.urls')),
        path('healthz/', TemplateView.as_view(template_name='healthz.txt', content_type='text/plain'), name='healthz'),
    ]


if settings.URL_PREFIX:
    urlpatterns = [path(f'{settings.URL_PREFIX}/', include(application_patterns()))]
else:
    urlpatterns = application_patterns()

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

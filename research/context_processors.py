from zoha.release import CODENAME, DISPLAY_VERSION, MARKER, RELEASE_NAME_FA, VERSION

def zoha_context(request):
    if request.user.is_authenticated:
        return {
            'release_version': VERSION, 'release_display_version': DISPLAY_VERSION, 'release_marker': MARKER,
            'release_name_fa': RELEASE_NAME_FA, 'release_codename': CODENAME,
            'unread_notifications_count': request.user.zoha_notifications.filter(read_at__isnull=True).count(),
            'is_zoha_admin': request.user.is_superuser or request.user.has_role('admin'),
            'user_has_researcher': request.user.is_superuser or request.user.has_role('researcher'),
            'user_has_reviewer': request.user.is_superuser or request.user.has_role('reviewer'),
        }
    return {'release_version': VERSION, 'release_display_version': DISPLAY_VERSION, 'release_marker': MARKER, 'release_name_fa': RELEASE_NAME_FA, 'release_codename': CODENAME, 'unread_notifications_count': 0, 'is_zoha_admin': False, 'user_has_researcher': False, 'user_has_reviewer': False}

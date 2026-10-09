from django.core.management.base import BaseCommand,CommandError
from accounts.models import User,Role
class Command(BaseCommand):
    def add_arguments(self,p): p.add_argument('--username',required=True); p.add_argument('--email',required=True); p.add_argument('--password',required=True); p.add_argument('--mobile',default='')
    def handle(self,*a,**o):
        u,created=User.objects.get_or_create(username=o['username'],defaults={'email':o['email'],'mobile':o['mobile'] or None,'is_staff':True,'is_superuser':True})
        u.email=o['email']; u.is_staff=True; u.is_superuser=True; u.is_enabled=True; u.set_password(o['password']); u.save()
        role,_=Role.objects.get_or_create(slug='admin',defaults={'name':'مدیر'}); u.roles.add(role)
        self.stdout.write(self.style.SUCCESS('Admin created/updated.'))

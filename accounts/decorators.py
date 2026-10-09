from functools import wraps
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

def role_required(*roles):
    def deco(view):
        @login_required
        @wraps(view)
        def wrapped(request,*args,**kwargs):
            if request.user.is_enabled and (request.user.is_superuser or any(request.user.has_role(r) for r in roles)):
                return view(request,*args,**kwargs)
            raise PermissionDenied
        return wrapped
    return deco

from ipaddress import ip_address
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.http import HttpResponseForbidden

class LocalDemoMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.local_demo = False
        if getattr(settings, 'TOUCHLINE_LOCAL_DEMO', False):
            try:
                local = ip_address(request.META.get('REMOTE_ADDR', '')).is_loopback
            except ValueError:
                local = False
            if not settings.DEBUG or not local:
                return HttpResponseForbidden('Şifresiz demo yalnızca yerel geliştirme sunucusunda açılabilir.')
            if not request.path.startswith(('/admin/', '/accounts/')):
                User = get_user_model()
                user, created = User.objects.get_or_create(username='touchline-local-demo', defaults={'is_active': True})
                if created:
                    user.set_unusable_password()
                    user.save(update_fields=['password'])
                if not user.is_active or user.has_usable_password() or user.is_superuser or user.is_staff:
                    return HttpResponseForbidden('Yerel demo hesabı yapılandırması uygun değil.')
                group, _ = Group.objects.get_or_create(name='Yönetici')
                user.groups.add(group)
                request.user = user
                request.local_demo = True
        return self.get_response(request)

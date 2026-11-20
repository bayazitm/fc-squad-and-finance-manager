from django.core.exceptions import PermissionDenied
from django.db.models import Q
from .models import Clubs, ClubAccess

def is_global(user):
    return user.is_superuser or user.groups.filter(name__in=['Yönetici', 'Görüntüleyici']).exists()

def visible_clubs(user):
    if is_global(user):
        return Clubs.objects.order_by('clubname')
    return Clubs.objects.filter(pk__in=ClubAccess.objects.filter(user=user).values('club_id')).order_by('clubname')

def can_edit(user):
    return user.is_superuser or user.groups.filter(name__in=['Yönetici', 'Kulüp Yetkilisi']).exists()

def require_edit(user):
    if not can_edit(user):
        raise PermissionDenied('Bu işlem için düzenleme yetkisi gerekiyor.')

def scope(queryset, user, kind):
    clubs = visible_clubs(user)
    if kind == 'clubs':
        return queryset.filter(pk__in=clubs)
    if kind == 'transfers':
        return queryset.filter(Q(fromclubid__in=clubs) | Q(toclubid__in=clubs))
    return queryset.filter(clubid__in=clubs)

def transfer_editable(user, obj):
    if user.is_superuser or user.groups.filter(name='Yönetici').exists():
        return True
    # Both registered clubs must be authorized for cross-club writes.
    ids = {obj.toclubid_id}
    if obj.fromclubid_id:
        ids.add(obj.fromclubid_id)
    allowed = set(visible_clubs(user).values_list('pk', flat=True))
    return ids <= allowed

from django.contrib import admin
from .models import ClubAccess, PlayerProfile, ClubSettings, SeasonSquad, SquadEntry, AuditLog
@admin.register(ClubAccess)
class ClubAccessAdmin(admin.ModelAdmin):
    list_display=('user','club')
@admin.register(ClubSettings)
class ClubSettingsAdmin(admin.ModelAdmin):
    list_display=('club','currency')
@admin.register(PlayerProfile)
class PlayerProfileAdmin(admin.ModelAdmin):
    list_display=('player','archived','eligible_turkey')
@admin.register(AuditLog)
class AuditAdmin(admin.ModelAdmin):
    list_display=('created_at','user','action','entity','object_id','summary')
    readonly_fields=('user','action','entity','object_id','summary','before','after','created_at')
    def has_add_permission(self,request):return False
    def has_change_permission(self,request,obj=None):return False
    def has_delete_permission(self,request,obj=None):return False
admin.site.site_header='Touchline · Yönetim'
admin.site.site_title='Touchline'

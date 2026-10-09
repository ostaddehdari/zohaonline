from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Role, Team, TeamMembership, User


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    search_fields = ('name', 'slug')


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("ضحی", {'fields': ('mobile', 'roles', 'is_enabled', 'expertise', 'preaching_field', 'avatar')}),)
    filter_horizontal = ('roles',)
    list_filter = UserAdmin.list_filter + ('is_enabled', 'roles')


class TeamMembershipInline(admin.TabularInline):
    model = TeamMembership
    extra = 0
    autocomplete_fields = ('user',)


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'is_active', 'updated_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'description', 'owner__username', 'owner__first_name', 'owner__last_name')
    autocomplete_fields = ('owner',)
    inlines = [TeamMembershipInline]


@admin.register(TeamMembership)
class TeamMembershipAdmin(admin.ModelAdmin):
    list_display = ('team', 'user', 'role', 'is_active', 'created_at')
    list_filter = ('role', 'is_active')
    search_fields = ('team__name', 'user__username', 'user__first_name', 'user__last_name')
    autocomplete_fields = ('team', 'user')

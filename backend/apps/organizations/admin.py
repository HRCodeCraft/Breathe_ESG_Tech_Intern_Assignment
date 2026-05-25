from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Organization, User


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'industry', 'reporting_year']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ['username', 'email', 'organization', 'role', 'is_active']
    list_filter = ['role', 'organization', 'is_active']
    fieldsets = UserAdmin.fieldsets + (
        ('ESG', {'fields': ('organization', 'role')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('ESG', {'fields': ('organization', 'role')}),
    )

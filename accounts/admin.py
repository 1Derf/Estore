from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from .models import Account, UserProfile, BlockedIP
from django.db import models
# Register your models here.

class AccountAdmin(UserAdmin):
    list_display = ('email','first_name', 'last_name', 'username','last_login', 'date_joined','is_active')
    list_display_links = ('email', 'first_name', 'last_name')
    readonly_fields = ('last_login', 'date_joined')
    ordering = ('-date_joined',)

    filter_horizontal = ()
    list_filter = ()
    fieldsets = ()

class UserProfileAdmin(admin.ModelAdmin):
    def thumbnail(self, object):
        if object.profile_picture:  # Check if image exists to avoid ValueError
            return format_html('<img src="{}" width="30" style=border-radius:50%>'.format(object.profile_picture.url))
        else:
            # Your default SVG placeholder (gray circle with ?)
            return format_html('''
                <svg width="30" height="30" viewBox="0 0 100 100" style="border-radius: 50%;">
                    <circle cx="50" cy="50" r="50" fill="#ccc" />
                    <text x="50" y="55" font-size="40" text-anchor="middle" fill="#fff">?</text>
                </svg>
            ''')
    thumbnail.short_description = 'Profile Picture'
    list_display = ('thumbnail','user', 'city', 'zip_code','state', 'country')

admin.site.register(Account, AccountAdmin)
admin.site.register(UserProfile, UserProfileAdmin)

@admin.register(BlockedIP)
class BlockedIPAdmin(admin.ModelAdmin):
    list_display = ('ip_address', 'reason', 'blocked_at', 'is_blocked')
    search_fields = ('ip_address',)
    list_filter = ('is_blocked',)
    actions = ['unblock_ips']

    def unblock_ips(self, request, queryset):
        queryset.update(is_blocked=False)
        self.message_user(request, "Selected IPs have been unblocked.")
    unblock_ips.short_description = "Unblock selected IPs"


from axes.admin import AccessLogAdmin as BaseAccessLogAdmin
from axes.models import AccessLog

class CustomAccessLogAdmin(BaseAccessLogAdmin):
    list_display = ('attempt_time_formatted', 'logout_time_formatted', 'ip_address', 'username', 'user_agent_short', 'path_info')  # Changed 'path' to 'path_info'
    list_filter = ('attempt_time', 'ip_address', 'username')  # Filters on the side for easy sorting
    search_fields = ('ip_address', 'username', 'user_agent', 'path_info')  # Changed 'path' to 'path_info'
    ordering = ('-attempt_time',)  # Sort by newest first
    readonly_fields = ('attempt_time', 'logout_time')  # Prevent editing timestamps

    def attempt_time_formatted(self, obj):
        return obj.attempt_time.strftime('%b %d, %Y, %I:%M %p') if obj.attempt_time else '-'
    attempt_time_formatted.short_description = 'Attempt Time'

    def logout_time_formatted(self, obj):
        return obj.logout_time.strftime('%b %d, %Y, %I:%M %p') if obj.logout_time else '-'
    logout_time_formatted.short_description = 'Logout Time'

    def user_agent_short(self, obj):
        return obj.user_agent[:50] + '...' if obj.user_agent and len(obj.user_agent) > 50 else obj.user_agent or '-'
    user_agent_short.short_description = 'User Agent'

    actions = ['delete_selected']  # Optional: Allow bulk delete for cleanup

# Replace the default registration with our custom subclass
admin.site.unregister(AccessLog)
admin.site.register(AccessLog, CustomAccessLogAdmin)
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
from .models import Client, ClientUsage


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    """Django admin interface for Client model"""
    
    list_display = [
        'name',
        'status_badge', 
        'tier',
        'api_key_display',
        'contact_email',
        'daily_quota',
        'monthly_quota',
        'usage_today',
        'last_used_display',
        'created_at',
    ]
    
    list_filter = [
        'status',
        'tier',
        'created_at',
        'last_used_at',
    ]
    
    search_fields = [
        'name',
        'contact_email',
        'key_prefix',
        'description',
    ]
    
    readonly_fields = [
        'api_key_display',
        'key_prefix',
        'created_at',
        'updated_at',
        'last_used_at',
        'key_created_at',
        'usage_summary_display',
    ]
    
    fieldsets = [
        ('Client Information', {
            'fields': [
                'name',
                'description',
                'contact_email',
                'created_by',
            ]
        }),
        ('API Access', {
            'fields': [
                'status',
                'tier',
                'api_key_display',
                'key_prefix',
                'key_expires_at',
            ]
        }),
        ('Quotas & Limits', {
            'fields': [
                'daily_quota',
                'monthly_quota', 
                'rate_limit_per_minute',
            ]
        }),
        ('Access Control', {
            'fields': [
                'allowed_endpoints',
                'allowed_ips',
            ],
            'classes': ['collapse'],
        }),
        ('Usage Statistics', {
            'fields': [
                'usage_summary_display',
            ],
            'classes': ['collapse'],
        }),
        ('Timestamps', {
            'fields': [
                'created_at',
                'updated_at',
                'last_used_at',
                'key_created_at',
            ],
            'classes': ['collapse'],
        }),
    ]
    
    actions = [
        'regenerate_api_keys',
        'activate_clients',
        'suspend_clients',
        'revoke_clients',
    ]
    
    def get_queryset(self, request):
        """Optimize queryset with usage counts"""
        return super().get_queryset(request).annotate(
            usage_count_today=Count(
                'usage_records',
                filter=Q(
                    usage_records__timestamp__gte=timezone.now().replace(
                        hour=0, minute=0, second=0, microsecond=0
                    )
                )
            )
        )
    
    def status_badge(self, obj):
        """Display status as colored badge"""
        colors = {
            'active': 'green',
            'inactive': 'gray',
            'suspended': 'orange',
            'revoked': 'red',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">●</span> {}',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'
    
    def api_key_display(self, obj):
        """Display API key with copy button"""
        if not obj.api_key:
            return '-'
        return format_html(
            '<code style="font-family: monospace; background: #f0f0f0; padding: 2px 4px;">{}</code>'
            '<button onclick="navigator.clipboard.writeText(\'{}\'); this.innerHTML=\'Copied!\'; setTimeout(()=>{{this.innerHTML=\'Copy\'}}, 2000);" '
            'style="margin-left: 10px; font-size: 11px; padding: 2px 6px;">Copy</button>',
            f"{obj.key_prefix}{'*' * (len(obj.api_key) - 8)}",
            obj.api_key
        )
    api_key_display.short_description = 'API Key'
    
    def usage_today(self, obj):
        """Display today's usage count"""
        return getattr(obj, 'usage_count_today', 0)
    usage_today.short_description = 'Today'
    usage_today.admin_order_field = 'usage_count_today'
    
    def last_used_display(self, obj):
        """Display last used time in a friendly format"""
        if not obj.last_used_at:
            return format_html('<span style="color: gray;">Never</span>')
        
        now = timezone.now()
        diff = now - obj.last_used_at
        
        if diff.days > 30:
            color = 'red'
        elif diff.days > 7:
            color = 'orange'
        else:
            color = 'green'
            
        return format_html(
            '<span style="color: {};">{}  ago</span>',
            color,
            self._humanize_timedelta(diff)
        )
    last_used_display.short_description = 'Last Used'
    last_used_display.admin_order_field = 'last_used_at'
    
    def usage_summary_display(self, obj):
        """Display comprehensive usage statistics"""
        if not obj.pk:
            return 'Save client first to view usage statistics'
        
        today_summary = obj.get_usage_summary('today')
        month_summary = obj.get_usage_summary('this_month')
        
        return format_html(
            '<div style="line-height: 1.5;">'
            '<strong>Today:</strong> {} requests to {} unique endpoints<br>'
            '<strong>This Month:</strong> {} requests to {} unique endpoints<br>'
            '<a href="{}" target="_blank">View detailed usage records →</a>'
            '</div>',
            today_summary['total_requests'] or 0,
            today_summary['unique_endpoints'] or 0,
            month_summary['total_requests'] or 0,
            month_summary['unique_endpoints'] or 0,
            reverse('admin:api_clientusage_changelist') + f'?client__id__exact={obj.pk}'
        )
    usage_summary_display.short_description = 'Usage Summary'
    
    def _humanize_timedelta(self, delta):
        """Convert timedelta to human readable format"""
        days = delta.days
        hours, remainder = divmod(delta.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        
        if days > 0:
            return f"{days} day{'s' if days > 1 else ''}"
        elif hours > 0:
            return f"{hours} hour{'s' if hours > 1 else ''}"
        elif minutes > 0:
            return f"{minutes} minute{'s' if minutes > 1 else ''}"
        else:
            return "just now"
    
    def save_model(self, request, obj, form, change):
        """Set created_by when saving"""
        if not change:  # Creating new object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    # Admin actions
    def regenerate_api_keys(self, request, queryset):
        """Regenerate API keys for selected clients"""
        count = 0
        for client in queryset:
            if client.is_active():
                client.regenerate_api_key()
                count += 1
        self.message_user(
            request,
            f"Successfully regenerated API keys for {count} client(s)."
        )
    regenerate_api_keys.short_description = "Regenerate API keys for selected clients"
    
    def activate_clients(self, request, queryset):
        """Activate selected clients"""
        updated = queryset.update(status='active')
        self.message_user(
            request,
            f"Successfully activated {updated} client(s)."
        )
    activate_clients.short_description = "Activate selected clients"
    
    def suspend_clients(self, request, queryset):
        """Suspend selected clients"""
        updated = queryset.update(status='suspended')
        self.message_user(
            request,
            f"Successfully suspended {updated} client(s)."
        )
    suspend_clients.short_description = "Suspend selected clients"
    
    def revoke_clients(self, request, queryset):
        """Revoke selected clients"""
        updated = queryset.update(status='revoked')
        self.message_user(
            request,
            f"Successfully revoked {updated} client(s)."
        )
    revoke_clients.short_description = "Revoke selected clients"


@admin.register(ClientUsage)
class ClientUsageAdmin(admin.ModelAdmin):
    """Django admin interface for ClientUsage model - Read-only for analytics"""
    
    list_display = [
        'timestamp',
        'client_name',
        'method',
        'endpoint',
        'status_code_display',
        'response_time_display',
        'ip_address',
    ]
    
    list_filter = [
        'method',
        'status_code',
        'timestamp',
        'client__status',
        'client__tier',
    ]
    
    search_fields = [
        'client__name',
        'endpoint',
        'ip_address',
        'user_agent',
    ]
    
    readonly_fields = [
        'client',
        'endpoint',
        'method',
        'status_code',
        'response_time_ms',
        'user_agent',
        'ip_address',
        'request_size_bytes',
        'response_size_bytes',
        'error_message',
        'timestamp',
    ]
    
    date_hierarchy = 'timestamp'
    
    def has_add_permission(self, request):
        """Disable adding usage records manually"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Disable editing usage records"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Allow deletion for cleanup"""
        return request.user.is_superuser
    
    def client_name(self, obj):
        """Display client name as link"""
        url = reverse('admin:api_client_change', args=[obj.client.pk])
        return format_html('<a href="{}">{}</a>', url, obj.client.name)
    client_name.short_description = 'Client'
    client_name.admin_order_field = 'client__name'
    
    def status_code_display(self, obj):
        """Display status code with color coding"""
        if obj.status_code < 300:
            color = 'green'
        elif obj.status_code < 400:
            color = 'blue'
        elif obj.status_code < 500:
            color = 'orange'
        else:
            color = 'red'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.status_code
        )
    status_code_display.short_description = 'Status'
    status_code_display.admin_order_field = 'status_code'
    
    def response_time_display(self, obj):
        """Display response time with performance coloring"""
        if not obj.response_time_ms:
            return '-'
        
        if obj.response_time_ms < 100:
            color = 'green'
        elif obj.response_time_ms < 500:
            color = 'orange'
        else:
            color = 'red'
        
        return format_html(
            '<span style="color: {};">{} ms</span>',
            color,
            obj.response_time_ms
        )
    response_time_display.short_description = 'Response Time'
    response_time_display.admin_order_field = 'response_time_ms'

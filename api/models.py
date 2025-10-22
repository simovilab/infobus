import secrets
import string
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinLengthValidator
from django.utils import timezone


class Client(models.Model):
    """API Client model for managing registered API consumers"""
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('suspended', 'Suspended'),
        ('revoked', 'Revoked'),
    ]
    
    TIER_CHOICES = [
        ('free', 'Free Tier'),
        ('basic', 'Basic Tier'), 
        ('premium', 'Premium Tier'),
        ('enterprise', 'Enterprise Tier'),
    ]
    
    # Basic client information
    name = models.CharField(
        max_length=255,
        help_text="Client application or organization name"
    )
    description = models.TextField(
        blank=True,
        default='',
        help_text="Description of the client application and its use case"
    )
    contact_email = models.EmailField(
        help_text="Primary contact email for this client"
    )
    
    # API key and security
    api_key = models.CharField(
        max_length=64,
        unique=True,
        help_text="Unique API key for this client"
    )
    key_prefix = models.CharField(
        max_length=8,
        help_text="Readable prefix for the API key (first 8 characters)"
    )
    
    # Status and tier
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
        help_text="Current status of the client"
    )
    tier = models.CharField(
        max_length=20,
        choices=TIER_CHOICES,
        default='free',
        help_text="Client tier determining quotas and limits"
    )
    
    # Quotas and limits
    daily_quota = models.PositiveIntegerField(
        default=1000,
        help_text="Daily API request limit"
    )
    monthly_quota = models.PositiveIntegerField(
        default=30000,
        help_text="Monthly API request limit"
    )
    rate_limit_per_minute = models.PositiveIntegerField(
        default=60,
        help_text="Rate limit per minute"
    )
    
    # Allowed endpoints (JSON field for flexibility)
    allowed_endpoints = models.JSONField(
        default=list,
        blank=True,
        help_text="List of allowed API endpoints. Empty means all endpoints allowed."
    )
    
    # IP restrictions
    allowed_ips = models.JSONField(
        default=list,
        blank=True,
        help_text="List of allowed IP addresses. Empty means no IP restrictions."
    )
    
    # Metadata
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_clients',
        help_text="User who created this client"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_used_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time this client made an API request"
    )
    
    # Key rotation
    key_created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the current API key was generated"
    )
    key_expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Optional expiration date for the API key"
    )
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'API Client'
        verbose_name_plural = 'API Clients'
    
    def __str__(self):
        return f"{self.name} ({self.key_prefix}***)"
    
    def save(self, *args, **kwargs):
        """Generate API key if not provided"""
        if not self.api_key:
            self.api_key = self.generate_api_key()
            self.key_prefix = self.api_key[:8]
            self.key_created_at = timezone.now()
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_api_key(length=64):
        """Generate a secure API key"""
        # Use a mix of letters and numbers for better readability
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))
    
    def regenerate_api_key(self):
        """Regenerate the API key for this client"""
        old_key = self.api_key
        self.api_key = self.generate_api_key()
        self.key_prefix = self.api_key[:8]
        self.key_created_at = timezone.now()
        self.save()
        return old_key
    
    def is_active(self):
        """Check if client is active and not expired"""
        if self.status != 'active':
            return False
        if self.key_expires_at and self.key_expires_at < timezone.now():
            return False
        return True
    
    def get_usage_summary(self, period='today'):
        """Get usage summary for this client"""
        from datetime import timedelta
        
        now = timezone.now()
        if period == 'today':
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == 'this_month':
            start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            start_date = now - timedelta(days=30)
        
        return self.usage_records.filter(
            timestamp__gte=start_date
        ).aggregate(
            total_requests=models.Count('id'),
            unique_endpoints=models.Count('endpoint', distinct=True)
        )


class ClientUsage(models.Model):
    """Track API usage metrics for clients"""
    
    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='usage_records'
    )
    
    # Request details
    endpoint = models.CharField(
        max_length=255,
        help_text="API endpoint that was accessed"
    )
    method = models.CharField(
        max_length=10,
        help_text="HTTP method used (GET, POST, etc.)"
    )
    
    # Response details
    status_code = models.PositiveSmallIntegerField(
        help_text="HTTP response status code"
    )
    response_time_ms = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Response time in milliseconds"
    )
    
    # Request metadata
    user_agent = models.TextField(
        blank=True,
        help_text="Client user agent string"
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="Client IP address"
    )
    
    # Additional context
    request_size_bytes = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Size of request body in bytes"
    )
    response_size_bytes = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Size of response body in bytes"
    )
    
    # Error tracking
    error_message = models.TextField(
        blank=True,
        help_text="Error message if request failed"
    )
    
    # Timestamp
    timestamp = models.DateTimeField(
        auto_now_add=True,
        help_text="When this API request was made"
    )
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Client Usage Record'
        verbose_name_plural = 'Client Usage Records'
        indexes = [
            models.Index(fields=['client', '-timestamp']),
            models.Index(fields=['endpoint', '-timestamp']),
            models.Index(fields=['timestamp']),
        ]
    
    def __str__(self):
        return f"{self.client.name} - {self.method} {self.endpoint} ({self.status_code})"
    
    @property
    def is_error(self):
        """Check if this was an error response"""
        return self.status_code >= 400
    
    @property 
    def is_success(self):
        """Check if this was a successful response"""
        return 200 <= self.status_code < 300

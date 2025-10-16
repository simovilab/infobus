"""
Django management command for client management operations
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from api.models import Client, ClientUsage
from django.utils import timezone
from datetime import timedelta


class Command(BaseCommand):
    help = 'Manage API clients - create, list, rotate keys, change status'

    def add_arguments(self, parser):
        parser.add_argument(
            'action',
            choices=['create', 'list', 'rotate-key', 'activate', 'suspend', 'revoke', 'usage'],
            help='Action to perform'
        )
        parser.add_argument(
            '--name',
            type=str,
            help='Client name (required for create)'
        )
        parser.add_argument(
            '--email',
            type=str,
            help='Contact email (required for create)'
        )
        parser.add_argument(
            '--tier',
            choices=['free', 'basic', 'premium', 'enterprise'],
            default='free',
            help='Client tier (for create, default: free)'
        )
        parser.add_argument(
            '--daily-quota',
            type=int,
            default=1000,
            help='Daily quota (for create, default: 1000)'
        )
        parser.add_argument(
            '--monthly-quota',
            type=int,
            default=30000,
            help='Monthly quota (for create, default: 30000)'
        )
        parser.add_argument(
            '--rate-limit',
            type=int,
            default=60,
            help='Rate limit per minute (for create, default: 60)'
        )
        parser.add_argument(
            '--client-id',
            type=int,
            help='Client ID (required for rotate-key, activate, suspend, revoke, usage)'
        )
        parser.add_argument(
            '--client-name',
            type=str,
            help='Client name (alternative to client-id)'
        )
        parser.add_argument(
            '--description',
            type=str,
            help='Client description (for create)'
        )
        parser.add_argument(
            '--created-by',
            type=str,
            help='Username of creator (for create)'
        )

    def handle(self, *args, **options):
        action = options['action']
        
        if action == 'create':
            self.create_client(options)
        elif action == 'list':
            self.list_clients(options)
        elif action == 'rotate-key':
            self.rotate_key(options)
        elif action == 'activate':
            self.change_status(options, 'active')
        elif action == 'suspend':
            self.change_status(options, 'suspended')
        elif action == 'revoke':
            self.change_status(options, 'revoked')
        elif action == 'usage':
            self.show_usage(options)

    def create_client(self, options):
        """Create a new API client"""
        if not options['name']:
            raise CommandError('--name is required for create action')
        if not options['email']:
            raise CommandError('--email is required for create action')
        
        created_by = None
        if options['created_by']:
            try:
                created_by = User.objects.get(username=options['created_by'])
            except User.DoesNotExist:
                raise CommandError(f"User '{options['created_by']}' not found")
        
        client = Client.objects.create(
            name=options['name'],
            description=options.get('description', ''),
            contact_email=options['email'],
            tier=options['tier'],
            daily_quota=options['daily_quota'],
            monthly_quota=options['monthly_quota'],
            rate_limit_per_minute=options['rate_limit'],
            created_by=created_by,
            status='active'
        )
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully created client: {client.name}')
        )
        self.stdout.write(f'Client ID: {client.id}')
        self.stdout.write(f'API Key: {client.api_key}')
        self.stdout.write(f'Key Prefix: {client.key_prefix}')
        self.stdout.write(
            self.style.WARNING('⚠️  Store the API key securely - it won\'t be shown again!')
        )

    def list_clients(self, options):
        """List all clients with their status"""
        clients = Client.objects.all().order_by('-created_at')
        
        if not clients.exists():
            self.stdout.write('No clients found.')
            return
        
        self.stdout.write(f'{"ID":<5} {"Name":<20} {"Status":<10} {"Tier":<12} {"Email":<25} {"Created":<12}')
        self.stdout.write('-' * 90)
        
        for client in clients:
            self.stdout.write(
                f'{client.id:<5} {client.name[:19]:<20} {client.status:<10} {client.tier:<12} '
                f'{client.contact_email[:24]:<25} {client.created_at.strftime("%Y-%m-%d"):<12}'
            )

    def get_client(self, options):
        """Get client by ID or name"""
        client_id = options.get('client_id')
        client_name = options.get('client_name')
        
        if not client_id and not client_name:
            raise CommandError('Either --client-id or --client-name is required')
        
        try:
            if client_id:
                return Client.objects.get(id=client_id)
            else:
                return Client.objects.get(name=client_name)
        except Client.DoesNotExist:
            identifier = client_id if client_id else client_name
            raise CommandError(f'Client "{identifier}" not found')

    def rotate_key(self, options):
        """Rotate API key for a client"""
        client = self.get_client(options)
        old_key = client.api_key
        new_key = client.regenerate_api_key()
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully rotated API key for client: {client.name}')
        )
        self.stdout.write(f'New API Key: {client.api_key}')
        self.stdout.write(f'New Key Prefix: {client.key_prefix}')
        self.stdout.write(
            self.style.WARNING('⚠️  Update your applications with the new API key!')
        )

    def change_status(self, options, new_status):
        """Change client status"""
        client = self.get_client(options)
        old_status = client.status
        client.status = new_status
        client.save()
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully changed status for client "{client.name}" '
                f'from {old_status} to {new_status}'
            )
        )

    def show_usage(self, options):
        """Show usage statistics for a client"""
        client = self.get_client(options)
        
        self.stdout.write(f'Usage statistics for client: {client.name}')
        self.stdout.write(f'Status: {client.status}')
        self.stdout.write(f'Tier: {client.tier}')
        self.stdout.write(f'Last used: {client.last_used_at or "Never"}')
        
        # Today's usage
        today_summary = client.get_usage_summary('today')
        self.stdout.write(f'Today: {today_summary["total_requests"]} requests to {today_summary["unique_endpoints"]} endpoints')
        
        # This month's usage
        month_summary = client.get_usage_summary('this_month')
        self.stdout.write(f'This month: {month_summary["total_requests"]} requests to {month_summary["unique_endpoints"]} endpoints')
        
        # Recent usage (last 10 records)
        recent_usage = ClientUsage.objects.filter(client=client).order_by('-timestamp')[:10]
        if recent_usage.exists():
            self.stdout.write('\nRecent usage:')
            self.stdout.write(f'{"Time":<20} {"Method":<6} {"Endpoint":<30} {"Status":<6} {"Response Time"}')
            self.stdout.write('-' * 80)
            
            for usage in recent_usage:
                response_time = f'{usage.response_time_ms}ms' if usage.response_time_ms else 'N/A'
                self.stdout.write(
                    f'{usage.timestamp.strftime("%Y-%m-%d %H:%M"):<20} '
                    f'{usage.method:<6} {usage.endpoint[:29]:<30} '
                    f'{usage.status_code:<6} {response_time}'
                )
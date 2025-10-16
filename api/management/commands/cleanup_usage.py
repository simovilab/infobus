"""
Django management command to clean up old usage records
"""

from django.core.management.base import BaseCommand
from api.models import ClientUsage
from django.utils import timezone
from datetime import timedelta


class Command(BaseCommand):
    help = 'Clean up old API usage records to maintain database performance'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=90,
            help='Delete usage records older than this many days (default: 90)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=1000,
            help='Process records in batches of this size (default: 1000)'
        )

    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        batch_size = options['batch_size']
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        self.stdout.write(f'Looking for usage records older than {days} days (before {cutoff_date.date()})')
        
        # Count records to be deleted
        old_records = ClientUsage.objects.filter(timestamp__lt=cutoff_date)
        count = old_records.count()
        
        if count == 0:
            self.stdout.write('No old usage records found.')
            return
        
        if dry_run:
            self.stdout.write(f'DRY RUN: Would delete {count} usage records')
            
            # Show some examples
            sample_records = old_records[:5]
            if sample_records:
                self.stdout.write('Sample records that would be deleted:')
                for record in sample_records:
                    self.stdout.write(
                        f'  - {record.timestamp} | {record.client.name} | '
                        f'{record.method} {record.endpoint} ({record.status_code})'
                    )
            return
        
        # Confirm deletion
        self.stdout.write(f'About to delete {count} usage records.')
        confirm = input('Are you sure you want to continue? (yes/no): ')
        
        if confirm.lower() != 'yes':
            self.stdout.write('Operation cancelled.')
            return
        
        # Delete in batches to avoid memory issues
        deleted_total = 0
        while True:
            batch_ids = list(
                ClientUsage.objects.filter(timestamp__lt=cutoff_date)
                .values_list('id', flat=True)[:batch_size]
            )
            
            if not batch_ids:
                break
            
            deleted_count = ClientUsage.objects.filter(id__in=batch_ids).delete()[0]
            deleted_total += deleted_count
            
            self.stdout.write(f'Deleted {deleted_count} records (total: {deleted_total})')
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully deleted {deleted_total} old usage records')
        )
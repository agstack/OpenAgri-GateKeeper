import os

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connections, connection
from django.db.utils import OperationalError
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.recorder import MigrationRecorder
from django.contrib.auth import get_user_model


# Make sure migrations folder inside backend app contains an empty __init__.py file


class Command(BaseCommand):
    help = "Initial setup command"

    def check_migration_applied(self):
        """Check if migrations have been applied to the database."""
        try:
            recorder = MigrationRecorder(connections['default'])
            applied_migrations = recorder.applied_migrations()
            return len(applied_migrations) > 0
        except OperationalError:
            # Handle cases where the database isn't initialised yet
            self.stdout.write(self.style.WARNING('Database not initialised. No migrations applied yet.'))
            return False

    def check_table_exists(self, table_name):
        """Check if a specific table exists (MySQL-specific)."""
        try:
            with connection.cursor() as cursor:
                cursor.execute(f"SHOW TABLES LIKE '{table_name}'")
                return cursor.fetchone() is not None
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error checking table existence: {str(e)}'))
            return False

    def check_pending_migrations(self):
        for connection in connections.all():
            executor = MigrationExecutor(connection)
            targets = executor.loader.graph.leaf_nodes()
            recorder = MigrationRecorder(connection)
            applied = recorder.applied_migrations()

            unapplied = [migration for migration in targets if migration not in applied]

            return len(unapplied) > 0

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Checking for migration changes...'))

        # Check if migrations are already applied
        if not self.check_migration_applied():
            self.stdout.write(self.style.WARNING('No migrations found. Running migrations...'))
            call_command('makemigrations')
            call_command('migrate')
        elif self.check_pending_migrations():
            self.stdout.write(self.style.SUCCESS('Pending migrations detected, running migrations...'))
            call_command('migrate')
        else:
            self.stdout.write(self.style.SUCCESS('Migrations already applied. Skipping migration step.'))


        # Check if essential tables exist
        if not self.check_table_exists('auth_user'):
            self.stdout.write(self.style.WARNING('auth_user table not found. Running migrations...'))
            call_command('migrate')

        # Collect static files only if not already collected
        static_dir = os.path.join(os.getcwd(), 'staticfiles')
        if not os.path.exists(static_dir) or not os.listdir(static_dir):
            self.stdout.write(self.style.SUCCESS('Collecting static files...'))
            call_command('collectstatic', '--noinput')
        else:
            self.stdout.write(self.style.SUCCESS('Static files already collected.'))

        self.stdout.write(self.style.SUCCESS('Checking for superuser...'))
        user = get_user_model()

        superuser_username = os.getenv('SUPERUSER_USERNAME')
        superuser_email = os.getenv('SUPERUSER_EMAIL')
        superuser_password = os.getenv('SUPERUSER_PASSWORD')

        if not user.objects.filter(username=superuser_username).exists():
            self.stdout.write(self.style.WARNING('Superuser does not exist. Creating one...'))
            user.objects.create_superuser(
                username=superuser_username,
                email=superuser_email,
                password=superuser_password
            )
            self.stdout.write(self.style.SUCCESS('Superuser successfully created.'))
        else:
            self.stdout.write(self.style.SUCCESS('Superuser already exists.'))
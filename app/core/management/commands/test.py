"""To fix the race condition."""

from django.core.management.commands.test import Command as TestCommand
from django.core.management import call_command

class Command(TestCommand):
    def handle(self, *args, **options):
        call_command('wait_for_db')  # Runs your existing wait logic
        super().handle(*args, **options)  # This runs ALL tests (like normal)

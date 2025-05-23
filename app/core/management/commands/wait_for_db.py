"""
Django command to to wait for the database to be available
"""
import time
from psycopg2 import OperationalError as Psycopg2OpError 
from django.db.utils import OperationalError
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    """Django command to wait for database. """

    def handle(self, *args, **options):
        """Entrypoint for command"""
        self.stdout.write('Waiting for database...')
        db_up = False
        MAX_RETRIES = 30
        retries = 0
        while db_up is False and retries < MAX_RETRIES:
            try:
                self.check(databases=['default'])
                db_up = True
            except (Psycopg2OpError, OperationalError):
                self.stdout.write('Database unavailable, waiting 1 second...')
                time.sleep(1)
            retries += 1
        if db_up:
            self.stdout.write(self.style.SUCCESS('Database available!'))
        else:
            self.stdout.write(self.style.ERROR('Database not available after max retries.'))
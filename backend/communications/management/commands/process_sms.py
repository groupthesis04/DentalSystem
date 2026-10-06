import time
import datetime as dt

from django.core.management.base import BaseCommand
from django.db import close_old_connections
from django.utils import timezone

from accounts.models import PatientAccountVerification
from communications.sms import process_queue


class Command(BaseCommand):
    help = "Process SMS events, seven-day balance reminders and provider status updates."

    def add_arguments(self, parser):
        parser.add_argument("--loop", action="store_true", help="Keep running every 30 seconds.")

    def handle(self, *args, **options):
        try:
            while True:
                close_old_connections()
                PatientAccountVerification.objects.filter(
                    created_at__lt=timezone.now() - dt.timedelta(days=1)
                ).delete()
                count = process_queue()
                self.stdout.write(f"SMS queue checked: {count} message(s) processed.")
                if not options["loop"]:
                    break
                time.sleep(30)
        except KeyboardInterrupt:
            self.stdout.write("SMS worker stopped.")

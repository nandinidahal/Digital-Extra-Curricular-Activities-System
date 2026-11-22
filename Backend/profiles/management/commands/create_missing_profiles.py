from django.core.management.base import BaseCommand

from profiles import services


class Command(BaseCommand):
    help = "Create a profile for every user that does not have one yet (safe to run repeatedly)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Only report how many would be created.")
        parser.add_argument("--batch-size", type=int, default=500)

    def handle(self, *args, **options):
        count = services.create_missing_profiles(
            batch_size=options["batch_size"], dry_run=options["dry_run"]
        )
        verb = "Would create" if options["dry_run"] else "Created"
        self.stdout.write(self.style.SUCCESS(f"{verb} {count} missing profile(s)."))

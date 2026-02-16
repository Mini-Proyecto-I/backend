import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = "Crea el usuario administrador de la aplicación (superuser)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--email",
            type=str,
            default=os.environ.get("ADMIN_EMAIL", "admin@example.com"),
            help="Correo del administrador (por defecto: ADMIN_EMAIL o admin@example.com)",
        )
        parser.add_argument(
            "--password",
            type=str,
            default=os.environ.get("ADMIN_PASSWORD", "admin123"),
            help="Contraseña del administrador (por defecto: ADMIN_PASSWORD o admin123)",
        )
        parser.add_argument(
            "--name",
            type=str,
            default=os.environ.get("ADMIN_NAME", "Administrador"),
            help="Nombre del administrador",
        )

    def handle(self, *args, **options):
        email = options["email"]
        password = options["password"]
        name = options["name"]

        if User.objects.filter(email=email).exists():
            self.stdout.write(
                self.style.WARNING(f"El usuario con correo '{email}' ya existe.")
            )
            return

        User.objects.create_superuser(email=email, password=password, name=name)
        self.stdout.write(
            self.style.SUCCESS(f"Usuario administrador creado: {email}")
        )

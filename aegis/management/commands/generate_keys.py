from django.conf import settings
from django.core.management.base import BaseCommand
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization


class Command(BaseCommand):
    help = "Generate ECC key pair and save them in the 'keys' folder at the project root."

    def handle(self, *args, **kwargs):
        # Use BASE_DIR from Django settings to locate the project root
        keys_folder = settings.BASE_DIR / "keys"
        private_key_path = keys_folder / "private_key.pem"
        public_key_path = keys_folder / "public_key.pem"
        log_file = keys_folder / "key_generation.log"

        # Ensure the keys folder exists
        if not keys_folder.exists():
            keys_folder.mkdir()
            self.stdout.write(f"Created folder: {keys_folder}")

        # Check if keys already exist
        if private_key_path.exists() and public_key_path.exists():
            self.stdout.write("Keys already exist. No action taken.")
            return

        # Generate private key
        private_key = ec.generate_private_key(ec.SECP256R1())
        private_key_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        )

        # Save private key to file
        with open(private_key_path, "wb") as private_file:
            private_file.write(private_key_bytes)
        self.stdout.write(f"Private key saved to: {private_key_path}")

        # Generate public key
        public_key = private_key.public_key()
        public_key_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

        # Save public key to file
        with open(public_key_path, "wb") as public_file:
            public_file.write(public_key_bytes)
        self.stdout.write(f"Public key saved to: {public_key_path}")

        # Log the key generation
        with open(log_file, "a") as log:
            log.write("Keys generated successfully.\n")
        self.stdout.write(f"Log entry added to: {log_file}")

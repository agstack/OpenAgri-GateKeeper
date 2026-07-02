# aegis/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver

from aegis.models import PermissionMaster, ServiceMaster


@receiver(post_save, sender=ServiceMaster)
def seed_standard_permissions(sender, instance, created, **kwargs):
    if not created:
        return
    for action, _ in PermissionMaster.ACTION_CHOICES:
        PermissionMaster.objects.get_or_create(
            service=instance,
            action=action,
            defaults={"status": 1},
        )

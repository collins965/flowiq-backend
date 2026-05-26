from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from .models import User, Profile


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Create Profile when a new User is created."""
    if created:
        transaction.on_commit(
            lambda: Profile.objects.get_or_create(user=instance)
        )


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, created, **kwargs):
    """Sync profile on user updates."""
    if not created and hasattr(instance, "profile"):
        try:
            instance.profile.save(update_fields=["updated_at"])
        except Exception:
            pass
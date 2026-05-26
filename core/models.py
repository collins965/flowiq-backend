# Base model all other models inherit from
import uuid
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin


class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required.")

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)

        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()

        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, **extra_fields):
        if not password:
            raise ValueError("Superusers must have a password.")

        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")

        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin, BaseModel):
    """
    Custom user model for FlowIQ.
    Uses email as the primary identifier instead of username.
    """

    email = models.EmailField(unique=True, db_index=True)
    full_name = models.CharField(max_length=200, blank=True, default="")

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        db_table = "core_user"
        verbose_name = "User"
        verbose_name_plural = "Users"

    def __str__(self):
        return self.email

    def get_full_name(self):
        return self.full_name or self.email.split("@")[0]


class Profile(BaseModel):
    """
    Extended profile data linked to User.
    One profile per user.
    """

    PLAN_CHOICES = [
        ("free", "Free"),
        ("pro", "Pro"),
        ("business", "Business"),
    ]

    EMPLOYMENT_CHOICES = [
        ("employed", "Employed"),
        ("self_employed", "Self-Employed"),
        ("both", "Both"),
    ]

    TWO_FA_CHOICES = [
        ("none", "None"),
        ("totp", "Authenticator App"),
        ("sms", "SMS"),
        ("email", "Email OTP"),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile",
    )

    # Personal info
    phone_number = models.CharField(max_length=20, blank=True, default="")
    phone_country_code = models.CharField(max_length=5, blank=True, default="")
    avatar_url = models.URLField(blank=True, default="")
    city = models.CharField(max_length=100, blank=True, default="")
    country_code = models.CharField(max_length=3, default="KE")
    currency_code = models.CharField(max_length=3, default="KES")
    timezone = models.CharField(max_length=50, default="Africa/Nairobi")

    # Employment
    employment_type = models.CharField(
        max_length=20,
        choices=EMPLOYMENT_CHOICES,
        default="employed",
    )

    # Subscription
    plan = models.CharField(
        max_length=20,
        choices=PLAN_CHOICES,
        default="free",
    )
    plan_expires_at = models.DateTimeField(null=True, blank=True)
    subscription_id = models.CharField(max_length=200, blank=True, default="")

    # Onboarding
    onboarding_complete = models.BooleanField(default=False)

    # 2FA
    two_fa_method = models.CharField(
        max_length=10,
        choices=TWO_FA_CHOICES,
        default="none",
    )
    totp_secret = models.CharField(max_length=64, blank=True, default="")

    # AI usage tracking
    ai_queries_this_month = models.IntegerField(default=0)
    ai_queries_reset_at = models.DateTimeField(null=True, blank=True)

    # AI permissions
    ai_permissions = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "core_profile"

    def __str__(self):
        return f"Profile({self.user.email})"

    def save(self, *args, **kwargs):
        if not self.ai_permissions:
            self.ai_permissions = {
                "view_transactions": True,
                "edit_budgets": False,
                "create_goals": False,
                "edit_debts": False,
                "update_profile": False,
                "generate_reports": False,
            }
        super().save(*args, **kwargs)

    @property
    def is_pro(self):
        return self.plan in ("pro", "business")

    @property
    def display_name(self):
        return self.user.get_full_name()
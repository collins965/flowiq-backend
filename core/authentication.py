# core/authentication.py

import logging
import jwt

from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from .models import User, Profile

logger = logging.getLogger(__name__)


class SupabaseJWTAuthentication(BaseAuthentication):
    """
    Authenticate requests using Supabase JWT.

    Expected header:
        Authorization: Bearer <token>
    """

    def authenticate(self, request):
        token = self._extract_token(request)
        if token is None:
            return None  # allow unauthenticated access if no token

        payload = self._verify_token(token)
        user = self._get_or_create_user(payload)

        return (user, token)

    # ─────────────────────────────────────────────
    # Token Extraction
    # ─────────────────────────────────────────────
    def _extract_token(self, request):
        auth_header = request.headers.get("Authorization")

        if not auth_header:
            return None

        parts = auth_header.split()

        if len(parts) != 2:
            raise AuthenticationFailed("Invalid Authorization header format.")

        prefix, token = parts

        if prefix.lower() != "bearer":
            raise AuthenticationFailed("Authorization header must start with Bearer.")

        return token

    # ─────────────────────────────────────────────
    # Token Verification
    # ─────────────────────────────────────────────
    def _verify_token(self, token):
        secret = getattr(settings, "SUPABASE_JWT_SECRET", None)

        if not secret:
            logger.error("SUPABASE_JWT_SECRET is missing.")
            raise AuthenticationFailed("Server authentication misconfigured.")

        try:
            payload = jwt.decode(
                token,
                secret,
                algorithms=["HS256"],
                options={
                    "verify_exp": True,
                    "verify_iat": True,
                    "require": ["sub", "exp", "iat"],
                },
            )
            return payload

        except jwt.ExpiredSignatureError:
            raise AuthenticationFailed("Token expired. Log in again.")

        except jwt.InvalidSignatureError:
            raise AuthenticationFailed("Invalid token signature.")

        except jwt.DecodeError:
            raise AuthenticationFailed("Invalid token format.")

        except jwt.InvalidTokenError:
            raise AuthenticationFailed("Invalid token.")

    # ─────────────────────────────────────────────
    # User Sync
    # ─────────────────────────────────────────────
    def _get_or_create_user(self, payload):
        supabase_uid = payload.get("sub")

        if not supabase_uid:
            raise AuthenticationFailed("Token missing user ID.")

        email = payload.get("email") or f"{supabase_uid}@supabase.local"

        user_metadata = payload.get("user_metadata") or {}
        full_name = user_metadata.get("full_name") or user_metadata.get("name") or ""
        avatar_url = user_metadata.get("avatar_url", "")

        try:
            user = User.objects.get(id=supabase_uid)

            updated_fields = []

            if user.email != email:
                user.email = email
                updated_fields.append("email")

            if full_name and user.full_name != full_name:
                user.full_name = full_name
                updated_fields.append("full_name")

            if updated_fields:
                user.save(update_fields=updated_fields)

        except User.DoesNotExist:
            logger.info(f"Creating user {supabase_uid}")

            user = User.objects.create(
                id=supabase_uid,
                email=email,
                full_name=full_name,
                is_active=True,
            )

            self._sync_profile(user, avatar_url, payload)

        return user

    # ─────────────────────────────────────────────
    # Profile Sync
    # ─────────────────────────────────────────────
    def _sync_profile(self, user, avatar_url, payload):
        try:
            profile, _ = Profile.objects.get_or_create(user=user)

            update_fields = []

            if avatar_url and not profile.avatar_url:
                profile.avatar_url = avatar_url
                update_fields.append("avatar_url")

            app_metadata = payload.get("app_metadata") or {}
            plan = app_metadata.get("plan")

            if plan in ("free", "pro", "business"):
                profile.plan = plan
                update_fields.append("plan")

            if update_fields:
                profile.save(update_fields=update_fields)

        except Exception as e:
            logger.warning(f"Profile sync failed for {user.id}: {e}")
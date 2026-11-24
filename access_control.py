"""Role assignment helpers for identities verified by the OIDC provider."""

from __future__ import annotations

import re
from collections.abc import Iterable


def parse_csv_values(value: str | None) -> frozenset[str]:
    if not value:
        return frozenset()
    return frozenset(
        entry.strip().casefold()
        for entry in value.split(",")
        if entry.strip()
    )


def normalize_email(email: str | None) -> str | None:
    if not isinstance(email, str):
        return None
    normalized = email.strip().casefold()
    if len(normalized) > 254 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized):
        return None
    return normalized


def resolve_role(
    email: str | None,
    admin_emails: Iterable[str],
    allowed_emails: Iterable[str],
    allowed_domains: Iterable[str],
    *,
    email_verified: bool,
) -> str | None:
    if email_verified is not True:
        return None
    identity = normalize_email(email)
    if identity is None:
        return None

    admins = {value.strip().casefold() for value in admin_emails if value.strip()}
    if identity in admins:
        return "admin"

    permitted_emails = {
        value.strip().casefold() for value in allowed_emails if value.strip()
    }
    permitted_domains = {
        value.strip().casefold().lstrip("@")
        for value in allowed_domains
        if value.strip()
    }
    domain = identity.rsplit("@", 1)[1]
    if identity in permitted_emails or domain in permitted_domains:
        return "user"
    return None

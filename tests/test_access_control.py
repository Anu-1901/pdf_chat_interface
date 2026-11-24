import unittest

from access_control import normalize_email, parse_csv_values, resolve_role


class AccessControlTests(unittest.TestCase):
    def test_admins_are_normalized_and_implicitly_allowed(self) -> None:
        role = resolve_role(
            "  ADMIN@Example.com ",
            {"admin@example.com"},
            set(),
            set(),
            email_verified=True,
        )
        self.assertEqual(role, "admin")

    def test_allowlisted_users_and_exact_domains(self) -> None:
        self.assertEqual(
            resolve_role(
                "person@example.com",
                set(),
                {"PERSON@example.com"},
                set(),
                email_verified=True,
            ),
            "user",
        )
        self.assertEqual(
            resolve_role(
                "person@example.com",
                set(),
                set(),
                {"example.com"},
                email_verified=True,
            ),
            "user",
        )
        self.assertIsNone(
            resolve_role(
                "person@sub.example.com",
                set(),
                set(),
                {"example.com"},
                email_verified=True,
            )
        )
        self.assertIsNone(
            resolve_role(
                "unknown@outside.com",
                set(),
                set(),
                set(),
                email_verified=True,
            )
        )

    def test_unverified_identity_never_receives_a_role(self) -> None:
        self.assertIsNone(
            resolve_role(
                "admin@example.com",
                {"admin@example.com"},
                set(),
                set(),
                email_verified=False,
            )
        )

    def test_invalid_emails_and_csv_configuration(self) -> None:
        self.assertIsNone(normalize_email("not-an-email"))
        self.assertIsNone(normalize_email(None))
        self.assertEqual(
            parse_csv_values(" Admin@Example.com, user@example.com ,,"),
            frozenset({"admin@example.com", "user@example.com"}),
        )


if __name__ == "__main__":
    unittest.main()

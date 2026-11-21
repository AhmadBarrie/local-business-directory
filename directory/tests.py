from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import Client, TestCase
from django.urls import reverse

from .models import Business, Category, Review

User = get_user_model()
PASSWORD = "S3cure-pass-98"


def make_user(username, **kwargs):
    return User.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password=PASSWORD,
        **kwargs,
    )


def make_business(owner, category, name="Test Shop", **kwargs):
    defaults = {
        "description": "A test business",
        "address": "1 Test Street",
        "area": "Central",
        "phone": "0800000000",
        "status": Business.Status.APPROVED,
    }
    defaults.update(kwargs)
    return Business.objects.create(
        owner=owner, category=category, name=name, **defaults
    )


class BaseTestCase(TestCase):
    def setUp(self):
        self.owner = make_user("owner")
        self.other = make_user("other")
        self.cat = Category.objects.create(name="Salons", slug="salons")
        self.cat2 = Category.objects.create(name="Mechanics", slug="mechanics")

    def login(self, username="owner"):
        self.assertTrue(self.client.login(username=username, password=PASSWORD))


# ---------------------------------------------------------------- unit tests
class ModelTests(BaseTestCase):
    def test_default_status_is_pending(self):
        b = Business.objects.create(
            owner=self.owner,
            category=self.cat,
            name="New",
            description="d",
            address="a",
            area="x",
            phone="1",
        )
        self.assertEqual(b.status, Business.Status.PENDING)
        self.assertFalse(b.is_public())

    def test_approved_only_returns_approved(self):
        good = make_business(self.owner, self.cat, "Good")
        make_business(self.owner, self.cat, "Waiting", status=Business.Status.PENDING)
        make_business(self.owner, self.cat, "Nope", status=Business.Status.REJECTED)
        self.assertEqual(list(Business.objects.approved()), [good])

    def test_search_matches_name_and_description(self):
        a = make_business(self.owner, self.cat, "Glam Salon")
        b = make_business(
            self.owner, self.cat, "Quick Fix", description="Best salon tools"
        )
        make_business(self.owner, self.cat, "Other", description="Nothing")
        self.assertCountEqual(Business.objects.search("salon"), [a, b])

    def test_search_blank_returns_everything(self):
        make_business(self.owner, self.cat, "A")
        make_business(self.owner, self.cat, "B")
        self.assertEqual(Business.objects.search("").count(), 2)

    def test_category_and_area_filters(self):
        a = make_business(self.owner, self.cat, "A", area="North")
        b = make_business(self.owner, self.cat2, "B", area="South")
        self.assertEqual(list(Business.objects.in_category(self.cat2)), [b])
        self.assertEqual(list(Business.objects.in_area("north")), [a])
        self.assertEqual(Business.objects.in_category(None).count(), 2)
        self.assertEqual(Business.objects.in_area("").count(), 2)

    def test_average_rating(self):
        b = make_business(self.owner, self.cat)
        self.assertIsNone(b.average_rating())
        Review.objects.create(business=b, user=self.owner, rating=5)
        Review.objects.create(business=b, user=self.other, rating=2)
        self.assertEqual(b.average_rating(), 3.5)

    def test_one_review_per_user_per_business(self):
        b = make_business(self.owner, self.cat)
        Review.objects.create(business=b, user=self.other, rating=4)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Review.objects.create(business=b, user=self.other, rating=1)

    def test_string_representations(self):
        b = make_business(self.owner, self.cat, "Shop")
        r = Review.objects.create(business=b, user=self.other, rating=4)
        self.assertEqual(str(self.cat), "Salons")
        self.assertEqual(str(b), "Shop")
        self.assertIn("4/5", str(r))


# ------------------------------------------------------- integration tests
class AccountTests(BaseTestCase):
    def register_data(self, **overrides):
        data = {
            "username": "newuser",
            "email": "new@example.com",
            "password1": PASSWORD,
            "password2": PASSWORD,
        }
        data.update(overrides)
        return data

    def test_register_creates_user_and_logs_in(self):
        response = self.client.post(reverse("register"), self.register_data())
        self.assertRedirects(response, reverse("home"))
        self.assertTrue(User.objects.filter(username="newuser").exists())
        self.assertIn("_auth_user_id", self.client.session)

    def test_register_rejects_duplicate_email(self):
        data = self.register_data(email="owner@example.com")
        response = self.client.post(reverse("register"), data)
        self.assertEqual(response.status_code, 200)
        self.assertIn("email", response.context["form"].errors)
        self.assertFalse(User.objects.filter(username="newuser").exists())

    def test_register_rejects_mismatched_passwords(self):
        data = self.register_data(password2="different-pass-1")
        response = self.client.post(reverse("register"), data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="newuser").exists())

    def test_logged_in_user_is_redirected_from_register(self):
        self.login()
        response = self.client.get(reverse("register"))
        self.assertRedirects(response, reverse("home"))

    def test_login_with_correct_password(self):
        data = {"username": "owner", "password": PASSWORD}
        response = self.client.post(reverse("login"), data)
        self.assertRedirects(response, reverse("home"))
        self.assertIn("_auth_user_id", self.client.session)

    def test_login_with_wrong_password_fails(self):
        data = {"username": "owner", "password": "wrong"}
        response = self.client.post(reverse("login"), data)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_ends_session(self):
        self.login()
        response = self.client.post(reverse("logout"))
        self.assertRedirects(response, reverse("home"))
        self.assertNotIn("_auth_user_id", self.client.session)


class ListingTests(BaseTestCase):
    def form_data(self, **overrides):
        data = {
            "name": "My Shop",
            "category": self.cat.pk,
            "area": "Central",
            "address": "2 Main Road",
            "phone": "0800111222",
            "opening_hours": "Mon-Fri 9-5",
            "description": "Great shop",
        }
        data.update(overrides)
        return data

    def test_create_requires_login(self):
        url = reverse("business_create")
        response = self.client.get(url)
        self.assertRedirects(response, f"{reverse('login')}?next={url}")

    def test_create_saves_pending_listing_for_current_user(self):
        self.login()
        response = self.client.post(reverse("business_create"), self.form_data())
        self.assertRedirects(response, reverse("dashboard"))
        b = Business.objects.get(name="My Shop")
        self.assertEqual(b.owner, self.owner)
        self.assertEqual(b.status, Business.Status.PENDING)

    def test_create_with_missing_fields_saves_nothing(self):
        self.login()
        response = self.client.post(reverse("business_create"), {})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Business.objects.count(), 0)

    def test_dashboard_requires_login(self):
        url = reverse("dashboard")
        response = self.client.get(url)
        self.assertRedirects(response, f"{reverse('login')}?next={url}")

    def test_dashboard_shows_only_own_listings(self):
        make_business(self.owner, self.cat, "Mine")
        make_business(self.other, self.cat, "Theirs")
        self.login()
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, "Mine")
        self.assertNotContains(response, "Theirs")

    def test_owner_can_edit_listing(self):
        b = make_business(self.owner, self.cat, "Old")
        self.login()
        url = reverse("business_edit", args=[b.pk])
        response = self.client.post(url, self.form_data(name="New"))
        self.assertRedirects(response, reverse("business_detail", args=[b.pk]))
        b.refresh_from_db()
        self.assertEqual(b.name, "New")
        self.assertEqual(b.status, Business.Status.APPROVED)

    def test_editing_rejected_listing_resubmits_it(self):
        b = make_business(self.owner, self.cat, status=Business.Status.REJECTED)
        self.login()
        self.client.post(reverse("business_edit", args=[b.pk]), self.form_data())
        b.refresh_from_db()
        self.assertEqual(b.status, Business.Status.PENDING)

    def test_other_user_cannot_edit_listing(self):
        b = make_business(self.owner, self.cat, "Old")
        self.login("other")
        url = reverse("business_edit", args=[b.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url, self.form_data(name="Hacked")).status_code, 404)
        b.refresh_from_db()
        self.assertEqual(b.name, "Old")

    def test_owner_can_delete_after_confirmation(self):
        b = make_business(self.owner, self.cat)
        self.login()
        url = reverse("business_delete", args=[b.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        response = self.client.post(url)
        self.assertRedirects(response, reverse("dashboard"))
        self.assertFalse(Business.objects.filter(pk=b.pk).exists())

    def test_other_user_cannot_delete_listing(self):
        b = make_business(self.owner, self.cat)
        self.login("other")
        response = self.client.post(reverse("business_delete", args=[b.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Business.objects.filter(pk=b.pk).exists())


class PublicViewTests(BaseTestCase):
    def test_home_lists_only_approved(self):
        make_business(self.owner, self.cat, "Visible")
        make_business(self.owner, self.cat, "Hidden", status=Business.Status.PENDING)
        response = self.client.get(reverse("home"))
        self.assertContains(response, "Visible")
        self.assertNotContains(response, "Hidden")

    def test_search_by_name(self):
        make_business(self.owner, self.cat, "Glam Salon")
        make_business(self.owner, self.cat, "Quick Fix")
        response = self.client.get(reverse("home"), {"q": "salon"})
        self.assertContains(response, "Glam Salon")
        self.assertNotContains(response, "Quick Fix")

    def test_search_without_matches_shows_message(self):
        make_business(self.owner, self.cat, "Glam Salon")
        response = self.client.get(reverse("home"), {"q": "zzzz"})
        self.assertContains(response, "No results found")

    def test_category_filter(self):
        make_business(self.owner, self.cat, "Haircut Place")
        make_business(self.owner, self.cat2, "Wrench Works")
        response = self.client.get(reverse("home"), {"category": "mechanics"})
        self.assertContains(response, "Wrench Works")
        self.assertNotContains(response, "Haircut Place")

    def test_unknown_category_returns_nothing(self):
        make_business(self.owner, self.cat, "Glam Salon")
        response = self.client.get(reverse("home"), {"category": "nope"})
        self.assertContains(response, "No results found")

    def test_area_filter(self):
        make_business(self.owner, self.cat, "Northern Shop", area="North")
        make_business(self.owner, self.cat, "Southern Shop", area="South")
        response = self.client.get(reverse("home"), {"area": "South"})
        self.assertContains(response, "Southern Shop")
        self.assertNotContains(response, "Northern Shop")

    def test_results_are_paginated(self):
        for i in range(7):
            make_business(self.owner, self.cat, f"Shop {i}")
        page1 = self.client.get(reverse("home"))
        self.assertEqual(len(page1.context["page_obj"]), 6)
        page2 = self.client.get(reverse("home"), {"page": 2})
        self.assertEqual(len(page2.context["page_obj"]), 1)

    def test_public_profile_shows_details(self):
        b = make_business(self.owner, self.cat, "Shop", phone="0800999888")
        response = self.client.get(reverse("business_detail", args=[b.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "0800999888")
        self.assertContains(response, "No ratings yet")

    def test_profile_shows_average_rating(self):
        b = make_business(self.owner, self.cat)
        Review.objects.create(business=b, user=self.owner, rating=5)
        Review.objects.create(business=b, user=self.other, rating=3)
        response = self.client.get(reverse("business_detail", args=[b.pk]))
        self.assertContains(response, "Average rating 4.0")

    def test_pending_listing_is_hidden_from_public(self):
        b = make_business(self.owner, self.cat, status=Business.Status.PENDING)
        response = self.client.get(reverse("business_detail", args=[b.pk]))
        self.assertEqual(response.status_code, 404)

    def test_pending_listing_hidden_from_other_users(self):
        b = make_business(self.owner, self.cat, status=Business.Status.PENDING)
        self.login("other")
        response = self.client.get(reverse("business_detail", args=[b.pk]))
        self.assertEqual(response.status_code, 404)

    def test_pending_listing_visible_to_owner_and_staff(self):
        b = make_business(self.owner, self.cat, status=Business.Status.PENDING)
        url = reverse("business_detail", args=[b.pk])
        self.login()
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.logout()
        make_user("staff", is_staff=True)
        self.login("staff")
        self.assertEqual(self.client.get(url).status_code, 200)


class ReviewTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.business = make_business(self.owner, self.cat)
        self.url = reverse("review_add", args=[self.business.pk])
        self.detail_url = reverse("business_detail", args=[self.business.pk])

    def test_review_requires_login(self):
        response = self.client.get(self.url)
        self.assertRedirects(response, f"{reverse('login')}?next={self.url}")

    def test_user_can_add_review(self):
        self.login("other")
        response = self.client.post(self.url, {"rating": 4, "comment": "Nice"})
        self.assertRedirects(response, self.detail_url)
        self.assertEqual(Review.objects.count(), 1)
        self.assertEqual(self.business.average_rating(), 4.0)

    def test_second_submission_updates_existing_review(self):
        self.login("other")
        self.client.post(self.url, {"rating": 4, "comment": "Nice"})
        self.client.post(self.url, {"rating": 2, "comment": "Changed my mind"})
        self.assertEqual(Review.objects.count(), 1)
        self.assertEqual(Review.objects.get().rating, 2)

    def test_owner_cannot_review_own_business(self):
        self.login()
        self.client.post(self.url, {"rating": 5, "comment": "Best"})
        self.assertEqual(Review.objects.count(), 0)

    def test_invalid_rating_is_rejected(self):
        self.login("other")
        response = self.client.post(self.url, {"rating": 9, "comment": "x"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Review.objects.count(), 0)

    def test_cannot_review_pending_listing(self):
        pending = make_business(self.owner, self.cat, "P", status=Business.Status.PENDING)
        self.login("other")
        url = reverse("review_add", args=[pending.pk])
        response = self.client.post(url, {"rating": 3, "comment": "x"})
        self.assertEqual(response.status_code, 404)


class AdminActionTests(BaseTestCase):
    def test_admin_can_approve_and_reject_listings(self):
        User.objects.create_superuser("admin", "admin@example.com", PASSWORD)
        self.login("admin")
        b = make_business(self.owner, self.cat, status=Business.Status.PENDING)
        url = reverse("admin:directory_business_changelist")
        self.client.post(url, {"action": "approve_listings", "_selected_action": [b.pk]})
        b.refresh_from_db()
        self.assertEqual(b.status, Business.Status.APPROVED)
        self.client.post(url, {"action": "reject_listings", "_selected_action": [b.pk]})
        b.refresh_from_db()
        self.assertEqual(b.status, Business.Status.REJECTED)


class SecurityTests(BaseTestCase):
    def test_script_in_listing_name_is_escaped(self):
        script = "<script>alert(1)</script>"
        b = make_business(self.owner, self.cat, script)
        home = self.client.get(reverse("home"))
        self.assertNotContains(home, script)
        self.assertContains(home, "&lt;script&gt;alert(1)&lt;/script&gt;")
        detail = self.client.get(reverse("business_detail", args=[b.pk]))
        self.assertNotContains(detail, script)

    def test_sql_injection_style_search_is_harmless(self):
        make_business(self.owner, self.cat, "Glam Salon")
        response = self.client.get(reverse("home"), {"q": "' OR 1=1 --"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No results found")
        self.assertEqual(Business.objects.count(), 1)

    def test_post_without_csrf_token_is_rejected(self):
        client = Client(enforce_csrf_checks=True)
        client.login(username="owner", password=PASSWORD)
        response = client.post(reverse("business_create"), {"name": "x"})
        self.assertEqual(response.status_code, 403)

    def test_passwords_are_stored_hashed(self):
        self.assertNotEqual(self.owner.password, PASSWORD)
        self.assertTrue(self.owner.check_password(PASSWORD))

    def test_admin_is_closed_to_normal_users(self):
        self.login()
        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response["Location"])

    def test_pages_cannot_be_framed(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response["X-Frame-Options"], "DENY")


class WebsiteFieldTests(BaseTestCase):
    def data(self, **overrides):
        data = {
            "name": "Web Shop",
            "category": self.cat.pk,
            "area": "Central",
            "address": "3 Link Road",
            "phone": "0800333444",
            "opening_hours": "",
            "description": "Has a site",
            "website": "https://example.com",
        }
        data.update(overrides)
        return data

    def test_website_is_saved_and_shown_on_profile(self):
        self.login()
        self.client.post(reverse("business_create"), self.data())
        b = Business.objects.get(name="Web Shop")
        response = self.client.get(reverse("business_detail", args=[b.pk]))
        self.assertContains(response, "https://example.com")

    def test_website_is_optional(self):
        self.login()
        self.client.post(reverse("business_create"), self.data(website=""))
        self.assertTrue(Business.objects.filter(name="Web Shop").exists())

    def test_javascript_url_is_rejected(self):
        self.login()
        url = reverse("business_create")
        response = self.client.post(url, self.data(website="javascript:alert(1)"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Business.objects.filter(name="Web Shop").exists())

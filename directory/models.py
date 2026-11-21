from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Avg, Q


class Category(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=80, unique=True)

    class Meta:
        verbose_name_plural = "categories"
        ordering = ["name"]

    def __str__(self):
        return self.name


class BusinessQuerySet(models.QuerySet):
    def approved(self):
        return self.filter(status=Business.Status.APPROVED)

    def search(self, q):
        if not q:
            return self
        return self.filter(Q(name__icontains=q) | Q(description__icontains=q))

    def in_category(self, category):
        if not category:
            return self
        return self.filter(category=category)

    def in_area(self, area):
        if not area:
            return self
        return self.filter(area__iexact=area)


class Business(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending approval"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="businesses"
    )
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="businesses"
    )
    name = models.CharField(max_length=150)
    description = models.TextField()
    address = models.CharField(max_length=255)
    area = models.CharField(max_length=100)
    phone = models.CharField(max_length=30)
    website = models.URLField(blank=True)
    opening_hours = models.CharField(max_length=255, blank=True)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = BusinessQuerySet.as_manager()

    class Meta:
        verbose_name_plural = "businesses"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["area"]),
        ]

    def __str__(self):
        return self.name

    def is_public(self):
        return self.status == self.Status.APPROVED

    def average_rating(self):
        avg = self.reviews.aggregate(avg=Avg("rating"))["avg"]
        return round(avg, 1) if avg is not None else None


class Review(models.Model):
    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="reviews"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews"
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["business", "user"],
                name="one_review_per_user_per_business",
            )
        ]

    def __str__(self):
        return f"{self.user} rated {self.business} {self.rating}/5"

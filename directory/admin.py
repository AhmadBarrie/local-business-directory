from django.contrib import admin

from .models import Business, Category, Review


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "area", "owner", "status", "created_at")
    list_filter = ("status", "category", "area")
    search_fields = ("name", "description", "address")
    actions = ["approve_listings", "reject_listings"]

    @admin.action(description="Approve selected listings")
    def approve_listings(self, request, queryset):
        updated = queryset.update(status=Business.Status.APPROVED)
        self.message_user(request, f"{updated} listing(s) approved.")

    @admin.action(description="Reject selected listings")
    def reject_listings(self, request, queryset):
        updated = queryset.update(status=Business.Status.REJECTED)
        self.message_user(request, f"{updated} listing(s) rejected.")


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("business", "user", "rating", "created_at")
    list_filter = ("rating",)
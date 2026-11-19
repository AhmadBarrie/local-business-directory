from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models import Avg, Count
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DeleteView, UpdateView

from .forms import BusinessForm, RegisterForm, ReviewForm
from .models import Business, Category, Review


def home(request):
    q = request.GET.get("q", "").strip()
    category_slug = request.GET.get("category", "")
    area = request.GET.get("area", "").strip()

    businesses = Business.objects.approved().select_related("category")
    if category_slug:
        category = Category.objects.filter(slug=category_slug).first()
        businesses = businesses.in_category(category) if category else businesses.none()
    businesses = (
        businesses.search(q)
        .in_area(area)
        .annotate(avg_rating=Avg("reviews__rating"), review_count=Count("reviews"))
    )

    paginator = Paginator(businesses, 6)
    page_obj = paginator.get_page(request.GET.get("page"))

    params = request.GET.copy()
    params.pop("page", None)

    areas = (
        Business.objects.approved()
        .order_by("area")
        .values_list("area", flat=True)
        .distinct()
    )
    context = {
        "page_obj": page_obj,
        "total": paginator.count,
        "categories": Category.objects.all(),
        "areas": areas,
        "q": q,
        "selected_category": category_slug,
        "selected_area": area,
        "querystring": params.urlencode(),
    }
    return render(request, "directory/home.html", context)


def business_detail(request, pk):
    business = get_object_or_404(
        Business.objects.select_related("category", "owner"), pk=pk
    )
    is_owner = request.user.is_authenticated and business.owner == request.user
    can_preview = is_owner or (request.user.is_authenticated and request.user.is_staff)
    if not business.is_public() and not can_preview:
        raise Http404
    user_review = None
    if request.user.is_authenticated:
        user_review = business.reviews.filter(user=request.user).first()
    context = {
        "business": business,
        "reviews": business.reviews.select_related("user"),
        "average": business.average_rating(),
        "is_owner": is_owner,
        "user_review": user_review,
    }
    return render(request, "directory/business_detail.html", context)


def register(request):
    if request.user.is_authenticated:
        return redirect("home")
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Welcome! Your account has been created.")
            return redirect("home")
    else:
        form = RegisterForm()
    return render(request, "registration/register.html", {"form": form})


class OwnerRequiredMixin(LoginRequiredMixin):
    """Only lets a logged-in owner reach their own listings.

    Other users get a 404 for listings they do not own.
    """

    def get_queryset(self):
        return super().get_queryset().filter(owner=self.request.user)


class BusinessCreateView(LoginRequiredMixin, CreateView):
    model = Business
    form_class = BusinessForm
    template_name = "directory/business_form.html"
    success_url = reverse_lazy("dashboard")

    def form_valid(self, form):
        form.instance.owner = self.request.user
        form.instance.status = Business.Status.PENDING
        messages.success(
            self.request,
            "Listing submitted. It will appear publicly once an administrator approves it.",
        )
        return super().form_valid(form)


class BusinessUpdateView(OwnerRequiredMixin, UpdateView):
    model = Business
    form_class = BusinessForm
    template_name = "directory/business_form.html"

    def get_success_url(self):
        return reverse("business_detail", args=[self.object.pk])

    def form_valid(self, form):
        if form.instance.status == Business.Status.REJECTED:
            form.instance.status = Business.Status.PENDING
            messages.info(self.request, "Your listing was resubmitted for approval.")
        messages.success(self.request, "Listing updated.")
        return super().form_valid(form)


class BusinessDeleteView(OwnerRequiredMixin, DeleteView):
    model = Business
    template_name = "directory/business_confirm_delete.html"
    success_url = reverse_lazy("dashboard")

    def form_valid(self, form):
        messages.success(self.request, "Listing deleted.")
        return super().form_valid(form)


@login_required
def dashboard(request):
    businesses = request.user.businesses.select_related("category")
    return render(request, "directory/dashboard.html", {"businesses": businesses})


@login_required
def add_review(request, pk):
    business = get_object_or_404(Business.objects.approved(), pk=pk)
    if business.owner == request.user:
        messages.error(request, "You cannot review your own business.")
        return redirect("business_detail", pk=pk)

    existing = Review.objects.filter(business=business, user=request.user).first()
    form = ReviewForm(request.POST or None, instance=existing)
    if request.method == "POST" and form.is_valid():
        review = form.save(commit=False)
        review.business = business
        review.user = request.user
        review.save()
        messages.success(request, "Your review has been saved.")
        return redirect("business_detail", pk=pk)
    return render(request, "directory/review_form.html", {"form": form, "business": business})
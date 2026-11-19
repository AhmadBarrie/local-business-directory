from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models import Avg, Count
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import CreateView

from .forms import BusinessForm, RegisterForm
from .models import Business, Category

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
    can_preview = request.user.is_authenticated and (
        business.owner == request.user or request.user.is_staff
    )
    if not business.is_public() and not can_preview:
        raise Http404
    context = {
        "business": business,
        "reviews": business.reviews.select_related("user"),
        "average": business.average_rating(),
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


@login_required
def dashboard(request):
    businesses = request.user.businesses.select_related("category")
    return render(request, "directory/dashboard.html", {"businesses": businesses})
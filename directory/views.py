from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.generic import CreateView

from .forms import BusinessForm, RegisterForm
from .models import Business


def home(request):
    return render(request, "directory/home.html")


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
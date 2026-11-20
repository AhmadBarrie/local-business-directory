from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("register/", views.register, name="register"),
    path("listings/new/", views.BusinessCreateView.as_view(), name="business_create"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("business/<int:pk>/", views.business_detail, name="business_detail"),
    path("business/<int:pk>/edit/", views.BusinessUpdateView.as_view(), name="business_edit"),
    path("business/<int:pk>/delete/", views.BusinessDeleteView.as_view(), name="business_delete"),
    path("business/<int:pk>/review/", views.add_review, name="review_add"),
]

from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("register/", views.register, name="register"),
    path("listings/new/", views.BusinessCreateView.as_view(), name="business_create"),
    path("dashboard/", views.dashboard, name="dashboard"),   
    path("business/<int:pk>/", views.business_detail, name="business_detail"),
]
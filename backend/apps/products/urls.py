from django.urls import path

from apps.products import views

urlpatterns = [
    path("", views.ProductListCreateView.as_view()),
    path("<int:pk>", views.ProductDetailView.as_view()),
]

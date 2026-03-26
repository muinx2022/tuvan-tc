from django.urls import path

from apps.categories import views

urlpatterns = [
    path("categories", views.CategoryListView.as_view()),
    path("categories/tree", views.CategoryTreeView.as_view()),
    path("categories/<int:pk>/status", views.CategoryStatusView.as_view()),
    path("categories/<int:pk>", views.CategoryDetailView.as_view()),
    path("admin/categories", views.CategoryListView.as_view()),
    path("admin/categories/tree", views.CategoryTreeView.as_view()),
    path("admin/categories/<int:pk>/status", views.CategoryStatusView.as_view()),
    path("admin/categories/<int:pk>", views.CategoryDetailView.as_view()),
]

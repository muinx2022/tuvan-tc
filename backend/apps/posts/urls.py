from django.urls import path

from apps.posts import views

urlpatterns = [
    path("posts", views.PostListCreateView.as_view()),
    path("posts/<int:pk>", views.PostDetailView.as_view()),
    path("admin/posts", views.PostListCreateView.as_view()),
    path("admin/posts/<int:pk>", views.PostDetailView.as_view()),
]

from django.urls import path

from apps.rbac import views

urlpatterns = [
    path("admin/rbac/permissions", views.RbacPermissionsView.as_view()),
    path("admin/rbac/roles", views.RbacRoleListCreateView.as_view()),
    path("admin/rbac/roles/<int:pk>", views.RbacRoleDetailView.as_view()),
]

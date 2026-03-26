from django.urls import path

from apps.users import views

urlpatterns = [
    path("users/me", views.UserMeView.as_view()),
    path("admin/me/permissions", views.AdminMePermissionsView.as_view()),
    path("admin/users", views.AdminUserListView.as_view()),
    path("admin/users/<int:pk>", views.AdminUserDetailView.as_view()),
    path("admin/users/<int:pk>/role", views.AdminUserPatchRoleView.as_view()),
    path("admin/users/<int:pk>/rbac-roles", views.AdminUserPatchRbacView.as_view()),
]

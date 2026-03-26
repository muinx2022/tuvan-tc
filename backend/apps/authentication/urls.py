from django.urls import path

from apps.authentication import views

urlpatterns = [
    path("register", views.RegisterView.as_view()),
    path("login", views.LoginView.as_view()),
    path("google", views.GoogleLoginView.as_view()),
    path("forgot-password", views.ForgotPasswordView.as_view()),
    path("reset-password", views.ResetPasswordView.as_view()),
    path("refresh", views.RefreshView.as_view()),
]

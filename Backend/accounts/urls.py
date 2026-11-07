from django.urls import path

from . import views

urlpatterns = [
    path("register/", views.RegisterView.as_view(), name="register"),
    path("verify-email/", views.VerifyEmailView.as_view(), name="verify-email"),
    path("resend-otp/", views.ResendOTPView.as_view(), name="resend-otp"),
    path("login/", views.LoginView.as_view(), name="login"),
    path("token/refresh/", views.RefreshView.as_view(), name="token-refresh"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("forgot-password/", views.ForgotPasswordView.as_view(), name="forgot-password"),
    path("verify-reset-otp/", views.VerifyResetOTPView.as_view(), name="verify-reset-otp"),
    path("reset-password/", views.ResetPasswordView.as_view(), name="reset-password"),
    path("me/", views.MeView.as_view(), name="me"),
]

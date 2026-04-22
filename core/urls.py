from django.contrib.auth import (
    views as auth_views,  # Import Django's default auth views
)
from django.urls import path

from . import views

urlpatterns = [
    path("", views.catalog, name="catalog"),
    path("bag/<int:bag_id>/", views.bag_detail, name="bag_detail"),
    path("add-to-cart/<int:bag_id>/", views.add_to_cart, name="add_to_cart"),
    path("cart/", views.view_cart, name="view_cart"),
    path("checkout/<int:bag_id>/", views.checkout, name="checkout"),
    path("clear-cart/", views.clear_cart, name="clear_cart"),
    path("payment/", views.initiate_payment, name="initiate_payment"),
    path(
        "stk-callback/", views.stk_callback, name="stk_callback"
    ),  # Added for M-Pesa callback
    path("success/", views.success_view, name="success"),
    path("mpesa-token/", views.get_access_token, name="mpesa-token"),
    # Authentication URLs
    path("register/", views.register_view, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("profile/", views.profile_view, name="profile"),  # Added for user profile page
    path(
        "download-invoice/<int:order_id>/",
        views.download_invoice,
        name="download_invoice",
    ),  # Added for downloading PDF invoice
    path(
        "track-order/<int:order_id>/", views.order_tracking_view, name="order_tracking"
    ),  # Added for order tracking page
]

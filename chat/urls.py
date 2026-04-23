from django.urls import path

from . import views

urlpatterns = [
    path("chat/", views.user_chat, name="user_chat"),
    path("chat/unread/", views.unread_count, name="chat_unread_count"),
    path("admin-chat/", views.admin_chat_list, name="admin_chat_list"),
    path("admin-chat/<int:user_id>/", views.admin_chat_room, name="admin_chat_room"),
]

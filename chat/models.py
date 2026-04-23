from django.conf import settings
from django.db import models


class ChatRoom(models.Model):
    """One room per user — they chat with admin."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chat_room"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Chat: {self.user.email}"

    def unread_count_for_admin(self):
        return self.messages.filter(is_read=False, is_from_admin=False).count()

    def unread_count_for_user(self):
        return self.messages.filter(is_read=False, is_from_admin=True).count()


class Message(models.Model):
    room = models.ForeignKey(
        ChatRoom, on_delete=models.CASCADE, related_name="messages"
    )
    content = models.TextField()
    is_from_admin = models.BooleanField(default=False)
    is_read = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["timestamp"]

    def __str__(self):
        sender = "Admin" if self.is_from_admin else self.room.user.email
        return f"{sender}: {self.content[:50]}"

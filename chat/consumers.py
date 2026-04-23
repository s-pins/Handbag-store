import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.utils import timezone


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]

        if not self.user.is_authenticated:
            await self.close()
            return

        # Admin connects to a specific user's room via URL
        # Regular user connects to their own room
        if self.user.is_staff:
            self.room_user_id = self.scope["url_route"]["kwargs"].get("user_id")
            self.room_group_name = f"chat_{self.room_user_id}"
        else:
            self.room_user_id = self.user.id
            self.room_group_name = f"chat_{self.user.id}"

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        # Mark messages as read on connect
        await self.mark_messages_read()

    async def disconnect(self, close_code):
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(
                self.room_group_name, self.channel_name
            )

    async def receive(self, text_data):
        data = json.loads(text_data)
        content = data.get("message", "").strip()

        if not content:
            return

        is_from_admin = self.user.is_staff
        message = await self.save_message(content, is_from_admin)

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat_message",
                "message": content,
                "sender": "Admin" if is_from_admin else self.user.username,
                "is_from_admin": is_from_admin,
                "timestamp": message.timestamp.strftime("%H:%M"),
                "message_id": message.id,
            },
        )

    async def chat_message(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "message": event["message"],
                    "sender": event["sender"],
                    "is_from_admin": event["is_from_admin"],
                    "timestamp": event["timestamp"],
                    "message_id": event["message_id"],
                }
            )
        )

    @database_sync_to_async
    def save_message(self, content, is_from_admin):
        from .models import ChatRoom, Message

        if is_from_admin:
            room_user_id = self.room_user_id
            room, _ = ChatRoom.objects.get_or_create(user_id=room_user_id)
        else:
            room, _ = ChatRoom.objects.get_or_create(user=self.user)

        return Message.objects.create(
            room=room,
            content=content,
            is_from_admin=is_from_admin,
            is_read=False,
        )

    @database_sync_to_async
    def mark_messages_read(self):
        from .models import ChatRoom, Message

        try:
            if self.user.is_staff:
                room = ChatRoom.objects.get(user_id=self.room_user_id)
                # Admin reads user messages
                Message.objects.filter(
                    room=room, is_from_admin=False, is_read=False
                ).update(is_read=True)
            else:
                room = ChatRoom.objects.get(user=self.user)
                # User reads admin messages
                Message.objects.filter(
                    room=room, is_from_admin=True, is_read=False
                ).update(is_read=True)
        except ChatRoom.DoesNotExist:
            pass

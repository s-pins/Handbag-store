from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from .models import ChatRoom, Message


def is_admin(user):
    return user.is_staff


@login_required
def user_chat(request):
    """The chat view for regular users."""
    room, created = ChatRoom.objects.get_or_create(user=request.user)
    chat_messages = room.messages.all()

    # Mark admin messages as read
    room.messages.filter(is_from_admin=True, is_read=False).update(is_read=True)

    return render(request, 'chat/user_chat.html', {
        'room': room,
        'chat_messages': chat_messages,
    })


@login_required
@user_passes_test(is_admin)
def admin_chat_list(request):
    """Admin view: list of all user conversations."""
    rooms = ChatRoom.objects.select_related('user').prefetch_related('messages').order_by('-created_at')
    return render(request, 'chat/admin_chat_list.html', {'rooms': rooms})


@login_required
@user_passes_test(is_admin)
def admin_chat_room(request, user_id):
    """Admin view: chat with a specific user."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    chat_user = get_object_or_404(User, id=user_id)
    room, created = ChatRoom.objects.get_or_create(user=chat_user)
    chat_messages = room.messages.all()

    # Mark user messages as read
    room.messages.filter(is_from_admin=False, is_read=False).update(is_read=True)

    return render(request, 'chat/admin_chat_room.html', {
        'room': room,
        'chat_user': chat_user,
        'chat_messages': chat_messages,
    })


@login_required
def unread_count(request):
    """AJAX endpoint — returns unread message count for the nav badge."""
    try:
        room = ChatRoom.objects.get(user=request.user)
        count = room.unread_count_for_user()
    except ChatRoom.DoesNotExist:
        count = 0
    return JsonResponse({'count': count})

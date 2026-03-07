from .models import Notification

def notifications_unread(request):
    if request.user.is_authenticated:
        count = Notification.objects.filter(user=request.user, unread=True).count()
    else:
        count = 0
    return {'notifications_unread': count}

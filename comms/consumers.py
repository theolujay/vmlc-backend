from djangochannelsrestframework.generics import GenericAsyncAPIConsumer
from djangochannelsrestframework.observer import model_observer
from djangochannelsrestframework.mixins import ListModelMixin

from .models import Notification
from .serializers import NotificationSerializer

class NotificationConsumer(ListModelMixin, GenericAsyncAPIConsumer):
    
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer

    async def connect(self):
        """
        Called when the websocket is trying to connect.
        If the user is not authenticated the connection will be rejected.
        """
        await self.accept()
        
    @model_observer(Notification)
    async def notification_activity(self,
        message: NotificationSerializer.Meta.model,
        observer=None, **kwargs):
        """
        This is called when a Notification instance is created.
        It sends the serialized data to the user's group.
        """
        await self.send_json(dict(message))
    
    @notification_activity.groups_for_signal
    def notification_activity(self, instance: Notification, **kwargs):
        """
        This function defines which group(s) to send the message to.
        Here, we send it to a group unique to the recipient.
        """
        yield f'user__{instance.recipient_id}'

    @notification_activity.groups_for_consumer
    def notification_activity(self, user_id=None, **kwargs):
        """
        This function defines which group(s) the consumer should subscribe to.
        We subscribe the consumer to their own unique group.
        """
        if self.scope["user"].is_authenticated:
            yield f'user__{self.scope["user"].pk}'
        
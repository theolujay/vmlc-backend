import pytest
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from djangochannelsrestframework.generics import GenericAsyncAPIConsumer

from comms.consumers import NotificationConsumer
from comms.models import Notification

User = get_user_model()


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_notification_consumer_receives_broadcast():
    """
    Tests that the NotificationConsumer correctly receives a message
    when a new Notification object is created for the connected user.
    """
    # 1. Create a user
    user = await User.objects.acreate(
        email="testuser@example.com", first_name="Test", last_name="User"
    )

    # 2. Instantiate the communicator for our consumer
    communicator = WebsocketCommunicator(
        NotificationConsumer.as_asgi(), f"/v1/ws/notifications/?user_id={user.id}"
    )
    # Add the user to the scope to simulate authentication
    communicator.scope["user"] = user

    # 3. Connect to the WebSocket
    connected, _ = await communicator.connect()
    assert connected, "WebSocket connection failed"

    # 4. Create a notification for the user (this should trigger the model_observer)
    notification = await Notification.objects.acreate(
        recipient=user,
        subject="Async Test Subject",
        message="This is a test message from pytest.",
    )

    # 5. Wait for and receive the message from the WebSocket
    response = await communicator.receive_json_from()

    # 6. Assert the received data is correct
    assert response["subject"] == "Async Test Subject"
    assert response["message"] == "This is a test message from pytest."
    assert response["read"] is False

    # 7. Disconnect
    await communicator.disconnect()

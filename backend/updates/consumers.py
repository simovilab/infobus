import json
from channels.generic.websocket import WebsocketConsumer
from screens.models import StopScreen
from .topics import UpdatesTopics
from asgiref.sync import async_to_sync
from redis import Redis
from django.conf import settings


r = Redis(
    host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_CELERY_DB
)


class UpdatesConsumer(WebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.subscriptions = set()

    def connect(self):
        self.accept()
        self.send(text_data=f"Connected successfully in channel {self.channel_name}")

    def disconnect(self, close_code):
        for topic in list(self.subscriptions):
            async_to_sync(self.channel_layer.group_discard)(topic, self.channel_name)
            r.srem("active_subscriptions", topic)

    def receive(self, text_data):
        message = json.loads(text_data)
        action = message["action"]
        if action == "subscribe":
            topic = UpdatesTopics.topic_builder(message)
            self.subscribe(topic)
        elif action == "unsubscribe":
            topic = UpdatesTopics.topic_builder(message)
            self.unsubscribe(topic)

    def subscribe(self, topic):
        async_to_sync(self.channel_layer.group_add)(topic, self.channel_name)
        r.sadd("active_subscriptions", topic)
        self.subscriptions.add(topic)
        self.send(text_data=json.dumps({"message": f"Subscribed to {topic}"}))

    def unsubscribe(self, topic):
        async_to_sync(self.channel_layer.group_discard)(topic, self.channel_name)
        r.srem("active_subscriptions", topic)
        self.subscriptions.discard(topic)
        self.send(text_data=json.dumps({"message": f"Unsubscribed from {topic}"}))

    def realtime_message(self, event):
        message = event["message"]
        self.send(text_data=json.dumps({"message": message}))


class ScreenConsumer(WebsocketConsumer):
    def connect(self):
        self.screen_type = self.scope["url_route"]["kwargs"]["screen_type"]
        self.screen_id = self.scope["url_route"]["kwargs"]["screen_id"]
        self.screen_group_name = f"screen_{self.screen_type}_{self.screen_id}"
        async_to_sync(self.channel_layer.group_add)(
            self.screen_group_name, self.channel_name
        )
        self.accept()
        self.send(text_data=f"Screen group name: {self.screen_group_name}")
        self.activate_screen(self.screen_id)

    def disconnect(self, close_code):
        async_to_sync(self.channel_layer.group_discard)(
            self.screen_group_name, self.channel_name
        )
        self.deactivate_screen(self.screen_id)

    def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = text_data_json["message"]
        async_to_sync(self.channel_layer.group_send)(
            self.screen_group_name, {"type": "screen_message", "message": message}
        )

    def screen_message(self, event):
        message = event["message"]
        self.send(text_data=json.dumps({"message": message}))

    def activate_screen(self, screen_id):
        screen = StopScreen.objects.get(screen_id=screen_id)
        screen.is_active = True
        screen.save()
        print(f"Screen {screen_id} is now connected and active")

    def deactivate_screen(self, screen_id):
        screen = StopScreen.objects.get(screen_id=screen_id)
        screen.is_active = False
        screen.save()
        print(f"Screen {screen_id} is now disconnected and inactive")


class StatusConsumer(WebsocketConsumer):
    def connect(self):
        self.status_group_name = "status"
        async_to_sync(self.channel_layer.group_add)(
            self.status_group_name, self.channel_name
        )
        self.accept()

    def disconnect(self, close_code):
        async_to_sync(self.channel_layer.group_discard)(
            self.status_group_name, self.channel_name
        )

    def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = text_data_json["message"]
        async_to_sync(self.channel_layer.group_send)(
            self.status_group_name, {"type": "status_message", "message": message}
        )

    def status_message(self, event):
        message = event["message"]
        self.send(text_data=json.dumps({"message": message}))

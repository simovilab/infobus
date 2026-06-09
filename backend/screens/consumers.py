import json
from channels.generic.websocket import WebsocketConsumer
from .models import StopScreen
from asgiref.sync import async_to_sync


class RealtimeConsumer(WebsocketConsumer):
    def __init__(self):
        self.subscriptions = set()

    def connect(self):
        self.web_component = self.scope["url_route"]["kwargs"]["web_component"]
        self.element_id = self.scope["url_route"]["kwargs"]["element_id"]
        self.web_group_name = f"web_{self.web_component}_{self.element_id}"
        async_to_sync(self.channel_layer.group_add)(
            self.web_group_name, self.channel_name
        )
        self.accept()
        # TODO: Send initial state (next trips) of the web component to the client
        self.send(text_data=f"Web group name: {self.web_group_name}")

    def disconnect(self, close_code):
        async_to_sync(self.channel_layer.group_discard)(
            self.web_group_name, self.channel_name
        )

    def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = text_data_json["message"]
        async_to_sync(self.channel_layer.group_send)(
            self.web_group_name, {"type": "web_message", "message": message}
        )

    def web_message(self, event):
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

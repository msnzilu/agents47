# 2. Create route (routing.py) - REQUIRED!
websocket_urlpatterns = [
    path('ws/chat/', ChatConsumer.as_asgi()),
]
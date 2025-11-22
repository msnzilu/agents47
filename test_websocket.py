#!/usr/bin/env python
"""
Test WebSocket connection to diagnose the issue
"""
import asyncio
import websockets
import json

async def test_websocket():
    # Replace with actual conversation ID
    uri = "ws://localhost:8000/ws/chat/1/"
    
    print(f"Attempting to connect to: {uri}")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Connected successfully!")
            
            # Wait for connection_established message
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            print(f"Received: {response}")
            
            # Send a test message
            test_msg = {
                "type": "chat_message",
                "message": "Hello from test script",
                "temp_id": "test-123"
            }
            await websocket.send(json.dumps(test_msg))
            print(f"Sent: {test_msg}")
            
            # Wait for response
            response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
            print(f"Received: {response}")
            
    except asyncio.TimeoutError:
        print("❌ Timeout waiting for response")
    except websockets.exceptions.InvalidStatusCode as e:
        print(f"❌ Invalid status code: {e.status_code}")
        print(f"   Headers: {e.headers}")
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")

if __name__ == "__main__":
    asyncio.run(test_websocket())

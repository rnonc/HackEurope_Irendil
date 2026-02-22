```python
uri = "ws://localhost:8000/ws/stool_analysis"
import asyncio
import websockets
import json

async with websockets.connect(uri) as websocket:
    # Préparer les paramètres à envoyer
    params = {
        "token": "YOUR_TOKEN",
        "stool":{"Roseburia spp.":0.1}
    }
    
    # Envoyer le JSON au serveur
    await websocket.send(json.dumps(params))
    
    # Recevoir les résultats en streaming
    try:
        while True:
            message = await websocket.recv()
            data = json.loads(message)
            print(data)
            
    except websockets.exceptions.ConnectionClosed:
        print("Stop")

```
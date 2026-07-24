import asyncio, json, websockets

async def test():
    uri = "ws://olfatometro.local:8765"
    print(f"Conectando a {uri}...")
    async with websockets.connect(uri) as ws:
        print("Conectado.\n")

        # 1) Ping
        await ws.send(json.dumps({"cmd": "ping"}))
        print("<-", await ws.recv())

        # 2) Escuchar 3 segundos de telemetria inactiva
        print("\n--- Telemetria inactiva (3s) ---")
        for _ in range(30):
            print("<-", await ws.recv())

        # 3) Activar canal 2 al 50%
        print("\n--- Activando canal 2 al 50% ---")
        await ws.send(json.dumps({"cmd": "activar", "canal": 2, "velocidad_%": 50}))
        for _ in range(30):
            print("<-", await ws.recv())

        # 4) Parar
        print("\n--- Parando canal 2 ---")
        await ws.send(json.dumps({"cmd": "parar", "canal": 2}))
        for _ in range(5):
            print("<-", await ws.recv())

asyncio.run(test())
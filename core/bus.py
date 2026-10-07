"""Bus de eventos: conecta el núcleo (Python) con la UI (Electron) por WebSocket.
Mensajes JSON: {"tipo": "...", ...}
  núcleo -> UI : estado (idle|escuchando|pensando|hablando), texto, imagen, expandir, contraer, mostrar, ocultar
  UI -> núcleo : texto_escrito, mover_objeto, toggle
"""
import asyncio, json
import websockets


class Bus:
    def __init__(self, puerto: int):
        self.puerto = puerto
        self.clientes = set()
        self.suscriptores = []  # callbacks async(msg)

    async def _handler(self, ws):
        self.clientes.add(ws)
        try:
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                for cb in self.suscriptores:
                    asyncio.create_task(cb(msg))
        finally:
            self.clientes.discard(ws)

    async def servir(self):
        async with websockets.serve(self._handler, "127.0.0.1", self.puerto):
            await asyncio.Future()  # corre para siempre

    def suscribir(self, cb):
        self.suscriptores.append(cb)

    async def emitir(self, tipo: str, **datos):
        if not self.clientes:
            return
        payload = json.dumps({"tipo": tipo, **datos}, ensure_ascii=False)
        await asyncio.gather(*(c.send(payload) for c in list(self.clientes)), return_exceptions=True)

    # Atajos que usa el resto del sistema
    async def estado(self, s: str):            await self.emitir("estado", valor=s)
    async def decir_texto(self, t: str):       await self.emitir("texto", valor=t)
    async def mostrar_imagen(self, ruta: str): await self.emitir("imagen", ruta=ruta)
    async def expandir(self):                  await self.emitir("expandir")
    async def contraer(self):                  await self.emitir("contraer")
    async def mostrar(self):                   await self.emitir("mostrar")
    async def ocultar(self):                   await self.emitir("ocultar")

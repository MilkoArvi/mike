"""Punto de entrada de Mike.  `python core/main.py`  (o el autostart lo lanza solo).

Une: Bus (UI) + Memoria (Obsidian) + Cerebro + 4 agentes + Oídos + Voz + Gestos + Manos.
"""
import asyncio, sys, os
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
os.chdir(RAIZ)
sys.path.insert(0, str(RAIZ / "core"))

import yaml
from bus import Bus
from memory import Memoria
from brain import Cerebro
from council import Consejo
from hive import Colmena
from agents import Orquestador
from voice import Voz
from ears import Oidos
from gestures import Gestos
import hands


class Mike:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.bus = Bus(cfg["ui"]["puerto"])
        self.memoria = Memoria(cfg["memoria"]["vault"])
        self.cerebro = Cerebro(cfg["cerebro"])
        self.consejo = Consejo(cfg["cerebro"], self.memoria)
        self.colmena = Colmena(cfg["cerebro"], self.memoria, self.cerebro)
        self.orq = Orquestador(self.cerebro, self.memoria,
                               cfg["cerebro"].get("doble_verificacion", True),
                               self.consejo, self.colmena)
        self.voz = Voz(cfg["voz"])
        hands.configurar({**cfg["manos"], "camara": cfg["gestos"]["camara"], "vault": cfg["memoria"]["vault"]},
                         self.memoria, self.cerebro, self.colmena, self.consejo)
        self.visible = False
        self.ocupado = asyncio.Lock()
        self.loop = None

    # ---------- entradas ----------
    async def on_palmada(self):
        """Aplauso o chasquido: alterna la UI y, si la muestra, escucha una orden."""
        await self.alternar_ui()

    async def on_texto(self, texto: str):
        """Orden por voz o escrita en la UI."""
        if self.ocupado.locked():
            return
        async with self.ocupado:
            if not self.visible:
                await self.bus.mostrar(); self.visible = True
            await self.bus.estado("pensando")
            try:
                turno = await asyncio.get_running_loop().run_in_executor(None, self.orq.procesar, texto)
            except Exception as e:  # noqa
                self.memoria.error("orquestador", str(e))
                turno = None
            if turno is None:
                await self.responder("Se me cruzaron los cables. Ya lo anoté.")
                return
            if turno.necesita_ejemplo or turno.imagen:
                await self.bus.expandir()
            if turno.imagen:
                await self.bus.mostrar_imagen(turno.imagen)
            await self.responder(turno.respuesta)
            if turno.necesita_ejemplo or turno.imagen:
                await asyncio.sleep(6)          # deja leer el ejemplo
                await self.bus.contraer()
                await asyncio.sleep(1.5)
                await self.bus.ocultar(); self.visible = False

    async def on_mensaje_ui(self, msg: dict):
        t = msg.get("tipo")
        if t == "texto_escrito":
            await self.on_texto(msg.get("valor", ""))
        elif t == "toggle":
            await self.alternar_ui()

    def on_gesto(self, gesto: str):
        # viene de un hilo: pásalo al loop asyncio
        if not self.loop:
            return
        if gesto == "mano_abierta":
            asyncio.run_coroutine_threadsafe(self.bus.mostrar(), self.loop); self.visible = True
        elif gesto == "puño":
            asyncio.run_coroutine_threadsafe(self.bus.ocultar(), self.loop); self.visible = False
        elif gesto.startswith("giro:"):
            asyncio.run_coroutine_threadsafe(self.bus.emitir("giro", grados=int(gesto[5:])), self.loop)

    # ---------- salidas ----------
    async def responder(self, texto: str):
        await self.bus.estado("hablando")
        await self.bus.decir_texto(texto)
        await self.voz.hablar(texto)
        await self.bus.estado("idle")

    async def alternar_ui(self):
        self.visible = not self.visible
        await (self.bus.mostrar() if self.visible else self.bus.ocultar())
        if self.visible:
            await self.bus.estado("escuchando")

    # ---------- arranque ----------
    async def correr(self):
        self.loop = asyncio.get_running_loop()
        self.bus.suscribir(self.on_mensaje_ui)
        tareas = [self.bus.servir()]
        oidos = Oidos(self.cfg["oidos"], self.on_palmada, self.on_texto)
        tareas.append(self._seguro(oidos.escuchar(), "oidos"))
        if self.cfg["gestos"].get("activo"):
            try:
                Gestos(self.cfg["gestos"], self.on_gesto).iniciar()
            except Exception as e:  # noqa
                self.memoria.error("gestos", str(e))
        if not self.cerebro.disponible():
            pista = ("¿Está corriendo Ollama? (ollama serve)" if self.cerebro.prov == "ollama"
                     else "Revisa tu anthropic_api_key en config.yaml.")
            print(f"[Mike] El cerebro no responde. {pista}")
            self.memoria.error("cerebro", "no disponible al arrancar")
        if self.consejo.activo:
            n = len(self.consejo.miembros)
            print(f"[Mike] Consejo: {n} IA(s) vivas." +
                  ("" if n >= 2 else " (se necesitan 2+; instala otro modelo con `ollama pull`)"))
        if self.colmena.viva():
            print(f"[Mike] Colmena: {len(self.colmena.abejas)} abejas sobre "
                  f"{len(self.colmena.pool)} modelo(s), comunicándose por Panal.md")
        self.memoria.diario("Mike arrancó")
        print("[Mike] Listo. Aplaude, di 'Mike' o escribe en la UI.")
        await asyncio.gather(*tareas)

    async def _seguro(self, coro, nombre):
        try:
            await coro
        except Exception as e:  # noqa
            self.memoria.error(nombre, str(e))
            print(f"[Mike] {nombre} se cayó: {e}")


if __name__ == "__main__":
    cfg = yaml.safe_load((RAIZ / "config.yaml").read_text(encoding="utf-8"))
    try:
        asyncio.run(Mike(cfg).correr())
    except KeyboardInterrupt:
        pass

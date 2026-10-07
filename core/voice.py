"""Voz de Mike.
  proveedor: elevenlabs -> usa tu key del plan gratis (~10,000 caracteres/mes).
                           Si falla o se acaba la cuota, cae automáticamente a edge-tts.
  proveedor: edge       -> edge-tts (voces neuronales de Microsoft, gratis, sin key).
"""
import asyncio, tempfile
from pathlib import Path


class Voz:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self._el = None
        key = cfg.get("elevenlabs_api_key", "")
        if cfg.get("proveedor") == "elevenlabs" and key and not key.startswith("TU_"):
            try:
                from elevenlabs.client import ElevenLabs
                self._el = ElevenLabs(api_key=key)
            except Exception:  # noqa
                self._el = None

    async def hablar(self, texto: str):
        if not texto:
            return
        ruta = Path(tempfile.gettempdir()) / "mike_voz.mp3"
        ok = False
        if self._el:
            ok = await asyncio.get_running_loop().run_in_executor(None, self._elevenlabs, texto, ruta)
        if not ok:
            ok = await self._edge(texto, ruta)
        if ok:
            await asyncio.get_running_loop().run_in_executor(None, self._reproducir, ruta)

    def _elevenlabs(self, texto: str, ruta: Path) -> bool:
        try:
            audio = self._el.text_to_speech.convert(
                voice_id=self.cfg["elevenlabs_voice_id"], text=texto,
                model_id="eleven_multilingual_v2", output_format="mp3_22050_32")
            with open(ruta, "wb") as f:
                for chunk in audio:
                    f.write(chunk)
            return True
        except Exception as e:  # noqa  (cuota agotada, key mala, sin internet)
            print("[voz] ElevenLabs falló, uso edge-tts:", e)
            return False

    async def _edge(self, texto: str, ruta: Path) -> bool:
        try:
            import edge_tts
            await edge_tts.Communicate(texto, self.cfg.get("edge_voz", "es-MX-JorgeNeural")).save(str(ruta))
            return True
        except Exception as e:  # noqa
            print("[voz] edge-tts falló:", e)
            return False

    @staticmethod
    def _reproducir(ruta: Path):
        import pygame
        pygame.mixer.init()
        pygame.mixer.music.load(str(ruta))
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            pygame.time.wait(50)
        pygame.mixer.music.unload()

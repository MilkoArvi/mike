"""Oídos de Mike: micrófono siempre abierto.
  1) Detección de aplauso / chasquido  -> evento 'palmada'  (muestra u oculta la UI)
  2) Palabra clave 'mike' o palmada    -> graba hasta silencio y transcribe con faster-whisper (local, gratis)

Un aplauso/chasquido es un pico muy corto y muy fuerte: energía RMS que sube >umbral en <60 ms
y vuelve a bajar. Se calibra con `aplauso_umbral` en config.yaml.
"""
import asyncio, os, queue, time
import numpy as np
import sounddevice as sd

SR = 16000


class Oidos:
    def __init__(self, cfg: dict, on_palmada, on_texto):
        self.cfg = cfg
        self.on_palmada = on_palmada   # async () -> None
        self.on_texto = on_texto       # async (str) -> None
        self.q = queue.Queue()
        self._ultimo_pico = 0.0
        self._modelo = None

    def _modelo_stt(self):
        if self._modelo is None:
            from faster_whisper import WhisperModel
            nombre = self.cfg.get("stt_modelo", "small")
            disp = self.cfg.get("stt_dispositivo", "cpu")   # cpu = no necesita CUDA/cublas
            hilos = os.cpu_count() or 4   # usa todos los núcleos: transcribe más rápido en CPU
            try:
                self._modelo = WhisperModel(nombre, device=disp, compute_type="int8", cpu_threads=hilos)
            except Exception:  # noqa - sin CUDA (falta cublas/cudnn) -> CPU
                self._modelo = WhisperModel(nombre, device="cpu", compute_type="int8", cpu_threads=hilos)
        return self._modelo

    def _callback(self, indata, frames, t, status):
        self.q.put(indata[:, 0].copy())

    def _es_palmada(self, bloque: np.ndarray) -> bool:
        rms = float(np.sqrt(np.mean(bloque ** 2)))
        pico = float(np.max(np.abs(bloque)))
        # pico alto y factor de cresta alto = transitorio (aplauso/chasquido), no voz
        cresta = pico / (rms + 1e-6)
        ahora = time.time()
        if pico > self.cfg.get("aplauso_umbral", 0.35) and cresta > 4 and ahora - self._ultimo_pico > 0.8:
            self._ultimo_pico = ahora
            return True
        return False

    def _grabar_hasta_silencio(self, max_seg: float = 8.0, silencio_seg: float = 0.6) -> np.ndarray:
        buf, inicio, ultimo_sonido = [], time.time(), time.time()
        while time.time() - inicio < max_seg:
            try:
                b = self.q.get(timeout=0.5)
            except queue.Empty:
                continue
            buf.append(b)
            if np.sqrt(np.mean(b ** 2)) > 0.01:
                ultimo_sonido = time.time()
            elif time.time() - ultimo_sonido > silencio_seg and len(buf) > 5:
                break
        return np.concatenate(buf) if buf else np.zeros(SR, dtype=np.float32)

    def _transcribir(self, audio: np.ndarray) -> str:
        # beam_size=1 (búsqueda voraz) es ~5x más rápido que el default 5; en CPU se nota mucho.
        # condition_on_previous_text=False evita reprocesar contexto viejo en cada ventana.
        segs, _ = self._modelo_stt().transcribe(
            audio, language="es", vad_filter=True,
            beam_size=1, best_of=1, condition_on_previous_text=False)
        return " ".join(s.text.strip() for s in segs).strip()

    async def escuchar(self):
        loop = asyncio.get_running_loop()
        palabra = self.cfg.get("palabra_clave", "mike").lower()
        with sd.InputStream(samplerate=SR, channels=1, dtype="float32", blocksize=1024,
                            device=self.cfg.get("microfono"), callback=self._callback):
            ventana = []
            while True:
                try:
                    b = self.q.get(timeout=0.5)
                except queue.Empty:
                    await asyncio.sleep(0.05)
                    continue
                if self.cfg.get("aplauso", True) and self._es_palmada(b):
                    await self.on_palmada()
                    continue
                # ventana deslizante de ~1.4 s para buscar la palabra clave (más corta = reacciona antes)
                ventana.append(b)
                if sum(len(x) for x in ventana) < int(SR * 1.4):
                    continue
                audio = np.concatenate(ventana)
                ventana = ventana[-8:]
                if np.sqrt(np.mean(audio ** 2)) < 0.01:
                    continue  # silencio, no gastes CPU
                texto = await loop.run_in_executor(None, self._transcribir, audio)
                if palabra in texto.lower():
                    orden = texto.lower().split(palabra, 1)[1].strip(" ,.")
                    if len(orden) < 3:  # dijo solo "mike": ahora graba la orden completa
                        resto = await loop.run_in_executor(None, self._grabar_hasta_silencio)
                        orden = await loop.run_in_executor(None, self._transcribir, resto)
                    ventana = []
                    if orden:
                        await self.on_texto(orden)

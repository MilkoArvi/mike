"""Memoria compartida de Mike: un vault de Obsidian (carpeta de .md).
Los 4 agentes leen y escriben aquí. Tú lo abres en Obsidian y ves todo lo que Mike sabe.

vault/
  Mike.md               <- perfil e instrucciones vivas (las reescribe el Crítico)
  Lecciones.md          <- qué aprendió de cada error
  Sugerencias.md        <- mejoras que Mike propone sobre lo que estás haciendo
  Errores/AAAA-MM-DD.md <- registro crudo de fallos
  Diario/AAAA-MM-DD.md  <- qué hizo hoy
"""
from datetime import datetime
from pathlib import Path
import threading


class Memoria:
    def __init__(self, vault: str):
        self.v = Path(vault).resolve()
        self._lock = threading.Lock()
        for d in ("Errores", "Diario"):
            (self.v / d).mkdir(parents=True, exist_ok=True)
        if not (self.v / "Mike.md").exists():
            (self.v / "Mike.md").write_text(PERFIL_INICIAL, encoding="utf-8")
        for f in ("Lecciones.md", "Sugerencias.md", "Panal.md"):
            (self.v / f).touch()

    # ---- lectura ----
    def leer(self, nombre: str) -> str:
        p = self.v / nombre
        return p.read_text(encoding="utf-8") if p.exists() else ""

    def contexto(self, max_chars: int = 6000) -> str:
        """Se inyecta al cerebro en cada turno: perfil + últimas lecciones + diario de hoy."""
        perfil = self.leer("Mike.md")
        lecciones = self.leer("Lecciones.md")[-2500:]
        hoy = self.leer(f"Diario/{self._hoy()}.md")[-1500:]
        return f"## Perfil\n{perfil}\n\n## Lecciones recientes\n{lecciones}\n\n## Hoy\n{hoy}"[-max_chars:]

    # ---- escritura ----
    def _append(self, nombre: str, texto: str):
        with self._lock:
            p = self.v / nombre
            p.parent.mkdir(parents=True, exist_ok=True)
            with p.open("a", encoding="utf-8") as f:
                f.write(texto.rstrip() + "\n")

    def diario(self, texto: str):
        self._append(f"Diario/{self._hoy()}.md", f"- {self._hora()} {texto}")

    def error(self, accion: str, detalle: str):
        self._append(f"Errores/{self._hoy()}.md", f"- {self._hora()} **{accion}** → {detalle}")

    def leccion(self, texto: str):
        self._append("Lecciones.md", f"- [{self._hoy()}] {texto}")

    def sugerencia(self, texto: str):
        self._append("Sugerencias.md", f"- [{self._hoy()}] {texto}")

    def reescribir_perfil(self, texto: str):
        with self._lock:
            (self.v / "Mike.md").write_text(texto, encoding="utf-8")

    # ---- Panal: tablero donde la colmena de agentes se comunica ----
    def panal_sesion(self, tema: str):
        """Abre una celda nueva del panal para una tarea. Recorta el panal si crece demasiado."""
        with self._lock:
            p = self.v / "Panal.md"
            prev = p.read_text(encoding="utf-8") if p.exists() else ""
            if len(prev) > 40000:            # panal rodante: no dejarlo crecer sin fin
                prev = prev[-8000:]
            cab = f"\n\n## {self._hoy()} {self._hora()} — {tema[:80]}\n"
            p.write_text(prev + cab, encoding="utf-8")

    def panal_publicar(self, agente: str, texto: str):
        """Un agente deja su celda en el panal para que las demás la lean."""
        self._append("Panal.md", f"- **{agente}**: {texto.strip()}")

    def panal_leer(self, max_chars: int = 4000) -> str:
        """Lo que llevan dicho las abejas en la sesión actual (cola del panal)."""
        return self.leer("Panal.md")[-max_chars:]

    @staticmethod
    def _hoy():  return datetime.now().strftime("%Y-%m-%d")
    @staticmethod
    def _hora(): return datetime.now().strftime("%H:%M")


PERFIL_INICIAL = """# Mike
Asistente local de Milko. Habla en español, corto y directo.

## Reglas
- Antes de ejecutar, el plan pasa por el Crítico. Si el Crítico dice NO, no se ejecuta.
- Nunca borra archivos ni mueve dinero. Si una acción es irreversible, pregunta primero.
- Cuando algo falla, lo registra en Errores/ y escribe una Lección.
- Si ve una mejora en lo que Milko está haciendo, la anota en Sugerencias.md y la dice una sola vez.

## Lo que sé de Milko
(Mike va llenando esto solo)
"""

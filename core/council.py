"""Consejo: varias IAs deliberan antes de responder para no equivocarse.

Flujo de una 'junta':
  1) Cada miembro responde por su cuenta a la misma pregunta.
  2) Rondas de revisión cruzada: cada miembro ve las respuestas de TODOS (incluida la suya),
     detecta errores y entrega una respuesta corregida + si está de acuerdo con las demás.
  3) Se repite hasta que hay consenso o se agotan las rondas.
  4) El moderador une todo en UNA respuesta final.
  5) Las correcciones se guardan como lecciones en el vault: así todas 'aprenden' para
     los próximos turnos (la lección entra en el contexto de cada IA).

Todo corre con Ollama (gratis, local). Un miembro = un modelo distinto (llama, qwen, gemma...).
Si hay menos de 2 miembros vivos, se degrada solo a un cerebro normal (sin junta).
"""
from brain import Cerebro


class Consejo:
    def __init__(self, cfg_cerebro: dict, memoria):
        self.m = memoria
        cc = cfg_cerebro.get("consejo", {}) or {}
        self.activo = bool(cc.get("activo", False))
        self.rondas = int(cc.get("rondas", 2))
        self.solo_preguntas = bool(cc.get("solo_preguntas", True))
        self.miembros = []  # lista de (nombre, Cerebro)
        for spec in cc.get("miembros", []):
            try:
                c = Cerebro(self._cfg_miembro(cfg_cerebro, spec))
                if c.disponible():
                    self.miembros.append((spec.get("modelo", "?"), c))
            except Exception:  # noqa - un miembro roto no debe tumbar al consejo
                continue

    # ---------- utilidades ----------
    @staticmethod
    def _cfg_miembro(base: dict, spec: dict) -> dict:
        cfg = dict(base)
        cfg["proveedor"] = spec.get("proveedor", base.get("proveedor", "ollama"))
        if cfg["proveedor"] == "ollama":
            cfg["ollama_modelo"] = spec.get("modelo", base.get("ollama_modelo"))
        elif cfg["proveedor"] == "anthropic":
            cfg["anthropic_modelo"] = spec.get("modelo", base.get("anthropic_modelo", "sonnet"))
        return cfg

    def hay_junta(self, intencion: str) -> bool:
        if not self.activo or len(self.miembros) < 2:
            return False
        if self.solo_preguntas and intencion not in ("pregunta",):
            return False
        return True

    def _seguro(self, cerebro, metodo: str, sistema: str, usuario: str):
        """Llama a un miembro sin dejar que su fallo tumbe la junta. Devuelve None si falla."""
        try:
            return getattr(cerebro, metodo)(sistema, usuario)
        except Exception:  # noqa
            return None

    # ---------- deliberación ----------
    def deliberar(self, sistema: str, usuario: str) -> str | None:
        """Devuelve la respuesta consensuada, o None si el consejo no pudo actuar (usar camino normal)."""
        # Ronda 0: cada quien responde por su cuenta
        respuestas = {}
        for nombre, c in self.miembros:
            r = self._seguro(c, "pensar", sistema, usuario)
            if r:
                respuestas[nombre] = r.strip()
        if len(respuestas) < 2:
            return None  # no hubo quórum: que responda el cerebro normal

        vivos = [(n, c) for n, c in self.miembros if n in respuestas]
        correcciones = []

        # Rondas de revisión cruzada
        for _ in range(max(1, self.rondas)):
            panel = "\n\n".join(f"[{n}] {t}" for n, t in respuestas.items())
            nuevas, acuerdos = {}, 0
            for nombre, c in vivos:
                rev = self._seguro_json(
                    c,
                    sistema +
                    "\nEres miembro de un consejo de IAs. Abajo están las respuestas de todos (incluida la tuya). "
                    "Compáralas, detecta errores o datos falsos y entrega la MEJOR respuesta corregida. "
                    'Responde SOLO JSON: {"respuesta":"...","de_acuerdo":true|false,"correccion":"qué estaba mal, o vacío"}',
                    f"Pregunta: {usuario}\n\nRespuestas del consejo:\n{panel}")
                if not isinstance(rev, dict):
                    continue
                nuevas[nombre] = rev.get("respuesta", respuestas[nombre]).strip() or respuestas[nombre]
                if rev.get("de_acuerdo"):
                    acuerdos += 1
                corr = (rev.get("correccion") or "").strip()
                if corr:
                    correcciones.append(corr)
            respuestas.update(nuevas)
            if acuerdos == len(vivos):  # consenso total: no hace falta seguir
                break

        # Moderador: une todo en una respuesta final
        panel = "\n\n".join(f"[{n}] {t}" for n, t in respuestas.items())
        final = self._seguro(
            vivos[0][1], "pensar",
            sistema +
            "\nEres el moderador del consejo. Une las respuestas en UNA sola, correcta, verificada y breve, en español. "
            "Si detectaste un dato dudoso, no lo afirmes.",
            f"Pregunta: {usuario}\n\nRespuestas del consejo:\n{panel}")
        if not final:
            final = max(respuestas.values(), key=len)  # respaldo: la más completa

        # Aprender: guardar correcciones para que TODAS mejoren en próximos turnos
        for corr in dict.fromkeys(correcciones):  # sin duplicados, en orden
            self.m.leccion(f"El consejo corrigió: {corr}")
        self.m.diario(f"Consejo ({len(vivos)} IAs, {len(correcciones)} correcciones) → {final[:80]}")
        return final.strip()

    def _seguro_json(self, cerebro, sistema: str, usuario: str):
        try:
            return cerebro.pensar_json(sistema, usuario)
        except Exception:  # noqa
            return None

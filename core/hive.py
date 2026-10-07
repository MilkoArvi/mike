"""Colmena: una 'mente de panal'. Muchos agentes especializados (abejas) trabajan sobre
una MISMA tarea y se comunican por el Panal (Panal.md en el vault de Obsidian). Cada abeja
lee lo que dijeron las demás, aporta su celda y así el enjambre converge en una decisión.

Diferencia con el Consejo:
  - Consejo  = el MISMO rol resuelto por varios MODELOS (verificación cruzada).
  - Colmena  = varios ROLES distintos (Investigador, Verificador, Seguridad...) que colaboran.
Aquí se combinan: cada abeja se ejecuta en un modelo del pool (rota), así el enjambre es
multi-rol Y multi-modelo. Todo con Ollama (gratis, local).

Flujo:
  1) Se abre una sesión en el Panal con la tarea.
  2) Rondas: cada abeja lee el Panal y publica su celda (se comunican por Obsidian).
  3) La Reina lee todo el Panal y sintetiza la decisión final.
  4) Si hubo una corrección importante, se guarda como Lección: el enjambre 'aprende'.

Se degrada solo: sin abejas o sin modelos vivos, devuelve None y Mike usa el camino normal.
"""
from council import Consejo


# Abejas por defecto (rol -> misión). Se pueden cambiar en config.yaml → cerebro.colmena.agentes
ABEJAS_DEFECTO = [
    {"rol": "Investigador", "mision": "aporta los datos y el contexto que hagan falta"},
    {"rol": "Verificador", "mision": "comprueba los hechos y marca lo que sea falso o dudoso"},
    {"rol": "Seguridad", "mision": "detecta riesgos, daños o acciones irreversibles"},
    {"rol": "Estratega", "mision": "propone la forma más simple y correcta de resolverlo"},
    {"rol": "AbogadoDelDiablo", "mision": "busca el fallo que a todas las demás se les escapó"},
]


class Colmena:
    def __init__(self, cfg_cerebro: dict, memoria, cerebro_principal):
        self.m = memoria
        self.reina = cerebro_principal
        cc = cfg_cerebro.get("colmena", {}) or {}
        self.activo = bool(cc.get("activo", False))
        self.rondas = int(cc.get("rondas", 1))
        self.abejas = cc.get("agentes") or ABEJAS_DEFECTO
        # pool de modelos = los miembros del consejo (varios modelos Ollama vivos)
        pool = Consejo(cfg_cerebro, memoria).miembros
        self.pool = [c for _, c in pool] or [cerebro_principal]

    def viva(self) -> bool:
        return self.activo and bool(self.abejas)

    def _modelo(self, i: int):
        return self.pool[i % len(self.pool)]

    def _zumbar(self, sistema: str, tarea: str) -> str:
        """Todas las abejas deliberan y dejan sus celdas en el Panal. Devuelve el Panal final."""
        self.m.panal_sesion(tarea)
        for ronda in range(max(1, self.rondas)):
            for i, ab in enumerate(self.abejas):
                cerebro = self._modelo(i + ronda)  # rota modelos entre abejas/rondas
                panal = self.m.panal_leer()
                celda = self._seguro(
                    cerebro,
                    sistema +
                    f"\nEres la abeja **{ab['rol']}** del enjambre. Tu misión: {ab['mision']}. "
                    "Lee el Panal (lo que aportaron las otras abejas) y añade SOLO tu aporte: corrige "
                    "errores ajenos si los ves, no repitas lo ya dicho. Máximo 3 frases.\n"
                    f"Panal actual:\n{panal or '(vacío, eres la primera)'}",
                    tarea)
                if celda:
                    self.m.panal_publicar(ab["rol"], celda)
        return self.m.panal_leer(6000)

    # ---------- responder una pregunta ----------
    def responder(self, sistema: str, pregunta: str) -> str | None:
        if not self.viva():
            return None
        panal = self._zumbar(sistema, f"Pregunta: {pregunta}")
        final = self._seguro(
            self.reina,
            sistema +
            "\nEres la Reina del enjambre. Con TODO lo que aportaron las abejas en el Panal, da UNA "
            "respuesta final en español, correcta, verificada y breve. No afirmes datos que el "
            "Verificador marcó como dudosos.\n"
            f"Panal:\n{panal}",
            f"Pregunta: {pregunta}")
        if final:
            self.m.diario(f"Colmena respondió: {final[:80]}")
        return final

    # ---------- revisar una orden antes de ejecutarla ----------
    def revisar_plan(self, sistema: str, orden: str, plan: list) -> dict | None:
        if not self.viva():
            return None
        tarea = f"Orden de Milko: {orden}\nPlan propuesto (herramientas): {plan}"
        panal = self._zumbar(
            sistema + "\nEl enjambre debe decidir si este plan es SEGURO y si CUMPLE la orden.", tarea)
        veredicto = self._seguro_json(
            self.reina,
            sistema +
            "\nEres la Reina. Con lo que dijeron las abejas en el Panal, decide sobre el plan. "
            "Si es peligroso o no cumple la orden, recházalo o corrígelo. Responde SOLO JSON: "
            '{"aprobado":true|false,"motivo":"...","plan_corregido":[...],"leccion":"regla reutilizable o vacío"}\n'
            f"Panal:\n{panal}",
            tarea)
        if isinstance(veredicto, dict) and veredicto.get("leccion", "").strip():
            self.m.leccion(f"Colmena: {veredicto['leccion'].strip()}")  # el enjambre aprende
        return veredicto if isinstance(veredicto, dict) else None

    # ---------- utilidades ----------
    def _seguro(self, cerebro, sistema: str, usuario: str) -> str:
        try:
            return (cerebro.pensar(sistema, usuario) or "").strip()
        except Exception:  # noqa - una abeja caída no tumba la colmena
            return ""

    def _seguro_json(self, cerebro, sistema: str, usuario: str):
        try:
            return cerebro.pensar_json(sistema, usuario)
        except Exception:  # noqa
            return None

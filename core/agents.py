"""Los 4 agentes de Mike. Comparten la misma Memoria (vault de Obsidian) y el mismo Cerebro.

  Oyente       -> entiende lo que dijiste y decide si es charla, orden o pregunta
  Planificador -> convierte una orden en pasos con herramientas concretas
  Crítico      -> revisa el plan ANTES de ejecutar (la "doble verificación") y DESPUÉS
                  de cada fallo escribe una lección. También propone sugerencias.
  Manos        -> ejecuta el plan aprobado con las herramientas de hands.py

Flujo por turno:  Oyente -> Planificador -> Crítico(pre) -> Manos -> Crítico(post) -> respuesta
"""
from dataclasses import dataclass, field
import traceback

from brain import Cerebro
from memory import Memoria
from council import Consejo
from hive import Colmena
import hands


@dataclass
class Turno:
    entrada: str
    intencion: str = "charla"          # charla | orden | pregunta
    plan: list = field(default_factory=list)
    aprobado: bool = False
    motivo: str = ""
    resultados: list = field(default_factory=list)
    respuesta: str = ""
    necesita_ejemplo: bool = False     # si True, la UI se expande a pantalla completa
    imagen: str | None = None


BASE = """Eres Mike, asistente local de Milko en su PC (Windows). Responde SIEMPRE en español, corto.
Memoria compartida (léela, es tu contexto real):
{memoria}
"""


class Oyente:
    def __init__(self, c: Cerebro, m: Memoria):
        self.c, self.m = c, m

    def clasificar(self, t: Turno):
        r = self.c.pensar_json(
            BASE.format(memoria=self.m.contexto()) +
            'Clasifica el mensaje. Responde SOLO JSON: {"intencion":"charla|orden|pregunta","resumen":"..."}',
            t.entrada)
        t.intencion = r.get("intencion", "charla") if r.get("intencion") in ("charla", "orden", "pregunta") else "charla"
        self.m.diario(f"Oyente: '{t.entrada[:60]}' → {t.intencion}")


class Planificador:
    def __init__(self, c: Cerebro, m: Memoria):
        self.c, self.m = c, m

    def planear(self, t: Turno):
        r = self.c.pensar_json(
            BASE.format(memoria=self.m.contexto()) +
            "Herramientas disponibles:\n" + hands.DESCRIPCION +
            '\nConvierte la orden en pasos. Usa solo esas herramientas. Responde SOLO JSON:\n'
            '{"pasos":[{"herramienta":"nombre","args":{...},"por_que":"..."}],"respuesta_corta":"..."}',
            t.entrada)
        t.plan = [p for p in r.get("pasos", []) if p.get("herramienta") in hands.HERRAMIENTAS]
        t.respuesta = r.get("respuesta_corta", "")


class Critico:
    def __init__(self, c: Cerebro, m: Memoria, doble: bool = True, colmena: Colmena | None = None):
        self.c, self.m, self.doble, self.colmena = c, m, doble, colmena

    # --- antes de ejecutar: la doble verificación ---
    def revisar(self, t: Turno):
        # 1) reglas duras que no dependen del modelo
        for p in t.plan:
            if p["herramienta"] == "ejecutar" and any(k in str(p["args"]) for k in hands.PELIGROSAS):
                t.aprobado, t.motivo = False, f"Comando peligroso bloqueado: {p['args']}"
                self.m.diario(f"Crítico bloqueó: {t.motivo}")
                return
        if not self.doble or not t.plan:
            t.aprobado = True
            return
        # 1b) comandos de configuración (modo rápido, cambiar modelo...) se aprueban al instante,
        #     sin junta: así apagar la junta es inmediato y no espera una última deliberación lenta.
        if all(p["herramienta"] in hands.RAPIDAS for p in t.plan):
            t.aprobado, t.motivo = True, "config instantánea"
            return
        # 2a) la colmena hace junta sobre la orden (si está viva)
        if self.colmena and self.colmena.viva():
            r = self.colmena.revisar_plan(BASE.format(memoria=self.m.contexto()), t.entrada, t.plan)
            if r:
                t.aprobado = bool(r.get("aprobado", False))
                t.motivo = r.get("motivo", "")
                if r.get("plan_corregido"):
                    t.plan = [p for p in r["plan_corregido"] if p.get("herramienta") in hands.HERRAMIENTAS]
                self.m.diario(f"Colmena {'aprobó' if t.aprobado else 'rechazó'}: {t.motivo}")
                return
        # 2b) respaldo: segunda opinión de un solo modelo, con las lecciones en contexto
        r = self.c.pensar_json(
            BASE.format(memoria=self.m.contexto()) +
            "Eres el Crítico. Revisa este plan contra las Lecciones y las Reglas del perfil. "
            "¿Cumple la orden? ¿Es seguro? ¿Repite un error pasado? Responde SOLO JSON: "
            '{"aprobado":true|false,"motivo":"...","plan_corregido":[...] }',
            f"Orden: {t.entrada}\nPlan: {t.plan}")
        t.aprobado = bool(r.get("aprobado", False))
        t.motivo = r.get("motivo", "")
        if r.get("plan_corregido"):
            t.plan = [p for p in r["plan_corregido"] if p.get("herramienta") in hands.HERRAMIENTAS]
        self.m.diario(f"Crítico {'aprobó' if t.aprobado else 'rechazó'}: {t.motivo}")

    # --- después de ejecutar: aprender ---
    def aprender(self, t: Turno):
        fallos = [r for r in t.resultados if r.get("error")]
        if not fallos:
            return
        for f in fallos:
            self.m.error(f["herramienta"], f["error"])
        r = self.c.pensar_json(
            BASE.format(memoria=self.m.contexto()) +
            "Algo falló. Escribe UNA lección concreta y reutilizable (qué evitar / qué hacer distinto). "
            'Responde SOLO JSON: {"leccion":"...","actualizar_perfil":"texto completo del perfil o vacío"}',
            f"Orden: {t.entrada}\nFallos: {fallos}")
        if r.get("leccion"):
            self.m.leccion(r["leccion"])
        if r.get("actualizar_perfil", "").strip():
            self.m.reescribir_perfil(r["actualizar_perfil"])

    # --- proactividad: sugerir mejoras ---
    def sugerir(self, contexto_trabajo: str) -> str | None:
        r = self.c.pensar_json(
            BASE.format(memoria=self.m.contexto()) +
            "Si ves UNA mejora concreta y útil para lo que Milko está haciendo, dila. Si no, sugerencia vacía. "
            'Responde SOLO JSON: {"sugerencia":"..."}',
            contexto_trabajo)
        s = r.get("sugerencia", "").strip()
        if s:
            self.m.sugerencia(s)
        return s or None


class Manos:
    def __init__(self, m: Memoria):
        self.m = m

    def ejecutar(self, t: Turno):
        for p in t.plan:
            h = hands.HERRAMIENTAS[p["herramienta"]]
            try:
                out = h(**(p.get("args") or {}))
                t.resultados.append({"herramienta": p["herramienta"], "salida": out})
                self.m.diario(f"Manos: {p['herramienta']} → {str(out)[:80]}")
                if p["herramienta"] in ("captura", "foto"):
                    t.imagen = out
            except Exception as e:  # noqa
                t.resultados.append({"herramienta": p["herramienta"], "error": f"{e}\n{traceback.format_exc()[-300:]}"})


class Orquestador:
    """Une los 4 agentes. Un `procesar(texto)` = un turno completo."""

    def __init__(self, cerebro: Cerebro, memoria: Memoria, doble_verificacion: bool = True,
                 consejo: Consejo | None = None, colmena: Colmena | None = None):
        self.c, self.m = cerebro, memoria
        self.consejo = consejo
        self.colmena = colmena
        self.oyente = Oyente(cerebro, memoria)
        self.planificador = Planificador(cerebro, memoria)
        self.critico = Critico(cerebro, memoria, doble_verificacion, colmena)
        self.manos = Manos(memoria)

    def procesar(self, texto: str) -> Turno:
        t = Turno(entrada=texto)
        self.oyente.clasificar(t)

        if t.intencion == "orden":
            self.planificador.planear(t)
            self.critico.revisar(t)
            if t.aprobado:
                self.manos.ejecutar(t)
                self.critico.aprender(t)
                fallos = [r for r in t.resultados if r.get("error")]
                if fallos:
                    t.respuesta = f"Lo intenté pero falló {fallos[0]['herramienta']}. Ya lo anoté para no repetirlo."
                elif not t.respuesta:
                    t.respuesta = "Listo."
            else:
                t.respuesta = f"No lo hice: {t.motivo}"
        elif t.intencion == "pregunta" and self.colmena and self.colmena.viva():
            # la colmena de agentes delibera por el Panal antes de responder
            final = self.colmena.responder(BASE.format(memoria=self.m.contexto()), texto)
            if final:
                t.respuesta = final
            else:
                self._responder_simple(t, texto)
        elif t.intencion == "pregunta" and self.consejo and self.consejo.hay_junta(t.intencion):
            # varias IAs (mismo rol, varios modelos) se corrigen antes de responder
            final = self.consejo.deliberar(BASE.format(memoria=self.m.contexto()), texto)
            if final:
                t.respuesta = final
                self.m.diario(f"Mike (consejo): {final[:80]}")
            else:
                self._responder_simple(t, texto)   # sin quórum: cerebro normal
        else:
            self._responder_simple(t, texto)
        return t

    def _responder_simple(self, t: Turno, texto: str):
        r = self.c.pensar_json(
            BASE.format(memoria=self.m.contexto()) +
            "Responde. Si la respuesta necesita un ejemplo visual largo (código, esquema, tabla), "
            'pon necesita_ejemplo=true. Responde SOLO JSON: {"respuesta":"...","necesita_ejemplo":false}',
            texto)
        t.respuesta = r.get("respuesta") or r.get("crudo", "No supe qué decir.")
        t.necesita_ejemplo = bool(r.get("necesita_ejemplo"))
        self.m.diario(f"Mike: {t.respuesta[:80]}")

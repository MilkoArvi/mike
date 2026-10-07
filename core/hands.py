"""Manos de Mike: las herramientas que ejecutan cosas reales en la PC.
Cada herramienta es una función `nombre(**args) -> str` registrada en HERRAMIENTAS.
El Planificador solo puede usar lo que está aquí; si necesitas algo nuevo, agrega una función.

Todo está pensado para Windows 11. Lo que necesita software externo:
  - RGB      -> OpenRGB abierto con "SDK Server" activado
  - Volumen  -> pycaw (solo Windows)
  - Cámara   -> OpenCV
"""
import os, subprocess, time, shutil
from pathlib import Path

import pyautogui
pyautogui.FAILSAFE = True  # mover el mouse a la esquina superior izquierda aborta

_CFG = {}
_MEM = None
_CEREBRO = None
_COLMENA = None
_CONSEJO = None


def configurar(cfg: dict, memoria, cerebro=None, colmena=None, consejo=None):
    global _CFG, _MEM, _CEREBRO, _COLMENA, _CONSEJO
    _CFG, _MEM, _CEREBRO = cfg, memoria, cerebro
    _COLMENA, _CONSEJO = colmena, consejo


# ---------- Apps y sistema ----------
def abrir_app(nombre: str) -> str:
    alias = _CFG.get("apps", {})
    cmd = alias.get(nombre.lower(), nombre)
    subprocess.Popen(cmd, shell=True)
    return f"Abrí {nombre}"


def escribir(texto: str) -> str:
    pyautogui.write(texto, interval=0.02)
    return f"Escribí: {texto[:40]}"


def tecla(combo: str) -> str:
    """Ej: 'ctrl+s', 'alt+tab', 'win+d'"""
    pyautogui.hotkey(*combo.split("+"))
    return f"Presioné {combo}"


def captura(ruta: str = "vault/Capturas/ultima.png") -> str:
    Path(ruta).parent.mkdir(parents=True, exist_ok=True)
    pyautogui.screenshot(ruta)
    return str(Path(ruta).resolve())


def ejecutar(comando: str) -> str:
    """Comando de shell. El Crítico bloquea rm/del/format/shutdown; ver agents.py"""
    r = subprocess.run(comando, shell=True, capture_output=True, text=True, timeout=60)
    return (r.stdout or r.stderr)[:1500] or "ok"


# ---------- Ventanas: mover / rotar / redimensionar ----------
def ventana_mover(titulo: str, x: int, y: int, ancho: int | None = None, alto: int | None = None) -> str:
    import pygetwindow as gw
    ws = gw.getWindowsWithTitle(titulo)
    if not ws:
        return f"No encontré ventana '{titulo}'"
    w = ws[0]
    w.moveTo(x, y)
    if ancho and alto:
        w.resizeTo(ancho, alto)
    return f"Moví '{w.title}' a ({x},{y})"


def ventana_orbitar(titulo: str, grados: int, radio: int = 300) -> str:
    """Mueve una ventana en círculo alrededor del centro de la pantalla (0-360°).
    Es lo más cercano a 'mover objetos a 360°' que permite Windows: las ventanas no rotan,
    pero sí se pueden colocar en cualquier ángulo alrededor de un punto."""
    import math, pygetwindow as gw
    ws = gw.getWindowsWithTitle(titulo)
    if not ws:
        return f"No encontré ventana '{titulo}'"
    sw, sh = pyautogui.size()
    w = ws[0]
    cx, cy = sw // 2 - w.width // 2, sh // 2 - w.height // 2
    x = int(cx + radio * math.cos(math.radians(grados)))
    y = int(cy + radio * math.sin(math.radians(grados)))
    w.moveTo(x, y)
    return f"'{w.title}' a {grados}°"


def ventanas_listar() -> str:
    import pygetwindow as gw
    return "\n".join(t for t in gw.getAllTitles() if t.strip())[:1500]


# ---------- Audio ----------
def volumen(nivel: int) -> str:
    """0-100"""
    try:
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        dev = AudioUtilities.GetSpeakers()
        iface = dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        vol = cast(iface, POINTER(IAudioEndpointVolume))
        vol.SetMasterVolumeLevelScalar(max(0, min(100, nivel)) / 100, None)
        return f"Volumen al {nivel}%"
    except Exception as e:  # noqa
        return f"No pude cambiar el volumen: {e}"


# ---------- RGB (OpenRGB) ----------
def rgb(color: str, dispositivo: str | None = None) -> str:
    """color: 'rojo' | '#ff0000' | 'apagar'"""
    from openrgb import OpenRGBClient
    from openrgb.utils import RGBColor
    nombres = {"rojo": "#ff0000", "verde": "#00ff00", "azul": "#0044ff", "blanco": "#ffffff",
               "morado": "#8000ff", "naranja": "#ff6a00", "cian": "#00ffff", "apagar": "#000000"}
    hexc = nombres.get(color.lower(), color).lstrip("#")
    rgbc = RGBColor(int(hexc[0:2], 16), int(hexc[2:4], 16), int(hexc[4:6], 16))
    cli = OpenRGBClient(_CFG.get("openrgb_host", "127.0.0.1"), _CFG.get("openrgb_puerto", 6742), "Mike")
    devs = [d for d in cli.devices if not dispositivo or dispositivo.lower() in d.name.lower()]
    for d in devs:
        d.set_color(rgbc)
    return f"RGB → {color} en {len(devs)} dispositivo(s)"


# ---------- Cámara ----------
def foto(ruta: str = "vault/Capturas/camara.png") -> str:
    import cv2
    cap = cv2.VideoCapture(_CFG.get("camara", 0))
    ok, frame = cap.read()
    cap.release()
    if not ok:
        return "La cámara no respondió"
    Path(ruta).parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(ruta, frame)
    return str(Path(ruta).resolve())


# ---------- Cerebro: cambiar modelo / modo de eficiencia por voz ----------
def cerebro_config(modelo: str | None = None, eficiencia: str | None = None) -> str:
    """Cambia en caliente qué Claude usa Mike y cuánto 'piensa'.
    modelo: 'opus' | 'sonnet' | 'haiku' (o id completo)
    eficiencia: 'rapido' | 'equilibrado' | 'profundo'
    """
    if _CEREBRO is None:
        return "El cerebro no está disponible para reconfigurar."
    cambios = []
    if modelo:
        cambios.append(f"modelo → {_CEREBRO.set_modelo(modelo)}")
    if eficiencia:
        m = _CEREBRO.set_eficiencia(eficiencia)
        cambios.append(f"eficiencia → {m}" if m else f"'{eficiencia}' no es un modo válido")
    if _MEM:
        _MEM.diario(f"Cerebro reconfigurado: {_CEREBRO.estado()}")
    return "Listo: " + (", ".join(cambios) if cambios else _CEREBRO.estado())


def modo_junta(activar: bool = True) -> str:
    """Prende o apaga la junta (colmena + consejo). Apagar = 'modo rápido' (responde una sola IA).
    Úsalo con 'modo rápido' / 'sin junta' (activar=false) o 'modo enjambre' / 'con junta' (activar=true).
    """
    act = bool(activar)
    if _COLMENA is not None:
        _COLMENA.activo = act
    if _CONSEJO is not None:
        _CONSEJO.activo = act
    estado = "activada (respuestas más lentas y verificadas)" if act else "apagada (modo rápido, una sola IA)"
    if _MEM:
        _MEM.diario(f"Junta {'ON' if act else 'OFF'} por voz")
    return f"Junta {estado}."


# ---------- Obsidian / notas ----------
def nota(titulo: str, contenido: str) -> str:
    p = Path(_CFG.get("vault", "vault")) / f"{titulo}.md"
    p.write_text(contenido, encoding="utf-8")
    return f"Nota '{titulo}' guardada en el vault"


HERRAMIENTAS = {
    "abrir_app": abrir_app, "escribir": escribir, "tecla": tecla, "captura": captura,
    "ejecutar": ejecutar, "ventana_mover": ventana_mover, "ventana_orbitar": ventana_orbitar,
    "ventanas_listar": ventanas_listar, "volumen": volumen, "rgb": rgb, "foto": foto, "nota": nota,
    "cerebro_config": cerebro_config, "modo_junta": modo_junta,
}

# Descripción que ve el Planificador (corta a propósito: los modelos locales se pierden con listas largas)
DESCRIPCION = """
abrir_app(nombre)                      abre una app (alias en config o nombre/ruta)
escribir(texto)                        teclea texto donde esté el cursor
tecla(combo)                           'ctrl+s', 'alt+tab', 'win+d'
captura()                              screenshot -> ruta del png
ejecutar(comando)                      comando de shell (peligrosos se bloquean)
ventana_mover(titulo,x,y[,ancho,alto]) mueve/redimensiona una ventana por título parcial
ventana_orbitar(titulo,grados[,radio]) coloca la ventana en un ángulo 0-360 alrededor del centro
ventanas_listar()                      títulos de ventanas abiertas
volumen(nivel)                         0-100
rgb(color[,dispositivo])               'rojo','#00ff00','apagar' (OpenRGB)
foto()                                 toma foto con la cámara -> ruta
nota(titulo,contenido)                 crea/reemplaza una nota .md en el vault
cerebro_config(modelo,eficiencia)      cambia el Claude ('opus'/'sonnet'/'haiku') y el modo ('rapido'/'equilibrado'/'profundo')
modo_junta(activar)                     activar=false = modo rápido (una sola IA); activar=true = junta/enjambre
"""

PELIGROSAS = ("rm ", "del ", "rmdir", "format", "shutdown", "reg delete", "diskpart", "Remove-Item")

# Herramientas de configuración: no tocan el sistema, se aprueban al instante (sin junta).
# Así "modo rápido" apaga la junta sin esperar una última deliberación lenta.
RAPIDAS = ("modo_junta", "cerebro_config")

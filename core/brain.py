"""Cerebro: envuelve el modelo de lenguaje. Por defecto Claude (tu cuenta Anthropic).
Puedes seguir usando Ollama poniendo `proveedor: ollama` en config.yaml.

Milko puede cambiar en caliente, por voz, dos cosas (ver hands.cerebro_config):
  - el MODELO       -> 'opus' | 'sonnet' | 'haiku' (o el id completo)
  - el MODO de EFICIENCIA -> 'rapido' | 'equilibrado' | 'profundo'
"""
import json, re
import requests


# Alias amables -> id real del modelo. Di "opus", "sonnet" o "haiku" y Mike lo traduce.
MODELOS = {
    "opus": "claude-opus-4-6",
    "sonnet": "claude-sonnet-4-6",
    "haiku": "claude-haiku-4-5-20251001",
}

# Modos de eficiencia: controlan cuánto "piensa" y cuánto escribe, independiente del modelo.
#   rapido      -> sin razonamiento extendido, respuestas cortas y baratas
#   equilibrado -> por defecto, sin razonamiento extendido
#   profundo    -> activa el pensamiento extendido (más lento y capaz)
EFICIENCIA = {
    "rapido":      {"max_tokens": 1200, "temperatura": 0.3, "pensar_tokens": 0},
    "equilibrado": {"max_tokens": 2000, "temperatura": 0.3, "pensar_tokens": 0},
    "profundo":    {"max_tokens": 6000, "temperatura": 1.0, "pensar_tokens": 3000},
}


class Cerebro:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.prov = cfg.get("proveedor", "anthropic")
        self._anthropic = None
        # estado que Milko puede cambiar en caliente por voz
        self.modelo = self._resolver_modelo(cfg.get("anthropic_modelo", "sonnet"))
        self.eficiencia = cfg.get("eficiencia", "equilibrado")
        if self.eficiencia not in EFICIENCIA:
            self.eficiencia = "equilibrado"
        if self.prov == "anthropic":
            import anthropic
            self._anthropic = anthropic.Anthropic(api_key=cfg["anthropic_api_key"])

    # ---------- control en caliente (lo usa hands.cerebro_config) ----------
    def _resolver_modelo(self, nombre: str) -> str:
        n = (nombre or "").strip().lower()
        return MODELOS.get(n, nombre)  # si no es alias, se asume id completo

    def set_modelo(self, nombre: str) -> str:
        self.modelo = self._resolver_modelo(nombre)
        return self.modelo

    def set_eficiencia(self, modo: str) -> str:
        m = (modo or "").strip().lower()
        if m not in EFICIENCIA:
            return ""
        self.eficiencia = m
        return m

    def estado(self) -> str:
        return f"modelo={self.modelo}, eficiencia={self.eficiencia}"

    # ---------- inferencia ----------
    def pensar(self, sistema: str, usuario: str, json_mode: bool = False) -> str:
        if self.prov == "anthropic":
            return self._pensar_anthropic(sistema, usuario)
        # Ollama
        # num_ctx acotado: sin esto Ollama reserva el contexto máximo del modelo y el KV cache
        # revienta la VRAM (cudaMalloc out of memory). 4096 entra cómodo en una GPU de ~12GB.
        body = {
            "model": self.cfg.get("ollama_modelo", "llama3.1:8b"),
            "system": sistema, "prompt": usuario, "stream": False,
            "options": {"temperature": 0.3, "num_ctx": self.cfg.get("ollama_ctx", 4096)},
        }
        if json_mode:
            body["format"] = "json"
        r = requests.post(f"{self.cfg.get('ollama_url','http://localhost:11434')}/api/generate",
                          json=body, timeout=120)
        r.raise_for_status()
        return r.json()["response"]

    def _pensar_anthropic(self, sistema: str, usuario: str) -> str:
        ef = EFICIENCIA.get(self.eficiencia, EFICIENCIA["equilibrado"])
        kwargs = {
            "model": self.modelo,
            "max_tokens": ef["max_tokens"],
            "temperature": ef["temperatura"],
            "system": sistema,
            "messages": [{"role": "user", "content": usuario}],
        }
        if ef["pensar_tokens"] > 0:  # modo profundo: razonamiento extendido
            kwargs["thinking"] = {"type": "enabled", "budget_tokens": ef["pensar_tokens"]}
            kwargs["temperature"] = 1.0  # requerido cuando se activa el pensamiento
        r = self._anthropic.messages.create(**kwargs)
        # con pensamiento extendido el primer bloque es el "thinking"; toma el texto real
        for bloque in r.content:
            if getattr(bloque, "type", None) == "text":
                return bloque.text
        return ""

    def pensar_json(self, sistema: str, usuario: str) -> dict:
        """Pide JSON y lo parsea de forma tolerante (los modelos a veces agregan texto)."""
        txt = self.pensar(sistema, usuario, json_mode=True)
        m = re.search(r"\{.*\}", txt, re.S)
        try:
            return json.loads(m.group(0) if m else txt)
        except json.JSONDecodeError:
            return {"error": "json_invalido", "crudo": txt}

    def disponible(self) -> bool:
        if self.prov == "anthropic":
            return bool(self._anthropic)
        try:
            return requests.get(self.cfg.get("ollama_url", "http://localhost:11434"), timeout=2).ok
        except requests.RequestException:
            return False

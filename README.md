# Mike — tu Jarvis local (v0.1)

Asistente que vive en tu PC: escucha, ve, habla y ejecuta. Memoria en Obsidian, 4 agentes,
UI de agujero negro abajo a la izquierda. Todo gratis (ElevenLabs solo en plan free).

## Lo que ya hace esta versión
| Pediste | Cómo está resuelto |
|---|---|
| Voz para hablarle | mic siempre abierto, palabra clave **"Mike"**, transcripción local (faster-whisper) |
| Aplauso / chasquido | detector de transitorios → muestra u oculta la UI |
| Gestos | cámara + MediaPipe: mano abierta = mostrar, puño = ocultar, pinza = girar 360° |
| Que hable | ElevenLabs (tu key) → si se acaba la cuota, edge-tts gratis automáticamente |
| Memoria | vault de Obsidian en `vault/` (ábrelo en Obsidian y verás todo lo que piensa) |
| 4 agentes con memoria compartida | Oyente → Planificador → Crítico → Manos, todos leen/escriben el mismo vault |
| Doble verificación + aprender de errores | el Crítico revisa cada plan antes; tras un fallo escribe en `Lecciones.md` y puede reescribir `Mike.md` |
| Sugerencias | `Sugerencias.md` + `Critico.sugerir()` |
| Manos | abrir apps, teclear, atajos, mover/orbitar ventanas, volumen, RGB (OpenRGB), cámara, screenshot, notas |
| UI agujero negro | Electron transparente, abajo-izquierda; se expande a pantalla completa para ejemplos y vuelve solo |
| Arranque con Windows | `install\instalar.ps1` registra una tarea al iniciar sesión |

## Instalación (Windows 11)
Necesitas tener instalado: **Python 3.11+**, **Node 20+**, **Ollama** (https://ollama.com) y opcionalmente **OpenRGB** y **Obsidian**.

```powershell
ollama pull llama3.1:8b          # cerebro gratis (una vez)
.\install\instalar.ps1           # instala todo y registra el arranque automático
.\install\mike.bat               # arrancar ahora sin reiniciar
```
Luego abre `vault/` como vault en Obsidian.

## Lo que tienes que poner tú (`config.yaml`)
- `voz.elevenlabs_api_key` y `voz.elevenlabs_voice_id` — si no los pones, usa edge-tts y ya.
- `cerebro.anthropic_api_key` — solo si quieres Claude en vez de Ollama (`proveedor: anthropic`).
- `manos.apps` — alias de tus programas.
- `oidos.aplauso_umbral` — si el aplauso no se detecta, bájalo (0.25); si se activa solo, súbelo (0.5).

## Cómo usarlo
- Di **"Mike, abre Spotify"**, **"Mike, pon las luces en morado"**, **"Mike, ¿qué es un closure?"**
- Aplaude o chasquea → aparece/desaparece.
- Clic en el agujero negro → campo para escribir.
- Arrastra el orbe con el mouse (o haz pinza con la mano y gira) → el disco rota 0-360°.
- **"Mike, pon la ventana de Chrome a 90 grados"** → `ventana_orbitar`.

## Límites honestos de v0.1
- No pude probar hardware desde aquí (mic, cámara, RGB). El código sigue las APIs oficiales, pero espera ajustar umbrales.
- Un modelo local de 8B se equivoca más que Claude al armar planes. El Crítico lo compensa en parte; si quieres precisión, pon la key de Anthropic (de pago).
- "Mover objetos a 360°": Windows no rota ventanas. Está resuelto como órbita alrededor del centro + rotación del propio orbe. Si querías otra cosa (p. ej. imágenes en la pantalla), dime.
- La palabra clave se detecta transcribiendo ventanas de 2 s; en una PC sin GPU eso consume CPU. Si molesta, cambia `stt_modelo: tiny`.

## Siguientes pasos sugeridos
1. Probar `python core/main.py` a solas y ver que `vault/Diario/` se llene.
2. Probar `npm start` dentro de `ui/` y ver el orbe.
3. Calibrar aplauso.
4. Agregar herramientas a `hands.py` (una función + una línea en `DESCRIPCION`).

---
name: mike-asistente-pc
description: Especificación y reglas de trabajo de "Mike", el asistente local tipo Jarvis de Milko (Windows 11, Python + Electron, memoria en Obsidian, 4 agentes, voz con ElevenLabs/edge-tts, aplauso/chasquido/gestos, UI de agujero negro). Úsala siempre que Milko mencione a Mike, Jarvis, su asistente de PC, el vault de Mike, los agentes Oyente/Planificador/Crítico/Manos, o pida agregar una capacidad, herramienta, gesto o integración al asistente — aunque no diga "Mike" por su nombre.
---

# Mike — asistente local de Milko

## Lo que Milko pidió, reducido a lo esencial
1. **Un asistente en su PC** que oye (mic), ve (cámara), habla (altavoces) y toca cosas (apps, ventanas, RGB, volumen).
2. **Gratis**: nada de suscripciones. ElevenLabs solo en plan free; todo lo demás local.
3. **Memoria + cerebro + manos**: recuerda entre sesiones, razona, ejecuta.
4. **4 agentes que comparten memoria** en un vault de Obsidian, sin que él abra código.
5. **Arranca con Windows**, invisible hasta que lo llames.
6. **UI**: un agujero negro abajo a la izquierda. Aparece/desaparece con aplauso, chasquido, voz o gesto. Muestra texto, imágenes o solo audio. Si va a dar un ejemplo, crece a pantalla completa y luego vuelve a su esquina y se oculta.
7. **Mover cosas a 360°** con la mano o el mouse.
8. **Aprende de cada error y se revisa dos veces** antes de actuar; sugiere mejoras.
9. División de trabajo: Claude hace código e interfaz; Milko conecta las APIs. Si Milko se traba, Claude lo dice claro.

## Mejoras sobre la petición original (por qué el diseño es así)
- **"Conciencia" → bucle Planificar → Criticar → Ejecutar → Aprender.** No existe conciencia real; lo que sí funciona es un segundo agente (Crítico) que revisa cada plan contra las lecciones pasadas y escribe una lección nueva cuando algo falla. Eso es medible y se puede leer en Obsidian.
- **Cerebro gratis = Ollama local.** Un LLM en la nube gratis y sin límites no existe. Ollama con `llama3.1:8b` o `qwen2.5:7b` corre sin costo; Anthropic queda como opción de pago con un cambio en `config.yaml`.
- **Voz con respaldo automático.** ElevenLabs free da ~10k caracteres/mes (unas 150 frases). Cuando se agota, Mike cae solo a edge-tts (gratis, ilimitado, voz `es-MX`). Milko no tiene que hacer nada.
- **"360°" tiene dos significados y se implementan los dos:** (a) girar el disco del agujero negro con la pinza de la mano o arrastrando el mouse; (b) `ventana_orbitar(titulo, grados)` coloca cualquier ventana en un ángulo alrededor del centro de la pantalla. Windows no rota ventanas; esto es lo más cercano.
- **Aplauso y chasquido son el mismo detector** (pico corto con factor de cresta alto). Se calibra con un número en config, no con código.
- **Sin abrir código:** un `.bat` lanzado por el Programador de tareas al iniciar sesión. Un solo script de instalación.

## Arquitectura (para no repetirla en cada conversación)
```
core/main.py      orquesta todo (asyncio)
core/bus.py       WebSocket núcleo <-> UI        ws://127.0.0.1:8765
core/memory.py    vault Obsidian: Mike.md, Lecciones.md, Sugerencias.md, Errores/, Diario/
core/brain.py     Ollama (default) | Anthropic
core/agents.py    Oyente, Planificador, Crítico, Manos + Orquestador
core/hands.py     HERRAMIENTAS = {abrir_app, escribir, tecla, captura, ejecutar, ventana_*, volumen, rgb, foto, nota}
core/ears.py      mic: palmada/chasquido + palabra clave "mike" + faster-whisper
core/voice.py     ElevenLabs -> edge-tts -> pygame
core/gestures.py  MediaPipe: mano_abierta / puño / pinza+giro
ui/main.js        Electron: ventana transparente, siempre encima, abajo-izquierda, expandir/contraer
ui/index.html     agujero negro en canvas; estados idle/escuchando/pensando/hablando
install/          instalar.ps1 crea venv, npm install, mike.bat y la tarea "Mike" al iniciar sesión
```

## Cómo trabajar con Milko en este proyecto
- Responde en español. Código en Python 3.11+ / JS moderno, comentarios en español.
- **Para agregar una capacidad**: escribe una función en `hands.py`, regístrala en `HERRAMIENTAS` y agrega una línea a `DESCRIPCION`. Nada más; el Planificador la descubre solo.
- **Para un gesto nuevo**: `gestures.py` emite un string; `main.py::on_gesto` lo enruta.
- **Para un estado visual nuevo**: agrega el par de colores en `COLORES` de `index.html`.
- Todo cambio peligroso (borrar, apagar, dinero) se bloquea en `Critico.revisar` por regla dura, no por el modelo.
- Cuando Milko se trabe: primero confirma qué línea de `config.yaml` sigue en `TU_...`, luego qué servicio externo no está corriendo (Ollama, OpenRGB SDK, mic/cámara con permisos). El 90 % de los fallos están ahí.
- No prometer lo que no corre: si algo no se puede probar aquí (hardware), decirlo y dar el comando exacto para que Milko lo pruebe.

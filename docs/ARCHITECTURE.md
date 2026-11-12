# Arquitectura del flujo

El producto usa un trabajador Python y, para la revisión interactiva, un servidor HTTP local ligado a `127.0.0.1`. Drive para escritorio sincroniza una carpeta; no hay servidor remoto, base de datos ni credenciales de Google dentro del trabajador.

```text
Teléfono → Drive → carpeta local
  → inputs.py: enlace o video estable, validación e ID
  → worker.py: exclusión mutua, estado, intentos y reintentos
  → visual.py + Watch Skill: video, frames, OCR y subtítulos
  → extraer_transcripcion.py: FFmpeg/Whisper si no hay subtítulos
  → core.py + Codex: mapa de enseñanzas, skill y revisión de fidelidad
  → core.py + Git/GitHub CLI: rama y draft PR (solo si es apto)
  → vault.py/vault_server.py: bóveda local y controles de prueba/activación
  → lifecycle.py: prueba temporal, evaluación y promoción explícita
```

`__main__.py` define los comandos `doctor`, `once`, `watch`, `status`, `vault`, `retry`, `evaluate` y `activate`. `doctor.py` revisa el equipo y las integraciones. `config.local.json` contiene la ruta y las preferencias locales; está ignorado por Git.

## Estado y recuperación

- `processing`: comenzó una pasada. Si el proceso se interrumpe, la siguiente pasada puede repetirla; la rama y PR se comprueban antes de crear otra.
- `needs_review`: existe un método posible, pero falta evidencia para publicar. El trabajador guarda la transcripción y el análisis para corrección humana.
- `not_skillable`: no hay un método aprovechable con la evidencia disponible.
- `published`: se verificó el PR y su URL quedó en el estado local. Los PR nuevos se crean como borradores.
- `failed`: falló una etapa técnica; `retry ID` o `once --retry-failed` permiten reintentar.

El estado vive en `.local-state/results.json`; una vez completada cada etapa, el ID conserva `.local-state/jobs/ID/transcript.txt`, `analysis.md`, `result.json` y copias de los intentos en `attempts/`. Los cambios se escriben de forma atómica. Un bloqueo de archivo impide que una ejecución manual y la tarea programada procesen a la vez; la pasada programada se omite si hay un reintento en curso. Los archivos recientes esperan 10 segundos si son `.txt` y 30 segundos si son videos para reducir lecturas durante la sincronización de Drive.

`visual.py` conserva `.local-state/jobs/ID/visual.json` y los frames de Watch Skill en `watch/`; los reintentos reutilizan esas imágenes. Se fijan los primeros segundos y Watch Skill selecciona escenas del resto del video con un máximo configurable. Si hay subtítulos, se reutilizan; si no, el extractor existente transcribe el video adquirido. Los videos sin audio pueden generar una skill basada en imágenes. El modelo inicial de audio es `whisper_model`. `review_whisper_model` es opcional y solo se usa cuando el análisis clasifica el problema como transcripción. Si el segundo modelo contradice un `needs_review` con `not_skillable`, el caso sigue pendiente en vez de descartarse. Un usuario puede corregir `transcript.txt` y usar `retry ID --use-transcript` sin volver a descargar el Reel. Los intentos antiguos quedan conservados.

## Límites de confianza

La generación usa tres llamadas: mapa con tesis, formato, enseñanzas y evidencia; skill redactada desde ese mapa; revisión independiente que compara cobertura, distorsiones y adaptaciones. Ante un fallo de fidelidad, se permite una corrección y una nueva revisión. Si persiste, el resultado queda en `needs_review` sin actualizar el PR. `result.json` conserva el mapa y el veredicto; `history/` conserva versiones previas de una regeneración.

`core.generate(..., task_intent=...)` permite orientar una generación manual hacia un objetivo explícito, como extraer técnicas de diseño de un video que muestra una interfaz de otro dominio. La intención viaja al mapa y a la redacción; no sustituye la evidencia visual. La entrada automática de enlaces `.txt` sigue aceptando Reels de Instagram; para un post de Threads, se debe aportar un archivo de video local a la carpeta o resolver su medio por separado antes de analizarlo con Watch Skill.

Un enlace o video, sus subtítulos, OCR, imágenes y transcripción son material externo. El generador recibe instrucciones para no obedecer órdenes dentro de ese material. La validación comprueba la estructura de la skill y que cada cita de audio o visual corresponda a una marca de tiempo realmente entregada. Esto no demuestra que el OCR sea correcto ni que una recomendación del creador sea válida: el PR queda como borrador para revisión humana.

Si el usuario subió un archivo, el video original permanece en Drive. Las transcripciones, frames, OCR y análisis completos quedan en `.local-state/` del computador, que Git ignora; la transcripción, el OCR y los frames seleccionados se envían a Codex para analizarlos. El repositorio público recibe únicamente la skill y un resumen de fuente con evidencias, nunca el video, los frames ni la transcripción completa. Para videos locales, la fuente pública muestra su SHA-256 sin revelar la ruta del archivo. Watch Skill se usa mediante su API Python; no requiere DeepWatch, Node, MCP ni una cuenta adicional.

La elección de un solo trabajador y archivos JSON evita exigir Docker o un servicio externo. A cambio, el computador debe estar encendido y Drive sincronizado. La comprobación de PR existente evita duplicados normales; si GitHub tiene una rama sin PR, se detiene para revisión manual en vez de sobrescribirla.

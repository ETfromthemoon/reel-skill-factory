# Arquitectura del flujo

El producto usa un solo proceso Python en el computador del usuario. Drive para escritorio sincroniza una carpeta; no hay servidor, base de datos ni credenciales de Google dentro del trabajador.

```text
Teléfono → Drive → carpeta local
  → inputs.py: enlace o video estable, validación e ID
  → worker.py: exclusión mutua, estado, intentos y reintentos
  → core.py + extraer_transcripcion.py: yt-dlp/FFmpeg/Whisper
  → core.py + Codex: análisis estructurado y validación
  → core.py + Git/GitHub CLI: rama y draft PR (solo si es apto)
```

`__main__.py` solo define los comandos `doctor`, `once`, `watch`, `status` y `retry`. `doctor.py` revisa el equipo y las integraciones. `config.local.json` contiene la ruta y las preferencias locales; está ignorado por Git.

## Estado y recuperación

- `processing`: comenzó una pasada. Si el proceso se interrumpe, la siguiente pasada puede repetirla; la rama y PR se comprueban antes de crear otra.
- `needs_review`: existe un método posible, pero falta evidencia para publicar. El trabajador guarda la transcripción y el análisis para corrección humana.
- `not_skillable`: no hay un método aprovechable con la evidencia disponible.
- `published`: se verificó el PR y su URL quedó en el estado local. Los PR nuevos se crean como borradores.
- `failed`: falló una etapa técnica; `retry ID` o `once --retry-failed` permiten reintentar.

El estado vive en `.local-state/results.json`; una vez completada cada etapa, el ID conserva `.local-state/jobs/ID/transcript.txt`, `analysis.md`, `result.json` y copias de los intentos en `attempts/`. Los cambios se escriben de forma atómica. Un bloqueo de archivo impide que una ejecución manual y la tarea programada procesen a la vez; la pasada programada se omite si hay un reintento en curso. Los archivos recientes esperan 10 segundos si son `.txt` y 30 segundos si son videos para reducir lecturas durante la sincronización de Drive.

El modelo inicial es `whisper_model`. `review_whisper_model` es opcional y solo se usa cuando el análisis clasifica el problema como transcripción. Si el segundo modelo contradice un `needs_review` con `not_skillable`, el caso sigue pendiente en vez de descartarse. Un usuario puede corregir `transcript.txt` y usar `retry ID --use-transcript` sin volver a descargar el Reel. Los intentos antiguos quedan conservados.

## Límites de confianza

Un enlace o video, sus subtítulos y su transcripción son material externo. El generador recibe instrucciones para no obedecer órdenes dentro de ese material. La validación comprueba la estructura de la skill y que sus marcas de tiempo estén en la transcripción. Esto no demuestra que la transcripción sea fiel ni que una recomendación del creador sea correcta: el PR queda como borrador para revisión humana.

Si el usuario subió un archivo, el video original permanece en Drive. Las transcripciones y análisis completos quedan en `.local-state/` del computador, que Git ignora; la transcripción se envía a Codex para analizarla. El repositorio público recibe únicamente la skill y un resumen de fuente con evidencias, nunca el video ni la transcripción completa. Para videos locales, la fuente pública muestra su SHA-256 sin revelar la ruta del archivo.

La elección de un solo trabajador y archivos JSON evita exigir Docker o un servicio externo. A cambio, el computador debe estar encendido y Drive sincronizado. La comprobación de PR existente evita duplicados normales; si GitHub tiene una rama sin PR, se detiene para revisión manual en vez de sobrescribirla.

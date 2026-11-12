# Arquitectura del workflow

El repositorio distribuye el programa, no los resultados personales. El trabajador Python lee una carpeta sincronizada con Drive y guarda los borradores en una biblioteca privada fuera del checkout. La bóveda HTTP solo escucha en `127.0.0.1:8766`. No hay base de datos, servidor remoto ni requisito de GitHub.

```text
Teléfono → Drive → carpeta local
  → inputs.py: enlace de Reel o video estable, validación e ID
  → worker.py: exclusión mutua, estado, intentos y reintentos
  → visual.py + Watch Skill: video, frames, OCR y subtítulos
  → extraer_transcripcion.py: FFmpeg/Whisper si no hay subtítulos
  → core.py + Codex: mapa, skill y revisión de fidelidad
  → library.py: borrador privado fuera del repositorio
  → vault.py/vault_server.py: revisión local
  → lifecycle.py: prueba temporal, aprobación y copia a agentes locales
```

`config.local.json` contiene la carpeta de entrada y, opcionalmente, `library_dir`. Está ignorado por Git. La biblioteca predeterminada es `~/.reel-skill-factory/library`; `load_config` rechaza bibliotecas dentro del checkout o de la entrada sincronizada. `drafts/ID` conserva `SKILL.md`, `source.md` y metadatos; `approved/NOMBRE` contiene solo skills aceptadas. `sync-skills` copia estas últimas a las carpetas de agentes y protege ediciones locales con hashes.

## Estados y recuperación

- `processing`: comenzó una pasada. Si se interrumpe, el siguiente intento puede repetirla.
- `needs_review`: hay una posible skill, pero falta evidencia o fidelidad. Se conservan los artefactos locales.
- `not_skillable`: la evidencia no permite extraer un método reutilizable.
- `draft`: el borrador privado está listo para revisar y probar.
- `failed`: falló una etapa técnica; `retry ID` o `once --retry-failed` permiten reintentar.

El estado, la transcripción, los frames, el mapa y los informes de prueba viven en `.local-state/` del checkout, ignorado por Git. La biblioteca privada vive fuera del checkout. Las escrituras de archivos nuevos usan reemplazo atómico; un bloqueo evita que dos pasadas del trabajador procesen el mismo video a la vez. Los archivos recién sincronizados esperan antes de leerse.

La generación separa mapa de enseñanzas, redacción y revisión de fidelidad. Ante una pérdida sustancial, permite una corrección y una nueva revisión; si persiste, deja el caso en `needs_review`. `retry ID --refresh-draft` reutiliza la evidencia local, conserva la versión previa en `history/` y solo reemplaza el borrador privado si la nueva generación es apta.

## Límites de confianza

Video, subtítulos, OCR y transcripción son material externo. Los prompts indican que no deben obedecerse instrucciones dentro de ese material. Las citas de evidencia se validan contra marcas de tiempo entregadas, pero esto no certifica que el OCR o las recomendaciones del creador sean correctas. El usuario revisa el borrador antes de activarlo.

La prueba usa un espacio temporal y el modo `workspace-write` de Codex; el evaluador posterior es de solo lectura. El sandbox limita las escrituras, pero no equivale a una máquina virtual aislada de lecturas. Cada informe se ata al SHA-256 del `SKILL.md` local; si el borrador cambia, requiere otra prueba. La activación exige una prueba terminada para esa versión y una confirmación humana de los vacíos. Copia a la biblioteca aprobada y después a las carpetas locales de agentes; no realiza llamadas a GitHub.

El computador debe estar encendido y Drive sincronizado. Los videos y enlaces pueden fallar por acceso, formato o permisos del origen. El repositorio compartido no contiene skills, fuentes personales ni el informe histórico de pruebas de un usuario.

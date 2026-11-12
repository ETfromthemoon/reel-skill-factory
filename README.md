# Reel Skill Factory

![Del video al borrador privado de skill](assets/workflow.png)

Workflow local para convertir videos en skills de Codex. Este repositorio comparte **el programa**, no las skills de quien lo usa. Cada persona configura su propia carpeta de entrada y conserva sus borradores y aprobaciones en una biblioteca privada fuera del checkout.

```text
Teléfono → video o enlace de Reel en Drive → carpeta sincronizada
  → Watch Skill: frames, OCR y subtítulos → Whisper si hace falta audio
  → Codex: mapa de enseñanzas → skill → control de fidelidad
  → biblioteca privada: borrador → prueba → aprobación → instalación local
```

Un video sin voz puede generar una skill visual. Para un post de Threads, guarda el archivo de video y súbelo a la carpeta: el trabajador automático de enlaces `.txt` acepta Reels de Instagram, no enlaces de Threads. Los Reels privados o retirados pueden fallar.

## Instalar

1. Descarga el ZIP o clona este repositorio. En Windows ejecuta `./setup.ps1`; en macOS/Linux, `sh setup.sh`. El instalador prepara Python, Codex CLI, FFmpeg, yt-dlp, Whisper y Watch Skill con OCR. En Windows/macOS también puede instalar Drive para escritorio. Usa `-SkipModelDownload` o `--skip-model-download` para posponer la descarga de Whisper, y `-SkipDriveDesktop` o `--skip-drive-desktop` si ya sincronizas la carpeta por otro medio.
2. Inicia sesión con `codex login`. Crea una carpeta en Drive y sincronízala con el computador. Copia `config.example.json` a `config.local.json` y cambia `inbox_dir` por la ruta local de esa carpeta. `library_dir` es opcional; por defecto usa `~/.reel-skill-factory/library`. Debe estar fuera del repositorio y de la carpeta de entrada. La configuración local está ignorada por Git.
3. Ejecuta `.venv\Scripts\python.exe -m reel_skill_factory doctor` en Windows, o `.venv/bin/python -m reel_skill_factory doctor` en macOS/Linux. El diagnóstico comprueba el equipo, la carpeta, el procesamiento visual, audio y Codex. Una subida real desde el teléfono sigue siendo necesaria para verificar la entrada móvil.
4. En Windows, ejecuta `./scripts/install-windows-task.ps1`. Instala una tarea oculta que procesa la carpeta cada cinco minutos y abre la bóveda local al iniciar sesión. En macOS/Linux, deja corriendo `.venv/bin/python -m reel_skill_factory watch` y `.venv/bin/python -m reel_skill_factory vault --serve`, o configúralos al inicio de sesión.

El instalador requiere internet y puede pedir permisos para instalar aplicaciones. En Linux no hay cliente oficial de Drive para escritorio: usa una carpeta local o una sincronización que configures tú. No necesitas cuenta ni repositorio de GitHub para generar skills.

## Enviar videos

Desde iPhone o Android sube un `.mp4`, `.mov`, `.m4v`, `.webm` o `.mkv` de hasta 500 MB a la carpeta sincronizada. También puedes guardar allí un `.txt` que contenga un único enlace público de Reel de Instagram. Si Instagram solo comparte el enlace, necesitas una acción móvil que cree ese archivo `.txt`; compartir un enlace a la carpeta no descarga el video.

Opcionalmente, [Code.gs](google_apps_script/Code.gs) puede recibir un correo enviado desde la hoja Compartir del teléfono y crear el `.txt` en Drive. Cada usuario autoriza y configura su propia cuenta de Google. La entrada por correo no es requisito del trabajador local.

El computador debe estar encendido y la carpeta sincronizada. El trabajador espera que un archivo deje de cambiar antes de procesarlo. Los errores no se reintentan solos; usa `once --retry-failed` o `retry ID`.

## Bóveda, prueba y activación

En Windows abre **Bóveda de Skills** desde el escritorio, o visita `http://127.0.0.1:8766/`. La bóveda solo escucha en el propio computador. Muestra los borradores, la tesis extraída del video, las evidencias y los vacíos. Cada resultado apto queda en:

```text
~/.reel-skill-factory/library/drafts/ID/SKILL.md
~/.reel-skill-factory/library/drafts/ID/source.md
```

Los frames, transcripciones e informes de trabajo permanecen en `.local-state/jobs/ID/` del checkout y Git los ignora. El video original permanece en la carpeta de entrada. Ni los borradores ni las skills aprobadas se envían a este repositorio.

Para probar un borrador, describe un caso concreto y el resultado esperado en la bóveda y pulsa **Probar en entorno aislado**. Codex intenta resolverlo en una carpeta temporal; otro evaluador compara la respuesta y los archivos con tu criterio. El informe queda en `.local-state/jobs/ID/evaluations/`. Revisa el resultado tú mismo: una prueba de un caso no demuestra todos los usos. El sandbox limita las escrituras, pero no es una máquina virtual aislada de las lecturas del equipo. En Windows, si Codex no puede escribir el archivo de prueba, el evaluador debe dejarlo en `review`.

Cuando estés conforme, marca que revisaste los vacíos y pulsa **Aprobar e instalar en mis agentes**. La skill pasa a `~/.reel-skill-factory/library/approved/NOMBRE/SKILL.md` y se copia a `~/.codex/skills` y `~/.agents/skills`. No hay publicación remota. Para otro agente, indica su carpeta de skills con `activate ID --target RUTA` o `sync-skills --target RUTA`. La sincronización no reemplaza ediciones locales ajenas.

Comandos útiles (usa el Python de `.venv`):

```text
python -m reel_skill_factory status
python -m reel_skill_factory retry ID --refresh-draft
python -m reel_skill_factory evaluate ID --scenario "Caso concreto..." --expected "Resultado esperado..."
python -m reel_skill_factory activate ID
python -m reel_skill_factory sync-skills
```

`retry ID --use-transcript` reutiliza una transcripción corregida en `.local-state/jobs/ID/transcript.txt`; conserva las marcas `[mm:ss]`. `retry ID --refresh-draft` reutiliza la evidencia guardada, deja el resultado anterior en `history/` y actualiza solo el borrador privado si la nueva revisión de fidelidad es apta. Si el evaluador de la prueba marca `review`, `activate ID` requiere `--accept-gaps` después de comprobar esos vacíos por tu cuenta.

## Privacidad y límites

Codex recibe la transcripción, OCR y frames seleccionados para analizar el video. El repositorio compartido contiene únicamente código, prompts genéricos, documentación y pruebas. La biblioteca privada se guarda fuera de él; `.local-state/` y `config.local.json` están ignorados. No subas manualmente videos, transcripciones ni bibliotecas personales a un repositorio público. La licencia MIT cubre el código original, no concede derechos sobre videos de terceros.

## Pruebas

```text
python -m unittest discover -s tests -v
```

La arquitectura y los estados están en [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

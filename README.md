# Reel Skill Factory

![Del video al borrador privado de skill](assets/workflow.png)

Workflow local para convertir videos en skills de Codex. Este repositorio comparte **el programa**, no las skills de quien lo usa. Cada persona configura su propia carpeta de entrada y conserva sus borradores y aprobaciones en una biblioteca privada fuera del checkout.

```text
Teléfono → video o enlace de Reel en Drive → carpeta sincronizada
  → Watch Skill: frames, OCR y subtítulos → Whisper si hace falta audio
  → Codex: mapa de enseñanzas → skill → control de fidelidad
  → biblioteca privada: borrador + demostración automática → corrección o aprobación → instalación local
```

Un video sin voz puede generar una skill visual. Para un post de Threads, guarda el archivo de video y súbelo a la carpeta: el trabajador automático de enlaces `.txt` acepta Reels de Instagram, no enlaces de Threads. Los Reels privados o retirados pueden fallar.

## Instalar

1. Descarga el ZIP del repositorio y descomprímelo en una carpeta permanente. Instala Google Drive para escritorio si aún no lo tienes; inicia sesión y crea una carpeta para recibir videos. Espera a que la carpeta aparezca también en el computador.
2. En Windows abre PowerShell en la carpeta descomprimida y ejecuta `./setup.ps1`. El instalador prepara Python, Codex CLI, FFmpeg, ffprobe, yt-dlp, Whisper, Watch Skill y OCR; te pide la **ruta local** de la carpeta, ayuda a iniciar sesión en Codex, ejecuta el diagnóstico y activa la tarea de fondo y la bóveda. También puedes usar `./setup.ps1 -InboxDir "G:\Mi unidad\VIDEO TO SKILL"` si ya conoces la ruta. No necesitas editar JSON ni tener GitHub.
3. En macOS/Linux ejecuta `sh setup.sh` y responde la misma pregunta de la carpeta. El instalador verifica dependencias y Codex. Allí el trabajador y la bóveda aún se inician con los dos comandos que imprime al finalizar; **el inicio persistente automático solo está preparado en Windows**.
4. Sube un video propio desde el teléfono a la carpeta de Drive. Abre **Bóveda de Skills** en el escritorio de Windows o `http://127.0.0.1:8766/`. Pulsa «Actualizar progreso» hasta ver el borrador privado y su demostración automática.

Si PowerShell impide ejecutar scripts, consulta la [guía de instalación paso a paso](docs/INSTALL.md). El instalador requiere internet y puede pedir permisos para instalar aplicaciones. `-SkipModelDownload` o `--skip-model-download` pospone el modelo de Whisper; `-SkipDriveDesktop` o `--skip-drive-desktop` omite Drive si ya tienes otra sincronización. `-NoAutostart` omite la tarea de fondo en Windows. Puedes repetir el instalador: conserva tu configuración existente y no sustituye una carpeta distinta en silencio.

En Linux no hay cliente oficial de Drive para escritorio: usa una carpeta local o una sincronización que configures tú. La biblioteca privada predeterminada es `~/.reel-skill-factory/library`, fuera del checkout y de Drive. Si necesitas cambiarla, edita `config.local.json` después de instalar.

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

Cada borrador nuevo llega con un caso de ejemplo, criterios, una muestra aplicada y una revisión independiente en `.local-state/jobs/ID/auto-demo.json`. Para skills de interfaz, la bóveda muestra una vista HTML estática con scripts y recursos externos bloqueados. **Es una demostración generada, no una ejecución comprobada en tu proyecto.** Compara el ejemplo con el video y la skill. Si no corresponde, escribe qué falta en «Pedir corrección»: el trabajador reutiliza el video y la transcripción, regenera el borrador y prepara otra muestra. Si estás conforme, pulsa **Aprobar e instalar**. La muestra nunca se publica en este repositorio.

La «Prueba adicional opcional» permite que tú plantees otro caso; su informe queda en `.local-state/jobs/ID/evaluations/`. El sandbox limita escrituras, pero no es una máquina virtual aislada de las lecturas del equipo. En este entorno Windows Codex puede iniciar en solo lectura incluso al solicitar `workspace-write`; en ese caso la prueba indica el vacío y no afirma haber validado archivos ni el navegador.

Cuando estés conforme, pulsa **Aprobar e instalar**. Si la revisión señala vacíos, el botón lo indica expresamente. La skill pasa a `~/.reel-skill-factory/library/approved/NOMBRE/SKILL.md` y se copia a `~/.codex/skills` y `~/.agents/skills`. No hay publicación remota. Para otro agente, indica su carpeta de skills con `activate ID --target RUTA` o `sync-skills --target RUTA`. La sincronización no reemplaza ediciones locales ajenas.

Comandos útiles (usa el Python de `.venv`):

```text
python -m reel_skill_factory status
python -m reel_skill_factory retry ID --refresh-draft
python -m reel_skill_factory retry ID --refresh-draft --feedback "Qué falta o qué corregir"
python -m reel_skill_factory demo ID
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

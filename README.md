# Reel Skill Factory

![Un video pasa por una carpeta personal y se convierte en un borrador de skill revisable.](assets/workflow.png)

Convierte videos y enlaces de Reels de Instagram en borradores de skills revisables en GitHub. Cada persona configura su propia carpeta de Drive como bandeja de entrada. [Watch Skill](https://github.com/oxbshw/watch-skill) descarga el video, selecciona frames de toda su duración y lee texto en pantalla mediante OCR. Los subtítulos o Whisper aportan el audio. Codex combina ambas evidencias y solo propone una skill si encuentra un método reutilizable. Un video sin voz también puede servir si el método está explicado visualmente.

```text
Video del teléfono (.mp4/.mov) o enlace de Reel en un .txt → carpeta de Drive
  → Drive para escritorio → trabajador Python local
  → Watch Skill: frames + OCR + subtítulos → Whisper si falta transcripción
  → Codex CLI: mapa de enseñanzas → skill → revisión de fidelidad
  → borrador de PR en GitHub si supera la revisión
```

El correo y Apps Script son una **opción de entrada**, no requisitos: sirven para convertir el enlace compartido desde el teléfono en un `.txt` cuando no hay una acción móvil que lo guarde directamente en Drive.

El equipo debe estar encendido, conectado y con el trabajador activo (`watch` o tarea programada en Windows). Un Reel privado, retirado o inaccesible puede fallar. Las skills se proponen en **draft PRs**: nunca se fusionan ni instalan solas. El repositorio público recibe la skill, una fuente y un análisis breve; la transcripción, los frames y el OCR completos permanecen en `.local-state/jobs/`. Codex recibe la transcripción, el OCR y las imágenes seleccionadas para analizarlas, pero los archivos originales no se publican en el PR. Cada usuario autentica sus propias cuentas de Google, Codex y GitHub. El análisis de imágenes puede aumentar el uso de Codex.

## Requisitos

- Windows, macOS o Linux. Recomendados 4 GB de RAM y 3 GB libres; el doctor informa la capacidad real.
- Windows: [WinGet](https://learn.microsoft.com/windows/package-manager/winget/). macOS: [Homebrew](https://brew.sh/). Linux: `apt`, `dnf` o `pacman`. El instalador prepara Python 3.11, Git, [GitHub CLI](https://cli.github.com/) y [Codex CLI](https://github.com/openai/codex) cuando faltan; en Windows/macOS también instala [Google Drive para escritorio](https://support.google.com/drive/answer/10838124). En Linux usa el instalador oficial de Codex.
- Cuenta Google para Drive y acceso de escritura al repositorio GitHub de destino. Gmail y Apps Script solo son necesarios si eliges la entrada por correo.
- Un Reel que `yt-dlp` pueda leer. No se usan cookies de navegador automáticamente.

## Instalar y comprobar viabilidad

1. Descarga el ZIP de este repositorio o clónalo si ya tienes Git, y abre una terminal en su carpeta. Ejecuta `./setup.ps1` en PowerShell o `sh setup.sh` en macOS/Linux. Si Windows bloquea la ejecución de scripts, usa `powershell -ExecutionPolicy Bypass -File .\setup.ps1` para esta ejecución. El script comprueba la versión de Python y el espacio libre antes de instalar. Prepara las herramientas externas que falten, crea `.venv`, instala `yt-dlp`, `openai-whisper`, `watch-skill[perceive,ocr]`, FFmpeg y `ffprobe`, y descarga el modelo Whisper `base` para el primer uso. Si ya existe `config.local.json`, descarga el modelo elegido allí. Watch Skill usa OCR local; su modelo predeterminado viene con la dependencia. No instala paquetes de nuevo cuando ya están disponibles.
   - Para posponer la descarga del modelo: `./setup.ps1 -SkipModelDownload` o `sh setup.sh --skip-model-download`.
   - Para usar otra sincronización o solo una carpeta local: `./setup.ps1 -SkipDriveDesktop` o `sh setup.sh --skip-drive-desktop`.
2. Ejecuta `gh auth login`, `gh auth setup-git` y `codex login` si aún no están autenticados. Configura el autor de Git con `git config --global user.name "Tu nombre"` y `git config --global user.email "tu@email"` si falta.
3. Crea una carpeta de Drive, por ejemplo `VIDEO TO SKILL`, y sincronízala con Drive para escritorio. Copia `config.example.json` a `config.local.json`; cambia `inbox_dir` por la ruta local real y `repository` por `OWNER/REPO`. `config.local.json` está excluido de Git. `visual_max_frames` limita las imágenes examinadas por video (48 por defecto; admite 3–96). Para un segundo intento automático cuando la transcripción sea el motivo de `needs_review`, define `"review_whisper_model": "small"`. Es opcional: Whisper descargará ese modelo la primera vez que lo necesite y puede tardar más en computadores modestos.
4. Ejecuta `.\.venv\Scripts\python.exe -m reel_skill_factory doctor` en Windows o `.venv/bin/python -m reel_skill_factory doctor` en macOS/Linux. Opcionalmente añade `--url https://www.instagram.com/reel/CODIGO/` para probar la disponibilidad de un Reel público. El doctor comprueba autenticación de Codex/GitHub, soporte de imágenes en Codex, Watch Skill/OCR, FFmpeg/ffprobe, repositorio y carpeta; la entrada desde el teléfono exige una prueba real.
5. Inicia el trabajador: en Windows ejecuta `./scripts/install-windows-task.ps1` para instalar una tarea de tu usuario que procesa la carpeta cada cinco minutos al iniciar sesión, sin abrir consola visible. Comprueba su estado con `Get-ScheduledTaskInfo -TaskName 'Reel Skill Factory'` y revisa `.local-state/task.log` para ver el PID y el resultado de cada pasada; para quitarla usa `Unregister-ScheduledTask -TaskName 'Reel Skill Factory' -Confirm:$false`. En macOS/Linux ejecuta `.venv/bin/python -m reel_skill_factory watch` y déjalo abierto o agrégalo al inicio de sesión. También puedes ejecutar `watch` en Windows sin instalar la tarea. Para procesar una sola tanda usa `once`.

La instalación en Windows crea un acceso directo **Bóveda de Skills** en el escritorio y otro en Inicio automático para abrir la página al iniciar sesión. Deja la pestaña abierta: `.local-state/vault.html` se actualiza cada 30 segundos mientras el trabajador procesa videos. Muestra las skills, el análisis y sus evidencias sin entrar a GitHub. Los archivos permanecen en tu computador; cada borrador tiene un enlace a su PR para la revisión final. Puedes quitar la apertura automática eliminando el acceso directo de la carpeta Inicio de Windows. En macOS/Linux genera o actualiza la página con `.venv/bin/python -m reel_skill_factory vault` y abre la ruta que imprime. No requiere servidor, puerto ni cuenta adicional.

El instalador necesita internet y, según el sistema, puede pedir permisos para instalar aplicaciones. En Linux instala la versión de PyTorch para CPU, suficiente para Whisper sin descargar componentes CUDA. No puede iniciar sesión por ti en Google, GitHub ni Codex, elegir tu carpeta de Drive o comprobar el menú Compartir de tu teléfono. En Linux no hay un cliente oficial de Google Drive para escritorio: usa una carpeta local o configura una sincronización compatible por tu cuenta. Si el gestor de paquetes indicado no está disponible, el script se detiene con una instrucción concreta.

### Entrada directa por la carpeta de Drive

Desde iPhone o Android, sube a `inbox` un video que tengas derecho a usar en formato `.mp4`, `.mov`, `.m4v`, `.webm` o `.mkv`, de hasta 500 MB. Tras sincronizarse con el computador y permanecer sin cambios durante 30 segundos, el trabajador examina los frames y transcribe el audio cuando existe. El archivo de video permanece en Drive; el borrador de PR solo lleva una huella SHA-256, el análisis y la skill. Conserva el video original para revisar el resultado antes de fusionar el PR.

También puedes colocar un archivo `.txt` con un solo enlace de Reel en `inbox`, por ejemplo `reel-001.txt`. Watch Skill usa `yt-dlp` para obtener el video y sus subtítulos; Whisper transcribe el audio si faltan. Es una forma sencilla de probar enlaces desde el computador.

Los enlaces compartidos de Threads no están admitidos como entrada `.txt` por este trabajador. Para analizar un video de Threads, guarda el archivo del video y súbelo a `inbox` como `.mp4` o usa el análisis manual con Watch Skill. Un video sin pista de audio puede producir una skill visual si sus frames explican el método. En una generación manual, `core.generate(..., task_intent=...)` permite indicar qué técnica se busca extraer cuando el tema que aparece en pantalla no es el objetivo de la skill.

Si Instagram solo te ofrece **compartir el enlace**, eso no sube el video a Drive. Para la entrada directa, guarda primero un archivo de video al teléfono y súbelo desde la app de Drive. Para compartir solo el enlace, necesitas una acción que **cree un archivo de texto** en esa carpeta. En iPhone puedes explorar un atajo de la hoja Compartir que reciba URL/texto y use Guardar archivo en la ubicación de Google Drive disponible en Archivos. En Android, usa una acción o app que acepte texto compartido y lo guarde como `.txt` en Drive. Comprueba que el enlace terminó dentro del archivo; las opciones de Compartir cambian entre apps y versiones.

### Entrada opcional por correo desde iPhone y Android

Esta opción convierte el enlace que compartes desde Instagram en un `.txt` dentro de **tu misma carpeta de Drive**. Úsala si quieres compartir desde el teléfono sin crear el archivo manualmente.

1. En [Google Apps Script](https://script.google.com/), crea un proyecto nuevo y copia [Code.gs](google_apps_script/Code.gs). En **Project Settings → Script Properties**, define:

   | Propiedad | Valor |
   | --- | --- |
   | `INBOX_ADDRESS` | Una variante de tu Gmail, por ejemplo `nombre+reels@gmail.com` |
   | `ALLOWED_SENDER` | Tu dirección desde la que compartirás los Reels |
   | `DRIVE_FOLDER_ID` | ID de la carpeta `inbox` en su URL de Drive |

2. Ejecuta `install()` una vez desde el editor y autoriza Gmail/Drive. Crea un disparador cada cinco minutos. `install()` inicia el cursor en el momento actual: envía el primer enlace **después** de ejecutarlo. No necesitas desplegar un web app ni exponer un webhook.
3. En Instagram, abre un Reel, toca **Compartir → Compartir en... → Gmail/Mail**, envía el enlace a `INBOX_ADDRESS` y comprueba que aparece un `.txt` en la carpeta de Drive. Si Instagram no ofrece correo en tu teléfono, usa **Copiar enlace** dentro de Instagram y pégalo en un correo al mismo destino. El menú exacto depende de la versión de Instagram y del teléfono.

El correo de entrada debe salir de `ALLOWED_SENDER`. Apps Script elimina parámetros de seguimiento del enlace, evita archivos duplicados por ID de mensaje y nunca guarda el correo completo. Si tu dominio no permite direcciones con `+`, usa una dirección o alias propio y verificado.

## Resultado y revisión

Cada video apto crea una rama `skill/CODIGO` y un draft PR con `skills/<nombre>/SKILL.md` y `sources/CODIGO.md`. Para archivos locales, `CODIGO` deriva del SHA-256 del video; la fuente documenta la huella en vez de publicar el archivo. Para enlaces, la fuente contiene el URL. Ambos incluyen análisis y marcas de tiempo de evidencia de audio o visual, sin transcripción ni frames completos. Si el video anuncia una lista y faltan elementos verificables, queda en `needs_review` en vez de inventar los puntos. Antes de fusionar, revisa fidelidad, utilidad, vigencia técnica y derechos de reutilización. Una opinión o video promocional sin método se registra como `not_skillable` y no crea PR. Cuando la duda proviene de la transcripción y configuraste `review_whisper_model`, el trabajador hace un segundo intento antes de dejarlo pendiente. Los errores no se repiten automáticamente; para reintentar todos los fallos usa `once --retry-failed`.

La generación ahora separa la tesis y los puntos observados en un mapa con evidencia, redacta una skill desde ese mapa y encarga una revisión de fidelidad aparte. Si la revisión encuentra una pérdida sustancial, se hace una corrección automática y se revisa una vez más. Un fallo de fidelidad bloquea la publicación. La sección de fuente y la bóveda distinguen lo que enseñaba el video de las adaptaciones editoriales. El veredicto automático orienta la revisión humana; no demuestra por sí solo que la interpretación sea correcta.

### Revisar y reintentar un video

`status` muestra el ID de cada video y su estado. Un trabajo conserva `visual.json`, los frames en `watch/`, `transcript.txt`, `analysis.md`, `result.json` y los intentos anteriores en `.local-state/jobs/ID/`. Estos archivos no se suben a GitHub. Para revisar un caso desde PowerShell:

```powershell
.\.venv\Scripts\python.exe -m reel_skill_factory status
.\.venv\Scripts\python.exe -m reel_skill_factory status CODIGO
.\.venv\Scripts\python.exe -m reel_skill_factory retry CODIGO --model small
.\.venv\Scripts\python.exe -m reel_skill_factory retry CODIGO --refresh-draft
```

En macOS/Linux usa `.venv/bin/python` en las mismas órdenes. Si el modelo aún deja errores, corrige manualmente `.local-state/jobs/CODIGO/transcript.txt`, conservando `[mm:ss]` al comienzo de cada línea, y ejecuta `retry CODIGO --use-transcript`. Ese reintento usa la edición sin descargar ni transcribir otra vez. Revisa la fidelidad al audio antes de editar: el programa no puede certificar una corrección humana. Para regenerar un PR existente usa `retry CODIGO --refresh-draft`: reutiliza la transcripción y los frames guardados, conserva el resultado anterior en `history/` y actualiza el mismo PR únicamente si continúa abierto como borrador y solo contiene los archivos de esa skill. Si la revisión nueva falla, deja el PR anterior intacto y muestra la regeneración pendiente en la bóveda. Los intentos previos se conservan bajo `attempts/`.

El worker usa una clonación temporal para cada PR y no modifica tu checkout. No lee ni sube cookies del navegador. Watch Skill procesa frames y OCR localmente; la transcripción, el OCR y las imágenes elegidas se envían a Codex CLI para generar el borrador. Codex se invoca en modo de solo lectura, sin comandos de shell y con búsqueda web activa para verificar detalles técnicos. El programa escribe únicamente los archivos del PR después de validar la estructura y las marcas de tiempo. Revisa todo contenido generado antes de usarlo.

La división de módulos, los estados y los límites de privacidad están en [Arquitectura](docs/ARCHITECTURE.md).

La licencia MIT cubre el contenido original de este repositorio. No concede derechos sobre los videos de terceros; quien publica una skill debe revisar su procedencia y su redacción.

## Pruebas

```bash
python -m unittest discover -s tests -v
```

Las pruebas locales cubren validación de enlaces, entrada de video, estados, reintentos y salida de generación. Una prueba completa requiere un video propio o Reel accesible, el teléfono, Drive sincronizado y autenticaciones activas; Gmail solo se necesita si eliges esa entrada.

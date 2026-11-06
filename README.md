# Reel Skill Factory

Convierte enlaces de Reels de Instagram en borradores de skills revisables en GitHub. Usa el extractor `video-a-skill` del autor como base: `yt-dlp` obtiene subtítulos o audio y Whisper transcribe cuando hace falta. Solo se genera una skill si el audio contiene un método reutilizable.

```text
Instagram (iPhone/Android) → compartir por correo → Gmail
  → Apps Script (cada 5 min) → archivo .txt en Drive
  → Drive para escritorio → trabajador Python local
  → yt-dlp + Whisper → Codex CLI → borrador de PR en GitHub
```

El equipo debe estar encendido, conectado y con el trabajador activo (`watch` o tarea programada en Windows). Un Reel privado, retirado o inaccesible puede fallar. Las skills se proponen en **draft PRs**: nunca se fusionan ni instalan solas. El repositorio público recibe la skill, una fuente y un análisis breve; la transcripción completa permanece local. Cada usuario autentica sus propias cuentas de Google, Codex y GitHub. La generación con Codex puede estar sujeta a límites o costos de su cuenta.

## Requisitos

- Windows, macOS o Linux con Python 3.11 o 3.12. Recomendados 4 GB de RAM y 3 GB libres; el doctor informa la capacidad real.
- Git, [GitHub CLI](https://cli.github.com/), [Codex CLI](https://developers.openai.com/codex/cli/), [FFmpeg](https://ffmpeg.org/) y [Google Drive para escritorio](https://support.google.com/drive/answer/10838124).
- Cuenta Gmail/Google para el correo de entrada, Apps Script y Drive; acceso de escritura al repositorio GitHub de destino.
- Un Reel que `yt-dlp` pueda leer. No se usan cookies de navegador automáticamente.

## Instalar y comprobar viabilidad

1. Clona este repositorio y abre una terminal en su carpeta. Ejecuta `./setup.ps1` en PowerShell o `sh setup.sh` en macOS/Linux. **Antes de instalar dependencias**, se ejecuta `doctor --preinstall` para revisar sistema, Python, RAM, disco y herramientas. El instalador crea `.venv` e instala `yt-dlp` y Whisper.
2. Ejecuta `gh auth login`, `gh auth setup-git` y `codex login` si aún no están autenticados. Configura el autor de Git con `git config --global user.name "Tu nombre"` y `git config --global user.email "tu@email"` si falta.
3. Crea una carpeta de Drive, por ejemplo `Reel Skill Factory/inbox`, y sincronízala con Drive para escritorio. Copia `config.example.json` a `config.local.json`; cambia `inbox_dir` por la ruta local real y `repository` por `OWNER/REPO`. `config.local.json` está excluido de Git.
4. Ejecuta `.\.venv\Scripts\python.exe -m reel_skill_factory doctor` en Windows o `.venv/bin/python -m reel_skill_factory doctor` en macOS/Linux. Opcionalmente añade `--url https://www.instagram.com/reel/CODIGO/` para probar la disponibilidad de un Reel público. El doctor comprueba autenticación de Codex/GitHub, repositorio, carpeta y extractor; la parte móvil y Apps Script exige la prueba del paso siguiente.

### Entrada desde iPhone y Android

1. En [Google Apps Script](https://script.google.com/), crea un proyecto nuevo y copia [Code.gs](google_apps_script/Code.gs). En **Project Settings → Script Properties**, define:

   | Propiedad | Valor |
   | --- | --- |
   | `INBOX_ADDRESS` | Una variante de tu Gmail, por ejemplo `nombre+reels@gmail.com` |
   | `ALLOWED_SENDER` | Tu dirección desde la que compartirás los Reels |
   | `DRIVE_FOLDER_ID` | ID de la carpeta `inbox` en su URL de Drive |

2. Ejecuta `install()` una vez desde el editor y autoriza Gmail/Drive. Crea un disparador cada cinco minutos. `install()` inicia el cursor en el momento actual: envía el primer enlace **después** de ejecutarlo. No necesitas desplegar un web app ni exponer un webhook.
3. En Instagram, abre un Reel, toca **Compartir → Compartir en... → Gmail/Mail**, envía el enlace a `INBOX_ADDRESS` y comprueba que aparece un `.txt` en la carpeta de Drive. Si Instagram no ofrece correo en tu teléfono, usa **Copiar enlace** dentro de Instagram y pégalo en un correo al mismo destino. El menú exacto depende de la versión de Instagram y del teléfono.
4. Inicia el trabajador: en Windows ejecuta `./scripts/install-windows-task.ps1` para instalar una tarea de tu usuario que procesa la carpeta cada cinco minutos al iniciar sesión. Comprueba su estado con `Get-ScheduledTaskInfo -TaskName 'Reel Skill Factory'`; para quitarla usa `Unregister-ScheduledTask -TaskName 'Reel Skill Factory' -Confirm:$false`. En macOS/Linux ejecuta `.venv/bin/python -m reel_skill_factory watch` y déjalo abierto o agrégalo al inicio de sesión. También puedes ejecutar `watch` en Windows sin instalar la tarea. Para procesar una sola tanda usa `once`.

El correo de entrada debe salir de `ALLOWED_SENDER`. Apps Script elimina parámetros de seguimiento del enlace, evita archivos duplicados por ID de mensaje y nunca guarda el correo completo. Si tu dominio no permite direcciones con `+`, usa una dirección o alias propio y verificado. También puedes poner un `.txt` con un enlace de Reel en la carpeta sincronizada para probar el trabajador sin correo.

## Resultado y revisión

Cada Reel apto crea una rama `skill/CODIGO` y un draft PR con `skills/<nombre>/SKILL.md` y `sources/CODIGO.md`. La fuente contiene el enlace, análisis y marcas de tiempo, sin transcripción completa. Antes de fusionar, revisa la fidelidad al video, utilidad de la skill, vigencia de plataformas/comandos y derechos de reutilización. Una opinión o video promocional sin método se registra como `not_skillable` en `.local-state/results.json` y no crea PR. Un caso ambiguo queda como `needs_review`. Los errores no se repiten automáticamente; para reintentar luego de resolverlos usa `once --retry-failed`.

El worker usa una clonación temporal para cada PR y no modifica tu checkout. No lee ni sube cookies del navegador. La transcripción se envía a Codex CLI para generar el borrador; Codex se invoca en modo de solo lectura, sin comandos de shell y con búsqueda web activa para verificar detalles técnicos. El programa escribe únicamente los archivos del PR después de validar la estructura y las marcas de tiempo. Revisa todo contenido generado antes de usarlo.

La licencia MIT cubre el código de este repositorio. No concede derechos sobre los videos de terceros; quien publica una skill debe revisar su procedencia y su redacción.

## Pruebas

```bash
python -m unittest discover -s tests -v
```

El test local cubre validación de enlaces, configuración y salida de generación. Una prueba completa requiere un Reel accesible, el teléfono, Gmail, Drive sincronizado y autenticaciones activas.

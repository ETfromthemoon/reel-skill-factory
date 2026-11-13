# Instalación guiada

## Antes de empezar

Necesitas Windows 10/11 de 64 bits, o macOS/Linux con Python 3.11/3.12; internet, al menos 3 GB libres, una cuenta para Codex y una carpeta local donde llegarán los videos. Con menos de 4 GB de RAM conviene usar el modelo Whisper `tiny`. El instalador comprueba estos puntos. En Linux, Google Drive para escritorio no existe; una carpeta local sirve para probar el flujo.

**No pongas el programa dentro de la carpeta de Drive.** La carpeta de entrada recibe videos; la biblioteca privada guarda tus borradores. El repositorio público contiene solo el programa.

## Windows

1. Descarga el ZIP y extráelo en una carpeta que no vayas a mover. Abre esa carpeta en el Explorador.
2. En la barra de dirección del Explorador escribe `powershell` y pulsa Enter. Ejecuta `./setup.ps1`.
3. Si Windows marca los scripts descargados como bloqueados, revisa que el ZIP venga del repositorio esperado y ejecuta `Unblock-File -Path .\setup.ps1, .\scripts\*.ps1`; luego repite `./setup.ps1`. Si una política de tu equipo prohíbe scripts, consulta a quien administra el equipo.
4. El instalador puede abrir el navegador para iniciar sesión en Codex y pedir confirmaciones de Windows para instalar aplicaciones. Cuando pregunte por la carpeta, pega su ruta **del computador**, no un enlace de Drive. En el Explorador puedes abrir la carpeta y copiar la ruta de la barra de dirección.
5. Al finalizar, abre **Bóveda de Skills** desde el escritorio. La tarea de fondo revisa la carpeta cada cinco minutos mientras tu sesión está abierta.

Si ya tienes una carpeta local, puedes evitar la pregunta: `./setup.ps1 -InboxDir "C:\ruta\a\carpeta"`. El instalador se puede repetir para reparar dependencias. Conserva la configuración previa y avisa si intentas cambiar la carpeta sin revisar el archivo.

## macOS y Linux

Abre Terminal en la carpeta extraída y ejecuta `sh setup.sh`. Introduce la ruta local de entrada cuando la pida. En macOS puedes instalar Drive para escritorio desde el instalador; en Linux, usa una carpeta local o sincronización externa. Al terminar, mantén abiertos `.venv/bin/python -m reel_skill_factory watch` y, en otra terminal, `.venv/bin/python -m reel_skill_factory vault --serve`. Abre `http://127.0.0.1:8766/`. El inicio automático persistente para estos sistemas aún no está incluido.

## Primera prueba de extremo a extremo

1. Desde el teléfono, sube un `.mp4` corto, propio o autorizado, a la carpeta de Drive. Espera a que aparezca en el computador. Un enlace de Drive a un video no equivale al archivo de video; para un Reel público usa un `.txt` con su enlace.
2. En Windows espera hasta cinco minutos; en macOS/Linux deja el trabajador `watch` abierto. En la bóveda pulsa «Actualizar progreso».
3. El workflow prepara automáticamente un caso, una muestra y una revisión. Si la skill crea interfaces, verás una vista HTML estática. Pulsa «Actualizar progreso» si aún aparece «Preparando demostración».
4. Abre «Qué enseñaba el video», «Leer skill» y «Contraste y adaptaciones». Compara esos apartados con la demostración, sus límites y sus vacíos.
5. Si falta algo, abre «Pedir corrección», describe el problema y pulsa «Corregir borrador y repetir demostración». Si te convence, pulsa «Aprobar e instalar». La skill se copia a las carpetas locales de Codex y de agentes; nunca se sube al repositorio público.

## Si algo no avanza

- Ejecuta `.venv\Scripts\python.exe -m reel_skill_factory doctor` en Windows, o `.venv/bin/python -m reel_skill_factory doctor` en macOS/Linux. Las líneas `FALTA` indican lo que falta.
- Comprueba que Drive haya descargado el archivo y que el computador esté encendido. En Windows revisa `.local-state/task.log` y el estado de la tarea «Reel Skill Factory».
- La prueba local puede terminar con vacíos si Codex no pudo escribir archivos; revisa la respuesta y repite con un caso acotado antes de aprobar.
- Los errores de entrada no se reintentan automáticamente. Usa `once --retry-failed` o `retry ID` desde el Python de `.venv`.

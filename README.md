# a gemini more like claude

Hooks para el **Antigravity CLI de Google** que le quitan a Gemini la costumbre de
decir "listo" sin haberlo comprobado.

No es para Claude Code: Claude ya trae parte de esto de serie y el formato de hooks es
otro. Esto es solo para `agy`.

No es un prompt pidiendo por favor que verifique: es un portón que **intercepta cada
llamada a herramienta** y bloquea el final de turno mientras falte la comprobación
que ese trabajo exige.

## Qué hace exactamente

- **Es proporcional al riesgo.** Un README no exige nada. Un script exige una
  ejecución real. Una web, un juego, un 3D o una animación exigen abrirlo, capturarlo
  y auditarlo con los ojos. Lo de solo lectura (`ls`, `cat`, `grep`…) se aprueba solo,
  para que la sesión no se vuelva lenta.
- **Escribir no es comprobar.** `cat > snake.html` no demuestra que el juego funcione,
  y el portón lo sabe.
- **Si dices que algo no funciona, tiene que reproducirlo.** En cuanto tu mensaje trae
  un "no me deja", "sigue igual", "está roto" o "da error", el turno no se cierra sin
  al menos una reproducción del fallo. Nada de "debería funcionar" ni "a mí me va":
  o pega la salida que lo demuestra, o dice qué probó, qué vio y qué le falta.
- **La auditoría cara se cobra una vez por tarea.** Las vueltas siguientes solo obligan
  a volver a mirar, no a repetir el ritual entero.
- **Guardia de destructivos**: avisa antes de un `rm -rf`, un `git reset --hard` o
  similar.
- **sudo por ventana**: el comando exacto se enseña en un diálogo `zenity` y la
  contraseña la escribe la persona. El agente nunca la ve ni la maneja.

Un solo proceso por evento (los grupos de hooks con nombres separados se pisan entre
sí), y `json`/`re` se importan tarde: el hook tarda ~43 ms y la mayoría de llamadas ni
los necesita.

## Cómo se ve

Un comando de solo lectura pasa sin preguntar:

```
$ echo '{"toolCall":{"name":"run_command","args":{"CommandLine":"ls -la"}}}' | dispatch.py pre
{"decision": "allow"}
```

Un `rm -rf` no:

```
{"decision": "force_ask",
 "reason": "Irreversible (rm recursivo/forzado). Mira antes que hay dentro y confirma."}
```

Un `sudo` se reescribe para que la contraseña la pida una ventana, no el agente:

```
{"decision": "allow",
 "reason": "Comando con sudo: te pedira la contrasena en una ventana.",
 "overwrite": {"CommandLine": "SUDO_ASKPASS=\".../askpass-zenity.sh\" sudo -A pacman -Syu"}}
```

Y esto es lo que pasa cuando el agente escribe una página con `<canvas>` y
`requestAnimationFrame` y acto seguido intenta dar la tarea por terminada:

```
PARA. Ibas a terminar y no lo has abierto ni una vez y no has interrogado la pagina
(teclas, `agy-ver js`, consola).

Acabas de escribir algo que se mueve o se juega:
  landing.html

No escribas todavia ninguna conclusion: mirar el codigo no demuestra que funcione.
Compruebalo con estos comandos exactos (la ventana se abre en pantalla, el usuario la
esta mirando; no uses headless ni playwright):

  agy-ver abrir landing.html
  agy-ver foto antes
  agy-ver mide 3              # FPS reales y errores durante 3 segundos
  agy-ver tecla ArrowRight 5  # o Space, KeyA, Enter... teclas de verdad
  agy-ver foto despues        # compara las dos capturas: cambio lo que esperabas?
  agy-ver logs

Y contesta estas seis ANTES de concluir nada, con lo que has OBSERVADO:
  1. CONTROLES: por cada tecla, di primero que esperas ("derecha -> x sube"), pulsala
     y mide con `agy-ver js`. [...]
  5. LO QUE SE MUEVE: compara las dos capturas. Lo que no cambia NO se mueve, diga lo
     que diga el codigo.
  6. CASO DE FALLO: provocalo de verdad (choque, game over) y mira la PANTALLA.
```

El agente no puede cerrar el turno hasta hacerlo.

## Instalar

**Linux y macOS**

    git clone https://github.com/iaguito22/a-gemini-more-like-claude /tmp/agmlc
    cp -r /tmp/agmlc/hooks-scripts ~/.gemini/config/
    cp /tmp/agmlc/hooks.json ~/.gemini/config/
    cp /tmp/agmlc/bin/agy-ver ~/.local/bin/ && chmod +x ~/.local/bin/agy-ver

**Windows** (PowerShell)

    git clone https://github.com/iaguito22/a-gemini-more-like-claude $env:TEMP\agmlc
    Copy-Item -Recurse $env:TEMP\agmlc\hooks-scripts $env:USERPROFILE\.gemini\config\
    Copy-Item $env:TEMP\agmlc\hooks.windows.json $env:USERPROFILE\.gemini\config\hooks.json
    Copy-Item $env:TEMP\agmlc\bin\agy-ver $env:USERPROFILE\.gemini\config\agy-ver.py

Abre el `hooks.json` que acabas de copiar y **sustituye `TU-USUARIO`** por tu carpeta de
usuario real, en las cuatro líneas. Se pone la ruta entera a propósito: no depende de que
el CLI expanda `%USERPROFILE%` ni de que exista el nombre `python3`, que en Windows suele
ser `python` o `py -3` (si el tuyo es `py`, cámbialo también ahí).

En Windows, `agy-ver` se llama con Python delante, porque no hay shebang:

    python $env:USERPROFILE\.gemini\config\agy-ver.py abrir pagina.html

Lo único que no funciona en Windows es el **sudo por ventana**: `zenity` es de escritorio
Linux. El resto (portón, proporcionalidad, guardia de destructivos, `agy-ver`) es Python
puro y usa la carpeta temporal del sistema, sea `/tmp` o `%TEMP%`.

Y pega el contenido de `EVIDENCIA.md` en tu `~/.gemini/config/GEMINI.md`. Los hooks
bloquean; ese texto es lo que le dice al modelo **cómo** comprobar. Sin él, el portón
funciona pero el agente tarda más en entender qué le piden.

Aplica en la siguiente sesión de `agy`.

## `agy-ver`

Va incluido porque el portón lo da por hecho: es la forma de mirar una página sin
pelearse con headless ni con Playwright. Abre una ventana de Chrome **visible** por
CDP.

    agy-ver abrir <fichero|url>     agy-ver foto [nombre]     agy-ver logs
    agy-ver ve '#seccion'           agy-ver movil             agy-ver escribe '#q' 'texto'
    agy-ver tecla ArrowLeft 3       agy-ver pulsa Space 600   agy-ver clic X Y
    agy-ver mide 3                  agy-ver js '<expr>'       agy-ver recarga
    agy-ver cerrar

Necesita Chrome o Chromium instalado; en Windows busca además el Chrome, el Edge y el
Brave de `Program Files` y de `LOCALAPPDATA`. `mide 3` da FPS reales y tirones durante 3
segundos.

- `ve` baja hasta un selector o a N px **sin scroll suave** y hace la foto. Con
  `js scrollTo` y `scroll-behavior: smooth` la captura salía a mitad de camino y el
  agente reabría la página una y otra vez.
- `movil` hace la foto a 390 px y avisa si hay scroll horizontal.
- `escribe` teclea como un teclado real: asignar `.value` no dispara el `onChange` de React.
- `cerrar` cierra Chrome por CDP (aunque se haya perdido su pid) y **deja las fotos**:
  si iba encadenado tras `foto`, el agente aún tiene que abrirlas.

## Comprobar que quedó bien puesto

    python3 ~/.gemini/config/hooks-scripts/test-porton.py                     # Linux · macOS
    python $env:USERPROFILE\.gemini\config\hooks-scripts\test-porton.py      # Windows

57 comprobaciones sobre el despachador. Tiene que terminar en `TODO OK`.

## Quitarlo

Renombra `~/.gemini/config/hooks.json` a `hooks.json.off` y reinicia la sesión.

## Licencia

MIT.

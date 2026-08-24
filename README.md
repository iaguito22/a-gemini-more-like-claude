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

    git clone https://github.com/iaguito22/a-gemini-more-like-claude /tmp/agmlc
    cp -r /tmp/agmlc/hooks-scripts ~/.gemini/config/
    cp /tmp/agmlc/hooks.json ~/.gemini/config/
    cp /tmp/agmlc/bin/agy-ver ~/.local/bin/ && chmod +x ~/.local/bin/agy-ver

Y pega el contenido de `EVIDENCIA.md` en tu `~/.gemini/config/GEMINI.md`. Los hooks
bloquean; ese texto es lo que le dice al modelo **cómo** comprobar. Sin él, el portón
funciona pero el agente tarda más en entender qué le piden.

Aplica en la siguiente sesión de `agy`.

## `agy-ver`

Va incluido porque el portón lo da por hecho: es la forma de mirar una página sin
pelearse con headless ni con Playwright. Abre una ventana de Chrome **visible** por
CDP.

    agy-ver abrir <fichero|url>     agy-ver foto [nombre]     agy-ver logs
    agy-ver tecla ArrowLeft 3       agy-ver pulsa Space 600   agy-ver clic X Y
    agy-ver mide 3                  agy-ver js '<expr>'       agy-ver recarga
    agy-ver cerrar

Necesita Chrome o Chromium instalado. `mide 3` da FPS reales y tirones durante 3
segundos.

## Comprobar que quedó bien puesto

    python3 ~/.gemini/config/hooks-scripts/test-porton.py

48 comprobaciones sobre el despachador. Tiene que terminar en `TODO OK`.

## Quitarlo

Renombra `~/.gemini/config/hooks.json` a `hooks.json.off` y reinicia la sesión.

## Licencia

MIT.

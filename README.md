# portón de verificación

Hooks para Antigravity CLI que impiden que el agente diga "listo" sin haberlo
comprobado.

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

## Instalar

    git clone https://github.com/iaguito22/porton-verificacion /tmp/porton
    cp -r /tmp/porton/hooks-scripts ~/.gemini/config/
    cp /tmp/porton/hooks.json ~/.gemini/config/
    cp /tmp/porton/bin/agy-ver ~/.local/bin/ && chmod +x ~/.local/bin/agy-ver

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

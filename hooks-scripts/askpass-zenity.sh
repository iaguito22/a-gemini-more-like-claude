#!/bin/sh
# SUDO_ASKPASS: pide la contrasena en una ventana, mostrando el comando exacto.
# El agente nunca ve ni maneja la contrasena: la escribe el usuario en el dialogo.
CMD=$(cat /tmp/agy-verify/last_sudo 2>/dev/null || echo "(comando desconocido)")
zenity --password \
  --title="El agente pide sudo" \
  --text="Antigravity quiere ejecutar como root:

$CMD

Escribe tu contrasena solo si esto es lo que esperabas." 2>/dev/null

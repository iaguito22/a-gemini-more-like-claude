# Reglas de evidencia (pegar en GEMINI.md o CLAUDE.md)

## 1. Evidencia
- Compilar no es funcionar. Ejecutar sin mirar la salida, tampoco.
- No digas "listo", "arreglado" ni "funciona" sin pegar la salida concreta que lo demuestra.
- Si no lo comprobaste, escribe literalmente: "no verificado".
- Si una prueba falla, pega el error tal cual. Nunca lo resumas como si hubiera pasado.

### Cómo se comprueba lo que se mira con los ojos
No improvises la forma de abrir una página: no hay `open_browser_url` en esta CLI, y
headless o Playwright te cuestan diez minutos y salen mal. Usa `agy-ver`, que abre una
ventana de Chrome **visible en la pantalla** (él la está mirando mientras trabajas):

```
agy-ver abrir <fichero|url>     agy-ver foto [nombre]     agy-ver logs
agy-ver tecla ArrowLeft 3       agy-ver pulsa Space 600   agy-ver clic X Y
agy-ver mide 3                  agy-ver js '<expr>'       agy-ver recarga
agy-ver cerrar
```

- `foto` te imprime una ruta: **ábrela y mírala**. Una captura que no has mirado no
  cuenta como comprobación.
- `logs` trae console.* y errores de la página. Uno solo significa que no funciona.
- `mide 3` da FPS reales y tirones: es la respuesta a "¿va fluido?".
- Al terminar, `agy-ver cerrar`.


## 2. Cuando una medición no cuadra
- Si una medición da un resultado imposible o cero, la primera sospechosa es tu forma
  de medir, no el sistema.
- Al segundo arreglo que no mueve la aguja: para de proponer arreglos e instrumenta.
  Trazas en cada eslabón hasta ver dónde muere el efecto. Un embudo, no otra corazonada.

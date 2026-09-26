#!/usr/bin/env python3
"""Despachador unico de hooks de Antigravity.

Un solo proceso por evento: los grupos con nombre separados se pisan entre si,
asi que toda la logica vive aqui. Uso: dispatch.py {pre|post|postinv|stop}

Principio: el porton es PROPORCIONAL al riesgo. Lo que se mira con los ojos
(webs, juegos, 3D, animacion) exige abrirlo y auditarlo; lo que solo se ejecuta
exige una ejecucion real; un README no exige nada. Y la auditoria cara se
entrega UNA vez por tarea: las vueltas siguientes solo obligan a volver a mirar.
"""
import os, sys

# json arrastra a re y cuesta 19 de los 43 ms del hook. La mayoria de llamadas no
# necesitan ninguno de los dos, asi que se importan tarde y solo si hacen falta.
def _tarde():
    global json, re
    import json, re


# Si ninguno de estos nombres aparece en el payload, la llamada no nos incumbe.
# Un falso positivo solo cuesta el camino lento; un falso negativo es imposible.
INTERESA = ("write_to_file", "replace_file_content", "propose_code", "notebook_edit",
            "create_file", "edit_file", "str_replace", "view_file", "view_file_outline",
            "view_code_item", "grep_search", "code_search", "run_command", "delete_file",
            "browser_", "capture_browser", "open_browser_url", "antigravity_browser",
            "read_url_content")


# PostToolUse solo dispara para run_command: para write_to_file no llega nunca (medido
# con AGY_HOOK_DEBUG=1). Por eso todo el conteo vive en pre() y post() solo recoge si
# el comando fallo, que es lo unico que pre no puede saber.
INTERESA_POST = ("run_command",)


def perm_rapido():
    """perm_default() sin json: nos basta con ver si la cadena esta en el fichero."""
    for ruta in ("~/.gemini/antigravity-cli/settings.json", "~/.gemini/config/config.json"):
        try:
            with open(os.path.expanduser(ruta)) as fh:
                if "always-proceed" in fh.read():
                    return "allow"
        except Exception:
            pass
    return "ask"

# Sin importar tempfile: arrastra shutil y el hook se paga en cada llamada.
TMP = os.environ.get("TMPDIR") or os.environ.get("TEMP") or ("C:\\Windows\\Temp" if os.name == "nt" else "/tmp")
STATE = os.path.join(TMP, "agy-verify")
ASKPASS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "askpass-zenity.sh")
DEBUG = os.environ.get("AGY_HOOK_DEBUG") == "1"
CRUDO = ""   # payload tal cual, para buscar la queja del usuario venga donde venga

# ------------------------------------------------------------------ catalogos

EDITA = ("write_to_file", "replace_file_content", "propose_code", "notebook_edit",
         "create_file", "edit_file", "str_replace")
LEE = ("view_file", "view_file_outline", "view_code_item", "grep_search", "code_search")

# Extensiones por nivel de exigencia. 2 = hay que mirarlo con los ojos.
VISUAL_EXT = (".html", ".htm", ".css", ".scss", ".jsx", ".tsx", ".vue", ".svelte",
              ".glsl", ".frag", ".vert", ".shader")
EJEC_EXT = (".py", ".js", ".mjs", ".cjs", ".ts", ".sh", ".bash", ".go", ".rs", ".rb",
            ".php", ".java", ".c", ".cc", ".cpp", ".h", ".lua", ".pl", ".sql", ".ipynb")

# Un componente suelto (.jsx sin pagina que lo monte) no se puede abrir en Chrome: exigir
# mirarlo obligaba a montar un index.html de pega (21 llamadas, 107 s medidos). Solo sube
# a visual si hay un index.html cerca, y entonces lo que se abre es esa pagina.
COMPONENTE_EXT = (".jsx", ".tsx", ".vue", ".svelte")

def pagina_cerca(ruta):
    d = os.path.dirname(os.path.abspath(ruta))
    for _ in range(3):
        for c in ("index.html", os.path.join("public", "index.html")):
            if os.path.isfile(os.path.join(d, c)):
                return os.path.join(d, c)
        d = os.path.dirname(d)
    return None

# Un .js puede ser un script de terminal o una pagina. Esto lo distingue.
PISTA_VISUAL = ("<canvas", "getcontext(", "requestanimationframe", "three.",
                "webglrenderer", "document.queryselector", "document.getelementbyid",
                "addeventlistener('key", 'addeventlistener("key', "<!doctype html",
                "createelement(", "new image(", "ctx.fill", "ctx.draw")

# Y esto separa una pagina quieta (basta una captura) de algo que se mueve o se juega
# (hacen falta dos fotogramas y la auditoria entera). Una transicion de hover NO cuenta:
# si contara, cualquier landing decente subiria de nivel y volveriamos a sobrecomprobar.
PISTA_MOVIL = ("requestanimationframe", "setinterval", "three.", "webglrenderer",
               "getcontext(", "<canvas", "@keyframes", "addeventlistener('key",
               'addeventlistener("key', "onkeydown", "onkeyup", "gamepad",
               "new audio(", "audiocontext")

# Comandos de solo lectura: se aprueban solos. Aqui se gana la sensacion de rapidez.
SEGUROS = frozenset("""ls cat head tail wc file stat pwd which type date du df tree
basename dirname realpath readlink uname id uptime free nl column printenv grep rg
sort uniq cut diff jq sed awk tr md5sum sha256sum ripgrep fd bat echo true test [""".split())
GIT_SEGURO = frozenset("status diff log show branch remote rev-parse ls-files describe blame config".split())

TERM_OK = ("model_stop", "NO_TOOL_CALL", "", None)

_re = {}


def rx(clave, patron, flags=0):
    """Compila bajo demanda: la mayoria de llamadas no necesitan estos regex."""
    if clave not in _re:
        _re[clave] = re.compile(patron, flags)
    return _re[clave]


# (palabra que tiene que aparecer, patron, aviso). La palabra evita compilar el
# regex en los comandos normales, que son casi todos.
DANGER = [
    ("rm", r'\brm\s+(-[a-zA-Z]*\s+)*-[a-zA-Z]*[rf]', "rm recursivo/forzado"),
    ("reset", r'\bgit\s+reset\s+--hard', "git reset --hard: descarta cambios sin copia"),
    ("checkout", r'\bgit\s+checkout\s+(--\s+)?\.', "git checkout .: descarta cambios sin copia"),
    ("clean", r'\bgit\s+clean\s+-[a-zA-Z]*[fdx]', "git clean: borra archivos no rastreados"),
    ("push", r'\bgit\s+push\s+.*(--force|-f)\b', "push forzado: reescribe historia remota"),
    ("branch", r'\bgit\s+branch\s+-D\b', "borrado forzado de rama"),
    ("fs", r'\b(mkfs|fdisk|parted)\b', "operacion de disco"),
    ("dd", r'\bdd\s+.*of=/dev/', "dd sobre un dispositivo"),
    ("chmod", r'\bchmod\s+-R\s+777', "chmod 777 recursivo"),
    ("/dev/", r'>\s*/dev/(sd|nvme)', "escritura directa a disco"),
    ("drop", r'\bdrop\s+(table|database)\b', "DROP en base de datos"),
]

# Escribir o mirar no es comprobar. `cat > snake.html` no demuestra que funcione.
NO_VERIFICA = (
    r'^\s*(cat|tee|printf|echo)\s+[^|]*>',
    r'^\s*(mkdir|touch|cp|mv|ln|chmod|chown|rm)\b',
    r'^\s*git\s+(add|commit|status|log|diff|remote)\b',
    r'^\s*(ls|pwd|cd|which|whoami|date|clear|wc|head|tail|cat)\b',
    r'^\s*(sed|awk)\s+-i\b',
)

# El usuario diciendo "no funciona" es un dato, no una opinion. Si aparece en el turno,
# ese turno tiene que contener una reproduccion del fallo, no una explicacion de por que
# deberia ir bien.
QUEJA = (
    r'\bno\s+(me\s+)?(deja|va|vaa|funciona|carga|sale|responde|aparece|arranca|tira|rula)\b',
    r'\bsigue\s+(igual|sin|roto|rota|fallando|mal|pasando|ahi)\b',
    r'\bno\s+(se\s+)?(ve|puede|scrollea|mueve|abre|guarda)\b',
    r'\b(esta|estan|sigue)\s+(roto|rota|rotos|mal)\b',
    r'\bse\s+(rompe|cuelga|peta|congela|queda\s+colgado)\b',
    r'\b(falla|fallan|petaba|peta|casca)\b',
    r'\b(da|sale|salta)\s+(un\s+)?error\b',
    r'\bsale\s+mal\b',
    r'\bvuelve\s+a\s+(pasar|fallar|romperse)\b',
    r'\bno\s+lo\s+(has|ha)\s+arreglado\b',
    r"\bdoesn'?t\s+work\b", r'\bnot\s+working\b', r'\bstill\s+(broken|fails|failing)\b',
)

# Sin \b final a proposito: 'playwright_test.js' cuenta igual que 'playwright'.
NAVEGA_CMD = (r'(agy-ver|playwright|puppeteer|selenium|xdg-open|firefox|chromium|google-chrome|'
              r'headless|cypress|webkit2png|serve\b|http-server)')

# Herramientas nativas de navegador, por prefijo.
NAVEGA = ("browser_", "capture_browser", "open_browser_url", "antigravity_browser",
          "read_url_content")


# Campos donde suele venir lo que ha escrito el usuario. Si no encontramos ninguno,
# miramos el payload entero, pero solo si es corto: un payload largo puede traer el
# historial completo, y entonces una queja de hace diez turnos frenaria para siempre.
CAMPOS_USUARIO = ("prompt", "userPrompt", "userMessage", "message", "text", "query",
                  "instruction", "lastUserMessage", "input")


def texto_usuario(p, crudo):
    for k in CAMPOS_USUARIO:
        v = p.get(k)
        if isinstance(v, str) and v.strip():
            return v
        if isinstance(v, dict):
            for k2 in ("text", "content", "value"):
                if isinstance(v.get(k2), str):
                    return v[k2]
    return crudo if len(crudo) < 4000 else ""


def rx_queja(texto):
    if not texto:
        return False
    bajo = texto.lower()
    return any(rx("q" + pat, pat, re.I).search(bajo) for pat in QUEJA)


def log(*a):
    if DEBUG:
        with open(os.path.join(TMP, "agy-debug.log"), "a") as f:
            f.write(" ".join(str(x) for x in a) + "\n")


# -------------------------------------------------------------------- estado

def ruta_estado(cid):
    return os.path.join(STATE, cid + ".json")


def cargar(cid):
    f = ruta_estado(cid)
    try:
        with open(f) as fh:
            return f, json.load(fh)
    except Exception:
        return f, {}


def guardar(f, st):
    """Relee bajo cerrojo y fusiona: pre y post corren a la vez y se pisaban."""
    import fcntl
    try:
        os.makedirs(STATE, exist_ok=True)
        lock = open(f + ".lock", "w")
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            with open(f) as fh:
                disco = json.load(fh)
        except Exception:
            disco = {}
        disco.update(st)
        with open(f, "w") as fh:
            json.dump(disco, fh)
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()
    except Exception:
        try:
            with open(f, "w") as fh:
                json.dump(st, fh)
        except Exception:
            pass


def perm_default():
    """Refleja el modo de permisos actual: no debilita nada de lo que ya tenias."""
    for p in ("~/.gemini/antigravity-cli/settings.json", "~/.gemini/config/config.json"):
        try:
            with open(os.path.expanduser(p)) as fh:
                if json.load(fh).get("toolPermission") == "always-proceed":
                    return "allow"
        except Exception:
            pass
    return "ask"


# ------------------------------------------------------------- clasificacion

def nivel_de(nombre, texto):
    """0 inerte · 1 hay que ejecutarlo · 2 hay que mirarlo · 3 ademas se mueve o se juega."""
    n = (nombre or "").lower()
    t = (texto or "").lower()[:20000]
    visual = n.endswith(VISUAL_EXT) or (n.endswith(EJEC_EXT) and any(x in t for x in PISTA_VISUAL))
    if not visual:
        return 1 if n.endswith(EJEC_EXT) else 0
    return 3 if any(x in t for x in PISTA_MOVIL) else 2


def es_seguro(cmd):
    """True si el comando entero es de solo lectura y puede aprobarse solo."""
    if not cmd or len(cmd) > 2000:
        return False
    if rx("subst", r'[`>]|\$\(').search(cmd):
        return False
    for trozo in rx("split", r'\|\||&&|[|;\n]').split(cmd):
        t = trozo.strip()
        if not t:
            continue
        piezas = t.split()
        jefe = os.path.basename(piezas[0])
        if jefe == "git":
            sub = next((x for x in piezas[1:] if not x.startswith("-")), "")
            if sub not in GIT_SEGURO:
                return False
        elif jefe == "find":
            if any(x in ("-delete", "-exec", "-execdir", "-ok", "-fprint") for x in piezas):
                return False
        elif jefe in ("sed", "awk"):
            if "-i" in piezas or any(x.startswith("-i") for x in piezas):
                return False
        elif jefe not in SEGUROS:
            return False
    return True


def es_verificacion(cmd):
    c = cmd.strip()
    return bool(c) and not any(rx("nv" + p, p, re.I).search(c) for p in NO_VERIFICA)


def rutas(obj, out):
    if isinstance(obj, str):
        s = obj.strip()
        if s and len(s) < 512 and "\n" not in s and ("/" in s or "." in s):
            out.append(s)
    elif isinstance(obj, dict):
        for v in obj.values():
            rutas(v, out)
    elif isinstance(obj, list):
        for v in obj:
            rutas(v, out)
    return out


def resolver(p, roots):
    cands = [p] if os.path.isabs(p) else [os.path.join(r, p) for r in roots] + [p]
    for c in cands:
        c = os.path.abspath(os.path.expanduser(c))
        if os.path.isfile(c):
            return os.path.realpath(c)
    return None


# ---------------------------------------------------------------- PreToolUse

def pre(p):
    call = p.get("toolCall") or {}
    name = (call.get("name") or "").strip()

    # Camino rapido: la mayoria de herramientas no nos interesan. Cero disco.
    navega = name.startswith(NAVEGA)
    if not navega and name not in EDITA and name not in LEE \
            and name not in ("run_command", "delete_file"):
        return {"decision": perm_default()}

    args = call.get("args") or {}
    cid = p.get("conversationId", "anon")

    if navega:
        f, st = cargar(cid)
        st["checks"] = st.get("checks", 0) + 1
        st["browser"] = st.get("browser", 0) + 1
        if "screenshot" in name:
            st["shots"] = st.get("shots", 0) + 1
        elif name.startswith(("browser_", "execute_browser", "capture_browser")):
            st["sondas"] = st.get("sondas", 0) + 1
        guardar(f, st)
        return {"decision": perm_default()}

    if name == "delete_file":
        return {"decision": "force_ask",
                "reason": "Vas a borrar un archivo. Confirma que es el correcto: " + json.dumps(args)[:200]}

    if name == "run_command":
        cmd = str(args.get("CommandLine") or args.get("command") or "")
        bajo = cmd.lower()
        peligro = [w for pal, pat, w in DANGER
                   if pal in bajo and rx("d" + pat, pat, re.I).search(cmd)]

        if rx("sudo", r'(^|[|;&]\s*)sudo\s+(?!-A\b|-n\b)', re.I).search(cmd):
            try:
                os.makedirs(STATE, exist_ok=True)
                with open(os.path.join(STATE, "last_sudo"), "w") as fh:
                    fh.write(cmd)
            except Exception:
                pass
            nuevo = 'SUDO_ASKPASS="%s" ' % ASKPASS + rx(
                "sudo", r'(^|[|;&]\s*)sudo\s+(?!-A\b|-n\b)', re.I).sub(
                lambda m: m.group(1) + "sudo -A ", cmd)
            return {"decision": "force_ask" if peligro else perm_default(),
                    "reason": "Comando con sudo: te pedira la contrasena en una ventana."
                              + (" ADEMAS es irreversible: " + peligro[0] if peligro else ""),
                    "overwrite": {"CommandLine": nuevo}}

        if peligro:
            return {"decision": "force_ask",
                    "reason": "Irreversible (%s). Mira antes que hay dentro y confirma." % peligro[0]}

        f, st = cargar(cid)
        if es_verificacion(cmd):
            st["checks"] = st.get("checks", 0) + 1
            if rx("nav", NAVEGA_CMD, re.I).search(cmd):
                st["browser"] = st.get("browser", 0) + 1
            # cada .png distinto que produce un comando es un fotograma mas
            pngs = len(set(rx("png", r'[\w./-]+\.png').findall(cmd)))
            if not pngs:
                b = cmd.lower()
                if "screenshot" in b:
                    pngs = 1
                else:
                    pngs = len(rx("aver", r'agy-ver\s+(?:foto|ve|movil)\b').findall(b))
            st["shots"] = st.get("shots", 0) + pngs
            st["sondas"] = st.get("sondas", 0) + len(
                rx("sonda", r'agy-ver\s+(js|tecla|pulsa|clic|mide|logs|escribe)').findall(cmd.lower()))
            guardar(f, st)
        return {"decision": "allow" if es_seguro(cmd) else perm_default()}

    roots = p.get("workspacePaths") or [os.getcwd()]
    crudas = rutas(args, [])
    resueltas = [r for r in (resolver(x, roots) for x in crudas) if r]
    fseen = os.path.join(STATE, cid + ".seen")

    if name in EDITA:
        try:
            with open(fseen) as fh:
                vistos = set(fh.read().split("\n"))
        except Exception:
            vistos = set()
        # Una pagina nueva sin la skill web delante sale con todos los delatores de IA
        # (medido: 9 avisos del revisor contra 0). La descripcion no basta para que la
        # cargue siempre, asi que aqui se garantiza. Una sola vez por conversacion.
        nuevo = str(args.get("TargetFile") or "")
        skill_web = os.path.expanduser("~/.gemini/config/skills/web-frontend/SKILL.md")
        # Una escena 3D, un juego o un canvas no es una landing: el dado y los delatores
        # de la skill web no le sirven de nada (medido: 3 pasos gastados en un cubo).
        cuerpo = str(args.get("CodeContent") or "").lower()
        es_lienzo = any(k in cuerpo for k in ("three.", "webglrenderer", "<canvas", "getcontext("))
        if name == "write_to_file" and nuevo.lower().endswith((".html", ".htm")) \
                and not es_lienzo \
                and not os.path.exists(nuevo) and os.path.exists(skill_web) \
                and os.path.realpath(skill_web) not in vistos:
            return {"decision": "deny",
                    "reason": "Antes de crear una pagina, lee " + skill_web +
                              " (view_file) y sigue su paso 1. Luego repite esta escritura."}
        # Solo exigimos lectura previa si el archivo YA existe: los nuevos pasan.
        sin_leer = [x for x in resueltas if x not in vistos]
        if sin_leer:
            return {"decision": "deny",
                    "reason": ("No has leido este archivo en esta sesion: " + sin_leer[0] + "\n"
                               "Editar a ciegas es como se rompen cosas que ya funcionaban. "
                               "Abrelo (view_file), mira las lineas que vas a tocar, y repite la edicion.")}

        # Clasificamos aqui porque PostToolUse no llega para las ediciones.
        nombre = str(args.get("TargetFile") or args.get("AbsolutePath") or
                     args.get("file_path") or args.get("path") or (crudas[0] if crudas else ""))
        cuerpo = ""
        for k in ("CodeContent", "content", "code_edit", "ReplacementContent", "new_string",
                  "CodeMarkdownLanguage", "instruction"):
            v = args.get(k)
            if isinstance(v, str):
                cuerpo += v
        f, st = cargar(cid)
        nv = nivel_de(nombre, cuerpo)
        objetivo = resolver(nombre, roots) or (resueltas[0] if resueltas else nombre)
        if nombre.lower().endswith(COMPONENTE_EXT):
            pag = pagina_cerca(objetivo if os.path.isabs(objetivo) else os.path.join(roots[0], objetivo))
            if pag:
                objetivo = pag
            else:
                nv = 1
        if nv >= st.get("nivel", 0) and nv > 0:
            st["obj"] = objetivo
        st["nivel"] = max(st.get("nivel", 0), nv)
        st["edits"] = st.get("edits", 0) + 1
        # Cada edicion invalida la verificacion anterior: si no, el arreglo hereda el
        # visto bueno del intento previo y nadie vuelve a mirar.
        if st.get("ok_una_vez"):
            st["ronda"] = st.get("ronda", 0) + 1
            st["ok_una_vez"] = 0
        st["checks"] = 0
        st["browser"] = 0
        st["shots"] = 0
        st["sondas"] = 0
        guardar(f, st)
        # Lo que acaba de escribir ya lo conoce: exigirle releerlo antes de la siguiente
        # edicion costaba un view_file por fichero nuevo sin evitar nada.
        propio = nombre if os.path.isabs(nombre) else os.path.join(roots[0], nombre)
        try:
            with open(fseen, "a") as fh:
                fh.write(os.path.realpath(propio) + "\n")
        except Exception:
            pass
        return {"decision": perm_default()}

    if resueltas:  # LEE
        try:
            os.makedirs(STATE, exist_ok=True)
            with open(fseen, "a") as fh:
                fh.write("\n".join(resueltas) + "\n")
        except Exception:
            pass
    return {"decision": perm_default()}


# --------------------------------------------------------------- PostToolUse

def post(p):
    """Solo recoge si el comando fallo. Lo demas se cuenta en pre()."""
    call = p.get("toolCall") or {}
    if (call.get("name") or "").strip() != "run_command":
        return {}
    f, st = cargar(p.get("conversationId", "anon"))
    fallo = bool(p.get("error"))
    st["last_failed"] = fallo
    st["fail_streak"] = st.get("fail_streak", 0) + 1 if fallo else 0
    guardar(f, st)
    return {}


# ------------------------------------------------------------- PostInvocation

AVISO_QUEJA = """El usuario acaba de decirte que algo NO funciona. Su reporte es el dato.
Antes de contestar: reproduce el fallo tal y como el lo describe y mira la salida.
Si no consigues reproducirlo, eso tambien es un resultado: dilo, di que probaste y que
viste. Lo que no vale es explicar por que deberia funcionar."""


def postinv(p):
    f, st = cargar(p.get("conversationId", "anon"))

    # La queja se marca una vez por turno: el estado se limpia al cerrar, asi que no
    # se arrastra a la conversacion siguiente.
    if not st.get("queja") and rx_queja(texto_usuario(p, CRUDO)):
        st["queja"] = 1
        guardar(f, st)
        log("QUEJA detectada")
        return {"injectSteps": [{"ephemeralMessage": AVISO_QUEJA}]}

    if st.get("fail_streak", 0) >= 3 and st.get("funneled", 0) < 2:
        st["funneled"] = st.get("funneled", 0) + 1
        st["fail_streak"] = 0
        guardar(f, st)
        return {"injectSteps": [{"ephemeralMessage": (
            "Llevas 3 intentos fallidos seguidos. Deja de proponer arreglos: estas adivinando. "
            "Cambia de metodo -> instrumenta. Anade trazas en cada eslabon de la cadena, "
            "ejecuta una vez, y localiza donde muere el efecto exactamente. "
            "Y sospecha de la sonda antes que del sistema: si mides cero, "
            "puede que no estes midiendo donde crees."
        )}]}

    # Guia proactiva: se entrega una vez por vuelta, en cuanto hay algo que comprobar
    # y todavia no se ha comprobado. Llega ANTES de que escriba el informe, que es
    # justo lo que evita que lo escriba dos veces (una a ciegas y otra tras el porton).
    nivel = st.get("nivel", 0)
    obj = st.get("obj")
    ronda = st.get("ronda", 0)
    if nivel >= 1 and obj and st.get("guia_r") != ronda + 1:
        pendiente = (st.get("browser", 0) == 0) if nivel >= 2 else (st.get("checks", 0) == 0)
        if pendiente:
            st["guia_r"] = ronda + 1
            guardar(f, st)
            plant = GUIA_MOVIL if nivel >= 3 else (GUIA_QUIETA if nivel == 2 else GUIA_EJEC)
            texto = plant % ((obj, obj) if nivel >= 2 else (obj,))
            return {"injectSteps": [{"ephemeralMessage": texto}]}
    return {}



# ------------------------------------------------- guia proactiva de comprobacion
# Sin receta el agente se inventa cada vez una forma distinta de mirar una pagina y
# pierde la mitad del turno. Se le da ANTES de que escriba nada, no despues. agy-ver y
# no open_browser_url: la ventana de agy-ver se ve en pantalla y el usuario la mira.

GUIA_QUIETA = """Acabas de escribir algo que se mira con los ojos:
  %s

No escribas todavia ninguna conclusion ni ningun informe: aun no lo has visto.
Compruebalo asi, con estos comandos exactos (no inventes otra forma, no uses headless
ni playwright: esta ventana se abre en la pantalla y el usuario quiere verla):

  agy-ver abrir %s
  agy-ver foto                # te imprime la ruta de un png: ABRELO y MIRALO
  agy-ver ve '#seccion'       # baja hasta ahi y hace foto (no uses js scrollTo)
  agy-ver movil               # foto a 390px; avisa si hay scroll horizontal
  agy-ver logs                # un solo error de consola significa que no funciona

Y mirando la captura, contesta estas cuatro ANTES de concluir nada:
  1. ESTA TODO: enumera lo que se pidio y marca lo que aparece en la imagen.
  2. ENCUADRE: ¿algo se sale, se solapa, se corta o queda pegado al borde?
  3. SE LEE: ¿el texto tiene contraste contra SU fondo?
  4. LO QUE DIJISTE: si prometiste "boton rojo" o "tres columnas", ¿lo es en la imagen?

Hazlo todo de una vez. Luego cierra con `agy-ver cerrar` y escribe el informe, UNA
sola vez, contando lo que has visto."""

GUIA_MOVIL = """Acabas de escribir algo que se mueve o se juega:
  %s

No escribas todavia ninguna conclusion: mirar el codigo no demuestra que funcione.
Compruebalo con estos comandos exactos (la ventana se abre en pantalla, el usuario la
esta mirando; no uses headless ni playwright):

  agy-ver abrir %s
  agy-ver foto antes
  agy-ver mide 3              # FPS reales y errores durante 3 segundos
  agy-ver tecla ArrowRight 5  # o Space, KeyA, Enter... teclas de verdad
  agy-ver foto despues        # compara las dos capturas: ¿cambio lo que esperabas?
  agy-ver logs

Otros: agy-ver js '<expresion>' para leer el estado por dentro, agy-ver clic X Y,
agy-ver escribe '<selector>' 'texto' para inputs (dispara onChange; .value no),
agy-ver pulsa ArrowUp 800 para mantener una tecla, agy-ver recarga, agy-ver cerrar.

Y contesta estas seis ANTES de concluir nada, con lo que has OBSERVADO:
  1. CONTROLES: por cada tecla, di primero que esperas ("derecha -> x sube"), pulsala
     y mide con `agy-ver js`. Las cuatro direcciones por separado. Ojo: la Y de
     pantalla crece hacia ABAJO, es la causa numero uno de controles invertidos.
  2. EJES Y GIRO: si algo rota, sobre que eje deberia y sobre cual gira.
  3. PARTES: cuenta las piezas que deberia tener y las que ves.
  4. ESCALA Y ENCUADRE: ¿algo gigante, minusculo o fuera de pantalla?
  5. LO QUE SE MUEVE: compara las dos capturas. Lo que no cambia NO se mueve, diga lo
     que diga el codigo.
  6. CASO DE FALLO: provocalo de verdad (choque, game over) y mira la PANTALLA.

Hazlo todo de una vez, en esta misma tanda. Luego `agy-ver cerrar` y escribe el
informe UNA sola vez, contando lo que has visto. Si te dejas algo, el porton te va a
parar y habras perdido una vuelta entera."""

GUIA_EJEC = """Acabas de escribir codigo ejecutable:
  %s

No escribas el informe antes de ejecutarlo: escribir el archivo no es comprobarlo.
Ejecutalo de verdad, con un caso normal y uno raro, mira la salida, y solo entonces
escribe la conclusion. Una sola vez, con la salida pegada."""


# ----------------------------------------------------------------------- Stop

EJECUTAR = """PARA. Has modificado archivos y no has ejecutado NADA que lo compruebe.
Escribir el archivo no es comprobarlo.
1) Ejecuta la comprobacion real y mira la salida.
2) Relee las lineas que editaste y confirma que dicen lo que crees.
3) Si no hay forma de comprobarlo, di "no verificado" y que comando haria falta.
Pega la salida concreta que lo demuestra."""

ROJO = """PARA. Tu ultima comprobacion ha fallado y ibas a terminar. O lo arreglas, o
cierras diciendo claramente que sigue roto y pegando el error tal cual."""

NO_REPITAS = """NO REESCRIBAS EL INFORME QUE ACABAS DE DAR. Ya lo has escrito una vez
y repetirlo con otras palabras es lo que mas molesta al usuario. Cuando termines lo que
falta, responde SOLO con lo nuevo que has visto, en dos o tres lineas. Nada de volver a
poner el titular, ni las viñetas, ni la linea "Comprobado:".

Lo que falta es esto:

"""

SIN_REPRODUCIR = """PARA. El usuario te ha dicho que algo no funciona y vas a cerrar el
turno sin haberlo reproducido ni una vez.
1) Reproduce el fallo como el lo describe y pega la salida que lo demuestra.
2) Si no lo reproduces, NO digas que esta bien: di que probaste, que viste, y que te
   falta para reproducirlo.
3) Solo entonces propon el arreglo, y vuelve a medir despues.
Su reporte gana a tu impresion: el lo tiene delante y tu no."""

REVISITA = """Ya lo diste por bueno una vez y lo has vuelto a tocar. Antes de cerrar:
di en una linea que arreglaste, que has visto AHORA que demuestra que ya no pasa, y
confirma que lo que antes iba sigue yendo."""


def stop(p):
    if p.get("terminationReason") not in TERM_OK:
        return {"decision": "stop"}
    cid = p.get("conversationId", "anon")
    f, st = cargar(cid)
    nivel = st.get("nivel", 0)

    etapa = razon = None
    # Prioridad maxima: si el usuario reporto un fallo y el turno no contiene ni una
    # sola reproduccion, no se cierra. Decir "esta bien" sin medir es el fallo que mas
    # le cuesta al usuario, porque le obliga a discutir en vez de a leer una salida.
    if st.get("queja") and st.get("checks", 0) == 0 and st.get("browser", 0) == 0:
        etapa, razon = "queja", SIN_REPRODUCIR
    elif nivel >= 2:
        # Un solo frenazo, y completo: lo que falta MAS la receta entera. La escalera de
        # antes (abrir, luego capturas, luego auditoria) costaba tres turnos y el modelo
        # reescribia el informe en cada uno.
        minimo = 2 if nivel >= 3 else 1
        falta = []
        if st.get("browser", 0) == 0:
            falta.append("no lo has abierto ni una vez")
        elif st.get("shots", 0) < minimo:
            falta.append("tienes menos de %d captura%s" % (minimo, "s" if minimo > 1 else ""))
        # Dos sondas de verdad (teclas, JS, FPS, consola) valen como repaso hecho: si no,
        # el porton frenaria siempre una vez aunque hubiera comprobado bien, y el usuario
        # se comeria dos respuestas en vez de una.
        if not st.get("auditado") and st.get("sondas", 0) < 2:
            falta.append("no has interrogado la pagina (teclas, `agy-ver js`, consola)")
        if falta:
            obj = st.get("obj") or "el fichero"
            guia = (GUIA_MOVIL if nivel >= 3 else GUIA_QUIETA) % (obj, obj)
            etapa = "visual"
            razon = "PARA. Ibas a terminar y %s.\n\n%s" % (" y ".join(falta), guia)
        elif st.get("ronda", 0) > st.get("revisitas", 0):
            etapa, razon = "revisita", REVISITA
    elif nivel == 1:
        if st.get("checks", 0) == 0:
            etapa, razon = "ejecutar", EJECUTAR
        elif st.get("last_failed"):
            etapa, razon = "rojo", ROJO

    # Topes: cada etapa como mucho dos veces, y cinco frenazos en toda la tarea.
    veces = st.get("v_" + etapa, 0) if etapa else 0
    # Un frenazo por vuelta como mucho: cada frenazo cuesta un turno entero y el modelo
    # reescribe el informe cada vez. Si en el mismo turno ya le paramos, no insistimos.
    ya_en_esta_vuelta = st.get("nag_r") == st.get("ronda", 0) + 1
    if razon and veces < 2 and st.get("nags", 0) < 5 and not ya_en_esta_vuelta:
        st["nag_r"] = st.get("ronda", 0) + 1
        st["v_" + etapa] = veces + 1
        st["nags"] = st.get("nags", 0) + 1
        if etapa == "visual":
            st["auditado"] = 1
            st["ok_una_vez"] = 1
        elif etapa == "revisita":
            st["revisitas"] = st.get("revisitas", 0) + 1
            st["ok_una_vez"] = 1
        if st.get("ronda", 0) > 0 and etapa == "visual":
            razon += ("\n\nEs la vuelta numero %d: ya habias 'arreglado' esto y seguia mal. "
                      "Esta vez mide, no mires." % (st["ronda"] + 1))
        razon = NO_REPITAS + razon
        guardar(f, st)
        return {"decision": "continue", "reason": razon}

    # Fin de turno. Conservamos la memoria de la CONVERSACION (que ya se audito,
    # cuantas vueltas lleva) y borramos lo que describia solo este turno: si no,
    # el siguiente arreglo repetiria la auditoria cara desde cero, o un README
    # heredaria el nivel visual del turno anterior.
    memoria = {k: st[k] for k in ("auditado", "ronda", "revisitas", "funneled") if k in st}
    if nivel >= 2 and not razon:
        memoria["ok_una_vez"] = 1
    elif st.get("ok_una_vez"):
        memoria["ok_una_vez"] = 1
    try:
        if memoria:
            with open(f, "w") as fh:
                json.dump(memoria, fh)
        else:
            os.unlink(f)
    except Exception:
        pass
    return {"decision": "stop"}


def main():
    global CRUDO
    ev = sys.argv[1] if len(sys.argv) > 1 else "post"
    crudo = CRUDO = sys.stdin.read()
    lista = INTERESA if ev == "pre" else INTERESA_POST
    if ev in ("pre", "post") and not any(t in crudo for t in lista):
        sys.stdout.write("{}" if ev == "post" else '{"decision":"%s"}' % perm_rapido())
        return
    _tarde()
    try:
        p = json.loads(crudo)
    except Exception:
        p = {}
    try:
        out = {"pre": pre, "post": post, "postinv": postinv, "stop": stop}[ev](p)
    except Exception as e:
        # Un hook roto no debe bloquear nunca el trabajo del agente.
        log("ERROR", ev, repr(e))
        out = {"decision": "allow"} if ev == "pre" else ({"decision": "stop"} if ev == "stop" else {})
    log(ev, "claves=" + ",".join(sorted(p.keys())) if DEBUG else "",
        (p.get("toolCall") or {}).get("name", ""), p.get("terminationReason", ""),
        json.dumps(out)[:160])
    print(json.dumps(out))


main()

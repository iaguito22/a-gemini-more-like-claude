import json, subprocess, os, shutil, sys
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dispatch.py")
CID = "TEST"
fallos = []

def h(ev, payload):
    payload.setdefault("conversationId", CID)
    r = subprocess.run(["python3","-S","-E",D,ev], input=json.dumps(payload),
                       capture_output=True, text=True)
    try: return json.loads(r.stdout)
    except Exception: return {"CRASH": r.stdout + r.stderr}

SKILL_WEB = os.path.expanduser("~/.gemini/config/skills/web-frontend/SKILL.md")

def limpia(con_skill=True):
    for suf in (".json",".seen",".json.lock"):
        try: os.unlink("/tmp/agy-verify/"+CID+suf)
        except Exception: pass
    # Los casos de abajo prueban el porton, no el freno de la skill web: la damos por leida.
    if con_skill:
        h("pre", {"toolCall": {"name": "view_file", "args": {"AbsolutePath": SKILL_WEB}}})

def edita(nombre, cuerpo=""):
    c = {"name":"write_to_file","args":{"TargetFile":nombre,"CodeContent":cuerpo}}
    h("pre", {"toolCall":c}); h("post", {"toolCall":c})

def cmd(linea, error=False):
    c = {"name":"run_command","args":{"CommandLine":linea}}
    pr = h("pre", {"toolCall":c}); h("post", {"toolCall":c, "error": error})
    return pr

def foto():
    c = {"name":"capture_browser_screenshot","args":{}}
    h("pre", {"toolCall":c}); h("post", {"toolCall":c})

def parar():
    return h("stop", {"terminationReason":"NO_TOOL_CALL"})

def eq(caso, real, esperado):
    ok = esperado in str(real) if isinstance(esperado,str) else real == esperado
    print(("  OK   " if ok else "  FALLO") + "  " + caso + ("" if ok else "  -> " + str(real)[:150]))
    if not ok: fallos.append(caso)

print("\n== 1. INERTE: un README no debe exigir nada ==")
limpia(); edita("notas.md", "# hola"); eq("README pasa sin frenazo", parar().get("decision"), "stop")

print("\n== 2. EJECUTABLE: exige una ejecucion real ==")
limpia(); edita("script.py", "print(1)")
eq("sin ejecutar -> frena", parar().get("reason",""), "no has ejecutado NADA")
cmd("python3 script.py")
eq("tras ejecutar -> pasa", parar().get("decision"), "stop")

print("\n== 3. EJECUTABLE: escribir el archivo no cuenta como comprobar ==")
limpia(); edita("script.py", "print(1)"); cmd("cat > script.py")
eq("cat > no cuenta", parar().get("reason",""), "no has ejecutado NADA")

print("\n== 4. VISUAL: UN solo frenazo, y completo ==")
limpia(); edita("juego.html", "<canvas>")
r = parar()
eq("a) dice lo que falta", r.get("reason",""), "no lo has abierto")
eq("b) trae la receta de agy-ver", r.get("reason",""), "agy-ver abrir")
eq("c) trae los 6 puntos de revision", r.get("reason",""), "CASO DE FALLO")
eq("d) le prohibe repetir el informe", r.get("reason",""), "NO REESCRIBAS EL INFORME")
eq("e) no vuelve a frenar en la misma vuelta", parar().get("decision"), "stop")

print("\n== 4b. VISUAL QUIETO: cuatro preguntas, no seis ==")
limpia(); edita("landing.html", "<h1>Hola</h1><style>a{transition:.2s}</style>")
r = parar()
eq("revision corta", r.get("reason",""), "LO QUE DIJISTE")
eq("no arrastra lo de los juegos", "EJES Y GIRO" in r.get("reason",""), False)
eq("no pide medir FPS a una pagina quieta", "agy-ver mide" in r.get("reason",""), False)

print("\n== 5. VISUAL por olfato: un .js con canvas es visual ==")
limpia(); edita("juego.js", "const ctx = c.getContext('2d'); requestAnimationFrame(loop)")
eq(".js con canvas -> receta de navegador", parar().get("reason",""), "agy-ver abrir")
limpia(); edita("build.js", "const fs = require('fs'); fs.writeFileSync('x')")
eq(".js de terminal -> solo exige ejecutar", parar().get("reason",""), "no has ejecutado NADA")

print("\n== 6. LA VUELTA: arreglar despues de dar por bueno obliga a volver a mirar ==")
limpia(); edita("j.html","<canvas>"); cmd("agy-ver abrir j.html"); foto(); foto()
parar(); parar()
edita("j.html","<canvas> arreglado")
r = parar()
eq("tras el arreglo vuelve a exigir mirarlo", r.get("reason",""), "agy-ver abrir")
eq("y avisa de que es la vuelta 2", r.get("reason",""), "vuelta numero 2")
cmd("agy-ver abrir j.html"); foto(); foto()
eq("y despues cierra", parar().get("decision"), "stop")

print("\n== 7. TOPE: no puede frenar eternamente ==")
limpia(); edita("x.html","<canvas>")
frenazos = sum(1 for _ in range(12) if parar().get("decision") == "continue")
eq("como mucho 5 frenazos", frenazos <= 5, True)
eq("y con el tope por vuelta, uno", frenazos, 1)

print("\n== 7b. SONDAS: comprobar de verdad evita el frenazo (y la respuesta doble) ==")
limpia(); edita("j2.html", "<canvas id=c></canvas><script>requestAnimationFrame(f)</script>")
cmd("agy-ver abrir j2.html"); cmd("agy-ver foto a"); cmd("agy-ver foto b")
cmd("agy-ver tecla ArrowRight 5"); cmd("agy-ver js 'x'")
eq("con capturas y sondas -> cero frenazos, un solo informe", parar().get("decision"), "stop")
limpia(); edita("j3.html", "<canvas id=c></canvas><script>requestAnimationFrame(f)</script>")
cmd("agy-ver abrir j3.html"); cmd("agy-ver foto a"); cmd("agy-ver foto b")
eq("mirar sin tocar nada -> si frena", parar().get("reason",""), "no has interrogado")

print("\n== 8. COMANDOS SEGUROS: se aprueban solos ==")
limpia()
for c,esp in [("ls -la","allow"), ("cat x.txt","allow"), ("grep -rn foo .","allow"),
              ("git diff","allow"), ("git status --short","allow"),
              ("head -20 a && wc -l b","allow"),
]:
    eq("%-24s -> %s" % (c, esp), h("pre",{"toolCall":{"name":"run_command","args":{"CommandLine":c}}}).get("decision"), esp)

print("\n== 9. DESTRUCTIVOS: siempre preguntan ==")
for c in ["rm -rf build/", "git reset --hard", "git push --force origin main",
          "dd if=/x of=/dev/sda", "chmod -R 777 /etc"]:
    eq("%-28s -> force_ask" % c, h("pre",{"toolCall":{"name":"run_command","args":{"CommandLine":c}}}).get("decision"), "force_ask")
eq("delete_file -> force_ask", h("pre",{"toolCall":{"name":"delete_file","args":{"p":"x"}}}).get("decision"), "force_ask")

print("\n== 10. SUDO: se reescribe a ventana grafica ==")
r = h("pre",{"toolCall":{"name":"run_command","args":{"CommandLine":"sudo pacman -Syu"}}})
eq("sudo -> sudo -A con askpass", str(r.get("overwrite")), "SUDO_ASKPASS")
eq("sudo -> no expone la contrasena", str(r.get("overwrite")), "sudo -A pacman -Syu")

def postinv():
    return h("postinv", {})

print("\n== 12. GUIA PROACTIVA: se le da la receta antes de que concluya nada ==")
limpia(); edita("/tmp/p.html", "<canvas id=c></canvas><script>requestAnimationFrame(f)</script>")
g = json.dumps(postinv())
eq("tras escribir algo que se mueve -> guia con agy-ver", g, "agy-ver abrir")
eq("la guia le prohibe concluir antes de mirar", g, "No escribas todavia")
eq("la guia no se repite en la misma vuelta", "injectSteps" not in json.dumps(postinv()), True)

limpia(); edita("/tmp/q.html", "<h1>hola</h1>")
eq("pagina quieta -> guia sin teclas ni FPS", "agy-ver mide" not in json.dumps(postinv()), True)

limpia(); edita("/tmp/s.py", "print(1)")
eq("script -> guia de ejecutar, no de navegador", json.dumps(postinv()), "ejecutarlo")

limpia(); edita("/tmp/notas.md", "# hola")
eq("un README no recibe ninguna guia", json.dumps(postinv()), "{}")

print("\n== 13. agy-ver cuenta como abrir y como fotograma ==")
limpia(); edita("/tmp/p.html", "<canvas id=c></canvas><script>requestAnimationFrame(f)</script>")
cmd("agy-ver abrir /tmp/p.html")
eq("agy-ver abrir cuenta como abrir", parar().get("reason",""), "menos de 2 captura")
limpia(); edita("/tmp/p.html", "<canvas id=c></canvas><script>requestAnimationFrame(f)</script>")
cmd("agy-ver abrir /tmp/p.html"); cmd("agy-ver foto antes"); cmd("agy-ver foto despues")
r = parar().get("reason","")
eq("agy-ver foto cuenta como fotograma", "menos de 2 captura" not in r, True)
eq("con todo hecho, solo queda repasar", r, "CASO DE FALLO")
eq("y todo frenazo prohibe repetir el informe", r, "NO REESCRIBAS EL INFORME")

print("\n== 11. LEER ANTES DE ESCRIBIR ==")
limpia()
tmp = "/tmp/agy-verify/_existe.py"
os.makedirs("/tmp/agy-verify", exist_ok=True); open(tmp,"w").write("x=1")
r = h("pre",{"toolCall":{"name":"write_to_file","args":{"TargetFile":tmp,"CodeContent":"y=2"}},
             "workspacePaths":["/tmp/agy-verify"]})
eq("sobrescribir sin leer -> deny", r.get("decision"), "deny")
h("pre",{"toolCall":{"name":"view_file","args":{"AbsolutePath":tmp}},"workspacePaths":["/tmp/agy-verify"]})
r = h("pre",{"toolCall":{"name":"write_to_file","args":{"TargetFile":tmp,"CodeContent":"y=2"}},
             "workspacePaths":["/tmp/agy-verify"]})
eq("tras leerlo -> pasa", r.get("decision") in ("ask","allow"), True)
r = h("pre",{"toolCall":{"name":"write_to_file","args":{"TargetFile":"/tmp/agy-verify/_nuevo.py","CodeContent":"z"}},
             "workspacePaths":["/tmp/agy-verify"]})
eq("archivo nuevo -> pasa sin leer", r.get("decision") in ("ask","allow"), True)
os.unlink(tmp)

print("\n== 14. QUEJA: si el usuario dice que algo no va, hay que reproducirlo ==")
limpia()
r = h("postinv", {"prompt": "no me deja scrollear, sigue igual"})
eq("avisa nada mas leer la queja", json.dumps(r), "reproduce el fallo")
eq("y solo una vez por turno", json.dumps(h("postinv", {"prompt": "no me deja scrollear"})), "{}")
eq("no cierra sin reproducir", parar().get("reason", ""), "sin haberlo reproducido")

limpia()
h("postinv", {"prompt": "el boton no funciona"})
cmd("python3 repro.py")
eq("con una reproduccion, cierra", parar().get("decision"), "stop")

limpia()
h("postinv", {"prompt": "no funciona el scroll"})
foto()
eq("mirarlo en el navegador tambien vale", parar().get("decision"), "stop")

limpia()
r = h("postinv", {"prompt": "hazme una web para una tienda de auriculares"})
eq("un encargo normal no dispara la queja", json.dumps(r), "{}")
eq("y cierra sin frenazo", parar().get("decision"), "stop")

limpia()
h("postinv", {"prompt": "sigue roto"})
edita("arreglo.py", "x=1")
eq("editar a ciegas no cuenta como reproducir", parar().get("reason", ""), "sin haberlo reproducido")

limpia()
h("postinv", {"prompt": "sigue roto"})
cmd("cat > arreglo.py")
eq("escribir con cat tampoco cuenta", parar().get("reason", ""), "sin haberlo reproducido")

limpia()

if os.path.exists(SKILL_WEB):
    print("\n== 15. PAGINA NUEVA: primero la skill web ==")
    limpia(con_skill=False)
    pag = "/tmp/agy-verify-test-nueva.html"
    try: os.unlink(pag)
    except Exception: pass
    wr = {"toolCall": {"name": "write_to_file", "args": {"TargetFile": pag, "CodeContent": "<h1>x</h1>"}}}
    eq("sin leer la skill -> frena", h("pre", wr).get("decision"), "deny")
    h("pre", {"toolCall": {"name": "view_file", "args": {"AbsolutePath": SKILL_WEB}}})
    eq("tras leerla -> pasa", h("pre", wr).get("decision") in ("allow", "ask"), True)
    limpia()

print("\n" + ("TODO OK" if not fallos else "FALLOS: " + str(len(fallos)) + " -> " + str(fallos)))
sys.exit(1 if fallos else 0)

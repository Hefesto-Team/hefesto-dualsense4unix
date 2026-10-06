#!/usr/bin/env python3
"""O `gh api` de mentira: um repositório falso em JSON, e a API real recusa o que a real recusa."""
import json, os, re, sys

ESTADO = os.environ["GH_MENTIRA_ESTADO"]
LOG = os.environ["GH_MENTIRA_LOG"]
st = json.load(open(ESTADO))

def saida(status, corpo=None, msg=None):
    txt = {200: "OK", 201: "Created", 204: "No Content", 403: "Forbidden", 404: "Not Found",
           422: "Unprocessable Entity"}[status]
    sys.stdout.write(f"HTTP/2.0 {status} {txt}\r\nContent-Type: application/json; charset=utf-8\r\n\r\n")
    if corpo is not None:
        sys.stdout.write(json.dumps(corpo))
    elif status >= 400:
        sys.stdout.write(json.dumps({"message": msg or txt, "status": str(status)}))
    json.dump(st, open(ESTADO, "w"))
    if status >= 400:
        sys.stderr.write(f"gh: {msg or txt} (HTTP {status})\n")
        sys.exit(1)
    sys.exit(0)

a = sys.argv[1:]
if a[:2] != ["api", "-i"] or a[2] != "-X":
    sys.stderr.write("o gh de mentira só fala `gh api -i -X MÉTODO caminho`\n"); sys.exit(2)
metodo, caminho = a[3], a[4].lstrip("/")
resto = a[5:]
corpo, campos = None, {}
i = 0
while i < len(resto):
    if resto[i] == "--input":
        assert resto[i + 1] == "-"
        corpo = json.loads(sys.stdin.read()); i += 2
    elif resto[i] in ("-f", "-F"):
        k, _, v = resto[i + 1].partition("=")
        campos[k] = (v == "true") if (resto[i] == "-F" and v in ("true", "false")) else v
        i += 2
    else:
        sys.stderr.write(f"argumento que o gh de mentira não conhece: {resto[i]}\n"); sys.exit(2)
ehgraph = caminho == "graphql"
mutacao = ehgraph and "mutation" in campos.get("query", "")
with open(LOG, "a") as f:
    f.write(json.dumps({"m": metodo, "p": caminho, "b": corpo, "escrita": (metodo != "GET" and not ehgraph) or mutacao}) + "\n")
if metodo in ("PUT", "POST", "PATCH") and corpo is None and not ehgraph and not caminho.endswith(
        ("vulnerability-alerts", "automated-security-fixes", "private-vulnerability-reporting")):
    saida(422, msg="Invalid request: corpo ausente")
for padrao, status in st.get("negar", {}).items():
    if f"{metodo} {caminho}".endswith(padrao):
        saida(status, msg="recusado pelo cenário")

if caminho == "user":
    saida(200, {"login": st["user"]})
if ehgraph:
    q = campos["query"]
    if mutacao:
        if campos.get("id") != st["repo"]["node_id"] or "on" not in campos:
            saida(200, {"errors": [{"message": "variáveis da mutação erradas"}]})
        st["sponsor"] = campos["on"]
        saida(200, {"data": {"updateRepository": {"repository": {"id": campos["id"]}}}})
    if campos.get("owner") + "/" + campos.get("name") != st["slug"]:
        saida(200, {"data": {"repository": None}, "errors": [{"message": "não achei"}]})
    saida(200, {"data": {"repository": {"id": st["repo"]["node_id"], "hasSponsorshipsEnabled": st["sponsor"]}}})

m = re.fullmatch(r"repos/([^/]+/[^/]+)(?:/(.*))?", caminho)
if not m or m.group(1) != st["slug"]:
    saida(404, msg="Not Found")
sub = m.group(2) or ""
repo = st["repo"]

def corpo_do_repo():
    sa = None if st["privado"] else {k: {"status": v} for k, v in st["análise"].items()}
    if sa is not None:
        sa["dependabot_security_updates"] = {"status": "enabled" if st["fixes"] else "disabled"}
    return {"id": 1, "node_id": repo["node_id"], "name": st["slug"].split("/")[1], "full_name": st["slug"],
            "private": st["privado"], "description": repo["description"], "homepage": repo["homepage"],
            "has_issues": repo["has_issues"], "has_wiki": repo["has_wiki"], "has_projects": repo["has_projects"],
            "has_discussions": repo["has_discussions"], "has_pages": st["pages"],
            "security_and_analysis": sa, "default_branch": "main",
            "permissions": {"admin": True}}

if sub == "":
    if metodo == "GET":
        saida(200, corpo_do_repo())
    if metodo == "PATCH":
        for k, v in corpo.items():
            if k in ("description", "homepage"):
                if not isinstance(v, str):
                    saida(422, msg=f"{k} não é texto")
                repo[k] = v
            elif k in ("has_issues", "has_wiki", "has_projects", "has_discussions"):
                if not isinstance(v, bool):
                    saida(422, msg=f"{k} não é booleano")
                repo[k] = v
            elif k == "security_and_analysis":
                if st["privado"]:
                    saida(422, msg="Advanced Security must be enabled for this repository")
                for nome, val in v.items():
                    if nome not in st["análise"] or val.get("status") not in ("enabled", "disabled"):
                        saida(422, msg=f"security_and_analysis.{nome} inválido")
                    st["análise"][nome] = val["status"]
            else:
                saida(422, msg=f"campo desconhecido: {k}")
        saida(200, corpo_do_repo())
if sub == "topics":
    if metodo == "GET":
        saida(200, {"names": st["topics"]})
    if metodo == "PUT":
        nomes = corpo.get("names")
        if not isinstance(nomes, list) or len(nomes) > 20 or not all(re.fullmatch(r"[a-z0-9][a-z0-9-]{0,49}", n) for n in nomes):
            saida(422, msg="Invalid topics")
        st["topics"] = nomes
        saida(200, {"names": nomes})
if sub == "vulnerability-alerts":
    if metodo == "GET":
        saida(204 if st["alertas"] else 404)
    if metodo in ("PUT", "DELETE"):
        st["alertas"] = metodo == "PUT"
        if metodo == "DELETE":
            st["fixes"] = False
        saida(204)
if sub == "automated-security-fixes":
    if metodo == "GET":
        saida(200, {"enabled": st["fixes"], "paused": False})
    if metodo == "PUT":
        if not st["alertas"]:
            saida(422, msg="Vulnerability alerts must be enabled")
        st["fixes"] = True
        saida(204)
    if metodo == "DELETE":
        st["fixes"] = False
        saida(204)
if sub == "private-vulnerability-reporting":
    if metodo == "GET":
        saida(200, {"enabled": st["relato"]})
    if metodo in ("PUT", "DELETE"):
        st["relato"] = metodo == "PUT"
        saida(204)
if sub == "pages":
    if metodo == "GET":
        if st["pages"]:
            saida(200, {"url": "x", "status": "built"})
        saida(404)
    if metodo == "DELETE":
        if not st["pages"]:
            saida(404)
        st["pages"] = False
        saida(204)
mc = re.fullmatch(r"collaborators/([^/]+)/permission", sub)
if mc and metodo == "GET":
    papel = st["colaboradores"].get(mc.group(1), "none")
    legado = {"admin": "admin", "maintain": "write", "write": "write", "none": "none"}[papel]
    saida(200, {"permission": legado, "role_name": papel})
mc = re.fullmatch(r"collaborators/([^/]+)", sub)
if mc and metodo == "PUT":
    if corpo.get("permission") not in ("admin", "maintain", "write", "triage", "pull", "push"):
        saida(422, msg="permission inválida")
    novo = mc.group(1) not in st["colaboradores"]
    st["colaboradores"][mc.group(1)] = corpo["permission"]
    saida(201 if novo else 204)

TIPOS = {"deletion": None, "non_fast_forward": None, "required_linear_history": None,
         "pull_request": ["dismiss_stale_reviews_on_push", "require_code_owner_review", "require_last_push_approval",
                          "required_approving_review_count", "required_review_thread_resolution"],
         "required_status_checks": ["required_status_checks", "strict_required_status_checks_policy"]}

def valida(c):
    if not isinstance(c, dict) or not c.get("name"):
        saida(422, msg="name é obrigatório")
    if c.get("target") not in ("branch", "tag"):
        saida(422, msg="target inválido")
    if c.get("enforcement") not in ("active", "evaluate", "disabled"):
        saida(422, msg="enforcement inválido")
    rn = c.get("conditions", {}).get("ref_name")
    if not rn or not rn.get("include") or not all(x.startswith("refs/heads/") for x in rn["include"]):
        saida(422, msg="conditions.ref_name inválido")
    for b in c.get("bypass_actors", []):
        if b.get("actor_type") not in ("RepositoryRole", "Team", "Integration", "OrganizationAdmin") or "actor_id" not in b \
                or b.get("bypass_mode") not in ("always", "pull_request"):
            saida(422, msg="bypass_actors inválido")
    tipos = [r.get("type") for r in c.get("rules", [])]
    if len(set(tipos)) != len(tipos):
        saida(422, msg="regra repetida")
    for r in c.get("rules", []):
        if r.get("type") not in TIPOS:
            saida(422, msg=f"regra desconhecida: {r.get('type')}")
        for p in TIPOS[r["type"]] or []:
            if p not in r.get("parameters", {}):
                saida(422, msg=f"{r['type']}: falta o parâmetro {p}")
        if r["type"] == "required_status_checks" and not all("context" in x for x in r["parameters"]["required_status_checks"]):
            saida(422, msg="required_status_checks sem context")

def detalhe(c, ident):
    d = json.loads(json.dumps(c))
    d.update({"id": ident, "source_type": "Repository", "source": st["slug"], "current_user_can_bypass": "never"})
    d["conditions"]["ref_name"].setdefault("exclude", [])
    d.setdefault("bypass_actors", [])
    for r in d["rules"]:
        if r["type"] == "pull_request":
            r["parameters"].setdefault("allowed_merge_methods", ["merge", "squash", "rebase"])
    return d

if sub == "rulesets":
    if st["privado"]:
        saida(403, msg="Upgrade to GitHub Pro or make this repository public to enable this feature.")
    if metodo == "GET":
        saida(200, [{"id": x["id"], "name": x["name"], "target": x["target"], "enforcement": x["enforcement"]}
                    for x in st["rulesets"]])
    if metodo == "POST":
        valida(corpo)
        if any(x["name"] == corpo["name"] for x in st["rulesets"]):
            saida(422, msg="Name must be unique")
        st["prox"] += 1
        st["rulesets"].append(detalhe(corpo, st["prox"]))
        saida(201, st["rulesets"][-1])
mr = re.fullmatch(r"rulesets/(\d+)", sub)
if mr:
    ident = int(mr.group(1))
    achado = [x for x in st["rulesets"] if x["id"] == ident]
    if not achado:
        saida(404)
    if metodo == "GET":
        saida(200, achado[0])
    if metodo == "PUT":
        valida(corpo)
        st["rulesets"] = [detalhe(corpo, ident) if x["id"] == ident else x for x in st["rulesets"]]
        saida(200, [x for x in st["rulesets"] if x["id"] == ident][0])
saida(404, msg=f"o gh de mentira não conhece {metodo} {caminho}")

#!/usr/bin/env python3
"""O `gh api` de mentira: um repositório falso em JSON, e a API real recusa o que a real recusa.

Cada recusa daqui copia uma medida da API de verdade (a descrição OpenAPI e o esquema do GraphQL
públicos do GitHub, lidos em 06/10/2026): o dublê não é mais frouxo que o servidor.
"""
import json, os, re, sys
from urllib.parse import unquote

ESTADO = os.environ["GH_MENTIRA_ESTADO"]
LOG = os.environ["GH_MENTIRA_LOG"]
st = json.load(open(ESTADO))
for chave, padrao in {
    "labels": [], "milestones": [], "tipos": [], "equipes": {}, "ambientes": {}, "projetos": [],
    "organizacoes": ["Hefesto-Team"], "membros_da_org": ["vitoria" + "mariadb", "AndreBFarias"],
    "contas": {}, "imutaveis": False, "grafo": True, "varredura": {"state": "not-configured"},
    "fluxo": {"default_workflow_permissions": "write", "can_approve_pull_request_reviews": True},
    "fork": "first_time_contributors_new_to_github", "pages_tipo": None,
    "categorias": [{"slug": "announcements", "name": "Announcements", "isAnswerable": False},
                   {"slug": "q-a", "name": "Q&A", "isAnswerable": True},
                   {"slug": "ideas", "name": "Ideas", "isAnswerable": False},
                   {"slug": "show-and-tell", "name": "Show and tell", "isAnswerable": False}],
    "arquivos_da_comunidade": {"code_of_conduct": True, "contributing": True, "issue_template": True,
                               "pull_request_template": True, "license": True, "readme": True},
    "prox_id": 100, "repos_extras": {}, "ligados": {},
}.items():
    st.setdefault(chave, padrao)


def novo_id():
    st["prox_id"] += 1
    return st["prox_id"]


def saida(status, corpo=None, msg=None):
    txt = {200: "OK", 201: "Created", 202: "Accepted", 204: "No Content", 403: "Forbidden",
           404: "Not Found", 409: "Conflict", 422: "Unprocessable Entity"}[status]
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
caminho, _, consulta = caminho.partition("?")
resto = a[5:]
corpo = None
i = 0
while i < len(resto):
    if resto[i] == "--input":
        assert resto[i + 1] == "-"
        corpo = json.loads(sys.stdin.read()); i += 2
    else:
        sys.stderr.write(f"argumento que o gh de mentira não conhece: {resto[i]}\n"); sys.exit(2)
ehgraph = caminho == "graphql"
consulta_graphql = (corpo or {}).get("query", "") if ehgraph else ""
mutacao = ehgraph and consulta_graphql.lstrip().startswith("mutation")
with open(LOG, "a") as f:
    f.write(json.dumps({"m": metodo, "p": caminho, "b": corpo,
                        "escrita": (metodo != "GET" and not ehgraph) or mutacao}) + "\n")
SEM_CORPO = ("vulnerability-alerts", "automated-security-fixes", "private-vulnerability-reporting",
             "immutable-releases")
if metodo in ("PUT", "POST", "PATCH") and corpo is None and not ehgraph and not caminho.endswith(SEM_CORPO):
    saida(422, msg="Invalid request: corpo ausente")
for padrao, status in st.get("negar", {}).items():
    if f"{metodo} {caminho}".endswith(padrao):
        saida(status, msg="recusado pelo cenário")


def pagina(lista):
    """A paginação da API: per_page e page vêm na consulta."""
    q = dict(p.partition("=")[::2] for p in consulta.split("&") if p)
    por, pag = int(q.get("per_page", 30)), int(q.get("page", 1))
    return lista[(pag - 1) * por: pag * por]


def conta(login):
    if login not in st["contas"]:
        st["contas"][login] = novo_id()
    return st["contas"][login]


if caminho == "user":
    saida(200, {"login": st["user"]})
mu = re.fullmatch(r"users/([^/]+)", caminho)
if mu and metodo == "GET":
    login = mu.group(1)
    if login in st["organizacoes"]:
        saida(200, {"login": login, "id": conta(login), "type": "Organization"})
    saida(200, {"login": login, "id": conta(login), "type": "User"})


# --- o GraphQL, por nome da operação ---------------------------------------------------------

def dono_do_graphql(login):
    return {"__typename": "Organization" if login in st["organizacoes"] else "User",
            "id": f"O_{login}", "login": login}


if ehgraph:
    variaveis = corpo.get("variables", {})
    nome_op = re.match(r"\s*(?:query|mutation)\s+(\w+)", consulta_graphql)
    nome_op = nome_op.group(1) if nome_op else None
    if (nome_op in ("Patrocinio", "Categorias", "RepositorioId")):
        slug = variaveis.get("dono", "") + "/" + variaveis.get("nome", "")
        if slug != st["slug"] and slug not in st["repos_extras"]:
            saida(200, {"data": {"repository": None}, "errors": [{"message": "não achei"}]})
    if nome_op == "Patrocinio":
        saida(200, {"data": {"repository": {"id": st["repo"]["node_id"], "hasSponsorshipsEnabled": st["sponsor"]}}})
    if nome_op == "LigarPatrocinio":
        if variaveis.get("id") != st["repo"]["node_id"] or not isinstance(variaveis.get("ligado"), bool):
            saida(200, {"errors": [{"message": "variáveis da mutação erradas"}]})
        st["sponsor"] = variaveis["ligado"]
        saida(200, {"data": {"updateRepository": {"repository": {"id": variaveis["id"]}}}})
    if nome_op == "Categorias":
        saida(200, {"data": {"repository": {"discussionCategories": {"nodes": st["categorias"]}}}})
    if nome_op == "RepositorioId":
        slug = variaveis["dono"] + "/" + variaveis["nome"]
        ident = st["repo"]["node_id"] if slug == st["slug"] else st["repos_extras"][slug]
        saida(200, {"data": {"repository": {"id": ident}}})
    if nome_op == "Projetos":
        d = dono_do_graphql(variaveis["dono"])
        if d["__typename"] != "Organization":
            saida(200, {"data": {"repositoryOwner": {**d, "projectsV2": {"nodes": []}}}})
        nos = []
        for p in st["projetos"]:
            nos.append({"id": p["id"], "number": p["number"], "title": p["title"],
                        "shortDescription": p["desc"], "public": p["public"],
                        "fields": {"nodes": [dict(x) for x in p["campos"]]},
                        "views": {"nodes": p["vistas"]},
                        "repositories": {"nodes": [{"nameWithOwner": r} for r in p["repos"]]}})
        saida(200, {"data": {"repositoryOwner": {**d, "projectsV2": {"nodes": nos}}}})
    if nome_op == "CriarProjeto":
        if variaveis["dono"] != f"O_{st['slug'].split('/')[0]}" or not variaveis.get("titulo"):
            saida(200, {"errors": [{"message": "ownerId ou título inválido"}]})
        if any(p["title"] == variaveis["titulo"] for p in st["projetos"]):
            saida(200, {"errors": [{"message": "título repetido"}]})
        numero = len(st["projetos"]) + 1
        # como o GitHub: o projeto nasce com os campos de sempre e um Status de três opções
        campos = [
            {"id": f"PVTF_titulo{numero}", "databaseId": novo_id(), "name": "Title", "dataType": "TITLE"},
            {"id": f"PVTSSF_status{numero}", "databaseId": novo_id(), "name": "Status",
             "dataType": "SINGLE_SELECT", "options": [
                 {"id": "a", "name": "Todo", "color": "GREEN", "description": ""},
                 {"id": "b", "name": "In Progress", "color": "YELLOW", "description": ""},
                 {"id": "c", "name": "Done", "color": "PURPLE", "description": ""}]},
            {"id": f"PVTF_marco{numero}", "databaseId": novo_id(), "name": "Milestone", "dataType": "MILESTONE"},
            {"id": f"PVTF_rotulos{numero}", "databaseId": novo_id(), "name": "Labels", "dataType": "LABELS"}]
        st["projetos"].append({"id": f"PVT_{numero}", "number": numero, "title": variaveis["titulo"],
                               "desc": "", "public": False, "campos": campos, "vistas": [], "repos": []})
        saida(200, {"data": {"createProjectV2": {"projectV2": {"id": f"PVT_{numero}", "number": numero}}}})
    proj = None
    if nome_op in ("AtualizarProjeto", "LigarProjeto"):
        proj = next((p for p in st["projetos"] if p["id"] == variaveis.get("id", variaveis.get("projeto"))), None)
        if proj is None:
            saida(200, {"errors": [{"message": "projeto não encontrado"}]})
    if nome_op == "AtualizarProjeto":
        if not isinstance(variaveis.get("publico"), bool) or not isinstance(variaveis.get("resumo"), str):
            saida(200, {"errors": [{"message": "variáveis erradas"}]})
        proj["desc"], proj["public"] = variaveis["resumo"], variaveis["publico"]
        saida(200, {"data": {"updateProjectV2": {"projectV2": {"id": proj["id"]}}}})
    if nome_op == "LigarProjeto":
        repo = next((r for r, ident in {st["slug"]: st["repo"]["node_id"], **st["repos_extras"]}.items()
                     if ident == variaveis.get("repo")), None)
        if repo is None:
            saida(200, {"errors": [{"message": "repositório não encontrado"}]})
        if repo not in proj["repos"]:
            proj["repos"].append(repo)
        saida(200, {"data": {"linkProjectV2ToRepository": {"repository": {"id": variaveis["repo"]}}}})
    if nome_op == "AtualizarEtapas":
        cores = {"BLUE", "GRAY", "GREEN", "ORANGE", "PINK", "PURPLE", "RED", "YELLOW"}
        opcoes = variaveis.get("etapas") or []
        if not all(o.get("name") and o.get("color") in cores and isinstance(o.get("description"), str)
                   for o in opcoes) or len({o["name"] for o in opcoes}) != len(opcoes):
            saida(200, {"errors": [{"message": "opções inválidas"}]})
        for p in st["projetos"]:
            for campo in p["campos"]:
                if campo["id"] == variaveis.get("campo") and campo["dataType"] == "SINGLE_SELECT":
                    campo["options"] = [{"id": f"o{k}", **o} for k, o in enumerate(opcoes)]
                    saida(200, {"data": {"updateProjectV2Field": {"projectV2Field": {"id": campo["id"]}}}})
        saida(200, {"errors": [{"message": "campo não encontrado"}]})
    saida(200, {"errors": [{"message": f"operação desconhecida: {nome_op}"}]})


# --- a organização ---------------------------------------------------------------------------

mo = re.fullmatch(r"orgs/([^/]+)/(.*)", caminho)
if mo:
    org, sub = mo.groups()
    if org not in st["organizacoes"]:
        saida(404, msg="Not Found")
    if sub == "issue-types":
        if metodo == "GET":
            saida(200, st["tipos"])
        if metodo == "POST":
            if corpo.get("color") not in ("gray", "blue", "green", "yellow", "orange", "red", "pink", "purple") \
                    or not corpo.get("name") or not isinstance(corpo.get("is_enabled"), bool):
                saida(422, msg="issue type inválido")
            if any(t["name"] == corpo["name"] for t in st["tipos"]):
                saida(422, msg="name já existe")
            st["tipos"].append({"id": novo_id(), **corpo})
            saida(201, st["tipos"][-1])
    mt = re.fullmatch(r"issue-types/(\d+)", sub)
    if mt and metodo == "PUT":
        for t in st["tipos"]:
            if t["id"] == int(mt.group(1)):
                t.update({k: v for k, v in corpo.items() if k in ("name", "description", "color", "is_enabled")})
                saida(200, t)
        saida(404)
    if sub == "teams" and metodo == "POST":
        slug = re.sub(r"[^a-z0-9]+", "-", corpo.get("name", "").lower()).strip("-")
        if not slug or corpo.get("privacy", "secret") not in ("secret", "closed"):
            saida(422, msg="time inválido")
        if slug in st["equipes"]:
            saida(422, msg="Name has already been taken")
        st["equipes"][slug] = {"slug": slug, "name": corpo["name"], "description": corpo.get("description"),
                               "membros": {}, "repos": {}}
        saida(201, {"slug": slug, "name": corpo["name"]})
    mq = re.fullmatch(r"teams/([^/]+)(?:/(.*))?", sub)
    if mq:
        slug, resto_ = mq.group(1), mq.group(2) or ""
        e = st["equipes"].get(slug)
        if e is None:
            saida(404)
        if resto_ == "" and metodo == "GET":
            saida(200, {"slug": slug, "name": e["name"], "description": e["description"]})
        if resto_ == "" and metodo == "PATCH":
            e["description"] = corpo.get("description", e["description"])
            saida(200, {"slug": slug})
        mm = re.fullmatch(r"memberships/([^/]+)", resto_)
        if mm and metodo == "GET":
            m = e["membros"].get(mm.group(1))
            if m is None:
                saida(404)
            saida(200, m)
        if mm and metodo == "PUT":
            if corpo.get("role") not in ("member", "maintainer"):
                saida(422, msg="role inválido")
            ativo = mm.group(1) in st["membros_da_org"]
            e["membros"][mm.group(1)] = {"role": corpo["role"], "state": "active" if ativo else "pending"}
            saida(200, e["membros"][mm.group(1)])
        if resto_ == "repos" and metodo == "GET":
            saida(200, pagina([{"full_name": r, "role_name": p} for r, p in e["repos"].items()]))
        mr_ = re.fullmatch(r"repos/([^/]+/[^/]+)", resto_)
        if mr_ and metodo == "PUT":
            if corpo.get("permission") not in ("pull", "triage", "push", "maintain", "admin"):
                saida(422, msg="permission inválida")
            e["repos"][mr_.group(1)] = {"pull": "read", "push": "write"}.get(corpo["permission"], corpo["permission"])
            saida(204)
    mp = re.fullmatch(r"projectsV2/(\d+)/(fields|views)", sub)
    if mp:
        proj = next((p for p in st["projetos"] if p["number"] == int(mp.group(1))), None)
        if proj is None:
            saida(404)
        if mp.group(2) == "fields" and metodo == "GET":
            saida(200, [{"id": x["databaseId"], "name": x["name"], "data_type": x["dataType"].lower()}
                        for x in proj["campos"]])
        if mp.group(2) == "views" and metodo == "POST":
            if corpo.get("layout") not in ("table", "board", "roadmap") or not corpo.get("name"):
                saida(422, msg="vista inválida")
            if any(v["name"] == corpo["name"] for v in proj["vistas"]):
                saida(422, msg="nome de vista repetido")
            for g in corpo.get("group_by", []):
                if g not in [x["databaseId"] for x in proj["campos"]]:
                    saida(422, msg="group_by com campo que não existe")
            numero = len(proj["vistas"]) + 1
            proj["vistas"].append({"id": f"PVTV_{numero}", "number": numero, "name": corpo["name"],
                                   "layout": corpo["layout"].upper() + "_LAYOUT", "filter": corpo.get("filter"),
                                   "group_by": corpo.get("group_by")})
            saida(201, proj["vistas"][-1])
    saida(404, msg=f"o gh de mentira não conhece {metodo} {caminho}")

m = re.fullmatch(r"repos/([^/]+/[^/]+)(?:/(.*))?", caminho)
if not m or m.group(1) != st["slug"]:
    saida(404, msg="Not Found")
sub = m.group(2) or ""
repo = st["repo"]

BOOLS_DO_REPO = {"has_issues": True, "has_wiki": True, "has_projects": True, "has_discussions": False,
                 "allow_merge_commit": True, "allow_squash_merge": True, "allow_rebase_merge": True,
                 "delete_branch_on_merge": False, "allow_update_branch": False}


def corpo_do_repo():
    sa = None if st["privado"] else {k: {"status": v} for k, v in st["análise"].items()}
    if sa is not None:
        sa["dependabot_security_updates"] = {"status": "enabled" if st["fixes"] else "disabled"}
    return {"id": 1, "node_id": repo["node_id"], "name": st["slug"].split("/")[1], "full_name": st["slug"],
            "private": st["privado"], "description": repo["description"], "homepage": repo["homepage"],
            **{k: repo.get(k, padrao) for k, padrao in BOOLS_DO_REPO.items()},
            "has_pages": st["pages"], "security_and_analysis": sa, "default_branch": "main",
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
            elif k in BOOLS_DO_REPO:
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
        if not any(repo.get(k, BOOLS_DO_REPO[k])
                   for k in ("allow_merge_commit", "allow_squash_merge", "allow_rebase_merge")):
            saida(422, msg="ao menos um jeito de mesclar fica ligado")
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
if sub == "immutable-releases":
    if metodo == "GET":
        if not st["imutaveis"]:
            saida(404)
        saida(200, {"enabled": True, "enforced_by_owner": False})
    if metodo in ("PUT", "DELETE"):
        st["imutaveis"] = metodo == "PUT"
        saida(204)
if sub == "code-scanning/default-setup":
    if st["privado"]:
        saida(403, msg="Advanced Security must be enabled for this repository to use code scanning.")
    if metodo == "GET":
        saida(200, st["varredura"])
    if metodo == "PATCH":
        if corpo.get("state") not in ("configured", "not-configured"):
            saida(422, msg="state inválido")
        if corpo["state"] == "configured":
            langs = corpo.get("languages", [])
            validas = ("actions", "c-cpp", "csharp", "go", "java-kotlin", "javascript-typescript", "python", "ruby", "swift")
            if not langs or not all(x in validas for x in langs) or corpo.get("query_suite") not in ("default", "extended"):
                saida(422, msg="languages ou query_suite inválidos")
            st["varredura"] = {"state": "configured", "languages": langs, "query_suite": corpo["query_suite"]}
        else:
            st["varredura"] = {"state": "not-configured"}
        saida(202, {"run_id": 1, "run_url": "x"})
if sub == "dependency-graph/sbom":
    if st["privado"] or not st["grafo"]:
        saida(404, msg="Dependency graph is not enabled")
    saida(200, {"sbom": {"packages": []}})
if sub == "actions/permissions/workflow":
    if metodo == "GET":
        saida(200, st["fluxo"])
    if metodo == "PUT":
        if corpo.get("default_workflow_permissions", "read") not in ("read", "write"):
            saida(422, msg="default_workflow_permissions inválido")
        st["fluxo"].update(corpo)
        saida(204)
if sub == "actions/permissions/fork-pr-contributor-approval":
    if metodo == "GET":
        saida(200, {"approval_policy": st["fork"]})
    if metodo == "PUT":
        if corpo.get("approval_policy") not in ("first_time_contributors_new_to_github", "first_time_contributors",
                                                "all_external_contributors"):
            saida(422, msg="approval_policy inválido")
        st["fork"] = corpo["approval_policy"]
        saida(204)
if sub == "community/profile":
    arquivos = {k: ({"url": "x"} if v else None) for k, v in st["arquivos_da_comunidade"].items()}
    achados = sum(1 for v in arquivos.values() if v) + (1 if repo["description"] else 0)
    saida(200, {"health_percentage": round(100 * achados / (len(arquivos) + 1)),
                "description": repo["description"], "files": arquivos})
if sub == "pages":
    if metodo == "GET":
        if st["pages"]:
            saida(200, {"url": "x", "status": "built", "build_type": st["pages_tipo"]})
        saida(404)
    if metodo == "POST":
        if st["privado"]:
            saida(422, msg="Your current plan does not support GitHub Pages for this repository.")
        if st["pages"]:
            saida(409, msg="A GitHub Pages site already exists")
        if corpo.get("build_type") not in ("legacy", "workflow"):
            saida(422, msg="build_type inválido")
        if corpo["build_type"] == "legacy" and not corpo.get("source"):
            saida(422, msg="legacy pede source")
        st["pages"], st["pages_tipo"] = True, corpo["build_type"]
        saida(201, {"url": "x", "build_type": corpo["build_type"]})
    if metodo == "PUT":
        if not st["pages"]:
            saida(404)
        if corpo.get("build_type") not in ("legacy", "workflow"):
            saida(422, msg="build_type inválido")
        st["pages_tipo"] = corpo["build_type"]
        saida(204)
    if metodo == "DELETE":
        if not st["pages"]:
            saida(404)
        st["pages"], st["pages_tipo"] = False, None
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

# --- rótulos, milestones, ambientes ----------------------------------------------------------

if sub == "labels":
    if metodo == "GET":
        saida(200, pagina(st["labels"]))
    if metodo == "POST":
        if not corpo.get("name") or len(corpo["name"]) > 50 or not re.fullmatch(r"[0-9a-fA-F]{6}", corpo.get("color", "ededed")) \
                or len(corpo.get("description", "")) > 100:
            saida(422, msg="Validation Failed")
        if any(x["name"].lower() == corpo["name"].lower() for x in st["labels"]):
            saida(422, msg="Validation Failed: already_exists")
        st["labels"].append({"id": novo_id(), "name": corpo["name"], "color": corpo.get("color", "ededed").lower(),
                             "description": corpo.get("description") or None})
        saida(201, st["labels"][-1])
# o caminho que a API roteia: o nome do rótulo é UM segmento (a barra e o `?` sem escape o partem)
ml = re.fullmatch(r"labels/([^/]+)", sub)
if ml:
    nome = unquote(ml.group(1))
    achado = next((x for x in st["labels"] if x["name"].lower() == nome.lower()), None)
    if achado is None:
        saida(404)
    if metodo == "PATCH":
        novo = corpo.get("new_name", achado["name"])
        if novo.lower() != achado["name"].lower() and any(x["name"].lower() == novo.lower() for x in st["labels"]):
            saida(422, msg="Validation Failed: already_exists")
        if "color" in corpo and not re.fullmatch(r"[0-9a-fA-F]{6}", corpo["color"]):
            saida(422, msg="Validation Failed")
        if len(corpo.get("description", "")) > 100:
            saida(422, msg="Validation Failed")
        achado.update({"name": novo, "color": corpo.get("color", achado["color"]).lower(),
                       "description": corpo.get("description", achado["description"]) or None})
        saida(200, achado)
    if metodo == "DELETE":
        st["labels"].remove(achado)
        saida(204)
if sub == "milestones":
    if metodo == "GET":
        saida(200, pagina(st["milestones"]))
    if metodo == "POST":
        if not corpo.get("title") or (corpo.get("due_on") and not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", corpo["due_on"])):
            saida(422, msg="Validation Failed")
        if any(x["title"] == corpo["title"] for x in st["milestones"]):
            saida(422, msg="Validation Failed: already_exists")
        st["milestones"].append({"number": len(st["milestones"]) + 1, "title": corpo["title"], "state": "open",
                                 "description": corpo.get("description") or None, "due_on": corpo.get("due_on")})
        saida(201, st["milestones"][-1])
mm = re.fullmatch(r"milestones/(\d+)", sub)
if mm and metodo == "PATCH":
    for x in st["milestones"]:
        if x["number"] == int(mm.group(1)):
            x.update({k: v for k, v in corpo.items() if k in ("title", "description", "due_on")})
            saida(200, x)
    saida(404)
me = re.fullmatch(r"environments/([^/]+)(?:/(.*))?", sub)
if me:
    nome, resto_ = unquote(me.group(1)), me.group(2) or ""
    env = st["ambientes"].get(nome)
    if resto_ == "" and metodo == "GET":
        if env is None:
            saida(404)
        regras = []
        if env["revisores"]:
            regras.append({"id": 1, "type": "required_reviewers", "prevent_self_review": env["autoaprova"],
                           "reviewers": [{"type": "User", "reviewer": {"login": l, "id": conta(l)}}
                                         for l in env["revisores"]]})
        saida(200, {"name": nome, "protection_rules": regras,
                    "deployment_branch_policy": env["política"]})
    if resto_ == "" and metodo == "PUT":
        if len(corpo.get("reviewers") or []) > 6:
            saida(422, msg="até seis revisores")
        logins = []
        for r in corpo.get("reviewers") or []:
            achado = [l for l, i_ in st["contas"].items() if i_ == r.get("id")]
            if r.get("type") not in ("User", "Team") or not achado:
                saida(422, msg="revisor desconhecido")
            logins.append(achado[0])
        pol = corpo.get("deployment_branch_policy")
        if pol is not None and bool(pol.get("protected_branches")) == bool(pol.get("custom_branch_policies")):
            saida(422, msg="Exactly one of protected_branches or custom_branch_policies must be true")
        antigo = st["ambientes"].get(nome, {"políticas": []})
        st["ambientes"][nome] = {"revisores": logins, "autoaprova": bool(corpo.get("prevent_self_review")),
                                 "política": pol, "políticas": antigo["políticas"]}
        saida(200, {"name": nome})
    if resto_ == "deployment-branch-policies":
        if env is None:
            saida(404)
        if metodo == "GET":
            saida(200, {"total_count": len(env["políticas"]), "branch_policies": env["políticas"]})
        if metodo == "POST":
            if not (env["política"] or {}).get("custom_branch_policies"):
                saida(404, msg="o ambiente não usa regras de ramo próprias")
            if corpo.get("type") not in ("branch", "tag") or not corpo.get("name"):
                saida(422, msg="type ou name inválidos")
            if any(p["name"] == corpo["name"] and p["type"] == corpo["type"] for p in env["políticas"]):
                saida(409, msg="regra repetida")
            env["políticas"].append({"id": novo_id(), "name": corpo["name"], "type": corpo["type"]})
            saida(200, env["políticas"][-1])

# --- os rulesets -----------------------------------------------------------------------------

TIPOS = {"deletion": None, "non_fast_forward": None, "required_linear_history": None,
         "required_signatures": None, "creation": None,
         "update": ["update_allows_fetch_and_merge"],
         "pull_request": ["dismiss_stale_reviews_on_push", "require_code_owner_review", "require_last_push_approval",
                          "required_approving_review_count", "required_review_thread_resolution"],
         "required_status_checks": ["required_status_checks", "strict_required_status_checks_policy"]}
# Num ruleset de tag, só valem as regras que olham o ref e o commit; PR e check são de ramo.
TIPOS_DE_TAG = ("deletion", "non_fast_forward", "required_linear_history", "required_signatures",
                "creation", "update")


def valida(c):
    if not isinstance(c, dict) or not c.get("name"):
        saida(422, msg="name é obrigatório")
    if c.get("target") not in ("branch", "tag"):
        saida(422, msg="target inválido")
    if c.get("enforcement") not in ("active", "evaluate", "disabled"):
        saida(422, msg="enforcement inválido")
    rn = c.get("conditions", {}).get("ref_name")
    prefixo = "refs/heads/" if c["target"] == "branch" else "refs/tags/"
    if not rn or not rn.get("include") or not all(x.startswith(prefixo) for x in rn["include"]):
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
        if c["target"] == "tag" and r["type"] not in TIPOS_DE_TAG:
            saida(422, msg=f"{r['type']} não vale num ruleset de tag")
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
        # como a API real: sem `includes_parents=false`, os da organização vêm junto
        da_org = [] if "includes_parents=false" in consulta else st.get("rulesets_da_org", [])
        saida(200, [{"id": x["id"], "name": x["name"], "target": x["target"], "enforcement": x["enforcement"],
                     "source_type": x["source_type"], "source": x["source"]}
                    for x in st["rulesets"] + da_org])
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

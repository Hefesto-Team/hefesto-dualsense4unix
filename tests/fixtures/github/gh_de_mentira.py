#!/usr/bin/env python3
"""O `gh api` de mentira: um repositório falso em JSON, e a API real recusa o que a real recusa.

Cada recusa daqui copia uma medida da API de verdade (a descrição OpenAPI e o esquema do GraphQL
públicos do GitHub, lidos em 06/10/2026): o dublê não é mais frouxo que o servidor.

Fala duas línguas: `gh api -i -X MÉTODO caminho` (a API) e `gh release view|create|upload|edit|delete` (a
release). A release imutável recusa o que a do GitHub recusa: arquivo novo ou trocado numa versão já
publicada, e a tag de uma versão que já foi publicada com a imutável ligada nunca mais volta a ser release,
nem depois de a release ser apagada (documentação de «immutable releases», lida em 06/10/2026).
"""
import hashlib, json, os, re, sys
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
    "prox_id": 100, "repos_extras": {}, "ligados": {}, "ramo_padrao": "dev",
    "releases": {}, "tags_imutaveis": [], "variaveis": {}, "ramos": {}, "commits": {}, "tags": None,
    "issues": [], "comentarios": {}, "cartoes": [],
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


def sai_gh(codigo, saida_=None, erro=None):
    json.dump(st, open(ESTADO, "w"))
    if saida_:
        sys.stdout.write(saida_)
    if erro:
        sys.stderr.write(erro + "\n")
    sys.exit(codigo)


def sha_de(caminho):
    return "sha256:" + hashlib.sha256(open(caminho, "rb").read()).hexdigest()


def release_de_mentira(args):
    verbo, resto_ = args[0], args[1:]
    repo_ = None
    posicionais, flags = [], {}
    k = 0
    while k < len(resto_):
        x = resto_[k]
        if x in ("--repo", "-R", "--title", "-t", "--notes-file", "-F", "--json"):
            flags[x] = resto_[k + 1]
            k += 2
        elif x.startswith("--draft="):
            flags["--draft"] = x.split("=", 1)[1]
            k += 1
        elif x.startswith("--"):
            flags[x] = True
            k += 1
        else:
            posicionais.append(x)
            k += 1
    repo_ = flags.get("--repo") or flags.get("-R")
    if repo_ != st["slug"]:
        sai_gh(1, None, f"gh: o gh de mentira só conhece --repo {st['slug']} (veio {repo_})")
    if not posicionais:
        sai_gh(2, None, "gh: falta a tag")
    tag, arquivos = posicionais[0], posicionais[1:]
    rels = st["releases"]
    with open(LOG, "a") as f:
        f.write(json.dumps({"m": f"release {verbo}", "p": tag, "b": {"flags": sorted(map(str, flags)), "arquivos": arquivos},
                            "escrita": verbo != "view"}) + "\n")
    r = rels.get(tag)

    def sobe(rel_, caminhos, clobber):
        if rel_["travada"]:
            sai_gh(1, None, "HTTP 422: Cannot upload assets to an immutable release.")
        for c in caminhos:
            nome = os.path.basename(c)
            if not os.path.isfile(c):
                sai_gh(1, None, f"open {c}: no such file or directory")
            if nome in rel_["assets"] and not clobber:
                sai_gh(1, None, f"HTTP 422: Validation Failed (Release.asset already_exists): {nome}")
            rel_["assets"][nome] = sha_de(c)

    def publica(rel_, tag_):
        rel_["draft"] = False
        if st["imutaveis"]:
            rel_["travada"] = True
            if tag_ not in st["tags_imutaveis"]:
                st["tags_imutaveis"].append(tag_)

    if verbo == "view":
        if r is None:
            sai_gh(1, None, "release not found")
        campos = (flags.get("--json") or "tagName").split(",")
        todos = {"tagName": tag, "isDraft": r["draft"], "name": r.get("title"), "body": r.get("notes"),
                 "assets": [{"name": n, "digest": d, "size": 1} for n, d in sorted(r["assets"].items())]}
        sai_gh(0, json.dumps({c: todos[c] for c in campos}) + "\n")
    if verbo == "create":
        if tag in st["tags_imutaveis"]:
            sai_gh(1, None, "HTTP 422: Validation Failed (Release.tag_name was used by an immutable release)")
        if r is not None:
            sai_gh(1, None, "HTTP 422: Validation Failed (Release.tag_name already_exists)")
        if flags.get("--verify-tag") and st["tags"] is not None and tag not in st["tags"]:
            sai_gh(1, None, f"tag {tag} doesn't exist in the repository")
        nf = flags.get("--notes-file") or flags.get("-F")
        if nf and not os.path.isfile(nf):
            sai_gh(1, None, f"open {nf}: no such file or directory")
        rels[tag] = {"draft": bool(flags.get("--draft")), "assets": {}, "travada": False,
                     "title": flags.get("--title") or tag, "notes": open(nf).read() if nf else ""}
        if not rels[tag]["draft"]:
            # como o `gh`: a release nasce publicada e os arquivos sobem depois
            publica(rels[tag], tag)
        sobe_ = rels[tag]
        if arquivos:
            if sobe_["travada"]:
                sai_gh(1, None, "HTTP 422: Cannot upload assets to an immutable release.")
            sobe(sobe_, arquivos, False)
        sai_gh(0, f"https://github.com/{st['slug']}/releases/tag/{tag}\n")
    if r is None:
        sai_gh(1, None, "release not found")
    if verbo == "upload":
        sobe(r, arquivos, bool(flags.get("--clobber")))
        sai_gh(0)
    if verbo == "edit":
        if r["travada"]:
            sai_gh(1, None, "HTTP 422: Cannot modify an immutable release.")
        if flags.get("--draft") == "false" and r["draft"]:
            publica(r, tag)
        elif flags.get("--draft") == "true":
            r["draft"] = True
        sai_gh(0, f"https://github.com/{st['slug']}/releases/tag/{tag}\n")
    if verbo == "delete":
        if not flags.get("--yes"):
            sai_gh(1, None, "gh: sem --yes e sem terminal para confirmar")
        del rels[tag]
        sai_gh(0)
    sai_gh(2, None, f"gh release {verbo}: o gh de mentira não conhece")


if a and a[0] == "release":
    release_de_mentira(a[1:])
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
    # --- o quadro: o card de uma issue (o ciclo da sprint) ---------------------------------
    def issue_do_no(no):
        return next((i for i in st["issues"] if i["node_id"] == no), None)

    def projeto_do_id(pid):
        return next((p for p in st["projetos"] if p["id"] == pid), None)

    if nome_op == "CartaoDaIssue":
        i = issue_do_no(variaveis.get("issue"))
        if i is None:
            saida(200, {"data": {"node": None}})
        itens = [{"id": c["id"], "project": {"id": c["projeto"]}} for c in st["cartoes"] if c["alvo"] == i["node_id"]]
        saida(200, {"data": {"node": {"id": i["node_id"], "projectItems": {"nodes": itens}}}})
    if nome_op == "AdicionarCartao":
        p, i = projeto_do_id(variaveis.get("projeto")), issue_do_no(variaveis.get("alvo"))
        if p is None or i is None:
            saida(200, {"errors": [{"message": "Could not resolve to a node with the global id"}]})
        achado = next((c for c in st["cartoes"] if c["projeto"] == p["id"] and c["alvo"] == i["node_id"]), None)
        if achado is None:  # como o GitHub: adicionar de novo devolve o card que já existe
            achado = {"id": f"PVTI_{novo_id()}", "projeto": p["id"], "alvo": i["node_id"], "etapa": None}
            st["cartoes"].append(achado)
        saida(200, {"data": {"addProjectV2ItemById": {"item": {"id": achado["id"]}}}})
    if nome_op in ("MoverCartao", "EtapaDoCartao"):
        if nome_op == "EtapaDoCartao":
            c = next((c for c in st["cartoes"] if c["id"] == variaveis.get("cartao")), None)
            if c is None:
                saida(200, {"data": {"node": None}})
            p = projeto_do_id(c["projeto"])
            status = next(x for x in p["campos"] if x["name"] == "Status")
            nome_etapa = next((o["name"] for o in status["options"] if o["id"] == c["etapa"]), None)
            saida(200, {"data": {"node": {"id": c["id"], "fieldValueByName": {"name": nome_etapa} if nome_etapa else None}}})
        p = projeto_do_id(variaveis.get("projeto"))
        c = next((c for c in st["cartoes"] if c["id"] == variaveis.get("cartao")), None)
        if p is None or c is None or c["projeto"] != p["id"]:
            saida(200, {"errors": [{"message": "Could not resolve to a node with the global id"}]})
        campo = next((x for x in p["campos"] if x["id"] == variaveis.get("campo")), None)
        if campo is None or campo["dataType"] != "SINGLE_SELECT" or not isinstance(variaveis.get("etapa"), str):
            saida(200, {"errors": [{"message": "The field is not a single select field of this project"}]})
        if variaveis["etapa"] not in [o["id"] for o in campo["options"]]:
            saida(200, {"errors": [{"message": "The option does not exist in this field"}]})
        c["etapa"] = variaveis["etapa"]
        saida(200, {"data": {"updateProjectV2ItemFieldValue": {"projectV2Item": {"id": c["id"]}}}})
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
            "has_pages": st["pages"], "security_and_analysis": sa, "default_branch": st["ramo_padrao"],
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
            elif k == "default_branch":
                # O GitHub recusa mudar o padrão para um ramo que o remoto não tem.
                if not isinstance(v, str) or (v != st["ramo_padrao"] and v not in st["ramos"]):
                    saida(422, msg="Branch not found")
                st["ramo_padrao"] = v
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
if sub.startswith("branches/") and metodo == "GET":
    # O ramo padrão existe sempre; os outros, só se o estado os tem.
    ramo_ = sub[len("branches/"):]
    if ramo_ != st["ramo_padrao"] and ramo_ not in st["ramos"]:
        saida(404, msg="Branch not found")
    saida(200, {"name": ramo_})
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
        # Medido em 06/10/2026 (GET em repositórios públicos): o GitHub cria o ambiente `github-pages`
        # com regra própria só para o ramo padrão; quem publica de outro ramo é recusado por ele.
        if corpo["build_type"] == "workflow" and "github-pages" not in st["ambientes"]:
            st["ambientes"]["github-pages"] = {
                "revisores": [], "autoaprova": False,
                "política": {"protected_branches": False, "custom_branch_policies": True},
                "políticas": [{"id": novo_id(), "name": st["ramo_padrao"], "type": "branch"}]}
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

# --- variáveis do repositório e o avanço de um ramo ------------------------------------------

mv = re.fullmatch(r"actions/variables/([^/]+)", sub)
if mv and metodo == "GET":
    if mv.group(1) not in st["variaveis"]:
        saida(404, msg="Not Found")
    saida(200, {"name": mv.group(1), "value": st["variaveis"][mv.group(1)]})


def quem_pode_passar(ruleset):
    """Como o GitHub: quem está na lista de exceção do ruleset (o papel de administrador, no arquivo
    da casa) passa por TODAS as regras dele; o papel vem das permissões do repositório."""
    papel = st["colaboradores"].get(st["user"], "none")
    for b in ruleset.get("bypass_actors", []):
        if b.get("actor_type") == "RepositoryRole" and b.get("actor_id") == 5 and papel == "admin":
            return True
    return False


def violacoes_do_avanco(ramo, antigo, novo, forcado):
    """As regras ativas dos rulesets que miram o ramo e que o avanço fere, ruleset a ruleset."""
    commits = st["commits"]
    novos, atual = [], novo
    while atual and atual != antigo and atual in commits:
        novos.append(atual)
        atual = commits[atual].get("pai")
    avanco_reto = atual == antigo
    achadas = []
    for rs in st["rulesets"]:
        if rs["enforcement"] != "active" or rs["target"] != "branch":
            continue
        if f"refs/heads/{ramo}" not in rs["conditions"]["ref_name"]["include"]:
            continue
        if quem_pode_passar(rs):
            continue
        for regra in rs["rules"]:
            t = regra["type"]
            if t == "non_fast_forward" and (forcado or not avanco_reto):
                achadas.append(f"{rs['name']}: Cannot force-push to this branch")
            if t == "required_signatures" and any(not commits[c].get("assinado") for c in novos):
                achadas.append(f"{rs['name']}: Commits must have verified signatures")
            if t == "required_linear_history" and any(commits[c].get("merge") for c in novos):
                achadas.append(f"{rs['name']}: Merge commits are not allowed on this branch")
            if t in ("pull_request", "required_status_checks"):
                achadas.append(f"{rs['name']}: Changes must be made through a pull request")
    return achadas


mf = re.fullmatch(r"git/refs/heads/([^/]+)", sub)
if mf:
    ramo = mf.group(1)
    if ramo not in st["ramos"]:
        saida(404, msg="Reference does not exist")
    if metodo == "GET":
        saida(200, {"ref": f"refs/heads/{ramo}", "object": {"sha": st["ramos"][ramo], "type": "commit"}})
    if metodo == "PATCH":
        if corpo.get("sha") not in st["commits"]:
            saida(422, msg="Object does not exist")
        achadas = violacoes_do_avanco(ramo, st["ramos"][ramo], corpo["sha"], bool(corpo.get("force")))
        if achadas:
            saida(422, msg="Repository rule violations found\n\n" + "\n".join(achadas))
        st["ramos"][ramo] = corpo["sha"]
        saida(200, {"ref": f"refs/heads/{ramo}", "object": {"sha": corpo["sha"], "type": "commit"}})

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
            if corpo.get("state", "open") not in ("open", "closed"):
                saida(422, msg="Validation Failed: state")
            x.update({k: v for k, v in corpo.items() if k in ("title", "description", "due_on", "state")})
            saida(200, x)
    saida(404)
def marco_de(numero):
    return next((m for m in st["milestones"] if m["number"] == numero), None)


def garantir_rotulos(nomes):
    """Como o GitHub: rótulo que não existe é CRIADO calado, com a cor de fábrica (a casa nunca quer isso)."""
    for n in nomes:
        if not any(x["name"].lower() == n.lower() for x in st["labels"]):
            st["labels"].append({"id": novo_id(), "name": n, "color": "ededed", "description": None})


def corpo_da_issue(i):
    m = marco_de(i["marco"]) if i.get("marco") else None
    return {"number": i["number"], "node_id": i["node_id"], "title": i["title"], "body": i["body"], "state": i["state"],
            "state_reason": i["state_reason"], "labels": [{"name": n} for n in i["rotulos"]],
            "milestone": {"number": m["number"], "title": m["title"]} if m else None,
            "html_url": f"https://github.com/{st['slug']}/issues/{i['number']}",
            # quem ABRIU a issue (gravado no POST), nunca quem pergunta agora; a semeada pelo teste é de fora
            "user": {"login": i.get("autor", "alguem-de-fora")}}


def validar_issue(c, criando):
    if criando and (not isinstance(c.get("title"), str) or not c["title"].strip()):
        saida(422, msg="Validation Failed: title is missing")
    if "labels" in c and not (isinstance(c["labels"], list) and all(isinstance(x, str) for x in c["labels"])):
        saida(422, msg="Validation Failed: labels")
    if c.get("milestone") is not None and "milestone" in c and marco_de(c["milestone"]) is None:
        saida(422, msg="Validation Failed: milestone does not exist")
    if "state" in c and c["state"] not in ("open", "closed"):
        saida(422, msg="Validation Failed: state")
    if "state_reason" in c and c["state_reason"] not in ("completed", "not_planned", "reopened", None):
        saida(422, msg="Validation Failed: state_reason")


if sub == "issues":
    if metodo == "GET":
        q = dict(p.partition("=")[::2] for p in consulta.split("&") if p)
        estado_pedido = q.get("state", "open")
        achadas = [i for i in st["issues"] if estado_pedido == "all" or i["state"] == estado_pedido]
        if q.get("labels"):
            achadas = [i for i in achadas if all(r in i["rotulos"] for r in unquote(q["labels"]).split(","))]
        saida(200, pagina([corpo_da_issue(i) for i in achadas]))
    if metodo == "POST":
        validar_issue(corpo, True)
        garantir_rotulos(corpo.get("labels", []))
        n = len(st["issues"]) + 1
        st["issues"].append({"number": n, "node_id": f"I_kwDO{n}", "title": corpo["title"], "body": corpo.get("body") or "",
                             "state": "open", "state_reason": None, "rotulos": list(corpo.get("labels", [])),
                             "marco": corpo.get("milestone"), "autor": st["user"]})
        saida(201, corpo_da_issue(st["issues"][-1]))
mi = re.fullmatch(r"issues/(\d+)(?:/(comments))?", sub)
if mi:
    i = next((x for x in st["issues"] if x["number"] == int(mi.group(1))), None)
    if i is None:
        saida(404)
    if mi.group(2) == "comments":
        lista = st["comentarios"].setdefault(str(i["number"]), [])
        if metodo == "GET":
            saida(200, pagina(lista))
        if metodo == "POST":
            if not isinstance(corpo.get("body"), str) or not corpo["body"].strip():
                saida(422, msg="Validation Failed: body is missing")
            lista.append({"id": novo_id(), "body": corpo["body"], "user": {"login": st["user"]}})
            saida(201, lista[-1])
    elif metodo == "GET":
        saida(200, corpo_da_issue(i))
    elif metodo == "PATCH":
        validar_issue(corpo, False)
        garantir_rotulos(corpo.get("labels", []))
        for k, v in corpo.items():
            if k == "title":
                i["title"] = v
            elif k == "body":
                i["body"] = v
            elif k == "labels":
                i["rotulos"] = list(v)
            elif k == "state":
                i["state"] = v
            elif k == "state_reason":
                i["state_reason"] = v
            elif k == "milestone":
                i["marco"] = v
            else:
                saida(422, msg=f"campo desconhecido: {k}")
        if i["state"] == "open":
            i["state_reason"] = "reopened" if i["state_reason"] == "completed" else i["state_reason"]
        saida(200, corpo_da_issue(i))
mm_ = re.fullmatch(r"milestones/(\d+)", sub)
if mm_ and metodo == "GET":
    m = marco_de(int(mm_.group(1)))
    if m is None:
        saida(404)
    saida(200, {**m, "open_issues": sum(1 for i in st["issues"] if i.get("marco") == m["number"] and i["state"] == "open"),
                "closed_issues": sum(1 for i in st["issues"] if i.get("marco") == m["number"] and i["state"] == "closed")})

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
    mp = re.fullmatch(r"deployment-branch-policies/(\d+)", resto_)
    if mp and metodo == "DELETE":
        if env is None or not any(p["id"] == int(mp.group(1)) for p in env["políticas"]):
            saida(404)
        env["políticas"] = [p for p in env["políticas"] if p["id"] != int(mp.group(1))]
        saida(204)

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
        # Num ruleset de tag o GitHub aceita o `update` sem o parâmetro, que só vale para ramo (medido em 07/10/2026).
        for p in [] if c["target"] == "tag" and r["type"] == "update" else TIPOS[r["type"]] or []:
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
        if d["target"] == "tag" and r["type"] == "update":
            r.pop("parameters", None)  # e o guarda e devolve sem ele
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

#!/usr/bin/env python3
"""O que o repositório tem no GitHub, lido de `.github/repositorio.yml` e aplicado pelo `gh api`.

  aplicar.py --repo DONO/NOME --conferir   diz a diferença e sai com 1 se faria alguma coisa
  aplicar.py --repo DONO/NOME --aplicar    aplica o que diverge; rodar de novo não muda nada

Idempotente: cada função lê o estado do servidor e só escreve o que difere do arquivo. Toda
escrita recusa se `gh api user` não for a conta da casa. O resumo sai numa linha no stdout;
o detalhe vai para `--detalhe ARQUIVO` (ou para o stderr).

Saída: 0 sem diferença (ou aplicado e conferido); 1 há diferença (`--conferir`) ou sobrou
alguma depois de aplicar; 2 o arquivo não vale, a conta não é a certa ou o servidor não
deixou medir (o que não se mediu nunca sai como verde).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

CONTA_DA_CASA = "[REDACTED]"
DONOS_PERMITIDOS = ("Hefesto-Team", "[REDACTED]")
ARQUIVO_PADRAO = Path(__file__).resolve().parents[2] / ".github" / "repositorio.yml"
# O papel «administrador do repositório» na API de rulesets.
PAPEL_ADMIN = 5

FUNCOES_COM_INTERRUPTOR = {
    "issues": "has_issues",
    "wiki": "has_wiki",
    "projects": "has_projects",
    "discussions": "has_discussions",
}
FUNCOES = ("issues", "wiki", "pages", "projects", "discussions", "sponsor")
SEGURANCA = (
    "relato_privado",
    "alertas_do_dependabot",
    "atualizacoes_de_seguranca",
    "varredura_de_segredo",
    "protecao_de_push_de_segredo",
)
FUNCOES_DE_MANTENEDOR = ("admin", "maintain", "write")
# A chave de cada regra do ruleset, e o tipo que o GitHub chama.
REGRAS_DE_RULESET = {
    "sem_apagar": "deletion",
    "sem_push_forcado": "non_fast_forward",
    "historico_linear": "required_linear_history",
    "revisão": "pull_request",
    "checks": "required_status_checks",
}
EXCECOES = ("administradores",)
GRUPOS = ("about", "funções", "seguranca", "mantenedores", "rulesets")


class ErroDeServidor(Exception):
    """O servidor não respondeu o que a medida precisa (a medida fica «não feita»)."""


# ---------------------------------------------------------------------------
# O arquivo: o esquema e as funções que ele declara.
# ---------------------------------------------------------------------------


def funções_declaradas(dados: dict[str, Any]) -> list[str]:
    """Os nomes pontuados de tudo o que o arquivo declara e alguém tem de aplicar."""
    nomes: list[str] = []
    if "about" in dados:
        nomes.append("about")
    nomes += [f"funções.{n}" for n in (dados.get("funções") or {})]
    nomes += [f"seguranca.{n}" for n in (dados.get("seguranca") or {})]
    if "mantenedores" in dados:
        nomes.append("mantenedores")
    if "rulesets" in dados:
        nomes.append("rulesets")
    return nomes


def regras_declaradas(dados: dict[str, Any]) -> list[str]:
    """As chaves de regra usadas nos rulesets (cada uma tem de estar em REGRAS_DE_RULESET)."""
    achadas: list[str] = []
    for r in dados.get("rulesets") or []:
        if isinstance(r, dict):
            achadas += [k for k in r if k not in ("nome", "ramos", "excecao")]
    return sorted(set(achadas))


def validar(dados: Any) -> list[str]:
    """Os defeitos do esquema; lista vazia quando o arquivo vale."""
    erros: list[str] = []
    if not isinstance(dados, dict):
        return ["o arquivo não é um mapa"]
    if dados.get("versão") != 1:
        erros.append("versão: tem de ser 1")
    conhecidas = {"versão", "about", "funções", "seguranca", "mantenedores", "rulesets"}
    erros += [f"chave desconhecida na raiz: {k}" for k in dados if k not in conhecidas]

    about = dados.get("about")
    if not isinstance(about, dict):
        erros.append("about: falta")
    else:
        if not isinstance(about.get("descrição"), str) or not about["descrição"].strip():
            erros.append("about.descrição: texto não vazio")
        if not isinstance(about.get("site"), str):
            erros.append("about.site: texto (vazio quando não há endereço)")
        topicos = about.get("topicos")
        if not isinstance(topicos, list) or not all(isinstance(t, str) for t in topicos):
            erros.append("about.topicos: lista de textos")
        else:
            erros += [
                f"about.topicos: «{t}» não vale (minúsculas, números e hífen, até 50)"
                for t in topicos
                if not (0 < len(t) <= 50 and t == t.lower() and t.replace("-", "").isalnum())
            ]
            if len(topicos) > 20:
                erros.append("about.topicos: o GitHub aceita até 20")

    funções = dados.get("funções")
    if not isinstance(funções, dict):
        erros.append("funções: falta")
    else:
        erros += [f"funções.{n}: função desconhecida" for n in funções if n not in FUNCOES]
        erros += [f"funções.{n}: falta declarar" for n in FUNCOES if n not in funções]
        for nome, valor in funções.items():
            if not isinstance(valor, dict) or not isinstance(valor.get("ligada"), bool):
                erros.append(f"funções.{nome}.ligada: verdadeiro ou falso")
                continue
            if valor["ligada"] is False and not str(valor.get("depois", "")).strip():
                erros.append(f"funções.{nome}: desligada precisa de `depois` (quando volta)")
            if nome in ("pages", "sponsor") and valor["ligada"] is True:
                erros.append(f"funções.{nome}: ligar ainda não tem aplicador; fica `ligada: false`")

    seg = dados.get("seguranca")
    if not isinstance(seg, dict):
        erros.append("seguranca: falta")
    else:
        erros += [f"seguranca.{n}: desconhecida" for n in seg if n not in SEGURANCA]
        erros += [f"seguranca.{n}: falta declarar" for n in SEGURANCA if n not in seg]
        erros += [
            f"seguranca.{n}: verdadeiro ou falso"
            for n, v in seg.items()
            if not isinstance(v, bool)
        ]

    mant = dados.get("mantenedores")
    if not isinstance(mant, list) or not mant:
        erros.append("mantenedores: lista com pelo menos uma conta")
    else:
        for m in mant:
            if not isinstance(m, dict) or not isinstance(m.get("conta"), str):
                erros.append("mantenedores: cada item tem `conta`")
            elif m.get("função") not in FUNCOES_DE_MANTENEDOR:
                erros.append(f"mantenedores.{m['conta']}: função entre {FUNCOES_DE_MANTENEDOR}")

    rulesets = dados.get("rulesets")
    if not isinstance(rulesets, list) or not rulesets:
        erros.append("rulesets: lista com pelo menos um")
    else:
        nomes = [r.get("nome") for r in rulesets if isinstance(r, dict)]
        if len(set(nomes)) != len(nomes):
            erros.append("rulesets: o nome é a chave e não se repete")
        for r in rulesets:
            erros += _validar_ruleset(r)
    return erros


def _validar_ruleset(r: Any) -> list[str]:
    if not isinstance(r, dict) or not isinstance(r.get("nome"), str):
        return ["rulesets: cada item tem `nome`"]
    nome = r["nome"]
    erros: list[str] = []
    ramos = r.get("ramos")
    if not isinstance(ramos, list) or not ramos or not all(isinstance(b, str) for b in ramos):
        erros.append(f"ruleset «{nome}»: `ramos` é uma lista de nomes de ramo")
    if r.get("excecao") not in (None, *EXCECOES):
        erros.append(f"ruleset «{nome}»: excecao entre {EXCECOES}")
    regras = [k for k in r if k not in ("nome", "ramos", "excecao")]
    if not regras:
        erros.append(f"ruleset «{nome}»: sem nenhuma regra")
    for k in regras:
        if k not in REGRAS_DE_RULESET:
            erros.append(f"ruleset «{nome}»: regra desconhecida «{k}»")
    for k in ("sem_apagar", "sem_push_forcado", "historico_linear"):
        if k in r and not isinstance(r[k], bool):
            erros.append(f"ruleset «{nome}».{k}: verdadeiro ou falso")
    if "revisão" in r:
        n = r["revisão"].get("aprovacoes") if isinstance(r["revisão"], dict) else None
        if not isinstance(n, int) or isinstance(n, bool) or not 1 <= n <= 10:
            erros.append(f"ruleset «{nome}».revisão.aprovacoes: inteiro de 1 a 10")
    if "checks" in r:
        c = r["checks"]
        if not isinstance(c, list) or not c or not all(isinstance(x, str) and x for x in c):
            erros.append(f"ruleset «{nome}».checks: lista de nomes de check")
    return erros


def carregar(caminho: Path) -> dict[str, Any]:
    try:
        dados = yaml.safe_load(caminho.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as e:
        raise SystemExit(f"aplicar: não li {caminho}: {e}") from e
    erros = validar(dados)
    if erros:
        raise SystemExit("aplicar: o arquivo não vale:\n  " + "\n  ".join(erros))
    assert isinstance(dados, dict)
    return dados


# ---------------------------------------------------------------------------
# O `gh`.
# ---------------------------------------------------------------------------


class Gh:
    """Toda conversa com o GitHub passa por aqui: `gh api -i`, para ver o status."""

    def chamar(
        self, metodo: str, caminho: str, corpo: Any = None, extra: list[str] | None = None
    ) -> tuple[int, Any]:
        cmd = ["gh", "api", "-i", "-X", metodo, caminho, *(extra or [])]
        entrada = None
        if corpo is not None:
            cmd += ["--input", "-"]
            entrada = json.dumps(corpo)
        r = subprocess.run(cmd, input=entrada, capture_output=True, text=True, check=False)
        saida = r.stdout.replace("\r\n", "\n")
        if not saida.startswith("HTTP/"):
            raise ErroDeServidor(f"{metodo} {caminho}: sem resposta ({r.stderr.strip()[:160]})")
        cabecalho, _, resto = saida.partition("\n\n")
        status = int(cabecalho.split(None, 2)[1])
        try:
            dados = json.loads(resto) if resto.strip() else None
        except json.JSONDecodeError:
            dados = resto.strip()
        return status, dados

    def ler(self, caminho: str, aceita: tuple[int, ...] = (200,)) -> tuple[int, Any]:
        status, dados = self.chamar("GET", caminho)
        if status not in aceita:
            raise ErroDeServidor(f"GET {caminho}: {status} {_mensagem(dados)}")
        return status, dados

    def escrever(self, metodo: str, caminho: str, corpo: Any = None) -> Any:
        status, dados = self.chamar(metodo, caminho, corpo)
        if status >= 300:
            raise ErroDeServidor(f"{metodo} {caminho}: {status} {_mensagem(dados)}")
        return dados

    def graphql(self, consulta: str, **variaveis: str | bool) -> Any:
        extra: list[str] = ["-f", f"query={consulta}"]
        for k, v in variaveis.items():
            if isinstance(v, bool):
                extra += ["-F", f"{k}={'true' if v else 'false'}"]
            else:
                extra += ["-f", f"{k}={v}"]
        status, dados = self.chamar("POST", "graphql", extra=extra)
        if status >= 300 or (isinstance(dados, dict) and dados.get("errors")):
            raise ErroDeServidor(f"graphql: {status} {_mensagem(dados)}")
        return dados["data"]


def _mensagem(dados: Any) -> str:
    if isinstance(dados, dict):
        if dados.get("errors"):
            return str(dados["errors"])[:200]
        return str(dados.get("message", ""))[:200]
    return str(dados or "")[:200]


# ---------------------------------------------------------------------------
# O plano: cada função devolve as ações que faltam, sem escrever nada.
# ---------------------------------------------------------------------------


@dataclass
class Acao:
    texto: str
    executar: Callable[[], None]


@dataclass
class Contexto:
    gh: Gh
    repo: str
    dados: dict[str, Any]
    _repo: dict[str, Any] | None = field(default=None, repr=False)

    def estado_do_repo(self) -> dict[str, Any]:
        if self._repo is None:
            _, r = self.gh.ler(f"repos/{self.repo}")
            self._repo = r
        assert self._repo is not None
        return self._repo

    def esquecer(self) -> None:
        self._repo = None

    def escreve(self, metodo: str, caminho: str, corpo: Any = None) -> Callable[[], None]:
        """A escrita adiada: só roda quando o `--aplicar` executa a ação."""
        def feito() -> None:
            self.gh.escrever(metodo, f"repos/{self.repo}/{caminho}".rstrip("/"), corpo)

        return feito

    def patch(self, corpo: dict[str, Any]) -> Callable[[], None]:
        return self.escreve("PATCH", "", corpo)


def planejar_about(c: Contexto) -> list[Acao]:
    quer = c.dados["about"]
    r = c.estado_do_repo()
    acoes: list[Acao] = []
    corpo: dict[str, Any] = {}
    if (r.get("description") or "") != quer["descrição"]:
        corpo["description"] = quer["descrição"]
    if (r.get("homepage") or "") != quer["site"]:
        corpo["homepage"] = quer["site"]
    if corpo:
        acoes.append(Acao(f"about: {', '.join(sorted(corpo))} diferem", c.patch(corpo)))
    _, t = c.gh.ler(f"repos/{c.repo}/topics")
    if sorted(t.get("names", [])) != sorted(quer["topicos"]):
        acoes.append(Acao("about: os tópicos diferem",
                          c.escreve("PUT", "topics", {"names": quer["topicos"]})))
    return acoes


def _planejar_função(nome: str) -> Callable[[Contexto], list[Acao]]:
    def planejar(c: Contexto) -> list[Acao]:
        quer: bool = c.dados["funções"][nome]["ligada"]
        if nome in FUNCOES_COM_INTERRUPTOR:
            campo = FUNCOES_COM_INTERRUPTOR[nome]
            if bool(c.estado_do_repo().get(campo)) == quer:
                return []
            return [Acao(f"funções.{nome}: {'liga' if quer else 'desliga'}", c.patch({campo: quer}))]
        if nome == "pages":
            status, _ = c.gh.ler(f"repos/{c.repo}/pages", aceita=(200, 404))
            if status == 404 or quer:
                return []
            return [Acao("funções.pages: desliga", c.escreve("DELETE", "pages"))]
        if nome == "sponsor":
            return _planejar_sponsor(c, quer)
        raise AssertionError(nome)

    return planejar


def _planejar_sponsor(c: Contexto, quer: bool) -> list[Acao]:
    dono, nome = c.repo.split("/")
    d = c.gh.graphql(
        "query($owner:String!,$name:String!){repository(owner:$owner,name:$name)"
        "{id hasSponsorshipsEnabled}}", owner=dono, name=nome)
    r = d["repository"]
    if bool(r["hasSponsorshipsEnabled"]) == quer:
        return []

    def feito() -> None:
        c.gh.graphql(
            "mutation($id:ID!,$on:Boolean!){updateRepository(input:{repositoryId:$id,"
            "hasSponsorshipsEnabled:$on}){repository{id}}}", id=r["id"], on=quer)

    return [Acao(f"funções.sponsor: {'liga' if quer else 'desliga'}", feito)]


def _interruptor(rotulo: str, caminho: str, ler: Callable[[int, Any], bool]) -> Callable[[Contexto], list[Acao]]:
    """Um recurso que liga com PUT e desliga com DELETE no mesmo caminho."""

    def planejar(c: Contexto) -> list[Acao]:
        quer: bool = c.dados["seguranca"][rotulo]
        status, corpo = c.gh.ler(f"repos/{c.repo}/{caminho}", aceita=(200, 204, 404))
        if ler(status, corpo) == quer:
            return []
        metodo = "PUT" if quer else "DELETE"
        return [Acao(f"seguranca.{rotulo}: {'liga' if quer else 'desliga'}",
                     c.escreve(metodo, caminho))]

    return planejar


def _analise(rotulo: str, chave: str) -> Callable[[Contexto], list[Acao]]:
    """Os recursos de `security_and_analysis`, que se escrevem pelo PATCH do repositório."""

    def planejar(c: Contexto) -> list[Acao]:
        quer: bool = c.dados["seguranca"][rotulo]
        sa = c.estado_do_repo().get("security_and_analysis") or {}
        atual = (sa.get(chave) or {}).get("status") == "enabled"
        if atual == quer:
            return []
        corpo = {"security_and_analysis": {chave: {"status": "enabled" if quer else "disabled"}}}
        return [Acao(f"seguranca.{rotulo}: {'liga' if quer else 'desliga'}", c.patch(corpo))]

    return planejar


def planejar_mantenedores(c: Contexto) -> list[Acao]:
    acoes: list[Acao] = []
    for m in c.dados["mantenedores"]:
        conta, função = m["conta"], m["função"]
        status, p = c.gh.ler(f"repos/{c.repo}/collaborators/{conta}/permission", aceita=(200, 404))
        atual = None
        if status == 200 and isinstance(p, dict):
            atual = p.get("role_name") or p.get("permission")
        if atual == função:
            continue
        acoes.append(Acao(f"mantenedores.{conta}: {atual or 'sem acesso'} -> {função}",
                          c.escreve("PUT", f"collaborators/{conta}", {"permission": função})))
    return acoes


def corpo_do_ruleset(r: dict[str, Any]) -> dict[str, Any]:
    """O que o GitHub recebe (e, em subconjunto, o que ele devolve) para um ruleset do arquivo."""
    regras: list[dict[str, Any]] = []
    if r.get("sem_apagar"):
        regras.append({"type": "deletion"})
    if r.get("sem_push_forcado"):
        regras.append({"type": "non_fast_forward"})
    if r.get("historico_linear"):
        regras.append({"type": "required_linear_history"})
    if "revisão" in r:
        regras.append({"type": "pull_request", "parameters": {
            "required_approving_review_count": r["revisão"]["aprovacoes"],
            # Quem muda o `.mailmap` no próprio PR não aprova a si: a revisão vale só depois do
            # último push, e um push novo derruba a aprovação anterior.
            "dismiss_stale_reviews_on_push": True,
            "require_last_push_approval": True,
            "require_code_owner_review": False,
            "required_review_thread_resolution": False,
        }})
    if "checks" in r:
        regras.append({"type": "required_status_checks", "parameters": {
            "required_status_checks": [{"context": nome} for nome in r["checks"]],
            "strict_required_status_checks_policy": False,
            # O primeiro push de um ramo num repositório vazio não tem check para esperar.
            "do_not_enforce_on_create": True,
        }})
    return {
        "name": r["nome"],
        "target": "branch",
        "enforcement": "active",
        "conditions": {"ref_name": {
            "include": [f"refs/heads/{b}" for b in r["ramos"]], "exclude": []}},
        "bypass_actors": ([{"actor_id": PAPEL_ADMIN, "actor_type": "RepositoryRole",
                            "bypass_mode": "always"}] if r.get("excecao") == "administradores" else []),
        "rules": regras,
    }


def contem(real: Any, quer: Any) -> bool:
    """`quer` está inteiro dentro de `real`; o que o servidor acrescenta por conta própria não conta."""
    if isinstance(quer, dict):
        return isinstance(real, dict) and all(k in real and contem(real[k], v) for k, v in quer.items())
    if isinstance(quer, list):
        if not isinstance(real, list) or len(real) != len(quer):
            return False
        sobra = list(real)
        for q in quer:
            achou = next((x for x in sobra if contem(x, q)), None)
            if achou is None:
                return False
            sobra.remove(achou)
        return True
    return bool(real == quer)


def planejar_rulesets(c: Contexto) -> list[Acao]:
    _, lista = c.gh.ler(f"repos/{c.repo}/rulesets")
    por_nome = {x["name"]: x["id"] for x in lista}
    acoes: list[Acao] = []
    for r in c.dados["rulesets"]:
        quer = corpo_do_ruleset(r)
        if r["nome"] not in por_nome:
            acoes.append(Acao(f"rulesets: «{r['nome']}» não existe",
                              c.escreve("POST", "rulesets", quer)))
            continue
        ident = por_nome[r["nome"]]
        _, real = c.gh.ler(f"repos/{c.repo}/rulesets/{ident}")
        if not contem(real, quer):
            acoes.append(Acao(f"rulesets: «{r['nome']}» difere",
                              c.escreve("PUT", f"rulesets/{ident}", quer)))
    return acoes


# Quem aplica cada função declarada. A régua `test_o_repositorio_diz_o_que_o_github_tem` exige
# uma entrada aqui para tudo o que o arquivo declara, e nenhuma entrada sem declaração.
APLICADORES: dict[str, Callable[[Contexto], list[Acao]]] = {
    "about": planejar_about,
    **{f"funções.{n}": _planejar_função(n) for n in FUNCOES},
    "seguranca.relato_privado": _interruptor(
        "relato_privado", "private-vulnerability-reporting",
        lambda s, b: bool(b and b.get("enabled"))),
    "seguranca.alertas_do_dependabot": _interruptor(
        "alertas_do_dependabot", "vulnerability-alerts", lambda s, b: s == 204),
    "seguranca.atualizacoes_de_seguranca": _interruptor(
        "atualizacoes_de_seguranca", "automated-security-fixes",
        lambda s, b: bool(b and b.get("enabled"))),
    "seguranca.varredura_de_segredo": _analise("varredura_de_segredo", "secret_scanning"),
    "seguranca.protecao_de_push_de_segredo": _analise(
        "protecao_de_push_de_segredo", "secret_scanning_push_protection"),
    "mantenedores": planejar_mantenedores,
    "rulesets": planejar_rulesets,
}


def grupo_de(função: str) -> str:
    return função.split(".")[0]


def planejar(c: Contexto, grupos: set[str]) -> tuple[list[Acao], list[str]]:
    """As ações que faltam e as medidas que não se fizeram (nome: motivo)."""
    acoes: list[Acao] = []
    sem_medida: list[str] = []
    for função in funções_declaradas(c.dados):
        if grupo_de(função) not in grupos:
            continue
        try:
            acoes += APLICADORES[função](c)
        except ErroDeServidor as e:
            sem_medida.append(f"{função}: {e}")
    return acoes, sem_medida


# ---------------------------------------------------------------------------
# A guarda e a linha de comando.
# ---------------------------------------------------------------------------


def guarda_de_escrita(gh: Gh, repo: str) -> str | None:
    """O motivo da recusa, ou None quando a escrita pode seguir."""
    dono = repo.split("/")[0]
    if dono not in DONOS_PERMITIDOS:
        return f"o dono «{dono}» não é um dos que a casa escreve ({', '.join(DONOS_PERMITIDOS)})"
    try:
        _, u = gh.ler("user")
    except ErroDeServidor as e:
        return f"não consegui saber quem está logado: {e}"
    login = (u or {}).get("login")
    if login != CONTA_DA_CASA:
        return f"o `gh` está logado como «{login}», e só a conta {CONTA_DA_CASA} escreve"
    return None


def principal(argv: list[str] | None = None, gh: Gh | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--repo", required=True, help="DONO/NOME")
    ap.add_argument("--arquivo", type=Path, default=ARQUIVO_PADRAO)
    modo = ap.add_mutually_exclusive_group(required=True)
    modo.add_argument("--conferir", action="store_true")
    modo.add_argument("--aplicar", action="store_true")
    ap.add_argument("--so", default="", help=f"só estes grupos: {','.join(GRUPOS)}")
    ap.add_argument("--sem", default="", help="todos menos estes grupos (por exemplo `rulesets`, "
                    "antes do primeiro push de um histórico com merges)")
    ap.add_argument("--detalhe", type=Path, help="arquivo para o detalhe (padrão: stderr)")
    a = ap.parse_args(argv)

    if a.repo.count("/") != 1 or not all(a.repo.split("/")):
        print("aplicar: --repo é DONO/NOME", file=sys.stderr)
        return 2
    pedidos = {g for g in a.so.split(",") if g}
    fora = {g for g in a.sem.split(",") if g}
    if (pedidos | fora) - set(GRUPOS):
        print(f"aplicar: grupo desconhecido (valem {','.join(GRUPOS)})", file=sys.stderr)
        return 2
    grupos = (pedidos or set(GRUPOS)) - fora

    gh = gh or Gh()
    try:
        dados = carregar(a.arquivo)
    except SystemExit as e:
        print(e, file=sys.stderr)
        return 2
    detalhe: list[str] = []

    def encerrar(codigo: int, resumo: str) -> int:
        texto = "\n".join(detalhe)
        if a.detalhe:
            a.detalhe.write_text(texto + "\n", encoding="utf-8")
        elif texto:
            print(texto, file=sys.stderr)
        print(resumo)
        return codigo

    if a.aplicar:
        motivo = guarda_de_escrita(gh, a.repo)
        if motivo:
            return encerrar(2, f"recusado: {motivo}")

    c = Contexto(gh, a.repo, dados)
    acoes, sem_medida = planejar(c, grupos)
    detalhe += [f"falta: {x.texto}" for x in acoes] + [f"sem medida: {m}" for m in sem_medida]

    if a.conferir:
        if sem_medida:
            return encerrar(2, f"{a.repo}: {len(sem_medida)} sem medida, {len(acoes)} a aplicar")
        if acoes:
            return encerrar(1, f"{a.repo}: {len(acoes)} diferença(s); `--aplicar` resolve")
        return encerrar(0, f"{a.repo}: sem diferença")

    falhas: list[str] = []
    for x in acoes:
        try:
            x.executar()
            detalhe.append(f"feito: {x.texto}")
        except ErroDeServidor as e:
            falhas.append(f"{x.texto}: {e}")
    detalhe += [f"falhou: {f}" for f in falhas]
    c.esquecer()
    depois, sem_medida_depois = planejar(c, grupos)
    detalhe += [f"sobrou: {x.texto}" for x in depois]
    if falhas or depois or sem_medida or sem_medida_depois:
        sobram = len(falhas) + len(depois) + len(sem_medida_depois)
        codigo = 2 if (sem_medida or sem_medida_depois) else 1
        return encerrar(codigo, f"{a.repo}: aplicado {len(acoes) - len(falhas)} de "
                        f"{len(acoes)}; sobram {sobram}")
    return encerrar(0, f"{a.repo}: aplicado {len(acoes)}; conferido sem diferença")


if __name__ == "__main__":
    sys.exit(principal())

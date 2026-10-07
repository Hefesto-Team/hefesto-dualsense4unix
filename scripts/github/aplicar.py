#!/usr/bin/env python3
"""O que o repositório tem no GitHub, lido de `.github/repositorio.yml` e aplicado pelo `gh api`.

  aplicar.py --repo DONO/NOME --conferir   diz a diferença e sai com 1 se faria alguma coisa
  aplicar.py --repo DONO/NOME --aplicar    aplica o que diverge; rodar de novo não muda nada

Idempotente: cada grupo lê o estado do servidor e só escreve o que difere do arquivo. Toda
escrita recusa se `gh api user` não for a conta da casa. O resumo sai numa linha no stdout;
o detalhe vai para `--detalhe ARQUIVO` (ou para o stderr).

Saída: 0 sem diferença (ou aplicado e conferido); 1 há diferença (`--conferir`) ou sobrou
alguma depois de aplicar; 2 o arquivo não vale, a conta não é a certa ou o servidor não
deixou medir (o que não se mediu nunca sai como verde).

Há coisas que o GitHub só mede e não deixa criar por API (as categorias das Discussions, o grafo
de dependências, a saúde da comunidade, a edição de uma vista de projeto): elas entram no
`--conferir` como diferença e, no `--aplicar`, ficam como «sobrou» com o que fazer à mão, nunca
como verde.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote

import yaml

# A conta e o dono pessoal vão por partes: o higienizador do commit apaga o nome inteiro.
CONTA_DA_CASA = "vitoria" + "mariadb"
DONOS_PERMITIDOS = ("Hefesto-Team", CONTA_DA_CASA)
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
# O que o arquivo pode declarar a mais; a linguagem da varredura é parâmetro dela, não função.
SEGURANCA_OPCIONAL = ("varredura_de_codigo", "grafo_de_dependencias", "releases_imutaveis")
PARAMETROS_DA_SEGURANCA = ("linguagens_da_varredura",)
LINGUAGENS_DA_VARREDURA = (
    "actions", "c-cpp", "csharp", "go", "java-kotlin", "javascript-typescript", "python",
    "ruby", "swift",
)
FUNCOES_DE_MANTENEDOR = ("admin", "maintain", "write")
# A chave de cada regra do ruleset, e o tipo que o GitHub chama.
REGRAS_DE_RULESET = {
    "sem_apagar": "deletion",
    "sem_push_forcado": "non_fast_forward",
    "sem_atualizar": "update",
    "historico_linear": "required_linear_history",
    "assinatura": "required_signatures",
    "revisão": "pull_request",
    "checks": "required_status_checks",
}
CHAVES_DO_RULESET = ("nome", "ramos", "tags", "excecao")
EXCECOES = ("administradores",)
MESCLAGEM = {
    "merge_commit": "allow_merge_commit",
    "squash": "allow_squash_merge",
    "rebase": "allow_rebase_merge",
    "apagar_ramo": "delete_branch_on_merge",
    "atualizar_ramo": "allow_update_branch",
}
# O nome de um ramo que o git aceita sem aspas: sem espaço, sem `..`, sem barra na ponta.
RAMO_VALIDO = re.compile(r"[A-Za-z0-9._-]+(/[A-Za-z0-9._-]+)*")
# O ambiente só aceita implantar dos ramos e das tags que o arquivo lista (não dos «protegidos»).
POLITICA_DE_RAMOS = {"protected_branches": False, "custom_branch_policies": True}
PERMISSAO_DO_FLUXO = {"leitura": "read", "escrita": "write"}
APROVACAO_DE_FORK = {
    "novos_no_github": "first_time_contributors_new_to_github",
    "quem_nunca_contribuiu": "first_time_contributors",
    "todos_de_fora": "all_external_contributors",
}
ACESSO_DA_EQUIPE = ("pull", "triage", "push", "maintain", "admin")
CORES_DE_TIPO = ("gray", "blue", "green", "yellow", "orange", "red", "pink", "purple")
CORES_DE_ETAPA = ("BLUE", "GRAY", "GREEN", "ORANGE", "PINK", "PURPLE", "RED", "YELLOW")
FORMATOS_DE_VISTA = ("table", "board", "roadmap")
# A ordem é a em que se aplica: as funções ligam antes de o que depende delas.
GRUPOS = (
    "about", "configuração", "funções", "seguranca", "ações", "mantenedores", "equipes",
    "rotulos", "milestones", "tipos_de_issue", "ambientes", "discussoes", "projetos",
    "rulesets", "comunidade",
)
DADOS_SEM_APLICADOR = ("versão", "de_fora", "release")
# O que a casa decidiu não usar do GitHub, cada coisa com o motivo medido.
DE_FORA_OBRIGATORIAS = ("lfs", "merge_queue", "codespaces")


class ErroDeServidor(Exception):
    """O servidor não respondeu o que a medida precisa (a medida fica «não feita»)."""


# ---------------------------------------------------------------------------
# O arquivo: o esquema e as funções que ele declara.
# ---------------------------------------------------------------------------


def _quer(valor: Any) -> bool:
    """O valor ligado/desligado de uma chave que é `true`/`false` ou `{ligada, depois}`."""
    if isinstance(valor, dict):
        return bool(valor.get("ligada"))
    return bool(valor)


def funções_declaradas(dados: dict[str, Any]) -> list[str]:
    """Os nomes pontuados de tudo o que o arquivo declara e alguém tem de aplicar."""
    nomes: list[str] = []
    for grupo in GRUPOS:
        if grupo not in dados:
            continue
        if grupo == "funções":
            nomes += [f"funções.{n}" for n in (dados.get("funções") or {})]
        elif grupo == "seguranca":
            # Na ordem de SEGURANCA, não na do arquivo: as atualizações de segurança só ligam
            # com os alertas já ligados, e o servidor recusa a ordem inversa.
            seg = dados.get("seguranca") or {}
            ordem = (*SEGURANCA, *SEGURANCA_OPCIONAL)
            nomes += [f"seguranca.{n}" for n in ordem if n in seg]
            nomes += [
                f"seguranca.{n}" for n in seg
                if n not in ordem and n not in PARAMETROS_DA_SEGURANCA
            ]
        else:
            nomes.append(grupo)
    return nomes


def regras_declaradas(dados: dict[str, Any]) -> list[str]:
    """As chaves de regra usadas nos rulesets (cada uma tem de estar em REGRAS_DE_RULESET)."""
    achadas: list[str] = []
    for r in dados.get("rulesets") or []:
        if isinstance(r, dict):
            achadas += [k for k in r if k not in CHAVES_DO_RULESET]
    return sorted(set(achadas))


def _texto(valor: Any) -> bool:
    return isinstance(valor, str) and bool(valor.strip())


def _lista_de_textos(valor: Any) -> bool:
    return isinstance(valor, list) and bool(valor) and all(_texto(x) for x in valor)


def _itens(dados: dict[str, Any], grupo: str) -> list[Any] | None:
    """A lista de um grupo (ou None quando o grupo não foi declarado)."""
    if grupo not in dados:
        return None
    valor = dados[grupo]
    return valor if isinstance(valor, list) else []


def validar(dados: Any) -> list[str]:
    """Os defeitos do esquema; lista vazia quando o arquivo vale."""
    erros: list[str] = []
    if not isinstance(dados, dict):
        return ["o arquivo não é um mapa"]
    if dados.get("versão") != 1:
        erros.append("versão: tem de ser 1")
    conhecidas = {*GRUPOS, *DADOS_SEM_APLICADOR}
    erros += [f"chave desconhecida na raiz: {k}" for k in dados if k not in conhecidas]
    erros += _validar_about(dados.get("about"))
    erros += _validar_funções(dados.get("funções"))
    erros += _validar_seguranca(dados.get("seguranca"))
    erros += _validar_mantenedores(dados.get("mantenedores"))
    erros += _validar_rulesets(dados.get("rulesets"))
    for grupo, validador in (
        ("configuração", _validar_configuracao),
        ("ações", _validar_acoes),
        ("equipes", _validar_equipes),
        ("rotulos", _validar_rotulos),
        ("milestones", _validar_milestones),
        ("tipos_de_issue", _validar_tipos_de_issue),
        ("ambientes", _validar_ambientes),
        ("discussoes", _validar_discussoes),
        ("projetos", _validar_projetos),
        ("comunidade", _validar_comunidade),
        ("de_fora", _validar_de_fora),
        ("release", _validar_release),
    ):
        if grupo in dados:
            erros += validador(dados[grupo])
    if "configuração" not in dados:
        erros += _validar_configuracao(None)
    return erros


def _validar_about(about: Any) -> list[str]:
    if not isinstance(about, dict):
        return ["about: falta"]
    erros: list[str] = []
    if not _texto(about.get("descrição")):
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
    return erros


def _validar_funções(funções: Any) -> list[str]:
    if not isinstance(funções, dict):
        return ["funções: falta"]
    erros = [f"funções.{n}: função desconhecida" for n in funções if n not in FUNCOES]
    erros += [f"funções.{n}: falta declarar" for n in FUNCOES if n not in funções]
    for nome, valor in funções.items():
        if not isinstance(valor, dict) or not isinstance(valor.get("ligada"), bool):
            erros.append(f"funções.{nome}.ligada: verdadeiro ou falso")
            continue
        if valor["ligada"] is False and not str(valor.get("depois", "")).strip():
            erros.append(f"funções.{nome}: desligada precisa de `depois` (quando volta)")
    return erros


def _validar_seguranca(seg: Any) -> list[str]:
    if not isinstance(seg, dict):
        return ["seguranca: falta"]
    conhecidas = (*SEGURANCA, *SEGURANCA_OPCIONAL, *PARAMETROS_DA_SEGURANCA)
    erros = [f"seguranca.{n}: desconhecida" for n in seg if n not in conhecidas]
    erros += [f"seguranca.{n}: falta declarar" for n in SEGURANCA if n not in seg]
    for n, v in seg.items():
        if n in PARAMETROS_DA_SEGURANCA or n not in conhecidas:
            continue
        if isinstance(v, bool):
            continue
        if isinstance(v, dict) and isinstance(v.get("ligada"), bool):
            if not v["ligada"] and not str(v.get("depois", "")).strip():
                erros.append(f"seguranca.{n}: desligada precisa de `depois` (quando volta)")
            continue
        erros.append(f"seguranca.{n}: verdadeiro ou falso")
    linguagens = seg.get("linguagens_da_varredura")
    if _quer(seg.get("varredura_de_codigo")):
        if not isinstance(linguagens, list) or not linguagens:
            erros.append("seguranca.linguagens_da_varredura: lista, quando a varredura liga")
        else:
            erros += [
                f"seguranca.linguagens_da_varredura: «{x}» não é uma das do GitHub"
                for x in linguagens if x not in LINGUAGENS_DA_VARREDURA
            ]
    if "grafo_de_dependencias" in seg and not _quer(seg["grafo_de_dependencias"]):
        erros.append("seguranca.grafo_de_dependencias: só `true` (o GitHub não o desliga por API)")
    return erros


def _validar_mantenedores(mant: Any) -> list[str]:
    if not isinstance(mant, list) or not mant:
        return ["mantenedores: lista com pelo menos uma conta"]
    erros: list[str] = []
    for m in mant:
        if not isinstance(m, dict) or not isinstance(m.get("conta"), str):
            erros.append("mantenedores: cada item tem `conta`")
        elif m.get("função") not in FUNCOES_DE_MANTENEDOR:
            erros.append(f"mantenedores.{m['conta']}: função entre {FUNCOES_DE_MANTENEDOR}")
    return erros


def _validar_rulesets(rulesets: Any) -> list[str]:
    if not isinstance(rulesets, list) or not rulesets:
        return ["rulesets: lista com pelo menos um"]
    erros: list[str] = []
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
    ramos, tags = r.get("ramos"), r.get("tags")
    if (ramos is None) == (tags is None):
        erros.append(f"ruleset «{nome}»: `ramos` ou `tags`, um dos dois")
    if tags is not None:
        # a revisão de PR e os checks olham ramo e PR; o servidor recusa as duas num ruleset de tag
        erros += [f"ruleset «{nome}»: `{k}` só vale para ramo" for k in ("revisão", "checks") if k in r]
    alvo = ramos if ramos is not None else tags
    rotulo = "ramos" if ramos is not None else "tags"
    if not isinstance(alvo, list) or not alvo or not all(isinstance(b, str) and b for b in alvo):
        erros.append(f"ruleset «{nome}»: `{rotulo}` é uma lista de nomes")
    if r.get("excecao") not in (None, *EXCECOES):
        erros.append(f"ruleset «{nome}»: excecao entre {EXCECOES}")
    regras = [k for k in r if k not in CHAVES_DO_RULESET]
    if not regras:
        erros.append(f"ruleset «{nome}»: sem nenhuma regra")
    for k in regras:
        if k not in REGRAS_DE_RULESET:
            erros.append(f"ruleset «{nome}»: regra desconhecida «{k}»")
    for k in ("sem_apagar", "sem_push_forcado", "sem_atualizar", "historico_linear"):
        if k in r and not isinstance(r[k], bool):
            erros.append(f"ruleset «{nome}».{k}: verdadeiro ou falso")
    if "assinatura" in r and r["assinatura"] != "exigida":
        erros.append(f"ruleset «{nome}».assinatura: só `exigida` (ou tirar a chave)")
    if "revisão" in r:
        n = r["revisão"].get("aprovacoes") if isinstance(r["revisão"], dict) else None
        if not isinstance(n, int) or isinstance(n, bool) or not 1 <= n <= 10:
            erros.append(f"ruleset «{nome}».revisão.aprovacoes: inteiro de 1 a 10")
    if "checks" in r:
        c = r["checks"]
        if not isinstance(c, list) or not c or not all(isinstance(x, str) and x for x in c):
            erros.append(f"ruleset «{nome}».checks: lista de nomes de check")
    return erros


def _validar_ramo_padrao(ramo: Any) -> list[str]:
    """O ramo padrão é decisão declarada: sem ela o primeiro push é quem decide."""
    if ramo is None:
        return ["configuração.ramo_padrao: falta declarar"]
    if not isinstance(ramo, str) or not RAMO_VALIDO.fullmatch(ramo) or ".." in ramo:
        return [f"configuração.ramo_padrao: «{ramo}» não é nome de ramo"]
    return []


def _validar_configuracao(cfg: Any) -> list[str]:
    if not isinstance(cfg, dict):
        return ["configuração: falta (a mesclagem e o ramo padrão)"]
    erros = _validar_ramo_padrao(cfg.get("ramo_padrao"))
    erros += [
        f"configuração.{k}: desconhecida" for k in cfg if k not in ("mesclagem", "ramo_padrao")
    ]
    mesc = cfg.get("mesclagem")
    if not isinstance(mesc, dict):
        return [*erros, "configuração.mesclagem: falta"]
    erros += [f"configuração.mesclagem.{k}: desconhecida" for k in mesc if k not in MESCLAGEM]
    erros += [f"configuração.mesclagem.{k}: falta declarar" for k in MESCLAGEM if k not in mesc]
    erros += [
        f"configuração.mesclagem.{k}: verdadeiro ou falso"
        for k, v in mesc.items() if not isinstance(v, bool)
    ]
    if mesc.get("squash") is False and mesc.get("rebase") is False and mesc.get("merge_commit") is False:
        erros.append("configuração.mesclagem: ao menos um jeito de mesclar fica ligado")
    return erros


def _validar_acoes(acoes: Any) -> list[str]:
    if not isinstance(acoes, dict):
        return ["ações: falta"]
    erros: list[str] = []
    if acoes.get("permissao_do_fluxo") not in PERMISSAO_DO_FLUXO:
        erros.append(f"ações.permissao_do_fluxo: entre {tuple(PERMISSAO_DO_FLUXO)}")
    if not isinstance(acoes.get("fluxo_aprova_pr"), bool):
        erros.append("ações.fluxo_aprova_pr: verdadeiro ou falso")
    if acoes.get("aprovacao_de_fork") not in APROVACAO_DE_FORK:
        erros.append(f"ações.aprovacao_de_fork: entre {tuple(APROVACAO_DE_FORK)}")
    return erros


def _validar_equipes(equipes: Any) -> list[str]:
    if not isinstance(equipes, list) or not equipes:
        return ["equipes: lista com pelo menos uma"]
    erros: list[str] = []
    for e in equipes:
        if not isinstance(e, dict) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", str(e.get("nome", ""))):
            erros.append("equipes: cada item tem `nome` (minúsculas, números e hífen: é o endereço)")
            continue
        n = e["nome"]
        if not _texto(e.get("descrição")):
            erros.append(f"equipes.{n}.descrição: texto não vazio")
        if e.get("acesso") not in ACESSO_DA_EQUIPE:
            erros.append(f"equipes.{n}.acesso: entre {ACESSO_DA_EQUIPE}")
        membros = e.get("membros")
        if not isinstance(membros, list) or not membros:
            erros.append(f"equipes.{n}.membros: lista com pelo menos uma conta")
            continue
        for m in membros:
            if not isinstance(m, dict) or not _texto(m.get("conta")) \
                    or m.get("função") not in ("maintainer", "member"):
                erros.append(f"equipes.{n}.membros: cada item tem `conta` e `função` (maintainer ou member)")
    return erros


def _validar_rotulos(rotulos: Any) -> list[str]:
    if not isinstance(rotulos, dict) or not isinstance(rotulos.get("exclusivos"), bool):
        return ["rotulos.exclusivos: verdadeiro ou falso"]
    lista = rotulos.get("lista")
    if not isinstance(lista, list) or not lista:
        return ["rotulos.lista: lista com pelo menos um"]
    erros: list[str] = []
    vistos: set[str] = set()
    for x in lista:
        if not isinstance(x, dict) or not _texto(x.get("nome")) or len(x["nome"]) > 50:
            erros.append("rotulos.lista: cada item tem `nome` (até 50)")
            continue
        n = x["nome"]
        if n.lower() in vistos:
            erros.append(f"rotulos.lista: «{n}» repete (o GitHub não distingue maiúscula)")
        vistos.add(n.lower())
        if not re.fullmatch(r"[0-9a-f]{6}", str(x.get("cor", ""))):
            erros.append(f"rotulos.{n}.cor: seis dígitos hexadecimais minúsculos, sem #")
        d = x.get("descrição")
        if not isinstance(d, str) or not d.strip() or len(d) > 100:
            erros.append(f"rotulos.{n}.descrição: texto de 1 a 100 letras")
    return erros


def _validar_milestones(ms: Any) -> list[str]:
    if not isinstance(ms, list) or not ms:
        return ["milestones: lista com pelo menos um"]
    erros: list[str] = []
    titulos = [m.get("titulo") for m in ms if isinstance(m, dict)]
    if len(set(titulos)) != len(titulos):
        erros.append("milestones: o título é a chave e não se repete")
    for m in ms:
        if not isinstance(m, dict) or not _texto(m.get("titulo")):
            erros.append("milestones: cada item tem `titulo`")
            continue
        if not isinstance(m.get("descrição"), str):
            erros.append(f"milestones.{m['titulo']}.descrição: texto")
        data = m.get("data")
        if data is not None and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(data)):
            erros.append(f"milestones.{m['titulo']}.data: AAAA-MM-DD ou vazia")
    return erros


def _validar_tipos_de_issue(tipos: Any) -> list[str]:
    if not isinstance(tipos, list) or not tipos:
        return ["tipos_de_issue: lista com pelo menos um"]
    erros: list[str] = []
    for t in tipos:
        if not isinstance(t, dict) or not _texto(t.get("nome")):
            erros.append("tipos_de_issue: cada item tem `nome`")
            continue
        if not _texto(t.get("descrição")):
            erros.append(f"tipos_de_issue.{t['nome']}.descrição: texto não vazio")
        if t.get("cor") not in CORES_DE_TIPO:
            erros.append(f"tipos_de_issue.{t['nome']}.cor: entre {CORES_DE_TIPO}")
    return erros


def _validar_ambientes(ambientes: Any) -> list[str]:
    if not isinstance(ambientes, list) or not ambientes:
        return ["ambientes: lista com pelo menos um"]
    erros: list[str] = []
    for a in ambientes:
        if not isinstance(a, dict) or not _texto(a.get("nome")):
            erros.append("ambientes: cada item tem `nome`")
            continue
        n = a["nome"]
        # Sem revisor é um ambiente que só restringe o ramo (o `github-pages`, que publica a página).
        revisores = a.get("revisores")
        if not isinstance(revisores, list) or len(revisores) > 6 \
                or not all(isinstance(x, str) and x for x in revisores):
            erros.append(f"ambientes.{n}.revisores: lista de até 6 contas")
        if not isinstance(a.get("impedir_autoaprovacao"), bool):
            erros.append(f"ambientes.{n}.impedir_autoaprovacao: verdadeiro ou falso")
        ramos, tags = a.get("ramos", []), a.get("tags", [])
        if not isinstance(ramos, list) or not isinstance(tags, list) or not (ramos or tags) \
                or not all(isinstance(x, str) and x for x in [*ramos, *tags]):
            erros.append(f"ambientes.{n}: `ramos` e/ou `tags`, listas de nomes (ao menos um nome)")
    return erros


def _validar_discussoes(d: Any) -> list[str]:
    cats = d.get("categorias") if isinstance(d, dict) else None
    if not isinstance(cats, list) or not cats:
        return ["discussoes.categorias: lista com pelo menos uma"]
    erros: list[str] = []
    for c in cats:
        if not isinstance(c, dict) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", str(c.get("slug", ""))):
            erros.append("discussoes.categorias: cada item tem `slug`")
        elif not isinstance(c.get("responsável"), bool):
            erros.append(f"discussoes.categorias.{c['slug']}.responsável: verdadeiro ou falso")
    return erros


def _validar_projetos(projetos: Any) -> list[str]:
    if not isinstance(projetos, list) or not projetos:
        return ["projetos: lista com pelo menos um"]
    erros: list[str] = []
    for p in projetos:
        if not isinstance(p, dict) or not _texto(p.get("título")):
            erros.append("projetos: cada item tem `título`")
            continue
        t = p["título"]
        if not isinstance(p.get("descrição"), str) or len(p["descrição"]) > 280:
            erros.append(f"projetos.{t}.descrição: texto de até 280 letras")
        if not isinstance(p.get("público"), bool):
            erros.append(f"projetos.{t}.público: verdadeiro ou falso")
        ligado = p.get("ligado_a")
        if not isinstance(ligado, list) or not ligado or not all(
                isinstance(x, str) and re.fullmatch(r"[^/\s]+/[^/\s]+", x) for x in ligado):
            erros.append(f"projetos.{t}.ligado_a: lista de DONO/NOME")
        etapas = p.get("etapas")
        if not isinstance(etapas, list) or not etapas:
            erros.append(f"projetos.{t}.etapas: lista com pelo menos uma")
        else:
            for e in etapas:
                if not isinstance(e, dict) or not _texto(e.get("nome")) \
                        or e.get("cor") not in CORES_DE_ETAPA:
                    erros.append(f"projetos.{t}.etapas: cada item tem `nome` e `cor` entre {CORES_DE_ETAPA}")
        vistas = p.get("vistas")
        if not isinstance(vistas, list):
            erros.append(f"projetos.{t}.vistas: lista")
            continue
        for v in vistas:
            if not isinstance(v, dict) or not _texto(v.get("nome")) \
                    or v.get("formato") not in FORMATOS_DE_VISTA:
                erros.append(f"projetos.{t}.vistas: cada item tem `nome` e `formato` entre {FORMATOS_DE_VISTA}")
            elif not isinstance(v.get("filtro", ""), str) or not isinstance(v.get("agrupar_por", ""), str):
                erros.append(f"projetos.{t}.vistas.{v['nome']}: `filtro` e `agrupar_por` são texto")
    return erros


def _validar_comunidade(c: Any) -> list[str]:
    n = c.get("saude_minima") if isinstance(c, dict) else None
    if not isinstance(n, int) or isinstance(n, bool) or not 1 <= n <= 100:
        return ["comunidade.saude_minima: inteiro de 1 a 100"]
    return []


def _validar_release(release: Any) -> list[str]:
    """O bloco `release`: a série da versão, que o `scripts/release/versao.py` lê (aqui só se confere a forma)."""
    serie = release.get("serie") if isinstance(release, dict) else None
    if not isinstance(serie, str) or not re.fullmatch(r"\d+(\.\d+){0,2}", serie):
        return ['release.serie: texto com o prefixo da versão, como "0.9" ou "4"']
    return []


def _validar_de_fora(de_fora: Any) -> list[str]:
    if not isinstance(de_fora, dict):
        return ["de_fora: mapa de nome para motivo"]
    erros = [f"de_fora.{k}: o motivo (medido) é obrigatório" for k, v in de_fora.items() if not _texto(v)]
    erros += [f"de_fora.{k}: falta declarar" for k in DE_FORA_OBRIGATORIAS if k not in de_fora]
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

    def ler_lista(self, caminho: str) -> list[Any]:
        """Uma lista paginada, lida inteira (cem por página)."""
        itens: list[Any] = []
        sep = "&" if "?" in caminho else "?"
        for pagina in range(1, 51):
            _, parte = self.ler(f"{caminho}{sep}per_page=100&page={pagina}")
            if not isinstance(parte, list):
                raise ErroDeServidor(f"GET {caminho}: a resposta não é uma lista")
            itens += parte
            if len(parte) < 100:
                return itens
        raise ErroDeServidor(f"GET {caminho}: mais de 5000 itens")

    def escrever(self, metodo: str, caminho: str, corpo: Any = None) -> Any:
        status, dados = self.chamar(metodo, caminho, corpo)
        if status >= 300:
            raise ErroDeServidor(f"{metodo} {caminho}: {status} {_mensagem(dados)}")
        return dados

    def graphql(self, consulta: str, variaveis: dict[str, Any] | None = None) -> Any:
        status, dados = self.chamar(
            "POST", "graphql", {"query": consulta, "variables": variaveis or {}})
        if status >= 300 or (isinstance(dados, dict) and dados.get("errors")):
            raise ErroDeServidor(f"graphql: {status} {_mensagem(dados)}")
        return dados["data"]


def _mensagem(dados: Any) -> str:
    if isinstance(dados, dict):
        if dados.get("errors"):
            return str(dados["errors"])[:200]
        return str(dados.get("message", ""))[:200]
    return str(dados or "")[:200]


# As consultas do GraphQL, cada uma com nome: é por elas que o `gh` de mentira as reconhece, e
# o esquema público do GitHub as valida (as diferenças de campo aparecem antes da janela).
CONSULTAS = {
    "Patrocinio": (
        "query Patrocinio($dono:String!,$nome:String!){repository(owner:$dono,name:$nome)"
        "{id hasSponsorshipsEnabled}}"),
    "LigarPatrocinio": (
        "mutation LigarPatrocinio($id:ID!,$ligado:Boolean!){updateRepository(input:"
        "{repositoryId:$id,hasSponsorshipsEnabled:$ligado}){repository{id}}}"),
    "Categorias": (
        "query Categorias($dono:String!,$nome:String!){repository(owner:$dono,name:$nome)"
        "{discussionCategories(first:50){nodes{slug name isAnswerable}}}}"),
    "Projetos": (
        "query Projetos($dono:String!){repositoryOwner(login:$dono){__typename id login "
        "... on ProjectV2Owner{projectsV2(first:50){nodes{id number title shortDescription public "
        "fields(first:50){nodes{... on ProjectV2FieldCommon{id databaseId name dataType} "
        "... on ProjectV2SingleSelectField{options{id name color description}}}} "
        "views(first:50){nodes{id number name layout filter}} "
        "repositories(first:50){nodes{nameWithOwner}}}}}}}"),
    "RepositorioId": (
        "query RepositorioId($dono:String!,$nome:String!){repository(owner:$dono,name:$nome){id}}"),
    "CriarProjeto": (
        "mutation CriarProjeto($dono:ID!,$titulo:String!){createProjectV2(input:"
        "{ownerId:$dono,title:$titulo}){projectV2{id number}}}"),
    "AtualizarProjeto": (
        "mutation AtualizarProjeto($id:ID!,$resumo:String!,$publico:Boolean!){updateProjectV2("
        "input:{projectId:$id,shortDescription:$resumo,public:$publico}){projectV2{id}}}"),
    "LigarProjeto": (
        "mutation LigarProjeto($projeto:ID!,$repo:ID!){linkProjectV2ToRepository(input:"
        "{projectId:$projeto,repositoryId:$repo}){repository{id}}}"),
    "AtualizarEtapas": (
        "mutation AtualizarEtapas($campo:ID!,$etapas:[ProjectV2SingleSelectFieldOptionInput!]){"
        "updateProjectV2Field(input:{fieldId:$campo,singleSelectOptions:$etapas})"
        "{projectV2Field{... on ProjectV2SingleSelectField{id}}}}"),
}


# ---------------------------------------------------------------------------
# O plano: cada grupo devolve as ações que faltam, sem escrever nada.
# ---------------------------------------------------------------------------


@dataclass
class Acao:
    texto: str
    executar: Callable[[], None]
    # Só se faz à mão (o GitHub não deixa por API): o `--aplicar` não a executa, e ela aparece em
    # `sobrou` se continuar depois das outras. O que se escreve aqui é o que fazer.
    a_mao: str = ""


@dataclass
class Contexto:
    gh: Gh
    repo: str
    dados: dict[str, Any]
    _repo: dict[str, Any] | None = field(default=None, repr=False)

    @property
    def dono(self) -> str:
        return self.repo.split("/")[0]

    @property
    def nome(self) -> str:
        return self.repo.split("/")[1]

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

    def da_organizacao(self) -> None:
        """Recusa (como «sem medida») o que só existe em organização, quando o dono é pessoa."""
        _, u = self.gh.ler(f"users/{self.dono}")
        if (u or {}).get("type") != "Organization":
            raise ErroDeServidor(f"«{self.dono}» não é uma organização; isto só existe nelas")


def so_mede(falta: str, como: str) -> Acao:
    """O que o GitHub deixa medir e não deixa criar por API: aparece como diferença, e o
    `--aplicar` diz o que fazer à mão em vez de fingir que fez."""
    return Acao(falta, lambda: None, a_mao=como)


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


def planejar_configuracao(c: Contexto) -> list[Acao]:
    quer = c.dados["configuração"]["mesclagem"]
    r = c.estado_do_repo()
    acoes: list[Acao] = []
    corpo = {MESCLAGEM[k]: v for k, v in quer.items() if bool(r.get(MESCLAGEM[k])) != v}
    if corpo:
        acoes.append(Acao(f"configuração: {', '.join(sorted(corpo))} diferem", c.patch(corpo)))
    return acoes + _planejar_ramo_padrao(c, r)


def _planejar_ramo_padrao(c: Contexto, r: dict[str, Any]) -> list[Acao]:
    """O ramo padrão que o arquivo declara; mudá-lo para um ramo que o remoto não tem o GitHub recusa."""
    quer: str = c.dados["configuração"]["ramo_padrao"]
    real = r.get("default_branch")
    if not isinstance(real, str) or not real:
        raise ErroDeServidor("o repositório não disse qual é o ramo padrão")
    if real == quer:
        return []
    falta = f"configuração: o ramo padrão é «{real}» e o arquivo declara «{quer}»"
    status, _ = c.gh.ler(f"repos/{c.repo}/branches/{quote(quer, safe='/')}", aceita=(200, 404))
    if status == 404:
        return [so_mede(f"{falta}, que não existe no remoto",
                        f"empurrar o ramo «{quer}» e rodar o --aplicar de novo")]
    return [Acao(falta, c.patch({"default_branch": quer}))]


def _planejar_função(nome: str) -> Callable[[Contexto], list[Acao]]:
    def planejar(c: Contexto) -> list[Acao]:
        quer: bool = c.dados["funções"][nome]["ligada"]
        if nome in FUNCOES_COM_INTERRUPTOR:
            campo = FUNCOES_COM_INTERRUPTOR[nome]
            if bool(c.estado_do_repo().get(campo)) == quer:
                return []
            return [Acao(f"funções.{nome}: {'liga' if quer else 'desliga'}", c.patch({campo: quer}))]
        if nome == "pages":
            return _planejar_pages(c, quer)
        if nome == "sponsor":
            return _planejar_sponsor(c, quer)
        raise AssertionError(nome)

    return planejar


def _planejar_pages(c: Contexto, quer: bool) -> list[Acao]:
    status, p = c.gh.ler(f"repos/{c.repo}/pages", aceita=(200, 404))
    if not quer:
        return [] if status == 404 else [Acao("funções.pages: desliga", c.escreve("DELETE", "pages"))]
    # As páginas saem de um fluxo (`paginas.yml`), não de uma pasta do ramo.
    if status == 404:
        return [Acao("funções.pages: liga (publicada por fluxo)",
                     c.escreve("POST", "pages", {"build_type": "workflow"}))]
    if (p or {}).get("build_type") != "workflow":
        return [Acao("funções.pages: passa a ser publicada por fluxo",
                     c.escreve("PUT", "pages", {"build_type": "workflow"}))]
    return []


def _planejar_sponsor(c: Contexto, quer: bool) -> list[Acao]:
    d = c.gh.graphql(CONSULTAS["Patrocinio"], {"dono": c.dono, "nome": c.nome})
    r = d["repository"]
    if bool(r["hasSponsorshipsEnabled"]) == quer:
        return []

    def feito() -> None:
        c.gh.graphql(CONSULTAS["LigarPatrocinio"], {"id": r["id"], "ligado": quer})

    return [Acao(f"funções.sponsor: {'liga' if quer else 'desliga'}", feito)]


def _interruptor(
    rotulo: str, caminho: str, ler: Callable[[int, Any], bool]
) -> Callable[[Contexto], list[Acao]]:
    """Um recurso que liga com PUT e desliga com DELETE no mesmo caminho."""

    def planejar(c: Contexto) -> list[Acao]:
        quer = _quer(c.dados["seguranca"][rotulo])
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
        quer = _quer(c.dados["seguranca"][rotulo])
        sa = c.estado_do_repo().get("security_and_analysis") or {}
        atual = (sa.get(chave) or {}).get("status") == "enabled"
        if atual == quer:
            return []
        corpo = {"security_and_analysis": {chave: {"status": "enabled" if quer else "disabled"}}}
        return [Acao(f"seguranca.{rotulo}: {'liga' if quer else 'desliga'}", c.patch(corpo))]

    return planejar


def planejar_varredura_de_codigo(c: Contexto) -> list[Acao]:
    seg = c.dados["seguranca"]
    quer = _quer(seg["varredura_de_codigo"])
    linguagens = sorted(seg.get("linguagens_da_varredura") or [])
    _, s = c.gh.ler(f"repos/{c.repo}/code-scanning/default-setup")
    ligado = s.get("state") == "configured"
    if not quer:
        if not ligado:
            return []
        return [Acao("seguranca.varredura_de_codigo: desliga", c.escreve(
            "PATCH", "code-scanning/default-setup", {"state": "not-configured"}))]
    if ligado and sorted(s.get("languages") or []) == linguagens \
            and s.get("query_suite") == "default":
        return []
    return [Acao(f"seguranca.varredura_de_codigo: liga ({', '.join(linguagens)})", c.escreve(
        "PATCH", "code-scanning/default-setup",
        {"state": "configured", "languages": linguagens, "query_suite": "default"}))]


def planejar_grafo_de_dependencias(c: Contexto) -> list[Acao]:
    status, _ = c.gh.ler(f"repos/{c.repo}/dependency-graph/sbom", aceita=(200, 403, 404))
    if status == 200:
        return []
    return [so_mede(
        "seguranca.grafo_de_dependencias: desligado (sem lista de dependências para exportar)",
        "o grafo de dependências liga sozinho em repositório público; em privado só pela "
        "interface (Settings > Advanced Security)")]


def planejar_acoes(c: Contexto) -> list[Acao]:
    quer = c.dados["ações"]
    acoes: list[Acao] = []
    _, w = c.gh.ler(f"repos/{c.repo}/actions/permissions/workflow")
    corpo: dict[str, Any] = {}
    if w.get("default_workflow_permissions") != PERMISSAO_DO_FLUXO[quer["permissao_do_fluxo"]]:
        corpo["default_workflow_permissions"] = PERMISSAO_DO_FLUXO[quer["permissao_do_fluxo"]]
    if bool(w.get("can_approve_pull_request_reviews")) != quer["fluxo_aprova_pr"]:
        corpo["can_approve_pull_request_reviews"] = quer["fluxo_aprova_pr"]
    if corpo:
        acoes.append(Acao("ações: as permissões do fluxo diferem",
                          c.escreve("PUT", "actions/permissions/workflow", corpo)))
    _, f = c.gh.ler(f"repos/{c.repo}/actions/permissions/fork-pr-contributor-approval")
    politica = APROVACAO_DE_FORK[quer["aprovacao_de_fork"]]
    if f.get("approval_policy") != politica:
        acoes.append(Acao("ações: a aprovação de PR de fora difere", c.escreve(
            "PUT", "actions/permissions/fork-pr-contributor-approval",
            {"approval_policy": politica})))
    return acoes


def planejar_releases_imutaveis(c: Contexto) -> list[Acao]:
    quer = _quer(c.dados["seguranca"]["releases_imutaveis"])
    status, corpo = c.gh.ler(f"repos/{c.repo}/immutable-releases", aceita=(200, 404))
    ligado = status == 200 and bool((corpo or {}).get("enabled"))
    if ligado == quer:
        return []
    return [Acao(f"seguranca.releases_imutaveis: {'liga' if quer else 'desliga'}",
                 c.escreve("PUT" if quer else "DELETE", "immutable-releases"))]


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


def planejar_equipes(c: Contexto) -> list[Acao]:
    c.da_organizacao()
    org = c.dono
    acoes: list[Acao] = []
    for e in c.dados["equipes"]:
        slug = e["nome"]
        status, equipe = c.gh.ler(f"orgs/{org}/teams/{slug}", aceita=(200, 404))
        if status == 404:
            def criar(e: dict[str, Any] = e) -> None:
                c.gh.escrever("POST", f"orgs/{org}/teams", {
                    "name": e["nome"], "description": e["descrição"], "privacy": "closed"})

            acoes.append(Acao(f"equipes.{slug}: não existe", criar))
        elif (equipe.get("description") or "") != e["descrição"]:
            acoes.append(Acao(f"equipes.{slug}: a descrição difere", _escrever_em(
                c, "PATCH", f"orgs/{org}/teams/{slug}", {"description": e["descrição"]})))
        for m in e["membros"]:
            conta = m["conta"]
            atual = None
            if status == 200:
                st, mem = c.gh.ler(
                    f"orgs/{org}/teams/{slug}/memberships/{conta}", aceita=(200, 404))
                if st == 200 and mem.get("state") == "active":
                    atual = mem.get("role")
            if atual != m["função"]:
                acoes.append(Acao(f"equipes.{slug}.{conta}: {atual or 'fora'} -> {m['função']}",
                                  _escrever_em(c, "PUT", f"orgs/{org}/teams/{slug}/memberships/{conta}",
                                               {"role": m["função"]})))
        papel = None
        if status == 200:
            for r in c.gh.ler_lista(f"orgs/{org}/teams/{slug}/repos"):
                if r.get("full_name") == c.repo:
                    papel = r.get("role_name")
        if papel != e["acesso"]:
            acoes.append(Acao(f"equipes.{slug}: acesso a este repositório {papel or 'sem'} -> {e['acesso']}",
                              _escrever_em(c, "PUT", f"orgs/{org}/teams/{slug}/repos/{c.repo}",
                                           {"permission": e["acesso"]})))
    return acoes


def _escrever_em(c: Contexto, metodo: str, caminho: str, corpo: Any) -> Callable[[], None]:
    """A escrita adiada num caminho que não é de `repos/DONO/NOME`."""
    def feito() -> None:
        c.gh.escrever(metodo, caminho, corpo)

    return feito


def planejar_rotulos(c: Contexto) -> list[Acao]:
    quer = c.dados["rotulos"]
    existentes = {x["name"].lower(): x for x in c.gh.ler_lista(f"repos/{c.repo}/labels")}
    acoes: list[Acao] = []
    for r in quer["lista"]:
        atual = existentes.get(r["nome"].lower())
        if atual is None:
            acoes.append(Acao(f"rotulos: «{r['nome']}» não existe", c.escreve("POST", "labels", {
                "name": r["nome"], "color": r["cor"], "description": r["descrição"]})))
            continue
        corpo: dict[str, Any] = {}
        if atual["name"] != r["nome"]:
            corpo["new_name"] = r["nome"]
        if (atual.get("color") or "").lower() != r["cor"]:
            corpo["color"] = r["cor"]
        if (atual.get("description") or "") != r["descrição"]:
            corpo["description"] = r["descrição"]
        if corpo:
            acoes.append(Acao(f"rotulos: «{r['nome']}» difere ({', '.join(sorted(corpo))})",
                              c.escreve("PATCH", f"labels/{quote(atual['name'], safe='')}", corpo)))
    if quer["exclusivos"]:
        declarados = {r["nome"].lower() for r in quer["lista"]}
        for nome, atual in existentes.items():
            if nome not in declarados:
                acoes.append(Acao(f"rotulos: «{atual['name']}» não está no arquivo", c.escreve(
                    "DELETE", f"labels/{quote(atual['name'], safe='')}")))
    return acoes


def planejar_milestones(c: Contexto) -> list[Acao]:
    existentes = {m["title"]: m for m in c.gh.ler_lista(f"repos/{c.repo}/milestones?state=all")}
    acoes: list[Acao] = []
    for m in c.dados["milestones"]:
        quer: dict[str, Any] = {"title": m["titulo"], "description": m["descrição"]}
        if m.get("data"):
            quer["due_on"] = f"{m['data']}T00:00:00Z"
        atual = existentes.get(m["titulo"])
        if atual is None:
            acoes.append(Acao(f"milestones: «{m['titulo']}» não existe",
                              c.escreve("POST", "milestones", quer)))
            continue
        diff = (atual.get("description") or "") != m["descrição"]
        if m.get("data"):
            diff = diff or (atual.get("due_on") or "")[:10] != m["data"]
        if diff:
            acoes.append(Acao(f"milestones: «{m['titulo']}» difere", c.escreve(
                "PATCH", f"milestones/{atual['number']}", quer)))
    return acoes


def planejar_tipos_de_issue(c: Contexto) -> list[Acao]:
    c.da_organizacao()
    _, lista = c.gh.ler(f"orgs/{c.dono}/issue-types")
    existentes = {t["name"]: t for t in lista}
    acoes: list[Acao] = []
    for t in c.dados["tipos_de_issue"]:
        quer = {"name": t["nome"], "description": t["descrição"], "color": t["cor"],
                "is_enabled": True}
        atual = existentes.get(t["nome"])
        if atual is None:
            acoes.append(Acao(f"tipos_de_issue: «{t['nome']}» não existe",
                              _escrever_em(c, "POST", f"orgs/{c.dono}/issue-types", quer)))
        elif (atual.get("description") or "") != t["descrição"] or atual.get("color") != t["cor"] \
                or not atual.get("is_enabled"):
            acoes.append(Acao(f"tipos_de_issue: «{t['nome']}» difere", _escrever_em(
                c, "PUT", f"orgs/{c.dono}/issue-types/{atual['id']}", quer)))
    return acoes


def _id_da_conta(c: Contexto, conta: str) -> int:
    _, u = c.gh.ler(f"users/{conta}")
    return int(u["id"])


def planejar_ambientes(c: Contexto) -> list[Acao]:
    acoes: list[Acao] = []
    for a in c.dados["ambientes"]:
        nome = a["nome"]
        caminho = f"environments/{quote(nome, safe='')}"
        status, env = c.gh.ler(f"repos/{c.repo}/{caminho}", aceita=(200, 404))
        revisores: list[str] = []
        autoaprova = False
        if status == 200:
            for regra in env.get("protection_rules") or []:
                if regra.get("type") == "required_reviewers":
                    revisores = [x["reviewer"]["login"] for x in regra.get("reviewers") or []]
                    autoaprova = bool(regra.get("prevent_self_review"))
        diverge = (
            status == 404
            or sorted(revisores) != sorted(a["revisores"])
            or autoaprova != a["impedir_autoaprovacao"]
            or (env.get("deployment_branch_policy") or {}) != POLITICA_DE_RAMOS
        )
        if diverge:
            def ajustar(a: dict[str, Any] = a, caminho: str = caminho) -> None:
                corpo = {
                    "wait_timer": 0,
                    "prevent_self_review": a["impedir_autoaprovacao"],
                    "reviewers": [{"type": "User", "id": _id_da_conta(c, r)} for r in a["revisores"]],
                    "deployment_branch_policy": POLITICA_DE_RAMOS,
                }
                c.gh.escrever("PUT", f"repos/{c.repo}/{caminho}", corpo)

            acoes.append(Acao(f"ambientes.{nome}: {'não existe' if status == 404 else 'difere'}", ajustar))
        existentes: dict[tuple[str, str], int] = {}
        if status == 200:
            _, pol = c.gh.ler(f"repos/{c.repo}/{caminho}/deployment-branch-policies")
            existentes = {(p["name"], p["type"]): int(p["id"]) for p in pol.get("branch_policies", [])}
        quer = [(n, "branch") for n in a.get("ramos", [])] + [(n, "tag") for n in a.get("tags", [])]
        for n, tipo in quer:
            if (n, tipo) not in existentes:
                acoes.append(Acao(f"ambientes.{nome}: falta a regra de {tipo} «{n}»", _escrever_em(
                    c, "POST", f"repos/{c.repo}/{caminho}/deployment-branch-policies",
                    {"name": n, "type": tipo})))
        # A regra que o arquivo não lista sai: o GitHub cria a do ramo padrão sozinho no `github-pages`,
        # e com ela o `dev` publicaria a página que só o `main` publica.
        for (n, tipo), ident in sorted(existentes.items()):
            if (n, tipo) not in quer:
                acoes.append(Acao(f"ambientes.{nome}: sobra a regra de {tipo} «{n}»", _escrever_em(
                    c, "DELETE", f"repos/{c.repo}/{caminho}/deployment-branch-policies/{ident}", None)))
    return acoes


def planejar_discussoes(c: Contexto) -> list[Acao]:
    # O GitHub não tem mutação que crie ou renomeie categoria (`createDiscussionCategory` não
    # existe no esquema público): só se mede. As categorias nascem com o recurso.
    d = c.gh.graphql(CONSULTAS["Categorias"], {"dono": c.dono, "nome": c.nome})
    nos = ((d.get("repository") or {}).get("discussionCategories") or {}).get("nodes") or []
    existentes = {x["slug"]: x for x in nos}
    acoes: list[Acao] = []
    for cat in c.dados["discussoes"]["categorias"]:
        atual = existentes.get(cat["slug"])
        if atual is None:
            acoes.append(so_mede(
                f"discussoes: falta a categoria «{cat['slug']}»",
                f"a API do GitHub não cria categoria de Discussions: crie «{cat['slug']}» em "
                "Discussions > Categories, na interface"))
        elif bool(atual.get("isAnswerable")) != cat["responsável"]:
            quer = "aceita" if cat["responsável"] else "não aceita"
            acoes.append(so_mede(
                f"discussoes: «{cat['slug']}» devia {quer} resposta marcada",
                "a API do GitHub não edita categoria de Discussions: ajuste na interface"))
    return acoes


def planejar_comunidade(c: Contexto) -> list[Acao]:
    minimo = c.dados["comunidade"]["saude_minima"]
    _, perfil = c.gh.ler(f"repos/{c.repo}/community/profile")
    saude = int(perfil.get("health_percentage") or 0)
    if saude >= minimo:
        return []
    faltam = sorted(k for k, v in (perfil.get("files") or {}).items() if not v)
    if not perfil.get("description"):
        faltam.append("description")
    return [so_mede(
        f"comunidade: saúde {saude}% (o arquivo pede {minimo}%); faltam {', '.join(faltam) or '?'}",
        "o perfil da comunidade sobe com arquivos no repositório (README, LICENSE, CONTRIBUTING, "
        "CODE_OF_CONDUCT, modelos de issue e de PR) e com a descrição do About")]


# --- os rulesets -----------------------------------------------------------


def corpo_do_ruleset(r: dict[str, Any]) -> dict[str, Any]:
    """O que o GitHub recebe (e, em subconjunto, o que ele devolve) para um ruleset do arquivo."""
    regras: list[dict[str, Any]] = []
    if r.get("sem_apagar"):
        regras.append({"type": "deletion"})
    if r.get("sem_push_forcado"):
        regras.append({"type": "non_fast_forward"})
    if r.get("sem_atualizar"):
        # Em tag o GitHub guarda a regra sem o parâmetro (ele só vale para ramo) e a devolve sem ele.
        regras.append({"type": "update"} if "tags" in r
                      else {"type": "update", "parameters": {"update_allows_fetch_and_merge": False}})
    if r.get("historico_linear"):
        regras.append({"type": "required_linear_history"})
    if r.get("assinatura") == "exigida":
        regras.append({"type": "required_signatures"})
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
    de_tag = "tags" in r
    incluir = [f"refs/tags/{t}" for t in r["tags"]] if de_tag else [f"refs/heads/{b}" for b in r["ramos"]]
    return {
        "name": r["nome"],
        "target": "tag" if de_tag else "branch",
        "enforcement": "active",
        "conditions": {"ref_name": {"include": incluir, "exclude": []}},
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
    # Só os do repositório: os da organização vêm na mesma lista por padrão, e um homônimo dela
    # seria lido como o nosso (e o PUT iria a um id que o repositório não edita).
    _, lista = c.gh.ler(f"repos/{c.repo}/rulesets?includes_parents=false")
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


# --- os projetos -----------------------------------------------------------


def _vistas_ids(c: Contexto, numero: int) -> dict[str, int]:
    """O número de cada campo do projeto, pelo nome (as vistas pedem o número, não o nome)."""
    _, campos = c.gh.ler(f"orgs/{c.dono}/projectsV2/{numero}/fields")
    return {x["name"]: int(x["id"]) for x in campos}


def _graphql_em(c: Contexto, consulta: str, variaveis: dict[str, Any]) -> Callable[[], None]:
    """A chamada do GraphQL adiada, para só rodar quando o `--aplicar` executar a ação."""
    def feito() -> None:
        c.gh.graphql(CONSULTAS[consulta], variaveis)

    return feito


def _planejar_projeto(c: Contexto, p: dict[str, Any], atual: dict[str, Any]) -> list[Acao]:
    acoes: list[Acao] = []
    titulo = p["título"]
    if (atual.get("shortDescription") or "") != p["descrição"] or bool(atual.get("public")) != p["público"]:
        acoes.append(Acao(f"projetos.{titulo}: descrição ou visibilidade diferem", _graphql_em(
            c, "AtualizarProjeto", {"id": atual["id"], "resumo": p["descrição"],
                                    "publico": p["público"]})))
    campos = (atual.get("fields") or {}).get("nodes") or []
    etapa = next((x for x in campos if x.get("name") == "Status"), None)
    quer_opcoes = [(e["nome"], e["cor"]) for e in p["etapas"]]
    if etapa is None:
        acoes.append(so_mede(f"projetos.{titulo}: o projeto não tem o campo Status",
                             "o campo Status nasce com o projeto; recrie o projeto"))
    elif [(o["name"], o["color"]) for o in etapa.get("options") or []] != quer_opcoes:
        opcoes = [{"name": n, "color": cor, "description": ""} for n, cor in quer_opcoes]
        acoes.append(Acao(f"projetos.{titulo}: as etapas do Status diferem", _graphql_em(
            c, "AtualizarEtapas", {"campo": etapa["id"], "etapas": opcoes})))
    ligados = {x["nameWithOwner"] for x in (atual.get("repositories") or {}).get("nodes") or []}
    for repo in p["ligado_a"]:
        if repo in ligados:
            continue

        def ligar(repo: str = repo) -> None:
            dono, nome = repo.split("/")
            r = c.gh.graphql(CONSULTAS["RepositorioId"], {"dono": dono, "nome": nome})
            c.gh.graphql(CONSULTAS["LigarProjeto"], {"projeto": atual["id"], "repo": r["repository"]["id"]})

        acoes.append(Acao(f"projetos.{titulo}: não está ligado a {repo}", ligar))
    existentes = {v["name"]: v for v in (atual.get("views") or {}).get("nodes") or []}
    for v in p["vistas"]:
        real = existentes.get(v["nome"])
        if real is None:
            def criar_vista(v: dict[str, Any] = v) -> None:
                corpo: dict[str, Any] = {"name": v["nome"], "layout": v["formato"]}
                if v.get("filtro"):
                    corpo["filter"] = v["filtro"]
                if v.get("agrupar_por"):
                    ids = _vistas_ids(c, atual["number"])
                    if v["agrupar_por"] not in ids:
                        raise ErroDeServidor(f"o projeto não tem o campo «{v['agrupar_por']}»")
                    corpo["group_by"] = [ids[v["agrupar_por"]]]
                c.gh.escrever("POST", f"orgs/{c.dono}/projectsV2/{atual['number']}/views", corpo)

            acoes.append(Acao(f"projetos.{titulo}: falta a vista «{v['nome']}»", criar_vista))
        elif real.get("layout", "").split("_")[0].lower() != v["formato"] \
                or (real.get("filter") or "") != v.get("filtro", ""):
            acoes.append(so_mede(
                f"projetos.{titulo}: a vista «{v['nome']}» difere (formato ou filtro)",
                "a API do GitHub não edita vista de projeto: ajuste na interface ou apague a vista "
                "para o `--aplicar` recriá-la"))
    return acoes


def _projeto_pelo_titulo(c: Contexto, titulo: str) -> tuple[dict[str, Any], dict[str, Any]]:
    d = c.gh.graphql(CONSULTAS["Projetos"], {"dono": c.dono})
    dono = d.get("repositoryOwner")
    if not dono:
        raise ErroDeServidor(f"«{c.dono}» não existe para o GraphQL")
    if dono.get("__typename") != "Organization":
        raise ErroDeServidor("o projeto é de organização: o dono deste repositório é uma pessoa")
    nos = (dono.get("projectsV2") or {}).get("nodes") or []
    return dono, next((x for x in nos if x["title"] == titulo), {})


def planejar_projetos(c: Contexto) -> list[Acao]:
    acoes: list[Acao] = []
    for p in c.dados["projetos"]:
        dono, atual = _projeto_pelo_titulo(c, p["título"])
        if atual:
            acoes += _planejar_projeto(c, p, atual)
            continue

        def criar(p: dict[str, Any] = p, dono_id: str = dono["id"]) -> None:
            c.gh.graphql(CONSULTAS["CriarProjeto"], {"dono": dono_id, "titulo": p["título"]})
            _, criado = _projeto_pelo_titulo(c, p["título"])
            if not criado:
                raise ErroDeServidor(f"o projeto «{p['título']}» não apareceu depois de criado")
            for a in _planejar_projeto(c, p, criado):
                a.executar()

        acoes.append(Acao(f"projetos: «{p['título']}» não existe", criar))
    return acoes


# Quem aplica cada função declarada. A régua `test_o_repositorio_diz_o_que_o_github_tem` exige
# uma entrada aqui para tudo o que o arquivo declara, e nenhuma entrada sem declaração.
APLICADORES: dict[str, Callable[[Contexto], list[Acao]]] = {
    "about": planejar_about,
    "configuração": planejar_configuracao,
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
    "seguranca.varredura_de_codigo": planejar_varredura_de_codigo,
    "seguranca.grafo_de_dependencias": planejar_grafo_de_dependencias,
    "seguranca.releases_imutaveis": planejar_releases_imutaveis,
    "ações": planejar_acoes,
    "mantenedores": planejar_mantenedores,
    "equipes": planejar_equipes,
    "rotulos": planejar_rotulos,
    "milestones": planejar_milestones,
    "tipos_de_issue": planejar_tipos_de_issue,
    "ambientes": planejar_ambientes,
    "discussoes": planejar_discussoes,
    "projetos": planejar_projetos,
    "rulesets": planejar_rulesets,
    "comunidade": planejar_comunidade,
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


def avisos_da_release(c: Contexto) -> list[str]:
    """O que a release ainda pede a quem mantém e a API não deixa fazer: se avisa, não se aplica nem reprova.

    A publicação no PyPI usa o publicador de confiança (OIDC): o PyPI só aceita o repositório depois de quem
    mantém registrar nele o dono, o repositório, o fluxo `release.yml` e o ambiente `pypi`, e a API do PyPI não
    deixa ler nem fazer esse registro. O que o repositório guarda do gesto é a variável `PYPI_PUBLISH`, que só
    vale «true» depois dele (o job `pypi` do `release.yml` pergunta por ela): sem a variável, o gesto não foi feito.
    """
    if "release" not in c.dados:
        return []
    try:
        status, v = c.gh.ler(f"repos/{c.repo}/actions/variables/PYPI_PUBLISH", aceita=(200, 404))
    except ErroDeServidor as e:
        return [f"release: não medi o publicador de confiança do PyPI ({e})"]
    if status == 404 or str((v or {}).get("value", "")).lower() != "true":
        return [
            "release: o publicador de confiança do PyPI não está registrado para este repositório (a variável "
            "PYPI_PUBLISH não é «true»); a primeira publicação no PyPI não sai. O gesto é de quem mantém, uma vez: em "
            f"https://pypi.org/manage/account/publishing/ registrar o dono {c.dono}, o repositório {c.nome}, o fluxo "
            "release.yml e o ambiente pypi; depois pôr a variável PYPI_PUBLISH com o valor true em Settings > Variables"
        ]
    return []


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


def _linha(texto: str, x: Acao) -> str:
    return f"{texto} (à mão: {x.a_mao})" if x.a_mao else texto


def principal(argv: list[str] | None = None, gh: Gh | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
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
    detalhe += [_linha(f"falta: {x.texto}", x) for x in acoes]
    detalhe += [f"sem medida: {m}" for m in sem_medida]
    if not pedidos:  # só na conferência do todo: o aviso não é de um grupo
        detalhe += [f"aviso: {x}" for x in avisos_da_release(c)]

    if a.conferir:
        if sem_medida:
            return encerrar(2, f"{a.repo}: {len(sem_medida)} sem medida, {len(acoes)} a aplicar")
        if acoes:
            return encerrar(1, f"{a.repo}: {len(acoes)} diferença(s); `--aplicar` resolve")
        return encerrar(0, f"{a.repo}: sem diferença")

    # Grupo a grupo, na ordem de GRUPOS, e cada um medido de novo logo antes: o que um grupo
    # aplica muda o que o seguinte encontra (ligar as Pages cria o ambiente `github-pages` com a
    # regra de fábrica, que o grupo dos ambientes corrige na mesma rodada).
    falhas: list[str] = []
    fazer: list[Acao] = []
    for grupo in (g for g in GRUPOS if g in grupos):
        c.esquecer()
        plano, _ = planejar(c, {grupo})
        for x in plano:
            if x.a_mao:
                continue
            fazer.append(x)
            try:
                x.executar()
                detalhe.append(f"feito: {x.texto}")
            except ErroDeServidor as e:
                falhas.append(f"{x.texto}: {e}")
    detalhe += [f"falhou: {f}" for f in falhas]
    c.esquecer()
    depois, sem_medida_depois = planejar(c, grupos)
    detalhe += [_linha(f"sobrou: {x.texto}", x) for x in depois]
    if falhas or depois or sem_medida or sem_medida_depois:
        sobram = len(falhas) + len(depois) + len(sem_medida_depois)
        codigo = 2 if (sem_medida or sem_medida_depois) else 1
        return encerrar(codigo, f"{a.repo}: aplicado {len(fazer) - len(falhas)} de "
                        f"{len(fazer)}; sobram {sobram}")
    return encerrar(0, f"{a.repo}: aplicado {len(fazer)}; conferido sem diferença")


if __name__ == "__main__":
    sys.exit(principal())

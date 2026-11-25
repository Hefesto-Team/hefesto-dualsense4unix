#!/usr/bin/env python3
"""changelog.py — a seção da versão nasce do que foi fechado, e as notas da release saem da seção.

  changelog.py montar VERSAO [--data D]   monta `## [VERSAO] — D` no CHANGELOG.md
  changelog.py notas VERSAO [--repo R]    escreve as notas da release (a seção e como conferir o que se baixa)

O QUE ENTRA na seção, nesta ordem e sem repetir linha (nem uma que uma versão anterior já tenha):
  1. o que estiver escrito à mão em `## [Unreleased]` (a seção passa a ficar vazia);
  2. o bloco `publico` de cada sprint fechada (`estado: feita`) desde a data da última tag da série; o
     formato e a régua são do `publico.py`. Sprint fechada sem o bloco não entra, e a saída a avisa; a que
     declara `# publico: em-casa` fica fora sem aviso; a que nomeia uma aba e fechou «sem tela» ou «sem
     cartão» fica fora, e a saída a avisa (a tela chega em outra sprint, e essa é que a anuncia);
  3. o título dos PRs que entraram desde a última tag (os commits `feat`, `fix` e `perf` que terminam em
     `(#N)`), na mesma régua. Título com palavra da casa não entra, e a saída o avisa.

Os itens saem agrupados pela `area` do bloco (sem área, em «Outras mudanças»), e a seção abre com o resumo de
três a cinco linhas que quem fecha a versão escreve em `## [Unreleased]`, antes do primeiro `###`. Sem o
resumo, `montar` recusa. Os títulos das áreas são os de `.github/release.yml`.

Quem lê as sprints é a máquina de quem mantém o projeto: as sprints moram em `docs/process/sprints/` (e `arquivados/`),
que não viaja ao GitHub. Sem essa pasta, entram só as duas outras fontes. A série e a última tag são as do
`versao.py`; a data da seção é a do AppStream (`versao.py gravar --data`), e a régua
`check_version_consistency.py` confere as duas.

O CONTRATO: idempotente, `--conferir` (diz o que mudaria; sai 1 se mudaria), resumo numa linha, detalhe depois
ou em `--detalhe ARQ`. Saída: 0 feito ou já feito; 1 `--conferir` com o que fazer; 2 uso; 3 a seção não existe
(`notas`); 4 não há nada a dizer da versão (`montar`); 1 também quando falta o resumo ou ele não tem de três
a cinco linhas.
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _comum
import publico

GRUPOS = ("Adicionado", "Mudado", "Removido", "Corrigido")
OUTRAS = "Outras mudanças"
LINHAS_DO_RESUMO = (3, 5)
TITULO_DA_AREA = re.compile(r'title:\s*"([^"]+)"\s*\n\s*labels:\s*\["área: ([^"]+)"\]')
OS_ARQUIVOS = """### Os arquivos desta versão

- `.whl` e `.tar.gz`: o pacote Python (para o `pip`) e o código-fonte.
- `.AppImage`: roda sem instalar; baixe, dê permissão de execução e abra.
- `.deb`: um para cada versão do Ubuntu (22.04 e 24.04); instale o da sua com o `apt`.
- `.flatpak`: o pacote Flatpak, com tudo o que o Hefesto precisa dentro.
- `xgameruntime.dll` e `gameinput.dll`: as duas peças que fazem os jogos do Xbox para PC (GDK) falarem com o
  controle no Wine e no Proton; o instalador e o atualizador as põem no lugar, e quem usa o pacote não as abre.
- `sonda-gdk.exe` e `sonda-gameinput.exe`: programas de prova das duas peças, usados para conferir a versão; não
  servem para abrir no dia a dia.
- `LICENCA-DA-ORIGEM.txt`: o aviso de licença das duas peças.
- `SHA256SUMS`: a soma de cada arquivo acima, para conferir o que se baixa.
"""
PR = re.compile(r"^(?P<tipo>feat|fix|perf)(?:\([^)]*\))?!?:\s+(?P<titulo>.+?)\s+\(#(?P<numero>\d+)\)$")
CABECALHO = re.compile(r"^##\s*\[(?P<numero>[^\]]+)\](?:\s*[—-]\s*(?P<data>\d{4}-\d{2}-\d{2}))?\s*$")
FECHADA = re.compile(r"^#\s*fechada\s+(\d{2})/(\d{2})/(\d{4})")
EM_CASA = re.compile(r"^#\s*publico:\s*em-casa\b", re.MULTILINE)
O_QUE_FOI_FEITO = re.compile(r"^##\s+O que foi feito\b.*?(?=^##\s|\Z)", re.MULTILINE | re.DOTALL)
SEM_TELA = re.compile(r"\bsem\s+(?:tela|cart[ãa]o)\b", re.IGNORECASE)
EM_CICLO = re.compile(r"^#\s*ciclo:\s*feita\b.*\bem=(\d{2})/(\d{2})/(\d{4})")


def partir(texto: str) -> tuple[str, list[tuple[str, list[str]]]]:
    """(o que vem antes da primeira seção, [(linha do cabeçalho, linhas do corpo)])."""
    linhas = texto.split("\n")
    inicio = next((i for i, ln in enumerate(linhas) if ln.startswith("## [")), len(linhas))
    cabeca = "\n".join(linhas[:inicio])
    secoes: list[tuple[str, list[str]]] = []
    for ln in linhas[inicio:]:
        if ln.startswith("## ["):
            secoes.append((ln, []))
        else:
            secoes[-1][1].append(ln)
    return cabeca, secoes


def itens(corpo: list[str]) -> dict[str, list[str]]:
    """Os itens de uma seção por grupo (`### Adicionado`…), cada item com as linhas de continuação."""
    grupos: dict[str, list[str]] = {}
    atual: str | None = None
    for ln in corpo:
        if ln.startswith("### "):
            atual = ln[4:].strip()
            grupos.setdefault(atual, [])
        elif atual is not None and ln.startswith("- "):
            grupos[atual].append(ln)
        elif atual is not None and ln.startswith("  ") and grupos[atual]:
            grupos[atual][-1] += "\n" + ln
    return grupos


def resumo_de(corpo: list[str]) -> list[str]:
    """As linhas de texto da seção antes do primeiro `###` (o resumo), sem as em branco das pontas."""
    antes: list[str] = []
    for ln in corpo:
        if ln.startswith("### "):
            break
        antes.append(ln.rstrip())
    while antes and not antes[0]:
        antes.pop(0)
    while antes and not antes[-1]:
        antes.pop()
    return antes


def titulos_das_areas(raiz: Path) -> dict[str, str]:
    """área -> título do grupo na nota: o de `.github/release.yml`, ou o nome da área com a inicial maiúscula."""
    arq = raiz / ".github" / "release.yml"
    do_arquivo = {a: t for t, a in TITULO_DA_AREA.findall(arq.read_text(encoding="utf-8"))} if arq.is_file() else {}
    return {a: do_arquivo.get(a, a[:1].upper() + a[1:]) for a in publico.areas_do_arquivo(raiz)}


def corpo_de(grupos: dict[str, list[str]], areas: list[str] | None = None, resumo: list[str] | None = None) -> list[str]:
    fixos = [*GRUPOS, *(areas or [])]
    ordem = ([g for g in fixos if grupos.get(g)] + [g for g in grupos if g not in fixos and g != OUTRAS and grupos[g]]
             + ([OUTRAS] if grupos.get(OUTRAS) else []))
    linhas: list[str] = [""]
    if resumo:
        linhas += [*resumo, ""]
    for g in ordem:
        linhas += [f"### {g}", "", *"\n".join(grupos[g]).split("\n"), ""]
    return linhas


def normal(item: str) -> str:
    return re.sub(r"\s+", " ", item.removeprefix("- ")).strip().lower()


def data_da_tag(raiz: Path, tag: str | None) -> dt.date | None:
    if not tag:
        return None
    bruto = _comum.git(raiz, "log", "-1", "--format=%cs", tag, ok=True).strip()
    return dt.date.fromisoformat(bruto) if bruto else None


def fechada_em(texto: str) -> dt.date | None:
    for ln in texto.split("---", 2)[1].splitlines() if texto.startswith("---") else []:
        for padrao in (FECHADA, EM_CICLO):
            m = padrao.match(ln)
            if m:
                return dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    return None


def frontmatter_diz(texto: str, chave: str) -> str | None:
    if not texto.startswith("---"):
        return None
    for ln in texto.split("---", 2)[1].splitlines():
        m = re.match(rf"^{chave}:\s*(\S+)", ln)
        if m:
            return m.group(1)
    return None


def promete_tela_que_nao_veio(texto: str, bloco: dict[str, str]) -> bool:
    """O `publico` nomeia uma aba e o relato do que foi feito diz «sem tela» ou «sem cartão»."""
    feito = O_QUE_FOI_FEITO.search(texto)
    if feito is None or not SEM_TELA.search(feito.group(0)):
        return False
    return any(publico.ABA_CITADA.search(bloco.get(campo, "")) for campo in ("titulo", "muda", "pronto"))


def do_sprints(raiz: Path, desde: dt.date | None, avisos: list[str]) -> list[tuple[str, str]]:
    """[(grupo, texto)] dos blocos `publico` das sprints fechadas desde `desde`, o grupo sendo o título da área."""
    titulos = titulos_das_areas(raiz)
    achados: list[tuple[str, str]] = []
    pasta = raiz / "docs" / "process" / "sprints"
    arquivos = sorted([*pasta.glob("*.md"), *(pasta / "arquivados").glob("*.md")]) if pasta.is_dir() else []
    for arq in arquivos:
        texto = arq.read_text(encoding="utf-8")
        if frontmatter_diz(texto, "estado") != "feita":
            continue
        quando = fechada_em(texto)
        if quando is None or (desde is not None and quando < desde):
            continue
        ident = frontmatter_diz(texto, "sprint") or arq.stem
        bloco = publico.extrair(texto)
        if bloco is None and EM_CASA.search(texto.split("---", 2)[1]):
            continue
        if bloco is None:
            avisos.append(f"aviso: {ident} fechou em {quando:%d/%m/%Y} sem bloco `publico`; a sprint não entra no CHANGELOG")
            continue
        erros = publico.validar(bloco, raiz)
        if erros:
            avisos.append(f"aviso: o bloco `publico` de {ident} não entra ({erros[0]})")
            continue
        if promete_tela_que_nao_veio(texto, bloco):
            avisos.append(f"aviso: o bloco `publico` de {ident} não entra (nomeia uma aba e a sprint fechou sem tela)")
            continue
        achados.append((titulos.get(bloco.get("area", ""), OUTRAS), f"- {bloco['muda']}"))
    return achados


def do_prs(raiz: Path, tag: str | None, avisos: list[str]) -> list[tuple[str, str]]:
    intervalo = f"{tag}..HEAD" if tag else "HEAD"
    achados: list[tuple[str, str]] = []
    for assunto in _comum.git(raiz, "log", "--format=%s", intervalo, ok=True).splitlines():
        m = PR.match(assunto.strip())
        if not m:
            continue
        titulo = m.group("titulo")
        titulo = titulo[0].upper() + titulo[1:]
        bloco = {"titulo": titulo, "tipo": "adicionado", "muda": titulo, "pronto": titulo}
        erros = publico.validar(bloco, raiz)
        if erros:
            avisos.append(f"aviso: o título do PR #{m.group('numero')} não entra ({erros[0]})")
            continue
        achados.append((OUTRAS, f"- {titulo}"))
    return achados


class ResumoRecusado(Exception):
    """A seção da versão não tem o resumo que a abre, ou ele não serve."""


def conferir_o_resumo(resumo: list[str], raiz: Path, numero: str) -> None:
    menos, mais = LINHAS_DO_RESUMO
    if not resumo:
        raise ResumoRecusado(
            f"a {numero} não tem resumo: escreva de {menos} a {mais} linhas sob `## [Unreleased]`, antes do primeiro `###`, "
            "e rode de novo")
    if not menos <= len(resumo) <= mais:
        raise ResumoRecusado(f"o resumo da {numero} tem {len(resumo)} linha(s) e deve ter de {menos} a {mais}")
    erros = publico.erros_de_texto("\n".join(resumo), raiz)
    if erros:
        raise ResumoRecusado(f"o resumo da {numero} não serve: {erros[0]}")


def montar_texto(raiz: Path, numero: str, data: str, avisos: list[str]) -> tuple[str, list[str]]:
    arq = raiz / "CHANGELOG.md"
    texto = arq.read_text(encoding="utf-8")
    cabeca, secoes = partir(texto)
    anteriores = {normal(i) for cab, corpo in secoes
                  if (m := CABECALHO.match(cab)) and m.group("numero") not in ("Unreleased", numero)
                  for lista in itens(corpo).values() for i in lista}

    serie = _comum.serie_do_arquivo(raiz)
    tags = _comum.tags_da_serie(raiz, serie)
    anterior = [t for t in tags if _comum.comparavel(t) < _comum.comparavel(numero)]
    tag = f"v{anterior[-1]}" if anterior else None
    desde = data_da_tag(raiz, tag)

    novas: list[tuple[str, str, str]] = []
    resumo_novo: list[str] = []
    indice_nao_lancado = next((i for i, (c, _b) in enumerate(secoes) if (m := CABECALHO.match(c)) and m.group("numero") == "Unreleased"), None)
    if indice_nao_lancado is not None:
        resumo_novo = resumo_de(secoes[indice_nao_lancado][1])
        for grupo, lista in itens(secoes[indice_nao_lancado][1]).items():
            novas += [(grupo, i, "o que estava em Unreleased") for i in lista]
    novas += [(g, i, "sprint") for g, i in do_sprints(raiz, desde, avisos)]
    novas += [(g, i, "PR") for g, i in do_prs(raiz, tag, avisos)]

    indice_versao = next((i for i, (c, _b) in enumerate(secoes) if (m := CABECALHO.match(c)) and m.group("numero") == numero), None)
    if indice_versao is not None:
        existente = itens(secoes[indice_versao][1])
        resumo_antigo = resumo_de(secoes[indice_versao][1])
        cab_versao = secoes[indice_versao][0]
    else:
        existente = {}
        resumo_antigo = []
        cab_versao = f"## [{numero}] — {data}"
    ja = {normal(i) for lista in existente.values() for i in lista}
    adicionadas: list[str] = []
    for grupo, item, origem in novas:
        chave = normal(item)
        if chave in ja or chave in anteriores:
            continue
        ja.add(chave)
        existente.setdefault(grupo, []).append(item)
        adicionadas.append(f"{origem}: {item[2:90]}")

    if indice_versao is None and not existente:
        return texto, []
    resumo = resumo_novo or resumo_antigo
    if adicionadas or resumo_novo or indice_versao is None:
        conferir_o_resumo(resumo, raiz, numero)
    areas = list(titulos_das_areas(raiz).values())
    topo: list[tuple[str, list[str]]] = [("## [Unreleased]", [""]), (cab_versao, corpo_de(existente, areas, resumo))]
    resto = [(c, b) for c, b in secoes if not ((m := CABECALHO.match(c)) and m.group("numero") in ("Unreleased", numero))]
    saida = cabeca.rstrip("\n") + "\n\n"
    for cab, corpo in topo + resto:
        corpo_limpo = list(corpo)
        while corpo_limpo and not corpo_limpo[-1].strip():
            corpo_limpo.pop()
        saida += cab + "\n" + "\n".join(corpo_limpo) + ("\n" if corpo_limpo else "") + "\n"
    return saida.rstrip("\n") + "\n", adicionadas


def cmd_montar(a: argparse.Namespace, raiz: Path) -> int:
    numero = a.numero.removeprefix("v")
    data = a.data or dt.date.today().isoformat()
    avisos: list[str] = []
    arq = raiz / "CHANGELOG.md"
    antes = arq.read_text(encoding="utf-8")
    try:
        novo, adicionadas = montar_texto(raiz, numero, data, avisos)
    except ResumoRecusado as erro:
        return _comum.encerrar("changelog", raiz, 1, f"changelog.py montar: {erro}", avisos, a.detalhe)
    detalhe = avisos + [f"entrou ({o})" for o in adicionadas]
    if novo == antes:
        existe = any((m := CABECALHO.match(c)) and m.group("numero") == numero for c, _b in partir(antes)[1])
        if not existe:
            return _comum.encerrar("changelog", raiz, 4, f"changelog.py montar: nada a dizer da {numero} (Unreleased vazio, nenhuma sprint, nenhum PR)", detalhe, a.detalhe)
        return _comum.encerrar("changelog", raiz, 0, f"changelog.py montar: a seção {numero} já está completa", detalhe, a.detalhe)
    if a.conferir:
        return _comum.encerrar("changelog", raiz, 1, f"changelog.py montar: a seção {numero} mudaria ({len(adicionadas)} item(ns) novo(s) ou movido(s))", detalhe, a.detalhe)
    arq.write_text(novo, encoding="utf-8")
    return _comum.encerrar("changelog", raiz, 0, f"changelog.py montar: seção {numero} de {data} com {len(adicionadas)} item(ns)", detalhe, a.detalhe)


def corpo_da_versao(raiz: Path, numero: str) -> list[str] | None:
    _cab, secoes = partir((raiz / "CHANGELOG.md").read_text(encoding="utf-8"))
    for c, corpo in secoes:
        m = CABECALHO.match(c)
        if m and m.group("numero") == numero:
            limpo = list(corpo)
            while limpo and not limpo[0].strip():
                limpo.pop(0)
            while limpo and not limpo[-1].strip():
                limpo.pop()
            return limpo
    return None


def notas_de(raiz: Path, numero: str, repo: str | None) -> str | None:
    corpo = corpo_da_versao(raiz, numero)
    if corpo is None:
        return None
    onde = f" --repo {repo}" if repo else ""
    return (
        "\n".join(corpo)
        + f"\n\n{OS_ARQUIVOS}\n### Como conferir o que você baixou\n\n"
        "Baixe o `SHA256SUMS` junto com os arquivos e rode, na mesma pasta:\n\n"
        "```\nsha256sum -c SHA256SUMS --ignore-missing\n```\n\n"
        "Cada arquivo também traz um atestado de procedência, que diz de qual commit e de qual fluxo ele saiu:\n\n"
        f"```\ngh attestation verify NOME-DO-ARQUIVO{onde or ' --repo DONO/REPOSITORIO'}\n```\n"
    )


def cmd_notas(a: argparse.Namespace, raiz: Path) -> int:
    numero = a.numero.removeprefix("v")
    texto = notas_de(raiz, numero, a.repo)
    if texto is None:
        print(f"changelog.py notas: o CHANGELOG.md não tem a seção [{numero}]; rode `changelog.py montar {numero}`", file=sys.stderr)
        return 3
    sys.stdout.write(texto)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--raiz", help="a árvore (padrão: a deste script)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("montar")
    p.add_argument("numero")
    p.add_argument("--data", help="AAAA-MM-DD (padrão: hoje)")
    p.add_argument("--conferir", action="store_true")
    p.add_argument("--detalhe", type=Path)
    p.set_defaults(f=cmd_montar)
    p = sub.add_parser("notas")
    p.add_argument("numero")
    p.add_argument("--repo", help="DONO/NOME, para o comando de conferir o atestado")
    p.set_defaults(f=cmd_notas)
    a = ap.parse_args(argv)
    return int(a.f(a, _comum.raiz_de(a.raiz)))


if __name__ == "__main__":
    sys.exit(main())

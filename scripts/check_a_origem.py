#!/usr/bin/env python3
"""A catraca da origem: três números que só descem (A-CATRACA-DA-ORIGEM-01).

A origem de um defeito mora no dono do eixo (conexão, modo, máscara, número do
jogador, modelo do controle), e a cura vale para todos. O que esta catraca
impede é o caminho inverso: um caso especial escrito longe do dono, um remendo
de sintoma, um projeto que só cresce.

1. ``casos-especiais-fora-do-dono``: ramo (``if``, expressão condicional,
   ``match``) que decide por um eixo e mora FORA dos donos declarados em
   ``docs/data/donos-de-comportamento.csv`` (linhas de veredito ``EIXO``).
2. ``remendos-de-sintoma``: ``sleep`` com constante, laço de nova tentativa,
   prazo (``timeout=``) por constante e ``except`` que só engole. O teto é POR
   ARQUIVO: um remendo novo não se esconde atrás de um velho que saiu noutro.
3. ``tamanho``: as linhas de ``src/``, ``tests/``, ``scripts/`` e ``docs/``
   versionados. Crescer só passa se algum commit da faixa trouxer
   ``Origem: <id>`` com o id de uma linha do ``mapa-controles.csv`` ou de uma
   decisão do ``decisoes-dela.csv``.

Medido por AST, nunca por palavra no texto: comentário e string não contam.
O teto mora em ``docs/data/a-catraca-da-origem.json`` e DESCE sozinho (o portão
o regrava menor; nunca maior). Para subir de propósito, ``--forcar-piso``.

Faixa dos commits do tamanho: ``--base REV``, ou ``HEFESTO_BASE_DA_LEVA``, ou o
último commit que mexeu no teto. Uma ``Origem:`` ainda sem commit entra por
``--origem ID`` ou ``HEFESTO_ORIGEM``.
"""

from __future__ import annotations

import ast
import csv
import os
import re
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from catraca import (
    Catraca,
    CatracaTorta,
    Censo,
    Medida,
    Veredito,
    executar,
    montar_argumentos,
)

PACOTE = Path("src") / "hefesto_dualsense4unix"
CADERNO = Path("docs/data/a-catraca-da-origem.json")
DONOS = Path("docs/data/donos-de-comportamento.csv")
MAPA = Path("docs/data/mapa-controles.csv")
DECISOES = Path("docs/data/decisoes-dela.csv")

VEREDITO_DE_EIXO = "EIXO"
CASOS = "casos-especiais-fora-do-dono"
REMENDOS = "remendos-de-sintoma"
TAMANHO = "tamanho"

# ---------------------------------------------------------------------------
# Os eixos: o NOME que o código dá ao eixo e o VOCABULÁRIO da constante do outro
# lado da comparação. Nome sem constante do eixo não conta (``modo != 432`` é
# permissão de arquivo), e constante sem nome só conta onde ela não é ambígua.

_NOMES = {
    "transporte": r"_*(transporte|transport|via)",
    "modo": r"_*(modo|modo_atual|mode)",
    "mascara": r"_*(mascara|mascara_no_jogo|mask)",
    "jogador": r"_*(jogador|player|player_index|slot|numero_do_jogador)",
    "modelo": r"_*(vid|pid|vendor_id|product_id|modelo)",
}
_VOCABULARIO: dict[str, frozenset[str | int]] = {
    "transporte": frozenset({"usb", "bt", "bluetooth", "cabo", "radio", "rádio"}),
    "modo": frozenset({"xbox", "xbox360", "nativo", "nativa", "native", "steam",
                       "steam_input", "desligado", "controlar_pc", "passthrough"}),
    "mascara": frozenset({"dualsense", "xbox360", "xbox 360", "xbox_360",
                          "nintendo", "nintendo_pro", "steam_input"}),
    "jogador": frozenset({0, 1, 2, 3, 4}),
    "modelo": frozenset({0x054C, 0x0CE6, 0x0DF2, 0x045E, 0x028E, 0x057E}),
}
#: constantes tão específicas do eixo que valem sem o nome (``x == "bt"``).
_SEM_NOME = {
    "transporte": frozenset({"usb", "bt", "bluetooth"}),
    "modelo": frozenset({0x054C, 0x0CE6, 0x0DF2, 0x045E, 0x028E, 0x057E}),
}
_NOME_RX = {eixo: re.compile(rx + "$", re.I) for eixo, rx in _NOMES.items()}


def _nome_do_lado(no: ast.AST) -> str | None:
    """O nome que o código dá ao valor: variável, atributo, ``["x"]`` ou ``.get("x")``."""
    if isinstance(no, ast.Name):
        return no.id
    if isinstance(no, ast.Attribute):
        return no.attr
    if isinstance(no, ast.Subscript) and isinstance(no.slice, ast.Constant):
        return str(no.slice.value)
    if (isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute)
            and no.func.attr == "get" and no.args
            and isinstance(no.args[0], ast.Constant)):
        return str(no.args[0].value)
    return None


def _constantes(no: ast.AST) -> list[str | int] | None:
    """As constantes de um lado da comparação, ou ``None`` se há algo que não é constante."""
    if isinstance(no, ast.Constant) and isinstance(no.value, (str, int)) \
            and not isinstance(no.value, bool):
        valor = no.value
        return [valor.lower() if isinstance(valor, str) else valor]
    if isinstance(no, (ast.Tuple, ast.List, ast.Set)) and no.elts:
        todas: list[str | int] = []
        for elt in no.elts:
            sub = _constantes(elt)
            if sub is None:
                return None
            todas.extend(sub)
        return todas
    return None


def _eixos_da_comparacao(comp: ast.Compare) -> set[str]:
    if not all(isinstance(op, (ast.Eq, ast.NotEq, ast.In, ast.NotIn)) for op in comp.ops):
        return set()
    lados = [comp.left, *comp.comparators]
    achados: set[str] = set()
    for i, lado in enumerate(lados):
        nome = _nome_do_lado(lado)
        outros = [_constantes(x) for j, x in enumerate(lados) if j != i]
        if any(c is None for c in outros):
            continue
        consts = [v for c in outros if c for v in c]
        for eixo in _NOMES:
            vocabulario = _VOCABULARIO[eixo]
            pelo_nome = nome is not None and _NOME_RX[eixo].match(nome) is not None \
                and any(v in vocabulario for v in consts)
            if pelo_nome or any(v in _SEM_NOME.get(eixo, frozenset()) for v in consts):
                achados.add(eixo)
    return achados


def _testes_de_ramo(arvore: ast.AST) -> Iterable[ast.expr]:
    for no in ast.walk(arvore):
        if isinstance(no, (ast.If, ast.IfExp, ast.While)):
            yield no.test
        elif isinstance(no, ast.comprehension):
            yield from no.ifs
        elif isinstance(no, ast.Match):
            yield no.subject


def ramos_de_eixo(fonte: str) -> list[tuple[int, str]]:
    """Cada ramo que decide por um eixo: ``(linha, eixo)``."""
    try:
        arvore = ast.parse(fonte)
    except SyntaxError:
        return []
    achados: list[tuple[int, str]] = []
    vistos: set[tuple[int, str]] = set()
    for teste in _testes_de_ramo(arvore):
        for no in ast.walk(teste):
            if isinstance(no, ast.Compare):
                for eixo in _eixos_da_comparacao(no):
                    chave = (no.lineno, eixo)
                    if chave not in vistos:
                        vistos.add(chave)
                        achados.append(chave)
    return sorted(achados)


# ---------------------------------------------------------------------------
# Os remendos de sintoma.

_PRAZOS = frozenset({"timeout", "prazo", "deadline", "timeout_s", "timeout_sec"})


def _e_sleep(no: ast.Call) -> bool:
    f = no.func
    nome = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
    return nome == "sleep"


def _e_constante_numerica(no: ast.AST) -> bool:
    if isinstance(no, ast.UnaryOp):
        no = no.operand
    return isinstance(no, ast.Constant) and isinstance(no.value, (int, float)) \
        and not isinstance(no.value, bool)


def _so_engole(corpo: list[ast.stmt]) -> bool:
    """O corpo do ``except`` não faz nada: ``pass``, ``continue``, ``return`` ou ``return None``."""
    for inst in corpo:
        if isinstance(inst, (ast.Pass, ast.Continue)):
            continue
        if isinstance(inst, ast.Expr) and isinstance(inst.value, ast.Constant):
            continue
        if isinstance(inst, ast.Return) and (
                inst.value is None
                or (isinstance(inst.value, ast.Constant) and inst.value.value is None)):
            continue
        return False
    return True


def remendos(fonte: str) -> list[tuple[int, str]]:
    """Cada remendo: ``(linha, categoria)``, por AST."""
    try:
        arvore = ast.parse(fonte)
    except SyntaxError:
        return []
    achados: list[tuple[int, str]] = []
    for no in ast.walk(arvore):
        if isinstance(no, ast.Call):
            if _e_sleep(no) and no.args and _e_constante_numerica(no.args[0]):
                achados.append((no.lineno, "sleep-com-constante"))
            for kw in no.keywords:
                if kw.arg in _PRAZOS and _e_constante_numerica(kw.value):
                    achados.append((no.lineno, "prazo-por-constante"))
        elif isinstance(no, ast.ExceptHandler) and _so_engole(no.body):
            achados.append((no.lineno, "except-que-so-engole"))
        elif isinstance(no, (ast.For, ast.While)):
            corpo = ast.Module(body=no.body, type_ignores=[])
            tem_try = any(isinstance(x, ast.Try) for x in ast.walk(corpo))
            tem_sleep = any(isinstance(x, ast.Call) and _e_sleep(x) for x in ast.walk(corpo))
            if tem_try and tem_sleep:
                achados.append((no.lineno, "laco-de-nova-tentativa"))
    return sorted(achados)


# ---------------------------------------------------------------------------
# Os donos: um registro só, o CSV que já existe.


def donos_dos_eixos(raiz: Path) -> dict[str, set[str]]:
    """``eixo -> arquivos dono`` (relativos ao pacote), das linhas ``EIXO`` do CSV."""
    caminho = raiz / DONOS
    if not caminho.exists():
        raise CatracaTorta(f"{DONOS} não existe: sem dono declarado, todo ramo seria 'fora'.")
    donos: dict[str, set[str]] = {}
    with caminho.open(encoding="utf-8", newline="") as fh:
        for linha in csv.DictReader(fh):
            if linha["veredito"] != VEREDITO_DE_EIXO:
                continue
            eixo = linha["comportamento"].split(".", 1)[-1].split("/", 1)[0]
            arquivo = linha["dono"].rpartition(":")[0]
            donos.setdefault(eixo, set()).add(arquivo)
    faltam = sorted(set(_NOMES) - set(donos))
    if faltam:
        raise CatracaTorta(
            f"eixo sem dono em {DONOS}: {', '.join(faltam)}. Sem dono declarado, "
            "o eixo inteiro contaria como 'fora' e o teto nasceria sem sentido.")
    return donos


def _arquivos_do_pacote(raiz: Path) -> list[Path]:
    base = raiz / PACOTE
    return sorted(
        p for p in base.rglob("*.py")
        if not {"paginas", "__pycache__"} & set(p.relative_to(base).parts))  # noqa-acento: PASTA


def censo_dos_casos(raiz: Path) -> Censo:
    donos = donos_dos_eixos(raiz)
    base = raiz / PACOTE
    arquivos = _arquivos_do_pacote(raiz)
    por_item: dict[str, int] = {}
    for p in arquivos:
        rel = p.relative_to(base).as_posix()
        for _linha, eixo in ramos_de_eixo(p.read_text(encoding="utf-8")):
            if rel in donos[eixo]:
                continue
            por_item[f"{rel}::{eixo}"] = por_item.get(f"{rel}::{eixo}", 0) + 1
    return Censo(
        numero=sum(por_item.values()), universo=len(arquivos), por_item=por_item,
        nota="ramos por eixo, fora dos arquivos dono de cada eixo")


def _contagem_por_arquivo(raiz: Path) -> tuple[dict[str, int], int]:
    base = raiz / PACOTE
    arquivos = _arquivos_do_pacote(raiz)
    por_item: dict[str, int] = {}
    for p in arquivos:
        quantos = len(remendos(p.read_text(encoding="utf-8")))
        if quantos:
            por_item[p.relative_to(base).as_posix()] = quantos
    return por_item, len(arquivos)


def censo_dos_remendos(raiz: Path) -> Censo:
    """O total de remendos; a contagem por arquivo vai em ``por_item`` e é o teto de cada um."""
    hoje, universo = _contagem_por_arquivo(raiz)
    return Censo(numero=sum(hoje.values()), universo=universo, por_item=hoje,
                 nota="remendos de sintoma por arquivo")


class CatracaDaOrigem(Catraca):
    """O motor, com uma regra a mais: o teto dos remendos é POR ARQUIVO."""

    def _comparar_uma(self, medida: Medida) -> Veredito:
        v = super()._comparar_uma(medida)
        if medida.nome != REMENDOS or v.estado != "VERDE":
            return v
        subiram = tuple(
            f"{arq}: {v.piso.por_item.get(arq, 0)} -> {n}"
            for arq, n in sorted(v.censo.por_item.items())
            if n > v.piso.por_item.get(arq, 0))
        if not subiram:
            return v
        return Veredito(
            medida, "VERMELHO", v.numero, v.piso, v.censo,
            queixas=(f"«{medida.nome}»: o total não subiu, mas há remendo NOVO em "
                     "arquivo que não tinha esse teto — um remendo novo não se esconde "
                     "atrás de um velho que saiu noutro lugar.",),
            entrou=subiram)


# ---------------------------------------------------------------------------
# O tamanho.

_EXTENSOES = frozenset({".py", ".sh", ".md", ".csv", ".json", ".html", ".toml", ".yml",
                        ".yaml", ".txt", ".css", ".js", ".po", ".pot", ".service", ".rules",
                        ".conf", ".desktop", ".svg", ".xml", ".cfg", ".ini"})
_PASTAS = ("src", "tests", "scripts", "docs")


def _versionados(raiz: Path) -> list[Path]:
    if (raiz / ".git").exists():
        saida = subprocess.run(
            ["git", "ls-files", "-z", "--", *_PASTAS], cwd=raiz, capture_output=True, check=False)
        if saida.returncode == 0:
            return [raiz / p for p in saida.stdout.decode().split("\0") if p]
    return [p for pasta in _PASTAS for p in sorted((raiz / pasta).rglob("*")) if p.is_file()]


def censo_do_tamanho(raiz: Path) -> Censo:
    por_pasta = dict.fromkeys(_PASTAS, 0)
    arquivos = 0
    for p in _versionados(raiz):
        if p.suffix not in _EXTENSOES or not p.is_file() or p == raiz / CADERNO:
            continue
        try:
            texto = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        arquivos += 1
        por_pasta[p.relative_to(raiz).parts[0]] += texto.count("\n")
    return Censo(numero=sum(por_pasta.values()), universo=arquivos, por_item=por_pasta,
                 nota="linhas de src, tests, scripts e docs versionados")


MEDIDAS = (
    Medida(CASOS, "ramos que decidem por eixo, escritos fora do dono do eixo",
           censo_dos_casos, "ramos"),
    Medida(REMENDOS, "remendos de sintoma acima do teto de cada arquivo",
           censo_dos_remendos, "remendos"),
    Medida(TAMANHO, "linhas de src, tests, scripts e docs versionados",
           censo_do_tamanho, "linhas"),
)

# ---------------------------------------------------------------------------
# A origem: o que paga o crescimento.

_TRAILER = re.compile(r"^Origem:[ \t]*(\S+)[ \t]*$", re.M)


def ids_validos(raiz: Path) -> set[str]:
    ids: set[str] = set()
    for arquivo in (MAPA, DECISOES):
        caminho = raiz / arquivo
        if caminho.exists():
            with caminho.open(encoding="utf-8", newline="") as fh:
                ids.update(linha[0].strip() for linha in csv.reader(fh) if linha)
    return ids


def origens_da_faixa(raiz: Path, base: str | None, extra: str | None = None) -> list[str]:
    """Os ``Origem:`` das mensagens de ``base..HEAD`` (git), mais a que ainda não tem commit."""
    achadas: list[str] = []
    extra = (extra or os.environ.get("HEFESTO_ORIGEM", "")).strip()
    if extra:
        achadas.append(extra)
    if base is None:
        base = os.environ.get("HEFESTO_BASE_DA_LEVA") or _ultimo_commit_do_teto(raiz)
    if base and set(base) == {"0"}:
        base = _ultimo_commit_do_teto(raiz)  # push que cria branch: o `before` é só zeros
    if base:
        saida = subprocess.run(
            ["git", "log", "--format=%B%x00", f"{base}..HEAD"], cwd=raiz,
            capture_output=True, text=True, check=False)
        if saida.returncode == 0:
            for mensagem in saida.stdout.split("\0"):
                achadas.extend(_TRAILER.findall(mensagem))
    return achadas


def _ultimo_commit_do_teto(raiz: Path) -> str | None:
    saida = subprocess.run(
        ["git", "log", "-1", "--format=%H", "--", str(CADERNO)], cwd=raiz,
        capture_output=True, text=True, check=False)
    return saida.stdout.strip() or None if saida.returncode == 0 else None


def avaliar_o_tamanho(veredito: Veredito, raiz: Path, base: str | None,
                      origem: str | None) -> tuple[bool, str]:
    """Cresceu? Passa se a faixa trouxer uma ``Origem:`` que existe. ``(passa, relato)``."""
    if veredito.estado != "VERMELHO" or veredito.numero is None or veredito.piso.numero is None:
        return veredito.passa, ""
    delta = veredito.numero - veredito.piso.numero
    ids = ids_validos(raiz)
    achadas = origens_da_faixa(raiz, base, origem)
    boas = [o for o in achadas if o in ids]
    ruins = [o for o in achadas if o not in ids]
    if boas:
        return True, (f"tamanho: +{delta} linhas ({veredito.piso.numero} -> {veredito.numero}),"
                      f" pagas por Origem: {', '.join(sorted(set(boas)))}")
    dica = (f" (Origem sem linha no mapa nem nas decisões: {', '.join(sorted(set(ruins)))})"
            if ruins else "")
    return False, (f"tamanho: +{delta} linhas ({veredito.piso.numero} -> {veredito.numero})"
                   f" sem `Origem: <id>` na faixa{dica}. O id é o de uma linha do "
                   f"{MAPA} ou de uma decisão do {DECISOES}.")


# ---------------------------------------------------------------------------


def _desce_sozinho(catraca: Catraca, vereditos: list[Veredito]) -> list[str]:
    """Regrava o teto menor quando o número desceu. Nunca maior."""
    descidas = []
    for v in vereditos:
        if v.estado != "VERDE" or v.numero is None or v.piso.numero is None:
            continue
        mudou = v.numero < v.piso.numero or (
            v.medida.nome == REMENDOS and v.censo.por_item != v.piso.por_item)
        if mudou:
            catraca.aceitar([v.medida.nome], "o teto desceu sozinho com o número")
            descidas.append(v.medida.nome)
    return descidas


def main(argv: list[str] | None = None) -> int:
    p = montar_argumentos(__doc__.split("\n", 1)[0])
    p.add_argument("--base", default=None, help="a faixa dos commits do tamanho (base..HEAD)")
    p.add_argument("--origem", default=None, help="uma Origem ainda sem commit")
    a = p.parse_args(argv)
    raiz = Path(a.raiz) if a.raiz else RAIZ
    catraca = CatracaDaOrigem(raiz / CADERNO, MEDIDAS, raiz)
    if a.aceitar is not None or a.forcar_piso:
        return executar(catraca, a, "A catraca da origem")
    try:
        vereditos = catraca.comparar()
    except CatracaTorta as erro:
        print(f"RECUSADO: {erro}", file=sys.stderr)
        return 2
    rc = 0
    for v in vereditos:
        passa = v.passa
        relato = ""
        if v.medida.nome == TAMANHO:
            passa, relato = avaliar_o_tamanho(v, raiz, a.base, a.origem)
        agora = "—" if v.numero is None else v.numero
        piso = "(sem piso)" if not v.piso.existe else v.piso.numero
        print(f"  [{'VERDE' if passa else v.estado:<10}] {v.medida.nome:<30} hoje={agora} piso={piso}")
        if relato:
            print(f"      {relato}")
        if not passa:
            rc = 1
            for q in v.queixas:
                print(f"      {q}")
            for linha in v.entrou[:30]:
                print(f"      {linha}")
    if rc == 0:
        for nome in _desce_sozinho(catraca, vereditos):
            print(f"  o teto de «{nome}» desceu e foi regravado")
    else:
        print("\nA catraca da origem REPROVOU: a cura mora no dono do eixo, não ao lado dele.")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())

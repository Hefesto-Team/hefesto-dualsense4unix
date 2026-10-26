#!/usr/bin/env python3
"""o-texto-enxuto.py — a pergunta única do texto enxuto: o que as réguas do texto reprovariam.

    o-texto-enxuto.py ARQUIVO...             aponta o que está errado (rc 1 se achou)
    o-texto-enxuto.py --aplicar ARQUIVO...   corrige o mecânico (o «dela» de pessoa) e aponta o resto
    o-texto-enxuto.py --mudados              o que mudou desde o pé comum com o `dev` (é o portão `texto-enxuto`)
    o-texto-enxuto.py --tudo                 todos os versionados (meio minuto: o portão não o usa)
    o-texto-enxuto.py --catraca              o volume de comentário e docstring em src/ só desce

As réguas moram nos donos delas e são IMPORTADAS daqui, nunca copiadas: o «dela» em
``neutralizar-o-texto.py``, a docstring longa em ``check_docstring_longa.py``, o comentário em
``check_codigo_sem_comentario.py`` e a citação nova em ``validar-citacoes-de-linha.py``. Régua ausente
é rc 2, nunca verde.
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import io
import re
import subprocess
import sys
import tokenize
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
sys.path.insert(0, str(AQUI))

from catraca import Catraca, Censo, Medida, executar, montar_argumentos

PACOTE = "src/hefesto_dualsense4unix/"
CADERNO = Path("docs/data/o-texto-enxuto.json")
NOME = "texto-em-src"
TETO_DA_SAIDA = 12
PISO_DO_ITEM = 40

RAIZES_DO_PYTHON = ("src/", "tests/", "scripts/")
REFS_DA_BASE = ("dev", "origin/dev")

AJUDA = {
    "dela": "rode `--aplicar`: a troca é mecânica",
    "dela-no-codigo": "mora num texto que o código usa (a AST mudaria): troque à mão e, se vira página, republique",
    "comentário": ("o código não tem comentário (D-2610-O-CODIGO-NAO-TEM-COMENTARIO): o porquê vai à docstring "
                   "ou a docs/research/o-porque-dos-modulos.md, e a diretiva fica nua"),
    "docstring": "a docstring fica com o contrato; a história vai para docs/research/o-porque-dos-modulos.md",
}


class ReguaAusente(RuntimeError):
    """A régua que esta pergunta importa não está na árvore: rc 2, nunca verde."""


_CARREGADOS: dict[str, ModuleType] = {}


def regua(arquivo: str) -> ModuleType:
    """O módulo de uma régua, carregado do ``scripts/`` deste script (``neutralizar-o-texto.py``…)."""
    if arquivo not in _CARREGADOS:
        caminho = AQUI / arquivo
        if not caminho.is_file():
            raise ReguaAusente(f"a régua {arquivo} não está em {AQUI}")
        nome = "texto_enxuto_" + re.sub(r"\W", "_", caminho.stem)
        spec = importlib.util.spec_from_file_location(nome, caminho)
        if spec is None or spec.loader is None:
            raise ReguaAusente(f"a régua {arquivo} não carrega")
        modulo = importlib.util.module_from_spec(spec)
        sys.modules[nome] = modulo
        try:
            spec.loader.exec_module(modulo)
        except Exception as erro:
            del sys.modules[nome]
            raise ReguaAusente(f"a régua {arquivo} quebrou ao carregar: {type(erro).__name__}") from erro
        _CARREGADOS[arquivo] = modulo
    return _CARREGADOS[arquivo]


@dataclass(frozen=True)
class Achado:
    arquivo: str
    linha: int
    regua: str
    texto: str
    mecanico: bool = False

    def __str__(self) -> str:
        return f"{self.arquivo}:{self.linha} [{self.regua}] {self.texto}"


def _git(raiz: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(raiz), *args], capture_output=True, text=True, check=False)


def no_head(raiz: Path, rel: str) -> str:
    """O texto do arquivo em ``HEAD`` (vazio se ele nasceu agora): a base de «subiu»."""
    feito = _git(raiz, "show", f"HEAD:{rel}")
    return feito.stdout if feito.returncode == 0 else ""


def _primeira_linha_trocada(antes: str, depois: str) -> tuple[int, int]:
    velhas, novas = antes.split("\n"), depois.split("\n")
    trocadas = [i for i, (a, b) in enumerate(zip(velhas, novas, strict=False), 1) if a != b]
    primeira = trocadas[0] if trocadas else min(len(velhas), len(novas))
    return primeira, max(len(trocadas), 1)


def _linha_do_nome(texto: str, nome: str, linhas: int) -> int:
    """A linha da ``def``/``class`` cuja docstring tem ``linhas`` linhas (1 se o ``ast`` não a acha)."""
    try:
        arvore = ast.parse(texto)
    except SyntaxError:
        return 1
    for no in ast.walk(arvore):
        if getattr(no, "name", "<módulo>") != nome:
            continue
        doc = ast.get_docstring(no, clean=False)  # type: ignore[arg-type]
        if doc is not None and len(doc.splitlines()) == linhas:
            return getattr(no, "lineno", 1)
    return 1


def docstrings_novas(rel: str, texto: str, head: str) -> list[Achado]:
    """As docstrings acima do limite que o arquivo não tinha em ``HEAD`` (a catraca é por total, aqui é por arquivo)."""
    dl = regua("check_docstring_longa.py")
    agora = dl.docstrings_longas(texto)
    if not agora:
        return []
    antes = dl.docstrings_longas(head)
    if sum(n for _, n in agora) <= sum(n for _, n in antes):
        return []
    sobra = list(antes)
    achados = []
    for nome, linhas in agora:
        if (nome, linhas) in sobra:
            sobra.remove((nome, linhas))
            continue
        achados.append(Achado(rel, _linha_do_nome(texto, nome, linhas), "docstring",
                              f"`{nome}` tem {linhas} linhas (limite {dl.LIMITE}): {AJUDA['docstring']}"))
    return achados


def comentarios_no_codigo(rel: str, texto: str) -> list[Achado]:
    """Todo comentário que não é diretiva nua, nos cinco tipos do portão ``codigo-sem-comentario``."""
    cs = regua("check_codigo_sem_comentario.py")
    tipo = cs.tipo_do_arquivo(rel, texto.split("\n", 1)[0])
    if tipo is None:
        return []
    return [Achado(rel, a.linha, "comentário", AJUDA["comentário"]) for a in cs.achados_do_texto(texto, tipo, rel)]


def base_de_comparacao(raiz: Path) -> str | None:
    """O ``merge-base`` do ``HEAD`` com o primeiro de ``REFS_DA_BASE`` que existe, ou ``None``."""
    for ref in REFS_DA_BASE:
        feito = _git(raiz, "merge-base", ref, "HEAD")
        if feito.returncode == 0 and feito.stdout.strip():
            return feito.stdout.strip()
    return None


def citacoes_novas(raiz: Path, documentos: set[str]) -> list[Achado]:
    """A citação ``arquivo:linha`` nova, sem nome prometido, nos documentos dados (a régua é do ``--novas``)."""
    vc = regua("validar-citacoes-de-linha.py")
    if not any(vc.vigiado(d) for d in documentos):
        return []
    pe = vc.pe_comum(raiz, None)
    if pe is None:
        return []
    achados, _ = vc.varrer_novas(raiz, pe)
    return [Achado(a.documento, a.linha, "citação", a.motivo) for a in achados if a.documento in documentos]


def _sem_docstrings(fonte: str) -> str:
    arvore = ast.parse(fonte)
    for no in ast.walk(arvore):
        if isinstance(no, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef) and no.body:
            primeiro = no.body[0]
            if isinstance(primeiro, ast.Expr) and isinstance(primeiro.value, ast.Constant) \
                    and isinstance(primeiro.value.value, str):
                no.body = no.body[1:] or [ast.Pass()]
    return ast.dump(arvore)


def mesmo_codigo(antes: str, depois: str) -> bool:
    """A AST, tirando as docstrings, é a mesma? É a prova de que a troca só tocou texto.

    O neutralizador também troca o comentário CSS ou JS dentro de uma string que vira página; isso muda o
    código, então não é mecânico aqui.
    """
    try:
        return _sem_docstrings(antes) == _sem_docstrings(depois)
    except SyntaxError:
        return False


def examinar(raiz: Path, rel: str, texto: str, aplicar: bool) -> tuple[str, list[Achado]]:
    """``(texto corrigido, achados)``: o mecânico sai trocado, o resto vem apontado."""
    achados: list[Achado] = []
    nz = regua("neutralizar-o-texto.py")
    tipo = nz.tipo_do_alvo(rel)
    if tipo is not None:
        novo = nz.reescrever_arquivo(texto, tipo)
        if novo != texto:
            linha, quantas = _primeira_linha_trocada(texto, novo)
            if tipo == "py" and not mesmo_codigo(texto, novo):
                achados.append(Achado(rel, linha, "dela", f"o «dela» que aponta para a pessoa {AJUDA['dela-no-codigo']}"))
            else:
                dito = f"corrigido ({quantas} linha(s) trocada(s))" if aplicar else AJUDA["dela"]
                achados.append(Achado(rel, linha, "dela", f"o «dela» que aponta para a pessoa: {dito}", True))
                if aplicar:
                    texto = novo
    achados += comentarios_no_codigo(rel, texto)
    if not rel.endswith(".py") or not rel.startswith(RAIZES_DO_PYTHON):
        return texto, achados
    head = no_head(raiz, rel)
    if head == texto:
        return texto, achados
    if rel.startswith(PACOTE):
        achados += docstrings_novas(rel, texto, head)
    return texto, achados


def no_escopo(rel: str) -> bool:
    if regua("neutralizar-o-texto.py").tipo_do_alvo(rel) is not None:
        return True
    if rel.endswith(".py") and rel.startswith(RAIZES_DO_PYTHON):
        return True
    return bool(regua("validar-citacoes-de-linha.py").vigiado(rel))


def versionados(raiz: Path) -> list[str]:
    feito = _git(raiz, "ls-files", "-z")
    if feito.returncode != 0:
        raise ReguaAusente("sem git nesta árvore: `--tudo` precisa da lista de versionados")
    return [r for r in feito.stdout.split("\0") if r]


def mudados(raiz: Path) -> list[str]:
    """Os arquivos que mudaram desde o pé comum com o ``dev`` (no CI, ``origin/dev``), mais os novos."""
    base = base_de_comparacao(raiz)
    if base is None:
        raise ReguaAusente("sem base: nem `dev` nem `origin/dev` alcançável deste HEAD (no CI, `fetch-depth: 0`)")
    feito = _git(raiz, "diff", "--name-only", "--diff-filter=ACMR", "-z", base)
    novos = _git(raiz, "ls-files", "-z", "--others", "--exclude-standard")
    return [r for r in (feito.stdout + novos.stdout).split("\0") if r]


def relativos(raiz: Path, pedidos: list[str]) -> list[str]:
    saida = []
    for p in pedidos:
        caminho = Path(p)
        caminho = (caminho if caminho.is_absolute() else Path.cwd() / caminho).resolve()
        try:
            rel = caminho.relative_to(raiz.resolve()).as_posix()
        except ValueError:
            continue
        if caminho.is_file():
            saida.append(rel)
    return saida


def no_indice(raiz: Path, rel: str) -> bool:
    """O arquivo tem mudança staged (vai no commit)?"""
    return _git(raiz, "diff", "--cached", "--quiet", "--", rel).returncode == 1


def rodar(raiz: Path, arquivos: list[str], aplicar: bool, restagear: bool) -> int:
    achados: list[Achado] = []
    corrigidos: list[str] = []
    for rel in sorted(set(arquivos)):
        if not no_escopo(rel):
            continue
        try:
            texto = (raiz / rel).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        novo, achou = examinar(raiz, rel, texto, aplicar)
        achados += achou
        if novo != texto:
            (raiz / rel).write_text(novo, encoding="utf-8")
            corrigidos.append(rel)
    achados += citacoes_novas(raiz, {a for a in arquivos if a.endswith((".md", ".csv"))})
    soltos = []
    for rel in corrigidos:
        if not restagear:
            continue
        if not no_indice(raiz, rel) or _git(raiz, "add", "--", rel).returncode != 0:
            soltos.append(rel)
    restantes = [a for a in achados if not (aplicar and a.mecanico)]
    if not achados and not soltos:
        return 0
    if aplicar:
        print(f"o-texto-enxuto: corrigi {len(corrigidos)} arquivo(s); restam {len(restantes)} achado(s)")
    else:
        print(f"o-texto-enxuto: {len(achados)} achado(s) em {len({a.arquivo for a in achados})} arquivo(s)")
    for a in achados[:TETO_DA_SAIDA]:
        print(a)
    if len(achados) > TETO_DA_SAIDA:
        print(f"(e mais {len(achados) - TETO_DA_SAIDA})")
    for rel in soltos:
        print(f"{rel}: corrigido no disco, mas fora do índice; rode `git add {rel}`")
    return 1 if restantes or soltos else 0


def volume_do_texto(texto: str) -> tuple[int, int]:
    """``(linhas de comentário, linhas de docstring)`` de um fonte Python."""
    comentarios = 0
    try:
        for tok in tokenize.generate_tokens(io.StringIO(texto).readline):
            comentarios += tok.type == tokenize.COMMENT
    except (tokenize.TokenError, IndentationError, SyntaxError):
        pass
    docstrings = 0
    try:
        arvore = ast.parse(texto)
    except SyntaxError:
        return comentarios, 0
    for no in ast.walk(arvore):
        if isinstance(no, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef) and no.body:
            primeiro = no.body[0]
            if isinstance(primeiro, ast.Expr) and isinstance(primeiro.value, ast.Constant) \
                    and isinstance(primeiro.value.value, str) and primeiro.value.end_lineno:
                docstrings += primeiro.value.end_lineno - primeiro.value.lineno + 1
    return comentarios, docstrings


def censo_do_volume(raiz: Path) -> Censo:
    base = raiz / PACOTE
    arquivos = sorted(base.rglob("*.py")) if base.is_dir() else []
    por_item: dict[str, int] = {}
    comentarios = docstrings = 0
    for p in arquivos:
        try:
            c, d = volume_do_texto(p.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            continue
        comentarios, docstrings = comentarios + c, docstrings + d
        if c + d >= PISO_DO_ITEM:
            por_item[p.relative_to(base).as_posix()] = c + d
    return Censo(numero=comentarios + docstrings, universo=len(arquivos), por_item=por_item,
                 nota=f"{comentarios} linhas de comentário e {docstrings} de docstring, em {PACOTE}")


MEDIDAS = (Medida(NOME, f"linhas de comentário e de docstring em {PACOTE}", censo_do_volume, "linhas"),)


def catraca_do_volume(a: argparse.Namespace, raiz: Path) -> int:
    """O volume só desce. Subir passa com ``Origem: <id>`` na faixa, como a catraca da origem."""
    catraca = Catraca(raiz / CADERNO, MEDIDAS, raiz)
    titulo = "A catraca do texto enxuto"
    if a.forcar_piso or a.aceitar is not None:
        return executar(catraca, a, titulo)
    veredito = catraca.comparar()[0]
    subiu = veredito.estado == "VERMELHO" and veredito.numero is not None and veredito.piso.numero is not None
    if not subiu:
        if a.registrar_subida:
            print(f"  nada a registrar (hoje={veredito.numero} piso={veredito.piso.numero})")
            return 0
        rc = executar(catraca, a, titulo)
        if rc == 0 and veredito.numero is not None and veredito.piso.numero is not None \
                and veredito.numero < veredito.piso.numero:
            print(f"  o volume desceu ({veredito.piso.numero} -> {veredito.numero}): "
                  f"grave o piso novo com `{Path(sys.argv[0]).name} --catraca --aceitar {NOME}`")
        return rc
    assert veredito.numero is not None and veredito.piso.numero is not None
    origem = regua("check_a_origem.py")
    pagas = sorted({o for o in origem.origens_da_faixa(raiz, a.base, a.origem) if o in origem.ids_validos(raiz)})
    delta = f"+{veredito.numero - veredito.piso.numero} linhas ({veredito.piso.numero} -> {veredito.numero})"
    if not pagas:
        print(f"{NOME}: {delta} sem `Origem: <id>` na faixa. O id é o de uma linha de "
              f"{origem.MAPA} ou de {origem.DECISOES}.")
        for linha in veredito.entrou[:TETO_DA_SAIDA]:
            print(f"      {linha}")
        return 1
    if a.registrar_subida:
        topo = _git(raiz, "rev-parse", "--short=12", "HEAD").stdout.strip() or "sem git"
        razao = f"{NOME}: {delta}, pagas por Origem: {', '.join(pagas)}; registrado no fecho, topo {topo}"
        catraca.forcar_piso(NOME, razao)
        print(f"  registrada: {razao}")
        return 0
    print(f"{NOME}: {delta}, pagas por Origem: {', '.join(pagas)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = montar_argumentos((__doc__ or "").split("\n", 1)[0])
    p.add_argument("arquivos", nargs="*", help="os arquivos a examinar")
    p.add_argument("--conferir", action="store_true", help="só aponta (é o padrão)")
    p.add_argument("--aplicar", action="store_true", help="corrige o mecânico e aponta o resto")
    p.add_argument("--restagear", action="store_true",
                   help="com --aplicar: o que estava no índice volta a ele; o que não estava reprova")
    p.add_argument("--tudo", action="store_true", help="todos os arquivos versionados no escopo")
    p.add_argument("--mudados", action="store_true", help="os arquivos mudados desde o pé comum com o `dev`")
    p.add_argument("--catraca", action="store_true", help="o volume de comentário e docstring em src/")
    p.add_argument("--registrar-subida", action="store_true",
                   help="o fecho: sobe o piso do volume quando a faixa o paga (grava a razão no caderno)")
    p.add_argument("--verbosos", type=int, default=0, metavar="N",
                   help="imprime os N arquivos de src/ com mais linhas de comentário e docstring")
    p.add_argument("--base", default=None, help="a faixa dos commits da catraca (base..HEAD)")
    p.add_argument("--origem", default=None, help="uma Origem ainda sem commit")
    a = p.parse_args(argv)
    raiz = Path(a.raiz).resolve() if a.raiz else RAIZ
    try:
        if a.verbosos:
            for nome, linhas in sorted(censo_do_volume(raiz).por_item.items(), key=lambda i: (-i[1], i[0]))[: a.verbosos]:
                print(f"{PACOTE}{nome}\t{linhas}")
            return 0
        if a.catraca or a.registrar_subida:
            return catraca_do_volume(a, raiz)
        if a.conferir and a.aplicar:
            print("RECUSADO: --conferir e --aplicar se excluem", file=sys.stderr)
            return 2
        if a.tudo:
            arquivos = versionados(raiz)
        elif a.mudados:
            arquivos = mudados(raiz)
        else:
            arquivos = relativos(raiz, a.arquivos)
        return rodar(raiz, arquivos, a.aplicar, a.restagear)
    except ReguaAusente as erro:
        print(f"o-texto-enxuto: {erro}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

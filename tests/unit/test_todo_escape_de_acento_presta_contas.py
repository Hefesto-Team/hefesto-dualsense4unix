"""O escape do portão de acentuação tem de prestar contas — todo escape NOVO.

Fora do código (Markdown, CSV, YAML), a razão vai na mesma anotação da marca. No código
(``.py`` e ``.sh``), a D-2610-O-CODIGO-NAO-TEM-COMENTARIO não deixa a razão ficar, e a marca
nua só vale onde o validador a pede.
"""
from __future__ import annotations

import functools
import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType

RAIZ = Path(__file__).resolve().parents[2]
VALIDADOR = RAIZ / "scripts" / "validar-acentuacao.py"
PORTAO = RAIZ / "scripts" / "check_codigo_sem_comentario.py"
REMOVEDOR = RAIZ / "scripts" / "tirar-os-comentarios.py"

ESTE_ARQUIVO = "tests/unit/test_todo_escape_de_acento_presta_contas.py"

PISO_DE_ESCAPES = 140

SEM_RAZAO_PINADOS: dict[str, int] = {
    ".github/workflows/ci.yml": 2,
}

_MARCA = re.compile(r"\(?noqa-acento\)?|\(?noqa:\s*acentuacao\)?")

_ABRE_ANOTACAO = ("<!--", "/*", "#", "//")

_SO_DELIMITADOR = ("<!--", "-->", "/*", "*/", "#", "//")


@functools.cache
def _carrega(caminho: Path, nome: str) -> ModuleType:
    """Os scripts têm hífen no nome: `import` não os alcança."""
    spec = importlib.util.spec_from_file_location(nome, caminho)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[nome] = mod
    spec.loader.exec_module(mod)
    return mod


def _carrega_validador() -> ModuleType:
    return _carrega(VALIDADOR, "_validador_acento")


def _tipo_de_codigo(rel: str, primeira: str) -> str | None:
    """``py`` ou ``sh`` quando o portão sem comentário cobre o arquivo; senão ``None``."""
    portao = _carrega(PORTAO, "_portao_sem_comentario")
    if rel.startswith(portao.FORA):
        return None
    tipo = portao.tipo_do_arquivo(rel, primeira)
    return tipo if tipo in ("py", "sh") else None


def tem_razao(linha: str) -> bool:
    """True se a marca vem acompanhada de razão NA MESMA ANOTAÇÃO."""
    m = _MARCA.search(linha)
    if m is None:
        return False
    inicio = 0
    for delim in _ABRE_ANOTACAO:
        pos = linha.rfind(delim, 0, m.start() + 1)
        inicio = max(inicio, pos)
    trecho = linha[inicio : m.start()] + " " + linha[m.end() :]
    for delim in _SO_DELIMITADOR:
        trecho = trecho.replace(delim, " ")
    return bool(re.findall(r"[0-9A-Za-zÀ-ÿ]{2,}", trecho))


def escapes() -> tuple[list[tuple[str, int, str]], list[tuple[str, int, str]]]:
    """Os escapes de fora do código, separados em (com razão, sem razão)."""
    com, sem, _codigo = _censo()
    return com, sem


def escapes_no_codigo() -> dict[str, str]:
    """Os arquivos de código com escape, e o tipo de cada um."""
    return _censo()[2]


def _censo() -> tuple[list[tuple[str, int, str]], list[tuple[str, int, str]], dict[str, str]]:
    val = _carrega_validador()
    com: list[tuple[str, int, str]] = []
    sem: list[tuple[str, int, str]] = []
    codigo: dict[str, str] = {}
    for arq in val.listar_arquivos_git(RAIZ):
        rel = str(arq.resolve().relative_to(RAIZ))
        if val.is_whitelisted(rel) or rel == ESTE_ARQUIVO:
            continue
        try:
            texto = arq.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if not _MARCA.search(texto):
            continue
        linhas = texto.splitlines()
        tipo = _tipo_de_codigo(rel, linhas[0] if linhas else "")
        if tipo is not None:
            codigo[rel] = tipo
            continue
        for n, linha in enumerate(linhas, 1):
            if _MARCA.search(linha):
                alvo = com if tem_razao(linha) else sem
                alvo.append((rel, n, linha.strip()[:120]))
    return com, sem, codigo


def _por_arquivo(achados: list[tuple[str, int, str]]) -> dict[str, int]:
    contas: dict[str, int] = {}
    for rel, _n, _t in achados:
        contas[rel] = contas.get(rel, 0) + 1
    return contas


def test_o_varredor_de_escapes_nao_ficou_cego() -> None:
    """Um leitor que devolve zero faz os testes abaixo passarem por vacuidade."""
    com, sem = escapes()
    total = len(com) + len(sem) + sum(
        len(_MARCA.findall((RAIZ / rel).read_text(encoding="utf-8")))
        for rel in escapes_no_codigo())
    assert total >= PISO_DE_ESCAPES, (
        f"achei {total} escapes de acentuação no repositório, piso "
        f"{PISO_DE_ESCAPES}.\n"
        "Se eles sumiram de propósito, baixe o piso no mesmo commit. Se não "
        "sumiram, o varredor deste arquivo quebrou — e um varredor que lê zero "
        "aprova qualquer coisa."
    )


def test_nenhum_escape_novo_sem_razao() -> None:
    _com, sem = escapes()
    atual = _por_arquivo(sem)

    novos: list[str] = []
    for rel, quantos in sorted(atual.items()):
        pinado = SEM_RAZAO_PINADOS.get(rel, 0)
        if quantos > pinado:
            linhas = [f"{r}:{n}" for r, n, _t in sem if r == rel]
            novos.append(
                f"  {rel}: {quantos} mudo(s), pinado {pinado} — {linhas}"
            )

    assert not novos, (
        "escape de acentuação SEM RAZÃO, e ele é novo:\n"
        + "\n".join(novos)
        + "\n\nEscreva por que a palavra está certa sem acento, na MESMA linha "
        "da marca — antes ou depois dela:\n"
        '    manager.delete("acao")  # slug literal ASCII (noqa-acento)\n'
        '    <div data-v="acao">     # (noqa-acento): endereço\n'
        "\nA marca vai NA linha da palavra: o escape é por linha, e escrito na "
        "linha de baixo ele não alcança nada.\n"
        "Se o escape não tem razão que se escreva, ele não é escape: é um erro "
        "de acentuação, e o conserto é o acento."
    )


def test_a_lista_de_escapes_mudos_so_encolhe() -> None:
    """`atual <= pinado`, no total. Encolher passa; crescer reprova."""
    _com, sem = escapes()
    teto = sum(SEM_RAZAO_PINADOS.values())
    assert len(sem) <= teto, (
        f"{len(sem)} escapes mudos contra um teto de {teto}. A lista "
        "`SEM_RAZAO_PINADOS` é dívida do dia em que este arquivo nasceu, e ela "
        "só encolhe."
    )


def test_a_lista_pinada_esta_em_dia_com_o_que_existe() -> None:
    """O outro lado da catraca: número pinado ACIMA do real também reprova."""
    _com, sem = escapes()
    atual = _por_arquivo(sem)
    sobrando = sorted(
        (rel, pinado, atual.get(rel, 0))
        for rel, pinado in SEM_RAZAO_PINADOS.items()
        if pinado > atual.get(rel, 0)
    )
    assert not sobrando, (
        "`SEM_RAZAO_PINADOS` promete mais escape mudo do que existe:\n"
        + "\n".join(
            f"  {rel}: pinado {pinado}, real {real}"
            + ("  (apague a linha)" if real == 0 else f"  (baixe para {real})")
            for rel, pinado, real in sobrando
        )
        + "\n\nA lista só encolhe, e encolher se ESCREVE: um número inflado é "
        "uma licença em branco para o próximo escape mudo."
    )


def test_tem_razao_reconhece_as_duas_formas_da_casa() -> None:
    marca = "noqa" + "-acento"
    com_razao = [
        f'manager.delete("x")  # slug literal ASCII ({marca})',
        f"<div>  # ({marca}): endereço",
        f"# comentário  # ({marca}: verbo medir, imperfeito)",
        f"<!-- {marca}: pretérito imperfeito de MEDIR -->",
        f"    /* {marca}: palavra-chave do CSS */",
        f'casa="x"  # ({marca}) variável',
    ]
    sem_razao = [
        f"print('x')  # {marca}",
        f"algo()  # ({marca})",
        f"> uma citação literal <!-- {marca} -->",
        f"@media (max-width: 640px) {{   /* {marca} */",
        "assert x  # noqa: acentuacao",
    ]
    for linha in com_razao:
        assert tem_razao(linha), f"devia ter razão: {linha!r}"
    for linha in sem_razao:
        assert not tem_razao(linha), f"NÃO devia ter razão: {linha!r}"


def test_a_razao_da_anotacao_vizinha_nao_conta() -> None:
    """Prosa de OUTRO comentário na mesma linha não é razão do escape."""
    marca = "noqa" + "-acento"
    exemplo = "# o glade não os referencia"  # (noqa-acento)
    assert not tem_razao(f"{exemplo}  # ({marca})")
    assert tem_razao(f"{exemplo}  # ({marca}: verbo, não substantivo)")


def _escapes_a_mais(texto: str, tipo: str, rel: str) -> int:
    removedor = _carrega(REMOVEDOR, "_removedor_de_comentario")
    return removedor._escapes_a_mais(texto, tipo, rel)[1]


def test_o_escape_no_codigo_e_so_o_que_o_validador_pede() -> None:
    """No código a marca não tem razão: só fica onde, sem ela, o validador reprova a linha."""
    codigo = escapes_no_codigo()
    assert codigo, "nenhum arquivo de código com escape: o censo ficou cego"
    sobrando = [rel for rel, tipo in sorted(codigo.items())
                if _escapes_a_mais((RAIZ / rel).read_text(encoding="utf-8"), tipo, rel)]
    assert not sobrando, (
        "escape de acentuação que o validador não pede, no código:\n  " + "\n  ".join(sobrando)
        + "\n\nRode `scripts/tirar-os-comentarios.py --aplicar` no arquivo: ele tira a marca "
        "que não escapa nada."
    )


def test_a_mordida_o_escape_que_nao_escapa_nada_e_achado() -> None:
    marca = "# (noqa" + "-acento)"
    assert _escapes_a_mais(f"x = 1  {marca}\n", "py", "src/x.py") == 1
    assert _escapes_a_mais(f'x = "{"na" + "o"}"  {marca}\n', "py", "src/x.py") == 0

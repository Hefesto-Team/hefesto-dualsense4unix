"""A-VALIDACAO-DO-TEMA-CUSTA-LINEAR-01 — as réguas.

Medido em 07/11/2026, no teto de 16 KB: a regex do comentário custava 243 ms, e o mesmo quadrático
morava em mais três (a vírgula de fora dos parênteses, 195 ms; a posição da parada, 2073 ms; o
``!important``, 262 ms). O tempo se mede contra ``tema.validar``, na régua da própria função: oito
vezes a entrada pede até 24 vezes o tempo, e o quadrático dá mais de 60. O comportamento se mede
contra as regex velhas, guardadas aqui, sobre texto sorteado com semente fixa; as duas diferenças
que um sorteio mais largo achou ficam escritas em ``test_o_que_mudou_de_proposito``.

MORDIDAS (07/11/2026, executadas sobre a cura e devolvidas): cada regex velha de volta reprova o
seu ``test_o_tempo_cresce_junto_com_a_entrada``; ``abre + 1`` no fim do comentário, ``rstrip``
tirado do ``!important``, o ``seguinte`` que não olha o ``(`` e a janela de quatro caracteres na
parada reprovam, cada um, o seu ``test_diz_o_mesmo_que_a_regex_velha``.
"""
from __future__ import annotations

import random
import re
import time
from collections.abc import Callable

import pytest

from hefesto_dualsense4unix.mods import tema

_SEMENTE = 20261107
_SORTEIOS = 4000
_PEQUENO = 2 * 1024
_GRANDE = tema.TAMANHO_MAXIMO
_TETO_DA_RAZAO = 24.0
_MEDIDAS = 9

_COMENTARIO_VELHO = re.compile(r"/\*.*?\*/", re.S)
_IMPORTANT_VELHO = re.compile(r"\s*!\s*important\s*$", re.I)
_VIRGULA_VELHA = re.compile(r",(?![^()]*\))")
_PARADA_VELHA = re.compile(r"(.+?)(?:\s+\d{1,3}%)?")

_FAMILIAS: dict[str, Callable[[int], str]] = {
    "comentario": lambda n: "/* " * (n // 3),
    "virgulas": lambda n: ":root{--logo-fundo:radial-gradient(" + "a," * (n // 2 - 30) + ")}",
    "parada": lambda n: (":root{--logo-fundo:radial-gradient(circle, #fff" + " " * (n - 80)
                         + "x, #000 1%)}"),
    "important": lambda n: ":root{--fg:rgb(" + " " * (n - 30) + ")}",
}


def _sorteado(gerador: random.Random, pedacos: tuple[str, ...]) -> str:
    return "".join(gerador.choice(pedacos) for _ in range(gerador.randint(0, 12)))


def _tempo(texto: str) -> float:
    casa, apelidos = {"--app-bg": "#000000"}, {"--x": "--y"}
    melhor = float("inf")
    for _ in range(_MEDIDAS):
        comeco = time.perf_counter()
        with pytest.raises(tema.TemaRecusadoError):
            tema.validar(texto, casa=casa, apelidos=apelidos)
        melhor = min(melhor, time.perf_counter() - comeco)
    return melhor


@pytest.mark.parametrize("familia", sorted(_FAMILIAS))
def test_o_tempo_cresce_junto_com_a_entrada(familia: str) -> None:
    pequena, grande = _FAMILIAS[familia](_PEQUENO), _FAMILIAS[familia](_GRANDE)
    assert len(grande.encode("utf-8")) <= tema.TAMANHO_MAXIMO
    assert len(grande) >= 7 * len(pequena)
    razao = _tempo(grande) / _tempo(pequena)
    assert razao < _TETO_DA_RAZAO, f"oito vezes a entrada custou {razao:.0f} vezes o tempo"


def _fundo_velho(valor: str) -> bool:
    texto = valor.strip().lower()
    if texto == "none" or tema.cor(texto) is not None:
        return True
    m = tema._GRADIENTE.fullmatch(texto)
    if m is None:
        return False
    partes = [p.strip() for p in _VIRGULA_VELHA.split(m.group(1))]
    primeira = _PARADA_VELHA.fullmatch(partes[0])
    if primeira is None or tema.cor(primeira.group(1)) is None:
        if not partes[0] or not tema._FORMA.fullmatch(partes[0]):
            return False
        partes = partes[1:]
    paradas = [_PARADA_VELHA.fullmatch(p) for p in partes]
    return len(paradas) >= 2 and all(p is not None and tema.cor(p.group(1)) is not None
                                     for p in paradas)


def test_diz_o_mesmo_que_a_regex_velha_no_comentario() -> None:
    gerador = random.Random(_SEMENTE)
    pedacos = ("/*", "*/", "/", "*", " ", "\n", "a", "/*/", "**")
    for _ in range(_SORTEIOS):
        texto = _sorteado(gerador, pedacos)
        assert tema._sem_comentario(texto) == _COMENTARIO_VELHO.sub("", texto), repr(texto)


def test_diz_o_mesmo_que_a_regex_velha_no_important() -> None:
    gerador = random.Random(_SEMENTE)
    pedacos = ("!", " ", "\n", "\t", "important", "IMPORTANT", "Important", "#fff", "x")
    for _ in range(_SORTEIOS):
        texto = _sorteado(gerador, pedacos).strip()
        assert tema._sem_important(texto) == _IMPORTANT_VELHO.sub("", texto), repr(texto)


def test_diz_o_mesmo_que_a_regex_velha_nas_virgulas() -> None:
    gerador = random.Random(_SEMENTE)
    pedacos = (",", "(", ")", " ", "a", "rgb(1,2,3)")
    for _ in range(_SORTEIOS):
        texto = _sorteado(gerador, pedacos)
        assert tema._virgulas_de_fora(texto) == _VIRGULA_VELHA.split(texto), repr(texto)


def _gradiente_sorteado(gerador: random.Random) -> str:
    paradas = [
        gerador.choice(("#fff", "#000000", "rgb(1,2,3)", "rgba(1,2,3,0.5)", "x", ""))
        + gerador.choice(("", " ", "  ", "\n", "\t "))
        + gerador.choice(("", "1%", "50%", "100%", "1000%", "%"))
        for _ in range(gerador.randint(1, 4))
    ]
    forma = gerador.choice(("", "circle, ", "ellipse at 50% 50%, ", "at 1% 2%, ", "x, "))
    return f"radial-gradient({forma}{gerador.choice((', ', ',')).join(paradas)})"


def test_diz_o_mesmo_que_a_regex_velha_no_fundo_da_logo() -> None:
    gerador = random.Random(_SEMENTE)
    pedacos = ("#fff", "rgb(1,2,3)", ",", " ", "\n", "1%", "100%", "circle", "x", "none")
    respostas = set()
    for _ in range(_SORTEIOS):
        valor = _gradiente_sorteado(gerador)
        assert tema.fundo_da_logo(valor) is _fundo_velho(valor), repr(valor)
        respostas.add(_fundo_velho(valor))
        cru = _sorteado(gerador, pedacos)
        assert tema.fundo_da_logo(cru) is _fundo_velho(cru), repr(cru)
    assert respostas == {True, False}, "o sorteio não passou pelos dois lados"


@pytest.mark.parametrize(("folha", "esperada"), [
    ("/* a */:root{--fg:#fff}/* b */", ":root{--fg:#fff}"),
    (":root{/* /* */--fg:#fff}", ":root{--fg:#fff}"),
    ("/*/:root{--fg:#fff}*/", ""),
    ("/* sem fim :root{--fg:#fff}", "/* sem fim :root{--fg:#fff}"),
])
def test_o_comentario_de_sempre(folha: str, esperada: str) -> None:
    assert tema._sem_comentario(folha) == esperada


def test_o_que_mudou_de_proposito() -> None:
    em_duas_linhas = "radial-gradient(rgb(1,\n2,3), #000000)"
    assert tema.fundo_da_logo("rgb(1,\n2,3)"), "a cor sozinha sempre valeu assim"
    assert tema.fundo_da_logo(em_duas_linhas) and not _fundo_velho(em_duas_linhas)
    sem_ponto = "#fff !\u0131mportant"
    assert tema._sem_important(sem_ponto) == sem_ponto
    assert _IMPORTANT_VELHO.sub("", sem_ponto) == "#fff"


def test_o_tema_com_tudo_ainda_passa() -> None:
    folha = (":root{\n /* o fundo */ --app-bg:#101018 ! IMPORTANT ;\n"
             "--logo-fundo:radial-gradient(circle at 50% 50%, rgba(255,255,255,0.2) 0%,"
             " #000000  100%) !important}")
    aceito = tema.validar(folha)
    assert aceito.tokens["--app-bg"] == "#101018"
    assert aceito.tokens["--logo-fundo"].startswith("radial-gradient(")

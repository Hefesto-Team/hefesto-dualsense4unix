"""Dois arrastes seguidos na Navegação gravam os dois valores.

DOIS-ARRASTES-SEGUIDOS-NA-NAVEGACAO-GRAVAM-OS-DOIS-VALORES-01: o gesto que muda um campo do
mouse parte do que está GRAVADO (o computador ou o perfil, relidos no gesto), não do retrato do
último tique. Os gestos aqui rodam sobre o MESMO `ctx`, sem tique entre eles: é o ritmo de quem
arrasta uma barra e logo a outra com o computador ocupado.
"""
from __future__ import annotations

import pathlib
import sys
from collections.abc import Callable
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
for _p in (str(RAIZ / "src"), str(RAIZ / "src" / "hefesto_dualsense4unix" / "interface")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

UM = "aa:bb:cc:00:00:01"
OUTRO = "aa:bb:cc:00:00:02"

O_TIQUE_VELHO = {"enabled": True, "speed": 6, "scroll_speed": 1}


@pytest.fixture
def a06() -> Any:
    from pacotes import a06_navegacao

    return a06_navegacao


@pytest.fixture
def pac() -> Any:
    import pacotes

    return pacotes


class PonteDeMentira:
    def __init__(self) -> None:
        self.chamadas: list[tuple[str, dict[str, Any]]] = []

    def resultado(self, metodo: str, **params: Any) -> dict[str, Any]:
        self.chamadas.append((metodo, params))
        return {"status": "ok"}

    def chamar(self, metodo: str, **params: Any) -> bool:
        self.chamadas.append((metodo, params))
        return True


def _ctx(pac: Any, *, perfil: str, conectados: int) -> Any:
    st = {"active_profile": perfil, "mouse_emulation": dict(O_TIQUE_VELHO),
          "keyboard_emulation": {"enabled": True}}
    corpos = [{"uniq": u, "connected": True, "is_primary": i == 0}
              for i, u in enumerate((UM, OUTRO)[:conectados])]
    return pac.Contexto(state=st, mesa=[], conectados=corpos, estados={})


def _semear_o_jogo_sem_mouse() -> None:
    from hefesto_dualsense4unix.profiles.loader import save_profile
    from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile

    save_profile(Profile(name="regua", match=MatchAny(), teclado_emulado=True),
                 origem="regua")


def _semear_o_computador_carregado() -> None:
    from hefesto_dualsense4unix.utils import maquina as m

    assert m.gravar_o_computador({"global": {"mouse": {
        "speed": O_TIQUE_VELHO["speed"], "scroll_speed": O_TIQUE_VELHO["scroll_speed"]}}})


def _gravado(onde: str) -> dict[str, Any]:
    if onde == "jogo":
        from hefesto_dualsense4unix.profiles.loader import load_profile

        mouse = load_profile("regua").mouse
    else:
        from hefesto_dualsense4unix.profiles.o_padrao_do_computador import o_computador

        mouse = o_computador().global_.mouse
    assert mouse is not None, f"nada foi gravado no {onde}"
    return {"speed": mouse.speed, "scroll_speed": mouse.scroll_speed,
            "point_and_click": mouse.point_and_click}


def _semear_os_dois() -> None:
    _semear_o_jogo_sem_mouse()
    _semear_o_computador_carregado()


_CENARIOS: dict[str, tuple[str, str, Callable[[], None]]] = {
    "computador-vazio": ("", "computador", lambda: None),
    "computador-carregado": ("", "computador", _semear_o_computador_carregado),
    "jogo-sem-mouse": ("regua", "jogo", _semear_o_jogo_sem_mouse),
    "jogo-sem-mouse-e-computador-carregado": ("regua", "jogo", _semear_os_dois),
}


def _cursor(a06: Any, ctx: Any, p: PonteDeMentira) -> None:
    assert a06.vel_cursor(ctx, {"valor": "9"}, p) is None


def _rolagem(a06: Any, ctx: Any, p: PonteDeMentira) -> None:
    assert a06.vel_rolagem(ctx, {"valor": "4"}, p) is None


def _point_and_click(a06: Any, ctx: Any, p: PonteDeMentira) -> None:
    assert a06.point_and_click_perfil(ctx, {"valor": "perfil:Corrida"}, p) is None


_GESTOS: dict[str, tuple[Callable[..., None], str, Any]] = {
    "cursor": (_cursor, "speed", 9),
    "rolagem": (_rolagem, "scroll_speed", 4),
    "point_and_click": (_point_and_click, "point_and_click", "perfil:Corrida"),
}

_ORDENS = [
    ("cursor", "rolagem"),
    ("rolagem", "cursor"),
    ("cursor", "point_and_click"),
    ("point_and_click", "cursor"),
    ("rolagem", "point_and_click"),
    ("point_and_click", "rolagem"),
    ("cursor", "point_and_click", "rolagem"),
]


@pytest.mark.parametrize("conectados", [1, 2])
@pytest.mark.parametrize("cenario", sorted(_CENARIOS))
@pytest.mark.parametrize("ordem", _ORDENS, ids=["-".join(o) for o in _ORDENS])
def test_gestos_seguidos_sem_tique_gravam_todos_os_valores(
        pac: Any, a06: Any, cenario: str, ordem: tuple[str, ...], conectados: int) -> None:
    perfil, onde, semear = _CENARIOS[cenario]
    semear()
    ctx = _ctx(pac, perfil=perfil, conectados=conectados)
    ponte = PonteDeMentira()
    for nome in ordem:
        _GESTOS[nome][0](a06, ctx, ponte)
    gravado = _gravado(onde)
    esperado = {_GESTOS[n][1]: _GESTOS[n][2] for n in ordem}
    assert {c: gravado[c] for c in esperado} == esperado, (
        f"{' → '.join(ordem)} no {onde} ({cenario}): um gesto desfez o anterior, gravado "
        f"{gravado}")


def test_o_campo_que_ninguem_mexeu_fica_como_estava_no_computador(
        pac: Any, a06: Any) -> None:
    from hefesto_dualsense4unix.utils import maquina as m

    assert m.gravar_o_computador({"global": {"mouse": {"speed": 2, "scroll_speed": 3}}})
    ctx = _ctx(pac, perfil="", conectados=1)
    _cursor(a06, ctx, PonteDeMentira())
    assert _gravado("computador")["scroll_speed"] == 3, (
        "o gesto do cursor regravou a rolagem com o número do tique, e não com o gravado")


def _semear_o_point_and_click_no_computador() -> None:
    from hefesto_dualsense4unix.utils import maquina as m

    assert m.gravar_o_computador({"global": {"mouse": {
        "speed": 2, "scroll_speed": 3, "point_and_click": "perfil:Corrida"}}})


@pytest.mark.parametrize("gesto", ["cursor", "rolagem"])
def test_a_velocidade_no_computador_nao_mexe_no_point_and_click(
        pac: Any, a06: Any, gesto: str) -> None:
    _semear_o_point_and_click_no_computador()
    _GESTOS[gesto][0](a06, _ctx(pac, perfil="", conectados=1), PonteDeMentira())
    assert _gravado("computador")["point_and_click"] == "perfil:Corrida"


@pytest.mark.parametrize("gesto", ["cursor", "rolagem"])
def test_a_velocidade_no_jogo_nao_copia_o_point_and_click_do_computador(
        pac: Any, a06: Any, gesto: str) -> None:
    from hefesto_dualsense4unix.profiles.loader import load_profile

    _semear_o_jogo_sem_mouse()
    _semear_o_point_and_click_no_computador()
    _GESTOS[gesto][0](a06, _ctx(pac, perfil="regua", conectados=1), PonteDeMentira())
    mouse = load_profile("regua").mouse
    assert mouse is not None and _GESTOS[gesto][1] in mouse.model_fields_set
    assert "point_and_click" not in mouse.model_fields_set, (
        "o gesto da velocidade congelou no jogo o Point and click do computador: "
        f"{mouse.model_dump(exclude_unset=True)}")

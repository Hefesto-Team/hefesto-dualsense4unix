"""A-JOGAR-ESCOLHE-O-MODO-UNICO-NOS-PACOTES-01 — a Jogar atende todo gesto do desenho dela.

O desenho da 01 (`mockup/01-jogar.html`) traz o chip «Nintendo Pro» e a seção Controles da 02.
D-2710-O-MODO-E-UM-SO-PARA-TODOS-OS-CONTROLES: o Nintendo Pro é o modo único sem caminho, pelo
escritor único do modo, e acende pelo par do daemon para todos os controles. A seção atende nas
páginas de `a02_controles.PAGINAS_DA_SECAO`, sem cópia, e o pacote da Jogar a pinta pelo pacote
da 02 quando a página publicada a mostra.

MORDIDAS: tire «01-jogar.html» de `PAGINAS_DA_SECAO` (os nove gestos da seção ficam órfãos e
`test_todo_gesto_do_desenho_tem_quem_o_atenda` reprova); tire o chip «nintendo» de
`painel.CHIPS_DA_ESCADA` (o clique recusa e a luz não acende).
"""
from __future__ import annotations

import html.parser
import pathlib
import shutil
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions.jogar import painel
from hefesto_dualsense4unix.interface import onde, pacotes
from hefesto_dualsense4unix.interface.pacotes import a01_jogar, a02_controles, camada

RAIZ = pathlib.Path(__file__).resolve().parents[2]
DESENHO = RAIZ / "mockup" / "01-jogar.html"
PAGINA = a01_jogar.PAGINA

FALSO = {"uniq": "aa:bb:cc:00:00:01", "transport": "usb", "battery_pct": 64}
MESA = [{"uniq": FALSO["uniq"], "pref": "p1", "jogador": 1, "nome": "DualSense",
         "cor": "", "transporte": "usb"}]


class _Atributos(html.parser.HTMLParser):
    """Os `data-gesto` e `data-campo` dos elementos, fora de `<script>` e `<style>`."""

    def __init__(self) -> None:
        super().__init__()
        self.gestos: set[str] = set()
        self.campos: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for nome, valor in attrs:
            if valor and nome == "data-gesto":
                self.gestos.add(valor)
            elif valor and nome == "data-campo":
                self.campos.add(valor)


def _do_desenho() -> _Atributos:
    leitor = _Atributos()
    leitor.feed(DESENHO.read_text(encoding="utf-8"))
    return leitor


def _da_moldura() -> set[str]:
    """Os gestos que a moldura atende (o menu, a trava e a fita), lidos dos donos."""
    import monta

    return set(camada.GESTOS_DO_MENU) | set(camada.GESTOS_DA_MOLDURA) | {monta.GESTO_DA_FITA}


def test_todo_gesto_do_desenho_tem_quem_o_atenda() -> None:
    gestos = _do_desenho().gestos
    assert {"modo-nintendo", "mudo", "volume", "modo-dos-controles"} <= gestos, "premissa"

    orfaos = sorted(g for g in gestos - _da_moldura()
                    if pacotes.gesto_da_pagina(PAGINA, g) is None)

    assert not orfaos, f"o desenho da Jogar tem botões sem dono: {orfaos}"


def test_a_secao_atende_pelo_mesmo_gesto_nas_duas_paginas() -> None:
    for (pagina, nome), fn in pacotes.GESTOS.items():
        if pagina != a02_controles.PAGINA:
            continue
        na_jogar = pacotes.GESTOS.get((PAGINA, nome))
        assert na_jogar is not None, nome
        assert getattr(na_jogar, "__wrapped__", None) is getattr(fn, "__wrapped__", None), nome
        assert pacotes.GESTOS_QUE_MEXEM.get((PAGINA, nome)) == pacotes.GESTOS_QUE_MEXEM.get(
            (pagina, nome)), nome


class _Ipc:
    def __init__(self) -> None:
        self.chamadas: list[tuple[str, dict[str, Any]]] = []

    def chamar(self, metodo: str, **params: Any) -> bool:
        self.chamadas.append((metodo, params))
        return True


@pytest.fixture
def sem_jogo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(a01_jogar, "_qual_jogo", lambda _state: (None, None))
    monkeypatch.setattr(a01_jogar, "_ESCOLHA", {})
    monkeypatch.setattr(a01_jogar, "_ROTULO", {})


@pytest.mark.usefixtures("sem_jogo")
@pytest.mark.parametrize(("chip", "pedido"), [
    ("nintendo", {"flavor": "nintendo"}),
    ("dualsense", {"caminho": "dualsense"}),
    ("xbox", {"caminho": "xbox"}),
])
def test_o_chip_pede_o_modo_unico_ao_escritor(chip: str, pedido: dict[str, str]) -> None:
    gesto = pacotes.gesto_da_pagina(PAGINA, f"modo-{chip}")
    assert gesto is not None
    ipc = _Ipc()
    ctx = pacotes.Contexto(state={"gamepad_emulation": {"enabled": True}}, mesa=[],
                           conectados=[], estados={})

    gesto(ctx, {"texto": a01_jogar._rotulo_do_chip(chip)}, ipc)

    emulacao = [p for m, p in ipc.chamadas if m == "gamepad.emulation.set"]
    assert emulacao == [{"enabled": True, "origin": "manual", **pedido}], ipc.chamadas
    assert a01_jogar._faixa_do_pendente({"gamepad_emulation": {"enabled": True}})[1] == (
        a01_jogar._rotulo_do_chip(chip))


@pytest.mark.parametrize(("caminho", "flavor", "aceso"), [
    ("dualsense", "dualsense", "dualsense"),
    ("xbox", "xbox", "xbox"),
    ("dualsense", "nintendo", "nintendo"),
])
def test_o_chip_acende_pelo_par_do_daemon(caminho: str, flavor: str, aceso: str) -> None:
    state = {"gamepad_emulation": {"enabled": True, "caminho": caminho, "flavor": flavor}}

    assert a01_jogar._estado_da_tela(state)["modo-aceso"] == aceso
    assert painel._rotulo_do_gamepad(state) == a01_jogar._rotulo_do_chip(aceso)


def test_o_pendente_do_nintendo_some_quando_o_daemon_chega() -> None:
    a01_jogar._ESCOLHA.clear()
    a01_jogar._lembrar_do_chip("nintendo", {"texto": "Nintendo Pro"})
    em_dualsense = {"gamepad_emulation": {"enabled": True, "caminho": "dualsense",
                                          "flavor": "dualsense"}}
    assert a01_jogar._pendencia(em_dualsense) == {"mascara": "nintendo"}

    a01_jogar._lembrar_do_chip("dualsense", {"texto": "Sony DualSense"})
    em_nintendo = {"gamepad_emulation": {"enabled": True, "caminho": "dualsense",
                                         "flavor": "nintendo"}}
    assert a01_jogar._pendencia(em_nintendo) == {"caminho": "dualsense"}, (
        "o caminho de reserva do Nintendo Pro apagou o pedido do DualSense")
    a01_jogar._ESCOLHA.clear()


@pytest.fixture
def jogar_publicada_com_a_secao(tmp_path: pathlib.Path,
                                monkeypatch: pytest.MonkeyPatch) -> None:
    """O publicado de mentira: a 01 do desenho e a 02 de hoje."""
    shutil.copy(DESENHO, tmp_path / PAGINA)
    shutil.copy(onde.pagina(a02_controles.PAGINA, publicado=True),
                tmp_path / a02_controles.PAGINA)
    monkeypatch.setattr(onde, "PUBLICADO", tmp_path)
    monkeypatch.setattr(a02_controles, "_ENDERECOS", None)
    monkeypatch.setattr(a02_controles, "_GESTOS_PUBLICADOS", {})


def _ctx() -> pacotes.Contexto:
    return pacotes.Contexto(state={"gamepad_emulation": {"enabled": True}}, mesa=MESA,
                            conectados=[FALSO], estados={})


@pytest.mark.usefixtures("jogar_publicada_com_a_secao")
def test_o_pacote_da_jogar_traz_os_campos_da_secao() -> None:
    da_secao = a02_controles.pacote(_ctx())
    card = da_secao["cards"][FALSO["uniq"]]
    assert card, "premissa: a 02 pinta o card"

    fora = pacotes.normalizar(pacotes.pacote_da_pagina(PAGINA, _ctx()) or {})

    pintado = fora["colunas"][FALSO["uniq"]]
    assert {k: pintado.get(k) for k in card} == card
    for chave, valor in da_secao["mesa"].items():
        assert fora["mesa"].get(chave) == valor, chave
    assert {"bateria", "jogador", "mic-num", "alto-num", "giro-ligado"} <= (
        _do_desenho().campos & set(card)), "a seção do desenho não lê o que a 02 pinta"


def test_a_jogar_publicada_sem_a_secao_fica_como_esta() -> None:
    if a02_controles.a_secao_esta_na_pagina(PAGINA):
        pytest.skip("a Jogar publicada já mostra a seção")
    cartao = (pacotes.pacote_da_pagina(PAGINA, _ctx()) or {})["cartoes"][FALSO["uniq"]]

    assert set(cartao) == set(a01_jogar.POR_CARTAO)
    assert cartao["jogador"].startswith("Player")

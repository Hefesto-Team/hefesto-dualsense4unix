"""A curva molda só o analógico físico, e a mira soma em cima, com o piso próprio.

Medido antes da cura, no pad virtual dos quatro, cabo e rádio: o gesto no piso, de 36 contagens,
virava 13 com a zona interna de 20 % e zero com 30 %; o de 20 °/s, de 48, virava 28 e 14. O caminho
é o do produto: `dispatch_gamepad` no P1, `CoopManager.forward_all` de P2 a P4, a curva depositada
por `ProfileManager.apply_acessibilidade`, só o nó dublado.

MORDIDAS: pôr `moldar_os_analogicos` de volta depois de `aplicar_o_movimento` no
`dispatch_gamepad` reprova o P1; no `forward_all` reprova de P2 a P4; tirá-la de um dos dois
reprova o analógico físico daquele caminho; moldar o físico dentro de `entregar_os_analogicos`
também reprova a mira; tirar a inversão ou a troca de `entregar_os_analogicos` reprova
`test_a_inversao_e_a_troca_seguem_valendo_para_a_mira`.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from evdev import ecodes

from hefesto_dualsense4unix.core import curva_do_analogico as cv
from hefesto_dualsense4unix.core import roteador_de_movimento as rot
from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.core.virtual_motion import REGISTRO, chave_de_sensor
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.integrations.uinput_gamepad import UinputGamepad
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import (
    ControllerOverrides,
    MatchAny,
    Profile,
    ProfileAnalogicosConfig,
)
from tests.unit.test_a_mira_vale_nos_quatro import (
    P1,
    P2,
    P3,
    P4,
    PARADO,
    QUATRO,
    TIQUE_S,
    _Mesa,
    _NoDoPad,
)

GESTO_LENTO = (0.0, 20.0, 0.0)
GESTO_NO_PISO = (0.0, 4.0, 0.0)
CENTRO = (128, 128, 128, 128)
NO_DIREITO = {"destino": "analogico_direito"}
PISO_EM_CONTAGENS = round(rot.PISO_PADRAO * rot.DEFLEXAO_MAXIMA)
PEQUENO = 128 + round(0.10 * 127)
FORA_DA_ZONA = 128 + round(0.60 * 127)


@pytest.fixture(autouse=True)
def _registro_limpo() -> Iterator[None]:
    REGISTRO.limpar()
    yield
    REGISTRO.limpar()


class _MesaDaCurva(_Mesa):
    """A mesa da mira com o analógico físico de cada peça e a curva pelo gerente de perfis."""

    def __init__(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        transporte: str,
        pecas: dict[str, dict[str, Any]],
        *,
        mesa: dict[str, Any] | None = None,
        curva_por_peca: dict[str, dict[str, Any]] | None = None,
        secundarios: tuple[str, ...] = (P2, P3, P4),
    ) -> None:
        self.fisico = {uniq: CENTRO for uniq in (P1, *secundarios)}
        super().__init__(monkeypatch, tmp_path, transporte, pecas, secundarios=secundarios)
        for uniq in secundarios:
            self.coop._players[uniq].reader = SimpleNamespace(
                snapshot=lambda u=uniq: self._foto(u), grab_state="held")
        ProfileManager(controller=self.daemon.controller, store=self.daemon.store)\
            .apply_acessibilidade(Profile(
                name="A curva",
                match=MatchAny(type="any"),
                analogicos=ProfileAnalogicosConfig(**mesa) if mesa is not None else None,
                controllers={
                    chave_de_sensor(uniq): ControllerOverrides(
                        analogicos=ProfileAnalogicosConfig(**campos))
                    for uniq, campos in (curva_por_peca or {}).items()
                },
            ))

    def _foto(self, uniq: str) -> Any:
        lx, ly, rx, ry = self.fisico[uniq]
        return SimpleNamespace(
            lx=lx, ly=ly, rx=rx, ry=ry, l2_raw=0, r2_raw=0, buttons_pressed=self.botoes[uniq])

    def tiques(self, quantos: int) -> None:
        lx, ly, rx, ry = self.fisico[P1]
        estado = ControllerState(
            battery_pct=100, l2_raw=0, r2_raw=0, connected=True,
            transport=self.transporte,  # type: ignore[arg-type]
            raw_lx=lx, raw_ly=ly, raw_rx=rx, raw_ry=ry,
        )
        for _ in range(quantos):
            self.relogio.agora += TIQUE_S
            gp.dispatch_gamepad(self.daemon, estado, self.botoes[P1])
            self.coop.forward_all()

    def gesto(
        self, uniq: str, giro: tuple[float, float, float] = GESTO_LENTO
    ) -> list[dict[str, int]]:
        """Tudo o que o pad virtual de `uniq` recebeu enquanto a mão fazia o gesto."""
        antes = len(self.pads[uniq].analog)
        self.nos[uniq].giro = giro
        self.tiques(8)
        self.nos[uniq].giro = PARADO
        self.tiques(2)
        return self.pads[uniq].analog[antes:]


def _todos_no_direito() -> dict[str, dict[str, Any]]:
    return {uniq: dict(NO_DIREITO) for uniq in QUATRO}


def _quadros_sem_curva(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    transporte: str,
    quem: str,
    giro: tuple[float, float, float] = GESTO_LENTO,
) -> list[dict[str, int]]:
    pasta = tmp_path / "sem-curva"
    pasta.mkdir(exist_ok=True)
    return _MesaDaCurva(monkeypatch, pasta, transporte, _todos_no_direito()).gesto(quem, giro)


@pytest.mark.parametrize("transporte", ["usb", "bt"])
@pytest.mark.parametrize("zona", [20, 30])
@pytest.mark.parametrize("giro", [GESTO_NO_PISO, GESTO_LENTO])
@pytest.mark.parametrize("quem", QUATRO)
def test_o_gesto_lento_chega_igual_com_qualquer_zona_morta(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    transporte: str,
    zona: int,
    giro: tuple[float, float, float],
    quem: str,
) -> None:
    livre = _quadros_sem_curva(monkeypatch, tmp_path, transporte, quem, giro)
    assert min(q["rx"] for q in livre) <= 128 - PISO_EM_CONTAGENS, livre
    mesa = _MesaDaCurva(
        monkeypatch, tmp_path, transporte, _todos_no_direito(), mesa={"zona_morta": zona})
    assert mesa.gesto(quem, giro) == livre, f"a zona de {zona} % comeu a mira de {quem}"


@pytest.mark.parametrize("transporte", ["usb", "bt"])
@pytest.mark.parametrize("quem", QUATRO)
@pytest.mark.parametrize(
    "curva",
    [
        {"curva": "precisa"},
        {"curva": "estavel"},
        {"curva": "digital"},
        {"sensibilidade": 50},
        {"sensibilidade": 150},
        {"zona_externa": 30},
        {"zona_morta": 50, "zona_externa": 30, "curva": "precisa", "sensibilidade": 50},
    ],
)
def test_nenhuma_forma_da_curva_toca_na_mira(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    transporte: str,
    quem: str,
    curva: dict[str, Any],
) -> None:
    livre = _quadros_sem_curva(monkeypatch, tmp_path, transporte, quem)
    mesa = _MesaDaCurva(monkeypatch, tmp_path, transporte, _todos_no_direito(), mesa=curva)
    assert mesa.gesto(quem) == livre, f"{curva} mudou a mira de {quem}"


@pytest.mark.parametrize("transporte", ["usb", "bt"])
@pytest.mark.parametrize("quem", QUATRO)
def test_o_analogico_fisico_segue_moldado(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, transporte: str, quem: str
) -> None:
    curva = {"zona_morta": 20, "curva": "precisa", "sensibilidade": 120}
    mesa = _MesaDaCurva(monkeypatch, tmp_path, transporte, {}, mesa=curva)
    molde = cv.Curva(zona_interna=0.2, forma="precisa", sensibilidade=1.2)

    mesa.fisico[quem] = (PEQUENO, 128, PEQUENO, 128)
    mesa.tiques(2)
    assert mesa.pads[quem].centro(), "os 10 % do físico caem na zona de 20 %"

    mesa.fisico[quem] = (FORA_DA_ZONA, 128, FORA_DA_ZONA, 128)
    mesa.tiques(2)
    eixos = mesa.pads[quem].analog[-1]
    moldado = cv.moldar(molde, FORA_DA_ZONA, 128)[0]
    assert moldado != FORA_DA_ZONA
    assert (eixos["lx"], eixos["rx"]) == (moldado, moldado)


@pytest.mark.parametrize("transporte", ["usb", "bt"])
@pytest.mark.parametrize("quem", QUATRO)
def test_a_mira_soma_ao_fisico_ja_moldado(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, transporte: str, quem: str
) -> None:
    livre = _quadros_sem_curva(monkeypatch, tmp_path, transporte, quem)
    mesa = _MesaDaCurva(
        monkeypatch, tmp_path, transporte, _todos_no_direito(), mesa={"zona_morta": 20})

    mesa.fisico[quem] = (128, 128, PEQUENO, 128)
    assert mesa.gesto(quem) == livre, "o tremor dentro da zona não soma à mira"

    mesa.fisico[quem] = (128, 128, FORA_DA_ZONA, 128)
    moldado = cv.moldar(cv.Curva(zona_interna=0.2), FORA_DA_ZONA, 128)[0]
    somados = mesa.gesto(quem)
    deflexoes = [quadro["rx"] - 128 for quadro in livre]
    assert [quadro["rx"] for quadro in somados] == [moldado + d for d in deflexoes]


@pytest.mark.parametrize("transporte", ["usb", "bt"])
@pytest.mark.parametrize("volta", range(4))
def test_cada_um_com_a_sua_curva_e_a_mira_inteira(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, transporte: str, volta: int
) -> None:
    """A curva em qualquer posição: a zona de cada peça não vaza para o físico nem para a mira."""
    zonas = (0, 20, 30, 50)
    curvas = {
        uniq: {"zona_morta": zonas[(n + volta) % 4]} for n, uniq in enumerate(QUATRO)}
    mesa = _MesaDaCurva(
        monkeypatch, tmp_path, transporte, _todos_no_direito(), curva_por_peca=curvas)
    for uniq in QUATRO:
        livre = _quadros_sem_curva(monkeypatch, tmp_path, transporte, uniq)
        assert [q["rx"] for q in mesa.gesto(uniq)] == [q["rx"] for q in livre]
    for uniq in QUATRO:
        mesa.fisico[uniq] = (PEQUENO, 128, 128, 128)
    mesa.tiques(2)
    for uniq in QUATRO:
        esperado = PEQUENO if curvas[uniq]["zona_morta"] == 0 else 128
        assert mesa.pads[uniq].analog[-1]["lx"] == esperado, uniq


@pytest.mark.parametrize(
    ("transporte", "presentes"),
    [("usb", (P3,)), ("bt", (P4,)), ("usb", (P2, P4)), ("bt", (P3, P4))],
)
def test_o_jogador_em_qualquer_posicao_que_sai_e_volta(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, transporte: str, presentes: tuple[str, ...]
) -> None:
    pecas = {uniq: dict(NO_DIREITO) for uniq in presentes}
    curvas = {uniq: {"zona_morta": 30} for uniq in presentes}
    pasta = tmp_path / "sem-curva-presentes"
    pasta.mkdir()
    sem_curva = _MesaDaCurva(monkeypatch, pasta, transporte, pecas, secundarios=presentes)
    mesa = _MesaDaCurva(
        monkeypatch, tmp_path, transporte, pecas, curva_por_peca=curvas, secundarios=presentes)
    for uniq in presentes:
        livre = sem_curva.gesto(uniq)
        assert mesa.gesto(uniq) == livre
        fora = mesa.coop._players.pop(uniq)
        mesa.tiques(2)
        mesa.coop._players[uniq] = fora
        mesa.tiques(2)
        assert [q["rx"] for q in mesa.gesto(uniq)] == [q["rx"] for q in sem_curva.gesto(uniq)]


@pytest.mark.parametrize("transporte", ["usb", "bt"])
@pytest.mark.parametrize("quem", QUATRO)
def test_a_inversao_e_a_troca_seguem_valendo_para_a_mira(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, transporte: str, quem: str
) -> None:
    """A forma é só do físico; o sentido e o lado de saída continuam sendo do jogador."""
    livre = _quadros_sem_curva(monkeypatch, tmp_path, transporte, quem)
    alvo = [q["rx"] for q in livre]

    invertido = _MesaDaCurva(
        monkeypatch, tmp_path, transporte, _todos_no_direito(),
        mesa={"zona_morta": 30, "inverter": ["rx"]})
    assert [q["rx"] for q in invertido.gesto(quem)] == [min(256 - v, 255) for v in alvo]

    trocado = _MesaDaCurva(
        monkeypatch, tmp_path, transporte, _todos_no_direito(),
        mesa={"zona_morta": 30, "trocar": True})
    quadros = trocado.gesto(quem)
    assert [q["lx"] for q in quadros] == alvo, "a troca leva a mira junto com o lado"
    assert all(q["rx"] == 128 for q in quadros)


@pytest.mark.parametrize("transporte", ["usb", "bt"])
@pytest.mark.parametrize("quem", QUATRO)
@pytest.mark.parametrize(
    ("mao", "destino"),  # (noqa-acento)
    [("esquerda", "analogico_esquerdo"), ("direita", "analogico_direito")],
)
def test_com_uma_mao_a_mira_sai_no_olhar_com_a_zona_morta_ligada(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    transporte: str,
    quem: str,
    mao: str,
    destino: str,
) -> None:
    livre = _quadros_sem_curva(monkeypatch, tmp_path, transporte, quem)
    pecas = {uniq: {"destino": destino} for uniq in QUATRO}
    mesa = _MesaDaCurva(
        monkeypatch, tmp_path, transporte, pecas,
        mesa={"zona_morta": 30, "mao": mao},  # (noqa-acento)
    )
    assert [q["rx"] for q in mesa.gesto(quem)] == [q["rx"] for q in livre]
    assert mesa.pads[quem].analog[-1]["lx"] == 128


@pytest.mark.parametrize("transporte", ["usb", "bt"])
@pytest.mark.parametrize("quem", QUATRO)
def test_a_rampa_da_calibracao_chega_inteira(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, transporte: str, quem: str
) -> None:
    """A rampa mede onde o jogo começa a ler: a zona do físico não pode entrar na conta."""
    mesa = _MesaDaCurva(
        monkeypatch, tmp_path, transporte, _todos_no_direito(), mesa={"zona_morta": 50})
    store = mesa.daemon.store
    rot.comecar_a_rampa(store, quem, mesa.relogio.agora)
    mesa.tiques(30)
    pedido = rot.rampa_agora(store, quem, mesa.relogio.agora)
    assert pedido is not None and pedido > 0
    assert mesa.pads[quem].analog[-1]["rx"] == 128 + rot.deflexao_da_rampa(pedido)[0]


@pytest.mark.parametrize("transporte", ["usb", "bt"])
@pytest.mark.parametrize(
    "mascaras",
    [
        {P1: "xbox", P2: "nintendo", P3: "dualsense", P4: "xbox"},
        {P1: "nintendo", P2: "xbox", P3: "nintendo", P4: "dualsense"},
        {P1: "dualsense", P2: "dualsense", P3: "xbox", P4: "nintendo"},
    ],
)
def test_toda_mascara_recebe_a_mira_inteira(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    transporte: str,
    mascaras: dict[str, str],
) -> None:
    def eixo_do_jogo(zona: int, pasta: Path) -> dict[str, int]:
        pasta.mkdir()
        mesa = _MesaDaCurva(
            monkeypatch, pasta, transporte, _todos_no_direito(), mesa={"zona_morta": zona})
        nos = {uniq: _NoDoPad() for uniq in QUATRO}
        for uniq, mascara in mascaras.items():
            pad = UinputGamepad(flavor=mascara)
            pad._device = nos[uniq]
            pad._ecodes = ecodes
            if uniq == P1:
                mesa.daemon._gamepad_device = pad
            else:
                mesa.coop._players[uniq].vpad = pad
            mesa.nos[uniq].giro = GESTO_LENTO
        mesa.tiques(4)
        return {uniq: no.eixos[ecodes.ABS_RX] for uniq, no in nos.items()}

    assert eixo_do_jogo(30, tmp_path / "com") == eixo_do_jogo(0, tmp_path / "sem"), mascaras

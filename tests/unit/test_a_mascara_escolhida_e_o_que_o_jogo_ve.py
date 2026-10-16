"""A-MASCARA-ESCOLHIDA-E-O-QUE-O-JOGO-VE-EM-TODO-MODO-01 — a tabela modo x caminho x máscara.

A pergunta (03/10): *«se na aba jogar a máscara funciona independente do
modo»*. O que se mediu no código e no diário (08/10): das nove combinações
(caminho nenhum, DualSense, Xbox x as três máscaras) e dos dois estados do
`/dev/uhid`, **uma só troca a máscara** — o caminho Xbox ESCOLHIDO, que veste
Xbox 360 em qualquer máscara. É decisão medida
(D-2709-O-XBOX-360-EM-TODA-MASCARA-NO-MODO-XBOX, G1/G3/L4 de 27/09: o Proton
não segura Edge nem Pro em `uinput` sem hidraw), e o diário a conta:
`vpad_vestido_pelo_modo mascara=dualsense no_jogo=xbox`, nove vezes desde 06/10.
O que faltava não era mais uma combinação respeitada: era a troca dizer POR QUE
(o log e o pad só diziam «vestido»), para a tela poder explicá-la.

A tabela abaixo é a régua: VID:PID literal que o kernel receberia, por
combinação, P1 a P4, com e sem `uhid`, com e sem cartão por controle. As trocas
(o caminho Xbox escolhido; sem `uhid`, a máscara DualSense) levam o motivo no pad.

MORDIDAS (cada uma reprova ao menos uma régua; devolva e confira o md5):
tire a chamada de `_vestir_o_aparelho` da fábrica; troque `normalizar_caminho`
por `caminho_resolvido` em `mascara_no_jogo`; tire o motivo da fábrica
(`troca_motivo`); faça `motivo_da_troca` devolver sempre o motivo.
"""

from __future__ import annotations

import pytest
import structlog.testing

from hefesto_dualsense4unix.daemon.subsystems.external_mask import registro_de_mascaras
from hefesto_dualsense4unix.integrations import uhid_gamepad
from hefesto_dualsense4unix.integrations.virtual_pad import (
    CAMINHO_DUALSENSE,
    CAMINHO_XBOX,
    motivo_da_degradacao,
    motivo_da_troca,
)
from tests.unit.test_no_modo_xbox_o_jogo_ve_o_pad import (  # noqa: F401
    MACS,
    MASCARAS,
    _evdev_que_grava,
    _hermetico,
    _no_de,
    _pad,
)

XBOX = (0x045E, 0x028E)
EDGE = (0x054C, 0x0DF2)
PRO = (0x057E, 0x2009)
POR_MASCARA = {"dualsense": EDGE, "xbox": XBOX, "nintendo": PRO}
JOGADORES = (1, 2, 3, 4)
MOTIVO = "modo_xbox_escolhido"
SEM_CANAL = "sem_canal_proprio"


@pytest.fixture
def uhid_de_pe(monkeypatch: pytest.MonkeyPatch) -> None:
    """O `/dev/uhid` disponível e o pad uhid sem kernel: nada abre em /dev."""
    monkeypatch.setattr(uhid_gamepad, "uhid_available", lambda: True)
    monkeypatch.setattr(uhid_gamepad.UhidDualSense, "start", lambda self: True)
    monkeypatch.setattr(
        uhid_gamepad.UhidDualSense, "wait_for_bind", lambda self, timeout_s=2.0: True
    )
    monkeypatch.setattr(uhid_gamepad.UhidDualSense, "stop", lambda self: None)


def _esperado(caminho: str | None, mascara: str) -> tuple[int, int]:
    """A tabela sem `uhid`, escrita à mão: o caminho Xbox ESCOLHIDO troca a máscara, e
    a máscara DualSense sem o canal próprio cai no Xbox 360 (a pergunta 6 da
    NO-MODO-XBOX-TUDO-FUNCIONA-01, resposta de 13/10)."""
    return XBOX if caminho == CAMINHO_XBOX or mascara == "dualsense" else POR_MASCARA[mascara]


class TestATabelaSemUhid:
    """MORDIDA: tire a chamada de `_vestir_o_aparelho` da fábrica, ou troque
    `normalizar_caminho` por `caminho_resolvido` em `mascara_no_jogo`."""

    @pytest.mark.parametrize("jogador", JOGADORES)
    @pytest.mark.parametrize("mascara", MASCARAS)
    @pytest.mark.parametrize("caminho", [None, CAMINHO_DUALSENSE, CAMINHO_XBOX])
    def test_o_par_que_o_kernel_recebe(
        self, caminho: str | None, mascara: str, jogador: int
    ) -> None:
        pad = _pad(mascara, caminho, player=jogador)
        try:
            assert _no_de(pad).vidpid == _esperado(caminho, mascara), (
                f"P{jogador}, caminho {caminho!r}, máscara {mascara}: o jogo recebeu "
                "outro aparelho que o da tabela"
            )
            assert pad.flavor == mascara, "o cartão (a máscara escolhida) não se perde"
        finally:
            pad.stop()

    @pytest.mark.parametrize("jogador", JOGADORES)
    @pytest.mark.parametrize("mascara", MASCARAS)
    def test_o_cartao_do_controle_vale_em_toda_vaga(self, mascara: str, jogador: int) -> None:
        """A máscara escolhida PARA ESTE controle (e não a do jogo) é a que veste:
        o cartão vence o padrão da sessão, no modo de fábrica e no Xbox."""
        mac = MACS[jogador - 1]
        registro_de_mascaras().set_mask(mac, mascara)
        outro = "xbox" if mascara != "xbox" else "dualsense"
        for caminho in (CAMINHO_DUALSENSE, CAMINHO_XBOX):
            pad = _pad(outro, caminho, identity=mac, player=jogador)
            try:
                assert pad.flavor == mascara, (caminho, mascara)
                assert _no_de(pad).vidpid == _esperado(caminho, mascara), (caminho, mascara)
            finally:
                pad.stop()


class TestATabelaComUhid:
    """Com o `/dev/uhid` de pé a máscara DualSense nasce HID de verdade nos dois
    caminhos que não são o Xbox; as outras duas máscaras seguem no `uinput`."""

    @pytest.mark.parametrize("jogador", JOGADORES)
    @pytest.mark.parametrize("mascara", MASCARAS)
    @pytest.mark.parametrize("caminho", [None, CAMINHO_DUALSENSE, CAMINHO_XBOX])
    def test_o_backend_e_o_aparelho(
        self, uhid_de_pe: None, caminho: str | None, mascara: str, jogador: int
    ) -> None:
        pad = _pad(mascara, caminho, player=jogador)
        try:
            if mascara == "dualsense" and caminho != CAMINHO_XBOX:
                assert pad.backend == "uhid", (caminho, jogador)
                assert pad.flavor == "dualsense"
            else:
                assert pad.backend == "uinput", (caminho, mascara, jogador)
                assert _no_de(pad).vidpid == _esperado(caminho, mascara)
            assert motivo_da_degradacao(pad) is None, (
                "com o uhid de pé e o modo escolhido não há queda a anunciar"
            )
        finally:
            pad.stop()


class TestATrocaDizOPorQue:
    """MORDIDA: tire o motivo da fábrica (`troca_motivo`), ou faça
    `motivo_da_troca` devolver sempre o motivo."""

    def test_a_pergunta_tem_um_dono(self) -> None:
        for caminho in (None, "", "qualquer", CAMINHO_DUALSENSE):
            for mascara in MASCARAS:
                assert motivo_da_troca(caminho, mascara) is None, (caminho, mascara)
        for mascara in ("dualsense", "nintendo"):
            assert motivo_da_troca(CAMINHO_XBOX, mascara) == MOTIVO, mascara
            assert motivo_da_troca(" XBOX ", mascara) == MOTIVO, mascara
        assert motivo_da_troca(CAMINHO_XBOX, "xbox") is None, "Xbox em Xbox não é troca"

    @pytest.mark.parametrize("mascara", MASCARAS)
    @pytest.mark.parametrize("caminho", [None, CAMINHO_DUALSENSE, CAMINHO_XBOX])
    def test_o_pad_leva_o_motivo_so_quando_trocou(
        self, caminho: str | None, mascara: str
    ) -> None:
        pad = _pad(mascara, caminho)
        try:
            trocou = _no_de(pad).vidpid != POR_MASCARA[mascara]
            esperado = (MOTIVO if caminho == CAMINHO_XBOX else SEM_CANAL) if trocou else None
            assert getattr(pad, "troca_motivo", None) == esperado, (caminho, mascara)
        finally:
            pad.stop()

    def test_o_diario_diz_o_motivo_da_troca(self) -> None:
        with structlog.testing.capture_logs() as diario:
            pad = _pad("nintendo", CAMINHO_XBOX, player=2)
        try:
            vestidos = [e for e in diario if e["event"] == "vpad_vestido_pelo_modo"]
            assert len(vestidos) == 1, vestidos
            assert vestidos[0]["mascara"] == "nintendo"
            assert vestidos[0]["no_jogo"] == "xbox"
            assert vestidos[0]["player"] == 2
            assert vestidos[0]["motivo"] == MOTIVO
        finally:
            pad.stop()

    def test_sem_troca_o_diario_cala(self) -> None:
        with structlog.testing.capture_logs() as diario:
            pad = _pad("nintendo", CAMINHO_DUALSENSE)
        try:
            assert not [e for e in diario if e["event"] == "vpad_vestido_pelo_modo"]
        finally:
            pad.stop()

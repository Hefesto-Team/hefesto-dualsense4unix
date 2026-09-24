"""STEAM-NO-FISICO-01 — no Modo Nativo, a barra e o número são do Hefesto.

A RESPOSTA DELA, 23/09/2026, em escolhas (`D-2309-NO-NATIVO-A-LUZ-E-O-NUMERO-
SAO-DO-HEFESTO`): *"No Modo Nativo, o Hefesto escreve a barra e o número
SEMPRE, com ou sem jogo segurando o controle."* Revoga o «zero escrita» do
Nativo (FEAT-PARITY-REVIEW-01) SÓ para a luz e o número; vibração, gatilhos e
áudio continuam do jogo.

O QUE HAVIA: a vigia do sequestro já reescrevia a barra no Nativo quando OUTRO
processo segurava o nó. Mas as mudanças do PRÓPRIO Hefesto — o gesto na aba, o
perfil, o controle que conecta no meio do jogo, a renumeração da mesa — ficavam
caladas atrás do `_output_mute` até ela sair do Nativo (defeito 6 da
conferência de 23/09).

A MATRIZ (regra dela, 23/09): cada régua roda com o P1 no RÁDIO e o P2 no
CABO, e os dois recebem — nunca só um transporte, nunca só o jogador 1.

AS MORDIDAS, exercidas e devolvidas com md5 (o relatório da sprint as lista):
devolva o portão do `_output_mute` em `_for_each_led`, `_write_partial_output`,
`reassert_resolved_outputs`, `defend_display`, `reescrever_lightbar_por_hidraw`
ou no reassert do hotplug, e a régua correspondente reprova.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydualsense.pydualsense import DSAudio, DSLight, DSTrigger

from hefesto_dualsense4unix.core import backend_pydualsense as bp
from hefesto_dualsense4unix.core.controller import OutputSpec
from hefesto_dualsense4unix.core.lightbar_gatilho import (
    COMMON_LIGHTBAR_B,
    COMMON_LIGHTBAR_R,
    COMMON_PLAYER_LEDS,
    mascara_de_player_leds,
)
from hefesto_dualsense4unix.core.trigger_effects import build_from_name

MAC_RADIO = "AA:BB:CC:00:00:01"
UNIQ_RADIO = "aabbcc000001"
MAC_CABO = "AA:BB:CC:00:00:02"
UNIQ_CABO = "aabbcc000002"

NUMERO_1 = (False, False, True, False, False)
NUMERO_2 = (False, True, False, True, False)
COR_1 = (0, 90, 255)
COR_2 = (255, 40, 40)


class _NoDeLed:
    """A classe LED do kernel de um controle no cabo (a regra 77 instalada)."""

    def __init__(self) -> None:
        self.cores: list[tuple[int, int, int]] = []
        self.numeros: list[tuple[bool, ...]] = []
        self.invalidacoes = 0
        self.indicator_dir = "/sys/class/leds/x"

    def writable(self) -> bool:
        return True

    def set_rgb(self, r: int, g: int, b: int, *, verify: bool = False) -> bool:
        self.cores.append((r, g, b))
        return True

    def set_players(self, bits: tuple[bool, ...]) -> bool:
        self.numeros.append(tuple(bits))
        return True

    def set_players_verified(self, bits: tuple[bool, ...]) -> bool:
        return self.set_players(bits)

    def invalidate_cache(self) -> None:
        self.invalidacoes += 1

    def get_rgb(self) -> tuple[int, int, int] | None:
        return self.cores[-1] if self.cores else None


def _handle(transporte: str) -> SimpleNamespace:
    escritos: list[list[int]] = []
    handle = SimpleNamespace(
        triggerL=DSTrigger(),
        triggerR=DSTrigger(),
        light=DSLight(),
        audio=DSAudio(),
        _raw_trigger_left=None,
        _raw_trigger_right=None,
        _output_muted=False,
        transporte=transporte,
        escritos=escritos,
    )
    handle.writeReport = lambda r: escritos.append(list(r)) or len(r)
    return handle


def _numero(uniq: str) -> bp._DesiredOutput:
    if uniq == UNIQ_CABO:
        return bp._DesiredOutput(led=COR_2, player_leds=NUMERO_2)
    return bp._DesiredOutput(led=COR_1, player_leds=NUMERO_1)


def _mesa_no_nativo() -> tuple[bp.PyDualSenseController, SimpleNamespace, _NoDeLed]:
    """P1 no rádio, P2 no cabo, e o Modo Nativo LIGADO pelo caminho de verdade."""
    ctl = bp.PyDualSenseController()
    radio = _handle("bt")
    cabo = _handle("usb")
    no_do_cabo = _NoDeLed()
    ctl._handles = {MAC_RADIO: radio, MAC_CABO: cabo}
    ctl._sysfs = {MAC_CABO: no_do_cabo}
    ctl._detect_transport = lambda h: h.transporte  # type: ignore[method-assign]
    ctl.set_auto_output_provider(_numero)
    ctl.set_output_mute(True)
    return ctl, radio, no_do_cabo


def _cor_do_report(report: list[int]) -> tuple[int, ...]:
    common = report[3:50]
    return tuple(common[COMMON_LIGHTBAR_R : COMMON_LIGHTBAR_B + 1])


def _numero_do_report(report: list[int]) -> int:
    return report[3:50][COMMON_PLAYER_LEDS]


class TestOGestoDelaSaiNoNativo:
    def test_a_cor_de_todos_sai_nos_dois_transportes(self) -> None:
        ctl, radio, no = _mesa_no_nativo()

        ctl.set_led((10, 20, 30))

        assert no.cores == [(10, 20, 30)]
        assert [_cor_do_report(r) for r in radio.escritos] == [(10, 20, 30)]

    def test_o_desenho_de_todos_sai_nos_dois_transportes(self) -> None:
        ctl, radio, no = _mesa_no_nativo()

        ctl.set_player_leds(NUMERO_2)

        assert no.numeros == [NUMERO_2]
        assert [_numero_do_report(r) for r in radio.escritos] == [
            mascara_de_player_leds(NUMERO_2)
        ]

    @pytest.mark.parametrize("uniq", [UNIQ_RADIO, UNIQ_CABO])
    def test_a_cor_de_um_controle_diz_escreveu(self, uniq: str) -> None:
        ctl, radio, no = _mesa_no_nativo()

        palavra = ctl.apply_output_for(uniq, OutputSpec(led=(7, 7, 7)))

        assert palavra == "escreveu"
        if uniq == UNIQ_CABO:
            assert no.cores == [(7, 7, 7)]
        else:
            assert [_cor_do_report(r) for r in radio.escritos] == [(7, 7, 7)]


class TestOHefestoRepintaNoNativo:
    def test_o_reassert_da_ativacao_de_perfil(self) -> None:
        ctl, _radio, no = _mesa_no_nativo()

        ctl.reassert_resolved_outputs()

        assert no.cores == [COR_2]
        assert no.numeros == [NUMERO_2]

    def test_a_defesa_de_exibicao(self) -> None:
        ctl, _radio, no = _mesa_no_nativo()

        ctl.defend_display()

        assert no.invalidacoes == 1
        assert no.cores == [COR_2]

    def test_o_gatilho_do_fim_da_sequencia_no_radio(self) -> None:
        ctl, radio, _ = _mesa_no_nativo()

        resultado = ctl.reescrever_lightbar_por_hidraw()

        assert resultado == {MAC_RADIO: True}
        (report,) = radio.escritos
        assert _cor_do_report(report) == COR_1
        assert _numero_do_report(report) == mascara_de_player_leds(NUMERO_1)

    def test_o_cabo_renumerado(self) -> None:
        ctl, _radio, no = _mesa_no_nativo()

        assert ctl.repintar_o_cabo_por_sysfs() != {}
        assert no.cores == [COR_2]

    def test_o_controle_que_conecta_no_meio_do_jogo(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O nó que nasce no Nativo recebe a cor e o número dele, na hora."""
        from hefesto_dualsense4unix.core import sysfs_leds

        ctl, _radio, _no = _mesa_no_nativo()
        ctl._sysfs = {}
        novo = _NoDeLed()
        monkeypatch.setattr(sysfs_leds, "discover", lambda: {UNIQ_CABO: novo})

        ctl._refresh_sysfs_leds()

        assert novo.cores == [COR_2]
        assert novo.numeros == [NUMERO_2]


class TestOResto:
    """O que a decisão NÃO revogou: vibração, gatilhos, áudio — e o LED do mic."""

    def test_o_fluxo_do_report_thread_continua_mudo(self) -> None:
        ctl, radio, _ = _mesa_no_nativo()

        assert all(h._output_muted for h in ctl._handles.values())
        ctl.set_led((1, 2, 3))
        # O que saiu pelo rádio é o report MÍNIMO: sem vibração, sem gatilho,
        # sem áudio (valid_flag0 e valid_flag2 zerados).
        common = radio.escritos[-1][3:50]
        assert common[0] == 0
        assert common[38] == 0

    def test_o_gatilho_fica_guardado(self) -> None:
        ctl, _radio, _no = _mesa_no_nativo()
        efeito = build_from_name("Rigid", [5, 200])

        palavra = ctl.apply_output_for(UNIQ_CABO, OutputSpec(trigger_left=efeito))

        assert palavra == "registrado"
        assert ctl._desired_by_uniq[UNIQ_CABO].trigger_left == efeito

    def test_o_led_do_mic_nao_sai_por_fora(self) -> None:
        ctl, radio, no = _mesa_no_nativo()

        ctl.set_mic_led(True)

        assert radio.escritos == []
        assert no.cores == []


def test_a_decisao_esta_no_dono_das_constantes() -> None:
    """Uma constante, com a decisão escrita: é a que o `apply_output_for` lê."""
    assert frozenset({"led", "player_leds"}) == bp._CAMPOS_QUE_O_NATIVO_ESCREVE

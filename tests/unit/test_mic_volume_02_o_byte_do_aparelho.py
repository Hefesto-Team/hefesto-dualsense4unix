"""MIC-VOLUME-02 — o `common[6]` do aparelho, medido na bancada dela e LIGADO.

**Decisão dela, 09/09/2026** (`D-0909-O-VOLUME-DO-MIC-LIGA-O-BYTE-DO-
APARELHO`): *"3-c"* — ligar o byte do aparelho, revogando neste ponto a
decisão de 06/09 que o mantinha fora da chamada.

O QUE DECIDIU FOI A BANCADA, e não uma leitura de código
-------------------------------------------------------
Duas afirmações desta casa se contradiziam, e nenhuma podia desempatar a outra:

* a docstring do `mic.volume.set` dizia que *"o DualSense não expõe registrador
  de ganho de microfone em transporte nenhum"*;
* o mapa de canais e o `hid-playstation` desta máquina diziam que o registrador
  existe e **tem nome** (`mic_volume`, comentário `0x0 - 0x40`).

O olho dela desempatou no CABO, em 09/09/2026, com o P2 plugado e a fonte do
sistema travada a 100 % para isolar o ganho do aparelho: *"Deu certo.
funciona"* (`docs/data/ensaios.csv`, `folha-mic-volume-o-byte-age-cabo-0909`).
Byte que obedece ganha campo — e o que esta régua guarda é o campo, não a
medição: o que o aparelho faz está no caderno, o que o produto faz está aqui.

O QUE CADA BLOCO MORDE (cada mordida foi arrancada, conferida reprovando e
devolvida)
-------------------------------------------------------------------------
1. o piso de 1 % da régua: sem ele, `1 %` vira byte `0` — o número na tela
   dizendo "um pouquinho" sobre um microfone mudo no aparelho;
2. o bit `0x40` do `flag0`: escrever o byte sem tomar a posse deixa o firmware
   dono do campo, e o `common[6]` sai inerte. É a diferença entre mandar e
   mandar de verdade;
3. a vizinhança: escrever o microfone NÃO pode mexer em fone, alto-falante nem
   rota — cada byte daquele bloco tem dono próprio;
4. `microfone=False` na devolução do alto-falante: sem ele, um "Devolver" do som
   apaga em silêncio o ganho de captura que ela ajustou;
5. a chamada no `mic.volume.set`: arrancá-la faz o gesto dela mexer só na fonte
   do sistema, que é o mundo de antes desta sprint;
6. a chamada no applier de perfil: arrancá-la faz o gesto dela valer e o PERFIL
   dela não — metade do número ficaria pelo caminho na próxima troca de janela;
7. o `uniq` nos dois: sem ele o byte vai para o handle do vizinho.

MACs fake (regra da casa: octetos 4 e 5 zerados).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core import ds_output_report as rep
from hefesto_dualsense4unix.core.backend_pydualsense import (
    byte_do_volume_do_microfone,
)

#: Os dois controles da mesa, com a máscara da casa.
P2 = "aabbcc000002"
P3 = "aabbcc000003"

#: As duas placas de captura — uma por aparelho no cabo.
FONTE_P2 = "alsa_input.usb-Sony_DualSense-00.mono-fallback"
FONTE_P3 = "alsa_input.usb-Sony_DualSense-01.mono-fallback"


# ---------------------------------------------------------------------------
# Handles e backend REAIS — o `_build_common` é a única testemunha do fio
# ---------------------------------------------------------------------------


def _handle_real() -> Any:
    """Handle da pydualsense sem device, só com o estado que o builder lê.

    Mesmo molde de `tests/unit/test_som_02_devolucao_da_posse.py`: um dublê de
    handle não teria os bits de validação, e é justamente o bit que decide se o
    byte age. Dublê mais frouxo que a peça real já deu verde sobre gesto que
    nunca gravou um byte nesta casa.
    """
    from pydualsense.pydualsense import DSAudio, DSLight, DSTrigger

    from hefesto_dualsense4unix.core.backend_pydualsense import _PinnedPyDualSense

    h = _PinnedPyDualSense.__new__(_PinnedPyDualSense)
    h.audio = DSAudio()
    h.light = DSLight()
    h.triggerL = DSTrigger()
    h.triggerR = DSTrigger()
    h.leftMotor = 0
    h.rightMotor = 0
    h._suppress_leds = False
    h._volumes_audio = [None, None, None, None]
    h._preamp_audio = None
    h._mic_mute_desejado = None
    h._mic_led_desejado = None
    h._raw_trigger_left = None
    h._raw_trigger_right = None
    h.connected = True
    h.conType = SimpleNamespace(name="USB")
    return h


def _backend_com_dois() -> tuple[Any, Any, Any]:
    """`PyDualSenseController` real com dois handles reais e sem hardware."""
    from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController
    from hefesto_dualsense4unix.core.evdev_reader import EvdevReader

    reader = EvdevReader(device_path=None)
    reader._device_path = None
    inst = PyDualSenseController(evdev_reader=reader)
    h2, h3 = _handle_real(), _handle_real()
    inst._handles = {"AA:BB:CC:00:00:02": h2, "AA:BB:CC:00:00:03": h3}
    inst._primary_key = "AA:BB:CC:00:00:02"
    return inst, h2, h3


# ---------------------------------------------------------------------------
# 1. A RÉGUA — uma conta, num lugar só
# ---------------------------------------------------------------------------


class TestARegua:
    def test_o_teto_e_lido_do_protocolo_e_nao_digitado(self) -> None:
        """100 % é o teto REAL do campo, e ele vem de `ds_output_report`.

        Um segundo `0x40` escrito na régua envelheceria no dia em que o
        primeiro mudasse — é a razão pela qual a régua do alto-falante virou
        módulo próprio.
        """
        assert rep.TETO_MIC_VOLUME == 0x40
        assert byte_do_volume_do_microfone(100) == rep.TETO_MIC_VOLUME

    def test_zero_e_zero_e_um_por_cento_nao_e_silencio(self) -> None:
        """MORDIDA 1: trocar o `max(1, ...)` pela conta crua `v * 0x40 // 100`.

        A conta crua do enunciado da sprint devolve **0 para 1 %** — a tela
        diria "um pouquinho" sobre um microfone mudo no aparelho. É a mesma
        regra que `core/speaker_scale.volume_do_percentual` já cobra do irmão:
        *"pedir 1 % e receber silêncio seria o defeito de novo"*.
        """
        assert byte_do_volume_do_microfone(0) == 0, (
            "0 % tem de ser ZERO no registrador — é o único valor que o resto "
            "do sistema reconhece como desligado")
        assert byte_do_volume_do_microfone(1) >= 1, (
            "1 % caiu em byte 0: a ponta de baixo do curso não faz nada, e a "
            "tela promete o que o aparelho não entrega")

    def test_a_conta_nunca_desce_quando_a_porcentagem_sobe(self) -> None:
        """Monotonia, e o limite de 64 passos para 101 valores DECLARADO."""
        bytes_ = [byte_do_volume_do_microfone(p) for p in range(101)]
        assert bytes_ == sorted(bytes_)
        assert max(bytes_) == rep.TETO_MIC_VOLUME
        assert min(bytes_) == 0

    def test_lixo_e_fora_de_faixa_nao_viram_byte_invalido(self) -> None:
        """O campo tem teto REAL: mandar mais é mandar lixo que o firmware lê."""
        assert byte_do_volume_do_microfone(150) == rep.TETO_MIC_VOLUME
        assert byte_do_volume_do_microfone(-5) == 0
        assert byte_do_volume_do_microfone(None) == 0
        assert byte_do_volume_do_microfone("nada") == 0


# ---------------------------------------------------------------------------
# 2. O BYTE NO FIO — e o bit que decide se ele age
# ---------------------------------------------------------------------------


class TestOByteSaiNoFioComPosse:
    def test_o_byte_e_o_bit_de_validacao_saem_juntos(self) -> None:
        """MORDIDA 2: arrancar a posse (escrever `common[6]` sem o `0x40`).

        Sem o bit, o firmware continua dono do campo e o byte sai INERTE — o
        produto diria "aplicado" sobre um report que o aparelho ignora. É
        exatamente a classe de defeito do AUDIO-OWNER-01, do outro lado.
        """
        inst, h2, _h3 = _backend_com_dois()
        assert inst.set_microphone_volume(100, uniq=P2) is True

        common = h2._build_common(rumble_asserted=False)
        assert common[rep.COMMON_MIC_VOLUME] == rep.TETO_MIC_VOLUME, (
            f"o `common[6]` saiu {common[rep.COMMON_MIC_VOLUME]}, não o teto")
        assert common[0] & rep.VALID_FLAG0_MIC_VOLUME, (
            "o bit 0x40 do flag0 não subiu: o byte vai no fio e o firmware o "
            "descarta — mandar sem posse é não mandar")

    def test_escrever_o_microfone_nao_mexe_na_vizinhanca(self) -> None:
        """MORDIDA 3: passar `headphone=`/`speaker=`/`audio_path=` junto.

        Os quatro bytes de `common[4..7]` têm posse POR BYTE, cada um com o seu
        bit. O `common[7]` é o pior: ele carrega a rota de saída E o caminho do
        microfone, e escrevê-lo inteiro apaga metade em silêncio (a regressão
        medida em 02/08, quando o microfone parou de captar).
        """
        inst, h2, _h3 = _backend_com_dois()
        inst.set_microphone_volume(50, uniq=P2)

        common = h2._build_common(rumble_asserted=False)
        outros = (
            rep.VALID_FLAG0_HEADPHONE_VOLUME
            | rep.VALID_FLAG0_SPEAKER_VOLUME
            | rep.VALID_FLAG0_AUDIO_PATH
        )
        assert common[0] & outros == 0, (
            "o gesto do microfone tomou a posse de byte que não é dele")
        assert common[rep.COMMON_HEADPHONE_VOLUME] == 0
        assert common[rep.COMMON_SPEAKER_VOLUME] == 0
        assert common[rep.COMMON_AUDIO_PATH] == 0

    def test_o_zero_com_dono_nao_e_a_mesma_coisa_que_sem_dono(self) -> None:
        """0 % TOMA a posse — e é isso que faz o silêncio ser nosso, não dele.

        `0x00` sem o bit é "o firmware manda"; `0x00` com o bit é "mandamos
        zero". Confundir os dois é a distinção cara do AUDIO-OWNER-01.
        """
        inst, h2, _h3 = _backend_com_dois()
        antes = h2._build_common(rumble_asserted=False)
        assert antes[0] & rep.VALID_FLAG0_MIC_VOLUME == 0

        assert inst.set_microphone_volume(0, uniq=P2) is True
        depois = h2._build_common(rumble_asserted=False)
        assert depois[rep.COMMON_MIC_VOLUME] == 0
        assert depois[0] & rep.VALID_FLAG0_MIC_VOLUME, (
            "0 % não tomou a posse: o firmware continua dono e o mudo por "
            "volume não vale nada")

    def test_sem_handle_para_o_uniq_ninguem_diz_que_aplicou(self) -> None:
        """"Não havia controle" nunca pode ser lido como "aplicado"."""
        inst, _h2, _h3 = _backend_com_dois()
        assert inst.set_microphone_volume(70, uniq="aabbcc0000ff") is False


class TestPorControle:
    def test_o_p2_em_zero_e_o_p3_em_cem_ao_mesmo_tempo(self) -> None:
        """MORDIDA 7: ignorar o `uniq` e escrever no primário.

        É o critério de pronto "por controle" da sprint, escrito em bytes: dois
        DualSense na mesa, dois ganhos diferentes, ao mesmo tempo. Sem o `uniq`
        os dois handles sairiam com o mesmo byte — e o gesto de um mexeria no
        microfone do outro.
        """
        inst, h2, h3 = _backend_com_dois()
        assert inst.set_microphone_volume(0, uniq=P2) is True
        assert inst.set_microphone_volume(100, uniq=P3) is True

        c2 = h2._build_common(rumble_asserted=False)
        c3 = h3._build_common(rumble_asserted=False)
        assert c2[rep.COMMON_MIC_VOLUME] == 0
        assert c3[rep.COMMON_MIC_VOLUME] == rep.TETO_MIC_VOLUME
        assert c2[0] & rep.VALID_FLAG0_MIC_VOLUME
        assert c3[0] & rep.VALID_FLAG0_MIC_VOLUME


# ---------------------------------------------------------------------------
# 3. A DEVOLUÇÃO DE UM CAMPO NÃO GASTA A DO OUTRO
# ---------------------------------------------------------------------------


class TestADevolucaoNaoGastaOCampoVizinho:
    def test_devolver_o_alto_falante_nao_apaga_o_ganho_do_microfone(self) -> None:
        """MORDIDA 4: tirar o `microfone=False` do `release_speaker_volume`.

        Sem ele o byte do microfone volta ao firmware junto com o do som, e em
        SILÊNCIO: o número fica na tela e o aparelho deixa de obedecer. São dois
        campos, com dois donos e duas telas.
        """
        inst, h2, _h3 = _backend_com_dois()
        inst.set_microphone_volume(100, uniq=P2)
        inst.set_speaker_volume(180, uniq=P2)

        assert inst.release_speaker_volume(uniq=P2) is True
        common = h2._build_common(rumble_asserted=False)
        assert common[rep.COMMON_MIC_VOLUME] == rep.TETO_MIC_VOLUME, (
            "o `Devolver` do alto-falante levou o ganho do microfone junto")
        assert common[0] & rep.VALID_FLAG0_MIC_VOLUME, (
            "a posse do `common[6]` caiu com a do alto-falante")
        assert common[0] & rep.VALID_FLAG0_SPEAKER_VOLUME == 0
        assert common[rep.COMMON_SPEAKER_VOLUME] == 0

    def test_devolver_o_microfone_nao_apaga_o_volume_do_som(self) -> None:
        """O caminho inverso, e pela mesma razão."""
        inst, h2, _h3 = _backend_com_dois()
        inst.set_speaker_volume(180, uniq=P2)
        inst.set_microphone_volume(100, uniq=P2)

        assert inst.release_microphone_volume(uniq=P2) is True
        common = h2._build_common(rumble_asserted=False)
        assert common[0] & rep.VALID_FLAG0_MIC_VOLUME == 0
        assert common[rep.COMMON_MIC_VOLUME] == 0
        assert common[rep.COMMON_SPEAKER_VOLUME] == 180, (
            "a devolução do microfone gastou o volume do alto-falante")

    def test_a_devolucao_inteira_continua_devolvendo_os_quatro(self) -> None:
        """O default do handle não mudou: quem pede tudo recebe tudo de volta."""
        inst, h2, _h3 = _backend_com_dois()
        inst.set_microphone_volume(100, uniq=P2)
        inst.set_speaker_volume(180, uniq=P2)

        h2.release_audio_volumes()
        common = h2._build_common(rumble_asserted=False)
        assert common[0] & rep.VALID_FLAG0_AUDIO_MASK == 0
        assert list(common[4:8]) == [0, 0, 0, 0]


# ---------------------------------------------------------------------------
# 4. OS DOIS CHAMADORES — o gesto dela e o perfil dela
# ---------------------------------------------------------------------------


class _Aparelho:
    """O que chegou a `set_microphone_volume`, com a assinatura ESTRITA.

    `uniq` é keyword-only e sem padrão, igual à do produto. Um dublê mais
    frouxo que a peça real é o instrumento falso que esta casa mais pegou — em
    04/09/2026, duas vezes num dia.
    """

    def __init__(self) -> None:
        self.escritas: list[tuple[int, str | None]] = []

    def set_microphone_volume(self, percentual: int, *, uniq: str | None) -> bool:
        self.escritas.append((int(percentual), uniq))
        return True


@pytest.mark.asyncio
async def test_o_gesto_dela_chega_ao_aparelho_no_controle_certo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MORDIDA 5: arrancar a chamada do `_handle_mic_volume_set`.

    Sem ela o gesto volta a mexer só na fonte do sistema — o mundo de antes
    desta sprint, com o campo do aparelho escrito e nunca ligado, que é a
    classe de defeito mais cara desta casa.
    """
    from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
    from hefesto_dualsense4unix.daemon.state_store import StateStore
    from hefesto_dualsense4unix.integrations import audio_control

    monkeypatch.setattr(
        audio_control, "definir_volume_da_captura",
        lambda _v, *, fonte: bool(fonte))
    monkeypatch.setattr(audio_control, "volume_da_captura", lambda *, fonte: 70)
    monkeypatch.setattr(
        audio_control, "fonte_de_captura_do_uniq",
        lambda uniq, **_kw: {P2: FONTE_P2, P3: FONTE_P3}.get(uniq))

    aparelho = _Aparelho()
    aparelho.describe_controllers = lambda: [  # type: ignore[attr-defined]
        {"uniq": P2, "connected": True}, {"uniq": P3, "connected": True}]

    class _Host(IpcHandlersMixin):  # type: ignore[misc]
        def __init__(self) -> None:
            self.controller = aparelho
            self.daemon = SimpleNamespace(controller=aparelho)
            self.store = StateStore()

    res = await _Host()._handle_mic_volume_set({"volume": 70, "uniq": P3})

    assert res["status"] == "ok"
    assert res["aparelho"] is True
    assert aparelho.escritas == [(70, P3)], (
        "o segundo degrau não saiu, ou saiu para o controle errado: "
        f"{aparelho.escritas}")


@pytest.mark.asyncio
async def test_sem_fonte_ninguem_escreve_nem_no_aparelho(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`sem_fonte` deixa o deslizante CINZA — e cinza não promete nada.

    Escrever o byte do aparelho por baixo de um controle insensível seria a
    tela prometendo nada e o aparelho mudando de ganho: o mesmo engano do
    `sem_fonte` que mentia "aplicado", só do outro lado.
    """
    from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
    from hefesto_dualsense4unix.daemon.state_store import StateStore
    from hefesto_dualsense4unix.integrations import audio_control

    monkeypatch.setattr(audio_control, "fonte_de_captura_do_uniq",
                        lambda _uniq, **_kw: None)

    aparelho = _Aparelho()
    aparelho.describe_controllers = lambda: [  # type: ignore[attr-defined]
        {"uniq": P2, "connected": True}]

    class _Host(IpcHandlersMixin):  # type: ignore[misc]
        def __init__(self) -> None:
            self.controller = aparelho
            self.daemon = SimpleNamespace(controller=aparelho)
            self.store = StateStore()

    res = await _Host()._handle_mic_volume_set({"volume": 70, "uniq": P2})

    assert res["status"] == "sem_fonte"
    assert aparelho.escritas == [], (
        f"escreveu no aparelho com o deslizante cinza: {aparelho.escritas}")


def test_o_perfil_dela_tambem_chega_ao_aparelho(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MORDIDA 6: arrancar a chamada do `apply_profile_mic`.

    **A cura cobre TODOS os chamadores**, e este é o segundo. Ligar o byte só
    no gesto vivo faria o número voltar ao disco, ser reaplicado na próxima
    troca de janela, e metade dele ficar pelo caminho — o preço que esta casa
    já pagou duas vezes num dia só.
    """
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon
    from hefesto_dualsense4unix.integrations import audio_control

    monkeypatch.setattr(
        audio_control, "definir_volume_da_captura", lambda _v, *, fonte: True)
    monkeypatch.setattr(
        audio_control, "fonte_de_captura_do_uniq",
        lambda uniq: {P2: FONTE_P2, P3: FONTE_P3}.get(uniq))

    aparelho = _Aparelho()
    daemon = Daemon.__new__(Daemon)
    daemon.controller = aparelho  # type: ignore[attr-defined]

    daemon.apply_profile_mic(volume=42, uniq=P3, origin="teste")

    assert aparelho.escritas == [(42, P3)], (
        "o perfil aplicou só o degrau da fonte do sistema: "
        f"{aparelho.escritas}")


# ---------------------------------------------------------------------------
# 5. O PERFIL SOBREVIVE AO SALVAR
# ---------------------------------------------------------------------------


def test_o_volume_por_peca_atravessa_o_salvar_e_volta() -> None:
    """Ida e volta do `controllers[uniq].mic.volume` pelo disco.

    Esta casa já perdeu **6 de 11 campos** num "Salvar", e três deles eram
    DESTRUÍDOS pelo próprio Salvar depois de a aba ter gravado o valor certo.
    Campo que o aparelho obedece e o disco esquece é meio campo.
    """
    from hefesto_dualsense4unix.profiles.loader import load_profile, save_profile
    from hefesto_dualsense4unix.profiles.schema import (
        ControllerMicOverride,
        ControllerOverrides,
        MatchAny,
        Profile,
    )

    perfil = Profile(
        name="a-mesa-de-dois",
        match=MatchAny(),
        controllers={
            P2: ControllerOverrides(mic=ControllerMicOverride(volume=0)),
            P3: ControllerOverrides(mic=ControllerMicOverride(volume=100)),
        },
    )
    save_profile(perfil, origem="teste:mic-volume-02")
    de_volta = load_profile("a-mesa-de-dois")

    assert de_volta.controllers is not None
    assert de_volta.controllers[P2].mic is not None
    assert de_volta.controllers[P2].mic.volume == 0, (
        "o 0 % do P2 não voltou do disco — e `0` é justamente o valor que um "
        "`if volume:` descarta como se fosse ausência")
    assert de_volta.controllers[P3].mic is not None
    assert de_volta.controllers[P3].mic.volume == 100
    assert byte_do_volume_do_microfone(
        de_volta.controllers[P3].mic.volume) == rep.TETO_MIC_VOLUME

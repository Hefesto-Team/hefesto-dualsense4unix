"""SOM-SEMPRE-01 — o volume nasce em 100%, em todo controle, sem ninguém pedir.

**A medição que é o alicerce disto**, feita na bancada na madrugada de
15-16/08/2026, com o controle azul na mão, no CABO, em teste CEGO (ela relatava
o que ouvia sem saber o que fora enviado). Três passadas em
`docs/data/ensaios.csv`, com o MESMO arquivo, a MESMA rota e o MESMO sink::

    sfx-cabo-sem-posse    volume nunca escrito por nós ... ela: "nenhum"      MUDO
    sfx-cabo-com-posse    `speaker volume 85` ........... ela: "bep bep bep"  SOA
    sfx-cabo-volume-zero  `speaker volume 0` ............ ela: "mudo"         MUDO

Nada mais mudou entre elas. A variável é a POSSE dos bytes de volume
(`common[4..7]`): enquanto ninguém a tomava, o alto-falante ficava mudo — e o
comentário do `_PinnedPyDualSense.__init__` já dizia *"idem, mandando volume
ZERO em todo report"* desde 25/07 sem que ninguém o tivesse ligado ao silêncio.
"A casa sabe e o produto não faz", de novo, e agora na mesma família do
keepalive que cancelava o rumble pelos BYTES.

A decisão de produto, textual (16/08/2026, 00h): **

O que estes testes travam:

1. a adoção de QUALQUER controle toma a posse e escreve 100%;
2. o "100%" é o da régua ÚNICA — o mesmo número que a barra da aba Status e o
   `speaker volume 100` da linha de comando produzem;
3. o microfone continua SEM DONO (o volume de captura é do kernel);
   **a ROTA saiu deste item em 16/09/2026** — `SOM-ROTA-02` mediu que não
   escrevê-la não é neutro, é escolher o fone vazio, e o alto-falante nascia
   mudo apesar dos 100%;
4. vale para o 2º, o 4º e o 7º controle, inclusive numa mesa já online;
5. quem tem opinião — perfil, janela, linha de comando — continua vencendo;
6. devolver a posse (`speaker release`) NÃO emudece: o firmware conserva os
   100% que mandamos.
"""

from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.core import ds_output_report as rep
from hefesto_dualsense4unix.core.backend_pydualsense import (
    ROTA_PADRAO_DO_SOM,
    VOLUME_PADRAO_DO_SOM,
    PyDualSenseController,
    _PinnedPyDualSense,
)
from hefesto_dualsense4unix.core.speaker_scale import (
    percentual_do_volume,
    volume_do_percentual,
)


class _Handle:
    """O mínimo de um handle adotado: o que a escrita de volume mexe."""

    def __init__(self) -> None:
        self._volumes_audio: list[int | None] = [None, None, None, None]
        self._preamp_audio: int | None = None
        self._speaker_volume_pref: int | None = None

    def set_audio_volumes(
        self,
        *,
        headphone: int | None = None,
        speaker: int | None = None,
        microphone: int | None = None,
        audio_path: int | None = None,
        preamp: int | None = None,
    ) -> None:
        # Mesma disciplina de posse por byte do `_PinnedPyDualSense`: campo
        for pos, valor in enumerate((headphone, speaker, microphone, audio_path)):
            if valor is not None:
                self._volumes_audio[pos] = int(valor)
        if preamp is not None:
            self._preamp_audio = int(preamp)


def _backend_sem_hardware() -> PyDualSenseController:
    """`PyDualSenseController` real, sem tocar em aparelho nenhum.

    Real de propósito: o que se afere é o caminho de adoção que roda na
    máquina do usuário, e um dublê de backend provaria apenas que a linha foi
    digitada.
    """
    from hefesto_dualsense4unix.core.evdev_reader import EvdevReader

    reader = EvdevReader(device_path=None)
    reader._device_path = None
    return PyDualSenseController(evdev_reader=reader)


def _backend_com_um_handle() -> tuple[PyDualSenseController, _Handle]:
    inst = _backend_sem_hardware()
    handle = _Handle()
    inst._handles = {"AA:BB:CC:00:00:01": handle}  # type: ignore[dict-item]
    inst._primary_key = "AA:BB:CC:00:00:01"
    return inst, handle


def test_a_adocao_toma_a_posse_e_poe_o_som_em_cem_por_cento() -> None:
    """Sem clique nenhum, o controle adotado já sai com volume 100%."""
    inst, handle = _backend_com_um_handle()

    assert handle._volumes_audio == [None, None, None, None], (
        "sanidade: o handle nasce sem dono, que é o estado que emudecia"
    )

    assert inst.assumir_volume_padrao_na_adocao("AA:BB:CC:00:00:01", handle) is True

    assert handle._volumes_audio[1] == VOLUME_PADRAO_DO_SOM
    assert handle._speaker_volume_pref == VOLUME_PADRAO_DO_SOM


def test_o_fone_vai_junto_porque_ele_manda_por_cima_da_rota() -> None:
    """Fone e alto-falante recebem o MESMO valor, e isso é medição, não simetria."""
    inst, handle = _backend_com_um_handle()

    inst.assumir_volume_padrao_na_adocao("AA:BB:CC:00:00:01", handle)

    assert handle._volumes_audio[0] == VOLUME_PADRAO_DO_SOM
    assert handle._volumes_audio[0] == handle._volumes_audio[1]


def test_o_microfone_continua_sem_dono_na_adocao() -> None:
    """A posse é POR BYTE, e a adoção toma só os que ela precisa."""
    inst, handle = _backend_com_um_handle()

    inst.assumir_volume_padrao_na_adocao("AA:BB:CC:00:00:01", handle)

    assert handle._volumes_audio[2] is None, "o volume do microfone é do kernel"


def test_o_pre_amplificador_entra_na_mesma_posse() -> None:
    """Volume sem pré-amp é um de três botões — e foi o que deixou 60% do curso inerte."""
    inst, handle = _backend_com_um_handle()

    inst.assumir_volume_padrao_na_adocao("AA:BB:CC:00:00:01", handle)

    assert handle._preamp_audio == rep.SP_PREAMP_GAIN_PADRAO


def test_o_cem_por_cento_e_o_da_regua_unica_e_relê_cem_na_tela() -> None:
    """O default sai de `speaker_scale`, e volta como 100% na aba Status."""
    assert volume_do_percentual(100) == VOLUME_PADRAO_DO_SOM
    assert percentual_do_volume(VOLUME_PADRAO_DO_SOM) == 100


def test_o_default_nao_e_255_nem_0x64_e_a_curva_medida_e_a_razao() -> None:
    """102, e não 255: de 102 para cima a curva medida em 01/08 não muda mais."""
    assert VOLUME_PADRAO_DO_SOM == 102
    assert VOLUME_PADRAO_DO_SOM != rep.TETO_SPEAKER_VOLUME
    assert VOLUME_PADRAO_DO_SOM <= rep.TETO_HEADPHONE_VOLUME, (
        "o fone recebe o mesmo valor e satura em 0x7F — acima disso o clamp "
        "por campo faria fone e alto-falante divergirem em silêncio"
    )


def _connect_com_handles_falsos(
    inst: PyDualSenseController,
    monkeypatch: pytest.MonkeyPatch,
    chaves: list[str],
) -> dict[str, _Handle]:
    """Roda o `connect()` REAL adotando os `chaves` pedidos, sem hardware."""
    criados: dict[str, _Handle] = {}

    def _enumerar() -> list[tuple[str, str, bool]]:
        return [(k, f"/dev/hidraw-falso-{i}", False) for i, k in enumerate(chaves)]

    def _abrir(path: str, *, is_edge: bool = False) -> _Handle:
        chave = chaves[int(path.rsplit("-", 1)[1])]
        h = criados.get(chave)
        if h is None:
            h = _Handle()
            criados[chave] = h
        return h

    monkeypatch.setattr(inst, "_enumerate_device_keys", _enumerar)
    monkeypatch.setattr(inst, "_open_one", _abrir)
    monkeypatch.setattr(inst, "_refresh_sysfs_leds", lambda: None)
    monkeypatch.setattr(inst, "_reapply_desired", lambda key, handle: None)
    monkeypatch.setattr(inst, "reassert_resolved_outputs", lambda: None)
    monkeypatch.setattr(inst, "_recompute_primary", lambda: None)
    inst.connect()
    return criados


def test_o_connect_poe_o_som_em_cem_em_todo_controle_que_ele_adota(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """**A MORDIDA.** É o `connect()` que adota, e é ele que tem de escrever.

    Sem esta linha o produto volta ao estado medido: controle plugado, daemon
    vivo, som mudo, e nenhuma mensagem de erro em lugar nenhum.

    MORDIDA: remover a chamada a `assumir_volume_padrao_na_adocao` do laço de
    `new_handles` em `PyDualSenseController.connect`.
    """
    inst = _backend_sem_hardware()

    criados = _connect_com_handles_falsos(
        inst, monkeypatch, ["AA:BB:CC:00:00:01"]
    )

    handle = criados["AA:BB:CC:00:00:01"]
    assert handle._volumes_audio[1] == VOLUME_PADRAO_DO_SOM
    assert handle._speaker_volume_pref == VOLUME_PADRAO_DO_SOM


def test_vale_para_os_sete_controles_e_nao_so_para_o_primeiro(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """UNIVERSAL: nada por MAC, nada por ordem de conexão, nenhum número mágico."""
    inst = _backend_sem_hardware()
    chaves = [f"AA:BB:CC:00:00:{n:02d}" for n in range(1, 8)]

    criados = _connect_com_handles_falsos(inst, monkeypatch, chaves)

    assert len(criados) == 7
    for chave in chaves:
        assert criados[chave]._volumes_audio[1] == VOLUME_PADRAO_DO_SOM, chave


def test_o_controle_que_chega_numa_mesa_ja_online_tambem_nasce_em_cem(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Todo controle adotado nasce em 100%, inclusive o 2º numa mesa online."""
    inst = _backend_sem_hardware()

    _connect_com_handles_falsos(inst, monkeypatch, ["AA:BB:CC:00:00:01"])
    criados = _connect_com_handles_falsos(
        inst, monkeypatch, ["AA:BB:CC:00:00:01", "AA:BB:CC:00:00:02"]
    )

    assert criados["AA:BB:CC:00:00:02"]._volumes_audio[1] == VOLUME_PADRAO_DO_SOM


def test_a_adocao_nao_reescreve_handle_que_ja_estava_na_mesa(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Quem já está conectado NÃO tem o volume reescrito a cada tique de hotplug."""
    inst = _backend_sem_hardware()

    criados = _connect_com_handles_falsos(
        inst, monkeypatch, ["AA:BB:CC:00:00:01"]
    )
    handle = criados["AA:BB:CC:00:00:01"]
    inst._handles = {"AA:BB:CC:00:00:01": handle}  # type: ignore[dict-item]
    inst._primary_key = "AA:BB:CC:00:00:01"
    inst.set_speaker_volume(60)
    assert handle._volumes_audio[1] == 60

    _connect_com_handles_falsos(inst, monkeypatch, ["AA:BB:CC:00:00:01"])

    assert handle._volumes_audio[1] == 60, (
        "o tique de hotplug reescreveu o volume que ela tinha acabado de "
        "escolher — a adoção é do handle NOVO, não da mesa inteira"
    )


def test_o_pedido_explicito_vence_o_padrao_da_adocao() -> None:
    """Perfil, janela e linha de comando escrevem DEPOIS, e por cima."""
    inst, handle = _backend_com_um_handle()

    inst.assumir_volume_padrao_na_adocao("AA:BB:CC:00:00:01", handle)
    inst.set_speaker_volume(40)

    assert handle._volumes_audio[1] == 40
    assert inst.speaker_state_for() == {
        "volume": 40, "muted": False, "rota": ROTA_PADRAO_DO_SOM,
    }


def test_o_mudo_passa_a_funcionar_de_primeira_por_causa_da_adocao() -> None:
    """Efeito colateral BOM, e ele merece um teste: `speaker mute` deixa de ser recusado."""
    inst, handle = _backend_com_um_handle()

    inst.assumir_volume_padrao_na_adocao("AA:BB:CC:00:00:01", handle)

    assert inst.set_speaker_volume(muted=True) is True
    assert handle._volumes_audio[1] == 0
    assert inst.speaker_state_for() == {
        "volume": VOLUME_PADRAO_DO_SOM,
        "muted": True,
        "rota": ROTA_PADRAO_DO_SOM,
    }
    assert inst.set_speaker_volume(muted=False) is True
    assert handle._volumes_audio[1] == VOLUME_PADRAO_DO_SOM


def test_o_alto_falante_passa_a_aparecer_na_aba_status() -> None:
    """"Tudo chega na interface" — e aqui chega sem tocar em uma linha de `app/`."""
    inst, handle = _backend_com_um_handle()

    assert inst.speaker_state_for() is None, (
        "sanidade: é esta ausência que escondia o módulo da aba Status"
    )

    inst.assumir_volume_padrao_na_adocao("AA:BB:CC:00:00:01", handle)

    assert inst.speaker_state_for() == {
        "volume": VOLUME_PADRAO_DO_SOM,
        "muted": False,
        "rota": ROTA_PADRAO_DO_SOM,
    }
    assert inst.speaker_state_for()["rota"] == ROTA_PADRAO_DO_SOM, (
        "a aba Status sabe para onde o som está indo"
    )


def _handle_real_de_report() -> Any:
    """`_PinnedPyDualSense` sem device — só o estado que o builder lê."""
    from pydualsense.pydualsense import DSAudio, DSLight, DSTrigger

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
    h._speaker_volume_pref = None
    h._mic_mute_desejado = None
    h._mic_led_desejado = None
    h._raw_trigger_left = None
    h._raw_trigger_right = None
    return h


def test_o_report_carrega_os_cem_por_cento_com_o_bit_de_validacao_ligado() -> None:
    """O fio, e não só o estado: o byte sai no report E o firmware é autorizado a lê-lo."""
    inst = _backend_sem_hardware()
    handle = _handle_real_de_report()
    inst._handles = {"AA:BB:CC:00:00:01": handle}
    inst._primary_key = "AA:BB:CC:00:00:01"

    inst.assumir_volume_padrao_na_adocao("AA:BB:CC:00:00:01", handle)
    common = handle._build_common(rumble_asserted=False)

    assert common[4] == VOLUME_PADRAO_DO_SOM, "fone"
    assert common[5] == VOLUME_PADRAO_DO_SOM, "alto-falante"
    assert common[0] & 0x10, "o bit de validação do fone"
    assert common[0] & 0x20, "o bit de validação do alto-falante"
    assert common[0] & 0x40 == 0, "o microfone continua do kernel"
    assert common[0] & 0x80, "a rota tem dono e o firmware pode lê-la"
    assert (common[7] & 0x30) >> 4 == ROTA_PADRAO_DO_SOM, "«Sons do jogo»"


def test_devolver_a_posse_nao_emudece_o_controle() -> None:
    """O PREÇO da posse, escrito e travado: `speaker release` devolve o CONTROLE.

    Depois da devolução os bits de validação caem e os quatro bytes saem
    zerados — mas byte com bit apagado é byte ignorado, e o firmware CONSERVA
    o último valor que mandamos, isto é, os 100%. Quem devolve a posse fica
    com o som ligado, não com o silêncio de antes desta cura.

    É por isso que a irreversibilidade que o usuário aceitou é menor do que parece:
    o que não volta é o valor que o firmware tinha ANTES de nós, e esse valor
    ninguém nunca soube — o DualSense não devolve o volume, não há report de
    entrada nem feature que o leia.

    MORDIDA: fazer o `release_audio_volumes` zerar os bytes MANTENDO os bits
    ligados — aí a devolução emudeceria o controle, que é o oposto do que o usuário
    pediu.
    """
    inst = _backend_sem_hardware()
    handle = _handle_real_de_report()
    inst._handles = {"AA:BB:CC:00:00:01": handle}
    inst._primary_key = "AA:BB:CC:00:00:01"

    inst.assumir_volume_padrao_na_adocao("AA:BB:CC:00:00:01", handle)
    assert inst.release_speaker_volume() is True

    common = handle._build_common(rumble_asserted=False)
    assert common[0] & rep.VALID_FLAG0_AUDIO_MASK == 0, (
        "sem posse, nenhum byte de áudio é autorizado — o firmware conserva "
        "os 100% que já recebeu"
    )
    assert inst.speaker_state_for() is None

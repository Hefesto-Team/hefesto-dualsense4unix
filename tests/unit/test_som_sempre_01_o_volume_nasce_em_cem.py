"""SOM-SEMPRE-01 — o volume nasce em 100%, em todo controle, sem ninguém pedir.

**A medição que é o alicerce disto**, feita na bancada dela na madrugada de
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

A decisão dela, textual (16/08/2026, 00h): *"precisamos setar o som sempre em
todos os controles no 100% e garantir que sempre fique acordado e ligar isso a
interface na aba de status (config default)."*

O que estes testes travam:

1. a adoção de QUALQUER controle toma a posse e escreve 100%;
2. o "100%" é o da régua ÚNICA — o mesmo número que a barra da aba Status e o
   `speaker volume 100` da linha de comando produzem;
3. o microfone e a rota continuam SEM DONO (só o que sai do controle é nosso);
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
        # omitido (None) NÃO vira dono.
        for pos, valor in enumerate((headphone, speaker, microphone, audio_path)):
            if valor is not None:
                self._volumes_audio[pos] = int(valor)
        if preamp is not None:
            self._preamp_audio = int(preamp)


def _backend_sem_hardware() -> PyDualSenseController:
    """`PyDualSenseController` real, sem tocar em aparelho nenhum.

    Real de propósito: o que se afere é o caminho de adoção que roda na
    máquina dela, e um dublê de backend provaria apenas que a linha foi
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


# ---------------------------------------------------------------------------
# 1. a adoção escreve, e escreve nos bytes certos
# ---------------------------------------------------------------------------


def test_a_adocao_toma_a_posse_e_poe_o_som_em_cem_por_cento() -> None:
    """Sem clique nenhum, o controle adotado já sai com volume 100%.

    Este é o coração da cura: antes dela, um controle recém-plugado ficava com
    `_volumes_audio` em `[None, None, None, None]` até alguém abrir a janela e
    mexer num controle deslizante — e, enquanto isso, o alto-falante ficava
    mudo (ensaio `sfx-cabo-sem-posse`, o "nenhum" dela).

    MORDIDA: apagar a chamada a `_escrever_volume_no_handle` de
    `assumir_volume_padrao_na_adocao`.
    """
    inst, handle = _backend_com_um_handle()

    assert handle._volumes_audio == [None, None, None, None], (
        "sanidade: o handle nasce sem dono, que é o estado que emudecia"
    )

    assert inst.assumir_volume_padrao_na_adocao("AA:BB:CC:00:00:01", handle) is True

    assert handle._volumes_audio[1] == VOLUME_PADRAO_DO_SOM
    assert handle._speaker_volume_pref == VOLUME_PADRAO_DO_SOM


def test_o_fone_vai_junto_porque_ele_manda_por_cima_da_rota() -> None:
    """Fone e alto-falante recebem o MESMO valor, e isso é medição, não simetria.

    Ensaio `sfx-o-fone-manda-por-cima` (15/08, par com/sem completo): com a
    MESMA rota e o MESMO canal, o som sai no fone quando há fone e no
    alto-falante quando não há. Se a cura pusesse só o alto-falante em 100% e
    deixasse o fone em zero, ela silenciaria exatamente quem plugasse um
    headset — o caso que o produto mais promete atender.

    MORDIDA: passar `headphone=None` na escrita.
    """
    inst, handle = _backend_com_um_handle()

    inst.assumir_volume_padrao_na_adocao("AA:BB:CC:00:00:01", handle)

    assert handle._volumes_audio[0] == VOLUME_PADRAO_DO_SOM
    assert handle._volumes_audio[0] == handle._volumes_audio[1]


def test_o_microfone_e_a_rota_continuam_sem_dono_na_adocao() -> None:
    """A posse é POR BYTE, e a adoção só toma os dois que ela precisa.

    `common[6]` é o volume do microfone, cujo dono no Linux é o kernel
    (AUDIO-OWNER-01); `common[7]` carrega a rota de saída nos bits 4-5 **e o
    caminho do microfone no resto**, e escrevê-lo pela metade já matou o
    microfone do controle uma vez (regressão medida em 02/08, SOM-CANAL-01).
    "O som em 100%" não autoriza tocar em nenhum dos dois.

    MORDIDA: passar `rota=0` ou `microphone=...` na chamada da adoção — a
    segunda apaga o `FORCE_INTERNAL_MIC` e o microfone do controle para de
    captar, em silêncio.
    """
    inst, handle = _backend_com_um_handle()

    inst.assumir_volume_padrao_na_adocao("AA:BB:CC:00:00:01", handle)

    assert handle._volumes_audio[2] is None, "o volume do microfone é do kernel"
    assert handle._volumes_audio[3] is None, "a rota carrega o caminho do mic"


def test_o_pre_amplificador_entra_na_mesma_posse() -> None:
    """Volume sem pré-amp é um de três botões — e foi o que deixou 60% do curso inerte.

    SOM-ROTA-01 já tinha estabelecido que quem assume o volume assume o
    `common[37]`. A adoção usa a MESMA porta, então herda a regra de graça — e
    este teste é o que impede alguém de "simplificar" a adoção escrevendo
    direto no `set_audio_volumes` sem o pré-amp.

    MORDIDA: tirar `preamp=` da escrita compartilhada.
    """
    inst, handle = _backend_com_um_handle()

    inst.assumir_volume_padrao_na_adocao("AA:BB:CC:00:00:01", handle)

    assert handle._preamp_audio == rep.SP_PREAMP_GAIN_PADRAO


# ---------------------------------------------------------------------------
# 2. o número: 100% é o da régua única, não um literal
# ---------------------------------------------------------------------------


def test_o_cem_por_cento_e_o_da_regua_unica_e_relê_cem_na_tela() -> None:
    """O default sai de `speaker_scale`, e volta como 100% na aba Status.

    Se ele fosse um literal, a tela nasceria mostrando um número que ninguém
    conseguiria reproduzir arrastando o controle deslizante até o fim — duas
    contas para a mesma grandeza, que é a classe de defeito que a SOM-03 já
    pagou uma vez.

    MORDIDA: trocar `volume_do_percentual(100)` por `255` (ou por `0x64`).
    """
    assert volume_do_percentual(100) == VOLUME_PADRAO_DO_SOM
    assert percentual_do_volume(VOLUME_PADRAO_DO_SOM) == 100


def test_o_default_nao_e_255_nem_0x64_e_a_curva_medida_e_a_razao() -> None:
    """102, e não 255: de 102 para cima a curva medida em 01/08 não muda mais.

        51 -> 35    64 -> 172    76 -> 687
       102 -> 8759  128 -> 8488  255 -> 8793

    Escrever 255 é escrever fora da faixa que o firmware usa na prática (a
    documentação do report 0x02 anota `0x3D..0x64`) para obter exatamente o
    mesmo som. E 0x64 — o que o `hid-playstation` escreve — fica dois passos
    abaixo da saturação medida AQUI e leria 97% na tela, não 100%.

    MORDIDA: qualquer um dos dois outros números reprova aqui.
    """
    assert VOLUME_PADRAO_DO_SOM == 102
    assert VOLUME_PADRAO_DO_SOM != rep.TETO_SPEAKER_VOLUME
    assert VOLUME_PADRAO_DO_SOM <= rep.TETO_HEADPHONE_VOLUME, (
        "o fone recebe o mesmo valor e satura em 0x7F — acima disso o clamp "
        "por campo faria fone e alto-falante divergirem em silêncio"
    )


# ---------------------------------------------------------------------------
# 3. a MORDIDA principal: o caminho de adoção do backend
# ---------------------------------------------------------------------------


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
    # Fora do escopo desta cura, e caros/ruidosos sem aparelho.
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
    """UNIVERSAL: nada por MAC, nada por ordem de conexão, nenhum número mágico.

    MORDIDA: escrever só no primário (`self._primary_key`) em vez de em cada
    handle novo — o P1 soaria e os outros seis ficariam mudos, que é o defeito
    de multi-controle mais difícil de perceber (ninguém desconfia do silêncio
    do controle do outro).
    """
    inst = _backend_sem_hardware()
    chaves = [f"AA:BB:CC:00:00:{n:02d}" for n in range(1, 8)]

    criados = _connect_com_handles_falsos(inst, monkeypatch, chaves)

    assert len(criados) == 7
    for chave in chaves:
        assert criados[chave]._volumes_audio[1] == VOLUME_PADRAO_DO_SOM, chave


def test_o_controle_que_chega_numa_mesa_ja_online_tambem_nasce_em_cem(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O caso que o gancho de perfil NÃO cobre, e por isso a cura mora aqui.

    `reapply_speaker_after_connect` só corre na TRANSIÇÃO offline→online do
    daemon (e só quando o perfil ativo tem seção `speaker`). Um segundo
    controle plugado com o primeiro já conectado não produz transição nenhuma
    — e era exatamente esse controle que nascia mudo.

    MORDIDA: mover a escrita para o gancho de transição do daemon; o segundo
    handle deste teste volta a nascer sem dono.
    """
    inst = _backend_sem_hardware()

    _connect_com_handles_falsos(inst, monkeypatch, ["AA:BB:CC:00:00:01"])
    criados = _connect_com_handles_falsos(
        inst, monkeypatch, ["AA:BB:CC:00:00:01", "AA:BB:CC:00:00:02"]
    )

    assert criados["AA:BB:CC:00:00:02"]._volumes_audio[1] == VOLUME_PADRAO_DO_SOM


def test_a_adocao_nao_reescreve_handle_que_ja_estava_na_mesa(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Quem já está conectado NÃO tem o volume reescrito a cada tique de hotplug.

    O `connect()` é o tique de reconciliação e roda a cada poucos segundos. Se
    a adoção escrevesse em TODO handle, ela desfaria a cada tique o volume que
    ela acabou de escolher na janela — a versão áudio do defeito que o
    keepalive de LED já causou nesta casa.

    MORDIDA: trocar o laço de `new_handles` por um laço de `self._handles`.
    """
    inst = _backend_sem_hardware()

    criados = _connect_com_handles_falsos(
        inst, monkeypatch, ["AA:BB:CC:00:00:01"]
    )
    handle = criados["AA:BB:CC:00:00:01"]
    # Ela baixa o volume na janela, com o controle já na mesa.
    inst._handles = {"AA:BB:CC:00:00:01": handle}  # type: ignore[dict-item]
    inst._primary_key = "AA:BB:CC:00:00:01"
    inst.set_speaker_volume(60)
    assert handle._volumes_audio[1] == 60

    _connect_com_handles_falsos(inst, monkeypatch, ["AA:BB:CC:00:00:01"])

    assert handle._volumes_audio[1] == 60, (
        "o tique de hotplug reescreveu o volume que ela tinha acabado de "
        "escolher — a adoção é do handle NOVO, não da mesa inteira"
    )


# ---------------------------------------------------------------------------
# 4. quem tem opinião continua vencendo
# ---------------------------------------------------------------------------


def test_o_pedido_explicito_vence_o_padrao_da_adocao() -> None:
    """Perfil, janela e linha de comando escrevem DEPOIS, e por cima.

    A adoção é um piso, não uma trava: ela existe para que o silêncio deixe de
    ser o default, e não para tirar dela a escolha. O `speaker volume 40`
    continua valendo 40.

    MORDIDA: fazer a adoção grampear o volume (recusar escrita menor que o
    padrão) — este teste reprova.
    """
    inst, handle = _backend_com_um_handle()

    inst.assumir_volume_padrao_na_adocao("AA:BB:CC:00:00:01", handle)
    inst.set_speaker_volume(40)

    assert handle._volumes_audio[1] == 40
    assert inst.speaker_state_for() == {"volume": 40, "muted": False}


def test_o_mudo_passa_a_funcionar_de_primeira_por_causa_da_adocao() -> None:
    """Efeito colateral BOM, e ele merece um teste: `speaker mute` deixa de ser recusado.

    A guarda da SOM-02 recusa `muted` sem volume conhecido — mudo como
    primeira escrita trancaria o controle em `{'volume': 0, 'muted': True}`
    sem nada a restaurar. Com a adoção, todo controle já tem volume conhecido,
    então o botão de mudo funciona desde o primeiro clique.

    MORDIDA: a mesma da adoção — sem ela, `set_speaker_volume(muted=True)`
    devolve False e não muta nada.
    """
    inst, handle = _backend_com_um_handle()

    inst.assumir_volume_padrao_na_adocao("AA:BB:CC:00:00:01", handle)

    assert inst.set_speaker_volume(muted=True) is True
    assert handle._volumes_audio[1] == 0
    assert inst.speaker_state_for() == {
        "volume": VOLUME_PADRAO_DO_SOM,
        "muted": True,
    }
    assert inst.set_speaker_volume(muted=False) is True
    assert handle._volumes_audio[1] == VOLUME_PADRAO_DO_SOM


# ---------------------------------------------------------------------------
# 5. a interface: a aba Status deixa de esconder o módulo
# ---------------------------------------------------------------------------


def test_o_alto_falante_passa_a_aparecer_na_aba_status() -> None:
    """"Tudo chega na interface" — e aqui chega sem tocar em uma linha de `app/`.

    `speaker_state_for` devolve `None` enquanto ninguém escreveu o volume, e
    `app/widgets/controller_card.speaker_do_entry` faz o módulo inteiro SUMIR
    quando a chave falta. Com a adoção, todo controle conectado publica o
    bloco `speaker` — o card mostra a barra em 100% e o botão de mudo, que é a
    "config default" que ela pediu na aba de status.

    MORDIDA: a da adoção. Sem ela o payload volta a não ter a chave `speaker`
    e o módulo some da tela de novo.
    """
    inst, handle = _backend_com_um_handle()

    assert inst.speaker_state_for() is None, (
        "sanidade: é esta ausência que escondia o módulo da aba Status"
    )

    inst.assumir_volume_padrao_na_adocao("AA:BB:CC:00:00:01", handle)

    assert inst.speaker_state_for() == {
        "volume": VOLUME_PADRAO_DO_SOM,
        "muted": False,
    }
    assert "rota" not in (inst.speaker_state_for() or {}), (
        "a rota continua sendo 'não dá para saber' — a adoção não a escreveu"
    )


# ---------------------------------------------------------------------------
# 6. o preço, e o que a devolução da posse faz de verdade
# ---------------------------------------------------------------------------


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
    """O fio, e não só o estado: o byte sai no report E o firmware é autorizado a lê-lo.

    Byte escrito com o bit de validação apagado é byte que o firmware IGNORA —
    o pior sintoma possível, porque o log diz "escrito" e o som não sai.

    MORDIDA: apagar o `flag0 |= bit` de `_build_common`.
    """
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
    assert common[0] & 0x80 == 0, "a rota continua sem dono"


def test_devolver_a_posse_nao_emudece_o_controle() -> None:
    """O PREÇO da posse, escrito e travado: `speaker release` devolve o CONTROLE.

    Depois da devolução os bits de validação caem e os quatro bytes saem
    zerados — mas byte com bit apagado é byte ignorado, e o firmware CONSERVA
    o último valor que mandamos, isto é, os 100%. Quem devolve a posse fica
    com o som ligado, não com o silêncio de antes desta cura.

    É por isso que a irreversibilidade que ela aceitou é menor do que parece:
    o que não volta é o valor que o firmware tinha ANTES de nós, e esse valor
    ninguém nunca soube — o DualSense não devolve o volume, não há report de
    entrada nem feature que o leia.

    MORDIDA: fazer o `release_audio_volumes` zerar os bytes MANTENDO os bits
    ligados — aí a devolução emudeceria o controle, que é o oposto do que ela
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

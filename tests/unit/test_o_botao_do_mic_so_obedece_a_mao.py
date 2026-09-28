"""O botão do microfone só obedece à mão — O-BOTAO-DO-MIC-SO-OBEDECE-A-MAO-01.

O DEFEITO, medido na sessão dela de 28/09/2026 (00h15 a 00h52)
--------------------------------------------------------------
Três bordas do botão do microfone do branco que ela não deu (00:18:40,
00:22:15 e 00:22:17). Ela: *«eu não apertei o botão do Mic»*. Cada uma
elegeu o microfone da máquina e **gravou o perfil dela**.

A causa estava escrita no leitor: a borda era contada pelo bit `MIC_MUTE` de
`status[1]` — a CONSEQUÊNCIA de um aperto —, e esse bit muda com QUALQUER um
que escreva o mudo no firmware. Medido nesta árvore, com o handle de verdade e
reports de verdade pelo `_consumir_report` (o leitor de antes):

    bit de estado virando com o botão parado ........ 1 borda (a mão deu 0)
    virando e desvirando ............................ 2 bordas (a mão deu 0)
    aperto com o bit parado (posse nossa) ........... 0 bordas (a mão deu 1)
    toque de 60 ms com o bit parado ................. 0 bordas (a mão deu 1)
    marca velha na fila do eco e dois apertos ....... 1 borda  (a mão deu 2)

A CURA: a borda é o BOTÃO (`buttons[2]` bit 2, o dedo dela), no mesmo report
que já passava pela porta que recusa o áudio do rádio; o bit de estado só diz
o que o firmware segurava no instante do aperto — e o aperto pede o contrário.

E A MÃO DEVOLVE A POSSE DO MUDO. Na mesma sessão o microfone do branco deu
zero absoluto por 40 s: o `state_full` mostra `mic_mudo_desejado=True` a
sessão inteira — o Hefesto segurava o mudo desde o «calado» do perfil —, e o
ato disparado pela borda fantasma viu o bit momentaneamente livre e não
escreveu nada. O próximo report nosso calou o controle de novo. Um aperto
de verdade abre a mesma porta (o kernel vira o bit antes de o ato ler), e por
isso o aperto solta a posse do mudo DAQUELE controle, no handle e no mapa.

As réguas valem nos dois transportes e para os quatro jogadores.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from hefesto_dualsense4unix.core import backend_pydualsense as bp
from hefesto_dualsense4unix.core import physical_report_reader as prr
from hefesto_dualsense4unix.core.events import EventBus, EventTopic
from hefesto_dualsense4unix.integrations.dualsense_bt_audio import STATUS_MIC_MUDO

#: O leitor do cabo entrega ~250 reports/s; o do rádio, menos. O relógio aqui
#: anda um report a cada leitura, e o cabo é o caso mais denso.
_PERIODO_S = 1.0 / 250.0

MUDO = STATUS_MIC_MUDO
LIVRE = 0x00

#: Os quatro da mesa, na faixa forjada da suíte.
_QUATRO = ("aabbcc000001", "aabbcc000002", "aabbcc000003", "aabbcc000004")


@pytest.fixture(autouse=True)
def _relogio(monkeypatch: pytest.MonkeyPatch) -> None:
    """O tempo da borda anda um report por leitura — pelo ponto de injeção."""
    marca = {"agora": 0.0}

    def _andar() -> float:
        marca["agora"] += _PERIODO_S
        return marca["agora"]

    monkeypatch.setattr(bp, "_relogio_da_borda", _andar)


class _Handle(bp._PinnedPyDualSense):
    """O handle de produção, sem aparelho.

    Nasce por `__new__` como os outros dezesseis dublês da suíte, com o estado
    da borda zerado pelo DONO ÚNICO (`zerar_estado_da_borda_do_mic`). Só o
    `readInput` da pydualsense é trocado: ele não participa da borda, e sem
    aparelho não há `DSState` para ele escrever. O caminho sob prova — a porta
    `_consumir_report`, o `_captura_status_audio` e o `_registrar_borda_do_mic`
    — é o de produção.
    """

    def __new__(cls) -> Any:
        return object.__new__(cls)

    def __init__(self) -> None:
        self._audio_status = None
        self._mic_mute_desejado = None
        self.zerar_estado_da_borda_do_mic()

    def readInput(self, in_report: Any) -> None:  # noqa: N802 - nome da pydualsense
        del in_report


def _report(transporte: str, *, status: int, botao: bool) -> bytes:
    """Report de ESTADO do aparelho: `0x01` do cabo ou `0x31` do rádio com CRC."""
    if transporte == "cabo":
        corpo = bytearray(64)
        corpo[0] = prr.INPUT_REPORT_USB
        base = 1
    else:
        corpo = bytearray(prr.INPUT_REPORT_BT_SIZE)
        corpo[0] = prr.INPUT_REPORT_BT
        base = 2
    corpo[base + prr.JACK_STATUS_OFFSET] = status
    if botao:
        corpo[base + prr.BUTTONS2_OFFSET] |= prr.MIC_BUTTON_BIT
    if transporte == "radio":
        crc = prr.bt_crc32(bytes(corpo[:-4]), seed=prr.BT_INPUT_CRC_SEED)
        corpo[-4:] = crc.to_bytes(4, "little")
    return bytes(corpo)


def _segurar(
    h: Any, transporte: str, *, status: int, botao: bool = False, s: float = 1.0
) -> None:
    """O mesmo estado por `s` segundos de reports."""
    for _ in range(max(1, round(s / _PERIODO_S))):
        h._consumir_report(_report(transporte, status=status, botao=botao))


def _apertar(h: Any, transporte: str, *, antes: int, depois: int | None = None) -> None:
    """Um aperto: o dedo desce, o kernel (talvez) vira o bit, o dedo sobe.

    `depois` é o que o firmware passa a segurar depois do aperto — o kernel
    vira o bit quando é dono do campo; com a posse nossa, o bit fica.
    """
    fim = antes if depois is None else depois
    _segurar(h, transporte, status=antes, botao=True, s=0.02)
    _segurar(h, transporte, status=fim, botao=True, s=0.06)
    _segurar(h, transporte, status=fim, botao=False, s=1.0)


class _LockFalso:
    def __enter__(self) -> None:
        return None

    def __exit__(self, *_: Any) -> None:
        return None


def _backend(handles: dict[str, Any]) -> Any:
    """O controlador de produção, sem aparelho: os handles, o lock e o mapa."""
    b = bp.PyDualSenseController.__new__(bp.PyDualSenseController)
    b._handles = handles
    b._io_lock = _LockFalso()
    b._mic_mute_by_uniq = {}
    return b


def _seq(backend: Any, uniq: str) -> int:
    return int(backend.bordas_do_mic()[uniq][0])


_TRANSPORTES = pytest.mark.parametrize("transporte", ["cabo", "radio"])


# ---------------------------------------------------------------------------
# 0. O bit do botão é UM número, nos três lugares que o conhecem
# ---------------------------------------------------------------------------


def test_o_bit_do_botao_e_o_do_kernel_e_o_do_vpad() -> None:
    """O leitor, o vpad e o `hid-playstation` falam do MESMO bit de `buttons[2]`.

    O vpad escreve `mic_btn` no report que o jogo lê; o leitor o conta como o
    dedo dela; o kernel o consome. Três cópias digitadas separadamente é a
    família de defeito desta casa — aqui elas ficam presas umas às outras.
    """
    import re
    from pathlib import Path

    from hefesto_dualsense4unix.integrations import uhid_gamepad

    assert prr.MIC_BUTTON_BIT == uhid_gamepad._BUTTONS2_BITS["mic_btn"]
    assert prr.BUTTONS2_OFFSET == uhid_gamepad._BUTTONS2_OFFSET
    fonte = (
        Path(__file__).resolve().parents[2]
        / "assets/dkms/hid-playstation/hid-playstation.c"
    ).read_text(encoding="utf-8")
    achado = re.search(r"#define DS_BUTTONS2_MIC_MUTE\s+BIT\((\d+)\)", fonte)
    assert achado is not None
    assert prr.MIC_BUTTON_BIT == 1 << int(achado.group(1))


# ---------------------------------------------------------------------------
# 1. O toque fantasma: o bit de estado mudando não é a mão
# ---------------------------------------------------------------------------


@_TRANSPORTES
def test_o_bit_de_estado_virando_com_o_botao_parado_nao_e_borda(transporte: str) -> None:
    """A régua da sprint: o LED/o mudo mudando e o botão parado -> zero bordas.

    É o desenho das três bordas fantasma do branco: o bit `MIC_MUTE` virou
    (a escrita de alguém no mudo do firmware), sustentou, e o leitor de antes
    contou uma borda por virada.

    MORDIDA: volte `_registrar_borda_do_mic` a contar a virada do bit de
    estado e esta régua reprova com seis bordas que ninguém deu.
    """
    h = _Handle()
    backend = _backend({_QUATRO[0]: h})
    _segurar(h, transporte, status=LIVRE)
    for _ in range(3):
        _segurar(h, transporte, status=MUDO)
        _segurar(h, transporte, status=LIVRE)
    assert _seq(backend, _QUATRO[0]) == 0, (
        "o bit de estado do microfone virou seis vezes com o botão parado, e "
        "virou gesto dela — é o toque fantasma que gravou o perfil"
    )


@_TRANSPORTES
def test_o_aperto_e_uma_borda_com_ou_sem_o_bit_virar(transporte: str) -> None:
    """Com o botão apertado -> uma. Com o kernel virando o bit, ainda UMA.

    O caso do meio é o que o leitor de antes perdia: com a posse do mudo
    nossa, o kernel escreve o que ele acredita e o bit pode ficar onde estava
    — o aperto dela sumia calado.
    """
    h = _Handle()
    backend = _backend({_QUATRO[0]: h})
    _segurar(h, transporte, status=LIVRE)

    _apertar(h, transporte, antes=LIVRE, depois=MUDO)
    assert _seq(backend, _QUATRO[0]) == 1, "o aperto com o bit virando é UMA borda"

    _apertar(h, transporte, antes=MUDO)
    assert _seq(backend, _QUATRO[0]) == 2, "o aperto com o bit parado sumiu"


@_TRANSPORTES
def test_o_toque_curto_conta(transporte: str) -> None:
    """Um toque de 20 ms: o dedo não trava nada, e ainda assim é o dedo."""
    h = _Handle()
    backend = _backend({_QUATRO[0]: h})
    _segurar(h, transporte, status=LIVRE)
    _segurar(h, transporte, status=LIVRE, botao=True, s=0.02)
    _segurar(h, transporte, status=LIVRE)
    assert _seq(backend, _QUATRO[0]) == 1


@_TRANSPORTES
def test_o_aperto_pede_o_contrario_do_que_o_firmware_segurava(transporte: str) -> None:
    """O `mudo` publicado é o que o aperto PEDE: o contrário do bit no instante.

    É o que a tradução de `_o_que_a_borda_pede` (`hotkey.py`) sempre recebeu
    — o valor do bit DEPOIS da virada do kernel —, agora sem depender de o
    kernel e o firmware estarem em fase.
    """
    h = _Handle()
    backend = _backend({_QUATRO[0]: h})
    _segurar(h, transporte, status=MUDO)
    _apertar(h, transporte, antes=MUDO)
    assert backend.bordas_do_mic()[_QUATRO[0]][1] is False, "mudo -> o aperto pede LIGAR"
    _apertar(h, transporte, antes=LIVRE)
    assert backend.bordas_do_mic()[_QUATRO[0]][1] is True, "livre -> o aperto pede CALAR"


@_TRANSPORTES
def test_o_eco_da_nossa_escrita_nao_e_borda(transporte: str) -> None:
    """O daemon escreve o mudo e o firmware ecoa: zero bordas, sem fila de marcas.

    E o caso que a fila de marcas errava: uma escrita que não ecoou (o bit já
    estava lá) deixava a marca viva, e ela engolia o PRÓXIMO aperto dela.
    """
    h = _Handle()
    backend = _backend({_QUATRO[0]: h})
    _segurar(h, transporte, status=LIVRE)
    h.set_microphone_mute(True)
    _segurar(h, transporte, status=MUDO)
    assert _seq(backend, _QUATRO[0]) == 0, "o eco da nossa escrita virou gesto dela"

    h.set_microphone_mute(True)  # o bit já está mudo: nada ecoa
    _segurar(h, transporte, status=MUDO)
    _apertar(h, transporte, antes=MUDO, depois=LIVRE)
    _apertar(h, transporte, antes=LIVRE, depois=MUDO)
    assert _seq(backend, _QUATRO[0]) == 2, "um aperto dela foi engolido como eco"


def test_o_quadro_de_audio_do_radio_nao_aperta_o_botao() -> None:
    """Com o microfone no ar, o rádio manda Opus no mesmo `0x31`: não é dedo.

    O bit do botão cai dentro do Opus (PS-PRESO-01); a porta `_consumir_report`
    recusa o quadro antes de alguém olhar o botão.
    """
    h = _Handle()
    backend = _backend({_QUATRO[0]: h})
    _segurar(h, "radio", status=LIVRE)
    cru = bytearray(_report("radio", status=MUDO, botao=True))
    cru[1] |= prr.INPUT_FLAG_AUDIO
    for _ in range(500):
        h._consumir_report(bytes(cru))
    _segurar(h, "radio", status=LIVRE)
    assert _seq(backend, _QUATRO[0]) == 0


@_TRANSPORTES
def test_o_botao_segurado_na_conexao_nao_e_aperto(transporte: str) -> None:
    """O primeiro report só é adotado: o micBtn da reconexão não vira gesto."""
    h = _Handle()
    backend = _backend({_QUATRO[0]: h})
    _segurar(h, transporte, status=LIVRE, botao=True, s=0.2)
    _segurar(h, transporte, status=LIVRE)
    assert _seq(backend, _QUATRO[0]) == 0
    _apertar(h, transporte, antes=LIVRE)
    assert _seq(backend, _QUATRO[0]) == 1


# ---------------------------------------------------------------------------
# 2. A mão devolve a posse do mudo (o microfone do branco em zero)
# ---------------------------------------------------------------------------


@_TRANSPORTES
def test_o_aperto_solta_a_posse_do_mudo_no_handle_e_no_mapa(transporte: str) -> None:
    """O «calado» do perfil deixa a posse nossa; o dedo dela a devolve ao kernel.

    Sem isto, o report seguinte do Hefesto (a luz que muda, basta) reafirma
    o mudo velho por cima do que o kernel fez com o aperto — foi assim que o
    branco ficou em zero com o ato dizendo «ligado».

    MORDIDA: tire a devolução de `_registrar_borda_do_mic` e o handle segue
    mandando mudo; tire a de `bordas_do_mic` e o mapa rependura o mudo velho
    na próxima reconexão.
    """
    h = _Handle()
    backend = _backend({_QUATRO[1]: h})
    _segurar(h, transporte, status=MUDO)
    assert backend.set_microphone_mute(True, uniq=_QUATRO[1]) is True
    assert backend.microphone_mute_for(_QUATRO[1]) is True

    _apertar(h, transporte, antes=MUDO, depois=LIVRE)

    assert h._mic_mute_desejado is None, "o handle segue reafirmando o mudo velho"
    assert _seq(backend, _QUATRO[1]) == 1
    assert _QUATRO[1] not in backend._mic_mute_by_uniq, (
        "o mapa segue dono do mudo: a próxima reconexão o rependura"
    )
    assert backend.microphone_mute_for(_QUATRO[1]) is None


@_TRANSPORTES
def test_o_bit_virando_sem_mao_nao_solta_a_posse(transporte: str) -> None:
    """A devolução é da MÃO: o bit mudando sozinho não tira a posse de ninguém."""
    h = _Handle()
    backend = _backend({_QUATRO[1]: h})
    _segurar(h, transporte, status=MUDO)
    backend.set_microphone_mute(True, uniq=_QUATRO[1])
    _segurar(h, transporte, status=LIVRE)
    _segurar(h, transporte, status=MUDO)
    backend.bordas_do_mic()
    assert h._mic_mute_desejado is True
    assert backend.microphone_mute_for(_QUATRO[1]) is True


# ---------------------------------------------------------------------------
# 3. Nunca só o P1: os quatro, nos dois transportes
# ---------------------------------------------------------------------------


def test_a_mesa_de_quatro_so_conta_o_dedo_de_quem_apertou() -> None:
    """P1 e P3 no cabo, P2 e P4 no rádio. O bit vira nos quatro; só o P3 aperta."""
    transportes = dict(zip(_QUATRO, ("cabo", "radio", "cabo", "radio"), strict=True))
    handles = {u: _Handle() for u in _QUATRO}
    backend = _backend(handles)
    for u, h in handles.items():
        _segurar(h, transportes[u], status=LIVRE)
    for u, h in handles.items():
        _segurar(h, transportes[u], status=MUDO)
        _segurar(h, transportes[u], status=LIVRE)
    p3 = _QUATRO[2]
    _apertar(handles[p3], transportes[p3], antes=LIVRE, depois=MUDO)

    bordas = backend.bordas_do_mic()
    assert {u: bordas[u][0] for u in _QUATRO} == {
        _QUATRO[0]: 0,
        _QUATRO[1]: 0,
        _QUATRO[2]: 1,
        _QUATRO[3]: 0,
    }


# ---------------------------------------------------------------------------
# 4. No tempo, até a eleição: a borda fantasma não chega ao ato nem ao perfil
# ---------------------------------------------------------------------------


class _Daemon:
    """O mínimo que o laço das bordas lê do daemon — com o `EventBus` real."""

    def __init__(self, controller: Any) -> None:
        self.bus = EventBus()
        self.controller = controller
        self._parando = False

    def _is_stopping(self) -> bool:
        return self._parando


@pytest.mark.asyncio
async def test_no_tempo_o_fantasma_nao_chega_a_eleicao(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Três segundos de luz/mudo virando nos quatro, e depois UM aperto do P2.

    O laço de produção (`mic_da_mesa_loop`) sobre o controlador de produção:
    cada `MIC_DA_MESA` é uma eleição e uma gravação no perfil dela
    (`hotkey.mic_button_loop` -> `ligar_o_microfone` -> `_o_disco_guarda_o_ato`).
    Zero publicações sem mão; uma, com o endereço dela, quando ela aperta.
    """
    from hefesto_dualsense4unix.daemon import lifecycle
    from hefesto_dualsense4unix.daemon.subsystems import mic_da_mesa

    monkeypatch.setattr(lifecycle, "INPUT_GRACE_SEC", 0.05)
    transportes = dict(zip(_QUATRO, ("radio", "cabo", "radio", "cabo"), strict=True))
    handles = {u: _Handle() for u in _QUATRO}
    backend = _backend(handles)
    daemon = _Daemon(backend)
    fila = daemon.bus.subscribe(EventTopic.MIC_DA_MESA)
    for u, h in handles.items():
        _segurar(h, transportes[u], status=LIVRE, s=0.1)

    tarefa = asyncio.create_task(mic_da_mesa.mic_da_mesa_loop(daemon))  # type: ignore[arg-type]
    try:
        await asyncio.sleep(0.2)
        for volta in range(12):
            for u, h in handles.items():
                _segurar(h, transportes[u], status=MUDO if volta % 2 else LIVRE, s=0.1)
            await asyncio.sleep(0.25)
        assert fila.qsize() == 0, "a luz e o mudo virando elegeram o microfone sozinhos"

        p2 = _QUATRO[1]
        _apertar(handles[p2], transportes[p2], antes=MUDO)
        for _ in range(10):
            await asyncio.sleep(0.05)
    finally:
        daemon._parando = True
        tarefa.cancel()
        with pytest.raises(asyncio.CancelledError):
            await tarefa

    assert fila.qsize() == 1
    evento = fila.get_nowait()
    assert evento["uniq"] == _QUATRO[1]
    assert evento["mudo"] is False, "o P2 estava mudo: o aperto pede ligar"

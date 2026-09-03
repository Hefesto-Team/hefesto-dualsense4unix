"""LUZ-DO-MIC-01 §2 — devolver a posse do `common[8]` REPINTA antes de soltar.

O defeito, medido no aparelho em 02/09/2026 com dois controles na mesa e o olho
dela: **devolver a posse deixa a luz presa no último valor que escrevemos.**
Palavra dela: *"ambos tão ligados. e ficaram."*

A causa está no contrato do kernel: o `hid-playstation` escreve
`mute_button_led = ds->mic_muted` **na borda do botão físico**, dentro de
`if (ds->update_mic_mute)` (`assets/dkms/hid-playstation/hid-playstation.c`
:1538-1540, armado em :1631-1640) — nunca em regime. Largar o byte com a luz
acesa (ou, sob a LUZ-DO-MIC, PISCANDO em `2`/`3`) deixa a mentira no plástico
até ela apertar o mudo.

**POR QUE ESTAS RÉGUAS CONTAM REPORTS ESCRITOS, E NÃO ESTADOS MONTADOS.** Esta
é a armadilha inteira desta peça, e ela dá VERDE sobre uma cura morta. O
`sendReport` amostra o estado desejado na PRÓPRIA thread e só escreve quando o
buffer muda; marcar o valor real e soltar em seguida colapsa nos dois, e o
valor real nunca sai pelo fio. Uma régua que chamasse `_build_common` à mão
veria o estado final correto — bit apagado, byte zerado — e passaria, porque
`_build_common` mostra o que se PEDIU, não o que se ENTREGOU. Por isso aqui o
handle tem um `device` de mentira que guarda cada `write`, e o que se afirma é
sobre os bytes que chegaram nele: quantos reports saíram, em que ordem, e com
que valor no `common[8]`.

A MORDIDA de cada régua está escrita no docstring dela, e a de todas é a mesma
raiz: tirar a chamada a `_repintar_antes_de_soltar` de
`PyDualSenseController.set_microphone_led`. Com ela arrancada, nenhum report sai
e as sete réguas de escrita reprovam — provado em 03/09/2026.
"""

from __future__ import annotations

import threading
from typing import Any

import pytest

from hefesto_dualsense4unix.core import ds_output_report as rep
from hefesto_dualsense4unix.core.backend_pydualsense import (
    PyDualSenseController,
    _PinnedPyDualSense,
)
from hefesto_dualsense4unix.integrations.dualsense_bt_audio import STATUS_MIC_MUDO

_A = "aabbcc000001"
_B = "aabbcc000002"

#: Onde o `common[0]` cai DENTRO do report que vai para o fio, por transporte.
#: USB (0x02): `[0]=id`, common em `[1..47]`. Rádio (0x31): `[0]=id`, `[1]=seq`,
#: `[2]=tag`, common em `[3..49]` — daí o "report[11] no rádio" para o
#: `common[8]`, que a linha `luz.led_microfone` do mapa já registrava.
_BASE_DO_COMMON = {"usb": 1, "bt": 3}


def _no_fio(relatorio: bytes, indice: int, transporte: str = "usb") -> int:
    """O `common[indice]` como ele saiu no report entregue."""
    return relatorio[_BASE_DO_COMMON[transporte] + indice]


class _DeviceFalso:
    """O fio. Guarda cada `write` — é ele que separa ENTREGUE de MONTADO."""

    def __init__(self) -> None:
        self.escritos: list[bytes] = []

    def write(self, dados: bytes | bytearray) -> int:
        self.escritos.append(bytes(dados))
        return len(dados)


class _LockFalso:
    def __enter__(self) -> None:
        return None

    def __exit__(self, *_: Any) -> None:
        return None


def _handle(*, mudo: bool | None, transporte: str = "usb") -> Any:
    """Handle REAL da casa (`_PinnedPyDualSense`) com um fio de mentira.

    Real de propósito: quem monta o report é o `prepareReport`/`_build_common`
    do produto, e quem o entrega é o `writeReport` do produto — inclusive o
    carimbo de `seq` e o CRC do rádio. Um dublê que só registrasse a chamada
    mediria a palavra, não o ato.

    `mudo=None` é o controle que ainda não entregou um report íntegro: o
    `_audio_status` nasce ausente e o `audio_status_for` devolve `None`.
    """
    from pydualsense.enums import ConnectionType
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
    h._mic_mute_desejado = None
    h._mic_led_desejado = None
    h._raw_trigger_left = None
    h._raw_trigger_right = None
    h._rumble_active = False
    h._rumble_stop_pending = False
    h._output_muted = False
    h.conType = ConnectionType.BT if transporte == "bt" else ConnectionType.USB
    h._write_lock = threading.Lock()
    h._bt_seq = 0
    h.device = _DeviceFalso()
    h._audio_status = None if mudo is None else (STATUS_MIC_MUDO if mudo else 0x00)
    return h


def _backend(handles: dict[str, Any]) -> Any:
    from hefesto_dualsense4unix.core.backend_pydualsense import _DesiredOutput

    ctrl = PyDualSenseController.__new__(PyDualSenseController)
    ctrl._handles = dict(handles)
    ctrl._io_lock = _LockFalso()
    ctrl._primary_key = next(iter(handles))
    ctrl._output_target_key = None
    ctrl._desired_default = _DesiredOutput()
    ctrl._desired_by_uniq = {}
    ctrl._desired_owner_by_uniq = {}
    return ctrl


def _led_entregue(handle: Any, transporte: str = "usb") -> list[tuple[int, int]]:
    """`[(flag1, common[8])]` de cada report que CHEGOU ao fio."""
    return [
        (_no_fio(relatorio, 1, transporte), _no_fio(relatorio, 8, transporte))
        for relatorio in handle.device.escritos
    ]


# ---------------------------------------------------------------------------
# 1. O report do meio SAI, e carrega o mudo de fato
# ---------------------------------------------------------------------------


def test_a_devolucao_entrega_um_report_com_o_mudo_real_antes_de_soltar() -> None:
    """Mudo no firmware: a luz é repintada em `1` (a frase do kernel) e ENTREGUE.

    Ela apertou o mudo; sob a LUZ-DO-MIC a nossa luz estava PISCANDO (`2`) para
    dizer "está entrando som". Devolver a posse sem repintar deixaria o `2` no
    plástico — um estado que o kernel nunca escreve, e que borda nenhuma
    explica.

    MORDIDA: tirar a chamada a `_repintar_antes_de_soltar` do
    `set_microphone_led` — nenhum report é entregue, `escritos` fica vazio e a
    primeira asserção reprova.
    """
    handle = _handle(mudo=True)
    backend = _backend({_A: handle})

    backend.set_microphone_led(2, uniq=_A)
    assert handle.device.escritos == [], (
        "tomar a posse não escreve sozinho — quem escreve em regime é a thread "
        "de report; se algo saiu aqui, a régua não está medindo a devolução"
    )

    assert backend.set_microphone_led(None, uniq=_A) is True

    entregues = _led_entregue(handle)
    assert len(entregues) == 1, (
        "a devolução tem de entregar EXATAMENTE um report — o da repintura. "
        f"Saíram {len(entregues)}"
    )
    flag1, byte = entregues[0]
    assert flag1 & rep.VALID_FLAG1_MIC_MUTE_LED_CONTROL_ENABLE, (
        "o report da repintura tem de sair COM a posse: sem o bit `0x01` o "
        "firmware ignora o byte e a repintura não pinta nada"
    )
    assert byte == 1, (
        "o firmware declara MUDO, e a convenção do kernel é `mute_button_led = "
        "ds->mic_muted` — a luz tem de ser deixada ACESA"
    )


def test_depois_de_repintar_a_posse_e_mesmo_devolvida() -> None:
    """A repintura não pode custar a devolução: o bit tem de cair no fim.

    A metade que impede a cura de virar "o hefesto ficou dono da luz para
    sempre" — que é o defeito que a porta de emergência existe para não ter.

    MORDIDA: fazer a repintura ser a última palavra (não chamar `tomar(None)`
    depois dela) — o bit `0x01` continua ligado e esta régua reprova.
    """
    handle = _handle(mudo=True)
    backend = _backend({_A: handle})
    backend.set_microphone_led(2, uniq=_A)
    backend.set_microphone_led(None, uniq=_A)

    assert handle._mic_led_desejado is None
    comum = handle._build_common(rumble_asserted=False)
    assert comum[1] & rep.VALID_FLAG1_MIC_MUTE_LED_CONTROL_ENABLE == 0, (
        "depois de repintar, o `0x01` do flag1 TEM de cair — senão o kernel "
        "nunca volta a mandar na luz"
    )
    assert comum[8] == 0


def test_a_repintura_e_leitura_e_nao_constante() -> None:
    """Sem mudo no firmware, a luz é deixada APAGADA — o valor vem do report.

    É a metade que prova que o `1` do teste anterior não é um literal escrito à
    mão. Dois controles em estados diferentes têm de sair com bytes diferentes.

    MORDIDA: trocar a leitura por uma constante (`valor = 1`) — esta régua
    reprova, e a de cima continua verde. Só as duas juntas medem.
    """
    handle = _handle(mudo=False)
    backend = _backend({_A: handle})
    backend.set_microphone_led(1, uniq=_A)
    backend.set_microphone_led(None, uniq=_A)

    entregues = _led_entregue(handle)
    assert len(entregues) == 1
    flag1, byte = entregues[0]
    assert flag1 & rep.VALID_FLAG1_MIC_MUTE_LED_CONTROL_ENABLE
    assert byte == 0, (
        "o firmware NÃO declara mudo — a luz que se devolve ao kernel é a "
        "apagada, e não o `1` que estava aceso pela nossa convenção"
    )


# ---------------------------------------------------------------------------
# 2. A mesa é de quatro, e a devolução tem ENDEREÇO
# ---------------------------------------------------------------------------


def test_cada_controle_repinta_o_seu_proprio_mudo() -> None:
    """Dois controles, dois estados, dois bytes — e ninguém escreve no vizinho.

    Foi assim que ela mediu a leitura em 03/09/2026: o do cabo devolvendo
    `mic_mudo: false` e o do rádio `mic_mudo: true`, no mesmo instante. Uma
    repintura que lesse o primário para todos deixaria a luz do segundo errada.

    MORDIDA: trocar `audio_status_for(uniq)` por `audio_status_for()` — o B
    passa a ser repintado com o mudo do A e a segunda asserção reprova.
    """
    a = _handle(mudo=False)
    b = _handle(mudo=True)
    backend = _backend({_A: a, _B: b})

    backend.set_microphone_led(2, uniq=_A)
    backend.set_microphone_led(2, uniq=_B)
    backend.set_microphone_led(None, uniq=_A)
    backend.set_microphone_led(None, uniq=_B)

    assert [byte for _, byte in _led_entregue(a)] == [0], (
        "o controle SEM mudo tem de ser deixado apagado"
    )
    assert [byte for _, byte in _led_entregue(b)] == [1], (
        "e o mudo, aceso — cada luz fala do PRÓPRIO microfone, nunca do sistema"
    )


def test_a_devolucao_de_um_controle_nao_escreve_no_outro() -> None:
    """A outra metade do endereço: soltar o A não põe byte nenhum no fio do B.

    MORDIDA: fazer a repintura varrer `self._handles` em vez de usar o handle
    já resolvido — o B recebe um report que ninguém pediu e esta régua reprova.
    """
    a = _handle(mudo=True)
    b = _handle(mudo=True)
    backend = _backend({_A: a, _B: b})

    backend.set_microphone_led(2, uniq=_A)
    backend.set_microphone_led(2, uniq=_B)
    backend.set_microphone_led(None, uniq=_A)

    assert len(a.device.escritos) == 1
    assert b.device.escritos == [], "o B não pediu nada e não pode ter recebido"
    assert b._mic_led_desejado == 2, "e continua dono do próprio byte"


# ---------------------------------------------------------------------------
# 3. O rádio, e o report que o firmware aceita
# ---------------------------------------------------------------------------


def test_no_radio_a_repintura_sai_carimbada_e_com_crc() -> None:
    """No rádio o report tem de ir pelo `writeReport`, não cru no `device`.

    O preço deste atalho já foi pago uma vez nesta casa e está escrito no
    `reescrever_lightbar_por_hidraw`: *"o firmware descarta o report fora de
    sequência e o log diz 'escrito' com a barra apagada"*. Uma repintura
    descartada é exatamente o defeito que a sprint fecha, com a cura no lugar.

    MORDIDA: escrever direto no `handle.device` (pulando o `writeReport`) — o
    `seq` sai 0 e o CRC fica o do buffer sem carimbo; a última asserção reprova.
    """
    from hefesto_dualsense4unix.core.ds_output_report import bt_crc32

    handle = _handle(mudo=True, transporte="bt")
    handle._bt_seq = 5
    backend = _backend({_A: handle})
    backend.set_microphone_led(3, uniq=_A)
    backend.set_microphone_led(None, uniq=_A)

    assert len(handle.device.escritos) == 1
    relatorio = handle.device.escritos[0]
    assert len(relatorio) == rep.BT_REPORT_LEN
    assert relatorio[0] == rep.BT_REPORT_ID
    assert _no_fio(relatorio, 8, "bt") == 1, "o mudo de fato, no byte do rádio"
    assert relatorio[1] >> 4 == 5, "o `seq` do fluxo daquele handle tem de estar lá"
    esperado = bt_crc32(relatorio[: rep.BT_REPORT_LEN - 4])
    assert (
        int.from_bytes(relatorio[rep.BT_REPORT_LEN - 4 :], "little") == esperado
    ), "CRC recalculado DEPOIS do carimbo — senão o firmware descarta"


# ---------------------------------------------------------------------------
# 4. As três recusas: sem posse, no escuro e no Modo Nativo
# ---------------------------------------------------------------------------


def test_devolver_o_que_ja_e_do_kernel_nao_escreve_nada() -> None:
    """A devolução continua IDEMPOTENTE — repintar sem posse é escrever por cima.

    `devolver_a_luz_ao_kernel` varre a mesa inteira e é chamada em transição de
    perfil; se cada passagem tomasse a posse por um report só para devolvê-la,
    estaríamos escrevendo por cima do kernel sem ter o que corrigir — que é a
    forma exata do defeito do `3d9bb7e`, no byte vizinho.

    MORDIDA: apagar a guarda de `_mic_led_desejado is None` — a segunda
    devolução passa a entregar um report e esta régua reprova.
    """
    handle = _handle(mudo=True)
    backend = _backend({_A: handle})

    backend.set_microphone_led(2, uniq=_A)
    backend.set_microphone_led(None, uniq=_A)
    assert len(handle.device.escritos) == 1

    backend.set_microphone_led(None, uniq=_A)
    assert len(handle.device.escritos) == 1, (
        "a segunda devolução não tem o que repintar: a posse já é do kernel"
    )


def test_sem_leitura_do_firmware_a_luz_e_deixada_apagada() -> None:
    """O controle que nunca reportou: repinta-se `0`, e NUNCA `1`.

    A escolha é assimétrica de propósito e o custo está no docstring de
    `_repintar_antes_de_soltar`. Na convenção do kernel `1` = MUDO: pintar `1`
    no escuro faria a luz afirmar *"você está mudo"* sobre um microfone que
    pode estar vivo — ela calaria achando que ninguém a ouve. `0` erra na
    direção barata, e o primeiro toque no botão põe tudo no lugar.

    Não repintar não é alternativa: deixaria no plástico o `2`/`3` que o kernel
    jamais escreveria.

    MORDIDA: fazer o desconhecido virar `bool(None) -> False -> 0` por acidente
    passa; o que reprova é trocar a política para `1` no escuro, ou desistir de
    escrever quando a leitura falta (a primeira asserção cai).
    """
    handle = _handle(mudo=None)
    backend = _backend({_A: handle})
    backend.set_microphone_led(2, uniq=_A)
    backend.set_microphone_led(None, uniq=_A)

    entregues = _led_entregue(handle)
    assert len(entregues) == 1, (
        "sem leitura ainda se repinta — largar o `2` piscando é pior que "
        "qualquer dos dois valores honestos"
    )
    flag1, byte = entregues[0]
    assert flag1 & rep.VALID_FLAG1_MIC_MUTE_LED_CONTROL_ENABLE
    assert byte == 0


def test_no_modo_nativo_a_devolucao_nao_toca_o_hidraw() -> None:
    """Com o Modo Nativo ligado o JOGO é o dono do hidraw — não se escreve.

    FEAT-NATIVE-OUTPUT-MUTE-01. A posse do byte volta ao kernel do mesmo jeito
    (é só estado nosso), mas nenhum report sai por cima do jogo.

    MORDIDA: tirar a guarda de `_output_muted` — um report nosso aparece no fio
    de um controle que o jogo está dirigindo, e esta régua reprova.
    """
    handle = _handle(mudo=True)
    backend = _backend({_A: handle})
    backend.set_microphone_led(2, uniq=_A)
    handle._output_muted = True

    assert backend.set_microphone_led(None, uniq=_A) is True
    assert handle.device.escritos == []
    assert handle._mic_led_desejado is None


# ---------------------------------------------------------------------------
# 5. O que a devolução NÃO faz
# ---------------------------------------------------------------------------


def test_a_repintura_nao_encosta_no_byte_do_mudo() -> None:
    """`common[9]` é campo de outro dono, e as três recusas medidas são sobre ele.

    BT-E-VPAD-01, MIC-BT-DONO-01, MIC-DOIS-DONOS-01. Repintar a LUZ não pode
    mutar nem desmutar nada — nem mesmo por tabela, autorizando o
    `POWER_SAVE_CONTROL_ENABLE` sem valor.

    MORDIDA: forçar uma borda do kernel escrevendo o `common[9]` na repintura
    (a ideia tentadora que a §3 da spec proíbe) — esta régua reprova.
    """
    handle = _handle(mudo=True)
    backend = _backend({_A: handle})
    backend.set_microphone_led(2, uniq=_A)
    backend.set_microphone_led(None, uniq=_A)

    relatorio = handle.device.escritos[0]
    assert _no_fio(relatorio, 9) == 0, "o `common[9]` viaja inerte"
    assert (
        _no_fio(relatorio, 1) & rep.VALID_FLAG1_POWER_SAVE_CONTROL_ENABLE == 0
    ), "e o bit que o autorizaria continua apagado"
    assert handle._mic_mute_desejado is None


@pytest.mark.parametrize("aceso", [True, False, 0, 1, 2, 3])
def test_tomar_a_posse_continua_sem_escrever_por_conta_propria(aceso: Any) -> None:
    """A cura é da DEVOLUÇÃO — acender não pode virar escrita avulsa.

    Quem escreve em regime é a thread de report, com o dedup que evita
    reafirmar o mesmo valor por cima do kernel a cada ciclo (o defeito do
    `3d9bb7e`). Se a repintura escapasse para o caminho de acender, cada tique
    da PEÇA C viraria um write avulso.

    MORDIDA: chamar `_repintar_antes_de_soltar` fora do `aceso is None` — esta
    régua reprova em todos os seis casos.
    """
    handle = _handle(mudo=True)
    backend = _backend({_A: handle})
    backend.set_microphone_led(aceso, uniq=_A)
    assert handle.device.escritos == []


# ---------------------------------------------------------------------------
# 6. OS TRÊS CAMINHOS DA §2 — a repintura não pode valer só para quem chama o
#    backend direto. As duas réguas abaixo atravessam o handler do IPC e a
#    palavra da CLI até o FIO, com o controller de verdade no meio.
# ---------------------------------------------------------------------------


class _DaemonDeMentira:
    """O mínimo que `_handle_mic_led_set` toca: um `controller`.

    O controller NÃO é dublê — é o `PyDualSenseController` do produto, com um
    handle real e um fio de mentira. É essa a diferença entre esta régua e a
    do `test_mic_da_mesa_o_ipc_a_tela_e_o_gesto.py`, que mede o handler contra
    um dublê e portanto não alcança a repintura.
    """

    def __init__(self, controller: Any) -> None:
        self.controller = controller

    async def chamar(self, params: dict[str, Any]) -> dict[str, Any]:
        from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin

        return await IpcHandlersMixin._handle_mic_led_set(self, params)  # type: ignore[arg-type]


def test_o_ipc_com_aceso_null_faz_a_repintura_chegar_ao_fio() -> None:
    """`mic.led.set {aceso: null}` entrega o report da repintura. Ponta a ponta.

    O segundo dos três caminhos da §2. O handler faz UMA chamada ao backend e
    é de propósito: se ele repintasse por conta própria, cada caminho novo
    teria de repetir a cura. Esta régua prova que a chamada única basta.

    MORDIDA: tirar a chamada a `_repintar_antes_de_soltar` do
    `set_microphone_led` — o `status` continua `"ok"` (o handler não sabe da
    diferença) e o fio fica vazio; a asserção do report reprova.
    """
    import asyncio

    handle = _handle(mudo=True)
    daemon = _DaemonDeMentira(_backend({_A: handle}))

    resposta = asyncio.run(daemon.chamar({"aceso": 2, "uniq": _A}))
    assert resposta == {"status": "ok", "aceso": 2}
    assert handle.device.escritos == [], "acender não escreve avulso"

    resposta = asyncio.run(daemon.chamar({"aceso": None, "uniq": _A}))
    assert resposta == {"status": "ok", "aceso": None}

    entregues = _led_entregue(handle)
    assert len(entregues) == 1, (
        "o caminho do IPC tem de entregar a repintura como qualquer outro — "
        f"saíram {len(entregues)} reports"
    )
    flag1, byte = entregues[0]
    assert flag1 & rep.VALID_FLAG1_MIC_MUTE_LED_CONTROL_ENABLE
    assert byte == 1, "o mudo de fato daquele controle, não o último que pintamos"
    assert handle._mic_led_desejado is None, "e a posse volta ao kernel"


def test_o_led_release_da_cli_e_a_palavra_que_chega_ao_fio() -> None:
    """`mic led-release` → `aceso: null` → repintura entregue. O 3º de PRONTO É.

    O primeiro dos três caminhos da §2, e ele é casca sobre o IPC: a CLI não
    escreve no aparelho, ela traduz a PALAVRA em `None` e manda. Por isso a
    régua parte do dicionário de ações do produto — se alguém trocar
    `led-release` por `False` (o defeito do `3d9bb7e`, no byte vizinho), a
    primeira asserção cai antes de qualquer report.

    MORDIDA: mapear `"led-release"` para `False` em `_ACOES_LED` — o `aceso`
    do payload deixa de ser `None`, a posse não é devolvida e as duas últimas
    asserções reprovam.
    """
    import asyncio

    from hefesto_dualsense4unix.cli.cmd_mic import _ACOES_LED

    aceso = _ACOES_LED["led-release"]
    assert aceso is None, (
        "`led-release` é a DEVOLUÇÃO; `led-off` é a ordem de apagar com a "
        "posse mantida, e confundir os dois é o defeito do `3d9bb7e`"
    )

    # O payload é montado como o `_mic_led` monta: `{"aceso": ...}` e o `uniq`
    # só quando ele existe. Daqui para baixo o caminho é o mesmo do IPC.
    payload: dict[str, Any] = {"aceso": aceso, "uniq": _A}

    handle = _handle(mudo=False)
    daemon = _DaemonDeMentira(_backend({_A: handle}))
    asyncio.run(daemon.chamar({"aceso": 3, "uniq": _A}))
    resposta = asyncio.run(daemon.chamar(payload))

    assert resposta["status"] == "ok"
    assert [byte for _, byte in _led_entregue(handle)] == [0], (
        "o `led-release` tem de deixar a luz no estado REAL (aqui: não mudo, "
        "logo apagada), e não no `3` que estava piscando"
    )
    assert handle._mic_led_desejado is None

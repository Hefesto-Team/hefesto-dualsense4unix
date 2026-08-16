"""PONTE-UNIVERSAL-01/Onda 1 — de quem é esta placa de som, com quatro na mesa.

O DEFEITO, medido na mesa de quatro em 15/08/2026: o botão "Ouvir no controle"
nascia insensível e o card não sabia dizer o sink de nenhum controle. A causa
não era o botão — era a atribuição. O ``mic_monitor.escolher_sink`` só sabia
casar por NOME, e o nome do sink de um DualSense é o mesmo em todos::

    alsa_output.usb-Sony_..._DualSense_Wireless_Controller-00.analog-surround-40
    alsa_output.usb-Sony_..._DualSense_Wireless_Controller-00.2.analog-surround-40

O ``-00``/``-00.2`` é desempate posicional do PipeWire, e o próprio
``/dev/snd/by-id`` só consegue guardar um link para os dois. Sem identidade no
nome, a resposta conservadora — e certa, à época — era recusar TODOS.

A CURA: casar placa e controle pelo **dispositivo USB em que os dois penduram**
(``app/usb_pai.py``), portado do ``scripts/ensaios/audio_por_transporte.py``.

O QUE ESTE ARQUIVO TRAVA, e o que cada teste arranca para ver vermelho:

* **Casa certo, e casa CRUZADO.** Na bancada de 15/08 o ``-00`` é o card 3 e o
  ``-00.2`` é o card 2 — a ordem do nome é o INVERSO da ordem do card. Um teste
  que só exigisse "cada um com um sink diferente" passaria com os dois
  trocados; este exige o par certo. Arranque o ``usb=`` da chamada e os dois
  viram ``None``.
* **Rádio não ganha placa emprestada.** Pelo rádio o DualSense não publica
  placa ALSA nenhuma (medido no mesmo dia: a placa segue o transporte). Com um
  controle no rádio e uma placa USB de outro aparelho na lista, a regra do
  "um para um" entregaria a placa a ele com toda a confiança. Arranque o
  ``CasamentoUSB.veta`` e o teste fica vermelho.
* **Sem número mágico.** Os mesmos dados com 1, 2 e 4 controles dão a mesma
  resposta por controle. Nada aqui olha MAC, ordem de conexão nem quantidade.

UNIVERSALIDADE (o que ela fixou em 15/08/2026): *"a ideia é fazermos algo
UNIVERSAL e USÁVEL EM QUALQUER PC COM QUALQUER DUALSENSE"*. Por isso o
casamento é pelo sysfs do kernel, que responde igual em qualquer máquina, e por
isso os testes montam um sysfs de MENTIRA — eles não podem depender de haver
controle plugado nesta bancada.

CONFUNDIMENTO: nenhum. A prova de que o par está certo não vem do produto: ela
vem do ``readlink -f /sys/class/sound/cardN/device`` e do
``readlink -f /sys/class/hidraw/hidrawN/device``, duas leituras independentes
do kernel, conferidas à mão antes de este arquivo existir.

Os MACs estão MASCARADOS na regra da casa (octetos 4 e 5 zerados) — aqui eles
são rótulo, e não parte do casamento: quem casa é o caminho do sysfs.
"""

from __future__ import annotations

import pytest

from hefesto_dualsense4unix.app import mic_monitor as mm
from hefesto_dualsense4unix.app.mic_monitor import (
    CasamentoUSB,
    escolher_fonte,
    escolher_sink,
    sinks_dualsense,
)
from hefesto_dualsense4unix.app.usb_pai import (
    dispositivo_usb_pai,
    nos_e_sysfs,
    usb_pai_por_no,
    usb_pai_por_uniq,
)

# ---------------------------------------------------------------------------
# A bancada de 15/08/2026, medida. Dois no cabo, dois no rádio.
# ---------------------------------------------------------------------------

#: Os dois no CABO. O nó USB de cada um saiu de
#: `readlink -f /sys/class/hidraw/hidrawN/device`.
_CABO_A = "aa:bb:cc:00:00:ab"  # hidraw8,  hw 0x0711 -> usb3/3-2 -> card3
_CABO_B = "aa:bb:cc:00:00:03"  # hidraw10, hw 0x0811 -> usb3/3-3 -> card2
#: Os dois no RÁDIO. Penduram em `/sys/devices/virtual/misc/uhid/...`, e por
#: isso o dispositivo USB pai deles é "" — não é falha de medição, é o fato.
_RADIO_A = "aa:bb:cc:00:00:d8"  # hidraw5, hw 0x1111
_RADIO_B = "aa:bb:cc:00:00:f0"  # hidraw4, hw 0x0710

_RAIZ = "/sys/devices/pci0000:00/0000:00:08.1/0000:0c:00.3/usb3"
_USB_DO_CABO_A = f"{_RAIZ}/3-2"
_USB_DO_CABO_B = f"{_RAIZ}/3-3"

#: Os nomes REAIS dos dois sinks, copiados de `pactl list sinks short` nesta
#: bancada. Repare que eles só diferem no `.2` — é todo o desempate que o
#: PipeWire oferece, e ele é posicional.
_SINK_A = (
    "alsa_output.usb-Sony_Interactive_Entertainment_DualSense_Wireless_"
    "Controller-00.analog-surround-40"
)
_SINK_B = (
    "alsa_output.usb-Sony_Interactive_Entertainment_DualSense_Wireless_"
    "Controller-00.2.analog-surround-40"
)
_SOURCE_A = (
    "alsa_input.usb-Sony_Interactive_Entertainment_DualSense_Wireless_"
    "Controller-00.iec958-stereo"
)
_SOURCE_B = (
    "alsa_input.usb-Sony_Interactive_Entertainment_DualSense_Wireless_"
    "Controller-00.2.iec958-stereo"
)

#: `pactl list sinks short` desta bancada, com os dois controles e a saída
#: HDMI dela no meio.
_SINKS_CURTO = (
    f"19595\talsa_output.pci-0000_0c_00.4.iec958-stereo\tPipeWire"
    f"\ts32le 2ch 48000Hz\tSUSPENDED\n"
    f"29553\t{_SINK_A}\tPipeWire\ts16le 4ch 48000Hz\tSUSPENDED\n"
    f"29574\t{_SINK_B}\tPipeWire\ts16le 4ch 48000Hz\tSUSPENDED\n"
    f"33286\talsa_output.pci-0000_0a_00.1.hdmi-stereo\tPipeWire"
    f"\ts16le 2ch 48000Hz\tSUSPENDED\n"
)

#: `pactl list sinks` (LONGO) desta bancada, recortado nas linhas que importam.
#: O corte de registro é a linha SEM recuo, como no `pactl` de verdade, e a
#: `Description:` traduzida fica de propósito: ela prova que o parser não se
#: apoia em texto localizado.
_SINKS_LONGO = f"""Sink #19595
\tState: SUSPENDED
\tName: alsa_output.pci-0000_0c_00.4.iec958-stereo
\tDescription: Starship/Matisse HD Audio Controller Estéreo digital (IEC958)
\tProperties:
\t\tsysfs.path = "/devices/pci0000:00/0000:00:08.1/0000:0c:00.4/sound/card1"
Sink #29553
\tState: SUSPENDED
\tName: {_SINK_A}
\tDescription: DualSense wireless controller (PS5) Surround analógico 4.0
\tProperties:
\t\talsa.card = "3"
\t\tsysfs.path = "{_RAIZ.removeprefix("/sys")}/3-2/3-2:1.0/sound/card3"
\tPorts:
\t\tanalog-output: Analog Output (type: Analog, priority: 9900)
Sink #29574
\tState: SUSPENDED
\tName: {_SINK_B}
\tDescription: DualSense wireless controller (PS5) Surround analógico 4.0
\tProperties:
\t\talsa.card = "2"
\t\tsysfs.path = "{_RAIZ.removeprefix("/sys")}/3-3/3-3:1.0/sound/card2"
"""


def _casamento(uniqs: dict[str, str], nos: dict[str, str]) -> CasamentoUSB:
    return CasamentoUSB(por_uniq=dict(uniqs), por_no=dict(nos))


#: O casamento como ele sai da bancada: os dois do cabo com o seu nó USB, os
#: dois do rádio com "" — e os sinks CRUZADOS em relação ao número do nome.
_USB_POR_UNIQ = {
    _CABO_A: _USB_DO_CABO_A,
    _CABO_B: _USB_DO_CABO_B,
    _RADIO_A: "",
    _RADIO_B: "",
}
_USB_POR_SINK = {
    _SINK_A: _USB_DO_CABO_A,
    _SINK_B: _USB_DO_CABO_B,
    "alsa_output.pci-0000_0c_00.4.iec958-stereo": "",
}


# ---------------------------------------------------------------------------
# 1. O casamento, no nível da função pura
# ---------------------------------------------------------------------------


def test_cada_placa_vai_para_o_seu_controle_e_nao_para_o_vizinho() -> None:
    """O par certo, com quatro controles na mesa.

    ARRANQUE PARA VER VERMELHO: tire o ``usb`` da chamada de `escolher_sink`
    (ou passe ``None``). Os quatro viram ``None`` — que é exatamente o defeito
    que esta onda curou, e o teste reprova nas duas primeiras asserções.
    """
    usb = _casamento(_USB_POR_UNIQ, _USB_POR_SINK)
    sinks = sinks_dualsense(_SINKS_CURTO)
    todos = [_CABO_A, _CABO_B, _RADIO_A, _RADIO_B]

    assert escolher_sink(sinks, _CABO_A, todos, usb) == _SINK_A
    assert escolher_sink(sinks, _CABO_B, todos, usb) == _SINK_B
    # O rádio não tem placa. "Nenhuma" é a resposta honesta, não um defeito.
    assert escolher_sink(sinks, _RADIO_A, todos, usb) is None
    assert escolher_sink(sinks, _RADIO_B, todos, usb) is None


def test_sem_o_casamento_por_usb_os_quatro_ficam_sem_placa() -> None:
    """O comportamento ANTES da cura, preservado como controle NEGATIVO.

    Não é nostalgia: é a metade que prova que o teste acima mede o casamento e
    não outra coisa. Se este passar a devolver sink, a cura virou um chute.
    """
    sinks = sinks_dualsense(_SINKS_CURTO)
    todos = [_CABO_A, _CABO_B, _RADIO_A, _RADIO_B]
    for uniq in todos:
        assert escolher_sink(sinks, uniq, todos, None) is None


def test_o_nome_nao_serve_de_prova_o_par_e_cruzado() -> None:
    """O ``-00`` é o card 3 e o ``-00.2`` é o card 2 — o inverso do que parece.

    Este teste existe porque o erro mais convincente desta família é o que
    acerta metade: adivinhar por posição casaria os dois trocados e passaria em
    qualquer teste que só exigisse "um sink diferente para cada um".
    """
    usb = _casamento(_USB_POR_UNIQ, _USB_POR_SINK)
    sinks = sinks_dualsense(_SINKS_CURTO)
    todos = [_CABO_A, _CABO_B]
    # O controle do 3-2 fica com o `-00` (card 3); o do 3-3, com o `-00.2`
    # (card 2). Trocar os dois é o defeito que este teste proíbe.
    assert escolher_sink(sinks, _CABO_A, todos, usb) == _SINK_A
    assert escolher_sink(sinks, _CABO_B, todos, usb) != _SINK_A


def test_um_controle_no_radio_sozinho_nao_herda_a_placa_de_outro_aparelho() -> None:
    """A guarda do "um para um" — e ela é o que separa cura de coincidência.

    Um controle só, uma placa USB de DualSense só (deixada por um controle que
    acabou de ser desplugado, ou por um segundo aparelho). A aritmética diz
    "só pode ser ele"; a física diz que um controle no rádio não tem placa.

    ARRANQUE PARA VER VERMELHO: faça `CasamentoUSB.veta` devolver sempre
    ``False``. O `escolher_sink` volta a entregar a placa ao controle do rádio.
    """
    usb = _casamento({_RADIO_A: ""}, {_SINK_A: _USB_DO_CABO_A})
    assert escolher_sink([_SINK_A], _RADIO_A, [_RADIO_A], usb) is None
    # E o contraste que prova que a guarda não é um "sempre None": o MESMO
    # controle, agora no cabo e naquele mesmo nó USB, recebe a placa.
    no_cabo = _casamento({_RADIO_A: _USB_DO_CABO_A}, {_SINK_A: _USB_DO_CABO_A})
    assert escolher_sink([_SINK_A], _RADIO_A, [_RADIO_A], no_cabo) == _SINK_A


def test_no_virtual_nao_veta_a_ponte_de_mic_por_bluetooth_continua_valendo() -> None:
    """Nó sem dispositivo USB não tem dono, e não pode vetar ninguém.

    A ponte de mic por Bluetooth deste projeto publica uma source virtual —
    sem ``sysfs.path`` — e ela existe justamente para quem está no RÁDIO. Se o
    veto olhasse "o controle não tem USB" em vez de "o nó tem outro dono", ele
    mataria o medidor de mic no cenário-alvo do projeto.
    """
    ponte = "hefesto_dualsense_bt_0000d8"
    usb = _casamento({_RADIO_A: ""}, {ponte: ""})
    assert escolher_fonte([ponte], _RADIO_A, [_RADIO_A], usb) == ponte


def test_a_mesma_resposta_com_um_dois_e_quatro_controles() -> None:
    """Nenhum número mágico: a resposta por controle não depende da mesa.

    É a exigência dela de 15/08/2026 posta em teste — o produto tem de servir a
    quem tem um controle e a quem tem sete, e numa máquina que não é a dela.
    """
    usb = _casamento(_USB_POR_UNIQ, _USB_POR_SINK)
    sinks = sinks_dualsense(_SINKS_CURTO)
    for mesa in ([_CABO_A], [_CABO_A, _RADIO_A], [_CABO_A, _CABO_B, _RADIO_A, _RADIO_B]):
        assert escolher_sink(sinks, _CABO_A, list(mesa), usb) == _SINK_A


# ---------------------------------------------------------------------------
# 2. As peças do `app/usb_pai.py`, contra um sysfs de mentira
# ---------------------------------------------------------------------------

#: Um sysfs inventado, com a forma REAL do de cá: o nó do dispositivo tem
#: `busnum`/`devnum`; a interface, não. É a diferença que faz a subida parar no
#: lugar certo.
_FALSO_SYSFS = {
    f"{_USB_DO_CABO_A}/busnum",
    f"{_USB_DO_CABO_A}/devnum",
    f"{_USB_DO_CABO_B}/busnum",
    f"{_USB_DO_CABO_B}/devnum",
}


def _existe(caminho: str) -> bool:
    return caminho in _FALSO_SYSFS


def test_a_subida_para_no_dispositivo_e_nao_na_interface_nem_no_barramento() -> None:
    """Parar cedo casa o HID só consigo; parar tarde casa todo mundo com todo mundo."""
    hid = f"{_USB_DO_CABO_A}/3-2:1.3/0003:054C:0CE6.0022"
    som = f"{_USB_DO_CABO_A}/3-2:1.0/sound/card3"
    achado_hid = dispositivo_usb_pai(hid, existe=_existe, real=lambda c: c)
    achado_som = dispositivo_usb_pai(som, existe=_existe, real=lambda c: c)
    assert achado_hid == _USB_DO_CABO_A
    assert achado_som == _USB_DO_CABO_A
    # E o do vizinho é OUTRO nó — se a subida fosse até o barramento (`usb3`),
    # estes dois seriam iguais e o casamento inteiro seria uma coincidência.
    outro = dispositivo_usb_pai(
        f"{_USB_DO_CABO_B}/3-3:1.0/sound/card2", existe=_existe, real=lambda c: c
    )
    assert outro != achado_som


def test_o_radio_nao_tem_dispositivo_usb_e_isso_e_uma_resposta() -> None:
    """`uhid` é virtual: a subida chega à raiz sem achar `busnum`, e devolve ""."""
    virtual = "/sys/devices/virtual/misc/uhid/0005:054C:0CE6.0020"
    assert dispositivo_usb_pai(virtual, existe=_existe, real=lambda c: c) == ""


def test_o_parser_do_pactl_longo_acha_o_sysfs_de_cada_no() -> None:
    """E não se apoia em texto traduzido nem confunde `Name:` de porta."""
    mapa = nos_e_sysfs(_SINKS_LONGO)
    assert mapa[_SINK_A].endswith("/3-2/3-2:1.0/sound/card3")
    assert mapa[_SINK_B].endswith("/3-3/3-3:1.0/sound/card2")
    # O nó que não é DualSense entra igual: quem filtra é o `sinks_dualsense`.
    assert "alsa_output.pci-0000_0c_00.4.iec958-stereo" in mapa


def test_o_parser_atravessa_o_pactl_ate_o_dispositivo_usb() -> None:
    """A ponta a ponta do lado do PipeWire: texto do `pactl` -> nó USB."""
    por_no = usb_pai_por_no(
        nos_e_sysfs(_SINKS_LONGO), existe=_existe, real=lambda c: c
    )
    assert por_no[_SINK_A] == _USB_DO_CABO_A
    assert por_no[_SINK_B] == _USB_DO_CABO_B
    assert por_no["alsa_output.pci-0000_0c_00.4.iec958-stereo"] == ""


def test_o_uniq_do_kernel_leva_ao_dispositivo_usb_sem_olhar_ordem() -> None:
    """`/sys/class/hidraw/*/device/uevent` -> nó USB, por `HID_UNIQ`.

    A varredura é por CONTEÚDO do uevent, nunca pelo número do hidraw: o
    `hidraw10` vem antes do `hidraw8` em ordem alfabética, e um casamento
    posicional trocaria os dois — que é o defeito que esta onda existe para
    não repetir.
    """
    uevents = {
        "/sys/class/hidraw/hidraw10/device/uevent": (
            f"HID_NAME=DualSense Wireless Controller\nHID_UNIQ={_CABO_B.upper()}\n"
        ),
        "/sys/class/hidraw/hidraw8/device/uevent": (
            f"HID_NAME=DualSense Wireless Controller\nHID_UNIQ={_CABO_A}\n"
        ),
        "/sys/class/hidraw/hidraw5/device/uevent": (
            f"HID_NAME=DualSense Wireless Controller\nHID_UNIQ={_RADIO_A}\n"
        ),
        "/sys/class/hidraw/hidraw0/device/uevent": "HID_NAME=CX 2.4G Wireless Receiver\n",
    }
    reais = {
        "/sys/class/hidraw/hidraw10/device": f"{_USB_DO_CABO_B}/3-3:1.3/0003:054C:0CE6",
        "/sys/class/hidraw/hidraw8/device": f"{_USB_DO_CABO_A}/3-2:1.3/0003:054C:0CE6",
        "/sys/class/hidraw/hidraw5/device": "/sys/devices/virtual/misc/uhid/0005:054C",
        "/sys/class/hidraw/hidraw0/device": "/sys/devices/virtual/misc/uhid/0003:AAAA",
    }
    achado = usb_pai_por_uniq(
        [_CABO_A, _CABO_B, _RADIO_A],
        listar=lambda _raiz: ["hidraw0", "hidraw10", "hidraw5", "hidraw8"],
        ler=lambda caminho: uevents.get(caminho, ""),
        existe=_existe,
        real=lambda c: reais.get(c, c),
    )
    # O `HID_UNIQ` do kernel veio em MAIÚSCULAS de propósito num dos dois: a
    # janela e o sysfs não combinam caixa, e o casamento é por dígito hex.
    assert achado == {
        _CABO_A: _USB_DO_CABO_A,
        _CABO_B: _USB_DO_CABO_B,
        _RADIO_A: "",
    }


# ---------------------------------------------------------------------------
# 3. O monitor inteiro — o que o card e o botão realmente consultam
# ---------------------------------------------------------------------------


@pytest.fixture
def monitor_da_bancada(monkeypatch: pytest.MonkeyPatch) -> mm.MicMonitor:
    """Um `MicMonitor` com o `pactl` e o sysfs da bancada de 15/08, dublados."""

    def _runner(cmd: list[str]) -> str:
        if cmd[:4] == ["pactl", "list", "sinks", "short"]:
            return _SINKS_CURTO
        if cmd[:3] == ["pactl", "list", "sinks"]:
            return _SINKS_LONGO
        if cmd[:2] == ["pactl", "get-sink-mute"]:
            # A placa do CABO_A está muda e a do CABO_B não — é o contraste
            # que mostra em qual card o selo acende.
            return "Mute: yes" if cmd[2] == _SINK_A else "Mute: no"
        return ""

    monkeypatch.setattr(mm, "usb_pai_por_uniq", lambda _uniqs: dict(_USB_POR_UNIQ))
    monkeypatch.setattr(
        mm,
        "usb_pai_por_no",
        lambda mapa, **_kw: {nome: _USB_POR_SINK.get(nome, "") for nome in mapa},
    )
    monitor = mm.MicMonitor(
        runner=_runner, capturador=lambda *a, **k: None, auto_supervisao=False
    )
    monitor.set_ativo(True)
    monitor.set_controles((_CABO_A, _CABO_B, _RADIO_A, _RADIO_B))
    return monitor


def test_o_monitor_publica_um_sink_por_controle_do_cabo(
    monitor_da_bancada: mm.MicMonitor,
) -> None:
    """É esta a porta que o card (`definir_sink_de_saida`) consome.

    Antes da cura os quatro devolviam "" e o bloco Alto-falante não tinha para
    onde tocar a confirmação.
    """
    monitor_da_bancada.reconciliar()
    assert monitor_da_bancada.sink_de(_CABO_A) == _SINK_A
    assert monitor_da_bancada.sink_de(_CABO_B) == _SINK_B
    assert monitor_da_bancada.sink_de(_RADIO_A) == ""
    assert monitor_da_bancada.sink_de(_RADIO_B) == ""


def test_o_selo_da_saida_muda_acende_no_card_certo(
    monitor_da_bancada: mm.MicMonitor,
) -> None:
    """A carona da camada 1 segue o mesmo casamento — e some no rádio.

    A placa do CABO_A está muda e a do CABO_B não. Acender "saída muda" no card
    do controle errado seria a interface culpando o PipeWire pelo silêncio do
    controle que está tocando — e antes desta onda a janela nem tinha como
    saber de quem era o silêncio.
    """
    monitor_da_bancada.reconciliar()
    leitura = monitor_da_bancada.leitura(_CABO_A)
    assert leitura is not None
    assert leitura.saida_muda is True
    assert leitura.sink == _SINK_A
    # `Mute: no` no vizinho: nada a dizer, e a leitura nem se materializa —
    # a regra da casa de nunca inventar presença de sensor para dizer "nada".
    assert monitor_da_bancada.leitura(_CABO_B) is None
    # E o rádio, de quem não se sabe nada, também fica fora.
    assert monitor_da_bancada.leitura(_RADIO_A) is None


def test_sem_pactl_o_monitor_nao_inventa_placa(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Degradar não pode virar chute: sem `pactl`, ninguém ganha sink.

    O casamento por USB depende de uma leitura a mais (`pactl list sinks`
    longo). Se ela falhar, o monitor tem de voltar ao conservador de antes —
    nunca cair na aritmética do "um para um" com dado pela metade.
    """
    monkeypatch.setattr(mm, "usb_pai_por_uniq", lambda _uniqs: dict(_USB_POR_UNIQ))
    monitor = mm.MicMonitor(
        runner=lambda cmd: (_SINKS_CURTO if cmd[-1] == "short" else ""),
        capturador=lambda *a, **k: None,
        auto_supervisao=False,
    )
    monitor.set_ativo(True)
    monitor.set_controles((_CABO_A, _CABO_B))
    monitor.reconciliar()
    assert monitor.sink_de(_CABO_A) == ""
    assert monitor.sink_de(_CABO_B) == ""

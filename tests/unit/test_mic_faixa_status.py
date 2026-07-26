"""MIC-FAIXA-01 — a faixa de microfone do rodapé da aba Status.

A queixa que abriu esta entrega foi visual e curta: *"falta o espaço do
medidor de microfone"*. Com quatro controles na mesa, a aba Status não tinha
medidor em cartão nenhum — porque o módulo antigo morava DENTRO do card e
sumia quando não havia source atribuível, e "sumiu" é indistinguível de "não
existe".

A regra que a mantenedora fixou depois, e que estes testes travam:

> *"o mic é pra aparecer mesmo não tendo conectado por cabo. O espaço deve
> ficar lá; sabemos que não funciona sem cabo, mas o espaço deve estar sempre
> presente."*

Então **a faixa é permanente**. Nenhum estado do sistema a esconde: sem
source, por rádio com a ponte desligada, com o nome ambíguo ou sem controle
nenhum, o que muda é o TEXTO. E o caso feliz tem de funcionar de verdade — no
cabo, com o mudo do firmware liberado, o nível se mexe.

Os dois testes que a validação cobra estão aqui com estes nomes:

* `test_a_faixa_existe_com_zero_microfones_disponiveis`
* `test_a_faixa_mostra_nivel_quando_ha_source_atribuida`

Tudo com GTK REAL e com o glade REAL: o defeito desta área é de LIGAÇÃO (a
peça, o `MicMeter`, sempre funcionou), então testar a peça isolada não
provaria nada.
"""
# ruff: noqa: E402 — gi.require_version precisa vir antes dos imports de gi
from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import gi

gi.require_version("Gtk", "3.0")

import pytest

# CI headless sem libcairo: os medidores da faixa são DrawingArea.
pytest.importorskip("cairo")

from gi.repository import Gtk

from hefesto_dualsense4unix.app.actions.status_actions import (
    TEXTO_MIC_SEM_CONTROLE,
    StatusActionsMixin,
)
from hefesto_dualsense4unix.app.mic_monitor import (
    MOTIVO_AGUARDANDO,
    MOTIVO_AMBIGUA,
    MOTIVO_MEDINDO,
    MOTIVO_MUDO_FIRMWARE,
    MOTIVO_MUDO_ROTA,
    MOTIVO_PONTE_DESLIGADA,
    MOTIVO_SEM_CAPTURA,
    MOTIVO_SEM_FONTE,
    MOTIVO_SEM_PORTA,
    LeituraMic,
    MicMonitor,
    audio_do_entry,
    diagnosticar_mic,
    escolher_fonte,
    portas_de_captura,
)

MAIN_GLADE = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "hefesto_dualsense4unix"
    / "gui"
    / "main.glade"
)

#: Os quatro MACs da mesa de validação (últimos seis hex distintos).
MACS = (
    "aa:bb:cc:c3:11:f0",
    "aa:bb:cc:c3:11:f1",
    "aa:bb:cc:c3:11:f2",
    "aa:bb:cc:c3:11:f3",
)
#: O que a ponte de áudio por Bluetooth publica para cada um deles.
PONTES = tuple(f"hefesto_dualsense_bt_c311f{n}" for n in range(4))

#: Nome de uma source ALSA de DualSense no cabo (string USB real).
SOURCE_USB = (
    "alsa_input.usb-Sony_Interactive_Entertainment_DualSense_Wireless_"
    "Controller-00.iec958-stereo"
)


# ---------------------------------------------------------------------------
# Dublês
# ---------------------------------------------------------------------------


class _MonitorFake:
    """Só o que a faixa consome do `MicMonitor`: fontes, portas e leitura."""

    def __init__(
        self,
        fontes: list[str] | None = None,
        leituras: dict[str, LeituraMic] | None = None,
        portas: dict[str, bool] | None = None,
    ) -> None:
        self._fontes = fontes
        self._leituras = leituras or {}
        self._portas = portas or {}
        self.controles: tuple[str, ...] = ()
        self.transportes: dict[str, str] = {}

    def fontes(self) -> list[str] | None:
        return self._fontes

    def portas(self) -> dict[str, bool]:
        return self._portas

    def leitura(self, uniq: str) -> LeituraMic | None:
        return self._leituras.get(uniq)

    def set_controles(
        self, uniqs: tuple[str, ...], transportes: dict[str, str] | None = None
    ) -> None:
        self.controles = uniqs
        self.transportes = dict(transportes or {})


class _Host(StatusActionsMixin):
    """A mixin de status com o glade REAL — inclusive a faixa do rodapé."""

    def __init__(self) -> None:
        self.builder = Gtk.Builder()
        self.builder.add_from_file(str(MAIN_GLADE))
        janela = Gtk.OffscreenWindow()
        raiz = self.builder.get_object("root_box")
        pai = raiz.get_parent()
        if pai is not None:
            pai.remove(raiz)
        janela.add(raiz)
        janela.show_all()
        self._status_cards = {}
        self._status_card_keys = []
        self._mic_faixa_linhas = []
        self._mic_faixa_keys = None

    @property
    def faixa(self) -> Any:
        return self.builder.get_object("status_mic_frame")

    @property
    def slot(self) -> Any:
        return self.builder.get_object("status_mic_slot")

    def linhas(self) -> list[Any]:
        """Filhos do slot na ordem de LEITURA (o grid devolve invertido)."""
        grid = self.slot
        return sorted(
            grid.get_children(),
            key=lambda w: (
                grid.child_get_property(w, "top-attach"),
                grid.child_get_property(w, "left-attach"),
            ),
        )

    def textos(self) -> list[str]:
        return [linha.motivo.get_text() for linha in self._mic_faixa_linhas]


@pytest.fixture()
def host() -> _Host:
    return _Host()


def _entry(pos: int = 0, **kw: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "index": pos,
        "connected": True,
        "transport": "bt",
        "is_primary": pos == 0,
        "uniq": MACS[pos],
        "player_slot": pos + 1,
        "battery_pct": 70,
        "lightbar_rgb": [40, 40, 80],
        "lightbar_on": True,
        "lightbar_source": "sysfs",
        "inputs": None,
        "vpad_backend": "uhid",
        "vpad_motivo": None,
    }
    base.update(kw)
    return base


def _state(*controllers: dict[str, Any], **topo: Any) -> dict[str, Any]:
    st: dict[str, Any] = {
        "connected": bool(controllers),
        "transport": "bt",
        "active_profile": "vitoria",
        "native_mode": False,
        "controllers": list(controllers),
    }
    st.update(topo)
    return st


# ---------------------------------------------------------------------------
# 1. A faixa é PERMANENTE — este é o teste que morde contra o sumiço
# ---------------------------------------------------------------------------


def test_a_faixa_existe_com_zero_microfones_disponiveis(host: _Host) -> None:
    """Quatro controles por rádio, ponte desligada, nenhuma source publicada.

    É o cenário-alvo da casa e o pior caso do medidor: não há absolutamente
    nada para medir. A faixa continua na tela, com uma linha por controle, e
    cada linha DIZ o porquê em vez de sumir.
    """
    host._mic_monitor = _MonitorFake(fontes=[])
    estado = _state(*(_entry(i) for i in range(4)), bt_mic={"running": False})

    host._render_live_state(estado)

    assert host.faixa.get_visible() is True
    assert host.slot.get_visible() is True
    assert len(host._mic_faixa_linhas) == 4
    for linha in host._mic_faixa_linhas:
        assert linha.box.get_visible() is True
        # Nulo honesto: o medidor fica VAZIO, não em zero fingindo silêncio.
        assert linha.medidor._inativo is True
        assert not any(linha.medidor._historico)
    for texto in host.textos():
        assert "ponte" in texto.lower()
        assert "hefesto mic bt" in texto


def test_a_faixa_existe_sem_controle_nenhum_na_mesa(host: _Host) -> None:
    """Zero controles não zera a faixa: o rodapé ocupa o mesmo lugar sempre."""
    host._mic_monitor = _MonitorFake(fontes=[])

    host._render_live_state(_state())

    assert host.faixa.get_visible() is True
    linhas = host.linhas()
    assert len(linhas) == 1
    assert linhas[0].get_text() == TEXTO_MIC_SEM_CONTROLE
    assert linhas[0].get_visible() is True


def test_a_faixa_sobrevive_a_troca_do_conjunto_de_controles(host: _Host) -> None:
    """Reconstruir as linhas não pode ser a porta dos fundos do sumiço.

    O rebuild acontece quando a mesa muda; se ele deixasse a faixa vazia (ou
    escondida) por um tique, a área do microfone voltaria a ser algo que "às
    vezes existe".
    """
    host._mic_monitor = _MonitorFake(fontes=[])

    host._render_live_state(_state(*(_entry(i) for i in range(4))))
    host._render_live_state(_state(_entry(0)))
    assert host.faixa.get_visible() is True
    assert len(host._mic_faixa_linhas) == 1

    host._render_live_state(_state())
    assert host.faixa.get_visible() is True
    assert len(host.linhas()) == 1

    host._render_live_state(_state(*(_entry(i) for i in range(2))))
    assert host.faixa.get_visible() is True
    assert len(host._mic_faixa_linhas) == 2
    assert all(linha.box.get_visible() for linha in host._mic_faixa_linhas)


# ---------------------------------------------------------------------------
# 2. O caso feliz: no cabo, com o mudo liberado, o nível se mexe
# ---------------------------------------------------------------------------


def test_a_faixa_mostra_nivel_quando_ha_source_atribuida(host: _Host) -> None:
    """Um DualSense no cabo, mudo do firmware liberado: a onda anda.

    É o critério de aceite da mantenedora. A leitura entra pelo mesmo caminho
    do produto (o `MicMonitor` da mixin), e o que se afere é o MEDIDOR da
    faixa — não a função pura que calcula o nível.
    """
    host._mic_monitor = _MonitorFake(
        fontes=[SOURCE_USB],
        leituras={MACS[0]: LeituraMic(nivel=0.62, muted=False, fonte=SOURCE_USB)},
        portas={SOURCE_USB: True},
    )
    estado = _state(
        _entry(0, transport="usb", audio={"mic_mudo": False, "mic_mudo_desejado": None})
    )

    host._render_live_state(estado)

    linha = host._mic_faixa_linhas[0]
    assert linha.medidor._inativo is False
    assert linha.medidor._nivel == pytest.approx(0.62)
    assert "ATIVO" in linha.selo.get_label()
    assert linha.motivo.get_text() == ""


def test_a_onda_da_faixa_anda_a_cada_tique(host: _Host) -> None:
    """Níveis diferentes deixam barras diferentes — a forma É o dado."""
    monitor = _MonitorFake(fontes=[SOURCE_USB], portas={SOURCE_USB: True})
    host._mic_monitor = monitor
    estado = _state(_entry(0, transport="usb"))

    for nivel in (0.1, 0.8, 0.35):
        monitor._leituras[MACS[0]] = LeituraMic(nivel=nivel, muted=False)
        host._render_live_state(estado)

    historico = host._mic_faixa_linhas[0].medidor._historico
    assert historico[-3:] == pytest.approx((0.1, 0.8, 0.35))


def test_do_pactl_ao_medidor_sem_atalho(host: _Host) -> None:
    """A fiação inteira, com o `MicMonitor` de verdade e só o `pactl` dublado.

    Este é o teste que prova a entrega: `pactl` devolve a source do controle,
    o `parec` devolve PCM, o monitor reconcilia, e a FAIXA mostra nível. Se
    qualquer elo da corrente for arrancado — a descoberta, a atribuição, o
    acessor `fontes()`, a chamada em `_render_live_state` — ele reprova.
    """
    curto = f"12\t{SOURCE_USB}\tPipeWire\ts16le 1ch 48000Hz\tRUNNING\n"
    bloco = (b"\x00\x40" * 1600)  # PCM s16le com amplitude bem acima do piso

    class _Stdout:
        def __init__(self) -> None:
            self._restam = [bloco]

        def read(self, _n: int) -> bytes:
            return self._restam.pop(0) if self._restam else b""

    class _Proc:
        def __init__(self) -> None:
            self.stdout = _Stdout()

        def terminate(self) -> None:
            pass

        def wait(self, timeout: float | None = None) -> int:
            return 0

    def runner(argv: list[str]) -> str:
        if "get-source-mute" in argv:
            return "Mute: no"
        if "json" in argv:
            return "[]"
        return curto

    monitor = MicMonitor(
        runner=runner, capturador=lambda _f: _Proc(), auto_supervisao=False
    )
    host._mic_monitor = monitor
    monitor.set_ativo(True)
    monitor.set_controles((MACS[0],))
    monitor.reconciliar()
    # A captura publica de uma thread; espera curta e determinística.
    for _ in range(200):
        if monitor.leitura(MACS[0]) is not None:
            break
        threading.Event().wait(0.01)

    host._render_live_state(_state(_entry(0, transport="usb")))

    linha = host._mic_faixa_linhas[0]
    assert linha.medidor._inativo is False
    assert linha.medidor._nivel > 0.5
    assert "ATIVO" in linha.selo.get_label()
    monitor.stop()


# ---------------------------------------------------------------------------
# 3. Quando não mede, a faixa diz QUAL é a causa (e cada uma tem cura própria)
# ---------------------------------------------------------------------------


def _diag(**kw: Any) -> Any:
    base: dict[str, Any] = {
        "fontes": [],
        "uniq": MACS[0],
        "uniqs_com_audio": list(MACS),
        "transporte": "usb",
    }
    base.update(kw)
    return diagnosticar_mic(**base)


def test_sem_descoberta_ainda_a_faixa_nao_afirma_ausencia() -> None:
    """`fontes` None = o monitor não procurou ainda — não é "não há mic".

    Sem esta distinção, cada troca de aba piscaria um falso "não há microfone"
    até a primeira descoberta.
    """
    assert _diag(fontes=None).motivo == MOTIVO_AGUARDANDO


def test_mudo_no_firmware_vem_antes_de_tudo_e_cita_a_posse() -> None:
    """Camada 3 primeiro: com ela ligada, o resto da cadeia entrega silêncio.

    E a cura precisa avisar da posse: `mic unmute` faz o Hefesto segurar o
    registrador do mudo, e enquanto isso o botão físico do controle não
    responde (medido ao vivo — ela apertou e o LED não apagou).
    """
    diag = _diag(fontes=[SOURCE_USB], uniqs_com_audio=[MACS[0]], mic_mudo=True)

    assert diag.motivo == MOTIVO_MUDO_FIRMWARE
    assert diag.nivel is None
    assert diag.muted is True
    assert "release" in diag.cura


def test_a_cura_do_firmware_muda_com_quem_esta_segurando() -> None:
    """`mic_mudo_desejado` existe no state_full só para esta escolha."""
    do_hefesto = _diag(mic_mudo=True, mic_mudo_desejado=True).cura
    do_kernel = _diag(mic_mudo=True, mic_mudo_desejado=None).cura

    assert "Hefesto está segurando" in do_hefesto
    assert "botão de microfone do controle" in do_kernel
    assert do_hefesto != do_kernel


def test_por_radio_sem_ponte_a_faixa_explica_a_ponte() -> None:
    diag = _diag(transporte="bt", ponte_bt_ligada=False)

    assert diag.motivo == MOTIVO_PONTE_DESLIGADA
    assert diag.nivel is None
    assert "hefesto mic bt" in diag.cura


def test_por_radio_com_a_ponte_de_pe_o_motivo_deixa_de_ser_a_ponte() -> None:
    """Ponte ligada e mesmo assim sem source: a causa é outra, e a faixa muda."""
    diag = _diag(transporte="bt", ponte_bt_ligada=True)

    assert diag.motivo == MOTIVO_SEM_FONTE


def test_fonte_que_nao_da_para_atribuir_recusa_em_vez_de_chutar() -> None:
    """Dois DualSense no cabo publicam nomes indistinguíveis.

    A recusa é deliberada (mostrar o mic do controle errado é pior), e a
    faixa a EXPLICA em vez de sumir. Cura nenhuma: aqui o projeto não sabe
    resolver, e inventar um gesto seria pior que admitir.
    """
    diag = _diag(fontes=[SOURCE_USB, SOURCE_USB + "-b"], uniqs_com_audio=list(MACS))

    assert diag.motivo == MOTIVO_AMBIGUA
    assert diag.nivel is None
    assert diag.cura == ""


def test_source_sem_porta_de_captura_e_a_camada_2_medida() -> None:
    """O critério é a PORTA, e a cura NÃO nomeia perfil nem o doctor.

    Medido ao vivo em 26/07 com o DualSense no cabo: no perfil
    `input:analog-stereo` — o que a MIC-USB-01 mandava usar — a source abre,
    desmutada e a 100%, e entrega 327.680 bytes com pico 0, com
    `active_port: null` e lista de portas vazia; no `input:iec958-stereo`, que
    a sprint chamava de errado, a mesma gravação dá pico 4606. Este teste
    morde se alguém trouxer de volta o "iec958 é S/PDIF sem sinal, cure com
    --fix-mic": aquilo mandaria a mantenedora quebrar o que funciona.
    """
    diag = _diag(
        fontes=[SOURCE_USB],
        uniqs_com_audio=[MACS[0]],
        portas={SOURCE_USB: False},
    )

    assert diag.motivo == MOTIVO_SEM_PORTA
    assert diag.nivel is None
    assert "porta de captura" in diag.texto
    assert "iec958" not in diag.cura
    assert "analog" not in diag.cura
    assert "fix-mic" not in diag.cura


def test_porta_desconhecida_nao_vira_acusacao() -> None:
    """`pactl` sem `-f json` devolve dicionário vazio — e isso é "não sei"."""
    diag = _diag(
        fontes=[SOURCE_USB],
        uniqs_com_audio=[MACS[0]],
        portas={},
        leitura=LeituraMic(nivel=0.3, muted=False),
    )

    assert diag.motivo == MOTIVO_MEDINDO


def test_mudo_por_rota_e_a_camada_1_e_a_cura_cita_a_fonte() -> None:
    diag = _diag(
        fontes=[SOURCE_USB],
        uniqs_com_audio=[MACS[0]],
        portas={SOURCE_USB: True},
        leitura=LeituraMic(nivel=0.0, muted=True, fonte=SOURCE_USB),
    )

    assert diag.motivo == MOTIVO_MUDO_ROTA
    assert diag.nivel is None
    assert SOURCE_USB in diag.cura


def test_fonte_atribuida_sem_bloco_ainda_nao_e_silencio() -> None:
    """Entre achar a source e o primeiro bloco do `parec` há um vão honesto."""
    diag = _diag(fontes=[SOURCE_USB], uniqs_com_audio=[MACS[0]], leitura=None)

    assert diag.motivo == MOTIVO_SEM_CAPTURA
    assert diag.nivel is None


def test_medindo_carrega_o_nivel_e_so_ele_carrega() -> None:
    """Nulo honesto: `nivel` só é número no estado que de fato mede."""
    medindo = _diag(
        fontes=[SOURCE_USB],
        uniqs_com_audio=[MACS[0]],
        leitura=LeituraMic(nivel=0.42, muted=False),
    )

    assert medindo.motivo == MOTIVO_MEDINDO
    assert medindo.nivel == pytest.approx(0.42)
    assert medindo.medindo is True

    outros = [
        _diag(fontes=None),
        _diag(mic_mudo=True),
        _diag(transporte="bt"),
        _diag(fontes=[SOURCE_USB, "outra"]),
        _diag(fontes=[SOURCE_USB], uniqs_com_audio=[MACS[0]]),
        _diag(
            fontes=[SOURCE_USB],
            uniqs_com_audio=[MACS[0]],
            portas={SOURCE_USB: False},
        ),
    ]
    assert [d.nivel for d in outros] == [None] * len(outros)
    assert not any(d.medindo for d in outros)


def test_audio_do_entry_le_as_duas_chaves_com_none_significando_coisas() -> None:
    assert audio_do_entry({}) == (None, None)
    assert audio_do_entry({"audio": "lixo"}) == (None, None)
    assert audio_do_entry({"audio": {"mic_mudo": True}}) == (True, None)
    assert audio_do_entry(
        {"audio": {"mic_mudo": False, "mic_mudo_desejado": True}}
    ) == (False, True)


# ---------------------------------------------------------------------------
# 4. A faixa mostra o motivo NA TELA (fiação do diagnóstico até o rótulo)
# ---------------------------------------------------------------------------


def test_o_motivo_do_firmware_chega_ao_rotulo_da_linha(host: _Host) -> None:
    host._mic_monitor = _MonitorFake(fontes=[SOURCE_USB], portas={SOURCE_USB: True})
    estado = _state(
        _entry(0, transport="usb", audio={"mic_mudo": True, "mic_mudo_desejado": None})
    )

    host._render_live_state(estado)

    linha = host._mic_faixa_linhas[0]
    assert "camada 3" in linha.motivo.get_text()
    assert "MUDO" in linha.selo.get_label()
    assert linha.medidor._inativo is True


def test_cada_controle_recebe_o_diagnostico_do_seu_proprio_transporte(host: _Host) -> None:
    """Um no cabo medindo e três por rádio sem ponte, na mesma faixa."""
    host._mic_monitor = _MonitorFake(
        fontes=[SOURCE_USB],
        leituras={MACS[0]: LeituraMic(nivel=0.5, muted=False)},
        portas={SOURCE_USB: True},
    )
    estado = _state(
        _entry(0, transport="usb"),
        _entry(1),
        _entry(2),
        _entry(3),
        bt_mic={"running": False},
    )

    host._render_live_state(estado)

    textos = host.textos()
    assert textos[0] == ""
    assert host._mic_faixa_linhas[0].medidor._nivel == pytest.approx(0.5)
    for texto in textos[1:]:
        assert "hefesto mic bt" in texto


def test_o_selo_espera_em_vez_de_cravar_ativo(host: _Host) -> None:
    """Mute ainda não lido: medidor sim, "ATIVO" não."""
    host._mic_monitor = _MonitorFake(
        fontes=[SOURCE_USB],
        leituras={MACS[0]: LeituraMic(nivel=0.3, muted=None)},
        portas={SOURCE_USB: True},
    )

    host._render_live_state(_state(_entry(0, transport="usb")))

    linha = host._mic_faixa_linhas[0]
    assert "ATIVO" not in linha.selo.get_label()
    assert "MUDO" not in linha.selo.get_label()
    assert linha.medidor._nivel == pytest.approx(0.3)


def test_a_faixa_recebe_os_controles_do_monitor(host: _Host) -> None:
    """Sem `set_controles`, o monitor não abriria captura nenhuma.

    E o TRANSPORTE tem de ir junto: a faixa recebe o mapa direto do payload,
    mas quem abre o `parec` é o monitor. Se só a faixa soubesse o transporte,
    os dois atribuiriam diferente — a faixa diria que há source para aquele
    controle e a captura nunca seria aberta, deixando a linha parada em
    "abrindo a captura..." para sempre.
    """
    monitor = _MonitorFake(fontes=[])
    host._mic_monitor = monitor

    host._render_live_state(
        _state(_entry(0, transport="usb"), _entry(1), _entry(2), _entry(3))
    )

    assert monitor.controles == MACS
    assert monitor.transportes == {
        MACS[0]: "usb",
        MACS[1]: "bt",
        MACS[2]: "bt",
        MACS[3]: "bt",
    }


# ---------------------------------------------------------------------------
# 5. MIC-BT-01: a atribuição aprende o nome que a NOSSA ponte escreve
# ---------------------------------------------------------------------------


def test_a_ponte_bt_casa_com_os_seis_hex_do_mac() -> None:
    """Quatro pontes, quatro controles: cada um acha a sua.

    Era o buraco do cenário-alvo: a regra do bluez exige nome começando com
    `bluez` (o da ponte começa com `hefesto`) e a do um para um exige UM
    controle candidato. Com quatro na mesa, nenhuma das duas valia.
    """
    achados = [escolher_fonte(list(PONTES), mac, list(MACS)) for mac in MACS]

    assert achados == list(PONTES)


def test_a_ponte_bt_nao_casa_por_hex_solto() -> None:
    """A armadilha do próprio prefixo: `_so_hex("hefesto_dualsense_bt_")` é
    `efedaeeb`, oito dígitos de lixo. Um casamento por substring de hex
    daria a source ao controle cujo MAC terminasse em `efedae`."""
    assert escolher_fonte(list(PONTES), "aa:bb:cc:ef:ed:ae", ["aa:bb:cc:ef:ed:ae"]) in (
        None,
        *PONTES,
    )
    assert escolher_fonte([PONTES[0]], "aa:bb:cc:ef:ed:ae", ["x", "y"]) is None


def test_o_sufixo_da_ponte_so_aceita_seis_hex() -> None:
    """Regra fixada na PEÇA, e o motivo de estar aqui é medido.

    Arrancar a validação de "seis dígitos hex" de `_sufixo_hex_da_ponte` não
    derruba nenhum teste de costura: quem compara é `_fonte_da_ponte`, e a
    cauda do MAC é sempre seis hex, então um sufixo diferente já falharia na
    igualdade. A mutação é EQUIVALENTE naquele ponto — e é exatamente por isso
    que a regra fica travada aqui: ela é a fronteira do que a função promete,
    e a próxima pessoa a reusá-la não terá a igualdade a protegê-la.
    """
    from hefesto_dualsense4unix.app.mic_monitor import _sufixo_hex_da_ponte

    assert _sufixo_hex_da_ponte("hefesto_dualsense_bt_c311f0") == "c311f0"
    assert _sufixo_hex_da_ponte("hefesto_dualsense_bt_C311F0") == "c311f0"
    assert _sufixo_hex_da_ponte("hefesto_dualsense_bt_hidraw9") is None
    assert _sufixo_hex_da_ponte("hefesto_dualsense_bt_c311f") is None
    assert _sufixo_hex_da_ponte("hefesto_dualsense_bt_") is None
    assert _sufixo_hex_da_ponte("alsa_input.usb-Sony") is None


def test_a_ponte_sem_hid_uniq_nao_atribui_nada() -> None:
    """Controle sem `HID_UNIQ` vira `hefesto_dualsense_bt_hidraw9` — e desse
    nome não sai atribuição, então a recusa honesta continua valendo."""
    assert (
        escolher_fonte(
            ["hefesto_dualsense_bt_hidraw9"], MACS[0], ["x", "y"]
        )
        is None
    )


def test_dois_controles_com_a_mesma_cauda_nao_escolhem_um_ao_acaso() -> None:
    """A ambiguidade nasce na ponte, que publicaria o MESMO nome para os dois."""
    # Dois OUIs sintéticos permitidos, mesmos três últimos bytes: é o único
    # jeito de forjar a colisão sem sair das faixas que o gate de anonimato
    # aceita (02:fe / aa:bb:cc / e8:47:3a).
    gemeos = ["aa:bb:cc:c3:11:f0", "e8:47:3a:c3:11:f0"]

    assert escolher_fonte([PONTES[0]], gemeos[0], gemeos) is None


def test_o_um_para_um_recorta_por_transporte_na_mesa_mista() -> None:
    """Um no cabo e três por rádio: o do cabo tem dono, os outros não.

    Sem o recorte, a única source ALSA da mesa tinha quatro candidatos e a
    regra 3 nunca disparava — a faixa dizia "não dá para saber de quem é"
    justamente para o controle que estava no cabo, com o microfone
    funcionando. E o recorte não afrouxa nada: uma source `alsa_*` não pode
    ser de um controle por rádio, porque por rádio não existe placa de áudio.
    """
    vias = {MACS[0]: "usb", MACS[1]: "bt", MACS[2]: "bt", MACS[3]: "bt"}

    assert escolher_fonte([SOURCE_USB], MACS[0], list(MACS), vias) == SOURCE_USB
    for mac in MACS[1:]:
        assert escolher_fonte([SOURCE_USB], mac, list(MACS), vias) is None


def test_dois_no_cabo_continuam_ambiguos_mesmo_com_transporte() -> None:
    """O recorte não pode virar chute: dois no cabo e uma source é empate."""
    vias = {MACS[0]: "usb", MACS[1]: "usb"}

    assert escolher_fonte([SOURCE_USB], MACS[0], list(MACS[:2]), vias) is None


def test_sem_transporte_conhecido_a_regra_volta_a_ser_a_de_antes() -> None:
    """Transporte desconhecido nunca inventa uma atribuição a mais."""
    assert escolher_fonte([SOURCE_USB], MACS[0], [MACS[0]], None) == SOURCE_USB
    assert escolher_fonte([SOURCE_USB], MACS[0], list(MACS), {}) is None


def test_reconciliar_na_mesa_mista_abre_a_captura_de_quem_esta_no_cabo() -> None:
    """A fiação do recorte por transporte, até o `parec`.

    O monitor tem de atribuir EXATAMENTE como a faixa diagnostica: se ele
    ignorasse o transporte, a faixa mostraria "medindo" para um controle cuja
    captura nunca foi aberta.
    """
    curto = f"12\t{SOURCE_USB}\tPipeWire\ts16le 1ch\tRUNNING\n"
    abertos: list[str] = []

    class _Proc:
        stdout = None

        def terminate(self) -> None:
            pass

    def capturador(fonte: str) -> Any:
        abertos.append(fonte)
        return _Proc()

    monitor = MicMonitor(
        runner=lambda argv: "" if "json" in argv else curto,
        capturador=capturador,
        auto_supervisao=False,
    )
    monitor.set_ativo(True)
    monitor.set_controles(
        MACS, {MACS[0]: "usb", MACS[1]: "bt", MACS[2]: "bt", MACS[3]: "bt"}
    )

    monitor.reconciliar()

    assert abertos == [SOURCE_USB]
    monitor.stop()


def test_reconciliar_com_quatro_pontes_abre_as_quatro_capturas() -> None:
    """A fiação, não a peça: é `reconciliar()` quem tem de atribuir as quatro.

    A MIC-BT-01 pede explicitamente este teste — chamar só `escolher_fonte`
    passaria mesmo com o monitor incapaz de usar a regra nova.
    """
    curto = "".join(
        f"{i}\t{nome}\tPipeWire\ts16le 1ch\tRUNNING\n"
        for i, nome in enumerate(PONTES)
    )
    abertos: list[str] = []

    class _Proc:
        stdout = None

        def terminate(self) -> None:
            pass

    def capturador(fonte: str) -> Any:
        abertos.append(fonte)
        return _Proc()

    monitor = MicMonitor(
        runner=lambda argv: "" if "json" in argv else curto,
        capturador=capturador,
        auto_supervisao=False,
    )
    monitor.set_ativo(True)
    monitor.set_controles(MACS)

    monitor.reconciliar()

    assert sorted(abertos) == sorted(PONTES)
    monitor.stop()


# ---------------------------------------------------------------------------
# 6. O DESENHO do medidor inativo (o pixel, não só o estado interno)
# ---------------------------------------------------------------------------


def _pintar(medidor: Any, largura: int = 72, altura: int = 22) -> Any:
    """Desenha o medidor num surface de memória e devolve o surface.

    O widget precisa estar ALOCADO: `_on_draw` lê
    `get_allocated_width/height`, e um DrawingArea fora de janela mede 1x1 —
    o desenho sairia num pixel e o teste não veria nada.
    """
    import cairo

    janela = Gtk.OffscreenWindow()
    medidor.set_size_request(largura, altura)
    janela.add(medidor)
    janela.show_all()
    while Gtk.events_pending():
        Gtk.main_iteration()
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, largura, altura)
    ctx = cairo.Context(surface)
    medidor._on_draw(medidor, ctx)
    surface.flush()
    janela.remove(medidor)
    return surface


def _pixel(surface: Any, x: int, y: int) -> tuple[int, int, int, int]:
    dados = bytes(surface.get_data())
    passo = surface.get_stride()
    base = y * passo + x * 4
    azul, verde, vermelho, alfa = dados[base : base + 4]
    return (vermelho, verde, azul, alfa)


def test_o_medidor_inativo_pinta_espaco_vazio_e_nao_barras() -> None:
    """O pixel, não a flag: inativo desenha a trilha inteira, sem barra.

    Este é o teste que morde contra "só troquei a flag e continuei desenhando
    as barras do piso" — que na tela é exatamente o silêncio inventado que a
    casa proíbe. No topo do medidor, inativo tem trilha pintada; medindo baixo
    não tem nada (as barras do piso ficam coladas na base).
    """
    from hefesto_dualsense4unix.app.widgets.sensor_widgets import (
        COR_TRILHA,
        MicMeter,
        hex_para_rgb,
    )

    inativo = MicMeter()
    inativo.set_inativo()
    topo_inativo = _pixel(_pintar(inativo), 36, 3)

    medindo = MicMeter()
    medindo.set_nivel(0.0)  # silêncio COM captura: as barras do piso aparecem
    topo_medindo = _pixel(_pintar(medindo), 36, 3)
    base_medindo = _pixel(_pintar(medindo), 36, 21)

    trilha = tuple(round(canal * 255) for canal in hex_para_rgb(COR_TRILHA))
    assert topo_inativo[:3] == trilha
    assert topo_inativo[3] == 255
    # Medindo em silêncio: o topo fica VAZIO e a base tem barra — é a linha
    # baixa e contínua que diz "estou vivo e nada entra".
    assert topo_medindo[3] == 0
    assert base_medindo[3] == 255


# ---------------------------------------------------------------------------
# 7. A porta de captura, lida do `pactl -f json`
# ---------------------------------------------------------------------------


_JSON_SOURCES = """
[
  {"name": "alsa_input.usb-Sony_DualSense-00.iec958-stereo",
   "active_port": "iec958-stereo-input",
   "ports": [{"name": "iec958-stereo-input"}],
   "properties": {"alsa.card": "1"}},
  {"name": "alsa_input.usb-Sony_DualSense-00.analog-stereo",
   "active_port": null,
   "ports": [],
   "properties": {"alsa.card": "1"}},
  {"name": "hefesto_dualsense_bt_c311f0",
   "active_port": null,
   "ports": [],
   "properties": {"device.description": "ponte"}}
]
"""


def test_portas_de_captura_separa_porta_ativa_de_porta_ausente() -> None:
    portas = portas_de_captura(_JSON_SOURCES)

    assert portas["alsa_input.usb-Sony_DualSense-00.iec958-stereo"] is True
    assert portas["alsa_input.usb-Sony_DualSense-00.analog-stereo"] is False


def test_a_ponte_virtual_fica_fora_da_conta_de_portas() -> None:
    """`module-pipe-source` não tem porta por construção. Aplicar a regra nela
    acusaria de quebrada justamente a ponte que está funcionando."""
    assert "hefesto_dualsense_bt_c311f0" not in portas_de_captura(_JSON_SOURCES)


@pytest.mark.parametrize("bruto", ["", "não é json", "{}", "null"])
def test_json_ilegivel_vira_nao_sei_e_nao_vira_acusacao(bruto: str) -> None:
    assert portas_de_captura(bruto) == {}


def test_o_monitor_publica_as_portas_que_descobriu() -> None:
    """Fiação: sem guardar as portas, o diagnóstico da camada 2 nunca chega."""
    curto = f"12\t{SOURCE_USB}\tPipeWire\ts16le 1ch\tRUNNING\n"
    json_bruto = (
        '[{"name": "' + SOURCE_USB + '", "active_port": null, "ports": [],'
        ' "properties": {"alsa.card": "1"}}]'
    )

    class _Proc:
        stdout = None

        def terminate(self) -> None:
            pass

    monitor = MicMonitor(
        runner=lambda argv: json_bruto if "json" in argv else curto,
        capturador=lambda _f: _Proc(),
        auto_supervisao=False,
    )
    monitor.set_ativo(True)
    monitor.set_controles((MACS[0],))

    monitor.reconciliar()

    assert monitor.fontes() == [SOURCE_USB]
    assert monitor.portas() == {SOURCE_USB: False}
    monitor.stop()


def test_o_monitor_so_diz_ter_procurado_depois_de_procurar() -> None:
    """`fontes()` None antes da primeira descoberta — o "não sei" do início."""
    monitor = MicMonitor(
        runner=lambda _argv: "", capturador=lambda _f: None, auto_supervisao=False
    )

    assert monitor.fontes() is None

    monitor.set_ativo(True)
    monitor.set_controles((MACS[0],))
    monitor.reconciliar()

    assert monitor.fontes() == []
    monitor.stop()

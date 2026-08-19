"""Microfone do DualSense na aba Status (S2): selo ATIVO/MUDO + medidor.

Sem controle conectado não existe source de áudio para medir, então tudo é
dublê: o `pactl` vira uma string de saída e o `parec`, um objeto com
`stdout.read()`. O que estes testes travam:

  * a atribuição source -> controle é CONSERVADORA: dois DualSense no cabo
    publicam sources indistinguíveis pelo nome, e mostrar o mic do controle
    errado é pior que não mostrar nenhum;
  * o selo só existe com o mute LIDO — `None` não vira "ATIVO";
  * sair da aba Status derruba a captura (o `parec` não fica segurando o
    microfone da usuária com ninguém olhando);
  * nada aqui levanta: sem `pactl`/`parec`/source, a leitura é None e o
    módulo some, na linha do tema que abre sem CSS.
"""
from __future__ import annotations

import array
import threading
import time
from typing import Any

import pytest

from hefesto_dualsense4unix.app import mic_monitor
from hefesto_dualsense4unix.app.mic_monitor import (
    LeituraMic,
    MicMonitor,
    _Captura,
    escolher_fonte,
    fontes_dualsense,
    muted_de_saida,
    nivel_para_fracao,
    rms_de_pcm_s16le,
)
from hefesto_dualsense4unix.app.widgets.sensor_widgets import selo_mic

# Saída real do `pactl list sources short` (índice, nome, driver, formato,
# estado — separados por TAB), com um DualSense no meio.
_PACTL = (
    "645\talsa_output.pci-0000_0c_00.4.iec958-stereo.monitor\tPipeWire\ts32le 2ch\tIDLE\n"
    "646\talsa_input.pci-0000_0c_00.4.analog-stereo\tPipeWire\ts32le 2ch\tSUSPENDED\n"
    "651\talsa_input.usb-Sony_Interactive_Entertainment_Wireless_Controller-00."
    "mono-fallback\tPipeWire\ts16le 1ch\tSUSPENDED\n"
)


# ---------------------------------------------------------------------------
# Descoberta e atribuição da source
# ---------------------------------------------------------------------------


def test_fontes_dualsense_pega_so_a_captura_do_controle() -> None:
    assert fontes_dualsense(_PACTL) == [
        "alsa_input.usb-Sony_Interactive_Entertainment_Wireless_Controller-00."
        "mono-fallback"
    ]


def test_monitor_de_saida_nunca_entra() -> None:
    """`.monitor` é o áudio que SAI pelo alto-falante do controle.

    Medir aquilo faria o "nível do mic" subir com a trilha do jogo.
    """
    saida = (
        "12\talsa_output.usb-Sony_Interactive_Entertainment_Wireless_Controller-00."
        "analog-stereo.monitor\tPipeWire\ts16le\tIDLE\n"
    )
    assert fontes_dualsense(saida) == []


def test_linha_malformada_nao_derruba_a_descoberta() -> None:
    assert fontes_dualsense("lixo sem tab\n\n") == []


def test_um_controle_uma_fonte_casa() -> None:
    fontes = fontes_dualsense(_PACTL)
    assert escolher_fonte(fontes, "aabbcc010203", ["aabbcc010203"]) == fontes[0]


def test_dois_controles_no_cabo_nao_chutam() -> None:
    """A string USB é a mesma nos dois; não há como distinguir pelo nome."""
    fontes = fontes_dualsense(_PACTL)

    assert escolher_fonte(fontes, "aabbcc010203", ["aabbcc010203", "aabbcc010204"]) is None


def test_fonte_bluez_casa_pelo_mac_mesmo_com_varios_controles() -> None:
    fontes = ["bluez_input.AA_BB_CC_01_02_03", "bluez_input.AA_BB_CC_01_02_04"]

    escolhida = escolher_fonte(fontes, "aabbcc010204", ["aabbcc010203", "aabbcc010204"])

    assert escolhida == "bluez_input.AA_BB_CC_01_02_04"


def test_nome_alsa_nunca_casa_por_acaso_com_um_mac() -> None:
    """O "hex" que sobra de um nome ALSA é lixo de palavra, não MAC.

    A busca por MAC é restrita a nomes `bluez` de propósito: sem isso, um
    casamento por acaso apontaria o mic do controle errado.
    """
    fontes = fontes_dualsense(_PACTL)
    # "eae" existe dentro de "...Entertainment..."; com dois candidatos, a
    # regra do "um para um" não vale e a resposta certa é não saber.
    assert escolher_fonte(fontes, "eae", ["eae", "outro"]) is None


# ---------------------------------------------------------------------------
# Mute e selo
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("saida", "esperado"),
    [("Mute: yes", True), ("Mute: no", False), ("Mudo: não", None), ("", None)],
)
def test_muted_de_saida(saida: str, esperado: bool | None) -> None:
    """A saída traduzida ("Mudo: não") vira None: é sinal de que o LC_ALL=C
    não pegou, e chutar ali seria inventar estado de microfone."""
    assert muted_de_saida(saida) is esperado


def test_selo_ativo_e_mudo_usam_as_cores_do_guia() -> None:
    assert selo_mic(False) == ("ATIVO", "#50fa7b", "#21222c")
    # LEGIBILIDADE-01: o texto do selo MUDO era `#6272a4` sobre a trilha
    # `#2b2d3a` — 2,85:1, o pior par da interface, e justamente a palavra que
    # diz se o microfone está aberto. Passou a `#c8ccda` (8,51:1).
    assert selo_mic(True) == ("MUDO", "#2b2d3a", "#c8ccda")


def test_selo_sem_mute_lido_nao_afirma_ativo() -> None:
    """`None` = ainda não li. Cravar "ATIVO" diria que o mic está aberto sem
    ter lido nada — é a diferença entre não saber e afirmar."""
    assert selo_mic(None) is None


# ---------------------------------------------------------------------------
# Nível
# ---------------------------------------------------------------------------


def _pcm(amplitude: int, amostras: int = 800) -> bytes:
    return array.array("h", [amplitude] * amostras).tobytes()


def test_rms_de_silencio_e_zero() -> None:
    assert rms_de_pcm_s16le(_pcm(0)) == 0.0


def test_rms_de_fundo_de_escala_e_um() -> None:
    assert rms_de_pcm_s16le(_pcm(32767)) == pytest.approx(1.0, abs=1e-3)


def test_rms_de_bloco_truncado_nao_vira_pico() -> None:
    """Um `read()` cortado no encerramento do `parec` não pode acender o
    medidor no talo."""
    assert rms_de_pcm_s16le(b"") == 0.0
    assert rms_de_pcm_s16le(b"\x01") == 0.0


def test_escala_em_db_e_nao_linear() -> None:
    """Escala linear é inútil num medidor de voz: fala normal ficaria em 3%
    de barra e só um grito encheria."""
    meia_escala = nivel_para_fracao(rms_de_pcm_s16le(_pcm(16384)))

    assert 0.85 < meia_escala < 1.0
    assert nivel_para_fracao(0.0) == 0.0
    assert nivel_para_fracao(1.0) == pytest.approx(1.0)


def test_abaixo_do_piso_o_medidor_fica_vazio() -> None:
    assert nivel_para_fracao(0.0005) == 0.0  # ~-66 dBFS


# ---------------------------------------------------------------------------
# Captura (thread) e ciclo de vida
# ---------------------------------------------------------------------------


class _Stdout:
    def __init__(self, blocos: list[bytes]) -> None:
        self._blocos = list(blocos)

    def read(self, _n: int) -> bytes:
        return self._blocos.pop(0) if self._blocos else b""


class _Proc:
    def __init__(self, blocos: list[bytes]) -> None:
        self.stdout = _Stdout(blocos)
        self.encerrado = False

    def terminate(self) -> None:
        self.encerrado = True

    def wait(self, timeout: float | None = None) -> int:
        return 0


def test_captura_publica_nivel_e_mute() -> None:
    publicados: list[LeituraMic] = []
    proc = _Proc([_pcm(16384)])
    captura = _Captura(
        uniq="aa",
        fonte="fonte-x",
        publicar=lambda _u, leitura: publicados.append(leitura),
        runner=lambda _argv: "Mute: yes",
        capturador=lambda _f: proc,
        parar_global=threading.Event(),
        mute_intervalo_s=1.0,
    )

    captura._loop()  # síncrono: sem corrida de thread no teste

    assert len(publicados) == 1
    assert publicados[0].muted is True
    assert publicados[0].nivel > 0.8
    assert proc.encerrado is True


def test_captura_sem_parec_nao_levanta_e_nao_publica() -> None:
    """Sem `parec` no PATH o módulo de microfone simplesmente não aparece."""
    publicados: list[Any] = []
    captura = _Captura(
        uniq="aa",
        fonte="fonte-x",
        publicar=lambda _u, leitura: publicados.append(leitura),
        runner=lambda _argv: "",
        capturador=lambda _f: None,
        parar_global=threading.Event(),
        mute_intervalo_s=1.0,
    )

    captura._loop()

    assert publicados == []


@pytest.fixture(autouse=True)
def _sem_conhecimento_de_usb(monkeypatch: pytest.MonkeyPatch) -> None:
    """Este arquivo NÃO sabe nada de USB — e agora diz isso em voz alta.

    MIC-QUE-DEPENDIA-DA-MAQUINA-01 (19/08/2026). Os testes daqui dublam o
    `pactl` e o capturador, e ainda assim `MicMonitor.reconciliar` chamava
    `usb_pai_por_uniq`, que lê o **sysfs de verdade** da máquina que estiver
    rodando. O resultado passava a depender do host: verde aqui, vermelho no
    runner do CI, sempre no mesmo teste. Medido — com um casamento por USB que
    dá dono ao nó de áudio, `reconciliar` devolve ZERO captura e a asserção
    `1 == 0` sai igualzinha à do CI.

    O casamento por USB tem casa própria (`test_a_placa_e_o_controle_pelo_usb_pai`),
    com sysfs dublado inteiro. Aqui ele fica de fora por escolha, não por
    esquecimento — que é a diferença entre um dublê e um buraco.
    """
    monkeypatch.setattr(mic_monitor, "usb_pai_por_uniq", lambda _uniqs, **_kw: {})


def _esperar_capturas(abertos: list[str], quantas: int, limite_s: float = 5.0) -> None:
    """Espera as capturas NASCEREM — elas abrem em thread, não no `reconciliar`.

    `_Captura.iniciar()` dá `Thread.start()` e volta na hora; quem chama o
    `capturador` é o `_loop` já na thread. Afirmar sobre `abertos` na linha
    seguinte é afirmar sobre uma corrida — e o teste passava porque o GIL
    costuma ceder rápido, não porque o código garantisse algo.

    A espera é pelo EFEITO, com teto: cinco segundos é mil vezes o que ela leva
    aqui, e ainda assim termina em milissegundos no caso bom.
    """
    limite = time.monotonic() + limite_s
    while len(abertos) < quantas and time.monotonic() < limite:
        time.sleep(0.002)


def _monitor(saida_pactl: str = _PACTL) -> tuple[MicMonitor, list[str]]:
    """Monitor com supervisora manual; `abertos` registra as sources pedidas."""
    abertos: list[str] = []

    def capturador(fonte: str) -> Any:
        abertos.append(fonte)
        return _Proc([])  # EOF na hora: a thread nasce e morre sem publicar

    monitor = MicMonitor(
        runner=lambda argv: saida_pactl if "list" in argv else "Mute: no",
        capturador=capturador,
        auto_supervisao=False,
    )
    return monitor, abertos


def test_aba_escondida_nao_captura_nada() -> None:
    """A captura só existe com a aba Status à vista — não é otimização."""
    monitor, abertos = _monitor()
    monitor.set_controles(("aabbcc010203",))

    monitor.reconciliar()

    assert abertos == []
    assert monitor.leitura("aabbcc010203") is None


def test_aba_visivel_abre_a_captura_do_controle() -> None:
    monitor, abertos = _monitor()
    monitor.set_ativo(True)
    monitor.set_controles(("aabbcc010203",))

    monitor.reconciliar()
    _esperar_capturas(abertos, 1)

    assert len(abertos) == 1
    assert "Wireless_Controller" in abertos[0]


def test_sair_da_aba_derruba_a_captura() -> None:
    monitor, _abertos = _monitor()
    monitor.set_ativo(True)
    monitor.set_controles(("aabbcc010203",))
    monitor.reconciliar()
    assert monitor._capturas != {}

    monitor.set_ativo(False)
    monitor.reconciliar()

    assert monitor._capturas == {}
    assert monitor.leitura("aabbcc010203") is None


def test_sem_fonte_atribuivel_nao_abre_nada() -> None:
    monitor, abertos = _monitor(saida_pactl="")
    monitor.set_ativo(True)
    monitor.set_controles(("aabbcc010203",))

    monitor.reconciliar()

    assert abertos == []
    assert monitor.leitura("aabbcc010203") is None


def test_stop_e_idempotente() -> None:
    monitor, _abertos = _monitor()
    monitor.set_ativo(True)
    monitor.set_controles(("aabbcc010203",))
    monitor.reconciliar()

    monitor.stop()
    monitor.stop()

    assert monitor._capturas == {}

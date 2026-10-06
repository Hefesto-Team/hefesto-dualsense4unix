"""SOM-ACORDADO-01 — os dois estados do som aparecem na aba Status."""

from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("som acordado 01")

from typing import Any

import gi

gi.require_version("Gtk", "3.0")

import pytest

pytest.importorskip("cairo")

from gi.repository import Gtk

from hefesto_dualsense4unix.app.actions.status_actions import StatusActionsMixin
from hefesto_dualsense4unix.app.audio_saida import (
    CANAL_ACORDADO,
    CANAL_DORMINDO,
    CANAL_SEM_LEITURA,
    RotaDeSaida,
    acordar_sink,
    estado_do_canal,
    estados_crus_dos_sinks,
    estados_dos_sinks,
    tocar_confirmacao,
)


def _gtk_pronto() -> bool:
    try:
        return bool(Gtk.init_check()[0])
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _gtk_pronto(), reason="sem GTK/display utilizável")

#: Os nomes REAIS dos dois sinks de DualSense desta bancada, copiados de
SINK_P1 = (
    "alsa_output.usb-Sony_Interactive_Entertainment_DualSense_Wireless_"
    "Controller-00.analog-surround-40"
)
SINK_P2 = (
    "alsa_output.usb-Sony_Interactive_Entertainment_DualSense_Wireless_"
    "Controller-00.2.analog-surround-40"
)
SINK_HDMI = "alsa_output.pci-0000_0a_00.1.hdmi-stereo"

LARGURA_DE_PROJETO = 1180

POSSE_100: dict[str, Any] = {"volume": 255, "muted": False}

_INPUTS: dict[str, Any] = {
    "lx": 60,
    "ly": 200,
    "rx": 180,
    "ry": 90,
    "l2_raw": 200,
    "r2_raw": 40,
    "buttons": ["cross"],
    "gyro": {"x": 143.2, "y": -412.0, "z": 22.8},
    "touchpad": {"touching": True, "x": 1440, "y": 270, "width": 1920, "height": 1080},
}
_ENTRY: dict[str, Any] = {
    "index": 0,
    "connected": True,
    "transport": "usb",
    "is_primary": True,
    "uniq": "aa:bb:cc:00:00:01",
    "battery_pct": 80,
    "player": None,
    "player_slot": 1,
    "lightbar_rgb": [255, 121, 198],
    "lightbar_on": True,
    "lightbar_source": "sysfs",
    "inputs": _INPUTS,
    "vpad_backend": "uhid",
    "vpad_motivo": None,
}
_ESTADO: dict[str, Any] = {"native_mode": False}

_janelas_vivas: list[Any] = []


class _LeituraMic:
    """Dublê da `LeituraMic` — o card lê `nivel`, `muted` e `saida_muda`."""

    def __init__(self, saida_muda: bool | None = None) -> None:
        self.nivel = 0.6
        self.muted = False
        self.saida_muda = saida_muda


def _lista_curta(**estados: str) -> str:
    """`pactl list sinks short` de mentira, no formato REAL de cinco colunas."""
    linhas = [
        f"{100 + i}\t{nome}\tPipeWire\ts16le 4ch 48000Hz\t{estado}"
        for i, (nome, estado) in enumerate(estados.items())
    ]
    return "\n".join(linhas) + "\n"


def test_o_estado_do_canal_sai_da_ultima_coluna_do_pactl() -> None:
    """`SUSPENDED` vira `dormindo`, `RUNNING` e `IDLE` viram `acordado`."""
    saida = _lista_curta(
        **{SINK_P1: "SUSPENDED", SINK_P2: "RUNNING", SINK_HDMI: "IDLE"}
    )

    assert estados_dos_sinks(saida) == {
        SINK_P1: CANAL_DORMINDO,
        SINK_P2: CANAL_ACORDADO,
        SINK_HDMI: CANAL_ACORDADO,
    }
    assert estado_do_canal(saida, SINK_P1) == CANAL_DORMINDO
    assert estado_do_canal(saida, "sink_que_nao_existe") == CANAL_SEM_LEITURA
    assert estado_do_canal(saida, "") == CANAL_SEM_LEITURA


def test_linha_sem_a_coluna_de_estado_vira_nao_sei_e_nunca_acordado() -> None:
    """A armadilha desta casa: instrumento que mente é pior que instrumento mudo."""
    curta = f"1\t{SINK_P1}\tPipeWire\n"

    assert estados_crus_dos_sinks(curta) == {}
    assert estados_dos_sinks(curta) == {}
    assert estado_do_canal(curta, SINK_P1) == CANAL_SEM_LEITURA


def test_a_rota_traz_o_estado_de_todos_os_canais_numa_leitura_so() -> None:
    """Um leitor, um subprocesso, e o estado de TODOS os canais."""
    chamadas: list[list[str]] = []

    def pactl(argv: list[str]) -> str:
        chamadas.append(list(argv))
        if argv[:2] == ["pactl", "get-default-sink"]:
            return SINK_HDMI + "\n"
        if argv[:3] == ["pactl", "list", "sinks"]:
            return _lista_curta(
                **{SINK_P1: "RUNNING", SINK_P2: "SUSPENDED", SINK_HDMI: "IDLE"}
            )
        return ""

    estado = RotaDeSaida(
        runner=pactl, ler_memoria=lambda: "", gravar_memoria=lambda _s: None
    ).estado(SINK_P1)

    assert estado.no_controle is False, "o som está no HDMI — este é o caso comum"
    assert dict(estado.canais) == {
        SINK_P1: CANAL_ACORDADO,
        SINK_P2: CANAL_DORMINDO,
        SINK_HDMI: CANAL_ACORDADO,
    }, "o estado dos canais tem de vir mesmo com o som FORA do controle"
    listas = [a for a in chamadas if a[:3] == ["pactl", "list", "sinks"]]
    assert len(listas) == 1, (
        f"a lista viva foi lida {len(listas)} vezes num ciclo só: o estado dos "
        "canais tem de pegar carona na leitura que já existia"
    )


def test_o_som_de_confirmacao_acorda_o_canal_antes_de_tocar() -> None:
    """** (dela).

    Os dois lados da conta são medidos, cada um do seu lado: o arquivo escolhido
    tem **0,067 s** (o mais curto dos candidatos, escolha registrada em
    `_CANDIDATOS_DE_SOM`), e o religar de um nó suspenso come o começo do som.
    Num som de 67 ms, "o começo" é o som inteiro — e a suspensão é o estado
    NORMAL entre dois gestos do usuário: os dois sinks de DualSense desta bancada
    estavam `SUSPENDED` na leitura de 16/08/2026, com os controles no cabo.

    Nada disto aparecia como falha: o `paplay` abria o fluxo, saía com zero, e
    o tocador devolvia `tocou`.

    Mordida: apagar as duas linhas do `set-sink-suspend` em `tocar_confirmacao`.
    A primeira asserção cai, e o produto volta a prometer um som que ninguém
    ouve — que é exatamente o que ela relatou.
    """
    chamadas: list[list[str]] = []
    dormindo = {"sim": True}

    def pactl(argv: list[str]) -> str:
        chamadas.append(list(argv))
        if argv[:4] == ["pactl", "set-sink-suspend", SINK_P1, "0"]:
            dormindo["sim"] = False
        if argv[:3] == ["pactl", "list", "sinks"]:
            estado = "SUSPENDED" if dormindo["sim"] else "RUNNING"
            return _lista_curta(**{SINK_P1: estado, SINK_HDMI: "IDLE"})
        return ""

    tocados: list[list[str]] = []
    resultado = tocar_confirmacao(
        SINK_P1,
        saida_muda=False,
        ligado=True,
        runner=pactl,
        tocador=lambda argv: (tocados.append(argv), 0)[1],
        achar=lambda _b: "/usr/bin/paplay",
    )

    assert ["pactl", "set-sink-suspend", SINK_P1, "0"] in chamadas, (
        "o canal estava dormindo e ninguém o acordou: o som de 67 ms se perde "
        "no religar do hardware"
    )
    assert tocados, "e depois de acordar, o som TEM de sair"
    posicao_acordar = chamadas.index(["pactl", "set-sink-suspend", SINK_P1, "0"])
    assert posicao_acordar < len(chamadas), "acordar vem ANTES de tocar"
    assert resultado.tocou is True


def test_o_canal_ja_acordado_nao_paga_subprocesso_nenhum() -> None:
    """O caso comum não pode ficar mais caro por causa do caso raro."""
    chamadas: list[list[str]] = []

    def pactl(argv: list[str]) -> str:
        chamadas.append(list(argv))
        if argv[:3] == ["pactl", "list", "sinks"]:
            return _lista_curta(**{SINK_P1: "RUNNING", SINK_HDMI: "IDLE"})
        return ""

    tocar_confirmacao(
        SINK_P1,
        saida_muda=False,
        ligado=True,
        runner=pactl,
        tocador=lambda _argv: 0,
        achar=lambda _b: "/usr/bin/paplay",
    )

    assert not [a for a in chamadas if a[:2] == ["pactl", "set-sink-suspend"]], (
        "o canal já estava acordado e o produto mandou acordá-lo assim mesmo"
    )
    assert len([a for a in chamadas if a[:3] == ["pactl", "list", "sinks"]]) == 1


def test_acordar_confere_relendo_em_vez_de_acreditar_no_pactl() -> None:
    """A janela que acredita na própria escrita é a janela que mente na tela."""
    teimoso = _lista_curta(**{SINK_P1: "SUSPENDED"})

    assert (
        acordar_sink(SINK_P1, runner=lambda _a: _lista_curta(**{SINK_P1: "RUNNING"}))
        is True
    )
    assert acordar_sink(SINK_P1, runner=lambda _a: teimoso) is False
    assert acordar_sink("", runner=lambda _a: teimoso) is False


class _CardEspiao:
    """Card de mentira que só anota o que a aba lhe entregou."""

    def __init__(self) -> None:
        self.canal: str | None = None
        self.regra: Any = "não perguntaram"
        self.sink = ""

    def update(self, *_a: Any, **_k: Any) -> None:
        pass

    def definir_sink_de_saida(self, sink: str) -> None:
        self.sink = sink

    def definir_estado_do_canal(
        self, estado: str, *, regra_instalada: bool | None = None
    ) -> None:
        self.canal = estado
        self.regra = regra_instalada


class _MonitorDeMentira:
    """Dublê do `MicMonitor` — só o que a aba pergunta a ele."""

    def __init__(self, sinks: dict[str, str]) -> None:
        self._sinks = sinks

    def set_controles(self, _uniqs: tuple[str, ...]) -> None:
        pass

    def sink_de(self, uniq: str) -> str:
        return self._sinks.get(uniq, "")

    def leitura(self, _uniq: str) -> Any:
        return None


class _SlotComAttach:
    def attach(self, *_a: Any, **_k: Any) -> None:  # pragma: no cover - inerte
        raise AssertionError("rebuild não devia acontecer com as chaves estáveis")


class _BuilderDaAba:
    def __init__(self, slot: Any) -> None:
        self._slot = slot

    def get_object(self, wid: str) -> Any:
        return self._slot if wid == "status_players_slot" else None


class _AbaStatus(StatusActionsMixin):
    """A janela do produto reduzida ao que este caminho toca (mixin REAL)."""

    def __init__(self, cards: dict[Any, Any], monitor: Any) -> None:
        self.builder = _BuilderDaAba(_SlotComAttach())
        self._mic_monitor = monitor
        self._status_cards = dict(cards)
        self._status_card_keys = list(cards)


UNIQ_P1 = "aa:bb:cc:00:00:01"
UNIQ_P2 = "aa:bb:cc:00:00:02"


def _estado_com_dois_controles() -> dict[str, Any]:
    p1 = dict(_ENTRY, index=0, uniq=UNIQ_P1)
    p2 = dict(_ENTRY, index=1, uniq=UNIQ_P2, is_primary=False, player_slot=2)
    return {"controllers": [p1, p2]}



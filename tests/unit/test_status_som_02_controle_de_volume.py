"""SOM-02 — o alto-falante que FUNCIONA: controle deslizante, mudo e devolução."""

from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("status som 02 controle de volume")

import contextlib
from typing import Any, Final

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")

import pytest

pytest.importorskip("cairo")

from gi.repository import Gdk, Gtk

from hefesto_dualsense4unix.app import ipc_bridge
from hefesto_dualsense4unix.core.speaker_scale import (
    _SPEAKER_REG_MUDO_ATE,
    _SPEAKER_REG_SATURA_EM,
    fracao_do_volume,
    percentual_do_volume,
    volume_do_percentual,
)

LARGURA_DA_TELA_DELA = 1870


def _gtk_pronto() -> bool:
    try:
        return bool(Gtk.init_check()[0])
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _gtk_pronto(), reason="sem GTK/display utilizável"
)

_INPUTS: dict[str, Any] = {
    "lx": 60,
    "ly": 200,
    "rx": 180,
    "ry": 90,
    "l2_raw": 200,
    "r2_raw": 40,
    "buttons": ["cross"],
    "gyro": {"x": 143.2, "y": -412.0, "z": 22.8},
    "touchpad": {
        "touching": True,
        "x": 1440,
        "y": 270,
        "width": 1920,
        "height": 1080,
    },
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
    "lightbar_rgb": [97, 53, 131],
    "lightbar_on": True,
    "lightbar_source": "sysfs",
    "inputs": _INPUTS,
    "vpad_backend": "uhid",
    "vpad_motivo": None,
    "audio": {
        "fone_plugado": False,
        "mic_externo": False,
        "mic_mudo": False,
        "mic_mudo_desejado": None,
    },
}
_ESTADO: dict[str, Any] = {"native_mode": False}

_ESTADO_ALTO: dict[str, Any] = {
    "native_mode": False,
    "rumble_ff": {
        "per_vpad": [
            {"player": 1, "motion_streaming": True, "motion_hz": 250.0}
        ]
    },
}


class _LeituraMic:
    """Dublê da `LeituraMic` — o card lê `nivel`, `muted` e (E5) `saida_muda`."""

    def __init__(self, saida_muda: bool | None = None) -> None:
        self.nivel = 0.6
        self.muted = False
        if saida_muda is not None:
            self.saida_muda = saida_muda


_janelas_vivas: list[Any] = []

_CICLOS_ATE_ALOCAR: Final[int] = 200


def _assentar(janela: Any, widget: Any) -> None:
    """Roda o laço de eventos ATÉ o widget receber alocação de verdade."""
    for _ in range(_CICLOS_ATE_ALOCAR):
        while Gtk.events_pending():
            Gtk.main_iteration()
        if widget.get_allocated_width() > 1 and widget.get_allocated_height() > 1:
            return
        with contextlib.suppress(Exception):
            janela.get_surface()
        janela.queue_resize()

    with contextlib.suppress(Exception):
        janela.realize()
        largura, altura = janela.get_size_request()
        if largura > 1 and altura > 1:
            aloc = Gdk.Rectangle()
            aloc.x, aloc.y, aloc.width, aloc.height = 0, 0, largura, altura
            janela.size_allocate(aloc)
            while Gtk.events_pending():
                Gtk.main_iteration()


def _entry_com(speaker: dict[str, Any] | None, **extra: Any) -> dict[str, Any]:
    """Uma entrada de ``state_full.controllers`` com (ou sem) a chave `speaker`.

    Sem posse a chave NÃO EXISTE — é assim que o daemon publica, e é o estado
    normal de qualquer sessão em que ninguém mexeu no volume.
    """
    entrada = dict(_ENTRY)
    entrada.update(extra)
    if speaker is None:
        entrada.pop("speaker", None)
    else:
        entrada["speaker"] = speaker
    return entrada


class _Pedidos:
    """Registra o que a interface MANDOU — e por onde mandou."""

    def __init__(self) -> None:
        self.agendados: list[Any] = []
        self.chamadas: list[dict[str, Any]] = []

    def run_in_thread(self, fn: Any, _ok: Any, _err: Any = None) -> None:
        self.agendados.append(fn)

    def speaker_set(self, **kwargs: Any) -> bool:
        self.chamadas.append(kwargs)
        return True

    def rodar(self) -> None:
        pendentes, self.agendados = self.agendados, []
        for fn in pendentes:
            fn()


@pytest.fixture
def pedidos(monkeypatch: pytest.MonkeyPatch) -> _Pedidos:
    espiao = _Pedidos()
    monkeypatch.setattr(ipc_bridge, "run_in_thread", espiao.run_in_thread)
    monkeypatch.setattr(ipc_bridge, "speaker_set", espiao.speaker_set)
    return espiao


class _AltoFalanteDeMentira:
    """O ``set_speaker_volume`` do backend como a SPRINT o mediu — sem guardas."""

    def __init__(self) -> None:
        self.volumes: list[int | None] = [None, None, None, None]
        self.pref: int | None = None

    def aplicar(self, pedido: dict[str, Any]) -> None:
        if pedido.get("release"):
            self.volumes = [None, None, None, None]
            self.pref = None
            return
        volume = pedido.get("volume")
        muted = pedido.get("muted")
        pref = self.pref
        if volume is not None:
            pref = max(0, min(255, int(volume)))
        if pref is None:
            pref = 0
        self.pref = pref
        efetivo = 0 if muted else pref
        self.volumes[0] = efetivo
        self.volumes[1] = efetivo

    def estado(self) -> dict[str, Any] | None:
        """O que o daemon publicaria em ``state_full`` (`speaker_state_for`)."""
        if self.volumes[1] is None:
            return None
        efetivo = int(self.volumes[1])
        base = self.pref if self.pref is not None else efetivo
        return {"volume": max(0, min(255, int(base))), "muted": efetivo == 0}


PISO_DO_TRILHO_PX: Final[int] = 100


def test_o_curso_inteiro_do_controle_cabe_na_faixa_que_soa() -> None:
    """Medição no hardware em 01/08: o registrador é fortemente NÃO-LINEAR.

    Tom de 1 kHz no sink, o microfone do próprio DualSense como instrumento,
    Goertzel no bin de 1 kHz, sink e mixer ALSA travados e só o registrador
    variando. A curva (registrador cru -> magnitude)::

        0 -> 3,9    13 -> 5,3    26 -> 3,1    38 -> 6,2     <- tudo MUDO
        51 -> 35    64 -> 172    76 -> 687                  <- a faixa audível
        102 -> 8759  128 -> 8488  255 -> 8793               <- saturado

    Com a régua linear ``pct * 255 / 100`` que a SOM-02 usava, o controle
    deslizante que a SOM-03 acabou de alargar para 240px seria 240px de curso
    em que **os primeiros 15 % emudecem, tudo o que se ouve cabe entre 15 % e
    40 %, e os últimos 60 % não fazem nada**. Alargar o controle sem isto seria
    dar mais pixels ao trecho inerte.

    Este teste cobra as três pontas do remapeamento de APRESENTAÇÃO:

    1. o topo do curso é a saturação e não passa dela — nenhum pedaço do curso
       cai na região em que o volume não muda mais;
    2. nenhuma porcentagem acima de zero cai na região MUDA — pedir 1 % e
       receber silêncio seria o mesmo defeito, do outro lado;
    3. o curso é monótono e percorre a faixa audível inteira.

    A mordida: devolver ``volume_do_percentual`` a ``round(pct * 255 / 100)``
    derruba (1) com 255 contra uma saturação em 102 e (2) com 1 % virando um
    registrador 3, que a curva mede como mudo.
    """
    assert volume_do_percentual(100) == _SPEAKER_REG_SATURA_EM, (
        f"100 % da tela manda {volume_do_percentual(100)} cru e o registrador "
        f"satura em {_SPEAKER_REG_SATURA_EM}: a diferença é curso do controle "
        "que não muda nada no ouvido"
    )
    for pct in range(1, 101):
        bruto = volume_do_percentual(pct)
        assert bruto > _SPEAKER_REG_MUDO_ATE, (
            f"{pct} % da tela manda o registrador {bruto}, que a medição de "
            f"01/08 põe na região MUDA (até {_SPEAKER_REG_MUDO_ATE}): esse "
            "pedaço do curso não faz som nenhum"
        )
        assert bruto <= _SPEAKER_REG_SATURA_EM, (
            f"{pct} % da tela manda {bruto}, acima da saturação"
        )
    percurso = [volume_do_percentual(p) for p in range(0, 101)]
    assert percurso == sorted(percurso), "o curso deixou de ser monótono"


def test_zero_por_cento_e_mudo_de_verdade_e_nao_o_piso_da_faixa_util() -> None:
    """A exceção que o remapeamento NÃO pode engolir."""
    assert volume_do_percentual(0) == 0
    assert volume_do_percentual(-5) == 0
    assert percentual_do_volume(0) == 0


def test_a_barra_que_le_e_o_controle_que_manda_nunca_se_contradizem() -> None:
    """A trava do requisito: leitura e comando dizem o MESMO número."""
    for pct in range(0, 101):
        bruto = volume_do_percentual(pct)
        de_volta = percentual_do_volume(bruto)
        assert abs(de_volta - pct) <= 1, (
            f"a tela manda {pct} %, o registrador guarda {bruto} e a barra "
            f"relê {de_volta} %: leitura e comando falam réguas diferentes"
        )
        assert fracao_do_volume(bruto) * 100 == pytest.approx(
            percentual_do_volume(bruto), abs=0.5
        )



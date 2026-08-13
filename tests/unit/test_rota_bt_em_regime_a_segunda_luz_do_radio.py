"""ROTA-BT-EM-REGIME-01 — por rádio, a cor do perfil sai TAMBÉM pelo hidraw.

O DEFEITO, medido na bancada dela em 12/08/2026
===============================================
Por Bluetooth o produto tinha UMA rota de LED **em regime** — o `sysfs` — e é
justamente a que perde. As duas linhas de `docs/data/ensaios.csv`, medidas no
mesmo instante com os mesmos três controles:

- `cor-rota-sysfs-com-steam` → **não obedece**. Com a Steam viva, escrever
  `multi_intensity` não muda a barra;
- `cor-rota-hidraw-com-steam` → o report `0x31` escrito no `/dev/hidraw*`
  **pintou os três**. Literal dela: *"todos tão magenta"*.

O caderno de eliminação já julga a ROTA como **e-a-causa** nesta linha
(`scripts/eliminacao.py`, `luz.lightbar.cor@dualsense [radio]`).

A rota existia e não era alcançável: o fallback pydualsense que o
`_for_each_led` e o `_write_partial_output` carregam é CÓDIGO MORTO por rádio,
porque `_suppress_leds` é True para todo handle BT (`LIGHTBAR-BT-NEVER-01`) e o
`report_thread` remove os bits de LED. O `reescrever_lightbar_por_hidraw`
(GATILHO-DA-COR-01) sabia escrever o report certo, mas só era chamado pelo
gatilho de CONEXÃO — trocar de perfil ou mexer na cor na GUI não passava por
ele.

O QUE ESTE ARQUIVO TRAVA
========================
- por rádio, `set_led` e `set_player_leds` emitem o `0x31` estreito, **além**
  de tentarem o sysfs (que continua sendo a primeira rota);
- o caminho do PERFIL/hotplug (`_write_partial_output`) faz o mesmo;
- por CABO nada sai — lá a barra obedece (ensaio `lightbar-usb-1`) e escrever
  seria trabalho sem defeito para curar. É a resposta à regra da casa
  ("a hipótese tem de explicar o que JÁ funcionava");
- em Modo Nativo / Conexão Nativa (Sony) é **no-op**: o dono é o jogo;
- o report NÃO carrega `RELEASE_LEDS` (0x08, o culpado 7/7 do
  `LIGHTBAR-BT-CULPADO-01`) nem os bits de SETUP/BRILHO do `flag2` (o
  `LIGHTBAR-BT-KEEPALIVE-01` mediu que reengatá-los trava a exibição).

O método é o do `test_gatilho_da_cor_escrita.py`: o método exercitado é o DO
PRODUTO, emprestado a um objeto mínimo. Um dublê que reimplementasse a regra
mediria o dublê.
"""
from __future__ import annotations

import threading
from typing import Any

from hefesto_dualsense4unix.core.backend_pydualsense import (
    PyDualSenseController,
    _DesiredOutput,
)

#: Offsets DENTRO do envelope 0x31 (o common começa em [3]).
POS_FLAG0 = 3 + 0
POS_FLAG1 = 3 + 1
POS_FLAG2 = 3 + 38
POS_PLAYERS = 3 + 43
POS_R = 3 + 44
POS_G = 3 + 45
POS_B = 3 + 46

FLAG1_LIGHTBAR = 0x04
FLAG1_RELEASE_LEDS = 0x08
FLAG1_PLAYER = 0x10


class _Handle:
    """Espelha o handle no que a escrita usa: `conType` + `writeReport` + `light`."""

    def __init__(self, transporte: str = "bt") -> None:
        self.conType = type(
            "Con", (), {"name": "BT_31" if transporte == "bt" else "USB_01"}
        )()
        self.reports: list[list[int]] = []
        self.light = type("Light", (), {})()
        self.light.setColorI = lambda *_a: None  # type: ignore[method-assign]
        self.audio = type("Audio", (), {})()

    def writeReport(self, dados: list[int]) -> None:  # noqa: N802 (API do upstream)
        self.reports.append(list(dados))


class _NoSysfs:
    """Nó de LED que ACEITA a escrita — o caso em que o sysfs "deu certo"...

    ...e a barra mesmo assim não muda, que é exatamente o que a bancada mediu
    com a Steam viva. Se a segunda rota dependesse do sysfs FALHAR, ela nunca
    dispararia no defeito real.
    """

    def __init__(self) -> None:
        self.escritas = 0

    def set_rgb(self, *_rgb: int, **_kw: Any) -> bool:
        self.escritas += 1
        return True

    def set_players(self, *_a: Any, **_kw: Any) -> bool:
        self.escritas += 1
        return True


class _BackendMinimo:
    """Só o necessário para exercitar as rotas de LED sem hardware."""

    def __init__(
        self,
        handles: dict[str, Any],
        *,
        mute: bool = False,
        sysfs: dict[str, Any] | None = None,
    ) -> None:
        self._handles = handles
        self._output_mute = mute
        self._io_lock = threading.RLock()
        self._sysfs = sysfs if sysfs is not None else {}
        self._output_target_key: str | None = None
        self._suprimir_player_leds = False
        self._desired = _DesiredOutput()

    def _record_desired_locked(self, _alvo: str | None, _campos: dict) -> None:
        return None


_METODOS = (
    "_for_each_led",
    "_pintar_por_hidraw_bt",
    "_write_partial_output",
    "_apply_trigger",
    "_pode_escrever_player_leds",
    "set_led",
    "set_player_leds",
    "_detect_transport",
)


def _backend(handles: dict[str, Any], **kw: Any) -> Any:
    alvo = _BackendMinimo(handles, **kw)
    for nome in _METODOS:
        metodo = getattr(PyDualSenseController, nome)
        # `_detect_transport` e `_apply_trigger` são staticmethods.
        if nome in ("_detect_transport", "_apply_trigger"):
            setattr(alvo, nome, metodo)
        else:
            setattr(alvo, nome, metodo.__get__(alvo))
    return alvo


def test_a_cor_por_radio_sai_pelo_hidraw_mesmo_com_o_sysfs_aceitando() -> None:
    """O defeito inteiro em um teste.

    `cor-rota-sysfs-com-steam`: o `multi_intensity` ACEITA a escrita e a barra
    não muda. Por isso a segunda rota não pode depender de o sysfs falhar.
    """
    handle = _Handle("bt")
    no = _NoSysfs()
    backend = _backend({"aa:bb": handle}, sysfs={"aa:bb": no})

    backend.set_led((255, 0, 255))

    assert no.escritas == 1, "a primeira rota (sysfs) tem de continuar sendo tentada"
    assert len(handle.reports) == 1, "a segunda rota (hidraw) não saiu"
    report = handle.reports[0]
    assert report[0] == 0x31 and len(report) == 78
    assert report[POS_FLAG1] & FLAG1_LIGHTBAR, "o bit da lightbar não foi autorizado"
    assert (report[POS_R], report[POS_G], report[POS_B]) == (255, 0, 255)


def test_o_numero_do_jogador_tambem_sai_por_radio() -> None:
    """São DUAS luzes, e a Steam repinta as duas (pergunta dela, 12/08)."""
    handle = _Handle("bt")
    backend = _backend({"aa:bb": handle})

    backend.set_player_leds((False, False, True, False, False))

    assert len(handle.reports) == 1
    report = handle.reports[0]
    assert report[POS_FLAG1] & FLAG1_PLAYER, "o bit do número não foi autorizado"
    assert report[POS_PLAYERS] == 0b00100, "o padrão --x-- do Player 1"


def test_o_perfil_e_o_hotplug_tambem_usam_a_segunda_rota() -> None:
    """`_write_partial_output` é o caminho do perfil e do `_reapply_desired`."""
    handle = _Handle("bt")
    backend = _backend({"aa:bb": handle})

    backend._write_partial_output(
        handle,
        None,
        False,
        _DesiredOutput(led=(0, 255, 0), player_leds=(True, False, False, False, True)),
        what="teste_perfil",
    )

    assert len(handle.reports) == 1
    report = handle.reports[0]
    assert (report[POS_R], report[POS_G], report[POS_B]) == (0, 255, 0)
    assert report[POS_PLAYERS] == 0b10001


def test_pelo_cabo_nada_sai_porque_pelo_cabo_a_barra_obedece() -> None:
    """A regra da casa: a cura tem de explicar o que JÁ funcionava.

    O report `0x02` do USB não tem janela nem máquina de estados de lightbar, e
    o fallback pydualsense do cabo nunca foi suprimido. Escrever ali seria
    trabalho sem defeito para curar — e um segundo escritor de graça.
    """
    handle = _Handle("usb")
    backend = _backend({"aa:bb": handle})

    backend.set_led((255, 0, 255))

    assert handle.reports == [], "escreveu no cabo, onde não há defeito"


def test_modo_nativo_nao_escreve_nada() -> None:
    """*"no modo nativo devolvemos o controle pra steam"* — regra dela, literal."""
    handle = _Handle("bt")
    backend = _backend({"aa:bb": handle}, mute=True)

    backend.set_led((255, 0, 255))
    backend._write_partial_output(
        handle, None, True, _DesiredOutput(led=(1, 2, 3)), what="teste_mudo"
    )

    assert handle.reports == [], "pisou no hidraw do jogo em Modo Nativo"


def test_o_report_nao_carrega_o_0x08_nem_o_setup_da_lightbar() -> None:
    """As duas medições que o report estreito respeita.

    `LIGHTBAR-BT-CULPADO-01` (03/08): o `0x08` (RELEASE_LEDS) dentro da janela
    travou a barra 7 de 7. `LIGHTBAR-BT-KEEPALIVE-01` (22/07): os bits de
    SETUP/BRILHO do flag2 travam a exibição no firmware.
    """
    handle = _Handle("bt")
    backend = _backend({"aa:bb": handle})

    backend.set_led((10, 20, 30))

    report = handle.reports[0]
    assert report[POS_FLAG1] & FLAG1_RELEASE_LEDS == 0, "mandou o 0x08"
    assert report[POS_FLAG2] == 0, "reengatou o SETUP/BRILHO da lightbar"
    assert report[POS_FLAG0] == 0, "pediu vibração, gatilho ou áudio num report de LED"

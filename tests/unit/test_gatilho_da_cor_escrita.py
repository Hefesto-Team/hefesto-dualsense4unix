"""GATILHO-DA-COR-01 — a escrita: rota hidraw, TODOS do rádio, e o portão dela.

Medido na bancada de 11-12/08/2026, com o olho dela e três DualSense no rádio
com a Steam viva. As linhas estão em `docs/data/ensaios.csv`.

O QUE ESTE ARQUIVO TRAVA, e cada item é uma medição
===================================================
- **a ROTA é hidraw, nunca sysfs.** Ensaios `cor-rota-sysfs-com-steam` (com a
  Steam aberta, escrever por `multi_intensity` NÃO muda a barra) contra
  `cor-rota-hidraw-com-steam` (o mesmo instante, o report 0x31 cru pintou os
  três — literal dela: *"todos tao magenta"*);
- **escreve em TODOS os do rádio**, não só no que chegou: a rajada da Steam é
  por evento e repinta todo mundo (`gatilho-1500ms-por-controle`);
- **cor E número de jogador no MESMO report**: a Steam repinta os dois, e
  pergunta dela em 12/08 — *"isso vai servir pro player e pro lightbar,
  certo?"*;
- **o portão dos dois modos**: em Modo Nativo / Conexão Nativa (Sony) o dono é
  o jogo, e o gatilho não escreve NADA. Regra dela, literal: *"no modo nativo
  devolvemos o controle pra steam e no modo conexão também, todo o resto é o
  hefesto"*;
- **o cabo fica de fora**: lá a barra obedece (ensaio `lightbar-usb-1`), e
  escrever seria trabalho sem defeito para curar;
- **a escrita é INCONDICIONAL**: nada de consultar cache de nó sysfs. Medido em
  12/08 — três `lightbar_reassert_skip_cache` no journal e as três barras
  seguiram apagadas.

O método é o do `test_lightbar_medir_o_0x08.py`: o método exercitado é o DO
PRODUTO, emprestado a um objeto mínimo. Um dublê que reimplementasse a regra
mediria o dublê.
"""
from __future__ import annotations

import threading
from typing import Any

from hefesto_dualsense4unix.core.backend_pydualsense import (
    KERNEL_DEFAULT_BLUE,
    PyDualSenseController,
    _DesiredOutput,
)

#: Offsets DENTRO do envelope 0x31 (o common começa em [3]): flag1, número do
#: jogador e os três bytes de cor.
POS_FLAG1 = 3 + 1
POS_PLAYERS = 3 + 43
POS_R = 3 + 44
POS_G = 3 + 45
POS_B = 3 + 46

FLAG1_LIGHTBAR = 0x04
FLAG1_PLAYER = 0x10
FLAG1_RELEASE_LEDS = 0x08


class _Handle:
    """Espelha o handle da pydualsense no que a escrita usa: `conType` + `writeReport`."""

    def __init__(self, transporte: str = "bt") -> None:
        self.conType = type("Con", (), {"name": "BT_31" if transporte == "bt" else "USB_01"})()
        self.reports: list[list[int]] = []

    def writeReport(self, dados: list[int]) -> None:  # noqa: N802 (API do upstream)
        self.reports.append(list(dados))


class _NoSysfs:
    """Nó de LED que RECUSA escrever e denuncia quem tentou a rota sysfs."""

    def __init__(self) -> None:
        self.tentativas = 0

    def set_rgb(self, *_rgb: int, **_kw: Any) -> bool:
        self.tentativas += 1
        return True

    def set_players(self, *_a: Any, **_kw: Any) -> bool:
        self.tentativas += 1
        return True

    def get_rgb(self) -> tuple[int, int, int]:
        self.tentativas += 1
        return (0, 0, 0)


class _BackendMinimo:
    """Só o necessário para exercitar a escrita do gatilho sem hardware."""

    def __init__(
        self,
        handles: dict[str, Any],
        *,
        mute: bool = False,
        desired: dict[str, _DesiredOutput] | None = None,
        sysfs: dict[str, Any] | None = None,
    ) -> None:
        self._handles = handles
        self._output_mute = mute
        self._io_lock = threading.RLock()
        self._sysfs = sysfs if sysfs is not None else {}
        self._desired = desired or {}
        self._suprimir_player_leds = False

    def _merged_desired_for_key(self, key: str) -> _DesiredOutput:
        return self._desired.get(key, _DesiredOutput())


def _backend(handles: dict[str, Any], **kw: Any) -> Any:
    alvo = _BackendMinimo(handles, **kw)
    for nome in (
        "reescrever_lightbar_por_hidraw",
        "consumir_conexoes_bt_novas",
        "_pode_escrever_player_leds",
        "_detect_transport",
    ):
        metodo = getattr(PyDualSenseController, nome)
        # `_detect_transport` é staticmethod — não se liga a instância.
        setattr(alvo, nome, metodo if nome == "_detect_transport" else metodo.__get__(alvo))
    return alvo


def test_escreve_pela_rota_hidraw_e_nunca_pelo_no_sysfs() -> None:
    """A rota é o achado da noite. Com a Steam viva, o sysfs perde e o hidraw vence.

    Ensaio `cor-rota-sysfs-com-steam` (não obedece) contra
    `cor-rota-hidraw-com-steam` (pintou os três). O produto tinha desligado
    justamente a rota que funciona: por rádio só sobrava o sysfs.
    """
    handle = _Handle("bt")
    no = _NoSysfs()
    backend = _backend({"aa:bb": handle}, sysfs={"aa:bb": no})

    resultado = backend.reescrever_lightbar_por_hidraw()

    assert resultado == {"aa:bb": True}
    assert no.tentativas == 0, "tocou no nó sysfs — a rota errada"
    assert len(handle.reports) == 1
    report = handle.reports[0]
    assert report[0] == 0x31, "não é o report de output por Bluetooth"
    assert len(report) == 78


def test_escreve_em_TODOS_os_do_radio_e_nao_so_no_que_chegou() -> None:  # noqa: N802
    """A lição do ensaio que falhou: a rajada da Steam repinta TODOS.

    `gatilho-1500ms-por-controle`, 12/08: escrever só no controle recém-chegado
    deixou dois dos três no padrão da Steam. Literal dela: *"só o player 4 que
    é o controle azul o resto tá no padrão da steam"*.
    """
    handles = {"aa:bb": _Handle("bt"), "cc:dd": _Handle("bt"), "ee:ff": _Handle("bt")}
    backend = _backend(handles)

    resultado = backend.reescrever_lightbar_por_hidraw()

    assert resultado == {"aa:bb": True, "cc:dd": True, "ee:ff": True}
    for key, handle in handles.items():
        assert len(handle.reports) == 1, f"{key} ficou sem repintura"


def test_o_cabo_fica_de_fora() -> None:
    """Pelo cabo a barra obedece — escrever lá é trabalho sem defeito para curar.

    Ensaio `lightbar-usb-1` (03/08) e a mesa cheia de 11/08: com o daemon
    parado e escrita direta, os DOIS do cabo ficaram brancos e os dois do rádio
    não.
    """
    radio, cabo = _Handle("bt"), _Handle("usb")
    backend = _backend({"radio": radio, "cabo": cabo})

    resultado = backend.reescrever_lightbar_por_hidraw()

    assert resultado == {"radio": True}
    assert len(radio.reports) == 1
    assert cabo.reports == [], "escreveu no controle do cabo"


def test_a_cor_e_o_numero_saem_no_MESMO_report() -> None:  # noqa: N802
    """*"isso vai servir pro player e pro lightbar, certo?"* — dela, 12/08.

    A Steam repinta os dois: ao abrir com as barras acesas, elas migraram para
    as cores de jogador dela e o número acompanhou. Um report carrega os dois
    (flag1 0x04|0x10, `common[43]` e `common[44..46]`); fazer duas escritas
    seria dobrar a chance de cair no meio de uma rajada nova.

    O padrão conferido é o do Controle 3 — `x-x-x`, que no driver desta máquina
    é `BIT(4)|BIT(2)|BIT(0)` = 0x15
    (`assets/dkms/hid-playstation/hid-playstation.c:1836-1842`).
    """
    handle = _Handle("bt")
    desired = _DesiredOutput(
        led=(255, 0, 128), player_leds=(True, False, True, False, True)
    )
    backend = _backend({"aa:bb": handle}, desired={"aa:bb": desired})

    backend.reescrever_lightbar_por_hidraw()

    report = handle.reports[0]
    assert report[POS_FLAG1] & FLAG1_LIGHTBAR, "o bit da lightbar não foi autorizado"
    assert report[POS_FLAG1] & FLAG1_PLAYER, "o bit do número do jogador não saiu"
    assert (report[POS_R], report[POS_G], report[POS_B]) == (255, 0, 128)
    assert report[POS_PLAYERS] == 0x15


def test_nao_manda_o_0x08_nem_os_bits_de_setup_da_lightbar() -> None:
    """Dois reports desta casa já travaram a barra. Nenhum dos dois sai daqui.

    - `RELEASE_LEDS` (0x08): travou a barra 7 de 7 dentro da janela pós-conexão
      (`LIGHTBAR-BT-CULPADO-01`, 03/08) e apaga os player-LEDs sempre;
    - `LIGHTBAR_SETUP_CONTROL_ENABLE` (flag2 0x02): reengatado em regime, trava
      a exibição no firmware (`LIGHTBAR-BT-KEEPALIVE-01`, 22/07).
    """
    handle = _Handle("bt")
    backend = _backend({"aa:bb": handle})

    backend.reescrever_lightbar_por_hidraw()

    report = handle.reports[0]
    assert not report[POS_FLAG1] & FLAG1_RELEASE_LEDS, "mandou o 0x08"
    assert report[3 + 0] == 0x00, "valid_flag0 não está neutro"
    assert report[3 + 38] == 0x00, "valid_flag2 não está zerado (setup/brilho)"


def test_sem_cor_resolvida_usa_o_azul_default_do_kernel() -> None:
    """Controle virgem tem de nascer ACESO, não apagado.

    É a mesma escolha do priming (`_refresh_sysfs_leds`): sem cor resolvida, o
    azul que o kernel pinta na probe. Decisão dela de 12/08 — *"nada de macs,
    nada de personalizacao por controle; se eu conectar controle virgem ele tem
    que funcionar via produto"*.
    """
    handle = _Handle("bt")
    backend = _backend({"aa:bb": handle})

    backend.reescrever_lightbar_por_hidraw()

    report = handle.reports[0]
    assert (report[POS_R], report[POS_G], report[POS_B]) == KERNEL_DEFAULT_BLUE


def test_em_modo_nativo_nao_escreve_nada() -> None:
    """O PORTÃO. Regra dela, e ela vale para os dois modos com o mesmo nome interno.

    *"no modo nativo devolvemos o controle pra steam e no modo conexão também,
    todo o resto é o hefesto"*. "Modo Nativo" e "Conexão Nativa (Sony)" são a
    MESMA coisa por dentro (`FEAT-NATIVE-MODE-01`; o segundo é o rótulo que ela
    escolheu para a tela), e os dois chegam aqui como `_output_mute`.
    """
    handle = _Handle("bt")
    backend = _backend({"aa:bb": handle}, mute=True)

    resultado = backend.reescrever_lightbar_por_hidraw()

    assert resultado == {}
    assert handle.reports == [], "escreveu por baixo do jogo em Modo Nativo"


def test_o_instrumento_de_isolar_players_tira_o_numero_e_mantem_a_cor() -> None:
    """LIGHTBAR-ISOLAR-OS-PLAYERS-01: o instrumento dela vale nesta rota também.

    Ligado, o número não sai — e o bit dele nem é autorizado, porque autorizar
    um campo que sai zerado é mandar "apaga" com cara de keepalive.
    """
    handle = _Handle("bt")
    desired = _DesiredOutput(led=(1, 2, 3), player_leds=(True, True, True, True, True))
    backend = _backend({"aa:bb": handle}, desired={"aa:bb": desired})
    backend._suprimir_player_leds = True

    backend.reescrever_lightbar_por_hidraw()

    report = handle.reports[0]
    assert report[POS_FLAG1] & FLAG1_LIGHTBAR
    assert not report[POS_FLAG1] & FLAG1_PLAYER
    assert report[POS_PLAYERS] == 0x00
    assert (report[POS_R], report[POS_G], report[POS_B]) == (1, 2, 3)


def test_falha_de_um_controle_nao_aborta_os_outros() -> None:
    """Best-effort por handle — três na mesa, e um com o link ruim não cala os dois."""

    class _Quebrado(_Handle):
        def writeReport(self, dados: list[int]) -> None:  # noqa: N802
            raise OSError("link caiu")

    bom, ruim = _Handle("bt"), _Quebrado("bt")
    backend = _backend({"bom": bom, "ruim": ruim})

    resultado = backend.reescrever_lightbar_por_hidraw()

    assert resultado == {"bom": True, "ruim": False}
    assert len(bom.reports) == 1


def test_o_contador_de_conexoes_novas_e_consumido() -> None:
    """O sinal do gatilho: contador, não flag — duas conexões não viram uma."""
    backend = _backend({})
    backend._conexoes_bt_novas = 3

    assert backend.consumir_conexoes_bt_novas() == 3
    assert backend.consumir_conexoes_bt_novas() == 0

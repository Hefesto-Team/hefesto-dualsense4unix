"""A-CONEXOES-DESCOBRE-OS-APARELHOS-DE-ENTRADA-AINDA-NAO-DECLARADOS-01 — o acionador ganha linha.

A aba Conexões lista os aparelhos de entrada USB presentes que podem ser acionador, cada um com a
linha «Usar como botões de…» já entregue, sem que a pessoa edite o ``maquina.json``. A régua nunca
abre o ``/sys`` nem o ``/dev/input`` da máquina: o ``/sys/class/input`` é uma pasta de mentira.
"""
from __future__ import annotations

import ctypes
from pathlib import Path
from typing import Any

import pytest
from evdev import ecodes

from hefesto_dualsense4unix.utils import maquina
from hefesto_dualsense4unix.utils.maquina import MaquinaConfig, acionadores_possiveis

LUGAR = "AA:BB:CC:00:00:F0"
PEDAL = ("event7", "FootSwitch", "usb-0000:00:14.0-3/input0", "3553", "b001")
CHAVE_DO_PEDAL = maquina.chave_do_acionador("3553", "b001", "FootSwitch", PEDAL[2])


def _mapa(*teclas: int) -> str:
    """O ``capabilities/key`` do kernel: palavras de ``unsigned long`` em hex, a de cima antes."""
    largura = ctypes.sizeof(ctypes.c_ulong) * 8
    valor = sum(1 << t for t in teclas)
    palavras = []
    while valor:
        palavras.append(f"{valor & ((1 << largura) - 1):x}")
        valor >>= largura
    return " ".join(reversed(palavras)) or "0"


def _no(raiz: Path, evento: str, nome: str, fisico: str, vendor: str, product: str,
        barramento: str, teclas: tuple[int, ...], soldado: bool = False,
        virtual: bool = False) -> None:
    dentro = raiz / evento / "device"
    if soldado or virtual:
        usb = raiz / ("virtual" if virtual else "usb") / evento
        usb.mkdir(parents=True)
        (usb / "idVendor").write_text(vendor + "\n")
        (usb / "removable").write_text("fixed\n" if soldado else "unknown\n")
        (usb / "input").mkdir()
        (raiz / evento).mkdir(parents=True)
        dentro.symlink_to(usb / "input")
    (dentro / "id").mkdir(parents=True, exist_ok=True)
    (dentro / "capabilities").mkdir(exist_ok=True)
    (dentro / "name").write_text(nome + "\n")
    (dentro / "phys").write_text(fisico + "\n")
    (dentro / "id" / "vendor").write_text(vendor + "\n")
    (dentro / "id" / "product").write_text(product + "\n")
    (dentro / "id" / "bustype").write_text(barramento + "\n")
    (dentro / "capabilities" / "key").write_text(_mapa(*teclas) + "\n")


def _sys_de_mentira(raiz: Path) -> Path:
    """Um pedal USB e o que enche o ``/sys`` de um notebook com a mesa montada, sem declarar."""
    letras = (ecodes.KEY_A, ecodes.KEY_B, ecodes.KEY_ENTER)
    _no(raiz, PEDAL[0], *PEDAL[1:], "0003", letras)
    _no(raiz, "event8", "FootSwitch Consumer Control", PEDAL[2].replace("input0", "input1"),
        "3553", "b001", "0003", (ecodes.KEY_VOLUMEUP, ecodes.KEY_PLAYPAUSE))
    _no(raiz, "event10", "FootSwitch", PEDAL[2].replace("input0", "input2"), "3553", "b001",
        "0003", letras)
    _no(raiz, "event1", "AT Translated Set 2 keyboard", "isa0060/serio0/input0", "0001", "0001",
        "0011", letras)
    _no(raiz, "event2", "SynPS/2 Synaptics TouchPad", "isa0060/serio1/input0", "0002", "0007",
        "0011", (ecodes.BTN_LEFT, ecodes.BTN_TOUCH))
    _no(raiz, "event3", "Logitech USB Optical Mouse", "usb-0000:00:14.0-1/input0", "046d", "c077",
        "0003", (ecodes.BTN_LEFT, ecodes.BTN_RIGHT, ecodes.BTN_MIDDLE))
    _no(raiz, "event4", "Integrated Camera: Integrated C", "usb-0000:00:14.0-6/button", "04f2",
        "b6d0", "0003", (ecodes.KEY_CAMERA,))
    _no(raiz, "event5", "Power Button", "PNP0C0C/button/input0", "0000", "0001", "0019",
        (ecodes.KEY_POWER,))
    _no(raiz, "event6", "Teclado soldado na máquina", "usb-0000:00:14.0-8/input0", "05ac", "0250",
        "0003", letras, soldado=True)
    _no(raiz, "event11", "input-remapper keyboard", "input-remapper", "0000", "0001", "0003",
        letras, virtual=True)
    _no(raiz, "event9", "Wireless Controller", "usb-0000:00:14.0-2/input0", "054c", "0ce6",
        "0003", (ecodes.BTN_SOUTH, ecodes.BTN_EAST))
    return raiz


def test_o_pedal_ganha_linha_e_o_resto_do_sys_nao(tmp_path: Path) -> None:
    """D-2011-A-CONEXOES-LISTA-O-ACIONADOR-USB-AINDA-NAO-DECLARADO: três nós do mesmo pedal.

    Dois deles com teclas viram um aparelho, com o nome que ele mesmo diz; o teclado e o touchpad
    do notebook, o mouse, a webcam, o botão de ligar, o teclado soldado, o remapeador virtual e o
    controle de jogo não entram.

    MORDIDA: tire do ``acionadores_possiveis`` o teste da tecla de teclado (``_TECLA_A``), o do
    barramento, o do ``removable``, o do ``virtual`` ou o agrupamento pelo caminho físico.
    """
    achados = acionadores_possiveis(_sys_de_mentira(tmp_path / "input"))
    assert [(a.evento, a.nome, a.chave) for a in achados] == [
        ("event7", "FootSwitch", CHAVE_DO_PEDAL)]


def test_sem_o_sys_ou_sem_nenhum_aparelho_a_lista_e_vazia(tmp_path: Path) -> None:
    """D-2011-A-CONEXOES-LISTA-O-ACIONADOR-USB-AINDA-NAO-DECLARADO: sem /sys, a lista é vazia."""
    assert acionadores_possiveis(tmp_path / "nao-existe") == []
    (tmp_path / "input").mkdir()
    assert acionadores_possiveis(tmp_path / "input") == []


@pytest.fixture
def a08() -> Any:
    from tests.conftest import exigir_gi_real

    exigir_gi_real("importa `interface.pacotes.a08_conexoes`, que carrega o GTK")
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes

    a08_conexoes._RASCUNHO = None
    yield a08_conexoes
    a08_conexoes._RASCUNHO = None


class _Ponte:
    def machine_declare(self, declaracao: dict[str, Any]) -> tuple[bool, str | None]:
        maquina.gravar_maquina_com_descartes(declaracao)
        return True, None


def test_a_linha_do_pedal_nasce_na_cena_se_declara_pela_janela_e_deixa_de_ser_nova(
        a08: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """D-2011-A-CONEXOES-LISTA-O-ACIONADOR-USB-AINDA-NAO-DECLARADO: o pedal nasce e se declara.

    A linha leva o nome do aparelho e o «Usar como botões de…»; o clique arma a janela com a
    chave dele, o «Guardar» declara, e declarado ele sai dos novos (uma linha só).

    MORDIDA: tire de ``_os_acionadores`` a parcela dos não declarados, ou o filtro dos já
    declarados.
    """
    from hefesto_dualsense4unix.interface.pacotes import em_fundo

    monkeypatch.setattr(a08, "_RAIZ_DAS_ENTRADAS", str(_sys_de_mentira(tmp_path / "input")))
    monkeypatch.setattr(em_fundo, "_FUNDO", {})
    monkeypatch.setattr(em_fundo, "_FUNDO_EM_VOO", set())
    monkeypatch.setattr(em_fundo, "LER_NA_HORA", True)
    vazia = MaquinaConfig()
    linhas = a08._os_acionadores(vazia, [{"id": LUGAR}])
    assert [(x["id"], x["nome"], x["tipo"], x["lugar"]) for x in linhas] == [
        (CHAVE_DO_PEDAL, "FootSwitch", "entrada", LUGAR)]
    assert a08._os_acionadores(vazia, []) == []
    html = a08.html_da_linha(linhas[0], {"aparelhos": linhas, "lugares": [{"id": LUGAR}]})
    assert 'value="FootSwitch"' in html and 'data-gesto="usar-como-botoes"' in html
    assert "Usar como botões de…" in html

    cena = {"aparelhos": linhas, "lugares": [{"id": LUGAR}],
            "quem_recebe": [("aabbcc0000f1", "Cosmic Red")], "colorway_de": {}}
    monkeypatch.setattr(a08, "_CENA_NA_TELA", cena)
    monkeypatch.setattr(a08, "_declaracao", lambda: vazia)
    monkeypatch.setattr(a08, "_reler_a_declaracao", lambda: None)
    assert a08.usar_como_botoes(None, {"alvo": CHAVE_DO_PEDAL}, _Ponte()) == {"armou": True}
    assert a08._RASCUNHO.chave == CHAVE_DO_PEDAL and a08._RASCUNHO.nome == "FootSwitch"
    a08._RASCUNHO.teclas.append([ecodes.KEY_ENTER, "Tecla 1", None])
    a08._RASCUNHO.sel = ecodes.KEY_ENTER
    a08.acionador_botao(None, {"entrada": "circle", "forma": {"acionador-quem": "aabbcc0000f1"}},
                        _Ponte())
    a08.acionador_guardar(None, {"forma": {"acionador-quem": "aabbcc0000f1"}}, _Ponte())

    declarada = maquina.carregar_maquina()
    assert declarada.acionadores[CHAVE_DO_PEDAL].teclas == {str(ecodes.KEY_ENTER): "circle"}
    assert [(x["id"], x["controle"]) for x in a08._os_acionadores(declarada, [{"id": LUGAR}])] == [
        (CHAVE_DO_PEDAL, "aabbcc0000f1")]

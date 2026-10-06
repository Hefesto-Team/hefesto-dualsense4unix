#!/usr/bin/env python3
"""A RÉGUA DO SEGUNDO TOQUE — o L3 abre, e apertado de novo FECHA.

DECISÃO, 02/09/2026, verbatim: *"deixar no preset do botão L3, no
mapeamento, abrir o teclado virtual e fechar o teclado virtual caso apertado
novamente."*

POR QUE ESTA RÉGUA EXISTE, e por que ela não mede o primeiro toque: **todo
alternador desta casa nasce verde medindo só a ida.** `open()` sozinho passa em
qualquer teste que aperte uma vez — e passaria igual se o segundo aperto abrisse
uma segunda janela por cima, que é exatamente o defeito que a pessoa vê. O caso
que decide é o SEGUNDO, e por isso ele vem primeiro aqui.

E ELA ANDA PELO CAMINHO DO PRODUTO, não pelo controlador direto: o aperto entra
em `UinputKeyboardDevice.dispatch(frozenset({"l3"}))`, que é quem o daemon chama
a cada tique, e sai no `virtual_token_callback` — o mesmo fio que
`start_keyboard_emulation` liga ao `_OSKController`. Uma régua que chamasse
`ctrl.toggle()` mediria o método e não o botão: bastaria o mapa de fábrica
apontar para outro token e ela continuaria verde com o L3 morto.

O QUE ELA NÃO TOCA: nenhum processo de verdade. O `Popen` é dublê e o
`shutil.which` é dublê — nada de wvkbd/onboard nascendo na tela de quem roda a
suíte.
"""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.core.keyboard_mappings import (
    DEFAULT_BUTTON_BINDINGS,
    TOKEN_TOGGLE_OSK,
)
from hefesto_dualsense4unix.daemon.subsystems import keyboard as subsistema
from hefesto_dualsense4unix.daemon.subsystems.keyboard import _OSKController
from hefesto_dualsense4unix.integrations.uinput_keyboard import UinputKeyboardDevice


class _ProcessoDeMentira:
    """O que o `Popen` devolveria — vivo até alguém o terminar."""

    def __init__(self, pid: int) -> None:
        self.pid = pid
        self.vivo = True
        self.terminado = False

    def poll(self) -> int | None:
        return None if self.vivo else 0

    def terminate(self) -> None:
        self.vivo = False
        self.terminado = True

    def morrer_por_fora(self) -> None:
        self.vivo = False


@pytest.fixture
def mesa(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Um teclado na tela instalado, um `Popen` de mentira, e o L3 no fio."""
    monkeypatch.setattr(
        subsistema.shutil, "which",
        lambda nome: f"/usr/bin/{nome}" if nome == "wvkbd-mobintl" else None)

    abertos: list[list[str]] = []
    processos: list[_ProcessoDeMentira] = []

    def _popen(argv: list[str], **_: Any) -> _ProcessoDeMentira:
        abertos.append(list(argv))
        proc = _ProcessoDeMentira(pid=4000 + len(processos))
        processos.append(proc)
        return proc

    monkeypatch.setattr(subsistema.subprocess, "Popen", _popen)
    monkeypatch.setattr(subsistema, "_OSK_SONDA", [(float("-inf"), False)])

    ctrl = _OSKController()
    dev = UinputKeyboardDevice(
        bindings=dict(DEFAULT_BUTTON_BINDINGS),
        virtual_token_callback=ctrl.dispatch_token,
    )
    dev._device = object()
    dev._uinput_mod = object()

    def apertar_l3() -> None:
        dev.dispatch(frozenset({"l3"}))
        dev.dispatch(frozenset())
        assert ctrl.esperar_os_toques(5.0)

    return {"ctrl": ctrl, "dev": dev, "abertos": abertos,
            "processos": processos, "apertar_l3": apertar_l3}


def test_o_preset_de_fabrica_do_l3_e_o_alternador() -> None:
    """O mapa é o que o usuário mandou mexer — *"no preset do botão L3, no mapeamento"*."""
    assert DEFAULT_BUTTON_BINDINGS["l3"] == (TOKEN_TOGGLE_OSK,), (
        "o L3 saiu do alternador. Se voltou a ser `__OPEN_OSK__`, o teclado na "
        "tela deixa de ter saída no mesmo dedo que o abriu.")


def test_o_segundo_toque_fecha(mesa: dict[str, Any]) -> None:
    """A RÉGUA. Aperta, abre; aperta de novo, FECHA."""
    mesa["apertar_l3"]()
    assert mesa["abertos"] == [["wvkbd-mobintl"]], (
        f"o primeiro aperto não abriu nada: {mesa['abertos']!r}")
    assert mesa["ctrl"].aberto() is True

    mesa["apertar_l3"]()
    assert len(mesa["abertos"]) == 1, (
        "o segundo aperto ABRIU DE NOVO em vez de fechar — é o defeito clássico "
        f"do alternador que só sabe ir: {mesa['abertos']!r}")
    assert mesa["processos"][0].terminado is True, (
        "o segundo aperto não terminou o teclado na tela que o primeiro abriu")
    assert mesa["ctrl"].aberto() is False


def test_o_terceiro_toque_reabre(mesa: dict[str, Any]) -> None:
    """Alternar é ida E volta, e a volta tem de voltar."""
    for _ in range(3):
        mesa["apertar_l3"]()
    assert len(mesa["abertos"]) == 2, (
        f"três apertos têm de dar abrir/fechar/abrir: {mesa['abertos']!r}")
    assert mesa["processos"][0].terminado is True
    assert mesa["processos"][1].terminado is False
    assert mesa["ctrl"].aberto() is True


def test_o_release_nao_fecha_o_que_o_press_acabou_de_abrir(
    mesa: dict[str, Any],
) -> None:
    """Um aperto é press + release, e o release NÃO pode contar como segundo."""
    mesa["dev"].dispatch(frozenset({"l3"}))
    mesa["dev"].dispatch(frozenset())
    assert mesa["ctrl"].esperar_os_toques(5.0)
    assert mesa["processos"][0].terminado is False, (
        "o release fechou o teclado na tela — o L3 abriria e fecharia no mesmo "
        "aperto, e ela veria a janela piscar")
    assert mesa["ctrl"].aberto() is True


def test_a_janela_morta_por_fora_faz_o_toque_seguinte_abrir(
    mesa: dict[str, Any],
) -> None:
    """Ela fechou o wvkbd no X — o L3 tem de ABRIR, não fechar o que já morreu."""
    mesa["apertar_l3"]()
    mesa["processos"][0].morrer_por_fora()

    mesa["apertar_l3"]()
    assert len(mesa["abertos"]) == 2, (
        "com a janela morta por fora, o aperto seguinte tem de ABRIR — veio "
        f"{mesa['abertos']!r}")
    assert mesa["ctrl"].aberto() is True


def test_sem_teclado_instalado_o_segundo_toque_continua_tentando(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sem wvkbd/onboard, nenhum aperto pode deixar o estado preso em "aberto"."""
    monkeypatch.setattr(subsistema.shutil, "which", lambda _nome: None)
    monkeypatch.setattr(subsistema, "_OSK_SONDA", [(float("-inf"), False)])
    avisos: list[list[str]] = []
    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.desktop_notifications."
        "notify_teclado_na_tela_ausente",
        lambda candidatos: (avisos.append(list(candidatos)) or True))

    ctrl = _OSKController()
    ctrl.dispatch_token(TOKEN_TOGGLE_OSK, "press")
    ctrl.dispatch_token(TOKEN_TOGGLE_OSK, "press")
    assert ctrl.esperar_os_toques(5.0)

    assert ctrl.aberto() is False
    assert len(avisos) == 2, (
        "os dois apertos têm de tentar abrir (o aviso tem dedup próprio no "
        f"`notify`, não aqui) — vieram {len(avisos)}")


def test_o_token_do_alternador_e_virtual_e_nao_vira_tecla(
    mesa: dict[str, Any],
) -> None:
    """`__TOGGLE_OSK__` sai pelo callback, nunca pelo uinput."""
    from hefesto_dualsense4unix.core.keyboard_mappings import is_virtual_token

    assert is_virtual_token(TOKEN_TOGGLE_OSK)
    mesa["apertar_l3"]()
    assert mesa["abertos"] == [["wvkbd-mobintl"]]



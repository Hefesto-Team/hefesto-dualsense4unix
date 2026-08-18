"""Testes do `_OSKController` — abrir/fechar onboard/wvkbd-mobintl."""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.core.keyboard_mappings import TOKEN_CLOSE_OSK, TOKEN_OPEN_OSK
from hefesto_dualsense4unix.daemon.subsystems.keyboard import _OSKController
from hefesto_dualsense4unix.integrations import desktop_notifications

#: Referência à implementação REAL, capturada antes de qualquer fixture trocar o
#: atributo do módulo. É por ela que o teste da frase entra — pelo nome, ele
#: pegaria o dublê autouse abaixo e não testaria nada.
_NOTIFICA_DE_VERDADE = desktop_notifications.notify_teclado_na_tela_ausente


@pytest.fixture(autouse=True)
def _sem_notificacao_de_verdade(
    monkeypatch: pytest.MonkeyPatch,
) -> list[list[str]]:
    """Intercepta o aviso do teclado na tela ausente (TECLADO-QUE-NAO-DIGITA-01).

    `_avisar_ausencia` passou a NOTIFICAR o desktop, e sem esta trava a suíte
    faria uma chamada D-Bus de verdade — uma notificação real na tela de quem
    está rodando os testes. Autouse porque o ramo "sem binário" é exercitado por
    mais de um teste deste arquivo; devolve a lista de chamadas para quem quiser
    afirmar sobre elas.
    """
    chamadas: list[list[str]] = []
    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.desktop_notifications."
        "notify_teclado_na_tela_ausente",
        lambda candidatos: (chamadas.append(list(candidatos)) or True),
    )
    return chamadas


class _FakeProc:
    def __init__(self, pid: int = 4242) -> None:
        self.pid = pid
        self._alive = True
        self.terminated = False

    def poll(self) -> int | None:
        return None if self._alive else 0

    def terminate(self) -> None:
        self._alive = False
        self.terminated = True


def test_sem_binario_nao_duplica_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """3 chamadas a open() sem binário não criam Popen e marcam flag 1x."""
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.subsystems.keyboard.shutil.which", lambda _name: None
    )
    spawned: list[Any] = []
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.subsystems.keyboard.subprocess.Popen",
        lambda *a, **k: spawned.append(("Popen", a, k)),
    )
    ctrl = _OSKController()
    ctrl.open()
    ctrl.open()
    ctrl.open()
    assert spawned == []
    assert ctrl._missing_warned is True


def test_onboard_spawn_e_fechamento(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.subsystems.keyboard.shutil.which",
        lambda name: f"/usr/bin/{name}" if name == "onboard" else None,
    )
    spawned: list[list[str]] = []
    fake_proc = _FakeProc()

    def _popen(argv: list[str], **_: Any) -> _FakeProc:
        spawned.append(argv)
        return fake_proc

    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.subsystems.keyboard.subprocess.Popen", _popen
    )

    ctrl = _OSKController()
    ctrl.open()
    assert spawned == [["onboard"]]
    # Segunda chamada open() é no-op (processo já vivo).
    ctrl.open()
    assert len(spawned) == 1

    ctrl.close()
    assert fake_proc.terminated is True
    # close() com processo morto é no-op seguro.
    ctrl.close()


def test_wvkbd_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Se `onboard` ausente mas `wvkbd-mobintl` presente, usa o fallback."""

    def _which(name: str) -> str | None:
        return "/usr/bin/wvkbd-mobintl" if name == "wvkbd-mobintl" else None

    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.subsystems.keyboard.shutil.which", _which
    )
    spawned: list[list[str]] = []

    def _popen(argv: list[str], **_: Any) -> _FakeProc:
        spawned.append(argv)
        return _FakeProc()

    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.subsystems.keyboard.subprocess.Popen", _popen
    )
    ctrl = _OSKController()
    ctrl.open()
    assert spawned == [["wvkbd-mobintl"]]


def test_dispatch_token_open_close(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.subsystems.keyboard.shutil.which",
        lambda name: f"/usr/bin/{name}" if name == "onboard" else None,
    )
    popens: list[list[str]] = []
    fake_proc = _FakeProc()
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.subsystems.keyboard.subprocess.Popen",
        lambda argv, **_: (popens.append(argv) or fake_proc),  # type: ignore[func-returns-value]
    )
    ctrl = _OSKController()
    ctrl.dispatch_token(TOKEN_OPEN_OSK, "press")
    assert popens == [["onboard"]]
    ctrl.dispatch_token(TOKEN_CLOSE_OSK, "press")
    assert fake_proc.terminated is True


def test_dispatch_token_release_e_noop() -> None:
    """Release não deve abrir/fechar — evita fechar logo após open em L3."""
    ctrl = _OSKController()
    # Sem mockar Popen: se release fosse abrir, subprocess real rodaria.
    ctrl.dispatch_token(TOKEN_OPEN_OSK, "release")
    ctrl.dispatch_token(TOKEN_CLOSE_OSK, "release")
    assert ctrl._process is None


# --- TECLADO-QUE-NAO-DIGITA-01: L3 sem teclado na tela para de ser silêncio ---
#
# Medido na máquina dela em 09/08/2026: `which onboard wvkbd-mobintl` não acha
# nenhum dos dois, e nenhum instalador, empacotamento ou doctor desta casa os
# instala, declara ou confere. Como `l3` é o ÚNICO caminho de fábrica para
# ESCREVER texto com o controle (todo o resto do mapa é atalho), apertar L3
# sumia inteiro: um `warning` no journal e mais nada.


def test_sem_binario_notifica_a_usuaria(
    monkeypatch: pytest.MonkeyPatch,
    _sem_notificacao_de_verdade: list[list[str]],
) -> None:
    """Apertar L3 sem teclado na tela instalado vira aviso na tela dela.

    A ORDEM dos nomes deixou de ser fixa em 10/08/2026 e passou a seguir a
    sessão: a frase é "instale X ou Y", e qual vem primeiro é a diferença entre
    um conselho que resolve e um que faz ela instalar o programa que abre sem
    digitar. Aqui a sessão é forçada para Wayland — o caso da máquina dela.
    """
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-1")
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.subsystems.keyboard.shutil.which",
        lambda _name: None,
    )
    ctrl = _OSKController()
    ctrl.dispatch_token(TOKEN_OPEN_OSK, "press")
    assert _sem_notificacao_de_verdade == [["wvkbd-mobintl", "onboard"]], (
        "L3 sem binário voltou a falhar em silêncio (ou o wvkbd deixou de vir "
        "primeiro em Wayland — e aí o conselho manda instalar o que não digita)"
    )


def test_com_binario_nao_notifica(monkeypatch: pytest.MonkeyPatch,
                                  _sem_notificacao_de_verdade: list[list[str]]) -> None:
    """Quem TEM o teclado na tela não recebe aviso nenhum."""
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.subsystems.keyboard.shutil.which",
        lambda name: f"/usr/bin/{name}" if name == "onboard" else None,
    )
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.subsystems.keyboard.subprocess.Popen",
        lambda argv, **_: _FakeProc(),
    )
    ctrl = _OSKController()
    ctrl.open()
    assert _sem_notificacao_de_verdade == []


def test_disponivel_responde_pelo_binario(monkeypatch: pytest.MonkeyPatch) -> None:
    """`disponivel()` é a pergunta que a tela faz — sem repetir o `which`."""
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.subsystems.keyboard.shutil.which",
        lambda _name: None,
    )
    assert _OSKController().disponivel() is False
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.subsystems.keyboard.shutil.which",
        lambda name: f"/usr/bin/{name}" if name == "wvkbd-mobintl" else None,
    )
    assert _OSKController().disponivel() is True


def test_a_notificacao_nomeia_os_dois_programas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A frase tem de dizer O QUE instalar — senão o aviso não resolve nada."""
    capturado: dict[str, Any] = {}

    def _fake_notify(summary: str, body: str = "", **kwargs: Any) -> bool:
        capturado["summary"] = summary
        capturado["body"] = body
        capturado["once_key"] = kwargs.get("once_key")
        return True

    monkeypatch.setattr(desktop_notifications, "notify", _fake_notify)
    assert _NOTIFICA_DE_VERDADE(["onboard", "wvkbd-mobintl"]) is True

    assert "onboard" in capturado["body"]
    assert "wvkbd-mobintl" in capturado["body"]
    assert "L3" in capturado["body"]
    # `once_key` é o que impede rajada: L3 é botão, e ela aperta várias vezes.
    assert capturado["once_key"] == "osk_binary_missing"

"""R-07 (auditoria 23/07) — só GESTO MANUAL persiste a máscara em disco.

`start_gamepad_emulation`/`stop_gamepad_emulation` gravavam a flag
``gamepad_emulation.flag`` sem olhar o ``origin``, contradizendo duas decisões
explícitas do mesmo eixo, escritas no próprio código:

- HARM-06 (`gamepad.py`, mouse): *"persist=False — a preferência de mouse da
  usuária sobrevive ao modo jogo"*;
- FEAT-COOP-DEFAULT-ON-01 (`lifecycle.py`, co-op): *"só gesto MANUAL persiste a
  escolha — perfil ligando/desligando co-op não pode virar opt-out da usuária"*.

Efeitos medidos com a configuração dela (flag = ``xbox``):

1. abre o Sackboy → o perfil pede ``dualsense`` → a flag em disco vira
   ``dualsense``; fecha o jogo e **a escolha dela sumiu**, sem ela ter tocado em
   nada, e volta assim no boot seguinte;
2. alt-tab para o navegador → "Navegação" (sem seção ``mode``) →
   ``stop_gamepad_emulation`` com ``persist`` default → a flag é **apagada** →
   no boot seguinte não nasce vpad nenhum e ela religa tudo na mão.

Estes testes olham o ARQUIVO, de propósito: a suíte existente monkeypatcha
``save_gamepad_emulation`` e por isso não enxergaria a regressão.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems.gamepad import (
    start_gamepad_emulation,
    stop_gamepad_emulation,
)
from hefesto_dualsense4unix.utils.session import (
    _GAMEPAD_EMULATION_FLAG_FILE,
    save_gamepad_emulation,
)


@pytest.fixture
def flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isola o config_dir e devolve o caminho da flag."""
    from hefesto_dualsense4unix.utils import session as session_mod

    monkeypatch.setattr(session_mod, "config_dir", lambda ensure=False: tmp_path)
    return tmp_path / _GAMEPAD_EMULATION_FLAG_FILE


class _DaemonFalso:
    """Superfície mínima que os dois setters tocam."""

    def __init__(self) -> None:
        from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig

        self.config = DaemonConfig()
        self._gamepad_device: Any = None
        self.controller = None

    def __getattr__(self, nome: str) -> Any:  # pragma: no cover - só p/ tolerar
        raise AttributeError(nome)


def _sem_device_real(monkeypatch: pytest.MonkeyPatch) -> None:
    """Curto-circuita a criação do vpad — só o ramo de persistência interessa.

    ``start_gamepad_emulation`` faz ``from ...virtual_pad import make_virtual_pad``
    DENTRO da função, então o patch tem de ser no MÓDULO DE ORIGEM: patchar o
    atributo em `subsystems.gamepad` cria um nome que ninguém lê, e o teste
    passaria criando um uinput de verdade (efeito colateral real no kernel).
    """
    import hefesto_dualsense4unix.daemon.subsystems.gamepad as gp
    import hefesto_dualsense4unix.integrations.virtual_pad as vp

    monkeypatch.setattr(
        vp, "make_virtual_pad", lambda *a, **k: type("Vpad", (), {"backend": "uinput"})()
    )
    monkeypatch.setattr(gp, "make_primary_rumble_sink", lambda *a, **k: None)
    monkeypatch.setattr(gp, "make_primary_replica_sinks", lambda *a, **k: {})
    monkeypatch.setattr(gp, "read_primary_calibration", lambda *a, **k: None)
    monkeypatch.setattr(gp, "controller_allows_uhid", lambda *a, **k: False)
    monkeypatch.setattr(gp, "start_motion_reader", lambda *a, **k: None)
    monkeypatch.setattr(gp, "_set_controller_grab", lambda *a, **k: None)
    monkeypatch.setattr(gp, "_materialize_launch_env", lambda *a, **k: None)
    monkeypatch.setattr(gp, "notify_vpad_degradado", lambda *a, **k: None)


def test_a_flag_de_referencia_e_escrita_de_verdade(flag: Path) -> None:
    """Sanidade do arranjo: sem isolar errado, o resto não prova nada."""
    save_gamepad_emulation(True, "xbox")
    assert flag.read_text(encoding="utf-8").strip() == "xbox"
    save_gamepad_emulation(False)
    assert not flag.exists()


def test_stop_por_perfil_nao_apaga_a_preferencia(
    flag: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O caso 2: perfil sem `mode` desligando o gamepad NÃO pode apagar a flag."""
    save_gamepad_emulation(True, "xbox")
    daemon = _DaemonFalso()
    daemon.config.gamepad_emulation_enabled = True

    # O contrato é do parâmetro: quem sabe a origem é o chamador (lifecycle
    # passa persist=(origin == "manual")).
    stop_gamepad_emulation(daemon, persist=False, release_grab=False)

    assert flag.exists(), (
        "perfil desligando o gamepad apagou a preferência em disco — no boot "
        "seguinte não nasceria vpad nenhum"
    )
    assert flag.read_text(encoding="utf-8").strip() == "xbox"


def test_stop_manual_apaga_a_preferencia(flag: Path) -> None:
    """A contraparte: gesto manual DESLIGA de verdade (senão nada nunca sai)."""
    save_gamepad_emulation(True, "xbox")
    daemon = _DaemonFalso()
    daemon.config.gamepad_emulation_enabled = True

    stop_gamepad_emulation(daemon, persist=True, release_grab=False)

    assert not flag.exists()


def test_start_por_perfil_nao_reescreve_o_flavor(
    flag: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O caso 1: o perfil do jogo troca a máscara em runtime, não em disco."""
    save_gamepad_emulation(True, "xbox")
    daemon = _DaemonFalso()

    # O start real cria device/uhid; aqui só interessa o ramo de persistência,
    # então o factory é curto-circuitado para um device inerte.
    _sem_device_real(monkeypatch)

    start_gamepad_emulation(daemon, flavor="dualsense", origin="profile")

    assert flag.read_text(encoding="utf-8").strip() == "xbox", (
        "o perfil do jogo reescreveu a máscara escolhida pela usuária em disco"
    )


def test_start_manual_reescreve_o_flavor(
    flag: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A contraparte: quando ELA escolhe, a escolha tem de persistir."""
    save_gamepad_emulation(True, "xbox")
    daemon = _DaemonFalso()

    _sem_device_real(monkeypatch)

    start_gamepad_emulation(daemon, flavor="dualsense", origin="manual")

    assert flag.read_text(encoding="utf-8").strip() == "dualsense"

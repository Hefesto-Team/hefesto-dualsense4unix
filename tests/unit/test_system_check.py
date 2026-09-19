"""Auto-diagnóstico de infra no boot (FEAT-SYSTEM-AUTOREPAIR-BOOT-01).

`system_warnings()` detecta (read-only, sem sudo) udev de hotplug com nome de
unit antigo e WirePlumber sequestrando o microfone do DualSense, devolvendo o
comando de reparo sugerido.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from hefesto_dualsense4unix.core import system_check


def test_udev_outdated_detecta_nome_errado(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rule = tmp_path / "73.rules"
    rule.write_text(
        'ENV{SYSTEMD_USER_WANTS}="hefesto-gui-hotplug.service"\n', encoding="utf-8"
    )
    monkeypatch.setattr(system_check, "_UDEV_RULES", (str(rule),))
    assert system_check._udev_hotplug_outdated() is True


def test_udev_ok_com_nome_certo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rule = tmp_path / "73.rules"
    rule.write_text(
        'ENV{SYSTEMD_USER_WANTS}="hefesto-dualsense4unix-gui-hotplug.service"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(system_check, "_UDEV_RULES", (str(rule),))
    assert system_check._udev_hotplug_outdated() is False


def test_wireplumber_hijack_detecta_dualsense(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    state = tmp_path / ".local/state/wireplumber"
    state.mkdir(parents=True)
    (state / "default-nodes").write_text(
        "default.configured.audio.source=alsa_input.usb-Sony_DualSense-00\n",
        encoding="utf-8",
    )
    assert system_check._wireplumber_hijacks_mic() is True


def test_system_warnings_vazio_quando_tudo_ok(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(system_check, "_UDEV_RULES", ())  # sem regras
    monkeypatch.setenv("HOME", str(tmp_path))  # sem default-nodes
    assert system_check.system_warnings() == []


def _default_nodes(lar: Path, corpo: str) -> None:
    estado = lar / ".local/state/wireplumber"
    estado.mkdir(parents=True)
    (estado / "default-nodes").write_text(corpo, encoding="utf-8")


def test_fonte_configurada_le_a_chave_exata_e_nao_a_pilha(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A escolha de agora é a chave SEM sufixo; `.0`, `.1` são o que foi antes.

    Quem lê é o nascimento do microfone (`hotkey._a_escolha_gravada_e_de_
    outro_controle`): ler a pilha como escolha faria a partida do daemon
    respeitar o microfone que ela já trocou. A pilha vem ANTES no arquivo de
    propósito — um leitor que pegasse a primeira linha com o prefixo cairia
    nela.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    _default_nodes(
        tmp_path,
        "[default-nodes]\n"
        "default.configured.audio.source.0=alsa_input.pci-0000_00_1f.3.analog-stereo\n"
        "default.configured.audio.sink=alsa_output.pci-0000_00_1f.3.analog-stereo\n"
        "default.configured.audio.source=hefesto_mic_0000b2\n",
    )
    assert system_check.fonte_configurada_do_wireplumber() == "hefesto_mic_0000b2"
    assert system_check._wireplumber_hijacks_mic() is False, (
        "o canal por controle não tem 'dualsense' no nome — o aviso de boot "
        "continua perguntando o que sempre perguntou"
    )


def test_fonte_configurada_sem_escolha_e_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A máquina nova nunca escolheu: sem arquivo, ou só com a pilha."""
    monkeypatch.setenv("HOME", str(tmp_path))
    assert system_check.fonte_configurada_do_wireplumber() is None
    _default_nodes(
        tmp_path,
        "[default-nodes]\ndefault.configured.audio.source.0=hefesto_mic_0000b1\n",
    )
    assert system_check.fonte_configurada_do_wireplumber() is None

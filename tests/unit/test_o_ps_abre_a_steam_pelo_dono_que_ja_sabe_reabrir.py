"""O-PS-ABRE-A-STEAM-PELO-DONO-QUE-JA-SABE-REABRIR-01: o PS pede ao ``reopen_steam``.

O «abrir ou focar» do botão PS, do gesto ``abrir_a_steam`` e do «repor o lançador» do
Reiniciar não pergunta nada por conta própria: a Steam de pé é a do ``steam_running``, e o
reabrir (o ``steam`` ou o ``xdg-open steam://open/main`` da Flatpak e da Snap) é o do
``reopen_steam``. Dublados aqui: o ``shutil.which``, o ``fora_do_servico.abrir`` e a
pergunta «a Steam está de pé?». Nenhum processo nasce.

MORDIDAS: devolver ao ``open_or_focus_steam`` o ``which("steam") is None → False`` reprova
o 1 e o 4; devolver a ele um ``pgrep`` próprio reprova o 2; dizer «de pé» sem a conferência
do ``reopen_steam`` reprova o 5.
"""
from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import reposicao_dos_lancadores as rl
from hefesto_dualsense4unix.integrations import steam_launch_options as slo
from hefesto_dualsense4unix.integrations import steam_launcher

CLIENTE = 100


class _Maquina:
    """O PATH, o gerenciador e a Steam de mentira: anota o que se pediu e o que se olhou."""

    def __init__(self, no_path: set[str], *, de_pe_antes: bool = False) -> None:
        self.no_path = no_path
        self.de_pe_antes = de_pe_antes
        self.pedidos: list[list[str]] = []
        self.olhados: list[str] = []

    def which(self, nome: str) -> str | None:
        self.olhados.append(nome)
        return f"/usr/bin/{nome}" if nome in self.no_path else None

    def abrir(self, argv: list[str], **_k: Any) -> None:
        self.pedidos.append(list(argv))

    def de_pe(self) -> bool:
        return self.de_pe_antes or bool(self.pedidos)


def _a_maquina(
    monkeypatch: pytest.MonkeyPatch,
    no_path: set[str],
    *,
    processos: list[slo.ProcessoDaSteam] | None = None,
    de_pe_antes: bool = False,
) -> _Maquina:
    maquina = _Maquina(no_path, de_pe_antes=de_pe_antes)
    monkeypatch.setattr(slo.shutil, "which", maquina.which)
    monkeypatch.setattr(slo.fora_do_servico, "abrir", maquina.abrir)
    monkeypatch.setattr(slo, "steam_running", maquina.de_pe)
    monkeypatch.setattr(slo, "processos_da_steam", lambda *a, **k: list(processos or []))
    steam_launcher._reset_missing_warning_for_tests()
    return maquina


def _proibido(nome: str) -> Callable[..., Any]:
    def _boom(*_a: Any, **_k: Any) -> Any:
        raise AssertionError(f"o PS perguntou por conta própria ({nome})")

    return _boom


def test_sem_steam_no_path_o_ps_abre_a_da_flatpak(monkeypatch: pytest.MonkeyPatch) -> None:
    """1. Só o ``xdg-open`` no PATH: o pedido é a URL que a Flatpak registra, e a Steam sobe."""
    maquina = _a_maquina(monkeypatch, {"xdg-open"})
    assert steam_launcher.open_or_focus_steam() is True
    assert maquina.pedidos == [["xdg-open", "steam://open/main"]]


def test_com_a_steam_deste_lar_de_pe_o_pedido_sai_uma_vez_sem_pgrep(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """2. A Steam deste lar de pé: o pedido vai à instância viva, e ninguém roda ``pgrep``."""
    maquina = _a_maquina(
        monkeypatch,
        {"steam", "xdg-open"},
        processos=[slo.ProcessoDaSteam(CLIENTE, "cliente", str(Path.home()), "1")],
        de_pe_antes=True,
    )
    monkeypatch.setattr(subprocess, "run", _proibido("subprocess.run"))
    monkeypatch.setattr(subprocess, "check_output", _proibido("subprocess.check_output"))
    assert steam_launcher.open_or_focus_steam() is True
    assert maquina.pedidos == [["steam"]]
    assert {"pgrep", "wmctrl"}.isdisjoint(maquina.olhados), maquina.olhados


def test_com_a_steam_de_outro_lar_nada_se_abre(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """3. A Steam de pé é toda de outro ``HOME``: a recusa de sempre, sem pedido nenhum."""
    maquina = _a_maquina(
        monkeypatch,
        {"steam", "xdg-open"},
        processos=[slo.ProcessoDaSteam(CLIENTE, "cliente", str(tmp_path / "outro-lar"), "1")],
    )
    assert steam_launcher.open_or_focus_steam() is False
    assert maquina.pedidos == []


def test_o_reiniciar_repoe_a_steam_da_flatpak(monkeypatch: pytest.MonkeyPatch) -> None:
    """4. O «repor o lançador» do Reiniciar com a Steam da Flatpak: ela entra em ``repostos``."""
    maquina = _a_maquina(monkeypatch, {"xdg-open", "flatpak"})
    steam = next(x for x in rl.LANCADORES if x.chave == "steam")
    monkeypatch.setattr(rl, "jogo_aberto", lambda: False)
    monkeypatch.setattr(rl, "abertos", lambda: [steam])
    monkeypatch.setattr(rl, "fechar", lambda _lancador: True)
    recibo = rl.repor()
    assert recibo.repostos == (steam.nome,)
    assert recibo.nao_reabriram == ()
    assert maquina.pedidos == [["xdg-open", "steam://open/main"]]


def test_a_steam_que_nao_sobe_por_porta_nenhuma_nao_vira_de_pe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """5. As duas portas no PATH e a Steam nunca sobe: o PS tenta as duas e diz ``False``."""
    maquina = _a_maquina(monkeypatch, {"steam", "xdg-open"})
    monkeypatch.setattr(slo, "steam_running", lambda: False)
    dormidas: list[float] = []
    monkeypatch.setattr(slo.time, "sleep", dormidas.append)
    assert steam_launcher.open_or_focus_steam() is False
    assert maquina.pedidos == [["steam"], ["xdg-open", "steam://open/main"]]
    assert dormidas, "a conferência não esperou a Steam subir"

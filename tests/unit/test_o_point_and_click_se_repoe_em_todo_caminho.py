"""O-POINT-AND-CLICK-SE-REPOE-EM-TODO-CAMINHO-01 (21/10/2026).

Com o `desktop` no Point and click, a tabela dos botões é a do «Perfil jogo - navegação». Dois
caminhos a deixavam de fora: os retornos cedo do `restore_last_profile` (sem escolha, Modo Nativo,
outro perfil já valendo, ativação que falha) e a troca da escolha na aba Navegação, que só gravava
o disco e valia na próxima entrada no Point and click.

O que a régua lê é o que os devices RECEBERAM, pela subclasse do `Daemon` real (a mesma de
`test_o_point_and_click_aplica_o_perfil_que_a_navegacao_escolhe.py`).

AS MORDIDAS: devolva o corpo do `restore_last_profile` sem o `try/finally` que chama o `repor`, e os
três retornos cedo do `desktop` ficam com a tabela do perfil; tire o pedido do
`point_and_click_perfil` (a06), e a escolha nova só vale na próxima entrada.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.connection import restore_last_profile
from hefesto_dualsense4unix.utils.session import (
    ARRANJO_NAVEGACAO,
    ARRANJO_POINT_AND_CLICK,
    gravar_a_escolha,
)
from tests.unit.test_o_point_and_click_aplica_o_perfil_que_a_navegacao_escolhe import (
    _daemon,
    _DaemonQueAnota,
)

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

METODO = "desktop.arranjo.repor"


def _o_que_o_point_and_click_poe(d: _DaemonQueAnota) -> tuple[str, ...] | None:
    """O «quadrado» da tabela que o Point and click põe com o perfil que vale agora."""
    d._aplicar_as_tabelas(
        d._tabelas_do_arranjo(ARRANJO_POINT_AND_CLICK, d._perfil_do_arranjo()), None)
    return d.quadrado()


def _com_as_tabelas_do_perfil(d: _DaemonQueAnota, nome: str) -> tuple[str, ...] | None:
    """O que a reconexão deixa nos devices: as tabelas do perfil, sem o Point and click."""
    from hefesto_dualsense4unix.profiles.loader import load_profile

    d._aplicar_as_tabelas(load_profile(nome), None)
    return d.quadrado()


def _contar_o_repor(d: _DaemonQueAnota, monkeypatch: pytest.MonkeyPatch) -> list[bool]:
    vezes: list[bool] = []
    original = d._repor_o_point_and_click

    def _espiao() -> bool:
        vezes.append(original())
        return vezes[-1]

    monkeypatch.setattr(d, "_repor_o_point_and_click", _espiao)
    return vezes


def _sem_escolha(d: _DaemonQueAnota, _mp: pytest.MonkeyPatch) -> None:
    d.store.set_active_profile("")


def _outro_perfil_ja_vale(d: _DaemonQueAnota, _mp: pytest.MonkeyPatch) -> None:
    gravar_a_escolha("perfil-ativo")
    d.store.set_active_profile("jogo-navegacao")


def _a_ativacao_falha(d: _DaemonQueAnota, mp: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.profiles.manager import ProfileManager

    def _levanta(*_a: Any, **_k: Any) -> Any:
        raise RuntimeError("ativação que falha (régua)")

    gravar_a_escolha("perfil-ativo")
    mp.setattr(ProfileManager, "activate", _levanta)


@pytest.mark.parametrize("caminho", [_sem_escolha, _outro_perfil_ja_vale, _a_ativacao_falha],
                         ids=["sem-escolha", "outro-perfil-ja-vale", "ativacao-que-falha"])
def test_cada_retorno_cedo_do_boot_deixa_a_tabela_do_point_and_click(caminho, monkeypatch) -> None:
    d = _daemon()
    d.aplicar_o_arranjo_do_desktop(origin="manual", arranjo=ARRANJO_POINT_AND_CLICK)
    caminho(d, monkeypatch)
    esperado = _o_que_o_point_and_click_poe(d)
    antes = _com_as_tabelas_do_perfil(d, d.store.active_profile or "perfil-ativo")
    assert antes != esperado, "a régua precisa de duas tabelas diferentes"
    vezes = _contar_o_repor(d, monkeypatch)

    asyncio.run(restore_last_profile(d))

    assert d.quadrado() == esperado, (
        f"a reconexão por aqui deixou a tabela do perfil: o quadrado digita {d.quadrado()!r}")
    assert vezes == [True], f"o retorno cedo não passou pelo `repor` uma vez ({vezes})"


def test_no_modo_nativo_o_repor_passa_e_nao_escreve(monkeypatch) -> None:
    """O Modo Nativo não é `desktop`: o `repor` é chamado e decide não escrever."""
    d = _daemon()
    d.aplicar_o_arranjo_do_desktop(origin="manual", arranjo=ARRANJO_POINT_AND_CLICK)
    gravar_a_escolha("perfil-ativo")
    antes = _com_as_tabelas_do_perfil(d, "perfil-ativo")
    d._native_mode = True
    vezes = _contar_o_repor(d, monkeypatch)

    asyncio.run(restore_last_profile(d))

    assert vezes == [False] and d.quadrado() == antes


def test_a_ativacao_do_boot_repoe_uma_vez_so(monkeypatch) -> None:
    d = _daemon()
    d.aplicar_o_arranjo_do_desktop(origin="manual", arranjo=ARRANJO_POINT_AND_CLICK)
    gravar_a_escolha("perfil-ativo")
    vezes = _contar_o_repor(d, monkeypatch)
    asyncio.run(restore_last_profile(d))
    assert vezes == [True] and d.quadrado() == ("KEY_LEFTCTRL",)


# A TROCA DA ESCOLHA NA ABA NAVEGAÇÃO -----------------------------------------------------------

class _PonteDoDaemon:
    """A ponte da tela com o handler de verdade do `desktop.arranjo.repor` atrás."""

    def __init__(self, d: _DaemonQueAnota) -> None:
        self.d = d
        self.chamados: list[str] = []

    def resultado(self, metodo: str, timeout: float | None = None, **params: Any) -> Any:
        from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin

        self.chamados.append(metodo)
        assert metodo == METODO, f"a escolha chamou {metodo}"
        casca = SimpleNamespace(daemon=self.d)
        return asyncio.run(
            IpcHandlersMixin._handle_desktop_arranjo_repor(casca, params))  # type: ignore[arg-type]


def _pelo_gravador(d: _DaemonQueAnota) -> _DaemonQueAnota:
    """O perfil ativo regravado pelo `save_profile`: o gesto grava no arquivo que ele nomeia."""
    from hefesto_dualsense4unix.profiles.loader import load_profile, save_profile
    from hefesto_dualsense4unix.utils.session import config_dir

    a_mao = Path(config_dir()) / "profiles" / "perfil-ativo.json"
    if save_profile(load_profile("perfil-ativo")) != a_mao:
        a_mao.unlink()
    return d


def _trocar_a_escolha(d: _DaemonQueAnota, valor: str) -> _PonteDoDaemon:
    from tests.conftest import exigir_gi_real

    exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")
    import pacotes  # noqa: F401  (registra os dez)
    from pacotes import Contexto, gesto_da_pagina

    fn = gesto_da_pagina("06-navegacao.html", "point-and-click-perfil")
    assert fn is not None
    ponte = _PonteDoDaemon(d)
    fn(Contexto(state={"active_profile": "perfil-ativo"}, mesa=[], conectados=[], estados={}),
       {"valor": valor}, ponte)
    return ponte


def test_trocar_a_escolha_com_o_point_and_click_de_pe_muda_o_quadrado_na_hora() -> None:
    """A prova da D-2110-O-POINT-AND-CLICK-SE-REPOE-PELO-SERVICO."""
    d = _pelo_gravador(_daemon())
    d.aplicar_o_arranjo_do_desktop(origin="manual", arranjo=ARRANJO_POINT_AND_CLICK)
    assert d.quadrado() == ("KEY_LEFTCTRL",)

    ponte = _trocar_a_escolha(d, "perfil:jogo-navegacao")

    assert ponte.chamados == [METODO], "a tela não pediu ao serviço"
    assert d.quadrado() == ("KEY_TAB",), (
        f"a escolha nova só vale na próxima entrada: o quadrado digita {d.quadrado()!r}")


def test_na_navegacao_o_servico_recebe_o_pedido_e_nao_troca_a_tabela() -> None:
    d = _pelo_gravador(_daemon())
    d.aplicar_o_arranjo_do_desktop(origin="manual", arranjo=ARRANJO_NAVEGACAO)
    assert d.quadrado() == ("KEY_SPACE",)

    ponte = _trocar_a_escolha(d, "perfil:jogo-navegacao")

    assert ponte.chamados == [METODO] and d.quadrado() == ("KEY_SPACE",)


def test_o_pedido_responde_se_repos() -> None:
    from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin

    d = _daemon()
    d.aplicar_o_arranjo_do_desktop(origin="manual", arranjo=ARRANJO_POINT_AND_CLICK)
    responde = asyncio.run(IpcHandlersMixin._handle_desktop_arranjo_repor(
        SimpleNamespace(daemon=d), {}))  # type: ignore[arg-type]
    assert responde == {"status": "ok", "reposto": True}
    sem = asyncio.run(IpcHandlersMixin._handle_desktop_arranjo_repor(
        SimpleNamespace(daemon=object()), {}))  # type: ignore[arg-type]
    assert sem == {"status": "failed", "reposto": False}

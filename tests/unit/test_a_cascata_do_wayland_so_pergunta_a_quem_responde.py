"""A-CASCATA-DO-WAYLAND-SO-PERGUNTA-A-QUEM-RESPONDE-01: a cascata é ``cosmic → wlrctl → null``.

O xdg-desktop-portal não tem interface ``Window`` nem método ``GetActiveWindow`` (a referência
pública, flatpak.github.io/xdg-desktop-portal, «API Reference»). O degrau que perguntava a ele
saiu, e com ele o texto que o prometia no instalador, no doctor e nas páginas.

MORDIDAS: devolver o degrau do portal à cascata faz o 1 contar conexão D-Bus e publicar um
caminho que nunca leu; devolver a oferta do ``wlrctl`` ao bloco do COSMIC no ``install.sh`` faz
o 3 reprovar.
"""
from __future__ import annotations

import re
import sys
import types
from pathlib import Path
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `app.actions.daemon_actions`, que carrega o GTK")

from hefesto_dualsense4unix.app.actions import daemon_actions
from hefesto_dualsense4unix.integrations import window_detect
from hefesto_dualsense4unix.integrations.window_backends import cosmic_toplevel, wlr_toplevel

RAIZ = Path(__file__).resolve().parents[2]
_TERMOS = re.compile(r"portal\.Window|GetActiveWindow")
_ADR = RAIZ / "docs" / "adr" / "014-cosmic-wayland-support.md"
_NOTA_DA_ADR = "## Nota de 10/10/2026"


class _Mudo:
    """Um backend que não responde: nem leitura, nem desistência."""

    backend_name = "mudo"
    available = False
    protocol_unsupported = True
    last_failure_reason = None

    def get_active_window_info(self) -> None:
        return None


class _CosmicMudo(_Mudo):
    backend_name = "cosmic"


class _WlrctlMudo(_Mudo):
    backend_name = "wlrctl"


def _jeepney_que_conta(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Um ``jeepney`` de mentira que anota cada conexão aberta."""
    conexoes: list[str] = []

    class _Conexao:
        def send_and_get_reply(self, *_a: Any, **_k: Any) -> Any:
            return types.SimpleNamespace(body=("", {}))

        def close(self) -> None:
            pass

    def _abrir(bus: str = "SESSION") -> _Conexao:
        conexoes.append(bus)
        return _Conexao()

    raiz = types.ModuleType("jeepney")
    raiz.DBusAddress = lambda *a, **k: (a, k)  # type: ignore[attr-defined]
    raiz.new_method_call = lambda *a, **k: (a, k)  # type: ignore[attr-defined]
    bloqueante = types.ModuleType("jeepney.io.blocking")
    bloqueante.open_dbus_connection = _abrir  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "jeepney", raiz)
    monkeypatch.setitem(sys.modules, "jeepney.io", types.ModuleType("jeepney.io"))
    monkeypatch.setitem(sys.modules, "jeepney.io.blocking", bloqueante)
    return conexoes


def test_sem_resposta_a_cascata_nao_abre_d_bus_e_diz_null(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """1. ``cosmic`` e ``wlrctl`` mudos: ``None``, ``null`` desde a primeira leitura, zero D-Bus."""
    conexoes = _jeepney_que_conta(monkeypatch)
    monkeypatch.setattr(cosmic_toplevel, "CosmicToplevelBackend", _CosmicMudo)
    monkeypatch.setattr(wlr_toplevel, "WlrctlBackend", _WlrctlMudo)
    cascata = window_detect._WaylandCascadeBackend()
    nomes = [cascata.backend_name]
    for _ in range(5):
        assert cascata.get_active_window_info() is None
        nomes.append(cascata.backend_name)
    assert nomes == ["null"] * 6
    assert conexoes == []
    assert cascata.last_failure_reason == window_detect.MOTIVO_CASCATA_SEM_LEITURA


def test_o_portal_nao_e_mais_um_caminho_de_janela() -> None:
    """O conjunto dos cegos ao processo é o dos backends que existem."""
    assert "portal" not in window_detect.BACKENDS_CEGOS_AO_PROCESSO
    assert window_detect.backend_ve_nome_do_processo("portal") is None
    assert not (RAIZ / "src/hefesto_dualsense4unix/integrations/window_backends"
                / "wayland_portal.py").exists()


def _onde_aparece() -> list[str]:
    arquivos = [RAIZ / "install.sh", RAIZ / "scripts" / "doctor.sh"]
    arquivos += sorted((RAIZ / "src").rglob("*.py"))
    arquivos += sorted(
        p for p in (RAIZ / "docs").rglob("*")
        if p.is_file() and p.suffix in {".md", ".html", ".csv", ".json"}
        and "process" not in p.relative_to(RAIZ / "docs").parts[:1]
        and "research" not in p.relative_to(RAIZ / "docs").parts[:1]
    )
    achados: list[str] = []
    for arquivo in arquivos:
        texto = arquivo.read_text(encoding="utf-8", errors="replace")
        if arquivo == _ADR:
            texto = texto.split(_NOTA_DA_ADR, 1)[0]
        for numero, linha in enumerate(texto.splitlines(), start=1):
            if _TERMOS.search(linha):
                achados.append(f"{arquivo.relative_to(RAIZ)}:{numero}")
    return achados


def test_ninguem_promete_a_interface_que_nao_existe() -> None:
    """2. Nenhum ``portal.Window`` nem ``GetActiveWindow`` fora da nota datada da ADR."""
    assert _onde_aparece() == []
    nota = _ADR.read_text(encoding="utf-8").split(_NOTA_DA_ADR, 1)
    assert len(nota) == 2 and "flatpak.github.io/xdg-desktop-portal" in nota[1]


def _bloco_do_cosmic(texto: str) -> str:
    """O corpo do ``if [[ "${DESKTOP_IS_COSMIC}" -eq 1 ]]; then`` até o ``fi`` da coluna zero."""
    inicio = texto.index('if [[ "${DESKTOP_IS_COSMIC}" -eq 1 ]]; then\n    printf')
    fim = texto.index("\nfi\n", inicio)
    return texto[inicio:fim]


def test_o_instalador_nao_oferece_o_wlrctl_no_cosmic() -> None:
    """3. Lido do texto, sem rodar: o bloco do COSMIC não instala nem recomenda o ``wlrctl``."""
    bloco = _bloco_do_cosmic((RAIZ / "install.sh").read_text(encoding="utf-8"))
    codigo = "\n".join(x for x in bloco.splitlines() if not x.lstrip().startswith("#"))
    assert "run_pkg wlrctl" not in codigo
    assert "ask_yn" not in codigo or "wlrctl" not in codigo
    assert "zcosmic_toplevel_info_v1" in codigo


def test_o_instalador_oferece_o_wlrctl_so_no_wlroots() -> None:
    """O ``wlrctl`` continua oferecido, e só onde o compositor fala o protocolo dele."""
    texto = (RAIZ / "install.sh").read_text(encoding="utf-8")
    ofertas = [m.start() for m in re.finditer(r"run_pkg wlrctl", texto)]
    assert ofertas, "o wlrctl sumiu de todo compositor"
    inicio = texto.index('if [[ "${DESKTOP_IS_WLROOTS}" -eq 1 ]]; then')
    fim = texto.index("\nfi\n", inicio)
    assert all(inicio < x < fim for x in ofertas)


def test_a_tela_traduz_o_cosmic_e_nao_conhece_o_portal() -> None:
    """4. O caminho que de fato lê no COSMIC tem nome na tela; o que nunca leu, não."""
    mapa = daemon_actions._BACKEND_EM_PORTUGUES
    assert "portal" not in mapa
    texto = daemon_actions.descrever_deteccao_de_janela(
        {"window_detect_backend": "cosmic", "window_detect_seeing": False,
         "window_detect_reason": "backend_sem_motivo"}
    )
    assert mapa["cosmic"] in texto

"""O app_id da janela casa o `.desktop`, e a identidade veste o processo ANTES da janela.

A-HAPTICA-MORA-EM-VIBRACAO-E-O-ICONE-DO-APP-VOLTA-01 (item 2, 05/10/2026). O ícone do app sumiu do
dock e a hipótese era «o `set_prgname` vem depois da janela, ou o app_id não bate com o `.desktop`».
MEDIDO na janela viva dela (cliente `ext_foreign_toplevel_list_v1`, só leitura): o app_id é
`hefesto-dualsense4unix`, o casador do dock (a reimplementação do `find_app_by_id` do
`appid_sonda.py`) o casa por `StartupWMClass` com o `.desktop` dela, e o GTK resolve o ícone no
tema dela e no hicolor. A hipótese caiu; o contrato medido fica guardado aqui para não regredir:

* no Wayland nativo o app_id é o prgname (`wm_instance`) e tem de ser o nome do `.desktop`;
* no XWayland o segundo campo do WM_CLASS é a classe (`wm_class`) e tem de ser o `StartupWMClass`;
* nenhuma janela nasce antes de `vestir_a_identidade`.

MORDIDAS: trocar `wm_instance` na identidade reprova o primeiro; trocar `StartupWMClass` do
`.desktop` reprova o segundo; pôr `vestir_a_identidade` depois do piloto reprova o terceiro.
"""

from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path
from types import ModuleType

import pytest

from hefesto_dualsense4unix.utils import identidade

RAIZ = Path(__file__).resolve().parents[2]
DESKTOP = RAIZ / "packaging" / "hefesto-dualsense4unix.desktop"
LANCADOR = RAIZ / "scripts" / "abrir_interface.py"


def _chave(nome: str) -> str:
    achado = re.search(rf"^{nome}=(.*)$", DESKTOP.read_text(encoding="utf-8"), re.M)
    assert achado, f"o .desktop não tem `{nome}=`"
    return achado.group(1).strip()


def test_o_app_id_do_wayland_e_o_nome_do_desktop() -> None:
    casa = identidade.atual()
    assert casa.wm_instance == DESKTOP.stem, (
        "no Wayland nativo o app_id é o prgname: ele tem de ser o nome do `.desktop`, ou o dock "
        "só acha o aplicativo por `StartupWMClass`")
    assert casa.wm_instance == casa.app_id == casa.icone


def test_a_classe_do_xwayland_e_o_startupwmclass_letra_por_letra() -> None:
    assert _chave("StartupWMClass") == identidade.atual().wm_class
    assert _chave("Icon") == identidade.atual().icone


def test_o_dock_casa_o_app_id_dos_dois_backends_com_o_desktop() -> None:
    """As etapas 1 e 2 do `find_app_by_id` (sem caixa): o app_id de qualquer backend casa."""
    casa = identidade.atual()
    wmclass = _chave("StartupWMClass").lower()
    for app_id in (casa.wm_instance, casa.wm_class):
        casa_pela_classe = app_id.lower() == wmclass
        casa_pelo_arquivo = app_id.lower() == DESKTOP.stem.lower()
        assert casa_pela_classe or casa_pelo_arquivo, app_id


def _carregar_o_lancador() -> ModuleType:
    sys.path.insert(0, str(LANCADOR.parent))
    try:
        sys.modules.pop("abrir_interface", None)
        return importlib.import_module("abrir_interface")
    finally:
        sys.path.remove(str(LANCADOR.parent))


def test_a_identidade_veste_o_processo_antes_de_a_janela_nascer(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    ai = _carregar_o_lancador()
    chamadas: list[str] = []
    piloto = tmp_path / "piloto.py"
    piloto.write_text("")
    monkeypatch.delenv("HEFESTO_NA_TELA", raising=False)
    monkeypatch.setattr("hefesto_dualsense4unix.app.arranque.sanear_loaders_do_gdk_pixbuf",
                        lambda: False)
    monkeypatch.setattr(ai, "diario_da_janela", lambda: None)
    monkeypatch.setattr(ai, "achar_o_piloto", lambda: piloto)
    monkeypatch.setattr(ai, "vestir_a_identidade",
                        lambda _casa: chamadas.append("identidade") or [])
    monkeypatch.setattr(ai.runpy, "run_path",
                        lambda *_a, **_k: chamadas.append("janela") or {})
    monkeypatch.setattr(sys, "argv", list(sys.argv))
    assert ai.main([]) == 0
    assert chamadas == ["identidade", "janela"]

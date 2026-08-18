"""GUARDA-GI-REAL-01 — o verde dos testes de interface tem de significar algo.

Defeito medido em 28/07: ``pytest.importorskip("gi")`` é DERROTADO por poluição
de ``sys.modules``. Vinte e um arquivos de teste plantam um ``gi`` falso (com
``Gtk.Box = object``) no nível de módulo; o arquivo seguinte na ORDEM ALFABÉTICA
importa esse falso, o ``importorskip`` responde "existe, pode seguir", e o
módulo roda inteiro contra um GTK de mentira reportando PASSED.

Estes testes mordem a cura em três pontos independentes:

1. o critério — ``Gtk.Box = object`` tem de REPROVAR, e o widget real passar;
2. o vazamento — o stub de um arquivo não pode sobreviver até a importação do
   arquivo seguinte (é o ``pytest_collectstart`` do conftest que corta);
3. a visibilidade — pular por falta de GTK real registra o módulo e, sob
   ``HEFESTO_EXIGE_GTK_REAL=1``, vira REPROVAÇÃO em vez de pulo calado.

Nenhum deles depende de a máquina ter (ou não) o PyGObject instalado: o estado
do ambiente é injetado por ``monkeypatch``.
"""
from __future__ import annotations

import sys
import types

import pytest

from tests import conftest as guarda


def _gi_falso() -> tuple[types.ModuleType, types.ModuleType, types.ModuleType]:
    """Reproduz o stub canônico dos 21 arquivos: ``Gtk.Box = object``."""
    gi_mod = types.ModuleType("gi")
    gi_mod.require_version = lambda *_a, **_kw: None  # type: ignore[attr-defined]
    repo_mod = types.ModuleType("gi.repository")
    gtk_mod = types.ModuleType("gi.repository.Gtk")
    for nome in ("Box", "Label", "Button", "ListStore", "Builder", "Window"):
        setattr(gtk_mod, nome, object)
    repo_mod.Gtk = gtk_mod  # type: ignore[attr-defined]
    return gi_mod, repo_mod, gtk_mod


def _plantar_gi_falso(monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
    """Planta o ``gi`` falso ISOLADO — desfeito no teardown do monkeypatch."""
    gi_mod, repo_mod, gtk_mod = _gi_falso()
    monkeypatch.setitem(sys.modules, "gi", gi_mod)
    monkeypatch.setitem(sys.modules, "gi.repository", repo_mod)
    monkeypatch.setitem(sys.modules, "gi.repository.Gtk", gtk_mod)
    return gtk_mod


# ---------------------------------------------------------------------------
# 1. O critério: `Gtk.Box = object` é o disfarce que o `importorskip` não vê
# ---------------------------------------------------------------------------


def test_o_stub_de_gtk_e_reprovado_pelo_criterio_de_widget_real() -> None:
    _, _, gtk_falso = _gi_falso()
    assert guarda._gtk_e_real(gtk_falso) is False


def test_um_gtk_com_widgets_de_verdade_passa_no_criterio() -> None:
    """Classes próprias (como as do PyGObject) passam; ``object`` não."""
    gtk = types.ModuleType("gi.repository.Gtk")

    class _Box:
        pass

    class _ListStore:
        pass

    gtk.Box = _Box  # type: ignore[attr-defined]
    gtk.ListStore = _ListStore  # type: ignore[attr-defined]
    assert guarda._gtk_e_real(gtk) is True


def test_importorskip_aceita_o_stub_e_por_isso_nao_serve_de_guarda(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A prova do defeito: ``importorskip`` deixa passar o GTK de mentira."""
    _plantar_gi_falso(monkeypatch)

    # Não levanta `Skipped`: para o `importorskip`, o stub É o `gi`.
    modulo = pytest.importorskip("gi")
    assert modulo is sys.modules["gi"]

    # A guarda, olhando o MESMO processo, reprova.
    assert guarda.gi_real_no_processo() is False
    assert guarda.gi_stub_no_processo() is True


# ---------------------------------------------------------------------------
# 2. O vazamento entre arquivos (a ordem alfabética decidindo o verde)
# ---------------------------------------------------------------------------


def _gi_que_parece_real() -> dict[str, types.ModuleType]:
    """Trio ``gi*`` com widgets de classe própria — imita o PyGObject instalado."""
    gtk = types.ModuleType("gi.repository.Gtk")

    class _Box:
        pass

    class _ListStore:
        pass

    gtk.Box = _Box  # type: ignore[attr-defined]
    gtk.ListStore = _ListStore  # type: ignore[attr-defined]
    repo = types.ModuleType("gi.repository")
    repo.Gtk = gtk  # type: ignore[attr-defined]
    gi_mod = types.ModuleType("gi")
    # Um `__spec__` preenchido é o que distingue o pacote instalado do stub.
    gi_mod.__spec__ = types.SimpleNamespace(name="gi")  # type: ignore[assignment]
    return {"gi": gi_mod, "gi.repository": repo, "gi.repository.Gtk": gtk}


def test_stub_de_gi_nao_sobrevive_ate_o_proximo_modulo_de_teste(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    """O ``pytest_collectstart`` corta o stub antes do módulo seguinte importar.

    Sem esse corte, o primeiro arquivo a plantar decide o destino de todos os
    que vierem depois dele no alfabeto — que foi exatamente o defeito medido.

    Sem fotografia (ambiente sem GTK, o caso do CI): o stub é APAGADO.
    """
    monkeypatch.setattr(guarda, "_MODULOS_DESPOLUIDOS", [])
    monkeypatch.setattr(guarda, "_FOTO_GI_REAL", {})
    _plantar_gi_falso(monkeypatch)
    assert guarda.gi_stub_no_processo() is True

    # `request.node.parent` é o `pytest.Module` DESTE arquivo — o mesmo tipo de
    # coletor que o hook recebe na coleta de verdade.
    modulo = request.node.parent
    assert isinstance(modulo, pytest.Module)

    guarda.pytest_collectstart(modulo)

    restantes = [n for n in sys.modules if n == "gi" or n.startswith("gi.")]
    assert restantes == [], f"stub sobreviveu em sys.modules: {restantes}"
    assert [modulo.nodeid] == guarda._MODULOS_DESPOLUIDOS


def test_com_gtk_real_o_stub_e_trocado_pelos_modulos_reais_sem_reimportar(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    """Na máquina com GTK, desfazer o stub é DEVOLVER a fotografia, não apagar.

    Apagar e deixar reimportar estoura ``RuntimeError: Unable to register enum
    'PyGLibUserDirectory'`` — o GObject não registra o mesmo tipo duas vezes no
    mesmo processo. Medido: 66 testes e 39 coletas caíram de uma vez.
    """
    foto = _gi_que_parece_real()
    monkeypatch.setattr(guarda, "_MODULOS_DESPOLUIDOS", [])
    monkeypatch.setattr(guarda, "_FOTO_GI_REAL", dict(foto))
    _plantar_gi_falso(monkeypatch)
    assert guarda.gi_stub_no_processo() is True

    guarda.pytest_collectstart(request.node.parent)

    assert guarda.gi_stub_no_processo() is False
    assert sys.modules["gi"] is foto["gi"]
    assert sys.modules["gi.repository.Gtk"] is foto["gi.repository.Gtk"]


def test_o_gi_real_nao_e_arrancado_pelo_hook(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    """O hook só mexe em MENTIRA; com o `gi` real no ar ele só fotografa."""
    monkeypatch.setattr(guarda, "_FOTO_GI_REAL", {})
    real = _gi_que_parece_real()
    for nome, mod in real.items():
        monkeypatch.setitem(sys.modules, nome, mod)

    assert guarda.gi_real_no_processo() is True
    guarda.pytest_collectstart(request.node.parent)
    assert sys.modules.get("gi") is real["gi"]
    assert guarda._FOTO_GI_REAL["gi"] is real["gi"]


# ---------------------------------------------------------------------------
# 3. O pulo tem de ser VISÍVEL (o pulo calado é metade do defeito)
# ---------------------------------------------------------------------------


def test_exigir_gi_real_pula_e_registra_quando_o_ambiente_nao_tem_gtk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(guarda, "GI_REAL_DISPONIVEL", False)
    monkeypatch.setattr(guarda, "EXIGE_GTK_REAL", False)
    monkeypatch.setattr(guarda, "_MODULOS_PULADOS_SEM_GI", [])
    _plantar_gi_falso(monkeypatch)

    with pytest.raises(pytest.skip.Exception):
        guarda.exigir_gi_real("modulo-de-mentira")

    assert guarda._MODULOS_PULADOS_SEM_GI == ["modulo-de-mentira"]


def test_exigir_gi_real_reprova_quando_o_job_exige_gtk_real(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No job dedicado do CI, pular por falta de GTK é defeito, não sucesso."""
    monkeypatch.setattr(guarda, "GI_REAL_DISPONIVEL", False)
    monkeypatch.setattr(guarda, "EXIGE_GTK_REAL", True)
    monkeypatch.setattr(guarda, "_MODULOS_PULADOS_SEM_GI", [])
    # Ambiente SEM GTK nenhum: nem o real carregado, nem stub plantado.
    for nome in [n for n in sys.modules if n == "gi" or n.startswith("gi.")]:
        monkeypatch.delitem(sys.modules, nome)

    with pytest.raises(pytest.fail.Exception):
        guarda.exigir_gi_real("job-com-python3-gi")

    assert guarda._MODULOS_PULADOS_SEM_GI == ["job-com-python3-gi"]


def test_exigir_gi_real_nao_pula_quando_o_ambiente_tem_gtk_mas_ha_stub(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ambiente bom + processo envenenado = limpar o stub, NÃO perder o teste.

    Na máquina da mantenedora o PyGObject está instalado; deixar a suíte pular
    centenas de testes porque um arquivo anterior plantou um stub trocaria uma
    mentira por outra.
    """
    if not guarda.GI_REAL_DISPONIVEL:
        pytest.skip("esta máquina não tem PyGObject real — nada a restaurar")

    monkeypatch.setattr(guarda, "_MODULOS_PULADOS_SEM_GI", [])
    _plantar_gi_falso(monkeypatch)
    assert guarda.gi_stub_no_processo() is True

    guarda.exigir_gi_real("modulo-que-precisa-do-gtk")

    assert guarda.gi_real_no_processo() is True
    assert guarda._MODULOS_PULADOS_SEM_GI == []


# ---------------------------------------------------------------------------
# 4. O plantio isolado oferecido pelo conftest
# ---------------------------------------------------------------------------


def test_instalar_stubs_gi_desfaz_o_plantio_no_teardown() -> None:
    """``monkeypatch.setitem`` devolve ``sys.modules`` ao estado anterior."""
    antes = sys.modules.get("gi")
    with pytest.MonkeyPatch.context() as mp:
        gtk = guarda.instalar_stubs_gi(mp, widgets=("Box", "Label"))
        assert sys.modules["gi.repository.Gtk"] is gtk
        assert guarda.gi_stub_no_processo() is True
    assert sys.modules.get("gi") is antes

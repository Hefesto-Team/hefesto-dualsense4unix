"""ENGASGO-VULKAN-01 (lado GUI) — o botão "Tirar a sobreposição Vulkan".

O botão fica na fileira Avançado da aba Sistema, ao lado do "Travar Proton
validado": mesma natureza (mexe no que a Steam guarda por jogo) e mesmo alcance
(todos os jogos). O que este arquivo garante:

- o botão EXISTE no glade, com rótulo e dica, e o handler está no mapa da
  janela — sem isso a cura fica escrita e nunca ligada, o defeito mais caro
  desta casa;
- o diálogo é o RELATÓRIO (ELO-MUDO-01): diz jogo por jogo o que achou, e
  distingue "ligada" de "pendurada mas o arquivo não está no disco" — que é o
  estado real em que a máquina dela estava;
- "Devolver" só aparece quando há o que devolver, e "Tirar" só quando há o que
  tirar. Botão que não faz nada ensina que a tela é enfeite;
- com jogo aberto o worker RECUSA e não toca em arquivo nenhum.

Padrão `_install_gi_stubs` do `test_proton_lock_button.py` (GATE-SKIP-MASK-01):
com o gi real presente, nada é stubado.
"""
from __future__ import annotations

import re
import sys

from tests.conftest import exigir_gi_real
import types
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

RAIZ = Path(__file__).resolve().parents[2]
GLADE = RAIZ / "src" / "hefesto_dualsense4unix" / "gui" / "main.glade"

#: O NOME DO BOTÃO, ESCRITO UMA VEZ SÓ NESTE ARQUIVO. Ele é a palavra dela de
#: 05/09/2026 — *"o procurar sobreposição de novo deveria ser Corrigir
#: Sobreposição do Vulkan, não?"* — com o verbo trocado pelo que a medição
#: sustenta (ver `test_o_rotulo_nao_promete_cura_de_engasgo`).
ROTULO = "Tirar a sobreposição Vulkan"


def _install_gi_stubs() -> None:
    existente = sys.modules.get("gi")
    if existente is None or getattr(existente, "__spec__", None) is not None:
        try:
            import gi

            gi.require_version("Gtk", "3.0")
            from gi.repository import Gtk  # noqa: F401

            return
        except Exception:  # pragma: no cover - ambientes sem GTK
            pass

    gi_mod = sys.modules.get("gi") or types.ModuleType("gi")
    gi_mod.require_version = lambda _n, _v: None  # type: ignore[attr-defined]
    repo_mod = sys.modules.get("gi.repository") or types.ModuleType("gi.repository")
    gtk_mod = sys.modules.get("gi.repository.Gtk") or types.ModuleType(
        "gi.repository.Gtk"
    )
    glib_mod = sys.modules.get("gi.repository.GLib") or types.ModuleType(
        "gi.repository.GLib"
    )
    for cls_name in (
        "Builder", "Window", "Button", "MessageDialog", "TextView",
        "TextBuffer", "Label", "Box",
    ):
        if not hasattr(gtk_mod, cls_name):
            setattr(gtk_mod, cls_name, type(cls_name, (), {}))
    if not hasattr(gtk_mod, "ResponseType"):
        gtk_mod.ResponseType = type(  # type: ignore[attr-defined]
            "ResponseType", (), {"OK": -5, "CANCEL": -6, "APPLY": -10}
        )
    if not hasattr(gtk_mod, "MessageType"):
        gtk_mod.MessageType = type(  # type: ignore[attr-defined]
            "MessageType", (), {"QUESTION": 2}
        )
    if not hasattr(gtk_mod, "ButtonsType"):
        gtk_mod.ButtonsType = type(  # type: ignore[attr-defined]
            "ButtonsType", (), {"NONE": 0}
        )
    glib_mod.idle_add = lambda fn, *a, **kw: fn(*a, **kw)  # type: ignore[attr-defined]
    glib_mod.timeout_add = lambda *_a, **_kw: 0  # type: ignore[attr-defined]
    glib_mod.timeout_add_seconds = lambda *_a, **_kw: 0  # type: ignore[attr-defined]
    glib_mod.source_remove = lambda *_a, **_kw: None  # type: ignore[attr-defined]
    repo_mod.Gtk = gtk_mod  # type: ignore[attr-defined]
    repo_mod.GLib = glib_mod  # type: ignore[attr-defined]
    sys.modules["gi"] = gi_mod
    sys.modules["gi.repository"] = repo_mod
    sys.modules["gi.repository.Gtk"] = gtk_mod
    sys.modules["gi.repository.GLib"] = glib_mod


_GI_REAL = exigir_gi_real(
    "o botão que tira o que faz engasgar"
)

from hefesto_dualsense4unix.app.actions import emulation_actions
from hefesto_dualsense4unix.app.actions.emulation_actions import (
    EmulationActionsMixin,
    frase_do_censo,
    frase_do_resultado,
)

_CV_MODNAME = "hefesto_dualsense4unix.integrations.camadas_vulkan"
_SLO_MODNAME = "hefesto_dualsense4unix.integrations.steam_launch_options"


# ---------------------------------------------------------------------------
# O botão está na tela, com o vizinho certo
# ---------------------------------------------------------------------------


def _botoes_do_glade() -> dict[str, ET.Element]:
    arvore = ET.parse(GLADE)
    return {
        obj.get("id", ""): obj
        for obj in arvore.iter("object")
        if obj.get("class") == "GtkButton" and obj.get("id")
    }


def test_o_botao_existe_com_rotulo_dica_e_handler() -> None:
    botao = _botoes_do_glade().get("btn_camadas_engasgo")
    assert botao is not None, "o botão sumiu do glade — a cura não tem porta"
    props = {
        p.get("name"): (p.text or "") for p in botao.findall("property")
    }
    assert props.get("label") == ROTULO
    dica = props.get("tooltip-text", "")
    assert len(dica) > 60, "a dica tem de explicar o preço, não repetir o rótulo"
    assert "devolve" in dica.lower(), "a dica precisa dizer que dá para voltar"
    assert "não prometo que resolve" in dica.lower(), (
        "a dica perdeu a ressalva do A/B de 23/08 — sem ela o botão que agora "
        "diz 'Vulkan' passa a prometer a cura que a medição derrubou"
    )
    sinais = [s.get("handler") for s in botao.findall("signal")]
    assert sinais == ["on_camadas_engasgo"]


def test_o_botao_e_vizinho_do_travar_proton() -> None:
    """Mesma caixa do `btn_proton_lock` — é a fileira Avançado da aba Sistema."""
    arvore = ET.parse(GLADE)
    for caixa in arvore.iter("object"):
        if caixa.get("class") != "GtkBox":
            continue
        ids = {
            filho.get("id")
            for child in caixa.findall("child")
            for filho in child.findall("object")
        }
        if "btn_proton_lock" in ids:
            assert "btn_camadas_engasgo" in ids, (
                "o botão saiu de perto do 'Travar Proton validado' — perdeu o "
                "vizinho que dá o contexto"
            )
            return
    pytest.fail("não achei a caixa do btn_proton_lock no glade")


def test_o_handler_esta_no_mapa_da_janela() -> None:
    """Sem a linha no `app.py`, o clique não chega a lugar nenhum."""
    fonte = (
        RAIZ / "src" / "hefesto_dualsense4unix" / "app" / "app.py"
    ).read_text(encoding="utf-8")
    assert '"on_camadas_engasgo": self.on_camadas_engasgo,' in fonte


def test_o_nome_do_botao_nao_traz_jargao() -> None:
    """O que continua banido da tela — e o que saiu da lista em 05/09/2026.

    A LISTA PERDEU A PALAVRA "VULKAN", E QUEM A TIROU FOI ELA: *"o procurar
    sobreposição de novo deveria ser Corrigir Sobreposição do Vulkan, não?"*. A
    régua nasceu dizendo que *"camada Vulkan" é jargão porque quem joga procura
    pelo que sente* — e a premissa caiu pela boca da dona da palavra, que
    procurou por ela. Os outros quatro termos ficam: nenhum deles é palavra que
    alguém digite procurando o botão.
    """
    botao = _botoes_do_glade()["btn_camadas_engasgo"]
    props = {p.get("name"): (p.text or "") for p in botao.findall("property")}
    tela = (props.get("label", "") + " " + props.get("tooltip-text", "")).lower()
    for jargao in ("camada implícita", "dword", "system.reg", "prefixo wine"):
        assert jargao not in tela, f"o jargão {jargao!r} vazou para a tela"


def test_o_rotulo_nao_promete_cura_de_engasgo() -> None:
    """O verbo dela era "corrigir", e é o único pedaço do pedido que não entrou.

    O A/B de 23/08 mediu a camada DESLIGADA pior que a ligada (p99 +4,19 ms/min
    contra +2,35; 121 picos/min contra 51, em `integrations/camadas_vulkan.py`),
    e o módulo escreve com todas as letras que *não pode prometer cura de
    engasgo*. Um rótulo com verbo de conserto desmentiria o próprio motor —
    então esta régua guarda a AUSÊNCIA dele, que é o que a decisão deixou.
    """
    props = {
        p.get("name"): (p.text or "")
        for p in _botoes_do_glade()["btn_camadas_engasgo"].findall("property")
    }
    rotulo = props.get("label", "").lower()
    for verbo in ("corrig", "consert", "resolv", "cura", "arrum"):
        assert verbo not in rotulo, (
            f"o rótulo voltou a prometer conserto ({verbo!r}) — o botão TIRA a "
            "sobreposição, e tirar não curou o engasgo quando foi medido"
        )


def test_a_janela_gtk_e_a_pagina_dizem_o_mesmo_rotulo() -> None:
    """Um botão, um nome. Dois nomes para o mesmo ato é paridade nascendo torta.

    O mesmo botão desenha em dois produtos — o `main.glade` da janela GTK e a
    página que o `WebView` renderiza —, e até 05/09/2026 eles diziam coisas
    diferentes ("Tirar o que faz engasgar" contra "Procurar sobreposição de
    novo"). Esta régua LÊ os dois; ela não digita o rótulo duas vezes.
    """
    props = {
        p.get("name"): (p.text or "")
        for p in _botoes_do_glade()["btn_camadas_engasgo"].findall("property")
    }
    from hefesto_dualsense4unix.interface import onde

    # O caminho do publicado tem DONO (`interface/onde.PUBLICADO`); digitá-lo
    # aqui seria o segundo dono da mesma pasta.
    pagina = onde.pagina("09-sistema.html", publicado=True).read_text(
        encoding="utf-8"
    )
    achado = re.search(
        r'data-gesto="procurar-camadas"[^>]*>([^<]+)</button>', pagina
    )
    assert achado is not None, (
        "o botão `procurar-camadas` sumiu da página publicada"
    )
    assert achado.group(1).strip() == props.get("label"), (
        "a janela GTK e a página publicada nomeiam o mesmo botão de formas "
        f"diferentes: {props.get('label')!r} contra {achado.group(1).strip()!r}"
    )


# ---------------------------------------------------------------------------
# frase_do_censo — o diálogo É o relatório
# ---------------------------------------------------------------------------


def _camada(
    nome: str,
    *,
    ligada: bool = True,
    presente: bool = True,
    preservada: str | None = None,
    driver: bool = False,
) -> Any:
    return SimpleNamespace(
        nome_curto=nome,
        ligada=ligada,
        presente=presente,
        preservada_por=preservada,
        e_o_driver=driver,
    )


def _prefixo(rotulo: str, *camadas: Any) -> Any:
    return SimpleNamespace(rotulo=rotulo, camadas=camadas)


class TestFraseDoCenso:
    def test_sem_prefixo_nenhum_diz_que_nao_ha_o_que_tirar(self) -> None:
        texto, tem_sobra, tem_devolucao = frase_do_censo([])
        assert "não há o que tirar" in texto.lower()
        assert (tem_sobra, tem_devolucao) == (False, False)

    def test_sem_biblioteca_nao_finge_que_olhou(self) -> None:
        """"Não achei nada" e "não consegui olhar" NÃO podem dar a mesma frase.

        Armadilha número um desta casa: os dois casos devolvem lista vazia, e
        dizer o primeiro quando o certo é o segundo faz a pessoa parar de
        procurar com o problema ainda lá. Medido em 23/08/2026 na CLI avulsa,
        que respondia exatamente essa mentira.
        """
        texto, tem_sobra, tem_devolucao = frase_do_censo([], bibliotecas=0)
        assert (tem_sobra, tem_devolucao) == (False, False)
        assert "não consegui abrir a lista" in texto.lower()
        assert "não há o que tirar" not in texto.lower(), (
            "sem biblioteca o produto não pode afirmar que os jogos estão limpos"
        )
        assert texto != frase_do_censo([])[0]

    def test_camada_ligada_vira_candidata_com_o_nome_do_jogo(self) -> None:
        texto, tem_sobra, tem_devolucao = frase_do_censo(
            [_prefixo("Jogo Bonito (222)", _camada("EOSOverlayVkLayer-Win64.json"))]
        )
        assert "Jogo Bonito (222)" in texto
        assert "EOSOverlayVkLayer-Win64.json" in texto
        assert tem_sobra is True
        assert tem_devolucao is False

    def test_o_arquivo_ausente_e_dito_e_nao_vira_ligada_seco(self) -> None:
        """O estado real da máquina dela: registrada e sem arquivo no disco."""
        texto, tem_sobra, _ = frase_do_censo(
            [_prefixo("Jogo (1)", _camada("EOSOverlayVkLayer-Win64.json", presente=False))]
        )
        assert "não está no disco" in texto
        assert tem_sobra is True

    def test_preservada_aparece_com_o_dono_e_nao_e_candidata(self) -> None:
        texto, tem_sobra, _ = frase_do_censo(
            [_prefixo("Jogo (1)", _camada("mangohud.json", preservada="MangoHud"))]
        )
        assert "fica: MangoHud" in texto
        assert tem_sobra is False

    def test_o_driver_nunca_aparece_no_relatorio(self) -> None:
        """Ele não é escolha da pessoa; mostrar convida ao clique errado."""
        texto, tem_sobra, _ = frase_do_censo(
            [_prefixo("Jogo (1)", _camada("winevulkan.json", driver=True))]
        )
        assert "winevulkan" not in texto
        assert tem_sobra is False

    def test_ja_desligada_habilita_a_devolucao(self) -> None:
        _, tem_sobra, tem_devolucao = frase_do_censo(
            [_prefixo("Jogo (1)", _camada("overlay.json", ligada=False))]
        )
        assert (tem_sobra, tem_devolucao) == (False, True)


# ---------------------------------------------------------------------------
# frase_do_resultado — silêncio não é resposta
# ---------------------------------------------------------------------------


def _resultado(**kw: Any) -> Any:
    dados: dict[str, Any] = {
        "desligadas": (), "religadas": (), "respeitadas": (), "erro": "",
    }
    dados.update(kw)
    dados["mexeu"] = bool(dados["desligadas"] or dados["religadas"])
    return SimpleNamespace(**dados)


class TestFraseDoResultado:
    def test_nada_a_mudar_e_dito_com_todas_as_letras(self) -> None:
        assert "Nada mudou" in frase_do_resultado([_resultado()], devolver=False)

    def test_conta_jogos_e_nomeia_o_que_tirou(self) -> None:
        msg = frase_do_resultado(
            [_resultado(desligadas=("a.json",)), _resultado(desligadas=("b.json",))],
            devolver=False,
        )
        assert "2 jogos" in msg
        assert "a.json" in msg and "b.json" in msg
        assert "Feche e abra o jogo" in msg

    def test_devolver_usa_o_verbo_certo_e_nao_manda_reabrir_o_jogo(self) -> None:
        msg = frase_do_resultado([_resultado(religadas=("a.json",))], devolver=True)
        assert msg.startswith("Devolvi em 1 jogo")
        assert "Feche e abra" not in msg

    def test_respeitado_e_dito_como_escolha_dela(self) -> None:
        msg = frase_do_resultado([_resultado(respeitadas=("a.json",))], devolver=False)
        assert "escolhido manter" in msg

    def test_erro_nao_e_engolido(self) -> None:
        msg = frase_do_resultado([_resultado(erro="disco cheio")], devolver=False)
        assert "disco cheio" in msg


# ---------------------------------------------------------------------------
# O worker: recusa com jogo aberto, e o clique é gesto explícito (forcar)
# ---------------------------------------------------------------------------


class _Stub(EmulationActionsMixin):
    def __init__(self) -> None:
        self.toasts: list[str] = []

    def _status_toast(self, _ctx: str, msg: str) -> None:
        self.toasts.append(msg)


@pytest.fixture()
def sincrono(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        emulation_actions,
        "_get_executor",
        lambda: SimpleNamespace(submit=lambda fn: fn()),
    )
    monkeypatch.setattr(
        emulation_actions,
        "GLib",
        SimpleNamespace(idle_add=lambda fn, *args: fn(*args)),
    )


@pytest.fixture()
def modulos_falsos(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    caixa: dict[str, Any] = {"jogo_aberto": False, "chamadas": [], "resultados": []}

    cv = types.ModuleType(_CV_MODNAME)

    def fake_curar(*, religar: bool = False, forcar: bool = False) -> list[Any]:
        caixa["chamadas"].append({"religar": religar, "forcar": forcar})
        return caixa["resultados"]

    cv.curar_todos = fake_curar  # type: ignore[attr-defined]
    cv.censo = lambda: []  # type: ignore[attr-defined]

    slo = types.ModuleType(_SLO_MODNAME)
    slo.steam_game_running = lambda: caixa["jogo_aberto"]  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, _CV_MODNAME, cv)
    monkeypatch.setitem(sys.modules, _SLO_MODNAME, slo)
    # `from pacote import módulo` resolve pelo ATRIBUTO do pacote quando ele já
    # foi importado uma vez — trocar só o `sys.modules` deixaria o worker
    # falando com o módulo de verdade e este teste mexeria nos jogos DELA.
    import hefesto_dualsense4unix.integrations as pacote

    monkeypatch.setattr(pacote, "camadas_vulkan", cv, raising=False)
    monkeypatch.setattr(pacote, "steam_launch_options", slo, raising=False)
    return caixa


class TestWorker:
    def test_jogo_aberto_recusa_e_nao_toca_em_nada(
        self, sincrono: None, modulos_falsos: dict[str, Any]
    ) -> None:
        """O Wine regrava o registro ao sair — escrever agora é perder calado."""
        modulos_falsos["jogo_aberto"] = True
        stub = _Stub()

        stub._camadas_worker(devolver=False)

        assert modulos_falsos["chamadas"] == []
        assert any("jogo aberto" in t for t in stub.toasts)

    def test_o_clique_forca_porque_a_vontade_da_gui_prevalece(
        self, sincrono: None, modulos_falsos: dict[str, Any]
    ) -> None:
        stub = _Stub()

        stub._camadas_worker(devolver=False)

        assert modulos_falsos["chamadas"] == [{"religar": False, "forcar": True}]

    def test_devolver_chega_ao_modulo_como_religar(
        self, sincrono: None, modulos_falsos: dict[str, Any]
    ) -> None:
        stub = _Stub()

        stub._camadas_worker(devolver=True)

        assert modulos_falsos["chamadas"] == [{"religar": True, "forcar": True}]

    def test_falha_do_modulo_vira_frase_e_nao_traceback(
        self, sincrono: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import hefesto_dualsense4unix.integrations as pacote

        monkeypatch.setitem(sys.modules, _CV_MODNAME, None)
        monkeypatch.delattr(pacote, "camadas_vulkan", raising=False)
        stub = _Stub()

        stub._camadas_worker(devolver=False)

        assert any("Não consegui" in t for t in stub.toasts)

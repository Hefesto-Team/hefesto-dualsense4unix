"""ENGASGO-VULKAN-01 (lado GUI) — o botão "Tirar a sobreposição Vulkan"."""
from __future__ import annotations

import ast
import html
import re
import sys

from tests.conftest import exigir_gi_real
import types
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

RAIZ = Path(__file__).resolve().parents[2]

ROTULO = "Corrigir Vulkan"


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


PAGINA = "09-sistema.html"
GESTO = "corrigir-vulkan"

DONO = (
    RAIZ / "src" / "hefesto_dualsense4unix" / "interface" / "pacotes"
    / "a09_sistema.py"
)
PAGINA_SERVIDA = (
    RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
    / "paginas" / PAGINA  # noqa-acento: nome da PASTA no disco, não leva acento
)


def _registros_de_gesto(fonte: Path) -> dict[tuple[str, str], str]:
    """`(página, nome) → nome da função`, lidos da ÁRVORE, não do texto."""
    achados: dict[tuple[str, str], str] = {}
    for no in ast.walk(ast.parse(fonte.read_text(encoding="utf-8"))):
        if not isinstance(no, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        for dec in no.decorator_list:
            if not isinstance(dec, ast.Call) or len(dec.args) < 2:
                continue
            alvo = dec.func
            chamado = (
                alvo.attr if isinstance(alvo, ast.Attribute)
                else getattr(alvo, "id", "")
            )
            pagina, nome = dec.args[0], dec.args[1]
            if (chamado == "gesto"
                    and isinstance(pagina, ast.Constant)
                    and isinstance(nome, ast.Constant)):
                achados[(pagina.value, nome.value)] = no.name
    return achados


def test_o_botao_existe_na_pagina_que_o_produto_serve() -> None:
    """O primeiro elo: sem o endereço na página, não há clique a entregar."""
    pagina = PAGINA_SERVIDA.read_text(encoding="utf-8")
    linhas = [ln for ln in pagina.splitlines() if f'data-gesto="{GESTO}"' in ln]
    assert linhas, (
        f"a página {PAGINA} não tem nenhum elemento com "
        f'`data-gesto="{GESTO}"` — o botão sumiu da tela e o handler abaixo '
        "ficou sem quem o acione.")
    assert any(ROTULO in ln for ln in linhas), (
        f"o botão de `{GESTO}` não diz mais {ROTULO!r} — se o rótulo mudou, "
        "quem decide é ela, e a palavra nova entra aqui e no gerador juntas.")
    assert any('title="' in ln for ln in linhas), (
        "o botão perdeu a dica. Ela é o que separa 'tirei o quê?' de um clique "
        "às cegas num ajuste que mexe no prefixo do jogo.")


def _as_duas_paginas() -> list[Path]:
    """O desenho (o que ela aprova) e o publicado (o que a tela carrega)."""
    import importlib.util

    from hefesto_dualsense4unix.interface import onde

    spec = importlib.util.spec_from_file_location(
        "check_o_desenho_aprovado", RAIZ / "scripts" / "check_o_desenho_aprovado.py")
    assert spec is not None and spec.loader is not None
    portao = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(portao)
    paginas = [onde.pagina(PAGINA)]
    if PAGINA not in portao.declaradas():
        paginas.append(onde.pagina(PAGINA, publicado=True))
    return paginas


def test_a_dica_nao_promete_cura_de_engasgo() -> None:
    """ARRANQUE a troca da dica em `interface/aba09.py` e este teste reprova."""
    for pagina in _as_duas_paginas():
        linha = next((ln for ln in pagina.read_text(encoding="utf-8").splitlines()
                      if f'data-gesto="{GESTO}"' in ln), "")
        achado = re.search(r'title="([^"]*)"', linha)
        assert achado, f"{pagina.name}: o ligável `{GESTO}` sumiu ou perdeu a dica"
        dica = html.unescape(achado.group(1))
        assert "Steam" in dica and "shaders" in dica, (
            f"{pagina.name}: a dica não diz o que o botão tira do jogo: {dica!r}")
        for pichacao in ("engasg", "picot", "resolv", "não cura", "prefixo"):
            assert pichacao not in dica.lower(), (
                f"{pagina.name}: a dica fala do que o botão não faz "
                f"({pichacao!r}): {dica!r}")


_LINHA_DO_EXAME = re.compile(
    r'<div class="saude"><span class="selo (?P<cls>\w+)"><span class="sg">[^<]*'
    r'</span>(?P<selo>[^<]*)</span><span class="txt" title="(?P<frase>[^"]*)">')


def test_o_exame_do_desenho_diz_a_frase_que_o_produto_pinta() -> None:
    """ARRANQUE o `frase_do_estado` do gerador e este teste reprova."""
    from hefesto_dualsense4unix.integrations import camadas_vulkan as cv

    for pagina in _as_duas_paginas():
        texto = pagina.read_text(encoding="utf-8")
        linhas = list(_LINHA_DO_EXAME.finditer(texto))
        assert linhas, f"{pagina.name}: o exame não tem linha nenhuma"
        frases = [html.unescape(m.group("frase")) for m in linhas]
        assert not [f for f in frases if "picot" in f.lower()], (
            f"{pagina.name}: o exame voltou a dizer que uma sobreposição "
            f"picota o jogo: {frases}")
        do_vulkan = [m for m in linhas
                     if html.unescape(m.group("frase")).startswith("Sobreposição Vulkan:")]
        assert len(do_vulkan) == 1, (
            f"{pagina.name}: esperava UMA linha «Sobreposição Vulkan:», "
            f"achei {len(do_vulkan)}")
        m = do_vulkan[0]
        frase = html.unescape(m.group("frase"))
        assert (m.group("cls"), m.group("selo")) == ("nt", "NOTA"), (
            f"{pagina.name}: a linha do Vulkan tem de levar o selo NOTA do "
            f"produto, e leva {m.group('selo')!r}")
        botao = next(ln for ln in texto.splitlines() if f'data-gesto="{GESTO}"' in ln)
        acesa = 'class="cadeado ligada"' in botao
        assert frase == cv.frase_do_estado(acesa), (
            f"{pagina.name}: a pílula está {'acesa' if acesa else 'apagada'} e o "
            f"exame da mesma cena diz {frase!r} — o produto pinta "
            f"{cv.frase_do_estado(acesa)!r}")


def test_o_handler_esta_registrado_no_dono_de_hoje() -> None:
    """Sem o `@gesto`, o clique não chega a lugar nenhum — o P desta sprint."""
    registros = _registros_de_gesto(DONO)
    assert (PAGINA, GESTO) in registros, (
        f"nenhuma função de `{DONO.name}` está decorada com "
        f'`@gesto("{PAGINA}", "{GESTO}")`. É a linha que substituiu o mapa de '
        "handlers de `app/app.py`, apagado com a janela GTK; sem ela o botão "
        "volta a ser desenho.")


def test_o_registro_vivo_entrega_o_clique_a_esse_handler() -> None:
    """A outra metade, e ela morde sozinha: o decorador tem de ter RODADO."""
    from hefesto_dualsense4unix.interface import pacotes

    atende = pacotes.gesto_da_pagina(PAGINA, GESTO)
    assert atende is not None, (
        f"`gesto_da_pagina({PAGINA!r}, {GESTO!r})` devolveu None — o registro "
        "está vazio para este botão e o piloto vai recusar o clique.")
    assert atende.__name__ == _registros_de_gesto(DONO)[(PAGINA, GESTO)], (
        "quem atende o clique não é a função que o dono declara. Dois donos "
        "para o mesmo botão é o defeito que o despachante existe para impedir.")
    assert atende.__module__.endswith("a09_sistema"), (
        f"o clique de `{GESTO}` foi parar em {atende.__module__} — o motor "
        "mora na aba 09.")


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
        """"Não achei nada" e "não consegui olhar" NÃO podem dar a mesma frase."""
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

    def test_o_rodape_nao_poe_a_camada_na_frente_do_quadro(self) -> None:
        """ARRANQUE o rodapé de 26/09/2026 e este teste reprova."""
        texto, tem_sobra, _ = frase_do_censo(
            [_prefixo("Jogo (1)", _camada("EOSOverlayVkLayer-Win64.json"))]
        )
        assert tem_sobra is True
        assert "não cura engasgo" in texto, texto
        for velho in ("frente de cada quadro", "Sackboy", "resolve"):
            assert velho not in texto, (velho, texto)


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

    def fake_curar(*, religar: bool = False, forcar: bool = False,
                   excluir: Any = ()) -> list[Any]:
        caixa["chamadas"].append(
            {"religar": religar, "forcar": forcar, "excluir": tuple(excluir)})
        return caixa["resultados"]

    cv.curar_todos = fake_curar  # type: ignore[attr-defined]
    cv.censo = lambda: []  # type: ignore[attr-defined]

    slo = types.ModuleType(_SLO_MODNAME)
    slo.steam_game_running = lambda: caixa["jogo_aberto"]  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, _CV_MODNAME, cv)
    monkeypatch.setitem(sys.modules, _SLO_MODNAME, slo)
    import hefesto_dualsense4unix.integrations as pacote

    monkeypatch.setattr(pacote, "camadas_vulkan", cv, raising=False)
    monkeypatch.setattr(pacote, "steam_launch_options", slo, raising=False)
    from hefesto_dualsense4unix.integrations import lista_de_exclusao

    monkeypatch.setattr(lista_de_exclusao, "appids", lambda *a, **kw: ["1599660"])
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

        assert modulos_falsos["chamadas"] == [
            {"religar": False, "forcar": True, "excluir": ("1599660",)}]

    def test_devolver_chega_ao_modulo_como_religar(
        self, sincrono: None, modulos_falsos: dict[str, Any]
    ) -> None:
        stub = _Stub()

        stub._camadas_worker(devolver=True)

        assert modulos_falsos["chamadas"] == [
            {"religar": True, "forcar": True, "excluir": ("1599660",)}]

    def test_falha_do_modulo_vira_frase_e_nao_traceback(
        self, sincrono: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import hefesto_dualsense4unix.integrations as pacote

        monkeypatch.setitem(sys.modules, _CV_MODNAME, None)
        monkeypatch.delattr(pacote, "camadas_vulkan", raising=False)
        stub = _Stub()

        stub._camadas_worker(devolver=False)

        assert any("Não consegui" in t for t in stub.toasts)

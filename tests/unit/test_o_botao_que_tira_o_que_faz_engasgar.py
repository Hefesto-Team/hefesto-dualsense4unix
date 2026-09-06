"""ENGASGO-VULKAN-01 (lado GUI) — o botão "Tirar a sobreposição Vulkan".

O botão fica na fileira Avançado da aba Sistema, ao lado do "Travar Proton
validado": mesma natureza (mexe no que a Steam guarda por jogo) e mesmo alcance
(todos os jogos). O que este arquivo garante:

- o botão EXISTE na página que o produto serve, com rótulo e dica, e o handler
  está registrado no dono de hoje — sem isso a cura fica escrita e nunca ligada,
  o defeito mais caro desta casa. **A ROTA MUDOU EM 06/09/2026**: até aqui esta
  régua lia o mapa de handlers de `app/app.py`, e a `GTK-3` apagou o arquivo com
  a janela inteira. O clique de hoje entra por `data-gesto="procurar-camadas"` na
  página 09 e sai no `@gesto` de `interface/pacotes/a09_sistema.py`, que chama o
  MESMO motor de `emulation_actions` que as classes abaixo exercitam;
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

import ast
import sys

from tests.conftest import exigir_gi_real
import types
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

RAIZ = Path(__file__).resolve().parents[2]

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


#: O ENDEREÇO DO BOTÃO, e ele é o mesmo dos dois lados: a página o carrega em
#: `data-gesto=`, o dono o declara em `@gesto(...)`. Escrito uma vez só.
PAGINA = "09-sistema.html"
GESTO = "procurar-camadas"

#: O DONO DE HOJE. Até 06/09/2026 quem atendia o clique era
#: `app/app.py`, o mapa de handlers da janela GTK — e a `GTK-3`
#: (`D-0609-GTK-LEVA-INTEIRA`) apagou o arquivo do disco. O ato não morreu com
#: ela: `emulation_actions` continua sendo o motor (as duas frases puras e o
#: `_camadas_worker` abaixo), e quem entrega o clique a ele agora é o registro
#: `@gesto` da aba 09.
DONO = (
    RAIZ / "src" / "hefesto_dualsense4unix" / "interface" / "pacotes"
    / "a09_sistema.py"
)
PAGINA_SERVIDA = (
    RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
    / "paginas" / PAGINA  # noqa-acento: nome da PASTA no disco, não leva acento
)


def _registros_de_gesto(fonte: Path) -> dict[tuple[str, str], str]:
    """`(página, nome) → nome da função`, lidos da ÁRVORE, não do texto.

    POR QUE `ast` E NÃO `in fonte`, e a cicatriz é desta mesma sprint: em
    23/08/2026 `test_o_install_materializa_o_curador_sem_flag` era `grep` no
    `install.sh` e **passava** com o bloco inteiro trancado atrás de um
    `if false` — a linha continuava escrita e inalcançável. Uma busca por texto
    dá o mesmo verde para uma linha viva, uma linha comentada e uma linha citada
    dentro de um docstring.

    E AQUI ELA DARIA, medido em 06/09/2026: com o decorador APAGADO do
    `a09_sistema.py`, `grep -c '"procurar-camadas"'` no mesmo arquivo ainda
    responde **2** — a literal sobrevive num comentário e na chamada
    `_confirmado(o, "procurar-camadas")`. A árvore só enxerga o decorador que o
    interpretador vai executar.
    """
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
    """O primeiro elo: sem o endereço na página, não há clique a entregar.

    A página servida é a que o `WebKit2.WebView` carrega — e o rótulo dela vem
    do gerador (`interface/aba09.py`), nunca deste arquivo. Aqui só se cobra
    que os dois digam a mesma palavra.
    """
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


def test_o_handler_esta_registrado_no_dono_de_hoje() -> None:
    """Sem o `@gesto`, o clique não chega a lugar nenhum — o P desta sprint."""
    registros = _registros_de_gesto(DONO)
    assert (PAGINA, GESTO) in registros, (
        f"nenhuma função de `{DONO.name}` está decorada com "
        f'`@gesto("{PAGINA}", "{GESTO}")`. É a linha que substituiu o mapa de '
        "handlers de `app/app.py`, apagado com a janela GTK; sem ela o botão "
        "volta a ser desenho.")


def test_o_registro_vivo_entrega_o_clique_a_esse_handler() -> None:
    """A outra metade, e ela morde sozinha: o decorador tem de ter RODADO.

    A árvore acima prova que a linha está escrita no dono. Ela não prova que o
    módulo é alcançado pelo carregador — um `a09_sistema.py` fora do
    `_carregar_tudo()` passaria no teste anterior e continuaria com o botão
    mudo. Quem responde isso é o registro depois do import.
    """
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
#
# LEIA ISTO ANTES DE ACREDITAR QUE ESTA SEÇÃO MEDE O PRODUTO DE HOJE.
# `EmulationActionsMixin._camadas_worker` era o que o botão do glade acionava,
# e desde a `GTK-3` **nada o chama**: o único chamador era
# `on_camadas_engasgo`, ligado pelo mapa de handlers de `app/app.py`, e os dois
# saíram do disco com a janela. O caminho vivo é
# `a09_sistema.procurar_camadas`, que chama `camadas_vulkan.curar_todos`
# direto e tem o SEU próprio portão de jogo aberto — coberto por
# `test_a_09_sistema_fecha_a_paridade.py::test_as_camadas_recusam_com_jogo_aberto`.
# Os quatro nós abaixo continuam de pé porque o dublê e as duas frases puras
# ainda são de `emulation_actions`, e porque apagar régua de código vivo por
# suspeita é como se perde cobertura de graça — mas quem for cobrar a recusa do
# PRODUTO cobra lá, não aqui. `emulation_actions.py` não é da posse desta
# sprint; a órfã está relatada na entrega.
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

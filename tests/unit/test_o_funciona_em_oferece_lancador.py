"""A coluna e a lista de jogos dizem DE ONDE O JOGO VEM, e o produto casa sozinho."""
from __future__ import annotations

import json
import pathlib
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]


if str(RAIZ / "src") not in sys.path:  # pragma: no cover - trava de caminho
    sys.path.insert(0, str(RAIZ / "src"))

from hefesto_dualsense4unix.integrations import jogos_locais as jl
from hefesto_dualsense4unix.integrations.identidade_de_janela import (
    classe_do_umu_id,
)
from hefesto_dualsense4unix.interface.pacotes import (
    Contexto,
    a10_perfis as a10,
)
from hefesto_dualsense4unix.profiles import loader
from tests.unit.test_o_censo_responde_como_o_lancador_responde import plantar_o_registro
from hefesto_dualsense4unix.profiles import simple_match as sm
from hefesto_dualsense4unix.profiles.schema import (
    MatchAny,
    MatchCriteria,
    Profile,
)

HEROIC_ID = "com.heroicgameslauncher.hgl"

UMU_DO_GOTG = "umu-1088850"

#: o erro de forma: quem responde é `identidade_de_janela`, e é a ele que a
CHAVE_DO_GOTG = classe_do_umu_id(UMU_DO_GOTG)

BAIXADO: dict[str, Any] = {
    "app_name": "63a665088eb1480298f1e57943b225d8",
    "title": "Marvel's Guardians of the Galaxy",
    "is_installed": True,
    "install": {"executable": "retail/gotg.exe",
                "install_path": "/casa/Games/Heroic/MarvelGOTG",
                "is_dlc": False},
}

MESA = [
    {"pref": "p1", "uniq": "aabbcc000001", "jogador": 1, "cor": "cosmic-red",
     "nome": "Cosmic Red", "via": "USB", "transporte": "usb", "alvo": True,
     "mascara": "DualSense"},
]


class PonteDeMentira:
    """Daemon calado: o gesto grava no disco e nada é reaplicado."""

    def profile_switch(self, nome: str) -> bool:
        return True

    def chamar(self, metodo: str, *a: Any, **kw: Any) -> Any:
        return True

    def resultado(self, metodo: str, *a: Any, **kw: Any) -> Any:
        return {}


def _ctx() -> Contexto:
    return Contexto(state={"active_profile": None}, mesa=list(MESA),
                    conectados=list(MESA), estados={})


def _heroic(lar: pathlib.Path, itens: list[dict[str, Any]]) -> None:
    """A biblioteca do Heroic num lar de mentira, com o `umu.json` junto."""
    cache = lar / ".var/app" / HEROIC_ID / "config/heroic/store_cache"
    cache.mkdir(parents=True, exist_ok=True)
    (cache / "legendary_library.json").write_text(
        json.dumps({"library": itens}), encoding="utf-8")
    plantar_o_registro(cache.parent, {
        str(i["app_name"]): {"is_dlc": bool((i.get("install") or {}).get("is_dlc"))}
        for i in itens if i.get("is_installed")})
    (cache / "umu.json").write_text(
        json.dumps({f"legendary_{i['app_name']}": UMU_DO_GOTG for i in itens}),
        encoding="utf-8")


@pytest.fixture(autouse=True)
def _caderno_limpo(monkeypatch: pytest.MonkeyPatch) -> None:
    """O caderno das janelas é memoizado no DONO — zerá-lo é obrigatório."""
    monkeypatch.setattr(jl, "_NOMES_DAS_JANELAS", None, raising=False)
    monkeypatch.setattr(a10, "_ESCOLHIDO", "", raising=False)
    monkeypatch.setattr(a10, "_ARMADO", None, raising=False)
    monkeypatch.setattr(a10, "_ARMADO_REBAIXAR", None, raising=False)
    monkeypatch.setattr(a10, "_DESFECHO", None, raising=False)


@pytest.fixture
def maquina_pelada(monkeypatch: pytest.MonkeyPatch,
                   tmp_path: pathlib.Path) -> pathlib.Path:
    """UMA MÁQUINA SEM NADA: sem Steam, sem Heroic, sem Lutris, sem `.desktop`."""
    vazio = tmp_path / "lar-pelado"
    vazio.mkdir()
    de_verdade, assinar = jl.jogos_com_janela, jl.assinatura_das_janelas
    monkeypatch.setattr(jl, "jogos_com_janela",
                        lambda *_a, **_k: de_verdade(lar=vazio, pastas=[vazio]))
    monkeypatch.setattr(jl, "assinatura_das_janelas",
                        lambda *_a, **_k: assinar(lar=vazio, pastas=[vazio]))
    monkeypatch.setattr(a10, "_nomes_dos_jogos", lambda: {})
    return vazio


@pytest.fixture
def maquina_dela(monkeypatch: pytest.MonkeyPatch,
                 tmp_path: pathlib.Path) -> pathlib.Path:
    """A MÁQUINA COM DUAS ORIGENS: o Heroic com o jogo baixado, e a Steam."""
    lar = tmp_path / "lar-dela"
    lar.mkdir()
    _heroic(lar, [BAIXADO])
    de_verdade, assinar = jl.jogos_com_janela, jl.assinatura_das_janelas
    monkeypatch.setattr(jl, "jogos_com_janela",
                        lambda *_a, **_k: de_verdade(lar=lar, pastas=[lar]))
    monkeypatch.setattr(jl, "assinatura_das_janelas",
                        lambda *_a, **_k: assinar(lar=lar, pastas=[lar]))
    monkeypatch.setattr(a10, "_nomes_dos_jogos",
                        lambda: {"1245620": "ELDEN RING"})
    return lar


def _o_disco_tem(monkeypatch: pytest.MonkeyPatch, *perfis: Any) -> list[Any]:
    todos = list(perfis)
    monkeypatch.setattr(loader, "load_all_profiles", lambda *a, **k: todos)
    monkeypatch.setattr(
        loader, "load_profile",
        lambda nome, *a, **k: next(p for p in todos if p.name == nome))
    return todos


def _aberto_no_editor(monkeypatch: pytest.MonkeyPatch, prof: Any) -> None:
    """O perfil que o editor abriu — o que o clique na linha da lista deixa."""
    monkeypatch.setattr(a10, "_ESCOLHIDO", prof.name, raising=False)


def _escolher(rotulo: str) -> dict[str, Any]:
    """O clique que o piloto manda: o `value` do `<select>` e o evento."""
    return {"valor": rotulo, "rotulo": rotulo, "evento": "change",
            "tipo": "select"}


def test_a_pagina_nova_nao_pinta_o_funciona_em(
    maquina_dela: pathlib.Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A aba Perfis do todo tirou o «Funciona em» (5faca7e8a): o pacote não o pinta no vazio."""
    _o_disco_tem(monkeypatch,
                 Profile(name="GOTG", priority=80,
                         match=MatchCriteria(window_class=[CHAVE_DO_GOTG])))

    assert 'select[data-hef="editor.ambiente"]' not in a10.pacote(_ctx())["blocos"]


def test_a_maquina_sem_lancador_nenhum_nao_oferece_jogo(
    maquina_pelada: pathlib.Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """**A ORDEM DE PRODUTO:** o produto é para qualquer pessoa, não para esta bancada."""
    _o_disco_tem(monkeypatch, Profile(name="Universal", priority=0,
                                      match=MatchAny()))

    assert a10.pacote(_ctx())["blocos"][a10.SELETOR_DOS_JOGOS] == ""


def test_o_perfil_que_ja_existe_diz_de_onde_ele_vem(
    maquina_dela: pathlib.Path,
) -> None:
    """As cinco leituras, e as duas últimas são o disco do usuário de 11/09/2026."""
    def vem_de(match: Any) -> str | None:
        return sm.procedencia_do_match(match, a10._lancador_da_chave)

    assert vem_de(MatchCriteria(window_class=["steam_app_1245620"])) == "Steam"
    assert vem_de(MatchCriteria(process_name=["steam"])) == "Steam"
    assert vem_de(MatchAny()) == "Qualquer jogo"
    assert vem_de(sm.SIMPLE_MATCH_PRESETS["browser"]) == "Navegação"
    assert vem_de(MatchCriteria(window_class=[CHAVE_DO_GOTG])) == "Heroic"
    assert vem_de(MatchCriteria(process_name=["guard"])) == jl.LANCADOR_DIRETO
    assert vem_de(
        MatchCriteria(window_class=["Hefesto-Dualsense4Unix"])
    ) == jl.LANCADOR_DIRETO


def test_a_regra_que_a_tela_nao_sabe_mostrar_continua_travando(
    maquina_dela: pathlib.Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A válvula do R-12 não morreu — ela só passou a falar a língua nova."""
    fino = MatchCriteria(window_title_regex="Elden Ring.*",
                         process_name=["eldenring.exe"])
    _o_disco_tem(monkeypatch, Profile(name="Fino", priority=90, match=fino))

    # a página nova não tem o «Funciona em» (o pacote não manda mais `editor.ambiente*`); a válvula
    # mora no editor do produto, que os gestos de gravar ainda consultam
    editor = a10._editor_de(Profile(name="Fino", priority=90, match=fino))

    assert editor["ambiente"] is None
    assert editor["ambiente_travado"] is True
    assert "título de janela" in editor["ambiente_recado"]
    assert "editor.ambiente" not in a10.pacote(_ctx())


def test_a_lista_de_baixo_segue_o_campo_de_cima(
    maquina_dela: pathlib.Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Escolhido «Heroic», o campo «Nome do Jogo» oferece os jogos do Heroic."""
    do_heroic = a10._html_dos_jogos("Heroic")
    da_steam = a10._html_dos_jogos("Steam")

    assert CHAVE_DO_GOTG in do_heroic and "1245620" not in do_heroic
    assert "1245620" in da_steam and CHAVE_DO_GOTG not in da_steam
    inteira = a10._html_dos_jogos("Qualquer jogo")
    assert CHAVE_DO_GOTG in inteira and "1245620" in inteira


def test_a_linha_da_lista_diz_nome_e_codigo_e_nunca_o_executavel(
    maquina_dela: pathlib.Path,
) -> None:
    """``ELDEN RING · 1245620``, e nunca ``eldenring.exe`` — item 12 da lista dela."""
    html = a10._html_dos_jogos("Steam")
    assert 'label="ELDEN RING · 1245620"' in html
    assert ".exe" not in html

    do_heroic = a10._html_dos_jogos("Heroic")
    assert 'label="Marvel&#x27;s Guardians of the Galaxy"' in do_heroic or (
        "label=\"Marvel's Guardians of the Galaxy\"" in do_heroic)
    assert f'value="{CHAVE_DO_GOTG}"' in do_heroic


@pytest.mark.parametrize("caminho", ["mockup/10-perfis.html",
                                    "src/hefesto_dualsense4unix/interface/"
                                    "paginas/10-perfis.html"])
def test_o_jargao_saiu_das_duas_telas(caminho: str) -> None:
    """O desenho e a página publicada dizem a MESMA coisa — ou nenhuma das duas.

    15/10/2026: o «Funciona em:» saiu da aba (o «Aplicar em» e o «Nome do jogo» ocupam o lugar), e
    com ele o jargão. MORDIDA: devolver o `<select data-hef="editor.ambiente">` à página reprova.
    """
    html = (RAIZ / caminho).read_text(encoding="utf-8")

    assert 'data-hef="editor.ambiente"' not in html, (
        f"o «Funciona em:» voltou a `{caminho}`; o editor novo escolhe pelo «Nome do jogo» "
        f"e pelo «Aplicar em»")
    for jargao in ("Jogo da Steam", "Jogo (pela janela)", ">Jogo<"):
        assert jargao not in html, (
            f"“{jargao}” voltou a `{caminho}` — é o jargão de implementação que ela mandou "
            f"tirar em 11/09/2026")
    assert 'data-hef="editor.estilo"' in html
    assert ">Estilo de jogo:</span>" in html


def test_a_coluna_fala_a_lingua_do_campo(maquina_dela: pathlib.Path) -> None:
    """`procedência · nome · código`, e o executável nunca quando há nome."""
    def coluna(match: Any) -> str:
        return a10._quando_usar(match, "Só neste programa")

    assert coluna(MatchCriteria(window_class=["steam_app_1245620"])) == (
        "Steam · ELDEN RING · 1245620")
    assert coluna(MatchCriteria(window_class=[CHAVE_DO_GOTG])) == (
        "Heroic · Marvel's Guardians of the Galaxy")
    assert ".exe" not in coluna(MatchCriteria(window_class=[CHAVE_DO_GOTG]))
    assert coluna(MatchCriteria(process_name=["mk1.exe"])) == (
        f"{jl.LANCADOR_DIRETO} · mk1.exe")
    assert coluna(MatchCriteria(window_class=["steam_app_9999999"])) == (
        "Steam · 9999999")
    assert coluna(sm.SIMPLE_MATCH_PRESETS["browser"]) == "Navegação"


def test_a_coluna_nao_engole_a_disputa_nem_a_frase_do_produto(
    maquina_dela: pathlib.Path,
) -> None:
    """As duas frases do produto que FICAM, e as duas ficam por conteúdo."""
    disputa = "Sempre — 2 disputam, este vence"
    assert a10._quando_usar(MatchAny(), disputa) == disputa

    fino = MatchCriteria(window_title_regex="Elden Ring.*",
                         process_name=["eldenring.exe"])
    assert a10._quando_usar(fino, "Só neste programa") == "Só neste programa"


def test_a_coluna_traduzida_chega_a_lupa_e_a_lista_so_mostra_nome_e_datas(
    maquina_dela: pathlib.Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A lista da tela é Nome, Criado em e Modificado em; o «Quando usar» vive só para a lupa."""
    _o_disco_tem(monkeypatch,
                 Profile(name="GOTG", priority=90,
                         match=MatchCriteria(window_class=[CHAVE_DO_GOTG])),
                 Profile(name="Elden Ring", priority=85,
                         match=MatchCriteria(
                             window_class=["steam_app_1245620"])))
    monkeypatch.setattr(a10, "_PROCURA", "heroic · marvel", raising=False)

    fora = a10.pacote(_ctx())

    assert "perfis.linha.quando" not in fora, "a coluna «Quando usar» saiu da tela"
    assert fora["perfis.linha.nome"] == ["GOTG"], "a lupa mede a frase traduzida"
    assert fora["perfis.linha.criado"] == fora["perfis.linha.modificado"] == ["—"]
    assert "<td" in fora["blocos"][a10.SELETOR_DA_LISTA]


def test_a_lupa_acha_o_jogo_pelo_nome_que_a_coluna_passou_a_mostrar(
    maquina_dela: pathlib.Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A tradução vem ANTES do filtro — senão a lupa mede a frase de ontem."""
    _o_disco_tem(monkeypatch,
                 Profile(name="GOTG", priority=90,
                         match=MatchCriteria(window_class=[CHAVE_DO_GOTG])),
                 Profile(name="Elden Ring", priority=85,
                         match=MatchCriteria(
                             window_class=["steam_app_1245620"])))
    monkeypatch.setattr(a10, "_PROCURA", "guardians", raising=False)

    fora = a10.pacote(_ctx())

    assert fora["perfis.linha.nome"] == ["GOTG"]


def test_o_clique_no_campo_arrasta_a_coluna_junto(
    maquina_dela: pathlib.Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """**O CLIQUE:** escolher o jogo do Heroic no campo e a coluna muda junto, sem recarregar."""
    prof = Profile(name="Guardioes", priority=80, match=MatchAny())
    _o_disco_tem(monkeypatch, prof)
    _aberto_no_editor(monkeypatch, prof)
    monkeypatch.setattr(a10, "_PROCURA", "heroic", raising=False)

    antes = a10.pacote(_ctx())["perfis.linha.nome"]
    a10.editor_jogo(_ctx(), _escolher(CHAVE_DO_GOTG), PonteDeMentira())
    depois = a10.pacote(_ctx())["perfis.linha.nome"]

    assert antes == []
    assert depois == ["Guardioes"]

"""O perfil que nasce na Lançadores diz o jogo e leva a máscara (20/10/2026).

Medido no piloto (lar de mentira): o perfil de um emulador com TRÊS classes de janela abria com o
«Nome do jogo» vazio aos 3, 4,5, 7 e 9 s. Causa: `_nascer` gravava só nome, regra e prioridade, e
o editor só diz o jogo da regra de uma linha (`simple_extra`). Cura: `Profile.nome_do_jogo` e a
máscara do prontuário em `mode`. As MORDIDAS estão na docstring de cada teste que a leva.
"""
from __future__ import annotations

from typing import Any

import pytest


from hefesto_dualsense4unix.interface.pacotes import Contexto, a10_perfis
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.schema import (
    MatchAny,
    MatchCriteria,
    PonteConfirmada,
    Profile,
)
from hefesto_dualsense4unix.profiles.simple_match import simple_extra

EMULADOR = ("pcsx2", "PCSX2-qt", "pcsx2-qt-nogui")


class Ponte:
    """O daemon calado: nada sai da máquina de teste."""

    def chamar(self, metodo: str, *a: Any, **kw: Any) -> Any:
        return True

    def resultado(self, metodo: str, *a: Any, **kw: Any) -> Any:
        return {}

    def profile_reaplicar(self, nome: str, *, prender: bool = False) -> bool:
        return True


@pytest.fixture(autouse=True)
def _memoria_limpa(monkeypatch: pytest.MonkeyPatch) -> None:
    for atributo, valor in (("_ESCOLHIDO", ""), ("_ARMADO", None), ("_PROCURA", ""),
                            ("_PINTADO_PARA", ""), ("_ULTIMO_TIQUE", 0.0)):
        monkeypatch.setattr(a10_perfis, atributo, valor, raising=False)


def _ctx() -> Contexto:
    return Contexto(state={}, mesa=[], conectados=[], estados={})


def _o_que_nasceu(nome: str) -> Profile:
    achados = [x for x in loader.load_all_profiles() if x.name == nome]
    assert achados, f"o perfil {nome!r} não está no disco"
    return achados[0]


def test_a_regra_de_varias_classes_nao_diz_o_jogo_sozinha() -> None:
    """A premissa da cura: sem o nome gravado, `simple_extra` fica vazio."""
    assert simple_extra(MatchCriteria(window_class=list(EMULADOR))) == ""


def test_o_editor_diz_o_jogo_do_emulador_a_cada_tique() -> None:
    """MORDIDA: voltar o campo ao `simple_extra` sozinho deixa o editor vazio."""
    frase = a10_perfis.criar_para_o_jogo(
        _ctx(), Ponte(), classes=EMULADOR, nome_do_jogo="Metal Slug Anthology")
    assert frase == "Perfil criado: Metal Slug Anthology"
    perfil = _o_que_nasceu("Metal Slug Anthology")
    assert perfil.nome_do_jogo == "Metal Slug Anthology"
    assert simple_extra(perfil.match) == ""
    # o campo que ela digita é pintado UMA vez por perfil (`_uma_vez_so`); os tiques seguintes
    # não o repintam, e nenhum pode apagá-lo
    assert a10_perfis.pacote(_ctx())["editor.jogo"] == "Metal Slug Anthology"
    for tique in range(2):
        assert a10_perfis.pacote(_ctx()).get("editor.jogo", "Metal Slug Anthology") == (
            "Metal Slug Anthology"), f"o campo «Nome do jogo» esvaziou no tique {tique + 2}"


def test_o_jogo_de_um_titulo_so_tambem_nasce_dizendo_o_nome() -> None:
    """O caminho do «Kyty» (a regra é um título) passa pelo `_nascer` sem o argumento novo."""
    regra = MatchCriteria(window_title_regex=r"\bPPSA21567\b")
    a10_perfis._nascer(_ctx(), Ponte(), regra, "Astro Bot")
    assert _o_que_nasceu("Astro Bot").nome_do_jogo == "Astro Bot"
    assert a10_perfis.pacote(_ctx())["editor.jogo"] == "Astro Bot"


def test_o_novo_da_aba_perfis_nao_inventa_jogo() -> None:
    """O «Novo» (nome de fábrica, regra qualquer) nasce sem nome de jogo."""
    a10_perfis._nascer(_ctx(), Ponte(), MatchAny(), "Novo perfil")
    assert _o_que_nasceu("Novo perfil").nome_do_jogo is None


def test_o_perfil_antigo_sem_o_campo_carrega_igual() -> None:
    perfil = Profile.model_validate({"name": "Antigo", "match": {"type": "any"}})
    assert perfil.nome_do_jogo is None
    assert "nome_do_jogo" not in perfil.model_dump(mode="json")
    sujo = Profile.model_validate({"name": "Sujo", "match": {"type": "any"}, "nome_do_jogo": "  "})
    assert sujo.nome_do_jogo is None


def _um_jogo_da_steam_com_ponte(mascara: str | None, kind: str = "gamepad") -> None:
    ponte = PonteConfirmada(kind=kind, gamepad_flavor=mascara)  # type: ignore[arg-type]
    loader.save_profile(
        Profile(name="Confirmado antes", match=MatchCriteria(window_class=["steam_app_1245620"]),
                priority=50, ponte=ponte),
        origem="régua")


def test_o_jogo_com_ponte_de_gamepad_nasce_com_a_mascara() -> None:
    """MORDIDA: tirar o `mode=` do `_nascer` deixa o perfil sem a máscara que o jogo pede.

    (D-2010-O-PERFIL-NASCE-COM-O-JOGO-E-A-MASCARA-QUE-O-PRONTUARIO-CONFIRMOU)
    """
    _um_jogo_da_steam_com_ponte("xbox")
    a10_perfis.criar_para_o_jogo(
        _ctx(), Ponte(), classes=("steam_app_1245620",), nome_do_jogo="Elden Ring")
    perfil = _o_que_nasceu("Elden Ring")
    assert perfil.mode is not None
    assert (perfil.mode.kind, perfil.mode.gamepad_flavor) == ("gamepad", "xbox")
    assert perfil.ponte is None, "o carimbo de confirmação não se copia: ninguém provou aqui"


def test_sem_ponte_confirmada_o_perfil_segue_sem_mascara() -> None:
    """Quando o produto não sabe, nasce sem opinião: o padrão que o daemon aplica."""
    a10_perfis.criar_para_o_jogo(
        _ctx(), Ponte(), classes=("steam_app_1245620",), nome_do_jogo="Elden Ring")
    assert _o_que_nasceu("Elden Ring").mode is None
    a10_perfis.criar_para_o_jogo(
        _ctx(), Ponte(), classes=EMULADOR, nome_do_jogo="Metal Slug Anthology")
    assert _o_que_nasceu("Metal Slug Anthology").mode is None


@pytest.mark.parametrize(("kind", "mascara"), [("native", None), ("desktop", None),
                                              ("gamepad", None)])
def test_ponte_que_nao_diz_mascara_nao_inventa_uma(kind: str, mascara: str | None) -> None:
    _um_jogo_da_steam_com_ponte(mascara, kind=kind)
    a10_perfis.criar_para_o_jogo(
        _ctx(), Ponte(), classes=("steam_app_1245620",), nome_do_jogo="Elden Ring")
    assert _o_que_nasceu("Elden Ring").mode is None


def test_reescrever_a_regra_larga_o_nome_antigo(monkeypatch: pytest.MonkeyPatch) -> None:
    """MORDIDA: sem o `prof.nome_do_jogo = None`, o nome de antes sobrevive à regra nova."""
    a10_perfis.criar_para_o_jogo(
        _ctx(), Ponte(), classes=("steam_app_1245620",), nome_do_jogo="Elden Ring")
    assert _o_que_nasceu("Elden Ring").nome_do_jogo == "Elden Ring"
    monkeypatch.setattr(a10_perfis, "_nomes_dos_jogos", lambda: {})
    a10_perfis.editor_jogo(_ctx(), {"valor": "1599660", "evento": "change"}, Ponte())
    perfil = _o_que_nasceu("Elden Ring")
    assert simple_extra(perfil.match) == "1599660"
    assert perfil.nome_do_jogo is None


def test_o_arquivo_do_perfil_novo_leva_o_nome_no_disco() -> None:
    a10_perfis.criar_para_o_jogo(
        _ctx(), Ponte(), classes=EMULADOR, nome_do_jogo="Metal Slug Anthology")
    achados = [p for p in loader.profiles_dir().iterdir()
               if '"nome_do_jogo": "Metal Slug Anthology"' in p.read_text(encoding="utf-8")]
    assert len(achados) == 1, sorted(p.name for p in loader.profiles_dir().iterdir())


def test_o_editor_do_produto_diz_o_jogo_para_todo_chamador() -> None:
    """MORDIDA: `perfis_web._pacote_do_editor` de volta ao `simple_extra` deixa o campo vazio.

    O dono do campo é a camada do produto, que enche o editor da aba e o do piloto de uma aba
    (`perfis_vivos`); a aba só traduz o appid em nome.
    """
    from hefesto_dualsense4unix.app.actions import perfis_web

    a10_perfis.criar_para_o_jogo(
        _ctx(), Ponte(), classes=EMULADOR, nome_do_jogo="Metal Slug Anthology")
    perfil = _o_que_nasceu("Metal Slug Anthology")
    editor = perfis_web.pacote_da_aba([perfil], ativo=None, editado=perfil)["editor"]
    assert editor["jogo"] == "Metal Slug Anthology"


def test_o_criar_da_aba_lancadores_chega_ao_editor(monkeypatch: pytest.MonkeyPatch) -> None:
    """O gesto da 07 (`_criar_o_perfil_de`), com as janelas do emulador, até o campo da 10."""
    from hefesto_dualsense4unix.interface import desenho_dos_lancadores as desenho
    from hefesto_dualsense4unix.interface.pacotes import a07_lancadores

    monkeypatch.setattr(a07_lancadores._ESCOLHA, "janelas", {"emulador:pcsx2": EMULADOR})
    monkeypatch.setattr(a07_lancadores._ESCOLHA, "titulos", {})
    jogo = desenho.JogoParaEscolher("emulador:pcsx2", "PCSX2 — emulador")
    assert a07_lancadores._criar_o_perfil_de(_ctx(), Ponte(), jogo) == "Perfil criado: PCSX2"
    assert a10_perfis.pacote(_ctx())["editor.jogo"] == "PCSX2"


def test_o_novo_com_o_jogo_em_foco_leva_a_mascara_e_nao_o_nome() -> None:
    """O «Novo» passa pelo mesmo `_nascer`: com o jogo confirmado em foco, a máscara vem junto."""
    _um_jogo_da_steam_com_ponte("nintendo")
    contexto = Contexto(state={"window_detect_last_class": "steam_app_1245620"}, mesa=[],
                        conectados=[], estados={})
    a10_perfis.novo(contexto, {}, Ponte())
    perfil = _o_que_nasceu("Novo perfil")
    assert perfil.mode is not None
    assert (perfil.mode.kind, perfil.mode.gamepad_flavor) == ("gamepad", "nintendo")
    assert perfil.nome_do_jogo is None

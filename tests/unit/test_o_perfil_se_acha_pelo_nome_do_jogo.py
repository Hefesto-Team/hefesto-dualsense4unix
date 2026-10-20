"""O-PERFIL-SE-ACHA-PELO-NOME-DO-JOGO-E-SE-APLICA-EM-QUATRO-ALVOS-01 — o editor e o desempate.

Medido antes de curar (15/10/2026): o editor perguntava «Funciona em», «Preferência» (um slider de
prioridade) e tinha o «Detectar»; o perfil se achava por um rótulo e não pelo NOME DO JOGO, e dois
perfis do mesmo jogo empatavam por ordem de arquivo. A tela nova tem «Nome do jogo», «Aplicar em»
(quatro alvos), «Quando» (só no alvo Eventos) e «Qual vale primeiro»; o desempate do manager é a
prioridade e, no empate, o perfil que a semeadura fez e ela nunca mexeu.

MORDIDAS (cada uma foi feita e viu reprovar):

* voltar a `_chave_de_selecao` à chave de dois termos -> o perfil editado vence o automático
  empatado;
* devolver o «Preferência» ao desenho -> `test_o_editor_nao_pergunta_mais_o_que_ele_ja_sabe`.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import MatchCriteria, Profile
from hefesto_dualsense4unix.testing import FakeController

RAIZ = Path(__file__).resolve().parents[2]
JOGO = "steam_app_1245620"


def _o_que_chega_aos_olhos(html: str) -> str:
    """O HTML sem comentário, estilo e roteiro: o que o desenho de fato diz."""
    sem = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    return re.sub(r"<(style|script)\b.*?</\1>", "", sem, flags=re.S)


@pytest.fixture
def disco(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    alvo = tmp_path / "profiles"
    alvo.mkdir()

    def _falso(ensure: bool = False) -> Path:
        if ensure:
            alvo.mkdir(parents=True, exist_ok=True)
        return alvo

    monkeypatch.setattr(loader, "profiles_dir", _falso)
    return alvo


def _manager(ativo: str | None = None) -> ProfileManager:
    controle = FakeController()
    controle.connect()
    loja = StateStore()
    if ativo is not None:
        loja.set_active_profile(ativo)
    return ProfileManager(controller=controle, store=loja)


def _do_jogo(nome: str, **resto: object) -> Profile:
    return Profile(name=nome, match=MatchCriteria(window_class=[JOGO]),
                   priority=loader.PRIORIDADE_DO_PERFIL_DE_JOGO, **resto)  # type: ignore[arg-type]


def test_o_editor_nao_pergunta_mais_o_que_ele_ja_sabe() -> None:
    """MORDIDA: devolver «Preferência», «Detectar» ou a contagem ao desenho reprova."""
    html = _o_que_chega_aos_olhos((RAIZ / "mockup" / "10-perfis.html").read_text(encoding="utf-8"))
    for dito in ("Nome do jogo:", "Aplicar em:", "Estilo de jogo:", "Qual vale primeiro"):
        assert dito in html, f"o editor perdeu o campo {dito!r}"
    for colunas in ("Nome<", "Criado em", "Modificado"):
        assert colunas in html, f"a lista perdeu a coluna {colunas!r}"
    for velho in ("Preferência", "Detectar", "Funciona em", "controles com ajuste próprio"):
        assert velho not in html, f"{velho!r} voltou ao desenho"


def test_o_automatico_vence_o_empate_mesmo_com_o_editado_ativo(disco: Path) -> None:
    """MORDIDA: a chave de dois termos devolve o empate à ordem de arquivo (ou ao incumbente)."""
    loader.save_profile(_do_jogo("Elden Ring"))
    editado = _do_jogo("Elden Ring 2", estilo="fps")
    loader.save_profile(editado)
    assert not loader.e_perfil_de_jogo_automatico(editado)
    assert loader.e_perfil_de_jogo_automatico(_do_jogo("Elden Ring"))

    for ativo in (None, "Elden Ring", "Elden Ring 2"):
        escolhido = _manager(ativo).select_for_window({"wm_class": JOGO})
        assert escolhido is not None
        assert escolhido.name == "Elden Ring", f"ativo={ativo!r}: o automático devia vencer"


def test_a_prioridade_maior_vence_o_automatico(disco: Path) -> None:
    """O desempate só vale no EMPATE: quem a pessoa subiu na ordem vence o automático."""
    loader.save_profile(_do_jogo("Elden Ring"))
    loader.save_profile(_do_jogo("Elden Ring 2", estilo="fps")
                        .model_copy(update={"priority": loader.PRIORIDADE_DO_PERFIL_DE_JOGO + 1}))
    escolhido = _manager().select_for_window({"wm_class": JOGO})
    assert escolhido is not None and escolhido.name == "Elden Ring 2"


def test_entre_dois_do_usuario_o_empate_segue_o_incumbente(disco: Path) -> None:
    """Dois editados e empatados: quem a pessoa deixou valendo continua (EMPATE-01 não regride)."""
    for nome in ("Elden Ring A", "Elden Ring B"):
        loader.save_profile(_do_jogo(nome, estilo="fps"))
    for ativo in ("Elden Ring A", "Elden Ring B"):
        escolhido = _manager(ativo).select_for_window({"wm_class": JOGO})
        assert escolhido is not None and escolhido.name == ativo

"""O mapa do controle do todo: a tela de configurar os botões, no desenho dos moldes.

A tela tem 23 linhas (uma por botão e peça do desenho), o seletor de perfil com três grupos
(Navegação, Moldes e Meus perfis), os moldes com os mesmos nomes da aba Navegação e o
Guardar que grava onde o perfil mora. Os sensores, as luzes e o áudio moram nas abas Controles e
Iluminação, e não voltam aqui.

MORDIDAS: devolver o chip «Nenhum» ou o `#cw` ao desenho, tirar um grupo do `#perfil`, trocar o
nome de um molde, aceitar um atalho que o motor não executa no schema, deixar o «Guardar» do molde
escrever no perfil ativo e deixar o «Voltar ao padrão» do molde esvaziar o molde reprovam.
"""

from __future__ import annotations

import pathlib
import re
import sys
from typing import Any
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.integrations.uinput_keyboard import SUPPORTED_KEYS
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.schema import Profile

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

MOCKUP = RAIZ / "mockup" / "mapa-do-controle.html"
_MATCH = {"type": "manual"}
NOMES_DOS_MOLDES = ["Point and click", "Visual novel", "Adulto", "Mouse", "Mouse e teclado"]


def _doc() -> str:
    """O desenho sem estilo, script e comentário: o que a pessoa vê e o que ela aciona."""
    bruto = MOCKUP.read_text(encoding="utf-8")
    sem_comentario = re.sub(r"<!--.*?-->", "", bruto, flags=re.S)
    return re.sub(r"<(style|script)\b[^>]*>.*?</\1>", "", sem_comentario, flags=re.S)


# ---------------------------------------------------------------- o desenho


def test_o_mapa_nao_tem_sensor_nem_chip_de_todos_ou_nenhum() -> None:
    doc = _doc()
    assert 'id="cw"' not in doc, "o painel dos sensores e das luzes saiu desta página"
    for palavra in ("Todos", "Nenhum", "data-todo"):
        assert palavra not in doc, f"«{palavra}» voltou ao desenho"


def test_cada_linha_tem_a_peca_dela_no_desenho() -> None:
    doc = _doc()
    linhas = re.findall(r'<button class="b2 item-([a-z0-9_-]+)" data-b="([a-z0-9_]+)"', doc)
    assert len(linhas) == 23, linhas
    assert len({b for _, b in linhas}) == 23
    pecas = set(re.findall(r'<g id="(mp-[a-z0-9_-]+)"', doc))
    for item, b in linhas:
        assert f"mp-{item}" in pecas, f"a linha {b} não tem a peça mp-{item} no desenho"


def test_o_perfil_tem_tres_grupos_e_os_moldes_com_o_nome_da_navegacao() -> None:
    # D-1610-O-PERFIL-JOGO-NAVEGACAO-E-O-ADULTO
    doc = _doc()
    seletor = re.search(r'<select[^>]*id="perfil".*?</select>', doc, flags=re.S)
    assert seletor, "sem o seletor de perfil"
    grupos = re.findall(r'<optgroup label="([^"]+)"', seletor.group(0))
    assert grupos == ["Navegação", "Moldes"], grupos  # «Meus perfis» nasce do disco, no gesto
    moldes = re.search(r'<optgroup label="Moldes">(.*?)</optgroup>', seletor.group(0), flags=re.S)
    assert moldes
    assert re.findall(r">([^<]+)</option>", moldes.group(1)) == NOMES_DOS_MOLDES
    assert [m.nome for m in loader.MOLDES_DE_PERFIL] == NOMES_DOS_MOLDES


def test_o_voltar_leva_a_navegacao_e_a_tela_nao_confessa_mesa_nem_jogador() -> None:
    doc = _doc()
    assert re.search(r'<a [^>]*class="voltar2 voltar"[^>]*href="06-navegacao.html"', doc) or \
        re.search(r'<a [^>]*href="06-navegacao.html"[^>]*class="voltar2 voltar"', doc)
    texto = re.sub(r"<[^>]+>", " ", doc).lower()
    assert "mesa" not in texto.split(), "«mesa» é palavra banida na tela"
    assert not re.search(r"\bp[1-4]\b", texto), "o controle se chama pela cor do plástico"
    assert 'class="ajuda"' not in doc, "o «?» saiu: a explicação mora na dica (`data-dica`)"


#: a linha do mapa → a linha da Navegação que fala do MESMO botão, e a palavra do desenho do todo.
O_MESMO_BOTAO = {"tp_toque": ("touchpad_toque", "Movimento do cursor"),
                 "l3": ("l3", "Teclado na tela"),
                 "r3_direcao": ("r3_direcao", "Rolagem")}


def test_o_mapa_e_a_navegacao_dizem_a_mesma_palavra_para_o_mesmo_botao() -> None:
    """O Toque, o L3 clique e a direção do R3 dizem nas duas telas o que o desenho diz."""
    # D-1510-AS-PALAVRAS-DOS-BOTOES-SAO-AS-DO-DESENHO
    # Prova da D-1510-AS-PALAVRAS-DOS-BOTOES-SAO-AS-DO-DESENHO.
    navegacao = (RAIZ / "mockup" / "06-navegacao.html").read_text(encoding="utf-8")
    for b, (linha, palavra) in O_MESMO_BOTAO.items():
        no_mapa = re.search(rf'data-b="{b}".*?<span class="b2-val"[^>]*>([^<]*)</span>', _doc(),
                            flags=re.S)
        assert no_mapa and no_mapa.group(1) == palavra, (b, no_mapa and no_mapa.group(1))
        na_06 = re.search(rf'data-linha="{linha}".*?<option selected>([^<]*)</option>', navegacao,
                          flags=re.S)
        assert na_06 and na_06.group(1) == palavra, (linha, na_06 and na_06.group(1))


def test_a_tela_cabe_sem_rolagem_vertical() -> None:
    from playwright.sync_api import sync_playwright

    chrome = pathlib.Path("/usr/bin/google-chrome")
    if not chrome.exists():
        pytest.skip("sem o Chrome do Playwright nesta máquina")
    with sync_playwright() as pw:
        nav = pw.chromium.launch(executable_path=str(chrome), args=["--no-sandbox"])
        pg = nav.new_page(viewport={"width": 1212, "height": 809})
        pg.goto(MOCKUP.as_uri())
        m = pg.evaluate("""() => {
          const d = document.documentElement;
          return {alto: d.scrollHeight, cabe: d.clientHeight,
                  largo: d.scrollWidth > d.clientWidth + 1};
        }""")
        nav.close()
    assert m["alto"] <= m["cabe"] + 1 and not m["largo"], m


# ---------------------------------------------------------------- os moldes


@pytest.mark.parametrize("molde", loader.MOLDES_DE_PERFIL, ids=lambda m: m.chave)
def test_cada_molde_nasce_um_perfil_valido_so_manual_com_o_mouse_ligado(molde: Any) -> None:
    prof = loader.perfil_do_molde(molde.chave, molde.nome)
    assert isinstance(prof, Profile)
    assert prof.match.type == "manual", "o molde nasce sem jogo: ela o entrega a um jogo depois"
    assert prof.mouse is not None and prof.mouse.enabled
    assert prof.button_actions == dict(molde.button_actions)


def test_o_molde_so_usa_ficha_que_o_motor_executa() -> None:
    # Prova da D-1510-O-MAPA-SO-OFERECE-O-QUE-O-MOTOR-EXECUTA.
    from hefesto_dualsense4unix.core import acoes_de_botao as acoes

    for molde in loader.MOLDES_DE_PERFIL:
        for motor, token in molde.button_actions.items():
            assert token in acoes.ACOES or token.startswith("KEY_"), (molde.chave, motor, token)
            if token.startswith("KEY_"):
                assert token in SUPPORTED_KEYS, (molde.chave, motor, token)


# ---------------------------------------------------------------- o schema aceita o atalho gravado


def test_o_schema_aceita_combinacao_de_teclas_do_motor_e_recusa_o_resto() -> None:
    aceito = Profile(name="x", match=_MATCH, button_actions={"l1": "KEY_LEFTCTRL+KEY_W"})
    assert aceito.button_actions == {"l1": "KEY_LEFTCTRL+KEY_W"}
    for ruim in ("KEY_PAUSE", "KEY_LEFTCTRL+KEY_PAUSE", "CTRL+W", "KEY_W+", "KEY_W++KEY_E"):
        with pytest.raises(ValueError, match="não é uma ação conhecida"):
            Profile(name="x", match=_MATCH, button_actions={"l1": ruim})


# ---------------------------------------------------------------- os gestos


def _ctx() -> Any:
    from hefesto_dualsense4unix.interface.pacotes import Contexto

    mesa = [{"pref": "p1", "uniq": "aa:bb:cc:00:00:01", "nome": "Cosmic Red", "via": "USB",
             "jogador": 1, "cor": "cosmic-red"}]
    return Contexto(
        state={"active_profile": "Fora do jogo"}, mesa=mesa,
        conectados=[{"uniq": "aa:bb:cc:00:00:01", "inputs": {"buttons": ["cross"]}}])


@pytest.fixture
def mapa() -> Any:
    from hefesto_dualsense4unix.interface.pacotes import a13_mapa_do_controle as a13

    a13._largar()
    yield a13
    a13._largar()


def test_o_molde_mais_guardar_cria_o_perfil_em_meus_perfis_e_nao_toca_o_ativo(mapa: Any) -> None:
    # Prova da D-1510-O-MOLDE-MAIS-GUARDAR-CRIA-UMA-COPIA.
    ctx = _ctx()
    mapa.mapa_perfil(ctx, {"valor": "molde:visual_novel"}, None)
    resposta = mapa.mapa_guardar(ctx, {}, MagicMock())
    gravado = loader.load_profile("Visual novel")
    assert gravado.button_actions["square"] == "KEY_LEFTCTRL"
    assert gravado.mouse is not None and gravado.mouse.enabled
    assert 'optgroup label="Meus perfis"' in mapa._opcoes_do_perfil(ctx)
    assert resposta["mesa"]["perfil"] == "perfil:Visual novel"


def test_voltar_ao_padrao_de_um_molde_devolve_o_molde_e_nao_o_esvazia(mapa: Any) -> None:
    # Prova da D-1510-O-MOLDE-MAIS-GUARDAR-CRIA-UMA-COPIA.
    ctx = _ctx()
    mapa.mapa_perfil(ctx, {"valor": "molde:mouse"}, None)
    mapa.mapa_botao(ctx, {"b": "cross"}, None)
    mapa.mapa_escolher(ctx, {"v": f"{mapa.ACAO}:KEY_ESC"}, None)
    depois = mapa.mapa_padrao(ctx, {}, None)["mesa"]
    assert depois["val-cross"] == "Botão esquerdo", depois["val-cross"]
    assert depois["val-circle"] == "Botão direito"


def test_gravar_a_tecla_na_navegacao_guarda_o_atalho_e_recusa_a_que_o_motor_nao_sabe(
        mapa: Any) -> None:
    ctx = _ctx()
    mapa.mapa_botao(ctx, {"b": "l1"}, None)
    assert mapa.mapa_gravar_tecla(
        ctx, {"tecla": "KEY_LEFTCTRL+KEY_W"}, None)["mesa"]["val-l1"] == "Ctrl + W"
    with pytest.raises(RuntimeError):
        mapa.mapa_gravar_tecla(ctx, {"tecla": "KEY_PAUSE"}, None)


def test_a_troca_de_botao_se_confere_antes_de_valer_e_o_ps_nao_se_troca(mapa: Any) -> None:
    # Prova da D-1510-O-MAPA-SO-OFERECE-O-QUE-O-MOTOR-EXECUTA.
    ctx = _ctx()
    mapa.mapa_botao(ctx, {"b": "cross"}, None)
    assert mapa.mapa_escolher(ctx, {"v": "troca:circle"}, None)["mesa"]["val-cross"] == "Círculo"
    mapa.mapa_botao(ctx, {"b": "ps"}, None)
    with pytest.raises(RuntimeError):
        mapa.mapa_escolher(ctx, {"v": f"{mapa.ACAO}:KEY_ESC"}, None)

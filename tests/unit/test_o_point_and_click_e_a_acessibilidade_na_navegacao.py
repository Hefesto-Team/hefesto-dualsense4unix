"""O point and click e a Acessibilidade se definem na Navegação: a fila, a tela e o perfil.

Absorve O-POINT-AND-CLICK-E-A-ACESSIBILIDADE-SE-DEFINEM-NA-NAVEGACAO-01. A fila leva ao mapa (os
botões do point and click) e à Acessibilidade. A Acessibilidade vem renderizada como no desenho,
mas todo controle sem dono sai `disabled`/`inert`, e o Guardar e o Voltar ao padrão da tela saem
apagados, porque nenhum campo do perfil as guarda ainda. A dica diz o que cada um faz,
nunca a dívida (regra de 07/09/2026: a tela não confessa o que o produto ainda não faz).
O «Perfil jogo - navegação» lista os moldes e os perfis do disco que configuram botão
(`blocos`), e a escolha vale para o perfil ativo: o do jogo, ou o `maquina.json` sem jogo.

MORDIDAS: tirar o `inert` de um controle da Acessibilidade, acender o Guardar dela, devolver a dica
«Chega com a próxima versão», tirar «Meus perfis» do pacote ou deixar o gesto aceitar um valor sem o
prefixo reprovam.
"""

from __future__ import annotations

import pathlib
import re
import sys
from typing import Any

import pytest

from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.schema import Profile

RAIZ = pathlib.Path(__file__).resolve().parents[2]
MOCKUP = RAIZ / "mockup" / "06-navegacao.html"


def _acessibilidade() -> str:
    bruto = MOCKUP.read_text(encoding="utf-8")
    sem = re.sub(r"<(style|script)\b[^>]*>.*?</\1>", "", bruto, flags=re.S)
    inicio = sem.index('id="acessibilidade"')
    return sem[inicio:sem.index("</body>", inicio)]


def test_todo_controle_da_acessibilidade_sem_dono_esta_apagado_e_inerte() -> None:
    tela = _acessibilidade()
    controles = re.findall(r'<span class="ac2-ctl"([^>]*)>(.*?)</span></div>', tela, flags=re.S)
    assert len(controles) >= 15, len(controles)
    for atributos, miolo in controles:
        assert "inert" in atributos, miolo[:80]
    for tag in re.findall(r"<(?:button|select|input)\b[^>]*>", tela):
        assert "disabled" in tag or "data-gesto" not in tag, tag
    assert "data-gesto" not in tela, "a Acessibilidade acendeu um gesto que ninguém atende"


DICAS_DO_RODAPE = {"Voltar ao padrão": "Volta estes ajustes ao de fábrica",
                   "Guardar": "Guarda estes ajustes para quem joga"}


def test_o_guardar_e_o_voltar_ao_padrao_da_acessibilidade_saem_apagados_com_a_dica() -> None:
    tela = _acessibilidade()
    rodape = tela[tela.index('class="tn-rod"'):]
    for rotulo, dica in DICAS_DO_RODAPE.items():
        tag = re.search(rf'<span class="btn[^"]*"([^>]*)>{rotulo}</span>', rodape)
        assert tag, f"o «{rotulo}» não é um botão apagado"
        assert 'aria-disabled="true"' in tag.group(1)
        assert f'data-dica="{dica}"' in tag.group(1)
    assert "Cancelar" in rodape
    assert "próxima versão" not in MOCKUP.read_text(encoding="utf-8"), (
        "a tela confessa dívida: «próxima versão» é promessa nossa, não o que o botão faz")


def _pacotes() -> Any:
    import hefesto_dualsense4unix

    interface = str(pathlib.Path(hefesto_dualsense4unix.__file__).parent / "interface")
    if interface not in sys.path:
        sys.path.insert(0, interface)
    import pacotes
    import pacotes.a06_navegacao as a06

    a06._A_MAQUINA = None
    return pacotes, a06


def test_meus_perfis_do_seletor_nasce_do_disco_e_so_com_perfil_de_botao() -> None:
    pacotes, a06 = _pacotes()
    loader.save_profile(Profile.model_validate({
        "name": "Meu mouse", "match": {"type": "manual"},
        "button_actions": {"cross": "BTN_LEFT"}}), origem="regua")
    loader.save_profile(Profile.model_validate({
        "name": "Sem botão", "match": {"type": "manual"}}), origem="regua")
    ctx = pacotes.Contexto(state={}, mesa=[], conectados=[], estados={})
    blocos = a06.pacote(ctx)["blocos"]
    meus = blocos['[data-bloco="meus-perfis"]']
    assert 'value="perfil:Meu mouse"' in meus and "Sem botão" not in meus, meus


def test_o_gesto_so_aceita_molde_ou_perfil_com_prefixo() -> None:
    pacotes, _a06 = _pacotes()
    ctx = pacotes.Contexto(state={}, mesa=[], conectados=[], estados={})
    fn = pacotes.gesto_da_pagina("06-navegacao.html", "point-and-click-perfil")

    class _Ponte:
        def __getattr__(self, nome: str) -> Any:
            return lambda *a, **k: True

    for ruim in ("Meu mouse", "molde:", "perfil:   ", "molde:nao_existe"):
        with pytest.raises(ValueError):
            fn(ctx, {"valor": ruim}, _Ponte())
    fn(ctx, {"valor": "perfil:Meu mouse"}, _Ponte())
    from hefesto_dualsense4unix.utils import maquina as m

    mouse = m.carregar_maquina().computador.global_.mouse
    assert mouse.point_and_click == "perfil:Meu mouse"


def test_com_um_jogo_ativo_a_escolha_vai_ao_perfil_dele_e_o_computador_fica() -> None:
    """Como a velocidade: o gesto vale para o perfil ATIVO (D-0610-O-ESCOPO-SAI-DAS-ABAS)."""
    pacotes, _a06 = _pacotes()
    loader.save_profile(Profile.model_validate({
        "name": "Jogo X", "match": {"type": "criteria", "window_class": ["jogox"]}}),
        origem="regua")
    ctx = pacotes.Contexto(state={"active_profile": "Jogo X"}, mesa=[], conectados=[],
                           estados={})

    class _Ponte:
        def __getattr__(self, nome: str) -> Any:
            return lambda *a, **k: True

    pacotes.gesto_da_pagina("06-navegacao.html", "point-and-click-perfil")(
        ctx, {"valor": "molde:visual_novel"}, _Ponte())
    from hefesto_dualsense4unix.utils import maquina as m

    do_jogo = loader.load_profile("Jogo X").mouse
    assert do_jogo is not None and do_jogo.point_and_click == "molde:visual_novel"
    assert m.carregar_maquina().computador.global_.mouse is None

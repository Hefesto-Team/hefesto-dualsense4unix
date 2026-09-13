"""Os dois campos da aba Perfis que passaram a ESCREVER — 03/09/2026.

**AS DUAS DECISÕES SÃO DELA, do mesmo dia:**

* *"Slider, como você pediu"* — reconfirmando o pedido de 27/08 (*"prioridade é
  slicer"*). A Prioridade era o **único campo do editor sem nenhum caminho de
  escrita** na interface nova: o desenho trazia um ``<span class="trilho">``, e
  barra não se arrasta. O conserto é um ``<input type=range>`` vestido com o CSS
  do trilho que já existia;
* *"Construir o motor"*, com o alcance escolhido por ela — **gatilho + vibração
  + luz**. O ``<select>`` de dezesseis opções era o campo mais aceso do painel e
  não tinha nada atrás: até a tarde deste dia ele afirmava um estilo que perfil
  nenhum guardava.

O QUE ESTA RÉGUA MEDE, e o que ela NÃO mede
--------------------------------------------
MEDE o Python: que o gesto grava o que promete, que os números saem dos DONOS
(``profiles/schema.PRIORIDADE_*`` e ``app/actions/trigger_specs.PRESETS``), e
que a lei da cor dela vale unidade a unidade.

NÃO mede o clique chegando. Quem prova isso é
``scripts/ensaios/o_slider_e_o_estilo_na_aba_perfis.py``, que abre a página da
BANCADA no ``WebKit2.WebView``, arrasta o punho com um ``change`` de verdade e
lê o ``.json`` do outro lado — porque um campo que o ouvinte do piloto não
alcançasse daria verde em toda régua de Python e silêncio na tela.

A REGRA QUE MANDA NA COR É DELA, verbatim, e é ENDEREÇO e não estética:

    *"nenhuma cor dos controles nunca pode ser a mesma, mesmo no mesmo perfil e
    estilo de jogo. Dentro da paleta de fps tem que ter variações pra cada
    unidade de controle."*

As 24 provas do motor em si estão em
``test_nenhuma_unidade_repete_a_cor_de_outra.py``; esta régua não as repete. O
que ela cobra é o outro degrau: que o gesto **chame** o motor por unidade, em
vez de escrever uma cor no global — que é onde a lei dela morreria em silêncio.
"""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions import trigger_specs
from hefesto_dualsense4unix.interface import onde
from hefesto_dualsense4unix.interface.pacotes import Contexto, a10_perfis
from hefesto_dualsense4unix.profiles import estilos_de_jogo, loader
from hefesto_dualsense4unix.profiles.schema import (
    PRIORIDADE_MAXIMA,
    PRIORIDADE_MINIMA,
    MatchAny,
    Profile,
)

PAGINA = "10-perfis.html"

#: A MESA — endereços MASCARADOS (octetos 4 e 5 zerados), a máscara da casa.
#: SÃO DOIS de propósito: com um só, "nenhuma unidade repete a cor de outra"
#: passaria por vacuidade.
MESA = [
    {"pref": "p1", "uniq": "aabbcc000001", "jogador": 1, "cor": "cosmic-red",
     "nome": "Cosmic Red", "via": "USB", "transporte": "usb", "alvo": True},
    {"pref": "p2", "uniq": "aabbcc000002", "jogador": 2, "cor": "white",
     "nome": "White", "via": "BT", "transporte": "bt", "alvo": False},
]


class PonteDeMentira:
    def __init__(self) -> None:
        self.chamadas: list[str] = []

    def profile_switch(self, nome: str) -> bool:
        self.chamadas.append(f"profile_switch:{nome}")
        return True

    def chamar(self, metodo: str, *a: Any, **kw: Any) -> Any:
        self.chamadas.append(f"chamar:{metodo}")
        return True

    def resultado(self, metodo: str, *a: Any, **kw: Any) -> Any:
        self.chamadas.append(f"resultado:{metodo}")
        return {}


@pytest.fixture(autouse=True)
def _memoria_limpa(monkeypatch: pytest.MonkeyPatch) -> None:
    """Estado de MÓDULO herdado de outro teste não é prova de nada.

    OS DOIS ÚLTIMOS SÃO A MEMÓRIA DO `_uma_vez_so`, e sem eles esta régua ficava
    VERDE SOZINHA e VERMELHA em lote — medido em 03/09/2026, rodando 57 arquivos
    juntos. Se outro teste chamou `pacote()` para o mesmo nome de perfil há menos
    de dois segundos, `_uma_vez_so` conclui que a aba não trocou de perfil e
    OMITE os campos que ela mexe — inclusive o `editor.prioridade.escolha` que
    esta régua cobra. Um teste que depende de quem rodou antes não mede nada.
    """
    monkeypatch.setattr(a10_perfis, "_ESCOLHIDO", "", raising=False)
    monkeypatch.setattr(a10_perfis, "_ARMADO", None, raising=False)
    monkeypatch.setattr(a10_perfis, "_ARMADO_REBAIXAR", None, raising=False)
    monkeypatch.setattr(a10_perfis, "_PINTADO_PARA", "", raising=False)
    monkeypatch.setattr(a10_perfis, "_ULTIMO_TIQUE", 0.0, raising=False)


@pytest.fixture
def disco(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Um perfil na "pasta", e o que o gesto GRAVAR fica aqui — não no disco.

    NADA TOCA ``~/.config``: `save_profile` é desviado para este dicionário. A
    ``conftest.py`` já desvia o ``HOME``, e mesmo assim escrever arquivo por
    teste seria I/O que esta régua não precisa.
    """
    guardado: dict[str, Any] = {
        "perfil": Profile(name="Pragmata", match=MatchAny(), priority=40),
        "salvos": [],
    }

    def _load_all(*a: Any, **kw: Any) -> list[Profile]:
        return [guardado["perfil"]]

    def _load(nome: str, *a: Any, **kw: Any) -> Profile:
        if nome != guardado["perfil"].name:
            raise FileNotFoundError(nome)
        return guardado["perfil"]

    def _save(prof: Profile, *a: Any, **kw: Any) -> None:
        guardado["perfil"] = prof
        guardado["salvos"].append(prof)

    monkeypatch.setattr(loader, "load_all_profiles", _load_all)
    monkeypatch.setattr(loader, "load_profile", _load)
    monkeypatch.setattr(loader, "save_profile", _save)
    a10_perfis._ESCOLHIDO = "Pragmata"
    return guardado


def _ctx(mesa: list[dict[str, Any]] | None = None) -> Contexto:
    tem = MESA if mesa is None else mesa
    return Contexto(state={"active_profile": None}, mesa=list(tem),
                    conectados=list(tem), estados={})


def _bancada() -> str:
    return onde.pagina(PAGINA, publicado=False).read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# 1. A PRIORIDADE VIROU SLIDER
# --------------------------------------------------------------------------

def test_a_prioridade_tem_gesto() -> None:
    """MORDIDA: tire o ``@gesto`` de ``editor_prioridade`` e isto reprova.

    Era o único campo do editor sem NENHUM caminho de escrita: o próprio produto
    declarava isso em ``perfis_web.DONOS_DOS_GESTOS["editor.prioridade"]``.
    """
    from hefesto_dualsense4unix.interface import pacotes

    assert pacotes.gesto_da_pagina(PAGINA, "editor.prioridade") is not None


def test_a_faixa_do_slider_e_a_do_esquema() -> None:
    """A régua PERGUNTA ao dono do teto, e não digita ``0..200``.

    O teto mora em ``profiles/schema.PRIORIDADE_MAXIMA`` desde a
    UNIFICA-CONSTANTE-01, e já mudou uma vez (era 100). Um ``max="200"`` escrito
    aqui envelheceria na próxima mudança — e o slider dela pararia de alcançar
    números que o produto aceita, sem ninguém ver.

    MORDIDA: troque o ``min``/``max`` do ``aba10.py`` por literais diferentes do
    esquema e isto reprova.
    """
    html = _bancada()
    assert f'min="{PRIORIDADE_MINIMA}"' in html and f'max="{PRIORIDADE_MAXIMA}"' in html, (
        "a faixa do `<input type=range>` da Prioridade não é a do esquema")
    assert '<input type="range" class="desliza"' in html, (
        "a Prioridade voltou a ser uma barra que não se arrasta")


def test_arrastar_grava_a_prioridade(disco: dict[str, Any]) -> None:
    """O caminho principal: o ``change`` do punho vira ``priority`` no perfil.

    MORDIDA: tire o ``_gravar`` de ``editor_prioridade`` e isto reprova — o
    campo volta a aceitar arrasto e não guardar nada, que era o estado de hoje
    de manhã.
    """
    ponte = PonteDeMentira()
    resposta = a10_perfis.editor_prioridade(_ctx(), {"valor": "137"}, ponte)

    assert disco["perfil"].priority == 137, (
        f"o arrasto não chegou ao perfil: {disco['perfil'].priority}")
    assert len(disco["salvos"]) == 1
    # E A RESPOSTA REPINTA OS DOIS VIZINHOS NA HORA, sem esperar o tique de
    # 500 ms. Sem isto, a barra fica meio segundo atrás do punho.
    assert resposta is not None
    mesa = resposta["mesa"]
    assert mesa["editor.prioridade.n"] == "137"
    # A LARGURA VAI EM NÚMERO PURO: o pintor faz `el.style.width = t + '%'`, e
    # um `'68%'` viraria `'68%%'` — CSS inválido e contador mentindo para sempre.
    esperada = str(round(137 * 100 / PRIORIDADE_MAXIMA))
    assert mesa["editor.prioridade"] == esperada, (
        f"a largura saiu {mesa['editor.prioridade']!r} e devia ser {esperada!r}, "
        f"sem `%` e sem travessão")


@pytest.mark.parametrize("valor", ["-1", str(PRIORIDADE_MAXIMA + 1), "9999"])
def test_fora_da_faixa_recusa_dizendo(disco: dict[str, Any], valor: str) -> None:
    """Um número fora da faixa iria direto para o ``.json`` dela.

    O ``<input>`` já traz ``min``/``max``, mas o clique pode chegar de qualquer
    lugar — inclusive de uma régua. ``RuntimeError`` porque é a única classe que
    ``_recusou_dizendo`` leva ao DOM.

    MORDIDA: tire a guarda de faixa do gesto e isto reprova.
    """
    with pytest.raises(RuntimeError, match="fora da faixa"):
        a10_perfis.editor_prioridade(_ctx(), {"valor": valor}, PonteDeMentira())
    assert not disco["salvos"], "gravou um número fora da faixa do esquema"


def test_o_que_nao_e_numero_recusa(disco: dict[str, Any]) -> None:
    """MORDIDA: tire o ``try/except ValueError`` e isto vira ``ValueError`` cru —
    que sai no ``stderr`` de quem lançou a janela e não na tela dela."""
    with pytest.raises(RuntimeError, match="tem de ser um número"):
        a10_perfis.editor_prioridade(_ctx(), {"valor": "meio"}, PonteDeMentira())
    assert not disco["salvos"]


def test_o_clique_solto_nao_grava(disco: dict[str, Any]) -> None:
    """Um ``<input type=range>`` dispara ``click`` E ``change`` no mesmo toque.

    O ouvinte do piloto escuta os dois (``hefesto_vivo.py``); sem ``_so_mudou``,
    cada arrasto gravaria duas vezes — e a segunda gravação é a que faz o daemon
    reaplicar o perfil no meio da partida.

    MORDIDA: tire o ``if not _so_mudou(o)`` do gesto e isto reprova.
    """
    assert a10_perfis.editor_prioridade(
        _ctx(), {"valor": "137", "evento": "click"}, PonteDeMentira()) is None
    assert not disco["salvos"], "um clique que não mudou nada gravou no disco"


def test_o_mesmo_numero_nao_regrava(disco: dict[str, Any]) -> None:
    """Regravar um perfil idêntico troca a data do arquivo e faz o daemon
    reaplicar — um ``profile.switch`` no meio de uma partida não é de graça."""
    assert a10_perfis.editor_prioridade(
        _ctx(), {"valor": "40"}, PonteDeMentira()) is None
    assert not disco["salvos"]


def test_o_punho_se_pinta_uma_vez_por_perfil() -> None:
    """``editor.prioridade.escolha`` tem de estar em ``CAMPOS_QUE_ELA_DIGITA``.

    A MEDIÇÃO: com ``data-hef-alvo="valor"`` a pintura faz ``el.value = t`` a
    cada 500 ms. Num ``<input type=range>``, isso devolve o punho ao número do
    disco NO MEIO do arrasto — o slider ficaria intocável, do mesmo jeito que os
    dois ``<input>`` de texto ficariam.

    E O NÚMERO AO LADO NÃO PODE ENTRAR: ele é leitura, e congelá-lo faria a
    legenda mostrar o valor velho depois de a gravação acontecer.

    MORDIDA: tire o nome de ``CAMPOS_QUE_ELA_DIGITA`` e isto reprova.
    """
    assert "editor.prioridade.escolha" in a10_perfis.CAMPOS_QUE_ELA_DIGITA
    assert "editor.prioridade.n" not in a10_perfis.CAMPOS_QUE_ELA_DIGITA


# --------------------------------------------------------------------------
# 2. O ESTILO DE JOGO GANHOU O FIO ATÉ O MOTOR
# --------------------------------------------------------------------------

def test_o_select_oferece_o_que_o_motor_sabe_aplicar() -> None:
    """O CONJUNTO, e não uma contagem: uma receita nova não pode ficar fora.

    Se o ``<select>`` oferecesse um rótulo que o motor não conhece, a tarja
    diria *"não é um dos Estilos de Jogo do produto"* sobre uma palavra que a
    própria página escreveu.

    MORDIDA: volte a digitar a lista de rótulos no ``aba10.py`` e acrescente uma
    receita ao motor — isto reprova nomeando a que ficou de fora.
    """
    html = _bancada()
    fora = [e.rotulo for e in estilos_de_jogo.ESTILOS
            if f">{e.rotulo}</option>" not in html]
    assert not fora, f"o motor conhece e o `<select>` não oferece: {fora}"


def test_o_estilo_grava_gatilho_vibracao_e_uma_cor_por_unidade(
    disco: dict[str, Any],
) -> None:
    """A entrega inteira num gesto: os três ajustes, e a cor POR UNIDADE.

    MORDIDA: tire o ``mudanca["controllers"] = atuais`` de ``_com_o_estilo`` e
    a última asserção reprova — o estilo passaria a ajustar gatilho e vibração e
    deixar os controles com a cor de antes, que é a metade que ela nomeou.
    """
    ponte = PonteDeMentira()
    resposta = a10_perfis.editor_estilo(_ctx(), {"valor": "FPS"}, ponte)

    prof = disco["perfil"]
    receita = estilos_de_jogo.POR_ROTULO["FPS"]
    assert prof.triggers.left.mode == receita.gatilho
    assert prof.triggers.right.mode == receita.gatilho
    assert prof.rumble.policy == receita.vibracao
    # UMA COR POR CONTROLE DA MESA, e nenhuma no global: escrever no global é
    # exatamente o defeito que a regra dela proíbe — os quatro herdariam a mesma.
    assert set(prof.controllers or {}) == {c["uniq"] for c in MESA}
    assert prof.leds.lightbar == (0, 0, 0), (
        "o estilo escreveu uma cor na seção GLOBAL — é a cor que os quatro "
        "herdariam, e a regra dela é que nenhum controle repete a cor de outro")
    assert resposta is not None and "FPS" in resposta["relato"]
    assert resposta["mesa"]["perfis.desfecho"] == "", "a tira voltou a falar"


def test_nenhuma_unidade_recebe_a_cor_de_outra(disco: dict[str, Any]) -> None:
    """A LEI DELA, medida no que foi GRAVADO — e não no motor.

    O motor já garante que as quatro variações são distinguíveis (24 provas em
    ``test_nenhuma_unidade_repete_a_cor_de_outra.py``). O que esta régua cobra é
    o degrau seguinte: que o gesto tenha chamado ``cor_da_unidade`` **por
    jogador**, e não uma vez só.

    MORDIDA: troque ``cor_da_unidade(estilo, jogador)`` por
    ``cor_da_unidade(estilo, 1)`` em ``_com_o_estilo`` e isto reprova.
    """
    for rotulo in [e.rotulo for e in estilos_de_jogo.ESTILOS
                   if e.chave != "personalizado"]:
        disco["perfil"] = Profile(name="Pragmata", match=MatchAny(), priority=40)
        a10_perfis.editor_estilo(_ctx(), {"valor": rotulo}, PonteDeMentira())
        cores = [tuple(o.leds.lightbar)
                 for o in (disco["perfil"].controllers or {}).values()]
        assert len(set(cores)) == len(cores), (
            f"“{rotulo}” deu a mesma cor a duas unidades: {cores}")


def test_o_gatilho_sai_do_dono_dos_parametros(disco: dict[str, Any]) -> None:
    """Os números do gatilho são PERGUNTADOS, nunca digitados.

    As factories de ``core/trigger_effects`` exigem posicionais sem default: um
    ``params=[]`` passaria pelo esquema e, no melhor caso, aplicaria um efeito
    com ZERO zona ativa — o gatilho fica solto e a tela diz que aplicou. Quem
    sabe os números é ``app/actions/trigger_specs.PRESETS``.

    MORDIDA: troque o ``preset_to_positional_params(spec, {})`` de
    ``_com_o_estilo`` por ``[]`` e isto reprova em todos os catorze.
    """
    sem_params = []
    for estilo in estilos_de_jogo.ESTILOS:
        if estilo.chave == "personalizado":
            continue
        disco["perfil"] = Profile(name="Pragmata", match=MatchAny(), priority=40)
        a10_perfis.editor_estilo(_ctx(), {"valor": estilo.rotulo},
                                 PonteDeMentira())
        spec = trigger_specs.get_spec(estilo.gatilho or "")
        assert spec is not None, f"{estilo.rotulo}: gatilho fora do produto"
        esperado = list(trigger_specs.preset_to_positional_params(spec, {}))
        for lado in ("left", "right"):
            tem = list(getattr(disco["perfil"].triggers, lado).params)
            assert tem == esperado, (
                f"{estilo.rotulo}/{lado}: params {tem} != {esperado} do dono")
        if spec.params and not esperado:  # pragma: no cover — defesa da régua
            sem_params.append(estilo.rotulo)
    assert not sem_params


def test_o_gatilho_gravado_e_construivel(disco: dict[str, Any]) -> None:
    """O que foi gravado tem de ABRIR no produto — senão o estrago é no `apply()`.

    Esta é a prova que a anterior não dá: ``params`` iguais aos do dono ainda
    poderiam ser recusados pela factory (faixa, número de argumentos). Aqui o
    produto MONTA o efeito, que é o que o daemon faz ao ativar o perfil.
    """
    from hefesto_dualsense4unix.core.trigger_effects import build_from_name

    for estilo in estilos_de_jogo.ESTILOS:
        if estilo.chave == "personalizado":
            continue
        disco["perfil"] = Profile(name="Pragmata", match=MatchAny(), priority=40)
        a10_perfis.editor_estilo(_ctx(), {"valor": estilo.rotulo},
                                 PonteDeMentira())
        cfg = disco["perfil"].triggers.left
        efeito = build_from_name(cfg.mode, cfg.params)
        assert efeito is not None, f"{estilo.rotulo}: o gatilho não monta"


def test_personalizado_nao_mexe_em_nada(disco: dict[str, Any]) -> None:
    """"Personalizado" é o estilo que diz *"eu ajusto na mão"*.

    ELE RESPONDE, e não recusa: escolhê-lo é uma escolha legítima, e uma tarja
    de recusa faria a tela tratar de erro o comportamento pedido.

    MORDIDA: tire o ramo do ``personalizado`` e o gesto levanta o ``ValueError``
    que ``as_quatro`` dispara de propósito — um erro para quem programa, no
    ``stderr``, calado na tela dela.
    """
    era = disco["perfil"]
    resposta = a10_perfis.editor_estilo(
        _ctx(), {"valor": "Personalizado"}, PonteDeMentira())
    assert not disco["salvos"], "o `Personalizado` gravou alguma coisa"
    assert disco["perfil"] is era
    assert resposta is not None
    assert "não mexe em nada" in resposta["relato"]


def test_um_estilo_que_o_produto_nao_conhece_recusa(disco: dict[str, Any]) -> None:
    """MORDIDA: tire o ``if estilo is None`` e isto vira ``AttributeError``."""
    with pytest.raises(RuntimeError, match="não é um dos Estilos de Jogo"):
        a10_perfis.editor_estilo(_ctx(), {"valor": "Boliche"}, PonteDeMentira())
    assert not disco["salvos"]


def test_dois_controles_no_mesmo_lugar_recusam(disco: dict[str, Any]) -> None:
    """O único caminho pelo qual a lei dela cairia com o motor inocente.

    Duas peças com o mesmo ``jogador`` receberiam a MESMA cor — e o motor não
    tem como saber: ele responde por jogador, e os dois pediriam o mesmo.

    MORDIDA: tire a guarda dos `lugares` de ``_com_o_estilo`` e isto reprova
    com duas unidades pintadas de igual.
    """
    mesa = [dict(MESA[0]), {**MESA[1], "jogador": 1}]
    with pytest.raises(RuntimeError, match="MESMA cor"):
        a10_perfis.editor_estilo(_ctx(mesa), {"valor": "FPS"}, PonteDeMentira())
    assert not disco["salvos"]


def test_mesa_vazia_ainda_ajusta_gatilho_e_vibracao(disco: dict[str, Any]) -> None:
    """Sem controle na mesa, os dois que não dependem de peça entram do mesmo
    jeito — e o desfecho DIZ que a luz não alcançou ninguém.

    Prometer cor a zero controles seria a tela afirmando o que não fez.
    """
    resposta = a10_perfis.editor_estilo(_ctx([]), {"valor": "Corrida"},
                                        PonteDeMentira())
    prof = disco["perfil"]
    assert prof.triggers.left.mode == estilos_de_jogo.POR_ROTULO["Corrida"].gatilho
    assert prof.rumble.policy == estilos_de_jogo.POR_ROTULO["Corrida"].vibracao
    assert not (prof.controllers or {})
    assert resposta is not None
    assert "nenhum controle ligado" in resposta["relato"]


def test_o_estilo_saiu_da_lista_de_travados() -> None:
    """``perfis_web`` não pode mais mostrar TRAVADO um campo que grava.

    É a mentira ao contrário, e igualmente cara: a tela desligaria o único
    caminho que resolve três ajustes de uma vez.

    MORDIDA: devolva ``"editor.estilo"`` a ``GESTOS_SEM_MOTOR`` e isto reprova.
    """
    from hefesto_dualsense4unix.app.actions import perfis_web

    assert "editor.estilo" not in perfis_web.GESTOS_SEM_MOTOR
    editor = perfis_web.pacote_da_aba(
        [Profile(name="Pragmata", match=MatchAny())],
        editado=Profile(name="Pragmata", match=MatchAny()))["editor"]
    assert editor["estilo_travado"] is False
    # E O CAMPO CONTINUA SEM VALOR A MOSTRAR: o estilo é um verbo, não um campo
    # do `Profile`. Pintar qualquer opção seria a tela afirmando o que não guarda.
    assert editor["estilo"] is None
    assert "editor.estilo" in a10_perfis.NAO_PINTAVEIS


# --------------------------------------------------------------------------
# 3. O QUE O PACOTE EMITE PARA O PUNHO
# --------------------------------------------------------------------------

def test_o_pacote_manda_o_numero_cru_para_o_punho(
    monkeypatch: pytest.MonkeyPatch, disco: dict[str, Any],
) -> None:
    """``editor.prioridade.escolha`` é o número CRU — nunca a porcentagem.

    O ``<input type=range>`` é endereçado por ``valor``: escrever ``"20%"`` nele
    é recusado pelo DOM, o campo volta ao meio da faixa, e ``el.value`` nunca
    volta igual ao escrito — o contador soma +1 por tique, para sempre.
    """
    disco["perfil"] = Profile(name="Pragmata", match=MatchAny(), priority=137)
    fora = a10_perfis.pacote(_ctx())
    assert fora["editor.prioridade.escolha"] == "137"
    # E A BARRA CONTINUA EM PORCENTAGEM PURA, que é o outro alvo do mesmo valor.
    assert fora["editor.prioridade"] == str(round(137 * 100 / PRIORIDADE_MAXIMA))


def test_sem_perfil_o_punho_nao_recebe_travessao(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A guarda que impede o contador de mentir para sempre.

    ``escrever()`` troca vazio por ``'—'`` ANTES de escolher o ramo, e ``'—'``
    num ``<input type=range>`` é inválido. Sem perfil aberto o punho fica onde o
    DESENHO o pôs — a leitura honesta de "não há prioridade para mostrar".

    MORDIDA: emita ``editor.prioridade.escolha`` sem o ``if editor:`` e isto
    reprova.
    """
    monkeypatch.setattr(loader, "load_all_profiles", lambda *a, **k: [])
    fora = a10_perfis.pacote(_ctx())
    assert "editor.prioridade.escolha" not in fora, (
        "o punho recebeu um valor sem perfil aberto — o `'—'` do pintor faz o "
        "contador somar uma pintura por tique, para sempre")

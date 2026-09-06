#!/usr/bin/env python3
"""As cinco luzes de jogador sem trocar o número — LUZES-01, 06/09/2026.

**A QUEIXA QUE ABRIU A SPRINT está no CSV da paridade, e é de uma linha:** toda
escrita de lâmpada do lado HTML vinha *"SEMPRE junto com a renumeração, nunca
sozinhos"*. Dar a este controle o desenho do P3 mantendo o número dele era
impossível pela interface nova — e o caminho de VOLTA (devolver as cinco ao
automático) não existia de jeito nenhum, porque um override por-`uniq` de
`player_leds` fica ACIMA da camada automática no merge do backend e as prende.

As cinco linhas `FALTA_NO_HTML` que este arquivo fecha, com o gêmeo de cada uma
na janela estável:

    csv:140  marcar/desmarcar cada uma das 5 luzes   on_player_led_toggled
    csv:141  presets "Desenho do P1".."P4"           aplicar_desenho_do_jogador
    csv:142  "Todas acesas" / "Todas apagadas"       on_player_leds_preset_none
    csv:143  "Aplicar o desenho" (reenvio)           on_player_leds_apply
    csv:148  "Voltar todos ao automático"            on_lightbar_auto_reset_all

**A MORDIDA QUE IMPORTA É A DA SEGUNDA ASSERÇÃO**, e a sprint a nomeia: um teste
que só prove *"o bitmask chegou à ponte"* passa com o defeito de HOJE — o gesto
`player` já manda bitmask, de carona na renumeração. O que separa a cura do
defeito é `identity_number_set` **não** ter sido chamado. Arranque essa linha e
a régua fica verde sobre o mundo de ontem.

**E A SEGUNDA MORDIDA É A DO CAMINHO DE VOLTA:** provar que o override **SAIU**
do perfil, e não que ele ficou zerado. `LedsConfig(player_leds=[False] * 5)` é
uma escolha EXPLÍCITA que o backend respeita (`manager._controllers_to_specs`
monta o `OutputSpec` a partir de `model_fields_set`), então cinco falsos gravados
prendem as lâmpadas apagadas — o oposto de devolvê-las ao automático.

O LAR É DE MENTIRA. O `conftest` desvia `HOME` e os quatro `XDG_*`; os casos que
gravam escrevem perfil de verdade, com `save_profile`, dentro dele — que é a
única forma de provar que o disco recebeu, em vez de provar que a função foi
chamada. É o mesmo desenho de `test_a_aba_04_iluminacao_fecha_as_linhas.py`.
"""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
for _p in (str(RAIZ / "src"), str(INTERFACE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

PAGINA = "04-iluminacao.html"

#: MACs da faixa sintética da casa — há dois portões de anonimato nesta árvore.
UM = "aa:bb:cc:00:00:01"
DOIS = "aa:bb:cc:00:00:02"
CHAVE_UM, CHAVE_DOIS = "aabbcc000001", "aabbcc000002"

MESA = [
    {"pref": "p1", "uniq": UM, "jogador": 1, "cor": "white",
     "nome": "White", "via": "USB"},
    {"pref": "p2", "uniq": DOIS, "jogador": 2, "cor": "galactic-purple",
     "nome": "Galactic Purple", "via": "BT"},
]

P1 = {"uniq": UM, "index": 0, "transport": "usb", "connected": True,
      "player": 1, "player_slot": 1, "is_primary": True,
      "lightbar_rgb": [0, 0, 255], "lightbar_on": True,
      "lightbar_source": "sysfs"}
P2 = {"uniq": DOIS, "index": 1, "transport": "bluetooth", "connected": True,
      "player": 2, "player_slot": 2, "is_primary": False,
      "lightbar_rgb": [255, 0, 0], "lightbar_on": True,
      "lightbar_source": "sysfs"}


@pytest.fixture
def a04():
    from pacotes import a04_iluminacao

    return a04_iluminacao


@pytest.fixture
def pac():
    import pacotes

    return pacotes


def _ctx(pac, *, perfil="regua", conectados=None, state=None):
    return pac.Contexto(state={"active_profile": perfil, **(state or {})},
                        mesa=[dict(m) for m in MESA],
                        conectados=[dict(c) for c in (conectados or [P1, P2])],
                        estados={})


class PonteDeMentira:
    """Um dublê da ponte que guarda o que foi chamado e devolve o caminho feliz.

    **ELE SABE RECUSAR** — com `corpo=None` o `player_leds_set_detalhado` volta
    sem corpo e os gestos levantam a frase do produto. Um dublê que só sabe
    passar não é dublê, e esta casa já mediu o preço disso três vezes.
    """

    def __init__(self, corpo: object = ...):
        self.corpo = ({"status": "ok", "aplicado_em": [UM, DOIS],
                       "guardado_em": []} if corpo is ... else corpo)
        self.chamadas: list[tuple[str, tuple, dict]] = []

    def __getattr__(self, nome: str):
        def registrar(*args, **kwargs):
            self.chamadas.append((nome, args, kwargs))
            return True if nome in ("chamar", "profile_switch") else self.corpo

        return registrar

    def nomes(self) -> list[str]:
        return [c[0] for c in self.chamadas]

    def so(self, nome: str) -> list[tuple[tuple, dict]]:
        return [(a, k) for n, a, k in self.chamadas if n == nome]


def _semear(nome: str = "regua", *, automatico: bool = True,
            overrides: dict | None = None):
    """Escreve um perfil no lar de mentira, PELO DONO da escrita."""
    from hefesto_dualsense4unix.profiles.loader import save_profile
    from hefesto_dualsense4unix.profiles.schema import (
        ControllerOverrides,
        LedsConfig,
        MatchAny,
        Profile,
    )

    prof = Profile(
        name=nome,
        match=MatchAny(),
        leds=LedsConfig(lightbar=(40, 80, 180), lightbar_brightness=1.0,
                        auto_player_colors=automatico),
        controllers={
            chave: ControllerOverrides(leds=LedsConfig(**campos))
            for chave, campos in (overrides or {}).items()
        },
    )
    return save_profile(prof, origem="regua")


def _do_disco(caminho) -> dict:
    return json.loads(pathlib.Path(caminho).read_text(encoding="utf-8"))


def _leds_de(caminho, chave: str) -> dict:
    """A seção `leds` do override daquele controle — `{}` quando não há."""
    dele = (_do_disco(caminho).get("controllers") or {}).get(chave) or {}
    return dele.get("leds") or {}


def _clique(**extra) -> dict:
    return {"controle": "p1", "uniq": UM, **extra}


# ---------------------------------------------------------------------------
# csv:140 — MARCAR/DESMARCAR CADA UMA DAS CINCO, E O NÚMERO NÃO SE MEXE
# ---------------------------------------------------------------------------
def test_a_lampada_escreve_o_bitmask_e_nao_renumera(pac, a04):
    """A mordida da sprint, e são DUAS asserções — a segunda é a que morde.

    **ARRANQUE A SEGUNDA E O TESTE PASSA COM O DEFEITO DE HOJE.** O gesto
    `player`, que já existia, também manda `player_leds_set_detalhado` — de
    carona numa renumeração. Provar só que o bitmask chegou é provar o mundo de
    ontem. Ver a saída da mordida no relatório desta sprint.

    O ESTADO DE PARTIDA É O DO DADO: sem override no perfil, o P1 mostra
    `player_led_pattern(1)` = `(F, F, T, F, F)`. Acender a lâmpada 1 dá
    `(T, F, T, F, F)` — e o padrão SAI DO DONO, nunca digitado aqui.
    """
    from hefesto_dualsense4unix.core.led_control import player_led_pattern

    _semear()
    ponte = PonteDeMentira()
    a04.luzes(_ctx(pac), _clique(lampada="1"), ponte)

    esperado = list(player_led_pattern(1))
    esperado[0] = True
    (args, kwargs), = ponte.so("player_leds_set_detalhado")
    assert args[0] == tuple(esperado), (
        f"a lâmpada 1 não somou ao desenho de agora: foi {args[0]}")
    assert kwargs == {"uniq": UM}, "o desenho saiu sem destinatário"
    # A METADE QUE MORDE.
    assert "identity_number_set" not in ponte.nomes(), (
        "acender uma lâmpada renumerou o controle — é exatamente o defeito que "
        "esta sprint fecha: no HTML de ontem toda escrita de lâmpada vinha de "
        "carona numa troca de número")


def test_a_lampada_grava_no_perfil_para_a_tela_nao_desfazer(pac, a04):
    """Sem a gravação, o tique seguinte apagaria o clique dela.

    **A CAUSA É MEDIDA E ESTÁ ESCRITA NO PRODUTO** (`desenho_gravado`): o
    `state_full` não publica `player_leds` por controle, então a tela só sabe o
    desenho pelo override do perfil. Se o gesto só mandasse ao fio, a pintura
    do tique seguinte leria o padrão do NÚMERO e repintaria a lâmpada apagada —
    o clique acenderia e a tela o desfaria um décimo de segundo depois.
    """
    caminho = _semear()
    a04.luzes(_ctx(pac), _clique(lampada="5"), PonteDeMentira())

    gravado = _leds_de(caminho, CHAVE_UM).get("player_leds")
    assert gravado == [False, False, True, False, True], (
        f"o desenho não chegou ao override do controle: {gravado!r}")


def test_a_gravacao_da_lampada_nao_apaga_a_cor_do_controle(pac, a04):
    """A fusão é POR CAMPO — a mesma regra dos dois irmãos que já existiam.

    Um override do disco dela hoje é `{"lightbar": [255, 0, 0]}` e nada mais;
    trocar a seção inteira por uma que só fale de desenho apagaria a cor que ela
    escolheu para aquele controle.
    """
    caminho = _semear(overrides={CHAVE_UM: {"lightbar": (255, 0, 0),
                                            "lightbar_brightness": 0.5}})
    a04.luzes(_ctx(pac), _clique(lampada="2"), PonteDeMentira())

    leds = _leds_de(caminho, CHAVE_UM)
    assert leds.get("lightbar") == [255, 0, 0], "a cor própria se perdeu"
    assert leds.get("lightbar_brightness") == 0.5, "o brilho próprio se perdeu"
    assert leds.get("player_leds") is not None, "o desenho não entrou"


def test_a_lampada_parte_do_override_quando_ele_existe(pac, a04):
    """O estado de partida é o DADO, e o override vence o padrão do número."""
    _semear(overrides={CHAVE_UM: {"player_leds": [True, True, False, False, False]}})
    ponte = PonteDeMentira()
    a04.luzes(_ctx(pac), _clique(lampada="2"), ponte)

    (args, _), = ponte.so("player_leds_set_detalhado")
    assert args[0] == (True, False, False, False, False), (
        f"o clique partiu do padrão do número em vez do override: {args[0]}")


def test_a_lampada_recusa_dizendo_quando_o_daemon_nao_responde(pac, a04):
    """O dublê SABE RECUSAR, e o gesto levanta a frase do produto."""
    _semear()
    with pytest.raises(RuntimeError) as erro:
        a04.luzes(_ctx(pac), _clique(lampada="1"), PonteDeMentira(corpo=None))
    assert str(erro.value), "a recusa saiu sem frase"


def test_a_lampada_recusa_sem_controle_e_sem_numero(pac, a04):
    """Duas guardas, e as duas dizem o que falta."""
    _semear()
    with pytest.raises(ValueError):
        a04.luzes(_ctx(pac), {"lampada": "1"}, PonteDeMentira())
    with pytest.raises(ValueError):
        a04.luzes(_ctx(pac), _clique(lampada="9"), PonteDeMentira())


# ---------------------------------------------------------------------------
# csv:141 — OS QUATRO DESENHOS, E O NOME QUE ENGANA
# ---------------------------------------------------------------------------
def test_o_desenho_do_p3_num_controle_que_e_o_p1_nao_muda_o_numero(pac, a04):
    """A mordida que a sprint pede com todas as letras.

    *"Clique `Desenho do P3` num controle que é o P1 e prove que o número
    continua 1 e as lâmpadas mudaram."*

    A TABELA É DO DAEMON — `core/led_control.player_led_pattern`. Ela é lida, e
    não digitada: se alguém a trocar, esta régua reprova em vez de o aparelho
    acender o desenho de outro jogador.
    """
    from hefesto_dualsense4unix.core.led_control import player_led_pattern

    caminho = _semear()
    ponte = PonteDeMentira()
    a04.desenho_de(_ctx(pac), _clique(desenho="3"), ponte)

    (args, kwargs), = ponte.so("player_leds_set_detalhado")
    assert args[0] == tuple(player_led_pattern(3)), (
        f"a tecla do P3 não mandou o padrão canônico do 3: {args[0]}")
    assert kwargs == {"uniq": UM}
    # AS DUAS METADES DO "sem trocar o número".
    assert "identity_number_set" not in ponte.nomes(), (
        "a tecla de desenho renumerou o controle")
    assert _do_disco(caminho).get("controllers", {}).get(CHAVE_UM, {}) \
        .get("player_slot") is None, "a tecla de desenho mexeu no número"


def test_a_tecla_todas_acende_as_cinco(pac, a04):
    _semear()
    ponte = PonteDeMentira()
    a04.desenho_de(_ctx(pac), _clique(desenho=a04.TODAS), ponte)
    (args, _), = ponte.so("player_leds_set_detalhado")
    assert args[0] == (True,) * 5


def test_a_tecla_de_desenho_recusa_um_valor_que_nao_e_desenho(pac, a04):
    _semear()
    with pytest.raises(ValueError):
        a04.desenho_de(_ctx(pac), _clique(desenho="banana"), PonteDeMentira())


# ---------------------------------------------------------------------------
# csv:142 — O CAMINHO DE VOLTA, E ELE TIRA O OVERRIDE (NÃO O ZERA)
# ---------------------------------------------------------------------------
def test_todas_apagadas_tira_o_override_em_vez_de_zera_lo(pac, a04):
    """**A segunda mordida da sprint**, e ela é sobre a forma do que fica.

    *"apague todas, prove que o override SAIU (não que ficou zerado — SAIU)"*.

    POR QUE ZERAR SERIA O OPOSTO: `manager._controllers_to_specs` monta o
    `OutputSpec` a partir de `model_fields_set`; `player_leds: [false]*5` gravado
    é uma escolha EXPLÍCITA, e o backend a respeita — as cinco ficariam presas
    APAGADAS, acima da camada automática. O que solta é o campo deixar de
    existir no arquivo.
    """
    caminho = _semear(overrides={CHAVE_UM: {"player_leds": [True] * 5,
                                            "lightbar": (255, 0, 0)}})
    a04.desenho_de(_ctx(pac), _clique(desenho=a04.NENHUMA), PonteDeMentira())

    leds = _leds_de(caminho, CHAVE_UM)
    assert "player_leds" not in leds, (
        f"o desenho ficou GRAVADO em vez de sair — {leds!r}. Cinco falsos "
        f"explícitos prendem as lâmpadas apagadas; o caminho de volta é o campo "
        f"deixar de existir")
    assert leds.get("lightbar") == [255, 0, 0], (
        "voltar as luzes ao automático apagou a COR própria do controle — são "
        "campos diferentes e a fusão é por campo")


def test_todas_apagadas_manda_o_daemon_reaplicar_o_perfil(pac, a04):
    """Só o disco não basta: a camada da USUÁRIA vive no daemon.

    `player_leds_set_detalhado` escreve na camada MANUAL, e `reset_profile_overrides`
    só solta o que está carimbado como `perfil`. Quem solta a manual é
    `ProfileManager.apply(origin="manual")` — e o único caminho até ele, daqui,
    é o `profile.switch` que `perfil.gravar_e_reaplicar` dispara.
    """
    _semear(overrides={CHAVE_UM: {"player_leds": [True] * 5}})
    ponte = PonteDeMentira()
    a04.desenho_de(_ctx(pac), _clique(desenho=a04.NENHUMA), ponte)

    assert ponte.so("profile_switch"), (
        "o perfil não foi reaplicado — o disco mudou e o aparelho ficou com o "
        "desenho preso, que é a tela dizendo uma coisa e o fio fazendo outra")
    assert not ponte.so("player_leds_set_detalhado"), (
        "o caminho de volta MANDOU um desenho ao aparelho — escrever "
        "`[False] * 5` na camada manual reescreveria justamente a camada que o "
        "`profile.switch` da linha seguinte existe para soltar")


def test_todas_apagadas_diz_o_que_fez(pac, a04):
    _semear(overrides={CHAVE_UM: {"player_leds": [True] * 5}})
    fora = a04.desenho_de(_ctx(pac), _clique(desenho=a04.NENHUMA),
                          PonteDeMentira())
    assert isinstance(fora, dict) and fora.get("recado"), (
        "o único ato desta célula cujo efeito não se vê no próprio botão saiu "
        "calado")
    assert "mesa" not in fora["recado"].lower(), (
        "a palavra `mesa` voltou a um texto de tela — ela é banida desde 06/09")


# ---------------------------------------------------------------------------
# csv:143 — O REENVIO, E ELE NÃO GRAVA
# ---------------------------------------------------------------------------
def test_o_reenvio_manda_o_desenho_que_esta_na_tela(pac, a04):
    _semear(overrides={CHAVE_UM: {"player_leds": [True, False, False, False, True]}})
    ponte = PonteDeMentira()
    a04.reenviar_desenho(_ctx(pac), _clique(), ponte)

    (args, kwargs), = ponte.so("player_leds_set_detalhado")
    assert args[0] == (True, False, False, False, True)
    assert kwargs == {"uniq": UM}


def test_o_reenvio_nao_cria_override_em_quem_nao_tinha(pac, a04):
    """Reenviar não é uma escolha nova — é repetir a que já está na tela.

    Gravar aqui PRENDERIA as lâmpadas de um controle que só estava exibindo o
    padrão automático do número, por um clique cujo texto promete "de novo".
    """
    caminho = _semear()
    a04.reenviar_desenho(_ctx(pac), _clique(), PonteDeMentira())
    assert "player_leds" not in _leds_de(caminho, CHAVE_UM), (
        "o reenvio gravou um override em quem não tinha nenhum")


# ---------------------------------------------------------------------------
# csv:148 — "TODOS NO AUTOMÁTICO", O ÚNICO DESFAZER DE UMA VEZ
# ---------------------------------------------------------------------------
def test_todos_no_automatico_limpa_as_cores_de_todos_e_religa_o_campo(pac, a04):
    """Campo a campo, o que o gêmeo da GTK faz (`on_lightbar_auto_reset_all`)."""
    caminho = _semear(
        automatico=False,
        overrides={CHAVE_UM: {"lightbar": (255, 0, 0), "lightbar_brightness": 0.5},
                   CHAVE_DOIS: {"lightbar": (0, 255, 0),
                                "player_leds": [True] * 5}})
    fora = a04.automatico_de_todos(_ctx(pac), _clique(), PonteDeMentira())

    disco = _do_disco(caminho)
    assert disco["leds"]["auto_player_colors"] is True, (
        "o automático não voltou a valer")
    for chave in (CHAVE_UM, CHAVE_DOIS):
        leds = _leds_de(caminho, chave)
        assert "lightbar" not in leds, f"a cor própria de {chave} ficou"
        assert "lightbar_brightness" not in leds, f"o brilho de {chave} ficou"
    # O DESENHO FICA — é o que a GTK preserva, e mexer nele aqui faria as duas
    # telas do mesmo produto responderem coisas diferentes ao mesmo botão.
    assert _leds_de(caminho, CHAVE_DOIS).get("player_leds") == [True] * 5, (
        "o `Todos no automático` apagou o desenho das luzes de jogador — o "
        "gêmeo da janela estável limpa a COR, e só ela")
    assert isinstance(fora, dict) and fora.get("recado")


def test_todos_no_automatico_reaplica_o_perfil(pac, a04):
    _semear(automatico=False,
            overrides={CHAVE_UM: {"lightbar": (255, 0, 0)}})
    ponte = PonteDeMentira()
    a04.automatico_de_todos(_ctx(pac), _clique(), ponte)
    assert ponte.so("profile_switch"), (
        "o perfil não foi reaplicado — as cores sairiam do disco e ficariam no "
        "aparelho até a próxima troca de perfil")


# ---------------------------------------------------------------------------
# O CO-OP, E A RECUSA QUE DIZ
# ---------------------------------------------------------------------------
def _com_coop(pac):
    """`players` É UM NÚMERO, e não um mapa — é o que o daemon publica.

    `o_coop_manda` lê `int(coop["players"]) > 1`, e a docstring dele traz a
    medição da mesa dela: `coop.enabled` continua `True` com o co-op parado, e
    quem responde de verdade é a CONTAGEM. Um dublê com um dicionário aqui faria
    o `int()` levantar, a função devolver `False` e esta régua pular calada —
    que é a forma de dublê que esta casa nomeia como "o que só sabe passar".
    """
    return _ctx(pac, state={"coop": {"enabled": True, "players": 2}})


def test_com_o_coop_ligado_os_tres_gestos_recusam_dizendo(pac, a04):
    """Escrever o override debaixo do co-op seria escrever debaixo de quem manda.

    A medição é a de `_acender_o_numero`, e ela é da mesa dela: com o co-op
    ligado o daemon responde `aplicado_em` e as lâmpadas **não se movem** — a
    camada dele está acima do override no merge por campo do backend. Um
    "aplicado" sobre lâmpadas paradas é a mentira que esta casa nomeia.
    """
    _semear()
    ctx = _com_coop(pac)
    if not a04.o_coop_manda(ctx.state):
        pytest.skip("o dublê de estado não acendeu o co-op — nada a medir")
    for chamar, carga in ((a04.luzes, _clique(lampada="1")),
                          (a04.desenho_de, _clique(desenho="2")),
                          (a04.reenviar_desenho, _clique())):
        ponte = PonteDeMentira()
        with pytest.raises(RuntimeError) as erro:
            chamar(ctx, carga, ponte)
        assert "co-op" in str(erro.value), (
            f"{chamar.__name__} recusou sem dizer que quem manda é o jogo")
        assert not ponte.so("player_leds_set_detalhado"), (
            f"{chamar.__name__} escreveu no aparelho debaixo do co-op")


# ---------------------------------------------------------------------------
# A LEITURA DO DESENHO VIVO — as duas camadas que esta tela alcança
# ---------------------------------------------------------------------------
def test_o_global_do_perfil_nao_vale_como_desenho_escolhido(a04):
    """`LedsConfig.player_leds` nasce `[False] * 5` em TODO perfil desta casa.

    Lê-lo como escolha faria a tela afirmar "as cinco apagadas" em trinta e três
    perfis dela, e o reenvio mandaria o preto ao aparelho.
    """
    from hefesto_dualsense4unix.core.led_control import player_led_pattern

    cru = {"leds": {"player_leds": [False] * 5}, "controllers": {}}
    assert a04.desenho_gravado(cru, UM) is None
    assert a04.desenho_de_agora(cru, UM, 2) == tuple(player_led_pattern(2)), (
        "o desenho de partida deixou de ser o padrão do número")


def test_a_chave_do_override_passa_pelo_dono_nos_dois_lados(a04):
    """Um perfil editado à mão guarda `aa:bb:cc:…` — a mesma cura do brilho."""
    cru = {"leds": {}, "controllers": {UM: {"leds": {"player_leds": [True] * 5}}}}
    assert a04.desenho_gravado(cru, UM) == (True,) * 5
    assert a04.desenho_gravado(cru, CHAVE_UM) == (True,) * 5


# ---------------------------------------------------------------------------
# A TELA — as doze teclas na página, e nenhuma num lugar vazio
# ---------------------------------------------------------------------------
def test_a_pagina_oferece_as_doze_teclas_em_toda_coluna_conectada():
    import monta
    from hefesto_dualsense4unix.interface import onde
    from pacotes import a04_iluminacao as a04

    import re

    texto = onde.pagina(PAGINA).read_text(encoding="utf-8")
    grade = texto.split('<div class="luz-grade">', 1)[-1] \
                 .split('<div class="rodape"', 1)[0]
    celulas = re.findall(r'<div class="cel-leds">(.*?)<div class="cel-acoes">',
                         grade, re.S)
    assert len(celulas) == len(monta.CONECTADOS)
    for bloco in celulas:
        assert bloco.count(f'data-gesto="{a04.GESTO_DA_LAMPADA}"') == 5
        assert bloco.count(f'data-gesto="{a04.GESTO_DO_DESENHO_DE}"') == 6
        assert f'data-gesto="{a04.GESTO_DO_REENVIO_DO_DESENHO}"' in bloco


def test_nenhum_lugar_vazio_oferece_tecla_de_luz():
    """Sem aparelho não há desenho a mandar — a mesma regra das outras células."""
    import re

    from hefesto_dualsense4unix.interface import onde
    from pacotes import a04_iluminacao as a04

    texto = onde.pagina(PAGINA).read_text(encoding="utf-8")
    grade = texto.split('<div class="luz-grade">', 1)[-1] \
                 .split('<div class="rodape"', 1)[0]
    for bloco in re.findall(
            r'<div class="ctrl vazia"(.*?)(?=<div class="ctrl[" ]|\Z)',
            grade, re.S):
        for gesto in (a04.GESTO_DA_LAMPADA, a04.GESTO_DO_DESENHO_DE,
                      a04.GESTO_DO_REENVIO_DO_DESENHO):
            assert f'data-gesto="{gesto}"' not in bloco, (
                f"um lugar vazio oferece `{gesto}` — o gesto levantaria `o "
                f"clique não disse em qual controle`, e o botão engoliria o toque")


def test_o_escopo_global_mora_na_faixa_do_titulo():
    """Dentro de uma coluna ele mentiria sobre o alcance — e custaria linha."""
    from hefesto_dualsense4unix.interface import onde
    from pacotes import a04_iluminacao as a04

    texto = onde.pagina(PAGINA).read_text(encoding="utf-8")
    topo = texto.split('<div class="quadro-topo">', 1)[-1].split("</div>", 1)[0]
    assert f'data-gesto="{a04.GESTO_DO_AUTOMATICO_DE_TODOS}"' in topo
    assert ">Todos no automático</button>" in topo


def test_a_botoeira_declara_o_piso_da_aba(a04):
    """O piso SÓ SOBE, e uma queda não aparece na tela — o clique simplesmente
    deixaria de fazer alguma coisa, que é o estado de antes desta sprint."""
    assert a04.PISO_DA_ABA >= 11

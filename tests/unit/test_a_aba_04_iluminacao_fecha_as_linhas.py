#!/usr/bin/env python3
"""As QUATRO decisões dela na aba Iluminação, medidas uma a uma — 04/09/2026.

A fonte é `docs/process/2026-09-04-O-PO-DECIDE-as-54-e-os-sete-conflitos.md`,
§2, aba `04-iluminacao`, e a sprint
`2026-09-04-ONDA2-04-ILUMINACAO-01-o-interruptor-de-verdade-e-a-cor-que-se-grava-ao-desligar`:

    [01] a razão do tracejado    uma linha só quando há ressalva          (D-02)
    [02] o automático do perfil  interruptor DE VERDADE na aba            (D-13)
    [03] reenviar uma cor        a caixa do hexadecimal vira o botão
    [04] o brilho guardado       uma frase curta

**A DE PESO É A [02], E ELA VEIO CONTRA A RECOMENDAÇÃO ESCRITA.** A lista desta
aba propunha que o botão só MOSTRASSE o estado do automático, e que mudá-lo
continuasse na aba Perfis (conflito C-4). Ela escolheu o interruptor, aceitou o
custo declarado (~30 px) e aceitou a consequência que ele abre — com estas
palavras: *"ok aceito o caminho"*. **Desligar GRAVA a cor de cada controle no
ato**, para cumprir a regra dela de 03/09 (*"nenhuma cor dos controles nunca
pode ser a mesma"*) sem o produto nunca dizer não a ela.

O QUE ESTE ARQUIVO MEDE, com a mordida escrita em cada caso:

1. o interruptor tem dono, mora no TOPO da aba, e a página o oferece com os
   três atributos que o piloto precisa para lê-lo e escrevê-lo;
2. **desligar grava a cor de cada CONECTADO no override dele**, com o
   `auto_player_colors` indo a `false` no MESMO arquivo — é a D-13 inteira;
3. ligar de volta não apaga cor nenhuma, e o perfil é REAPLICADO nas duas
   direções (sem isso o campo só entra em vigor na próxima troca de perfil, e o
   interruptor seria o botão que aceita o toque e não age);
4. o `click` que o navegador manda junto do `change` não inverte duas vezes;
5. o reenvio lê o TEXTO da caixa, e **ignora o `data-hex`** — que é a metade
   que morde: o `data-hex` é escrito pelo gerador e fica congelado no que o
   mockup sabia;
6. a linha de ressalva carrega a frase do MOTOR, some quando não há o que
   dizer, e **não cobra pixel no repouso** — medido no Chrome, na página;
7. a frase do brilho guardado é curta e **não é uma recusa**.

O LAR É DE MENTIRA. O `conftest` desvia `HOME` e os quatro `XDG_*`; os casos que
gravam escrevem perfil de verdade, com `save_profile`, dentro dele — que é a
única forma de provar que o disco recebeu, em vez de provar que a função foi
chamada. É o mesmo desenho de `test_a_04_o_trilho_de_brilho_grava.py`.

**RELATADO, e é de outra posse:** `("04-iluminacao.html", "auto-cores")` tem de
entrar em `hefesto_vivo.PERIGOSOS` — o gesto chama `gravar_e_reaplicar`, e a
régua de clique acionaria o interruptor sozinha, desligando o automático no
perfil DELA para provar que sabe clicar. `interface/hefesto_vivo.py` é da ONDA 0
e esta frente não o toca; quem já reprova por isso é
`tests/unit/test_todo_gesto_que_grava_esta_protegido.py`, com o nome do gesto na
mensagem.
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

#: AS DUAS COLUNAS COMO O DAEMON AS PUBLICA. `lightbar_rgb` é PÓS-escala de
#: brilho por contrato (D8) — aqui, os dois a 100%: o azul do P1 e o vermelho do
#: P2, que são `player_slot_color(1)` e `(2)`.
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

    **ELE SABE RECUSAR**, e é o que o `COMO-EXECUTAR-UMA-SPRINT` exige de todo
    dublê desta casa: com `corpo=None` o `led.set` volta sem corpo e os gestos de
    cor levantam a frase do produto. Um dublê que só sabe passar não é dublê.
    """

    def __init__(self, corpo: object = ...):
        self.corpo = ({"aplicado_em": [UM, DOIS], "guardado_em": []}
                      if corpo is ... else corpo)
        self.chamadas: list[tuple[str, tuple, dict]] = []

    def __getattr__(self, nome: str):
        def registrar(*args, **kwargs):
            self.chamadas.append((nome, args, kwargs))
            return True if nome in ("chamar", "profile_switch") else self.corpo

        return registrar

    def nomes(self) -> list[str]:
        return [c[0] for c in self.chamadas]


def _semear(nome: str = "regua", *, automatico: bool = True,
            overrides: dict | None = None, brilho: float = 1.0):
    """Escreve um perfil no lar de mentira e devolve o caminho do arquivo.

    ELE PASSA PELO `save_profile` DO PRODUTO, e não por um `json.dump` à mão: o
    que este arquivo mede é um round-trip disco→gesto→disco, e semear por fora
    do dono deixaria a régua concordando com uma forma de arquivo que o produto
    não escreve.
    """
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
        leds=LedsConfig(lightbar=(40, 80, 180), lightbar_brightness=brilho,
                        auto_player_colors=automatico),
        controllers={
            chave: ControllerOverrides(leds=LedsConfig(**campos))
            for chave, campos in (overrides or {}).items()
        },
    )
    return save_profile(prof, origem="regua")


def _do_disco(caminho) -> dict:
    return json.loads(pathlib.Path(caminho).read_text(encoding="utf-8"))


def _mudanca(**extra) -> dict:
    """O clique que o piloto manda quando ela MEXE num `<input>`: o `change`.

    Os dois campos são do BOOTSTRAP e chegam em todo clique — `tipo` é o
    `tagName` do alvo e `evento` é o `ev.type`. Escrevê-los aqui é o que separa
    o ato da abertura; ver `a04_iluminacao._so_abriu_o_seletor`.
    """
    return {"controle": "p1", "uniq": UM, "tipo": "input",
            "evento": "change", "valor": "on", "texto": "", **extra}


# ---------------------------------------------------------------------------
# [02] O INTERRUPTOR DO AUTOMÁTICO — a D-13, e ela é a decisão de peso da aba
# ---------------------------------------------------------------------------
def test_o_interruptor_tem_dono(pac, a04):
    """Um `data-gesto` sem função é uma chave que engole o clique.

    A MORDIDA: apague o `@gesto("04-iluminacao.html", "auto-cores")` e esta
    linha reprova — que é o estado da aba até hoje, com a diferença de que lá
    nem o interruptor existia.
    """
    assert pac.gesto_da_pagina(PAGINA, "auto-cores") is not None
    assert a04.PISO_DA_ABA >= 7, (
        f"o piso da aba é {a04.PISO_DA_ABA} e só sobe — com 5 a régua dos "
        f"botões daria verde sobre uma aba que perdeu o interruptor e o "
        f"reenvio")


def test_a_pagina_oferece_o_interruptor_no_topo_da_aba():
    """*"Um interruptor no topo da aba Iluminação."* — e o topo é a faixa do título.

    AS TRÊS METADES, e a segunda é a que morde: sem
    `data-hef-alvo="marcado"` a chave fica congelada no `checked` que o gerador
    escreveu e passa a afirmar o estado do MOCKUP sobre o perfil dela.

    A MORDIDA: tire o `data-hef-alvo="marcado"` do gerador, rode
    `python3 aba04.py` — o próprio `_conferir` reprova antes desta linha. São
    duas réguas independentes sobre o mesmo defeito, e é regra desta casa.
    """
    from hefesto_dualsense4unix.interface import onde
    from pacotes import a04_iluminacao as a04

    texto = onde.pagina(PAGINA).read_text(encoding="utf-8")
    topo = texto.split('<div class="quadro-topo">', 1)[-1].split("</div>", 1)[0]
    assert 'class="chave-auto"' in topo, (
        "o interruptor não está na faixa do título — fora dela ele custa uma "
        "linha da grade, e a coluna já está a 4px do teto medido")
    for atributo in (f'data-gesto="{a04.ENDERECO_DO_AUTOMATICO}"',
                     f'data-campo="{a04.ENDERECO_DO_AUTOMATICO}"',
                     'data-hef-alvo="marcado"'):
        assert atributo in topo, f"o interruptor perdeu {atributo!r}"


def test_o_pacote_diz_o_estado_do_automatico(a04, pac):
    """A tela lê o PERFIL, e as duas respostas são exercitadas.

    A LÍNGUA É `sim`/`""` — a do alvo `marcado` do piloto. `str(True)` seria
    `"True"`, o JS escreveria `"true"` e a chave nunca marcaria.

    A MORDIDA: troque o `"sim"` por `True` no `pacote()` e a primeira linha
    reprova; troque a leitura por uma constante e a segunda.
    """
    _semear(automatico=True)
    assert a04.pacote(_ctx(pac))[a04.ENDERECO_DO_AUTOMATICO] == "sim"
    _semear(automatico=False)
    assert a04.pacote(_ctx(pac))[a04.ENDERECO_DO_AUTOMATICO] == ""


def test_o_estado_do_automatico_chega_a_tela(a04, pac):
    """E ele atravessa o `normalizar`, que é o que a tela consome.

    NÃO É ZELO: o `normalizar` DESCARTA `dict` e lista de `dict`, e um campo que
    ele comesse sairia do pacote sem uma linha de erro — foi assim que o
    `blocos:` ficou dois dias fora da tela, calado. O interruptor é da MESA (um
    valor para o perfil inteiro), então ele tem de aparecer em `mesa`.
    """
    _semear(automatico=True)
    fora = pac.normalizar(a04.pacote(_ctx(pac)))
    assert fora["mesa"].get(a04.ENDERECO_DO_AUTOMATICO) == "sim", (
        "o estado do automático não chegou à `mesa` — o piloto só escreve o "
        f"que está lá, e o `{a04.ENDERECO_DO_AUTOMATICO}` sumiu no caminho")


def test_desligar_grava_a_cor_de_cada_controle(pac, a04):
    """**A D-13 INTEIRA, e é o caso que ela aceitou por escrito.**

    *"ok aceito o caminho"* — desligar o automático grava a cor de cada
    controle no ato. Sem isso, o controle que chega depois cai na cor GLOBAL do
    perfil, o seguinte também, e dois ficam iguais: a regra dela de 03/09
    (*"nenhuma cor dos controles nunca pode ser a mesma"*) quebraria pelo
    caminho que o próprio interruptor abre.

    AS TRÊS ASSERÇÕES SÃO UMA SÓ DECISÃO: o campo global vai a `false`, os DOIS
    conectados ganham override de cor, e as duas cores são DIFERENTES.

    A MORDIDA: apague o laço `for c in ctx.conectados` do gesto e o
    `auto_player_colors: false` continua indo ao disco — o interruptor passa a
    funcionar e a regra dela cai calada. As duas últimas asserções reprovam.
    """
    caminho = _semear(automatico=True)
    p = PonteDeMentira()
    a04.auto_cores(_ctx(pac), _mudanca(), p)

    disco = _do_disco(caminho)
    assert disco["leds"]["auto_player_colors"] is False, (
        "o interruptor não desligou o automático no perfil")
    cores = {}
    for chave in (CHAVE_UM, CHAVE_DOIS):
        dele = disco.get("controllers", {}).get(chave, {})
        assert "leds" in dele and "lightbar" in dele["leds"], (
            f"o controle {chave} ficou SEM cor gravada — com o automático fora "
            f"ele cai na cor global, e o vizinho também: as duas iguais")
        cores[chave] = tuple(dele["leds"]["lightbar"])
    assert cores[CHAVE_UM] != cores[CHAVE_DOIS], (
        f"os dois controles ficaram com a MESMA cor ({cores}) — é exatamente a "
        f"regra dela que a gravação existe para cumprir")


def test_a_cor_gravada_e_a_que_estava_acesa(pac, a04):
    """E ela é a PEDIDA, não a publicada — a diferença é o brilho.

    `lightbar_rgb` vem PÓS-escala por contrato do daemon (D8). Gravar esse valor
    faria a cor do perfil escurecer a cada volta: a 50%, o azul `#0000FF` acende
    `#00007F`, e guardar `#00007F` deixaria o brilho escalá-lo DE NOVO na
    aplicação seguinte.

    A MORDIDA: troque `cor_escolhida(...)` por `cor_do_swatch(...)` cru em
    `_a_cor_de_agora` e esta linha reprova com `(0, 0, 127)`.
    """
    caminho = _semear(automatico=True, brilho=0.5)
    meio = dict(P1, lightbar_rgb=[0, 0, 127])
    a04.auto_cores(_ctx(pac, conectados=[meio]), _mudanca(), PonteDeMentira())

    gravada = _do_disco(caminho)["controllers"][CHAVE_UM]["leds"]["lightbar"]
    assert tuple(gravada) == (0, 0, 255), (
        f"gravou {tuple(gravada)} — a cor guardada é a PEDIDA, e a 50% de "
        f"brilho o daemon publica a metade dela")


def test_sem_cor_conhecida_grava_a_do_numero(pac, a04):
    """A queda não é preto, e não é um remendo: é a cor que o automático dava.

    Nos estados em que o motor não afirma cor (a Steam com o `fd`, Nativo, cor
    desconhecida) o que o automático estava dando àquele controle é exatamente
    `player_slot_color(numero)` — é essa a paleta que ele governa. Um preto aqui
    apagaria a barra dela por um clique num interruptor.

    A MORDIDA: troque a queda por `(0, 0, 0)` e esta linha reprova.
    """
    from hefesto_dualsense4unix.core.led_control import player_slot_color

    caminho = _semear(automatico=True)
    cego = dict(P1, lightbar_source="desconhecida", lightbar_rgb=None)
    a04.auto_cores(_ctx(pac, conectados=[cego]), _mudanca(), PonteDeMentira())

    gravada = tuple(_do_disco(caminho)["controllers"][CHAVE_UM]["leds"]["lightbar"])
    assert gravada == player_slot_color(1), (
        f"gravou {gravada} — sem cor conhecida a resposta é a do número, que é "
        f"o que o automático estava dando")


def test_ligar_de_volta_nao_apaga_cor_nenhuma(pac, a04):
    """O caminho de volta, e ele não tem consequência a confessar.

    As cores gravadas continuam no perfil; a camada automática passa a vencer no
    merge por campo do backend. Apagá-las aqui perderia a escolha dela sem uma
    palavra na tela.

    A MORDIDA: faça o gesto limpar `controllers` ao ligar e esta linha reprova.
    """
    caminho = _semear(automatico=False,
                      overrides={CHAVE_UM: {"lightbar": (7, 8, 9)}})
    a04.auto_cores(_ctx(pac), _mudanca(), PonteDeMentira())

    disco = _do_disco(caminho)
    assert disco["leds"]["auto_player_colors"] is True
    assert tuple(disco["controllers"][CHAVE_UM]["leds"]["lightbar"]) == (7, 8, 9), (
        "ligar o automático apagou a cor que ela tinha escolhido para o "
        "controle — override e camada automática convivem no merge por campo")


def test_o_interruptor_reaplica_o_perfil(pac, a04):
    """Metade do gesto, e sem ela ele é o botão que aceita o toque e não age.

    `auto_player_colors` só entra em vigor na ATIVAÇÃO do perfil
    (`ProfileManager._configure_auto_player_colors`, chamado por
    `apply_profile`). Gravar sem reaplicar deixaria a tela dizendo uma coisa e o
    aparelho fazendo outra até a próxima troca de perfil.

    A MORDIDA: troque `gravar_e_reaplicar` por `save_profile` puro e esta linha
    reprova nomeando o que faltou.
    """
    _semear(automatico=True)
    p = PonteDeMentira()
    a04.auto_cores(_ctx(pac), _mudanca(), p)
    assert "profile_switch" in p.nomes(), (
        f"o gesto não mandou o daemon reaplicar o perfil: {p.nomes()}")


def test_o_click_que_vem_junto_do_change_nao_inverte_duas_vezes(pac, a04):
    """Um clique dela é UM ato — e o navegador manda dois eventos por ele.

    Um `<input type="checkbox">` dispara `click` E `change` no mesmo ato, e o
    BOOTSTRAP escuta os dois. Sem o guarda, um clique viraria DUAS inversões: o
    interruptor voltaria sozinho ao lugar, com duas gravações no perfil dela
    pelo caminho.

    A MORDIDA: tire o `if _so_abriu_o_seletor(o): return None` do gesto e esta
    linha reprova — o `auto_player_colors` volta a `True` e o arquivo ganha uma
    segunda gravação.
    """
    caminho = _semear(automatico=True)
    ctx = _ctx(pac)
    p = PonteDeMentira()
    a04.auto_cores(ctx, _mudanca(evento="click"), p)
    assert _do_disco(caminho)["leds"]["auto_player_colors"] is True, (
        "o `click` sozinho já inverteu — com o `change` que vem junto, um "
        "clique dela viraria duas gravações")
    assert p.chamadas == [], f"o `click` chegou a falar com o daemon: {p.nomes()}"


def test_sem_perfil_ativo_o_interruptor_recusa_dizendo(pac, a04):
    """As cores automáticas são do PERFIL, não da máquina.

    `RuntimeError` é o contrato: é a única exceção que o piloto leva ao cartão
    dela. Um `ValueError` aqui iria para o terminal de quem lançou a janela.
    """
    with pytest.raises(RuntimeError, match="perfil"):
        a04.auto_cores(_ctx(pac, perfil=""), _mudanca(), PonteDeMentira())


def test_o_recado_do_interruptor_conta_a_consequencia(pac, a04):
    """O cartão diz as DUAS metades do que aconteceu ao desligar.

    A segunda é a que ela aceitou por escrito, e é a que ninguém adivinha: o
    clique gravou a cor de cada controle. Um recado que só dissesse "desligado"
    esconderia uma escrita no perfil dela.
    """
    _semear(automatico=True)
    saiu = a04.auto_cores(_ctx(pac), _mudanca(), PonteDeMentira())
    assert isinstance(saiu, dict) and "recado" in saiu, (
        "o gesto voltou calado — o canal de sucesso da D-01 existe justamente "
        "para o clique que muda o perfil dizer o que fez")
    assert "cor" in saiu["recado"].lower(), (
        f"o recado não conta a gravação da cor: {saiu['recado']!r}")


# ---------------------------------------------------------------------------
# [03] A CAIXA DO HEXADECIMAL VIRA O BOTÃO
# ---------------------------------------------------------------------------
def test_o_reenvio_manda_a_cor_escrita_na_caixa(pac, a04):
    """O gesto existe, e o que ele manda é o texto que está na tela.

    A MORDIDA: troque `o.get("texto")` por `o.get("hex")` no gesto e o caso
    seguinte reprova — este continuaria verde, e é por isso que são dois.
    """
    assert pac.gesto_da_pagina(PAGINA, "reenviar") is not None
    p = PonteDeMentira()
    a04.reenviar(_ctx(pac), {"controle": "p1", "uniq": UM, "texto": "#12AB34"}, p)
    assert p.chamadas and p.chamadas[0][0] == "led_set_detalhado"
    assert p.chamadas[0][1] == ((18, 171, 52),), (
        f"o reenvio mandou {p.chamadas[0][1]!r}")


def test_o_reenvio_ignora_o_data_hex(pac, a04):
    """**A metade que morde**, e ela é a razão inteira de o gesto ser novo.

    `data-hex` é escrito pelo GERADOR e fica congelado no que o mockup sabia. Um
    reenvio por ele mandaria ao plástico dela a cor do DESENHO — que é o defeito
    que a prova botão a botão pegou em 01/09, quando o `data-hex` levava o tom
    da CASA ao aparelho.

    Aqui o clique traz os dois campos, com valores diferentes de propósito: o
    `hex` do mockup e o `texto` que o produto pintou. Passa quem lê o segundo.
    """
    p = PonteDeMentira()
    a04.reenviar(_ctx(pac),
                 {"controle": "p1", "uniq": UM,
                  "hex": "#FF0000", "texto": "#12AB34"}, p)
    assert p.chamadas[0][1] == ((18, 171, 52),), (
        f"o reenvio leu o `data-hex` congelado: {p.chamadas[0][1]!r}")


def test_a_caixa_do_hexadecimal_nao_leva_data_hex():
    """E a página não oferece a porta errada — a régua olha o ARQUIVO.

    A MORDIDA: acrescente `data-hex="{cor}"` à caixa no `aba04.py` e o próprio
    `_conferir` reprova ao gerar; esta linha é a segunda régua sobre o mesmo
    defeito, do lado do arquivo publicado na bancada.
    """
    from hefesto_dualsense4unix.interface import onde

    texto = onde.pagina(PAGINA).read_text(encoding="utf-8")
    caixas = [linha for linha in texto.splitlines() if 'class="hex reenvia"' in linha]
    assert caixas, "a caixa do hexadecimal deixou de ser botão"
    for caixa in caixas:
        assert 'data-gesto="reenviar"' in caixa
        assert "data-hex=" not in caixa, (
            "a caixa ganhou `data-hex` — o reenvio passaria a mandar a cor "
            "cravada no desenho, e não a que está na tela")


def test_o_travessao_de_um_lugar_vazio_nao_reenvia(pac, a04):
    """Numa coluna que esvaziou, a caixa mostra `—`, e `—` não é cor.

    A folha desta aba já tira o clique dali (`pointer-events:none`); esta é a
    segunda trava — a que vale se alguém alcançar o gesto por outro caminho.

    A MORDIDA: apague a guarda e o gesto passa a levantar a frase de formato do
    `hex_to_rgb`, que fala com quem programa em vez de dizer o que aconteceu.
    """
    from pacotes import TRAVESSAO

    p = PonteDeMentira()
    with pytest.raises(ValueError, match="sem controle"):
        a04.reenviar(_ctx(pac), {"controle": "p3", "uniq": UM,
                                 "texto": TRAVESSAO}, p)
    assert p.chamadas == [], "a recusa ainda assim falou com o daemon"


# ---------------------------------------------------------------------------
# [01] A LINHA DE RESSALVA — a D-02 aplicada a esta aba
# ---------------------------------------------------------------------------
def test_a_ressalva_carrega_a_frase_do_motor(pac, a04):
    """A frase é de `controller_card.rotulo_lightbar`, e não se escreve aqui.

    A RÉGUA PERGUNTA AO DONO em vez de digitar a frase: a casa pagou onze vezes
    em 26/08 por réguas que digitavam o que deviam ler — elas reprovam a melhora
    em vez do defeito.

    A MORDIDA: troque o `recado` por uma frase escrita no `pacote()` e esta
    linha reprova, porque o motor diz outra coisa.
    """
    from hefesto_dualsense4unix.app.widgets.controller_card import rotulo_lightbar

    _semear()
    disputado = dict(P1, lightbar_disputada=True)
    ctx = _ctx(pac, conectados=[disputado])
    esperado, _ = rotulo_lightbar(disputado, ctx.state)

    coluna = a04.pacote(ctx)["colunas"][UM]
    assert coluna[a04.ENDERECO_DA_RESSALVA] == esperado, (
        f"a linha diz {coluna[a04.ENDERECO_DA_RESSALVA]!r} e o motor diz "
        f"{esperado!r}")


def test_sem_ressalva_a_linha_recebe_o_marcador(pac, a04):
    """E a chave vai em TODO tique — é o que faz a linha sumir.

    Omiti-la quando não há nada a dizer deixaria a frase anterior na tela para
    sempre; mandar `""` a trocaria por um travessão solto, porque `escrever()`
    faz isso de propósito.

    A MORDIDA: emita `""` em vez do marcador e a tela passa a mostrar um `—`
    debaixo de uma tira que está perfeitamente acesa.
    """
    _semear()
    coluna = a04.pacote(_ctx(pac))["colunas"][UM]
    assert coluna[a04.ENDERECO_DA_RESSALVA] == a04.NADA_A_DIZER


def test_o_marcador_e_o_mesmo_do_monta(a04):
    """As duas cópias do literal não podem divergir caladas.

    É a mesma guarda que `test_a_linha_de_ressalva_so_nasce_quando_ha` faz para
    a `a06_navegacao`: a folha das dez esconde a linha por
    `:has(.nada)`, e um marcador diferente aqui deixaria a linha VISÍVEL, vazia,
    cobrando a altura da fonte nas quatro colunas.
    """
    import monta

    assert a04.NADA_A_DIZER == monta.NADA_A_DIZER, (
        f"o marcador divergiu: `monta` diz {monta.NADA_A_DIZER!r} e "
        f"`a04_iluminacao` diz {a04.NADA_A_DIZER!r}")


def test_a_pagina_tem_a_linha_em_todo_lugar_da_mesa():
    """Uma ressalva que nasça em três de quatro colunas é a quarta calada.

    E SÃO OS QUATRO LUGARES, não os dois conectados — 07/09/2026. Esta régua
    contava `len(monta.CONECTADOS)`, e assim **media o defeito**: o lugar que  (noqa-acento)
    nascia vazio não tinha a linha, e o P3 que chegasse depois não teria onde
    acender a razão de a barra ter apagado — voltaria a escondê-la no `title`,
    que é exatamente o que a D-02 fechou.

    NO REPOUSO ELA NÃO CUSTA PIXEL, e é por isso que pôr as quatro é de graça:
    a folha das dez a tira do fluxo por `:has(.nada)`, e a desta aba a esconde
    enquanto `data-conectado="nao"`. Quem mede esse pixel é
    `test_no_repouso_a_linha_nao_cobra_pixel_e_a_aba_nao_rola`, logo acima.

    A MORDIDA: devolva `len(monta.CONECTADOS)` ao `exigir` da §10 do `aba04.py`
    e regere — o gerador para antes de escrever, e esta régua reprova com 2.
    """
    import monta
    from hefesto_dualsense4unix.interface import onde
    from pacotes import a04_iluminacao as a04

    texto = onde.pagina(PAGINA).read_text(encoding="utf-8")
    grade = texto.split('<div class="luz-grade">', 1)[-1]
    quantas = grade.count(
        f'class="ressalva" data-campo="{a04.ENDERECO_DA_RESSALVA}"')
    assert quantas == len(monta.MESA), (
        f"a linha de ressalva está em {quantas} coluna(s) e a mesa do desenho "
        f"tem {len(monta.MESA)} lugar(es) — o lugar sem ela fica mudo no dia "
        f"em que ganhar um controle")
    assert monta.NADA_A_DIZER in grade, (
        "a linha nasceu com frase cravada — o desenho passaria a afirmar uma "
        "causa que só o produto vivo conhece")


# ---------------------------------------------------------------------------
# A LINHA NA TELA — lida no Chrome, porque pixel não se deduz
# ---------------------------------------------------------------------------
CHROME = pathlib.Path("/usr/bin/google-chrome")


@pytest.fixture(scope="module")
def pagina_no_chrome():
    """A aba aberta num Chrome de verdade, com a `.nota` escondida.

    `headless` E NADA DE JANELA: ela tem UMA tela e está trabalhando nela. É a
    mesma escolha de `interface/olhar.py`, e a razão está no topo do
    `COMO-OLHAR-A-TELA.md`.
    """
    if not CHROME.exists():
        pytest.skip("Chrome do sistema ausente — esta régua mede pixel de verdade")
    playwright = pytest.importorskip("playwright.sync_api")
    from hefesto_dualsense4unix.interface import onde

    with playwright.sync_playwright() as pw:
        b = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"],
                               ignore_default_args=["--hide-scrollbars"])
        pg = b.new_page(viewport={"width": 1920, "height": 1080},
                        device_scale_factor=1)
        pg.goto(f"file://{onde.pagina(PAGINA)}")
        pg.wait_for_load_state("networkidle")
        pg.add_style_tag(content=".nota{display:none}")
        pg.wait_for_timeout(300)
        yield pg
        b.close()


def _medida(pg) -> dict:
    """O que a tela mostra — e o VÃO DO PAI, que é onde o pixel se paga.

    **A ALTURA DA LINHA NÃO RESPONDE À PERGUNTA, e isto está medido nesta
    bancada, em 04/09/2026.** Com as duas metades do `.ressalva` arrancadas de
    `monta.CSS_FOLHA`, o Chrome continua devolvendo **0 px** para a linha vazia:
    um bloco cujo único filho é um inline VAZIO não gera caixa de linha. Uma
    régua que olhasse só a altura daria VERDE com a cura fora — foi o que
    aconteceu na primeira redação deste arquivo, e é a mesma armadilha que
    `test_a_linha_de_ressalva_so_nasce_quando_ha` já documenta para a peça
    genérica.

    QUEM PAGA O PIXEL É O PAI: dentro de um flex o `margin-top:5px` da linha
    **não colapsa**, então a linha escondida-mas-presente empurra a tira 2,5 px
    para cima dentro da faixa. Por isso o que se mede aqui é o VÃO ACIMA e o VÃO
    ABAIXO da tira na célula dela: com a peça, os dois são iguais; sem ela,
    diferem pela metade do `margin-top`.
    """
    return pg.evaluate("""() => {
      const m = document.querySelector('.miolo');
      const q = document.querySelector('.quadro.luzes');
      const vaos = Array.from(document.querySelectorAll('.cel-leds')).map(cel => {
        const c = cel.getBoundingClientRect();
        const t = cel.querySelector('.aceso').getBoundingClientRect();
        return [+(t.top - c.top).toFixed(2), +(c.bottom - t.bottom).toFixed(2)];
      });
      return {rola: m.scrollHeight > m.clientHeight,
              quadro: Math.round(q.getBoundingClientRect().height),
              colunas: Array.from(document.querySelectorAll('.ctrl'))
                .map(c => Math.round(c.getBoundingClientRect().height)),
              ressalvas: Array.from(document.querySelectorAll('.ressalva'))
                .map(e => Math.round(e.getBoundingClientRect().height)),
              vaos: vaos};
    }""")


def test_no_repouso_a_linha_nao_cobra_pixel_e_a_aba_nao_rola(pagina_no_chrome):
    """A régua da D-02, aplicada a esta aba: zero no repouso.

    DUAS COISAS DE UMA VEZ, e as duas são pixel medido:

    * **a linha vazia não empurra a tira** — a folha das dez a tira do fluxo por
      `:has(.nada)`, e sem isso o `margin-top:5px` dela desequilibra a célula.
      Ver `_medida`: a altura da linha NÃO serve para medir isto;
    * o quadro CABE. A coluna cresceu 12px com a faixa da ressalva, e o teto
      desta aba é medido: passar dele faz o miolo rolar por dentro, e quadro que
      rola por dentro é conteúdo que ninguém sabe que existe.

    AS DUAS MORDIDAS, e as duas foram feitas:

    * comente `.ressalva:empty` e `.ressalva:has(.nada)` em `monta.CSS_FOLHA` —
      os vãos passam a `8.5 / 13.5` e a primeira asserção reprova;
    * suba `--r-leds` sem tirar de outra linha (80px) — a segunda reprova, e o
      quadro vai a 550 contra os 530 que a caixa do miolo oferece.
    """
    m = pagina_no_chrome and _medida(pagina_no_chrome)
    assert m["vaos"], "nenhuma `.cel-leds` na página — a tira perdeu a célula"
    for acima, abaixo in m["vaos"]:
        assert abs(acima - abaixo) <= 0.6, (
            f"a tira ficou descentrada na faixa dos LEDs ({acima} acima, "
            f"{abaixo} abaixo) — a linha de ressalva vazia está no fluxo e "
            f"cobra o `margin-top` dela em toda tela")
    assert not m["rola"], (
        f"a aba passou a rolar por dentro — o quadro mede {m['quadro']}px")


def test_com_a_frase_a_linha_aparece_e_a_aba_continua_cabendo(pagina_no_chrome):
    """E o outro lado: com ressalva ela nasce, e o orçamento aguenta.

    A frase é escrita como o PILOTO a escreve — `innerHTML` no `data-campo`, que
    é o alvo `html` — e não com um `display:block` de mentira: medir o mecanismo
    em vez do caminho real deixaria passar uma linha que o produto nunca
    consegue acender.

    E O LUGAR SEM DONO ENTROU NA CONTA — 07/09/2026, com a função única do
    `aba04.py`: a linha de ressalva passou a nascer nos QUATRO lugares, e não
    só nos dois conectados. Até aqui esta régua escrevia a frase em TODAS as
    linhas e cobrava altura de todas, porque só havia duas e as duas tinham
    dono. Agora há quatro, e escrever ressalva num lugar vazio é um estado que
    o produto **não produz**: `pacotes.apagar_os_lugares_sem_dono` escreve
    TRAVESSÃO em todo campo de um lugar sem dono, e a chave da ressalva só é
    montada para quem tem dono (`a04_iluminacao`, `ENDERECO_DA_RESSALVA`).

    ENTÃO A RÉGUA PASSA A SIMULAR O PRODUTO, em duas metades — e a segunda é a
    que morde, porque ela é nova:

    * **com dono, a frase acende.** É a D-02 de sempre.
    * **um lugar que GANHA dono acende a dele.** O piloto vira
      `data-conectado` nos dois sentidos (passos `1b` e `1c`), e é só isso que
      ele vira: a classe `.vazia` é fato de NASCIMENTO e ninguém a tira nunca.
      Uma folha que esconda a ressalva por `.vazia` — em vez de por
      `[data-conectado="nao"]` — deixa o P3 mudo para sempre, inclusive depois
      de ele chegar. Foi essa a escolha que esta metade guarda.

    A MORDIDA: tire a `.cel-leds` do gerador e ponha a ressalva como oitava
    faixa da grade; a penúltima asserção reprova, porque a faixa nova cobra o
    `--r-passo` inteiro e o quadro passa do teto. Para a metade nova, troque
    `[data-conectado="nao"]` por `.vazia` na regra da ressalva do `aba04.py`.
    """
    pg = pagina_no_chrome
    antes = _medida(pg)
    # Como o produto faz: a ressalva vai para quem TEM dono.
    acesas = pg.evaluate("""() => {
      let n = 0;
      for (const raiz of document.querySelectorAll('.ctrl[data-conectado="sim"]'))
        for (const el of raiz.querySelectorAll('[data-campo="luz-ressalva"]')) {
          el.innerHTML = 'A Steam tem este controle aberto'; n += 1;
        }
      return n;
    }""")
    pg.wait_for_timeout(120)
    depois = _medida(pg)

    assert acesas, "nenhuma coluna conectada tem linha de ressalva"
    with_dono = pg.evaluate("""() => Array.from(
      document.querySelectorAll('.ctrl[data-conectado="sim"] .ressalva'))
      .map(e => Math.round(e.getBoundingClientRect().height))""")
    assert min(with_dono) > 0, (
        "a frase entrou e a linha continuou com altura zero — a folha a esconde "
        "por engano, e a razão do tracejado volta a viver só no `title`")
    assert depois["colunas"] == antes["colunas"], (
        f"a coluna mudou de altura com a frase ({antes['colunas']} → "
        f"{depois['colunas']}) — as divisórias das cinco colunas deixam de "
        f"cair no mesmo y, que é o que ela mandou arrumar em 30/08")
    assert not depois["rola"], "com a ressalva na tela a aba passou a rolar"

    # E A METADE QUE MORDE: o lugar vazio ganha dono, como no passo `1c`.
    ganhou = pg.evaluate("""() => {
      const raiz = document.querySelector('.ctrl[data-conectado="nao"]');
      if (!raiz) return null;
      raiz.dataset.conectado = 'sim';
      raiz.classList.remove('off');
      for (const el of raiz.querySelectorAll('[data-campo="luz-ressalva"]'))
        el.innerHTML = 'A Steam tem este controle aberto';
      return raiz.getAttribute('data-controle');
    }""")
    assert ganhou, "a mesa do desenho não tem nenhum lugar vazio para reabrir"
    pg.wait_for_timeout(120)
    alt = pg.evaluate("""(pref) => Math.round(document.querySelector(
      '[data-controle="' + pref + '"] .ressalva').getBoundingClientRect().height)""",
                      ganhou)
    assert alt > 0, (
        f"o lugar {ganhou} ganhou um controle e a razão do tracejado dele "
        f"continuou invisível — a folha o esconde por uma marca que o piloto "
        f"não tira. `.vazia` é fato de nascimento; quem vira nos dois sentidos "
        f"é `data-conectado`")


# ---------------------------------------------------------------------------
# [04] A FRASE DO BRILHO GUARDADO — curta, e não é uma recusa
# ---------------------------------------------------------------------------
def test_o_brilho_guardado_diz_uma_frase_curta_e_nao_recusa(pac, a04):
    """Decisão [04] dela, entre a frase inteira, a curta e o silêncio.

    **E O DESFECHO DEIXOU DE MENTIR SOBRE SI MESMO.** A frase saía por
    `RuntimeError`, que no piloto é o canal da RECUSA — cartão laranja, 30 s. E
    o produto FEZ: o brilho está no disco dela, que é a promessa inteira do
    gesto. Com a D-01 entregue, ele volta pelo canal de SUCESSO.

    AS TRÊS ASSERÇÕES: não levanta, o disco recebeu, e a frase é UMA — sem a
    explicação do *"porque não há cor a reacender"*, que é o que ela mandou
    cortar (*"a versão longa repete com palavras o que a tira tracejada já diz
    com desenho"*).

    A QUARTA ASSERÇÃO FOI INVERTIDA EM 05/09/2026, e a razão é decisão dela na
    04-Q4:

        *"1, mas com o botão realmente fazendo o que se pressupõe a fazer"*

    Ela dizia `p.chamadas == []` — *sem cor conhecida, o gesto NÃO escreve no
    aparelho*. Era o defeito, não o contrato: o trilho gravava 60% no disco e a
    barra continuava no brilho de antes, e o produto ficava com a promessa
    escrita e nada aceso. Agora o gesto escreve a cor de agora no brilho
    escolhido, e a ressalva sobre a disputa continua vindo na frase — que é o
    que ela pediu: o disco E o aparelho, com o aviso.

    A MORDIDA: devolva o `raise RuntimeError(...)` e a primeira asserção
    reprova; devolva a frase longa e a terceira; tire o `_escrever_a_cor` do
    ramo sem cor pedida e a quarta.
    """
    caminho = _semear()
    disputado = dict(P1, lightbar_disputada=True)
    ctx = _ctx(pac, conectados=[disputado])
    p = PonteDeMentira()

    saiu = a04.brilho(ctx, {"controle": "p1", "uniq": UM, "tipo": "input",
                            "evento": "change", "valor": "60"}, p)

    assert isinstance(saiu, dict) and saiu.get("recado"), (
        "o gesto não devolveu recado — ou levantou, e um brilho GUARDADO não é "
        "uma recusa")
    frase = saiu["recado"]
    guardado = _do_disco(caminho)["controllers"][CHAVE_UM]["leds"]
    assert guardado["lightbar_brightness"] == pytest.approx(0.6), (
        f"a frase saiu e o disco não recebeu: {guardado}")
    assert "reacender" not in frase and len(frase) <= 110, (
        f"a frase não encolheu ({len(frase)} caracteres): {frase!r}")
    assert p.nomes() == ["led_set_detalhado"], (
        f"o brilho escolhido não chegou ao aparelho: {p.nomes()}")
    _, _, argumentos = p.chamadas[0]
    assert argumentos.get("brightness") == pytest.approx(0.6), (
        f"chegou ao aparelho com outro brilho: {argumentos}")


def test_a_frase_curta_carrega_a_causa_do_motor(pac, a04):
    """Encolher não é perder o porquê: a causa continua vindo do dono.

    A MORDIDA: escreva a causa à mão no gesto e esta linha reprova, porque o
    motor diz outra coisa.
    """
    from hefesto_dualsense4unix.app.widgets.controller_card import rotulo_lightbar

    _semear()
    disputado = dict(P1, lightbar_disputada=True)
    ctx = _ctx(pac, conectados=[disputado])
    causa, _ = rotulo_lightbar(disputado, ctx.state)

    saiu = a04.brilho(ctx, {"controle": "p1", "uniq": UM, "tipo": "input",
                            "evento": "change", "valor": "60"}, PonteDeMentira())
    assert causa in saiu["recado"], (
        f"a frase não traz a causa do motor ({causa!r}): {saiu['recado']!r}")


# ---------------------------------------------------------------------------
# A GUARDA DO LAR DE MENTIRA — sem ela, tudo acima poderia escrever no dela
# ---------------------------------------------------------------------------
def test_a_pasta_de_perfis_desta_regua_e_de_mentira():
    """A guarda de vacuidade, e ela é a mais importante deste arquivo.

    Sete casos aqui chamam `save_profile`. Se o desvio do `conftest` cair, eles
    gravariam nos 33 perfis DELA — e o sintoma seria um teste VERDE. Uma régua
    que pode estragar a máquina de quem a roda tem de provar, ANTES, que está no
    lugar certo.

    A COMPARAÇÃO É CONTRA O `$HOME` REAL, e é o `conftest` quem o guarda
    (`lar_real`, fixado antes do desvio). Comparar contra `Path.home()` não
    mediria nada: dentro da suíte ele JÁ é o lar de mentira, e a asserção seria
    verdadeira nos dois mundos.

    A MORDIDA: rode um caso deste arquivo com a escotilha do `conftest` ligada
    (ela desarma o desvio) e esta linha reprova.

    O `lar_real` VEM DO MÓDULO CARREGADO PELO PYTEST, e não de um `import
    conftest`: o `tests/conftest.py` é carregado como plugin, com nome próprio,
    e não está em `sys.path` para um import comum.
    """
    from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir

    conftest = next(m for nome, m in sys.modules.items()
                    if nome.endswith("conftest") and hasattr(m, "lar_real"))
    onde_grava = pathlib.Path(profiles_dir()).resolve()
    real = pathlib.Path(conftest.lar_real()).resolve()
    assert not onde_grava.is_relative_to(real), (
        f"a régua escreveria em {onde_grava}, que está dentro do $HOME REAL "
        f"({real}) — sete casos deste arquivo chamam `save_profile`")

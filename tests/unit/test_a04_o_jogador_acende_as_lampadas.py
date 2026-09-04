#!/usr/bin/env python3
"""AS CINCO LÂMPADAS SEGUEM O NÚMERO — a queixa dela, 04/09/2026.

*"escolha do jogador no iluminação não funciona"*.

O gesto `player` da aba Iluminação chamava `identity.number.set` e parava aí.
Isso troca o NÚMERO EXIBIDO; as cinco lâmpadas brancas do DualSense não vêm
com ele. Medido na mesa dela, com os dois controles ligados e o daemon vivo,
lendo `/sys/class/leds` a cada passo::

    estado de partida            slot=2 → lâmpadas do 2 · slot=1 → do 1
    1. identity.number.set       slot=1 → lâmpadas do 2 · slot=2 → do 1   ✗
    2. + led.player_set por uniq slot=1 → lâmpadas do 2 · slot=2 → do 1   ✗
    3. + coop.sync               slot=1 → lâmpadas do 1 · slot=2 → do 2   ✓

**A LINHA 2 É O QUE ESTA RÉGUA GUARDA.** A cura óbvia — escrever o desenho por
`uniq` — não move lâmpada nenhuma com o co-op ligado, e o daemon ainda responde
``aplicado_em: [<o controle>]``. É a camada do co-op repintando por cima, uma
posição acima do override por-uniq no merge do backend. Um gesto que escrevesse
o override e lesse aquele `aplicado_em` como sucesso poria "aplicado" na tela
dela sobre duas lâmpadas paradas.

Daí os DOIS ramos que os testes abaixo separam, e a régua existe porque eles são
fáceis de fundir num só por engano:

* co-op mandando (mais de um jogador na mesa) → `coop.sync`, e **nenhum**
  override — escrever debaixo de quem manda é o que não funciona;
* co-op fora → o desenho por `uniq`, com o padrão do número de AGORA, para o
  alvo E para o parceiro da troca.

A MORDIDA, e ela está escrita nos testes um a um: tire a chamada de
`_acender_o_numero` do gesto e sete testes reprovam; troque o `player_led_pattern`
por um literal e o teste da tabela reprova; funda os dois ramos e o do co-op
reprova dizendo que escreveu override debaixo de quem manda.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

#: Dois controles de mentira. MACs da faixa sintética da casa — há dois portões
#: de anonimato nesta árvore e eles não perdoam.
P1 = "aa:bb:cc:00:00:01"
P2 = "aa:bb:cc:00:00:02"

CONECTADOS = [
    {"uniq": P1, "player": 1, "connected": True, "transport": "usb",
     "lightbar_rgb": [0, 0, 255], "is_primary": True, "inputs": {}},
    {"uniq": P2, "player": 2, "connected": True, "transport": "bt",
     "lightbar_rgb": [255, 0, 0], "is_primary": False, "inputs": {}},
]
MESA = [
    {"pref": "p1", "jogador": 1, "uniq": P1, "nome": "Um", "via": "USB"},
    {"pref": "p2", "jogador": 2, "uniq": P2, "nome": "Dois", "via": "BT"},
]

#: O CORPO FELIZ do `led.player_set`, na forma EXATA que a mesa dela devolveu
#: (medida em 04/09/2026, colada do log). Um dicionário inventado aqui poria a
#: régua a medir uma resposta que o daemon não dá.
def _corpo(uniq: str, bits: tuple[bool, ...]) -> dict:
    return {"status": "ok", "bits": list(bits),
            "aplicado_em": [uniq], "guardado_em": []}


class Ponte:
    """O dublê da `pacotes/ponte.py` — guarda o que foi chamado, na ORDEM.

    Ele responde por QUALQUER nome de propósito (o mesmo desenho do dublê da
    régua dos botões): virar uma segunda lista das funções da ponte faria a
    régua envelhecer em silêncio. Quem confere que o nome existe de verdade é
    `test_os_botoes_tem_dono.test_nenhum_gesto_chama_funcao_que_a_ponte_nao_tem`.
    """

    def __init__(self, *, numero_ok: bool = True, motivo: str | None = None,
                 corpo: object = "feliz", coop_ok: bool = True) -> None:
        self.chamadas: list[tuple[str, tuple, dict]] = []
        self._numero_ok = numero_ok
        self._motivo = motivo
        self._corpo = corpo
        self._coop_ok = coop_ok

    def identity_number_set(self, uniq: str, n: int):
        self.chamadas.append(("identity_number_set", (uniq, n), {}))
        return self._numero_ok, self._motivo

    def player_leds_set_detalhado(self, bits, uniq=None):
        self.chamadas.append(("player_leds_set_detalhado", (tuple(bits),),
                              {"uniq": uniq}))
        return _corpo(uniq, tuple(bits)) if self._corpo == "feliz" else self._corpo

    def chamar(self, metodo: str, timeout=None, **params):
        self.chamadas.append(("chamar", (metodo,), params))
        return self._coop_ok

    def __getattr__(self, nome: str):
        def registrar(*args, **kwargs):
            self.chamadas.append((nome, args, kwargs))
            return True
        return registrar

    def nomes(self) -> list[str]:
        return [c[0] for c in self.chamadas]

    def desenhos(self) -> list[tuple[str, tuple]]:
        """(uniq, bits) de cada escrita das cinco lâmpadas, na ordem."""
        return [(kw["uniq"], a[0]) for n, a, kw in self.chamadas
                if n == "player_leds_set_detalhado"]


@pytest.fixture(scope="module")
def pac():
    import pacotes

    return pacotes


def _ctx(pac, *, coop_players: int = 0):
    """A mesa da régua. `coop_players` > 1 é o co-op MANDANDO nas lâmpadas.

    O gate é `players`, e não `enabled`, porque é o que `o_coop_manda` mede — a
    camada do co-op no backend só existe com secundário na mesa, e ler o
    booleano diria "quem manda é o co-op" numa mesa de um jogador só.
    """
    state = {"active_profile": "regua",
             "coop": {"enabled": bool(coop_players), "players": coop_players}}
    return pac.Contexto(state=state, mesa=MESA, conectados=CONECTADOS,
                        estados={})


def _clique(uniq: str, n: int) -> dict:
    return {"controle": "p1", "uniq": uniq, "player": str(n), "texto": "Régua"}


def _gesto(pac):
    fn = pac.gesto_da_pagina("04-iluminacao.html", "player")
    assert fn is not None, "o gesto `player` da aba Iluminação perdeu o dono"
    return fn


# --------------------------------------------------------------------------
# 1. o coração: o clique acende, e acende o desenho CERTO no controle CERTO
# --------------------------------------------------------------------------
def test_o_clique_no_jogador_escreve_o_desenho_das_cinco_lampadas(pac):
    """MORDIDA: tire `_acender_o_numero(ctx, p, uniq, n)` do fim do gesto.

    Sem ela o gesto volta a ser meio gesto — renumera e não acende —, que é
    exatamente a queixa dela. Este teste reprova dizendo que só o número foi.
    """
    p = Ponte()
    _gesto(pac)(_ctx(pac), _clique(P1, 2), p)

    assert "player_leds_set_detalhado" in p.nomes(), (
        "o clique no jogador NÃO escreveu as cinco lâmpadas — só trocou o "
        "número. É a queixa dela de 04/09/2026, de volta.")
    assert (P1, (False, True, False, True, False)) in p.desenhos(), (
        f"o controle clicado não recebeu o desenho do Player 2. Foi: "
        f"{p.desenhos()}")


def test_o_desenho_sai_da_tabela_do_daemon_e_nao_de_um_literal(pac):
    """O bitmask é `core/led_control.player_led_pattern`, e só ele.

    MORDIDA: escreva os padrões à mão no gesto. Enquanto forem iguais aos da
    tabela nada acusa — e foi assim que os quatro botões "Desenho do PN" da
    janela GTK ficaram pintando o desenho antigo, sem um teste vermelho
    (`lightbar_actions.aplicar_desenho_do_jogador`, a fiação que faltava). Este
    teste compara com a tabela VIVA: mudá-la move a expectativa junto.
    """
    from hefesto_dualsense4unix.core.led_control import player_led_pattern

    for n in (1, 2, 3, 4):
        p = Ponte()
        _gesto(pac)(_ctx(pac), _clique(P1, n), p)
        assert (P1, tuple(player_led_pattern(n))) in p.desenhos(), (
            f"Player {n}: o desenho escrito não é `player_led_pattern({n})`. "
            f"Foi: {p.desenhos()}")


def test_o_parceiro_da_troca_tambem_acende_o_numero_novo(pac):
    """Trocar é TROCA: os DOIS mudam de número, os dois mudam de lâmpada.

    MORDIDA: devolva só `[(uniq, n)]` em `_pares_da_troca`. O alvo acende
    certo e o parceiro fica preso no desenho que o alvo acabou de receber —
    dois controles com o MESMO padrão aceso, que é a colisão que a numeração
    única (R-24) existe para matar.
    """
    from hefesto_dualsense4unix.core.led_control import player_led_pattern

    p = Ponte()
    # O P1 é o 1 e pede o 2; o P2, que tem o 2, fica com o 1.
    _gesto(pac)(_ctx(pac), _clique(P1, 2), p)

    assert p.desenhos() == [
        (P1, tuple(player_led_pattern(2))),
        (P2, tuple(player_led_pattern(1))),
    ], (f"a troca não acendeu os dois lados: {p.desenhos()}")


def test_sem_parceiro_na_mesa_so_o_alvo_recebe(pac):
    """Número livre não inventa um segundo destinatário.

    MORDIDA: faça `_pares_da_troca` devolver sempre dois pares. Com um número
    que ninguém tem, o segundo par teria `uniq` vazio — um `led.player_set` sem
    alvo, que o daemon grava no DEFAULT GLOBAL e o próximo reforço do
    automático desfaz. É o defeito PLAYER-01 medido na GTK: sucesso mentiroso.
    """
    p = Ponte()
    _gesto(pac)(_ctx(pac), _clique(P1, 4), p)  # ninguém tem o 4 nesta mesa

    assert [u for u, _ in p.desenhos()] == [P1], (
        f"o clique num número livre escreveu em mais de um controle: "
        f"{p.desenhos()}")


# --------------------------------------------------------------------------
# 2. a ordem, e o que ela decide
# --------------------------------------------------------------------------
def test_renumera_primeiro_e_acende_depois(pac):
    """Sem o número novo não há padrão de lâmpada a acender.

    MORDIDA: inverta as duas metades de `player`. A lâmpada passa a acender o
    número VELHO — e o teste reprova na ordem, não no conteúdo.
    """
    p = Ponte()
    _gesto(pac)(_ctx(pac), _clique(P1, 2), p)

    assert p.nomes()[0] == "identity_number_set", (
        f"a primeira chamada foi {p.nomes()[0]!r}, e tinha de ser a "
        f"renumeração: o desenho é função do número NOVO.")


def test_a_renumeracao_recusada_nao_acende_nada(pac):
    """O daemon recusou o número (jogo aberto, número fora da mesa): pare aí.

    MORDIDA: tire o `raise` do ramo `if not ok`. As lâmpadas passam a acender
    um número que o produto NÃO deu ao controle — a tela mostrando um jogador e
    o plástico mostrando outro.
    """
    p = Ponte(numero_ok=False, motivo="O jogo está aberto")
    with pytest.raises(RuntimeError, match="O jogo está aberto"):
        _gesto(pac)(_ctx(pac), _clique(P1, 2), p)

    assert "player_leds_set_detalhado" not in p.nomes(), (
        "a renumeração foi RECUSADA e o gesto acendeu as lâmpadas assim "
        "mesmo.")


# --------------------------------------------------------------------------
# 3. o ramo do co-op — o que a medição da mesa dela derrubou
# --------------------------------------------------------------------------
def test_com_o_coop_mandando_o_gesto_reconcilia_em_vez_de_escrever(pac):
    """Com o co-op ligado, o override por-uniq é escrito DEBAIXO de quem manda.

    Medido na mesa dela em 04/09/2026: `led.player_set` por `uniq` respondeu
    `aplicado_em` para os DOIS controles e nenhuma lâmpada se mexeu — a camada
    do co-op fica acima do override no merge por campo do backend. O que move é
    recalcular a camada, e o gesto que o produto tem para isso é `coop.sync`.

    MORDIDA: apague o ramo do co-op de `_acender_o_numero` e deixe só a escrita
    por `uniq`. Este teste reprova nos dois sentidos — o `coop.sync` some e o
    override aparece.
    """
    p = Ponte()
    _gesto(pac)(_ctx(pac, coop_players=2), _clique(P1, 2), p)

    assert ("chamar", ("coop.sync",), {}) in p.chamadas, (
        f"com o co-op mandando, o gesto não pediu a reconciliação da mesa: "
        f"{p.chamadas}")
    assert "player_leds_set_detalhado" not in p.nomes(), (
        "com o co-op mandando, o gesto escreveu o override por-uniq — a "
        "escrita que a mesa dela mediu como INERTE (o daemon diz `aplicado` e "
        "a lâmpada não muda).")


def test_um_jogador_so_nao_e_coop_mandando(pac):
    """`players: 1` é o co-op LIGADO sem secundário — e aí a camada não existe.

    `coop._apply_coop_player_leds` volta antes de publicar quando não há
    secundário (e revoga a camada que houver). Ler `enabled` em vez de
    `players` mandaria um `coop.sync` inútil e deixaria o override — que é o
    que de fato acende — sem ser escrito.

    MORDIDA: troque `o_coop_manda` por `state["coop"]["enabled"]`.
    """
    p = Ponte()
    _gesto(pac)(_ctx(pac, coop_players=1), _clique(P1, 2), p)

    assert "player_leds_set_detalhado" in p.nomes(), (
        f"com UM jogador na mesa o gesto não escreveu o desenho: {p.nomes()}")
    assert "chamar" not in p.nomes(), (
        f"com UM jogador na mesa o gesto pediu `coop.sync`: {p.nomes()}")


def test_o_coop_que_nao_reconcilia_recusa_dizendo(pac):
    """O daemon não respondeu ao `coop.sync`: quem clicou fica sabendo.

    MORDIDA: troque o `raise` por um `return`. O número muda, as lâmpadas não,
    e a tela não diz uma palavra — o silêncio que esta casa nomeia como o
    defeito mais caro.
    """
    p = Ponte(coop_ok=False)
    with pytest.raises(RuntimeError) as erro:
        _gesto(pac)(_ctx(pac, coop_players=2), _clique(P1, 2), p)

    assert "lâmpadas" in str(erro.value), (
        f"a frase da recusa não fala das lâmpadas: {erro.value}")


# --------------------------------------------------------------------------
# 4. o desfecho se LÊ do corpo do daemon — a razão de a porta ser `_detalhado`
# --------------------------------------------------------------------------
def test_sem_resposta_do_daemon_o_gesto_recusa_dizendo(pac):
    """`None` = o Hefesto não respondeu. A frase é a da GTK, não uma nossa.

    MORDIDA: troque `player_leds_set_detalhado` por `player_leds_set` e jogue o
    retorno fora. O gesto passa a dizer "aplicado" para um daemon desligado —
    o mesmo defeito que os três gestos de cor desta aba tinham até 02/09.
    """
    from hefesto_dualsense4unix.app.actions import lightbar_actions

    p = Ponte(corpo=None)
    with pytest.raises(RuntimeError) as erro:
        _gesto(pac)(_ctx(pac), _clique(P1, 2), p)

    assert str(erro.value) == str(lightbar_actions._AVISO_HEFESTO_DESLIGADO), (
        f"a frase do daemon mudo não é a da janela GTK: {erro.value}")


def test_o_guardado_chega_na_tela_em_vez_de_virar_aplicado(pac):
    """O daemon GUARDOU (o controle não está na mesa): a tela tem de dizer.

    É a razão inteira de a porta ser a `_detalhado`. Com o `bool` do
    `player_leds_set`, um "guardado" e um "aplicado" são o mesmo `True`, e o
    cartão diria que a lâmpada acendeu.

    MORDIDA: no `_cobrar_a_frase_do_desenho`, devolva sem comparar. Este teste
    reprova dizendo que o gesto engoliu o guardado.
    """
    p = Ponte(corpo={"status": "ok", "aplicado_em": [], "guardado_em": [P1]})
    with pytest.raises(RuntimeError) as erro:
        _gesto(pac)(_ctx(pac), _clique(P1, 2), p)

    assert "guardado" in str(erro.value).lower(), (
        f"o guardado do daemon não virou frase de tela: {erro.value}")


def test_a_frase_feliz_e_perguntada_ao_dono_e_nao_digitada(pac):
    """O caminho feliz sai CALADO — e o texto dele não mora neste lado.

    A frase do desenho das cinco luzes é montada dentro de
    `lightbar_actions._msg_do_desenho` e não tem nome público; digitá-la no
    pacote seria a segunda escrita da mesma frase, e o dia em que a GTK a
    mudasse esta aba passaria a levantar sobre um clique que deu certo.

    MORDIDA: escreva a frase feliz à mão no pacote (`f"Desenho das luzes
    atualizado — {descricao}"`) e depois mude o `feito` da GTK para
    "aplicado" — este teste reprova; a comparação por igualdade contra o que o
    dono DIZ não reprova, porque acompanha.
    """
    p = Ponte()
    _gesto(pac)(_ctx(pac), _clique(P1, 2), p)  # não levanta: é o caminho feliz

    fonte = (RAIZ / "src/hefesto_dualsense4unix/interface/pacotes"
                    "/a04_iluminacao.py").read_text(encoding="utf-8")
    assert "Desenho das luzes" not in fonte, (
        "a frase do desenho das cinco luzes foi DIGITADA no pacote. Ela é de "
        "`lightbar_actions._msg_do_desenho`; pergunte a ele.")


# --------------------------------------------------------------------------
# 5. o eco: por que esta aba continua SEM `SEM_ECO`
# --------------------------------------------------------------------------
def test_a_aba_iluminacao_nao_declara_sem_eco(pac):
    """`SEM_ECO` é *"o daemon não publica este assunto"* — e não é o caso aqui.

    A régua `--prova-no-aparelho` do piloto clica cada gesto e cobra que ALGO
    mude no `state_full`. O `state_full` não publica `player_leds` (é comando
    de ida: não há canal de leitura de LED de jogador em transporte nenhum,
    `docs/data/mapa-controles.csv`) — mas **publica `player_slot`**, e é ele
    que este gesto muda, nos DOIS controles da troca. O eco existe; declarar
    `SEM_ECO` calaria a régua para sempre sobre um caminho que ela mede.

    MORDIDA: acrescente `SEM_ECO = ("player",)` ao pacote. Este teste reprova —
    e a régua do aparelho deixaria de acusar o dia em que a renumeração parasse
    de chegar ao daemon.
    """
    from pacotes import a04_iluminacao

    assert not hasattr(a04_iluminacao, "SEM_ECO"), (
        "a aba Iluminação declarou `SEM_ECO`: o gesto `player` muda o "
        "`player_slot`, que o `state_full` publica.")

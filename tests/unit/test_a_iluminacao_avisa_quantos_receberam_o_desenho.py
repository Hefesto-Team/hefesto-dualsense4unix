#!/usr/bin/env python3
"""O aviso dos N na aba Iluminação — ILUMINACAO-O-AVISO-DOS-N-01, 06/09/2026.

**A LINHA DO CSV (`paridade-gtk-html.csv:158`):** *"Aviso 'o mesmo desenho foi
para os N controles'"*, `FALTA_NO_HTML`. O dono da frase é
`lightbar_actions._AVISO_MESMO_DESENHO_NOS_QUATRO` (L12, 25/08/2026) e o dono da
conta é `lightbar_actions._quantos_recebem_o_desenho`; o que faltava era o lado
HTML **ler** os dois e pôr a frase no canal de recado verde (6,0 s).

**O QUE ESTE ARQUIVO MORDE SÃO DUAS COISAS, e a segunda é a que ninguém via.**

1. **A conta era uma CONSTANTE.** `_Janela._quantos_recebem_o_desenho` tinha um
   `return 0` cravado, com a razão escrita: nesta aba todo gesto leva `uniq`,
   e com alvo por controle a própria GTK devolve 0. O valor estava certo; o
   MÉTODO estava errado — ele afirmava sozinho uma conta que tem dono, e uma
   constante não erra junto com o dono, ela só para de concordar. Agora o
   `_Janela` carrega os dois degraus (`_edit_uniq`, `_uniqs_conectados`) e a
   conta é a do dono, sobre os mesmos dados. **A resposta de hoje continua 0** —
   a diferença é que ela passou a ser medida.

2. **O AVISO ERA ENGOLIDO, e por construção.** `_cobrar_a_frase_do_desenho`
   pergunta ao dono o que ele diria no caminho FELIZ e compara com o que ele diz
   para o corpo real; iguais, cala. Só que o `_msg_do_desenho` cola o aviso dos
   N no fim de **toda** frase que compõe quando N ≥ 2 — na do corpo real e na do
   corpo feliz, porque as duas saem do mesmo método com a mesma `_Janela`. As
   duas ficavam iguais, o `!=` calava, e o aviso morria ali dentro: o clique
   teria pegado em N controles e a tela não diria nada. É a L12 —
   *"nada na tela avisava"* — reaparecendo do lado HTML, um degrau adiante.

**A PORTA DO "TODOS" É A DO PRÓPRIO MÓDULO, e é por isso que ela se abre aqui
com a função do produto e não com um dublê.** `_janela_do_desfecho(ctx, "")`
monta um `_Janela` com o alvo em "Todos" — `definir_alvo` é quem sabe que `uniq`
vazio quer dizer isso —, e é literalmente o que o docstring do `_Janela` mandava
fazer *"se um dia esta aba ganhar um Todos"*. **A aba ainda não tem esse
escopo** (é decisão dela, e está na lista *"Ainda aberto"* do `aba04.py`:
*"um 'aplicar a todos' teria de ser um botão próprio — e ele não existe"*), então
a régua abre a porta com `monkeypatch` sobre a FUNÇÃO DO PRODUTO, nunca sobre um
dublê que responda o que a régua quer ouvir.

O LAR É DE MENTIRA: o `conftest` desvia `HOME` e os quatro `XDG_*`, e os casos
que gravam escrevem perfil de verdade com `save_profile` dentro dele. É o mesmo
desenho de `test_a_04_as_cinco_lampadas_sem_o_numero.py`.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
for _p in (str(RAIZ / "src"), str(INTERFACE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

#: MACs da faixa sintética da casa — há dois portões de anonimato nesta árvore.
UM = "aa:bb:cc:00:00:01"
DOIS = "aa:bb:cc:00:00:02"
CHAVE_UM = "aabbcc000001"

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


@pytest.fixture
def dono():
    """O módulo da janela estável — o dono da frase E o dono da conta."""
    from hefesto_dualsense4unix.app.actions import lightbar_actions

    return lightbar_actions


def _ctx(pac, *, perfil="regua", conectados=None, state=None):
    return pac.Contexto(state={"active_profile": perfil, **(state or {})},
                        mesa=[dict(m) for m in MESA],
                        conectados=[dict(c) for c in (conectados or [P1, P2])],
                        estados={})


class PonteDeMentira:
    """Dublê da ponte que guarda o que foi chamado e devolve o caminho feliz.

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
            return ((True, "") if nome == "identity_number_set" else
                    True if nome in ("chamar", "profile_switch") else self.corpo)

        return registrar


def _semear(nome: str = "regua"):
    """Escreve um perfil no lar de mentira, PELO DONO da escrita."""
    from hefesto_dualsense4unix.profiles.loader import save_profile
    from hefesto_dualsense4unix.profiles.schema import (
        LedsConfig,
        MatchAny,
        Profile,
    )

    return save_profile(
        Profile(name=nome, match=MatchAny(),
                leds=LedsConfig(lightbar=(40, 80, 180), lightbar_brightness=1.0,
                                auto_player_colors=True),
                controllers={}),
        origem="regua")


def _janela_de_todos(a04, pac, conectados=None):
    """Um `_Janela` com o alvo em "Todos" — pela função DO PRODUTO.

    `_janela_do_desfecho` com `uniq` vazio é a porta que o próprio módulo
    nomeia; `definir_alvo` é quem sabe que vazio quer dizer "Todos".
    """
    return a04._janela_do_desfecho(_ctx(pac, conectados=conectados), "")


def _abrir_o_todos(monkeypatch, a04, pac):
    """Faz o desfecho desta aba mirar "Todos" — sobre a função do produto.

    A ABA NÃO TEM ESSE ESCOPO HOJE (decisão dela, em aberto), então a régua o
    abre pela única porta honesta: a própria `_janela_do_desfecho`, chamada com
    o `uniq` vazio que ela já sabe interpretar. Nada de dublê que responda o que
    a régua quer ouvir — o objeto que chega ao dono da frase é o mesmo que
    chegaria no dia em que o botão nascer.
    """
    real = a04._janela_do_desfecho
    monkeypatch.setattr(
        a04, "_janela_do_desfecho",
        lambda ctx, uniq, rotulo="": real(ctx, "", rotulo))


# ---------------------------------------------------------------------------
# 1. A CONTA DEIXOU DE SER CONSTANTE
# ---------------------------------------------------------------------------
def test_a_conta_e_a_do_dono_e_nao_um_zero_cravado(a04, pac, dono):
    """Com o alvo em "Todos" e dois na mesa, a conta é DOIS.

    **A MORDIDA:** devolva o `return 0` a `_Janela._quantos_recebem_o_desenho`
    e esta asserção cai — era esse o estado de ontem, e ele estava documentado
    como um fato desta aba em vez de como uma pergunta ao dono.
    """
    janela = _janela_de_todos(a04, pac)
    assert janela._quantos_recebem_o_desenho() == 2, (
        "a `_Janela` não contou os dois controles da mesa com o alvo em "
        "'Todos' — a conta voltou a ser uma constante desta aba")
    # E ELA É A MESMA CONTA DO DONO, sobre o MESMO objeto: se as duas
    # divergirem, quem está reescrevendo a regra é este lado.
    assert (janela._quantos_recebem_o_desenho()
            == dono.LightbarActionsMixin._quantos_recebem_o_desenho(janela)), (
        "a conta desta aba divergiu da do dono sobre o mesmo objeto")


def test_com_alvo_por_controle_a_conta_e_zero_e_agora_e_medida(a04, pac):
    """O zero de hoje continua zero — e passou a ser resposta, não afirmação.

    Todo gesto desta aba leva `uniq`, então o alvo é CONTROLE e o dono devolve
    0. Este caso existe para que a cura não vire regressão silenciosa: se um dia
    a conta passar a responder N para um alvo de um controle só, o aviso apareceria
    num clique que pegou em um.
    """
    janela = a04._janela_do_desfecho(_ctx(pac), UM, "White")
    assert janela._quantos_recebem_o_desenho() == 0, (
        "o alvo é UM controle e a conta disse mais de um — o aviso dos N "
        "apareceria num clique que pegou em um só")


def test_a_mesa_de_um_controle_nao_dispara_o_aviso(a04, pac):
    """"Todos" com UM na mesa é um, e um não é aviso — a régua do limiar.

    O dono só cola a frase a partir de dois (`quantos >= 2`), e é a única
    leitura possível de *"o mesmo desenho foi para os N controles"*.
    """
    janela = _janela_de_todos(a04, pac, conectados=[P1])
    assert janela._quantos_recebem_o_desenho() == 1
    assert a04._o_aviso_dos_n(janela) == "", (
        "um controle só disparou o aviso dos N")


# ---------------------------------------------------------------------------
# 2. A FRASE É DO DONO, PALAVRA POR PALAVRA
# ---------------------------------------------------------------------------
def test_o_aviso_e_a_frase_do_dono_e_nenhuma_silaba_nasce_aqui(a04, pac, dono):
    """O texto sai de `_AVISO_MESMO_DESENHO_NOS_QUATRO`, com o N do dono."""
    janela = _janela_de_todos(a04, pac)
    esperada = dono._AVISO_MESMO_DESENHO_NOS_QUATRO.format(n=2)
    assert a04._o_aviso_dos_n(janela) == esperada, (
        "o aviso do lado HTML não é o texto do dono")


def test_o_pacote_nao_digita_o_texto_do_aviso(a04):
    """O fonte cita o NOME da constante e nunca o texto dela.

    A régua lê o próprio arquivo porque é o único jeito de pegar a segunda
    escrita: uma cópia literal da frase passaria em todos os casos acima e só
    apareceria no dia em que o dono mudasse uma palavra e as duas telas do mesmo
    produto passassem a contar o mesmo evento diferente.
    """
    fonte = pathlib.Path(a04.__file__).read_text(encoding="utf-8")
    assert "_AVISO_MESMO_DESENHO_NOS_QUATRO" in fonte, (
        "o pacote deixou de citar o dono do texto — é o `sinal` que o CSV da "
        "paridade cobra do lado HTML")
    assert "O mesmo desenho foi para os" not in fonte, (
        "a frase do dono foi DIGITADA neste lado — é a segunda escrita do "
        "mesmo texto, o defeito que a RADAR-01 mediu")


# ---------------------------------------------------------------------------
# 3. O AVISO PAROU DE SER ENGOLIDO — a mordida que importa
# ---------------------------------------------------------------------------
def test_a_comparacao_do_desfecho_e_surda_ao_aviso_por_construcao(a04, pac, dono):
    """O fato que fazia o aviso morrer: as duas frases são IGUAIS com N ≥ 2.

    Este caso não mede a cura — mede a CAUSA, e existe para que ela não se
    perca. O `_msg_do_desenho` cola o aviso na frase do corpo real E na do corpo
    feliz, porque as duas saem do mesmo método com a mesma `_Janela`. Um
    `if frase != feliz` nunca ia vê-lo.
    """
    janela = _janela_de_todos(a04, pac)
    bits = (False, True, False, True, False)
    descricao = dono.LightbarActionsMixin._descreve_player_leds(bits)

    def diz(corpo):
        return dono.LightbarActionsMixin._msg_do_desenho(
            janela, ok=True, motivo=None, corpo=corpo, descricao=descricao,
            feito="atualizado", fazer="atualizar")

    feliz = diz({"status": "ok", "aplicado_em": [UM], "guardado_em": []})
    real = diz({"status": "ok", "aplicado_em": [UM, DOIS], "guardado_em": []})
    aviso = dono._AVISO_MESMO_DESENHO_NOS_QUATRO.format(n=2)
    assert aviso in feliz and aviso in real, (
        "o dono parou de colar o aviso nas duas frases")
    assert feliz == real, (
        "as duas frases divergiram — se um dia divergirem, a comparação do "
        "`_cobrar_a_frase_do_desenho` passa a levantar e este arquivo tem de "
        "ser relido antes de a cura mudar")


def test_o_desfecho_devolve_a_frase_quando_ela_tem_aviso(monkeypatch, a04, pac,
                                                         dono):
    """A CURA: `_cobrar_a_frase_do_desenho` devolve a frase do dono, com o aviso.

    **A MORDIDA:** troque o corpo pelo de ontem — `if frase != feliz: raise` e
    nada mais — e a devolução volta a ser `None`. O caso acima prova que o
    `!=` cala; este prova que alguém mais fala.
    """
    _abrir_o_todos(monkeypatch, a04, pac)
    bits = (False, True, False, True, False)
    frase = a04._cobrar_a_frase_do_desenho(
        _ctx(pac), UM, bits,
        {"status": "ok", "aplicado_em": [UM, DOIS], "guardado_em": []})
    assert dono._AVISO_MESMO_DESENHO_NOS_QUATRO.format(n=2) in frase, (
        f"o desfecho voltou sem o aviso dos N: {frase!r}")


def test_sem_aviso_o_desfecho_continua_mudo(a04, pac):
    """N < 2 devolve `""` — o silêncio de antes, e a piscada responde."""
    frase = a04._cobrar_a_frase_do_desenho(
        _ctx(pac), UM, (False, False, True, False, False),
        {"status": "ok", "aplicado_em": [UM], "guardado_em": []})
    assert frase == "", (
        f"o desfecho de UM controle falou quando devia piscar: {frase!r}")


def test_o_desfecho_que_falhou_continua_levantando(monkeypatch, a04, pac):
    """A cura não engoliu a recusa: corpo sem destino nenhum ainda levanta.

    É a guarda contra a regressão mais provável desta mudança — trocar um
    `raise` por um `return` e transformar toda recusa em recibo verde.
    """
    _abrir_o_todos(monkeypatch, a04, pac)
    with pytest.raises(RuntimeError):
        a04._cobrar_a_frase_do_desenho(
            _ctx(pac), UM, (True,) * 5,
            {"status": "ok", "aplicado_em": [], "guardado_em": [UM]})


def test_se_o_dono_parar_de_colar_o_aviso_o_pacote_recusa(monkeypatch, a04, pac,
                                                          dono):
    """As duas metades andam juntas — ou ninguém anda.

    Com a conta dizendo N ≥ 2 e a frase do dono sem o aviso, calar poria um
    recibo comum no canal que existe para o aviso, e devolver a frase seria
    prometer um aviso que ela não tem. O pacote levanta, nomeando os dois lados.
    """
    _abrir_o_todos(monkeypatch, a04, pac)
    # O DONO PARA DE COLAR — e a conta continua dizendo dois. Não se troca a
    # CONSTANTE aqui: trocá-la mudaria o texto nos dois lados ao mesmo tempo (o
    # dono a lê do módulo e a sonda também), e as duas metades continuariam
    # concordando. Quem tem de deixar de colar é o método que compõe.
    monkeypatch.setattr(dono.LightbarActionsMixin, "_msg_do_desenho",
                        staticmethod(lambda *a, **k: "Desenho das luzes."))
    with pytest.raises(RuntimeError, match="2 controles"):
        a04._cobrar_a_frase_do_desenho(
            _ctx(pac), UM, (True,) * 5,
            {"status": "ok", "aplicado_em": [UM, DOIS], "guardado_em": []})


# ---------------------------------------------------------------------------
# 4. OS QUATRO GESTOS PÕEM A FRASE NO CANAL VERDE — todos, não um
# ---------------------------------------------------------------------------
def _os_quatro(a04, pac):
    """Os quatro caminhos de escrita de desenho desta aba, com o clique de cada.

    **SÃO QUATRO E NÃO UM**, e a razão é a regra desta casa de 05/09: *quando a
    cura conhece a causa, ela cobre TODOS os chamadores*. Cobrir um deixa a
    próxima pessoa remedindo o mesmo defeito no gesto vizinho.
    """
    clique = {"controle": "p1", "uniq": UM}
    return [
        ("luzes", a04.luzes, {**clique, "lampada": "1"}),
        ("desenho-de", a04.desenho_de, {**clique, "desenho": "3"}),
        ("desenho-de/todas", a04.desenho_de, {**clique, "desenho": a04.TODAS}),
        ("reenviar-desenho", a04.reenviar_desenho, dict(clique)),
        ("player", a04.player, {**clique, "player": "2"}),
    ]


@pytest.mark.parametrize("indice", range(5))
def test_o_gesto_poe_a_frase_do_dono_no_canal_de_recado(monkeypatch, a04, pac,
                                                        dono, indice):
    """O clique que pegou em N controles volta com `{"recado": …}`.

    É a entrega da sprint em uma linha: *o pacote lê a conta e põe a frase do
    dono no canal de recado verde*. O canal é o do piloto
    (`hefesto_vivo._deu_certo_dizendo` → `_depositar(..., "sucesso")`), e a
    chave é `recado` — ver `test_o_canal_e_o_verde_de_seis_segundos`.

    **A MORDIDA:** tire o `_o_recado(...)` de qualquer um dos cinco e só aquele
    caso cai. Foi para isso que ele é `parametrize` e não um `for`.
    """
    _semear()
    _abrir_o_todos(monkeypatch, a04, pac)
    nome, gesto, clique = _os_quatro(a04, pac)[indice]
    resposta = gesto(_ctx(pac), clique, PonteDeMentira())
    assert isinstance(resposta, dict), (
        f"o gesto {nome} não devolveu recado nenhum: {resposta!r}")
    assert dono._AVISO_MESMO_DESENHO_NOS_QUATRO.format(n=2) in str(
        resposta.get("recado") or ""), (
        f"o recado do gesto {nome} não carrega o aviso dos N: {resposta!r}")


@pytest.mark.parametrize("indice", range(5))
def test_sem_o_aviso_o_gesto_continua_calado(a04, pac, indice):
    """Um controle só: nada de recado, e a piscada do piloto responde.

    Sem este caso a cura poderia pôr uma frase de seis segundos no cartão a cada
    clique de lâmpada — que é o contrário da `03-Q4` dela (*"quando o gesto só
    repete o que ela acabou de fazer, a tela pisca"*).
    """
    _semear()
    nome, gesto, clique = _os_quatro(a04, pac)[indice]
    assert gesto(_ctx(pac), clique, PonteDeMentira()) is None, (
        f"o gesto {nome} falou num clique que pegou em um controle só")


def test_o_ramo_nenhuma_continua_com_o_recado_dele(a04, pac):
    """"Todas apagadas" não perdeu a frase que já tinha.

    O `desenho-de` tinha UM recado antes desta sprint — o do override que saiu —
    e a plumbing nova passa pelo mesmo `return`. Uma cura que trocasse um recado
    por outro seria uma regressão de tela invisível para todo o resto.
    """
    _semear()
    resposta = a04.desenho_de(_ctx(pac),
                              {"controle": "p1", "uniq": UM,
                               "desenho": a04.NENHUMA},
                              PonteDeMentira())
    assert resposta == {"recado": a04._RECADO_DO_DESENHO_AUTOMATICO}


# ---------------------------------------------------------------------------
# 5. O CANAL É O VERDE DE SEIS SEGUNDOS
# ---------------------------------------------------------------------------
def test_o_canal_e_o_verde_de_seis_segundos(a04, pac):
    """A chave e o relógio, os dois pelo dono — a sprint pede os dois.

    `recado` é a chave que o piloto colhe e RETIRA da carga antes da pintura
    (ela não é endereço de campo nenhum), e o relógio do sucesso é
    `SEGUNDOS_DO_RECADO_DE_SUCESSO`. Digitar 6,0 aqui seria a segunda cópia da
    decisão dela; o que a régua exige é que a chave devolvida seja a que aquele
    canal lê.
    """
    from hefesto_dualsense4unix.interface import hefesto_vivo as hv

    assert a04._o_recado("uma frase") == {"recado": "uma frase"}
    assert a04._o_recado("") is None
    assert "recado" in hv.CHAVES_QUE_O_VIVO_RECUSA, (
        "a chave do recado deixou de ser podada da carga de pintura")
    assert hv.SEGUNDOS_DO_RECADO_DE_SUCESSO == 6.0, (
        "o relógio do recado verde mudou — a sprint pede os 6 s, e o número "
        "é dela (D-01, 04/09/2026)")

"""A régua do defeito D3: nenhum endereço da aba Gatilhos fica sem quem escreva.

O DEFEITO, medido em 02/09/2026 com a bancada (dois controles, perfil
`meu_perfil`, `triggers.left = {mode: 'Off', params: []}` e o mesmo à direita) e
fotografado com o piloto oculto:

    Modo:          Desligado          <- pintado, e certo
    Efeito pronto: — Nenhum —         <- pintado, e certo
    Ajustes:       Força          7   <- MOCKUP
                   Frequência     4   <- MOCKUP
                   Início do curso 25 <- MOCKUP
                   Fim do curso  230  <- MOCKUP

A tela contradizia a si mesma em três linhas de distância — e o pacote não
estava "sem ligar os ajustes": ele pintava **as casas que o modo tem**, e `Off`
tem zero. O laço não rodava nenhuma volta e as quatro barras que o desenho
deixou na página nunca eram endereçadas.

**A REGRA QUE ESTA RÉGUA CRAVA:** *um endereço que a página tem e o pacote não
escreve continua mostrando o desenho.* Não é o pacote que decide quantas casas
existem — é a página, e é dela que a contagem sai.

O QUE ELA MORDE, e os quatro já aconteceram:

* voltar a pintar só `len(spec.params)` casas   → `test_o_modo_sem_ajuste_apaga_as_casas`
* deixar UM `data-campo` da página sem escritor → `test_nenhum_endereco_da_pagina_fica_sem_dono`
* a barra de preenchimento pintar por texto     → `test_a_barra_diz_como_quer_ser_pintada`
* a coluna vazia aceitar clique sem dizer nada  → `test_o_lugar_vazio_recusa_dizendo_que_esta_vazio`
* a coluna VAZIA ficar com o efeito de quem saiu → `test_o_lugar_vazio_recebe_desligado_e_nenhum`
* a recusa do daemon chegar CRUA na tela do usuário   →
  `test_a_recusa_do_daemon_chega_na_lingua_da_tela`
"""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
sys.path.insert(0, str(INTERFACE))

PAGINA = "03-gatilhos.html"

#: `pacotes.topo()` — cobrá-los do pacote da aba faria a régua reprovar o
#: no instante em que o rodapé ganhou endereço: `pacotes.topo()` passou a emitir
def _do_cabecalho() -> set[str]:
    import pacotes  # noqa: F401  (registra os dez)
    from pacotes import Contexto, topo

    ctx = Contexto(state={}, mesa=[], conectados=[], estados={})
    return set(topo(ctx)) | {"conta", "conta-b", "perfil", "fita-chip"}


@pytest.fixture(scope="module")
def a03():
    import pacotes  # noqa: F401  (registra os dez)
    from pacotes import a03_gatilhos

    return a03_gatilhos


@pytest.fixture(scope="module")
def publicada() -> str:
    from hefesto_dualsense4unix.interface import onde

    caminho = onde.pagina(PAGINA, publicado=True)
    assert caminho.exists(), f"{PAGINA} sumiu do produto — o `WebView` não teria o que abrir"
    return caminho.read_text(encoding="utf-8")


FALSO = {
    "uniq": "aa:bb:cc:00:00:01", "player": 1, "transport": "usb", "is_primary": True,
    "inputs": {"l2_raw": 0, "r2_raw": 0},
}
MESA = [{"pref": "p1", "jogador": 1, "uniq": "aa:bb:cc:00:00:01",
         "nome": "Régua", "via": "USB", "cor": "starlight-blue",
         "mascara": "DualSense", "alvo": True}]


def _coluna(a03, modo_esq: str = "Off", modo_dir: str = "Off") -> dict:
    """A coluna que o pacote devolve para um perfil com aqueles dois modos."""
    from pacotes import Contexto, perfil

    guardado = perfil.ativo
    perfil.ativo = lambda _nome: {  # type: ignore[assignment]
        "triggers": {"left": {"mode": modo_esq, "params": []},
                     "right": {"mode": modo_dir, "params": []}},
        "controllers": {},
    }
    try:
        ctx = Contexto(state={"active_profile": "régua"}, mesa=MESA,
                       conectados=[FALSO], estados={})
        r = a03.pacote(ctx)
    finally:
        perfil.ativo = guardado  # type: ignore[assignment]
    return next(iter(r["colunas"].values()))


def _pacote_com(a03, modo_esq="Off", modo_dir="Off", ps_esq=None, ps_dir=None):
    """O pacote INTEIRO para um perfil com aqueles dois modos."""
    from pacotes import Contexto, perfil

    guardado = perfil.ativo
    perfil.ativo = lambda _nome: {  # type: ignore[assignment]
        "triggers": {"left": {"mode": modo_esq, "params": list(ps_esq or [])},
                     "right": {"mode": modo_dir, "params": list(ps_dir or [])}},
        "controllers": {},
    }
    try:
        ctx = Contexto(state={"active_profile": "régua"}, mesa=MESA,
                       conectados=[FALSO], estados={})
        return a03.pacote(ctx)
    finally:
        perfil.ativo = guardado  # type: ignore[assignment]


def _bloco(a03, r, pref, sigla):
    """O HTML da caixa de ajustes daquela coluna, do `blocos` que o pacote devolve."""
    chave = f'[data-controle="{pref}"] .ajustes.{sigla}'
    assert chave in r["blocos"], (
        f"o pacote não emitiu a caixa de ajustes de {pref}·{sigla}. Sem ela a "
        f"coluna fica com as barras que o gerador desenhou — é o defeito D3, e "
        f"o que saiu foi: {sorted(r['blocos'])}")
    return str(r["blocos"][chave])


def test_a_cobertura_conta_o_que_a_pagina_recebe(a03, publicada):
    """A nota da aba é o que PINTA, não o que o dicionário tem."""
    from pacotes import Contexto, perfil

    guardado = perfil.ativo
    perfil.ativo = lambda _nome: {"triggers": {}, "controllers": {}}  # type: ignore[assignment]
    try:
        r = a03.pacote(Contexto(state={"active_profile": "régua"}, mesa=MESA,
                                conectados=[FALSO], estados={}))
    finally:
        perfil.ativo = guardado  # type: ignore[assignment]

    na_pagina = set(re.findall(r'data-campo="([^"]+)"', publicada))
    devia = sum(1 for col in r["colunas"].values() for k in col if k in na_pagina)
    sobra = sum(1 for col in r["colunas"].values() for k in col if k not in na_pagina)
    assert r["cobertura"]["pintados"] == devia, (
        f"a cobertura diz {r['cobertura']['pintados']} e a página só tem "
        f"endereço para {devia}. Contar o que não pousa é a aba se dando nota.")
    assert r["cobertura"]["sem_endereco"] == sobra, (
        "o que sai e não tem onde pousar tem de estar DITO, não escondido")


def test_o_lugar_vazio_recusa_dizendo_que_esta_vazio(a03):
    """Clicar numa coluna sem controle recusa NOMEANDO o lugar.

    Os dois casos chegavam ao gesto idênticos — o clique sem controle e o
    clique numa coluna vazia — e saíam com a mesma frase, que culpava o
    instrumento. A página publicada deixa os campos de P3 e P4 abertos com
    `data-conectado="nao"` ao lado; a trava de forma foi para a bancada, e esta
    é a de fundo.
    """
    with pytest.raises(RuntimeError) as vazio:
        a03._exigir_controle({"controle": "p3"}, "modo")
    assert "P3" in str(vazio.value), (
        f"a recusa não nomeou o lugar: {vazio.value}. Quem clicou precisa saber "
        f"que a coluna está vazia, não que o clique foi malfeito.")

    with pytest.raises(ValueError) as mudo:
        a03._exigir_controle({}, "modo")
    assert "não disse em qual controle" in str(mudo.value), (
        "um clique que não traz controle nenhum é `ValueError` — clique "
        "inválido —, e não `RuntimeError`, que é o produto recusando")


class _PonteDeMentira:
    """Um dublê que responde a qualquer nome e guarda o que foi chamado."""

    def __init__(self) -> None:
        self.chamadas: list[str] = []

    def __getattr__(self, nome: str):
        def registrar(*args, **kwargs):
            self.chamadas.append(nome)
            return True
        return registrar


@pytest.mark.parametrize("nome_do_gesto", ["modo", "imersao"])
def test_o_lugar_vazio_nao_alcanca_a_ponte(a03, nome_do_gesto):
    """Os dois gestos de escolha da coluna recusam antes de falar com o daemon."""
    from pacotes import Contexto, gesto_da_pagina

    fn = gesto_da_pagina(PAGINA, nome_do_gesto)
    assert fn is not None, f"o gesto {nome_do_gesto!r} perdeu o dono"
    ponte = _PonteDeMentira()
    ctx = Contexto(state={"active_profile": "régua"}, mesa=MESA,
                   conectados=[FALSO], estados={})
    clique = {"controle": "p4", "lado": "e", "modo": "Rigid", "valor": "rajada-que-sobe-sozinha",
              "forma": {"modo-chave-e": "Machine"}}
    with pytest.raises(RuntimeError) as recusa:
        fn(ctx, clique, ponte)
    assert "P4" in str(recusa.value)
    assert ponte.chamadas == [], (
        f"o gesto {nome_do_gesto!r} falou com o daemon para um lugar vazio: "
        f"{ponte.chamadas}. Sem `uniq`, `trigger.set` vai em broadcast e zera "
        f"o gatilho dos quatro — é o ABAS-06 de volta.")


MESA_DE_DOIS = [*MESA, {"pref": "p2", "jogador": 2, "uniq": "aa:bb:cc:00:00:02",
                        "nome": "Régua", "via": "BT", "cor": "cosmic-red",
                        "mascara": "DualSense", "alvo": False}]
FALSO_2 = dict(FALSO, uniq="aa:bb:cc:00:00:02", player=2, transport="bt",
               is_primary=False)


def _com_a_mesa(a03, mesa, conectados, modo: str = "Rigid") -> dict:
    """O pacote inteiro para aquela mesa, com o perfil injetado pela porta."""
    from pacotes import Contexto, perfil

    guardado = perfil.ativo
    perfil.ativo = lambda _nome: {  # type: ignore[assignment]
        "triggers": {"left": {"mode": modo, "params": []},
                     "right": {"mode": modo, "params": []}},
        "controllers": {}}
    try:
        return a03.pacote(Contexto(state={"active_profile": "régua"}, mesa=mesa,
                                   conectados=conectados, estados={}))
    finally:
        perfil.ativo = guardado  # type: ignore[assignment]


def test_o_lugar_vazio_recebe_desligado_e_nenhum(a03, publicada):
    """A coluna sem aparelho é ESCRITA, e com valor que o `<select>` aceita."""
    r = _com_a_mesa(a03, MESA_DE_DOIS, [FALSO, FALSO_2])
    vazios = sorted(a03._lugares_que_o_desenho_da_por_vazios())
    assert vazios, "a página não marca lugar vazio nenhum — a régua ficou cega"
    for pref in vazios:
        col = r["colunas"].get(pref)
        assert col, (
            f'a coluna {pref} não foi escrita. A página a marca '
            f'`data-conectado="nao"`, e o que o pacote não escreve continua '
            f"mostrando o desenho — é o ENDEREÇO MORTO da régua do mockup.")
        assert not [k for k in col if k.startswith("aj-")], (
            f"{pref} recebeu {sorted(k for k in col if k.startswith('aj-'))}. A "
            f"coluna vazia do desenho não tem barra de ajuste nenhuma — ela traz "
            f"'Este modo não tem o que ajustar.' —, e emitir `aj-*` ali é se dar "
            f"nota por escrever no vazio.")
        assert {"modo-chave-e", "modo-chave-d", "imersao-e", "imersao-d",
                a03.CAMPO_DO_CHIP, a03.CAMPO_DO_PLASTICO} <= set(col), (
            f"{pref} recebeu {sorted(col)} e falta um dos seis que a coluna "
            f"vazia precisa: as quatro escolhas e os dois do cabeçalho.")
        escolhas = {k: v for k, v in col.items()
                    if k not in (a03.CAMPO_DO_CHIP, a03.CAMPO_DO_PLASTICO)
                    and not k.startswith(a03.PREFIXO_DA_DICA_DO_MODO)
                    and not k.startswith(a03.PREFIXO_DA_DICA_DA_IMERSAO)}
        for campo, valor in escolhas.items():
            oferece = re.search(
                rf'data-campo="{campo}"(.*?)</select>', publicada, re.S)
            assert oferece, f"{pref}·{campo} não é um `<select>` da página"
            na_tela = valor if valor != "" else a03.TRAVESSAO
            assert f'value="{na_tela}"' in oferece.group(1), (
                f"{pref}·{campo} = {valor!r} (na tela: {na_tela!r}), e o "
                f"`<select>` da página não oferece essa opção. `escrever()` do "
                f"piloto devolve 0 sem escrever, e a coluna fica com o efeito de "
                f"quem saiu dali.")


def test_o_lugar_vazio_nao_rouba_a_marca_do_piloto(a03):
    """O pacote NÃO escreve numa coluna que o desenho dá por conectada.

    POR QUE ISTO É UMA RÉGUA E NÃO UM DETALHE: o piloto deduz "lugar vazio" de
    "coluna que ninguém emitiu" (`hefesto_vivo.py:851-861`) e é essa dedução
    que põe o `data-conectado="nao"` — o atributo de que pende o
    `pointer-events:none` do lugar vazio (`03-gatilhos.html:899`). Emitir a
    coluna do P2 com um controle só na mesa tiraria o P2 daquela conta, e a
    trava do clique cairia CALADA.

    O acoplamento é do piloto; enquanto ele existir, esta aba escreve só onde a
    marca já está no arquivo.
    """
    r = _com_a_mesa(a03, MESA, [FALSO])
    assert "p2" not in r["colunas"], (
        'o pacote emitiu a coluna do P2 com um controle só na mesa. O piloto '
        'deixaria de marcá-la `data-conectado="nao"` e o lugar vazio voltaria '
        "a aceitar clique.")
    assert "p3" in r["colunas"] and "p4" in r["colunas"]


def test_o_lugar_vazio_apaga_o_efeito_de_quem_saiu(a03):
    """Com o controle na mesa, `Rigid`; sem ele, o travessão. É o D4 inteiro."""
    mesa_de_tres = [
        *MESA_DE_DOIS,
        {"pref": "p3", "jogador": 3, "uniq": "aa:bb:cc:00:00:03",
         "nome": "Régua", "via": "BT", "cor": "cosmic-red",
         "mascara": "DualSense", "alvo": False}]
    tres = [FALSO, FALSO_2, dict(FALSO, uniq="aa:bb:cc:00:00:03", player=3)]

    com_ele = _com_a_mesa(a03, mesa_de_tres, tres)["colunas"]["aa:bb:cc:00:00:03"]
    assert com_ele["modo-chave-e"] == "Resistance"

    sem_ele = _com_a_mesa(a03, MESA_DE_DOIS, [FALSO, FALSO_2])["colunas"]["p3"]
    assert sem_ele["modo-chave-e"] != "Rigid", (
        "o P3 esvaziou e o campo continuou dizendo `Rigid`. É a tela afirmando "
        "um efeito num lugar onde não há aparelho.")
    assert sem_ele["modo-chave-e"] in ("", "—"), (
        f"o lugar vazio devolveu {sem_ele['modo-chave-e']!r}. Ele mostra o "
        "travessão desde a decisão dela de 02/09")


# `app/actions/triggers_actions.humanizar_erro_gatilho` é a HARM-19, escrita e


class _PonteQueRecusa:
    """Uma ponte que diz não com a frase CRUA do daemon, e conta as chamadas."""

    def __init__(self, motivo: str) -> None:
        self.motivo = motivo
        self.chamadas: list[str] = []

    def __getattr__(self, nome: str):
        def recusar(*_args, **_kwargs):
            self.chamadas.append(nome)
            return (False, self.motivo, {})

        return recusar


@pytest.mark.parametrize(
    ("gesto_", "clique", "cru", "esperado"),
    [
        ("modo", {"lado": "d", "modo": "SemiAutoGun"},  # (noqa-acento) id
         "end (3) deve ser > start (5)",
         "Fim (3) precisa ser maior que Início (5)"),
    ],
)
def test_a_recusa_do_daemon_chega_na_lingua_da_tela(a03, gesto_, clique, cru, esperado):
    """A frase que vai para a tela do usuário é a humanizada, não a do `core`."""
    from pacotes import Contexto, gesto_da_pagina

    fn = gesto_da_pagina(PAGINA, gesto_)
    assert fn is not None, f"o gesto {gesto_!r} sumiu da aba"
    ponte = _PonteQueRecusa(cru)
    ctx = Contexto(state={"active_profile": "régua"}, mesa=MESA,
                   conectados=[FALSO], estados={})
    with pytest.raises(RuntimeError) as recusa:
        fn(ctx, dict(clique, uniq=FALSO["uniq"]), ponte)
    assert str(recusa.value) == esperado, (
        f"a tela receberia {str(recusa.value)!r}. A tradução tem dono desde a "
        f"HARM-19 — `triggers_actions.humanizar_erro_gatilho` — e ela usa os "
        f"MESMOS rótulos que o `<select>` desta aba mostra.")
    assert ponte.chamadas, "o gesto nem chegou ao daemon"


def test_a_recusa_que_o_tradutor_nao_conhece_volta_inteira(a03):
    """Sem tradução, o motivo CRU vai para a tela. Calar seria pior.

    É o contrato do próprio `humanizar_erro_gatilho`, que devolve `None` para
    todo formato que não conhece: *"aí o chamador mostra o texto cru do daemon,
    que ainda diz mais que 'daemon offline?'"*.
    """
    from pacotes import Contexto, gesto_da_pagina

    fn = gesto_da_pagina(PAGINA, "modo")
    ponte = _PonteQueRecusa("o hidraw sumiu no meio do caminho")
    ctx = Contexto(state={"active_profile": "régua"}, mesa=MESA,
                   conectados=[FALSO], estados={})
    with pytest.raises(RuntimeError) as recusa:
        fn(ctx, {"lado": "e", "modo": "Rigid", "uniq": FALSO["uniq"]}, ponte)
    assert str(recusa.value) == "o hidraw sumiu no meio do caminho"


def test_o_travessao_espera_a_publicacao_dela(a03):
    """O pacote NÃO manda travessão numa página que não o oferece."""
    guardado = a03._OFERECE
    try:
        a03._OFERECE = {"modo": frozenset({"Off"}), "imersao": frozenset({""})}
        assert a03._sem_nada("modo", "Off") == "Off"
        assert a03._sem_nada("imersao", "") == ""
        a03._OFERECE = {"modo": frozenset({"Off", a03.TRAVESSAO}),
                        "imersao": frozenset({"", a03.TRAVESSAO})}
        assert a03._sem_nada("modo", "Off") == a03.VAZIO, (
            "a página já oferece o travessão e o pacote continua mandando `Off` "
            "— o lugar vazio segue dizendo a mesma palavra que um controle "
            "conectado diria")
        assert a03._sem_nada("imersao", "") == a03.VAZIO
    finally:
        a03._OFERECE = guardado


def test_o_travessao_esta_no_desenho_de_hoje(a03):
    """A BANCADA oferece `—` nos dois campos de escolha, e ele é `disabled`."""
    from hefesto_dualsense4unix.interface import onde

    bancada = onde.pagina(PAGINA).read_text(encoding="utf-8")
    miolo = bancada.split('<div class="miolo">', 1)[-1].split('<div class="nota">', 1)[0]
    quantos = len(re.findall(
        rf'<option value="{a03.TRAVESSAO}"[^>]*\bdisabled\b', miolo))
    # o «Partir de» da área de criar (`data-linha`) não pinta lugar nenhum: não leva `—`
    campos = len(re.findall(r"<select(?![^>]*data-linha)", miolo))
    assert quantos == campos, (
        f"{quantos} campos oferecem `—` e há {campos} campos de "
        f"escolha na bancada. O que não oferece não pode receber o vazio.")


def test_a_regua_do_css_nao_le_o_proprio_comentario(a03):
    """Uma régua que procura a declaração no documento INTEIRO acha a prosa."""
    doc = ("/* A CURA É `grid-template-rows:subgrid`: as trilhas passam a ser "
           "da GRADE */\n  .duas-colunas > div{display:grid;grid-row:1/-1}")
    assert "grid-template-rows:subgrid" in doc, "o caso de teste perdeu a isca"
    assert "grid-template-rows:subgrid" not in a03.sem_comentarios_de_css(doc), (
        "o comentário sobreviveu à limpeza — a régua do gerador volta a medir "
        "a própria prosa em vez da página")
    vivo = "  .duas-colunas > div{display:grid;grid-template-rows:subgrid}"
    assert "grid-template-rows:subgrid" in a03.sem_comentarios_de_css(vivo), (
        "a limpeza comeu a DECLARAÇÃO junto com o comentário")

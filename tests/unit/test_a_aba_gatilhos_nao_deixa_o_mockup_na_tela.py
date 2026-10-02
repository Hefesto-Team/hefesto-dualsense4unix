"""A régua do defeito D3: nenhum endereço da aba Gatilhos fica sem quem escreva.

O DEFEITO, medido em 02/09/2026 com a mesa dela (dois controles, perfil
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
* a recusa do daemon chegar CRUA na tela dela   → `test_a_recusa_do_daemon_chega_na_lingua_da_tela`
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


def test_o_modo_sem_ajuste_nao_deixa_barra_nenhuma(a03):
    """`Off` não tem ajuste — logo a caixa NÃO pode ter barra nenhuma."""
    r = _pacote_com(a03)
    for sigla in ("e", "d"):
        html = _bloco(a03, r, "p1", sigla)
        assert 'class="barra"' not in html, (
            f"p1·{sigla}: o modo `Off` não tem ajuste e a caixa veio com barra. "
            f"Uma barra aqui é a tela dizendo `Força 7` debaixo de um campo que "
            f"diz `Desligado`.")
        assert a03.SEM_AJUSTE in html, (
            f"p1·{sigla}: a caixa vazia perdeu a frase que o desenho já tinha — "
            f"sobra um buraco sem explicação")


def test_o_modo_com_ajuste_traz_os_dele_e_so_os_dele(a03):
    """A cura não pode ter apagado o caso que já funcionava."""
    r = _pacote_com(a03, modo_esq="Rigid", ps_esq=[0, 180])
    html = _bloco(a03, r, "p1", "e")
    quantas = html.count('class="barra"')
    assert quantas == 2, f"o `Rigid` tem 2 parâmetros e a caixa veio com {quantas}"
    assert "Posição" in html and "Força" in html
    assert 'data-campo="aj-val-e-1"' in html and ">180<" in html, (
        "a Força do L2 não chegou com o valor do disco (180) — o pacote está "
        "lendo a tabela de padrões em vez do perfil dela")


def test_o_modo_grande_nao_esconde_ajuste(a03):
    """A DECISÃO 2 DELA numa asserção: *"a tela nunca esconde o que está
    gravado no disco"*.

    Cinco dos 19 modos pedem mais barras do que a página reservava —
    `Galloping` 5, `Machine` 6, `Custom` 8, `MultiPositionFeedback` 10 e
    `MultiPositionVibration` 11 — e a página crava 4 no L2 e 2 no R2. Até
    02/09 a caixa mostrava as quatro primeiras e CALAVA sobre o resto.

    O número vem do PRODUTO (`trigger_specs.get_spec(...).params`), nunca
    digitado aqui: no dia em que o produto mudar um modo, a régua acompanha.
    """
    from hefesto_dualsense4unix.app.actions import trigger_specs

    casas = a03._casas_cravadas()
    maiores = 0
    for nome in ("Galloping", "Machine", "Custom", "MultiPositionFeedback",
                 "MultiPositionVibration"):
        esperado = len(trigger_specs.get_spec(nome).params)
        html = _bloco(a03, _pacote_com(a03, modo_esq=nome), "p1", "e")
        quantas = html.count('class="barra"')
        assert quantas == esperado, (
            f"o modo {nome} tem {esperado} ajustes e a caixa trouxe {quantas}. "
            f"Esconder o que está no disco é o que a decisão dela proíbe.")
        if esperado > casas["e"]:
            maiores += 1
            assert quantas > casas["e"], (
                f"{nome}: a caixa parou no que a PÁGINA reserva ({casas['e']}) "
                f"em vez do que o MODO tem ({esperado})")
    assert maiores >= 3, (
        f"só {maiores} dos cinco modos passam do que a página reserva — se este "
        f"número foi a zero, a régua deixou de medir o caso que ela existe para "
        f"medir")


def test_a_caixa_do_lugar_sem_aparelho_tambem_e_trocada(a03):
    """TODA coluna sem controle recebe a caixa — inclusive a que o desenho dá
    por CONECTADA.

    O P2 é o caso, e é o que se perde sem esta régua: a página nasce com o P1 e
    o P2 conectados. Com UM controle na mesa, o P2 não entra em `colunas`
    (emiti-lo tiraria o `data-conectado="nao"` que o piloto escreve) — e, se o
    bloco também não chegasse lá, a coluna ficaria com as barras do mockup. O
    bloco pousa por SELETOR, então alcança o P2 sem custar a marca.
    """
    r = _com_a_mesa(a03, MESA, [FALSO], modo="Rigid")
    assert "p2" not in r["colunas"], "esta régua supõe que o P2 fica fora de `colunas`"
    for sigla in ("e", "d"):
        html = _bloco(a03, r, "p2", sigla)
        assert 'class="barra"' not in html and a03.SEM_AJUSTE in html, (
            f"a caixa do P2·{sigla} não foi apagada — a coluna de um lugar sem "
            f"aparelho continua mostrando os ajustes que o gerador desenhou")


def test_nenhum_endereco_da_pagina_fica_sem_dono(a03, publicada):
    """Todo `data-campo` da página tem quem o escreva. É a catraca da aba."""
    r = _pacote_com(a03, modo_esq="Rigid", modo_dir="Rigid")
    col = next(iter(r["colunas"].values()))
    da_caixa = set()
    for m in re.finditer(r'<div class="ajustes ([ed])">(.*?)\n {10}</div>',
                         publicada, re.S):
        da_caixa |= set(re.findall(r'data-campo="([^"]+)"', m.group(2)))
    assert da_caixa, (
        "a página publicada não tem endereço nenhum dentro de uma caixa de "
        "ajustes — a régua ficaria cega justamente onde o defeito D3 morava")
    for pref in sorted(a03._todos_os_lugares_da_pagina()):
        for sigla in ("e", "d"):
            assert f'[data-controle="{pref}"] .ajustes.{sigla}' in r["blocos"], (
                f"a caixa de {pref}·{sigla} não tem bloco. Os endereços dela "
                f"ficam com o que o gerador desenhou, e ninguém acusa.")

    na_pagina = set(re.findall(r'data-campo="([^"]+)"', publicada)) - _do_cabecalho()
    sem_dono = sorted(na_pagina - set(col) - da_caixa)
    assert not sem_dono, (
        f"{len(sem_dono)} endereço(s) da página que ninguém escreve: {sem_dono}. "
        f"Cada um continua mostrando o valor que o gerador desenhou.")

    dos_blocos = set()
    for html in r["blocos"].values():
        dos_blocos |= set(re.findall(r'data-campo="([^"]+)"', str(html)))
    assert dos_blocos, (
        "o bloco da caixa de ajustes não trouxe endereço nenhum — o 'Guardar "
        "esse efeito' recolhe a coluna por endereço e passaria a gravar os "
        "padrões do modo por cima do que ela salvou")


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


def test_a_barra_diz_como_quer_ser_pintada(a03):
    """A barra que o PRODUTO monta declara `largura`, e traz a largura dentro.

    Duas coisas, e a segunda é a de hoje. `data-hef-alvo="largura"` é como a
    régua do mockup sabe LER a barra: sem ele o valor cravado passa a ser o
    texto (vazio) e ela deixa de enxergar a largura. E o `style="width:…%"` já
    vem no HTML do bloco — a caixa é trocada inteira, então a largura chega com
    ela em vez de depender de uma segunda pintura.

    ARRANQUE o `style="width:{a["pct"]}%"` de `html_dos_ajustes` e a barra
    volta à largura do desenho com o número certo ao lado, que é a forma exata
    do defeito que esta aba passou o dia a fechar.
    """
    r = _pacote_com(a03, modo_esq="Rigid", ps_esq=[0, 180])
    html = _bloco(a03, r, "p1", "e")
    barras = re.findall(r'<span class="cheio"[^>]*>', html)
    assert len(barras) == 2, f"o `Rigid` tem duas barras e o bloco trouxe {barras}"
    mudas = [b for b in barras if 'data-hef-alvo="largura"' not in b]
    assert not mudas, (
        f"{len(mudas)} de {len(barras)} barras não dizem que pintam por largura: "
        f"{mudas}")
    sem_largura = [b for b in barras if "width:" not in b]
    assert not sem_largura, (
        f"{len(sem_largura)} barras sem largura no próprio HTML — a caixa é "
        f"trocada inteira e ninguém pinta dentro dela, então a largura que não "
        f"vier aqui fica a do mockup: {sem_largura}")
    assert "width:71%" in html, (
        "a Força do L2 vale 180 numa faixa de 0 a 255, que é 71% — a barra veio "
        "com outra conta, ou com a do desenho")


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


@pytest.mark.parametrize("nome_do_gesto", ["modo", "pronto", "guardar"])
def test_o_lugar_vazio_nao_alcanca_a_ponte(a03, nome_do_gesto):
    """Os TRÊS gestos da aba recusam antes de falar com o daemon."""
    from pacotes import Contexto, gesto_da_pagina

    fn = gesto_da_pagina(PAGINA, nome_do_gesto)
    assert fn is not None, f"o gesto {nome_do_gesto!r} perdeu o dono"
    ponte = _PonteDeMentira()
    ctx = Contexto(state={"active_profile": "régua"}, mesa=MESA,
                   conectados=[FALSO], estados={})
    clique = {"controle": "p4", "lado": "e", "modo": "Rigid", "v": "stop_hard",
              "forma": {"modo-chave-e": "Rigid"}}
    with pytest.raises(RuntimeError) as recusa:
        fn(ctx, clique, ponte)
    assert "P4" in str(recusa.value)
    assert ponte.chamadas == [], (
        f"o gesto {nome_do_gesto!r} falou com o daemon para um lugar vazio: "
        f"{ponte.chamadas}. Sem `uniq`, `trigger.set` vai em broadcast e zera "
        f"o gatilho dos quatro — é o ABAS-06 de volta.")


def test_a_contagem_de_casas_sai_da_pagina_e_nao_do_codigo(a03, publicada):
    """As casas CRAVADAS são as do desenho, lidas dele. Nenhum número digitado."""
    casas = a03._casas_cravadas()
    for sigla, quantas in casas.items():
        indices = {int(i) for i in re.findall(
            rf'data-campo="aj-nome-{sigla}-(\d+)"', publicada)}
        assert quantas == (max(indices) + 1 if indices else 0), (
            f"o lado {sigla!r}: o pacote conta {quantas} casas e a página tem "
            f"{sorted(indices)}.")
    r = _pacote_com(a03)
    assert r["cobertura"]["casas_cravadas"] == sum(casas.values()), (
        "a cobertura diz um número de casas cravadas e a leitura da página diz "
        "outro — o diagnóstico da publicação pendente deixou de ser lido")


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
        assert {"modo-chave-e", "modo-chave-d", "pronto-e", "pronto-d",
                a03.CAMPO_DO_CHIP, a03.CAMPO_DO_PLASTICO} <= set(col), (
            f"{pref} recebeu {sorted(col)} e falta um dos seis que a coluna "
            f"vazia precisa: as quatro escolhas e os dois do cabeçalho.")
        escolhas = {k: v for k, v in col.items()
                    if k not in (a03.CAMPO_DO_CHIP, a03.CAMPO_DO_PLASTICO)
                    and not k.startswith(a03.PREFIXO_DA_DICA_DO_MODO)
                    and not k.startswith(a03.PREFIXO_DA_DICA_DO_PRONTO)}
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
    assert com_ele["modo-chave-e"] == "Rigid"

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
        ("pronto", {"lado": "e", "v": "stop_hard"},  # (noqa-acento) id
         "pos_4 fora do range 0-8: 12",
         "Posição 4 precisa estar entre 0 e 8 (você pediu 12)"),
    ],
)
def test_a_recusa_do_daemon_chega_na_lingua_da_tela(a03, gesto_, clique, cru, esperado):
    """A frase que vai para a tela dela é a humanizada, não a do `core`."""
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
        a03._OFERECE = {"modo": frozenset({"Off"}), "pronto": frozenset({"custom"})}
        assert a03._sem_nada("modo", "Off") == "Off"
        assert a03._sem_nada("pronto", "custom") == "custom"
        a03._OFERECE = {"modo": frozenset({"Off", a03.TRAVESSAO}),
                        "pronto": frozenset({"custom", a03.TRAVESSAO})}
        assert a03._sem_nada("modo", "Off") == a03.VAZIO, (
            "a página já oferece o travessão e o pacote continua mandando `Off` "
            "— o lugar vazio segue dizendo a mesma palavra que um controle "
            "conectado diria")
        assert a03._sem_nada("pronto", "custom") == a03.VAZIO
    finally:
        a03._OFERECE = guardado


def test_o_travessao_esta_no_desenho_de_hoje(a03):
    """A BANCADA oferece `—` nos dois campos de escolha, e ele é `disabled`."""
    from hefesto_dualsense4unix.interface import onde

    bancada = onde.pagina(PAGINA).read_text(encoding="utf-8")
    miolo = bancada.split('<div class="miolo">', 1)[-1].split('<div class="nota">', 1)[0]
    quantos = len(re.findall(
        rf'<option value="{a03.TRAVESSAO}"[^>]*\bdisabled\b', miolo))
    assert quantos == miolo.count("<select"), (
        f"{quantos} campos oferecem `—` e há {miolo.count('<select')} campos de "
        f"escolha na bancada. O que não oferece não pode receber o vazio.")


def test_o_efeito_com_nome_nasce_e_volta(a03, tmp_path, monkeypatch):
    """A decisão 17 inteira: ela salva, o nome aparece na lista, e escolhê-lo aplica.

    A BIBLIOTECA MORA EM `app/gui_prefs.py` — a caixa de preferências da
    interface, que já existia, é XDG-correta e resolve o caminho NA CHAMADA. O
    `conftest.py` desta casa já desvia `HOME` e os `XDG_*` para um lar de
    mentira, então nada aqui toca o disco dela.

    ARRANQUE o `_salvar_o_meu` do gesto `guardar` e esta régua reprova na
    primeira asserção: o nome não volta.
    """
    from pacotes import Contexto, gesto_da_pagina

    ctx = Contexto(state={"active_profile": ""}, mesa=MESA,
                   conectados=[FALSO], estados={})
    forma = {"modo-chave-e": "Rigid", "aj-val-e-0": "3", "aj-val-e-1": "180",
             "modo-chave-d": "Off", "nome-do-efeito": "Recuo do MK"}
    guardar = gesto_da_pagina(PAGINA, "guardar")
    assert guardar is not None
    volta = guardar(ctx, {"uniq": FALSO["uniq"], "forma": forma}, _PonteDeMentira())

    salvos = a03.meus_efeitos()
    assert "Recuo do MK" in salvos, (
        f"o efeito não foi guardado. A biblioteca devolveu {sorted(salvos)} — e "
        f"sem ela os 'Meus efeitos' voltam a ser dois nomes de exemplo sem dono.")
    assert salvos["Recuo do MK"]["left"] == {"mode": "Rigid", "params": [3, 180]}, (
        "o que foi guardado não é o que estava na coluna — os ajustes vêm do "
        "`data-campo` de cada barra, e sem eles o efeito nasce com os PADRÕES "
        "do modo em vez do que ela ajustou")

    opcoes = a03.html_das_opcoes_de_pronto()
    assert f'value="{a03.PREFIXO_DO_MEU}Recuo do MK"' in opcoes, (
        f"o efeito salvo não entrou no campo de escolha:\n{opcoes}")
    assert a03.SEPARADOR_DOS_MEUS in opcoes
    assert isinstance(volta, dict) and volta.get("blocos"), (
        "o gesto não devolveu a lista nova — ela só veria o nome no tique "
        "seguinte, e um botão que parece não fazer nada é clicado duas vezes")

    ponte = _PonteQueGuarda()
    pronto = gesto_da_pagina(PAGINA, "pronto")
    pronto(ctx, {"uniq": FALSO["uniq"], "lado": "e",
                 "v": f"{a03.PREFIXO_DO_MEU}Recuo do MK"}, ponte)
    assert ponte.chamadas == [("trigger_set_detalhado", ("left", "Rigid", [3, 180]))], (
        f"escolher o efeito dela não chegou ao daemon com o que ela salvou: "
        f"{ponte.chamadas}")

    assert a03._meu_efeito_que_casa("left", {"mode": "Rigid", "params": [3, 180]}) \
        == "Recuo do MK"
    assert a03._meu_efeito_que_casa("left", {"mode": "Rigid", "params": [0, 0]}) == ""


def test_a_lista_nao_promete_efeito_que_nao_existe(a03):
    """Sem efeito salvo, NÃO nasce separador de "Meus efeitos"."""
    opcoes = a03.html_das_opcoes_de_pronto()
    assert a03.SEPARADOR_DOS_MEUS not in opcoes, (
        f"a lista trouxe o separador sem nenhum efeito salvo:\n{opcoes}")
    assert "Recuo do MK" not in opcoes, (
        "os dois nomes de EXEMPLO do desenho vazaram para o produto — a lista "
        "do produto é a biblioteca dela, e ela está vazia")
    assert "custom" in opcoes, "a lista perdeu as opções que o desenho oferece"


class _PonteQueGuarda:
    """Um dublê que anota o nome e os argumentos posicionais de cada chamada."""

    def __init__(self) -> None:
        self.chamadas: list[tuple[str, tuple]] = []

    def __getattr__(self, nome: str):
        def anotar(*args, **kwargs):
            self.chamadas.append((nome, args))
            return (True, "", {})
        return anotar


_GRANDES = ("Machine", "Custom", "MultiPositionFeedback", "MultiPositionVibration")


def _visiveis(html: str) -> int:
    """Quantas barras a tela MOSTRA — as escondidas não contam."""
    return sum(1 for linha in html.splitlines()
               if 'class="barra"' in linha and "display:none" not in linha)


def test_a_caixa_nao_vaza_na_pagina_que_o_produto_renderiza_hoje(a03):
    """Nenhum modo põe na tela mais barras do que a página publicada comporta.

    A MORDIDA: devolva `html_dos_ajustes` ao `cabem=None` (ou apague o
    `_cabem_no_desenho` da chamada em `_blocos_da_coluna`) e este teste reprova
    com o nome do modo e o número de barras que vazariam.

    O TETO NÃO É DIGITADO: ele é `_casas_cravadas()`, lido da página publicada,
    e some sozinho no dia em que ela publicar a bancada — ver
    `test_a_caixa_cresce_no_dia_em_que_ela_publicar`.
    """
    casas = {"e": 4, "d": 2}
    grandes = 0
    for nome in _GRANDES:
        quantos = len(a03._padroes(nome))
        assert quantos > 2, (
            f"{nome} devolveu {quantos} parâmetros e esta régua existe para os "
            "modos GRANDES, que são os que estouram a caixa")
        for sigla in ("e", "d"):
            html = a03.html_dos_ajustes(
                sigla,
                [{"nome": f"P{i}", "valor": str(i), "pct": 10 * i}
                 for i in range(quantos)],
                cabem=casas[sigla])
            assert _visiveis(html) <= casas[sigla], (
                f"{nome}·{sigla}: a caixa põe {_visiveis(html)} barras à vista "
                f"onde a página publicada reserva {casas[sigla]}. O que sobra "
                f"cai por cima da linha de baixo — medido no Chrome, 58 a 119px")
            grandes += 1
    assert grandes >= 8, "a régua deixou de exercitar os modos que estouram"


def test_o_aviso_do_que_nao_coube_saiu_por_decisao_dela(a03):
    """Ela mandou tirar o aviso, e a casa que ele ocupava voltou a ser barra."""
    assert not hasattr(a03, "NAO_COUBE"), (
        "a constante do aviso voltou. Ela saiu por decisão dela em 02/09/2026, "
        "e uma frase de tela não volta sem a palavra dela")

    for teto in (2, 4):
        html = a03.html_dos_ajustes("e", [
            {"nome": f"P{i}", "valor": str(i), "pct": 10 * i} for i in range(11)
        ], cabem=teto)
        assert _visiveis(html) == teto, (
            f"com teto {teto} a caixa mostrou {_visiveis(html)} barras. Sem o "
            "aviso, a casa que ele ocupava é uma barra — o teto é o número de "
            "barras à vista, não ele menos um")
        assert "não cabem" not in html, (
            f"o aviso voltou ao HTML com teto {teto}:\n{html}")

def test_o_que_nao_coube_continua_no_dom_para_o_guardar_nao_destruir(a03):
    """O que a tela não mostra o "Guardar" ainda tem de LER."""
    html = a03.html_dos_ajustes(
        "e",
        [{"nome": f"Posição {i}", "valor": str(i), "pct": 10 * i}
         for i in range(10)],
        cabem=4,
    )
    assert _visiveis(html) < 10, "esta régua supõe a caixa com teto"
    forma = {m.group(1): m.group(2) for m in re.finditer(
        r'data-campo="(aj-val-e-\d+)"[^>]*>([^<]*)<', html)}
    assert len(forma) == 10, (
        f"a caixa levou {len(forma)} endereços de valor e o modo tem 10. O que "
        f"não coube na vista some do DOM, e o Guardar grava o padrão por cima "
        f"do que ela salvou: {sorted(forma)}")
    guardado = a03._ajustes_da_coluna(forma, "e", "MultiPositionFeedback")
    padrao = a03._padroes("MultiPositionFeedback")
    assert guardado != padrao, (
        "o Guardar leu a coluna e devolveu exatamente os padrões do modo — os "
        "valores dela não sobreviveram à caixa com teto")


def test_a_caixa_cresce_no_dia_em_que_ela_publicar(a03, monkeypatch):
    """Publicada a bancada, o teto SOME sozinho — sem ninguém mexer no pacote.

    O pacote pergunta à página, e a pergunta é a declaração que faz a trilha
    crescer (`minmax(var(--r-aj-<lado>),auto)`). Aqui a bancada entra no lugar
    da publicada e a resposta vira `None` nos dois lados.

    A MORDIDA: crave `return None` em `_cabem_no_desenho` e o irmão de cima
    (`..._nao_vaza_na_pagina_que_o_produto_renderiza_hoje`) reprova; crave um
    número e este reprova.
    """
    from hefesto_dualsense4unix.interface import onde

    bancada = onde.pagina(PAGINA).read_text(encoding="utf-8")
    monkeypatch.setattr(a03, "_pagina_publicada", lambda: bancada)
    for nome in ("_LIDO", "_ENDERECOS", "_VAZIOS", "_OFERECE",
                 "_OPCOES_DO_PRONTO", "_CRESCE"):
        monkeypatch.setattr(a03, nome, None)

    assert a03._a_caixa_cresce() == {"e": True, "d": True}, (
        "a bancada não declara a trilha que cresce — a decisão 2 dela saiu do "
        "desenho, e publicar deixaria de curar o vazamento")
    assert a03._cabem_no_desenho("e") is None and a03._cabem_no_desenho("d") is None

    r = _pacote_com(a03, modo_esq="MultiPositionVibration",
                    modo_dir="MultiPositionVibration")
    for sigla in ("e", "d"):
        html = _bloco(a03, r, "p1", sigla)
        assert "display:none" not in html, (
            f"o lado {sigla!r} continuou escondendo barra numa página que "
            f"deixa a caixa crescer")
        assert "não cabem" not in html, (
            f"o lado {sigla!r} avisou que algo não coube, e coube")
        assert _visiveis(html) == 11, (
            f"o lado {sigla!r} mostrou {_visiveis(html)} das 11 barras do modo")


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

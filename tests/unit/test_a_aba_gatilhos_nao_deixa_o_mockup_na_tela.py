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

#: O `data-campo` do CABEÇALHO não é desta aba. `conta`, `conta-b` e `perfil`
#: moram no `topo.html`, o esqueleto das dez, e quem os pinta é
#: `pacotes.topo()` — cobrá-los do pacote da aba faria a régua reprovar o
#: pacote por não fazer o trabalho de outro. Medido em 01/09/2026, quando os
#: três apareciam vazios em TODAS as abas porque ninguém cuidava do que era de
#: todas.
DO_CABECALHO = {"conta", "conta-b", "perfil"}


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


#: UM CONTROLE DE MENTIRA, com a forma que o daemon devolve. O MAC é da faixa
#: sintética da casa (`aa:bb:cc`): há dois portões de anonimato nesta árvore.
FALSO = {
    "uniq": "aa:bb:cc:00:00:01", "player": 1, "transport": "usb", "is_primary": True,
    "inputs": {"l2_raw": 0, "r2_raw": 0},
}
MESA = [{"pref": "p1", "jogador": 1, "uniq": "aa:bb:cc:00:00:01",
         "nome": "Régua", "via": "USB", "cor": "starlight-blue",
         "mascara": "DualSense", "alvo": True}]


def _coluna(a03, modo_esq: str = "Off", modo_dir: str = "Off") -> dict:
    """A coluna que o pacote devolve para um perfil com aqueles dois modos.

    O PERFIL É INJETADO PELA PORTA DE CIMA (`perfil.ativo`), e não por um
    arquivo de mentira no disco: o que esta régua mede é a TRADUÇÃO do perfil
    para endereços de tela, e escrever um `.json` faria a régua medir também o
    leitor de perfis — que tem régua própria em `test_o_perfil_chega_na_tela.py`.
    """
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


def test_o_modo_sem_ajuste_apaga_as_casas(a03, publicada):
    """`Off` não tem ajuste — logo NENHUMA barra pode sobrar com o desenho.

    É o defeito D3 inteiro numa asserção. Arranque o `encher()` de
    `_do_lado` e esta régua reprova nomeando a casa que ficou órfã.
    """
    col = _coluna(a03)
    casas, _ = a03._casas_e_barras()
    assert casas["e"] and casas["d"], (
        f"a página não declarou casa de ajuste nenhuma ({casas}). Zero aqui faz "
        f"a régua passar por VACUIDADE, que é o pior estado: ela deixaria de "
        f"cobrar exatamente o que existe para cobrar.")

    orfas = []
    for sigla, quantas in casas.items():
        for i in range(quantas):
            for peca in ("nome", "val", "pct"):
                chave = f"aj-{peca}-{sigla}-{i}"
                if chave not in col:
                    orfas.append(chave)
    assert not orfas, (
        f"o modo `Off` não tem ajuste e estes {len(orfas)} endereços ficaram sem "
        f"quem escreva: {orfas}. Um endereço que ninguém escreve continua "
        f"mostrando o DESENHO — foi assim que a tela mostrou `Força 7` debaixo "
        f"de um campo que dizia `Desligado`.")

    for sigla, quantas in casas.items():
        for i in range(quantas):
            assert col[f"aj-nome-{sigla}-{i}"] == a03.VAZIO, (
                f"aj-nome-{sigla}-{i} saiu {col[f'aj-nome-{sigla}-{i}']!r} com o "
                f"modo `Off`. Um nome de ajuste aqui é a tela nomeando um "
                f"controle que o modo não tem.")
            assert col[f"aj-val-{sigla}-{i}"] == a03.VAZIO
            assert col[f"aj-pct-{sigla}-{i}"] == 0, (
                "a barra tem de ir a ZERO. Vazio vira `width:—%`, que o "
                "navegador ignora — e a barra ficaria na largura do mockup.")


def test_o_modo_com_ajuste_continua_pintando_os_dele(a03):
    """A cura não pode ter apagado o caso que já funcionava.

    `Rigid` tem dois parâmetros e a página tem quatro casas à esquerda: as duas
    primeiras levam o dado, as duas de trás saem vazias. Sem esta régua, um
    `encher()` chamado cedo demais zeraria os valores dela.
    """
    col = _coluna(a03, modo_esq="Rigid")
    assert col["aj-nome-e-0"] == "Posição"
    assert col["aj-nome-e-1"] == "Força"
    casas, _ = a03._casas_e_barras()
    for i in range(2, casas["e"]):
        assert col[f"aj-nome-e-{i}"] == a03.VAZIO, (
            f"a casa {i} não é do `Rigid` (ele tem 2) e veio "
            f"{col[f'aj-nome-e-{i}']!r} — o desenho vazando por trás do dado.")


def test_nenhum_endereco_da_pagina_fica_sem_dono(a03, publicada):
    """Todo `data-campo` da página tem quem o escreva. É a catraca da aba.

    Ela conta os endereços da PÁGINA, não os do pacote — e é essa direção que
    faz dela uma régua e não um espelho. Um `data-campo` novo no desenho entra
    aqui vermelho até alguém ligá-lo.
    """
    col = _coluna(a03)
    na_pagina = set(re.findall(r'data-campo="([^"]+)"', publicada)) - DO_CABECALHO
    sem_dono = sorted(na_pagina - set(col))
    assert not sem_dono, (
        f"{len(sem_dono)} endereço(s) da página que ninguém escreve: {sem_dono}. "
        f"Cada um continua mostrando o valor que o gerador desenhou.")


def test_a_cobertura_conta_o_que_a_pagina_recebe(a03, publicada):
    """A nota da aba é o que PINTA, não o que o dicionário tem.

    Medido em 02/09/2026 contra a mesa dela: o pacote devolvia 20 chaves por
    controle e o piloto escrevia 8 valores — as doze restantes (`l2-raw`,
    `l2-pct`, `r2-raw`, `r2-pct`, `modo-e`, `modo-d`, vezes as duas colunas) são
    endereços que a página não tem. Contá-las era esta aba dando-se nota por
    escrever no vazio, que é a forma exata do `77%` falso que a medição de 02/09
    derrubou.
    """
    from pacotes import Contexto, perfil

    guardado = perfil.ativo
    perfil.ativo = lambda _nome: {"triggers": {}, "controllers": {}}  # type: ignore[assignment]
    try:
        r = a03.pacote(Contexto(state={"active_profile": "régua"}, mesa=MESA,
                                conectados=[FALSO], estados={}))
    finally:
        perfil.ativo = guardado  # type: ignore[assignment]

    # A CONTA É DE TODAS AS COLUNAS, e não da primeira — mudado em 02/09/2026,
    # quando a coluna do LUGAR VAZIO passou a ser escrita também (o defeito D4).
    # Ler só `next(iter(...))` faria esta régua reprovar a cura: ela compararia
    # a nota da aba INTEIRA com os endereços de UM controle.
    na_pagina = set(re.findall(r'data-campo="([^"]+)"', publicada))
    devia = sum(1 for col in r["colunas"].values() for k in col if k in na_pagina)
    sobra = sum(1 for col in r["colunas"].values() for k in col if k not in na_pagina)
    assert r["cobertura"]["pintados"] == devia, (
        f"a cobertura diz {r['cobertura']['pintados']} e a página só tem "
        f"endereço para {devia}. Contar o que não pousa é a aba se dando nota.")
    assert r["cobertura"]["sem_endereco"] == sobra, (
        "o que sai e não tem onde pousar tem de estar DITO, não escondido")


def test_a_barra_diz_como_quer_ser_pintada():
    """A barra de ajuste pinta por LARGURA — e a régua olha a BANCADA.

    `escrever()` do piloto (`hefesto_vivo.py`) só encomprida quem declara
    `data-hef-alvo="largura"`; sem isso o alvo é `texto` e a pintura escreve o
    número DENTRO do trilho de 5px, deixando a barra na largura do mockup.

    A BANCADA, e não o publicado, porque é ela que o gerador escreve: o
    publicado só muda quando ela aprovar a aba, e cobrar dele faria esta régua
    reprovar por uma decisão que é dela. A divergência está declarada em
    `mockup/DIVERGENCIAS.md`, e `check_o_desenho_aprovado.py` a cobra.
    """
    from hefesto_dualsense4unix.interface import onde

    texto = onde.pagina(PAGINA).read_text(encoding="utf-8")
    barras = re.findall(r'<span[^>]*data-campo="aj-pct-[ed]-\d+"[^>]*>', texto)
    assert barras, "a bancada não tem barra de ajuste nenhuma — a régua ficou cega"
    mudas = [b for b in barras if 'data-hef-alvo="largura"' not in b]
    assert not mudas, (
        f"{len(mudas)} de {len(barras)} barras não dizem que pintam por largura. "
        f"Sem o alvo, a pintura escreve o número dentro da barra e a largura "
        f"continua a do desenho: {mudas[:2]}")


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
    """Um dublê que responde a qualquer nome e guarda o que foi chamado.

    O DAEMON VIVO NÃO ENTRA AQUI, e a razão é de bancada: há dois controles na
    mesa dela e um `trigger.set` de régua mudaria o aparelho debaixo de quem
    estiver jogando. O que esta régua mede é se o gesto CHEGA à ponte — e para
    isso o dublê basta, porque a ponte é injetada, não importada.
    """

    def __init__(self) -> None:
        self.chamadas: list[str] = []

    def __getattr__(self, nome: str):
        def registrar(*args, **kwargs):
            self.chamadas.append(nome)
            return True
        return registrar


@pytest.mark.parametrize("nome_do_gesto", ["modo", "pronto", "guardar"])
def test_o_lugar_vazio_nao_alcanca_a_ponte(a03, nome_do_gesto):
    """Os TRÊS gestos da aba recusam antes de falar com o daemon.

    É o que separa esta cura de uma mensagem bonita: um `trigger.set` com
    `uniq` vazio vai em BROADCAST e zera o gatilho dos QUATRO — foi o defeito
    ABAS-06 (25/07), descrito no próprio `ipc_bridge.trigger_reset_detalhado`.
    A régua conta as chamadas: zero é o único número aceitável.
    """
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
    """As casas são as do desenho, lidas dele. Nenhum número digitado aqui.

    Se alguém trocar a leitura por um `4` e um `2` cravados, esta régua não
    reprova sozinha — mas o dia em que o desenho mudar, sim: ela compara com o
    que está no arquivo, que é a única fonte que envelhece junto.
    """
    casas, _ = a03._casas_e_barras()
    for sigla, quantas in casas.items():
        indices = {int(i) for i in re.findall(
            rf'data-campo="aj-nome-{sigla}-(\d+)"', publicada)}
        assert quantas == (max(indices) + 1 if indices else 0), (
            f"o lado {sigla!r}: o pacote conta {quantas} casas e a página tem "
            f"{sorted(indices)}. Endereçar a menos deixa o desenho na tela.")


# ---------------------------------------------------------------------------
# O DEFEITO D4 — A COLUNA DO LUGAR VAZIO, e ele é o D3 numa coluna que ninguém
# olhava. Medido em 02/09/2026 pela `--prova-de-mockup` com a mesa dela:
#
#     03-gatilhos.html (8):
#         p3·modo-chave-e = 'Off'     <- ENDERECO MORTO
#         p3·pronto-e     = 'custom'  <- ENDERECO MORTO   (e os seis irmãos)
#
# "ENDEREÇO MORTO" na régua quer dizer: **o pacote declara um valor e a tela
# mostra outro**. O piloto preenche todo lugar que a mesa não tem com um
# travessão (`hefesto_vivo.py:1006-1016`) e `escrever()` RECUSA pôr num
# `<select>` um valor que ele não oferece (`:145-151`) — a recusa é certa, e o
# desfecho é que a coluna vazia continua com o que o gerador escreveu.
#
# ENQUANTO O CRAVADO É `Off`/`custom` ISSO PASSA POR INOFENSIVO. Não é: no dia
# em que um controle sair do P3 com `Rígido` aplicado, o `Rígido` FICA — a
# coluna de um lugar sem aparelho afirmando um efeito.
# ---------------------------------------------------------------------------

#: A MESA DE DOIS, que é a dela. Os `uniq` são da faixa sintética da casa.
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
    """A coluna sem aparelho é ESCRITA, e com valor que o `<select>` aceita.

    ARRANQUE o laço dos vazios em `pacote()` e esta régua reprova nomeando a
    coluna: sem ele o pacote não devolve `p3` nenhum, e o único valor que chega
    àqueles quatro campos é o travessão que o `<select>` recusa.

    O VALOR TEM DE SER OFERECIDO PELA PÁGINA — não basta ser honesto. É a
    segunda asserção, e é ela que separa esta cura de escrever `'—'` de novo.
    """
    r = _com_a_mesa(a03, MESA_DE_DOIS, [FALSO, FALSO_2])
    vazios = sorted(a03._lugares_que_o_desenho_da_por_vazios())
    assert vazios, "a página não marca lugar vazio nenhum — a régua ficou cega"
    for pref in vazios:
        col = r["colunas"].get(pref)
        assert col, (
            f'a coluna {pref} não foi escrita. A página a marca '
            f'`data-conectado="nao"`, e o que o pacote não escreve continua '
            f"mostrando o desenho — é o ENDEREÇO MORTO da régua do mockup.")
        assert set(col) == {"modo-chave-e", "modo-chave-d", "pronto-e", "pronto-d"}, (
            f"{pref} recebeu {sorted(col)}. A coluna vazia do desenho não tem "
            f"barra de ajuste nenhuma — ela traz 'Este modo não tem o que "
            f"ajustar.' —, e emitir `aj-*` ali é se dar nota por escrever no vazio.")
        for campo, valor in col.items():
            oferece = re.search(
                rf'data-campo="{campo}"(.*?)</select>', publicada, re.S)
            assert oferece, f"{pref}·{campo} não é um `<select>` da página"
            assert f'value="{valor}"' in oferece.group(1), (
                f"{pref}·{campo} = {valor!r}, e o `<select>` da página não "
                f"oferece essa opção. `escrever()` do piloto devolve 0 sem "
                f"escrever, e a coluna fica com o efeito de quem saiu dali.")


def test_o_lugar_vazio_nao_rouba_a_marca_do_piloto(a03):
    """O pacote NÃO escreve numa coluna que o desenho dá por conectada.

    POR QUE ISTO É UMA RÉGUA E NÃO UM DETALHE: o piloto deduz "lugar vazio" de
    "coluna que ninguém emitiu" (`hefesto_vivo.py:1006-1016`) e é essa dedução
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
    """Com o controle na mesa, `Rigid`; sem ele, `Off`. É o D4 inteiro.

    Esta é a asserção que dá o CUSTO do defeito em vez do nome dele: o mesmo
    perfil, a mesma aba, o controle saindo do lugar — e o campo tem de mudar.
    """
    mesa_de_tres = [
        *MESA_DE_DOIS,
        {"pref": "p3", "jogador": 3, "uniq": "aa:bb:cc:00:00:03",
         "nome": "Régua", "via": "BT", "cor": "cosmic-red",
         "mascara": "DualSense", "alvo": False}]
    tres = [FALSO, FALSO_2, dict(FALSO, uniq="aa:bb:cc:00:00:03", player=3)]

    com_ele = _com_a_mesa(a03, mesa_de_tres, tres)["colunas"]["aa:bb:cc:00:00:03"]
    assert com_ele["modo-chave-e"] == "Rigid"

    sem_ele = _com_a_mesa(a03, MESA_DE_DOIS, [FALSO, FALSO_2])["colunas"]["p3"]
    assert sem_ele["modo-chave-e"] == "Off", (
        "o P3 esvaziou e o campo continuou dizendo `Rigid`. É a tela afirmando "
        "um efeito num lugar onde não há aparelho.")


# ---------------------------------------------------------------------------
# A RECUSA DO DAEMON NA LÍNGUA DA TELA — LEI 0: a tradução já existia.
# `app/actions/triggers_actions.humanizar_erro_gatilho` é a HARM-19, escrita e
# testada para a aba Gatilhos da GUI estável. Conferido em 02/09/2026: ZERO
# pacotes da interface nova a chamavam, e o daemon falava com ela na língua do
# `core/trigger_effects`.
# ---------------------------------------------------------------------------


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
    """A frase que vai para a tela dela é a humanizada, não a do `core`.

    ARRANQUE o `_na_lingua_da_tela` das duas linhas de `raise` e esta régua
    reprova mostrando a frase crua — que é exatamente o que ela via.
    """
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

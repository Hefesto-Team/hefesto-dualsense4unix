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

    col = next(iter(r["colunas"].values()))
    na_pagina = set(re.findall(r'data-campo="([^"]+)"', publicada))
    devia = sum(1 for k in col if k in na_pagina)
    assert r["cobertura"]["pintados"] == devia, (
        f"a cobertura diz {r['cobertura']['pintados']} e a página só tem "
        f"endereço para {devia}. Contar o que não pousa é a aba se dando nota.")
    assert r["cobertura"]["sem_endereco"] == len(col) - devia, (
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

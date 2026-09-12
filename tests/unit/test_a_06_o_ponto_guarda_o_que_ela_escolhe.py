#!/usr/bin/env python3
"""A RÉGUA DA `F2-POINT-AND-CLICK`: o *Estilo Point-and-click* passou a gravar.

O QUE ESTA FRENTE FECHOU, medido pela `PAGINAS-ESPECIAIS-B1` em 11/09/2026:

    doze páginas especiais   doze ABREM · quatro FAZEM
    `#point-and-click`       7 `<select>` · ZERO com endereço
    `#remapeamento`          22 `<select>` · ZERO com endereço

A reação dela ao número é o dado desta sprint: *"eu achei que elas
funcionavam"*. E a ordem que ela deu na onda anterior é a régua do que cabe
aqui — *"A ideia não é adicionar mais nada em termos de feature ou interface,
Mas é fazer o todo funcionar"*: estas telas já estão desenhadas e prometidas.

**ELA LÊ, NÃO DIGITA.** Nenhum id de botão, nenhum rótulo de ação e nenhuma
contagem está escrita aqui: os botões saem de `core.acoes_de_botao.BOTOES`, o
de fábrica de `acoes_de_botao.padrao()`, os rótulos de `acoes_de_botao.rotulo`
e as linhas da tela da PÁGINA PUBLICADA. Esta casa pagou onze vezes em 26/08
por réguas que digitavam o que deviam ler.

**E ELA MEDE O PRODUTO, não a frase.** As gravações passam pelo gesto inteiro —
a `forma` que o piloto recolheria, o `Profile` do esquema (nunca um dublê mais
frouxo) e o `resolver()` do motor, que é literalmente a chamada que
`profiles/manager.apply_button_actions` faz para alimentar o device.

A MORDIDA de cada caso está na docstring dele.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
for _caminho in (str(RAIZ / "src"), str(INTERFACE)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

PAGINA = "06-navegacao.html"  # (noqa-acento) nome de arquivo
TELA = "point-and-click"  # (noqa-acento) id da pop-up
TELA_IRMA = "definicoes-mouse"  # (noqa-acento) id da pop-up

#: Um controle de mentira, na faixa sintética da casa — há dois portões de
#: anonimato nesta árvore e eles não perdoam.
UNIQ = "aa:bb:cc:00:00:01"
FALSO = {"uniq": UNIQ, "player": 1, "connected": True, "transport": "bt",
         "battery_pct": 95, "is_primary": True, "inputs": {}, "audio": {},
         "speaker": {}}
MESA = [{"pref": "p1", "jogador": 1, "uniq": UNIQ, "nome": "Régua",
         "via": "rádio", "cor": "starlight-blue", "mascara": "DualSense"}]

ESTADO = {
    "active_profile": "regua",
    "mouse_emulation": {"enabled": False, "speed": 6, "scroll_speed": 1,
                        "bloqueio": "desligada", "despachando": False},
    "keyboard_emulation": {"enabled": True, "osk_disponivel": True},
    "controllers": [FALSO],
}


class _PonteMuda:
    """Aceita tudo e ANOTA. É o que separa "não gravou" de "não chamou"."""

    def __init__(self) -> None:
        self.chamadas: list[tuple[str, dict]] = []

    def chamar(self, metodo: str, **params: object) -> bool:
        self.chamadas.append((metodo, dict(params)))
        return True

    def __getattr__(self, _nome: str):
        return lambda *a, **k: True


def _publicado() -> str:
    """A página que o PRODUTO renderiza — e é ela que tem de estar certa.

    A bancada não serve aqui: o piloto lê `interface/paginas/`, e uma tela
    endereçada só no `mockup/` é uma tela que continua muda para quem clica.
    """
    import onde

    return onde.pagina(PAGINA, publicado=True).read_text(encoding="utf-8")


def _recorte(doc: str, ident: str) -> str:
    """O pedaço do documento que é aquela pop-up."""
    return doc.split(f'id="{ident}"', 1)[-1].split('class="tela-nova"', 1)[0]


def _linhas_da_tela() -> list[str]:
    """Os botões que a tela do estilo ENDEREÇA — lidos da página publicada."""
    return re.findall(r'data-linha="([^"]+)"', _recorte(_publicado(), TELA))


def _perfil(**campos):
    """Um `Profile` DE VERDADE — o do esquema, nunca um dublê mais frouxo.

    A RAZÃO É MEDIDA E É DESTA CASA: em 06/09/2026 um dublê de device com a
    assinatura antiga transformou um `TypeError` em "o produto falhou ao
    aplicar". Aqui o perfil é o pydantic do produto: se um campo desta frente
    não couber no esquema, a régua estoura na hora em vez de gravar um
    dicionário que o disco recusaria.
    """
    from hefesto_dualsense4unix.profiles.schema import Profile

    return Profile(name="regua", match={"type": "manual"}, **campos)


@pytest.fixture
def bancada(monkeypatch):
    """O pacote da 06 com um disco de mentira e a trava sempre limpa.

    A LIMPEZA É OBRIGATÓRIA: `_MEXENDO` é estado de MÓDULO, e um teste que a
    deixasse suja contaminaria o seguinte — o vazamento seria justamente o
    defeito que estes casos existem para medir.
    """
    import pacotes
    from pacotes import a06_navegacao as mod
    from pacotes import perfil
    from hefesto_dualsense4unix.profiles import loader
    from hefesto_dualsense4unix.profiles.schema import Profile

    disco: dict[str, object] = {}

    def _gravar(prof, **_):
        # O DISCO REVALIDA, e é de propósito: `model_copy` do pydantic **não**
        # valida, então um dublê que apenas guardasse o objeto seria mais
        # frouxo que o `save_profile` de verdade, que serializa e relê.
        disco[prof.name] = Profile.model_validate(
            json.loads(prof.model_dump_json()))

    monkeypatch.setattr(loader, "load_profile", lambda n: disco[n], raising=False)
    monkeypatch.setattr(loader, "save_profile", _gravar, raising=False)
    monkeypatch.setattr(
        perfil, "ativo",
        lambda nome: (disco[nome].model_dump() if nome in disco else {}))
    mod._MEXENDO.clear()
    monkeypatch.setattr(mod, "_ULTIMA_PINTURA", 0.0, raising=False)
    _gravar(_perfil())
    ctx = pacotes.Contexto(state=ESTADO, mesa=MESA, conectados=[FALSO], estados={})
    yield ctx, mod, disco
    mod._MEXENDO.clear()


def _forma(mod, perfil_dict, **trocas) -> dict[str, str]:
    """A `forma` que o piloto recolheria de `#point-and-click`, com trocas.

    Ela parte do que a tela PINTADA mostra — que é o perfil —, porque é esse o
    estado em que o dedo dela encontra a tela. Uma forma montada do desenho
    mede o instante anterior ao primeiro tique, e é o que o caso da trava usa.
    """
    mostra = mod._linhas_dos_botoes(perfil_dict)
    fora = {b: mostra[f"{mod.PREFIXO_DA_ACAO}{b}"] for b in _linhas_da_tela()}
    fora.update(trocas)
    return fora


def _trocas_que_o_produto_atende(mod) -> dict[str, str]:
    """Uma escolha diferente do de fábrica para cada linha que tem atendente.

    PERGUNTADA AO MOTOR, nunca digitada: o de fábrica sai de
    `acoes_de_botao.padrao()`, a lista de `acoes_de_botao.ACOES`, e o que o
    produto não atende hoje de `SEM_ATENDENTE`. Uma régua que digitasse
    "Botão direito no círculo" envelheceria calada no dia em que o produto
    mudasse o padrão daquela linha.

    OS DOIS EIXOS FICAM DE FORA, e é o motor que o diz: `resolver()` os pula
    (mover o cursor e rolar não são evento de botão). Uma troca neles iria ao
    perfil e não chegaria a device nenhum — e este arquivo mede o caminho
    inteiro, não meio dele.
    """
    from hefesto_dualsense4unix.core import acoes_de_botao as acoes

    fabrica = acoes.padrao()
    fora: dict[str, str] = {}
    for botao in _linhas_da_tela():
        if botao in (acoes.EIXO_ESQUERDO, acoes.EIXO_DIREITO):
            continue
        alvo = next(
            t for t in acoes.ACOES
            if t != fabrica[botao] and t not in acoes.SEM_ATENDENTE
            and not t.startswith("__"))
        fora[botao] = acoes.rotulo(alvo)
    assert fora, "nenhuma linha desta tela tem atendente — a régua perdeu o alvo"
    return fora


# ---------------------------------------------------------------------------
# 1 — O ENDEREÇO, na página que o produto renderiza
# ---------------------------------------------------------------------------
def test_toda_linha_que_e_botao_do_produto_tem_endereco():
    """Cada `<select>` desta tela cujo assunto é botão do produto ENDEREÇA.

    E o inverso também: a linha que NÃO é botão em `acoes_de_botao.BOTOES` —
    *deslizar o dedo no touchpad*, que é o mouse virtual e não uma peça — fica
    sem endereço, porque dar-lhe um inventaria um botão que o `resolver()` não
    conhece.

    A MORDIDA: tire o `gesto=`/`linha=`/`campo=` do `drop` da `TELA_PONTO` em
    `aba06.py` e regenere — este caso nomeia quantas linhas ficaram mudas.
    """
    from hefesto_dualsense4unix.core import acoes_de_botao as acoes

    tela = _recorte(_publicado(), TELA)
    listas = re.findall(r"<select[^>]*>", tela)
    com_endereco = [s for s in listas if "data-linha=" in s]
    enderecados = _linhas_da_tela()
    assert len(listas) > len(com_endereco), (
        "todas as listas desta tela ganharam endereço, inclusive a que não é "
        "botão do produto — `deslizar o dedo no touchpad` não está em "
        "`acoes_de_botao.BOTOES`, e gravá-lo seria inventar um botão")
    assert len(listas) - len(com_endereco) == 1, (
        f"{len(listas) - len(com_endereco)} listas desta tela estão sem "
        "endereço, e só UMA tem motivo medido (a do deslizar). As outras são "
        "escolha que o Guardar descarta em silêncio.")
    assert set(enderecados) <= set(acoes.BOTOES), (
        f"a tela endereça o que o produto não conhece: "
        f"{sorted(set(enderecados) - set(acoes.BOTOES))}")
    for lista in com_endereco:
        assert 'data-hef-alvo="valor"' in lista, (
            f"uma lista endereçada perdeu o `data-hef-alvo=\"valor\"`: {lista} "
            "— sem ele o piloto escreveria o texto DENTRO do `<select>` e "
            "comeria as opções")
        assert 'data-gesto="linha-de-botao"' in lista, (
            f"uma lista endereçada perdeu o `data-gesto`: {lista} — sem ele o "
            "`change` morre no navegador e o tique reescreve a escolha dela")


def test_as_duas_telas_falam_do_mesmo_campo_pelo_mesmo_endereco():
    """Um botão, um endereço. Duas grafias seriam duas verdades sobre um dado.

    As telas *Definições Controle e Mouse* e *Estilo Point-and-click* escrevem
    o MESMO campo do perfil (`Profile.button_actions`). Se cada uma tivesse o
    seu `data-campo`, a pintura escreveria em uma e não na outra — e a tela não
    pintada mostraria o desenho enquanto o perfil diz outra coisa.

    A MORDIDA: troque o `campo=` da `TELA_PONTO` por qualquer outro prefixo e
    regenere — este caso nomeia o botão cujo endereço divergiu.
    """
    doc = _publicado()
    irma = _recorte(doc, TELA_IRMA)
    for botao in _linhas_da_tela():
        alvo = f'data-campo="acao-{botao}"'
        assert alvo in irma, (
            f"o {botao} é endereçado como {alvo!r} no Estilo Point-and-click e "
            "a tela de Definições não usa esse endereço — as duas passariam a "
            "mostrar coisas diferentes sobre o mesmo campo do perfil")


def test_o_guardar_pede_a_forma_da_propria_pop_up():
    """Sem `data-hef-forma`, o Guardar não sabe o que está escolhido.

    E o `id` pedido tem de ser o DA PRÓPRIA POP-UP: o piloto recorta a
    varredura por `getElementById`, e é isso que impede as duas telas que
    escrevem o mesmo campo de recolherem a forma uma da outra. Um `id` trocado
    faria o Guardar do estilo gravar as 22 linhas da tela vizinha.

    A MORDIDA: tire o `data-hef-forma` do Guardar, ou aponte-o para
    `definicoes-mouse` — este caso reprova nos dois casos.
    """
    tela = _recorte(_publicado(), TELA)
    guardar = [a for a in re.findall(r"<a[^>]*>", tela)
               if 'data-gesto="guardar-ponto"' in a]
    assert guardar, "o Guardar do Estilo Point-and-click sumiu da página"
    assert f'data-hef-forma="{TELA}"' in guardar[0], (
        f"o Guardar desta tela não pede a forma de `{TELA}`: {guardar[0]} — "
        "sem ela ele volta a não ter o que gravar, e com o `id` da outra tela "
        "ele gravaria as linhas que ninguém abriu")


def test_o_sair_desta_tela_tem_nome():
    """O botão de fechar e o `Cancelar` avisam o Python de que ela desistiu.

    São DOIS, e a razão é a mesma que deu nome aos da tela irmã em 02/09: a
    trava das escolhas pendentes só se solta quando alguém diz que houve
    desistência.

    A MORDIDA: tire o `data-gesto="fechar-ponto"` de um dos dois e regenere.
    """
    tela = _recorte(_publicado(), TELA)
    quantas = tela.count('data-gesto="fechar-ponto"')
    assert quantas == 2, (
        f"esta tela tem {quantas} saída(s) com nome e precisa de duas (o botão "
        "de fechar e o `Cancelar`) — sem elas a trava fica presa depois de ela "
        "desistir")


# ---------------------------------------------------------------------------
# 2 — O CLIQUE: o que ela escolhe chega ao disco, e volta à tela
# ---------------------------------------------------------------------------
def test_a_escolha_dela_chega_ao_perfil_e_ao_device(bancada):
    """**A MORDIDA DESTA FRENTE.** Ela troca as linhas do estilo; o perfil muda.

    E a prova vai até o DEVICE: não basta o campo aparecer no arquivo. O
    `resolver()` do motor é a chamada que `apply_button_actions` faz para
    alimentar o mouse virtual, e é ela que tem de devolver o botão.

    A MORDIDA: troque o `perfil.gravar_e_reaplicar` do `guardar_ponto` por um
    `return` — este caso reprova dizendo que o disco não mudou.
    """
    from hefesto_dualsense4unix.core import acoes_de_botao as acoes

    ctx, mod, disco = bancada
    p = _PonteMuda()
    trocas = _trocas_que_o_produto_atende(mod)
    for botao, rotulo in trocas.items():
        mod.linha_de_botao(ctx, {"linha": botao, "valor": rotulo}, p)
    mod.guardar_ponto(ctx, {"forma": _forma(mod, disco["regua"].model_dump(),
                                            **trocas)}, p)

    gravado = disco["regua"].button_actions or {}
    for botao, rotulo in trocas.items():
        assert gravado.get(botao) == acoes.token_do_rotulo(rotulo), (
            f"o {botao} devia ter ido ao perfil como "
            f"{acoes.token_do_rotulo(rotulo)!r} e foi como "
            f"{gravado.get(botao)!r}")
    do_mouse, do_teclado, _sem = acoes.resolver(gravado)
    for botao in trocas:
        assert botao in do_mouse or botao in do_teclado, (
            f"o {botao} está no perfil e o `resolver()` — a chamada que o "
            "daemon faz — não o entrega a device nenhum")


def test_a_tela_volta_a_mostrar_o_que_gravou(bancada):
    """Gravar sem reler é meio gesto: o tique seguinte tem de dizer o mesmo.

    A MORDIDA: tire o `campo=` das listas desta tela em `aba06.py` — a pintura
    deixa de alcançá-las, e este caso reprova nomeando o endereço que o pacote
    emite para o vazio.
    """
    ctx, mod, disco = bancada
    p = _PonteMuda()
    trocas = _trocas_que_o_produto_atende(mod)
    for botao, rotulo in trocas.items():
        mod.linha_de_botao(ctx, {"linha": botao, "valor": rotulo}, p)
    mod.guardar_ponto(ctx, {"forma": _forma(mod, disco["regua"].model_dump(),
                                            **trocas)}, p)
    mod._MEXENDO.clear()

    doc = _recorte(_publicado(), TELA)
    mostra = mod._linhas_dos_botoes(disco["regua"].model_dump())
    for botao, rotulo in trocas.items():
        campo = f"{mod.PREFIXO_DA_ACAO}{botao}"
        assert mostra.get(campo) == rotulo, (
            f"a tela reabre mostrando {mostra.get(campo)!r} no {botao} e o "
            f"perfil guarda {rotulo!r}")
        assert f'data-campo="{campo}"' in doc, (
            f"o pacote emite {campo!r} e esta tela não tem onde pô-lo — o "
            "valor iria para o vazio")


def test_o_guardar_junta_e_nao_substitui(bancada):
    """As dezesseis linhas que esta tela NÃO mostra não podem ser apagadas.

    A forma desta pop-up traz só as linhas dela. Um Guardar que gravasse
    exatamente o que recebeu apagaria o resto do `button_actions` sem uma
    palavra — o apagador com rótulo de "Guardar", que esta aba já pagou uma vez
    em 02/09/2026.

    A MORDIDA: troque o `novo = dict(prof.button_actions or {})` do
    `guardar_ponto` por `novo = {}` — este caso nomeia a escolha perdida.
    """
    from hefesto_dualsense4unix.core import acoes_de_botao as acoes

    ctx, mod, disco = bancada
    p = _PonteMuda()
    # UMA ESCOLHA DE FORA DESTA TELA, escolhida PERGUNTANDO: um botão que a
    # pop-up não endereça, com um valor diferente do de fábrica dele.
    de_fora = next(b for b in acoes.BOTOES if b not in _linhas_da_tela())
    outro = next(t for t in acoes.ACOES
                 if t != acoes.padrao()[de_fora] and t not in acoes.SEM_ATENDENTE)
    disco["regua"] = disco["regua"].model_copy(
        update={"button_actions": {de_fora: outro}})

    trocas = _trocas_que_o_produto_atende(mod)
    for botao, rotulo in trocas.items():
        mod.linha_de_botao(ctx, {"linha": botao, "valor": rotulo}, p)
    mod.guardar_ponto(ctx, {"forma": _forma(mod, disco["regua"].model_dump(),
                                            **trocas)}, p)

    assert (disco["regua"].button_actions or {}).get(de_fora) == outro, (
        f"o Guardar do Estilo Point-and-click apagou a escolha do {de_fora}, "
        "que não está nesta tela")


def test_voltar_uma_linha_ao_de_fabrica_tira_do_perfil(bancada):
    """`button_actions` guarda DIFERENÇA: o de fábrica SAI, não é gravado.

    Gravar o padrão congelaria o padrão VELHO no dia em que o produto mudasse o
    dele — e ninguém teria pedido isso.

    A MORDIDA: troque o `novo.pop(botao, None)` por `novo[botao] = token` — este
    caso reprova mostrando o de fábrica escrito no arquivo.
    """
    from hefesto_dualsense4unix.core import acoes_de_botao as acoes

    ctx, mod, disco = bancada
    p = _PonteMuda()
    trocas = _trocas_que_o_produto_atende(mod)
    for botao, rotulo in trocas.items():
        mod.linha_de_botao(ctx, {"linha": botao, "valor": rotulo}, p)
    mod.guardar_ponto(ctx, {"forma": _forma(mod, disco["regua"].model_dump(),
                                            **trocas)}, p)
    assert disco["regua"].button_actions, "o primeiro Guardar não gravou nada"

    devolve = {b: acoes.rotulo(acoes.padrao()[b]) for b in trocas}
    for botao, rotulo in devolve.items():
        mod.linha_de_botao(ctx, {"linha": botao, "valor": rotulo}, p)
    mod.guardar_ponto(ctx, {"forma": _forma(mod, disco["regua"].model_dump(),
                                            **devolve)}, p)
    assert disco["regua"].button_actions is None, (
        f"o perfil ficou com {disco['regua'].button_actions!r} depois de a "
        "tela voltar inteira ao de fábrica — o campo tinha de sumir, que é o "
        "estado de um perfil que herda")


# ---------------------------------------------------------------------------
# 3 — AS RECUSAS, e todas DIZEM
# ---------------------------------------------------------------------------
def test_a_tela_que_ainda_nao_falou_nao_grava(bancada):
    """A trava contra o desenho — e aqui ela é mais larga que a da tela irmã.

    O desenho desta pop-up **não é o de fábrica**: ele crava a receita do
    estilo. Logo um clique nos 100 ms entre a página carregar e o primeiro
    tique pintar gravaria trocas que ela não pediu. Sem nenhuma linha em
    `_MEXENDO`, qualquer divergência quer dizer *o piloto ainda não falou*.

    A MORDIDA: apague o bloco `if divergem and not _MEXENDO` do `guardar_ponto`
    — este caso passa a ver a escolha do DESENHO no disco.
    """
    ctx, mod, disco = bancada
    p = _PonteMuda()
    do_desenho = dict(_forma(mod, disco["regua"].model_dump()))
    do_desenho.update(_trocas_que_o_produto_atende(mod))
    with pytest.raises(RuntimeError) as erro:
        mod.guardar_ponto(ctx, {"forma": do_desenho}, p)
    assert "tente de novo" in str(erro.value)
    assert disco["regua"].button_actions is None, (
        "o Guardar gravou a receita do desenho como se fosse escolha dela")


def test_sem_perfil_ativo_ele_recusa_dizendo(bancada):
    """Zero controle, zero perfil: a recusa nomeia o que falta.

    É a ordem dela de 11/09 — *"a ideia é que todas as features mesmo do app
    funcionem nao so pra mim mas pra qualquer outro user"*  (noqa-acento:
    citação literal dela): o gesto não pode depender de haver controle na mesa,
    e com perfil nenhum ele diz o caminho.

    A MORDIDA: tire a chamada a `_perfil_ativo_ou_recusa` — este caso vê um
    `KeyError` cru em vez da frase.
    """
    import pacotes

    _ctx, mod, disco = bancada
    vazio = pacotes.Contexto(state={"active_profile": ""}, mesa=[], conectados=[],
                             estados={})
    with pytest.raises(RuntimeError) as erro:
        mod.guardar_ponto(vazio, {"forma": _forma(
            mod, disco["regua"].model_dump())}, _PonteMuda())
    assert "perfil" in str(erro.value).lower()


def test_uma_opcao_que_o_produto_nao_conhece_e_recusada(bancada):
    """Rótulo que não é do produto = o desenho andou sem o gerador.

    A MORDIDA: engula o `nao_reconhecidas` e o rótulo inventado vira uma linha
    a menos, calada, no perfil dela.
    """
    ctx, mod, disco = bancada
    alvo = _linhas_da_tela()[0]
    with pytest.raises(ValueError) as erro:
        mod.guardar_ponto(ctx, {"forma": _forma(
            mod, disco["regua"].model_dump(), **{alvo: "Fazer café"})},
            _PonteMuda())
    assert "Fazer café" in str(erro.value)
    assert disco["regua"].button_actions is None


def test_o_cancelar_larga_a_escolha_pendente(bancada):
    """Fechar é o "sair" — a trava não pode ficar presa depois da desistência.

    A MORDIDA: troque o corpo de `fechar_ponto` por `return None` e a linha
    abandonada continua sendo oferecida ao Guardar seguinte.
    """
    ctx, mod, _disco = bancada
    p = _PonteMuda()
    botao, rotulo = next(iter(_trocas_que_o_produto_atende(mod).items()))
    mod.linha_de_botao(ctx, {"linha": botao, "valor": rotulo}, p)
    assert mod._MEXENDO, "o `linha-de-botao` não anotou a escolha dela"
    mod.fechar_ponto(ctx, {}, p)
    assert not mod._MEXENDO, (
        "o Cancelar desta tela não largou a escolha pendente")


def test_o_gesto_esta_registrado_e_a_casa_sabe_que_ele_grava():
    """Ele saiu do `SEM_GESTO` e entrou nas duas listas que importam.

    A segunda é a que protege a máquina DELA: `pacotes.perigosos()` é derivada
    do `grava=` do decorador, e é ela que faz a prova de clique do piloto
    recusar-se a apertar este botão contra o daemon vivo. Um gesto que grava
    perfil e não aparece ali é uma régua que escreve no perfil real de quem a
    roda — e esta casa já pagou isso em 06/09/2026.

    A MORDIDA: tire o `grava="gravar_e_reaplicar"` do decorador — este caso
    reprova, e sem ele o `--prova-clique` voltaria a apertar o Guardar no
    perfil real dela.
    """
    import pacotes
    from pacotes import a06_navegacao as mod

    assert "guardar-ponto" not in mod.SEM_GESTO, (
        "`guardar-ponto` voltou ao inventário do que não tem dono")
    for nome in ("guardar-ponto", "fechar-ponto"):
        assert pacotes.gesto_da_pagina(PAGINA, nome) is not None, (
            f"o gesto {nome!r} não está registrado — o piloto o recusaria "
            "pelo nome, e o clique dela voltaria a não produzir nada")
    assert (PAGINA, "guardar-ponto") in pacotes.perigosos(), (
        "`guardar-ponto` grava perfil e não está entre os perigosos — a prova "
        "de clique do piloto escreveria no perfil real de quem a rodasse")

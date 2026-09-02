#!/usr/bin/env python3
"""O DESPACHANTE: uma função de pacote por aba, e um contrato só para as dez.

DECISÃO DELA, 01/09/2026, e ela recusou a alternativa com estas palavras:

    "se vc achar melhor, ao invés de agentes, você mesmo vai conectando tudo aba
     a aba. e olhando o arquivo de specs.html — lá já temos até a parte do BT
     mapeada."

O plano de uma hora previa oito agentes, um por aba. A razão de NÃO ir por ali é
medida, e são três:

1. **O plano é anterior à leva que mudou as dez abas.** Ele foi escrito em 31/08
   às ~20h; depois disso a mesa virou dois conectados e dois lugares vazios, os
   rótulos mudaram, a fita virou "Selecionar:" e a janela foi para 777px. Os
   pilotos que os agentes leriam apontam endereços que essa leva moveu — oito
   agentes sobre premissa velha entregam oito pacotes que não pintam, e a régua
   só acusaria no fim.
2. **O teto de sessão.** O próprio plano registra: em 31/08, **37 de 40 agentes
   morreram** por isso, e a auditoria mais importante do dia ficou 3/39.
3. **O defeito mais comum do dia atravessava abas.** "Frase que nomeia um
   controle fora da mesa" apareceu QUATRO vezes — na Iluminação, na Navegação, na
   Conexões e na Sistema — e só foi visto porque as abas irmãs estavam na mesma
   cabeça. Um agente por aba não enxerga o que se repete entre abas.

O CONTRATO, e ele é o que impede a integração de virar um segundo projeto:

    def pacote(ctx: Contexto) -> dict[str, object]

Uma função por página. Ela recebe o que o daemon respondeu, já mastigado, e
devolve **endereço → valor**: o que a pintura consome. Nenhuma função de pacote
toca GTK, WebView ou IPC — elas são puras, e é por isso que dá para testá-las
sem abrir janela.

DE ONDE VEM O ENDEREÇO DE CADA VALOR, e é a parte que ela apontou: o
`docs/data/mapa-controles.csv` (308 linhas, o mesmo que gera o `specs.html`) diz,
para cada peça do controle, o canal, o `report_id` e o comando **por transporte**
— e se ela ACIONA no cabo e no rádio. Um valor de tela sem linha lá é um valor
sem dono, e o `pacotes/mapa.py` recusa inventar.
"""
from __future__ import annotations

import pathlib
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

#: OS DOIS CONTRATOS DESTE MÓDULO, ditos uma vez. Eles nasceram em 01/09/2026,
#: quando a interface entrou no `src/` e passou a ser conferida pelo `mypy` em
#: modo `strict` como todo o resto do pacote — os outros 285 arquivos já
#: passavam. Sem eles, os decoradores ficam sem tipo e o `mypy` marca as 50
#: funções que eles decoram como "untyped by decorator": 59 erros que somem
#: escrevendo estas duas linhas.
#:
#: `Any` no lugar da ponte é HONESTO, e não preguiça: a régua injeta um dublê
#: que responde a qualquer nome de propósito (ver `PonteDeMentira`), e um
#: `Protocol` com as 38 funções da ponte seria uma SEGUNDA lista que
#: envelheceria calada — o defeito que esta casa persegue. Quem confere que o
#: nome existe é `test_nenhum_gesto_chama_funcao_que_a_ponte_nao_tem`, contra a
#: ponte de verdade.
Pintura = Callable[["Contexto"], "dict[str, Any]"]
Gesto = Callable[["Contexto", "dict[str, Any]", Any], "dict[str, Any] | None"]

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))


@dataclass
class Contexto:
    """O que toda função de pacote recebe. É o mesmo para as dez.

    `state` é a resposta crua do daemon; os outros três são o que o piloto já
    mastigava para a Controles, e que passam a servir todas:

    * `mesa` — os controles da bancada, na ordem, com `uniq` e cor;
    * `conectados` — só os que estão de fato aqui. **Toda frase que promete
      alcance conta ESTES**, e não a mesa: o defeito de nomear um controle que
      não está apareceu quatro vezes em 31/08;
    * `estados` — o estado vivo por `uniq` (sticks, botões, sensores).
    """

    state: dict[str, Any]
    mesa: list[dict[str, Any]] = field(default_factory=list)
    conectados: list[dict[str, Any]] = field(default_factory=list)
    estados: dict[str, Any] = field(default_factory=dict)

    def por_uniq(self, uniq: str) -> dict[str, Any]:
        """A entrada do daemon daquele controle, ou `{}` — nunca levanta.

        Levantar aqui derrubaria a pintura da aba INTEIRA por causa de um
        controle que caiu no meio do tique, e a tela ficaria congelada sem dizer
        por quê. O `{}` faz o valor virar travessão, que é o que a tela sabe
        mostrar.
        """
        for e in self.conectados:
            if str(e.get("uniq") or "") == uniq:
                return e
        return {}


#: AS DEZ PÁGINAS E QUEM AS PINTA. A chave é o nome do arquivo, porque é o que o
#: `load-changed` do WebView entrega — o piloto sabe em que página está, não em
#: que "aba" no sentido do produto.
#:
#: `None` quer dizer **ainda não ligada**, e é diferente de ausente: a régua
#: `test_o_despachante_serve_as_dez.py` conta as duas coisas separadas e é ela
#: que diz, a cada rodada, quanto falta. Uma aba que sai desta tabela some da
#: contagem e a régua fica verde por VACUIDADE — que é o pior estado.
PACOTES: dict[str, Pintura] = {}


def registrar(pagina: str) -> Callable[[Pintura], Pintura]:
    """Decorador: `@registrar("01-jogar.html")` põe a função na tabela.

    POR QUE DECORADOR, e não um dicionário escrito à mão: o dicionário obriga a
    escrever o nome da página duas vezes — no módulo e na tabela — e é o segundo
    lugar que diverge. Aqui o módulo declara a si mesmo, e importar é registrar.
    """
    def dentro(fn: Pintura) -> Pintura:
        if pagina in PACOTES:
            raise SystemExit(f"ERRO: {pagina} já tem pacote ({PACOTES[pagina].__module__}). "
                             f"Dois donos para a mesma página é o defeito que este "
                             f"despachante existe para impedir.")
        PACOTES[pagina] = fn
        return fn
    return dentro


#: OS GESTOS, e a chave é `(página, nome)`. Cada pacote declara OS SEUS, no
#: próprio arquivo, com `@gesto(...)` — do mesmo jeito que `@registrar` declara
#: quem pinta.
#:
#: POR QUE NÃO UM DICIONÁRIO ESCRITO À MÃO, e a razão é de processo: a lista dos
#: gestos com dono vivia num dicionário único dentro do piloto, e ligar as dez
#: abas em paralelo significaria oito pessoas editando a MESMA linha. Com o
#: decorador, cada aba tem território exclusivo: quem liga a Iluminação toca só
#: `a04_iluminacao.py`, e não há merge a resolver.
GESTOS: dict[tuple[str, str], Gesto] = {}


def gesto(pagina: str, nome: str) -> Callable[[Gesto], Gesto]:
    """Decorador: `@gesto("04-iluminacao.html", "cor")` liga um botão.

    A função recebe `(ctx, o, ipc)`:

    * `ctx` — o mesmo `Contexto` da pintura: mesa, conectados, estado do daemon;
    * `o` — o clique como o JS o mandou (`texto`, `campo`, `player`, `lado`…);
    * `ipc` — o carimbo para falar com o daemon: `ipc("profile.switch", name=…)`.

    O `ipc` É INJETADO, e não importado: sem ele a função abriria um socket, e
    uma função que abre socket não se testa sem daemon. Com ele, a régua passa
    um `ipc` de mentira e cobra QUAL método foi chamado e com quais parâmetros —
    que é a única forma de provar que o botão faz o que promete, em vez de
    provar que ele existe.
    """
    def dentro(fn: Gesto) -> Gesto:
        chave = (pagina, nome)
        if chave in GESTOS:
            raise SystemExit(
                f"ERRO: o gesto {nome!r} de {pagina} já tem dono "
                f"({GESTOS[chave].__module__}). Dois donos para o mesmo botão é "
                f"o defeito que este despachante existe para impedir.")
        GESTOS[chave] = fn
        return fn
    return dentro


def gesto_da_pagina(pagina: str, nome: str) -> Gesto | None:
    """Quem atende aquele botão, ou `None`.

    `None` NÃO é erro: é o estado honesto de um botão que ainda não foi ligado,
    e quem chama tem de **recusar dizendo**. Um botão que responde calado quando
    não há quem atenda é a `A-CASA-SABE-E-O-PRODUTO-NAO-FAZ` em miniatura —
    quem clicou conclui que funcionou.
    """
    return GESTOS.get((pagina, nome)) or GESTOS.get(("*", nome))


def pacote_da_pagina(pagina: str, ctx: Contexto) -> dict[str, Any] | None:
    """O pacote daquela página, ou `None` se ela ainda não tem quem a pinte.

    `None` NÃO é erro: é o estado honesto de uma aba que ainda não foi ligada, e
    o piloto o distingue de um pacote vazio — um diz "ninguém pinta isto ainda",
    o outro diz "pintei nada", e confundir os dois é como uma tela morta passa
    por tela sem novidade.

    COM A MESA VAZIA ELE ACRESCENTA O MOLDE (ver `molde_do_lugar`), e é a única
    coisa que este despachante põe num pacote que não é dele: sem controle
    nenhum a aba não emite coluna nenhuma, e sem coluna a tela fica com o
    desenho — "P1 · Cosmic Red · USB · 100%" com zero controles na mesa.
    """
    fn = PACOTES.get(pagina)
    if fn is None:
        return None
    fora = fn(ctx)
    molde = molde_do_lugar(pagina, ctx, fora)
    if not molde:
        return fora
    colunas = dict(fora.get(POR_CONTROLE[0]) or {})
    colunas[LUGAR_SEM_DONO] = molde
    return {**fora, POR_CONTROLE[0]: colunas}


#: AS TRÊS PALAVRAS PARA A MESMA COISA. Cada aba nasceu com a sua — `cartoes` na
#: Jogar, `cards` na Controles, `colunas` nas outras sete — porque cada uma foi
#: escrita olhando o desenho dela, e o desenho as chama assim.
#:
#: NÃO SE UNIFICA NO PACOTE, e a razão é dela: as funções falam a língua da aba
#: que servem, e renomear `cartoes` para `colunas` na Jogar afastaria o código
#: do desenho sem ganhar nada. Unifica-se AQUI, na saída, que é onde o piloto lê.
POR_CONTROLE = ("colunas", "cartoes", "cards")

#: O que NUNCA é valor de tela: a contagem da régua e a lista de órfãos. As duas
#: são metadado do pacote e pintá-las escreveria "{'pintados': 25}" numa caixa.
NAO_SAO_VALOR = {"cobertura", "sem_dono"}

# ---------------------------------------------------------------------------
# O ESTADO VAZIO — a tela mente quando a mesa esvazia
# ---------------------------------------------------------------------------
# FOTOGRAFADO em 02/09/2026, com um dublê de estado sem controle nenhum
# (`mesa_viva.estado_do_daemon` devolvendo `controllers: []`, para não
# desconectar o controle dela): o topo dizia `0 controles: 0 USB · 0 BT` e a
# MESMA tela mostrava `P1 · Cosmic Red · USB` com bateria 100%, touchpad
# "Tocando", barra de luz `#7EB8D4`, microfone `ATIVO` e um `P2 · Starlight
# Blue · BT · 64%`. Nada disso existia. Medido pela régua do mockup, a mesma
# árvore, só mudando a mesa (`--prova-de-mockup --voltas-por-aba 8`):
#
#     ANTES   mesa VAZIA (0 controles)  330: 114 PRODUTO · 179 MOCKUP · 37 IND
#     DEPOIS  mesa VAZIA (0 controles)  330: 184 PRODUTO · 109 MOCKUP · 37 IND
#     mesa CHEIA (2 controles)          330: 188 PRODUTO ·  68 MOCKUP · 74 IND
#                                       (igual antes e depois — o molde se cala
#                                        quando há dono)
#
# A CAUSA, e ela não é de nenhuma das dez abas: o piloto já apaga os lugares
# sem dono (`hefesto_vivo.py:1005-1016`), mas as CHAVES que ele apaga são a
# união do que as colunas VIVAS trouxeram — e com zero controles não há coluna
# viva nenhuma. `set()` de chaves faz `dict.fromkeys(chaves, "—")` devolver
# `{}`, e o desenho fica inteiro na tela.
#
# O QUE A GTK FAZIA, e é a razão de esta cura ser de MIGRAÇÃO e não de
# invenção: lá o card só existe enquanto o controle existe —
# `status_actions.py:1516` ("Remove todos os cards"). O HTML não tem essa
# saída: o desenho publica QUATRO lugares fixos, por decisão dela em 31/08. O
# equivalente aqui é o travessão, que é a palavra que o PRÓPRIO desenho usa nos
# lugares vazios (`paginas/02-controles.html:2089-2096`, o P3 com
# `<span class="leia">—</span>` e `<span class="bat">—</span>`). Nenhum texto
# novo nasce nesta cura.

#: A CHAVE RESERVADA DA COLUNA-MOLDE. Ela NÃO é um lugar: nenhuma página tem
#: `data-controle="*"`, então o `querySelectorAll` do piloto devolve zero
#: elementos e o molde não escreve nada por si.
#:
#: E É EXATAMENTE POR ISSO QUE ELE É `*` E NÃO `p1`/`p2`. Emitir o vazio
#: direto nas colunas dos lugares sem dono APAGARIA A MOLDURA: o piloto calcula
#: `apagar = TODOS_OS_LUGARES - set(carga["colunas"])` e só marca
#: `data-conectado="nao"` / classe `off` no que sobra dessa conta
#: (`hefesto_vivo.py:1008-1016`). Com `p1`…`p4` ocupados pelo molde, a conta dá
#: lista vazia e os quatro lugares ficariam com a moldura de CONECTADO — meio
#: apagado, que é pior que aceso. Sob `*` a conta continua dando os quatro, o
#: piloto escreve o travessão em todos E acende a moldura de vazio.
#:
#: `*` é a mesma reserva que os gestos do rodapé já usam (`GESTOS[("*", nome)]`
#: — "de todas as abas"), e não um segundo vocabulário.
LUGAR_SEM_DONO = "*"

#: O CONTROLE DE MENTIRA que a aba responde para dizer QUAIS campos um lugar
#: tem. Ele traz o `uniq` e nada mais **de propósito**: o molde precisa dos
#: NOMES dos campos, e um dublê com valores plausíveis faria a aba emitir a
#: bateria de um controle que não existe. Sem valor nenhum, toda aba cai no
#: caminho de "não sei" — que é o caminho certo para um lugar vazio.
#:
#: O `uniq` é da faixa SINTÉTICA da casa (`aabbcc`), nunca da bancada dela —
#: há dois portões de anonimato nesta árvore.
_CONTROLE_DE_MENTIRA: dict[str, Any] = {"uniq": "aa:bb:cc:00:00:00", "connected": True}

#: O LUGAR DE MENTIRA na mesa, e ele precisou existir: a `05-vibracao` não
#: percorre `ctx.conectados` — ela delega a `app/telas/vibracao.pacote_da_mesa`,
#: que percorre a MESA. Sem esta entrada o molde dela saía vazio e os sete
#: campos do lugar (`mult`, `motor-e`, `motor-d`, as três barras, `identidade`)
#: continuavam mostrando o desenho. Medido em 02/09/2026, comparando o molde das
#: dez abas com o `casamento.do_pacote`: nove batiam e só a Vibração dava zero.
#:
#: `jogador`, `nome` e `via` vêm em `None` — não é desleixo. São as três chaves
#: que `app/telas/vibracao.pacote_da_coluna:223-224` lê por COLCHETE, e sem elas
#: aquela função levanta `KeyError`. O valor tinha de ser algo que não se
#: confunda com dado: `None` atravessa a `f-string`, o molde joga fora a
#: identidade montada com ele, e se um dia vazar para a tela lerá "PNone" — que
#: ninguém confunde com um controle de verdade.
_LUGAR_DE_MENTIRA: dict[str, Any] = {
    "uniq": _CONTROLE_DE_MENTIRA["uniq"], "pref": "p1",
    "jogador": None, "nome": None, "via": None,
}

#: O molde já calculado, por página e por perfil ativo. O perfil entra na chave
#: porque a Gatilhos nomeia os ajustes do PERFIL (`aj-nome-e-0`…): trocar de
#: perfil com a mesa vazia troca os campos que o lugar tem, e um cache só por
#: página serviria o molde do perfil anterior.
_MOLDE: dict[tuple[str, str], dict[str, str]] = {}

#: O que a tela escreve onde não há dado. TEXTO DE TELA É DELA, e este não é
#: novo: é o mesmo caractere que o desenho já põe nos lugares P3/P4 e que o
#: `escrever()` do piloto já escreve em `null`/`""`.
#:
#: Está aqui como literal, e não importado da `regua_do_mockup.TRAVESSAO`,
#: porque o produto não depende de instrumento de medição. Quem impede as duas
#: grafias de divergirem é `test_o_molde_escreve_o_travessao_do_desenho`, que
#: procura este caractere DENTRO do lugar vazio da página publicada.
TRAVESSAO = "—"


#: OS DOIS ALVOS QUE O TRAVESSÃO NÃO ATENDE, e os dois foram medidos, não
#: supostos (02/09/2026, com o dublê de mesa vazia sobre a `02-controles`):
#:
#: `largura` — o `escrever()` do piloto monta `el.style.width = "—%"`, que o
#:   CSSOM RECUSA. A barra fica na largura do mockup e, como `el.style.width`
#:   nunca volta igual ao que se escreveu, o contador de pintura soma +1 por
#:   barra POR TIQUE, para sempre. Um contador que mente é pior que um campo
#:   parado — é o mesmo defeito que fez o `<select>` ganhar guarda no piloto.
#:   Com as barras no molde, a `02-controles` relatava 25 valores a cada um dos
#:   13 tiques; sem elas, ela pinta uma vez e sossega.
#: `html`  — o alvo escreve `innerHTML`, e um travessão APAGA a marcação: os
#:   quatro botões de jogador da Iluminação (`players`) e a explicação do teto
#:   da Conexões (`teto-explica`) viram um traço. O desenho não faz isso no
#:   lugar vazio dele.
#:
#: `valor` FICA, e é de propósito: num `<select>` o piloto só escreve o que o
#: campo oferece, então o travessão é no-op onde não há opção `—` e acerta onde
#: houver. Nada quebra, e nada precisa ser lembrado no dia em que o desenho
#: ganhar essa opção.
ALVOS_QUE_O_TRAVESSAO_NAO_ATENDE = {"largura", "html"}

_ENDERECO_NO_HTML = re.compile(r'data-(?:campo|papel|hef)="([^"]+)"')
_ALVO_NO_HTML = re.compile(r'data-hef-alvo="([^"]+)"')
_ELEMENTO_NO_HTML = re.compile(r"<[A-Za-z][^>]*>")
_LUGAR_NO_HTML = re.compile(r'data-controle="(p\d+)"')

#: Os lugares de controle de cada página publicada, lidos uma vez.
_LUGARES: dict[str, frozenset[str]] = {}


def lugares_da_pagina(pagina: str) -> frozenset[str]:
    """Os `data-controle="pN"` da página PUBLICADA — os lugares do desenho.

    ELA É A TRAVA DE SEGURANÇA DO MOLDE, e a razão é medida. `molde_do_lugar`
    roda a pintura da aba uma segunda vez, com um controle de mentira; o
    despachante promete no alto deste arquivo que as pinturas são PURAS.
    **Não são todas.** `a10_perfis._uma_vez_so:214` guarda `_PINTADO_PARA` e
    `_ULTIMO_TIQUE` em módulo para não repintar os três campos que ELA DIGITA
    (nome, jogo, estilo) enquanto ela digita. Uma segunda chamada no mesmo tique
    troca o `_PINTADO_PARA`, e no tique seguinte o produto volta a escrever por
    cima do que ela estava escrevendo — que é exatamente o defeito que aquela
    função existe para impedir.

    A `10-perfis` não tem lugar de controle nenhum, então não tem molde a fazer:
    esta trava a poupa da segunda chamada. O mesmo vale para a `09-sistema` e a
    `07-lancadores`.

    Achado em 02/09/2026 por `test_o_casamento_das_dez`, que passava sozinho e
    reprovava depois desta régua rodar — a marca de estado de módulo vazando
    entre testes.
    """
    lembrado = _LUGARES.get(pagina)
    if lembrado is not None:
        return lembrado
    from hefesto_dualsense4unix.interface import onde

    try:
        doc = onde.pagina(pagina, publicado=True).read_text(encoding="utf-8")
    except OSError:
        return frozenset()
    fora = frozenset(_LUGAR_NO_HTML.findall(doc))
    _LUGARES[pagina] = fora
    return fora

#: `pagina` → `{endereço: os alvos daquele endereço}`.  # noqa-acento (nome do parametro)
#: Lido uma vez por página.
_ALVOS: dict[str, dict[str, set[str]]] = {}


def alvos_da_pagina(pagina: str) -> dict[str, set[str]]:
    """Com que alvo cada endereço da página PUBLICADA é escrito.

    LER A PÁGINA AQUI NÃO É O MESMO que tirar dela a LISTA de campos — e a
    diferença é o que separa esta cura da destruição que `molde_do_lugar`
    descreve. A lista de campos sai da aba, que sabe o que é dado; a página só
    responde **como** cada endereço é escrito, que é informação que só ela tem
    (`data-hef-alvo` é atributo do desenho).

    Vazio quando a página não abre — e aí `molde_do_lugar` desiste, porque sem
    saber como a página escreve o molde escreveria travessão numa barra.
    """
    lembrado = _ALVOS.get(pagina)
    if lembrado is not None:
        return lembrado
    from hefesto_dualsense4unix.interface import onde

    try:
        doc = onde.pagina(pagina, publicado=True).read_text(encoding="utf-8")
    except OSError:
        return {}
    fora: dict[str, set[str]] = {}
    for elemento in _ELEMENTO_NO_HTML.findall(doc):
        endereco = _ENDERECO_NO_HTML.search(elemento)
        if endereco is None:
            continue
        alvo = _ALVO_NO_HTML.search(elemento)
        fora.setdefault(endereco.group(1), set()).add(
            alvo.group(1) if alvo else "texto")
    _ALVOS[pagina] = fora
    return fora


def chaves_por_controle(pacote: dict[str, Any]) -> set[str]:
    """Os campos que este pacote emite POR CONTROLE, nas três palavras.

    Só escalar entra: um `dict` ou uma `list` de dicionários é estrutura, e o
    `normalizar` já os descarta antes da tela.
    """
    fora: set[str] = set()
    for nome in POR_CONTROLE:
        for campos in (pacote.get(nome) or {}).values():
            if not isinstance(campos, dict):
                continue
            fora |= {str(k) for k, v in campos.items()
                     if not isinstance(v, (dict, list))}
    return fora


def molde_do_lugar(
    pagina: str, ctx: Contexto, pacote: dict[str, Any] | None = None
) -> dict[str, str]:
    """Quais campos um lugar de controle desta aba tem, todos no travessão.

    Vazio (`{}`) quando não há o que fazer — que é o caso comum: **com pelo
    menos UMA coluna viva o piloto já se vira**, porque a união das chaves
    vivas é justamente o que ele apaga nos lugares sem dono.

    DE ONDE SAI A LISTA DE CAMPOS, e a resposta ÓBVIA está errada. O caminho
    natural seria ler os `data-campo` de dentro do `[data-controle="pN"]` da
    página publicada — é o que `a03_gatilhos._casas_e_barras()` faz para contar
    casas. **Medido nas dez páginas publicadas de 02/09/2026: isso destrói a
    tela.** Dentro do lugar da `05-vibracao` há `data-papel="testar"` e
    `data-papel="parar"` — os dois BOTÕES —, quatro `data-papel="forca"` que são
    os rótulos `Economia`/`Balanceado`/`Máximo`/`Auto`, e um
    `data-papel="desenho"` com 231 filhos, que é o SVG do controle. Escrever
    travessão neles apagaria os botões e o desenho: é o mesmo defeito que a
    Vibração cometeu em 01/09, quando escreveu `balanceado` dentro dos quatro
    degraus.

    Quem sabe separar DADO de DESENHO é a própria aba: ela emite exatamente os
    campos que são dado. Então o molde pergunta a ela — roda a pintura com UM
    controle de mentira e fica com os NOMES, jogando fora os valores. Por
    construção, o molde nunca alcança um endereço que a aba não pinta.

    A pintura é pura por contrato (nenhuma toca GTK, WebView ou IPC), então
    rodá-la duas vezes não tem efeito nenhum além do custo — e o custo fica no
    `_MOLDE`. Se ela levantar, o molde é `{}`: uma aba que não responde não
    perde a pintura de verdade, que já aconteceu antes desta chamada.
    """
    if ctx.conectados:
        return {}
    pacote = pacote if pacote is not None else {}
    if chaves_por_controle(pacote):
        # A ABA JÁ EMITIU COLUNA sem controle nenhum (nenhuma faz isso hoje).
        # Se um dia fizer, a união dela é melhor que o molde — é dado de
        # verdade, e o piloto já a usa.
        return {}
    fn = PACOTES.get(pagina)
    if fn is None:
        return {}
    if not lugares_da_pagina(pagina):
        # PÁGINA SEM LUGAR DE CONTROLE não tem molde a fazer — e rodar a pintura
        # dela de novo NÃO É INÓCUO. Ver `lugares_da_pagina`.
        return {}
    chave = (pagina, str(ctx.state.get("active_profile")))
    lembrado = _MOLDE.get(chave)
    if lembrado is not None:
        return dict(lembrado)
    alvos = alvos_da_pagina(pagina)
    if not alvos:
        # A PÁGINA NÃO ABRIU. Sem saber com que alvo cada endereço é escrito, o
        # molde poria travessão numa barra — e uma barra com `width: "—%"` fica
        # na largura do mockup somando pintura para sempre. Desistir devolve a
        # tela ao estado de antes desta cura, que é ruim mas não é falso.
        #
        # ANTES de rodar o fantasma, e não depois: aqui não há o que guardar no
        # `_MOLDE`, então a ordem inversa pagaria uma pintura inteira POR TIQUE
        # numa página que não vai dar molde nenhum.
        return {}
    fantasma = Contexto(
        state=ctx.state, mesa=[dict(_LUGAR_DE_MENTIRA)],
        conectados=[dict(_CONTROLE_DE_MENTIRA)], estados=dict(ctx.estados))
    try:
        seria = fn(fantasma)
    except Exception:
        # UMA ABA QUE LEVANTA NÃO DERRUBA A PINTURA. A de verdade já rodou e já
        # deu certo antes desta chamada; o que se perde aqui é só o molde dela.
        seria = {}
    molde = dict.fromkeys(
        sorted(k for k in chaves_por_controle(seria)
               if not (alvos.get(k, set()) & ALVOS_QUE_O_TRAVESSAO_NAO_ATENDE)),
        TRAVESSAO)
    _MOLDE[chave] = molde
    return dict(molde)


def topo(ctx: Contexto) -> dict[str, Any]:
    """Os três valores do CABEÇALHO, que são iguais nas dez abas.

    A contagem de controles e o nome do perfil ativo vivem no `topo.html`, que é
    um só para as dez páginas — logo não pertencem a pacote nenhum. Medido em
    01/09/2026: `conta`, `conta-b` e `perfil` apareciam como campos VAZIOS em
    todas as abas, porque cada função de pacote cuidava da sua aba e ninguém
    cuidava do que era de todas.

    A contagem sai do `mesa_viva.texto_da_contagem`, que já é dona dela e
    devolve as duas metades separadas — o desenho põe a segunda em `<b>`, e
    escrever a frase inteira num `textContent` apagaria a tag.
    """
    from hefesto_dualsense4unix.interface import mesa_viva

    conta, conta_b = mesa_viva.texto_da_contagem(ctx.mesa)
    return {
        # O `●` é do desenho e já está na página; o texto começa depois dele.
        "conta": conta.replace("● ", "").strip(),
        "conta-b": conta_b,
        "perfil": ctx.state.get("active_profile") or "—",
    }


# ---------------------------------------------------------------------------
# OS DONOS DE FATO — um por pergunta que a tela faz sobre UM controle
# ---------------------------------------------------------------------------
# ROTA-A + ROTA-C (02/09/2026). Estas funções existem porque o levantamento
# abaixo mediu a assinatura que a migração da GTK para o HTML deixou: **o HTML
# lendo UMA chave onde a GTK lia DUAS**, ou não lendo nenhuma.
#
# O levantamento, feito varrendo `.get("<chave>")` nas duas árvores (02/09/2026,
# na ponta de `dev` 2b219284) — as dezoito chaves que o daemon publica por
# controle, contadas em `app/{widgets,actions,telas}` contra `interface/pacotes`:
#
#     chave                GTK  HTML   veredito
#     player_slot            6     1   <- a assinatura: `jogador_de`
#     player                10     7
#     vpad_motivo            1     0   <- SÓ A GTK LÊ: `degradacao_de`
#     nascimento             2     0   <- SÓ A GTK LÊ: sem dono ainda (ver abaixo)
#     connected              6     0      não é perda: `ctx.conectados` já filtrou
#     serial/modelo/…        —     —      nasceram nesta onda (ROTA-A)
#
# `nascimento` (SINAL-NO-NASCIMENTO-01) fica SEM dono de propósito: é chave
# ÚNICA, não a assinatura de duas, e quem a consome é o botão "A luz não acende"
# da aba Conexões — território de outra onda. Está escrito aqui para que a
# próxima leva não precise refazer a varredura.


def jogador_de(c: dict[str, Any]) -> int | None:
    """Que jogador é este controle — o NÚMERO que a tela mostra, ou ``None``.

    O daemon publica DUAS chaves: ``player_slot`` (a posição de sessão, que o
    PRODUTO decide e que sobrevive a desconectar e reconectar) e ``player`` (o
    número do jogador que o JOGO vê). A GTK sempre leu a primeira para o número
    do card (``app/actions/base.numero_do_controle``); o HTML lia só a segunda.

    **CORREÇÃO DE FATO, medida em 02/09/2026 com os dois controles na mesa.** O
    MAPA e a ROTA-C diziam *"no rádio o `player` volta None"*. **Não é o
    transporte.** O que se mediu foi:

        uniq 444648000003 · bt  · player 1    · player_slot 1 · is_primary TRUE
        uniq d42f4b0000d8 · usb · player None · player_slot 2 · is_primary false

    O ``None`` está no controle do CABO. A condição real está escrita em
    ``daemon/subsystems/coop.CoopManager.player_indexes``: *"Só entra quem o
    jogo enxerga: um secundário ainda aguardando o grab não tem vpad —
    reservou o índice, mas não é jogador nenhum até ser promovido."* Confirmado
    no estado vivo: ``coop.enabled=true``, ``coop.players=1``, e a ``coop.mesa``
    tem UMA entrada — a do primário. **Quem volta ``None`` é quem não é jogador
    do co-op**, em qualquer transporte. Com o co-op DESLIGADO
    (``resolve_player_numbers``) todos os conectados são o jogador 1.

    **A ORDEM DAS CHAVES É A DA GTK** — ``player_slot`` primeiro. A régua
    ``test_os_donos_de_fato.py`` confere isso contra ``base.numero_do_controle``
    e reprova se aquela função deixar de ler ``player_slot`` na frente: as duas
    têm de mudar no mesmo commit.

    **O QUE ESTA FUNÇÃO NÃO HERDA DA GTK, e é deliberado:** o
    ``numero_do_controle`` cai em ``index + 1`` quando não há slot, e daí em 1.
    Isso é a POSIÇÃO — exatamente o que fez o mesmo controle mudar de nome
    quando o segundo entrou na mesa. Aqui a resposta é ``None``, e ``None`` vira
    travessão. Melhor calar que numerar por ordem de chegada.
    """
    for chave in ("player_slot", "player"):
        valor = c.get(chave)
        if valor is None:
            continue
        try:
            n = int(valor)
        except (TypeError, ValueError):
            continue
        if n > 0:
            return n
    return None


#: O que a mesa escreve quando a cor do plástico não foi lida
#: (`interface/mesa_viva.COR_DESCONHECIDA`). Repetido aqui como literal para não
#: importar `mesa_viva` — que puxa GTK pelo `actions/base` — só para comparar uma
#: string; a régua `test_os_donos_de_fato.py` confere que as duas são a MESMA.
NOME_SEM_LEITURA = "Não sei"

#: Como o transporte cru do daemon se escreve na tela. É a MESMA tradução do
#: `mesa_viva.mesa_do_estado` (`"USB" if transporte == "usb" else "BT"`).
VIA_DO_TRANSPORTE = {"usb": "USB", "bt": "BT"}


def identidade_de(
    c: dict[str, Any], mesa: list[dict[str, Any]] | None = None
) -> str:
    """O nome deste controle na tela, ou o travessão.

    Ordem: **o que ELA nomeou > o modelo decodificado > o transporte só.**
    NUNCA a posição — foi o que fez o mesmo controle mudar de nome quando o
    segundo entrou na mesa (ROTA-A, medido em 02/09/2026: com um controle o do
    cabo era "Starlight Blue"; com dois, o MESMO cabo virou "Cosmic Red").

    As quatro fontes, em ordem, e por que são quatro:

    1. ``nome_declarado`` — a declaração dela em ``maquina.json``, publicada
       pelo daemon. Vence tudo: ela é a dona do nome do aparelho dela;
    2. ``modelo`` — o nome de fábrica que o daemon decodificou do serial;
    3. ``mesa[…]["nome"]`` — **o MESMO fato pela outra porta**, e ele fica
       porque é o que funciona HOJE: o ``mesa_viva.LeitorDeCor`` já lê a cor do
       plástico pelo broker, uma vez por endereço, e o piloto já a tem na mão.
       As chaves 1 e 2 só existem depois que o daemon dela for reiniciado — e
       reiniciá-lo não é ato meu. Sem esta linha, ligar o dono novo seria
       REGRESSÃO para a aba Jogar, que hoje usa a mesa;
    4. o transporte sozinho — "USB"/"BT". É pouco, mas é verdade, e é o que a
       tela pode afirmar sem inventar.

    ``"Não sei"`` vindo da mesa **não** é nome: é a ausência de leitura, e
    passá-lo adiante poria "Não sei · USB" onde cabia "USB".
    """
    declarado = c.get("nome_declarado")
    if isinstance(declarado, str) and declarado.strip():
        return declarado.strip()

    modelo = c.get("modelo")
    if isinstance(modelo, str) and modelo.strip():
        return modelo.strip()

    uniq = str(c.get("uniq") or "")
    for item in mesa or []:
        if str(item.get("uniq") or "") != uniq:
            continue
        nome = item.get("nome")
        if isinstance(nome, str) and nome.strip() and nome.strip() != NOME_SEM_LEITURA:
            return nome.strip()
        break

    via = VIA_DO_TRANSPORTE.get(str(c.get("transport") or "").lower(), "")
    return via or "—"


def degradacao_de(c: dict[str, Any]) -> str:
    """A frase "Emulação degradada (uinput): …", ou ``""`` quando não há.

    DUAS CHAVES, e o levantamento acima mostrou que o HTML não lia NENHUMA das
    duas em conjunto: ``vpad_backend`` (que a aba Controles lê sozinho) e
    ``vpad_motivo`` (que nenhum pacote lia). Sozinho, o backend não separa
    "degradou" de "é uinput por design" — a máscara Xbox é uinput e não é
    defeito nenhum.

    **DELEGA para ``app/widgets/controller_card.texto_degradacao``**, que é o
    dono da regra na GTK e traduz o motivo técnico para a frase leiga
    (``MOTIVOS_DEGRADACAO_LEIGOS``). Reescrever a tabela aqui criaria uma
    segunda lista de motivos, que envelheceria calada no primeiro motivo novo
    que o daemon publicasse. O import é LAZY e não custa GTK: aquele módulo só
    puxa ``gi`` dentro de uma função, bem depois.

    ``""`` e não ``None``: o valor vai para um ``data-campo``, e a pintura
    escreve string.
    """
    from hefesto_dualsense4unix.app.widgets.controller_card import texto_degradacao

    return texto_degradacao(c) or ""


def normalizar(pacote: dict[str, Any], para_pref: dict[str, str] | None = None) -> dict[str, Any]:
    """O pacote na forma que a tela consome: `{mesa, colunas, blocos}`.

    O `blocos` É CHAVE DE CONTRATO, não valor de campo — e ficou DOIS DIAS
    fora daqui, calado. O `BOOTSTRAP` do piloto sabe consumi-lo desde 01/09
    (`hefesto_vivo.py`, o laço `for(const [seletor, html] of
    Object.entries(p.blocos || {}))`), e `a08_conexoes.py` o emite para trocar
    o mapa do gabinete DELA inteiro — mas o ramo `isinstance(valor, dict):
    continue` abaixo o comia antes de chegar ao JS, porque um `dict` de HTML
    parece um valor estruturado e não é.

    MEDIDO em 02/09/2026, e por QUATRO frentes independentes desta leva, cada
    uma pelo seu lado: `normalizar({"blocos": {".mm-faces": "<b>x</b>"}})`
    devolvia `['colunas', 'mesa']`. O mapa do gabinete e a lista de aparelhos
    da aba Conexões nunca chegaram à tela pelo tique — e nada acusava, que é a
    forma exata do defeito que esta casa chama de *ausência de notícia lida
    como sucesso*.

    POR QUE ELA EXISTE, medido em 01/09/2026 na primeira execução do piloto
    único: a aba Jogar pintou **0 valores** com um pacote de cinco. O piloto lia
    `colunas` e `mesa`; o pacote da Jogar devolvia `cartoes` e punha `perfil`,
    `conta` e `conta_b` na RAIZ. Nada casava, e nada acusava — a pintura
    devolvia zero sem uma linha de erro, que é a forma exata do defeito que esta
    casa chama de *ausência de notícia lida como sucesso*.

    `para_pref` traduz `uniq → pref`. O daemon endereça por `uniq` (`d4:2f:00:00:…`) e
    o desenho por `pref` (`p1`), que é o que o `data-controle` das páginas traz.
    Sem a tradução o `querySelector` procura um MAC numa página que só conhece
    `p1` e devolve `null` — zero escrito, zero erro.
    """
    para_pref = para_pref or {}
    colunas: dict[str, dict[str, Any]] = {}
    for nome in POR_CONTROLE:
        for chave, valores in (pacote.get(nome) or {}).items():
            if not isinstance(valores, dict):
                continue
            # O `uniq` do daemon vem com e sem os dois-pontos conforme a aba;
            # as duas formas procuram a mesma tradução.
            pref = para_pref.get(chave) or para_pref.get(_so_hex(chave)) or chave
            colunas.setdefault(pref, {}).update(valores)

    mesa = dict(pacote.get("mesa") or {})
    for chave, valor in pacote.items():
        if chave in NAO_SAO_VALOR or chave in POR_CONTROLE or chave == "mesa":
            continue
        # UMA LISTA DE ESCALARES PASSA: a tela a distribui por N blocos iguais
        # (os achados do exame, os perfis). Uma lista de dicionários não — ela
        # é estrutura, e escrever `[object Object]` numa caixa é pior que nada.
        if isinstance(valor, list):
            if valor and all(not isinstance(x, (dict, list)) for x in valor):
                mesa.setdefault(chave, valor)
            continue
        if isinstance(valor, dict):
            continue
        mesa.setdefault(chave, valor)
    # O `blocos` atravessa INTACTO, e é o único `dict` que atravessa: quem o
    # emite endereça por SELETOR CSS (`.mm-faces`), não por `data-campo`, e o
    # valor é HTML pronto. Passar pelo laço acima o descartaria.
    fora: dict[str, Any] = {"mesa": mesa, "colunas": colunas}
    blocos = pacote.get("blocos")
    if isinstance(blocos, dict) and blocos:
        fora["blocos"] = blocos
    return fora


def _so_hex(chave: str) -> str:
    """`d42f4b0000d8` → o mesmo, e `d4:2f:00:00:…` → `d42f…`. Uma forma só para casar."""
    return chave.replace(":", "").lower()


#: OS DEZ, IMPORTADOS PELO NOME — e a redundância com o `_carregar_tudo()` é
#: deliberada. Ele usa `importlib.import_module`, que é IMPORT DINÂMICO: o
#: `portao_a_casa_sabe_e_o_produto_nao_faz` segue o fecho de import lendo o
#: **AST**, e um nome montado em tempo de execução não aparece ali. Sem estas
#: linhas, os dez pacotes ficam fora do fecho a partir do piloto — e as camadas
#: de tela que eles chamam (`app/telas/vibracao.py`, `gui/aba_sistema.py`,
#: `app/actions/perfis_web.py`) continuam contando como promessa SEM CAMINHO
#: mesmo depois de ligadas. Medido em 01/09/2026.
#:
#: O `_carregar_tudo()` fica: ele é quem pega um pacote NOVO sem ninguém
#: precisar lembrar de escrever a linha. Estas dez são o que uma ferramenta que
#: lê código estático consegue ver.
from . import (  # noqa: E402
    a01_jogar,  # noqa: F401
    a02_controles,  # noqa: F401
    a03_gatilhos,  # noqa: F401
    a04_iluminacao,  # noqa: F401
    a05_vibracao,  # noqa: F401
    a06_navegacao,  # noqa: F401
    # A 07 FALTAVA AQUI, e a falta era exatamente o que este bloco existe para
    # impedir. A casa diz em dois lugares que ela é a aba SEM pacote
    # (`hefesto_vivo.SEM_PACOTE` e o comentário do `_tique`) — mas
    # `a07_lancadores.py:236` traz `@registrar("07-lancadores.html")` desde que
    # foi ligada, e `pacote_da_pagina` devolve 26 chaves para ela. Achado em
    # 02/09/2026 por um teste que assumiu a frase da casa e reprovou.
    a07_lancadores,  # noqa: F401
    a08_conexoes,  # noqa: F401
    a09_sistema,  # noqa: F401
    a10_perfis,  # noqa: F401
    rodape,  # noqa: F401
)


def _carregar_tudo() -> None:
    """Importa os módulos de pacote, que é o que os registra."""
    import importlib
    aqui = pathlib.Path(__file__).resolve().parent
    for f in sorted(aqui.glob("a[0-9][0-9]_*.py")):
        # `__name__` E NÃO A LITERAL `"pacotes"`: este módulo é importado com
        # DOIS nomes — `pacotes` (as réguas, que entram na pasta pelo
        # `sys.path`) e `hefesto_dualsense4unix.interface.pacotes` (o produto).
        # Com a literal, o carregamento a partir do produto criava uma SEGUNDA
        # cópia de cada módulo de aba, com um segundo registro de gestos — e o
        # piloto consultava um enquanto o decorador escrevia no outro.
        importlib.import_module(f"{__name__}.{f.stem}")
    # O RODAPÉ É DAS DEZ, e por isso não casa com `aNN_*`: ele mora no
    # `topo.html`, o esqueleto compartilhado, e seus gestos são registrados em
    # `("*", nome)`. Sem esta linha ele não é importado, logo não se registra,
    # logo os quatro botões do rodapé recusam em todas as abas — em silêncio,
    # porque um gesto não registrado é indistinguível de um gesto sem dono.
    importlib.import_module(f"{__name__}.rodape")


_carregar_tudo()

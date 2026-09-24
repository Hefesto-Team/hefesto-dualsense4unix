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

import html.parser
import pathlib
import re
import sys
from collections.abc import Callable, Iterable
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
    * `estados` — o estado vivo por `uniq` (sticks, botões, sensores);
    * `externos` — os controles que o Hefesto VÊ e NÃO adota (Nintendo Pro,
      8BitDo, Xbox). **Campo próprio, e nunca dentro de `conectados`** — ver a
      nota do campo.
    """

    state: dict[str, Any]
    mesa: list[dict[str, Any]] = field(default_factory=list)
    conectados: list[dict[str, Any]] = field(default_factory=list)
    estados: dict[str, Any] = field(default_factory=dict)
    #: OS CONTROLES QUE O HEFESTO SÓ VÊ — EXTERNOS-01, 06/09/2026, e ele fecha
    #: as linhas 16 e 305 de `docs/data/paridade-gtk-html.csv`.
    #:
    #: **CAMPO PRÓPRIO, E A ROTA DA SPRINT DIZ POR QUÊ:** *"nunca dentro de
    #: `controllers`"*. Os três campos acima são os ASSENTOS — quem tem `pref`
    #: (`p1`..`p4`), quem o co-op numerou, quem a fita escolhe como alvo de
    #: edição. Um externo não tem nada disso: o Hefesto não o adota, não lhe
    #: monta vpad e não escreve nele. Somá-lo a `conectados` faria o cabeçalho
    #: contar jogadores que não existem, a fita oferecer um alvo que nenhum
    #: gesto alcança e `apagar_os_lugares_sem_dono` disputar um cartão que não é
    #: dele — três defeitos por uma lista só.
    #:
    #: **DE ONDE ELE VEM, e não é o `state_full`:** o daemon publica esta lista
    #: SÓ em `controller.list {"external": true}` (`daemon/ipc_handlers.py:4850`),
    #: sob opt-in e fora do caminho quente, porque a enumeração de `/dev/input`
    #: mais a sonda de holders custa 10-40 ms e um subprocess. Quem pergunta é o
    #: piloto, no tique LENTO e com teto próprio (`hefesto_vivo._talvez_ler_os_externos`)
    #: — a mesma escolha que a janela antiga já fazia
    #: (`home_actions._maybe_fetch_externos`, `EXTERNOS_THROTTLE_S = 4.0`).
    #:
    #: **LISTA VAZIA É DUAS COISAS** — *"não há"* e *"ainda não perguntei"* — e
    #: quem lê trata as duas igual: não desenha card nenhum. A diferença só
    #: importaria para ACUSAR ausência, e nenhuma das duas abas acusa. É a
    #: mesma decisão escrita em `home_actions.externos_na_mesa`, que é o dono.
    externos: list[dict[str, Any]] = field(default_factory=list)

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

#: O QUE CADA GESTO DECLARA QUE MUDA NA MÁQUINA DELA — `(página, nome) → o que`.
#: Só entram os que passaram `grava=`; o silêncio é "não mexe em nada dela".
#:
#: ELE É A FONTE DE `hefesto_vivo.PERIGOSOS`, e é por isso que existe. Até
#: 06/09/2026 aquela lista era DIGITADA num arquivo que os pacotes têm no
#: `nao_toca`, e chegou atrasada QUATRO vezes em três dias — `01-jogar·cadeado`,
#: `08-conexoes·renomear-adaptador`, os dois da Vibração e os dois da tela de
#: teclas. A forma do defeito é sempre a mesma: quem escreve o gesto não pode
#: fechar o próprio contrato, porque as duas linhas moram longe dele.
#:
#: Aqui a declaração mora NO GESTO, e a lista é derivada. Ver `perigosos()`.
GESTOS_QUE_MEXEM: dict[tuple[str, str], str] = {}


def gesto(pagina: str, nome: str, *,
          grava: str = "") -> Callable[[Gesto], Gesto]:
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

    `grava=` — O QUE ESTE GESTO MUDA NA MÁQUINA DELA, e quem o declara é quem o
    escreve. Duas formas, e a diferença decide quem confere:

    * **o nome da porta**, quando existe uma chamada que a árvore enxerga —
      `grava="save_profile"`, `grava="gravar_e_reaplicar"`,
      `grava="marcar_jogo_sem_wrapper"`. `test_todo_gesto_que_grava_esta_
      protegido` LÊ a árvore do gesto e cobra que a porta declarada esteja lá:
      declaração errada ou envelhecida reprova nomeando;
    * **uma frase**, quando o perigo não é uma chamada — `grava="para o serviço
      e ela fica sem controle"`. Aí a árvore não tem o que confirmar, e quem
      assembla é a régua, no `FORA_DA_ARVORE` dela, com a medição do lado.

    NÃO É "grava no disco", é **"muda algo dela que ela não mandou mudar"** — a
    área de transferência da 07 e o cursor da 06 estão aqui pela mesma razão que
    o `save_profile`. O que sai daqui é `hefesto_vivo.PERIGOSOS`, a lista do que
    a prova botão a botão NÃO clica sozinha.
    """
    limpo = grava.strip()
    if grava and not limpo:
        raise SystemExit(
            f"ERRO: o gesto {nome!r} de {pagina} declarou `grava=` em branco. "
            f"Declaração vazia é pior que nenhuma: ela some da lista derivada "
            f"sem ninguém notar. Diga a porta ou diga a frase.")

    def dentro(fn: Gesto) -> Gesto:
        chave = (pagina, nome)
        if chave in GESTOS:
            raise SystemExit(
                f"ERRO: o gesto {nome!r} de {pagina} já tem dono "
                f"({GESTOS[chave].__module__}). Dois donos para o mesmo botão é "
                f"o defeito que este despachante existe para impedir.")
        GESTOS[chave] = fn
        if limpo:
            GESTOS_QUE_MEXEM[chave] = limpo
        return fn
    return dentro


#: QUEM SEGURA UM APARELHO DELA ENQUANTO A JANELA ESTÁ ABERTA — 15/09/2026,
#: A-TELA-QUE-TRAVA-02. Uma aba pode deixar o produto num estado que é DELA
#: enquanto ela olha, e não do jogo: hoje é um só, o "Testar" da Vibração, que
#: tira os motores do jogo (`rumble.passthrough(False)`) até ela clicar em
#: "Parar".
#:
#: A ORDEM DELA, 15/09/2026, com o controle na mão: *"o testar e parar é sobre o
#: teste naquele momento isso nao interfere in game (noqa-acento: dela). (…)
#: clicar em parar é só pra impactar no teste naquele momento e não mutar a
#: vibração in game. em game se eu quiser desligar a vibração do motor esquerdo
#: zero o slicer"*
#:
#: O QUE ESTAVA QUEBRADO: `parar_o_teste()` tinha DOIS chamadores — o botão
#: "Parar" e o controle que sai da mesa — e nenhum deles é fechar a janela.
#: Trocar de aba, fechar a janela ou a janela morrer deixava
#: `rumble_passthrough=False` para sempre, e o jogo ficava mudo sem que nada na
#: tela dissesse por quê.
#:
#: SÃO DUAS METADES, e as duas foram escolha dela entre quatro caminhos:
#:
#: * **o CORAÇÃO** (`CORACOES`) — enquanto a janela vive, ela bate a cada tique
#:   e o daemon sabe que alguém ainda segura. É a aba que decide se há o que
#:   bater e com que espaçamento; o piloto só bate;
#: * **a LARGADA** (`LARGADAS`) — ao trocar de página e ao fim da janela, o
#:   piloto manda largar. Aqui não há espaçamento: largar duas vezes é inócuo,
#:   não largar é o jogo mudo.
#:
#: A terceira metade é do daemon e não mora aqui: um teto de ociosidade solta o
#: rumble fixado que ninguém rebate — a rede para a janela que MORRE sem
#: conseguir largar (`daemon/subsystems/rumble.TETO_DO_RUMBLE_FIXADO_S`).
#:
#: POR QUE GENÉRICO, e não um desvio por nome de página dentro do piloto: ele é
#: o dono das DEZ abas e não conhece o assunto de nenhuma. Uma segunda aba que
#: segure um aparelho amanhã registra aqui e ganha as duas metades de graça —
#: e, mais importante, quem escreve a aba não precisa lembrar de mexer no
#: piloto, que é a forma de defeito que o `GESTOS_QUE_MEXEM` acima já nomeia.
CORACOES: list[Callable[[Contexto, Any], None]] = []

#: Quem devolve ao jogo/à máquina o que a aba segurava. Ver `CORACOES`.
LARGADAS: list[Callable[[Any], None]] = []


def coracao(fn: Callable[[Contexto, Any], None]) -> Callable[[Contexto, Any], None]:
    """Registra um batimento por tique. A aba decide se há o que bater."""
    CORACOES.append(fn)
    return fn


def largada(fn: Callable[[Any], None]) -> Callable[[Any], None]:
    """Registra quem larga o que a aba segurava, ao sair da página ou da janela."""
    LARGADAS.append(fn)
    return fn


#: QUEM ESQUECE O CONTROLE QUE SAIU DA MESA — CACHE-SEM-PODA-01, 20/09/2026.
#:
#: A QUEIXA DELA, 19/09/2026: *"noto que existe alguma espécie de cachê que
#: demora a ser apagado. Principalmente quando desconectamos controles e
#: afins."* <!-- noqa-acento: citação literal dela -->
#:
#: **O DAEMON SABE NA HORA; A INTERFACE ESPERAVA O RELÓGIO.** Todo cache desta
#: interface expirava por TEMPO e nenhum escutava a saída de um controle: o som
#: da 02 a cada 2 s, a biblioteca da 07 a cada 20 s, o prontuário da 09 a cada
#: 300 s. Na mesma tela, ao mesmo tempo, um bloco já tinha esquecido o controle
#: e o outro ainda o mostrava — e é isso que se lê como *"cache que demora a ser
#: apagado"*.
#:
#: **E O RELÓGIO ERA MAIS LENTO DO QUE O NÚMERO DIZIA.** Medido nesta árvore em
#: 20/09/2026, com o cache da 02 preenchido por injeção e a mesa esvaziando:
#:
#:     logo depois de sair   sono 'acordado' · sink 'sink-de-mentira'
#:     300 s depois          sono 'acordado' · sink 'sink-de-mentira'
#:
#: Os 2 s só valem enquanto SOBRA alguém na mesa: `a02_controles._camada_1`
#: começa com `if not na_mesa: return`, então com a mesa vazia a thread de
#: renovação **nunca roda** e a entrada do que saiu fica para sempre — servida
#: de novo, velha, no instante em que ele volta (o `uniq` é o MAC, e volta igual).
#:
#: **UM PONTO SÓ, E A RAZÃO É A DA SPRINT:** *"o que não pode é cada aba
#: inventar a própria poda — seriam seis versões da mesma regra, que é o defeito
#: que esta casa mais paga"*. Aqui a aba declara o que esquecer e o despachante
#: decide QUANDO, do mesmo jeito que `CORACOES` e `LARGADAS` já fazem.
PODAS: list[Callable[[frozenset[str]], None]] = []

#: Quem estava na mesa no tique ANTERIOR. Lista de um elemento porque o que se
#: troca é o conteúdo, nunca o nome — o mesmo arranjo do `_CAMADA_1_QUANDO`.
#:
#: Ela nasce vazia, e por isso o primeiro tique nunca poda: `frozenset() - agora`
#: é vazio. Uma janela que abre com a mesa cheia não é um controle saindo.
_NA_MESA_ANTES: list[frozenset[str]] = [frozenset()]


def poda(fn: Callable[[frozenset[str]], None]) -> Callable[[frozenset[str]], None]:
    """Registra quem esquece um controle que saiu. Recebe quem FICOU.

    A aba recebe o conjunto de `uniq` que ainda está na mesa — e não a lista de
    quem saiu — de propósito: o que ela tem de fazer é *"esqueça tudo o que não
    está nesta lista"*, que é uma regra que não erra por omissão. Com a lista de
    quem saiu, uma entrada que envelheceu sem hotplug nenhum ficaria para
    sempre, porque ninguém a nomearia.
    """
    PODAS.append(fn)
    return fn


def na_mesa_agora(ctx: Contexto) -> frozenset[str]:
    """Os `uniq` que estão de fato aqui, neste tique.

    `conectados` e não `mesa`: a mesa é a BANCADA, com os lugares vazios
    incluídos, e um lugar vazio não é um controle. É a mesma distinção que o
    campo `conectados` do `Contexto` já carrega escrita.
    """
    return frozenset(str(c.get("uniq") or "") for c in ctx.conectados
                     if c.get("uniq"))


def podar_o_que_saiu(ctx: Contexto) -> frozenset[str]:
    """Quem saiu da mesa desde o tique anterior — e já esquecido por todos.

    **Nunca levanta**, pela mesma razão de `bater_os_coracoes`: ela roda DENTRO
    do tique, e um tique que levanta para de pintar a aba inteira.

    **A PODA SÓ ACONTECE QUANDO ALGUÉM SAI**, e não a cada tique: varrer seis
    caches dez vezes por segundo para não achar nada é trabalho por nada, e o
    evento que a queixa dela nomeia é raro — é a mão dela tirando o cabo.

    ELA NÃO PODA QUEM CHEGA. Um controle que entra não deixa lixo em cache
    nenhum; o que ele encontra é a própria entrada, da sessão anterior dele, e
    quem a tirou foi a poda da SAÍDA. Curar na chegada seria curar tarde: entre
    a saída e a volta a tela já teria mostrado o dado velho.
    """
    agora = na_mesa_agora(ctx)
    antes, _NA_MESA_ANTES[0] = _NA_MESA_ANTES[0], agora
    saiu = antes - agora
    if not saiu:
        return frozenset()
    for esquecer in PODAS:
        try:
            esquecer(agora)
        except Exception as erro:  # o tique não morre por isto
            print(f"[poda] {esquecer.__name__}: {erro}", file=sys.stderr)
    return saiu


def bater_os_coracoes(ctx: Contexto, p: Any) -> None:
    """O que o despachante faz a cada tique: PODAR o que saiu e BATER os corações.

    Ele roda DENTRO do tique, e um tique que levanta para de pintar a aba
    inteira — trocar um jogo sem vibração por uma tela congelada seria o pior
    dos dois negócios. O que der errado vai ao diário da janela.

    **A PODA VEM ANTES DO BATIMENTO, E ANTES DA PINTURA** — CACHE-SEM-PODA-01.
    O piloto chama esta função e, logo depois, `pacote_da_pagina()`: esquecer
    aqui é o que faz a aba pintar o tique com o cache já limpo, que é a prova de
    pronto da sprint (*"em menos de um tique"*, e não em 2, 20 ou 300 segundos).

    **POR QUE A PODA MORA AQUI E NÃO EM `pacote_da_pagina`**, e a razão é
    medida: aquela função tem trinta chamadores nas réguas, cada um montando um
    `Contexto` à mão. Uma poda ali faria a régua de uma aba apagar o cache que a
    régua da irmã acabou de injetar — contaminação por ORDEM DE TESTE, que esta
    casa já pagou com o dublê do co-op em 04/09/2026. Esta função tem **um
    chamador só**, e ele é o tique.
    """
    podar_o_que_saiu(ctx)
    for bate in CORACOES:
        try:
            bate(ctx, p)
        except Exception as erro:  # o tique não morre por isto
            print(f"[coração] {bate.__name__}: {erro}", file=sys.stderr)


def largar_o_que_as_abas_seguram(p: Any) -> None:
    """Devolve ao jogo/à máquina tudo o que as abas seguravam. **Nunca levanta.**

    Chamado ao TROCAR de página e ao fim da janela. Largar o que já está solto é
    inócuo; não largar é o jogo mudo até ela voltar à aba e clicar em "Parar".
    """
    for larga in LARGADAS:
        try:
            larga(p)
        except Exception as erro:  # a saída não morre por isto
            print(f"[largada] {larga.__name__}: {erro}", file=sys.stderr)


def perigosos() -> set[tuple[str, str]]:
    """Os gestos que mexem na máquina dela — DERIVADOS, nunca digitados.

    É o que `hefesto_vivo.PERIGOSOS` passou a ser em 06/09/2026, e a diferença
    não é de estilo. A lista digitada tinha DOIS defeitos que a derivação torna
    impossíveis, e os dois foram medidos nesta casa:

    1. **entrada que não casa gesto nenhum.** `("09-sistema.html",
       "restaurar-de-fabrica")` ficou anos protegendo NADA — o gesto sempre se
       chamou `refazer-proton`. Uma lista lida só para PULAR nunca acusa o
       próprio erro de digitação. Aqui a chave SAI do registro: um fantasma não
       tem como nascer;
    2. **a linha que chega no commit seguinte.** Quatro vezes em três dias um
       gesto aprendeu a gravar e a lista ficou para trás — e a janela entre as
       duas é a janela em que a prova botão a botão escreve no disco dela.

    O QUE A DERIVAÇÃO **NÃO** RESOLVE, e por isso a régua de AST continua: quem
    esquece a linha também pode esquecer o `grava=`. São duas fontes
    independentes de propósito — a declaração diz o que o autor quis, a árvore
    diz o que o código faz, e a régua cobra as duas direções.
    """
    return set(GESTOS_QUE_MEXEM)


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
    com_molde = {**fora, POR_CONTROLE[0]: colunas}
    # E O QUE A ABA PINTA POR LUGAR, INTEIRO — ver `CAMPOS_DO_LUGAR`. O molde
    # deixa de fora os campos `html`, e é neles que o desenho do lugar vazio
    # tem mais a dizer.
    pinta = _PINTA.get(_chave_do_molde(pagina, ctx))
    if pinta:
        com_molde[CAMPOS_DO_LUGAR] = sorted(pinta)
    return com_molde


#: AS TRÊS PALAVRAS PARA A MESMA COISA. Cada aba nasceu com a sua — `cartoes` na
#: Jogar, `cards` na Controles, `colunas` nas outras sete — porque cada uma foi
#: escrita olhando o desenho dela, e o desenho as chama assim.
#:
#: NÃO SE UNIFICA NO PACOTE, e a razão é dela: as funções falam a língua da aba
#: que servem, e renomear `cartoes` para `colunas` na Jogar afastaria o código
#: do desenho sem ganhar nada. Unifica-se AQUI, na saída, que é onde o piloto lê.
POR_CONTROLE = ("colunas", "cartoes", "cards")

#: OS CAMPOS QUE A ABA PINTA POR LUGAR — O-LUGAR-VAZIO-DIZ-O-QUE-O-DESENHO-DIZ-01,
#: 23/09/2026. Lista na raiz do pacote da mesa VAZIA, e ela só existe ali.
#:
#: Com um controle na mesa as colunas vivas já dizem o que a aba pinta. Com a
#: mesa vazia só sobra o molde, e o molde é o que o TRAVESSÃO atende: os campos
#: `html` ficam fora dele. Sem esta lista `apagar_os_lugares_sem_dono` não
#: saberia que a 08 pinta o `nome` do cartão — e o nome ficava como estava: o
#: exemplo do desenho, ou o do último controle que passou por ali.
#:
#: ELA É A TRAVA, e não só a fonte: o desenho do lugar vazio só é escrito onde a
#: aba ESCREVE. Um campo que ninguém reescreve quando o controle chega guardaria
#: o vazio no lugar cheio. Sai da carga em `apagar_os_lugares_sem_dono`.
CAMPOS_DO_LUGAR = "campos-do-lugar"

#: O que NUNCA é valor de tela: a contagem da régua, a lista de órfãos e os
#: campos do lugar. São metadado do pacote, e pintá-los escreveria
#: "{'pintados': 25}" numa caixa.
NAO_SAO_VALOR = {"cobertura", "sem_dono", CAMPOS_DO_LUGAR}

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
# ESSAS TRÊS LINHAS SÃO DESTA CURA SOZINHA, e a árvore andou no mesmo dia: com o
# SELO DA VISITA junto (a outra metade da fundação) o INDECIDÍVEL vai a ZERO, e
# as mesmas medições dão `222 · 108 · 0` com a mesa vazia sem o filtro dos
# filhos mudos, `218 · 112 · 0` com ele, e `262 · 68 · 0` com a mesa cheia (dois
# controles, um USB e um BT). Os quatro campos de diferença na mesa vazia são
# ENTREGA e não regressão — ver `enderecos_que_o_texto_apaga`.
#
# A CAUSA, e ela não é de nenhuma das dez abas: o piloto já apaga os lugares
# sem dono (por `apagar_os_lugares_sem_dono`), mas as CHAVES que ele apaga são a
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
#: (`apagar_os_lugares_sem_dono`). Com `p1`…`p4` ocupados pelo molde, a conta dá
#: lista vazia e os quatro lugares ficariam com a moldura de CONECTADO — meio
#: apagado, que é pior que aceso. Sob `*` a conta continua dando os quatro, o
#: piloto escreve o travessão em todos E acende a moldura de vazio.
#:
#: `*` é a mesma reserva que os gestos do rodapé já usam (`GESTOS[("*", nome)]`
#: — "de todas as abas"), e não um segundo vocabulário.
LUGAR_SEM_DONO = "*"

#: O QUE O LUGAR VAZIO MOSTRA ONDE O TRAVESSÃO NÃO ALCANÇA — 21/09/2026.
#:
#: `{campo: valor}` na raiz do pacote. O molde escreve `—` só nos campos de
#: TEXTO (`ALVOS_QUE_O_TRAVESSAO_NAO_ATENDE`), e os campos de alvo `html` —
#: um DESENHO — ficavam com o que o mockup desenhou. Ela fotografou isso com
#: zero controles na mesa: a linha LEDs do P1 e do P2 ACESA em azul e vermelho,
#: a do P3 e do P4 com o travessão, e o cartão da Navegação dizendo
#: `P1 • P1 • Desconectado` em verde — *"p1,p2 tão diferentes do p3 e p4"*.
#:
#: QUEM SABE O DESENHO APAGADO É A ABA, e é por isso que o valor vem dela: o
#: travessão é a palavra de um campo de texto, e num desenho seria apagar o
#: desenho — ela pediu o contrário, *"tem que aparecer, mas não ligado"*. O
#: despachante só aplica: em TODO lugar sem dono (o que nasceu vazio e o que
#: esvaziou), para que os quatro tenham UMA leitura. `apagar_os_lugares_sem_dono`
#: consome a chave; ela não viaja até a página.
LUGAR_VAZIO = "vazio"

#: AS MARCAS DO LUGAR — `{classe: [uniq, …]}` na raiz do pacote, 21/09/2026.
#:
#: Uma classe que a casca de UM lugar carrega por ser quem é — o `navega` da
#: `06-navegacao`, o cartão verde de quem navega o PC. O gerador a escreve no
#: P1 do desenho e ninguém a tirava: com a mesa vazia o P1 continuava verde
#: afirmando um controle navegando, e com o P2 no comando o verde ficava no P1.
#: O piloto acende a classe nos lugares da lista e apaga nos outros três; uma
#: classe que o pacote não nomeia não é tocada.
MARCAS_DO_LUGAR = "marcas"

#: OS QUATRO LUGARES DA MESA DO DESENHO. O HTML nasce com eles todos — dois
#: conectados e dois vazios, por decisão dela em 31/08 — e o produto tem de
#: apagar o que a mesa de agora não preenche.
TODOS_OS_LUGARES = frozenset({"p1", "p2", "p3", "p4"})

#: UM BLOCO QUE MIRA O CAMPO DE UM LUGAR. É a forma que `a03_gatilhos.
#: seletor_do_chip` emite, e a única que esta conta precisa reconhecer:
#: um `data-controle` e, dentro dele, um `data-campo`. Selector de classe
#: (`.ajustes.e`, `select.modo[data-lado="e"]`) não casa de propósito — aqueles
#: elementos não têm endereço de campo, logo o molde nunca escreveria neles.
_BLOCO_DE_UM_CAMPO = re.compile(
    r'\[data-controle="(?P<pref>[^"]+)"\]\s*\[data-campo="(?P<campo>[^"]+)"\]')


def _o_que_o_bloco_ja_escreveu(carga: dict[str, Any]) -> dict[str, set[str]]:
    """`{pref: {campo, …}}` — o que a aba já pôs naquele lugar por BLOCO.

    POR QUE ISTO EXISTE, medido no DOM vivo em 11/09/2026 com UM controle na
    bancada, na aba 03::

        p1  'P1 • Starlight Blue • rádio'
        p2  '—'                             ← a queixa dela
        p3  'P3 • Desconectado'
        p4  'P4 • Desconectado'

    O bloco do P2 POUSAVA — `a03_gatilhos` o emite, e o piloto o escreve no
    passo 0 da pintura. O que vinha depois é que o desfazia: o passo 2 escreve
    os CAMPOS, e o molde desta função tinha acabado de encher a coluna do P2
    com `dict.fromkeys(chaves, TRAVESSAO)` — `chip-do-controle` entre elas,
    porque as outras três colunas o emitem. Duas escritas no mesmo elemento, e
    a segunda ganha; no tique seguinte o bloco se cala (`alvo.__hefBloco ===
    html`) e o travessão fica para sempre.

    A REGRA É A QUE ESTA CASA JÁ ESCREVE EM TODA PARTE: **não se escreve duas
    vezes no mesmo elemento.** Quem mandou um bloco para aquele endereço daquele
    lugar já disse o que ele mostra — o molde não tem o que acrescentar ali.

    E ELA É GERAL DE PROPÓSITO. A cura de 05/09 conhecia esta causa e cobriu UM
    nome de campo (`identidade`, logo abaixo); seis dias depois a mesma falta
    voltou noutra aba com outro nome de campo. Cobrir um chamador deixa a
    próxima pessoa remedindo o mesmo defeito — é o que aconteceu.
    """
    fora: dict[str, set[str]] = {}
    for seletor in (carga.get("blocos") or {}):
        achado = _BLOCO_DE_UM_CAMPO.search(str(seletor))
        if achado:
            fora.setdefault(achado.group("pref"), set()).add(achado.group("campo"))
    return fora


def apagar_os_lugares_sem_dono(
        carga: dict[str, Any],
        com_dono: Iterable[str] | None = None,
        pagina: str | None = None) -> dict[str, Any]:
    """Escreve travessão em todo lugar do desenho que a mesa de agora não tem.

    E ONDE O TRAVESSÃO NÃO CHEGA À TELA, O DESENHO DIZ — O-LUGAR-VAZIO-DIZ-O-QUE-
    O-DESENHO-DIZ-01, 23/09/2026. Com a página, os campos de alvo `html`, `cor` e
    `atributo` de um lugar vazio recebem o que o desenho publica num lugar vazio
    (`o_que_o_desenho_diz_do_lugar_vazio`). Sem a página, só o travessão, como
    antes — o piloto sempre a passa.

    ELA MORA AQUI, e não no piloto, POR CAUSA DA RÉGUA. O molde do despachante
    só vira travessão na tela porque alguém aplica esta conta, e a régua que
    guardava esse acoplamento COBRAVA TRÊS LITERAIS dentro do `hefesto_vivo.py`
    — a PALAVRA, não o ATO. Medido em 02/09/2026: acrescentar
    `if pref_ == "*": continue` ao laço da união mata a cura inteira (a régua do
    mockup volta ao `330 · 114 · 179 · 37` de antes dela, com a mesa vazia) e os
    três literais continuam no arquivo, com **13 testes verdes**. Extrair a
    conta é o que deixa o teste RODAR o que o produto roda.

    A CHAVE RESERVADA ENTRA NA UNIÃO DE PROPÓSITO: é a coluna do `*` que traz o
    molde, e é dela que saem as chaves a apagar quando não há uma só coluna
    viva. Pulá-la — o que qualquer pessoa faria ao "limpar" um dicionário de
    `p1..p4` com um `*` no meio — é exatamente o que desfaz a cura.

    :param carga: o que `normalizar()` devolveu, já com o `topo()` somado. Volta
        a MESMA carga, mexida no lugar, com `vazios` dizendo quais lugares a
        moldura tem de marcar como desconectados.
    """
    colunas = carga.setdefault("colunas", {})
    chaves: set[str] = set()
    for campos in colunas.values():
        chaves |= set(campos)
    # QUEM TEM DONO É A MESA QUE DIZ, e não a lista de colunas que a aba
    # emitiu. A primeira versão desta conta fez `set(colunas)`, e ela estava
    # ERRADA — medido no DOM vivo em 03/09/2026, com UM controle na bancada: a
    # `03-gatilhos` emite coluna para os QUATRO lugares (as vazias levam
    # travessão de propósito, para as barras de ajuste nascerem no lugar), e o
    # p3 e o p4 entraram em `ocupados`. O passo `1c` do piloto os REABRIU, e a
    # tela passou a dizer `data-conectado="sim"` em dois lugares vazios.
    #
    # TER COLUNA NÃO É TER DONO. Uma aba manda coluna para desenhar; a mesa diz
    # quem está aqui. Quando `com_dono` não vem, o caminho antigo continua —
    # nenhum lugar reabre, que é o comportamento anterior a esta cura e é
    # seguro: a tela pode ficar atrasada, nunca mentindo a mais.
    ocupados = sorted(set(com_dono or ()) & TODOS_OS_LUGARES)
    apagar = sorted(TODOS_OS_LUGARES - set(colunas))
    # O QUE A ABA JÁ ESCREVEU POR BLOCO NÃO SE APAGA — 11/09/2026, e a razão
    # inteira está em `_o_que_o_bloco_ja_escreveu`. Sem esta linha o molde
    # reescreve por cima do que o passo 0 da pintura acabou de pôr na tela, e
    # o que sobra é um travessão onde a aba tinha escrito o estado do lugar.
    ja_escrito = _o_que_o_bloco_ja_escreveu(carga)
    # O QUE A ABA DISSE DO LUGAR VAZIO VENCE O TRAVESSÃO — ver `LUGAR_VAZIO`.
    # Sai da carga AQUI, e não no `normalizar`, porque é esta conta que sabe
    # QUAIS lugares estão vazios.
    vazio = carga.pop(LUGAR_VAZIO, None) or {}
    # O QUE A ABA PINTA POR LUGAR — as chaves vivas e, com a mesa vazia, a lista
    # que o despachante mandou (`CAMPOS_DO_LUGAR`). Sai da carga SEMPRE: ela é
    # instrução para esta conta, não valor de tela.
    pinta = chaves | {str(k) for k in (carga.pop(CAMPOS_DO_LUGAR, None) or ())}
    diz = o_que_o_desenho_diz_do_lugar_vazio(pagina) if pagina else {}
    for pref in apagar:
        colunas[pref] = dict.fromkeys(chaves - ja_escrito.get(pref, set()),
                                      TRAVESSAO)
        # O LUGAR VAZIO DIZ QUE ESTÁ VAZIO, e não um travessão mudo.
        #
        # MEDIDO NA TELA EM 05/09/2026, com UM controle na bancada: a aba 05
        # mostrava `P3 • Desconectado` e `P4 • Desconectado` — porque essas
        # duas colunas são desenho e ninguém escreve nelas — e um `—` seco na
        # do P2, que TEM endereço (`data-hef="identidade"`) e por isso recebia
        # o travessão por cima. Três lugares igualmente vazios, dois dizendo o
        # que são e um calado, lado a lado.
        #
        # O travessão continua certo para todo o resto da coluna: *"isto eu
        # não sei"* é a resposta honesta para o volume de um controle que não
        # está aqui. Mas a IDENTIDADE do lugar não é desconhecida — o lugar é
        # o P2, e ele está desconectado. Isso se sabe, e a tela já sabia dizer
        # em dois dos quatro.
        #
        # A frase é a mesma do desenho, sem a marcação: as abas escrevem esta
        # chave por `texto`, não por `html`.
        if IDENTIDADE_DO_LUGAR in chaves:
            colunas[pref][IDENTIDADE_DO_LUGAR] = (
                f"P{pref[1:]} {PONTO_DO_ROTULO} {SEM_NINGUEM_AQUI}")
        # O DESENHO DIZ O LUGAR VAZIO onde o travessão não chega — e só onde a
        # aba pinta (`pinta`), senão o vazio ficaria no lugar quando o controle
        # chegasse. A foto dela, 23/09/2026, zero controles na mesa: a 08 dizia
        # `Sony • Player 1 • Cosmic Red • USB` com a barra rosa acesa no P1.
        colunas[pref].update({k: v for k, v in diz.get(pref, {}).items()
                              if k in pinta and k not in ja_escrito.get(pref, set())})
        colunas[pref].update({k: v for k, v in vazio.items()
                              if k not in ja_escrito.get(pref, set())})
    # A MOLDURA TAMBÉM, e não só o texto: com os travessões escritos, o card do
    # P2 continuava com a borda de CONECTADO e os botões de máscara acesos. Meio
    # apagado é pior que aceso — quem olha lê a borda antes de ler o campo.
    carga["vazios"] = apagar
    # E O COMPLEMENTO, que faltava — QUEBRA-CARTAO-QUE-NAO-REABRE-01,
    # 03/09/2026. `vazios` só sabia MARCAR: o piloto escrevia
    # `data-conectado="nao"` e a classe `off`, e não havia uma linha em lugar
    # nenhum que as tirasse. O primeiro controle a chegar num lugar que já
    # esvaziou uma vez encontrava o cartão fechado — 24 px de altura contra os
    # 358 de um cartão aberto — e o dado dela chegava INVISÍVEL. Só recarregar a
    # página (sair da aba e voltar) desfazia.
    #
    # POR QUE O DESENHO NÃO RESOLVIA SOZINHO: o P3 e o P4 nascem com a marca no
    # HTML, por decisão dela de 31/08. Uma marca que o HTML crava e o produto só
    # sabe acrescentar é uma marca de mão única.
    carga["ocupados"] = ocupados
    return carga


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
#:
#: ELE NÃO ENTRA NA PODA DE `PODAS`, E FOI MEDIDO — CACHE-SEM-PODA-01,
#: 20/09/2026. A sprint o listou como suspeito por não ser chaveado por
#: controle; ele não é chaveado por controle porque **não guarda nenhum**. São
#: duas razões independentes, as duas no código logo abaixo:
#:
#: * `molde_do_lugar` começa com `if ctx.conectados: return {}` — ele só existe
#:   quando a mesa está VAZIA, que é depois de o último ter saído;
#: * o valor é `dict.fromkeys(…, TRAVESSAO)`: só os NOMES dos campos sobrevivem,
#:   e todos valem travessão. O `_CONTROLE_DE_MENTIRA` com que ele é montado é
#:   sintético (`aa:bb:cc:…`) e os valores dele são jogados fora.
#:
#: Um controle que sai não tem entrada aqui para levar consigo. Podá-lo custaria
#: uma pintura fantasma inteira por hotplug para chegar ao mesmo dicionário.
_MOLDE: dict[tuple[str, str], dict[str, str]] = {}

#: TUDO o que a pintura fantasma emitiu por lugar, na mesma chave do `_MOLDE` —
#: o molde menos as exceções do travessão. É a lista `CAMPOS_DO_LUGAR`. Mesmas
#: duas razões do `_MOLDE` para não entrar na poda: só nomes, de um controle
#: sintético.
_PINTA: dict[tuple[str, str], frozenset[str]] = {}


def _chave_do_molde(pagina: str, ctx: Contexto) -> tuple[str, str]:
    """`(página, perfil ativo)` — a chave do `_MOLDE` e do `_PINTA`.

    O NOME SE PERGUNTA AO DONO, e aqui ele é CHAVE DE CACHE — 19/09/2026. Com o
    `ctx.state.get("active_profile")` cru a chave era `None` em toda volta na
    máquina dela (o daemon não publica o perfil de janela), e trocar de perfil
    NÃO invalidava o molde: a página seguia com o molde do perfil anterior. Ver
    `perfil.nome_do_ativo`.
    """
    from hefesto_dualsense4unix.interface.pacotes import perfil as _perfil_

    return (pagina, _perfil_.nome_do_ativo(ctx.state))

#: O que a tela escreve onde não há dado. TEXTO DE TELA É DELA, e este não é
#: novo: é o mesmo caractere que o desenho já põe nos lugares P3/P4 e que o
#: `escrever()` do piloto já escreve em `null`/`""`.
#:
#: Está aqui como literal, e não importado da `regua_do_mockup.TRAVESSAO`,
#: porque o produto não depende de instrumento de medição. Quem impede as duas
#: grafias de divergirem é `test_o_molde_escreve_o_travessao_do_desenho`, que
#: procura este caractere DENTRO do lugar vazio da página publicada.
TRAVESSAO = "—"

#: A CHAVE QUE CARREGA A IDENTIDADE DO LUGAR nas abas de quatro colunas. Quem
#: a emite recebe `P2 • Desconectado` no lugar vazio, em vez do travessão —
#: ver a razão medida em :func:`apagar_os_lugares_sem_dono`. Aba que não a emite não ganha
#: chave nova: `chaves` é a união do que a PRÓPRIA carga trouxe.
#: O CABEÇALHO SEM CONTROLE NENHUM — 22/09/2026. Com o «N controles:» fora da
#: tela, a segunda metade é tudo o que sobra, e com a mesa vazia
#: `frase_dos_transportes(0, 0)` devolve vazio: a tela mostraria um travessão
#: solto ao lado da bolinha.
SEM_CONTROLE_NA_MESA = "Nenhum controle"

IDENTIDADE_DO_LUGAR = "identidade"
#: O separador do rótulo, igual ao do desenho (que o envolve num `<span
#: class="pt">` — aqui não, porque esta chave se escreve por `texto`).
PONTO_DO_ROTULO = "\u2022"
#: E a palavra, uma só, para não haver duas versões dela na casa.
SEM_NINGUEM_AQUI = "Desconectado"


#: OS TRÊS ALVOS QUE O TRAVESSÃO NÃO ATENDE, e os três foram medidos, não
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
#: `fundo` — SOFRE A MESMA RECUSA QUE TIROU A `largura`, e faltava aqui. O ramo
#:   do `escrever()` é `if(el.style.background !== t){ el.style.background = t;
#:   return 1; }`: `background: "—"` é tão inválido quanto `width: "—%"`, o
#:   CSSOM não guarda, a comparação nunca casa e o contador soma +1 por tique
#:   para sempre. Hoje é LATENTE — nenhuma das dez páginas publicadas tem um só
#:   `data-hef-alvo="fundo"` (medido) —, e é exatamente por isso que ele
#:   precisava entrar antes de o desenho ganhar o primeiro.
#:
#: `altura` — o GÊMEO VERTICAL DA `largura`, e entrou com ele em 05/09/2026,
#:   pelo defeito idêntico e medido no mesmo dia: `el.style.height = "—%"` o
#:   CSSOM recusa, as catorze barrinhas de cada onda sonora da aba 02 ficam na
#:   altura do desenho, e `--prova-de-mockup` acusou as 56 como ENDEREÇO MORTO
#:   no lugar vazio. Um alvo de estilo que o travessão não atende nasce com esta
#:   dívida; o alvo nasceu e a dívida foi paga junto.
#:
#: `valor` FICA, e é de propósito: num `<select>` o piloto só escreve o que o
#: campo oferece, então o travessão é no-op onde não há opção `—` e acerta onde
#: houver. Nada quebra, e nada precisa ser lembrado no dia em que o desenho
#: ganhar essa opção.
#:
#: `cor` FICA pela razão inversa e igualmente medida: o ramo dele ESCREVE e
#: depois COMPARA (`el.style.color = t; return el.style.color === antes ? 0 : 1`),
#: então um travessão recusado devolve 0 e o contador não mente.
#:
#: E ERA O PONTO CEGO — 23/09/2026, O-LUGAR-VAZIO-DIZ-O-QUE-O-DESENHO-DIZ-01. O
#: contador não mente, e a TELA fica com a cor de antes: o `—` recusado não apaga
#: nada. A razão acima mediu o contador, não o que ela vê — e a barra rosa do P1
#: da 08 ficou acesa com zero controles na mesa. Quem apaga agora é o desenho do
#: lugar vazio (`ALVOS_QUE_O_DESENHO_DIZ`), e o `cor` continua fora deste
#: conjunto porque o molde precisa da chave para o desenho saber que ela existe.
ALVOS_QUE_O_TRAVESSAO_NAO_ATENDE = {"largura", "altura", "html", "fundo"}

#: OS ALVOS EM QUE O LUGAR VAZIO DIZ O QUE O DESENHO DIZ — O-LUGAR-VAZIO-DIZ-O-
#: QUE-O-DESENHO-DIZ-01, 23/09/2026. São os três em que o travessão não põe na
#: tela a palavra do lugar vazio:
#:
#: `html`     — fica fora do molde (ver acima) e, com um controle na mesa, vira
#:              um `—` que apaga a marcação. O nome do cartão da 08 é `html`.
#: `cor`      — o `—` é recusado e a cor de antes fica. Vazio é `""`, que devolve
#:              o elemento à folha de estilo.
#: `atributo` — o `—` só sabe apagar. O desenho diz o que um lugar vazio tem ali.
#:
#: O DONO É O DESENHO: o valor de um campo num lugar vazio é o valor dele no
#: cartão que o desenho publica vazio (`data-conectado="nao"`), com o número do
#: jogador trocado. Ver `o_que_o_desenho_diz_do_lugar_vazio`.
ALVOS_QUE_O_DESENHO_DIZ = frozenset({"html", "cor", "atributo"})

_LUGAR_NO_HTML = re.compile(r'data-controle="(p\d+)"')

#: As tags que não fecham. Sem esta lista, um `<input data-campo="x">` deixaria
#: um quadro aberto para sempre e engoliria os irmãos todos.
_SEM_FECHO = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
})


class _OlhoNaPagina(html.parser.HTMLParser):
    """A página publicada, lida UMA vez, para as duas perguntas do molde.

    POR QUE UM PARSER, E NÃO TRÊS EXPRESSÕES REGULARES: a segunda pergunta é
    sobre ESTRUTURA — *este endereço tem filho de elemento?* —, e busca de texto
    não responde estrutura. É a mesma razão que o `_Leitor` da régua já carrega,
    e esta casa já pagou por ler árvore com `grep`.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        #: `endereço` → os alvos com que a página o escreve.
        self.alvos: dict[str, set[str]] = {}
        #: Os endereços cujo elemento tem um filho MUDO — ver `molde_do_lugar`.
        self.mudos: set[str] = set()
        self._pilha: list[dict[str, Any]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        d = {k: (v or "") for k, v in attrs}
        chave = (d.get("data-campo") or d.get("data-papel")
                 or d.get("data-hef") or "")
        alvo = d.get("data-hef-alvo") or "texto"
        if chave:
            self.alvos.setdefault(chave, set()).add(alvo)
        quadro: dict[str, Any] = {"tag": tag, "chave": chave, "alvo": alvo,
                                  "texto": [], "filhos": []}
        if self._pilha:
            self._pilha[-1]["filhos"].append(quadro)
        self._pilha.append(quadro)
        if tag in _SEM_FECHO:
            self._fechar(tag)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in _SEM_FECHO:
            self._fechar(tag)

    def handle_endtag(self, tag: str) -> None:
        self._fechar(tag)

    def handle_data(self, data: str) -> None:
        for quadro in self._pilha:
            quadro["texto"].append(data)

    def _fechar(self, tag: str) -> None:
        # PROCURA O QUADRO DA TAG, e não presume que é o topo: um `</div>`
        # sobrando desalinharia a pilha para sempre.
        for i in range(len(self._pilha) - 1, -1, -1):
            if self._pilha[i]["tag"] == tag:
                break
        else:
            return
        while len(self._pilha) > i:
            quadro = self._pilha.pop()
            if (quadro["chave"] and quadro["alvo"] == "texto"
                    and any(not "".join(f["texto"]).strip()
                            for f in quadro["filhos"])):
                self.mudos.add(quadro["chave"])

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

#: `pagina` → o olho já passado por ela. Lido uma vez por página.  # (noqa-acento): nome de campo
_ALVOS: dict[str, _OlhoNaPagina] = {}


def _olhar_a_pagina(pagina: str) -> _OlhoNaPagina | None:
    """A página publicada, lida e lembrada. `None` quando ela não abre."""
    lembrado = _ALVOS.get(pagina)
    if lembrado is not None:
        return lembrado
    from hefesto_dualsense4unix.interface import onde

    try:
        doc = onde.pagina(pagina, publicado=True).read_text(encoding="utf-8")
    except OSError:
        return None
    olho = _OlhoNaPagina()
    olho.feed(doc)
    olho.close()
    _ALVOS[pagina] = olho
    return olho


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
    olho = _olhar_a_pagina(pagina)
    return olho.alvos if olho is not None else {}


def enderecos_que_o_texto_apaga(pagina: str) -> frozenset[str]:
    """Os endereços cujo elemento tem um filho que o TEXTO não sabe dizer.

    A TERCEIRA EXCEÇÃO DO TRAVESSÃO, e ela é de COMPORTAMENTO, não de contador.
    O alvo `texto` escreve `el.textContent`, e isso APAGA os filhos. Onde o
    filho é `<span class="pt">•</span>` nada se perde: o ponto está no texto e
    volta no texto. Onde o filho é MUDO — um elemento sem texto nenhum, que só
    existe para o CSS desenhar algo — o texto não tem como devolvê-lo.

    MEDIDO em 02/09/2026, com o piloto de verdade e um dublê de TEMPO (mesa
    vazia até 8 s, mesa real depois; o daemon dela nunca foi tocado), na
    `06-navegacao`::

        com o molde   1-mesa-vazia  navega filhos=0 '—'
                      2-o-controle-voltou  filhos=0 'USB • Navega o PC'
        sem o molde   1-mesa-vazia  navega filhos=2 'USB • Navega o PC'
                      2-o-controle-voltou  filhos=2 'USB • Navega o PC'

    O endereço `navega` é `<div class="nav-est" data-campo="navega"><span
    class="bolinha"></span>USB <span class="pt">•</span> Navega o PC</div>`. O
    travessão matou o `<span class="bolinha">` — o PONTO VERDE que diz quem
    navega o PC —, e ele **não volta quando o controle volta**: `a06_navegacao`
    emite exatamente o texto que já está lá, `el.textContent !== t` dá falso, e
    o nó nunca mais é tocado. Só trocar de aba (que recarrega o documento) o
    traz de volta.

    UMA CURA QUE APAGA E NÃO DEVOLVE É PIOR QUE A DOENÇA: a mesa dela conecta e
    desconecta o tempo todo, e o dano dura enquanto ela ficar naquela aba.

    OS SEIS ENDEREÇOS QUE ISTO POUPA HOJE, medidos nas dez publicadas em
    03/09/2026: `06-navegacao·navega` (o ponto), `04-iluminacao·troca.item`,
    `05-vibracao·forca`, `05-vibracao·motor`, `08-conexoes·exame` e
    `10-perfis·editor.prioridade.dica`.

    FATO SUBSTITUÍDO — 03/09/2026: esta linha dizia *"os DOIS endereços…
    `04-iluminacao·aceso`"*. O `aceso` saiu da página publicada: a cura de 02/09
    renomeou o endereço para `luz` com alvo `html` (ver a nota do campo `luz` em
    `a04_iluminacao`), e o `html` já é poupado por
    `ALVOS_QUE_O_TRAVESSAO_NAO_ATENDE`. O desenho da barra de luz continua
    inteiro — por outra porta.

    O QUE ISTO NÃO PODE PARECER: uma desculpa para o desenho ficar na tela. Os
    `identidade` da Jogar, da Iluminação e da Vibração TÊM filho — mas o filho é
    `<span class="pt">•</span>`, que o texto reproduz. Eles continuam no molde,
    e a cura do estado vazio continua inteira onde ela pega.
    """
    olho = _olhar_a_pagina(pagina)
    return frozenset(olho.mudos) if olho is not None else frozenset()


# ---------------------------------------------------------------------------
# O LUGAR VAZIO DIZ O QUE O DESENHO DIZ — O-LUGAR-VAZIO-DIZ-O-QUE-O-DESENHO-DIZ-01
# ---------------------------------------------------------------------------
# A QUEIXA DELA, 23/09/2026, com a foto da 08 e nenhum controle na mesa: o topo
# dizia `Nenhum controle` e os cartões `Sony • Player 1 • Cosmic Red • USB` e
# `Sony • Player 2 • Starlight Blue • BT`, com a barra rosa do P1 acesa. Não era
# cache: o nome é `html` e a barra é `cor`, e num lugar vazio ninguém os
# escrevia. MEDIDO no piloto oculto, nesta árvore, antes da cura: com um
# controle de mentira no P2 que depois SAI, o cartão do P2 continuava dizendo
# `Sony • Player 2 • USB` três segundos depois, com o topo em `Nenhum controle`.
#
# A CLASSE: sete páginas publicam campo por lugar de alvo `html`, `cor` ou
# `atributo`, e só três declaravam o próprio `LUGAR_VAZIO`. Cada aba inventando
# o seu é o defeito que a casa mais paga — então o dono é UM, e é o desenho.

#: Um `data-controle` que é LUGAR (`p1`…`p4`), e não o SVG (`dualsense`).
_E_LUGAR = re.compile(r"p\d+")


def _o_numero_trocado(valor: str, de: int, para: int) -> str:
    """O número do jogador `de` vira `para` onde ele É o número: `P3`, `Player 3`.

    A FRONTEIRA É A TRAVA: `#74588e`, `3px`, `0.3` e `gc-p3` não são o número
    de um jogador, e nenhum deles casa. Quem confere que a troca não pegou
    nada a mais é `_a_palavra_do_desenho`, contra o segundo lugar vazio.
    """
    return re.sub(rf"(?<![0-9A-Za-z#_.-])([Pp]?){de}(?![0-9A-Za-z_%-])",
                  lambda m: f"{m.group(1)}{para}", valor)


class _OLugarNoDesenho(html.parser.HTMLParser):
    """Os lugares da página publicada, campo a campo — com o miolo CRU do `html`.

    CRU, E NÃO O TEXTO: o alvo `html` escreve `innerHTML`, e o nome do cartão da
    08 é `Player 3 <span class="pt">•</span> Desconectado`. O texto perderia o
    `<span>`, e o `•` sairia colado.

    SÓ OS DESCENDENTES DO LUGAR: o `achar()` do piloto procura com
    `querySelectorAll` DENTRO do `[data-controle]`, e o próprio elemento do
    lugar nunca é alcançado — a 06 põe o `plastico` nele.
    """

    def __init__(self, doc: str) -> None:
        super().__init__(convert_charrefs=True)
        self._doc = doc
        #: Onde começa cada linha — o `getpos()` conta linha e coluna.
        self._linhas = [0, *(m.end() for m in re.finditer("\n", doc))]
        #: `pref` → `campo` → `[((alvo, atributo), valor), …]`, em ordem.
        self.campos: dict[str, dict[str, list[tuple[tuple[str, str], str]]]] = {}
        #: Os lugares que o desenho publica VAZIOS, em ordem.
        self.vazios: list[str] = []
        self._pilha: list[dict[str, Any]] = []

    def _onde(self) -> int:
        linha, coluna = self.getpos()
        return self._linhas[linha - 1] + coluna

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        d = {k: (v or "") for k, v in attrs}
        lugar = d.get("data-controle", "")
        lugar = lugar if _E_LUGAR.fullmatch(lugar) else ""
        vazio = d.get("data-conectado") == "nao"  # (noqa-acento) valor do atributo
        if lugar and vazio and lugar not in self.vazios:
            self.vazios.append(lugar)
        dentro = next((q["lugar"] for q in reversed(self._pilha) if q["lugar"]), "")
        chave = d.get("data-campo") or d.get("data-papel") or d.get("data-hef") or ""
        quadro: dict[str, Any] = {
            "tag": tag, "lugar": lugar, "campo": None,
            "miolo": self._onde() + len(self.get_starttag_text() or "")}
        if chave and dentro and not lugar:
            alvo = d.get("data-hef-alvo") or "texto"
            nome = (d.get("data-hef-atributo") or "").strip().lower()
            if alvo != "atributo":
                nome = ""
            quadro["campo"] = (dentro, chave, (alvo, nome), d.get(nome, "") if nome else "")
        self._pilha.append(quadro)
        if tag in _SEM_FECHO:
            self._fechar(tag, quadro["miolo"])

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in _SEM_FECHO:
            self._fechar(tag, self._pilha[-1]["miolo"])

    def handle_endtag(self, tag: str) -> None:
        self._fechar(tag, self._onde())

    def _fechar(self, tag: str, fim: int) -> None:
        for i in range(len(self._pilha) - 1, -1, -1):
            if self._pilha[i]["tag"] == tag:
                break
        else:
            return
        while len(self._pilha) > i:
            quadro = self._pilha.pop()
            if quadro["campo"] is None:
                continue
            lugar, chave, assinatura, valor = quadro["campo"]
            if assinatura[0] == "html":
                valor = self._doc[quadro["miolo"]:fim]
            self.campos.setdefault(lugar, {}).setdefault(chave, []).append(
                (assinatura, valor))


def _a_palavra_do_desenho(alvo: str, por_lugar: dict[int, list[str]]) -> Callable[[int], str]:
    """O que o desenho diz daquele campo num lugar vazio de número `n`.

    `por_lugar` é `{número: [valores]}` dos lugares que o desenho publica vazios.
    Quatro respostas, na ordem:

    * `cor` é sempre `""` — a cor sai e o elemento volta à folha de estilo;
    * os lugares vazios dizem a MESMA coisa (o traço, a paleta da 04) — é ela;
    * dizem a mesma coisa A MENOS DO NÚMERO (`Player 3 •…`, `Player 4 •…`) — é o
      molde, com o número do lugar. A troca é CONFERIDA: aplicada ao primeiro,
      tem de reproduzir os outros letra por letra;
    * qualquer outra coisa — um só lugar vazio com número dentro, ou exemplos
      diferentes em cada um (o colorway `galactic-purple` e `white`) — é `""`:
      o desenho não diz UMA coisa do lugar vazio, e campo sem informação não
      mostra nada.
    """
    if alvo == "cor":
        return lambda _n: ""
    valores: dict[int, str] = {}
    for n, vs in por_lugar.items():
        if not vs:
            continue
        if len(set(vs)) != 1:
            return lambda _n: ""
        valores[n] = vs[0]
    if len(set(valores.values())) == 1 and (
            len(valores) > 1
            or all(_o_numero_trocado(v, n, n + 1) == v for n, v in valores.items())):
        (unica,) = set(valores.values())
        return lambda _n: unica
    if len(valores) > 1:
        ref = min(valores)
        molde = valores[ref]
        if all(_o_numero_trocado(molde, ref, n) == v for n, v in valores.items()):
            return lambda n: _o_numero_trocado(molde, ref, n)
    return lambda _n: ""


#: Nome da página → `{pref: {campo: valor}}`, lido uma vez por página.
_DESENHO_DO_VAZIO: dict[str, dict[str, dict[str, str]]] = {}


def o_que_o_desenho_diz_do_lugar_vazio(pagina: str) -> dict[str, dict[str, str]]:
    """`{pref: {campo: valor}}` — o lugar vazio do desenho, para os QUATRO lugares.

    UM DONO SÓ para o lugar vazio de toda aba, e ele é o desenho: o P3 e o P4
    nascem vazios na página publicada, por decisão dela de 31/08, e o que eles
    mostram é o que um lugar vazio mostra. Só os alvos em que o travessão não
    chega (`ALVOS_QUE_O_DESENHO_DIZ`), e só os campos de UM alvo — um endereço
    que a página escreve de dois jeitos (o `alto-canal` da 02 é `classe` num
    elemento e `html` noutro) não tem uma palavra que sirva aos dois.

    O QUE A ABA DECLARA EM `LUGAR_VAZIO` VENCE — é aplicado depois, em
    `apagar_os_lugares_sem_dono`: a linha LEDs apagada da 04 é pedido dela que o
    desenho não tem.

    Vazio quando a página não abre ou não publica lugar vazio nenhum: aí o
    desenho não diz nada, e o travessão continua sozinho.
    """
    lembrado = _DESENHO_DO_VAZIO.get(pagina)
    if lembrado is None:
        lembrado = _ler_o_lugar_vazio_do_desenho(pagina)
        _DESENHO_DO_VAZIO[pagina] = lembrado
    return {pref: dict(campos) for pref, campos in lembrado.items()}


def _ler_o_lugar_vazio_do_desenho(pagina: str) -> dict[str, dict[str, str]]:
    from hefesto_dualsense4unix.interface import onde

    try:
        doc = onde.pagina(pagina, publicado=True).read_text(encoding="utf-8")
    except OSError:
        return {}
    olho = _OLugarNoDesenho(doc)
    olho.feed(doc)
    olho.close()
    if not olho.vazios:
        return {}
    assinaturas: dict[str, set[tuple[str, str]]] = {}
    for campos in olho.campos.values():
        for chave, ocorrencias in campos.items():
            assinaturas.setdefault(chave, set()).update(a for a, _ in ocorrencias)
    fora: dict[str, dict[str, str]] = {pref: {} for pref in sorted(TODOS_OS_LUGARES)}
    for chave, sinais in sorted(assinaturas.items()):
        if len(sinais) != 1:
            continue
        ((alvo, _nome),) = sinais
        if alvo not in ALVOS_QUE_O_DESENHO_DIZ:
            continue
        palavra = _a_palavra_do_desenho(alvo, {
            int(pref[1:]): [v for _, v in olho.campos.get(pref, {}).get(chave, [])]
            for pref in olho.vazios})
        for pref in fora:
            fora[pref][chave] = palavra(int(pref[1:]))
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
    # A CHAVE TEM DONO — `_chave_do_molde`, que diz por que o perfil entra.
    chave = _chave_do_molde(pagina, ctx)
    lembrado = _MOLDE.get(chave)
    if lembrado is not None and chave in _PINTA:
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
    apaga = enderecos_que_o_texto_apaga(pagina)
    molde = dict.fromkeys(
        sorted(k for k in chaves_por_controle(seria)
               if not (alvos.get(k, set()) & ALVOS_QUE_O_TRAVESSAO_NAO_ATENDE)
               and k not in apaga),
        TRAVESSAO)
    _MOLDE[chave] = molde
    _PINTA[chave] = frozenset(chaves_por_controle(seria))
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

    _, conta_b = mesa_viva.texto_da_contagem(ctx.mesa)
    # O CHIP "PERFIL ATIVO" É DAS DEZ ABAS, e por isso ele pergunta ao dono —
    # costura da ONDA D, 06/09/2026. Aqui estava `ctx.state.get("active_profile")`
    # cru, que só tem a PRIMEIRA das duas pernas: o daemon. Com ele respondendo
    # `active_profile: null` — o estado da máquina dela, descrito em
    # `profiles_actions.perfil_que_esta_valendo` — as dez abas escreviam o
    # travessão sobre um perfil que ESTAVA valendo, e a `PERFIL-MODO-01` mediu.
    # `perfil.nome_do_ativo` resolve as duas pernas (daemon, depois o marcador em
    # disco) e é o mesmo dono que a aba 05 e a 10 passaram a ler.
    from hefesto_dualsense4unix.interface.pacotes import perfil as _perfil

    ativo = _perfil.nome_do_ativo(ctx.state)
    return {
        # O «N controles:» SAIU DA TELA — 22/09/2026, pedido dela:
        # *"Esse x controles cai fora pra ganharmos espaçço Lateral"*.  # (noqa-acento): dela
        # O cabeçalho diz só `x USB · y BT`, que já conta; e sem controle
        # nenhum a metade que sobrou diria nada, então ela diz `Nenhum controle`.
        "conta-b": conta_b or SEM_CONTROLE_NA_MESA,
        "perfil": ativo or "—",
        # AS DUAS DICAS DO RODAPÉ, e elas são do topo pela MESMA razão que o
        # resto daqui: o `fim.html` é um só para as dez páginas, logo não
        # pertence a pacote de aba nenhuma.
        #
        # O DEFEITO QUE ISTO CURA, medido em 03/09/2026: o desenho congelou o
        # EXEMPLO do pedido dela — *"Salvar Perfil grava no Mortal Kombat"* — em
        # vez do nome, e as dez abas diziam "Grava no perfil Mortal Kombat" com
        # `meu_perfil` ativo. Uma dica que nomeia com confiança o perfil errado,
        # sobre o botão que GRAVA NO DISCO, é o pior arranjo possível.
        #
        # SEM PERFIL ATIVO NÃO SE INVENTA NOME: o texto cai para "no perfil
        # ativo", que é o mesmo que o desenho já traz congelado — dizer "no
        # perfil —" seria pior do que não dizer.
        # Sem perfil ativo, o Salvar grava no «Freestyle» (O-MODO-FREESTYLE-02),
        # e a dica diz onde — o dono é `rodape.perfil_do_salvar`.
        "rodape.salvar": _dica_do_salvar(ativo or _onde_o_salvar_grava()),
        "rodape.exportar": _dica_do_exportar(ativo),
    }


#: O QUE A DICA DIZ QUANDO NÃO HÁ PERFIL ATIVO. É a mesma palavra que o
#: `fim.html` congela, para que a tela antes e depois da pintura diga a mesma
#: coisa — e nunca um nome que não existe.
_SEM_PERFIL = "no perfil ativo"


def _dica_do_salvar(ativo: str) -> str:
    """A dica do botão que GRAVA, com o nome do perfil que vai receber.

    O texto é o do desenho, palavra por palavra; o que muda é o nome. Reescrevê-lo
    aqui faria duas versões da mesma frase, e a do desenho envelheceria calada —
    então esta função só troca a metade que é dado.
    """
    onde = f"no perfil {ativo}" if ativo else _SEM_PERFIL
    return (f"Grava {onde}. É onde a mudança vai cair: o que você salvar aqui "
            "volta sozinho toda vez que este jogo abrir.")


def _onde_o_salvar_grava() -> str:
    """O perfil em que o «Salvar Perfil» grava sem perfil ativo — do dono."""
    from hefesto_dualsense4unix.interface.pacotes.rodape import perfil_do_salvar

    return perfil_do_salvar({})


def _dica_do_exportar(ativo: str) -> str:
    """A dica do botão que leva o perfil para um arquivo, com o nome certo."""
    qual = f"o perfil {ativo}" if ativo else "o perfil ativo"
    return (f"Escreve {qual} num arquivo .json, para guardar ou levar para "
            "outra máquina.")


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
#     vpad_motivo            1     0   <- SÓ A GTK LÊ, e de propósito desde 13/09
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

#: A SIGLA DE MÁQUINA do transporte — **e ela não é mais a palavra da tela.**
#: O `.get(..., "")` é o ponto: ausência vira travessão, nunca uma das duas.
#:
#: Até 05/09/2026 este comentário afirmava ser "a MESMA tradução do
#: `mesa_viva.mesa_do_estado`", que era `"USB" if transporte == "usb" else
#: "BT"` — e as duas divergiam exatamente na AUSÊNCIA: a de lá dizia **"BT"**
#: sobre um campo que o daemon não publicou, e a aba 01 afirmava rádio sobre
#: nada. Hoje o `mesa_viva` LÊ este dicionário, e a afirmação virou verdade.
#:
#: **A PALAVRA DA TELA SAIU DAQUI — ONDA4-S10, 06/09/2026.** A decisão é dela
#: (D-05): *"cabo / rádio, pela função que já existe."* A dona é
#: `app/actions/home_actions.palavra_do_transporte`, e ela tem duas coisas que
#: esta tabela não tem: transporte desconhecido volta CRU (para alguém o ver em
#: vez de sumir atrás de uma frase genérica) e transporte AUSENTE diz *"não sei
#: por onde"*. As abas 01, 07 e 09 já a chamam.
#:
#: **POR QUE ESTA TABELA CONTINUA VIVA, e é dívida DECLARADA, não descuido:**
#: `via` é a chave que `mesa_viva.mesa_do_estado` publica, e ela é COMPARADA em
#: dois arquivos que não são desta posse —
#: `interface/monta.py:877` (o descarte que evita `P2 • BT • BT` na fita das dez
#: abas) e `interface/pacotes/a08_conexoes.py:2498`, `:2499`, `:2505` e `:2513`
#: (o agrupamento por adaptador de rádio). Trocar a palavra desta tabela sem
#: tocar nesses cinco pontos faria a Conexões mostrar ZERO controles no rádio
#: com os dois no rádio — calado, sem log e sem régua vermelha. O caminho está
#: pronto e é de UMA linha em cada ponto: o item da mesa publica `transporte`,
#: a chave crua, ao lado da palavra. Relatado em
#: `docs/process/agentes/2026-09-06/ONDA4-S10-O-TRANSPORTE-01.md`.
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

    # A PALAVRA VEM DO DONO — costura da ONDA B, 06/09/2026. `VIA_DO_TRANSPORTE`
    # era a sigla de máquina; quem a comparava passou a ler o `transporte` cru,
    # então o que sobra aqui é texto de tela, e texto de tela vem do dono.
    from hefesto_dualsense4unix.app.actions.home_actions import (
        palavra_do_transporte,
    )

    # E A AUSÊNCIA VOLTA A SER O TRAVESSÃO, aqui e só aqui — defeito MEDIDO em
    # 06/09/2026. O dono responde `"não sei por onde"` para o campo vazio, e
    # isso é certo no CAMPO DO TRANSPORTE, que responde *por onde ele fala*.
    # Esta função responde outra pergunta — *como este controle se chama* —, e o
    # último degrau dela é o transporte só porque um transporte lido já é uma
    # identidade fraca. Transporte NÃO LIDO não identifica nada: sem a guarda, um
    # controle sem leitura nenhuma passou a se chamar "não sei por onde", que
    # ocupa o lugar do nome sem dizer nada. O travessão é o que o desenho dela
    # espera onde não há o que dizer.
    if not str(c.get("transport") or "").strip():
        return "—"
    return palavra_do_transporte(c.get("transport")) or "—"


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
        #
        # A LISTA VAZIA PASSA TAMBÉM, e ela é o caso que mais importa — foi o
        # `valor and` desta linha que fez a coluna Atenção da aba 01 MENTIR,
        # fotografada no DOM vivo em 04/09/2026:
        #
        #     "RÁDIO · Dois rádios da bancada estão em portas vizinhas"   ← o MOCKUP
        #     "nenhum aviso"                                              ← o produto
        #
        # As duas frases na tela, no mesmo tique. Com a lista vazia descartada, o
        # endereço some do pacote, o piloto nunca visita aqueles seis elementos, e
        # o que o gerador desenhou fica lá para sempre.
        #
        # LISTA VAZIA É UMA RESPOSTA, não a ausência de uma: quer dizer *"não há
        # nada nesta coleção"*, e a tela precisa ouvir isso para apagar o que
        # mostrava. É a mesma regra que `apagar_os_lugares_sem_dono` já aplica aos
        # quatro lugares da mesa, e que o `forEach` do bootstrap já sabe honrar —
        # ele escreve `''` no que sobra.
        #
        # (`all([])` é `True`, então a condição de escalares já aceitava a vazia;
        # quem a barrava era só o `valor and` à esquerda.)
        if isinstance(valor, list):
            if all(not isinstance(x, (dict, list)) for x in valor):
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
    # AS DUAS CHAVES DO LUGAR — 21/09/2026, ver `LUGAR_VAZIO` e
    # `MARCAS_DO_LUGAR`. São `dict` na raiz, e o laço acima come todo `dict`
    # calado: é o mesmo buraco que o `blocos` passou dois dias dentro.
    vazio = pacote.get(LUGAR_VAZIO)
    if isinstance(vazio, dict) and vazio:
        fora[LUGAR_VAZIO] = {str(k): v for k, v in vazio.items()
                             if not isinstance(v, (dict, list))}
    marcas = pacote.get(MARCAS_DO_LUGAR)
    if isinstance(marcas, dict):
        fora[MARCAS_DO_LUGAR] = {
            str(classe): sorted({para_pref.get(str(u)) or para_pref.get(_so_hex(str(u)))
                                 or str(u) for u in (lugares or [])})
            for classe, lugares in marcas.items()}
    # OS CAMPOS DO LUGAR, com a mesa vazia — ver `CAMPOS_DO_LUGAR`. Lista na
    # raiz: o laço acima a poria na `mesa` como campo solto, e ela é instrução.
    campos = pacote.get(CAMPOS_DO_LUGAR)
    if isinstance(campos, (list, tuple, set, frozenset)) and campos:
        fora[CAMPOS_DO_LUGAR] = sorted(str(k) for k in campos)
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
    # impedir: `a07_lancadores.py` traz `@registrar("07-lancadores.html")` desde
    # que foi ligada, e `pacote_da_pagina` devolve 26 chaves para ela. Achado em
    # 02/09/2026 por um teste que assumiu a frase da casa e reprovou.
    #
    # A FRASE DA CASA CAIU JUNTO — 09/09/2026, LANCADORES-ZERO-01 §5. Estas
    # linhas diziam que *"a casa diz em dois lugares que ela é a aba SEM
    # pacote (`hefesto_vivo.SEM_PACOTE` e o comentário do `_tique`)"*, e os
    # dois lugares foram reescritos: a constante era morta — ninguém a lia — e
    # os comentários nomeavam esta aba. **Uma correção pela metade deixa as
    # duas versões vivas**, que é o defeito que a regra existe para matar.
    a07_lancadores,  # noqa: F401
    a08_conexoes,  # noqa: F401
    a09_sistema,  # noqa: F401
    a10_perfis,  # noqa: F401
    # A `a11` NÃO É UMA ABA — é a página AVULSA da calibração dos sensores
    # (`calibrar-sensores.html`), que abre por fora das dez, por um botão da
    # Controles. Ela entra aqui pela MESMA razão que as dez: o fecho de import
    # do `portao_a_casa_sabe_e_o_produto_nao_faz` lê o AST, e um nome montado
    # pelo `_carregar_tudo()` não aparece ali. F3-CALIBRAR, 11/09/2026.
    a11_calibrar_sensores,  # noqa: F401
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

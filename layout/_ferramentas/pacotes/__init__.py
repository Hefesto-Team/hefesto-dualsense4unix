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
import sys
from dataclasses import dataclass, field

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

    state: dict
    mesa: list[dict] = field(default_factory=list)
    conectados: list[dict] = field(default_factory=list)
    estados: dict = field(default_factory=dict)

    def por_uniq(self, uniq: str) -> dict:
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
PACOTES: dict[str, object] = {}


def registrar(pagina: str):
    """Decorador: `@registrar("01-jogar.html")` põe a função na tabela.

    POR QUE DECORADOR, e não um dicionário escrito à mão: o dicionário obriga a
    escrever o nome da página duas vezes — no módulo e na tabela — e é o segundo
    lugar que diverge. Aqui o módulo declara a si mesmo, e importar é registrar.
    """
    def dentro(fn):
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
GESTOS: dict[tuple[str, str], object] = {}


def gesto(pagina: str, nome: str):
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
    def dentro(fn):
        chave = (pagina, nome)
        if chave in GESTOS:
            raise SystemExit(
                f"ERRO: o gesto {nome!r} de {pagina} já tem dono "
                f"({GESTOS[chave].__module__}). Dois donos para o mesmo botão é "
                f"o defeito que este despachante existe para impedir.")
        GESTOS[chave] = fn
        return fn
    return dentro


def gesto_da_pagina(pagina: str, nome: str):
    """Quem atende aquele botão, ou `None`.

    `None` NÃO é erro: é o estado honesto de um botão que ainda não foi ligado,
    e quem chama tem de **recusar dizendo**. Um botão que responde calado quando
    não há quem atenda é a `A-CASA-SABE-E-O-PRODUTO-NAO-FAZ` em miniatura —
    quem clicou conclui que funcionou.
    """
    return GESTOS.get((pagina, nome)) or GESTOS.get(("*", nome))


def pacote_da_pagina(pagina: str, ctx: Contexto) -> dict | None:
    """O pacote daquela página, ou `None` se ela ainda não tem quem a pinte.

    `None` NÃO é erro: é o estado honesto de uma aba que ainda não foi ligada, e
    o piloto o distingue de um pacote vazio — um diz "ninguém pinta isto ainda",
    o outro diz "pintei nada", e confundir os dois é como uma tela morta passa
    por tela sem novidade.
    """
    fn = PACOTES.get(pagina)
    return fn(ctx) if fn else None


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


def topo(ctx: Contexto) -> dict:
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
    import mesa_viva

    conta, conta_b = mesa_viva.texto_da_contagem(ctx.mesa)
    return {
        # O `●` é do desenho e já está na página; o texto começa depois dele.
        "conta": conta.replace("● ", "").strip(),
        "conta-b": conta_b,
        "perfil": ctx.state.get("active_profile") or "—",
    }


def normalizar(pacote: dict, para_pref: dict[str, str] | None = None) -> dict:
    """O pacote na forma que a tela consome: `{mesa, colunas}` e nada mais.

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
    colunas: dict[str, dict] = {}
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
    return {"mesa": mesa, "colunas": colunas}


def _so_hex(chave: str) -> str:
    """`d42f4b0000d8` → o mesmo, e `d4:2f:00:00:…` → `d42f…`. Uma forma só para casar."""
    return chave.replace(":", "").lower()


def _carregar_tudo() -> None:
    """Importa os módulos de pacote, que é o que os registra."""
    import importlib
    aqui = pathlib.Path(__file__).resolve().parent
    for f in sorted(aqui.glob("a[0-9][0-9]_*.py")):
        importlib.import_module(f"pacotes.{f.stem}")
    # O RODAPÉ É DAS DEZ, e por isso não casa com `aNN_*`: ele mora no
    # `topo.html`, o esqueleto compartilhado, e seus gestos são registrados em
    # `("*", nome)`. Sem esta linha ele não é importado, logo não se registra,
    # logo os quatro botões do rodapé recusam em todas as abas — em silêncio,
    # porque um gesto não registrado é indistinguível de um gesto sem dono.
    importlib.import_module("pacotes.rodape")


_carregar_tudo()

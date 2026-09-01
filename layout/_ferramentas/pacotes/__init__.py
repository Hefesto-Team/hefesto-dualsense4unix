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


def pacote_da_pagina(pagina: str, ctx: Contexto) -> dict | None:
    """O pacote daquela página, ou `None` se ela ainda não tem quem a pinte.

    `None` NÃO é erro: é o estado honesto de uma aba que ainda não foi ligada, e
    o piloto o distingue de um pacote vazio — um diz "ninguém pinta isto ainda",
    o outro diz "pintei nada", e confundir os dois é como uma tela morta passa
    por tela sem novidade.
    """
    fn = PACOTES.get(pagina)
    return fn(ctx) if fn else None


def _carregar_tudo() -> None:
    """Importa os módulos de pacote, que é o que os registra."""
    import importlib
    aqui = pathlib.Path(__file__).resolve().parent
    for f in sorted(aqui.glob("a[0-9][0-9]_*.py")):
        importlib.import_module(f"pacotes.{f.stem}")


_carregar_tudo()

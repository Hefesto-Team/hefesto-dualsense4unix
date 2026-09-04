"""As frases que ela mandou tirar da tela, e o lugar único onde elas moram.

ELA, 31/08/2026, sobre o aviso do Modo Nativo: *"qualquer coisa fora isso tá
incorreta"*. A regra que sobrou é curta e vale para a interface inteira:

    **NENHUM ALARME SEM MEDIÇÃO.**

As três frases abaixo alarmavam sobre número que **ensaio nenhum deste
repositório mede**. Não são erro de gosto: uma frase que assusta sem medir
custa a confiança dela em todas as outras.

POR QUE ESTE MÓDULO EXISTE — e é o OITAVO CONFLITO da leva de 04/09/2026,
achado pela frente da aba 01 e da mesma família dos sete do `O-PO-DECIDE`:

A proibição vivia **só** dentro de `aba01._conferir`, que lê o **HTML
ESTÁTICO** da página gerada. A coluna Atenção, porém, é escrita em **tempo de
execução** — o piloto manda o texto pelo `_json`. Logo um agente cumprindo a
decisão [01] ao pé da letra (*"o aviso do Modo Nativo na coluna Atenção"*)
poria a frase banida na tela dela **com o gerador VERDE**.

A régua olhava o lugar errado. Agora a lista é uma só, e há duas guardas
lendo-a: a estática (`aba01._conferir`) e a de execução (`hefesto_vivo._json`,
o funil por onde TODO valor passa a caminho do WebView).

O QUE A DECISÃO [01] AINDA PODE TER, e é a leitura de PO de 04/09/2026: a
coluna Atenção pode dizer **o estado medido** — *o Modo Nativo está ligado, a
Ponte com o jogo está desligada* — porque isso o produto mede e sabe. O que ela
não pode é PROFETIZAR consequência que ninguém mediu. A decisão dela de 31/08
vence a minha recomendação de 04/09, como venceu nas outras sete.
"""

from __future__ import annotations

#: Trechos proibidos em qualquer texto que chegue à tela. A comparação é por
#: SUBSTRING e sem normalizar: são trechos literais que já estiveram no
#: produto, e uma reescrita que os evite por acaso já não é a frase banida.
FRASES_BANIDAS: tuple[str, ...] = (
    "derrubam o controle",
    "resultado é ZERO",
    "duros como no PS5",
)


def frase_banida_em(texto: str) -> str | None:
    """O primeiro trecho banido presente em ``texto``, ou ``None``."""
    for frase in FRASES_BANIDAS:
        if frase in texto:
            return frase
    return None

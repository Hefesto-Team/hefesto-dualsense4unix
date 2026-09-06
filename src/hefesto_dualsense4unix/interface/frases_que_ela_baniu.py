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

A TERCEIRA GUARDA — 06/09/2026, ONDA5-01-02, e ela lê o **FONTE**:

As duas guardas de 04/09 param a frase na SAÍDA — o HTML já gerado e o valor a
caminho do WebView. Nenhuma delas olha de onde a frase VEM, e por isso *"Alguns
jogos derrubam o controle no meio da partida"* sobreviveu uma semana em
`app/actions/home_actions.py` com as duas verdes: nada as fazia olhar para lá.
Pior — uma régua desta casa **exigia que ela ficasse**, como lápide de si
mesma. Agora `tests/unit/test_a_frase_que_ela_baniu_nao_chega_a_tela.py`
(`test_nenhuma_banida_vive_no_fonte`) varre `app/actions/` e `interface/` pelos
literais e pelos comentários, com duas isenções declaradas: este módulo, que é
o dono da lista, e os comentários de `aba01.py`, onde a lápide de 31/08 mora.

**Três réguas independentes é o desenho desta casa** — o mesmo dos dois portões
de endereço de rádio, e pela mesma razão: cada uma tem um ponto cego que só a
outra alcança.
"""

from __future__ import annotations

#: Trechos proibidos em qualquer texto que chegue à tela. A comparação é por
#: SUBSTRING e sem normalizar: são trechos literais que já estiveram no
#: produto, e uma reescrita que os evite por acaso já não é a frase banida.
#:
#: **O TERCEIRO TRECHO ESTAVA CEGO PARA O PRODUTO — corrigido em 06/09/2026,
#: ONDA5-01-02.** Ele era ``"duros como no PS5"``, a forma que o gerador da
#: interface nova cita; a janela antiga escrevia *"os gatilhos ficam duros de
#: apertar, como no PS5"*, e ``"duros como no PS5" in`` essa frase é ``False``.
#: A lista nasceu medida contra o texto do gerador, não contra o do produto, e
#: **um terço da proibição foi decorativo desde o primeiro dia**.
#:
#: ``"gatilhos ficam duros"`` casa com as DUAS escritas, e é o trecho mais
#: curto que casa sem pegar frase inocente. **A sprint propunha
#: ``"como no PS5"`` e a medição o RECUSOU**: esse trecho aparece em
#: ``app/actions/config/secao_controles.py``, na `DICA_MIC_NO_RADIO` —
#: *"Traz o microfone deste controle pelo rádio, como no PS5"* —, que é frase
#: medida e viva. Ele reprovaria a guarda de fonte sobre ela e, pior, o funil
#: de execução a recusaria a caminho do WebView: a régua contra o alarme sem
#: medição viraria o alarme sem medição. Medido em 06/09/2026 com
#: ``grep -rn "gatilhos ficam duros" src/``: duas ocorrências, as duas a frase
#: banida; ``grep -rn "como no PS5" src/``: quatro, uma delas inocente.
FRASES_BANIDAS: tuple[str, ...] = (
    "derrubam o controle",
    "resultado é ZERO",
    "gatilhos ficam duros",
)


def frase_banida_em(texto: str) -> str | None:
    """O primeiro trecho banido presente em ``texto``, ou ``None``."""
    for frase in FRASES_BANIDAS:
        if frase in texto:
            return frase
    return None

"""As frases — e a PALAVRA — que ela mandou tirar da tela, num lugar só.

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

A PALAVRA ENTROU AO LADO DAS FRASES — 06/09/2026, A-PALAVRA-MESA-SAI-01:

Ela, 06/09: *"Falei do termo mesa que é horrível. Mas os claudes anteriores
entraram na pira de usar isso em tudo no layout. O termo sai e coloca-se termos
simples pro user comum. feature fica."*

Uma frase se compara por trecho; uma PALAVRA, não — ``"mesa" in texto`` casa
com *remessa* e com todo nome de campo que a carrega (``mesa-frase``,
``radio-mesa``, ``perfil-da-mesa``). Por isso a lista é uma segunda tupla, com
régua própria: :data:`PALAVRAS_BANIDAS`, casada por borda de palavra.

**A BORDA IGNORA O QUE ESTÁ COLADO A `-`, `_` ou `.`**, e isso não é detalhe de
regex: é a linha do glossário. `mesa` é nome interno vivo — `mesa_viva.py`,
`app/mesa.py`, `monta.MESA`, `MESA_VAZIA`, `data-campo="mesa-frase"` — e a
sprint diz com todas as letras que *o nome fica*. Quem trocasse identificador
por causa desta lista faria estrago, não cura.
"""

from __future__ import annotations

import re
from functools import cache

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


#: PALAVRAS proibidas em texto de tela, casadas por BORDA DE PALAVRA e sem
#: distinguir maiúscula. Elas são a outra metade da proibição, e a comparação é
#: outra de propósito: :data:`FRASES_BANIDAS` casa por substring porque são
#: frases literais que já estiveram no produto; uma palavra por substring
#: pegaria *remessa* e todo identificador que a carrega.
#:
#: ``mesa`` entrou em 06/09/2026 (A-PALAVRA-MESA-SAI-01). O que entra no lugar
#: dela está no glossário, §1: *os controles*, *todos*, *P1 e P2*, *quem está
#: ligado*. **A feature não sai; a palavra sai** — nenhuma tabela, contagem ou
#: aviso caiu por causa disto.
PALAVRAS_BANIDAS: tuple[str, ...] = ("mesa",)

#: As letras que fazem de uma ocorrência um IDENTIFICADOR e não uma palavra.
#: `-` e `_` estão aqui porque `mesa-frase`, `radio-mesa` e `MESA_VAZIA` são
#: endereços vivos desta casa; os acentuados estão porque `\w` do `re` já os
#: cobre em `str`, e escrever a classe à mão sem eles deixaria *mesamente*
#: passar por palavra inteira.
_COLADO = r"0-9A-Za-zÀ-ÖØ-öø-ÿ_\-"

#: `<style>`, `<script>` e comentário HTML NÃO são tela. Foi medido em
#: 06/09/2026: das 194 ocorrências cruas de `mesa` nos dez mockups, **121
#: estavam em comentário de CSS** e 14 em comentário de HTML — prosa da casa,
#: que o glossário deixa ficar.
_MUDOS = re.compile(
    r"<!--.*?-->|<style\b[^>]*>.*?</style>|<script\b[^>]*>.*?</script>",
    re.S | re.I,
)

#: `<code>` é a ZONA DO IDENTIFICADOR na tela desta casa: é assim que a legenda
#: dos mockups escreve `monta.MESA` e `a10_perfis`. O nome fica, e por isso o
#: que está dentro dele não é palavra de tela.
_CODIGO = re.compile(r"<code\b[^>]*>.*?</code>", re.S | re.I)

#: OS ATRIBUTOS QUE A PESSOA LÊ. `title` é a dica do `?` — o glossário diz que
#: *a explicação mora aqui* —, e uma régua que só olhasse nó de texto daria
#: verde sobre a palavra escondida numa dica.
_ATRIBUTO_LIDO = re.compile(
    r"\b(?:title|placeholder|aria-label|alt)\s*=\s*(\"[^\"]*\"|'[^']*')", re.I
)

_TAG = re.compile(r"<[^>]*>", re.S)


def _apagar(alvo: list[str], inicio: int, fim: int) -> None:
    """Espaço no lugar das letras, do mesmo tamanho."""
    for i in range(inicio, fim):
        if alvo[i] != "\n":
            alvo[i] = " "


def texto_visivel(pagina: str) -> str:
    """O que uma pessoa LÊ nesta página — sem tag, sem CSS, sem identificador.

    A ordem importa, e cada passo tem uma medição atrás:

    1. saem `<style>`, `<script>` e comentário HTML (135 das 194 ocorrências de
       `mesa` de 06/09 moravam aí, e nenhuma delas chega a olho nenhum);
    2. saem os `<code>…</code>`, que são o nome interno escrito de propósito;
    3. saem as tags que sobraram — **menos** os `title`/`placeholder`/
       `aria-label`/`alt`, que a pessoa lê mesmo estando dentro de uma tag.

    **ELA DEVOLVE UMA STRING DO MESMO TAMANHO**, com espaço no lugar do que não
    é tela e a quebra de linha preservada. Isso não é economia: é o que deixa a
    régua dizer *página, linha e frase* em vez de "há uma em algum lugar" — e a
    entrega de uma régua é o endereço do defeito, não o número dele.

    A ENTIDADE FICA COMO ESTÁ (`&nbsp;`, `&amp;`): desfazê-la mudaria o
    tamanho, e nenhuma palavra desta lista se escreve com entidade — a borda de
    palavra trata `;` e `&` como separador, que é o que basta.

    CONFERIDO CONTRA O NAVEGADOR, 06/09/2026: para as quatro abas fotografadas,
    o número que esta função dá é o mesmo do `innerText` da `.nota` num Chrome
    de verdade (13 · 6 · 6 · 3). Um stripper que ninguém conferiu contra o
    motor é a armadilha do `COMO-OLHAR-A-TELA.md`.
    """
    letras = list(pagina)
    for muda in _MUDOS.finditer(pagina):
        _apagar(letras, muda.start(), muda.end())
    limpo = "".join(letras)
    for codigo in _CODIGO.finditer(limpo):
        _apagar(letras, codigo.start(), codigo.end())
    limpo = "".join(letras)
    for tag in _TAG.finditer(limpo):
        lidos = [m.span(1) for m in _ATRIBUTO_LIDO.finditer(tag.group(0))]
        _apagar(letras, tag.start(), tag.end())
        for a, b in lidos:
            # o valor volta SEM as aspas — elas são sintaxe, não leitura.
            for i in range(tag.start() + a + 1, tag.start() + b - 1):
                letras[i] = limpo[i]
    return "".join(letras)


@cache
def _borda(palavra: str) -> re.Pattern[str]:
    """A palavra inteira, e nunca o pedaço de um nome.

    O `functools.cache` porque esta régua roda por LINHA das dez páginas e por
    literal dos dez pacotes — são dezenas de milhares de chamadas, e
    recompilar o mesmo padrão em cada uma é trabalho que ninguém pediu.
    """
    p = re.escape(palavra)
    return re.compile(
        rf"(?<![{_COLADO}])(?<![{_COLADO}]\.){p}(?![{_COLADO}])(?!\.[{_COLADO}])",
        re.IGNORECASE,
    )


def frase_banida_em(texto: str) -> str | None:
    """O primeiro trecho banido presente em ``texto``, ou ``None``.

    ELA NÃO CONSULTA :data:`PALAVRAS_BANIDAS`, e isso foi medido, não esquecido.
    Esta função é o que `hefesto_vivo._json` chama, e o `_json` **levanta** —
    ele é o funil por onde todo valor passa a caminho do WebView. Duas coisas o
    fariam quebrar a tela dela hoje:

    * a chave ``"mesa"`` do próprio pacote, que sete pacotes emitem a cada
      tique (``{"mesa": {campo: valor}}``);
    * **dezesseis frases de `app/`** que ainda dizem a palavra e chegam à tela em
      execução (medidas em 06/09; a lista está no relatório da sprint). O
      `app/` não é da posse desta sprint, e um funil que levanta sobre frase
      que ninguém pode curar troca uma palavra feia por uma janela morta.

    Quem curar o `app/` fecha o ciclo trocando esta chamada por
    :func:`primeiro_trecho_banido`, que já sabe consultar as duas listas.
    """
    for frase in FRASES_BANIDAS:
        if frase in texto:
            return frase
    return None


def palavra_banida_em(texto: str) -> str | None:
    """A primeira palavra banida presente em ``texto``, ou ``None``.

    DUAS OCORRÊNCIAS NÃO CONTAM, e as duas são o nome interno:

    * o texto que **é** a palavra e nada mais — ``"mesa"`` sozinho é a chave do
      pacote, não uma frase;
    * a forma de chave num JSON já serializado (``"mesa":``), que é o mesmo
      nome depois de passar pelo `json.dumps`.
    """
    for palavra in PALAVRAS_BANIDAS:
        if texto.strip().lower() == palavra.lower():
            continue
        for achada in _borda(palavra).finditer(texto):
            antes = texto[achada.start() - 1:achada.start()]
            depois = texto[achada.end():achada.end() + 2]
            if antes == '"' and depois == '":':
                continue
            return palavra
    return None


def primeiro_trecho_banido(texto: str) -> str | None:
    """As DUAS listas numa consulta só — a frase primeiro, a palavra depois."""
    return frase_banida_em(texto) or palavra_banida_em(texto)

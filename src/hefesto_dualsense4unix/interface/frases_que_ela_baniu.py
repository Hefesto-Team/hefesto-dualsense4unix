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

DUAS LEITURAS, E A DIFERENÇA É O PRODUTO — 06/09/2026,
A-REGUA-DA-PALAVRA-VE-O-PRODUTO-01:

`texto_visivel` lê a página CRUA, que é o que ela abre no navegador quando olha
a bancada. O produto renderiza a mesma página com a folha de usuário do piloto
por cima, e a primeira regra dela apaga a `.nota` — o bilhete de projeto. Por
isso há :func:`texto_visivel_no_produto`, que pergunta ao dono da folha o que
ele esconde antes de contar. Sem essa separação a régua acusava **34
ocorrências visíveis "em o produto"** onde um Chrome com a folha posta mostrava
**zero**.

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
#: ``reconciliad`` e ``compactada`` entraram em 09/09/2026 (JOGAR-02 §5), e as
#: duas são a LÍNGUA DE DENTRO: `CoopManager.sync` e `identity.compact`
#: escritos na tela dela. A frase que ela mandou remover era
#: *"Jogadores reconciliados — 2 jogador(es). A numeração já estava
#: compacta."*, e o que entra no lugar nomeia o assento: *"Os controles foram
#: renumerados: P1, P2."*
#:
#: **`compactada` E NÃO `compacta`:** a segunda é raiz de `compactar`, que é o
#: verbo certo em código e em comentário, e a régua casa por BORDA DE PALAVRA —
#: banir a raiz curta acusaria toda prosa que explica o que o daemon faz.
#:
#: **A LISTA DEIXOU DE SER DIGITADA — 11/09/2026, F5-A-REGUA-LE-O-GESTO.** Ela
#: tinha TRÊS palavras enquanto o glossário
#: (`docs/A-LINGUA-DESTA-CASA-o-glossario-que-a-tela-e-o-codigo-falam.md`)
#: proibia ONZE, e só a de baixo tinha régua. Foi por essa fresta que `uinput`
#: chegou à dica da Navegação e ficou.
#:
#: **O DONO É O GLOSSÁRIO, e esta tupla é a CÓPIA que o produto carrega.** O
#: pacote instalado não leva `docs/` junto, então um módulo que lesse o arquivo
#: em execução quebraria na máquina dela. A cópia não envelhece porque
#: `tests/unit/test_a_palavra_mesa_nao_chega_a_tela.py` mede as duas listas uma
#: contra a outra NOS DOIS SENTIDOS: palavra nova no glossário e ausente daqui
#: reprova, e palavra daqui que o glossário não tem reprova também.
#:
#: As oito que entraram são língua de dentro — o nome do subsistema
#: (`uinput`, `hidraw`), o do arquivo da Steam (`vdf`), o da variável (`env`), o
#: do endereço do aparelho (`uniq`, `MAC`), o do campo interno (`wrapper_used`,
#: `dedup`) — mais duas frases que mandam a pessoa a um lugar que a tela dela
#: não tem (*janela do aplicativo*, *linha de comando*).
PALAVRAS_BANIDAS: tuple[str, ...] = (
    "env",
    "vdf",
    "uinput",
    "hidraw",
    "MAC",
    "uniq",
    "wrapper_used",
    "dedup",
    "mesa",
    "janela do aplicativo",
    "linha de comando",
    "reconciliad",
    "compactada",
)

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


#: As tags que NÃO FECHAM. Sem esta lista, um `<br>` dentro do elemento
#: escondido contaria como abertura e a conta de profundidade nunca voltaria a
#: zero — o resto do arquivo sairia apagado, e um apagão silencioso numa régua
#: é o mesmo defeito que ela veio curar, só que ao contrário.
_SEM_FECHO = frozenset(
    (
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr",
    )
)

#: Uma tag de ABERTURA, com o nome separado dos atributos e com as aspas
#: respeitadas: um `title="a > b"` tem `>` DENTRO do valor, e o `<[^>]*>` da
#: leitura de tag cortaria a tag no meio dele.
_ABERTURA = re.compile(
    r"<([A-Za-z][A-Za-z0-9:-]*)((?:\"[^\"]*\"|'[^']*'|[^>\"'])*)>", re.S
)


def _valor(atributos: str, nome: str) -> str:
    achado = re.search(
        rf"\b{re.escape(nome)}\s*=\s*(\"([^\"]*)\"|'([^']*)'|([^\s>]+))",
        atributos,
        re.I | re.S,
    )
    if achado is None:
        return ""
    return next(g for g in achado.groups()[1:] if g is not None)


def _casa(nome: str, atributos: str, seletor: str) -> bool:
    """Este elemento é o que o seletor nomeia?

    Só as três formas que a folha desta casa usa — `.classe`, `#id` e `tag`. O
    que passa daí é RECUSADO lá no dono (`folha_da_casa.seletores_escondidos`),
    em voz alta, antes de chegar aqui.
    """
    if seletor.startswith("."):
        return seletor[1:] in _valor(atributos, "class").split()
    if seletor.startswith("#"):
        return _valor(atributos, "id") == seletor[1:]
    return nome.lower() == seletor.lower()


def _fim_do_elemento(pagina: str, nome: str, apos: int) -> int:
    """Onde acaba o elemento aberto em ``apos`` — contando os aninhados.

    A `.nota` do mockup tem `<div>` dentro de `<div>`: parar no primeiro
    `</div>` deixaria de fora justamente o miolo, que é onde o texto mora.
    """
    par = re.compile(
        rf"<(/?){re.escape(nome)}\b((?:\"[^\"]*\"|'[^']*'|[^>\"'])*)>", re.I | re.S
    )
    fundo = 1
    for achada in par.finditer(pagina, apos):
        if achada.group(1):
            fundo -= 1
            if fundo == 0:
                return achada.end()
        elif not achada.group(2).rstrip().endswith("/"):
            fundo += 1
    raise ValueError(
        f"<{nome}> aberto em {apos} e nunca fechado — a régua não sabe onde o "
        "elemento escondido termina, e chutar aqui apagaria o resto da página. "
        "Conserte o HTML: o produto renderiza esta mesma marcação."
    )


def _apagar_o_escondido(
    letras: list[str], pagina: str, escondidos: tuple[str, ...]
) -> None:
    """Apaga cada elemento que a folha do produto manda esconder."""
    if not escondidos:
        return
    for abertura in _ABERTURA.finditer(pagina):
        nome, atributos = abertura.group(1), abertura.group(2)
        if not any(_casa(nome, atributos, s) for s in escondidos):
            continue
        if nome.lower() in _SEM_FECHO or atributos.rstrip().endswith("/"):
            fim = abertura.end()
        else:
            fim = _fim_do_elemento(pagina, nome, abertura.end())
        _apagar(letras, abertura.start(), fim)


def _ler(pagina: str, escondidos: tuple[str, ...] = ()) -> str:
    """O motor das duas leituras — a da bancada e a do produto.

    ``escondidos`` são os seletores que a FOLHA do produto apaga, e é o único
    ponto em que as duas diferem. Ele entra ANTES do `<code>` e das tags, e
    DEPOIS do `<style>`/comentário de propósito: um comentário de CSS que cite
    ``<div class="nota">`` viraria elemento de verdade se a ordem fosse outra.
    """
    letras = list(pagina)
    for muda in _MUDOS.finditer(pagina):
        _apagar(letras, muda.start(), muda.end())
    limpo = "".join(letras)
    _apagar_o_escondido(letras, limpo, escondidos)
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


def texto_visivel(pagina: str) -> str:
    """O que uma pessoa LÊ nesta página NO NAVEGADOR — a leitura da BANCADA.

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

    **ELA CONTA A `.nota`, E ISSO É O CERTO AQUI.** A bancada (`mockup/`) é o
    que ela abre NO NAVEGADOR, sem folha de usuário nenhuma: ali o bilhete de
    projeto é texto visível de verdade. Quem quer a leitura do PRODUTO chama
    :func:`texto_visivel_no_produto` — a diferença entre as duas é o ponto
    inteiro da separação.
    """
    return _ler(pagina)


def texto_visivel_no_produto(pagina: str) -> str:
    """O que uma pessoa LÊ nesta página DENTRO DA JANELA — a leitura do PRODUTO.

    A diferença para :func:`texto_visivel` é uma só, e ela custou uma sprint:
    o produto não renderiza a página crua. O `JanelaDaAba` injeta a
    :data:`~hefesto_dualsense4unix.interface.folha_da_casa.FOLHA_DA_CASA` pela
    `UserContentManager`, e a primeira regra dela é
    `.nota{display:none !important}` — *"tira os bilhetes de projeto que o
    mockup carrega para quem o lê no navegador; eles não são produto"*.

    O NÚMERO QUE PROVA, medido em 06/09/2026 sobre `interface/paginas/`:
    `--palavra mesa --publicado` acusava **34 ocorrências visíveis "em o
    produto"** e um Chrome com a folha posta mostrava **ZERO** — as 34 estavam
    todas dentro da `.nota`. O instrumento respondia sobre o ARQUIVO e dizia "o
    produto"; é a assinatura de instrumento falso que esta casa persegue.

    **O SELETOR NÃO SE DIGITA AQUI.** Ele vem de
    :func:`~hefesto_dualsense4unix.interface.folha_da_casa.seletores_escondidos`, que
    lê o `display:none` da folha do produto: uma segunda regra de esconder
    amanhã vale para esta régua sem ninguém tocar nela. Digitar `.nota` uma
    segunda vez seria o defeito que esta casa mais paga — o mesmo valor com dois
    donos.
    """
    from hefesto_dualsense4unix.interface.folha_da_casa import seletores_escondidos

    return _ler(pagina, seletores_escondidos())


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

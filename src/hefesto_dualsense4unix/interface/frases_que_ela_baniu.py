"""As frases — e a PALAVRA — que o usuário mandou tirar da tela, num lugar só.

A DECISÃO DE PRODUTO DE 31/08/2026, sobre o aviso do Modo Nativo. A regra que sobrou é curta e
vale para a interface inteira:

    **NENHUM ALARME SEM MEDIÇÃO.**

As três primeiras frases abaixo alarmavam sobre número que **ensaio nenhum
deste repositório mede**. Não são erro de gosto: uma frase que assusta sem
medir custa a confiança dela em todas as outras.

A QUARTA É DE OUTRA FAMÍLIA — 24/09/2026, A-FRASE-DO-RECONECTAR-SAI-01. Ela
não alarma: NARRA o que a tela já mostra. A razão está ao lado dela, em
:data:`FRASES_BANIDAS`.

POR QUE ESTE MÓDULO EXISTE — e é o OITAVO CONFLITO da leva de 04/09/2026,
achado pela frente da aba 01 e da mesma família dos sete do `O-PO-DECIDE`:

A proibição vivia **só** dentro de `aba01._conferir`, que lê o **HTML
ESTÁTICO** da página gerada. A coluna Atenção, porém, é escrita em **tempo de
execução** — o piloto manda o texto pelo `_json`. Logo quem cumprir a
decisão [01] ao pé da letra (*"o aviso do Modo Nativo na coluna Atenção"*)
poria a frase banida na tela do usuário **com o gerador VERDE**.

A régua olhava o lugar errado. Agora a lista é uma só, e há duas guardas
lendo-a: a estática (`aba01._conferir`) e a de execução (`hefesto_vivo._json`,
o funil por onde TODO valor passa a caminho do WebView).

O QUE A DECISÃO [01] AINDA PODE TER, e é a leitura de PO de 04/09/2026: a
coluna Atenção pode dizer **o estado medido** — *o Modo Nativo está ligado, a
Ponte com o jogo está desligada* — porque isso o produto mede e sabe. O que ela
não pode é PROFETIZAR consequência que ninguém mediu. A decisão de 31/08
vence a recomendação de 04/09, como venceu nas outras sete.

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

Ela, 06/09: *"Falei do termo mesa que é horrível. Mas as levas anteriores
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
por cima, e a primeira regra de produto apaga a `.nota` — o bilhete de projeto. Por
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
import threading
from functools import cache

FRASES_BANIDAS: tuple[str, ...] = (
    "derrubam o controle",
    "resultado é ZERO",
    "gatilhos ficam duros",
    "foram renumerados",
)


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

#: `-` e `_` estão aqui porque `mesa-frase`, `radio-mesa` e `MESA_VAZIA` são
_COLADO = r"0-9A-Za-zÀ-ÖØ-öø-ÿ_\-"

_MUDOS = re.compile(
    r"<!--.*?-->|<style\b[^>]*>.*?</style>|<script\b[^>]*>.*?</script>",
    re.S | re.I,
)

_CODIGO = re.compile(r"<code\b[^>]*>.*?</code>", re.S | re.I)

_ATRIBUTO_LIDO = re.compile(
    r"\b(?:title|placeholder|aria-label|alt)\s*=\s*(\"[^\"]*\"|'[^']*')", re.I
)

_TAG = re.compile(r"<[^>]*>", re.S)


def _apagar(alvo: list[str], inicio: int, fim: int) -> None:
    """Espaço no lugar das letras, do mesmo tamanho."""
    for i in range(inicio, fim):
        if alvo[i] != "\n":
            alvo[i] = " "


_SEM_FECHO = frozenset(
    (
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr",
    )
)

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
    """Este elemento é o que o seletor nomeia?"""
    if seletor.startswith("."):
        return seletor[1:] in _valor(atributos, "class").split()
    if seletor.startswith("#"):
        return _valor(atributos, "id") == seletor[1:]
    return nome.lower() == seletor.lower()


def _fim_do_elemento(pagina: str, nome: str, apos: int) -> int:
    """Onde acaba o elemento aberto em ``apos`` — contando os aninhados."""
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
    """O motor das duas leituras — a da bancada e a do produto."""
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
            for i in range(tag.start() + a + 1, tag.start() + b - 1):
                letras[i] = limpo[i]
    return "".join(letras)


def texto_visivel(pagina: str) -> str:
    """O que uma pessoa LÊ nesta página NO NAVEGADOR — a leitura da BANCADA."""
    return _ler(pagina)


def texto_visivel_no_produto(pagina: str) -> str:
    """O que uma pessoa LÊ nesta página DENTRO DA JANELA — a leitura do PRODUTO."""
    from hefesto_dualsense4unix.interface.folha_da_casa import seletores_escondidos

    return _ler(pagina, seletores_escondidos())


@cache
def _borda(palavra: str) -> re.Pattern[str]:
    """A palavra inteira, e nunca o pedaço de um nome."""
    p = re.escape(palavra)
    return re.compile(
        rf"(?<![{_COLADO}])(?<![{_COLADO}]\.){p}(?![{_COLADO}])(?!\.[{_COLADO}])",
        re.IGNORECASE,
    )


def frase_banida_em(texto: str) -> str | None:
    """O primeiro trecho banido presente em ``texto``, ou ``None``."""
    for frase in FRASES_BANIDAS:
        if frase in texto:
            return frase
    return None


def palavra_banida_em(texto: str) -> str | None:
    """A primeira palavra banida presente em ``texto``, ou ``None``."""
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


def sem_o_trecho(texto: str, trecho: str) -> str:
    """``texto`` sem as ocorrências de ``trecho``, lido como a régua o lê."""
    if trecho in FRASES_BANIDAS:
        return texto.replace(trecho, " ")
    return _borda(trecho).sub(" ", texto)


CITACOES_QUE_O_FUNIL_LEMBRA = 16

_CITADOS: dict[str, None] = {}
_TRAVA_DOS_CITADOS = threading.Lock()


def citar(texto: str) -> str:
    """Registra ``texto`` como CITAÇÃO de outro programa e o devolve igual."""
    if texto:
        with _TRAVA_DOS_CITADOS:
            _CITADOS.pop(texto, None)
            _CITADOS[texto] = None
            while len(_CITADOS) > CITACOES_QUE_O_FUNIL_LEMBRA:
                _CITADOS.pop(next(iter(_CITADOS)))
    return texto


def citados() -> tuple[str, ...]:
    """Uma CÓPIA do registro das citações, lida sob a trava."""
    with _TRAVA_DOS_CITADOS:
        return tuple(_CITADOS)


def sem_o_citado(texto: str) -> str:
    """O que o funil lê de ``texto``: tudo, menos os trechos citados."""
    for citado in citados():
        if citado in texto:
            texto = texto.replace(citado, "\n")
    return texto

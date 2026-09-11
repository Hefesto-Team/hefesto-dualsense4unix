#!/usr/bin/env python3
"""check_a_maiuscula_decorativa.py — a CAIXA ALTA que não significa nada.

POR QUE ELE NASCEU, e a ordem é dela
-------------------------------------
Em 11/09/2026 ela abriu o produto instalado com um DualSense no cabo e leu, na
MESMA tela, a mesma palavra escrita de dois jeitos::

    fita    P1 • Cosmic Red • CABO
    card    Cosmic Red • cabo

    "Leia o cabo e acordado (ambos minusculo sem iniciar de forma   (noqa-acento: citação literal dela)
     capitular). Esse tipo de coisa não pode se repetir na interface."   (noqa-acento: citação literal dela)

**A segunda frase é o que fez esta régua existir.** O caso dela foi curado no
`topo.html` (ESQUELETO-C2); o que não pode é voltar — nem ali, nem em nenhuma
das outras nove páginas.

E A REGRA DA CASA SOBRE MAIÚSCULA É DELA, de 30/08/2026: *"a maiúscula a   (noqa-acento: citação literal dela)
regra é sobre a primeira letra a ser capitalizada, é o padrão do projeto"*.
Palavra INTEIRA em caixa alta não é ênfase nesta casa — é ruído, e é o que esta
régua procura.

AS DUAS METADES, E UMA SOZINHA MENTE
-------------------------------------
O `CABO` dela **não estava escrito em lugar nenhum**. O HTML dizia `cabo`
(regra de `monta.rotulo`: quem escreve em maiúscula no HTML tira dela a chance
de copiar o nome como ele é) e quem gritava era UMA LINHA DE CSS. Uma régua que
lesse só o texto das dez páginas daria **verde sobre a tela que ela
fotografou**.

Por isso são duas peneiras, e as duas reprovam:

§1 **A FOLHA** — nenhuma regra das dez páginas pode subir a caixa de uma
   palavra. Lê o `<style>` de cada página **com os comentários apagados**: um
   comentário que cita a regra proibida (esta casa já pagou isso seis vezes)
   não é a regra.

§2 **O TEXTO** — toda palavra em caixa alta que uma pessoa LÊ no produto tem de
   estar declarada: sigla, selo, código de máquina — ou dívida, com dono.

O QUE ELE NÃO LÊ, E É DECISÃO
------------------------------
* **O ``<title>`` do documento** (``Hefesto — aba JOGAR``). Mesma razão do
  ``check_a_janela_nao_confessa``: o `WebKit2.WebView` mora numa `Gtk.Window`
  sem barra de abas e sem barra de endereço — **nesta janela ninguém o lê**.
  Contá-lo daria dez vermelhos sobre texto que a tela dela não mostra.
* **O conteúdo dos SELOS**, e é ordem da sprint: *"Os selos são desenho e
  ficam."* A peneira é ESTRUTURAL (a classe do elemento), nunca uma lista de
  palavras: um selo novo amanhã já nasce coberto, e uma palavra decorativa que
  se disfarce de selo continua sendo pega — porque ela não está dentro de um.
* **A bancada (`mockup/`)**. O alvo é o que o produto RENDERIZA; o desenho em
  conclusão é assunto do `check_o_desenho_aprovado`.

QUEM DECIDE O QUE É "LIDO NO PRODUTO" NÃO É ESTE ARQUIVO
---------------------------------------------------------
É ``interface.frases_que_ela_baniu.texto_visivel_no_produto``, que já é o dono
dessa leitura — inclusive do que a folha do piloto ESCONDE (o bilhete de
projeto da `.nota`). Uma segunda cópia dessa lógica aqui seria o defeito que
esta casa mais paga: o mesmo valor com dois donos, respondendo números
diferentes sobre a mesma tela.

Uso::

    scripts/check_a_maiuscula_decorativa.py            # reprova
    scripts/check_a_maiuscula_decorativa.py --lista    # só mostra o inventário
"""
from __future__ import annotations

import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[1]
PUBLICADO = RAIZ / "src" / "hefesto_dualsense4unix" / "interface" / "paginas"  # noqa-acento: nome de PASTA, e caminho nao leva acento
E_ABA = re.compile(r"^\d\d-[a-z]+\.html$")

sys.path.insert(0, str(RAIZ / "src"))

# ---------------------------------------------------------------------------
# §1 — A FOLHA
# ---------------------------------------------------------------------------
#: As formas que SOBEM a caixa. `lowercase` não entra: abaixar não inventa
#: maiúscula nenhuma, e `none` é justamente a cura que várias páginas já
#: escrevem para desfazer herança.
SOBE_A_CAIXA = frozenset({"uppercase", "capitalize"})

#: Regras de caixa alta que FICAM, com a razão. **Vazia hoje, e isso é medido**:
#: a última morreu em 11/09/2026 (`.fita .chip .via`, no `topo.html`). Se um dia
#: houver uma legítima, ela entra aqui com a razão e a data — nunca calada.
CAIXA_QUE_FICA: dict[str, str] = {}

_COMENTARIO_CSS = re.compile(r"/\*.*?\*/", re.S)
_ESTILO = re.compile(r"<style[^>]*>(.*?)</style>", re.S | re.I)
_TRANSFORMA = re.compile(r"text-transform\s*:\s*([a-z-]+)", re.I)


def _folha(pagina: str) -> list[tuple[int, str, str]]:
    """`(linha, valor, seletor)` de cada regra que sobe a caixa nesta página.

    O COMENTÁRIO É APAGADO COM ESPAÇO DO MESMO TAMANHO, e não removido: só
    assim o número da linha continua sendo o número da linha do arquivo — e a
    entrega de uma régua é o endereço, não a contagem.
    """
    limpo = _COMENTARIO_CSS.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), pagina)
    fora = []
    for bloco in _ESTILO.finditer(limpo):
        for m in _TRANSFORMA.finditer(bloco.group(1)):
            if m.group(1).lower() not in SOBE_A_CAIXA:
                continue
            onde = bloco.start(1) + m.start()
            linha = limpo.count("\n", 0, onde) + 1
            # o seletor é o que vem antes da `{` mais próxima acima
            antes = limpo[max(0, onde - 400):onde]
            corte = antes.rfind("}")
            seletor = antes[corte + 1:].split("{")[0].strip().replace("\n", " ")
            fora.append((linha, m.group(1).lower(), seletor[-70:] or "(?)"))
    return fora


# ---------------------------------------------------------------------------
# §2 — O TEXTO
# ---------------------------------------------------------------------------
#: OS SELOS, POR CLASSE — ordem da sprint: *"Os selos são desenho e ficam."*
#: Eles são etiquetas de estado, e a caixa alta ali É a forma da etiqueta.
#: A peneira é a CLASSE e não a palavra, de propósito: um selo novo nasce
#: coberto, e uma palavra decorativa não se salva por parecer um.
SELO = ("selo", "lanc-selo", "selo-som", "selo-ativo")

#: O `<title>` DO DOCUMENTO — ver o cabeçalho. Achado pela tag, nunca por um
#: número de linha cravado: o `<head>` já mudou de tamanho.
#:
#: **SÓ O DO DOCUMENTO, e o recorte é o `<body>`**: o desenho do DualSense traz
#: um `<title>` por grupo de peça (`CHASSI`, `BOTÕES DA FACE`), que é o nome
#: acessível daquele pedaço — texto que uma pessoa alcança, e que está na
#: DÍVIDA abaixo. Apagar os dois com a mesma regra esconderia catorze achados.
_TITULO = re.compile(r"<title>.*?</title>", re.S | re.I)
_CORPO = re.compile(r"<body\b", re.I)

#: O QUE NÃO É MARCAÇÃO DE TELA — apagado ANTES de procurar selo.
#:
#: **ESTA LINHA É CICATRIZ, e de dentro desta régua** (11/09/2026): sem ela, um
#: comentário do `<style>` que CITA `<span class="lanc-selo localizado">` —
#: escrito para explicar por que a folha não conhecia a classe nova — era lido
#: como abertura de selo de verdade. O varredor de `<span>` saía dali
#: procurando o fechamento, atravessava o `</style>` e o apagava junto: a folha
#: de estilo inteira virava "texto visível", e a régua acusava **306** caixas
#: altas, quase todas prosa de comentário de CSS.
#:
#: É a armadilha de prosa desta casa pela sétima vez — *o comentário que
#: descreve o padrão VIRA a primeira ocorrência dele* — e desta vez ela pegou o
#: instrumento que nasceu para medi-la.
_FORA_DA_TELA = re.compile(
    r"<style[^>]*>.*?</style>|<script[^>]*>.*?</script>|<!--.*?-->", re.S | re.I)

#: VALOR DE MÁQUINA QUE A TELA MOSTRA: cor em hexa e endereço de rádio
#: mascarado. Apagado ANTES de separar as palavras, e é a diferença entre uma
#: peneira e um acaso.
#:
#: **MEDIDO EM 11/09/2026, pelo próprio teste desta régua:** a primeira versão
#: tratava qualquer par `[0-9A-F]{2}` como código, para cobrir os octetos de
#: `AA:BB:CC:00:00:01`. Com isso o `DA` de «BOTÕES DA FACE» virava "código de
#: máquina" e saía calado do inventário — uma preposição do português inteira
#: perdida porque as duas letras dela também são dígitos hexadecimais. Quem
#: pega o endereço é a FORMA INTEIRA dele, nunca o pedaço.
_VALOR_DE_MAQUINA = re.compile(
    r"#[0-9A-Fa-f]{3,8}\b|\b(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}\b")

#: `<span>` é a única tag em que os selos moram hoje, e o varredor conta
#: aberturas para achar o fechamento certo — um selo com `<span>` dentro (o
#: caso de `<span class="selo ok"><span data-campo="selo">CERTO</span></span>`)
#: quebraria uma busca ingênua pelo primeiro `</span>`.
_SPAN = re.compile(r"<span\b[^>]*>|</span>", re.I)


def _apagar(alvo: list[str], inicio: int, fim: int) -> None:
    for i in range(inicio, fim):
        if alvo[i] != "\n":
            alvo[i] = " "


def _branco(texto: str) -> str:
    """Espaço no lugar de tudo, menos a quebra de linha — o tamanho não muda."""
    return re.sub(r"[^\n]", " ", texto)


def _so_a_tela(pagina: str) -> str:
    """A página sem o `<style>`, o `<script>`, os comentários e o `<title>` dela.

    Do MESMO tamanho, sempre: é o que deixa a régua dizer página e LINHA.
    """
    limpo = _FORA_DA_TELA.sub(lambda m: _branco(m.group(0)), pagina)
    limpo = _VALOR_DE_MAQUINA.sub(lambda m: _branco(m.group(0)), limpo)
    corpo = _CORPO.search(limpo)
    ate = corpo.start() if corpo else len(limpo)
    cabeca = _TITULO.sub(lambda m: _branco(m.group(0)), limpo[:ate])
    return cabeca + limpo[ate:]


def _sem_os_selos(pagina: str) -> str:
    """A página com o conteúdo dos selos trocado por espaço do mesmo tamanho."""
    letras = list(pagina)
    abre = re.compile(
        r"<span\b[^>]*\bclass\s*=\s*\"[^\"]*\b(?:%s)\b[^\"]*\"[^>]*>"
        % "|".join(re.escape(c) for c in SELO), re.I)
    for m in abre.finditer(pagina):
        # O FECHAMENTO TEM DE FECHAR. Um `<span>` que não equilibra não é
        # marcação de selo — é texto que se parece com uma —, e apagar até o
        # fim do arquivo por causa dele foi exatamente o defeito de 11/09.
        fundo, fim = 1, None
        for t in _SPAN.finditer(pagina, m.end()):
            fundo += -1 if t.group(0).startswith("</") else 1
            if fundo == 0:
                fim = t.end()
                break
        if fim is not None:
            _apagar(letras, m.start(), fim)
    return "".join(letras)


#: A PALAVRA. Um corrido de letras/dígitos/`_`/`-` que é TODO maiúsculo e traz
#: ao menos duas letras. O `w == w.upper() != w.lower()` é o que separa `GHz`
#: (que tem minúscula e não é caixa alta) de `GH`, que uma peneira ingênua
#: recortaria de dentro dele e acusaria como palavra.
_PALAVRA = re.compile(r"[^\W_]+(?:[_-][^\W_]+)*", re.UNICODE)

#: MODELO DE APARELHO, pela FORMA e não por lista (`AX211`, `UB500`): uma lista
#: envelheceria a cada aparelho novo na mesa dela. A cor em hexa e o endereço
#: de rádio já saíram antes, em :data:`_VALOR_DE_MAQUINA`.
_CODIGO = re.compile(r"^[A-Z]{1,3}[0-9]{3,5}$")

#: SIGLA, MARCA E NOME DE BOTÃO — a caixa alta é a grafia PRÓPRIA delas, e
#: escrevê-las de outro jeito seria escrevê-las erradas.
SIGLA = frozenset({
    "USB", "BT", "PC", "TV", "ID", "LED", "FPS", "MK", "SDL", "GTK", "IPC",
    "HID", "A2DP", "HFP", "GOG", "GBA", "DKMS", "CPU", "SVG", "CSV", "JSON",
    "HDMI", "COSMIC",
    # os botões e gatilhos do aparelho, como o próprio aparelho os chama
    "PS", "L1", "L2", "L3", "R1", "R2", "R3", "ZL", "ZR", "LB", "RB", "LT", "RT",
})

#: A DÍVIDA — caixa alta que a tela mostra HOJE e que não é sigla nem selo.
#: Ela **não reprova**: nenhuma destas mora num arquivo da ESQUELETO-C2, e uma
#: régua que reprovasse de saída dezoito frases de outras frentes seria
#: desligada na primeira segunda-feira. Ela é IMPRESSA a cada corrida, com o
#: dono, para que a dívida não cresça calada — e uma palavra que não esteja
#: aqui reprova.
#:
#: LEVANTADA EM 11/09/2026, nas dez páginas publicadas.
DIVIDA: dict[str, tuple[str, str]] = {
    # -- os rótulos de grupo do desenho do DualSense --------------------------
    # Dez títulos de `<title>` dentro do SVG, em caixa alta. Pela regra dela de
    # 30/08 seriam «Chassi», «Botões da face»… Dono: `interface/exportar.py`,
    # que os escreve no `ds_limpo.svg` (linhas 74-84).
    "CHASSI": ("rótulo de grupo do SVG", "interface/exportar.py"),
    "BOTÕES": ("rótulo de grupo do SVG («BOTÕES DA FACE»)", "interface/exportar.py"),
    "DA": ("rótulo de grupo do SVG («BOTÕES DA FACE»)", "interface/exportar.py"),
    "FACE": ("rótulo de grupo do SVG («BOTÕES DA FACE»)", "interface/exportar.py"),
    "DIRECIONAL": ("rótulo de grupo do SVG", "interface/exportar.py"),
    "OMBROS": ("rótulo de grupo do SVG («OMBROS E GATILHOS»)", "interface/exportar.py"),
    "GATILHOS": ("rótulo de grupo do SVG («OMBROS E GATILHOS»)", "interface/exportar.py"),
    "ANALÓGICOS": ("rótulo de grupo do SVG", "interface/exportar.py"),
    "CENTRO": ("rótulo de grupo do SVG", "interface/exportar.py"),
    "ÁUDIO": ("rótulo de grupo do SVG", "interface/exportar.py"),
    "SENSORES": ("rótulo de grupo do SVG («SENSORES E MOTORES»)", "interface/exportar.py"),
    "MOTORES": ("rótulo de grupo do SVG («SENSORES E MOTORES»)", "interface/exportar.py"),
    "GLIFOS": ("rótulo de grupo do SVG", "interface/exportar.py"),
    "LUZES": ("rótulo de grupo do SVG", "interface/exportar.py"),
    # -- ênfase decorativa dentro da prosa das dicas --------------------------
    # É o caso mais puro do que ela proibiu: a palavra sobe de caixa só para
    # gritar. Dono: o gerador da aba em que a dica mora — as frentes da onda
    # A-LINGUA-DA-TELA passam por todas elas.
    "INTEIRO": ("ênfase na dica do giroscópio", "interface/exportar.py · aba01"),
    "MULTIPLICA": ("ênfase na dica da força", "aba05 · a05_vibracao"),
    "ESTE": ("ênfase na dica de ignorar", "aba08 · a08_conexoes"),
    "DERIVADO": ("ênfase na dica da cor do jogador", "aba02 · a02_controles"),
    "FONTE": ("ênfase na dica do volume", "aba02 · a02_controles"),
    "MÁQUINA": ("ênfase na dica do mudo do sistema", "aba08 · a08_conexoes"),
    "TAMBÉM": ("ênfase na dica do «Ouvir junto»", "aba02 · a02_controles"),
    "TROCA": ("ênfase na dica da curva pronta", "aba03 · a03_gatilhos"),
    "GABINETE": ("ênfase na dica das entradas", "aba08 · a08_conexoes"),
    "JOGADOR": ("ênfase na dica do código da cor", "aba02 · a02_controles"),
    "UM": ("ênfase na dica do motor", "aba05 · a05_vibracao"),
    "LIGADO": ("ênfase no bilhete de estado", "aba01 · a01_jogar"),
    "DESLIGADO": ("ênfase no bilhete de estado", "aba01 · a01_jogar"),
    "FICA": ("ênfase na dica do hub de bancada", "aba08 · a08_conexoes"),
    "TEM": ("ênfase na dica de tirar daqui", "aba08 · a08_conexoes"),
    "TODOS": ("ênfase na dica de pôr em todos os jogos", "aba09 · a09_sistema"),
    "TOTAL": ("ênfase na dica do contador", "aba08 · a08_conexoes"),
    "OCUPAÇÃO": ("ênfase na dica do rádio cheio", "aba08 · a08_conexoes"),
    # -- a casa falando a língua de dentro ------------------------------------
    # Nome de constante do produto citado na tela. Não é assunto de caixa alta:
    # é `check_a_tela_nao_confessa`, e por isso fica declarado aqui em vez de
    # ser curado por esta frente.
    "LINHAS_DO_TETO": ("nome de constante do produto na dica",
                       "aba09 — assunto do `check_a_tela_nao_confessa`"),
    "RUMBLE_POLICY_MULT": ("nome de constante do produto na dica",
                           "aba09 — assunto do `check_a_tela_nao_confessa`"),
}


def _palavras(pagina: str) -> dict[str, list[tuple[int, str]]]:
    """`{PALAVRA: [(linha, trecho), …]}` do que a pessoa lê no produto."""
    from hefesto_dualsense4unix.interface.frases_que_ela_baniu import (
        texto_visivel_no_produto,
    )

    texto = texto_visivel_no_produto(_sem_os_selos(_so_a_tela(pagina)))
    achadas: dict[str, list[tuple[int, str]]] = {}
    for n, linha in enumerate(texto.splitlines(), 1):
        for m in _PALAVRA.finditer(linha):
            p = m.group(0)
            if p != p.upper() or p == p.lower():
                continue
            if len(re.sub(r"[\W\d_]", "", p, flags=re.UNICODE)) < 2:
                continue
            a, b = max(0, m.start() - 38), m.end() + 38
            achadas.setdefault(p, []).append((n, " ".join(linha[a:b].split())))
    return achadas


def _legitima(p: str) -> bool:
    return p in SIGLA or bool(_CODIGO.match(p))


# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    so_lista = "--lista" in argv

    paginas = sorted(p for p in PUBLICADO.glob("*.html") if E_ABA.match(p.name))
    # RÉGUA QUE ACHA ZERO NÃO É RÉGUA VERDE.
    if len(paginas) != 10:
        print(f"achei {len(paginas)} abas em {PUBLICADO} — o caminho mudou?",
              file=sys.stderr)
        return 2

    vermelhos: list[str] = []
    divida: dict[str, list[str]] = {}

    for p in paginas:
        bruto = p.read_text(encoding="utf-8")

        for linha, valor, seletor in _folha(bruto):
            if seletor in CAIXA_QUE_FICA:
                continue
            vermelhos.append(
                f"§1 {p.name}:{linha}  a folha sobe a caixa: "
                f"`{seletor}{{text-transform:{valor}}}`\n"
                f"     a tela passa a mostrar a palavra INTEIRA em maiúscula, e o "
                f"documento continua minúsculo — a mesma palavra, duas grafias.")

        for palavra, lugares in sorted(_palavras(bruto).items()):
            if _legitima(palavra):
                continue
            if palavra in DIVIDA:
                n, trecho = lugares[0]
                divida.setdefault(palavra, []).append(f"{p.name}:{n}  …{trecho}…")
                continue
            n, trecho = lugares[0]
            vermelhos.append(
                f"§2 {p.name}:{n}  «{palavra}» em caixa alta, e ela não é sigla, "
                f"selo nem código\n     …{trecho}…\n"
                f"     a regra dela (30/08/2026) é a PRIMEIRA letra: escreva "
                f"«{palavra.capitalize()}» ou «{palavra.lower()}». Se for sigla "
                f"ou selo, declare em SIGLA/SELO com a razão.")

    if divida:
        print("DÍVIDA declarada — caixa alta que a tela mostra hoje "
              f"({len(divida)} palavra(s), e nenhuma é desta frente):")
        for palavra in sorted(divida):
            oque, dono = DIVIDA[palavra]
            print(f"  {palavra:<20} {oque} · dono: {dono}")
            for onde in divida[palavra][:1]:
                print(f"      {onde}")
        print()
        # A DÍVIDA SAI ANTES DO VERMELHO na tela de quem roda: sem o `flush` os
        # dois fluxos chegam trocados e o relato começa pelo fim.
        sys.stdout.flush()

    if so_lista:
        return 0

    if vermelhos:
        print(f"REPROVADO — {len(vermelhos)} caixa(s) alta(s) sem declaração:\n",
              file=sys.stderr)
        for v in vermelhos:
            print("  " + v + "\n", file=sys.stderr)
        print("Ela, 11/09/2026: «Esse tipo de coisa não pode se repetir na "
              "interface.»", file=sys.stderr)
        return 1

    print(f"OK: {len(paginas)} páginas publicadas, nenhuma regra de folha sobe a "
          "caixa e nenhuma palavra em caixa alta sem declaração.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

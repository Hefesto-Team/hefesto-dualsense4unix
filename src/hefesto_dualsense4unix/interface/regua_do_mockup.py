#!/usr/bin/env python3
"""A RÉGUA QUE FALTAVA: o que a tela mostra é DADO, ou é o desenho congelado?

PEDIDO DELA, e foi ELA quem viu o buraco (02/09/2026):

    *"um portão que, com o daemon vivo e a mesa real, reprove quando um campo
    continua exibindo o valor do mockup. Hoje nada acusa isso."*

O CASO QUE NOMEIA O DEFEITO, e está no HTML publicado de hoje: a aba Gatilhos
mostra ``Força 7 · Frequência 4 · Início do curso 25 · Fim do curso 230`` — com
o perfil dela dizendo ``modo='Off' params=[]``. Nenhum daqueles quatro números
saiu do aparelho: são o desenho, cravado no arquivo em 26/08 e nunca repintado.
Quem olha a tela lê quatro medidas de um gatilho que está DESLIGADO.

POR QUE NENHUM PORTÃO PEGAVA ISSO, e é a lição-mãe do dia: as réguas desta casa
contavam se o NOME de um campo aparecia no código do pacote. Foi assim que o
assistente reportou **77% de paridade** onde o produto entregava 36%, e assim
que a segunda medição do mesmo dia disse **61%** contando `data-campo` em
arquivo. **Presença de string não é funcionamento.** Um pacote pode nomear o
campo, montar o valor e escrevê-lo num endereço que não existe na página — e a
tela continua mostrando o mockup, calada. Foi o que a `06-navegacao` fez: sete
campos MENCIONADOS, três PINTADOS.

O QUE ESTA RÉGUA MEDE, e a diferença é o ponto inteiro: ela lê o valor que está
NA TELA, com o daemon vivo, e compara com o valor CRAVADO no arquivo publicado.

    PRODUTO      o valor mudou — alguém pintou; ou é igual ao cravado E o
                 piloto SELOU o elemento, que é o mesmo fato provado por outro
                 caminho
    MOCKUP       igual ao cravado, e nenhum pacote declara este campo
    INDECIDIVEL  igual ao cravado, o pacote declara EXATAMENTE esse valor, e o
                 piloto NÃO passou pelo elemento

A TERCEIRA CLASSE ERA 74 CAMPOS EM 330, e hoje é ZERO — **medido em 02/09/2026
com DOIS controles na mesa, um no USB e um no BT**. O número depende da mesa, e
dizer qual mesa é obrigatório: o mesmo instrumento, no mesmo dia e sem uma linha
de código mudar, deu ``114 PRODUTO · 179 MOCKUP · 37 INDECIDÍVEL`` com a mesa
VAZIA e ``262 · 68 · 0`` com ela cheia. Esta seção dizia: *"separá-las exigiria
marcar cada elemento no momento da escrita — uma marca no caminho quente da
pintura, paga por toda volta do tique, para responder uma pergunta de bancada"*,
e concluía que a régua preferia dizer quantos eram.
**A conta estava errada, e foi medida em 02/09/2026:** a marca é um
``el.dataset.hefVisto = '1'`` no ``escrever()``, e o custo do tique não se mexeu
— mediana **1,13 ms antes, 1,03 ms depois**, na mesma aba e na mesma mesa (a de
dois controles). Os 74 viraram PRODUTO, e o número de MOCKUP não mudou uma
unidade.

E A MARCA NÃO É "LER O CÓDIGO", que é o erro que esta régua existe para não
repetir: ela não pergunta se o nome do campo aparece no pacote — ela registra,
em tempo de execução, que o valor emitido CHEGOU a um elemento desta página.
Endereço morto continua sem selo, e continua acusado. A mordida que prova que o
selo decide alguma coisa é ``--sem-selo``: os 74 voltam.

A CLASSE FICA, e não é resíduo: um bloco que a pintura troca INTEIRO
(``innerHTML``) não passa pelo ``escrever()``, e um filho dele que nasça igual
ao desenho volta a ser indecidível — com a nota dizendo isso.

O QUARTO CASO CAI EM ``MOCKUP``, e é o mais grave dos três: o pacote declara o
campo com OUTRO valor e a tela continua no cravado. Isso é **endereço morto** —
o pacote escreve num lugar que a página não tem. A nota do veredito diz.

O QUE ESTE MÓDULO NÃO FAZ: abrir janela. Ele é puro — parser e classificador —
e por isso roda no CI sem GTK, sem display e sem daemon. Quem abre a janela e lê
o DOM é o ``--prova-de-mockup`` do ``hefesto_vivo.py``, que traz os dois lados
para cá.

POR QUE TODO NOME AQUI COMEÇA COM ``_``, e não é estilo — é o contrato do
``portao_a_casa_sabe_e_o_produto_nao_faz``. Ele mede *promessa ao produto* por
NOME PÚBLICO de módulo, e ele **poda a bancada** antes de medir: tudo o que só
roda sob uma flag de régua do piloto (``--prova-de-mockup``,
``--prova-no-aparelho``, ``--sem-cor``) sai da conta. Um nome público alcançado
só por aí cai no caso mais fino do defeito-mãe daquele portão — *cura escrita,
testada, e nunca ligada na tela*, embrulhada em verde. O portão diz, com estas
palavras: **"A régua não é caminho."**

Este módulo É régua, e assume isso: nenhum nome dele promete nada ao produto.
Quem quiser fiar uma destas funções à espinha viva do piloto — o tique, a
pintura, o gesto dela — tira o ``_`` NA HORA de fiar, e aí o portão volta a
cobrar dela o que cobra de toda promessa.
"""
from __future__ import annotations

import colorsys
import dataclasses
import html.parser
import math
import re
from typing import Any

#: OS TRÊS VOCABULÁRIOS DE ENDEREÇO DE CAMPO, e nenhum se aposenta. É a mesma
#: lista que a função ``achar()`` do BOOTSTRAP procura no DOM — repeti-la aqui é
#: o preço de o Python não poder ler o JS, e o
#: ``test_a_regua_le_os_mesmos_enderecos_do_bootstrap`` é quem impede as duas de
#: divergirem em silêncio.
ATRIBUTOS_DE_CAMPO = ("data-campo", "data-papel", "data-hef")

#: OS ENDEREÇOS DE GESTO QUE A RÉGUA CLICA. ``data-papel`` está de FORA de
#: propósito, e a razão é medida: na aba Vibração ele endereça 28 CAMPOS, e o
#: ouvinte do bootstrap o aceita como gesto — clicar os 28 seria a régua
#: inventando 28 botões que ninguém desenhou. Eles saem no relato como
#: ``ambiguos``, que é o que eles são: um endereço que é campo e gesto ao mesmo
#: tempo.
ATRIBUTOS_DE_GESTO = ("data-gesto", "data-hef-gesto")

#: O QUINTO VOCABULÁRIO, POR CLASSE: o rodapé mora no ``topo.html``, o esqueleto
#: das dez, e um ``data-gesto`` ali mudaria as dez páginas de uma vez.
CLASSE_DE_GESTO = re.compile(r"\br-([a-z]+)\b")

#: Quem endereça o BLOCO de um controle. A tela fala ``pref`` (``p1``); o daemon
#: fala ``uniq``. As duas formas aparecem em página, e o bootstrap aceita as duas.
ATRIBUTOS_DE_DONO = ("data-controle", "data-uniq")

#: As tags que não fecham. Sem esta lista, um ``<input data-campo="x">`` deixaria
#: um quadro aberto para sempre e engoliria o texto de todos os irmãos.
SEM_FECHO = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
})

#: O que o ``escrever()`` do BOOTSTRAP põe no lugar do vazio. Não é enfeite: um
#: campo pintado com ``None`` mostra travessão, e comparar contra ``""`` diria
#: que o produto não pintou quando pintou.
TRAVESSAO = "—"

PRODUTO = "PRODUTO"
MOCKUP = "MOCKUP"
INDECIDIVEL = "INDECIDIVEL"
#: O QUARTO VEREDITO, e ele é dela (03/09/2026). Um título de seção, o texto de
#: um botão e o nome de uma opção NÃO são dívida — são RÓTULO, e rótulo não muda.
#: Contá-los como ``MOCKUP`` fazia 100% ser inalcançável por construção: medido
#: em 02/09, 38 dos 53 "pendentes" eram rótulos, e o teto aritmético era ~89%.
#:
#: A marca é ``data-hef-rotulo`` no elemento, e ela é DECLARAÇÃO, nunca
#: inferência: quem não a puser continua acusado. Foi assim que ela pediu — *"a
#: régua para de cobrá-lo e passa a EXIGIR a marca"* —, e é o que impede a
#: categoria de virar o esconderijo onde dívida real vai morar.
ROTULO = "ROTULO"


def _espremer(texto: str) -> str:
    """O texto como o DOM o entrega a esta régua: sem espaço em excesso.

    O HTML é gerado com indentação, e ``textContent`` traz as quebras de linha
    junto. Comparar cru diria que TODO campo mudou.
    """
    return " ".join(texto.split())


class _SoOTexto(html.parser.HTMLParser):
    """O texto de um trecho de HTML, sem as tags. Ver :func:`_so_o_texto`."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.pedacos: list[str] = []

    def handle_data(self, data: str) -> None:
        self.pedacos.append(data)


def _so_o_texto(marcado: str) -> str:
    """``"hoje <b>segue o global</b>"`` → ``"hoje segue o global"``.

    O QUE ELA MOSTRARIA se este HTML fosse escrito no ``innerHTML``, lido do
    jeito que esta régua lê o alvo ``html``: pelo TEXTO. Nenhuma tag acrescenta
    espaço — ``textContent`` cola ``<b>a</b>b`` como ``"ab"``, e o ``<br>`` não
    vira branco nenhum —, então concatenar os dados do parser reproduz o
    navegador. As entidades vêm resolvidas (``convert_charrefs``), como no DOM.
    """
    p = _SoOTexto()
    p.feed(marcado)
    p.close()
    return _espremer("".join(p.pedacos))


@dataclasses.dataclass(frozen=True)
class _Campo:
    """Um endereço de pintura, com o que o ARQUIVO crava nele.

    :param chave: o valor do ``data-campo`` (ou ``data-papel``/``data-hef``).
    :param dono: o ``pref`` do bloco de controle em volta, ou ``""`` quando o
        campo é da mesa. Sem isto a aba Gatilhos seria ilegível: os 25 campos
        se repetem QUATRO vezes, uma por coluna, e ``aj-val-e-0`` vale ``7`` na
        do P1 e ``3`` na do P2.
    :param alvo: o mesmo ``data-hef-alvo`` que o bootstrap lê — o que na tela
        recebe o valor: o texto, a largura da barra, o ``value`` do campo.
    :param valor: o que está CRAVADO no arquivo publicado.
    :param rotulo: o ``data-hef-rotulo`` — a DECLARAÇÃO de que este campo é
        texto fixo, e não dado que o produto deveria escrever. Ver :data:`ROTULO`.
    :param quando: só para o alvo ``classe`` — o ``data-hef-quando``, que é
        QUEM ESTE ELEMENTO É dentro do grupo. Os quatro degraus da Vibração
        compartilham um endereço só, e sem isto a régua não saberia que uma
        declaração de ``'max'`` deixa os outros três apagados DE PROPÓSITO —
        acusaria três endereços mortos onde o produto acertou.
    """

    chave: str
    dono: str
    alvo: str
    valor: str
    quando: str = ""
    rotulo: bool = False

    @property
    def endereco(self) -> str:
        return f"{self.dono}·{self.chave}" if self.dono else self.chave


@dataclasses.dataclass(frozen=True)
class _Gesto:
    """Um endereço CLICÁVEL do arquivo, com o controle em volta (ou ``""``)."""

    nome: str
    dono: str


@dataclasses.dataclass(frozen=True)
class _Veredito:
    campo: _Campo
    vivo: str
    classe: str
    declarado: str | None
    nota: str


class _Leitor(html.parser.HTMLParser):
    """Lê o HTML publicado e devolve os endereços com o que está cravado neles.

    POR QUE UM PARSER, E NÃO UM ``grep``: um ``data-campo`` não guarda o valor
    num atributo — ele guarda no CONTEÚDO do elemento, que pode ter tags
    dentro, e o dono está no ancestral. Expressão regular sobre isso é a
    ferramenta errada, e a casa já pagou por ler estrutura com busca de texto.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.campos: list[tuple[int, _Campo]] = []
        self.gestos: list[_Gesto] = []
        #: Os endereços que são CAMPO e GESTO ao mesmo tempo — a aba Vibração
        #: inteira. Saem no relato porque não dá para tratá-los como nenhum dos
        #: dois sem escolher por eles.
        self.ambiguos: list[str] = []
        #: Os ``data-papel``, que o ouvinte do bootstrap ACEITA como gesto. Eles
        #: não entram na lista de cliques (ver ``ATRIBUTOS_DE_GESTO``), mas
        #: precisam sair no relato: em 05-vibracao os três gestos REGISTRADOS
        #: — `forca`, `testar`, `parar` — são endereçados só assim, e uma régua
        #: que os ignorasse não clicaria um único botão daquela aba.
        self.papeis: list[_Gesto] = []
        self.scripts = 0
        self._pilha: list[dict[str, Any]] = []
        self._donos: list[str] = []
        self._ordem = 0

    # -- os quadros --------------------------------------------------------
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        d = {k: (v or "") for k, v in attrs}
        if tag == "script":
            self.scripts += 1
        dono = ""
        for a in ATRIBUTOS_DE_DONO:
            if d.get(a):
                dono = d[a]
                break
        chave = ""
        for a in ATRIBUTOS_DE_CAMPO:
            if d.get(a):
                chave = d[a]
                break
        for a in ATRIBUTOS_DE_GESTO:
            if d.get(a):
                self.gestos.append(_Gesto(d[a], dono or (self._donos[-1] if self._donos else "")))
                break
        else:
            achou = CLASSE_DE_GESTO.search(d.get("class", ""))
            if achou:
                self.gestos.append(
                    _Gesto(achou.group(1), dono or (self._donos[-1] if self._donos else "")))
        if d.get("data-papel"):
            self.papeis.append(
                _Gesto(d["data-papel"], dono or (self._donos[-1] if self._donos else "")))
            if d.get("data-gesto") or d.get("data-hef-gesto"):
                self.ambiguos.append(d["data-papel"])

        quadro: dict[str, Any] = {
            "tag": tag,
            "attrs": d,
            "chave": chave,
            "dono": dono or (self._donos[-1] if self._donos else ""),
            "texto": [],
            "cru": [],
            "escolhas": [],
            "ordem": self._ordem,
        }
        if chave:
            self._ordem += 1
        if dono:
            self._donos.append(dono)
            quadro["empilhou_dono"] = True
        self._pilha.append(quadro)
        if tag in SEM_FECHO:
            self._fechar(tag)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in SEM_FECHO:
            self._fechar(tag)

    def handle_endtag(self, tag: str) -> None:
        self._fechar(tag)

    def handle_data(self, data: str) -> None:
        for quadro in self._pilha:
            quadro["texto"].append(data)
            quadro["cru"].append(data)

    def _fechar(self, tag: str) -> None:
        # PROCURA O QUADRO DA TAG, e não presume que é o topo: um ``</div>``
        # sobrando (ou um ``<p>`` sem fecho) desalinharia a pilha para sempre.
        for i in range(len(self._pilha) - 1, -1, -1):
            if self._pilha[i]["tag"] == tag:
                break
        else:
            return
        while len(self._pilha) > i:
            quadro = self._pilha.pop()
            if quadro.get("empilhou_dono") and self._donos:
                self._donos.pop()
            # UMA ``<option>`` VIRA ITEM DO ``<select>`` que a contém — é o que
            # deixa a régua saber qual valor o navegador vai mostrar sem abrir
            # navegador nenhum.
            if quadro["tag"] == "option" and self._pilha:
                for acima in reversed(self._pilha):
                    if acima["tag"] == "select":
                        # SEM ATRIBUTO `value`, O VALOR DA OPÇÃO É O TEXTO
                        # DELA. É contrato do HTML, e ignorá-lo custou caro
                        # aqui: os `<select>` da aba Conexões escrevem
                        # `<option>Wi-Fi</option>` sem `value`, e a régua os
                        # lia como vazios — depois acusava a página virgem de
                        # "já ter sido pintada" porque o navegador devolvia
                        # `Wi-Fi` e ela esperava `''`.
                        acima["escolhas"].append(
                            (quadro["attrs"].get("value",
                                                 _espremer("".join(quadro["texto"]))),
                             "selected" in quadro["attrs"]))
                        break
            if quadro["chave"]:
                self.campos.append((quadro["ordem"], self._campo(quadro)))

    # -- o valor cravado ---------------------------------------------------
    def _campo(self, quadro: dict[str, Any]) -> _Campo:
        d: dict[str, str] = quadro["attrs"]
        alvo = d.get("data-hef-alvo") or "texto"
        texto = _espremer("".join(quadro["texto"]))
        valor = texto
        if alvo == "valor":
            if quadro["tag"] == "select":
                escolhidas = [v for v, sel in quadro["escolhas"] if sel]
                # SEM ``selected``, O NAVEGADOR ESCOLHE A PRIMEIRA. Presumir
                # vazio faria a régua acusar como PRODUTO todo ``<select>`` que
                # ninguém pintou.
                valor = escolhidas[0] if escolhidas else (
                    quadro["escolhas"][0][0] if quadro["escolhas"] else "")
            else:
                valor = d.get("value", "")
        elif alvo == "largura":
            valor = _do_estilo(d.get("style", ""), "width")
        elif alvo == "cor":
            # LIDA DE VERDADE, e não pelo texto: a normalização do WebKit para
            # ``color`` é fechada e ``_cor_css`` a reproduz. Ver a nota do
            # ``LER_CAMPOS``, com a sondagem que a mediu.
            valor = _cor_css(_do_estilo(d.get("style", ""), "color"))
        elif alvo == "atributo":
            # O ALVO `atributo` — o que o ARQUIVO crava no atributo que o
            # `data-hef-atributo` nomeia. Sem este ramo a régua leria o TEXTO de
            # um `<svg>` (que é vazio) e chamaria de ENDEREÇO MORTO todo
            # `data-colorway` que o produto pintasse certo — foi o que acabou de
            # acontecer com o alvo `html`, e a lição ficou escrita em
            # `_declarado_neste_elemento`.
            #
            # O VAZIO POR OMISSÃO CASA COM O `|| ''` do `LER_CAMPOS`: atributo
            # ausente é `""` nos dois lados, que é como o produto deixa um SVG
            # cujo aparelho não disse a cor.
            valor = d.get((d.get("data-hef-atributo") or "").strip().lower(), "")
        elif alvo == "classe":
            classe = d.get("data-hef-classe") or "on"
            quando = d.get("data-hef-quando") or ""
            aceso = classe in (d.get("class") or "").split()
            valor = (quando or "sim") if aceso else ""
        elif alvo in ("fundo", "html"):
            # OS DOIS ALVOS QUE A RÉGUA LÊ PELO TEXTO, e ela DIZ que faz isso.
            # ``el.style.background`` e ``el.innerHTML`` voltam do WebKit
            # NORMALIZADOS — a cor vira ``rgb(…)``, as aspas dos atributos
            # trocam — e comparar a forma do arquivo com a forma do navegador
            # acusaria mudança onde não houve. O texto visível é o denominador
            # comum, e é o que responde a pergunta desta régua: quem olha a tela
            # está lendo dado ou desenho?
            valor = texto
        return _Campo(chave=quadro["chave"], dono=quadro["dono"], alvo=alvo,
                      valor=valor, quando=d.get("data-hef-quando") or "",
                      rotulo="data-hef-rotulo" in d)


#: Um comprimento CSS: o número e a unidade. Serve para reproduzir, do lado
#: Python, a forma com que o navegador devolve ``el.style.width``.
_COMPRIMENTO = re.compile(r"^([+-]?(?:\d+\.?\d*|\.\d+))([a-z%]*)$", re.IGNORECASE)


def _numero_css(valor: str) -> str:
    """``"100.0%"`` → ``"100%"``; ``"66.7%"`` fica ``"66.7%"``.

    O NAVEGADOR REESCREVE O NÚMERO ao guardá-lo, e o gerador do desenho escreve
    ``width:100.0%`` porque vem de um ``float`` do Python. Comparar as duas
    formas cruas dizia que a barra da Vibração tinha sido pintada quando ninguém
    a tocou — foi a última cegueira que esta régua acusou contra si mesma.
    """
    achou = _COMPRIMENTO.match(valor.strip())
    if not achou:
        return valor.strip()
    numero, unidade = achou.groups()
    try:
        n = float(numero)
    except ValueError:
        return valor.strip()
    curto = f"{n:g}"
    return f"{curto}{unidade}"


#: AS TRÊS FAMÍLIAS DE COR QUE O CSSOM REESCREVE — hexadecimal, ``rgb()`` e
#: ``hsl()``. Palavra (``red``, ``transparent``, ``currentcolor``), ``var(--x)``
#: e as funções que o motor não resolve (``color-mix``) voltam como foram
#: escritas, só em minúsculas.
_HEXA = re.compile(r"^#([0-9a-f]*)$", re.IGNORECASE)
_FUNCAO_DE_COR = re.compile(r"^(rgba?|hsla?)\((.*)\)$", re.IGNORECASE | re.DOTALL)

#: Uma palavra-chave de CSS: uma só, sem espaço. Serve para separar ``red`` de
#: ``Cosmic Red``, que o CSSOM RECUSA devolvendo ``''``.
_UMA_PALAVRA = re.compile(r"^[a-z][a-z0-9-]*$", re.IGNORECASE)

#: As unidades de ângulo do matiz, e o fator que leva cada uma a GRAUS. A ordem
#: é POR TAMANHO, do maior para o menor, e não é enfeite: ``"grad"`` termina em
#: ``"rad"``, e testar ``rad`` primeiro leria ``200grad`` como ``200g`` radianos.
_ANGULO = (("turn", 360.0), ("grad", 0.9), ("deg", 1.0), ("rad", 180.0 / math.pi))


def _meio_para_cima(n: float) -> int:
    """O arredondamento do CSSOM, que NÃO é o do Python.

    ``round()`` do Python é bancário — ``round(76.5)`` dá ``76``. O CSSOM
    arredonda meio PARA CIMA, e a diferença aparece: ``rgba(10%, 20%, 30%, 50%)``
    volta do WebKit com o canal azul em ``77`` (30% de 255 = 76,5) e esta régua
    dizia ``76``. Sondado no WebKit desta máquina em 02/09/2026.
    """
    return math.floor(n + 0.5)


def _canal(bruto: str) -> int | None:
    """Um canal de cor — ``"186"`` ou ``"50.439%"`` — no inteiro 0-255 do CSSOM."""
    bruto = bruto.strip()
    try:
        n = float(bruto[:-1]) * 255 / 100 if bruto.endswith("%") else float(bruto)
    except ValueError:
        return None
    return max(0, min(255, _meio_para_cima(n)))


def _fracao(bruto: str, teto: float = 1.0) -> float | None:
    """``"50%"`` ou ``"50"`` → ``0.5``. A saturação e a luminosidade do ``hsl()``.

    O TETO É INFINITO PARA A SATURAÇÃO, e isso foi medido: o WebKit não corta a
    saturação em 100% — ele calcula com o valor cheio e corta os CANAIS.
    ``hsl(210, 150%, 40%)`` volta ``rgb(0, 102, 255)``; cortando a saturação
    antes dá ``rgb(0, 102, 204)``, que foi a última divergência da sonda.
    """
    bruto = bruto.strip()
    try:
        n = float(bruto[:-1] if bruto.endswith("%") else bruto)
    except ValueError:
        return None
    return max(0.0, min(teto, n / 100))


def _matiz(bruto: str) -> float | None:
    """O matiz do ``hsl()`` na volta 0-1, aceitando ``deg``/``grad``/``rad``/``turn``."""
    bruto = bruto.strip().lower()
    escala = 1.0
    for unidade, fator in _ANGULO:
        if bruto.endswith(unidade):
            bruto, escala = bruto[: -len(unidade)], fator
            break
    try:
        graus = float(bruto) * escala
    except ValueError:
        return None
    return (graus % 360.0) / 360.0


def _opacidade(bruto: str) -> int | None:
    """A opacidade em BYTE — que é como o CSSOM a guarda antes de serializar."""
    bruto = bruto.strip()
    try:
        n = float(bruto[:-1]) / 100 if bruto.endswith("%") else float(bruto)
    except ValueError:
        return None
    return max(0, min(255, _meio_para_cima(n * 255)))


def _alfa(byte: int) -> str:
    """O byte de opacidade na forma mais CURTA que volta ao mesmo byte.

    É o que o CSSOM serializa, e não um arredondamento a três casas: ``128``
    vira ``0.5`` — não ``0.502`` —, ``170`` vira ``0.667`` e ``1`` vira
    ``0.004``. Sondado no WebKit desta máquina em 02/09/2026; era esta a
    metade errada da família de oito dígitos que a régua dizia reproduzir.
    """
    for casas in (1, 2, 3):
        curto = f"{byte / 255:.{casas}f}"
        if _meio_para_cima(float(curto) * 255) == byte:
            return f"{float(curto):g}"
    return f"{byte / 255:.3f}"


def _tinta(canais: list[int], byte: int | None) -> str:
    """Os três canais e a opacidade na forma serializada do CSSOM.

    ``alfa`` cheio some: o WebKit devolve ``rgb(0, 0, 255)`` para ``#0000ffff``.
    """
    r, g, b = canais
    if byte is None or byte >= 255:
        return f"rgb({r}, {g}, {b})"
    return f"rgba({r}, {g}, {b}, {_alfa(byte)})"


def _cor_css(valor: str) -> str:
    """A cor como ``el.style.color`` a devolve — a forma do NAVEGADOR, não a do arquivo.

    POR QUE ISTO EXISTE, e é a diferença entre medir e desistir: sem a forma do
    navegador, um campo de cor teria de ser lido pelo TEXTO — e pintar uma cor
    não mexe numa letra, logo o campo seria INDECIDÍVEL para sempre.

    O QUE ELA COBRE, e cada linha é uma sonda no WebKit desta máquina, não uma
    suposição (``test_a_cor_e_medida_no_webkit_e_nao_transcrita`` refaz a sonda
    a cada execução e reprova se as duas se separarem)::

        #RGB · #RGBA · #RRGGBB · #RRGGBBAA    → rgb()/rgba(), com o alfa CURTO
        rgb() · rgba(), vírgula ou espaço     → rgb()/rgba(), canais 0-255
        hsl() · hsla(), deg/grad/rad/turn     → rgb()/rgba()
        red · transparent · currentColor      → minúsculas, como foram escritas
        var(--plastico) · color-mix(…)        → intactas
        hexadecimal e função INVÁLIDOS        → '' , que é o que o CSSOM recusa

    **A AFIRMAÇÃO ANTERIOR CAIU, e ela estava escrita aqui e no ``LER_CAMPOS``
    do piloto:** *"a normalização é FECHADA e pequena — hexadecimal e ``rgb()``
    viram uma só forma, e todo o resto volta como foi escrito"*. Não é fechada.
    Medido em 02/09/2026 com uma sonda de 51 formas: o ``hsl()`` também vira
    ``rgb()``, o alfa de oito dígitos é serializado CURTO (``#0000ff80`` dá
    ``0.5``, e a régua dizia ``0.502``), o alfa cheio DESAPARECE (``#0000ffff``
    dá ``rgb(…)``), o arredondamento é meio-para-cima e não bancário, e todo CSS
    inválido volta ``''`` em vez de voltar como foi escrito.

    O QUE ELA AINDA NÃO SABE, e é o único buraco que sobra: uma PALAVRA de uma
    só peça que não seja cor de verdade (``vermelho``, ``azull``) passa por aqui
    e o CSSOM devolveria ``''``. Separar as duas exigiria a lista das 148 cores
    nomeadas do CSS, e o erro é barulhento: a guarda do DOM virgem do
    ``--prova-de-mockup`` compara este parser com o leitor de tela endereço a
    endereço, e a divergência sai como CEGUEIRA, que reprova.
    """
    valor = valor.strip()
    if not valor:
        return ""
    baixo = valor.lower()
    if baixo.startswith("var("):
        return valor
    achou = _HEXA.match(valor)
    if achou:
        digitos = achou.group(1)
        if len(digitos) not in (3, 4, 6, 8):
            # HEXADECIMAL INVÁLIDO: o CSSOM recusa e o elemento fica sem cor de
            # linha, logo `el.style.color` devolve `''`. Voltar a string crua
            # diria PRODUTO sobre um campo que o navegador nem aceitou.
            return ""
        if len(digitos) in (3, 4):
            digitos = "".join(c * 2 for c in digitos)
        canais = [int(digitos[i:i + 2], 16) for i in (0, 2, 4)]
        return _tinta(canais, int(digitos[6:8], 16) if len(digitos) == 8 else None)
    achou = _FUNCAO_DE_COR.match(valor)
    if achou:
        nome = achou.group(1).lower()
        partes = [p for p in re.split(r"[,\s/]+", achou.group(2).strip()) if p]
        if len(partes) not in (3, 4):
            return ""
        byte = _opacidade(partes[3]) if len(partes) == 4 else None
        if len(partes) == 4 and byte is None:
            return ""
        if nome.startswith("rgb"):
            crus = [_canal(p) for p in partes[:3]]
            if any(c is None for c in crus):
                return ""
            canais = [c for c in crus if c is not None]
        else:
            matiz = _matiz(partes[0])
            saturacao = _fracao(partes[1], teto=math.inf)
            luz = _fracao(partes[2])
            if matiz is None or saturacao is None or luz is None:
                return ""
            canais = [max(0, min(255, _meio_para_cima(c * 255)))
                      for c in colorsys.hls_to_rgb(matiz, luz, saturacao)]
        return _tinta(canais, byte)
    if "(" in valor:
        # UMA FUNÇÃO QUE O CSSOM NÃO RESOLVE — `color-mix`, `light-dark` — volta
        # como foi escrita.
        return baixo
    if not _UMA_PALAVRA.match(valor):
        # NÃO É PALAVRA-CHAVE NENHUMA (`Cosmic Red` tem espaço): o CSSOM recusa.
        return ""
    return baixo


def _ligado(texto: str) -> bool:
    """O que conta como LIGADO no alvo ``classe`` — a mesma lista do ``ligado()`` do JS.

    Sem esta função os dois lados discordariam no caso mais comum: o pacote
    emite ``True`` e ``_como_a_tela_escreveria`` devolve ``"True"``, enquanto o
    JS escreveria ``"true"``. Para texto isso é inofensivo (o campo cai em
    MOCKUP, que é o erro para o lado seguro); para uma CLASSE seria o contrário
    — a régua acusaria endereço morto sobre um botão que acende certo.
    """
    b = texto.strip().lower()
    # (noqa-acento) `nao` sem til é VALOR de máquina, e não prosa: é o que um
    # pacote pode emitir. O `escrever()` do JS lê a mesma lista, nas duas grafias.
    return b not in ("", TRAVESSAO, "0", "false", "nao", "não", "off",  # (noqa-acento): valor
                     "none", "null")


def _do_estilo(estilo: str, propriedade: str) -> str:
    """``"width:78%"`` → ``"78%"`` — a mesma forma que ``el.style.width`` devolve."""
    for parte in estilo.split(";"):
        nome, _, valor = parte.partition(":")
        if nome.strip().lower() == propriedade:
            return _numero_css(valor)
    return ""


def _ler_html(texto: str) -> _Leitor:
    """O arquivo publicado, lido uma vez. Devolve o leitor com tudo dentro."""
    leitor = _Leitor()
    leitor.feed(texto)
    leitor.close()
    return leitor


def _campos_cravados(texto: str) -> list[_Campo]:
    """Os endereços de campo do arquivo, EM ORDEM DE DOCUMENTO.

    A ordem é contrato: é ela que deixa o resultado ser comparado, item a item,
    com o que ``querySelectorAll`` devolve do DOM vivo. Sem ordem comum, um
    campo repetido em quatro colunas não teria como casar com o seu par.
    """
    return [c for _, c in sorted(_ler_html(texto).campos, key=lambda p: p[0])]


def _gestos_cravados(texto: str) -> list[_Gesto]:
    """Os endereços CLICÁVEIS do arquivo, com o controle em volta de cada um.

    É esta lista — e não o registro de ``pacotes.GESTOS`` — que a prova botão a
    botão tem de percorrer. A diferença é o defeito de 29/08/2026: o
    ``--prova-gesto`` da aba Controles clicava o que o CÓDIGO registrava, deu
    verde, e nunca tocou os dois botões que a PÁGINA tinha e o código não. Uma
    validação de interface que não cobre o botão novo é uma validação que mente.
    """
    return list(_ler_html(texto).gestos)


def _papeis_cravados(texto: str) -> list[_Gesto]:
    """Os ``data-papel`` da página — endereços que o ouvinte trata como gesto.

    Eles são a razão de a lista de cliques ser a UNIÃO do que a página oferece
    com o que o código registra: na aba Vibração o HTML não tem um único
    ``data-gesto``, e os três gestos daquela aba vivem aqui.
    """
    return list(_ler_html(texto).papeis)


def _como_a_tela_escreveria(valor: Any) -> str:
    """O que o ``escrever()`` do BOOTSTRAP poria na tela para este valor.

    É a tradução de ida do que o pacote declara, para poder comparar com o que
    se lê da tela. O vazio vira travessão, como lá.

    ONDE ELA ERRA, e erra para o lado seguro: ``str(True)`` é ``"True"`` e o JS
    escreveria ``"true"``; ``str(7.0)`` é ``"7.0"`` e o JS escreveria ``"7"``.
    Nos dois casos a régua deixa de reconhecer o valor declarado e o campo cai
    em ``MOCKUP`` em vez de ``INDECIDIVEL`` — isto é, ela deixa de dar por
    provado o que não conseguiu provar, que é a direção certa do erro.
    """
    if valor is None or valor == "":
        return TRAVESSAO
    return str(valor)


def _declarados_do_pacote(carga: dict[str, Any]) -> dict[tuple[str, str], Any]:
    """A carga que o piloto mandaria pintar, como ``{(dono, chave): valor}``.

    ``carga`` é o que o ``pacotes.normalizar()`` devolve, já com o ``topo()``
    somado — ou seja, EXATAMENTE o que iria para a tela naquele tique. Ler daí,
    e não do código-fonte do pacote, é o que impede esta régua de repetir o erro
    das anteriores: ela não pergunta se o nome do campo APARECE em algum lugar,
    pergunta se ele foi EMITIDO com um valor.
    """
    fora: dict[tuple[str, str], Any] = {}
    for chave, valor in (carga.get("mesa") or {}).items():
        fora[("", str(chave))] = valor
    for dono, campos in (carga.get("colunas") or {}).items():
        for chave, valor in (campos or {}).items():
            fora[(str(dono), str(chave))] = valor
    return fora


#: O QUE A RÉGUA PÕE NO LUGAR DE UM CAMPO QUE SUMIU DA TELA. Ele não é um valor
#: possível de nenhum campo — nem o travessão é, porque travessão é o que a
#: pintura escreve num lugar vazio da mesa.
SUMIU = "\x00o bloco foi trocado"


def _alinhar(cravados: list[_Campo], vivos: list[tuple[str, ...]],
            ) -> tuple[list[str], list[tuple[str, str]]]:
    """Casa cada campo do ARQUIVO com o que a tela mostra nele AGORA.

    POR QUE ISTO NÃO É UM ``zip``, e a primeira execução desta régua provou:
    a pintura troca BLOCOS INTEIROS — a fita de chips, a lista de perfis, o mapa
    do gabinete —, porque um bloco cujo NÚMERO DE FILHOS muda com o dado não tem
    como ser pintado campo a campo. Depois de oito voltas, a `10-perfis` tinha
    **81 endereços no arquivo e 55 na tela**: o produto trocou a tabela de
    perfis do desenho pela dela, que é mais curta.

    Comparar por posição ali casaria o campo de uma linha com o da linha
    seguinte e chamaria isso de medição. Aqui o casamento é por ENDEREÇO
    (``chave`` + ``dono``) e por ORDEM DE OCORRÊNCIA dentro dele — que é
    exatamente como o bootstrap distribui uma lista pelos elementos de mesmo
    endereço.

    :returns: os valores vivos na ordem de ``cravados`` (com ``SUMIU`` onde o
        campo deixou de existir), e os endereços que NASCERAM na tela e não
        estão no arquivo — os dois são obra do produto, e o relato os separa.
    """
    por_endereco: dict[tuple[str, str], list[str]] = {}
    for linha in vivos:
        chave, dono, _alvo, valor = linha[:4]
        por_endereco.setdefault((str(chave), str(dono)), []).append(str(valor))
    gastos: dict[tuple[str, str], int] = {}
    fora: list[str] = []
    for campo in cravados:
        endereco = (campo.chave, campo.dono)
        i = gastos.get(endereco, 0)
        gastos[endereco] = i + 1
        disponiveis = por_endereco.get(endereco) or []
        fora.append(disponiveis[i] if i < len(disponiveis) else SUMIU)
    nasceram = [(k, d) for (k, d), valores in sorted(por_endereco.items())
                if len(valores) > gastos.get((k, d), 0)]
    return fora, nasceram


def _selos_alinhados(cravados: list[_Campo],
                     vivos: list[tuple[Any, ...]]) -> list[bool]:
    """O SELO DA VISITA de cada campo, na ordem de ``cravados``.

    Mesmo casamento do ``_alinhar`` — por endereço e por ordem de ocorrência —,
    só que sobre o quinto elemento que o ``LER_CAMPOS`` passou a devolver: se o
    ``escrever()`` do piloto ESTEVE naquele elemento. Um campo que sumiu da tela
    (bloco trocado) vale ``False``: não há elemento para ter selo, e o
    ``_classificar`` já o julga PRODUTO por outro caminho.

    POR QUE FUNÇÃO SEPARADA, e não um terceiro retorno do ``_alinhar``: ele é
    chamado em teste com quatro colunas e mudar a aridade quebraria a chamada
    sem que ninguém ganhasse nada. Acrescentar é a regra desta casa.
    """
    por_endereco: dict[tuple[str, str], list[bool]] = {}
    for linha in vivos:
        chave, dono = str(linha[0]), str(linha[1])
        por_endereco.setdefault((chave, dono), []).append(
            bool(linha[4]) if len(linha) > 4 else False)
    gastos: dict[tuple[str, str], int] = {}
    fora: list[bool] = []
    for campo in cravados:
        endereco = (campo.chave, campo.dono)
        i = gastos.get(endereco, 0)
        gastos[endereco] = i + 1
        disponiveis = por_endereco.get(endereco) or []
        fora.append(disponiveis[i] if i < len(disponiveis) else False)
    return fora


def _declarado_neste_elemento(campo: _Campo, declarado: str,
                              quandos: frozenset[str] = frozenset()) -> str:
    """O que ESTE elemento mostraria se a declaração do pacote fosse pintada.

    DOIS ALVOS PRECISAM DISTO, e os dois pelo mesmo motivo: entre o que o pacote
    EMITE e o que a tela MOSTRA há uma tradução, e comparar os dois crus acusa
    endereço morto sobre o produto que acertou.

    ``classe`` — os quatro degraus da Vibração dividem UM endereço, o pacote
    declara ``'max'`` uma vez só, e o bootstrap visita os quatro com esse mesmo
    valor. Quem não é ``max`` fica apagado DE PROPÓSITO, e apagado é ``''``.

    ``cor`` — o CSSOM NORMALIZA na atribuição: o pacote emite ``'#0000FF'``
    (``a04_iluminacao._hex`` produz exatamente isso) e ``el.style.color``
    devolve ``'rgb(0, 0, 255)'``. Sem passar a declaração pelo mesmo
    ``_cor_css`` que o parser e o leitor de tela já usam, as duas nunca casam e
    a régua chama de ENDEREÇO MORTO a cor que o produto pintou CERTO. Só a forma
    ``var(--x)`` escapava, e é a única que os testes usavam.

    :param quandos: os ``data-hef-quando`` de TODOS os membros do grupo. Sem
        eles o alvo ``classe`` fica cego ao valor errado: um token que ninguém
        conhece apagaria o grupo inteiro, e como apagado é ``''`` nos dois lados
        a régua daria o MESMO veredito da tela que acende certo. Com eles, o
        token desconhecido volta como veio e cai no ramo do endereço morto.

    Para todo outro alvo a declaração vale como veio.
    """
    if campo.alvo == "html":
        # O ALVO `html` COMPARAVA MARCAÇÃO COM TEXTO, e por isso nunca casava.
        # Achado pela frente da aba 03 em 03/09/2026, com a prova mais dura que
        # se pode ter: a régua chamava de ENDEREÇO MORTO um elemento em que o
        # piloto TINHA CARIMBADO O SELO. Uma régua que diz "o pacote escreve num
        # lugar que a página não tem" sobre um lugar que ela mesma viu ser
        # visitado está se contradizendo.
        #
        # A causa é de forma: o lado do ARQUIVO lê este alvo pelo TEXTO (é o
        # ramo `alvo in ("fundo", "html")` do `_Leitor`, que o documenta), e o
        # pacote emite MARCAÇÃO. Passar a declaração pelo mesmo espremedor de
        # texto põe os dois na mesma língua — é a cura do alvo `cor`, aplicada
        # ao alvo que faltava.
        #
        # A frente que achou isto mediu o efeito e NÃO aplicou, porque a régua
        # não era arquivo dela: fecharia treze campos. Ela tinha razão nas duas
        # coisas — no achado e em não tocar.
        # A função é a da frente da aba 03 (`_so_o_texto`, que já espreme por
        # dentro) — eu tinha escrito uma segunda sem ver a dela, e o `mypy`
        # pegou o `no-redef`. Uma casa com duas implementações da mesma regra
        # é o defeito que esta leva inteira existe para não repetir.
        return _so_o_texto(declarado or "")
    if campo.alvo == "largura":
        # A LARGURA TAMBÉM É NORMALIZADA NA ATRIBUIÇÃO, e ignorar isso acusava
        # endereço morto sobre o produto que ACERTOU — medido em 02/09/2026, na
        # aba Iluminação: a barra do P1 saiu de `width:82%` para `100%` e a régua
        # chamou de MOCKUP, porque o pacote emite `100` (número) e a tela devolve
        # `100%` (a unidade que o CSSOM acrescenta).
        #
        # É o mesmo defeito de forma do alvo `cor`, uma linha acima, e a cura é a
        # mesma: passar a declaração pela tradução que o bootstrap faz ao
        # escrever, em vez de comparar cru com cru.
        bruto = declarado.strip() if declarado else declarado
        if bruto and not bruto.endswith(("%", "px", "em", "rem", "vw", "vh")):
            return f"{bruto}%"
        return bruto
    if campo.alvo == "valor":
        # O `value` de um `<input>` volta do DOM como TEXTO, sempre. Um pacote
        # que emite o número `80` via `el.value = 80` deixa `"80"` na tela, e
        # comparar `80` com `"80"` acusa o produto que acertou.
        return "" if declarado is None else str(declarado)
    if campo.alvo == "html":
        # O TERCEIRO ALVO DA DECISÃO 15 DELA — 03/09/2026, e ele faltava: *"a
        # régua aprende os alvos que faltam (`largura`, `valor`, `html`), como
        # já traduz `classe` e `cor`"*. Os dois primeiros entraram; este não.
        #
        # A TRADUÇÃO É A MESMA IDEIA DAS OUTRAS: entre o que o pacote EMITE e o
        # que a régua LÊ há uma conversão, e comparar cru com cru acusa endereço
        # morto sobre o produto que acertou. Aqui a conversão é a mais grosseira
        # de todas — o pacote emite `<b>segue o global</b>` e esta régua lê o
        # alvo `html` pelo TEXTO, de propósito (ver `_campo` e o `LER_CAMPOS` do
        # piloto: o WebKit devolve o `innerHTML` normalizado, e a forma do
        # arquivo nunca casaria com a do navegador).
        #
        # MEDIDO em 03/09/2026, na aba Conexões: `p1·teto-explica` e
        # `p2·teto-explica` saíam como ENDEREÇO MORTO com o produto pintando os
        # dois a cada tique, e o texto na tela byte a byte igual ao emitido. A
        # única diferença eram as seis tags que a régua não tirava — dois campos
        # cobrados de uma pintura que estava certa.
        return _so_o_texto("" if declarado is None else str(declarado))
    if campo.alvo == "cor":
        # O VAZIO APAGA A COR DE LINHA — o `escrever()` põe `''` no
        # `style.color`, e não o travessão, que não é cor nenhuma.
        return _cor_css("" if declarado == TRAVESSAO else declarado)
    if campo.alvo == "atributo":
        # O TRAVESSÃO APAGA O ATRIBUTO, e não vira o texto `—`. O `escrever()`
        # chama `removeAttribute` no vazio e no travessão (é o mesmo par de
        # caminhos do alvo `plastico`: `""` é a cor que o aparelho não respondeu,
        # `—` é o que o molde escreve num lugar sem dono), e atributo ausente
        # volta do `LER_CAMPOS` como `''`.
        #
        # Sem esta linha a régua compararia `'—'` com `''` e acusaria ENDEREÇO
        # MORTO exatamente sobre a mesa dela: pelo rádio o mapa de canais
        # responde que a cor do aparelho NÃO se lê, e todo SVG daquele controle
        # é pintado com o vazio.
        return "" if declarado == TRAVESSAO else declarado
    if campo.alvo != "classe":
        return declarado
    if not campo.quando:
        return "sim" if _ligado(declarado) else ""
    if declarado == campo.quando:
        return campo.quando
    if quandos and _ligado(declarado) and declarado not in quandos:
        # O TOKEN QUE NENHUM MEMBRO DO GRUPO CONHECE. A tela apaga TUDO, e
        # apagado é `''` — o mesmo que este elemento mostraria se o produto
        # tivesse acertado. Colapsar aqui para `''` daria PRODUTO sobre um
        # grupo inteiramente APAGADO: medido em 02/09/2026, `'maximo'` no lugar  # noqa-acento (token de máquina)
        # de `'max'` dava os mesmos 4 PRODUTO da tela que acende. Devolvendo o
        # token cru, ele não casa com o vazio da tela e a régua acusa.
        return declarado
    return ""


def _classificar(
    cravados: list[_Campo],
    vivos: list[str],
    declarados: dict[tuple[str, str], Any] | None = None,
    selos: list[bool] | None = None,
) -> list[_Veredito]:
    """O veredito de cada campo: PRODUTO, ROTULO, MOCKUP ou INDECIDIVEL.

    :param cravados: os campos do arquivo publicado, em ordem de documento.
    :param vivos: o que a TELA mostra em cada um deles, na mesma ordem.
    :param declarados: o que o pacote emitiu naquele tique — usado só para
        separar ``MOCKUP`` de ``INDECIDIVEL``, e para nomear o endereço morto.
    :param selos: se o ``escrever()`` do piloto ESTEVE em cada elemento. É o
        que decide um INDECIDÍVEL: valor igual ao cravado **com** selo é o
        produto pintando um valor que por acaso coincide com o desenho — e isso
        é PRODUTO, provado. Sem os selos (uma chamada antiga, um teste que só
        compara valores) a classificação é a de antes, campo por campo.

    A ORDEM É O CASAMENTO, e as duas listas têm de ter o mesmo tamanho: quem
    garante isso é o ``--prova-de-mockup``, que compara o conjunto de endereços
    do arquivo com o do DOM antes de chegar aqui e reprova se divergirem.
    """
    if len(cravados) != len(vivos):
        raise ValueError(
            f"a régua recebeu {len(cravados)} campos do arquivo e {len(vivos)} da "
            f"tela. Não se comparam listas de tamanhos diferentes: seria casar "
            f"campo com vizinho e chamar de medição.")
    declarados = declarados or {}
    #: Quantas vezes cada endereço já apareceu — é o índice com que uma LISTA
    #: declarada se distribui pelos elementos de mesmo endereço, do mesmo jeito
    #: que o bootstrap distribui.
    ja_vistos: dict[tuple[str, str], int] = {}
    #: OS MEMBROS DE CADA GRUPO DO ALVO ``classe``, por endereço. É o que deixa
    #: `_declarado_neste_elemento` distinguir "apagado de propósito" de "o
    #: pacote emitiu um token que ninguém conhece" — sem isso os dois têm a
    #: mesma cara na tela (``''``) e a régua não acusa nem um nem outro.
    quandos: dict[tuple[str, str], set[str]] = {}
    for campo in cravados:
        if campo.alvo == "classe" and campo.quando:
            quandos.setdefault((campo.dono, campo.chave), set()).add(campo.quando)
    selados = list(selos or [False] * len(cravados))
    if len(selados) != len(cravados):
        raise ValueError(
            f"a régua recebeu {len(cravados)} campos e {len(selados)} selos de "
            f"visita. Casar selo com o vizinho é pior que não ter selo nenhum.")
    fora: list[_Veredito] = []
    for campo, vivo, selo in zip(cravados, vivos, selados, strict=True):
        endereco = (campo.dono, campo.chave)
        i = ja_vistos.get(endereco, 0)
        ja_vistos[endereco] = i + 1
        bruto = declarados.get(endereco, declarados.get(("", campo.chave), ...))
        if isinstance(bruto, list):
            bruto = bruto[i] if i < len(bruto) else ""
        declarado = (None if bruto is ... else _declarado_neste_elemento(
            campo, _como_a_tela_escreveria(bruto),
            frozenset(quandos.get(endereco, ()))))

        if campo.rotulo:
            # RÓTULO DECLARADO SAI DA CONTA — decisão dela, 03/09/2026. Ele vem
            # ANTES de todos os outros ramos de propósito: um título de seção
            # que por acaso mudasse de texto viraria PRODUTO nos ramos abaixo, e
            # isso seria pior que contá-lo como dívida — daria por escrito pelo
            # produto uma coisa que ninguém escreve.
            #
            # E a marca é EXIGIDA, não inferida: quem não puser `data-hef-rotulo`
            # continua caindo nos ramos de baixo e sendo cobrado. É a diferença
            # entre uma categoria e um esconderijo.
            fora.append(_Veredito(
                campo, vivo, ROTULO, None,
                "rótulo declarado: texto fixo, não é dado que o produto escreva"))
        elif vivo == SUMIU:
            fora.append(_Veredito(
                campo, vivo, PRODUTO, declarado,
                "o bloco que continha este campo foi TROCADO pelo produto — "
                "o desenho não sobreviveu, que é o que se queria"))
        elif vivo != campo.valor:
            fora.append(_Veredito(campo, vivo, PRODUTO, declarado,
                                 f"a tela mudou: {campo.valor!r} → {vivo!r}"))
        elif declarado is None:
            fora.append(_Veredito(campo, vivo, MOCKUP, None,
                                 "nenhum pacote declara este endereço"))
        elif declarado == vivo and selo:
            # O INDECIDÍVEL DECIDIDO. Eram 74 campos em 330 assim, e a nota
            # abaixo dizia a verdade: ler a TELA não separa "pintou igual" de
            # "não pintou". O selo não é a tela — é o piloto declarando que
            # ESTEVE neste elemento com este valor. Com ele o campo é do
            # produto, provado, e a coincidência com o desenho passa a ser o
            # que sempre foi: uma coincidência.
            fora.append(_Veredito(
                campo, vivo, PRODUTO, declarado,
                "o piloto ESCREVEU este valor neste elemento — coincide com o "
                "que o desenho cravou, e é o produto que manda"))
        elif declarado == vivo:
            fora.append(_Veredito(
                campo, vivo, INDECIDIVEL, declarado,
                "o pacote declara este mesmo valor e o piloto NÃO passou por "
                "este elemento — ler a tela não separa 'pintou igual' de 'não "
                "pintou'"))
        else:
            # O ENDEREÇO MORTO, e ele é o pior dos casos: o pacote monta o valor
            # e escreve num lugar que a página não tem. A tela continua no
            # desenho, o pacote continua "cobrindo" o campo, e portão nenhum via.
            fora.append(_Veredito(
                campo, vivo, MOCKUP, declarado,
                f"ENDEREÇO MORTO: o pacote declara {declarado!r} e a tela "
                f"continua em {campo.valor!r}"))
    return fora


def _contar(vereditos: list[_Veredito]) -> dict[str, int]:
    """As QUATRO contagens de uma aba, sempre com as quatro chaves presentes.

    Eram três até 03/09/2026; a `ROTULO` entrou com a decisão dela. As chaves
    nascem todas em zero de propósito — quem lê `contas[MOCKUP]` numa aba sem
    nenhum não pode receber `KeyError`.
    """
    fora = {PRODUTO: 0, ROTULO: 0, MOCKUP: 0, INDECIDIVEL: 0}
    for v in vereditos:
        fora[v.classe] += 1
    return fora


def _alvos_a_clicar(
    da_pagina: list[_Gesto],
    registrados: set[str],
    pagina: str,
    perigosos: set[tuple[str, str]],
) -> tuple[list[str], list[str]]:
    """Os gestos a clicar, e os que ficam de fora por mexerem na máquina dela.

    A LISTA É A UNIÃO, e as duas metades pegam defeitos opostos:

    * o que a PÁGINA oferece e o código não registra — o botão que ninguém
      ligou. Era o que ficava de fora, e é o defeito de 29/08/2026: o
      ``--prova-gesto`` da aba Controles clicava só o que o código registrava,
      deu verde, e nunca tocou os dois botões que a página tinha. *Uma
      validação de interface que não cobre o botão novo é uma validação que
      mente.*
    * o que o CÓDIGO registra e a página não oferece por ``data-gesto`` — a aba
      Vibração inteira, cujos três gestos são endereçados por ``data-papel``.
      Tirar essa metade deixaria aquela aba sem um único clique.

    A ordem de saída é estável: primeiro os da página, depois os que só o
    código conhece — para o relato ler igual em duas execuções seguidas.
    """
    vistos: list[str] = []
    pulados: list[str] = []
    for nome in [g.nome for g in da_pagina] + sorted(registrados):
        if nome in vistos or nome in pulados:
            continue
        # O CORINGA `("*", nome)` EXISTE PORQUE O GESTO EXISTE ASSIM: o rodapé
        # registra `@gesto("*", "salvar")` — um gesto só, vivo nas dez páginas.
        # Sem o coringa aqui, isentá-lo pediria dez linhas na lista e a décima
        # primeira aba nasceria desprotegida sem ninguém notar.
        perigoso = (pagina, nome) in perigosos or ("*", nome) in perigosos
        (pulados if perigoso else vistos).append(nome)
    return vistos, pulados


def _cobertura_dos_gestos(
    da_pagina: list[_Gesto],
    registrados: set[str],
    clicados: list[str],
    pulados: list[str],
) -> list[str]:
    """Os endereços clicáveis que a prova NÃO tocou.

    Devolver lista vazia é a única saída aceitável de uma prova de interface.
    Qualquer nome aqui é a régua confessando que deu verde sobre um botão que
    nunca apertou — que é o que ela existe para não fazer.
    """
    tocados = set(clicados) | set(pulados)
    return sorted(({g.nome for g in da_pagina} | set(registrados)) - tocados)

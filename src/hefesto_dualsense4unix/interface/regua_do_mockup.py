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
contavam se o NOME de um campo aparecia no código do pacote. Foi assim que a
primeira medição reportou **77% de paridade** onde o produto entregava 36%, e assim
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

ATRIBUTOS_DE_CAMPO = ("data-campo", "data-papel", "data-hef")

ATRIBUTOS_DE_GESTO = ("data-gesto", "data-hef-gesto")

CLASSE_DE_GESTO = re.compile(r"\br-([a-z]+)\b")

ATRIBUTOS_DE_DONO = ("data-controle", "data-uniq")

SEM_FECHO = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
})

TRAVESSAO = "—"

PRODUTO = "PRODUTO"
MOCKUP = "MOCKUP"
INDECIDIVEL = "INDECIDIVEL"
ROTULO = "ROTULO"


def _espremer(texto: str) -> str:
    """O texto como o DOM o entrega a esta régua: sem espaço em excesso."""
    return " ".join(texto.split())


class _SoOTexto(html.parser.HTMLParser):
    """O texto de um trecho de HTML, sem as tags. Ver :func:`_so_o_texto`."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.pedacos: list[str] = []

    def handle_data(self, data: str) -> None:
        self.pedacos.append(data)


def _so_o_texto(marcado: str) -> str:
    """``"hoje <b>segue o global</b>"`` → ``"hoje segue o global"``."""
    p = _SoOTexto()
    p.feed(marcado)
    p.close()
    return _espremer("".join(p.pedacos))


@dataclasses.dataclass(frozen=True)
class _Campo:
    """Um endereço de pintura, com o que o ARQUIVO crava nele."""

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
    """Lê o HTML publicado e devolve os endereços com o que está cravado neles."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.campos: list[tuple[int, _Campo]] = []
        self.gestos: list[_Gesto] = []
        self.ambiguos: list[str] = []
        self.papeis: list[_Gesto] = []
        self.scripts = 0
        self._pilha: list[dict[str, Any]] = []
        self._donos: list[str] = []
        self._ordem = 0

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
        for i in range(len(self._pilha) - 1, -1, -1):
            if self._pilha[i]["tag"] == tag:
                break
        else:
            return
        while len(self._pilha) > i:
            quadro = self._pilha.pop()
            if quadro.get("empilhou_dono") and self._donos:
                self._donos.pop()
            if quadro["tag"] == "option" and self._pilha:
                for acima in reversed(self._pilha):
                    if acima["tag"] == "select":
                        acima["escolhas"].append(
                            (quadro["attrs"].get("value",
                                                 _espremer("".join(quadro["texto"]))),
                             "selected" in quadro["attrs"]))
                        break
            if quadro["chave"]:
                self.campos.append((quadro["ordem"], self._campo(quadro)))

    def _campo(self, quadro: dict[str, Any]) -> _Campo:
        d: dict[str, str] = quadro["attrs"]
        alvo = d.get("data-hef-alvo") or "texto"
        texto = _espremer("".join(quadro["texto"]))
        valor = texto
        if alvo == "valor":
            if quadro["tag"] == "select":
                escolhidas = [v for v, sel in quadro["escolhas"] if sel]
                valor = escolhidas[0] if escolhidas else (
                    quadro["escolhas"][0][0] if quadro["escolhas"] else "")
            else:
                valor = d.get("value", "")
        elif alvo == "largura":
            valor = _do_estilo(d.get("style", ""), "width")
        elif alvo == "altura":
            valor = _do_estilo(d.get("style", ""), "height")
        elif alvo == "posicao":
            valor = _posicao_do_estilo(d.get("style", ""))
        elif alvo == "cor":
            valor = _cor_css(_do_estilo(d.get("style", ""), "color"))
        elif alvo == "atributo":
            valor = d.get((d.get("data-hef-atributo") or "").strip().lower(), "")
        elif alvo == "marcado":
            valor = "sim" if "checked" in d else ""
        elif alvo == "classe":
            classe = d.get("data-hef-classe") or "on"
            quando = d.get("data-hef-quando") or ""
            aceso = classe in (d.get("class") or "").split()
            valor = (quando or "sim") if aceso else ""
        elif alvo in ("fundo", "html"):
            valor = texto
        return _Campo(chave=quadro["chave"], dono=quadro["dono"], alvo=alvo,
                      valor=valor, quando=d.get("data-hef-quando") or "",
                      rotulo="data-hef-rotulo" in d)


_COMPRIMENTO = re.compile(r"^([+-]?(?:\d+\.?\d*|\.\d+))([a-z%]*)$", re.IGNORECASE)


def _numero_css(valor: str) -> str:
    """``"100.0%"`` → ``"100%"``; ``"66.7%"`` fica ``"66.7%"``."""
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


_HEXA = re.compile(r"^#([0-9a-f]*)$", re.IGNORECASE)
_FUNCAO_DE_COR = re.compile(r"^(rgba?|hsla?)\((.*)\)$", re.IGNORECASE | re.DOTALL)

_UMA_PALAVRA = re.compile(r"^[a-z][a-z0-9-]*$", re.IGNORECASE)

_ANGULO = (("turn", 360.0), ("grad", 0.9), ("deg", 1.0), ("rad", 180.0 / math.pi))


def _meio_para_cima(n: float) -> int:
    """O arredondamento do CSSOM, que NÃO é o do Python."""
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
    """``"50%"`` ou ``"50"`` → ``0.5``. A saturação e a luminosidade do ``hsl()``."""
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
    """O byte de opacidade na forma mais CURTA que volta ao mesmo byte."""
    for casas in (1, 2, 3):
        curto = f"{byte / 255:.{casas}f}"
        if _meio_para_cima(float(curto) * 255) == byte:
            return f"{float(curto):g}"
    return f"{byte / 255:.3f}"


def _tinta(canais: list[int], byte: int | None) -> str:
    """Os três canais e a opacidade na forma serializada do CSSOM."""
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
        return baixo
    if not _UMA_PALAVRA.match(valor):
        return ""
    return baixo


def _ligado(texto: str) -> bool:
    """O que conta como LIGADO no alvo ``classe`` — a mesma lista do ``ligado()`` do JS."""
    b = texto.strip().lower()
    # (noqa-acento) `nao` sem til é VALOR de máquina, e não prosa: é o que um
    return b not in ("", TRAVESSAO, "0", "false", "nao", "não", "off",  # (noqa-acento): valor
                     "none", "null")


def _do_estilo(estilo: str, propriedade: str) -> str:
    """``"width:78%"`` → ``"78%"`` — a mesma forma que ``el.style.width`` devolve."""
    for parte in estilo.split(";"):
        nome, _, valor = parte.partition(":")
        if nome.strip().lower() == propriedade:
            return _numero_css(valor)
    return ""


def _posicao_do_estilo(estilo: str) -> str:
    """``"--hef-x:62%;--hef-y:44%"`` → ``"62,44"``; sem as duas, ``""``."""
    lido: dict[str, str] = {}
    for parte in estilo.split(";"):
        nome, _, valor = parte.partition(":")
        lido[nome.strip().lower()] = valor.strip().removesuffix("%")
    x, y = lido.get("--hef-x", ""), lido.get("--hef-y", "")
    return f"{x},{y}" if (x or y) else ""


def _ler_html(texto: str) -> _Leitor:
    """O arquivo publicado, lido uma vez. Devolve o leitor com tudo dentro."""
    leitor = _Leitor()
    leitor.feed(texto)
    leitor.close()
    return leitor


def _campos_cravados(texto: str) -> list[_Campo]:
    """Os endereços de campo do arquivo, EM ORDEM DE DOCUMENTO."""
    return [c for _, c in sorted(_ler_html(texto).campos, key=lambda p: p[0])]


def _gestos_cravados(texto: str) -> list[_Gesto]:
    """Os endereços CLICÁVEIS do arquivo, com o controle em volta de cada um."""
    return list(_ler_html(texto).gestos)


def _papeis_cravados(texto: str) -> list[_Gesto]:
    """Os ``data-papel`` da página — endereços que o ouvinte trata como gesto."""
    return list(_ler_html(texto).papeis)


def _como_a_tela_escreveria(valor: Any) -> str:
    """O que o ``escrever()`` do BOOTSTRAP poria na tela para este valor."""
    if valor is None or valor == "":
        return TRAVESSAO
    return str(valor)


def _declarados_do_pacote(carga: dict[str, Any]) -> dict[tuple[str, str], Any]:
    """A carga que o piloto mandaria pintar, como ``{(dono, chave): valor}``."""
    fora: dict[tuple[str, str], Any] = {}
    for chave, valor in (carga.get("mesa") or {}).items():
        fora[("", str(chave))] = valor
    for dono, campos in (carga.get("colunas") or {}).items():
        for chave, valor in (campos or {}).items():
            fora[(str(dono), str(chave))] = valor
    return fora


SUMIU = "\x00o bloco foi trocado"


def _alinhar(cravados: list[_Campo], vivos: list[tuple[str, ...]],
            ) -> tuple[list[str], list[tuple[str, str]]]:
    """Casa cada campo do ARQUIVO com o que a tela mostra nele AGORA."""
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
    """O SELO DA VISITA de cada campo, na ordem de ``cravados``."""
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
        return _so_o_texto(declarado or "")
    if campo.alvo in ("largura", "altura"):
        bruto = declarado.strip() if declarado else declarado
        if bruto and not bruto.endswith(("%", "px", "em", "rem", "vw", "vh")):
            return f"{bruto}%"
        return bruto
    if campo.alvo == "valor":
        return "" if declarado is None else str(declarado)
    if campo.alvo == "posicao":
        return "" if declarado in (None, "", TRAVESSAO) else str(declarado)
    if campo.alvo == "html":
        return _so_o_texto("" if declarado is None else str(declarado))
    if campo.alvo == "cor":
        return _cor_css("" if declarado == TRAVESSAO else declarado)
    if campo.alvo == "atributo":
        return "" if declarado == TRAVESSAO else declarado
    if campo.alvo != "classe":
        return declarado
    if not campo.quando:
        return "sim" if _ligado(declarado) else ""
    if declarado == campo.quando:
        return campo.quando
    if quandos and _ligado(declarado) and declarado not in quandos:
        # grupo inteiramente APAGADO: medido em 02/09/2026, `'maximo'` no lugar  # (noqa-acento): token de máquina
        return declarado
    return ""


def _classificar(
    cravados: list[_Campo],
    vivos: list[str],
    declarados: dict[tuple[str, str], Any] | None = None,
    selos: list[bool] | None = None,
) -> list[_Veredito]:
    """O veredito de cada campo: PRODUTO, ROTULO, MOCKUP ou INDECIDIVEL."""
    if len(cravados) != len(vivos):
        raise ValueError(
            f"a régua recebeu {len(cravados)} campos do arquivo e {len(vivos)} da "
            f"tela. Não se comparam listas de tamanhos diferentes: seria casar "
            f"campo com vizinho e chamar de medição.")
    declarados = declarados or {}
    ja_vistos: dict[tuple[str, str], int] = {}
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
            fora.append(_Veredito(
                campo, vivo, MOCKUP, declarado,
                f"ENDEREÇO MORTO: o pacote declara {declarado!r} e a tela "
                f"continua em {campo.valor!r}"))
    return fora


def _contar(vereditos: list[_Veredito]) -> dict[str, int]:
    """As QUATRO contagens de uma aba, sempre com as quatro chaves presentes."""
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
    """Os gestos a clicar, e os que ficam de fora por mexerem na máquina dela."""
    vistos: list[str] = []
    pulados: list[str] = []
    for nome in [g.nome for g in da_pagina] + sorted(registrados):
        if nome in vistos or nome in pulados:
            continue
        perigoso = (pagina, nome) in perigosos or ("*", nome) in perigosos
        (pulados if perigoso else vistos).append(nome)
    return vistos, pulados


def _cobertura_dos_gestos(
    da_pagina: list[_Gesto],
    registrados: set[str],
    clicados: list[str],
    pulados: list[str],
) -> list[str]:
    """Os endereços clicáveis que a prova NÃO tocou."""
    tocados = set(clicados) | set(pulados)
    return sorted(({g.nome for g in da_pagina} | set(registrados)) - tocados)

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

    PRODUTO      o valor mudou — alguém pintou
    MOCKUP       igual ao cravado, e nenhum pacote declara este campo
    INDECIDIVEL  igual ao cravado, e o pacote declara EXATAMENTE esse valor

A TERCEIRA CLASSE NÃO É PREGUIÇA, é o limite honesto do instrumento. Se o
desenho escreveu ``85%`` e o controle dela está mesmo em ``85%``, ler a tela não
distingue "pintou o valor certo" de "nunca pintou". Separá-las exigiria marcar
cada elemento no momento da escrita — uma marca no caminho quente da pintura,
paga por toda volta do tique, para responder uma pergunta de bancada. A régua
prefere DIZER QUANTOS SÃO a inventar certeza.

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

import dataclasses
import html.parser
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


def _espremer(texto: str) -> str:
    """O texto como o DOM o entrega a esta régua: sem espaço em excesso.

    O HTML é gerado com indentação, e ``textContent`` traz as quebras de linha
    junto. Comparar cru diria que TODO campo mudou.
    """
    return " ".join(texto.split())


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
    """

    chave: str
    dono: str
    alvo: str
    valor: str

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
        elif alvo in ("fundo", "html"):
            # OS DOIS ALVOS QUE A RÉGUA LÊ PELO TEXTO, e ela DIZ que faz isso.
            # ``el.style.background`` e ``el.innerHTML`` voltam do WebKit
            # NORMALIZADOS — a cor vira ``rgb(…)``, as aspas dos atributos
            # trocam — e comparar a forma do arquivo com a forma do navegador
            # acusaria mudança onde não houve. O texto visível é o denominador
            # comum, e é o que responde a pergunta desta régua: quem olha a tela
            # está lendo dado ou desenho?
            valor = texto
        return _Campo(chave=quadro["chave"], dono=quadro["dono"], alvo=alvo, valor=valor)


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


def _alinhar(cravados: list[_Campo], vivos: list[tuple[str, str, str, str]],
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
    for chave, dono, _alvo, valor in vivos:
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


def _classificar(
    cravados: list[_Campo],
    vivos: list[str],
    declarados: dict[tuple[str, str], Any] | None = None,
) -> list[_Veredito]:
    """O veredito de cada campo: PRODUTO, MOCKUP ou INDECIDIVEL.

    :param cravados: os campos do arquivo publicado, em ordem de documento.
    :param vivos: o que a TELA mostra em cada um deles, na mesma ordem.
    :param declarados: o que o pacote emitiu naquele tique — usado só para
        separar ``MOCKUP`` de ``INDECIDIVEL``, e para nomear o endereço morto.

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
    fora: list[_Veredito] = []
    for campo, vivo in zip(cravados, vivos, strict=True):
        endereco = (campo.dono, campo.chave)
        i = ja_vistos.get(endereco, 0)
        ja_vistos[endereco] = i + 1
        bruto = declarados.get(endereco, declarados.get(("", campo.chave), ...))
        if isinstance(bruto, list):
            bruto = bruto[i] if i < len(bruto) else ""
        declarado = None if bruto is ... else _como_a_tela_escreveria(bruto)

        if vivo == SUMIU:
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
        elif declarado == vivo:
            fora.append(_Veredito(
                campo, vivo, INDECIDIVEL, declarado,
                "o pacote declara este mesmo valor — ler a tela não separa "
                "'pintou igual' de 'não pintou'"))
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
    """As três contagens de uma aba, sempre com as três chaves presentes."""
    fora = {PRODUTO: 0, MOCKUP: 0, INDECIDIVEL: 0}
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
        (pulados if (pagina, nome) in perigosos else vistos).append(nome)
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

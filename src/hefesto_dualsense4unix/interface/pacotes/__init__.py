#!/usr/bin/env python3
"""O DESPACHANTE: uma função de pacote por aba, e um contrato só para as dez.

DECISÃO DE 01/09/2026: as dez abas se ligam numa mão só, aba a aba, e não por
um pacote de trabalho independente por aba. A razão é medida, e são três:

1. **O plano era anterior à leva que mudou as dez abas.** Os pilotos de cada aba
   apontavam endereços que essa leva moveu (a mesa virou dois conectados e dois
   lugares vazios, os rótulos mudaram, a fita virou "Selecionar:" e a janela foi
   para 777px): oito pacotes escritos em paralelo sobre premissa velha não pintam,
   e a régua só acusaria no fim.
2. **O teto de sessão.** Em 31/08, **37 de 40 execuções paralelas morreram** por
   isso, e a auditoria mais importante do dia ficou 3/39.
3. **O defeito mais comum do dia atravessava abas.** "Frase que nomeia um
   controle fora da mesa" apareceu QUATRO vezes — na Iluminação, na Navegação, na
   Conexões e na Sistema — e só foi visto olhando as abas irmãs juntas.

O CONTRATO, e ele é o que impede a integração de virar um segundo projeto:

    def pacote(ctx: Contexto) -> dict[str, object]

Uma função por página. Ela recebe o que o daemon respondeu, já mastigado, e
devolve **endereço → valor**: o que a pintura consome. Nenhuma função de pacote
toca GTK, WebView ou IPC — elas são puras, e é por isso que dá para testá-las
sem abrir janela.

DE ONDE VEM O ENDEREÇO DE CADA VALOR, e é a parte que o usuário apontou: o
`docs/data/mapa-controles.csv` (308 linhas, o mesmo que gera o `specs.html`) diz,
para cada peça do controle, o canal, o `report_id` e o comando **por transporte**
— e se ela ACIONA no cabo e no rádio. Quem o pergunta em tempo de execução é
`mesa_viva.aciona(chave, transporte)`, o leitor que o produto usa para a cor, o
giroscópio e o alto-falante. O segundo leitor (`pacotes/mapa.py`) saiu em
28/09/2026 (A-TELA-PERGUNTA-AO-DONO-01): nasceu em 01/09, nenhuma aba o chamou,
e ele respondia a primeira linha da chave sem olhar o controle.
"""
from __future__ import annotations

import html.parser
import pathlib
import re
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

Pintura = Callable[["Contexto"], "dict[str, Any]"]
Gesto = Callable[["Contexto", "dict[str, Any]", Any], "dict[str, Any] | None"]

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))


@dataclass
class Contexto:
    """O que toda função de pacote recebe. É o mesmo para as dez."""

    state: dict[str, Any]
    mesa: list[dict[str, Any]] = field(default_factory=list)
    conectados: list[dict[str, Any]] = field(default_factory=list)
    estados: dict[str, Any] = field(default_factory=dict)
    #: **DE ONDE ELE VEM, e não é o `state_full`:** o daemon publica esta lista
    externos: list[dict[str, Any]] = field(default_factory=list)
    escolhido: str = ""

    def por_uniq(self, uniq: str) -> dict[str, Any]:
        """A entrada do daemon daquele controle, ou `{}` — nunca levanta."""
        for e in self.conectados:
            if str(e.get("uniq") or "") == uniq:
                return e
        return {}


PACOTES: dict[str, Pintura] = {}


def registrar(pagina: str) -> Callable[[Pintura], Pintura]:
    """Decorador: `@registrar("01-jogar.html")` põe a função na tabela."""
    def dentro(fn: Pintura) -> Pintura:
        if pagina in PACOTES:
            raise SystemExit(f"ERRO: {pagina} já tem pacote ({PACOTES[pagina].__module__}). "
                             f"Dois donos para a mesma página é o defeito que este "
                             f"despachante existe para impedir.")
        PACOTES[pagina] = fn
        return fn
    return dentro


GESTOS: dict[tuple[str, str], Gesto] = {}

GESTOS_QUE_MEXEM: dict[tuple[str, str], str] = {}


def gesto(pagina: str, nome: str, *,
          grava: str = "") -> Callable[[Gesto], Gesto]:
    """Decorador: `@gesto("04-iluminacao.html", "cor")` liga um botão.

    A função recebe `(ctx, o, ipc)`:

    * `ctx` — o mesmo `Contexto` da pintura: mesa, conectados, estado do daemon;
    * `o` — o clique como o JS o mandou (`texto`, `campo`, `player`, `lado`…);
    * `ipc` — o carimbo para falar com o daemon: `ipc("profile.switch", name=…)`.

    O `ipc` É INJETADO, e não importado: sem ele a função abriria um socket, e
    uma função que abre socket não se testa sem daemon. Com ele, a régua passa
    um `ipc` de mentira e cobra QUAL método foi chamado e com quais parâmetros —
    que é a única forma de provar que o botão faz o que promete, em vez de
    provar que ele existe.

    `grava=` — O QUE ESTE GESTO MUDA NA MÁQUINA DO USUÁRIO, e quem o declara é quem o
    escreve. Duas formas, e a diferença decide quem confere:

    * **o nome da porta**, quando existe uma chamada que a árvore enxerga —
      `grava="save_profile"`, `grava="gravar_e_reaplicar"`,
      `grava="marcar_jogo_sem_wrapper"`. `test_todo_gesto_que_grava_esta_
      protegido` LÊ a árvore do gesto e cobra que a porta declarada esteja lá:
      declaração errada ou envelhecida reprova nomeando;
    * **uma frase**, quando o perigo não é uma chamada — `grava="para o serviço
      e ela fica sem controle"`. Aí a árvore não tem o que confirmar, e quem
      assembla é a régua, no `FORA_DA_ARVORE` dela, com a medição do lado.

    NÃO É "grava no disco", é **"muda algo dela que ela não mandou mudar"** — a
    área de transferência da 07 e o cursor da 06 estão aqui pela mesma razão que
    o `save_profile`. O que sai daqui é `hefesto_vivo.PERIGOSOS`, a lista do que
    a prova botão a botão NÃO clica sozinha.
    """
    limpo = grava.strip()
    if grava and not limpo:
        raise SystemExit(
            f"ERRO: o gesto {nome!r} de {pagina} declarou `grava=` em branco. "
            f"Declaração vazia é pior que nenhuma: ela some da lista derivada "
            f"sem ninguém notar. Diga a porta ou diga a frase.")

    def dentro(fn: Gesto) -> Gesto:
        chave = (pagina, nome)
        if chave in GESTOS:
            raise SystemExit(
                f"ERRO: o gesto {nome!r} de {pagina} já tem dono "
                f"({GESTOS[chave].__module__}). Dois donos para o mesmo botão é "
                f"o defeito que este despachante existe para impedir.")
        GESTOS[chave] = fn
        if limpo:
            GESTOS_QUE_MEXEM[chave] = limpo
        return fn
    return dentro


#: teste naquele momento isso nao interfere in game (noqa-acento: dela). (…)
#: `rumble_passthrough=False` para sempre, e o jogo ficava mudo sem que nada na
#: o dono das DEZ abas e não conhece o assunto de nenhuma. Uma segunda aba que
CORACOES: list[Callable[[Contexto, Any], None]] = []

LARGADAS: list[Callable[[Any], None]] = []


def coracao(fn: Callable[[Contexto, Any], None]) -> Callable[[Contexto, Any], None]:
    """Registra um batimento por tique. A aba decide se há o que bater."""
    CORACOES.append(fn)
    return fn


def largada(fn: Callable[[Any], None]) -> Callable[[Any], None]:
    """Registra quem larga o que a aba segurava, ao sair da página ou da janela."""
    LARGADAS.append(fn)
    return fn


#: afins."* <!-- noqa-acento: citação literal -->
#: começa com `if not na_mesa: return`, então com a mesa vazia a thread de
PODAS: list[Callable[[frozenset[str]], None]] = []

_NA_MESA_ANTES: list[frozenset[str]] = [frozenset()]


def poda(fn: Callable[[frozenset[str]], None]) -> Callable[[frozenset[str]], None]:
    """Registra quem esquece um controle que saiu. Recebe quem FICOU."""
    PODAS.append(fn)
    return fn


def na_mesa_agora(ctx: Contexto) -> frozenset[str]:
    """Os `uniq` que estão de fato aqui, neste tique."""
    return frozenset(str(c.get("uniq") or "") for c in ctx.conectados
                     if c.get("uniq"))


def podar_o_que_saiu(ctx: Contexto) -> frozenset[str]:
    """Quem saiu da mesa desde o tique anterior — e já esquecido por todos.

    **Nunca levanta**, pela mesma razão de `bater_os_coracoes`: ela roda DENTRO
    do tique, e um tique que levanta para de pintar a aba inteira.

    **A PODA SÓ ACONTECE QUANDO ALGUÉM SAI**, e não a cada tique: varrer seis
    caches dez vezes por segundo para não achar nada é trabalho por nada, e o
    evento que a queixa de uso nomeia é raro — é a mão do usuário tirando o cabo.

    ELA NÃO PODA QUEM CHEGA. Um controle que entra não deixa lixo em cache
    nenhum; o que ele encontra é a própria entrada, da sessão anterior dele, e
    quem a tirou foi a poda da SAÍDA. Curar na chegada seria curar tarde: entre
    a saída e a volta a tela já teria mostrado o dado velho.
    """
    agora = na_mesa_agora(ctx)
    antes, _NA_MESA_ANTES[0] = _NA_MESA_ANTES[0], agora
    saiu = antes - agora
    if not saiu:
        return frozenset()
    for esquecer in PODAS:
        try:
            esquecer(agora)
        except Exception as erro:
            print(f"[poda] {esquecer.__name__}: {erro}", file=sys.stderr)
    return saiu


def bater_os_coracoes(ctx: Contexto, p: Any) -> None:
    """O que o despachante faz a cada tique: PODAR o que saiu e BATER os corações."""
    podar_o_que_saiu(ctx)
    for bate in CORACOES:
        try:
            bate(ctx, p)
        except Exception as erro:
            print(f"[coração] {bate.__name__}: {erro}", file=sys.stderr)


def largar_o_que_as_abas_seguram(p: Any) -> None:
    """Devolve ao jogo/à máquina tudo o que as abas seguravam. **Nunca levanta.**"""
    for larga in LARGADAS:
        try:
            larga(p)
        except Exception as erro:
            print(f"[largada] {larga.__name__}: {erro}", file=sys.stderr)


def perigosos() -> set[tuple[str, str]]:
    """Os gestos que mexem na máquina do usuário — DERIVADOS, nunca digitados."""
    return set(GESTOS_QUE_MEXEM)


def gesto_da_pagina(pagina: str, nome: str) -> Gesto | None:
    """Quem atende aquele botão, ou `None`."""
    return GESTOS.get((pagina, nome)) or GESTOS.get(("*", nome))


def pacote_da_pagina(pagina: str, ctx: Contexto) -> dict[str, Any] | None:
    """O pacote daquela página, ou `None` se ela ainda não tem quem a pinte."""
    fn = PACOTES.get(pagina)
    if fn is None:
        return None
    fora = fn(ctx)
    from .camada import com_a_camada

    fora = com_a_camada(pagina, ctx, fora)
    molde = molde_do_lugar(pagina, ctx, fora)
    if not molde:
        return fora
    colunas = dict(fora.get(POR_CONTROLE[0]) or {})
    colunas[LUGAR_SEM_DONO] = molde
    com_molde = {**fora, POR_CONTROLE[0]: colunas}
    pinta = _PINTA.get(_chave_do_molde(pagina, ctx))
    if pinta:
        com_molde[CAMPOS_DO_LUGAR] = sorted(pinta)
    return com_molde


POR_CONTROLE = ("colunas", "cartoes", "cards")

CAMPOS_DO_LUGAR = "campos-do-lugar"

NAO_SAO_VALOR = {"cobertura", "sem_dono", CAMPOS_DO_LUGAR}


#: `data-conectado="nao"` / classe `off` no que sobra dessa conta
LUGAR_SEM_DONO = "*"

LUGAR_VAZIO = "vazio"

MARCAS_DO_LUGAR = "marcas"

TODOS_OS_LUGARES = frozenset({"p1", "p2", "p3", "p4"})

_BLOCO_DE_UM_CAMPO = re.compile(
    r'\[data-controle="(?P<pref>[^"]+)"\]\s*\[data-campo="(?P<campo>[^"]+)"\]')


def _o_que_o_bloco_ja_escreveu(carga: dict[str, Any]) -> dict[str, set[str]]:
    """`{pref: {campo, …}}` — o que a aba já pôs naquele lugar por BLOCO."""
    fora: dict[str, set[str]] = {}
    for seletor in (carga.get("blocos") or {}):
        achado = _BLOCO_DE_UM_CAMPO.search(str(seletor))
        if achado:
            fora.setdefault(achado.group("pref"), set()).add(achado.group("campo"))
    return fora


def apagar_os_lugares_sem_dono(
        carga: dict[str, Any],
        com_dono: Iterable[str] | None = None,
        pagina: str | None = None) -> dict[str, Any]:
    """Escreve travessão em todo lugar do desenho que a mesa de agora não tem."""
    colunas = carga.setdefault("colunas", {})
    chaves: set[str] = set()
    for campos in colunas.values():
        chaves |= set(campos)
    # tela passou a dizer `data-conectado="sim"` em dois lugares vazios.
    ocupados = sorted(set(com_dono or ()) & TODOS_OS_LUGARES)
    apagar = sorted(TODOS_OS_LUGARES - set(colunas))
    # O QUE A ABA JÁ ESCREVEU POR BLOCO NÃO SE APAGA — 11/09/2026, e a razão
    ja_escrito = _o_que_o_bloco_ja_escreveu(carga)
    vazio = carga.pop(LUGAR_VAZIO, None) or {}
    pinta = chaves | {str(k) for k in (carga.pop(CAMPOS_DO_LUGAR, None) or ())}
    diz = o_que_o_desenho_diz_do_lugar_vazio(pagina) if pagina else {}
    for pref in apagar:
        colunas[pref] = dict.fromkeys(chaves - ja_escrito.get(pref, set()),
                                      TRAVESSAO)
        if IDENTIDADE_DO_LUGAR in chaves:
            colunas[pref][IDENTIDADE_DO_LUGAR] = (
                f"P{pref[1:]} {PONTO_DO_ROTULO} {SEM_NINGUEM_AQUI}")
        colunas[pref].update({k: v for k, v in diz.get(pref, {}).items()
                              if k in pinta and k not in ja_escrito.get(pref, set())})
        colunas[pref].update({k: v for k, v in vazio.items()
                              if k not in ja_escrito.get(pref, set())})
    carga["vazios"] = apagar
    # `data-conectado="nao"` e a classe `off`, e não havia uma linha em lugar
    carga["ocupados"] = ocupados
    return carga


_CONTROLE_DE_MENTIRA: dict[str, Any] = {"uniq": "aa:bb:cc:00:00:00", "connected": True}

_LUGAR_DE_MENTIRA: dict[str, Any] = {
    "uniq": _CONTROLE_DE_MENTIRA["uniq"], "pref": "p1",
    "jogador": None, "nome": None, "via": None,
}

_MOLDE: dict[tuple[str, str], dict[str, str]] = {}

_PINTA: dict[tuple[str, str], frozenset[str]] = {}


def _chave_do_molde(pagina: str, ctx: Contexto) -> tuple[str, str]:
    """`(página, perfil ativo)` — a chave do `_MOLDE` e do `_PINTA`.

    O NOME SE PERGUNTA AO DONO, e aqui ele é CHAVE DE CACHE — 19/09/2026. Com o
    `ctx.state.get("active_profile")` cru a chave era `None` em toda volta na
    máquina do usuário (o daemon não publica o perfil de janela), e trocar de perfil
    NÃO invalidava o molde: a página seguia com o molde do perfil anterior. Ver
    `perfil.nome_do_ativo`.
    """
    from hefesto_dualsense4unix.interface.pacotes import perfil as _perfil_

    return (pagina, _perfil_.nome_do_ativo(ctx.state))

TRAVESSAO = "—"

SEM_CONTROLE_NA_MESA = "Nenhum controle"

IDENTIDADE_DO_LUGAR = "identidade"
PONTO_DO_ROTULO = "\u2022"
SEM_NINGUEM_AQUI = "Desconectado"


#:   CSSOM não guarda, a comparação nunca casa e o contador soma +1 por tique
ALVOS_QUE_O_TRAVESSAO_NAO_ATENDE = {"largura", "altura", "html", "fundo"}

#: cartão que o desenho publica vazio (`data-conectado="nao"`), com o número do
ALVOS_QUE_O_DESENHO_DIZ = frozenset({"html", "cor", "atributo"})

_LUGAR_NO_HTML = re.compile(r'data-controle="(p\d+)"')

_SEM_FECHO = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
})


class _OlhoNaPagina(html.parser.HTMLParser):
    """A página publicada, lida UMA vez, para as duas perguntas do molde."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.alvos: dict[str, set[str]] = {}
        self.mudos: set[str] = set()
        self._pilha: list[dict[str, Any]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        d = {k: (v or "") for k, v in attrs}
        chave = (d.get("data-campo") or d.get("data-papel")
                 or d.get("data-hef") or "")
        alvo = d.get("data-hef-alvo") or "texto"
        if chave:
            self.alvos.setdefault(chave, set()).add(alvo)
        quadro: dict[str, Any] = {"tag": tag, "chave": chave, "alvo": alvo,
                                  "texto": [], "filhos": []}
        if self._pilha:
            self._pilha[-1]["filhos"].append(quadro)
        self._pilha.append(quadro)
        if tag in _SEM_FECHO:
            self._fechar(tag)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in _SEM_FECHO:
            self._fechar(tag)

    def handle_endtag(self, tag: str) -> None:
        self._fechar(tag)

    def handle_data(self, data: str) -> None:
        for quadro in self._pilha:
            quadro["texto"].append(data)

    def _fechar(self, tag: str) -> None:
        # sobrando desalinharia a pilha para sempre.
        for i in range(len(self._pilha) - 1, -1, -1):
            if self._pilha[i]["tag"] == tag:
                break
        else:
            return
        while len(self._pilha) > i:
            quadro = self._pilha.pop()
            if (quadro["chave"] and quadro["alvo"] == "texto"
                    and any(not "".join(f["texto"]).strip()
                            for f in quadro["filhos"])):
                self.mudos.add(quadro["chave"])

_LUGARES: dict[str, frozenset[str]] = {}


def lugares_da_pagina(pagina: str) -> frozenset[str]:
    """Os `data-controle="pN"` da página PUBLICADA — os lugares do desenho."""
    lembrado = _LUGARES.get(pagina)
    if lembrado is not None:
        return lembrado
    from hefesto_dualsense4unix.interface import onde

    try:
        doc = onde.pagina(pagina, publicado=True).read_text(encoding="utf-8")
    except OSError:
        return frozenset()
    fora = frozenset(_LUGAR_NO_HTML.findall(doc))
    _LUGARES[pagina] = fora
    return fora

#: `pagina` → o olho já passado por ela. Lido uma vez por página.  # (noqa-acento): nome de campo
_ALVOS: dict[str, _OlhoNaPagina] = {}


def _olhar_a_pagina(pagina: str) -> _OlhoNaPagina | None:
    """A página publicada, lida e lembrada. `None` quando ela não abre."""
    lembrado = _ALVOS.get(pagina)
    if lembrado is not None:
        return lembrado
    from hefesto_dualsense4unix.interface import onde

    try:
        doc = onde.pagina(pagina, publicado=True).read_text(encoding="utf-8")
    except OSError:
        return None
    olho = _OlhoNaPagina()
    olho.feed(doc)
    olho.close()
    _ALVOS[pagina] = olho
    return olho


def alvos_da_pagina(pagina: str) -> dict[str, set[str]]:
    """Com que alvo cada endereço da página PUBLICADA é escrito.

    LER A PÁGINA AQUI NÃO É O MESMO que tirar dela a LISTA de campos — e a
    diferença é o que separa esta cura da destruição que `molde_do_lugar`
    descreve. A lista de campos sai da aba, que sabe o que é dado; a página só
    responde **como** cada endereço é escrito, que é informação que só ela tem
    (`data-hef-alvo` é atributo do desenho).

    Vazio quando a página não abre — e aí `molde_do_lugar` desiste, porque sem
    saber como a página escreve o molde escreveria travessão numa barra.
    """
    olho = _olhar_a_pagina(pagina)
    return olho.alvos if olho is not None else {}


def enderecos_que_o_texto_apaga(pagina: str) -> frozenset[str]:
    """Os endereços cujo elemento tem um filho que o TEXTO não sabe dizer."""
    olho = _olhar_a_pagina(pagina)
    return frozenset(olho.mudos) if olho is not None else frozenset()


_E_LUGAR = re.compile(r"p\d+")


def _o_numero_trocado(valor: str, de: int, para: int) -> str:
    """O número do jogador `de` vira `para` onde ele É o número: `P3`, `Player 3`."""
    return re.sub(rf"(?<![0-9A-Za-z#_.-])([Pp]?){de}(?![0-9A-Za-z_%-])",
                  lambda m: f"{m.group(1)}{para}", valor)


class _OLugarNoDesenho(html.parser.HTMLParser):
    """Os lugares da página publicada, campo a campo — com o miolo CRU do `html`."""

    def __init__(self, doc: str) -> None:
        super().__init__(convert_charrefs=True)
        self._doc = doc
        self._linhas = [0, *(m.end() for m in re.finditer("\n", doc))]
        self.campos: dict[str, dict[str, list[tuple[tuple[str, str], str]]]] = {}
        self.vazios: list[str] = []
        self._pilha: list[dict[str, Any]] = []

    def _onde(self) -> int:
        linha, coluna = self.getpos()
        return self._linhas[linha - 1] + coluna

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        d = {k: (v or "") for k, v in attrs}
        lugar = d.get("data-controle", "")
        lugar = lugar if _E_LUGAR.fullmatch(lugar) else ""
        vazio = d.get("data-conectado") == "nao"  # (noqa-acento) valor do atributo
        if lugar and vazio and lugar not in self.vazios:
            self.vazios.append(lugar)
        dentro = next((q["lugar"] for q in reversed(self._pilha) if q["lugar"]), "")
        chave = d.get("data-campo") or d.get("data-papel") or d.get("data-hef") or ""
        quadro: dict[str, Any] = {
            "tag": tag, "lugar": lugar, "campo": None,
            "miolo": self._onde() + len(self.get_starttag_text() or "")}
        if chave and dentro and not lugar:
            alvo = d.get("data-hef-alvo") or "texto"
            nome = (d.get("data-hef-atributo") or "").strip().lower()
            if alvo != "atributo":
                nome = ""
            quadro["campo"] = (dentro, chave, (alvo, nome), d.get(nome, "") if nome else "")
        self._pilha.append(quadro)
        if tag in _SEM_FECHO:
            self._fechar(tag, quadro["miolo"])

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in _SEM_FECHO:
            self._fechar(tag, self._pilha[-1]["miolo"])

    def handle_endtag(self, tag: str) -> None:
        self._fechar(tag, self._onde())

    def _fechar(self, tag: str, fim: int) -> None:
        for i in range(len(self._pilha) - 1, -1, -1):
            if self._pilha[i]["tag"] == tag:
                break
        else:
            return
        while len(self._pilha) > i:
            quadro = self._pilha.pop()
            if quadro["campo"] is None:
                continue
            lugar, chave, assinatura, valor = quadro["campo"]
            if assinatura[0] == "html":
                valor = self._doc[quadro["miolo"]:fim]
            self.campos.setdefault(lugar, {}).setdefault(chave, []).append(
                (assinatura, valor))


def _a_palavra_do_desenho(alvo: str, por_lugar: dict[int, list[str]]) -> Callable[[int], str]:
    """O que o desenho diz daquele campo num lugar vazio de número `n`."""
    if alvo == "cor":
        return lambda _n: ""
    valores: dict[int, str] = {}
    for n, vs in por_lugar.items():
        if not vs:
            continue
        if len(set(vs)) != 1:
            return lambda _n: ""
        valores[n] = vs[0]
    if len(set(valores.values())) == 1 and (
            len(valores) > 1
            or all(_o_numero_trocado(v, n, n + 1) == v for n, v in valores.items())):
        (unica,) = set(valores.values())
        return lambda _n: unica
    if len(valores) > 1:
        ref = min(valores)
        molde = valores[ref]
        if all(_o_numero_trocado(molde, ref, n) == v for n, v in valores.items()):
            return lambda n: _o_numero_trocado(molde, ref, n)
    return lambda _n: ""


_DESENHO_DO_VAZIO: dict[str, dict[str, dict[str, str]]] = {}


def o_que_o_desenho_diz_do_lugar_vazio(pagina: str) -> dict[str, dict[str, str]]:
    """`{pref: {campo: valor}}` — o lugar vazio do desenho, para os QUATRO lugares."""
    lembrado = _DESENHO_DO_VAZIO.get(pagina)
    if lembrado is None:
        lembrado = _ler_o_lugar_vazio_do_desenho(pagina)
        _DESENHO_DO_VAZIO[pagina] = lembrado
    return {pref: dict(campos) for pref, campos in lembrado.items()}


def _ler_o_lugar_vazio_do_desenho(pagina: str) -> dict[str, dict[str, str]]:
    from hefesto_dualsense4unix.interface import onde

    try:
        doc = onde.pagina(pagina, publicado=True).read_text(encoding="utf-8")
    except OSError:
        return {}
    olho = _OLugarNoDesenho(doc)
    olho.feed(doc)
    olho.close()
    if not olho.vazios:
        return {}
    assinaturas: dict[str, set[tuple[str, str]]] = {}
    for campos in olho.campos.values():
        for chave, ocorrencias in campos.items():
            assinaturas.setdefault(chave, set()).update(a for a, _ in ocorrencias)
    fora: dict[str, dict[str, str]] = {pref: {} for pref in sorted(TODOS_OS_LUGARES)}
    for chave, sinais in sorted(assinaturas.items()):
        if len(sinais) != 1:
            continue
        ((alvo, _nome),) = sinais
        if alvo not in ALVOS_QUE_O_DESENHO_DIZ:
            continue
        palavra = _a_palavra_do_desenho(alvo, {
            int(pref[1:]): [v for _, v in olho.campos.get(pref, {}).get(chave, [])]
            for pref in olho.vazios})
        for pref in fora:
            fora[pref][chave] = palavra(int(pref[1:]))
    return fora


def chaves_por_controle(pacote: dict[str, Any]) -> set[str]:
    """Os campos que este pacote emite POR CONTROLE, nas três palavras."""
    fora: set[str] = set()
    for nome in POR_CONTROLE:
        for campos in (pacote.get(nome) or {}).values():
            if not isinstance(campos, dict):
                continue
            fora |= {str(k) for k, v in campos.items()
                     if not isinstance(v, (dict, list))}
    return fora


def molde_do_lugar(
    pagina: str, ctx: Contexto, pacote: dict[str, Any] | None = None
) -> dict[str, str]:
    """Quais campos um lugar de controle desta aba tem, todos no travessão."""
    if ctx.conectados:
        return {}
    pacote = pacote if pacote is not None else {}
    if chaves_por_controle(pacote):
        return {}
    fn = PACOTES.get(pagina)
    if fn is None:
        return {}
    if not lugares_da_pagina(pagina):
        return {}
    chave = _chave_do_molde(pagina, ctx)
    lembrado = _MOLDE.get(chave)
    if lembrado is not None and chave in _PINTA:
        return dict(lembrado)
    alvos = alvos_da_pagina(pagina)
    if not alvos:
        return {}
    fantasma = Contexto(
        state=ctx.state, mesa=[dict(_LUGAR_DE_MENTIRA)],
        conectados=[dict(_CONTROLE_DE_MENTIRA)], estados=dict(ctx.estados))
    try:
        seria = fn(fantasma)
    except Exception:
        seria = {}
    apaga = enderecos_que_o_texto_apaga(pagina)
    molde = dict.fromkeys(
        sorted(k for k in chaves_por_controle(seria)
               if not (alvos.get(k, set()) & ALVOS_QUE_O_TRAVESSAO_NAO_ATENDE)
               and k not in apaga),
        TRAVESSAO)
    _MOLDE[chave] = molde
    _PINTA[chave] = frozenset(chaves_por_controle(seria))
    return dict(molde)


def topo(ctx: Contexto) -> dict[str, Any]:
    """Os três valores do CABEÇALHO, que são iguais nas dez abas.

    A contagem de controles e o nome do perfil ativo vivem no `topo.html`, que é
    um só para as dez páginas — logo não pertencem a pacote nenhum. Medido em
    01/09/2026: `conta`, `conta-b` e `perfil` apareciam como campos VAZIOS em
    todas as abas, porque cada função de pacote cuidava da sua aba e ninguém
    cuidava do que era de todas.

    A contagem sai do `mesa_viva.texto_da_contagem`, que já é dona dela e
    devolve as duas metades separadas — o desenho põe a segunda em `<b>`, e
    escrever a frase inteira num `textContent` apagaria a tag.
    """
    from hefesto_dualsense4unix.interface import mesa_viva

    _, conta_b = mesa_viva.texto_da_contagem(ctx.mesa)
    # costura da ONDA D, 06/09/2026. Aqui estava `ctx.state.get("active_profile")`
    # `perfil.nome_do_ativo` resolve as duas pernas (daemon, depois o marcador em
    from hefesto_dualsense4unix.interface.pacotes import perfil as _perfil

    ativo = _perfil.nome_do_ativo(ctx.state)
    do_rodape = ativo or _o_perfil_do_rodape()
    return {
        # .  # (noqa-acento): dela
        "conta-b": conta_b or SEM_CONTROLE_NA_MESA,
        "perfil": ativo or "—",
        "rodape.salvar": _dica_do_salvar(do_rodape),
        "rodape.exportar": _dica_do_exportar(do_rodape),
    }


_SEM_PERFIL = "no perfil ativo"


_QUANDO_VOLTA = {
    "jogo": "o que você salvar aqui volta sozinho toda vez que este jogo abrir.",
    "any": "vale fora do jogo e em todo jogo sem perfil próprio.",
    "manual": "vale quando você escolher este perfil.",
}


def _tipo_do_perfil(nome: str) -> str:
    """`jogo`, `any`, `manual` ou `""` — o `match` do disco, lido cru."""
    from hefesto_dualsense4unix.interface.pacotes import perfil as _perfil

    try:
        cru = _perfil.ativo(nome) if nome else {}
        casamento = cru.get("match") if cru else None
    except Exception:
        return ""
    if not isinstance(casamento, dict):
        return ""
    tipo = casamento.get("type", "criteria")
    if tipo == "criteria":
        regra = ("window_class", "window_title_regex", "process_name")
        return "jogo" if any(casamento.get(k) for k in regra) else "manual"
    return tipo if tipo in _QUANDO_VOLTA else ""


def _dica_do_salvar(ativo: str) -> str:
    """A dica do botão que GRAVA, com o nome do perfil que vai receber."""
    onde = f"no perfil {ativo}" if ativo else _SEM_PERFIL
    quando = _QUANDO_VOLTA.get(_tipo_do_perfil(ativo), "")
    if not quando:
        return f"Grava {onde}. É onde a mudança vai cair."
    return f"Grava {onde}. É onde a mudança vai cair: {quando}"


def _o_perfil_do_rodape() -> str:
    """O perfil dos gestos do rodapé sem perfil ativo — do dono."""
    from hefesto_dualsense4unix.interface.pacotes.rodape import perfil_do_rodape

    return perfil_do_rodape({})


def _dica_do_exportar(ativo: str) -> str:
    """A dica do botão que leva o perfil para um arquivo, com o nome certo."""
    qual = f"o perfil {ativo}" if ativo else "o perfil ativo"
    return (f"Escreve {qual} num arquivo .json, para guardar ou levar para "
            "outra máquina.")


#     player_slot            6     1   <- a assinatura: `jogador_de`


def jogador_de(c: dict[str, Any]) -> int | None:
    """Que jogador é este controle — o NÚMERO que a tela mostra, ou ``None``.

    O daemon publica DUAS chaves: ``player_slot`` (a posição de sessão, que o
    PRODUTO decide e que sobrevive a desconectar e reconectar) e ``player`` (o
    número do jogador que o JOGO vê). A GTK sempre leu a primeira para o número
    do card (``app/actions/base.numero_do_controle``); o HTML lia só a segunda.

    **CORREÇÃO DE FATO, medida em 02/09/2026 com os dois controles na mesa.** O
    MAPA e a ROTA-C diziam *"no rádio o `player` volta None"*. **Não é o
    transporte.** O que se mediu foi:

        uniq 444648000003 · bt  · player 1    · player_slot 1 · is_primary TRUE
        uniq d42f4b0000d8 · usb · player None · player_slot 2 · is_primary false

    O ``None`` está no controle do CABO. A condição real está escrita em
    ``daemon/subsystems/coop.CoopManager.player_indexes``: *"Só entra quem o
    jogo enxerga: um secundário ainda aguardando o grab não tem vpad —
    reservou o índice, mas não é jogador nenhum até ser promovido."* Confirmado
    no estado vivo: ``coop.enabled=true``, ``coop.players=1``, e a ``coop.mesa``
    tem UMA entrada — a do primário. **Quem volta ``None`` é quem não é jogador
    do co-op**, em qualquer transporte. Com o co-op DESLIGADO
    (``resolve_player_numbers``) todos os conectados são o jogador 1.

    **A ORDEM DAS CHAVES É A DA GTK** — ``player_slot`` primeiro. A régua
    ``test_os_donos_de_fato.py`` confere isso contra ``base.numero_do_controle``
    e reprova se aquela função deixar de ler ``player_slot`` na frente: as duas
    têm de mudar no mesmo commit.

    **O QUE ESTA FUNÇÃO NÃO HERDA DA GTK, e é deliberado:** o
    ``numero_do_controle`` cai em ``index + 1`` quando não há slot, e daí em 1.
    Isso é a POSIÇÃO — exatamente o que fez o mesmo controle mudar de nome
    quando o segundo entrou na mesa. Aqui a resposta é ``None``, e ``None`` vira
    travessão. Melhor calar que numerar por ordem de chegada.
    """
    for chave in ("player_slot", "player"):
        valor = c.get(chave)
        if valor is None:
            continue
        try:
            n = int(valor)
        except (TypeError, ValueError):
            continue
        if n > 0:
            return n
    return None


#: string; a régua `test_os_donos_de_fato.py` confere que as duas são a MESMA.
NOME_SEM_LEITURA = "Não sei"

#: `mesa_viva.mesa_do_estado`", que era `"USB" if transporte == "usb" else
#: `via` é a chave que `mesa_viva.mesa_do_estado` publica, e ela é COMPARADA em
VIA_DO_TRANSPORTE = {"usb": "USB", "bt": "BT"}


def identidade_de(
    c: dict[str, Any], mesa: list[dict[str, Any]] | None = None
) -> str:
    """O nome deste controle na tela, ou o travessão."""
    declarado = c.get("nome_declarado")
    if isinstance(declarado, str) and declarado.strip():
        return declarado.strip()

    modelo = c.get("modelo")
    if isinstance(modelo, str) and modelo.strip():
        return modelo.strip()

    uniq = str(c.get("uniq") or "")
    for item in mesa or []:
        if str(item.get("uniq") or "") != uniq:
            continue
        nome = item.get("nome")
        if isinstance(nome, str) and nome.strip() and nome.strip() != NOME_SEM_LEITURA:
            return nome.strip()
        break

    # A PALAVRA VEM DO DONO — costura da ONDA B, 06/09/2026. `VIA_DO_TRANSPORTE`
    from hefesto_dualsense4unix.app.actions.home_actions import (
        palavra_do_transporte,
    )

    if not str(c.get("transport") or "").strip():
        return "—"
    return palavra_do_transporte(c.get("transport")) or "—"


def normalizar(pacote: dict[str, Any], para_pref: dict[str, str] | None = None) -> dict[str, Any]:
    """O pacote na forma que a tela consome: `{mesa, colunas, blocos}`."""
    para_pref = para_pref or {}
    colunas: dict[str, dict[str, Any]] = {}
    for nome in POR_CONTROLE:
        for chave, valores in (pacote.get(nome) or {}).items():
            if not isinstance(valores, dict):
                continue
            pref = para_pref.get(chave) or para_pref.get(_so_hex(chave)) or chave
            colunas.setdefault(pref, {}).update(valores)

    mesa = dict(pacote.get("mesa") or {})
    for chave, valor in pacote.items():
        if chave in NAO_SAO_VALOR or chave in POR_CONTROLE or chave == "mesa":
            continue
        if isinstance(valor, list):
            if all(not isinstance(x, (dict, list)) for x in valor):
                mesa.setdefault(chave, valor)
            continue
        if isinstance(valor, dict):
            continue
        mesa.setdefault(chave, valor)
    fora: dict[str, Any] = {"mesa": mesa, "colunas": colunas}
    blocos = pacote.get("blocos")
    if isinstance(blocos, dict) and blocos:
        fora["blocos"] = blocos
    vazio = pacote.get(LUGAR_VAZIO)
    if isinstance(vazio, dict) and vazio:
        fora[LUGAR_VAZIO] = {str(k): v for k, v in vazio.items()
                             if not isinstance(v, (dict, list))}
    marcas = pacote.get(MARCAS_DO_LUGAR)
    if isinstance(marcas, dict):
        fora[MARCAS_DO_LUGAR] = {
            str(classe): sorted({para_pref.get(str(u)) or para_pref.get(_so_hex(str(u)))
                                 or str(u) for u in (lugares or [])})
            for classe, lugares in marcas.items()}
    campos = pacote.get(CAMPOS_DO_LUGAR)
    if isinstance(campos, (list, tuple, set, frozenset)) and campos:
        fora[CAMPOS_DO_LUGAR] = sorted(str(k) for k in campos)
    return fora


def _so_hex(chave: str) -> str:
    """`d42f4b0000d8` → o mesmo, e `d4:2f:00:00:…` → `d42f…`. Uma forma só para casar."""
    return chave.replace(":", "").lower()


#: `portao_a_casa_sabe_e_o_produto_nao_faz` segue o fecho de import lendo o
#: de tela que eles chamam (`app/telas/vibracao.py`, `interface/sistema.py`,
from . import (  # noqa: E402
    a01_jogar,  # noqa: F401
    a02_controles,  # noqa: F401
    a03_gatilhos,  # noqa: F401
    a04_iluminacao,  # noqa: F401
    a05_vibracao,  # noqa: F401
    a06_navegacao,  # noqa: F401
    a07_lancadores,  # noqa: F401
    a08_conexoes,  # noqa: F401
    a09_sistema,  # noqa: F401
    a10_perfis,  # noqa: F401
    # do `portao_a_casa_sabe_e_o_produto_nao_faz` lê o AST, e um nome montado
    a11_calibrar_sensores,  # noqa: F401
    a12_mapa_das_portas,  # noqa: F401
    a13_mapa_do_controle,  # noqa: F401
    camada,  # noqa: F401
    rodape,  # noqa: F401
)


def _carregar_tudo() -> None:
    """Importa os módulos de pacote, que é o que os registra."""
    import importlib
    aqui = pathlib.Path(__file__).resolve().parent
    for f in sorted(aqui.glob("a[0-9][0-9]_*.py")):
        importlib.import_module(f"{__name__}.{f.stem}")
    importlib.import_module(f"{__name__}.rodape")
    importlib.import_module(f"{__name__}.camada")


_carregar_tudo()

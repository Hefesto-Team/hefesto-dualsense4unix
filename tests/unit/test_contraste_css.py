"""Contraste WCAG dos PARES texto x fundo do `theme.css`.

Contraste é propriedade de PAR, e o projeto não tinha teste de par nenhum:

* `test_color_contrast.py` não lê o CSS — ele afere um auxiliar de runtime que
  corrige cores de lightbar vindas do IPC, com piso `3.0` (a régua de
  NÃO-texto). Nenhum par do tema passa por lá.
* `test_paleta_unica.py` valida o CONJUNTO: exige que todo hex pertença às 26
  cores oficiais. `color: @comment` sobre `background-color: @chrome` é 100%
  aprovado por ele — as duas cores são da paleta. **É possível reprovar WCAG
  usando exclusivamente cores aprovadas**, e era o que acontecia em dez lugares.

Este arquivo fecha esse furo. Ele extrai os tokens `@define-color`, monta os
pares texto x fundo que a interface realmente produz e exige 4,5:1 (3,0:1 para
texto grande, na definição do WCAG 1.4.3: >= 18,66px, ou >= 14px em negrito).

## Como o par é montado

O CSS diz a cor do texto; quem diz o FUNDO é a árvore de widgets, que o CSS
sozinho não conhece. As três regras abaixo cobrem os casos reais sem inventar
hierarquia:

1. **Fundo próprio.** O bloco declara `background-color`: o par é com a cor
   daquele mesmo bloco. Quando o bloco não declara `color`, a cor vem do bloco
   irmão sem a pseudo-classe (`button:hover` herda o `color` de `button`) e, em
   último caso, de `@fg` — o texto padrão da janela.
2. **`<seletor> label`.** Um `GtkLabel` dentro de um widget pintado casa com o
   fundo DAQUELE widget (`button.btn-apply label` x o verde do botão). É o
   caminho que o BUG-GUI-FOOTER-LABEL-BRANCO-01 tornou obrigatório: a cor do
   texto dos botões do rodapé só chega pelo seletor que casa o label.
3. **Texto solto.** Sem fundo próprio e sem pai pintado, o rótulo pode cair em
   qualquer uma das três superfícies que CONTÊM texto corrente — a janela
   (`@app_bg`), o cromo (`@chrome`) e o card (`@bg`) — e precisa passar nas
   três. `@elevated` fica fora de propósito: é superfície de CONTROLE (trilha
   de slider, cabeçalho de tabela, corpo de botão), e todo texto que cai nela
   chega por uma regra com fundo próprio, coberta pelo caso 1.

`CONTEXTOS` restringe o caso 3 aos poucos seletores cujo fundo é ÚNICO e
demonstrável — cada entrada diz onde a prova está.

Nós que não pintam texto (trilha, cursor, seta, marcador de check) ficam de
fora: `check:checked` pinta `color: @app_bg` sobre roxo, mas isso é o desenho
do "visto", não uma letra.

Estado `:disabled` fica isento do piso pelo próprio WCAG 1.4.3 ("Incidental:
texto que é parte de um componente de interface INATIVO não tem requisito de
contraste") — o que não impede o tema de melhorá-lo, e ele melhorou.
"""
from __future__ import annotations

import re
from pathlib import Path

CSS_PATH = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "hefesto_dualsense4unix"
    / "gui"
    / "theme.css"
)

#: Pisos do WCAG 2.1 nível AA para contraste de texto.
PISO_TEXTO_NORMAL = 4.5
PISO_TEXTO_GRANDE = 3.0

#: Tamanho que o texto SEM regra de `font-size` recebe. `gtk-font-name` é
#: definido sem número, então o Pango entrega o padrão dele — 10pt a 96 dpi =
#: 13,33px. É o tamanho de ~90% da janela, e é por isso que ele é o default
#: aqui em vez de um dos degraus da escala tipográfica.
PX_HERDADO = 13.33

#: Fronteiras de "texto grande" do WCAG 1.4.3 (em px, a 96 dpi).
PX_GRANDE = 18.66
PX_GRANDE_NEGRITO = 14.0
PESO_NEGRITO = 700

#: Cor do texto quando nenhuma regra manda: `.hefesto-dualsense4unix-window`
#: (e o `label` escopado nela) pintam tudo de `@fg`.
COR_HERDADA = "@fg"

#: As superfícies que CONTÊM texto corrente — o caso 3 do cabeçalho.
SUPERFICIES_DE_TEXTO = ("@app_bg", "@chrome", "@bg")

#: Nós GTK que desenham forma, não letra. Uma regra cujo último nó é um destes
#: nunca produz par de texto.
NOS_SEM_TEXTO = frozenset(
    {
        "trough",
        "progress",
        "highlight",
        "fill",
        "slider",
        "arrow",
        "separator",
        "check",
        "radio",
        "switch",
        "decoration",
        "border",
        "undershoot",
        "scrollbar",
    }
)

#: Seletores cujo fundo é ÚNICO e demonstrável — cada um com a prova.
CONTEXTOS: dict[str, tuple[str, str]] = {
    # O único uso da classe é o `app_subtitle` do glade, filho direto do
    # `header_bar`, que carrega `.hefesto-barra-titulo` (fundo @chrome).
    ".hefesto-dualsense4unix-window label.hefesto-subtitulo": (
        "@chrome",
        "subtítulo do cabeçalho (glade: dentro de box.hefesto-barra-titulo)",
    ),
    # A tira de abas é @chrome por regra deste mesmo arquivo, e o `tab` é
    # filho obrigatório do `header`.
    ".hefesto-dualsense4unix-window notebook > header > tabs > tab": (
        "@chrome",
        "aba do notebook (o próprio CSS pinta notebook > header de @chrome)",
    ),
    ".hefesto-dualsense4unix-window notebook > header > tabs > tab:checked": (
        "@chrome",
        "aba ativa (mesma tira @chrome)",
    ),
    ".hefesto-dualsense4unix-window notebook > header > tabs > tab:hover": (
        "@chrome",
        "aba sob o mouse (mesma tira @chrome)",
    ),
    # O GtkStatusbar do rodapé está dentro do box `.hefesto-rodape` (@chrome).
    ".hefesto-dualsense4unix-window statusbar": (
        "@chrome",
        "nota do rodapé (glade: dentro de box.hefesto-rodape)",
    ),
    ".hefesto-dualsense4unix-window statusbar label": (
        "@chrome",
        "nota do rodapé (glade: dentro de box.hefesto-rodape)",
    ),
    # O nó `text` do GtkProgressBar é IRMÃO de `progress` e mora sobre a
    # trilha, que este arquivo pinta de @elevated.
    ".hefesto-dualsense4unix-window progressbar text": (
        "@elevated",
        "porcentagem da bateria (o nó text fica sobre a trilha @elevated)",
    ),
    ".hefesto-dualsense4unix-window progressbar > text": (
        "@elevated",
        "porcentagem da bateria (o nó text fica sobre a trilha @elevated)",
    ),
}

_COMENTARIO = re.compile(r"/\*.*?\*/", re.DOTALL)
_DEFINE = re.compile(r"@define-color\s+(\w+)\s+(#[0-9a-fA-F]{3,8})\s*;")
_REGRA = re.compile(r"([^{}]+)\{([^{}]*)\}")
#: Pseudo-classes/estados que o GTK empilha no fim de um seletor simples.
_PSEUDO = re.compile(r":[a-z-]+$")


def _sem_comentarios(css: str) -> str:
    """Tira comentários preservando a contagem de linhas (para o relato)."""
    return _COMENTARIO.sub(lambda m: "\n" * m.group(0).count("\n"), css)


def _tokens(css: str) -> dict[str, str]:
    return {f"@{nome}": hexa.lower() for nome, hexa in _DEFINE.findall(css)}


def _expandir(valor: str) -> str:
    return " ".join(valor.split())


class Regra:
    """Um bloco do CSS já normalizado: seletores + declarações + linha."""

    def __init__(self, seletores: list[str], decls: dict[str, str], linha: int):
        self.seletores = seletores
        self.decls = decls
        self.linha = linha


def _carregar() -> tuple[dict[str, str], list[Regra]]:
    css = _sem_comentarios(CSS_PATH.read_text(encoding="utf-8"))
    tokens = _tokens(css)
    corpo = _DEFINE.sub("", css)
    linhas_ate = [0]
    for linha in corpo.split("\n"):
        linhas_ate.append(linhas_ate[-1] + len(linha) + 1)

    def _linha_de(pos: int) -> int:
        for i, limite in enumerate(linhas_ate):
            if limite > pos:
                return i
        return len(linhas_ate)

    regras: list[Regra] = []
    for m in _REGRA.finditer(corpo):
        seletores = [_expandir(s) for s in m.group(1).split(",") if s.strip()]
        decls: dict[str, str] = {}
        for pedaco in m.group(2).split(";"):
            if ":" not in pedaco:
                continue
            chave, valor = pedaco.split(":", 1)
            decls[chave.strip()] = _expandir(valor)
        if seletores and decls:
            # A linha do PRIMEIRO caractere do seletor: `m.start()` cai no fim
            # do bloco anterior e reportaria a linha de cima.
            bruto = m.group(1)
            inicio = m.start(1) + (len(bruto) - len(bruto.lstrip()))
            regras.append(Regra(seletores, decls, _linha_de(inicio)))
    return tokens, regras


TOKENS, REGRAS = _carregar()


# ---------------------------------------------------------------------------
# WCAG 2.1 — luminância relativa e razão de contraste
# ---------------------------------------------------------------------------


def _para_rgb(valor: str) -> tuple[int, int, int] | None:
    """`@token` ou `#rgb`/`#rrggbb` -> canais 0-255; None se não for cor."""
    texto = valor.strip().lower()
    if texto.startswith("@"):
        texto = TOKENS.get(texto, "")
    if not texto.startswith("#"):
        return None
    corpo = texto[1:]
    if len(corpo) == 3:
        corpo = "".join(c * 2 for c in corpo)
    if len(corpo) != 6:
        return None
    return (int(corpo[0:2], 16), int(corpo[2:4], 16), int(corpo[4:6], 16))


def luminancia(rgb: tuple[int, int, int]) -> float:
    """Luminância relativa do WCAG 2.1 (fórmula 1.4.3)."""
    canais = []
    for bruto in rgb:
        c = bruto / 255
        canais.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * canais[0] + 0.7152 * canais[1] + 0.0722 * canais[2]


def razao(frente: str, fundo: str) -> float | None:
    """Razão de contraste entre duas cores; None se alguma não for cor."""
    a, b = _para_rgb(frente), _para_rgb(fundo)
    if a is None or b is None:
        return None
    la, lb = luminancia(a), luminancia(b)
    claro, escuro = max(la, lb), min(la, lb)
    return (claro + 0.05) / (escuro + 0.05)


# ---------------------------------------------------------------------------
# Montagem dos pares
# ---------------------------------------------------------------------------


def _partes(seletor: str) -> list[str]:
    """Seletor em pedaços simples, sem os combinadores `>` e `+`."""
    return [p for p in seletor.split(" ") if p not in (">", "+", "~")]


def _no_final(seletor: str) -> str:
    """Nome do NÓ (elemento GTK) do último seletor simples, sem classes."""
    partes = _partes(seletor)
    if not partes:
        return ""
    ultimo = _PSEUDO.sub("", partes[-1])
    while _PSEUDO.search(ultimo):
        ultimo = _PSEUDO.sub("", ultimo)
    return ultimo.split(".")[0].split(":")[0]


def _pai(seletor: str) -> str:
    """Seletor do PAI: o mesmo sem o último seletor simples nem combinador."""
    fatias = seletor.split(" ")
    while fatias and fatias[-1] in (">", "+", "~"):
        fatias.pop()
    if fatias:
        fatias.pop()
    while fatias and fatias[-1] in (">", "+", "~"):
        fatias.pop()
    return " ".join(fatias)


def _indice(propriedade: str) -> dict[str, tuple[str, Regra]]:
    """Mapa seletor -> (valor, regra) para uma propriedade."""
    tabela: dict[str, tuple[str, Regra]] = {}
    for regra in REGRAS:
        valor = regra.decls.get(propriedade)
        if valor is None:
            continue
        for seletor in regra.seletores:
            tabela[seletor] = (valor, regra)
    return tabela


FUNDOS = _indice("background-color")
CORES = _indice("color")
TAMANHOS = _indice("font-size")
PESOS = _indice("font-weight")


def _sem_pseudo(seletor: str) -> str:
    """Tira as pseudo-classes do ÚLTIMO seletor simples (`btn:hover` -> `btn`)."""
    fatias = seletor.split(" ")
    if not fatias:
        return seletor
    alvo = fatias[-1]
    while _PSEUDO.search(alvo):
        alvo = _PSEUDO.sub("", alvo)
    fatias[-1] = alvo
    return " ".join(fatias)


def _buscar(tabela: dict[str, tuple[str, Regra]], seletor: str) -> str | None:
    """Valor declarado para o seletor, ou para ele sem as pseudo-classes."""
    achado = tabela.get(seletor)
    if achado is not None:
        return achado[0]
    base = _sem_pseudo(seletor)
    if base != seletor:
        achado = tabela.get(base)
        if achado is not None:
            return achado[0]
    return None


def _cor_efetiva(seletor: str) -> str:
    return _buscar(CORES, seletor) or COR_HERDADA


def _tamanho_efetivo(seletor: str) -> tuple[float, int]:
    """`(px, peso)` do texto daquele seletor."""
    px_txt = _buscar(TAMANHOS, seletor)
    if px_txt is None:
        # A escala tipográfica mora em classes próprias: se o seletor carrega
        # uma delas, o tamanho vem de lá.
        for parte in _partes(seletor):
            for classe in parte.split(".")[1:]:
                declarado = _buscar(TAMANHOS, f".{classe}")
                if declarado is not None:
                    px_txt = declarado
                    break
    px = float(px_txt.replace("px", "")) if px_txt else PX_HERDADO
    peso_txt = _buscar(PESOS, seletor) or "400"
    peso = PESO_NEGRITO if peso_txt == "bold" else int(peso_txt or 400)
    return px, peso


def _piso(px: float, peso: int) -> float:
    grande = px >= PX_GRANDE or (px >= PX_GRANDE_NEGRITO and peso >= PESO_NEGRITO)
    return PISO_TEXTO_GRANDE if grande else PISO_TEXTO_NORMAL


def _fundos_do_texto(seletor: str) -> list[tuple[str, str]]:
    """`[(fundo, motivo)]` — as superfícies contra as quais medir o texto."""
    contexto = CONTEXTOS.get(seletor)
    if contexto is not None:
        return [(contexto[0], contexto[1])]

    partes = _partes(seletor)
    if partes and _PSEUDO.sub("", partes[-1]) == "label":
        # Caso 2: um GtkLabel dentro de um widget pintado casa com o fundo
        # DAQUELE widget. A raiz não conta como widget pintado — sobre ela o
        # rótulo pode estar dentro de qualquer card.
        pai = _pai(seletor)
        while pai:
            fundo = _buscar(FUNDOS, pai)
            if fundo is not None and fundo != "transparent":
                if pai.strip(". ") != "hefesto-dualsense4unix-window":
                    return [(fundo, f"label dentro de `{pai}`")]
                break
            pai = _pai(pai)

    return [(s, "texto solto: cai em qualquer superfície") for s in SUPERFICIES_DE_TEXTO]


class Par:
    """Um par texto x fundo pronto para medir."""

    def __init__(
        self,
        seletor: str,
        linha: int,
        frente: str,
        fundo: str,
        motivo: str,
        px: float,
        peso: int,
    ) -> None:
        self.seletor = seletor
        self.linha = linha
        self.frente = frente
        self.fundo = fundo
        self.motivo = motivo
        self.px = px
        self.peso = peso

    @property
    def isento(self) -> bool:
        """WCAG 1.4.3 dispensa componente INATIVO do piso de contraste."""
        return ":disabled" in self.seletor

    def __str__(self) -> str:
        return (
            f"theme.css:{self.linha} `{self.seletor}` — "
            f"{self.frente} sobre {self.fundo} ({self.motivo}, {self.px:g}px)"
        )


def pares() -> list[Par]:
    """Todos os pares texto x fundo que o tema produz."""
    achados: list[Par] = []
    for regra in REGRAS:
        for seletor in regra.seletores:
            if _no_final(seletor) in NOS_SEM_TEXTO:
                continue
            px, peso = _tamanho_efetivo(seletor)
            fundo_proprio = regra.decls.get("background-color")
            if fundo_proprio is not None and fundo_proprio != "transparent":
                achados.append(
                    Par(
                        seletor,
                        regra.linha,
                        _cor_efetiva(seletor),
                        fundo_proprio,
                        "fundo do próprio bloco",
                        px,
                        peso,
                    )
                )
                continue
            cor = regra.decls.get("color")
            if cor is None:
                continue
            for fundo, motivo in _fundos_do_texto(seletor):
                achados.append(
                    Par(seletor, regra.linha, cor, fundo, motivo, px, peso)
                )
    return achados


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------


def test_todo_token_referenciado_existe() -> None:
    """`@token` desconhecido DERRUBA A CARGA DO ARQUIVO INTEIRO no GTK3.

    O projeto já tropeçou duas vezes no mesmo mecanismo com at-rules
    (`theme.css:105` e `:805`): o parser trata o token que não conhece como
    erro de sintaxe e desiste do CSS todo — a janela abre com o tema do
    sistema, clara, e nada no log diz qual linha era.
    """
    conhecidos = set(TOKENS)
    orfaos: dict[str, set[str]] = {}
    for regra in REGRAS:
        for valor in regra.decls.values():
            for referencia in re.findall(r"@[a-z_]+", valor):
                if referencia not in conhecidos:
                    orfaos.setdefault(str(regra.linha), set()).add(referencia)

    assert not orfaos, (
        "tokens referenciados e nunca declarados (o GTK3 descarta o CSS "
        f"inteiro por causa deles): {sorted(orfaos.items())}"
    )


def test_todo_par_texto_fundo_passa_no_wcag_aa() -> None:
    """Nenhum par texto x fundo abaixo de 4,5:1 (3,0:1 para texto grande)."""
    reprovados: list[str] = []
    for par in pares():
        if par.isento:
            continue
        medida = razao(par.frente, par.fundo)
        if medida is None:
            continue
        piso = _piso(par.px, par.peso)
        if medida < piso:
            reprovados.append(f"{medida:.2f}:1 (piso {piso}) — {par}")

    assert not reprovados, (
        "pares texto x fundo abaixo do piso WCAG AA:\n  "
        + "\n  ".join(sorted(reprovados))
    )


def test_a_paleta_tem_par_legivel_para_cada_superficie() -> None:
    """Cada superfície de texto precisa de um degrau apagado que se leia nela.

    O achado que motivou a sprint: `@comment` (#6272a4) é cor de BORDA, não de
    texto — ele reprova sobre TODAS as superfícies do aplicativo. E `@text_muted`
    passa sobre a janela e o cromo, mas NÃO sobre o card: dentro de card o
    degrau apagado tem de ser `@text_soft`. Este teste trava as duas conclusões
    para que a próxima edição não as desfaça sem perceber.
    """
    for superficie in SUPERFICIES_DE_TEXTO:
        medida = razao("@comment", superficie)
        assert medida is not None and medida < PISO_TEXTO_NORMAL, (
            f"@comment passou a se ler sobre {superficie} ({medida}): se o "
            "token mudou de valor, revise onde ele volta a servir de texto"
        )
    no_card = razao("@text_muted", "@bg")
    assert no_card is not None and no_card < PISO_TEXTO_NORMAL, (
        f"@text_muted sobre @bg agora dá {no_card}:1 — a regra 'dentro de card "
        "o apagado é @text_soft' pode ser revista"
    )
    for superficie in SUPERFICIES_DE_TEXTO:
        medida = razao("@text_soft", superficie)
        assert medida is not None and medida >= PISO_TEXTO_NORMAL, (
            f"@text_soft reprovou sobre {superficie} ({medida}) — o degrau "
            "apagado do card ficou sem cor legível"
        )

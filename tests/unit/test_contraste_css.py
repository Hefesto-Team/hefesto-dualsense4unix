"""Contraste WCAG dos PARES texto x fundo do `theme.css`."""
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

PISO_TEXTO_NORMAL = 4.5
PISO_TEXTO_GRANDE = 3.0

PX_HERDADO = 13.33

PX_GRANDE = 18.66
PX_GRANDE_NEGRITO = 14.0
PESO_NEGRITO = 700

COR_HERDADA = "@fg"

SUPERFICIES_DE_TEXTO = ("@app_bg", "@chrome", "@bg")

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

CONTEXTOS: dict[str, tuple[str, str]] = {
    ".hefesto-dualsense4unix-window label.hefesto-subtitulo": (
        "@chrome",
        "subtítulo do cabeçalho (glade: dentro de box.hefesto-barra-titulo)",
    ),
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
    ".hefesto-dualsense4unix-window statusbar": (
        "@chrome",
        "nota do rodapé (glade: dentro de box.hefesto-rodape)",
    ),
    ".hefesto-dualsense4unix-window statusbar label": (
        "@chrome",
        "nota do rodapé (glade: dentro de box.hefesto-rodape)",
    ),
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
            bruto = m.group(1)
            inicio = m.start(1) + (len(bruto) - len(bruto.lstrip()))
            regras.append(Regra(seletores, decls, _linha_de(inicio)))
    return tokens, regras


TOKENS, REGRAS = _carregar()


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


def test_todo_token_referenciado_existe() -> None:
    """`@token` desconhecido DERRUBA A CARGA DO ARQUIVO INTEIRO no GTK3."""
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
    """Cada superfície de texto precisa de um degrau apagado que se leia nela."""
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

"""O tema de cores de uma modificação: troca tokens do ``:root``, e só se o texto continua legível.

O produto põe por cima das páginas publicadas uma folha de usuário (``interface/janela.py``); o
tema é uma segunda folha, depois dela, que só redefine cores. Nada além disso passa:

* a folha é UM bloco ``:root{…}``, sem seletor, sem ``url()``, sem ``@import``: o tema não
  esconde botão nem busca nada fora;
* só os tokens de :data:`TOKENS_DA_CASA` e os das categorias da aba Conexões (``--c-<tipo>`` na
  régua, ``--sala-<tipo>`` na sala); os plásticos (``--cosmic-red``…) ficam fora, porque a
  identidade de cada controle vem do aparelho;
* o valor é uma cor escrita por extenso (``#rrggbb``, ``rgb()``, ``rgba()``), nunca ``var()``;
* cada texto de :data:`TEXTOS` contra cada fundo de :data:`FUNDOS` passa de 4,5:1, o limiar
  medido em 30/08/2026 para texto pequeno. O reprovado não liga, e a frase diz o par e o número.

Os valores da casa são lidos do ``:root`` da página publicada (:data:`PAGINA_DOS_TOKENS`): o tema
que troca só o fundo é medido contra os textos de verdade.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: A página publicada de onde saem os valores da casa (todas as dez têm o mesmo ``:root``).
PAGINA_DOS_TOKENS = (Path(__file__).resolve().parent.parent / "interface"
                     / "paginas"  # (noqa-acento): nome da pasta
                     / "01-jogar.html")

LIMIAR_DO_CONTRASTE = 4.5
#: O tema maior que isto não é um tema de cores.
TAMANHO_MAXIMO = 16 * 1024

TEXTOS = ("--fg", "--texto-suave", "--texto-mudo", "--comment")
FUNDOS = ("--app-bg", "--panel", "--elevated")

#: Os tokens de cor do ``:root`` da casa que um tema pode trocar.
TOKENS_DA_CASA = frozenset({
    *TEXTOS, *FUNDOS, "--border-sutil", "--border-forte", "--cyan", "--green", "--orange",
    "--pink", "--purple", "--red", "--yellow", "--sel-bg", "--rot-campo", "--linha",
    "--rot-linha",
})
#: As categorias da aba Conexões: a cor de cada tipo na régua, na sala e na faixa do mapa.
_TOKEN_DE_CATEGORIA = re.compile(r"--(?:c|sala|mapa)-[a-z][a-z_]{0,23}")
#: Os plásticos: a cor de cada controle é a do aparelho, e tema nenhum a troca.
PLASTICOS = frozenset({"--cosmic-red", "--nova-pink", "--starlight-blue", "--galactic-purple",
                       "--midnight-black"})

_COMENTARIO = re.compile(r"/\*.*?\*/", re.S)
_BLOCO = re.compile(r"\s*:root\s*\{([^{}]*)\}\s*")
_NOME = re.compile(r"--[a-z][a-z0-9_-]*")
_HEX = re.compile(r"#([0-9a-f]{3}|[0-9a-f]{6}|[0-9a-f]{8})")
_RGB = re.compile(r"rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*"
                  r"(?:,\s*(0|1|0?\.\d+|1\.0+)\s*)?\)")
_PROIBIDO = re.compile(r"url\s*\(|@import|\\|<|expression\s*\(", re.I)


class TemaRecusadoError(ValueError):
    """O tema não serve; ``frase`` é a linha que a pessoa lê."""

    def __init__(self, frase: str) -> None:
        super().__init__(frase)
        self.frase = frase


@dataclass(frozen=True)
class TemaAceito:
    """O tema que passou: os tokens e a folha que a janela põe por cima da da casa."""

    tokens: dict[str, str]
    folha: str


@dataclass(frozen=True)
class TemaDaCasa:
    """O tema ligado agora: ``folha`` vazia sem tema; ``recusa`` diz por que o ligado não vale."""

    folha: str = ""
    de: str = ""
    recusa: str = ""
    avisos: tuple[str, ...] = field(default_factory=tuple)


def token_permitido(nome: str) -> bool:
    return nome in TOKENS_DA_CASA or bool(_TOKEN_DE_CATEGORIA.fullmatch(nome))


def cor(valor: str) -> tuple[float, float, float, float] | None:
    """``#rgb``, ``#rrggbb``, ``#rrggbbaa``, ``rgb()`` ou ``rgba()`` em ``(r, g, b, alfa)``."""
    texto = valor.strip().lower()
    m = _HEX.fullmatch(texto)
    if m:
        h = m.group(1)
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        alfa = int(h[6:8], 16) / 255 if len(h) == 8 else 1.0
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), alfa
    m = _RGB.fullmatch(texto)
    if m:
        r, g, b = (int(m.group(i)) for i in (1, 2, 3))
        if max(r, g, b) > 255 or (texto.startswith("rgb(") and m.group(4) is not None):
            return None
        return r, g, b, float(m.group(4)) if m.group(4) is not None else 1.0
    return None


def _luminancia(c: tuple[float, float, float, float]) -> float:
    def canal(v: float) -> float:
        s = v / 255
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4

    return 0.2126 * canal(c[0]) + 0.7152 * canal(c[1]) + 0.0722 * canal(c[2])


def contraste(a: str, b: str) -> float:
    """O contraste WCAG entre duas cores opacas."""
    ca, cb = cor(a), cor(b)
    if ca is None or cb is None:
        raise ValueError(f"cor ilegível: {a!r} ou {b!r}")
    la, lb = sorted((_luminancia(ca), _luminancia(cb)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _numero(razao: float) -> str:
    return f"{razao:.2f}".replace(".", ",") + ":1"


def tokens_da_casa(pagina: Path = PAGINA_DOS_TOKENS) -> dict[str, str]:
    """Os tokens de cor do primeiro ``:root`` da página publicada (o da casa)."""
    saida = tokens_do_root(pagina.read_text(encoding="utf-8"))
    if not saida:
        raise TemaRecusadoError(f"A página {pagina.name} não tem o :root da casa.")
    return saida


def tokens_do_root(texto: str) -> dict[str, str]:
    """Os tokens de cor do primeiro ``:root`` de um texto com CSS (vazio, se não houver)."""
    m = re.search(r":root\s*\{([^{}]*)\}", _COMENTARIO.sub("", texto))
    if m is None:
        return {}
    saida = {}
    for declaracao in m.group(1).split(";"):
        nome, _, valor = declaracao.partition(":")
        if _NOME.fullmatch(nome.strip()) and cor(valor) is not None:
            saida[nome.strip()] = valor.strip().lower()
    return saida


def validar(folha: str, *, casa: dict[str, str] | None = None) -> TemaAceito:
    """Aceita o tema ou o recusa com :class:`TemaRecusadoError` (uma frase para a tela)."""
    if len(folha.encode("utf-8")) > TAMANHO_MAXIMO:
        raise TemaRecusadoError("O tema passa de 16 KB: um tema só troca cores.")
    sem_comentario = _COMENTARIO.sub("", folha)
    if _PROIBIDO.search(sem_comentario):
        raise TemaRecusadoError("O tema não pode buscar nada fora nem usar url(), @import ou "
                                "escape: só cores.")
    bloco = _BLOCO.fullmatch(sem_comentario)
    if bloco is None:
        raise TemaRecusadoError("O tema precisa ser um bloco :root{…} só com cores, sem outro "
                                "seletor.")
    tokens: dict[str, str] = {}
    for declaracao in bloco.group(1).split(";"):
        if not declaracao.strip():
            continue
        nome, dois_pontos, valor = declaracao.partition(":")
        nome = nome.strip()
        valor = re.sub(r"\s*!\s*important\s*$", "", valor.strip(), flags=re.I)
        if not dois_pontos or not _NOME.fullmatch(nome):
            raise TemaRecusadoError(f"O tema tem «{declaracao.strip()}», que não é um token de "
                                    "cor: só cores, nada de layout.")
        if nome in PLASTICOS:
            raise TemaRecusadoError(f"O tema não pode trocar «{nome}»: a cor do plástico vem "
                                    "do controle.")
        if not token_permitido(nome):
            raise TemaRecusadoError(f"O tema não pode trocar «{nome}»: só as cores da "
                                    "interface.")
        if cor(valor) is None:
            raise TemaRecusadoError(f"O valor de «{nome}» não é uma cor (#rrggbb, rgb ou rgba).")
        tokens[nome] = valor.lower()
    if not tokens:
        raise TemaRecusadoError("O tema não troca cor nenhuma.")
    _conferir_o_contraste(tokens, tokens_da_casa() if casa is None else casa)
    folha_final = ":root{" + "".join(f"{k}:{v} !important;" for k, v in tokens.items()) + "}"
    return TemaAceito(tokens=tokens, folha=folha_final)


def _conferir_o_contraste(tokens: dict[str, str], casa: dict[str, str]) -> None:
    valores = {**casa, **tokens}
    for nome in (*TEXTOS, *FUNDOS):
        c = cor(valores.get(nome, ""))
        if c is None:
            raise TemaRecusadoError(f"Não sei a cor de «{nome}» na casa: o tema não liga.")
        if c[3] < 1:
            raise TemaRecusadoError(f"«{nome}» precisa ser uma cor opaca: o contraste do texto "
                                    "se mede sobre ela.")
    # a frase diz o PIOR par: é ele que a pessoa precisa consertar primeiro
    razao, texto, fundo = min((contraste(valores[t], valores[f]), t, f)
                              for t in TEXTOS for f in FUNDOS)
    if razao < LIMIAR_DO_CONTRASTE:
        raise TemaRecusadoError(
            f"O texto ficaria ilegível: «{texto}» sobre «{fundo}» dá {_numero(razao)}, "
            f"e o mínimo é {_numero(LIMIAR_DO_CONTRASTE)}.")


def folha_do_manifesto(bloco: dict[str, Any] | None, pasta: Path) -> str:
    """A folha que o bloco ``tema`` do manifesto declara: ``{"folha": ":root{…}"}`` ou
    ``{"arquivo": "tema.css"}``, um arquivo DENTRO da pasta da modificação."""
    if not isinstance(bloco, dict) or len(bloco) != 1 or not ({"folha", "arquivo"} & set(bloco)):
        raise TemaRecusadoError("O bloco «tema» do manifesto precisa de «folha» ou de «arquivo», "
                                "um dos dois.")
    if "folha" in bloco:
        if not isinstance(bloco["folha"], str):
            raise TemaRecusadoError("A «folha» do tema precisa ser texto.")
        return bloco["folha"]
    nome = bloco["arquivo"]
    if not isinstance(nome, str) or not nome:
        raise TemaRecusadoError("O «arquivo» do tema precisa ser um caminho.")
    raiz = pasta.resolve()
    alvo = (raiz / nome).resolve()
    if alvo == raiz or raiz not in alvo.parents:
        raise TemaRecusadoError("O «arquivo» do tema precisa estar dentro da modificação.")
    try:
        if alvo.stat().st_size > TAMANHO_MAXIMO:
            raise TemaRecusadoError("O tema passa de 16 KB: um tema só troca cores.")
        return alvo.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise TemaRecusadoError(f"O arquivo do tema «{nome}» não pôde ser lido.") from exc


def tema_da_casa(lugares: Any = None) -> TemaDaCasa:
    """O tema da modificação ligada, com a permissão ``tema`` aceita, já conferido.

    Ligada mais de uma com tema, vale a ligada por último; as outras ficam nos avisos. Nada aqui
    escreve: o registro é lido como está.
    """
    from hefesto_dualsense4unix.mods import instalador
    from hefesto_dualsense4unix.mods.manifesto import ManifestoRecusadoError, ler_manifesto

    lg = lugares or instalador.Lugares.do_xdg()
    try:
        registro = instalador.ler_registro(lg.registro)
    except instalador.InstalacaoRecusadaError as exc:
        return TemaDaCasa(recusa=exc.frase)
    candidatos = []
    for entrada in registro.values():
        if not entrada.ligada or "tema" not in entrada.permissoes_aceitas:
            continue
        pasta = lg.codigo / entrada.id
        try:
            manifesto = ler_manifesto(pasta)
        except ManifestoRecusadoError:
            continue
        if "tema" in manifesto.tipos and manifesto.tema is not None:
            candidatos.append((entrada.ligada_em, entrada.id, manifesto, pasta))
    if not candidatos:
        return TemaDaCasa()
    candidatos.sort(key=lambda c: (c[0], c[1]))
    _quando, mod_id, manifesto, pasta = candidatos[-1]
    avisos = tuple(f"«{c[2].nome}» também tem tema, e vale o da «{manifesto.nome}»."
                   for c in candidatos[:-1])
    try:
        aceito = validar(folha_do_manifesto(manifesto.tema, pasta))
    except TemaRecusadoError as exc:
        return TemaDaCasa(de=mod_id, recusa=f"O tema de «{manifesto.nome}» não ligou. {exc.frase}",
                          avisos=avisos)
    return TemaDaCasa(folha=aceito.folha, de=mod_id, avisos=avisos)


__all__ = [
    "FUNDOS",
    "LIMIAR_DO_CONTRASTE",
    "PLASTICOS",
    "TEXTOS",
    "TOKENS_DA_CASA",
    "TemaAceito",
    "TemaDaCasa",
    "TemaRecusadoError",
    "contraste",
    "cor",
    "folha_do_manifesto",
    "tema_da_casa",
    "token_permitido",
    "tokens_da_casa",
    "tokens_do_root",
    "validar",
]

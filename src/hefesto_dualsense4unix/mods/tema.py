"""O tema de uma modificação: troca tokens do ``:root`` (só se o texto continua legível) e escolhe
o lado dos botões da janela.

A folha é UM bloco ``:root{…}`` só com cores por extenso, dos tokens de :data:`TOKENS_DA_CASA` e das
categorias da aba Conexões; os plásticos ficam fora. Texto passa de 4,5:1 e acento de 3:1 contra
cada fundo (``docs/research/o-porque-dos-modulos.md``, «O tema de cores»). O bloco ``tema`` traz a
cor (``folha``/``arquivo``), o lado (``botoes``) ou os dois, cada um ligável a uma opção ``ligado``;
ou os liga a uma ``escolha`` (``folhas_por_escolha``, ``importados_por_escolha``,
``lados_por_escolha``). O destaque (``--green``) passa pela mesma régua; a logo importada é dado
da pessoa e vem de ``mods/importados.py``.
"""
from __future__ import annotations

import re
from collections.abc import Collection, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from hefesto_dualsense4unix.mods import meu_css

PAGINA_DOS_TOKENS = (Path(__file__).resolve().parent.parent / "interface"
                     / "paginas"  # (noqa-acento)
                     / "01-jogar.html")

LADOS_DOS_BOTOES = ("esquerda", "direita")
CHAVES_DA_COR = ("folha", "arquivo")
CHAVE_DO_LADO = "botoes"
CHAVE_DA_OPCAO_DA_COR = "cor_pela_opcao"
CHAVE_DA_OPCAO_DO_LADO = "botoes_pela_opcao"
CHAVE_DAS_FOLHAS = "folhas_por_escolha"
CHAVE_DOS_IMPORTADOS = "importados_por_escolha"
CHAVE_DOS_LADOS = "lados_por_escolha"
CHAVE_DO_DESTAQUE = "destaque_pela_opcao"
CHAVE_DO_DESTAQUE_LIGADO = "destaque_ligado_pela_opcao"
CHAVE_DA_LOGO = "logo_pela_opcao"
CHAVES_DA_ESCOLHA_DA_COR = (CHAVE_DAS_FOLHAS, CHAVE_DOS_IMPORTADOS)
CHAVES_QUE_FAZEM = (*CHAVES_DA_COR, CHAVE_DO_LADO, *CHAVES_DA_ESCOLHA_DA_COR, CHAVE_DOS_LADOS,
                    CHAVE_DO_DESTAQUE, CHAVE_DA_LOGO)
CHAVES_DO_BLOCO = frozenset({*CHAVES_QUE_FAZEM, CHAVE_DA_OPCAO_DA_COR, CHAVE_DA_OPCAO_DO_LADO,
                             CHAVE_DO_DESTAQUE_LIGADO})
TOKEN_DO_DESTAQUE = "--green"

LIMIAR_DO_CONTRASTE = 4.5
TAMANHO_MAXIMO = 16 * 1024

TEXTOS = ("--fg", "--texto-suave", "--texto-mudo", "--comment", "--rot-campo")
FUNDOS = ("--app-bg", "--panel", "--elevated")
FUNDO_DA_PAGINA = "--fundo-da-pagina"
ACENTOS = ("--green", "--cyan", "--purple", "--orange", "--pink", "--red", "--yellow")
LIMIAR_DO_ACENTO = 3.0

TOKENS_DA_CASA = frozenset({
    *TEXTOS, *FUNDOS, *ACENTOS, "--border-sutil", "--border-forte", "--sel-bg", "--linha",
    "--rot-linha", "--logo-aro", FUNDO_DA_PAGINA,
})
FUNDO_DA_LOGO = "--logo-fundo"
_TOKEN_DE_CATEGORIA = re.compile(r"--(?:c|sala|mapa)-[a-z][a-z_]{0,23}")
PLASTICOS = frozenset({"--cosmic-red", "--nova-pink", "--starlight-blue", "--galactic-purple",
                       "--midnight-black"})

_COMENTARIO = re.compile(r"/\*.*?\*/", re.S)
_BLOCO = re.compile(r"\s*:root\s*\{([^{}]*)\}\s*")
_NOME = re.compile(r"--[a-z][a-z0-9_-]*")
_APELIDO = re.compile(r"var\(\s*(--[a-z][a-z0-9_-]*)\s*\)")
_HEX = re.compile(r"#([0-9a-f]{3}|[0-9a-f]{6}|[0-9a-f]{8})")
_RGB = re.compile(r"rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*"
                  r"(?:,\s*(0|1|0?\.\d+|1\.0+)\s*)?\)")
_PROIBIDO = re.compile(r"url\s*\(|@import|\\|<|expression\s*\(", re.I)
_GRADIENTE = re.compile(r"radial-gradient\((.*)\)", re.S)
_FORMA = re.compile(r"(?:circle|ellipse)?\s*(?:at\s+\d{1,3}%\s+\d{1,3}%)?")
_PARADA = re.compile(r"(.+?)(?:\s+\d{1,3}%)?")
_VIRGULA_DE_FORA = re.compile(r",(?![^()]*\))")


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
    """O tema ligado agora: ``folha`` vazia sem tema; ``recusa`` diz por que o ligado não vale.

    ``botoes`` é o lado que a extensão ligada escolhe (``esquerda`` ou ``direita``); vazio deixa o
    lado do sistema. ``css`` é o CSS de quem usa (``meu_css.py``), já pronto para ir por cima da
    ``folha``; ``css_de`` é a extensão dele e ``recusa_do_css`` diz por que não vale.
    """

    folha: str = ""
    de: str = ""
    recusa: str = ""
    avisos: tuple[str, ...] = field(default_factory=tuple)
    botoes: str = ""
    css: str = ""
    css_de: str = ""
    recusa_do_css: str = ""
    recusa_do_destaque: str = ""


def token_permitido(nome: str) -> bool:
    return (nome in TOKENS_DA_CASA or nome == FUNDO_DA_LOGO
            or bool(_TOKEN_DE_CATEGORIA.fullmatch(nome)))


def fundo_da_logo(valor: str) -> bool:
    """``none``, uma cor, ou ``radial-gradient(<forma>, <cor> [N%], <cor> [N%]…)`` só de cores."""
    texto = valor.strip().lower()
    if texto == "none" or cor(texto) is not None:
        return True
    m = _GRADIENTE.fullmatch(texto)
    if m is None:
        return False
    partes = [p.strip() for p in _VIRGULA_DE_FORA.split(m.group(1))]
    primeira = _PARADA.fullmatch(partes[0])
    if primeira is None or cor(primeira.group(1)) is None:
        if not partes[0] or not _FORMA.fullmatch(partes[0]):
            return False
        partes = partes[1:]
    paradas = [_PARADA.fullmatch(p) for p in partes]
    return len(paradas) >= 2 and all(p is not None and cor(p.group(1)) is not None
                                     for p in paradas)


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


def tokens_da_folha(folha: str) -> dict[str, str]:
    """Os tokens de cor de uma folha de tema já aceita (os ``!important`` saem)."""
    return tokens_do_root(re.sub(r"\s*!\s*important", "", folha, flags=re.I))


def e_escuro(tokens: dict[str, str], casa: dict[str, str] | None = None) -> bool:
    """Se o fundo que vale (o ``--app-bg`` do tema, senão o da casa) é escuro.

    Escuro é o fundo em que o branco tem mais contraste que o preto: a mesma conta da régua.
    Sem cor legível, vale o da casa, que é escura.
    """
    fundo = cor(tokens.get("--app-bg", "")) or cor(
        (tokens_da_casa() if casa is None else casa).get("--app-bg", ""))
    if fundo is None:
        return True
    luz = _luminancia(fundo)
    return (1.05 / (luz + 0.05)) > ((luz + 0.05) / 0.05)


def _declaracoes_do_root(texto: str) -> list[tuple[str, str]]:
    m = re.search(r":root\s*\{([^{}]*)\}", _COMENTARIO.sub("", texto))
    if m is None:
        return []
    pares = (declaracao.partition(":") for declaracao in m.group(1).split(";"))
    return [(nome.strip(), valor.strip()) for nome, _, valor in pares
            if _NOME.fullmatch(nome.strip())]


def tokens_do_root(texto: str) -> dict[str, str]:
    """Os tokens de cor do primeiro ``:root`` de um texto com CSS (vazio, se não houver)."""
    return {nome: valor.lower() for nome, valor in _declaracoes_do_root(texto)
            if cor(valor) is not None}


def apelidos_do_root(texto: str) -> dict[str, str]:
    """Os tokens do primeiro ``:root`` que são só ``var(--outro)``, com o token que seguem."""
    saida = {}
    for nome, valor in _declaracoes_do_root(texto):
        m = _APELIDO.fullmatch(valor.lower())
        if m:
            saida[nome] = m.group(1)
    return saida


def apelidos_da_casa(pagina: Path = PAGINA_DOS_TOKENS) -> dict[str, str]:
    """Os apelidos do ``:root`` da página publicada (o ``--rot-campo`` segue o ``--green``)."""
    return apelidos_do_root(pagina.read_text(encoding="utf-8"))


def valores_pintados(casa: dict[str, str], tokens: dict[str, str],
                     apelidos: dict[str, str]) -> dict[str, str]:
    """A cor que cada token pinta com o tema por cima: o apelido que o tema não diz segue o alvo."""
    valores = {**casa, **tokens}
    for _ in range(len(apelidos)):
        soltos = {nome: valores[alvo] for nome, alvo in apelidos.items()
                  if nome not in tokens and alvo in valores and valores.get(nome) != valores[alvo]}
        if not soltos:
            break
        valores.update(soltos)
    return valores


def validar(folha: str, *, casa: dict[str, str] | None = None,
            apelidos: dict[str, str] | None = None) -> TemaAceito:
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
        if nome == FUNDO_DA_LOGO:
            if not fundo_da_logo(valor):
                raise TemaRecusadoError(f"O valor de «{nome}» precisa ser none, uma cor ou um "
                                        "radial-gradient só de cores.")
        elif cor(valor) is None:
            raise TemaRecusadoError(f"O valor de «{nome}» não é uma cor (#rrggbb, rgb ou rgba).")
        tokens[nome] = valor.lower()
    if not tokens:
        raise TemaRecusadoError("O tema não troca cor nenhuma.")
    _conferir_o_contraste(tokens, tokens_da_casa() if casa is None else casa,
                          apelidos_da_casa() if apelidos is None else apelidos)
    return TemaAceito(tokens=tokens, folha=folha_de_tokens(tokens))


def _conferir_o_contraste(tokens: dict[str, str], casa: dict[str, str],
                          apelidos: dict[str, str]) -> None:
    valores = valores_pintados(casa, tokens, apelidos)
    moldura = (FUNDO_DA_PAGINA,) if FUNDO_DA_PAGINA in valores else ()
    for nome in (*TEXTOS, *FUNDOS, *ACENTOS, *moldura):
        c = cor(valores.get(nome, ""))
        if c is None:
            raise TemaRecusadoError(f"Não sei a cor de «{nome}» na casa: o tema não liga.")
        if c[3] < 1:
            raise TemaRecusadoError(f"«{nome}» precisa ser uma cor opaca: o contraste do texto "
                                    "se mede sobre essa cor.")
    for nomes, limiar in ((TEXTOS, LIMIAR_DO_CONTRASTE), (ACENTOS, LIMIAR_DO_ACENTO)):
        razao, texto, fundo = min((contraste(valores[t], valores[f]), t, f)
                                  for t in nomes for f in FUNDOS)
        if razao < limiar:
            raise TemaRecusadoError(
                f"O texto ficaria ilegível: «{texto}» sobre «{fundo}» dá {_numero(razao)}, "
                f"e o mínimo é {_numero(limiar)}.")
    for fundo in moldura:
        razao = contraste(valores["--fg"], valores[fundo])
        if razao < LIMIAR_DO_CONTRASTE:
            raise TemaRecusadoError(
                f"O texto ficaria ilegível: «--fg» sobre «{fundo}» dá {_numero(razao)}, "
                f"e o mínimo é {_numero(LIMIAR_DO_CONTRASTE)}.")


def folha_do_manifesto(bloco: dict[str, Any] | None, pasta: Path) -> str:
    """A folha que o bloco ``tema`` do manifesto declara: ``{"folha": ":root{…}"}`` ou
    ``{"arquivo": "tema.css"}``, um arquivo DENTRO da pasta da modificação. Vazia quando o bloco só
    escolhe o lado dos botões."""
    if not isinstance(bloco, dict):
        raise TemaRecusadoError("O bloco «tema» do manifesto precisa de «folha» ou de «arquivo», "
                                "um dos dois.")
    estranha = sorted(set(bloco) - CHAVES_DO_BLOCO)
    if estranha:
        raise TemaRecusadoError(f"O bloco «tema» do manifesto tem «{estranha[0]}», que este "
                                "Hefesto não conhece.")
    fontes = [c for c in CHAVES_DA_COR if c in bloco]
    if len(fontes) > 1 or not any(c in bloco for c in CHAVES_QUE_FAZEM):
        raise TemaRecusadoError("O bloco «tema» do manifesto precisa de «folha» ou de «arquivo», "
                                "um dos dois.")
    if not fontes:
        return ""
    if "folha" in bloco:
        if not isinstance(bloco["folha"], str):
            raise TemaRecusadoError("A «folha» do tema precisa ser texto.")
        return bloco["folha"]
    return arquivo_da_pasta(bloco["arquivo"], pasta)


def arquivo_da_pasta(nome: object, pasta: Path) -> str:
    """O texto de uma folha do pacote: um arquivo DENTRO da pasta da modificação, até 16 KB."""
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


def conferir_o_bloco(bloco: dict[str, Any] | None, pasta: Path) -> None:
    """A régua do bloco ``tema`` inteiro: a folha, quando há, passa em :func:`validar`.

    O bloco que só escolhe o lado dos botões não tem cor a conferir.
    """
    folha = folha_do_manifesto(bloco, pasta)
    if folha or (bloco and any(c in bloco for c in CHAVES_DA_COR)):
        validar(folha)
    for nome in (bloco or {}).get(CHAVE_DAS_FOLHAS, {}).values():
        validar(arquivo_da_pasta(nome, pasta))


def _opcao_de_tipo(opcoes: Sequence[Any], chave: str, alvo: object, *tipos: str) -> Any:
    opcao = next((o for o in opcoes if o.id == alvo), None)
    if not isinstance(alvo, str) or opcao is None:
        raise ValueError(f"tema.{chave} aponta para a opção {alvo!r}, que não existe")
    if opcao.tipo not in tipos:
        raise ValueError(f"tema.{chave}: a opção {alvo!r} precisa ser do tipo {' ou '.join(tipos)}")
    return opcao


def _mapa_de_escolhas(bloco: dict[str, Any], chave: str, opcao: Any) -> dict[str, Any]:
    mapa = bloco[chave]
    if not isinstance(mapa, dict) or not mapa:
        raise ValueError(f"tema.{chave} é {{escolha: valor}}")
    fora = [e for e in mapa if e not in opcao.escolhas]
    if fora:
        raise ValueError(f"tema.{chave}: «{fora[0]}» não é escolha de {opcao.id!r}")
    return mapa


def conferir_o_bloco_e_as_opcoes(bloco: dict[str, Any] | None, opcoes: Sequence[Any],
                                 tipos: Sequence[str]) -> None:
    """A forma do bloco ``tema`` e o vínculo de cada chave com a opção que a chave lê.

    A cor e o lado se ligam a uma ``ligado`` (vale ou não vale) ou, com ``folhas_por_escolha``,
    ``importados_por_escolha`` e ``lados_por_escolha``, a uma ``escolha`` (cada escolha mapeada
    vale o que o mapa diz; a que não está no mapa deixa o da casa). A folha em si é da régua de
    :func:`validar`, que roda ao instalar e ao ligar.
    """
    importar = [o for o in opcoes if o.tipo == "importar"]
    if importar and "tema" not in tipos:
        raise ValueError(f"a opção {importar[0].id} importa, e só uma extensão de tema importa")
    if not bloco:
        return
    lado = bloco.get(CHAVE_DO_LADO)
    if CHAVE_DO_LADO in bloco and lado not in LADOS_DOS_BOTOES:
        raise ValueError(f"tema.botoes é {' ou '.join(LADOS_DOS_BOTOES)}")
    if CHAVE_DO_LADO in bloco and CHAVE_DOS_LADOS in bloco:
        raise ValueError(f"tema.{CHAVE_DO_LADO} e tema.{CHAVE_DOS_LADOS} não andam juntos")
    if any(c in bloco for c in CHAVES_DA_COR) and any(c in bloco for c in CHAVES_DA_ESCOLHA_DA_COR):
        raise ValueError("tema: a folha vem do arquivo ou das escolhas, não dos dois")
    por_escolha = any(c in bloco for c in CHAVES_DA_ESCOLHA_DA_COR)
    for chave, faz, pela_escolha in (
            (CHAVE_DA_OPCAO_DA_COR, any(c in bloco for c in CHAVES_DA_COR) or por_escolha,
             por_escolha),
            (CHAVE_DA_OPCAO_DO_LADO, CHAVE_DO_LADO in bloco or CHAVE_DOS_LADOS in bloco,
             CHAVE_DOS_LADOS in bloco)):
        if chave not in bloco:
            if pela_escolha:
                raise ValueError(f"tema.{chave}: as escolhas pedem a opção que as escolhe")
            continue
        if not faz:
            raise ValueError(f"tema.{chave} liga uma escolha que o bloco tema não faz")
        opcao = _opcao_de_tipo(opcoes, chave, bloco[chave], "escolha" if pela_escolha else "ligado")
        if chave == CHAVE_DA_OPCAO_DO_LADO and pela_escolha:
            lados = _mapa_de_escolhas(bloco, CHAVE_DOS_LADOS, opcao)
            if any(v not in LADOS_DOS_BOTOES for v in lados.values()):
                raise ValueError(f"tema.{CHAVE_DOS_LADOS} leva a {' ou '.join(LADOS_DOS_BOTOES)}")
        if chave == CHAVE_DA_OPCAO_DA_COR and pela_escolha:
            for mapa in (CHAVES_DA_ESCOLHA_DA_COR):
                if mapa in bloco:
                    _mapa_de_escolhas(bloco, mapa, opcao)
            if set(bloco.get(CHAVE_DAS_FOLHAS, {})) & set(bloco.get(CHAVE_DOS_IMPORTADOS, {})):
                raise ValueError("tema: uma escolha vem do pacote ou do importado, não dos dois")
            for alvo in bloco.get(CHAVE_DOS_IMPORTADOS, {}).values():
                if _opcao_de_tipo(opcoes, CHAVE_DOS_IMPORTADOS, alvo, "importar").formato != "tema":
                    raise ValueError(f"tema.{CHAVE_DOS_IMPORTADOS}: {alvo!r} importa outra coisa")
    if CHAVE_DO_DESTAQUE in bloco:
        _opcao_de_tipo(opcoes, CHAVE_DO_DESTAQUE, bloco[CHAVE_DO_DESTAQUE], "cor")
    if CHAVE_DO_DESTAQUE_LIGADO in bloco:
        if CHAVE_DO_DESTAQUE not in bloco:
            raise ValueError(f"tema.{CHAVE_DO_DESTAQUE_LIGADO} liga um destaque que não há")
        _opcao_de_tipo(opcoes, CHAVE_DO_DESTAQUE_LIGADO, bloco[CHAVE_DO_DESTAQUE_LIGADO], "ligado")
    if CHAVE_DA_LOGO in bloco and _opcao_de_tipo(
            opcoes, CHAVE_DA_LOGO, bloco[CHAVE_DA_LOGO], "importar").formato != "logo":
        raise ValueError(f"tema.{CHAVE_DA_LOGO}: {bloco[CHAVE_DA_LOGO]!r} importa outra coisa")


def _ligada(opcao_id: object, valores: dict[str, Any]) -> bool:
    """O bloco que não liga a escolha a opção nenhuma vale sempre; ligada a uma, vale o que diz
    agora (a escolha guardada, senão o padrão do manifesto)."""
    return not isinstance(opcao_id, str) or valores.get(opcao_id) is True


def _valores(manifesto: Any, lugares: Any) -> dict[str, Any]:
    from hefesto_dualsense4unix.mods import opcoes

    return dict(opcoes.ler(manifesto, lugares)) if manifesto.opcoes else {}


def _folha_da_entrada(manifesto: Any, pasta: Path, lugares: Any,
                      valores: dict[str, Any]) -> str | None:
    """A folha que a extensão pinta agora (``None``: não pinta cor). A escolha mapeada a um
    arquivo do pacote lê o arquivo; a mapeada ao importado lê o que se importou (sem arquivo,
    não pinta); a que não está no mapa deixa a cor da casa."""
    bloco = manifesto.tema
    if any(c in bloco for c in CHAVES_DA_ESCOLHA_DA_COR):
        escolha = valores.get(str(bloco.get(CHAVE_DA_OPCAO_DA_COR)))
        if escolha in bloco.get(CHAVE_DAS_FOLHAS, {}):
            return arquivo_da_pasta(bloco[CHAVE_DAS_FOLHAS][escolha], pasta)
        alvo = bloco.get(CHAVE_DOS_IMPORTADOS, {}).get(escolha)
        if alvo is None:
            return None
        from hefesto_dualsense4unix.mods import importados

        return importados.ler_o_tema(manifesto.id, alvo, lugares) or None
    pinta = any(c in bloco for c in CHAVES_DA_COR) or not any(c in bloco for c in CHAVES_QUE_FAZEM)
    if pinta and _ligada(bloco.get(CHAVE_DA_OPCAO_DA_COR), valores):
        return folha_do_manifesto(bloco, pasta)
    return None


def _destaque_da_entrada(bloco: dict[str, Any], valores: dict[str, Any]) -> str:
    """A cor do destaque escolhida (``#rrggbb``), ou vazio quando ele está desligado."""
    if CHAVE_DO_DESTAQUE not in bloco or not _ligada(bloco.get(CHAVE_DO_DESTAQUE_LIGADO), valores):
        return ""
    valor = valores.get(bloco[CHAVE_DO_DESTAQUE])
    return valor if isinstance(valor, str) and cor(valor) is not None else ""


def _lado_da_entrada(bloco: dict[str, Any], valores: dict[str, Any]) -> str:
    """O lado dos botões que a extensão escolhe agora; vazio deixa o do sistema."""
    if CHAVE_DOS_LADOS in bloco:
        lado = bloco[CHAVE_DOS_LADOS].get(valores.get(str(bloco.get(CHAVE_DA_OPCAO_DO_LADO))), "")
        return str(lado) if lado in LADOS_DOS_BOTOES else ""
    lado = bloco.get(CHAVE_DO_LADO)
    if lado in LADOS_DOS_BOTOES and _ligada(bloco.get(CHAVE_DA_OPCAO_DO_LADO), valores):
        return str(lado)
    return ""


def folha_de_tokens(tokens: dict[str, str]) -> str:
    return ":root{" + "".join(f"{k}:{v} !important;" for k, v in tokens.items()) + "}"


def css_da_extensao(manifesto: Any, lugares: Any) -> meu_css.FolhaDeQuemUsa:
    """O CSS de quem usa da extensão: vazio sem a opção ``css`` ou desligada; senão, o
    ``meu.css`` (a folha, ou a recusa com a linha). A aba lê o mesmo que a janela aplica."""
    from hefesto_dualsense4unix.mods import opcoes

    opcao = manifesto.opcao_do_css
    if opcao is None or opcoes.ler(manifesto, lugares).get(opcao.id) is not True:
        return meu_css.FolhaDeQuemUsa()
    return meu_css.ler(manifesto.id, lugares)


def tema_da_casa(lugares: Any = None) -> TemaDaCasa:
    """O tema da modificação ligada, com a permissão ``tema`` aceita, já conferido.

    A cor e o lado dos botões se escolhem à parte: cada um vale pela extensão ligada por último
    que o traz (com a opção dele ligada, quando o bloco o liga a uma). As outras ficam nos avisos.
    O CSS de quem usa vale pela ligada por último que tem a opção ``css`` ligada, à parte da cor.
    Nada aqui escreve: o registro é lido como está.
    """
    from hefesto_dualsense4unix.mods import instalador
    from hefesto_dualsense4unix.mods.manifesto import ManifestoRecusadoError, ler_manifesto

    lg = lugares or instalador.Lugares.do_xdg()
    try:
        registro = instalador.ler_registro(lg.registro)
    except instalador.InstalacaoRecusadaError as exc:
        return TemaDaCasa(recusa=exc.frase)
    com_cor: list[tuple[str, str, Any, str, str, str]] = []
    com_lado: list[tuple[str, str, Any, str]] = []
    com_css: list[tuple[str, str, Any]] = []
    com_logo: list[tuple[str, str, Any, str]] = []
    sem_manifesto: list[str] = []
    for entrada in registro.values():
        if not entrada.ligada or "tema" not in entrada.permissoes_aceitas:
            continue
        pasta = lg.codigo / entrada.id
        try:
            manifesto = ler_manifesto(pasta)
        except ManifestoRecusadoError as exc:
            sem_manifesto.append(f"O manifesto de «{entrada.nome}» não abriu: {exc.frase}")
            continue
        bloco = manifesto.tema
        if "tema" not in manifesto.tipos:
            continue
        chave = (entrada.ligada_em, entrada.id)
        if manifesto.opcao_do_css is not None:
            com_css.append((*chave, manifesto))
        if not bloco:
            continue
        valores = _valores(manifesto, lg)
        try:
            folha, erro = _folha_da_entrada(manifesto, pasta, lg, valores), ""
        except TemaRecusadoError as exc:
            folha, erro = "", exc.frase
        destaque = _destaque_da_entrada(bloco, valores)
        if folha is not None or destaque or erro:
            com_cor.append((*chave, manifesto, folha or "", destaque, erro))
        lado = _lado_da_entrada(bloco, valores)
        if lado:
            com_lado.append((*chave, manifesto, lado))
        logo = str(bloco.get(CHAVE_DA_LOGO, ""))
        if logo and isinstance(valores.get(logo), str) and valores[logo]:
            com_logo.append((*chave, manifesto, logo))
    com_cor.sort(key=lambda c: c[:2])
    com_lado.sort(key=lambda c: c[:2])
    botoes = com_lado[-1][3] if com_lado else ""
    dele = _o_css_de_quem_usa(com_css, lg, _a_logo(com_logo, lg))
    if not com_cor:
        return TemaDaCasa(de=com_lado[-1][1] if com_lado else "", botoes=botoes, **dele,
                          avisos=_avisos_do_lado(sem_manifesto, com_lado, avisados=()))
    _quando, mod_id, manifesto, folha, destaque, erro = com_cor[-1]
    avisos = (*sem_manifesto, *(f"«{c[2].nome}» também tem tema, e vale o da «{manifesto.nome}»."
                                for c in com_cor[:-1]))
    avisos = _avisos_do_lado(avisos, com_lado, avisados={c[1] for c in com_cor[:-1]})
    try:
        if erro:
            raise TemaRecusadoError(erro)
        tokens = validar(folha).tokens if folha else {}
    except TemaRecusadoError as exc:
        return TemaDaCasa(de=mod_id, recusa=f"O tema de «{manifesto.nome}» não ligou. {exc.frase}",
                          avisos=avisos, botoes=botoes, **dele)
    recusa_do_destaque = ""
    if destaque:
        try:
            tokens = validar(folha_de_tokens({**tokens, TOKEN_DO_DESTAQUE: destaque})).tokens
        except TemaRecusadoError as exc:
            recusa_do_destaque = f"O destaque de «{manifesto.nome}» não ligou. {exc.frase}"
    return TemaDaCasa(folha=folha_de_tokens(tokens) if tokens else "", de=mod_id, avisos=avisos,
                      botoes=botoes, recusa_do_destaque=recusa_do_destaque, **dele)


def _a_logo(com_logo: list[tuple[str, str, Any, str]], lugares: Any) -> tuple[str, str]:
    """A folha da logo importada pela ligada por último que a tem, com o id da extensão."""
    from hefesto_dualsense4unix.mods import importados

    for _quando, mod_id, _manifesto, opcao_id in sorted(com_logo, key=lambda c: c[:2],
                                                         reverse=True):
        folha = importados.css_da_logo(mod_id, opcao_id, lugares)
        if folha:
            return folha, mod_id
    return "", ""


def _o_css_de_quem_usa(com_css: list[tuple[str, str, Any]], lugares: Any,
                      logo: tuple[str, str] = ("", "")) -> dict[str, str]:
    """O CSS da ligada por último que o tem ligado; a recusa, se o arquivo não serve. A
    folha da logo importada vai antes, e o CSS de quem usa ainda pode passar por cima."""
    folha_da_logo, logo_de = logo
    for _quando, mod_id, manifesto in sorted(com_css, key=lambda c: c[:2], reverse=True):
        dele = css_da_extensao(manifesto, lugares)
        if dele.folha or dele.recusa:
            recusa = f"«{manifesto.nome}»: {dele.recusa}" if dele.recusa else ""
            return {"css": folha_da_logo + dele.folha, "css_de": mod_id, "recusa_do_css": recusa}
    return {"css": folha_da_logo, "css_de": logo_de} if folha_da_logo else {}


def _arquivos_da_pessoa(mod_id: str, lugares: Any) -> list[Path]:
    """O ``meu.css`` da extensão que o aceita e o arquivo de cada opção ``importar`` da extensão
    (manifesto que não se lê: nenhum)."""
    from hefesto_dualsense4unix.mods import importados
    from hefesto_dualsense4unix.mods.manifesto import ManifestoRecusadoError, ler_manifesto

    try:
        manifesto = ler_manifesto(lugares.codigo / mod_id)
    except ManifestoRecusadoError:
        return []
    css = [meu_css.caminho(mod_id, lugares)] if manifesto.opcao_do_css is not None else []
    return [*css, *(importados.caminho(mod_id, o.id, lugares) for o in manifesto.opcoes
                    if o.tipo == "importar")]


def arquivos_de_opcoes_dos_temas(lugares: Any = None) -> list[Path]:
    """Os ``opcoes.json`` das extensões de tema ligadas, o ``meu.css`` das que o aceitam e os
    arquivos importados: a janela os vigia, porque a escolha, o CSS salvo e o tema ou a logo
    importados trocam o tema sem tocar no registro."""
    from hefesto_dualsense4unix.mods import instalador, opcoes

    lg = lugares or instalador.Lugares.do_xdg()
    try:
        registro = instalador.ler_registro(lg.registro)
    except instalador.InstalacaoRecusadaError:
        return []
    arquivos: list[Path] = []
    for e in registro.values():
        if not (e.ligada and "tema" in e.permissoes_aceitas):
            continue
        arquivos.append(opcoes.caminho(e.id, lg))
        arquivos.extend(_arquivos_da_pessoa(e.id, lg))
    return arquivos


def _avisos_do_lado(avisos: Sequence[str], com_lado: list[tuple[str, str, Any, str]], *,
                    avisados: Collection[str]) -> tuple[str, ...]:
    """Quem perdeu a escolha do lado para a ligada por último, sem repetir quem já foi avisado."""
    if len(com_lado) < 2:
        return tuple(avisos)
    vencedora = com_lado[-1][2].nome
    return (*avisos, *(f"«{c[2].nome}» também escolhe o lado dos botões, e vale o da "
                       f"«{vencedora}»." for c in com_lado[:-1] if c[1] not in avisados))


__all__ = [
    "ACENTOS",
    "CHAVES_DO_BLOCO",
    "CHAVE_DAS_FOLHAS",
    "CHAVE_DA_LOGO",
    "CHAVE_DA_OPCAO_DA_COR",
    "CHAVE_DA_OPCAO_DO_LADO",
    "CHAVE_DOS_IMPORTADOS",
    "CHAVE_DOS_LADOS",
    "CHAVE_DO_DESTAQUE",
    "CHAVE_DO_DESTAQUE_LIGADO",
    "CHAVE_DO_LADO",
    "FUNDOS",
    "FUNDO_DA_LOGO",
    "FUNDO_DA_PAGINA",
    "LADOS_DOS_BOTOES",
    "LIMIAR_DO_ACENTO",
    "LIMIAR_DO_CONTRASTE",
    "PLASTICOS",
    "TEXTOS",
    "TOKENS_DA_CASA",
    "TemaAceito",
    "TemaDaCasa",
    "TemaRecusadoError",
    "apelidos_da_casa",
    "apelidos_do_root",
    "arquivo_da_pasta",
    "arquivos_de_opcoes_dos_temas",
    "conferir_o_bloco",
    "conferir_o_bloco_e_as_opcoes",
    "contraste",
    "cor",
    "css_da_extensao",
    "e_escuro",
    "folha_de_tokens",
    "folha_do_manifesto",
    "fundo_da_logo",
    "tema_da_casa",
    "token_permitido",
    "tokens_da_casa",
    "tokens_da_folha",
    "tokens_do_root",
    "validar",
    "valores_pintados",
]

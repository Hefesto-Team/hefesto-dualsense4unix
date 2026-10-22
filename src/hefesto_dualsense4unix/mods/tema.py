"""O tema de uma modificação: troca tokens do ``:root`` (só se o texto continua legível) e escolhe
o lado dos botões da janela.

A folha é UM bloco ``:root{…}`` só com cores por extenso, dos tokens de :data:`TOKENS_DA_CASA` e das
categorias da aba Conexões; os plásticos ficam fora. Texto passa de 4,5:1 e acento de 3:1 contra
cada fundo (``docs/research/o-porque-dos-modulos.md``, «O tema de cores»). O bloco ``tema`` traz a
cor (``folha``/``arquivo``), o lado (``botoes``) ou os dois, cada um ligável a uma opção ``ligado``.
"""
from __future__ import annotations

import re
from collections.abc import Collection, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: A página publicada de onde saem os valores da casa (todas as dez têm o mesmo ``:root``).
PAGINA_DOS_TOKENS = (Path(__file__).resolve().parent.parent / "interface"
                     / "paginas"  # (noqa-acento): nome da pasta
                     / "01-jogar.html")

#: Os lados em que uma extensão de tema pode pôr os botões da janela.
LADOS_DOS_BOTOES = ("esquerda", "direita")
#: As chaves do bloco ``tema``: a cor (uma das duas), o lado, e a opção que liga cada um.
CHAVES_DA_COR = ("folha", "arquivo")
CHAVE_DO_LADO = "botoes"
CHAVE_DA_OPCAO_DA_COR = "cor_pela_opcao"
CHAVE_DA_OPCAO_DO_LADO = "botoes_pela_opcao"
CHAVES_DO_BLOCO = frozenset({*CHAVES_DA_COR, CHAVE_DO_LADO, CHAVE_DA_OPCAO_DA_COR,
                             CHAVE_DA_OPCAO_DO_LADO})

LIMIAR_DO_CONTRASTE = 4.5
#: O tema maior que isto não é um tema de cores.
TAMANHO_MAXIMO = 16 * 1024

TEXTOS = ("--fg", "--texto-suave", "--texto-mudo", "--comment", "--rot-campo")
FUNDOS = ("--app-bg", "--panel", "--elevated")
#: O fundo em volta da janela (o ``body``), um tom abaixo do ``--app-bg`` (21/10/2026,
#: A-MOLDURA-DA-PAGINA-SEGUE-O-TEMA-01). Sobre ele só cai o texto do ``body``, o ``--fg``: é esse
#: par que a régua mede, e não os cinco textos de dentro da janela, que nunca pintam ali.
FUNDO_DA_PAGINA = "--fundo-da-pagina"
#: As cores de destaque, que as páginas também usam como cor de texto (título, estado, botão).
ACENTOS = ("--green", "--cyan", "--purple", "--orange", "--pink", "--red", "--yellow")
#: O piso do acento: o da WCAG para componente e texto em negrito. A palavra ao lado do acento
#: diz o mesmo que a cor, e na casa o pior acento (``--red`` sobre ``--elevated``) dá 4,34:1.
LIMIAR_DO_ACENTO = 3.0

#: Os tokens de cor do ``:root`` da casa que um tema pode trocar.
TOKENS_DA_CASA = frozenset({
    *TEXTOS, *FUNDOS, *ACENTOS, "--border-sutil", "--border-forte", "--sel-bg", "--linha",
    "--rot-linha", "--logo-aro", FUNDO_DA_PAGINA,
})
#: O fundo da logo (``none`` na casa): o tema claro diz o disco escuro, para a logo de sempre
#: pintar sobre ele (20/10/2026, O-TEMA-CLARO-NASCE-COMO-EXTENSAO-01). Aceita ``none``, uma cor ou
#: um ``radial-gradient`` só de cores; o aro (``--logo-aro``) é uma cor como as outras.
FUNDO_DA_LOGO = "--logo-fundo"
#: As categorias da aba Conexões: a cor de cada tipo na régua, na sala e na faixa do mapa.
_TOKEN_DE_CATEGORIA = re.compile(r"--(?:c|sala|mapa)-[a-z][a-z_]{0,23}")
#: Os plásticos: a cor de cada controle é a do aparelho, e tema nenhum a troca.
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
    lado do sistema.
    """

    folha: str = ""
    de: str = ""
    recusa: str = ""
    avisos: tuple[str, ...] = field(default_factory=tuple)
    botoes: str = ""


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
        # a primeira parte não é cor: é a forma («circle at 35% 30%»), ou o valor não serve
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
    folha_final = ":root{" + "".join(f"{k}:{v} !important;" for k, v in tokens.items()) + "}"
    return TemaAceito(tokens=tokens, folha=folha_final)


def _conferir_o_contraste(tokens: dict[str, str], casa: dict[str, str],
                          apelidos: dict[str, str]) -> None:
    valores = valores_pintados(casa, tokens, apelidos)
    # a página publicada antes do token não o tem: lá o fundo é cor por extenso, e tema nenhum o
    # troca
    moldura = (FUNDO_DA_PAGINA,) if FUNDO_DA_PAGINA in valores else ()
    for nome in (*TEXTOS, *FUNDOS, *ACENTOS, *moldura):
        c = cor(valores.get(nome, ""))
        if c is None:
            raise TemaRecusadoError(f"Não sei a cor de «{nome}» na casa: o tema não liga.")
        if c[3] < 1:
            raise TemaRecusadoError(f"«{nome}» precisa ser uma cor opaca: o contraste do texto "
                                    "se mede sobre ela.")
    # a frase diz o PIOR par: é ele que a pessoa precisa consertar primeiro
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
    if len(fontes) > 1 or (not fontes and CHAVE_DO_LADO not in bloco):
        raise TemaRecusadoError("O bloco «tema» do manifesto precisa de «folha» ou de «arquivo», "
                                "um dos dois.")
    if not fontes:
        return ""
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


def conferir_o_bloco(bloco: dict[str, Any] | None, pasta: Path) -> None:
    """A régua do bloco ``tema`` inteiro: a folha, quando há, passa em :func:`validar`.

    O bloco que só escolhe o lado dos botões não tem cor a conferir.
    """
    folha = folha_do_manifesto(bloco, pasta)
    if folha or (bloco and any(c in bloco for c in CHAVES_DA_COR)):
        validar(folha)


def _opcao_ligada(manifesto: Any, opcao_id: object, lugares: Any) -> bool:
    """O bloco que não liga a escolha a opção nenhuma vale sempre; ligada a uma, vale o que ela diz
    agora (a escolha guardada, senão o padrão do manifesto)."""
    if not isinstance(opcao_id, str):
        return True
    from hefesto_dualsense4unix.mods import opcoes

    return opcoes.ler(manifesto, lugares).get(opcao_id) is True


def tema_da_casa(lugares: Any = None) -> TemaDaCasa:
    """O tema da modificação ligada, com a permissão ``tema`` aceita, já conferido.

    A cor e o lado dos botões se escolhem à parte: cada um vale pela extensão ligada por último
    que o traz (com a opção dele ligada, quando o bloco o liga a uma). As outras ficam nos avisos.
    Nada aqui escreve: o registro é lido como está.
    """
    from hefesto_dualsense4unix.mods import instalador
    from hefesto_dualsense4unix.mods.manifesto import ManifestoRecusadoError, ler_manifesto

    lg = lugares or instalador.Lugares.do_xdg()
    try:
        registro = instalador.ler_registro(lg.registro)
    except instalador.InstalacaoRecusadaError as exc:
        return TemaDaCasa(recusa=exc.frase)
    com_cor: list[tuple[str, str, Any, Path]] = []
    com_lado: list[tuple[str, str, Any, str]] = []
    sem_manifesto: list[str] = []
    for entrada in registro.values():
        if not entrada.ligada or "tema" not in entrada.permissoes_aceitas:
            continue
        pasta = lg.codigo / entrada.id
        try:
            manifesto = ler_manifesto(pasta)
        except ManifestoRecusadoError as exc:
            # o manifesto que não abre não liga tema nenhum, e a frase dele vai aos avisos
            sem_manifesto.append(f"O manifesto de «{entrada.nome}» não abriu: {exc.frase}")
            continue
        bloco = manifesto.tema
        if "tema" not in manifesto.tipos or not bloco:
            continue
        chave = (entrada.ligada_em, entrada.id)
        # o bloco que não diz cor nem lado também entra pela cor: é a régua dela que o recusa
        if (any(c in bloco for c in CHAVES_DA_COR) or CHAVE_DO_LADO not in bloco) and _opcao_ligada(
                manifesto, bloco.get(CHAVE_DA_OPCAO_DA_COR), lg):
            com_cor.append((*chave, manifesto, pasta))
        lado = bloco.get(CHAVE_DO_LADO)
        if lado in LADOS_DOS_BOTOES and _opcao_ligada(
                manifesto, bloco.get(CHAVE_DA_OPCAO_DO_LADO), lg):
            com_lado.append((*chave, manifesto, lado))
    com_cor.sort(key=lambda c: c[:2])
    com_lado.sort(key=lambda c: c[:2])
    botoes = com_lado[-1][3] if com_lado else ""
    if not com_cor:
        return TemaDaCasa(de=com_lado[-1][1] if com_lado else "", botoes=botoes,
                          avisos=_avisos_do_lado(sem_manifesto, com_lado, avisados=()))
    _quando, mod_id, manifesto, pasta = com_cor[-1]
    avisos = (*sem_manifesto, *(f"«{c[2].nome}» também tem tema, e vale o da «{manifesto.nome}»."
                                for c in com_cor[:-1]))
    avisos = _avisos_do_lado(avisos, com_lado, avisados={c[1] for c in com_cor[:-1]})
    try:
        aceito = validar(folha_do_manifesto(manifesto.tema, pasta))
    except TemaRecusadoError as exc:
        return TemaDaCasa(de=mod_id, recusa=f"O tema de «{manifesto.nome}» não ligou. {exc.frase}",
                          avisos=avisos, botoes=botoes)
    return TemaDaCasa(folha=aceito.folha, de=mod_id, avisos=avisos, botoes=botoes)


def arquivos_de_opcoes_dos_temas(lugares: Any = None) -> list[Path]:
    """Os ``opcoes.json`` das extensões de tema ligadas: a janela os vigia, porque a opção
    «Cores claras» ou «Botões à esquerda» troca o tema sem tocar no registro."""
    from hefesto_dualsense4unix.mods import instalador, opcoes

    lg = lugares or instalador.Lugares.do_xdg()
    try:
        registro = instalador.ler_registro(lg.registro)
    except instalador.InstalacaoRecusadaError:
        return []
    return [opcoes.caminho(e.id, lg) for e in registro.values()
            if e.ligada and "tema" in e.permissoes_aceitas]


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
    "CHAVE_DA_OPCAO_DA_COR",
    "CHAVE_DA_OPCAO_DO_LADO",
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
    "arquivos_de_opcoes_dos_temas",
    "conferir_o_bloco",
    "contraste",
    "cor",
    "e_escuro",
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

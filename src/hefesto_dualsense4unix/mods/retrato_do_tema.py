"""O retrato de uma extensão de tema para a janela da extensão: cada tema escolhível, já pintado, o
papel de cada opção, a paleta que o tema pinta e o que se exporta.

Tudo sai do bloco ``tema`` do manifesto e das escolhas guardadas: o produto não conhece o nome de
extensão nenhuma. Nada aqui escreve, salvo :func:`exportar`, que só devolve o texto.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from hefesto_dualsense4unix.mods import meu_css, tema
from hefesto_dualsense4unix.mods.leitura_da_caixa import ler_ou_vazio

PAPEL_DOS_TOKENS = (
    ("--app-bg", "Fundo"), ("--panel", "Painel"), ("--elevated", "Cartão"),
    ("--fg", "Texto"), ("--texto-suave", "Texto suave"), ("--texto-mudo", "Texto mudo"),
    ("--green", "Destaque"), ("--cyan", "Ciano"), ("--purple", "Roxo"), ("--orange", "Laranja"),
    ("--pink", "Rosa"), ("--red", "Vermelho"), ("--yellow", "Amarelo"),
)
LINHAS_DO_CSS = 9
DESTAQUES = ("#50fa7b", "#8be9fd", "#bd93f9", "#ff79c6", "#ffb86c", "#f1fa8c",
             "#1d7a3c", "#006d85", "#6a3dc2", "#ad2f6c", "#a35200", "#c01f2e")
MAXIMO_DE_DESTAQUES = 7
DE_FABRICA = "fabrica"
IMPORTADO = "importado"


@dataclass(frozen=True)
class Papeis:
    """O id da opção de cada papel do bloco ``tema`` (vazio: o bloco não tem o papel)."""

    cor: str = ""
    importado: str = ""
    destaque: str = ""
    destaque_ligado: str = ""
    botoes: str = ""
    logo: str = ""
    css: str = ""
    lados: dict[str, str] = field(default_factory=dict)
    importados: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Carta:
    """Um tema que a extensão escolhe: a escolha, de onde vem e as cores que ele pinta (vazias:
    importado sem arquivo, ou um tema que não passa na régua)."""

    escolha: str
    origem: str
    cores: dict[str, str]
    arquivo: str = ""


@dataclass(frozen=True)
class Retrato:
    papeis: Papeis
    cartas: tuple[Carta, ...] = ()
    escolhida: str = ""
    cores: dict[str, str] = field(default_factory=dict)
    contraste: float = 0.0
    destaque: str = ""
    lado: str = ""
    botoes: str = ""
    logo: str = ""
    css_ligado: bool = False
    css_linhas: tuple[str, ...] = ()

    @property
    def carta(self) -> Carta | None:
        return next((c for c in self.cartas if c.escolha == self.escolhida), None)


def papeis(manifesto: Any) -> Papeis:
    bloco = manifesto.tema or {}
    importados = {str(k): str(v) for k, v in bloco.get(tema.CHAVE_DOS_IMPORTADOS, {}).items()}
    css = manifesto.opcao_do_css
    return Papeis(
        cor=str(bloco.get(tema.CHAVE_DA_OPCAO_DA_COR) or ""),
        importado=next(iter(importados.values()), ""),
        destaque=str(bloco.get(tema.CHAVE_DO_DESTAQUE) or ""),
        destaque_ligado=str(bloco.get(tema.CHAVE_DO_DESTAQUE_LIGADO) or ""),
        botoes=str(bloco.get(tema.CHAVE_DA_OPCAO_DO_LADO) or ""),
        logo=str(bloco.get(tema.CHAVE_DA_LOGO) or ""),
        css=css.id if css is not None else "",
        lados={str(k): str(v) for k, v in bloco.get(tema.CHAVE_DOS_LADOS, {}).items()},
        importados=importados)


def _tokens(texto: str, casa: dict[str, str], apelidos: dict[str, str]) -> dict[str, str]:
    try:
        return tema.validar(texto, casa=casa, apelidos=apelidos).tokens if texto else {}
    except tema.TemaRecusadoError:
        return {}


def _so_cores(valores: dict[str, str]) -> dict[str, str]:
    return {k: v for k, v in valores.items()
            if tema.token_permitido(k) and k not in tema.PLASTICOS and tema.cor(v) is not None}


def _cartas(manifesto: Any, pasta: Path, lugares: Any, valores: dict[str, Any], p: Papeis,
            casa: dict[str, str], apelidos: dict[str, str]) -> tuple[Carta, ...]:
    from hefesto_dualsense4unix.mods import importados

    opcao = next((o for o in manifesto.opcoes if o.id == p.cor and o.tipo == "escolha"), None)
    if opcao is None:
        return ()
    folhas = (manifesto.tema or {}).get(tema.CHAVE_DAS_FOLHAS, {})
    cartas = []
    for escolha in opcao.escolhas:
        alvo = p.importados.get(escolha)
        if alvo:
            tokens = _tokens(importados.ler_o_tema(manifesto.id, alvo, lugares), casa, apelidos)
            arquivo = str(valores.get(alvo) or "")
            cores = _so_cores(tema.valores_pintados(casa, tokens, apelidos)) if tokens else {}
            cartas.append(Carta(escolha, IMPORTADO, cores, arquivo))
            continue
        tokens = {}
        if escolha in folhas:
            try:
                tokens = _tokens(tema.arquivo_da_pasta(folhas[escolha], pasta), casa, apelidos)
            except tema.TemaRecusadoError:
                cartas.append(Carta(escolha, DE_FABRICA, {}))
                continue
        cartas.append(Carta(escolha, DE_FABRICA,
                            _so_cores(tema.valores_pintados(casa, tokens, apelidos))))
    return tuple(cartas)


def _menor_contraste(cores: dict[str, str]) -> float:
    try:
        return min(tema.contraste(cores[t], cores[f]) for t in tema.TEXTOS for f in tema.FUNDOS)
    except (KeyError, ValueError):
        return 0.0


def _com_o_destaque(cores: dict[str, str], destaque: str) -> dict[str, str]:
    if not destaque or not cores:
        return cores
    com = {**cores, tema.TOKEN_DO_DESTAQUE: destaque}
    try:
        tema.validar(tema.folha_de_tokens(com), casa=cores, apelidos={})
    except tema.TemaRecusadoError:
        return cores
    return com


def _primeiras_linhas(mod_id: str, lugares: Any) -> tuple[str, ...]:
    alvo = meu_css.caminho(mod_id, lugares)
    try:
        texto = ler_ou_vazio(alvo, meu_css.TAMANHO_MAXIMO).decode("utf-8")
    except UnicodeDecodeError:
        return ()
    linhas = [ln.rstrip() for ln in texto.splitlines() if ln.strip()]
    return tuple("".join(c for c in ln if c.isprintable())[:80] for ln in linhas[:LINHAS_DO_CSS])


def retratar(manifesto: Any, lugares: Any, *, casa: dict[str, str] | None = None,
             apelidos: dict[str, str] | None = None, pinta: bool = True) -> Retrato | None:
    """O retrato da extensão de tema (``None`` sem bloco ``tema``), pelas escolhas guardadas.
    Com ``pinta`` falso (a extensão desligada ou sem a permissão), o que a tela pinta é a casa:
    as cartas continuam, e as cores, o destaque, o lado, a logo e o CSS em uso são os da casa."""
    if not manifesto.tema:
        return None
    from hefesto_dualsense4unix.mods import opcoes

    casa = tema.tokens_da_casa() if casa is None else casa
    apelidos = tema.apelidos_da_casa() if apelidos is None else apelidos
    valores = dict(opcoes.ler(manifesto, lugares)) if manifesto.opcoes else {}
    p = papeis(manifesto)
    pasta = Path(lugares.codigo) / manifesto.id
    cartas = _cartas(manifesto, pasta, lugares, valores, p, casa, apelidos)
    escolhida = str(valores.get(p.cor) or "") if pinta else ""
    carta = next((c for c in cartas if c.escolha == escolhida), None)
    base = carta.cores if carta and carta.cores else _so_cores(
        tema.valores_pintados(casa, {}, apelidos))
    destaque = ""
    if pinta and p.destaque and (not p.destaque_ligado or valores.get(p.destaque_ligado) is True):
        valor = valores.get(p.destaque)
        destaque = valor if isinstance(valor, str) and tema.cor(valor) is not None else ""
    cores = _com_o_destaque(base, destaque)
    lado_escolhido = str(valores.get(p.botoes) or "") if pinta else ""
    return Retrato(
        papeis=p, cartas=cartas, escolhida=escolhida, cores=cores,
        contraste=_menor_contraste(cores),
        destaque=destaque if cores.get(tema.TOKEN_DO_DESTAQUE) == destaque else "",
        lado=p.lados.get(lado_escolhido, ""), botoes=lado_escolhido,
        logo=str(valores.get(p.logo) or "") if p.logo and pinta else "",
        css_ligado=pinta and bool(p.css) and valores.get(p.css) is True,
        css_linhas=_primeiras_linhas(manifesto.id, lugares) if p.css else ())


def exportar(retrato: Retrato) -> str:
    """O tema que a extensão pinta, como um arquivo que a régua aceita de volta no «Importar»."""
    tokens = dict(retrato.cores)
    if not tokens:
        raise tema.TemaRecusadoError("Não há tema para exportar.")
    corpo = "".join(f"\n  {k}: {v};" for k, v in sorted(tokens.items()))
    texto = f":root {{{corpo}\n}}\n"
    tema.validar(texto)
    return texto


def escolha_do_importado(manifesto: Any, opcao_id: str) -> tuple[str, str] | None:
    """A opção e a escolha que passam a valer quando se importa um tema em ``opcao_id``."""
    p = papeis(manifesto)
    escolha = next((e for e, alvo in p.importados.items() if alvo == opcao_id), None)
    return (p.cor, escolha) if p.cor and escolha else None


def ligar_o_destaque(manifesto: Any, opcao_id: str) -> str | None:
    """A opção ``ligado`` do destaque, que liga quando se escolhe a cor dele."""
    p = papeis(manifesto)
    if p.destaque and opcao_id == p.destaque and p.destaque_ligado:
        return p.destaque_ligado
    return None


def destaques_legiveis(cores: dict[str, str]) -> tuple[str, ...]:
    """As cores prontas de destaque que se leem sobre os fundos do tema em uso."""
    fundos = [cores[f] for f in tema.FUNDOS if f in cores]
    if not fundos:
        return ()
    boas = [c for c in DESTAQUES
            if all(tema.contraste(c, f) >= tema.LIMIAR_DO_ACENTO for f in fundos)]
    return tuple(boas[:MAXIMO_DE_DESTAQUES])


def papel_do_token(nome: str) -> str:
    return dict(PAPEL_DOS_TOKENS).get(nome, nome)


__all__ = ["DESTAQUES", "DE_FABRICA", "IMPORTADO", "PAPEL_DOS_TOKENS", "Carta", "Papeis",
           "Retrato", "destaques_legiveis", "escolha_do_importado", "exportar",
           "ligar_o_destaque", "papeis", "papel_do_token", "retratar"]

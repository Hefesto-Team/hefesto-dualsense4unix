"""As extensões que o install traz de um endereço git, ao lado das de fábrica que moram no pacote.

A lista é dado (``de_fabrica_por_endereco.json``), nunca código: o produto não conhece o nome de
extensão nenhuma. Trazer é idempotente. A que falta se instala do endereço e se liga (só na
primeira vez: a que quem usa desligou fica desligada); a que já está fica como está, e a que veio
de um endereço antigo passa a apontar para o novo, para a atualização sozinha não depender do
redirecionamento do GitHub. Aviso nunca se aceita por quem usa: a que pede aviso fica desligada.
A que substitui uma desligada nasce desligada, e a que quem usa removeu não volta: as já trazidas
ficam anotadas ao lado do registro.
"""
from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from hefesto_dualsense4unix.mods.instalador import (
    AvisoParaVerError,
    InstalacaoRecusadaError,
    Lugares,
    gravar_registro,
    instalar,
    ler_registro,
    ligar,
)

ARQUIVO = Path(__file__).resolve().parent / "de_fabrica_por_endereco.json"
TRAZIDAS = "mods-de-fabrica.json"
FRASE_DA_REMOVIDA = "Quem usa a removeu; não volta sozinha."

OQueFez = Literal["instalada", "ligada", "ja_estava", "endereco_novo", "recusada", "removida"]


class DeFabrica(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    endereco: str
    enderecos_antigos: list[str] = []
    ligar: bool = True


@dataclass(frozen=True)
class Feito:
    id: str
    o_que: OQueFez
    frase: str = ""


def ler(arquivo: Path = ARQUIVO) -> list[DeFabrica]:
    try:
        bruto = json.loads(arquivo.read_text(encoding="utf-8"))
        return [DeFabrica.model_validate(linha)
                for linha in bruto["extensoes"]]  # (noqa-acento)
    except (OSError, ValueError, KeyError, TypeError, ValidationError) as exc:
        raise InstalacaoRecusadaError(f"A lista {arquivo.name} não pôde ser lida.") from exc


def _o_mesmo(a: str, b: str) -> bool:
    def limpo(endereco: str) -> str:
        return endereco.strip().removesuffix("/").removesuffix(".git").lower()

    return limpo(a) == limpo(b)


def _caminho_das_trazidas(lg: Lugares) -> Path:
    return lg.registro.with_name(TRAZIDAS)


def _trazidas(lg: Lugares) -> set[str]:
    try:
        bruto = json.loads(_caminho_das_trazidas(lg).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    ids = bruto.get("trazidas") if isinstance(bruto, dict) else None
    return {str(i) for i in ids} if isinstance(ids, list) else set()


def _anotar(lg: Lugares, mod_id: str) -> None:
    trazidas = _trazidas(lg)
    if mod_id in trazidas:
        return
    alvo = _caminho_das_trazidas(lg)
    alvo.parent.mkdir(parents=True, exist_ok=True)
    provisorio = alvo.with_suffix(".tmp")
    provisorio.write_text(json.dumps({"trazidas": sorted(trazidas | {mod_id})}), encoding="utf-8")
    provisorio.replace(alvo)


def _uma(item: DeFabrica, lg: Lugares, instalar_: Callable[..., Any],
         ligar_: Callable[..., Any]) -> Feito:
    feito = _trazer_uma(item, lg, instalar_, ligar_)
    if feito.o_que not in ("recusada", "removida"):
        _anotar(lg, item.id)
    return feito


def _trazer_uma(item: DeFabrica, lg: Lugares, instalar_: Callable[..., Any],
                ligar_: Callable[..., Any]) -> Feito:
    registro = ler_registro(lg.registro)
    entrada = registro.get(item.id)
    if entrada is None and item.id in _trazidas(lg):
        return Feito(item.id, "removida", FRASE_DA_REMOVIDA)
    if entrada is not None:
        if entrada.origem != "local" and any(
                _o_mesmo(entrada.endereco, antigo) for antigo in item.enderecos_antigos):
            entrada.endereco = item.endereco
            gravar_registro(lg.registro, registro)
            return Feito(item.id, "endereco_novo")
        return Feito(item.id, "ja_estava")
    ligadas_antes = {mod_id for mod_id, e in registro.items() if e.ligada}
    try:
        resultado = instalar_(item.endereco, lugares=lg, aviso_visto=None)
    except InstalacaoRecusadaError as exc:
        return Feito(item.id, "recusada", exc.frase)
    if resultado.entrada.ligada:
        return Feito(item.id, "ligada")
    desligadas = resultado.substituidas and not ligadas_antes & set(resultado.substituidas)
    if not item.ligar or desligadas:
        return Feito(item.id, "instalada")
    try:
        ligar_(item.id, permissoes_vistas=resultado.manifesto.permissoes, aviso_visto="",
               lugares=lg)
    except AvisoParaVerError as aviso:
        return Feito(item.id, "instalada", aviso.frase)
    except InstalacaoRecusadaError as exc:
        return Feito(item.id, "instalada", exc.frase)
    return Feito(item.id, "ligada")


def trazer(*, lugares: Lugares | None = None, arquivo: Path = ARQUIVO,
           instalar_: Callable[..., Any] = instalar,
           ligar_: Callable[..., Any] = ligar) -> list[Feito]:
    """Traz cada extensão da lista; a que falha não segura as outras."""
    lg = lugares or Lugares.do_xdg()
    return [_uma(item, lg, instalar_, ligar_) for item in ler(arquivo)]


__all__ = ["ARQUIVO", "FRASE_DA_REMOVIDA", "TRAZIDAS", "DeFabrica", "Feito", "ler", "trazer"]

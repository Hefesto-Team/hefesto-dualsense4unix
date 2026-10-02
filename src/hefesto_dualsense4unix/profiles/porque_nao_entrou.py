"""Por que o perfil DAQUELE jogo não entrou — a pergunta que ninguém respondia."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from hefesto_dualsense4unix.profiles.schema import MatchCriteria, Profile
from hefesto_dualsense4unix.profiles.steam_app import steam_appid_from_wm_class

__all__ = [
    "CampoReprovado",
    "PerfilQueNaoEntrou",
    "campos_reprovados",
    "frase_do_perfil_que_nao_entrou",
    "perfis_que_nao_entraram",
]

_ROTULO_DO_CAMPO = {
    "window_class": "classe da janela",
    "window_title_regex": "título da janela",
    "process_name": "nome do processo",
}

_CHAVE_OBSERVADA = {
    "window_class": "wm_class",
    "window_title_regex": "wm_name",
    "process_name": "exe_basename",
}


@dataclass(frozen=True)
class CampoReprovado:
    """Um critério que o perfil exigiu e a janela em foco não satisfez."""

    campo: str
    exigido: list[str]
    observado: str

    @property
    def rotulo(self) -> str:
        return _ROTULO_DO_CAMPO.get(self.campo, self.campo)


@dataclass(frozen=True)
class PerfilQueNaoEntrou:
    """Um perfil que reprovou, e por quais campos."""

    nome: str
    reprovados: list[CampoReprovado]
    e_regra_deste_jogo: bool


def _observado(window_info: dict[str, Any], campo: str) -> str:
    valor = window_info.get(_CHAVE_OBSERVADA[campo])
    return valor if isinstance(valor, str) else ""


def campos_reprovados(
    match: MatchCriteria, window_info: dict[str, Any]
) -> list[CampoReprovado]:
    """Quais campos preenchidos do critério NÃO casaram com esta janela."""
    reprovados: list[CampoReprovado] = []
    for campo in ("window_class", "window_title_regex", "process_name"):
        exigido = getattr(match, campo, None)
        if not exigido:
            continue
        lista = [exigido] if isinstance(exigido, str) else list(exigido)
        so_este_campo = MatchCriteria(**{campo: exigido})
        if not so_este_campo.matches(window_info):
            reprovados.append(
                CampoReprovado(
                    campo=campo,
                    exigido=lista,
                    observado=_observado(window_info, campo),
                )
            )
    return reprovados


def perfis_que_nao_entraram(
    window_info: dict[str, Any], perfis: list[Profile]
) -> list[PerfilQueNaoEntrou]:
    """Os perfis que reprovaram nesta janela, com o motivo de cada um."""
    appid_em_foco = steam_appid_from_wm_class(str(window_info.get("wm_class") or ""))
    achados: list[PerfilQueNaoEntrou] = []
    for perfil in perfis:
        match = getattr(perfil, "match", None)
        if not isinstance(match, MatchCriteria):
            continue
        if match.matches(dict(window_info)):
            continue
        reprovados = campos_reprovados(match, window_info)
        if not reprovados:
            continue
        e_deste_jogo = appid_em_foco is not None and any(
            steam_appid_from_wm_class(classe) == appid_em_foco
            for classe in match.window_class
        )
        achados.append(
            PerfilQueNaoEntrou(
                nome=str(getattr(perfil, "name", "") or ""),
                reprovados=reprovados,
                e_regra_deste_jogo=e_deste_jogo,
            )
        )
    achados.sort(key=lambda a: (not a.e_regra_deste_jogo, a.nome))
    return achados


def _lista_humana(valores: list[str]) -> str:
    aspas = [f'"{v}"' for v in valores]
    if len(aspas) == 1:
        return aspas[0]
    if len(aspas) == 2:
        return f"{aspas[0]} ou {aspas[1]}"
    return f"{', '.join(aspas[:-1])} ou {aspas[-1]}"


def frase_do_perfil_que_nao_entrou(achado: PerfilQueNaoEntrou) -> str:
    """A frase que a janela mostra. Factual: o exigido e o observado, lado a lado."""
    partes: list[str] = []
    for r in achado.reprovados:
        if r.observado:
            partes.append(f"exige {r.rotulo} {_lista_humana(r.exigido)}, e aqui vê ")
            partes.append(f'"{r.observado}"')
        else:
            partes.append(
                f"exige {r.rotulo} {_lista_humana(r.exigido)}, "
                f"e aqui não vê {r.rotulo} nesta janela"
            )
        partes.append("; ")
    motivo = "".join(partes).rstrip("; ")
    if achado.e_regra_deste_jogo:
        return (
            f'O seu perfil "{achado.nome}" é deste jogo, mas não entrou: '
            f"ele {motivo}."
        )
    return f'O perfil "{achado.nome}" não entrou: ele {motivo}.'

"""Os jogos da Steam que não recebem gatilhos e vibração, e a cura de cada um.

Duas perguntas por jogo, ambas com dono: o Steam Input ligado por jogo fora da lista de exceções
(``steam_input_ponte``) e o jogo fora do Proton fixado (``proton_pin``). Sondar só lê (``dry_run``);
curar escreve pelas primitivas, que recusam com a Steam aberta. Toda função recebe o ``home``.
"""
from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

_LOG = logging.getLogger(__name__)

ENTRADA = "entrada"
PROTON = "proton"

#: O que a linha diz do impedimento e o rótulo do botão que o resolve, por tipo.
FRASE = {
    ENTRADA: "O Steam Input está ligado: o jogo vê um controle de Xbox",
    PROTON: "Fora do Proton fixado: a vibração e os gatilhos não chegam",
}
BOTAO = {
    ENTRADA: "Desligar o Steam Input",
    PROTON: "Usar o Proton fixado",
}


class ImpedimentoNaoCuradoError(Exception):
    """A cura não saiu; ``frase`` é o que a pessoa lê."""

    def __init__(self, frase: str) -> None:
        super().__init__(frase)
        self.frase = frase


@dataclass(frozen=True)
class Impedimento:
    appid: str
    jogo: str
    tipo: str

    @property
    def chave(self) -> str:
        """O ``data-v`` do botão: o tipo e o appid, que são o que separa os dois jeitos de cura."""
        return f"{self.tipo}:{self.appid}"

    @property
    def frase(self) -> str:
        return FRASE[self.tipo]

    @property
    def botao(self) -> str:
        return BOTAO[self.tipo]


def _nome(appid: str, home: Path | None) -> str:
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    try:
        return slo.nome_do_appid(appid, home) or f"appid {appid}"
    except Exception:
        return f"appid {appid}"


def _com_o_steam_input_ligado(home: Path | None) -> list[str]:
    from hefesto_dualsense4unix.integrations import steam_input_ponte as sip

    _estado, detalhe = sip.garantir_fora_da_lista_desligado(home, dry_run=True)
    return sorted(
        {d["appid"] for d in detalhe
         if d.get("desfecho") == sip.PONTE_DESLIGADA and d.get("appid")},
        key=lambda a: (not a.isdigit(), int(a) if a.isdigit() else 0, a),
    )


def _fora_do_proton_fixado(home: Path | None) -> list[str]:
    """Os jogos instalados cujo Proton efetivo não é o fixado; vazio quando o pino não está aqui."""
    from hefesto_dualsense4unix.integrations import proton_pin as pp

    caminho = pp.default_pin_conf_path()
    if caminho is None:
        return []
    conf = pp.parse_pin_conf(caminho.read_text(encoding="utf-8"))
    compat = pp.default_compat_dir(home)
    if not pp.pinned_proton_installed(conf["name"], compat):
        return []
    vdf = pp.default_config_vdf(home)
    if not vdf.is_file():
        return []
    texto = vdf.read_text(encoding="utf-8", errors="replace")
    instalados = pp.list_installed_appids(home)
    relato = pp.proton_pin_report(
        conf, compat_dir=compat, config_vdf_text=texto, installed_appids=instalados)
    mapa = relato["mapping"]
    fora = [str(a) for a in relato["games_off_pin"]]  # type: ignore[attr-defined]
    nomeados = set(pp.ler_jogos_fora_do_pino(pp.fora_do_pino_path(home)))
    fora = [a for a in fora if a not in nomeados]
    sem_entrada = [a for a in fora if not mapa.get(a)]  # type: ignore[attr-defined]
    nativos = set(pp.jogos_sem_entrada_nova(sem_entrada, home=home)) if sem_entrada else set()
    return [a for a in fora if a not in nativos]


def sondar(home: Path | None = None) -> tuple[Impedimento, ...]:
    """Os impedimentos desta máquina, só lendo; leitura que falha deixa só aquele tipo de fora."""
    achados: list[Impedimento] = []
    for tipo, leitor in ((ENTRADA, _com_o_steam_input_ligado), (PROTON, _fora_do_proton_fixado)):
        try:
            appids = leitor(home)
        except Exception:
            _LOG.debug("impedimentos_da_steam_leitura_falhou", exc_info=True)
            continue
        achados.extend(Impedimento(a, _nome(a, home), tipo) for a in appids)
    return tuple(achados)


def _recusa_da_steam(motivo: str) -> str:
    return {
        "jogo_da_steam_aberto": "Feche o jogo e a Steam antes: com ela aberta a edição se perde.",
        "adiado_jogo_aberto": "Feche o jogo e a Steam antes: com ela aberta a edição se perde.",
        "steam_aberta": "Feche a Steam antes: com ela aberta a edição se perde.",
        "adiado_steam_aberta": "Feche a Steam antes: com ela aberta a edição se perde.",
    }.get(motivo, "")


def _desligar_o_steam_input(appids: Sequence[str], home: Path | None) -> None:
    from hefesto_dualsense4unix.integrations import steam_input_ponte as sip

    lista = sip.ler_allowlist()
    # A primitiva desliga TODO jogo configurado fora da lista; os outros impedimentos entram como
    # exceção desta chamada, para a cura de um jogo não desligar o do vizinho.
    outros = [x for x in _com_o_steam_input_ligado(home) if x not in set(appids)]
    status, _detalhe = sip.garantir_fora_da_lista_desligado(
        home, allowlist=[*lista, *outros])
    if status == sip.PONTE_DESLIGADA:
        return
    if status == sip.PONTE_NADA:
        return
    frase = _recusa_da_steam(status)
    if frase:
        raise ImpedimentoNaoCuradoError(frase)
    raise ImpedimentoNaoCuradoError(
        "Não consegui desligar o Steam Input: o arquivo da Steam não deixou escrever.")


def _fixar_o_proton(appids: Sequence[str], home: Path | None) -> None:
    from hefesto_dualsense4unix.integrations import proton_pin as pp

    caminho = pp.default_pin_conf_path()
    if caminho is None:
        raise ImpedimentoNaoCuradoError("Não achei o Proton fixado desta versão do Hefesto.")
    conf = pp.parse_pin_conf(caminho.read_text(encoding="utf-8"))
    resultado = pp.lock_games_to_pinned_proton(
        tool_name=conf["name"], appids=list(appids), home=home, todos=True,
        excluir=pp.ler_jogos_fora_do_pino(pp.fora_do_pino_path(home)),
        compat_dir=pp.default_compat_dir(home))
    status = str(resultado.get("status"))
    if status in ("locked", "noop"):
        return
    motivo = str(resultado.get("reason") or "")
    frase = _recusa_da_steam(motivo)
    if frase:
        raise ImpedimentoNaoCuradoError(frase)
    if motivo == "pino_ausente":
        raise ImpedimentoNaoCuradoError("O Proton fixado não está instalado nesta máquina.")
    raise ImpedimentoNaoCuradoError("Não consegui trocar o Proton do jogo: nada foi alterado.")


def curar(impedimentos: Sequence[Impedimento], *, home: Path | None = None) -> str:
    """Resolve os impedimentos, cada tipo pelo seu dono; devolve a frase e levanta se não saiu."""
    if not impedimentos:
        raise ImpedimentoNaoCuradoError("Esse impedimento já foi resolvido.")
    por_tipo: dict[str, list[str]] = {}
    for imp in impedimentos:
        por_tipo.setdefault(imp.tipo, []).append(imp.appid)
    if ENTRADA in por_tipo:
        _desligar_o_steam_input(por_tipo[ENTRADA], home)
    if PROTON in por_tipo:
        _fixar_o_proton(por_tipo[PROTON], home)
    nomes = ", ".join(i.jogo for i in impedimentos[:3])
    resto = f" e mais {len(impedimentos) - 3}" if len(impedimentos) > 3 else ""
    return f"Resolvido: {nomes}{resto}."


__all__ = [
    "BOTAO", "ENTRADA", "FRASE", "PROTON", "Impedimento", "ImpedimentoNaoCuradoError",
    "curar", "sondar",
]

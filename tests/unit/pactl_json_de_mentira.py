"""O texto que o `pactl --format=json list …` imprime, para os dublês de servidor de som.

O produto lê o servidor pelo JSON (`integrations/porta_do_som.py`); os testes
que dublam o servidor montam a MESMA forma que o `pactl` 16.1 devolve, com
campos nomeados. Aqui mora a montagem, para cada dublê não reescrever o formato.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

def argv_json(tipo: str) -> list[str]:
    return ["pactl", "--format=json", "list", tipo]


def e_lista_json(argv: Sequence[str], tipo: str) -> bool:
    """O argv é a lista completa em JSON de ``tipo`` (`--format=json` ou `-f json`)?"""
    return list(argv[:4]) == argv_json(tipo) or list(argv[:5]) == [
        "pactl", "-f", "json", "list", tipo]


def volume(porcentos: Iterable[int], canais: Sequence[str] | None = None) -> dict[str, Any]:
    """O objeto ``volume`` do JSON: um canal por por cento, na ordem do mapa."""
    porcentos = list(porcentos)
    nomes = list(canais) if canais else {
        1: ["mono"], 2: ["front-left", "front-right"],
        4: ["front-left", "front-right", "rear-left", "rear-right"],
    }.get(len(porcentos), [f"aux{i}" for i in range(len(porcentos))])
    return {n: {"value": int(65536 * p / 100), "value_percent": f"{p}%",
                "db": "0.00 dB" if p == 100 else "-23.88 dB"}
            for n, p in zip(nomes, porcentos, strict=False)}


def no(indice: int, nome: str, *, descricao: str = "", estado: str = "IDLE",
       formato: str = "float32le 2ch 48000Hz", mudo: bool = False,
       porcentos: Iterable[int] | None = None, props: Mapping[str, str] | None = None,
       extra: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Um nó (`sink` ou `source`) do `pactl --format=json list sinks|sources`."""
    saida: dict[str, Any] = {
        "index": indice, "state": estado, "name": nome, "description": descricao,
        "driver": "PipeWire", "sample_specification": formato, "mute": mudo,
        "properties": {"node.name": nome, **(props or {})},
    }
    if porcentos is not None:
        saida["volume"] = volume(porcentos)
    saida.update(extra or {})
    return saida


def fluxo(indice: int, alvo: int | str | None, *, tipo: str = "sink",
          props: Mapping[str, str] | None = None, cliente: str | None = "77",
          corked: bool = False, mudo: bool = False,
          formato: str = "float32le 4ch 48000Hz") -> dict[str, Any]:
    """Um fluxo (`sink-input` com ``tipo="sink"``, `source-output` com ``tipo="source"``)."""
    return {
        "index": indice, tipo: alvo, "client": cliente, "driver": "PipeWire",
        "sample_specification": formato, "corked": corked, "mute": mudo,
        "properties": dict(props or {}),
    }


def texto(*objetos: Mapping[str, Any]) -> str:
    """A lista, no texto que o `pactl` imprime."""
    return json.dumps(list(objetos))


_BLOCO = re.compile(r"^(Sink Input|Source Output|Sink|Source|Card) #(\d+)\s*$")
_PORTA = re.compile(r"^(.+?): (.*?) \((.*)\)\s*$")
_PERFIL = re.compile(
    r"^(\S+?): (.*?) \(sinks: (\d+), sources: (\d+), priority: (\d+), available: (yes|no)\)\s*$")
_CANAL = re.compile(r"^([\w-]+): (\d+) / +(-?\d+)% / (\S+ dB|-inf dB)$")


def _volume_do_longo(valor: str) -> dict[str, Any]:
    canais: dict[str, Any] = {}
    for parte in valor.split(",   "):
        achado = _CANAL.match(parte.strip())
        if achado:
            nome, bruto, pct, db = achado.groups()
            canais[nome] = {"value": int(bruto), "value_percent": f"{pct}%", "db": db}
    return canais


def json_do_longo(longo: str) -> str:
    """O JSON que o `pactl` daria para blocos copiados do texto longo.

    Só lê o que os nós e fluxos têm de campo simples: `State`, `Name`,
    `Description`, `Driver`, `Sample Specification`, `Mute`, `Volume`, `Balance`,
    `Sink`/`Source` (o alvo do fluxo), `Client`, `Corked` e as `Properties`.
    Seções com mais fundo (`Ports`, `Formats`) ficam de fora, como o JSON as
    põe em outra chave.
    """
    objetos: list[dict[str, Any]] = []
    atual: dict[str, Any] | None = None
    em_props = False
    secao_alheia = False
    secao = ""
    for linha in longo.splitlines():
        if not linha.strip():
            continue
        cabeca = _BLOCO.match(linha)
        if cabeca:
            tipo, indice = cabeca.groups()
            atual = {"index": int(indice), "properties": {}}
            atual["_tipo"] = tipo
            objetos.append(atual)
            em_props = False
            secao_alheia = False
            secao = ""
            continue
        if atual is None:
            continue
        fundo = len(linha) - len(linha.lstrip("\t"))
        corpo = linha.strip()
        if fundo == 1:
            em_props = False
            secao_alheia = False
            secao = ""
            chave, _, valor = corpo.partition(":")
            valor = valor.strip()
            if chave == "Properties":
                em_props = True
            elif chave == "Ports":
                secao = "ports"
                atual.setdefault("ports", [])
            elif chave == "Profiles":
                secao = "profiles"
                atual.setdefault("profiles", {})
            elif chave == "Active Port":
                atual["active_port"] = None if valor in ("", "(null)") else valor
            elif chave == "Active Profile":
                atual["active_profile"] = valor
            elif chave == "Formats":
                secao_alheia = True
            elif chave == "State":
                atual["state"] = valor
            elif chave == "Name":
                atual["name"] = valor
            elif chave == "Description":
                atual["description"] = valor
            elif chave == "Driver":
                atual["driver"] = valor
            elif chave == "Sample Specification":
                atual["sample_specification"] = valor
            elif chave == "Mute":
                atual["mute"] = valor == "yes"
            elif chave == "Corked":
                atual["corked"] = valor == "yes"
            elif chave == "Volume":
                atual["volume"] = _volume_do_longo(valor)
            elif chave == "Balance":
                atual["balance"] = float(valor)
            elif chave in ("Sink", "Source"):
                atual[chave.lower()] = int(valor) if valor.isdigit() else valor
            elif chave == "Client":
                atual["client"] = None if valor == "n/a" else valor
            continue
        if secao_alheia:
            continue
        if secao == "ports" and fundo >= 2:
            achada = _PORTA.match(corpo)
            if achada:
                nome, descricao, dados = achada.groups()
                atual["ports"].append({
                    "name": nome, "description": descricao,
                    "availability": ("not available" if "not available" in dados
                                     else "available" if dados.rstrip().endswith("available")
                                     and "not available" not in dados
                                     else "availability unknown")})
            continue
        if secao == "profiles" and fundo >= 2:
            achado = _PERFIL.match(corpo)
            if achado:
                nome, descricao, sinks, sources, prio, disp = achado.groups()
                atual["profiles"][nome] = {
                    "description": descricao, "sinks": int(sinks), "sources": int(sources),
                    "priority": int(prio), "available": disp == "yes"}
            continue
        if em_props and fundo >= 2 and " = " in corpo:
            k, _, v = corpo.partition(" = ")
            atual["properties"][k] = v.strip().strip('"')
        elif fundo == 1 and atual.get("volume") is not None and corpo.startswith("balance"):
            atual["balance"] = float(corpo.split()[1])
    for o in objetos:
        o.pop("_tipo", None)
    return json.dumps(objetos)


def _unidade_do_volume(valor: str) -> str:
    """A unidade em que o ``parse_volume`` do ``pactl`` 16.1 lê um canal."""
    texto = str(valor).strip().lstrip("+-")
    if texto.endswith("%"):
        return "%"
    if texto.lower().endswith("db"):
        return "dB"
    return "fator" if "." in texto else "bruto"


def o_pactl_aceita_os_volumes(valores: Sequence[str]) -> bool:
    """Os canais de um ``set-*-volume`` passam pelo ``parse_volumes`` do ``pactl`` 16.1?

    Ele recusa o comando inteiro (``Inconsistent volume specification.``, rc 1,
    antes de falar com o servidor) quando os canais misturam unidades: ``100%``
    com ``2.0000`` não passa. O dublê que aceita tudo deixou o portão dos
    motores do cabo preso fechado de 14/10 até a rodada 1 da bancada.
    """
    return len({_unidade_do_volume(v) for v in valores}) <= 1

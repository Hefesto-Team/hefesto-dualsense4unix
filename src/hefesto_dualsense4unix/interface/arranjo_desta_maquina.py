#!/usr/bin/env python3
"""O arranjo do computador de QUEM ABRE, na forma que o `mapa-das-portas` desenha."""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import secrets
import threading
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from hefesto_dualsense4unix.interface import pagina_do_mapa

PAGINA = "mapa-das-portas.html"

QUANDO_DE_AGORA = "leitura deste computador · {quando}"

ROTULO_DE_AGORA = "lido agora"
ROTULO_DE_ANTES = "a leitura anterior — ainda é esta"
ROTULO_DA_ANTERIOR = "a leitura anterior"

CHAVE_DA_ENTREGA = "arranjo"

CHAVE_DEPOIS_DE_GRAVAR = "arranjoGravado"

COMO_ABRE = ""
COMO_REEXAME = "releitura"
COMO_GRAVOU = "gravou"

_SAL = secrets.token_bytes(16)
_PREFIXO_DO_ID = "ap-"

Lida = dict[str, tuple[str, str]]

_FILEIRA_DO_HUB = "fileira"
_COLUNA_CURTA = "coluna"
_GRADE = "grade-tras"

_TETO_DA_COLUNA = 2

CABO_DECLARADO = "Extensor, declarado por você"

ENTRADAS_DO_HUB_DECLARADO = 4


def arranjo(
    agora: _dt.datetime | None = None,
    carregar: Callable[[], Any] | None = None,
    ler_o_barramento: Callable[[], Any] | None = None,
    *,
    antes: Mapping[str, tuple[str, str]] | None = None,
    ler_o_serial: Callable[[str], str] | None = None,
) -> dict[str, Any] | None:
    """O arranjo desta máquina, ou ``None`` quando não há o que desenhar."""
    lido = _ler_a_maquina(agora, carregar, ler_o_barramento,
                          antes=antes, ler_o_serial=ler_o_serial)
    return None if lido is None else lido[0]


def _ler_a_maquina(
    agora: _dt.datetime | None = None,
    carregar: Callable[[], Any] | None = None,
    ler_o_barramento: Callable[[], Any] | None = None,
    *,
    antes: Mapping[str, tuple[str, str]] | None = None,
    ler_o_serial: Callable[[str], str] | None = None,
) -> tuple[dict[str, Any], Lida] | None:
    """O :func:`arranjo` e a :data:`Lida` dele, que o reexame seguinte confere."""
    try:
        from hefesto_dualsense4unix.integrations import mapa_das_portas
        from hefesto_dualsense4unix.integrations.censo_do_barramento import (
            ler_o_barramento as _ler,
        )
        from hefesto_dualsense4unix.integrations.entrada_a_entrada import (
            nome_da_entrada,
            rotulos_das_entradas,
        )
        from hefesto_dualsense4unix.utils.maquina import carregar_maquina, entradas_do_mapa
    except Exception:
        return None

    try:
        documento = (carregar or carregar_maquina)()
        declarado = getattr(documento, "mapa", None)
        if declarado is None or not declarado.faces:
            return None
        censo = (ler_o_barramento or _ler)()
        bancada = mapa_das_portas.mesa_do_motor(declarado, censo)
        conectados = censo.conectados()
        ids = identidades(
            conectados, ler_o_serial or mapa_das_portas.serial_do_no, antes,
            lido_em=bancada.mesa.leitura)
        modelos = _modelos(conectados)
    except Exception:
        return None

    mesa = bancada.mesa
    if not mesa.faces:
        return None

    quando = (agora or _dt.datetime.now()).strftime("%d/%m/%Y %Hh%M")
    caminhos = {ids.get(a.id, a.id): mesa.leitura.get(a.id, a.id) for a in mesa.aparelhos}
    faces = _faces(mesa.faces)
    hub_lido = _o_que_ela_declarou_nas_entradas(
        faces, declarado, lambda numero: nome_da_entrada(numero, maquina=documento))
    anterior = (
        {"rotulo": ROTULO_DE_ANTES, "caminho": dict(caminhos)}
        if antes is None
        else {"rotulo": ROTULO_DA_ANTERIOR,
              "caminho": {i: caminho for i, (caminho, _m) in antes.items()}}
    )
    lida = {ids.get(a.id, a.id): (mesa.leitura.get(a.id, a.id), modelos.get(a.id, ""))
            for a in mesa.aparelhos}
    return {
        "quando": QUANDO_DE_AGORA.format(quando=quando),
        "aparelhos": [_aparelho(a, ids.get(a.id, a.id)) for a in mesa.aparelhos],
        "faces": faces,
        "mapa": dict(mesa.mapa),
        "leituras": {
            "agora": {"rotulo": ROTULO_DE_AGORA, "caminho": caminhos},
            "antes": anterior,
        },
        "declarado": _declarado(
            declarado,
            entradas_do_mapa(declarado),
            lambda numero: nome_da_entrada(numero, maquina=documento),
        ),
        "rotulos": rotulos_das_entradas(documento),
        "hubLido": hub_lido,
        "usbDe": dict(bancada.usb_de),
    }, lida


class _ALeituraNaTela:
    """A :data:`Lida` da última leitura entregue à página."""

    def __init__(self) -> None:
        self._trava = threading.Lock()
        self._lida: Lida | None = None

    def ler(self) -> Lida | None:
        with self._trava:
            return None if self._lida is None else dict(self._lida)

    def guardar(self, lida: Mapping[str, tuple[str, str]]) -> None:
        copia = dict(lida)
        with self._trava:
            self._lida = copia


_NA_TELA = _ALeituraNaTela()


def para_a_pagina(**fontes: Any) -> dict[str, Any] | None:
    """A leitura que a página recebe ao abrir — e que vira o «antes» do reexame."""
    return _guardar_e_entregar(_ler_a_maquina(**fontes))


def reexaminar(**fontes: Any) -> dict[str, Any] | None:
    """O «Examinar»: relê a máquina, e o «antes» é a leitura que a página tem."""
    return _guardar_e_entregar(_ler_a_maquina(antes=_NA_TELA.ler(), **fontes))


def depois_de_gravar(**fontes: Any) -> dict[str, Any] | None:
    """O arranjo relido depois de uma gravação do editor — ver"""
    return _guardar_e_entregar(_ler_a_maquina(antes=_NA_TELA.ler(), **fontes))


def _guardar_e_entregar(lido: tuple[dict[str, Any], Lida] | None) -> dict[str, Any] | None:
    """A leitura que vai à página vira o «antes» do próximo «Examinar»."""
    if lido is None:
        return None
    dado, lida = lido
    _NA_TELA.guardar(lida)
    return dado


def js_da_entrega(
    dado: Mapping[str, Any], *, reexame: bool = False, como: str = COMO_ABRE
) -> str:
    """O JavaScript que entrega um arranjo à página — a abertura, o reexame e a"""
    corpo = json.dumps(dado, ensure_ascii=False)
    if reexame:
        como = COMO_REEXAME
    if como not in (COMO_ABRE, COMO_REEXAME, COMO_GRAVOU):
        raise ValueError(f"{como!r} não é um jeito de a página receber o arranjo")
    if como == COMO_GRAVOU:
        return f"window.hefestoArranjo({corpo}, {json.dumps(COMO_GRAVOU)})"
    return f"window.hefestoArranjo({corpo}, {'true' if como == COMO_REEXAME else 'false'})"


def identidades(
    aparelhos: Sequence[Any],
    ler_o_serial: Callable[[str], str],
    antes: Mapping[str, tuple[str, str]] | None = None,
    *,
    lido_em: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """``caminho -> id`` de cada aparelho, o mesmo enquanto ele for o mesmo."""
    modelos = _modelos(aparelhos)
    sementes: dict[str, str] = {}
    for aparelho in aparelhos:
        caminho = aparelho.nome_do_kernel
        serial = (ler_o_serial(aparelho.no) or "").strip()
        if serial:
            sementes[caminho] = f"serial|{modelos[caminho]}|{serial}"
        elif aparelho.vid or aparelho.pid:
            sementes[caminho] = f"modelo|{modelos[caminho]}"
        else:
            sementes[caminho] = ""
    repetidas = Counter(sementes.values())
    parados = {(caminho, modelo): i for i, (caminho, modelo) in (antes or {}).items()}
    fora: dict[str, str] = {}
    for caminho, semente in sementes.items():
        if semente.startswith("serial|") and repetidas[semente] == 1:
            fora[caminho] = _resumo(semente)
    usados = set(fora.values())
    for caminho in sementes:
        de_antes = parados.get(((lido_em or {}).get(caminho, caminho), modelos[caminho]))
        if caminho not in fora and de_antes is not None and de_antes not in usados:
            fora[caminho] = de_antes
            usados.add(de_antes)
    for caminho, semente in sementes.items():
        if caminho in fora:
            continue
        pelo_caminho = _resumo(f"caminho|{modelos[caminho]}|{caminho}")
        resumo = pelo_caminho if not semente or repetidas[semente] > 1 else _resumo(semente)
        fora[caminho] = pelo_caminho if resumo in usados else resumo
        usados.add(fora[caminho])
    return fora


def _modelos(aparelhos: Sequence[Any]) -> dict[str, str]:
    """``caminho -> vid:pid`` — o modelo, que não separa dois iguais."""
    return {a.nome_do_kernel: f"{a.vid}:{a.pid}" for a in aparelhos}


def _resumo(semente: str) -> str:
    feito = hashlib.blake2s(semente.encode("utf-8"), key=_SAL, digest_size=8)
    return _PREFIXO_DO_ID + feito.hexdigest()


def _declarado(
    mapa: Any, numeros: Any, nome_de: Callable[[str], str | None] | None = None
) -> dict[str, dict[str, Any]]:
    """O que ela disse de cada entrada DO MAPA DELA, para o editor da página."""
    saida: dict[str, dict[str, Any]] = {}
    for numero in sorted(numeros):
        porta = mapa.portas.get(numero)
        dito: dict[str, Any] = {}
        if porta is not None and porta.liga:
            dito["liga"] = porta.liga
        if porta is not None and porta.usb:
            dito["usb"] = porta.usb
        nome = nome_de(numero) if nome_de is not None else None
        if nome:
            dito["nome"] = nome
        saida[numero] = dito
    return saida


def _o_que_ela_declarou_nas_entradas(
    faces: list[dict[str, Any]],
    mapa: Any,
    nome_de: Callable[[str], str | None] = lambda _n: None,
) -> dict[str, bool]:
    """Cada face diz de qual entrada pende; o hub sem face ganha a dele; o"""
    from hefesto_dualsense4unix.integrations.entrada_a_entrada import (
        de_quem_pende,
        faces_dos_hubs,
    )
    from hefesto_dualsense4unix.utils.rotulo_da_entrada import (
        frase_do_hub_lido,
        titulo_do_hub,
    )

    pendencias = de_quem_pende(mapa)
    por_numero: dict[str, dict[str, Any]] = {}
    for face in faces:
        for entrada in face["portas"]:
            por_numero.setdefault(entrada["n"], entrada)
            if "filho" in entrada:
                por_numero.setdefault(entrada["filho"]["n"], entrada["filho"])
    hub_lido: dict[str, bool] = {}
    for face in faces:
        dela = pendencias.get(face["nome"])
        if dela is None:
            continue
        face["daEntrada"] = dela.entrada
        face["titulo"] = titulo_do_hub(dela.entrada, nome_de(dela.entrada))
        if dela.lida is not None:
            face["diverge"] = frase_do_hub_lido(dela.lida, nome_de(dela.lida))
        if dela.barramento is not None:
            hub_lido[dela.barramento] = True
    ligadas = {dela.entrada for dela in pendencias.values()}
    for numero, nome in faces_dos_hubs(mapa).items():
        entrada = por_numero.get(numero)
        if entrada is None or numero in ligadas:
            continue
        faces.append({
            "nome": nome,
            "titulo": titulo_do_hub(numero, nome_de(numero)),
            "forma": _FILEIRA_DO_HUB,
            "regiao": "hub",
            "daEntrada": numero,
            "fantasma": True,
            "portas": [
                {"n": f"{numero}.{i}", "usb": entrada["usb"], "onde": "hub", "pos": i}
                for i in range(1, ENTRADAS_DO_HUB_DECLARADO + 1)
            ],
        })
    for numero, entrada in por_numero.items():
        porta = mapa.portas.get(numero)
        if porta is None or porta.liga != "extensor" or "filho" in entrada:
            continue
        entrada["filho"] = {
            "n": f"{numero}a",
            "usb": entrada["usb"],
            "onde": entrada["onde"],
            "esticada": True,
            "cabo": CABO_DECLARADO,
        }
    return hub_lido


def _aparelho(aparelho: Any, identidade: str) -> dict[str, Any]:
    """Um aparelho do motor nos cinco campos que a página LÊ."""
    return {
        "id": identidade,
        "tipo": aparelho.tipo,
        "nome": aparelho.nome,
        "classe": aparelho.classe,
        "cor": pagina_do_mapa.CORES_POR_CLASSE.get(
            aparelho.classe, pagina_do_mapa.COR_SEM_CLASSE),
    }


def _faces(faces: Any) -> list[dict[str, Any]]:
    """As faces do motor mais a FORMA do desenho, que não vem de fonte nenhuma."""
    saida = []
    dona = _dona_da_faixa(faces)
    for face in faces:
        corpo: dict[str, Any] = {
            "nome": face.nome,
            "forma": _forma(face),
            "regiao": face.regiao,
            "portas": [_entrada(e) for e in face.entradas],
        }
        if face.perto:
            corpo["perto"] = True
        if face.alto:
            corpo["alto"] = True
        if face is dona:
            corpo["donaDaFaixaPc"] = True
        saida.append(corpo)
    return saida


def _dona_da_faixa(faces: Any) -> Any:
    """A face do PC com mais entradas, ou ``None`` se nenhuma face é do PC."""
    do_pc = [f for f in faces if f.regiao == "pc"]
    return max(do_pc, key=lambda f: len(f.entradas)) if do_pc else None


def _forma(face: Any) -> str:
    if face.regiao == "hub":
        return _FILEIRA_DO_HUB
    return _COLUNA_CURTA if len(face.entradas) <= _TETO_DA_COLUNA else _GRADE


def _entrada(entrada: Any) -> dict[str, Any]:
    """Uma entrada do motor, sem os campos que ela não tem."""
    corpo: dict[str, Any] = {"n": entrada.n, "usb": entrada.usb, "onde": entrada.onde}
    if entrada.par:
        corpo["par"] = entrada.par
    if entrada.pos is not None:
        corpo["pos"] = entrada.pos
    if entrada.esticada:
        corpo["esticada"] = True
        corpo["cabo"] = CABO_DECLARADO
    if entrada.filho is not None:
        corpo["filho"] = _entrada(entrada.filho)
    return corpo

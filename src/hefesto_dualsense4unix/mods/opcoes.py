"""Os valores das opções que uma modificação declara, guardados em ``<dados>/<id>/opcoes.json``.

A tela escolhe, a modificação lê o mesmo arquivo na sua pasta de dados. Ler nunca levanta: um valor
que o manifesto não aceita (arquivo editado, opção que saiu da versão nova) cai no padrão.
"""
from __future__ import annotations

import contextlib
import json
import os
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from hefesto_dualsense4unix.mods.instalador import InstalacaoRecusadaError, Lugares
from hefesto_dualsense4unix.mods.manifesto import CHAVE_DE_JOGO, COR_HEXA, Manifesto, Opcao

NOME_DO_ARQUIVO = "opcoes.json"

Valor = str | bool | float | list[str]


def caminho(mod_id: str, lugares: Lugares) -> Path:
    return lugares.dados / mod_id / NOME_DO_ARQUIVO


def padrao_de(opcao: Opcao) -> Valor:
    """O que a opção vale sem escolha: o padrão do manifesto, ou o primeiro jeito de cada tipo."""
    if opcao.padrao is not None:
        if opcao.tipo == "cor" and isinstance(opcao.padrao, str):
            return opcao.padrao.lower()
        return list(opcao.padrao) if isinstance(opcao.padrao, list) else opcao.padrao
    if opcao.tipo == "escolha":
        return opcao.escolhas[0]
    if opcao.tipo == "cor":
        return "#ffffff"
    if opcao.tipo == "jogos":
        return []
    return False if opcao.tipo == "ligado" else 0.0


def validar(opcao: Opcao, valor: Any) -> Valor:
    """O valor no tipo da opção, ou a recusa dita em uma frase."""
    if opcao.tipo == "ligado":
        if isinstance(valor, bool):
            return valor
        if str(valor).strip().lower() in ("true", "1", "ligado", "sim"):
            return True
        if str(valor).strip().lower() in ("false", "0", "desligado", "não"):
            return False
        raise InstalacaoRecusadaError(f"«{opcao.rotulo}» é ligado ou desligado.")
    if opcao.tipo == "escolha":
        if valor not in opcao.escolhas:
            raise InstalacaoRecusadaError(f"«{valor}» não é uma das escolhas de «{opcao.rotulo}».")
        return str(valor)
    if opcao.tipo == "cor":
        if not isinstance(valor, str) or not COR_HEXA.match(valor):
            raise InstalacaoRecusadaError(f"«{opcao.rotulo}» pede uma cor no formato #rrggbb.")
        return valor.lower()
    if opcao.tipo == "jogos":
        return _jogos_validos(opcao, valor)
    numero = _numero_valido(opcao, valor)
    if opcao.tipo == "deslizante":
        return _na_faixa_do_deslizante(opcao, numero)
    return numero


def _numero_valido(opcao: Opcao, valor: Any) -> float:
    try:
        numero = float(str(valor).replace(",", "."))
    except ValueError:
        raise InstalacaoRecusadaError(f"«{opcao.rotulo}» pede um número.") from None
    if numero != numero or numero in (float("inf"), float("-inf")):
        raise InstalacaoRecusadaError(f"«{opcao.rotulo}» pede um número.")
    return numero


def _na_faixa_do_deslizante(opcao: Opcao, numero: float) -> float:
    """O número no degrau mais perto do passo; fora da faixa do manifesto, a recusa."""
    minimo, maximo, passo = opcao.minimo, opcao.maximo, opcao.passo
    if minimo is None or maximo is None or passo is None:
        raise InstalacaoRecusadaError(f"«{opcao.rotulo}» não declara a faixa.")
    if not minimo <= numero <= maximo:
        raise InstalacaoRecusadaError(
            f"«{opcao.rotulo}» vai de {minimo:g} a {maximo:g}; {numero:g} está fora.")
    degraus = round((numero - minimo) / passo)
    return min(maximo, round(minimo + degraus * passo, 6))


def _jogos_validos(opcao: Opcao, valor: Any) -> list[str]:
    """A lista de chaves de jogo, sem repetir e na ordem em que veio."""
    if not isinstance(valor, (list, tuple)) or not all(
        isinstance(x, str) and CHAVE_DE_JOGO.match(x) for x in valor
    ):
        raise InstalacaoRecusadaError(f"«{opcao.rotulo}» pede uma lista de jogos.")
    return list(dict.fromkeys(valor))


def _guardados(mod_id: str, lugares: Lugares) -> dict[str, Any]:
    try:
        bruto = json.loads(caminho(mod_id, lugares).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return bruto if isinstance(bruto, dict) else {}


def ler(manifesto: Manifesto, lugares: Lugares) -> dict[str, Valor]:
    """O valor de agora de cada opção: o guardado, se o manifesto o aceita; senão o padrão."""
    guardados = _guardados(manifesto.id, lugares)
    saida: dict[str, Valor] = {}
    for opcao in manifesto.opcoes:
        try:
            saida[opcao.id] = validar(opcao, guardados[opcao.id])
        except (KeyError, InstalacaoRecusadaError):
            saida[opcao.id] = padrao_de(opcao)
    return saida


def guardar(manifesto: Manifesto, opcao_id: str, valor: Any, lugares: Lugares) -> Valor:
    """Valida e grava UMA opção, preservando as outras (arquivo novo e ``rename``, em ``0600``)."""
    opcao = next((o for o in manifesto.opcoes if o.id == opcao_id), None)
    if opcao is None:
        raise InstalacaoRecusadaError(f"«{manifesto.nome}» não tem a opção «{opcao_id}».")
    certo = validar(opcao, valor)
    atuais = ler(manifesto, lugares)
    atuais[opcao_id] = certo
    _gravar(manifesto.id, atuais, lugares)
    return certo


def _gravar(mod_id: str, valores: dict[str, Any], lugares: Lugares) -> None:
    """Arquivo novo e ``rename``, em ``0600``: quem lê nunca vê o arquivo pela metade."""
    destino = caminho(mod_id, lugares)
    destino.parent.mkdir(parents=True, exist_ok=True)
    fd, nome = tempfile.mkstemp(prefix=".opcoes-", suffix=".json", dir=destino.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as arquivo:
            json.dump(valores, arquivo, ensure_ascii=False, indent=2)
            arquivo.write("\n")
        os.chmod(nome, 0o600)
        os.replace(nome, destino)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(nome)
        raise


def herdar(manifesto: Manifesto, antigas: Sequence[str], lugares: Lugares) -> dict[str, Valor]:
    """As escolhas das extensões ``antigas`` que ``manifesto`` aceita, gravadas nas dele.

    Passa a escolha de id igual cujo valor a opção da nova valida. A que já foi feita na nova
    vale mais (fica); o que a nova não tem ou não aceita fica no padrão de produto, e nada se grava.
    Entre duas antigas, a primeira da lista vale. Devolve o que foi herdado.
    """
    feitas = _guardados(manifesto.id, lugares)
    herdadas: dict[str, Valor] = {}
    for opcao in manifesto.opcoes:
        if opcao.id in feitas:
            continue
        for mod_id in antigas:
            bruto = _guardados(mod_id, lugares)
            if opcao.id not in bruto:
                continue
            with contextlib.suppress(InstalacaoRecusadaError):
                herdadas[opcao.id] = validar(opcao, bruto[opcao.id])
                break
    if herdadas:
        _gravar(manifesto.id, {**feitas, **herdadas}, lugares)
    return herdadas


__all__ = ["NOME_DO_ARQUIVO", "Valor", "guardar", "herdar", "ler", "padrao_de", "validar"]

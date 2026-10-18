"""Os valores das opções que uma modificação declara, guardados em ``<dados>/<id>/opcoes.json``.

A tela escolhe, a modificação lê o mesmo arquivo na sua pasta de dados. Ler nunca levanta: um valor
que o manifesto não aceita (arquivo editado, opção que saiu da versão nova) cai no padrão.
"""
from __future__ import annotations

import contextlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from hefesto_dualsense4unix.mods.instalador import InstalacaoRecusadaError, Lugares
from hefesto_dualsense4unix.mods.manifesto import Manifesto, Opcao

NOME_DO_ARQUIVO = "opcoes.json"

Valor = str | bool | float


def caminho(mod_id: str, lugares: Lugares) -> Path:
    return lugares.dados / mod_id / NOME_DO_ARQUIVO


def padrao_de(opcao: Opcao) -> Valor:
    """O que a opção vale sem escolha: o padrão do manifesto, ou o primeiro jeito de cada tipo."""
    if opcao.padrao is not None:
        return opcao.padrao
    if opcao.tipo == "escolha":
        return opcao.escolhas[0]
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
    try:
        numero = float(str(valor).replace(",", "."))
    except ValueError:
        raise InstalacaoRecusadaError(f"«{opcao.rotulo}» pede um número.") from None
    if numero != numero or numero in (float("inf"), float("-inf")):
        raise InstalacaoRecusadaError(f"«{opcao.rotulo}» pede um número.")
    return numero


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
    destino = caminho(manifesto.id, lugares)
    destino.parent.mkdir(parents=True, exist_ok=True)
    fd, nome = tempfile.mkstemp(prefix=".opcoes-", suffix=".json", dir=destino.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as arquivo:
            json.dump(atuais, arquivo, ensure_ascii=False, indent=2)
            arquivo.write("\n")
        os.chmod(nome, 0o600)
        os.replace(nome, destino)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(nome)
        raise
    return certo


__all__ = ["NOME_DO_ARQUIVO", "Valor", "guardar", "ler", "padrao_de", "validar"]

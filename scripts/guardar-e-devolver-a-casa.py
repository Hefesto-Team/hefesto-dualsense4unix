#!/usr/bin/env python3
"""Guarda a casa inteira do Hefesto, confere a máquina limpa e devolve tudo.

ESQUECER-OS-CONTROLES-01, o alcance que cresceu (25/09/2026). O pedido dela:
*«os perfis e demais configs poderiam ser selecionado e jogados na mesma pasta
de backup. dariamos um uninstall completo um resete completo nos 4 controles e
testaríamos tudo. […] Aí depois restauramos os perfis.»*  (noqa-acento: citação literal dela)

O fluxo, e este script serve a cada passo::

    python3 scripts/guardar-e-devolver-a-casa.py guardar     # com a Steam fechada
    ./uninstall.sh --purge-config --yes
    python3 scripts/guardar-e-devolver-a-casa.py limpa       # «a máquina está limpa?»
    ./install.sh --yes
    (o teste: a primeira vez de verdade, com os controles resetados)
    python3 scripts/guardar-e-devolver-a-casa.py devolver    # com a Steam fechada

POR QUE UM SCRIPT DO REPOSITÓRIO, e com o ``python3`` do sistema: depois do
uninstall o comando do Hefesto não existe (a ``.venv`` sai junto). O dono do
inventário é ``src/hefesto_dualsense4unix/utils/memoria_dos_controles.py``, e
este script o carrega PELO CAMINHO — ele é só biblioteca padrão, como os
módulos de ``integrations/`` que o próprio uninstall roda avulsos.

A parte do root (os pareamentos Bluetooth dos controles, as cópias de
pareamento, o diário do root) passa por ``sudo -A`` quando há ``SUDO_ASKPASS``
e por ``sudo -n`` quando não há. Senha no terminal, nunca: sem nenhum dos dois o
script recusa ANTES de tocar em qualquer coisa.
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

RAIZ = Path(__file__).resolve().parents[1]
DONO = RAIZ / "src" / "hefesto_dualsense4unix" / "utils" / "memoria_dos_controles.py"


def carregar_o_dono() -> ModuleType:
    """O inventário, pelo caminho — sem o pacote instalado."""
    spec = importlib.util.spec_from_file_location("_hefesto_memoria", DONO)
    if spec is None or spec.loader is None:
        raise SystemExit(f"não achei o dono do inventário em {DONO}")
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["_hefesto_memoria"] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def principal(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="guardar-e-devolver-a-casa.py",
        description="Guarda a casa inteira do Hefesto, confere a máquina limpa "
                    "depois do uninstall, e devolve tudo por cima do install novo.",
    )
    sub = p.add_subparsers(dest="verbo", required=True)
    g = sub.add_parser("guardar", help="copia a casa e esquece os controles (Steam fechada)")
    g.add_argument("--seco", action="store_true", help="só diz o que faria")
    sub.add_parser("limpa", help="depois do uninstall: sobrou algo do Hefesto? "
                   "(sai 0 limpa, 1 sobrou, 3 não sei: falta privilégio)")
    d = sub.add_parser("devolver", help="devolve a pasta (a mais nova, se não disser qual)")
    d.add_argument("pasta", nargs="?", default=None)
    d.add_argument("--seco", action="store_true", help="só diz o que faria")
    sub.add_parser("pastas", help="lista as pastas guardadas")
    a = p.parse_args(argv)

    m = carregar_o_dono()
    raizes = m.Raizes.do_ambiente()
    sistema = m.Sistema()
    try:
        m.conferir_o_ensaio(raizes)
        if a.verbo == "guardar":
            relato = m.guardar(raizes, m.CASA, sistema, seco=a.seco)
        elif a.verbo == "devolver":
            relato = m.devolver(raizes, sistema, a.pasta, seco=a.seco)
        elif a.verbo == "pastas":
            for pasta in m.pastas_guardadas(raizes):
                print(pasta)
            return 0
        else:
            # Três respostas, e «não sei» é uma delas: o BlueZ só o root lê, e
            # sem privilégio a pergunta não tem resposta — contá-lo como
            # «sobrou» faria toda máquina de verdade reprovar; como «limpa»,
            # esconderia um controle ainda pareado.
            rastros = m.conferir_a_casa(raizes, sistema)
            defeitos = [r for r in rastros if not r.de_proposito and not r.nao_sei]
            incertos = [r for r in rastros if r.nao_sei]
            for r in rastros:
                marca = ("NÃO SEI" if r.nao_sei
                         else "de propósito" if r.de_proposito else "SOBROU")
                print(f"{marca:<13} {r.onde} — {r.o_que}")
            if defeitos:
                return 1
            if incertos:
                print("não sei se está limpa: há lugar que só o root lê (acima)")
                return 3
            if not rastros:
                print("limpa: nenhum rastro do Hefesto nos lugares do inventário")
            else:
                print("limpa: só o que o uninstall deixa de propósito")
            return 0
    except m.RecusaError as erro:
        print(f"recusado: {erro}", file=sys.stderr)
        return 2
    for linha in relato.linhas:
        print(linha)
    return 0


if __name__ == "__main__":
    sys.exit(principal())

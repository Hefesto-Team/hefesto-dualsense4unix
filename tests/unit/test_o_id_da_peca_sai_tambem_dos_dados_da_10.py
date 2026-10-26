#!/usr/bin/env python3
"""O ID da peça sai também dos dados da 10: nenhuma linha da guarda leva a chave `id`.

O-ID-DA-PECA-SAI-TAMBEM-DOS-DADOS-DA-10-01, depois da D-2610-O-ID-DA-PECA-SAI-DA-TELA: a tela não
mostra mais o endereço de rádio de cada controle, e o `perfis_web` não o monta mais. A chave do
dado continua sendo o `uniq`, que vai no `data-hef-uniq`.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
if str(RAIZ / "src") not in sys.path:
    sys.path.insert(0, str(RAIZ / "src"))

from hefesto_dualsense4unix.app.actions import perfis_web
from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile

UNIQS = [f"aa:bb:cc:00:00:0{n}" for n in range(1, 5)]
TRANSPORTES = [("usb", "bt", "usb", "bt"), ("usb",) * 4, ("bt",) * 4]


def _mesa(transportes: tuple[str, ...]) -> list[dict[str, str]]:
    return [{"uniq": u, "rotulo": f"P{n} • {t.upper()}", "plastico": "#ffffff", "nome": "DualSense",
             "transporte": t}
            for n, (u, t) in enumerate(zip(UNIQS, transportes, strict=True), start=1)]


@pytest.mark.parametrize("transportes", TRANSPORTES, ids="-".join)
def test_nenhuma_linha_da_guarda_leva_o_id(transportes: tuple[str, ...]) -> None:
    perfil = Profile(name="meu_perfil", match=MatchAny())
    pacote = perfis_web.pacote_da_aba([perfil], ativo="meu_perfil", mesa=_mesa(transportes))
    guarda = pacote["guarda"]
    assert [linha["uniq"] for linha in guarda] == UNIQS
    for linha in guarda:
        assert "id" not in linha, f"a linha do {linha['uniq']} voltou a levar o ID da peça: {linha}"


def test_o_formatador_do_id_nao_existe_mais() -> None:
    assert not hasattr(perfis_web, "_id_visivel")

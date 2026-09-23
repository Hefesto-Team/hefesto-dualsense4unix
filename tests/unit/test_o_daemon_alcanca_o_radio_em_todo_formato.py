"""O daemon alcança o socket de Bluetooth em todo formato — o medidor do ar depende disso.

INSTALL-E-UNINSTALL-DO-RADIO-01 (23/09/2026), o pedido P-3 da AR-MEDIDO-01. O
medidor do rádio (os Hz de cada controle e os canais do AFH, que a seção
aprovada por ela mostra) abre um socket HCI cru e faz ioctls de leitura. Duas
condições o install tem de CONTINUAR cumprindo, e uma que faltava:

1. a unit do daemon sem `PrivateNetwork=yes` (fora do netns inicial o kernel
   devolve EAFNOSUPPORT ao socket de Bluetooth) e, se um dia ganhar
   `RestrictAddressFamilies`, com o AF_BLUETOOTH na lista — o bloco do broker
   (`PrivateNetwork=yes` com AF_UNIX) NÃO pode ser copiado para cá;
2. o Flatpak, onde o daemon roda dentro do sandbox, com `--allow=bluetooth`
   (o seccomp) e `--share=network` (o netns) — decisão de quem coordena.

A MORDIDA, medida: tirar o `--allow=bluetooth` do manifesto reprova o teste 2;
pôr `PrivateNetwork=yes` na unit do daemon, o 1.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
UNIT = RAIZ / "assets" / "hefesto-dualsense4unix.service"
MANIFESTO = RAIZ / "flatpak" / "io.github.hefesto_team.hefesto_dualsense4unix.yml"


def _diretivas(texto: str) -> dict[str, str]:
    saida: dict[str, str] = {}
    for linha in texto.splitlines():
        linha = linha.strip()
        if not linha or linha.startswith(("#", ";", "[")) or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        saida[chave.strip()] = valor.strip()
    return saida


def test_a_unit_do_daemon_nao_fecha_o_socket_de_bluetooth() -> None:
    diretivas = _diretivas(UNIT.read_text(encoding="utf-8"))
    assert "daemon start" in diretivas.get("ExecStart", ""), (
        "controle: esta não é mais a unit que roda o daemon"
    )
    assert diretivas.get("PrivateNetwork", "no").lower() not in ("yes", "true", "1", "on"), (
        "PrivateNetwork=yes tira o daemon do netns inicial e o kernel recusa o socket "
        "de Bluetooth: o medidor do ar passaria a dizer «não sei» em todo adaptador"
    )
    familias = diretivas.get("RestrictAddressFamilies")
    if familias is not None:
        assert not familias.startswith("~") and "AF_BLUETOOTH" in familias.split(), (
            f"RestrictAddressFamilies={familias} deixa o AF_BLUETOOTH de fora"
        )


def _finish_args() -> list[str]:
    texto = MANIFESTO.read_text(encoding="utf-8")
    bloco = texto[texto.index("\nfinish-args:\n") : texto.index("\nmodules:\n")]
    return re.findall(r"^\s*-\s+(--\S+)", bloco, re.MULTILINE)


@pytest.mark.parametrize("permissao", ["--allow=bluetooth", "--share=network"])
def test_o_flatpak_deixa_o_daemon_medir_o_ar(permissao: str) -> None:
    args = _finish_args()
    assert "--device=all" in args, "controle: o bloco de finish-args não foi lido"
    assert permissao in args, (
        f"sem {permissao} no finish-args, o daemon dentro do sandbox não abre o socket "
        "de Bluetooth e o medidor do ar responde «não sei» em todo adaptador"
    )

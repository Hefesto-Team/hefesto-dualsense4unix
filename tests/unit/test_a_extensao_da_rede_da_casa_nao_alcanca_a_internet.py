"""A extensão que pede a rede da casa não alcança a internet
(A-EXTENSAO-QUE-PEDE-A-REDE-DA-CASA-NAO-ALCANCA-A-INTERNET-01).

Medido em 26/11/2026 (``medir_rede_local.py`` da leva): a linha da caixa com ``rede:local`` era
igual, argumento por argumento, à de ``rede:internet``; o «sim» dizia «Usar a rede desta casa.» e a
caixa entregava a rota padrão do ``pasta``. Agora, entre o ``pasta`` e o ``bwrap``, a caixa com
``rede:local`` tira toda rota e põe de volta só as faixas privadas e link-local; o ``bwrap`` abre
depois, sem poder sobre a rede. Sem o ``pasta`` a caixa segue no espaço da casa, e o «sim» já diz
que a rede inclui a internet e esta máquina (``frase_da_rede``).

MORDIDAS (26/11/2026, executadas sobre a cura e devolvidas):

- sem o ``so_a_casa`` no ``comando_na_caixa``: ``test_a_linha_da_rede_local_leva_o_filtro``;
- sem o ``route flush`` no filtro: ``test_dentro_do_filtro_so_a_rede_da_casa_tem_rota``;
- a frase do ``rede:local`` de volta com «inclui a internet»:
  ``test_a_frase_da_rede_local_nao_promete_a_internet``.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from hefesto_dualsense4unix.mods import supervisor as sup
from hefesto_dualsense4unix.mods.manifesto import Manifesto

_PASTA = "/usr/bin/pasta"


def _manifesto(rede: str) -> Manifesto:
    return Manifesto.model_validate({
        "id": "exemplo", "nome": "Exemplo", "versao": "0.1.0", "api": ">=1,<3",  # (noqa-acento)
        "licenca": "MIT", "tipos": ["processo"], "processo": {"executar": ["python3", "m.py"]},
        "permissoes": [f"rede:{rede}"],  # (noqa-acento)
    })


def _linha(rede: str, tmp_path: Path) -> list[str]:
    return sup.comando_na_caixa(
        bwrap="bwrap", comando=["python3", "m.py"], codigo=tmp_path / "c", dados=tmp_path / "d",
        porta=tmp_path / "p.sock", manifesto=_manifesto(rede), casa=tmp_path / "h", execucao=(),
        pasta=_PASTA, ocupada=lambda _p, _u: False)


def test_a_linha_da_rede_local_leva_o_filtro(tmp_path: Path) -> None:
    local = _linha("local", tmp_path)
    fim_do_pasta = local.index("--")
    assert local[0] == _PASTA
    assert local[fim_do_pasta + 1:fim_do_pasta + 5] == sup.linha_da_rede_da_casa()
    assert local[fim_do_pasta + 5] == "bwrap"
    internet = _linha("internet", tmp_path)
    assert sup.SO_A_REDE_DA_CASA not in internet
    assert internet[internet.index("--") + 1] == "bwrap"


def test_a_frase_da_rede_local_nao_promete_a_internet(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sup, "rede_propria_da_caixa", lambda: _PASTA)
    assert sup.A_REDE_INCLUI_A_INTERNET not in sup.frase_da_rede(_manifesto("local"))
    assert sup.frase_da_rede(_manifesto("internet")) == sup.A_REDE_INCLUI_A_INTERNET
    monkeypatch.setattr(sup, "rede_propria_da_caixa", lambda: None)
    assert sup.frase_da_rede(_manifesto("local")) == sup.A_REDE_INCLUI_A_MAQUINA


_ESPACO = (
    "ip link add d0 type dummy && ip link set d0 up && ip link set lo up && "
    "ip addr add 192.168.50.2/24 dev d0 && ip route add default via 192.168.50.1 dev d0 && "
    "ip route add 8.8.0.0/16 via 192.168.50.1 dev d0 && "
    'exec sh -c "$0" rede-da-casa sh -c "$1"'
)
_OLHAR = (
    "for alvo in 1.1.1.1 8.8.8.8 192.168.7.7 10.1.2.3 172.20.0.1 169.254.1.1; do "
    'if ip route get "$alvo" >/dev/null 2>&1; then echo "$alvo rota"; '
    'else echo "$alvo sem"; fi; done'
)


def test_dentro_do_filtro_so_a_rede_da_casa_tem_rota() -> None:
    """Num espaço de rede de mentira com rota padrão e uma rota pública a mais, como o ``pasta``
    copia da casa, o filtro deixa só as faixas da casa."""
    if shutil.which("unshare") is None or shutil.which("ip") is None:
        pytest.skip("sem unshare ou ip")
    if subprocess.run(["unshare", "-rn", "true"], capture_output=True, check=False).returncode:
        pytest.skip("o espaço de usuário sem privilégio não abre aqui")
    feito = subprocess.run(
        ["unshare", "-rn", "sh", "-c", _ESPACO, sup.SO_A_REDE_DA_CASA, _OLHAR],
        capture_output=True, text=True, timeout=30, check=False)
    assert feito.returncode == 0, feito.stderr
    visto = dict(linha.split() for linha in feito.stdout.splitlines())
    assert visto == {"1.1.1.1": "sem", "8.8.8.8": "sem", "192.168.7.7": "rota",
                     "10.1.2.3": "rota", "172.20.0.1": "rota", "169.254.1.1": "rota"}, visto


def test_sem_o_ip_a_extensao_da_rede_local_nao_liga(tmp_path: Path) -> None:
    feito = subprocess.run(["sh", "-c", sup.SO_A_REDE_DA_CASA, "rede-da-casa", "echo", "abriu"],
                           env={"PATH": str(tmp_path)}, capture_output=True, text=True,
                           timeout=10, check=False, executable="/bin/sh")
    assert feito.returncode != 0 and "abriu" not in feito.stdout
    assert "a extensão não liga" in feito.stderr

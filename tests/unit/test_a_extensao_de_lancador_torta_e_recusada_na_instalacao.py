"""A extensão de lançador com o manifesto torto é recusada na instalação, com a frase (20/10/2026).

Medido na caçada das extensões: uma extensão de lançador escrita pelo guia, sem o ``rotulo``,
instalava, ligava e nunca aparecia na aba Experimental, porque o conferidor do bloco só rodava no
censo, que a deixava de fora calado. A porta de entrada (``instalar``) confere agora o mesmo bloco
com o mesmo conferidor, e o tipo, o bloco e a permissão ``lancador`` andam juntos.

MORDIDA (executada à mão em 20/10): tirada a chamada de ``_conferir_o_lancador`` do ``instalar``,
os quatro casos da recusa reprovam (a instalação passa e o registro ganha a extensão).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from hefesto_dualsense4unix.cli import cmd_mod
from hefesto_dualsense4unix.integrations import censo_dos_lancadores as censo
from hefesto_dualsense4unix.mods.instalador import (
    InstalacaoRecusadaError,
    Lugares,
    instalar,
    ler_registro,
    ligar,
)
from tests.unit import test_as_modificacoes_rodam_fora_do_daemon as _base

curto, lar = _base.curto, _base.lar

_BLOCO_CERTO: dict[str, Any] = {"rotulo": "Meu lançador", "comandos": ["meulancador"]}


def _pasta(curto: Path, nome: str, **campos: Any) -> Path:
    """Uma extensão só de lançador, com os campos do manifesto ajustados (``None`` tira o campo)."""
    dado: dict[str, Any] = {
        "id": nome, "nome": "Meu lançador", "api": ">=2,<3", "licenca": "MIT",
        "versao": "0.1",  # (noqa-acento): chave do contrato
        "tipos": ["lancador"],
        "permissoes": ["lancador"],  # (noqa-acento): chave do contrato
        "lancador": _BLOCO_CERTO,
    }
    for chave, valor in campos.items():
        if valor is None:
            dado.pop(chave, None)
        else:
            dado[chave] = valor
    pasta = curto / f"fonte-{nome}"
    pasta.mkdir()
    (pasta / "hefesto-mod.json").write_text(json.dumps(dado), encoding="utf-8")
    return pasta


@pytest.mark.parametrize("campos, frase", [
    ({"lancador": {"comandos": ["meulancador"]}}, "«lancador.rotulo» precisa ter de 1 a 60"),
    ({"lancador": {"rotulo": "X"}}, "sem «atalhos» nem «comandos»"),
    ({"lancador": {**_BLOCO_CERTO, "ordem": 0}}, "«ordem», que não existe"),
    ({"lancador": None}, "o tipo «lancador» sem o bloco «lancador»"),
    ({"tipos": ["tema"], "tema": {}}, "o bloco «lancador» sem o tipo «lancador»"),
    ({"permissoes": []},  # (noqa-acento): chave do contrato
     "o bloco «lancador» sem a permissão «lancador»"),
])
def test_o_manifesto_de_lancador_torto_e_recusado_com_a_frase(
    lar: Lugares, curto: Path, campos: dict[str, Any], frase: str
) -> None:
    pasta = _pasta(curto, "meu", **campos)
    with pytest.raises(InstalacaoRecusadaError, match=frase):
        instalar(str(pasta), lugares=lar)
    assert "meu" not in ler_registro(lar.registro)
    assert not (lar.codigo / "meu").exists()


def test_o_bloco_certo_instala_e_aparece_no_censo(lar: Lugares, curto: Path) -> None:
    instalar(str(_pasta(curto, "meu")), lugares=lar)
    ligar("meu", permissoes_vistas=["lancador"], lugares=lar)
    (item,) = censo.lancadores_das_extensoes(lar)
    assert item.bloco.rotulo == "Meu lançador"


def test_ligar_a_extensao_sem_processo_nao_promete_servico(lar: Lugares, curto: Path) -> None:
    instalar(str(_pasta(curto, "meu")), lugares=lar)
    saiu = CliRunner().invoke(cmd_mod.app, ["ligar", "meu", "--sim"])
    assert saiu.exit_code == 0, saiu.output
    assert "aba Experimental" in saiu.output
    assert "o serviço abre" not in saiu.output

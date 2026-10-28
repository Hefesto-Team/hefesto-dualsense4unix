"""O adaptador que só não está ligado ao computador é ``desligado``: some da 08 e fica apagado."""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.interface import desenho_da_experimental as exp
from hefesto_dualsense4unix.interface.pacotes import a08_conexoes
from hefesto_dualsense4unix.mods import porta

CONEXOES = "conexoes"  # (noqa-acento)
LIGUE = "Ligue o adaptador USB da Lovense"
SEM_PERMISSAO = "O adaptador USB está sem permissão"


def _estado(estado: str, motivo: str) -> dict[str, Any]:
    return porta.estado_dos_acessorios("intiface", {
        "ligado": True,
        "nivel": 0,
        "aparelhos": [],
        CONEXOES: [{"id": "usb", "tipo": "Adaptador USB", "transporte": "usb",
                    "estado": estado, "motivo": motivo}],
    })


def _na_janela(estado: dict[str, Any]) -> str:
    return exp.agora_html([CONEXOES], estado)


def test_o_contrato_aceita_o_desligado_com_o_motivo() -> None:
    conexao = _estado("desligado", LIGUE)[CONEXOES][0]
    assert (conexao["estado"], conexao["motivo"]) == ("desligado", LIGUE)


def test_o_adaptador_ausente_nao_gera_linha_na_08() -> None:
    ausente = _estado("desligado", LIGUE)
    assert a08_conexoes.html_do_agora_das_extensoes([("Lovense", ausente)]) == ""


def test_o_adaptador_ausente_fica_apagado_na_janela_com_o_motivo_na_dica() -> None:
    janela = _na_janela(_estado("desligado", LIGUE))
    assert f'data-dica="{LIGUE}"' in janela
    assert 'class="ic c-mudo"' in janela and "est-mudo" in janela and "Desligado" in janela
    assert "laranja" not in janela and "Falhou" not in janela


@pytest.mark.parametrize("motivo", [SEM_PERMISSAO, "Adaptador sem suporte"])
def test_a_falha_de_verdade_segue_laranja_na_08_e_na_janela(motivo: str) -> None:
    estado = _estado("falhou", motivo)
    linha = a08_conexoes.html_do_agora_das_extensoes([("Lovense", estado)])
    assert linha.count('class="ext-linha ext-acessorio"') == 1
    assert f'data-dica="{motivo}"' in linha
    assert 'class="ic c-laranja"' in linha and "est-laranja" in linha and "Falhou" in linha
    assert "via Lovense" in linha
    janela = _na_janela(estado)
    assert 'class="ic c-laranja"' in janela and "Falhou" in janela

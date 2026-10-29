"""A JOGAR: cada modo do Desligado leva o desenho dele dentro do botão, como os do Ligado.

Pedido de 29/10/2026: Nativo com o DualSense Edge, Steam Input com o símbolo da Steam e
Navegação com teclado e mouse, no traço dos desenhos da interface (`assets/control-svg/`).
A mordida: tirar uma das três chaves do `SILHUETAS` da `aba01.py` reprova o desenho e o
gerador.
"""
from __future__ import annotations

import re

import pytest

from hefesto_dualsense4unix.interface import aba01, onde

DESENHOS = {"nativo": "dualsense-edge.svg", "steam": "steam.svg",
            "navegacao": "teclado-e-mouse.svg"}


def test_cada_modo_do_desligado_tem_o_arquivo_dele() -> None:
    assert [m["chave"] for m in aba01.DO_DESLIGADO] == list(DESENHOS)
    for chave, arquivo in DESENHOS.items():
        assert aba01.SILHUETAS[chave] == (arquivo, "traco"), chave
        assert (aba01.ARTE_DOS_CONTROLES / arquivo).is_file(), arquivo


@pytest.mark.parametrize("publicado", [False, True], ids=["desenho", "publicado"])
def test_o_botao_de_cada_modo_do_desligado_desenha_o_dele(publicado: bool) -> None:
    doc = onde.pagina("01-jogar.html", publicado=publicado).read_text(encoding="utf-8")
    fileira = doc.split('class="hef-modo so-desligado"', 1)[1].split("</div>", 1)[0]
    for m in aba01.DO_DESLIGADO:
        botao = re.search(rf'<span class="degrau[^"]*"[^>]*data-hef-quando="{m["chave"]}"'
                          rf'[^>]*>(.*?)</span></span>', fileira, re.S)
        assert botao, m["chave"]
        assert botao.group(1) == (aba01.silhueta(m["chave"])
                                  + f'<span class="{aba01.ROTULO_DO_MODO}">{m["rot"]}'), m["chave"]

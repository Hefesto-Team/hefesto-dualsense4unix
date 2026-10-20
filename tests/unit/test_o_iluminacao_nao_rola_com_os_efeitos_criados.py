"""A Iluminação não rola com os efeitos criados: a variante de 20/10/2026, que espera a escolha.

A sprint O-ILUMINACAO-NAO-ROLA-COM-OS-EFEITOS-CRIADOS-01 mediu no piloto, a 1212 px, a aba 04
rolando na vertical a partir do terceiro efeito de luz criado. A variante troca os chips, um por
efeito, por um chip só com a contagem e os nomes na dica.

MORDIDA (executada): com os chips de um em um de volta no `#seus-efeitos`, reprova
`test_um_chip_so_com_a_contagem`.
"""

from __future__ import annotations

import difflib
import pathlib
import re

RAIZ = pathlib.Path(__file__).resolve().parents[2]
BASE = RAIZ / "mockup" / "04-iluminacao.html"
VARIANTE = RAIZ / "mockup" / "variantes" / "04-seus-efeitos-A-a-contagem-com-os-nomes-na-dica.html"
LISTA = re.compile(r'<span class="meus" id="seus-efeitos"[^>]*>(.*?)</span></span>', re.S)


def test_um_chip_so_com_a_contagem() -> None:
    lista = LISTA.search(VARIANTE.read_text(encoding="utf-8"))
    assert lista, "o #seus-efeitos sumiu da variante"
    chips = re.findall(r'<span class="meu[^"]*"[^>]*>', lista.group(1))
    assert len(chips) == 1, chips
    assert 'class="meu conta"' in chips[0]
    assert re.search(r"Seus efeitos: \d+", lista.group(1))
    assert "Alerta vermelho" in chips[0] and "lista do Efeito" in chips[0]


def test_a_variante_so_muda_o_chip_e_a_regra() -> None:
    base = BASE.read_text(encoding="utf-8").splitlines()
    variante = VARIANTE.read_text(encoding="utf-8").splitlines()
    mudou = [d[1:] for d in difflib.unified_diff(base, variante, lineterm="", n=0)
             if d[:1] in "+-" and not d.startswith(("+++", "---"))]
    assert all("seus-efeitos" in d or "VARIANTE" in d or "contagem" in d or ".meu.conta" in d
               or "Seus efeitos" in d for d in mudou), mudou

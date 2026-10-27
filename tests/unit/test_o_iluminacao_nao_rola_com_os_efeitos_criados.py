"""A Iluminação não rola com os efeitos criados: a variante A, escolhida em 20/10/2026.

A sprint O-ILUMINACAO-NAO-ROLA-COM-OS-EFEITOS-CRIADOS-01 mediu no piloto, a 1212 px, a aba 04
rolando na vertical a partir do terceiro efeito de luz criado (o miolo com 653 de 618 px): um
chip por efeito quebrava a linha da barra «Criar efeitos novos». A cura é do pacote: um chip só,
«Seus efeitos: N», com os nomes na dica; o desenho da 04 sai dele.

MORDIDA (executada em 21/10/2026): com o `html_dos_efeitos` de volta a um chip por efeito,
`test_um_chip_so_com_a_contagem` e `test_o_desenho_tem_o_chip_da_contagem` reprovam.
"""

from __future__ import annotations

import pathlib
import re

import pytest


from hefesto_dualsense4unix.interface.pacotes import a04_iluminacao as a04

RAIZ = pathlib.Path(__file__).resolve().parents[2]
DESENHO = RAIZ / "src/hefesto_dualsense4unix/interface/paginas/04-iluminacao.html"
LISTA = re.compile(r'<span class="meus" id="seus-efeitos"[^>]*>(.*?)</span></span>', re.S)
NOMES = ["Alerta vermelho", "Respiro calmo", "Passos na neve", "Trovão", "Portão",
         "Chuva fina", "Sino", "Tambor", "Brasa", "Mar", "Neon", "Aurora"]


def _biblioteca(n: int) -> dict[str, dict[str, object]]:
    return {nome: {"nome": nome, "base": ("piscar", "respirar")[i % 2],
                   "parametros": {"cores": "#FF0000", "ritmo": 3}}
            for i, nome in enumerate(NOMES[:n])}


@pytest.mark.parametrize("n", [1, 2, 3, 8, 12])
def test_um_chip_so_com_a_contagem(n: int) -> None:
    html = a04.html_dos_efeitos(_biblioteca(n))
    chips = re.findall(r'<span class="meu[^"]*"[^>]*>', html)
    assert len(chips) == 1, chips
    assert 'class="meu conta"' in chips[0]
    assert f"Seus efeitos: {n}<" in html
    for nome in NOMES[:n]:
        assert nome in chips[0], f"{nome} fora da dica"
    assert "lista do Efeito" in chips[0]


def test_sem_efeito_criado_nao_ha_chip() -> None:
    assert a04.html_dos_efeitos({}) == ""


def test_o_desenho_tem_o_chip_da_contagem() -> None:
    texto = DESENHO.read_text(encoding="utf-8")
    lista = LISTA.search(texto)
    assert lista, "o #seus-efeitos sumiu do desenho"
    assert len(re.findall(r'<span class="meu[^"]*"', lista.group(1))) == 1
    assert re.search(r"Seus efeitos: \d+$", lista.group(1))
    assert ".criar .meu.conta{cursor:help;white-space:nowrap}" in texto

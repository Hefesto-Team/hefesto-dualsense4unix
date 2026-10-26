"""O «Ligado na entrada» do mapa diz a entrada pelo dono (O-LIGADO-NA-ENTRADA-...-01).

Em Conexões, na tela de mapear entradas, o hub dizia «Ligado na entrada 15» com uma constante e o
número, fora do dono da grafia (`utils/rotulo_da_entrada`): em minúscula e sem o nome dado à
entrada. Agora a frase sai da `rotulo_da_entrada` («Ligado na Entrada 15», «Ligado na entrada
Meio»), e a régua do dono (`test_a_costura_da_onda_2.py`) enxerga a composição por constante.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from hefesto_dualsense4unix.interface import conexoes, logica_do_mapa
from tests.unit.test_a_costura_da_onda_2 import _composicoes_da_palavra

RAIZ = Path(__file__).resolve().parents[2]


def _o_mapa(extensoes: dict[str, str], nomes_das_entradas: dict[str, str] | None = None,
            *, aberta: bool = False) -> str:
    return conexoes.html_do_mapa(
        [{"nome": "Traseira", "portas": ["14", "15"]}],
        quem_esta={},
        extensoes=extensoes,
        veredito_de=lambda n, e: ("", "", ""),
        rotulos={"vazia": "vazia", "por_extensao": "por extensão",
                 "nova_entrada": "Acrescentar entrada"},
        dicas={"esticada": "", "enumera": "", "nova_entrada": ""},
        nomes_das_entradas=nomes_das_entradas,
        pergunta={"aberta": aberta, "entradas": ["14", "15"]} if aberta else None,
    )


def _o_ligado(html: str) -> str:
    achado = re.search(r'<span class="mm-ligado">(.*?)</span>', html)
    assert achado, "o hub perdeu a frase de onde está ligado"
    return re.sub(r"<[^>]+>", "", achado.group(1))


def test_a_entrada_sem_nome_diz_entrada_e_o_numero() -> None:
    assert _o_ligado(_o_mapa({"15": "15a"})).startswith("Ligado na Entrada 15")


def test_a_entrada_com_nome_diz_o_nome_que_ela_deu() -> None:
    assert _o_ligado(_o_mapa({"15": "15a"}, {"15": "Meio"})).startswith("Ligado na entrada Meio")


def test_o_nome_que_so_repete_o_numero_nao_e_nome() -> None:
    for repetido in ("15", "Entrada 15", "entrada 15"):
        dito = _o_ligado(_o_mapa({"15": "15a"}, {"15": repetido}))
        assert dito.startswith("Ligado na Entrada 15"), repetido


def test_o_negrito_e_o_da_entrada_e_o_artigo_fica_fora_como_no_motor() -> None:
    """A forma do motor do arranjo (`arranjo_da_mesa`): «na <b>Entrada 3</b>», o artigo fora."""
    assert "Ligado na <b>Entrada 15</b> " in _o_mapa({"15": "15a"})
    assert "Ligado na <b>entrada Meio</b> " in _o_mapa({"15": "15a"}, {"15": "Meio"})


def test_a_pergunta_do_hub_diz_cada_entrada_pelo_dono() -> None:
    """Prova da D-2110-O-LIGADO-NA-ENTRADA-SE-DIZ-PELO-DONO."""
    html = _o_mapa({}, {"15": "Meio"}, aberta=True)
    opcoes = re.findall(r'<option value="(\d+)">([^<]*)</option>', html)
    assert opcoes == [("14", "Entrada 14"), ("15", "Meio")]
    assert re.search(r'<label class="hub-rot">Ligado\s', html)


def test_cada_opcao_da_pergunta_abre_com_maiuscula() -> None:
    """Cada opção da lista é uma linha: abre com maiúscula, inclusive o nome dado em minúscula."""
    html = _o_mapa({}, {"14": "meio"}, aberta=True)
    opcoes = re.findall(r'<option value="\d+">([^<]*)</option>', html)
    assert opcoes and all(o[:1].isupper() for o in opcoes), opcoes


def test_a_constante_da_frase_velha_saiu() -> None:
    assert not hasattr(logica_do_mapa, "ROTULO_LIGADO_NA_ENTRADA")
    fonte = (RAIZ / "src/hefesto_dualsense4unix/interface/conexoes.py").read_text(encoding="utf-8")
    assert "ROTULO_LIGADO_NA_ENTRADA" not in fonte


def test_a_regua_do_dono_ve_a_composicao_por_constante(tmp_path: Path) -> None:
    """A MORDIDA da régua: a composição velha (constante + número) é achada; a nova, não."""
    (tmp_path / "velho.py").write_text(
        'ROTULO_LIGADO = "Ligado na entrada"\n'
        'def f(n):\n    return f"<b>{escapa(ROTULO_LIGADO)}</b> {n}"\n', encoding="utf-8")
    (tmp_path / "novo.py").write_text(
        'from x import com_artigo, na_frase\n'
        'def f(n):\n    return f"Ligado {com_artigo(na_frase(n), em=True)}"\n', encoding="utf-8")
    (tmp_path / "anotado.py").write_text(
        'ROTULO: str = "Ligado na entrada"\n'
        'def f(n):\n    return f"{ROTULO} {n}"\n', encoding="utf-8")
    achados = _composicoes_da_palavra(tmp_path)
    assert ("velho.py", "compõe por constante") in achados
    assert ("anotado.py", "compõe por constante") in achados
    assert not [a for a in achados if a[0] == "novo.py"]


@pytest.mark.parametrize("arquivo", ["interface/conexoes.py", "interface/logica_do_mapa.py"])
def test_o_mapa_nao_compoe_a_entrada_por_conta_propria(arquivo: str) -> None:
    achados = {f for f in _composicoes_da_palavra(RAIZ / "src" / "hefesto_dualsense4unix")}
    assert (arquivo, "compõe por constante") not in achados

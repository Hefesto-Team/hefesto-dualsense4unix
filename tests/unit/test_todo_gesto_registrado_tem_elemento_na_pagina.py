"""Todo `@gesto` das abas 08 e 09 tem elemento na página, ou está na lista nomeada com o motivo.

OS-GESTOS-SEM-ELEMENTO-DAS-ABAS-SISTEMA-E-CONEXOES-SAEM-01 (17/10/2026): cinco gestos viveram meses
registrados, com pergunta, recibo e testes, sem nenhum botão na página (`aplicar-aos-jogos`,
`refazer-consertos`, `fixar-proton`, `corrigir-vulkan`, `teto-da-vibracao`). Cada um era um segundo
escritor em potencial e código morto sustentado por régua. Esta régua impede a volta: o gesto
novo sem `data-gesto` na página (publicada e desenho) reprova, a menos que entre em
`SEM_ELEMENTO_ESTATICO` com o motivo escrito. O silêncio não é motivo.

MORDIDA: recoloque `@gesto("09-sistema.html", "fixar-proton")` (ou `todos` ou `mic-existe` na 08) em
qualquer pacote e `test_o_registro_real_nao_tem_gesto_sem_elemento` reprova com o nome dele;
`test_a_regua_acusa_o_gesto_sem_elemento` morde sozinho, sem tocar no produto.
Escopo: as duas abas. As outras oito ficam para quem as tocar.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import hefesto_dualsense4unix
from hefesto_dualsense4unix.interface import onde

PAGINAS = ("08-conexoes.html", "09-sistema.html")

#: Gestos registrados que a página estática não traz, cada um com o motivo. Os dois são
#: pintados pelo pacote em tempo de execução, para o controle externo conectado
#: (`_lista_do_externo`): sem externo na mesa não há elemento, e com ele há.
SEM_ELEMENTO_ESTATICO: dict[tuple[str, str], str] = {
    ("08-conexoes.html", "externo-modo"):
        "pintado em execução pela lista do controle externo (`_lista_do_externo`)",
    ("08-conexoes.html", "externo-botoes"):
        "pintado em execução pela lista do controle externo (`_lista_do_externo`)",
}


def _pacotes() -> Any:
    interface = str(Path(hefesto_dualsense4unix.__file__).parent / "interface")
    if interface not in sys.path:
        sys.path.insert(0, interface)
    import pacotes

    pacotes._carregar_tudo()
    return pacotes


def _tem_o_elemento(texto: str, nome: str) -> bool:
    return bool(re.search(rf'\bdata-(?:hef-)?gesto="{re.escape(nome)}"', texto))


def sem_elemento(registro: Any, textos: dict[str, str]) -> list[tuple[str, str]]:
    """Os `(página, gesto)` do registro, nas páginas dadas, sem `data-gesto` no texto da página."""
    return sorted(
        (pagina, nome) for pagina, nome in registro
        if pagina in textos and not _tem_o_elemento(textos[pagina], nome))


def _textos(*, publicado: bool) -> dict[str, str]:
    return {p: onde.pagina(p, publicado=publicado).read_text(encoding="utf-8") for p in PAGINAS}


def test_a_regua_acusa_o_gesto_sem_elemento() -> None:
    """Mordida sem tocar no produto: um registro com os gestos que saíram é reprovado."""
    textos = {"09-sistema.html": '<button data-gesto="correcoes-automaticas">',
              "08-conexoes.html": '<button data-gesto="forca">'}
    registro = [("09-sistema.html", "correcoes-automaticas"), ("09-sistema.html", "fixar-proton"),
                ("08-conexoes.html", "teto-da-vibracao"), ("08-conexoes.html", "forca"),
                ("07-lancadores.html", "qualquer")]
    assert sem_elemento(registro, textos) == [
        ("08-conexoes.html", "teto-da-vibracao"), ("09-sistema.html", "fixar-proton")]
    assert sem_elemento([("09-sistema.html", "doctor")], {"09-sistema.html": ""}) == [
        ("09-sistema.html", "doctor")]


def test_o_registro_real_nao_tem_gesto_sem_elemento() -> None:
    """Nas duas abas, todo gesto registrado tem `data-gesto` na publicada e no desenho.

    A prova da D-2010-A-PONTE-DO-MICROFONE-FICA-SEM-BOTAO.
    """
    pac = _pacotes()
    for publicado in (True, False):
        faltam = [chave for chave in sem_elemento(pac.GESTOS, _textos(publicado=publicado))
                  if chave not in SEM_ELEMENTO_ESTATICO]
        assert not faltam, (
            f"gesto sem elemento na página {'publicada' if publicado else 'do desenho'}: "
            f"{faltam}. Ou o elemento existe, ou o gesto sai do pacote, ou entra em "
            "`SEM_ELEMENTO_ESTATICO` com o motivo.")


def test_a_lista_de_excecoes_nao_apodrece() -> None:
    """Cada exceção segue registrada e sem elemento: quem ganhou botão ou saiu, sai da lista."""
    pac = _pacotes()
    for chave, motivo in SEM_ELEMENTO_ESTATICO.items():
        assert motivo.strip(), f"{chave}: exceção sem motivo"
        assert chave in pac.GESTOS, f"{chave} saiu do registro: tire-o da lista"
        for publicado in (True, False):
            assert chave in sem_elemento(pac.GESTOS, _textos(publicado=publicado)), (
                f"{chave} ganhou elemento na página: tire-o da lista")

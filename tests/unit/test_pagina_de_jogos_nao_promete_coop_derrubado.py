"""A página que ela lê não pode dizer que a exceção de Steam Input mata o co-op."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

PAGINA = Path("docs/usage/jogos-e-mascaras.md")

_PROMESSA_ANTIGA = re.compile(
    r"(sem co-op|vale só o controle 1|virtual sai de cena)",
    re.IGNORECASE,
)


def _raiz() -> Path:
    return Path(__file__).resolve().parents[2]


def _linhas_fora_de_citacao(texto: str) -> list[tuple[int, str]]:
    """As linhas que afirmam por conta própria, sem as de bloco `>`."""
    return [
        (n, ln)
        for n, ln in enumerate(texto.splitlines(), start=1)
        if not ln.lstrip().startswith(">")
    ]


def test_a_pagina_nao_promete_perda_de_coop():
    """Nenhuma linha afirmativa pode dizer que a exceção derruba o jogador 2."""
    texto = (_raiz() / PAGINA).read_text(encoding="utf-8")
    achados = [
        f"{PAGINA}:{n}: {ln.strip()[:90]}"
        for n, ln in _linhas_fora_de_citacao(texto)
        if _PROMESSA_ANTIGA.search(ln)
    ]
    assert not achados, (
        "a página diz que a exceção de Steam Input custa o co-op. Isso caducou em "
        "09/08/2026 (ESCONDER-EM-VEZ-DE-SAIR-01): a exceção passou a esconder o "
        "FÍSICO e o gamepad virtual FICA, justamente para o jogador 2 não cair.\n"
        + "\n".join(achados)
    )


def test_a_pagina_diz_que_o_coop_continua():
    """E o oposto: ela tem de afirmar, sem rodeio, que o co-op sobrevive."""
    texto = (_raiz() / PAGINA).read_text(encoding="utf-8")
    assert "co-op continua funcionando" in texto.lower(), (
        f"{PAGINA} não afirma que o co-op continua funcionando nos jogos com "
        "exceção de Steam Input. Remover a frase errada não basta: a pergunta "
        "precisa de resposta na mesma tela."
    )


def test_o_codigo_ainda_esconde_o_fisico_e_mantem_o_virtual():
    """A cura que a página descreve tem de continuar no produto."""
    fonte = (
        _raiz() / "src/hefesto_dualsense4unix/daemon/subsystems/gamepad.py"
    ).read_text(encoding="utf-8")

    assert "esconder_o_fisico_para_o_jogo" in fonte, (
        "a função que esconde o físico sumiu; se a cura foi revertida, a página "
        "de uso precisa voltar a falar em perda de co-op — e esta é a hora de decidir"
    )
    assert "coop_derrubado_pela_excecao_steam_input" in fonte, (
        "o registro do defeito que a ESCONDER-EM-VEZ-DE-SAIR-01 curou saiu do "
        "fonte; sem ele, a próxima pessoa reintroduz o caminho que derrubava o jogador 2"
    )


_O_MECANISMO = ("esconde o controle físico", "virtual continua de pé")


@pytest.mark.parametrize("trecho", _O_MECANISMO)
def test_a_pagina_diz_o_mecanismo(trecho):
    """A página tem de dizer por que o co-op fica, e não só que ele fica."""
    texto = (_raiz() / PAGINA).read_text(encoding="utf-8")
    assert trecho in texto, (
        f"a página não diz {trecho!r}: sem o mecanismo, a frase do co-op fica "
        "sem razão, e a próxima pessoa volta a escrevê-la errado"
    )

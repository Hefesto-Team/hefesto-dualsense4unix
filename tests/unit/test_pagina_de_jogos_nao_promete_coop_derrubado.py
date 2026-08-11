"""A página que ela lê não pode dizer que a exceção de Steam Input mata o co-op.

Defeito achado em 11/08/2026, na varredura das contradições entre a documentação
e o produto — e foi a mais cara das quarenta e uma, porque não é de protocolo:
é da página de uso, a que ela abre.

`docs/usage/jogos-e-mascaras.md` afirmava que, com a exceção ativa, *"o gamepad
virtual sai de cena: nesse jogo vale só o controle 1, sem co-op"*. Era verdade
até 08/08. Em 09/08 a ESCONDER-EM-VEZ-DE-SAIR-01 inverteu o mecanismo por
decisão dela: passou a esconder o FÍSICO e manter o virtual de pé, justamente
porque derrubar o jogador 2 era o defeito
(`coop_derrubado_pela_excecao_steam_input`, vinte ocorrências num dia).

A correção entrou no produto e nunca desceu para a página. Durante dois dias a
documentação disse a ela que perderia o co-op num jogo onde não perde.

Este teste amarra os dois: se alguém reescrever a página com a promessa antiga,
reprova; se alguém desfizer a cura no código, o teste do co-op reprova antes.

A MORDIDA, provada em 11/08/2026
================================
Devolvida a frase *"o gamepad virtual sai de cena: nesse jogo vale só o controle
1, sem co-op"* ao parágrafo principal da página,
`test_a_pagina_nao_promete_perda_de_coop` reprova nomeando a linha. Removida a
menção ao co-op continuar funcionando, `test_a_pagina_diz_que_o_coop_continua`
reprova. Desfeitas, verde.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

PAGINA = Path("docs/usage/jogos-e-mascaras.md")

#: A promessa que caducou em 09/08. Procurada só FORA de bloco de citação: uma
#: nota datada que cita a frase antiga para explicar o que mudou é exatamente o
#: que a casa manda escrever, e reprová-la seria castigar a honestidade.
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
    """E o oposto: ela tem de afirmar, sem rodeio, que o co-op sobrevive.

    Não basta remover a frase errada. Quem lê a seção precisa da resposta, senão
    a dúvida fica de pé e a página volta a ser reescrita errado por alguém
    tentando preenchê-la.
    """
    texto = (_raiz() / PAGINA).read_text(encoding="utf-8")
    assert "co-op continua funcionando" in texto.lower(), (
        f"{PAGINA} não afirma que o co-op continua funcionando nos jogos com "
        "exceção de Steam Input. Remover a frase errada não basta: a pergunta "
        "precisa de resposta na mesma tela."
    )


def test_o_codigo_ainda_esconde_o_fisico_e_mantem_o_virtual():
    """A cura que a página descreve tem de continuar no produto.

    Este caso é o outro lado do par: se alguém reverter a decisão de 09/08 no
    código, a página passa a mentir de novo — e o teste acima continuaria verde,
    porque ele só olha o texto. Aqui se olha o mecanismo.
    """
    fonte = (
        _raiz() / "src/hefesto_dualsense4unix/daemon/subsystems/gamepad.py"
    ).read_text(encoding="utf-8")

    assert "esconder_o_fisico_para_o_jogo" in fonte, (
        "a função que esconde o físico sumiu; se a cura foi revertida, a página "
        "de uso precisa voltar a falar em perda de co-op — e esta é a hora de decidir"
    )
    # O nome do defeito curado fica citado no fonte de propósito (a casa não
    # apaga decisão medida). Se ele sumir, alguém reescreveu o bloco sem ler.
    assert "coop_derrubado_pela_excecao_steam_input" in fonte, (
        "o registro do defeito que a ESCONDER-EM-VEZ-DE-SAIR-01 curou saiu do "
        "fonte; sem ele, a próxima pessoa reintroduz o caminho que derrubava o jogador 2"
    )


@pytest.mark.parametrize("marca", ["ESCONDER-EM-VEZ-DE-SAIR-01", "09/08"])
def test_a_nota_datada_explica_o_que_mudou(marca):
    """A página tem de dizer o que caducou, não só apagar.

    Fato errado se substitui; decisão medida ganha data. A medição de 06/08
    (a exceção não cala o Hefesto: a cor fica, o gatilho segura) continua
    valendo e fica. O que mudou foi o mecanismo, e isso leva data.
    """
    texto = (_raiz() / PAGINA).read_text(encoding="utf-8")
    assert marca in texto, (
        f"a página não menciona {marca!r}: sem isso, quem ler a nota de 06/08 não "
        "sabe qual metade dela ainda vale"
    )

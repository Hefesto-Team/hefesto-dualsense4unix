"""O que o doctor imprime fala com quem usa — a parte do ``scripts/doctor.sh`` da
AS-PAGINAS-DE-USO-FALAM-COM-QUEM-USA-01 (29/09/2026).

Cada ``pass``, ``fail``, ``warn``, ``info`` e ``hdr`` do exame chega a quem roda
o doctor, numa máquina qualquer. O ID da tarefa que fez cada mudança, a «Onda»,
«esta casa» e um caminho de ``docs/process`` (que não viaja com o produto) não
dizem nada a essa pessoa: o ``git log`` já os guarda. É a irmã da régua do
instalador (``test_install_respeita_o_nao_e_help_completo.py``), com o mesmo
vocabulário, e o critério 5 da sprint é o grep das linhas que começam pelo verbo.

Os comentários ficam de fora. A etiqueta do kernel-watch (``[USB-71]``) também:
ela não é chamada de mensagem, e sim o nome da linha que o ``storm_watch.sh``
escreve. O «dela» não entra, pela mesma razão da régua do instalador.

A MORDIDA: devolver o ``(VPAD-09)`` ao aviso da ACL do login, ou o ``(Onda T)``
ao ``info`` do patch do hid-nintendo, reprova aqui.
"""

from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DOCTOR = RAIZ / "scripts" / "doctor.sh"

#: Uma chamada de mensagem na linha: no começo, ou depois de ``&&``, ``||``,
#: ``{`` ou ``;`` (o ``[[ … ]] && info "…"`` e o ``{ info "…"; return 0; }``).
_MENSAGEM = re.compile(
    r"""(?:^\s*|&&\s*|\|\|\s*|\{\s*|;\s*)(?:pass|fail|warn|info|hdr|printf|echo)\b"""
)
_VOCABULARIO_DE_QUEM_CONSTROI = re.compile(
    r"\b[A-Z]{2,}(?:-[A-Z0-9]+)*-[0-9]{2}\b|\b(?:d|n)?esta casa\b|\bOnda [A-Z]\b|docs/process"
)
#: O critério 5 da sprint, literal.
_CRITERIO_5_LINHA = re.compile(r"^\s*(step|warn|die|printf|_faria|info)")
_CRITERIO_5_VOCABULARIO = re.compile(
    r"\b[A-Z]{2,}(-[A-Z0-9]+)*-[0-9]{2}\b|\bcasa\b|Onda [A-Z]\b"
)


def mensagens_com_vocabulario(texto: str) -> list[str]:
    """As linhas de mensagem do exame com o vocabulário de quem constrói."""
    achados = []
    for n, linha in enumerate(texto.splitlines(), 1):
        if linha.lstrip().startswith("#"):
            continue
        if _MENSAGEM.search(linha) and _VOCABULARIO_DE_QUEM_CONSTROI.search(linha):
            achados.append(f"doctor.sh:{n}: {linha.strip()[:120]}")
    return achados


def test_o_que_o_doctor_imprime_nao_tem_id() -> None:
    achados = mensagens_com_vocabulario(DOCTOR.read_text(encoding="utf-8"))
    assert not achados, (
        "mensagem do doctor com o vocabulário de quem constrói (ID, «Onda», "
        "«esta casa», docs/process); diga o que o exame viu:\n" + "\n".join(achados)
    )


def test_o_criterio_5_da_sprint_da_zero() -> None:
    linhas = [
        linha
        for linha in DOCTOR.read_text(encoding="utf-8").splitlines()
        if _CRITERIO_5_LINHA.search(linha) and _CRITERIO_5_VOCABULARIO.search(linha)
    ]
    assert linhas == []


def test_a_regua_ve_as_tres_formas() -> None:
    """A régua não mede o vazio: a mensagem no começo, depois de ``&&`` e dentro
    de ``{ … }`` são achadas, e o comentário e a etiqueta do kernel-watch não."""
    achadas = (
        '        warn "… contra o logind (VPAD-09). Rode: sudo bash x"',
        '    [[ -n "${x}" ]] && info "o default da Steam, que esta casa não mediu"',
        '    f && { info "  não gravo (§D.7 da MIC-PADRAO-NO-CABO-01)"; return 0; }',
        '        info "dkms ausente — patch DKMS do hid-nintendo (Onda T) não instalado"',
        '        warn "o porquê está em docs/process/estudos/x.md"',
    )
    ignoradas = (
        "# VPAD-09: o comentário pode citar a sprint",
        '        "storm USB (-71) registrado no kernel-watch [USB-71] — a ENTRADA"',
        '        fail "a Steam adota ${HOME}/.steam como casa"',
    )
    assert all(mensagens_com_vocabulario(linha) for linha in achadas)
    assert not any(mensagens_com_vocabulario(linha) for linha in ignoradas)

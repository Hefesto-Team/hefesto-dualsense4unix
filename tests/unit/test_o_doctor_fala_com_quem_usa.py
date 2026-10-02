"""O que o doctor imprime fala com quem usa — a parte do ``scripts/doctor.sh`` da"""

from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DOCTOR = RAIZ / "scripts" / "doctor.sh"

_MENSAGEM = re.compile(
    r"""(?:^\s*|&&\s*|\|\|\s*|\{\s*|;\s*)(?:pass|fail|warn|info|hdr|printf|echo)\b"""
)
_VOCABULARIO_DE_QUEM_CONSTROI = re.compile(
    r"\b[A-Z]{2,}(?:-[A-Z0-9]+)*-[0-9]{2}\b|\b(?:d|n)?esta casa\b|\bOnda [A-Z]\b|\bONDA-[A-Z0-9]+\b"
    r"|docs/process"
)
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
    """A régua não mede o vazio: a mensagem no começo, depois de ``&&`` e dentro"""
    achadas = (
        '        warn "… contra o logind (VPAD-09). Rode: sudo bash x"',
        '    [[ -n "${x}" ]] && info "o default da Steam, que esta casa não mediu"',
        '    f && { info "  não gravo (§D.7 da MIC-PADRAO-NO-CABO-01)"; return 0; }',
        '        info "dkms ausente — patch DKMS do hid-nintendo (Onda T) não instalado"',
        '        warn "o porquê está em docs/process/estudos/x.md"',
        '        warn "x: $(so_no_checkout "(ONDA-R aplica por default)")"',
    )
    ignoradas = (
        "# VPAD-09: o comentário pode citar a sprint",
        '        "storm USB (-71) registrado no kernel-watch [USB-71] — a ENTRADA"',
        '        fail "a Steam adota ${HOME}/.steam como casa"',
    )
    assert all(mensagens_com_vocabulario(linha) for linha in achadas)
    assert not any(mensagens_com_vocabulario(linha) for linha in ignoradas)

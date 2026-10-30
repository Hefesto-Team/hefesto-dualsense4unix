"""OS-AVISOS-DO-INSTALL-FALAM-COM-QUEM-INSTALA-01: quem instala lê o que aconteceu."""
from __future__ import annotations

import ast
import re
import subprocess
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SCRIPTS_DO_INSTALL = (
    RAIZ / "install.sh",
    RAIZ / "scripts" / "lib" / "camada_de_maquina.sh",
    RAIZ / "scripts" / "lib" / "som_da_sessao.sh",
    RAIZ / "scripts" / "desempenho.sh",
    RAIZ / "scripts" / "doctor.sh",
)
PYTHON_QUE_O_INSTALL_MOSTRA = (
    RAIZ / "src" / "hefesto_dualsense4unix" / "integrations" / "proton_pin.py",
    RAIZ / "src" / "hefesto_dualsense4unix" / "integrations" / "censo_dos_lancadores.py",
)
PALAVRAS_DA_CASA = re.compile(r"(?<!\w)(bancada|dela|a provar)(?!\w)", re.IGNORECASE)
QUEM_FALA = (
    "printf", "echo", "warn", "info", "ok", "die", "step", "ask_yn", "_faria", "_faria_root",
    "_nao_faria", "_dizer", "diga", "anotar_reinicio_pendente", "pass", "fail", "hdr",
)
FALA = re.compile(
    r"(?:^|;|\|\||&&|\bthen\b|\belse\b|\bdo\b)\s*(?:" + "|".join(map(re.escape, QUEM_FALA))
    + r")\s+(?P<resto>.*)$"
)
CADEIA = re.compile(r'"((?:[^"\\]|\\.)*)"|\'([^\']*)\'')


def frases_do_shell(texto: str) -> list[tuple[int, str]]:
    achadas: list[tuple[int, str]] = []
    for numero, linha in enumerate(texto.splitlines(), start=1):
        if linha.lstrip().startswith("#"):
            continue
        fala = FALA.search(linha)
        if fala is None:
            continue
        for dupla, simples in CADEIA.findall(fala.group("resto")):
            achadas.append((numero, dupla or simples))
    return achadas


def frases_do_python(texto: str) -> list[tuple[int, str]]:
    achadas: list[tuple[int, str]] = []
    for no in ast.walk(ast.parse(texto)):
        if not isinstance(no, ast.Call) or not isinstance(no.func, ast.Name):
            continue
        if no.func.id != "print":
            continue
        for filho in ast.walk(no):
            if isinstance(filho, ast.Constant) and isinstance(filho.value, str):
                achadas.append((filho.lineno, filho.value))
    return achadas


def palavras_da_casa(frases: list[tuple[int, str]]) -> list[tuple[int, str]]:
    return [(n, f) for n, f in frases if PALAVRAS_DA_CASA.search(f)]


def test_nenhuma_frase_do_install_nem_do_doctor_fala_a_lingua_da_casa() -> None:
    """Mordida: devolva «a provar» ao doctor.sh e a régua o aponta pela linha."""
    achados = []
    for caminho in SCRIPTS_DO_INSTALL:
        texto = caminho.read_text(encoding="utf-8")
        for numero, frase in palavras_da_casa(frases_do_shell(texto)):
            achados.append(f"{caminho.relative_to(RAIZ)}:{numero}: {frase}")
    for caminho in PYTHON_QUE_O_INSTALL_MOSTRA:
        texto = caminho.read_text(encoding="utf-8")
        for numero, frase in palavras_da_casa(frases_do_python(texto)):
            achados.append(f"{caminho.relative_to(RAIZ)}:{numero}: {frase}")
    assert not achados, "\n".join(achados)


def test_a_regua_le_cada_forma_de_falar_e_deixa_o_comentario() -> None:
    script = "\n".join((
        'warn "o PipeWire dela fica"',
        '    cmd || warn "a bancada confere"',
        "    printf '      nvidia: a provar\\n'",
        'if x; then _faria "algo da bancada"; fi',
        '# warn "comentário da bancada não conta"',
        'warn "o vidro de uma janela fica"',
        'warn "o Proton dele fica"',
        '    fail "o alvo do RUN+= dela falta"',
        '        pass "é escolha dela"',
    ))
    linhas = sorted({n for n, _ in palavras_da_casa(frases_do_shell(script))})
    assert linhas == [1, 2, 3, 4, 8, 9], linhas
    python = 'print("trava pela bancada")\nx = "dela"\nprint(f"a provar {x}")\n'
    assert sorted({n for n, _ in palavras_da_casa(frases_do_python(python))}) == [1, 3]


def _o_case_do_11a() -> str:
    texto = (RAIZ / "install.sh").read_text(encoding="utf-8")
    bloco = texto[texto.index('step "11a"'): texto.index('step "11a-bis"')]
    inicio = bloco.index('    case "${_pp_rc}" in')
    return bloco[inicio: bloco.index("    esac", inicio) + len("    esac")]


def _roda_o_case(rc: int) -> str:
    programa = "\n".join((
        'warn() { printf "AVISO %s\\n" "$*"; }',
        f"_pp_rc={rc}",
        '_pp_saida=""',
        "PROTON_PIN_PY=/opt/hefesto/proton_pin.py",
        "PYTHON_DO_PINO=/opt/hefesto/.venv/bin/python",
        _o_case_do_11a(),
    ))
    rodou = subprocess.run(
        ["bash", "-c", programa], capture_output=True, text=True, timeout=30, check=False
    )
    assert rodou.returncode == 0, rodou.stderr
    return rodou.stdout


def test_sem_steam_o_install_diz_que_guardou_e_quem_fixa_depois() -> None:
    """D-3010-O-PIN-DO-PROTON-VALE-PARA-TODO-JOGO, nota de 30/10: o download não espera lançador.

    Mordida: devolva ao `case` do 11a um ramo que diga «nada foi baixado» e a régua reprova.
    """
    saida = _roda_o_case(4)
    assert "guardado no cache" in saida, saida
    assert "sem rodar o install de novo" in saida, saida
    assert "/opt/hefesto/.venv/bin/python /opt/hefesto/proton_pin.py --manter" in saida, saida
    caso = _o_case_do_11a()
    assert "nada foi baixado" not in caso, caso
    assert not re.search(r"^\s+8\)\s*$", caso, re.M), "voltou o ramo do rc 8, o que não baixa"


def test_os_ramos_adiados_dizem_o_que_aconteceu_sem_jargao() -> None:
    for rc in (4, 7):
        saida = _roda_o_case(rc)
        assert "ADIADO" not in saida and "pino" not in saida, saida
        assert "Proton fixado" in saida, saida

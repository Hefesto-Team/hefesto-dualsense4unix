"""A vigia não morre calada: o `&&` no fim da função sob `set -e`.

Medido em 24/09/2026, 23h57, logo depois do boot: o
``hefesto-bt-health-watchdog.service`` ficou ``failed`` duas rodadas seguidas,
sem uma linha no diário. O ``_uniqs_hidraw`` terminava o laço com
``[[ -n "$u" ]] && printf``; quando o ÚLTIMO hidraw vinha sem UNIQ (teclado ou
mouse USB, ou um DualSense no cabo), a função devolvia 1, e o ``set -e`` matava
o script em ``UNIQS="$(_uniqs_hidraw)"``. O preço: sem controle no rádio, as
vigias 4 e 5 (o religar do cabo e o adaptador travado) não rodavam. Às 23h59 os
dois DualSense do BT conectaram, o último hidraw passou a ter UNIQ, e a vigia
voltou sozinha, o que escondia o defeito.

A origem é a FORMA, e não o watchdog: o bash só mata quando o `&&` vira o
retorno de uma função (direto, ou pelo laço, `if` ou `case` que fecha a função)
ou a saída do script. Laço ou `if` solto no meio do script sobrevive. As três
réguas abaixo são a forma medida no bash, nenhum script da casa com ela, e o
watchdog em toda mesa: os três modos, cabo e BT, de zero a quatro controles.
"""

from __future__ import annotations

import itertools
import os
import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
WATCHDOG = REPO_ROOT / "scripts" / "bt_health_watchdog.sh"

SET_E = re.compile(r"^\s*set\s+-[a-zA-Z]*e[a-zA-Z]*\b|^\s*set\s+-o\s+errexit", re.MULTILINE)
CABECALHO = re.compile(r"^(\s*)(?:function\s+)?[A-Za-z_]\w*\s*\(\)\s*\{?\s*(?:#.*)?$")
FECHAMENTO = re.compile(r"^\s*(?:done|\}|fi|esac|;;)(?:\s|;|$|<|>|\))")
HEREDOC = re.compile(r"<<-?\s*['\"]?([A-Za-z_]\w*)['\"]?")
# O que vem depois do `&&` e ainda é pergunta: aí o `&&` é o predicado que a
# função devolve de propósito (`e_microfone() { [[ a ]] && [[ b ]]; }`).
PERGUNTA = re.compile(r"^\s*(?:!\s*)?(?:\[\[|\[\s|test\s|grep\s+-\w*q|true\b|false\b)")


def _sem_texto(linha: str) -> str:
    """A linha sem aspas, sem o miolo do ``[[ ]]`` e sem comentário no fim."""
    s = re.sub(r"'[^']*'", "''", linha)
    s = re.sub(r'"(?:\\.|[^"\\])*"', '""', s)
    s = re.sub(r"\[\[.*?\]\]", "[[ ]]", s)
    return re.sub(r"\s+#.*$", "", s).strip()


def _significativas(linhas: list[str]) -> list[tuple[int, str]]:
    """As linhas que o bash executa: sem branco, sem comentário, sem heredoc e
    sem o miolo de aspas simples que atravessam linhas (o programa do `awk`)."""
    sig: list[tuple[int, str]] = []
    fim_do_heredoc: str | None = None
    em_aspas = False
    for i, linha in enumerate(linhas):
        simples = re.sub(r'"(?:\\.|[^"\\])*"', "", linha).count("'") % 2 == 1
        if em_aspas:
            em_aspas = not simples
            continue
        if fim_do_heredoc is not None:
            if linha.strip() == fim_do_heredoc:
                fim_do_heredoc = None
            continue
        if not linha.strip() or linha.strip().startswith("#"):
            continue
        sig.append((i, linha))
        em_aspas = simples
        m = HEREDOC.search(linha)
        if m is not None and "<<<" not in linha:
            fim_do_heredoc = m.group(1)
    return sig


def _vira_retorno(linhas: list[str], sig: list[tuple[int, str]], k: int) -> bool:
    """Anda pelos fechamentos depois da linha ``k``: a função fechou, ou o arquivo?"""
    i = sig[k][0]
    funcao: tuple[int, int] | None = None
    for j in range(i, -1, -1):
        m = CABECALHO.match(linhas[j])
        if m is not None:
            funcao = (j, len(m.group(1)))
            break
    kk = k + 1
    while kk < len(sig):
        ii, linha = sig[kk]
        st = linha.strip()
        if st.startswith(";;"):
            while kk < len(sig) and not re.match(r"^\s*esac\b", sig[kk][1]):
                kk += 1
            continue
        if not FECHAMENTO.match(linha):
            return False
        recuo = len(linha) - len(linha.lstrip())
        if st.startswith("}") and funcao is not None and recuo == funcao[1] and ii > funcao[0]:
            return True
        kk += 1
    return True


def formas_que_matam(texto: str) -> list[int]:
    """As linhas (base 1) cujo ``A && ação`` vira retorno de função ou saída do script."""
    linhas = texto.split("\n")
    sig = _significativas(linhas)
    achados: list[int] = []
    for k, (i, linha) in enumerate(sig):
        s = _sem_texto(linha)
        if "&&" not in s or s.startswith(("if ", "elif ", "while ", "until ")):
            continue
        if s.endswith(("&&", "||", "|", "\\")):
            continue
        cauda = s.rsplit("&&", 1)[1]
        if "||" in cauda or PERGUNTA.match(cauda):
            continue
        if _vira_retorno(linhas, sig, k):
            achados.append(i + 1)
    return achados


def _scripts_com_set_e() -> list[tuple[str, str]]:
    nomes = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split("\n")
    scripts: list[tuple[str, str]] = []
    for nome in nomes:
        caminho = REPO_ROOT / nome
        if not nome or not caminho.is_file():
            continue
        try:
            texto = caminho.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        primeira = texto.split("\n", 1)[0]
        e_shell = nome.endswith(".sh") or (primeira.startswith("#!") and "sh" in primeira)
        if e_shell and SET_E.search(texto):
            scripts.append((nome, texto))
    return scripts


def _bash(codigo: str) -> str:
    return subprocess.run(
        ["bash", "-c", f"set -euo pipefail; {codigo}; echo VIVO"],
        capture_output=True,
        text=True,
        timeout=10,
    ).stdout


class TestAFormaMataDeVerdade:
    """A régua de forma só vale se a forma mata: medido no bash, não suposto."""

    def test_o_e_logico_no_fim_da_funcao_mata_por_cifrao(self) -> None:
        funcao = 'f() { for x in a; do [[ -z "$x" ]] && echo "$x"; done; }'
        assert "VIVO" not in _bash(f'{funcao}; y="$(f)"')

    def test_o_if_no_fim_da_funcao_sobrevive(self) -> None:
        funcao = 'f() { for x in a; do if [[ -z "$x" ]]; then echo; fi; done; }'
        assert "VIVO" in _bash(f'{funcao}; y="$(f)"')

    def test_o_laco_solto_no_meio_do_script_sobrevive(self) -> None:
        assert "VIVO" in _bash('for x in a; do [[ -z "$x" ]] && echo "$x"; done')


class TestNenhumScriptTemAForma:
    def test_a_regua_ve_a_forma_que_matou_o_watchdog(self) -> None:
        ruim = (
            "set -euo pipefail\n"
            "f() {\n"
            '    for x in a; do\n        [[ -n "$x" ]] && printf "%s" "$x"\n    done\n'
            "}\n"
            'y="$(f)"\n'
        )
        assert formas_que_matam(ruim) == [4]
        boa = ruim.replace(
            '[[ -n "$x" ]] && printf "%s" "$x"',
            'if [[ -n "$x" ]]; then printf "%s" "$x"; fi',
        )
        assert formas_que_matam(boa) == []

    def test_o_predicado_de_proposito_nao_e_a_forma(self) -> None:
        predicado = 'set -e\ne_mic() {\n    [[ "$1" == a* ]] && [[ "$1" != *b ]]\n}\n'
        assert formas_que_matam(predicado) == []

    def test_nenhum_script_com_set_e_termina_funcao_em_e_logico(self) -> None:
        scripts = _scripts_com_set_e()
        assert len(scripts) > 20, "a lista de scripts veio curta: a régua ficou cega"
        achados = [f"{nome}:{n}" for nome, texto in scripts for n in formas_que_matam(texto)]
        assert not achados, (
            "`A && ação` no fim de função (ou do script) sob `set -e` devolve 1 "
            "quando A é falso, e mata calado quem chama; troque por `if A; then "
            f"ação; fi`: {achados}"
        )


# A mesa de mentira, na ordem em que o kernel numera: as entradas da máquina
# primeiro, depois os controles, depois os bonecos. O glob do script é
# lexicográfico (hidraw10 vem antes de hidraw2), então o «último» muda com o
# tamanho da mesa, e a matriz cobre isso sem escolher o caso.
MODOS = ("nativo", "dualsense", "xbox")
TRANSPORTES = ("usb", "bt", "misto")


def _mesa(modo: str, transporte: str, jogadores: int) -> list[str]:
    uniqs = ["", "", "", ""]  # mouse e teclado USB: UNIQ vazio
    for n in range(1, jogadores + 1):
        pelo_bt = transporte == "bt" or (transporte == "misto" and n % 2 == 0)
        uniqs.append(f"aa:bb:cc:00:00:1{n}" if pelo_bt else "")
    if modo == "dualsense":  # o boneco é uhid e tem hidraw; o do xbox é uinput
        uniqs.extend(f"02:fe:00:00:00:0{n}" for n in range(1, jogadores + 1))
    return uniqs


CASOS = [("nativo", "usb", 0), ("dualsense", "usb", 0), ("xbox", "usb", 0)] + [
    (modo, transporte, jogadores)
    for modo, transporte, jogadores in itertools.product(MODOS, TRANSPORTES, range(1, 5))
]


@pytest.mark.parametrize(("modo", "transporte", "jogadores"), CASOS)
def test_o_watchdog_roda_inteiro_em_toda_mesa(
    tmp_path: Path, modo: str, transporte: str, jogadores: int
) -> None:
    hidraw = tmp_path / "hidraw"
    for numero, uniq in enumerate(_mesa(modo, transporte, jogadores)):
        dispositivo = hidraw / f"hidraw{numero}" / "device"
        dispositivo.mkdir(parents=True)
        (dispositivo / "uevent").write_text(f"HID_UNIQ={uniq}\n", encoding="utf-8")
    bluez = tmp_path / "bluetooth"
    bluez.mkdir()

    proc = subprocess.run(
        ["bash", str(WATCHDOG), "--sdp-cache-only"],
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "HEFESTO_BT_SRC": str(bluez),
            "HEFESTO_HIDRAW_ROOT": str(hidraw),
            "HEFESTO_BT_STAMP_DIR": str(tmp_path / "stamps"),
        },
        timeout=60,
    )
    assert proc.returncode == 0, (
        f"a vigia morreu calada com {jogadores} controle(s) em {transporte}, modo {modo} "
        f"(rc={proc.returncode}, stderr={proc.stderr!r})"
    )

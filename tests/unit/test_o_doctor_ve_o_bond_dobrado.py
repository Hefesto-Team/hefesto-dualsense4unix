"""BOND-DOBRADO-01 — o controle com chave em dois adaptadores, e ninguém via.

Achado na mesa dela em 19/09/2026: quatro DualSense, SEIS bonds. Dois
controles com chave de pareamento em dois adaptadores ao mesmo tempo — uma
migração feita pela metade, em que o bond do adaptador de ORIGEM ficou.

Nenhuma superfície mostrava isso: nem o `doctor`, nem a aba Conexões, nem o
`plano_de_radio`, que conta ocupação por adaptador sem nunca perguntar se o
mesmo controle está contado duas vezes.

Estas réguas exercitam a FUNÇÃO do shell, não o texto dela: o corpo é extraído
do `doctor.sh` e rodado com uma lista de caminhos de mentira. É a mesma
mordida que separa "acha o defeito" de "acusa qualquer coisa".

A-SOBRA-DO-BOND-SAI-SOZINHA-01 (25/09/2026): o check contava OBJETO do BlueZ, e
o BlueZ guarda um objeto para todo aparelho que uma busca achou. Na mesa dela,
dez vizinhos vistos por hci1 e hci2 viraram dez «chaves em dois adaptadores»,
e o doctor deu 12 avisos para UM controle com chave dobrada. Agora só conta
objeto com ``Paired=true`` — e quem apaga a sobra é a central do rádio, sozinha
(``test_a_sobra_do_bond_sai_sozinha.py``).
"""

from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DOCTOR = RAIZ / "scripts" / "doctor.sh"


def _rodar(caminhos: list[str], *, pareados: list[str] | None = None) -> str:
    """Roda `check_bond_dobrado` com a lista de caminhos dada, e devolve a saída.

    ``pareados`` são os caminhos com ``Paired=true``; sem ele, todos têm chave.
    """
    falsa = "\n".join(caminhos)
    com_chave = "\n".join(caminhos if pareados is None else pareados)
    roteiro = textwrap.dedent(f"""
        _dbus_bt_device_paths() {{ printf '%s\\n' "$FALSA"; }}
        _dbus_bt_prop() {{
            if [[ "$3" != Paired ]]; then return 0; fi
            if grep -qxF -- "$1" <<<"$COM_CHAVE"; then echo true; else echo false; fi
        }}
        pass() {{ echo "[OK] $*"; }}
        warn() {{ echo "[WARN] $*"; }}
        info() {{ echo "[INFO] $*"; }}
        eval "$(sed -n '/^_bond_dobrado_por_controle() {{/,/^}}/p' {DOCTOR})"
        eval "$(sed -n '/^check_bond_dobrado() {{/,/^}}/p' {DOCTOR})"
        check_bond_dobrado
    """)
    fim = subprocess.run(
        ["bash", "-c", roteiro],
        capture_output=True,
        text=True,
        env={"FALSA": falsa, "COM_CHAVE": com_chave, "PATH": "/usr/bin:/bin"},
        check=False,
    )
    return fim.stdout


def test_o_check_existe_e_e_chamado() -> None:
    texto = DOCTOR.read_text(encoding="utf-8")
    assert "check_bond_dobrado() {" in texto, "a função não existe"
    chamadas = [
        linha for linha in texto.splitlines() if linha.strip() == "check_bond_dobrado"
    ]
    assert chamadas, (
        "a função existe mas ninguém a chama — é a assinatura desta casa de "
        "instrumento que dá verde sobre nada, porque nem roda."
    )


def test_acusa_o_controle_em_dois_adaptadores() -> None:
    saida = _rodar(
        [
            "/org/bluez/hci0/dev_AA_BB_CC_00_00_01",
            "/org/bluez/hci1/dev_AA_BB_CC_00_00_01",
            "/org/bluez/hci2/dev_AA_BB_CC_00_00_03",
        ]
    )
    assert "[WARN]" in saida, f"não acusou a dobra:\n{saida}"
    assert "AA:BB:CC:00:00:01" in saida, "não disse QUAL controle"
    assert "hci0" in saida and "hci1" in saida, "não disse QUAIS adaptadores"
    assert "AA:BB:CC:00:00:03" not in saida, (
        "acusou o controle que está num adaptador só — a régua pega qualquer "
        "coisa, não a dobra."
    )


def test_cada_controle_no_seu_adaptador_passa_verde() -> None:
    saida = _rodar(
        [
            "/org/bluez/hci0/dev_AA_BB_CC_00_00_01",
            "/org/bluez/hci1/dev_AA_BB_CC_00_00_02",
            "/org/bluez/hci2/dev_AA_BB_CC_00_00_03",
        ]
    )
    assert "[WARN]" not in saida, f"acusou uma mesa limpa:\n{saida}"
    assert "[OK]" in saida, "nem verde nem vermelho — o check calou"


def test_caminho_repetido_nao_e_dobra() -> None:
    # O `busctl tree --list` pode repetir um caminho. Repetição do MESMO
    # adaptador não é dobra — contar linha em vez de adaptador distinto
    # acusaria toda máquina.
    saida = _rodar(
        [
            "/org/bluez/hci0/dev_AA_BB_CC_00_00_01",
            "/org/bluez/hci0/dev_AA_BB_CC_00_00_01",
        ]
    )
    assert "[WARN]" not in saida, (
        f"tratou repetição do mesmo adaptador como dobra:\n{saida}"
    )


def test_mesa_sem_adaptador_nenhum_nao_quebra() -> None:
    # O produto é de acessibilidade e roda em máquina de outra pessoa:
    # `mesa_de_radio.py:44-52` registra que zero adaptadores é o caso mais
    # comum lá fora.
    saida = _rodar([])
    assert "[WARN]" not in saida, f"acusou uma máquina sem adaptador:\n{saida}"
    assert "[OK]" in saida, "calou numa máquina sem adaptador"


def test_o_recado_diz_o_gesto_e_nao_apaga_sozinho() -> None:
    saida = _rodar(
        [
            "/org/bluez/hci0/dev_AA_BB_CC_00_00_01",
            "/org/bluez/hci1/dev_AA_BB_CC_00_00_01",
        ]
    )
    assert "esquecer" in saida, (
        "o recado não diz COMO limpar. Regra desta casa: quem acusa diz o gesto."
    )
    corpo = DOCTOR.read_text(encoding="utf-8").split("check_bond_dobrado() {", 1)[-1]
    corpo = corpo.split("\n}\n", 1)[0]
    assert "fail " not in corpo, (
        "bond dobrado é `warn`, não `fail`: é estado a arrumar com a escolha "
        "dela, não defeito que impede o produto de funcionar."
    )
    assert "rm " not in corpo and "remove" not in corpo, (
        "o check APAGANDO bond: o doctor só acusa. Quem apaga a sobra é a "
        "central do rádio, e só com a prova do controle conectado num dos dois."
    )


def test_o_vizinho_de_busca_nao_e_chave() -> None:
    """O defeito medido em 25/09: objeto de busca em dois adaptadores não é bond.

    MORDIDA: tire a linha do ``Paired`` do ``_bond_dobrado_por_controle`` — o
    vizinho visto por hci1 e hci2 volta a ser acusado, e esta régua reprova.
    """
    vizinho = ["/org/bluez/hci1/dev_AA_BB_CC_00_00_77", "/org/bluez/hci2/dev_AA_BB_CC_00_00_77"]
    dobrado = ["/org/bluez/hci0/dev_AA_BB_CC_00_00_03", "/org/bluez/hci1/dev_AA_BB_CC_00_00_03"]
    saida = _rodar(vizinho + dobrado, pareados=dobrado)
    assert saida.count("[WARN]") == 1, f"um controle dobrado, um aviso:\n{saida}"
    assert "AA:BB:CC:00:00:03" in saida
    assert "AA:BB:CC:00:00:77" not in saida, (
        f"acusou o vizinho que só uma busca viu — objeto não é chave:\n{saida}"
    )


def test_so_um_lado_com_chave_nao_e_dobra() -> None:
    """Chave num adaptador e objeto de busca no outro: um bond só."""
    caminhos = ["/org/bluez/hci0/dev_AA_BB_CC_00_00_01", "/org/bluez/hci1/dev_AA_BB_CC_00_00_01"]
    saida = _rodar(caminhos, pareados=caminhos[:1])
    assert "[WARN]" not in saida, f"um bond só, lido como dois:\n{saida}"
    assert "[OK]" in saida


def test_o_recado_diz_que_a_sobra_sai_sozinha() -> None:
    saida = _rodar(
        ["/org/bluez/hci0/dev_AA_BB_CC_00_00_01", "/org/bluez/hci1/dev_AA_BB_CC_00_00_01"]
    )
    assert "sozinho" in saida, (
        "o recado manda ela apagar à mão o que o daemon apaga sozinho quando o "
        "controle conecta — o recado mente sobre o produto."
    )

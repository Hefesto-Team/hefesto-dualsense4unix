"""A troca de nome da regra do nó é idempotente, reversível, e o doctor só lê.

O-FISICO-NASCE-ESCONDIDO-EM-QUALQUER-MAQUINA-01, conferência de 25/09/2026 com
a lente «segurança e reversibilidade». As outras réguas da sprint provam que a
regra certa fecha o nó; esta prova que instalar, desinstalar e atualizar não
deixam a máquina pior do que estava — de 1 a N vezes, em qualquer ordem:

1. **o install roda numa máquina nova e roda duas vezes**: o `rm` da regra de
   antes tem de ser `rm -f`, porque o `install_udev.sh` corre sob `set -e` e a
   máquina nova não tem a velha. As réguas de antes criavam a velha ANTES de
   instalar, e um `rm` sem `-f` passava nelas;
2. **o `--no-fechar-o-no` vai e volta**: fechada → aberta → fechada, e o fim é
   o asset byte a byte;
3. **o uninstall roda duas vezes** e tira a regra da máquina que só tem a
   velha; a remoção dos PACOTES roda numa máquina em que o helper nunca rodou
   (o `prerm` do .deb corre sob `set -e`: um `rm` que falha ali deixa o pacote
   impossível de remover);
4. **o `--keep-udev` não deixa a regra fechada sem o broker.** O broker sai com
   ou sem ele, e a regra do nó FECHADA que ficasse deixaria o DualSense físico
   `0600 root` para sempre: a Steam e o jogo perderiam o controle depois de o
   Hefesto sair. Até 25/09 a `71-sony-controllers.rules` do Pop!_OS escondia
   isso (reabria o nó); com a 73-hefesto falando por último, vale em toda
   máquina. A regra preservada vira a variante aberta;
5. **o doctor só LÊ**: as funções novas não têm verbo que escreva, e o IPC que
   elas fazem é o `daemon.state_full`;
6. **o doctor não diz que a barra está acesa**: a cor que ele imprime é a
   PEDIDA (`cor_pedida=`), não a lâmpada.

Tudo roda numa raiz de mentira: o `sudo` de mentira executa só `install` e
`rm`, recusa qualquer argumento que aponte para o /etc, /usr, /lib ou /run de
verdade, e só anota o resto. O socket do daemon é um servidor de mentira.

AS MORDIDAS, medidas em 25/09/2026: `rm` sem `-f` no `install_udev.sh` reprova
a 1 e a 2; `rm` sem `-f` no `uninstall.sh` reprova a 3; `rm` sem `-f` no helper
reprova a régua do helper; `rm` sem `-f` na remoção de qualquer pacote reprova
a régua da remoção daquele pacote; tirar a chamada de
`_abrir_a_regra_do_no_que_fica` do ramo do `--keep-udev` reprova a 4; um
`setfacl` numa função nova do doctor reprova a 5; a cor de volta a
`lightbar_rgb=` reprova a 6.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import threading
from pathlib import Path

import pytest

from tests.unit import test_o_fisico_nasce_escondido_em_qualquer_maquina as udev

BASH = shutil.which("bash") or "/bin/bash"
RAIZ = Path(__file__).resolve().parents[2]
ASSET = RAIZ / "assets" / "73-hefesto-ps5-controller.rules"
NOVA = "73-hefesto-ps5-controller.rules"
VELHA = "70-ps5-controller.rules"
ETC = "/etc/udev/rules.d"

INSTALL_UDEV = (RAIZ / "scripts" / "install_udev.sh").read_text(encoding="utf-8")
HOST_UDEV = (RAIZ / "scripts" / "install-host-udev.sh").read_text(encoding="utf-8")
UNINSTALL = (RAIZ / "uninstall.sh").read_text(encoding="utf-8")
DOCTOR = RAIZ / "scripts" / "doctor.sh"

#: O `sudo` de mentira: `install` e `rm` executam; o resto só se anota.
SUDO_DE_MENTIRA = r"""#!/usr/bin/env bash
for a in "$@"; do
  case "$a" in
    /etc/*|/usr/*|/lib/*|/run/*) echo "RECUSEI $a" >&2; exit 97 ;;
  esac
done
while [[ "${1:-}" == -[nAEHkS] ]]; do shift; done
case "${1:-}" in
  true) exit 0 ;;
  install|rm) exec "$@" ;;
  *) echo "ANOTEI $*" >> "${ANOTACOES:-/dev/null}"; exit 0 ;;
esac
"""


def _rodar(
    tmp: Path, script: str, *, estrito: bool = True
) -> subprocess.CompletedProcess[str]:
    """Roda um recorte com o sudo de mentira. `estrito` = `set -euo pipefail`."""
    fakes = tmp / "fakes"
    fakes.mkdir(exist_ok=True)
    sudo = fakes / "sudo"
    sudo.write_text(SUDO_DE_MENTIRA, encoding="utf-8")
    sudo.chmod(0o755)
    cabeca = "set -euo pipefail\n" if estrito else ""
    r = subprocess.run(
        [BASH, "-c", cabeca + script],
        env={
            "PATH": f"{fakes}:/usr/bin:/bin",
            "HOME": str(tmp),
            "LC_ALL": "C.UTF-8",
            "ANOTACOES": str(tmp / "anotacoes"),
        },
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert "RECUSEI" not in r.stderr, r.stderr
    return r


def _etc(tmp: Path) -> Path:
    etc = tmp / "etc" / "udev" / "rules.d"
    etc.mkdir(parents=True, exist_ok=True)
    return etc


def _efetivas(texto: str) -> list[str]:
    return [
        linha
        for linha in texto.splitlines()
        if linha.strip() and not linha.lstrip().startswith("#")
    ]


def _comando_rm(texto: str, *, depois_de: str = "") -> str:
    """O `rm` que cita a regra de hoje, com a continuação — ache-o pela FORMA.

    Pela forma (qualquer `rm`, com ou sem `-f`), e não pelo texto exato: a
    mordida desta régua é justamente o `-f`, e um recorte que digitasse
    `rm -f` reprovaria por «não achei o texto», e não pela razão certa.
    """
    inicio = texto.index(depois_de) if depois_de else 0
    padrao = re.compile(
        rf"^[ \t]*(?:sudo[ \t]+)?rm\b[^\n]*{re.escape(ETC)}/{re.escape(NOVA)}", re.M
    )
    m = padrao.search(texto, inicio)
    assert m, "não achei o rm da regra do nó"
    linhas = []
    for linha in texto[m.start() :].splitlines():
        linhas.append(linha)
        if not linha.rstrip().endswith("\\"):
            break
    return "\n".join(linhas) + "\n"


def _funcao(texto: str, nome: str) -> str:
    a = texto.index(f"{nome}() {{")
    b = texto.index("\n}\n", a)
    return texto[a : b + 3]


# ---------------------------------------------------------------------------
# 1-2. install_udev.sh: máquina nova, duas vezes, e o opt-out que vai e volta
# ---------------------------------------------------------------------------

BLOCO_DO_INSTALL = INSTALL_UDEV[
    INSTALL_UDEV.index('if [[ "$ABRIR_O_NO" -eq 1 ]]; then\n    # A transformação tem UM DONO') :
    INSTALL_UDEV.index('sudo install -Dm644 "$ASSETS/71-uinput.rules"')
]


def _instalar(tmp: Path, *, abrir: bool = False) -> Path:
    etc = _etc(tmp)
    bloco = BLOCO_DO_INSTALL.replace(f"{ETC}/", f"{etc}/")
    assert ETC not in bloco.replace(str(etc), ""), bloco
    script = f'HERE="{RAIZ}"\nASSETS="{RAIZ}/assets"\nABRIR_O_NO={1 if abrir else 0}\n' + bloco
    r = _rodar(tmp, script)
    assert r.returncode == 0, r.stderr
    return etc


def test_o_install_numa_maquina_nova(tmp_path: Path) -> None:
    """Sem a regra de antes no disco: o `set -e` do script não perdoa um `rm` sem `-f`."""
    etc = _instalar(tmp_path)
    assert sorted(p.name for p in etc.iterdir()) == [NOVA]
    assert (etc / NOVA).read_bytes() == ASSET.read_bytes()


def test_o_install_duas_vezes_da_o_mesmo(tmp_path: Path) -> None:
    etc = _instalar(tmp_path)
    primeira = {p.name: p.read_bytes() for p in etc.iterdir()}
    _instalar(tmp_path)
    assert {p.name: p.read_bytes() for p in etc.iterdir()} == primeira


def test_o_opt_out_vai_e_volta(tmp_path: Path) -> None:
    """Fechada → aberta (`--no-fechar-o-no`) → fechada: o fim é o asset, byte a byte."""
    etc = _instalar(tmp_path)
    _instalar(tmp_path, abrir=True)
    aberta = _efetivas((etc / NOVA).read_text(encoding="utf-8"))
    assert not any('TAG-="uaccess"' in linha for linha in aberta), aberta
    _instalar(tmp_path)
    assert sorted(p.name for p in etc.iterdir()) == [NOVA]
    assert (etc / NOVA).read_bytes() == ASSET.read_bytes()


# ---------------------------------------------------------------------------
# 3. uninstall.sh: duas vezes, e a máquina que só tem a regra de antes
# ---------------------------------------------------------------------------

RM_DO_UNINSTALL = _comando_rm(UNINSTALL, depois_de='if [[ "${REMOVE_UDEV}" -eq 1 ]]; then')


def _desinstalar(tmp: Path, etc: Path) -> subprocess.CompletedProcess[str]:
    bloco = RM_DO_UNINSTALL.replace("/etc/", f"{tmp / 'etc'}/")
    assert not re.search(r"(^|\s)/etc/", bloco), bloco
    return _rodar(tmp, bloco)


def test_o_uninstall_depois_do_install_e_de_novo(tmp_path: Path) -> None:
    etc = _instalar(tmp_path)
    (etc / "99-de-outro-programa.rules").write_text("#\n", encoding="utf-8")
    r = _desinstalar(tmp_path, etc)
    assert r.returncode == 0, r.stderr
    assert sorted(p.name for p in etc.iterdir()) == ["99-de-outro-programa.rules"]
    # A segunda vez não acha nada, e não pode falhar por isso.
    r = _desinstalar(tmp_path, etc)
    assert r.returncode == 0, r.stderr
    assert sorted(p.name for p in etc.iterdir()) == ["99-de-outro-programa.rules"]


def test_o_uninstall_na_maquina_que_so_tem_a_velha(tmp_path: Path) -> None:
    etc = _etc(tmp_path)
    (etc / VELHA).write_text(ASSET.read_text(encoding="utf-8"), encoding="utf-8")
    r = _desinstalar(tmp_path, etc)
    assert r.returncode == 0, r.stderr
    assert list(etc.iterdir()) == []


# ---------------------------------------------------------------------------
# 4. --keep-udev: a regra do nó que fica vira a aberta, porque o broker sai
# ---------------------------------------------------------------------------

ABRIR_A_QUE_FICA = _funcao(UNINSTALL, "_abrir_a_regra_do_no_que_fica")


def _manter_udev(tmp: Path) -> subprocess.CompletedProcess[str]:
    corpo = ABRIR_A_QUE_FICA.replace(f"{ETC}/", f"{_etc(tmp)}/")
    assert ETC not in corpo.replace(str(_etc(tmp)), ""), corpo
    script = (
        f'ROOT_DIR="{RAIZ}"\nDRY_RUN=0\nlog() {{ printf "%s\\n" "$*"; }}\n'
        + corpo
        + "_abrir_a_regra_do_no_que_fica\n"
    )
    r = _rodar(tmp, script)
    assert r.returncode == 0, r.stderr
    return r


def _fechada(texto: str) -> bool:
    return any('TAG-="uaccess"' in linha for linha in _efetivas(texto))


@pytest.mark.parametrize("nome", [NOVA, VELHA])
def test_a_regra_fechada_que_fica_vira_a_aberta(tmp_path: Path, nome: str) -> None:
    """A de hoje e a de antes (um install anterior a 25/09 que nunca se atualizou)."""
    etc = _etc(tmp_path)
    (etc / nome).write_text(ASSET.read_text(encoding="utf-8"), encoding="utf-8")
    _manter_udev(tmp_path)
    assert sorted(p.name for p in etc.iterdir()) == [nome], "o --keep-udev preserva o nome"
    texto = (etc / nome).read_text(encoding="utf-8")
    assert not _fechada(texto), texto
    abertas = [linha for linha in _efetivas(texto) if 'TAG+="uaccess"' in linha]
    assert len(abertas) == 5, abertas  # as quatro físicas e a do vpad


#: Linhas de enchimento DEPOIS das fechadas: a saída do `grep -v` passa do
#: buffer do cano (64 KiB), e um `| grep -q` que ache cedo leva o produtor ao
#: SIGPIPE de forma determinística (a régua da casa é
#: `test_o_pipefail_nao_transforma_acerto_em_falha.py`; esta mede o EFEITO).
ENCHIMENTO = "".join(f'ENV{{HEFESTO_ENCHIMENTO}}="{i:06d}"\n' for i in range(8000))


def test_a_regra_grande_nao_engana_a_troca_sob_pipefail(tmp_path: Path) -> None:
    """Uma fechada grande: sob `pipefail` o cano com `grep -q` a leria como aberta."""
    etc = _etc(tmp_path)
    (etc / NOVA).write_text(ASSET.read_text(encoding="utf-8") + ENCHIMENTO, encoding="utf-8")
    _manter_udev(tmp_path)
    texto = (etc / NOVA).read_text(encoding="utf-8")
    assert not _fechada(texto), "a fechada grande ficou fechada, e o broker saiu"


def test_a_regra_grande_nao_engana_o_doctor_sob_pipefail(tmp_path: Path) -> None:
    """O mesmo cano no `_regra_do_no_e_a_aberta` do doctor, que roda com `pipefail`."""
    grande = tmp_path / NOVA
    grande.write_text(ASSET.read_text(encoding="utf-8") + ENCHIMENTO, encoding="utf-8")
    r = subprocess.run(
        [
            BASH,
            "-c",
            'set --; source "$DOCTOR_SH"; '
            'if _regra_do_no_e_a_aberta "$REGRA"; then echo ABERTA; else echo FECHADA; fi',
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env={"DOCTOR_SH": str(DOCTOR), "REGRA": str(grande), "PATH": "/usr/bin:/bin"},
    )
    assert r.stdout.strip() == "FECHADA", (r.stdout, r.stderr)


def test_com_a_regra_que_fica_o_fisico_volta_ao_mundo_de_antes(tmp_path: Path) -> None:
    """Pela cadeia inteira (o udev de bolso): o físico e o vpad com a ACL da sessão.

    É o estado de uma máquina sem o Hefesto: sem broker, um nó fechado é um
    controle que ninguém abre — nem a Steam, nem o jogo.
    """
    raiz = udev.montar(tmp_path, terceiros=udev.TERCEIROS_POR_MAQUINA["nenhuma"])
    _manter_udev(tmp_path)
    for nome, aparelho in sorted(udev.FISICOS.items()):
        assert udev.rodar(aparelho(), raiz).acl_da_sessao, nome
    assert udev.rodar(udev.o_vpad(), raiz).acl_da_sessao


def test_a_aberta_e_o_link_para_dev_null_ficam_como_estao(tmp_path: Path) -> None:
    """O que já não fecha nada não se toca: a aberta, e a regra que alguém desligou."""
    etc = _etc(tmp_path)
    aberta = udev._aberta()
    (etc / NOVA).write_text(aberta, encoding="utf-8")
    os.symlink("/dev/null", etc / VELHA)
    _manter_udev(tmp_path)
    assert (etc / NOVA).read_text(encoding="utf-8") == aberta
    assert (etc / VELHA).is_symlink() and os.readlink(etc / VELHA) == "/dev/null"


def test_a_fechada_que_nao_reabre_sai(tmp_path: Path) -> None:
    """A transformação recusa uma forma que ela não alcança: aberto é o lado seguro."""
    etc = _etc(tmp_path)
    estranha = (
        'KERNEL=="hidraw*", KERNELS=="0005:054C:0CE6.*", MODE="0600", TAG-="uaccess"\n'
    )
    (etc / NOVA).write_text(estranha, encoding="utf-8")
    r = _manter_udev(tmp_path)
    assert list(etc.iterdir()) == [], r.stdout


def test_o_keep_udev_duas_vezes(tmp_path: Path) -> None:
    etc = _etc(tmp_path)
    (etc / NOVA).write_text(ASSET.read_text(encoding="utf-8"), encoding="utf-8")
    _manter_udev(tmp_path)
    uma = (etc / NOVA).read_bytes()
    _manter_udev(tmp_path)
    assert (etc / NOVA).read_bytes() == uma


def test_o_ramo_do_keep_udev_chama_a_troca() -> None:
    """A função só vale se o ramo do `--keep-udev` a chamar (com a credencial)."""
    ramo = UNINSTALL[UNINSTALL.index("udev rules preservadas (--keep-udev)") - 1200 :]
    ramo = ramo[: ramo.index("udev rules preservadas (--keep-udev)")]
    assert "else\n" in ramo
    depois_do_else = ramo[ramo.rindex("\nelse\n") :]
    assert "_abrir_a_regra_do_no_que_fica\n" in depois_do_else, depois_do_else


def test_o_ensaio_do_keep_udev_so_diz(tmp_path: Path) -> None:
    """No `--dry-run` a troca vira uma linha FARIA, e nada se escreve."""
    etc = _etc(tmp_path)
    (etc / NOVA).write_text(ASSET.read_text(encoding="utf-8"), encoding="utf-8")
    corpo = ABRIR_A_QUE_FICA.replace(f"{ETC}/", f"{etc}/")
    script = (
        f'ROOT_DIR="{RAIZ}"\nDRY_RUN=1\nlog() {{ :; }}\n'
        '_faria() { printf "FARIA %s\\n" "$*"; }\n'
        + corpo
        + "_abrir_a_regra_do_no_que_fica\n"
    )
    r = _rodar(tmp_path, script)
    assert r.returncode == 0, r.stderr
    assert "FARIA (root) trocar" in r.stdout, r.stdout
    assert (etc / NOVA).read_bytes() == ASSET.read_bytes()


# ---------------------------------------------------------------------------
# 5. install-host-udev.sh: o comando de root roda limpo numa máquina nova
# ---------------------------------------------------------------------------


def _comandos_do_helper(tmp: Path, etc: Path, src: Path) -> list[str]:
    escopo = "\n".join(
        (
            'BROKER_BIN_SRC="" BROKER_INSTALL_OK=1 BROKER_SESSION_GROUP="" BROKER_SESSION_UID=0',
            'BROKER_UNITS_SRC="" BTRES_INSTALL_OK=0 BTRES_SCRIPTS_SRC="" BTRES_UNIT_SRC=""',
            'BTUSB_SRC="" HIDNINTENDO_SRC="" HIDPLAYSTATION_SRC=""',
            'MODLOAD_DEST=/x MODLOAD_SRC="" SNDQUIRK_DEST=/x SNDQUIRK_SRC=""',
            f'RULES_SRC="{src}" RULES_DEST="{etc}"',
            f'RULES=("{NOVA}")',
            f'REGRA_DO_NO="{NOVA}" REGRA_DO_NO_SRC="{src}/{NOVA}" REGRA_DO_NO_VELHA="{VELHA}"',
        )
    )
    montador = _funcao(HOST_UDEV, "_build_install_cmd")
    r = _rodar(tmp, escopo + "\n" + montador + "_build_install_cmd\n")
    assert r.returncode == 0, r.stderr
    return [
        c.strip()
        for c in r.stdout.split("; ")
        if c.strip().startswith(("install -Dm644", "rm ")) and str(etc) in c
    ]


def test_o_helper_roda_limpo_numa_maquina_nova_e_duas_vezes(tmp_path: Path) -> None:
    """Como ele roda de verdade: `bash -c` SEM `set -e` — o erro vira ruído na tela dela."""
    src = tmp_path / "src"
    src.mkdir()
    shutil.copy(ASSET, src / NOVA)
    etc = _etc(tmp_path)
    comandos = "\n".join(_comandos_do_helper(tmp_path, etc, src)) + "\n"
    for _ in range(2):
        r = _rodar(tmp_path, comandos, estrito=False)
        assert r.returncode == 0 and r.stderr == "", r.stderr
    assert sorted(p.name for p in etc.iterdir()) == [NOVA]


# ---------------------------------------------------------------------------
# 6. Os pacotes: a remoção numa máquina em que o helper nunca rodou
# ---------------------------------------------------------------------------

REMOCAO = {
    "deb": (RAIZ / "packaging" / "debian" / "prerm", "\n    remove)\n"),
    "arch": (RAIZ / "packaging" / "arch" / "hefesto-dualsense4unix.install", "pre_remove() {"),
    "fedora": (RAIZ / "packaging" / "fedora" / "hefesto-dualsense4unix.spec", "\n%preun\n"),
}
POS_INSTALACAO = {
    "deb": RAIZ / "packaging" / "debian" / "postinst",
    "arch": RAIZ / "packaging" / "arch" / "hefesto-dualsense4unix.install",
    "fedora": RAIZ / "packaging" / "fedora" / "hefesto-dualsense4unix.spec",
}


def _bloco_do_mv(texto: str) -> str:
    abre = f"if [ -e {ETC}/{VELHA} ]; then"
    i = texto.index(abre)
    comeco = texto.rfind("\n", 0, i) + 1
    recuo = texto[comeco:i]
    fim = texto.index(f"\n{recuo}fi\n", i) + len(recuo) + 4
    return texto[comeco:fim]


def _no_etc_de_mentira(bloco: str, tmp: Path) -> str:
    trocado = bloco.replace(f"{ETC}/", f"{_etc(tmp)}/")
    assert ETC not in trocado.replace(str(_etc(tmp)), ""), trocado
    return trocado


@pytest.mark.parametrize("pacote", sorted(REMOCAO))
def test_a_remocao_numa_maquina_em_que_o_helper_nunca_rodou(tmp_path: Path, pacote: str) -> None:
    """Nada em /etc: o `prerm` do .deb corre sob `set -e`, e um `rm` que falha o trava."""
    arquivo, secao = REMOCAO[pacote]
    rm = _comando_rm(arquivo.read_text(encoding="utf-8"), depois_de=secao)
    r = _rodar(tmp_path, _no_etc_de_mentira(rm, tmp_path))
    assert r.returncode == 0, r.stderr


@pytest.mark.parametrize("pacote", sorted(REMOCAO))
def test_o_ciclo_do_pacote_nao_deixa_rastro(tmp_path: Path, pacote: str) -> None:
    """A 70 fechada do helper → a atualização (duas vezes) → a remoção: /etc vazio."""
    etc = _etc(tmp_path)
    (etc / VELHA).write_text(ASSET.read_text(encoding="utf-8"), encoding="utf-8")
    pos = POS_INSTALACAO[pacote].read_text(encoding="utf-8")
    mv = _no_etc_de_mentira(_bloco_do_mv(pos), tmp_path)
    for _ in range(2):
        assert _rodar(tmp_path, mv).returncode == 0
        assert sorted(p.name for p in etc.iterdir()) == [NOVA]
    assert (etc / NOVA).read_bytes() == ASSET.read_bytes()
    arquivo, secao = REMOCAO[pacote]
    rm = _comando_rm(arquivo.read_text(encoding="utf-8"), depois_de=secao)
    assert _rodar(tmp_path, _no_etc_de_mentira(rm, tmp_path)).returncode == 0
    assert list(etc.iterdir()) == []


# ---------------------------------------------------------------------------
# 7. O doctor só lê, e não diz que a barra está acesa
# ---------------------------------------------------------------------------

#: As funções que a sprint pôs no doctor. Nenhuma pode escrever na máquina.
FUNCOES_NOVAS_DO_DOCTOR = (
    "_regras_udev_em_ordem",
    "_caminho_da_regra_do_no",
    "_regra_do_no_instalada",
    "_regra_do_no_e_a_aberta",
    "_regras_que_reabrem_o_fisico",
    "_tags_correntes_do_no",
    "_veredito_do_no_fisico_no_udev",
    "check_o_no_fisico_nasce_sem_acl",
    "_veredito_de_quem_segura_o_fisico",
    "_nascimentos_do_daemon",
    "_veredito_dos_nascimentos",
    "check_quem_segura_o_fisico",
)

_VERBO_QUE_ESCREVE = re.compile(
    r"\b(sudo|pkexec|udevadm|setfacl|chmod|chown|chgrp|rm|mv|cp|ln|install|tee|touch|"
    r"mkdir|truncate|systemctl|bluetoothctl|busctl|pkill|kill|modprobe|rmmod)\b"
)


def _codigo_sem_texto(corpo: str) -> str:
    """O corpo sem o que não executa: heredoc, comentário e texto entre aspas."""
    corpo = re.sub(r"<<'PYEOF'.*?\nPYEOF\n", "\n", corpo, flags=re.S)
    corpo = re.sub(r"'[^']*'", "''", corpo)
    corpo = re.sub(r'"(?:[^"\\]|\\.)*"', '""', corpo)
    return "\n".join(
        linha.split(" #", 1)[0]
        for linha in corpo.splitlines()
        if not linha.lstrip().startswith("#")
    )


@pytest.mark.parametrize("nome", FUNCOES_NOVAS_DO_DOCTOR)
def test_as_funcoes_novas_do_doctor_so_leem(nome: str) -> None:
    codigo = _codigo_sem_texto(_funcao(DOCTOR.read_text(encoding="utf-8"), nome))
    assert not _VERBO_QUE_ESCREVE.findall(codigo), (nome, _VERBO_QUE_ESCREVE.findall(codigo))
    # Redirecionar para arquivo também escreve; só o /dev/null e os descritores valem.
    for alvo in re.findall(r"(?<![<0-9&])[0-9]?>>?\s*([^\s;|)]+)", codigo):
        assert alvo.startswith(("/dev/null", "&")), (nome, alvo)


def test_o_ipc_do_doctor_so_pergunta_o_estado() -> None:
    corpo = _funcao(DOCTOR.read_text(encoding="utf-8"), "_nascimentos_do_daemon")
    metodos = re.findall(r'"method":\s*"([^"]+)"', corpo)
    assert metodos == ["daemon.state_full"], metodos


def _servidor_de_mentira(caminho: Path, resultado: dict[str, object]) -> threading.Thread:
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(str(caminho))
    srv.listen(1)

    def _laco() -> None:
        conn, _ = srv.accept()
        try:
            conn.settimeout(5.0)
            buf = b""
            while not buf.endswith(b"\n"):
                pedaco = conn.recv(65536)
                if not pedaco:
                    break
                buf += pedaco
            resposta = json.dumps({"jsonrpc": "2.0", "id": 1, "result": resultado})
            conn.sendall(resposta.encode("utf-8") + b"\n")
        finally:
            conn.close()
            srv.close()

    fio = threading.Thread(target=_laco, daemon=True)
    fio.start()
    return fio


def test_o_doctor_diz_a_cor_pedida_e_nao_a_lampada(tmp_path: Path) -> None:
    """Em 25/09 a linha dizia `lightbar_rgb=[0, 255, 0]` sobre a barra APAGADA do P3.

    O socket é um servidor de mentira: o `runtime_socket` é trocado DEPOIS do
    `source`, e nenhum IPC chega ao daemon dela.
    """
    caminho = tmp_path / "d.sock"
    fio = _servidor_de_mentira(
        caminho,
        {
            "game_signal": {"authority": "daemon"},
            "controllers": [
                {"player_slot": 3, "lightbar_source": "sysfs", "lightbar_rgb": [0, 255, 0]},
            ],
        },
    )
    r = subprocess.run(
        [
            BASH,
            "-c",
            'set --; source "$DOCTOR_SH"; runtime_socket() { printf "%s" "$SOCK"; }; '
            "check_display_authority",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env={
            "DOCTOR_SH": str(DOCTOR),
            "SOCK": str(caminho),
            "PATH": "/usr/bin:/bin",
            "LC_ALL": "C.UTF-8",
            "HOME": str(tmp_path),
        },
    )
    fio.join(5)
    assert r.returncode == 0, r.stderr
    assert "player_slot=3 lightbar_source=sysfs cor_pedida=[0, 255, 0]" in r.stdout, r.stdout
    assert "lightbar_rgb=" not in r.stdout, r.stdout

"""Os pacotes levam a regra do nó para o nome novo, e a tiram quando saem.

O-FISICO-NASCE-ESCONDIDO-EM-QUALQUER-MAQUINA-01, conferência de 25/09/2026.
A regra que fecha o hidraw do DualSense físico passou de `70-ps5-controller.rules`
para `73-hefesto-ps5-controller.rules`. Nos pacotes (.deb, Arch, Fedora) a cura
tem duas cópias com o MESMO nome, e é o nome igual que a faz valer:

- o pacote grava a variante ABERTA em /usr/lib (sem broker, ninguém abriria
  um nó fechado);
- o `install-host-udev.sh`, quando instala o broker, grava a FECHADA em /etc,
  e /etc sombreia /usr/lib só quando o nome é o mesmo.

O DEFEITO QUE A CONFERÊNCIA ACHOU: quem já tinha rodado o helper tem a 70
FECHADA em /etc, fora do manifesto do pacote. A atualização troca a 70 aberta
de /usr/lib pela 73 aberta, e a 70 de /etc deixa de sombreá-la: a 73 aberta
corre DEPOIS e reabre o nó em TODA máquina, com ou sem a `71-sony`, até
alguém rodar o helper de novo. A cura é o pós-instalação levar a 70 de /etc
para o nome novo — e ela leva a ESCOLHA de quem instalou (a fechada ou a
aberta), sem decidir por ninguém.

E o outro lado: a remoção do pacote desliga o broker, e a 73 fechada que o
helper gravou em /etc ficava — o DualSense físico nascia `0600 root` para
sempre, sem ninguém para abri-lo. As duas metades da cura viajam juntas, ou
nenhuma (`scripts/regra_do_no_aberta.sh`).

Os blocos são recortados dos scriptlets REAIS e rodam com o /etc trocado por
uma pasta de mentira. Nada aqui toca o /etc de verdade.

AS MORDIDAS, medidas: tirar o bloco do `mv` de qualquer um dos três reprova o
caso da atualização daquele pacote; tirar o `rm` da remoção reprova o caso da
remoção daquele pacote.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

BASH = shutil.which("bash") or "/bin/bash"
RAIZ = Path(__file__).resolve().parents[2]
NOVA = "73-hefesto-ps5-controller.rules"
VELHA = "70-ps5-controller.rules"
ETC = "/etc/udev/rules.d"

POS_INSTALACAO = {
    "deb": RAIZ / "packaging" / "debian" / "postinst",
    "arch": RAIZ / "packaging" / "arch" / "hefesto-dualsense4unix.install",
    "fedora": RAIZ / "packaging" / "fedora" / "hefesto-dualsense4unix.spec",
}
REMOCAO = {
    "deb": RAIZ / "packaging" / "debian" / "prerm",
    "arch": RAIZ / "packaging" / "arch" / "hefesto-dualsense4unix.install",
    "fedora": RAIZ / "packaging" / "fedora" / "hefesto-dualsense4unix.spec",
}


def _bloco_do_mv(texto: str) -> str:
    """Do `if [ -e …/70 ]` até o `fi` da MESMA indentação."""
    abre = f"if [ -e {ETC}/{VELHA} ]; then"
    i = texto.index(abre)
    comeco = texto.rfind("\n", 0, i) + 1
    recuo = texto[comeco:i]
    fim = texto.index(f"\n{recuo}fi\n", i) + len(recuo) + 4
    return texto[comeco:fim]


def _linha_do_rm(texto: str) -> str:
    """O `rm -f` dos dois nomes da regra do nó, com a continuação."""
    i = texto.index(f"rm -f {ETC}/{NOVA} \\")
    comeco = texto.rfind("\n", 0, i) + 1
    linhas = []
    for linha in texto[comeco:].splitlines():
        linhas.append(linha)
        if not linha.rstrip().endswith("\\"):
            break
    return "\n".join(linhas) + "\n"


def _rodar(bloco: str, etc: Path) -> None:
    trocado = bloco.replace(f"{ETC}/", f"{etc}/")
    assert ETC not in trocado.replace(str(etc), ""), trocado
    r = subprocess.run(
        [BASH, "-c", "set -eu\n" + trocado],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env={"PATH": "/usr/bin:/bin", "LC_ALL": "C.UTF-8"},
    )
    assert r.returncode == 0, r.stderr


def _etc(tmp: Path) -> Path:
    etc = tmp / "etc" / "udev" / "rules.d"
    etc.mkdir(parents=True)
    return etc


# ---------------------------------------------------------------------------
# A atualização: a 70 de /etc vira a 73, com a escolha de quem instalou
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("pacote", sorted(POS_INSTALACAO))
def test_a_70_de_etc_vira_a_73_com_o_mesmo_conteudo(tmp_path: Path, pacote: str) -> None:
    """A fechada do helper segue fechada, agora com o nome que sombreia a do pacote."""
    etc = _etc(tmp_path)
    (etc / VELHA).write_text("# a fechada que o helper gravou\n", encoding="utf-8")
    _rodar(_bloco_do_mv(POS_INSTALACAO[pacote].read_text(encoding="utf-8")), etc)
    assert sorted(p.name for p in etc.iterdir()) == [NOVA]
    assert (etc / NOVA).read_text(encoding="utf-8") == "# a fechada que o helper gravou\n"


@pytest.mark.parametrize("pacote", sorted(POS_INSTALACAO))
def test_com_as_duas_em_etc_a_de_hoje_fica(tmp_path: Path, pacote: str) -> None:
    etc = _etc(tmp_path)
    (etc / VELHA).write_text("# a de antes\n", encoding="utf-8")
    (etc / NOVA).write_text("# a de hoje\n", encoding="utf-8")
    _rodar(_bloco_do_mv(POS_INSTALACAO[pacote].read_text(encoding="utf-8")), etc)
    assert sorted(p.name for p in etc.iterdir()) == [NOVA]
    assert (etc / NOVA).read_text(encoding="utf-8") == "# a de hoje\n"


@pytest.mark.parametrize("pacote", sorted(POS_INSTALACAO))
def test_sem_nenhuma_em_etc_nada_nasce(tmp_path: Path, pacote: str) -> None:
    """O pós-instalação não grava regra nenhuma: quem grava em /etc é o helper."""
    etc = _etc(tmp_path)
    _rodar(_bloco_do_mv(POS_INSTALACAO[pacote].read_text(encoding="utf-8")), etc)
    assert list(etc.iterdir()) == []


@pytest.mark.parametrize("pacote", sorted(POS_INSTALACAO))
def test_o_mv_vem_antes_do_reload(pacote: str) -> None:
    """Depois do reload, o udev já estaria lendo a cadeia com a sombra quebrada."""
    texto = POS_INSTALACAO[pacote].read_text(encoding="utf-8")
    assert texto.index(f"if [ -e {ETC}/{VELHA} ]") < texto.index("udevadm control --reload-rules")


# ---------------------------------------------------------------------------
# A remoção: a regra do nó sai junto com o broker
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("pacote", sorted(REMOCAO))
def test_a_remocao_tira_os_dois_nomes(tmp_path: Path, pacote: str) -> None:
    etc = _etc(tmp_path)
    for nome in (NOVA, VELHA, "99-de-outro-programa.rules"):
        (etc / nome).write_text("#\n", encoding="utf-8")
    _rodar(_linha_do_rm(REMOCAO[pacote].read_text(encoding="utf-8")), etc)
    assert sorted(p.name for p in etc.iterdir()) == ["99-de-outro-programa.rules"]


def test_a_remocao_so_roda_na_remocao_de_verdade() -> None:
    """Na ATUALIZAÇÃO a regra fica: o broker também fica."""
    deb = REMOCAO["deb"].read_text(encoding="utf-8")
    i = deb.index(f"rm -f {ETC}/{NOVA}")
    assert deb.rfind("\n    remove)\n", 0, i) > deb.rfind("remove|upgrade|deconfigure)", 0, i)

    arch = REMOCAO["arch"].read_text(encoding="utf-8")
    i = arch.index(f"rm -f {ETC}/{NOVA}")
    assert arch.rfind("pre_remove() {", 0, i) > arch.rfind("post_install() {", 0, i)

    spec = REMOCAO["fedora"].read_text(encoding="utf-8")
    i = spec.index(f"rm -f {ETC}/{NOVA}")
    preun = spec.rfind("\n%preun\n", 0, i)
    assert preun != -1 and spec.find("if [ $1 -eq 0 ]; then", preun) < i
    assert spec.find("\n%", preun + 2) > i, "o rm saiu do %preun"

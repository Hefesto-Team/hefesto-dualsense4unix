"""O passo 3f decide pelo BINÁRIO que o systemd executa, e não pela versão.

INSTALL-E-UNINSTALL-DO-RADIO-01 (23/09/2026), o pedido P-5 da
BLUETOOTHD-NAO-DERRUBA-01, na forma que quem coordena decidiu:

- o portão de antes perguntava `bluetoothd --version` («5.86» no .3 e no .4) e
  pulava por «já ≥ 5.79»: o .4 — o do hefesto-0002, em que o EAGAIN do socket
  L2CAP deixa de derrubar a sessão dos controles — nunca chegaria sobre o .3,
  que é o que roda na máquina dela;
- e comparar a versão do dpkg também não basta: um 5.86-0ubuntu0.1 OFICIAL
  passa de qualquer `~hefesto` na ordem do dpkg sem trazer patch nenhum.

A pergunta vai às marcas que cada patch deixa no binário
(`MARCA_hefesto-NNNN` do `assets/bluez-backport/BASELINE`). As funções são
recortadas do `install.sh` REAL e rodadas com binários, `dpkg` e `apt-cache` de
mentira.

A MORDIDA, medida: trocar o laço das marcas pelo `--version ≥ 5.79` de antes
reprova o caso do .3 e o do oficial; tirar o `dpkg -S`, o do tarball.
"""

from __future__ import annotations

import re
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

BASH = shutil.which("bash") or "/bin/bash"
DPKG = shutil.which("dpkg")
RAIZ = Path(__file__).resolve().parents[2]
INSTALL = (RAIZ / "install.sh").read_text(encoding="utf-8")
DOCTOR = (RAIZ / "scripts" / "doctor.sh").read_text(encoding="utf-8")
BASELINE = RAIZ / "assets" / "bluez-backport" / "BASELINE"
ALVO = "5.86-0ubuntu0.1~hefesto24.04.4"

pytestmark = pytest.mark.skipif(DPKG is None, reason="sem dpkg para comparar versões")


def _funcao(nome: str) -> str:
    inicio = INSTALL.index(f"{nome}() {{\n")
    fim = INSTALL.index("\n}\n", inicio) + 3
    return INSTALL[inicio:fim]


def _marcas() -> dict[str, str]:
    return dict(
        re.findall(r"^MARCA_([^=]+)=(.*)$", BASELINE.read_text(encoding="utf-8"), re.MULTILINE)
    )


def _fake(pasta: Path, nome: str, corpo: str) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    alvo = pasta / nome
    alvo.write_text("#!/bin/bash\n" + corpo, encoding="utf-8")
    alvo.chmod(alvo.stat().st_mode | stat.S_IEXEC)


def _veredito(
    tmp_path: Path,
    *,
    marcas: list[str] | None,
    do_dpkg: bool = True,
    versoes: dict[str, str] | None = None,
    baseline: Path = BASELINE,
) -> tuple[str, str]:
    fakes = tmp_path / "fakes"
    binario = tmp_path / "bluetoothd"
    if marcas is not None:
        todas = _marcas()
        binario.write_bytes(
            b"\x7fELF\x00lixo\x00" + b"\x00".join(todas[m].encode() for m in marcas) + b"\x00fim"
        )
    versoes = versoes or {"bluez": ALVO, "bluez-cups": ALVO, "libbluetooth3": ALVO}
    casos = "\n".join(f'  {p}) echo -n "{v}" ;;' for p, v in versoes.items())
    _fake(
        fakes,
        "dpkg",
        f'if [[ "$1" == "-S" ]]; then exit {0 if do_dpkg else 1}; fi\nexec "{DPKG}" "$@"\n',
    )
    _fake(fakes, "dpkg-query", f'case "${{@: -1}}" in\n{casos}\nesac\nexit 0\n')
    script = (
        "set -euo pipefail\n"
        + _funcao("_bz_veredito")
        + f'_bz_veredito "{binario if marcas is not None else ""}" "{baseline}" "{ALVO}"\n'
    )
    r = subprocess.run(
        [BASH, "-c", script],
        env={"PATH": f"{fakes}:/usr/bin:/bin"},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert r.returncode == 0, r.stderr
    veredito, _, detalhe = r.stdout.rstrip("\n").partition("\t")
    return veredito, detalhe


def test_o_baseline_tem_as_duas_marcas() -> None:
    """Controle: sem marcas no dono do fato, as réguas abaixo não medem nada."""
    assert {"hefesto-0001", "hefesto-0002"} <= set(_marcas())


def test_o_4_de_pe_e_curado(tmp_path: Path) -> None:
    assert _veredito(tmp_path, marcas=["hefesto-0001", "hefesto-0002"])[0] == "curado"


def test_o_3_da_maquina_dela_precisa_do_4(tmp_path: Path) -> None:
    veredito, detalhe = _veredito(
        tmp_path,
        marcas=["hefesto-0001"],
        versoes={
            "bluez": "5.86-0ubuntu0.1~hefesto24.04.3",
            "bluez-cups": "5.86-0ubuntu0.1~hefesto24.04.3",
            "libbluetooth3": "5.86-0ubuntu0.1~hefesto24.04.2",
        },
    )
    assert veredito == "precisa", (
        "o bluetoothd .3 (sem o hefesto-0002) passou por curado — é exatamente o "
        "pulo que o portão pela versão dava"
    )
    assert "hefesto-0002" in detalhe


def test_o_5_86_oficial_sem_patch_nao_passa_por_curado(tmp_path: Path) -> None:
    veredito, _ = _veredito(
        tmp_path,
        marcas=[],
        versoes={
            "bluez": "5.86-0ubuntu0.1",
            "bluez-cups": "5.86-0ubuntu0.1",
            "libbluetooth3": "5.86-0ubuntu0.1",
        },
    )
    assert veredito == "precisa", "o 5.86 oficial passa de ~hefesto no dpkg e não traz patch"


def test_o_tarball_fora_do_dpkg_nao_e_trocado_pelo_pacote(tmp_path: Path) -> None:
    veredito, detalhe = _veredito(tmp_path, marcas=["hefesto-0001"], do_dpkg=False)
    assert veredito == "fora-do-dpkg", veredito
    assert "hefesto-0002" in detalhe


def test_binario_curado_com_a_biblioteca_atras(tmp_path: Path) -> None:
    veredito, detalhe = _veredito(
        tmp_path,
        marcas=["hefesto-0001", "hefesto-0002"],
        versoes={
            "bluez": ALVO,
            "bluez-cups": ALVO,
            "libbluetooth3": "5.86-0ubuntu0.1~hefesto24.04.2",
        },
    )
    assert veredito == "atras", veredito
    assert "libbluetooth3" in detalhe


def test_sem_binario(tmp_path: Path) -> None:
    assert _veredito(tmp_path, marcas=None)[0] == "sem-binario"


def test_baseline_sem_marca_e_nao_sei_e_nunca_curado(tmp_path: Path) -> None:
    """Sem marca nenhuma no dono do fato, não houve pergunta ao binário.

    Conferência da INSTALL-E-UNINSTALL-DO-RADIO-01: o laço vazio deixava
    `faltam` vazio, e um 5.86 OFICIAL — que passa de qualquer ~hefesto no
    dpkg — saía «curado» sem ter sido perguntado. A MORDIDA: tirar o
    `perguntadas -eq 0` faz este caso voltar a dizer «curado».
    """
    vazio = tmp_path / "BASELINE-sem-marcas"
    vazio.write_text(
        "# um BASELINE que perdeu as linhas MARCA_\nREVISAO_ULTIMA=4\n", encoding="utf-8"
    )
    veredito, _ = _veredito(
        tmp_path,
        marcas=[],
        versoes={
            "bluez": "5.86-0ubuntu0.1",
            "bluez-cups": "5.86-0ubuntu0.1",
            "libbluetooth3": "5.86-0ubuntu0.1",
        },
        baseline=vazio,
    )
    assert veredito == "sem-marcas", veredito
    assert "sem-marcas)" in _bloco_3f(), "o 3f não trata o «não sei» do veredito"


def test_o_registro_leva_a_versao_que_o_archive_serve(tmp_path: Path) -> None:
    fakes = tmp_path / "fakes"
    _fake(
        fakes,
        "apt-cache",
        "cat <<'X'\n"
        "     bluez | 5.86-0ubuntu0.1~hefesto24.04.4 | file:/cache Packages\n"
        "     bluez | 5.72-0ubuntu5.5 | http://apt.pop-os.org/ubuntu noble-updates/main "
        "amd64 Packages\n"
        "     bluez | 5.72-0ubuntu5 | http://apt.pop-os.org/ubuntu noble/main amd64 Packages\n"
        "X\n",
    )
    _fake(fakes, "dpkg", f'exec "{DPKG}" "$@"\n')
    script = (
        "set -euo pipefail\n" + _funcao("_bz_maior_do_archive") + "_bz_maior_do_archive bluez\n"
    )
    r = subprocess.run(
        [BASH, "-c", script],
        env={"PATH": f"{fakes}:/usr/bin:/bin"},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert r.stdout.strip() == "5.72-0ubuntu5.5", r.stdout + r.stderr


def _bloco_3f() -> str:
    inicio = INSTALL.index('step "3f"')
    fim = INSTALL.index('step "3g"', inicio)
    return INSTALL[inicio:fim]


def test_os_debs_sao_os_da_versao_alvo_e_nunca_o_mais_novo_do_diretorio() -> None:
    bloco = _bloco_3f()
    codigo = "\n".join(
        linha for linha in bloco.splitlines() if not linha.lstrip().startswith("#")
    )
    assert "ls -t" not in codigo, (
        "o 3f voltou a escolher o .deb mais novo do diretório — um .deb fora do "
        "SHA256SUMS podia ser o instalado"
    )
    assert '${_bz_pkg}_${_BZ_TARGET}_${_bz_arch}.deb' in codigo


def test_a_receita_apontada_e_o_script_que_constroi() -> None:
    for nome, texto in (("install.sh", INSTALL), ("scripts/doctor.sh", DOCTOR)):
        assert "seção 3, caminho 1" not in texto, (
            f"{nome} ainda manda para a receita à mão (dget/dch) em vez do "
            "scripts/construir_bluez_backport.sh"
        )
    assert "scripts/construir_bluez_backport.sh" in _bloco_3f()


# ---------------------------------------------------------------------------
# O doctor faz a mesma pergunta
# ---------------------------------------------------------------------------


def _doctor(tmp_path: Path, marcas: list[str], **extra: str) -> str:
    todas = _marcas()
    binario = tmp_path / "bluetoothd-doctor"
    binario.write_bytes(b"\x00".join(todas[m].encode() for m in marcas) + b"\x00")
    r = subprocess.run(
        [BASH, "-c", f'source "{RAIZ / "scripts" / "doctor.sh"}"; check_bluez_curas_do_backport'],
        env={
            "PATH": "/usr/bin:/bin",
            "HOME": str(tmp_path),
            "HEFESTO_DOCTOR_BLUETOOTHD": str(binario),
            **extra,
        },
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    return r.stdout + r.stderr


def test_o_doctor_acusa_o_bluetoothd_sem_o_0002(tmp_path: Path) -> None:
    saida = _doctor(tmp_path, ["hefesto-0001"])
    assert "[WARN]" in saida and "hefesto-0002" in saida, saida


def test_o_doctor_passa_o_bluetoothd_com_as_curas(tmp_path: Path) -> None:
    saida = _doctor(tmp_path, ["hefesto-0001", "hefesto-0002"])
    assert "[ OK ] o bluetoothd em execução traz as curas" in saida, saida


def test_o_doctor_sem_marca_no_baseline_diz_que_nao_sabe(tmp_path: Path) -> None:
    """MORDIDA: tirar o ramo `else` do doctor faz a linha sumir — silêncio."""
    vazio = tmp_path / "BASELINE-sem-marcas"
    vazio.write_text("REVISAO_ULTIMA=4\n", encoding="utf-8")
    saida = _doctor(tmp_path, [], HEFESTO_DOCTOR_BLUEZ_BASELINE=str(vazio))
    assert "não sei conferir as curas do backport" in saida, saida
    assert "[WARN]" not in saida, saida
    assert "[ OK ]" not in saida, saida


def test_o_doctor_sem_dpkg_nao_manda_rodar_o_install(tmp_path: Path) -> None:
    """Numa distro sem dpkg o 3f não existe: mandar rodar o install é mandar
    repetir o que não entrega. MORDIDA: tirar a guarda do dpkg volta o WARN."""
    saida = _doctor(tmp_path, ["hefesto-0001"], HEFESTO_DOCTOR_DPKG="dpkg-que-nao-existe")
    assert "[WARN]" not in saida, saida
    assert "sem dpkg nesta distro" in saida, saida

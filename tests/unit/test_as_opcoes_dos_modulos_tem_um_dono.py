"""As opções dos módulos têm UM dono: a conf de `assets/modprobe.d/`."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.unit.fonte_do_instalador import texto_do_install_sh, texto_do_instalador

BASH = shutil.which("bash") or "/bin/bash"
RAIZ = Path(__file__).resolve().parents[2]
CONFS = RAIZ / "assets" / "modprobe.d"
LIB = (RAIZ / "scripts" / "lib" / "camada_de_maquina.sh").read_text(encoding="utf-8")
HOST_UDEV = (RAIZ / "scripts" / "install-host-udev.sh").read_text(encoding="utf-8")


def _opcoes_das_confs() -> dict[tuple[str, str], tuple[str, str]]:
    """`{(módulo, opção): (valor, conf)}` de todas as linhas `options` das confs."""
    opcoes: dict[tuple[str, str], tuple[str, str]] = {}
    for conf in sorted(CONFS.glob("*.conf")):
        for linha in conf.read_text(encoding="utf-8").splitlines():
            partes = linha.split()
            if len(partes) < 3 or partes[0] != "options":
                continue
            for par in partes[2:]:
                chave, _, valor = par.partition("=")
                opcoes[(partes[1], chave)] = (valor, conf.name)
    return opcoes


OPCOES = _opcoes_das_confs()
NOMES_COM_DONO = {opcao for _modulo, opcao in OPCOES}


def _funcao(texto: str, nome: str) -> str:
    achado = re.search(rf"^{re.escape(nome)}\(\) \{{\n", texto, re.MULTILINE)
    assert achado is not None, f"a função {nome}() sumiu"
    fim = re.search(r"^\}$", texto[achado.end() :], re.MULTILINE)
    assert fim is not None, f"o fim de {nome}() sumiu"
    return texto[achado.start() : achado.end() + fim.end() + 1]


def _executa(texto: str) -> list[str]:
    """Linhas que podem executar: sem comentário, com a continuação por `\\` colada."""
    return [
        linha
        for linha in texto.replace("\\\n", " ").splitlines()
        if linha.strip() and not linha.lstrip().startswith("#")
    ]


LEITORES = {
    "lib (install.sh)": _funcao(LIB, "opcao_do_modprobe"),
    "install-host-udev.sh": _funcao(HOST_UDEV, "_opcao_do_modprobe"),
}


def _ler(leitor: str, conf: Path, opcao: str) -> subprocess.CompletedProcess[str]:
    nome = re.match(r"(\w+)\(\)", leitor)
    assert nome is not None
    return subprocess.run(
        [BASH, "-c", f'{leitor}\n{nome.group(1)} "$1" "$2"', "leitor", str(conf), opcao],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env={"PATH": "/usr/bin:/bin"},
    )


def test_as_confs_declaram_as_opcoes_que_a_regua_vai_medir() -> None:
    """Guarda da premissa: sem opções, as réguas de baixo mediriam o vazio."""
    assert ("hid_playstation", "feature_retries") in OPCOES, sorted(OPCOES)
    assert len(OPCOES) >= 10, sorted(OPCOES)


@pytest.mark.parametrize("onde", sorted(LEITORES))
def test_o_leitor_devolve_o_valor_de_cada_opcao_de_cada_conf(onde: str) -> None:
    errados = []
    for (modulo, opcao), (valor, conf) in sorted(OPCOES.items()):
        r = _ler(LEITORES[onde], CONFS / conf, opcao)
        if r.returncode != 0 or r.stdout.strip() != valor:
            errados.append(f"{modulo}.{opcao}: conf diz {valor!r}, leu {r.stdout.strip()!r}")
    assert errados == [], f"o leitor de {onde} não responde o que a conf declara: {errados}"


@pytest.mark.parametrize("onde", sorted(LEITORES))
def test_opcao_ausente_nao_vira_valor_vazio(onde: str) -> None:
    r = _ler(LEITORES[onde], CONFS / "hefesto-hid-playstation.conf", "opcao_que_nao_existe")
    assert (r.returncode, r.stdout) == (1, ""), (r.returncode, r.stdout)


@pytest.mark.parametrize("onde", sorted(LEITORES))
def test_valor_com_forma_estranha_e_recusado(onde: str, tmp_path: Path) -> None:
    """O caminho por pacote põe o valor entre aspas simples num comando de root."""
    conf = tmp_path / "estranha.conf"
    conf.write_text("options hid_playstation feature_retries=1';reboot;'\n", encoding="utf-8")
    r = _ler(LEITORES[onde], conf, "feature_retries")
    assert (r.returncode, r.stdout) == (1, ""), (r.returncode, r.stdout)


def test_a_ultima_linha_options_vence_como_no_modprobe(tmp_path: Path) -> None:
    conf = tmp_path / "duas.conf"
    conf.write_text(
        "# options hid_playstation feature_retries=9\n"
        "options hid_playstation feature_retries=1\n"
        "options hid_playstation ds4_synthetic_mac=1 feature_retries=3\n",
        encoding="utf-8",
    )
    for onde, leitor in LEITORES.items():
        assert _ler(leitor, conf, "feature_retries").stdout.strip() == "3", onde


_ESCRITA_DIGITADA = re.compile(
    r"printf\s+'([^'%$]*)'\s*(?:\|\s*sudo\s+tee\s+(?:-a\s+)?|>\s*)"
    r"/sys/module/(\w+)/parameters/(\w+)"
)


@pytest.mark.parametrize(
    ("onde", "texto"),
    [("install.sh + lib", texto_do_instalador()), ("install-host-udev.sh", HOST_UDEV)],
    ids=["install.sh+lib", "install-host-udev.sh"],
)
def test_nenhuma_escrita_a_quente_digita_o_valor_de_uma_opcao_com_dono(
    onde: str, texto: str
) -> None:
    digitadas = sorted(
        f"{modulo}.{opcao}={valor!r}"
        for linha in _executa(texto)
        for valor, modulo, opcao in _ESCRITA_DIGITADA.findall(linha)
        if (modulo, opcao) in OPCOES
    )
    assert digitadas == [], (
        f"{onde} escreve a quente um valor digitado para opção que a conf possui "
        f"(pergunte a ela, com o leitor): {digitadas}"
    )


@pytest.mark.parametrize(
    ("onde", "texto"),
    [("install.sh + lib", texto_do_instalador()), ("install-host-udev.sh", HOST_UDEV)],
    ids=["install.sh+lib", "install-host-udev.sh"],
)
def test_nenhuma_fala_digita_opcao_igual_valor_de_uma_opcao_com_dono(
    onde: str, texto: str
) -> None:
    padrao = re.compile(
        r"\b(" + "|".join(sorted(map(re.escape, NOMES_COM_DONO))) + r")=([0-9A-Za-z]+)\b"
    )
    digitadas = sorted(
        f"{opcao}={valor}" for linha in _executa(texto) for opcao, valor in padrao.findall(linha)
    )
    assert digitadas == [], (
        f"{onde} digita, numa linha que executa, o valor de uma opção que a conf "
        f"possui — o rótulo pergunta a ela: {digitadas}"
    )


def test_o_ensaio_do_hid_playstation_diz_o_feature_retries_da_conf(tmp_path: Path) -> None:
    ensaio = _funcao(texto_do_install_sh(), "_ensaio_camada")
    script = "\n".join(
        (
            "set -euo pipefail",
            f"ROOT_DIR={RAIZ}",
            "NO_DKMS=0",
            'HOME="$1"',
            '_faria_root() { printf "FARIA: %s\\n" "$*"; }',
            '_faria() { printf "FARIA: %s\\n" "$*"; }',
            '_nao_faria() { printf "NAO: %s\\n" "$*"; }',
            LEITORES["lib (install.sh)"],
            ensaio,
            "_ensaio_camada dkms-playstation",
        )
    )
    r = subprocess.run(
        [BASH, "-c", script, "ensaio", str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env={"PATH": "/usr/bin:/bin"},
    )
    assert r.returncode == 0, r.stderr
    valor, _conf = OPCOES[("hid_playstation", "feature_retries")]
    linha = [x for x in r.stdout.splitlines() if "hefesto-hid-playstation.conf" in x]
    assert linha, r.stdout
    assert f"(feature_retries={valor} +" in linha[0], linha[0]


_ESCOPO_DO_PACOTE = (
    'BROKER_BIN_SRC="" BROKER_INSTALL_OK=0 BROKER_SESSION_GROUP="" BROKER_SESSION_UID=0',
    'BROKER_UNITS_SRC="" BTRES_INSTALL_OK=0 BTRES_SCRIPTS_SRC="" BTRES_UNIT_SRC=""',
    'BTUSB_SRC="$1" HIDNINTENDO_SRC="$1" HIDPLAYSTATION_SRC="$1"',
    'MODLOAD_DEST=/x MODLOAD_SRC="" REGRA_DO_NO=x REGRA_DO_NO_SRC=x REGRA_DO_NO_VELHA=x',
    'RULES=() RULES_DEST=/x',
    'RULES_SRC=/x SNDQUIRK_DEST=/x SNDQUIRK_SRC=""',
)


def test_o_comando_de_root_dos_pacotes_escreve_a_quente_o_valor_da_conf() -> None:
    """A escrita que ia `2` ao `feature_retries` do módulo carregado, medida no"""
    montador = _funcao(HOST_UDEV, "_build_install_cmd")
    assert montador.count("/etc/modprobe.d/hefesto-uhid.conf") == 2, montador
    montador = montador.replace(
        "/etc/modprobe.d/hefesto-uhid.conf", str(CONFS / "hefesto-uhid.conf")
    )
    script = "\n".join(
        (
            "set -euo pipefail",
            *_ESCOPO_DO_PACOTE,
            LEITORES["install-host-udev.sh"],
            montador,
            "_build_install_cmd",
        )
    )
    r = subprocess.run(
        [BASH, "-c", script, "pacote", str(CONFS)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env={"PATH": "/usr/bin:/bin"},
    )
    assert r.returncode == 0, r.stderr
    escritas = {
        (modulo, opcao): valor
        for valor, modulo, opcao in re.findall(
            r"printf '([^']*)' > /sys/module/(\w+)/parameters/(\w+)", r.stdout
        )
    }
    com_dono = {chave: v for chave, v in escritas.items() if chave in OPCOES}
    assert ("hid_playstation", "feature_retries") in com_dono, sorted(escritas)
    assert ("uhid", "backpressure") in com_dono, sorted(escritas)
    citados = {
        chave
        for chave in re.findall(
            r"/sys/module/(\w+)/parameters/(\w+)", "\n".join(_executa(montador))
        )
        if chave in OPCOES
    }
    assert set(com_dono) == citados, sorted(citados - set(com_dono))
    errados = sorted(
        f"{m}.{o}: escreve {v!r}, a conf diz {OPCOES[(m, o)][0]!r}"
        for (m, o), v in com_dono.items()
        if v != OPCOES[(m, o)][0]
    )
    assert errados == [], errados


_SUDO_QUE_RECUSA_O_REAL = (
    "#!/usr/bin/env bash\n"
    'for a in "$@"; do\n'
    '  [[ "$a" == /sys/* || "$a" == /etc/* ]] && { echo "RECUSEI $a" >&2; exit 97; }\n'
    "done\n"
    'while [[ "${1:-}" == -[nAEHkS] ]]; do shift; done\n'
    'exec "$@"\n'
)

_FUNCOES_DA_LIB = {
    "install_dkms_hid_nintendo_host": "hid_nintendo",
    "install_dkms_hid_playstation_host": "hid_playstation",
    "install_dkms_uhid_host": "uhid",
}


@pytest.mark.parametrize("rotina", sorted(_FUNCOES_DA_LIB))
def test_a_lib_escreve_a_quente_o_valor_da_conf(rotina: str, tmp_path: Path) -> None:
    modulo = _FUNCOES_DA_LIB[rotina]
    corpo = _funcao(LIB, rotina)
    params = sorted(
        {o for m, o in re.findall(r"/sys/module/(\w+)/parameters/(\w+)", corpo) if m == modulo}
    )
    assert params, f"{rotina} deixou de escrever parâmetro de {modulo}"
    parametros = tmp_path / "sys" / "module" / modulo / "parameters"
    parametros.mkdir(parents=True)
    for p in params:
        (parametros / p).write_text("ANTES", encoding="utf-8")
    (tmp_path / "etc" / "modprobe.d").mkdir(parents=True)
    corpo = (
        corpo.replace('source "${ROOT_DIR}/scripts/dkms_lib.sh"', ":")
        .replace("/sys/module/", f"{tmp_path}/sys/module/")
        .replace("/etc/modprobe.d/", f"{tmp_path}/etc/modprobe.d/")
    )
    sobrou = [x for x in _executa(corpo) if re.search(r"(^|[\s'\"=])/(sys|etc)/", x)]
    assert sobrou == [], f"a troca do /sys e do /etc não pegou a função inteira: {sobrou}"
    fakes = tmp_path / "fakes"
    fakes.mkdir()
    sudo = fakes / "sudo"
    sudo.write_text(_SUDO_QUE_RECUSA_O_REAL, encoding="utf-8")
    sudo.chmod(0o755)
    script = "\n".join(
        (
            "set -euo pipefail",
            f"ROOT_DIR={RAIZ}",
            "NO_DKMS=0",
            "COM_UHID_CONTRAPRESSAO=1",
            'warn() { printf "WARN: %s\\n" "$*"; }',
            "dkms_warn_secureboot_once() { :; }",
            "dkms_pkg_version() { echo 0; }",
            "dkms_install_patched_module() { :; }",
            "dkms_module_from_updates() { return 0; }",
            LEITORES["lib (install.sh)"],
            corpo,
            rotina,
        )
    )
    r = subprocess.run(
        [BASH, "-c", script],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env={"PATH": f"{fakes}:/usr/bin:/bin", "HOME": str(tmp_path), "LC_ALL": "C.UTF-8"},
    )
    assert "RECUSEI" not in r.stderr, r.stderr
    assert r.returncode == 0, r.stderr
    assert "WARN" not in r.stdout, r.stdout
    errados = sorted(
        f"{modulo}.{p}: ficou {(parametros / p).read_text(encoding='utf-8')!r}, "
        f"a conf diz {OPCOES[(modulo, p)][0]!r}"
        for p in params
        if (parametros / p).read_text(encoding="utf-8") != OPCOES[(modulo, p)][0]
    )
    assert errados == [], errados

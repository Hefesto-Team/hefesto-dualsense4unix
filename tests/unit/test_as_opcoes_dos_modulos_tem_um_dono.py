"""As opções dos módulos têm UM dono: a conf de `assets/modprobe.d/`.

OS-TEXTOS-QUE-A-6E-1-DEIXOU-VELHOS-01 (25/09/2026), item 7, achado da
conferência da A-BANCADA-DO-LUGAR-GUARDADO-01: o rótulo do ensaio do install
anunciava `feature_retries=2`, e a conf entregue manda `feature_retries=1`
desde 09/08 (a NOTA DATADA dela diz por quê: com 2 tentativas extras o pior
caso da probe por rádio vai a 27 s).

A CURA FOI À ORIGEM, e a origem era maior que o rótulo. Medido em 25/09: o
mesmo `2` estava DIGITADO em cinco lugares — o rótulo do ensaio, a fala do
passo do install e a escrita A QUENTE nos dois instaladores (o `install.sh`,
pela lib, e o `install-host-udev.sh` dos pacotes). A escrita punha 2 no
módulo carregado a cada install: até o boot seguinte, o controle que perde a
probe pagava a contenção uma vez a mais. Agora quem fala e quem escreve
PERGUNTA à conf (`opcao_do_modprobe`, e a cópia dele no caminho por pacote,
que não leva a lib), e o número não mora em mais lugar nenhum.

O QUE ESTA RÉGUA MEDE, e nada aqui digita um valor: cada um sai da conf.

- os dois leitores devolvem, para cada opção de cada conf, o valor que ela
  declara — e recusam (nada, `rc=1`) a opção ausente e o valor com forma
  estranha, que o caminho por pacote poria entre aspas num comando de root;
- nenhuma linha que EXECUTA nos instaladores escreve a quente um valor
  digitado para uma opção que tem conf dona;
- nenhuma fala ou rótulo que executa digita `opção=valor` de uma opção que
  tem conf dona;
- o ensaio de verdade (a função `_ensaio_camada`, recortada do `install.sh`)
  diz o valor da conf;
- o comando de root que o `install-host-udev.sh` MONTA (sem executá-lo)
  escreve a quente, em cada opção com conf dona, o valor dela.

A MORDIDA, medida: devolver o `printf '2' | sudo tee …/feature_retries` à lib
reprova a da escrita a quente; devolver o `(feature_retries=2 …)` ao rótulo
reprova a da fala e a do ensaio; tirar a recusa de forma estranha do leitor do
caminho por pacote reprova a do valor estranho; e perguntar à conf ERRADA no
caminho por pacote (sem digitar nada) só a do comando de root reprova. md5
conferido em cada volta.
"""

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


# ---------------------------------------------------------------------------
# 1. Os dois leitores respondem o que a conf declara
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# 2. Ninguém digita o número que a conf possui
# ---------------------------------------------------------------------------

#: Uma escrita a quente com o valor DIGITADO: `printf 'V' | sudo tee <nó>` (o
#: `install.sh` e a lib) ou `printf 'V' > <nó>` (o comando elevado do
#: `install-host-udev.sh`).
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


# ---------------------------------------------------------------------------
# 3. O ensaio de verdade diz o valor da conf
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# 4. O comando elevado do caminho por pacote escreve o valor da conf
# ---------------------------------------------------------------------------

#: O que `_build_install_cmd` lê do escopo do script. Só strings: a função
#: MONTA o comando de root e o devolve, e nada dele é executado aqui.
_ESCOPO_DO_PACOTE = (
    'BROKER_BIN_SRC="" BROKER_INSTALL_OK=0 BROKER_SESSION_GROUP="" BROKER_SESSION_UID=0',
    'BROKER_UNITS_SRC="" BTRES_INSTALL_OK=0 BTRES_SCRIPTS_SRC="" BTRES_UNIT_SRC=""',
    'BTUSB_SRC="$1" HIDNINTENDO_SRC="$1" HIDPLAYSTATION_SRC="$1"',
    'MODLOAD_DEST=/x MODLOAD_SRC="" REGRA_70=x REGRA_70_SRC=x RULES=() RULES_DEST=/x',
    'RULES_SRC=/x SNDQUIRK_DEST=/x SNDQUIRK_SRC=""',
)


def test_o_comando_de_root_dos_pacotes_escreve_a_quente_o_valor_da_conf() -> None:
    """A escrita que ia `2` ao `feature_retries` do módulo carregado, medida no
    comando que o `install-host-udev.sh` monta — sem executá-lo."""
    script = "\n".join(
        (
            "set -euo pipefail",
            *_ESCOPO_DO_PACOTE,
            LEITORES["install-host-udev.sh"],
            _funcao(HOST_UDEV, "_build_install_cmd"),
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
    errados = sorted(
        f"{m}.{o}: escreve {v!r}, a conf diz {OPCOES[(m, o)][0]!r}"
        for (m, o), v in com_dono.items()
        if v != OPCOES[(m, o)][0]
    )
    assert errados == [], errados

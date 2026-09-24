"""O `uninstall.sh --purge-config` leva as cópias de pareamento de uninstalls anteriores.

O-PURGE-LEVA-AS-COPIAS-DE-PAREAMENTO-01 (24/09/2026), decisão dela
D-2409-AS-COPIAS-DE-PAREAMENTO-SAEM-NO-PURGE. Todo uninstall sem
`--purge-config` guarda o acervo de bonds numa
`/var/lib/hefesto-dualsense4unix/bt-bonds.pre-uninstall-<carimbo>` e diz «para
apagar de vez: rode o uninstall com --purge-config». O `--purge-config` só
levava o acervo DESTA vida: as cópias de antes, com as LinkKeys dentro, nunca
saíam, e o `rmdir` do pai falhava calado por causa delas.

Os blocos são recortados do `uninstall.sh` REAL e rodam com o /var/lib trocado
por uma pasta de mentira (o caminho de `test_o_uninstall_leva_o_radio.py`), sob
o mesmo `set -euo pipefail` do script. O `sudo` de mentira executa o comando e
RECUSA qualquer argumento que ainda aponte para o /var/lib de verdade.

A segunda metade é a medição da sprint virada régua: O QUE TEM CHAVE DE
PAREAMENTO NASCE SÓ PARA O ROOT. Medido em 24/09 por `git grep` do caminho e
pelo histórico: só dois escritores do produto põem chave nessa pasta — o
`bt_bonds_snapshot.sh` (o acervo) e o `uninstall.sh` (as cópias). Os outros
escrevem sem chave: o diário do rádio (0644 de propósito, porque o daemon o
lê), a lápide da ponte e o livro do autorestore (0600, só endereços). As
capturas de Bluetooth de 22/07 e a `bt-bonds-protegidos` de 04/08, na máquina
dela, não têm escritor no repositório nem no histórico. Os dois escritores rodam
aqui sob `umask 000`, a pior máscara, com a fonte do BlueZ frouxa de propósito.

A MORDIDA, medida: tirar o laço das cópias reprova os cinco testes do purge e o
do ensaio; alargar o padrão para `bt-bonds*` reprova o da vizinha; tirar o
`KEEP_CONFIG` do laço reprova o sem-flag e os dois da cópia guardada (o laço
levaria a cópia desta vida); tirar a linha da senha, o da senha; tirar o aviso
sem root, o do aviso; tirar do snapshot o `chmod -R go-rwx` ou o `-m 700` do
acervo, o do acervo; tirar o `-m700` da pasta guardada, os dois da cópia — o
`install -d` sem modo abre para 0755 até a pasta que o `mv` trouxe fechada.
E da conferência: tirar o `sudo` do `rm` do laço reprova só o do ensaio (a
pasta de mentira é da usuária, e o `rm` sozinho apagaria aqui); tirar o `-L` da
guarda, ou trocar o `-e` por `-d`, reprova o do link (o quebrado ficaria).
"""

from __future__ import annotations

import hashlib
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

BASH = shutil.which("bash") or "/bin/bash"
RAIZ = Path(__file__).resolve().parents[2]
UNINSTALL = (RAIZ / "uninstall.sh").read_text(encoding="utf-8")
SNAPSHOT = RAIZ / "scripts" / "bt_bonds_snapshot.sh"
VAR_LIB = "/var/lib/hefesto-dualsense4unix"

#: Faixa sintética canônica das fixtures (test_anonimato_de_fixtures.py).
ADAPTADOR = "AA:BB:CC:00:00:01"
CONTROLE = "AA:BB:CC:00:00:11"
#: O que faz de um arquivo do BlueZ uma chave: a seção, como o
#: `bt_bonds_autorestore.sh::_tem_chave` a procura.
INFO_COM_CHAVE = "[General]\nName=DualSense Wireless Controller\n\n[LinkKey]\nType=4\nPINLength=0\n"
CACHE_SDP = "[General]\nName=DualSense Wireless Controller\n\n[ServiceRecords]\n0x00010001=3602\n"

#: As cópias que dois uninstalls de agosto deixaram, no formato do carimbo de sempre.
ANTIGAS = (
    "bt-bonds.pre-uninstall-20260808-101010",
    "bt-bonds.pre-uninstall-20260815-202020",
)


def _recorte(inicio: str, fim: str) -> str:
    a = UNINSTALL.index(inicio)
    b = UNINSTALL.index(fim, a)
    return UNINSTALL[a:b]


BLOCO_DOS_BONDS = _recorte(
    "    # O carimbo da desinstalação, um só:",
    "    sudo systemctl daemon-reload >/dev/null 2>&1 || true\n",
)
LINHA_DA_SENHA = _recorte(
    "# AS CÓPIAS DE PAREAMENTO DE UNINSTALLS ANTERIORES",
    "# Onda S: broker root hide-hidraw",
)
AVISO_SEM_ROOT = _recorte(
    "# SEM ROOT, AS CÓPIAS DE ANTES FICAM",
    "# Agente de pareamento persistente",
)
BLOCO_DO_ENSAIO = _recorte(
    'if [[ "${DRY_RUN}" -eq 1 ]]; then\n    exec 3>&1',
    "# Prime a credencial só se algum passo com root vai rodar",
)

#: O `sudo` de mentira, com a senha em cache: executa, e recusa o que ainda
#: apontar para o /var/lib real. As opções da frente (`-n`, `-A`…) saem como no
#: de verdade, senão o `sudo -n true` viraria `exec -n` e mentiria «sem root».
SUDO_QUE_RECUSA_O_REAL = (
    'for a in "$@"; do\n'
    '  [[ "$a" == *' + VAR_LIB + '* ]] && { echo "RECUSEI $a" >&2; exit 97; }\n'
    "done\n"
    'while [[ "${1:-}" == -[nAEHkS] ]]; do shift; done\n'
    'exec "$@"\n'
)
#: O `sudo` de quem não tem senha em cache nem TTY: toda pergunta é «não».
SUDO_QUE_NEGA = 'echo "NEGUEI $*" >&2\nexit 1\n'


def _fake(pasta: Path, nome: str, corpo: str) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    alvo = pasta / nome
    alvo.write_text("#!/usr/bin/env bash\n" + corpo, encoding="utf-8")
    alvo.chmod(0o755)


def _escrever(arquivo: Path, texto: str, modo: int) -> None:
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(texto, encoding="utf-8")
    arquivo.chmod(modo)


def _um_acervo(pasta: Path) -> None:
    """Um snapshot como o `bt_bonds_snapshot.sh` o grava: 0700 e 0600."""
    snap = pasta / "20260807-230000-4242"
    _escrever(snap / ADAPTADOR / CONTROLE / "info", INFO_COM_CHAVE, 0o600)
    for d in (snap / ADAPTADOR / CONTROLE, snap / ADAPTADOR, snap, pasta):
        d.chmod(0o700)


def _mesa_do_root(tmp_path: Path, *, com_bonds: bool = True, com_diario: bool = True) -> Path:
    raiz = tmp_path / "var-lib"
    raiz.mkdir(mode=0o755)
    if com_bonds:
        _um_acervo(raiz / "bt-bonds")
    if com_diario:
        for nome in ("radio-diario.jsonl", "radio-diario.jsonl.1"):
            _escrever(raiz / nome, '{"o_que": "x"}\n', 0o644)
    for nome in ANTIGAS:
        _um_acervo(raiz / nome)
        _escrever(raiz / nome / "radio-diario.jsonl", '{"o_que": "antigo"}\n', 0o644)
    return raiz


def _rodar(
    tmp_path: Path,
    bloco: str,
    *,
    purge: bool,
    remove_udev: bool = False,
    sudo: str = SUDO_QUE_RECUSA_O_REAL,
    antes: str = "",
) -> subprocess.CompletedProcess[str]:
    raiz = tmp_path / "var-lib"
    fakes = tmp_path / "fakes"
    _fake(fakes, "sudo", sudo)
    codigo = bloco.replace(VAR_LIB, str(raiz))
    assert VAR_LIB not in codigo, "a troca do /var/lib não pegou o bloco inteiro"
    script = (
        "set -euo pipefail\n"
        + antes
        + 'log() { printf "[uninstall] %s\\n" "$*"; }\n'
        + f"KEEP_CONFIG={0 if purge else 1}\nREMOVE_UDEV={1 if remove_udev else 0}\n"
        + codigo
    )
    r = subprocess.run(
        [BASH, "-c", script],
        env={"PATH": f"{fakes}:/usr/bin:/bin", "HOME": str(tmp_path), "LC_ALL": "C.UTF-8"},
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert "RECUSEI" not in r.stderr, r.stderr
    return r


def _retrato(pasta: Path) -> dict[str, tuple[str, int]]:
    retrato: dict[str, tuple[str, int]] = {}
    for p in sorted([pasta, *pasta.rglob("*")]):
        st = p.lstat()
        conteudo = hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "dir"
        retrato[str(p.relative_to(pasta))] = (conteudo, stat.S_IMODE(st.st_mode))
    return retrato


# ---------------------------------------------------------------------------
# 1. O --purge-config leva as cópias de antes; sem ele, nada muda
# ---------------------------------------------------------------------------


def test_com_purge_config_as_copias_de_antes_saem(tmp_path: Path) -> None:
    raiz = _mesa_do_root(tmp_path)
    r = _rodar(tmp_path, BLOCO_DOS_BONDS, purge=True)
    assert r.returncode == 0, r.stderr
    sobra = sorted(p.name for p in raiz.iterdir())
    assert sobra == [], (
        "com --purge-config as cópias de pareamento de antes tinham de sair — "
        f"ficaram: {sobra}\n{r.stdout}"
    )
    for nome in ANTIGAS:
        assert f"{raiz}/{nome}" in r.stdout, f"o uninstall apagou sem dizer: {nome}\n{r.stdout}"


def test_com_purge_config_a_pasta_do_root_sai_mesmo_com_copias_de_antes(tmp_path: Path) -> None:
    """O `rmdir` do pai é puro: com uma cópia de antes dentro, ele falhava calado
    e a pasta ficava em /var/lib com as LinkKeys de agosto."""
    raiz = _mesa_do_root(tmp_path)
    r = _rodar(tmp_path, BLOCO_DOS_BONDS, purge=True, remove_udev=True)
    assert r.returncode == 0, r.stderr
    assert not raiz.exists(), sorted(p.name for p in raiz.iterdir())


def test_so_as_copias_de_antes_sem_acervo_nem_diario_tambem_saem(tmp_path: Path) -> None:
    """O segundo uninstall de quem seguiu o «para apagar de vez»: o acervo já foi
    guardado pelo primeiro, e só as cópias sobraram."""
    raiz = _mesa_do_root(tmp_path, com_bonds=False, com_diario=False)
    r = _rodar(tmp_path, BLOCO_DOS_BONDS, purge=True, remove_udev=True)
    assert r.returncode == 0, r.stderr
    assert not raiz.exists(), sorted(p.name for p in raiz.iterdir())


def test_sem_purge_config_as_copias_de_antes_ficam_intactas(tmp_path: Path) -> None:
    raiz = _mesa_do_root(tmp_path)
    antes = {nome: _retrato(raiz / nome) for nome in ANTIGAS}
    r = _rodar(tmp_path, BLOCO_DOS_BONDS, purge=False, remove_udev=True)
    assert r.returncode == 0, r.stderr
    for nome in ANTIGAS:
        assert _retrato(raiz / nome) == antes[nome], f"sem --purge-config {nome} mudou"
    novas = sorted(p.name for p in raiz.glob("bt-bonds.pre-uninstall-*") if p.name not in ANTIGAS)
    assert len(novas) == 1, f"o acervo desta vida tinha de virar UMA cópia nova: {novas}"
    assert "cópia de pareamento de um uninstall anterior" not in r.stdout, r.stdout


def test_o_purge_so_leva_o_prefixo_que_o_uninstall_escreve(tmp_path: Path) -> None:
    """A vizinha de nome parecido fica. A `bt-bonds-protegidos` é a que existe na
    máquina dela desde 04/08, sem escritor no repositório: ela não é cópia de
    uninstall, e o uninstall não decide por ela. O pai, com ela dentro, fica."""
    raiz = _mesa_do_root(tmp_path)
    _um_acervo(raiz / "bt-bonds-protegidos")
    _escrever(raiz / "LEIA-ME.txt", "anotação de alguém\n", 0o644)
    vizinhas = {nome: _retrato(raiz / nome) for nome in ("bt-bonds-protegidos", "LEIA-ME.txt")}
    r = _rodar(tmp_path, BLOCO_DOS_BONDS, purge=True, remove_udev=True)
    assert r.returncode == 0, r.stderr
    assert sorted(p.name for p in raiz.iterdir()) == ["LEIA-ME.txt", "bt-bonds-protegidos"]
    for nome, retrato in vizinhas.items():
        assert _retrato(raiz / nome) == retrato, f"o purge mexeu na vizinha {nome}"


def test_um_link_com_o_nome_da_copia_sai_sem_levar_o_alvo(tmp_path: Path) -> None:
    """O link quebrado também sai: é o caso que o `-L` da guarda existe para pegar."""
    raiz = _mesa_do_root(tmp_path, com_bonds=False, com_diario=False)
    fora = tmp_path / "fora-da-pasta"
    _um_acervo(fora)
    retrato_de_fora = _retrato(fora)
    (raiz / "bt-bonds.pre-uninstall-20260901-000000").symlink_to(fora)
    (raiz / "bt-bonds.pre-uninstall-20260902-000000").symlink_to(tmp_path / "nao-existe")
    r = _rodar(tmp_path, BLOCO_DOS_BONDS, purge=True)
    assert r.returncode == 0, r.stderr
    assert not (raiz / "bt-bonds.pre-uninstall-20260901-000000").is_symlink()
    assert not (raiz / "bt-bonds.pre-uninstall-20260902-000000").is_symlink(), (
        "o link quebrado com o nome da cópia ficou"
    )
    assert _retrato(fora) == retrato_de_fora, "o purge seguiu o link para fora da pasta"


def test_o_ensaio_diz_cada_copia_que_apagaria_e_nao_apaga_nenhuma(tmp_path: Path) -> None:
    """O `--dry-run` é como quem coordena olha o uninstall na máquina dela.

    O «(root)» é a parte que morde: a pasta de mentira é da usuária, e um `rm`
    sem `sudo` passaria em todos os outros testes daqui — na máquina dela a
    pasta é de root e ele não apagaria nada."""
    raiz = _mesa_do_root(tmp_path)
    antes = _retrato(raiz)
    r = _rodar(tmp_path, BLOCO_DO_ENSAIO + BLOCO_DOS_BONDS, purge=True, antes="DRY_RUN=1\n")
    assert r.returncode == 0, r.stderr
    assert _retrato(raiz) == antes, "o ensaio mexeu na pasta do root"
    faria = [linha for linha in r.stdout.splitlines() if "FARIA:" in linha]
    for nome in ANTIGAS:
        assert any(f"(root) rm -rf -- {raiz}/{nome}" in linha for linha in faria), (
            f"o ensaio não disse que apagaria {nome} como root:\n" + "\n".join(faria)
        )


# ---------------------------------------------------------------------------
# 2. A senha e o aviso: o purge não fica calado sem root
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("purge", "com_copia", "pede"),
    [(True, True, 1), (False, True, 0), (True, False, 0)],
    ids=["purge-com-copia", "sem-purge", "purge-sem-copia"],
)
def test_a_copia_de_antes_pede_a_senha_so_com_purge_config(
    tmp_path: Path, purge: bool, com_copia: bool, pede: int
) -> None:
    raiz = tmp_path / "var-lib"
    raiz.mkdir()
    if com_copia:
        _um_acervo(raiz / ANTIGAS[0])
    r = _rodar(
        tmp_path,
        LINHA_DA_SENHA + 'echo "PEDE=${_NEEDS_SUDO}"\n',
        purge=purge,
        antes="_NEEDS_SUDO=0\n",
    )
    assert r.returncode == 0, r.stderr
    assert f"PEDE={pede}" in r.stdout, r.stdout


@pytest.mark.parametrize("purge", [True, False], ids=["purge", "sem-purge"])
def test_sem_root_o_purge_diz_que_as_copias_ficaram(tmp_path: Path, purge: bool) -> None:
    raiz = tmp_path / "var-lib"
    raiz.mkdir()
    _um_acervo(raiz / ANTIGAS[0])
    r = _rodar(tmp_path, AVISO_SEM_ROOT, purge=purge, sudo=SUDO_QUE_NEGA)
    assert r.returncode == 0, r.stderr
    if purge:
        assert (
            "FICARAM" in r.stdout and f"sudo rm -rf {raiz}/bt-bonds.pre-uninstall-*" in r.stdout
        ), "sem root o --purge-config deixou as cópias caladas:\n" + r.stdout
    else:
        assert r.stdout == "", "sem --purge-config não há o que avisar:\n" + r.stdout


def test_com_root_o_aviso_nao_aparece(tmp_path: Path) -> None:
    raiz = tmp_path / "var-lib"
    raiz.mkdir()
    _um_acervo(raiz / ANTIGAS[0])
    r = _rodar(tmp_path, AVISO_SEM_ROOT, purge=True)
    assert r.returncode == 0, r.stderr
    assert r.stdout == "", r.stdout


# ---------------------------------------------------------------------------
# 3. O que tem chave de pareamento nasce só para o root
# ---------------------------------------------------------------------------


def _tem_chave(arquivo: Path) -> bool:
    linhas = arquivo.read_text(encoding="utf-8", errors="replace").splitlines()
    return any(
        linha.startswith(("[LinkKey]", "[LongTermKey]", "[PeripheralLongTermKey]"))
        for linha in linhas
    )


def _abertos_a_outros(pasta: Path) -> list[str]:
    """Pasta ou arquivo com chave que alguém além do dono alcança."""
    abertos = []
    for p in [pasta, *pasta.rglob("*")]:
        if p.is_symlink() or not (p.is_dir() or _tem_chave(p)):
            continue
        modo = stat.S_IMODE(p.lstat().st_mode)
        if modo & 0o077:
            abertos.append(f"{p.relative_to(pasta.parent)} {oct(modo)}")
    return abertos


def test_o_acervo_do_snapshot_nasce_so_para_o_root(tmp_path: Path) -> None:
    fonte = tmp_path / "bluetooth"
    _escrever(fonte / ADAPTADOR / "settings", "[General]\nDiscoverable=false\n", 0o644)
    _escrever(fonte / ADAPTADOR / CONTROLE / "info", INFO_COM_CHAVE, 0o644)
    _escrever(fonte / ADAPTADOR / "cache" / CONTROLE, CACHE_SDP, 0o644)
    for d in (fonte, fonte / ADAPTADOR, fonte / ADAPTADOR / CONTROLE, fonte / ADAPTADOR / "cache"):
        d.chmod(0o755)
    raiz = tmp_path / "var-lib"
    raiz.mkdir()
    acervo = raiz / "bt-bonds"
    r = subprocess.run(
        [BASH, "-c", 'umask 000; exec bash "$0" "$@"', str(SNAPSHOT), "--quiet"],
        env={
            "PATH": "/usr/bin:/bin",
            "HOME": str(tmp_path),
            "HEFESTO_BT_SRC": str(fonte),
            "HEFESTO_BT_SNAP_ROOT": str(acervo),
            "HEFESTO_BT_LOG_DEST": "none",
        },
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert r.returncode == 0, r.stderr
    chaves = [p for p in acervo.rglob("*") if p.is_file() and _tem_chave(p)]
    assert chaves, f"o snapshot não gravou chave nenhuma — a régua mediria o vazio: {r.stdout}"
    assert _abertos_a_outros(acervo) == [], "o acervo nasceu aberto a outros usuários"


@pytest.mark.parametrize("com_bonds", [True, False], ids=["acervo-guardado", "so-o-diario"])
def test_a_copia_que_o_uninstall_guarda_nasce_so_para_o_root(
    tmp_path: Path, com_bonds: bool
) -> None:
    raiz = tmp_path / "var-lib"
    raiz.mkdir(mode=0o755)
    if com_bonds:
        _um_acervo(raiz / "bt-bonds")
    for nome in ("radio-diario.jsonl", "radio-diario.jsonl.1"):
        _escrever(raiz / nome, '{"o_que": "x"}\n', 0o644)
    r = _rodar(tmp_path, BLOCO_DOS_BONDS, purge=False, antes="umask 000\n")
    assert r.returncode == 0, r.stderr
    copias = sorted(raiz.glob("bt-bonds.pre-uninstall-*"))
    assert len(copias) == 1, sorted(p.name for p in raiz.iterdir())
    assert _abertos_a_outros(copias[0]) == [], "a cópia guardada nasceu aberta a outros usuários"
    if com_bonds:
        assert any(_tem_chave(p) for p in copias[0].rglob("*") if p.is_file())

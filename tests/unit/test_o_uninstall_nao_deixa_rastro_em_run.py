"""O `uninstall.sh` tira de `/run` tudo o que o produto põe lá.

OS-TEXTOS-QUE-A-6E-1-DEIXOU-VELHOS-01 (25/09/2026), item 4. A conferência da
STORM-USB-02 achou que o uninstall não apagava `/run/hefesto-bt-rebind`, onde o
`bt_rebind_orphans.sh` guarda os contadores do tique e, desde a STORM-USB-02,
os `evento-*` do aviso do kernel. É tmpfs e some no boot, mas o produto não
deixa rastro: a `/run/hefesto-bt-ponte`, vizinha dela, já saía.

A cura foi à ORIGEM, e a régua também: medido em 25/09 com a lista abaixo,
eram TRÊS as raízes de `/run` que o produto escreve e o uninstall esquecia —
a do religar, a do watchdog (`promoted-*` e o carimbo do reinício, desde
sempre) e a pasta do socket do broker, que o systemd cria e não apaga no stop.
Uma lista digitada esqueceria a próxima; por isso a primeira régua LÊ o
produto: toda raiz `/run/hefesto-*` citada em `scripts/`, `src/` ou
`assets/` tem de ter um `rm` ou `rmdir` no código do uninstall.

As outras são as do item 4, com o molde da O-PURGE-LEVA-AS-COPIAS-DE-
PAREAMENTO-01: os blocos são recortados do `uninstall.sh` REAL e rodam com o
`/run` e o `/etc` trocados por pastas de mentira, sob o mesmo
`set -euo pipefail`; o `sudo` de mentira executa e RECUSA qualquer argumento
que ainda aponte para o `/run` de verdade. Nada aqui roda o uninstall inteiro,
nada pede senha e nada toca o `/run` da máquina.

A MORDIDA, medida: tirar `/run/hefesto-bt-rebind` do `rm` do bloco da
resiliência reprova a da raiz, a do `rm` e a do ensaio; tirá-lo da conta do
`_NEEDS_SUDO`, a da senha; tirar o `rm` da pasta do broker, a da raiz.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

BASH = shutil.which("bash") or "/bin/bash"
RAIZ = Path(__file__).resolve().parents[2]
UNINSTALL = (RAIZ / "uninstall.sh").read_text(encoding="utf-8")

#: Uma raiz de `/run` do produto: `/run/hefesto-<nome>`, até a primeira barra.
_RAIZ_DE_RUN = re.compile(r"/run/(hefesto[A-Za-z0-9_.-]*)")
#: Onde o produto escreve. O `uninstall.sh` fica de fora: ele é quem responde.
_ONDE_O_PRODUTO_ESCREVE = ("scripts", "src", "assets", "install.sh")


def _recorte(inicio: str, fim: str) -> str:
    a = UNINSTALL.index(inicio)
    b = UNINSTALL.index(fim, a)
    return UNINSTALL[a:b]


def _codigo(texto: str) -> str:
    """O que EXECUTA: sem as linhas de comentário nem as falas (`log`).

    A continuação por `\\` vira uma linha só: um `rm` que quebra a lista de
    caminhos em duas linhas continua sendo UM `rm`.
    """
    return "\n".join(
        linha
        for linha in texto.replace("\\\n", " ").splitlines()
        if not linha.lstrip().startswith(("#", "log "))
    )


def _raizes_que_o_produto_escreve() -> set[str]:
    raizes: set[str] = set()
    for base in _ONDE_O_PRODUTO_ESCREVE:
        caminho = RAIZ / base
        arquivos = [caminho] if caminho.is_file() else sorted(caminho.rglob("*"))
        for arquivo in arquivos:
            if not arquivo.is_file() or "__pycache__" in arquivo.parts:
                continue
            try:
                texto = arquivo.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            raizes.update(m.group(1).rstrip(".") for m in _RAIZ_DE_RUN.finditer(texto))
    return raizes


# ---------------------------------------------------------------------------
# 1. Toda raiz de /run do produto tem quem a tire
# ---------------------------------------------------------------------------


def test_a_lista_de_raizes_nao_esta_vazia() -> None:
    """Guarda da premissa: sem raiz nenhuma, a régua de baixo mediria o vazio."""
    raizes = _raizes_que_o_produto_escreve()
    assert "hefesto-bt-rebind" in raizes, sorted(raizes)
    assert "hefesto-dualsense4unix" in raizes, sorted(raizes)


def test_toda_raiz_de_run_que_o_produto_escreve_sai_no_uninstall() -> None:
    remocoes = [
        linha
        for linha in _codigo(UNINSTALL).splitlines()
        if re.search(r"\b(rm|rmdir)\b", linha)
    ]
    esquecidas = sorted(
        raiz
        for raiz in _raizes_que_o_produto_escreve()
        if not any(re.search(rf"/run/{re.escape(raiz)}(?![\w.-])", r) for r in remocoes)
    )
    assert esquecidas == [], (
        "o produto escreve estas raízes de /run e o uninstall não as tira "
        f"(nenhum rm/rmdir no código): {esquecidas}"
    )


# ---------------------------------------------------------------------------
# 2. O religar: a senha, o rm e o ensaio
# ---------------------------------------------------------------------------

LINHAS_DA_SENHA = _recorte(
    "# O-DIARIO-DO-RADIO-01 (instalado pela INSTALL-E-UNINSTALL-DO-RADIO-01)",
    "compgen -G '/var/lib/hefesto-dualsense4unix/radio-diario.jsonl*'",
)
BLOCO_DOS_CARIMBOS = _recorte(
    "    # OS CARIMBOS DE ROOT EM /run das peças que este bloco tira",
    "    # A TRAVA COMUM DO RÁDIO",
)
BLOCO_DO_ENSAIO = _recorte(
    'if [[ "${DRY_RUN}" -eq 1 ]]; then\n    exec 3>&1',
    "# Prime a credencial só se algum passo com root vai rodar",
)

#: O `sudo` de mentira, com a senha em cache: executa, e recusa o que ainda
#: apontar para o /run de verdade.
SUDO_QUE_RECUSA_O_REAL = (
    'for a in "$@"; do\n'
    '  [[ "$a" == /run/* ]] && { echo "RECUSEI $a" >&2; exit 97; }\n'
    "done\n"
    'while [[ "${1:-}" == -[nAEHkS] ]]; do shift; done\n'
    'exec "$@"\n'
)


def _trocar_as_raizes(bloco: str, falso: Path) -> str:
    codigo = bloco.replace("/run/hefesto", f"{falso}/run/hefesto").replace(
        "/etc/tmpfiles.d/", f"{falso}/etc/tmpfiles.d/"
    )
    assert not re.search(r"(^|[\s'\"=])/(run|etc)/", codigo), (
        "a troca do /run e do /etc não pegou o bloco inteiro:\n" + codigo
    )
    return codigo


def _rodar(tmp_path: Path, bloco: str, antes: str = "") -> subprocess.CompletedProcess[str]:
    fakes = tmp_path / "fakes"
    fakes.mkdir(exist_ok=True)
    sudo = fakes / "sudo"
    sudo.write_text("#!/usr/bin/env bash\n" + SUDO_QUE_RECUSA_O_REAL, encoding="utf-8")
    sudo.chmod(0o755)
    script = (
        "set -euo pipefail\n"
        + antes
        + 'log() { printf "[uninstall] %s\\n" "$*"; }\n'
        + _trocar_as_raizes(bloco, tmp_path)
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


def _carimbos_do_religar(tmp_path: Path) -> Path:
    """Os carimbos como o `bt_rebind_orphans.sh` os deixa: tique, aviso e desistência."""
    pasta = tmp_path / "run" / "hefesto-bt-rebind"
    pasta.mkdir(parents=True)
    for nome in ("0005:054C:0CE6.000F", "evento-0005:054C:0CE6.000F", "3-4.4:1.3.desisti"):
        (pasta / nome).write_text("1\n", encoding="utf-8")
    return pasta


def test_so_os_carimbos_do_religar_pedem_a_senha(tmp_path: Path) -> None:
    """Um uninstall anterior sem root deixou só a pasta do religar: a senha é pedida."""
    _carimbos_do_religar(tmp_path)
    r = _rodar(tmp_path, LINHAS_DA_SENHA + 'echo "PEDE=${_NEEDS_SUDO}"\n', "_NEEDS_SUDO=0\n")
    assert r.returncode == 0, r.stderr
    assert "PEDE=1" in r.stdout, r.stdout


def test_sem_nada_em_run_a_senha_nao_e_pedida_por_eles(tmp_path: Path) -> None:
    (tmp_path / "run").mkdir()
    r = _rodar(tmp_path, LINHAS_DA_SENHA + 'echo "PEDE=${_NEEDS_SUDO}"\n', "_NEEDS_SUDO=0\n")
    assert r.returncode == 0, r.stderr
    assert "PEDE=0" in r.stdout, r.stdout


def test_os_carimbos_do_religar_saem_com_os_da_ponte_e_do_watchdog(tmp_path: Path) -> None:
    religar = _carimbos_do_religar(tmp_path)
    run = tmp_path / "run"
    (run / "hefesto-bt-ponte").mkdir()
    (run / "hefesto-bt-ponte" / "reset-hci1").write_text("x\n", encoding="utf-8")
    (run / "hefesto-bt-watchdog").mkdir()
    (run / "hefesto-bt-watchdog" / "promoted-AA-BB-CC-00-00-11").write_text("x\n", encoding="utf-8")
    (run / "hefesto-bt-watchdog.restart-stamp").write_text("0\n", encoding="utf-8")
    (run / "outra-coisa").mkdir()
    r = _rodar(tmp_path, BLOCO_DOS_CARIMBOS)
    assert r.returncode == 0, r.stderr
    assert not religar.exists(), sorted(p.name for p in religar.iterdir())
    assert sorted(p.name for p in run.iterdir()) == ["outra-coisa"], (
        "sobrou rastro do Hefesto em /run, ou o uninstall levou o que não é dele: "
        + ", ".join(sorted(p.name for p in run.iterdir()))
    )


def test_o_ensaio_diz_que_tiraria_os_carimbos_do_religar_e_nao_tira(tmp_path: Path) -> None:
    """O `--dry-run` é como quem coordena olha o uninstall na máquina dela."""
    religar = _carimbos_do_religar(tmp_path)
    antes = sorted(p.name for p in religar.iterdir())
    r = _rodar(tmp_path, BLOCO_DO_ENSAIO + BLOCO_DOS_CARIMBOS, "DRY_RUN=1\nAUTO_YES=0\n")
    assert r.returncode == 0, r.stderr
    assert sorted(p.name for p in religar.iterdir()) == antes, "o ensaio mexeu no /run"
    faria = [linha for linha in r.stdout.splitlines() if "FARIA:" in linha]
    assert any(
        "(root) rm -rf" in linha and f"{tmp_path}/run/hefesto-bt-rebind" in linha
        for linha in faria
    ), "o ensaio não disse que tiraria os carimbos do religar:\n" + "\n".join(faria)

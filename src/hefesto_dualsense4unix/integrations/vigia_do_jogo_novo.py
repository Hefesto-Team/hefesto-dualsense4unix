"""O jogo novo recebe as configurações quando a Steam fecha.

O guarda acordava em `PathChanged=…/userdata`, que não é recursivo: o
`localconfig.vdf` mora dois níveis abaixo e a Steam o regrava ali, então o gatilho
nunca disparava e só o relógio de 30 min rodava. Este módulo escreve o drop-in com
os caminhos que a Steam de fato toca (o `localconfig.vdf` de cada conta e o
`steamapps` de cada biblioteca) e guarda o interruptor `aplicar_a_cada_jogo_novo`.
100% stdlib: o guarda o roda com o `python3` do sistema.
"""
from __future__ import annotations

import argparse
import contextlib
import os
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

try:
    from .steam_launch_options import (
        _real,
        caminho_do_localconfig,
        pastas_steamapps,
        raizes_de_jogos,
        steam_input_allowlist_path,
    )
except ImportError:  # pragma: no cover - executado como script avulso
    from steam_launch_options import (  # type: ignore[no-redef]
        _real,
        caminho_do_localconfig,
        pastas_steamapps,
        raizes_de_jogos,
        steam_input_allowlist_path,
    )

INTERRUPTOR = "aplicar_a_cada_jogo_novo"
UNIDADE = "hefesto-steam-input-guard"
DROPIN_DOS_CAMINHOS = "caminhos.conf"
DROPIN_DO_RITMO = "ritmo.conf"
#: Teto de cada chamada ao systemd: o guarda não pode ficar preso num `systemctl` que não responde.
PRAZO_DO_SYSTEMCTL_S = 20

LIGADO = "ligado"
DESLIGADO = "desligado"
SEM_UNIDADE = "sem_unidade"
SEM_STEAM = "sem_steam"
EM_DIA = "em_dia"
ESCRITO = "escrito"
ERRO = "erro"

_RECUSAS = frozenset(
    {"0", "nao", "não", "off", "false", "desligado", "desliga"}  # (noqa-acento: as duas grafias)
)

_CABECALHO = (
    "# Gerado pelo Hefesto (vigia_do_jogo_novo.py) a cada ciclo do guarda; não edite.\n"
)
_RITMO = (
    _CABECALHO
    + "# Baixar um jogo regrava o appmanifest o tempo todo: sem folga no limite de\n"
    + "# partidas, o systemd derrubaria o vigia do caminho (unit-start-limit-hit).\n"
    + "[Unit]\nStartLimitIntervalSec=60\nStartLimitBurst=30\n"
)


def caminho_do_interruptor(config_home: Path | None = None) -> Path:
    """`~/.config/hefesto-dualsense4unix/aplicar_a_cada_jogo_novo`, sem tocar no disco."""
    return steam_input_allowlist_path(config_home).parent / INTERRUPTOR


def interruptor_ligado(config_home: Path | None = None) -> bool:
    """Ligado por padrão. Só uma palavra de recusa na primeira linha viva o desliga."""
    try:
        texto = caminho_do_interruptor(config_home).read_text(encoding="utf-8")
    except (OSError, ValueError):
        return True
    for linha in texto.splitlines():
        palavra = linha.split("#", 1)[0].strip().lower()
        if palavra:
            return palavra not in _RECUSAS
    return True


def _contas_da_raiz(raiz: Path) -> list[str]:
    """Os números `userdata/<conta>` da raiz: os que existem e a conta que a Steam vai abrir."""
    contas: set[str] = set()
    with contextlib.suppress(OSError):
        contas.update(p.name for p in (raiz / "userdata").iterdir() if p.name.isdigit())
    try:
        from .opcoes_por_jogo import conta_logada
    except ImportError:  # pragma: no cover - executado como script avulso
        from opcoes_por_jogo import conta_logada  # type: ignore[no-redef]
    with contextlib.suppress(OSError):
        logada = conta_logada(raiz)
        if logada:
            contas.add(logada)
    return sorted(contas, key=int)


def caminhos_a_vigiar(home: Path | None = None) -> list[Path]:
    """O `localconfig.vdf` de cada conta e o `steamapps` de cada biblioteca."""
    base = home or Path.home()
    caminhos: list[Path] = []
    vistos: set[Path] = set()

    def anotar(caminho: Path) -> None:
        chave = _real(caminho.parent) / caminho.name
        if chave not in vistos:
            vistos.add(chave)
            caminhos.append(caminho)

    for raiz in raizes_de_jogos(base):
        for conta in _contas_da_raiz(raiz):
            anotar(caminho_do_localconfig(raiz, conta))
    for pasta in pastas_steamapps(base):
        if pasta.is_dir():
            anotar(pasta)
    return caminhos


def _como_especificador(caminho: Path, base: Path) -> str:
    """`%h/…` para o que mora no lar (o drop-in vale em qualquer máquina); `%` escapado."""
    try:
        return "%h/" + caminho.relative_to(base).as_posix().replace("%", "%%")
    except ValueError:
        return caminho.as_posix().replace("%", "%%")


def texto_do_dropin(caminhos: list[Path], base: Path) -> str:
    """O `[Path]` que ACRESCENTA estes caminhos aos três que o `.path` já traz."""
    linhas = [_como_especificador(c, base) for c in caminhos]
    return _CABECALHO + "[Path]\n" + "".join(f"PathChanged={x}\n" for x in linhas)


def _pasta_das_unidades(home: Path | None) -> Path:
    return (home or Path.home()) / ".config" / "systemd" / "user"


def _recarregar_o_systemd() -> bool:
    """Pede ao systemd do usuário que releia as unidades e reabra o vigia."""
    try:
        for comando in (
            ["systemctl", "--user", "daemon-reload"],
            ["systemctl", "--user", "try-restart", f"{UNIDADE}.path"],
        ):
            subprocess.run(
                comando, check=False, timeout=PRAZO_DO_SYSTEMCTL_S, capture_output=True
            )
    except (OSError, subprocess.SubprocessError):
        return False
    return True


def _gravar(destino: Path, texto: str) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=destino.parent, prefix=destino.name + ".")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as arq:
            arq.write(texto)
        Path(tmp).chmod(0o644)
        Path(tmp).replace(destino)
    except OSError:
        with contextlib.suppress(OSError):
            Path(tmp).unlink()
        raise


def _dropins(unidades: Path) -> tuple[Path, Path]:
    return (
        unidades / f"{UNIDADE}.path.d" / DROPIN_DOS_CAMINHOS,
        unidades / f"{UNIDADE}.service.d" / DROPIN_DO_RITMO,
    )


def _tirar_os_dropins(
    unidades: Path, dry_run: bool, recarregar: Callable[[], bool] | None
) -> str:
    """Desligado: o guarda volta a acordar só pelo `.path` versionado e pelo relógio."""
    presentes = [d for d in _dropins(unidades) if d.is_file()]
    if not presentes or dry_run:
        return DESLIGADO
    try:
        for destino in presentes:
            destino.unlink()
    except OSError:
        return ERRO
    (recarregar or _recarregar_o_systemd)()
    return DESLIGADO


def garantir(
    home: Path | None = None,
    *,
    config_home: Path | None = None,
    dry_run: bool = False,
    recarregar: Callable[[], bool] | None = None,
) -> str:
    """Põe o vigia nos arquivos que a Steam regrava. Devolve o desfecho; nunca levanta.

    `desligado` (interruptor) tira os dois drop-ins que este módulo escreveu, se
    houver, e volta o guarda ao que era; `sem_unidade` (o guarda não está instalado)
    não escreve nada. Só reescreve quando o texto muda, e só então recarrega o systemd.
    """
    unidades = _pasta_das_unidades(home)
    if not interruptor_ligado(config_home):
        return _tirar_os_dropins(unidades, dry_run, recarregar)
    if not (unidades / f"{UNIDADE}.path").is_file():
        return SEM_UNIDADE
    caminhos = caminhos_a_vigiar(home)
    if not caminhos:
        return SEM_STEAM
    base = home or Path.home()
    dos_caminhos, do_ritmo = _dropins(unidades)
    alvos = {dos_caminhos: texto_do_dropin(caminhos, base), do_ritmo: _RITMO}
    mudou = []
    for destino, texto in alvos.items():
        try:
            atual: str | None = destino.read_text(encoding="utf-8")
        except (OSError, ValueError):
            atual = None
        if atual != texto:
            mudou.append(destino)
    if not mudou:
        return EM_DIA
    if dry_run:
        return ESCRITO
    try:
        for destino in mudou:
            _gravar(destino, alvos[destino])
    except OSError:
        return ERRO
    (recarregar or _recarregar_o_systemd)()
    return ESCRITO


def jogos_novos_a_receber(
    home: Path | None = None, *, config_home: Path | None = None
) -> list[str]:
    """Os appids com `appmanifest` em disco, ou `[]` com o interruptor desligado.

    Quem escreve no `localconfig.vdf` passa isto como `instalados`: o jogo que a
    Steam ainda não abriu não tem bloco, e sem isto seria recusado como
    desconhecido. O appid vem do `appmanifest`, nunca de lista embarcada.
    """
    if not interruptor_ligado(config_home):
        return []
    try:
        from .prontuario_dos_jogos import jogos_instalados
    except ImportError:  # pragma: no cover - executado como script avulso
        from prontuario_dos_jogos import jogos_instalados  # type: ignore[no-redef]
    try:
        return [appid for appid, _, _ in jogos_instalados(home) if appid.isdigit()]
    except OSError:  # pragma: no cover - biblioteca sumiu entre o listar e o ler
        return []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="vigia_do_jogo_novo",
        description="Escreve o drop-in do vigia da Steam (jogo novo e conta nova).",
    )
    parser.add_argument("--dry-run", action="store_true", help="não escreve nada")
    parser.add_argument("--caminhos", action="store_true", help="só lista o que vigiaria")
    args = parser.parse_args(argv)
    if args.caminhos:
        for caminho in caminhos_a_vigiar():
            print(caminho)
        return 0
    desfecho = garantir(dry_run=args.dry_run)
    print(f"[vigia-do-jogo-novo] {desfecho}")
    return 1 if desfecho == ERRO else 0


if __name__ == "__main__":  # pragma: no cover - entrypoint do guarda
    sys.exit(main())

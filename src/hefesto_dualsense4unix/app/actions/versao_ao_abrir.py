"""A versão mais recente do ``dev``: baixa ao abrir a janela e entra quando a janela fecha.

Só numa instalação pelo código, em ``dev``, com a árvore limpa, sem trabalho em voo e sem jogo
aberto; qualquer outra coisa para em silêncio, com uma linha no diário. A rede fica num fio que a
janela não espera, e o avanço, só rápido, fica para o fecho: a janela importa código sob demanda.

A faixa que pede install o solta fora do cgroup da janela (``--install``): ele espera o jogo fechar
de vez, roda uma vez só e nunca guarda senha. Sem autorização a parte do sistema fica pendente, e a
falha fica em ``install-pendente`` com o motivo, que a aba Sistema e o ``doctor`` dizem.
"""
from __future__ import annotations

import atexit
import contextlib
import dataclasses
import fcntl
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import Any

RAMO = "dev"
MARCA_DE_VOO = "hefesto-em-voo"
ANOTACAO_DO_INSTALL = "install-pendente"
ESCOLHAS_DO_INSTALL = "install-escolhas"
TETO_DO_GIT_S = 15.0
TETO_DO_INSTALL_S = 3600.0
FOLGA_DO_FIM_DO_INSTALL_S = 60.0
CURTO = 9
MODULO = "hefesto_dualsense4unix.app.actions.versao_ao_abrir"
PEDIDO_DO_INSTALL = "--install"
REGISTRO_DO_INSTALL = "install-ao-fechar.log"
TRAVA_DO_INSTALL = "install-ao-fechar.trava"
MARCA_DO_INSTALL = "install-em-curso"
PREFIXO_DO_MOTIVO = "motivo: "
JOGO_ABERTO = "jogo aberto"
SEM_AUTORIZACAO = "sem autorização de administrador"
FORA_DO_AVANCO = "o ramo local tem o que o remoto não tem: fica como está"
REPOSITORIO = re.compile(
    r"(?:^|[:/])hefesto-team/hefesto-dualsense4unix(?:\.git)?/?$", re.IGNORECASE)
PASTA_DO_SERVICO = "src/"
_PACOTE = f"{PASTA_DO_SERVICO}hefesto_dualsense4unix"
PEDEM_INSTALL = (
    "install.sh", "pyproject.toml", "constraints.txt",
    f"{_PACOTE}/broker/hidraw_broker.py",
    f"{_PACOTE}/integrations/anticheat_conhecido.json",
    f"{_PACOTE}/integrations/audio_ks_dualsense.py",
    f"{_PACOTE}/integrations/camadas_vulkan.py",
    f"{_PACOTE}/integrations/leitor_do_estado.py",
)
PASTAS_DO_INSTALL = ("assets/", "locale/", "packaging/", "scripts/")


def _dizer(frase: str) -> None:
    with contextlib.suppress(ValueError, OSError):
        print(f"  versão: {frase}", flush=True)


def _encerrar(processo: subprocess.Popen[str]) -> None:
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(processo.pid, signal.SIGKILL)
    processo.communicate()


def _git(raiz: Path, *args: str, com_teto: bool = True) -> str | None:
    """A saída do git, ou ``None`` se ele falhou ou passou do teto (com os filhos dele)."""
    from hefesto_dualsense4unix.mods.instalador import _ambiente_do_git

    processo = subprocess.Popen(
        ["git", "-c", "gc.auto=0", "-C", str(raiz), *args],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        text=True, env=_ambiente_do_git(), start_new_session=True,
    )
    try:
        saida, _ = processo.communicate(timeout=TETO_DO_GIT_S if com_teto else None)
    except subprocess.TimeoutExpired:
        _encerrar(processo)
        return None
    return saida.strip() if processo.returncode == 0 else None


def _jogo_aberto() -> bool:
    from hefesto_dualsense4unix.app.actions.troca_no_fim_do_jogo import _jogo_aberto as perguntar

    return perguntar()


def _ha_voo(comum: Path) -> bool:
    """A marca tem uma linha por conjunto em voo: vazia ou ausente, nada voa."""
    try:
        return bool((comum / MARCA_DE_VOO).read_text(encoding="utf-8").strip())
    except FileNotFoundError:
        return False
    except (OSError, ValueError):
        return True


def por_que_nao(raiz: Path, jogo_aberto: Callable[[], bool] = _jogo_aberto) -> str:
    """A guarda, a mais barata antes: o motivo de parar, ou vazio."""
    if not (raiz / ".git").exists():
        return "instalação sem clone"
    if _git(raiz, "symbolic-ref", "--short", "-q", "HEAD") != RAMO:
        return f"fora de {RAMO}"
    if _git(raiz, "--no-optional-locks", "status", "--porcelain") != "":
        return "árvore com mudança"
    comum = _git(raiz, "rev-parse", "--git-common-dir")
    if comum is None or _ha_voo(raiz / comum):
        return "trabalho em voo"
    if jogo_aberto():
        return JOGO_ABERTO
    return ""


def remoto_do_produto(raiz: Path) -> str | None:
    """O remoto que aponta para o repositório do produto, pelo endereço e não pelo nome."""
    for linha in (_git(raiz, "remote", "-v") or "").splitlines():
        partes = linha.split()
        if len(partes) == 3 and partes[2] == "(fetch)" and REPOSITORIO.search(partes[1]):
            return partes[0]
    return None


def _e_avanco(raiz: Path, antes: str, alvo: str) -> bool:
    return _git(raiz, "merge-base", "--is-ancestor", antes, alvo) is not None


def baixar(raiz: Path, *, jogo_aberto: Callable[[], bool] = _jogo_aberto) -> str | None:
    """Traz o ``dev`` do remoto sem tocar na árvore. Devolve o commit, se ele é outro."""
    motivo = por_que_nao(raiz, jogo_aberto)
    if motivo:
        _dizer(f"fica como está ({motivo})")
        return None
    remoto = remoto_do_produto(raiz)
    if remoto is None:
        _dizer("fica como está (sem o remoto do produto)")
        return None
    if _git(raiz, "fetch", "--quiet", "--no-tags", remoto, RAMO) is None:
        _dizer("fica como está (o remoto não respondeu)")
        return None
    alvo = _git(raiz, "rev-parse", "--verify", "FETCH_HEAD^{commit}")
    topo = _git(raiz, "rev-parse", "HEAD")
    if alvo is not None and alvo == topo:
        _dizer("já é a mais recente")
        return None
    if alvo is None or topo is None or not _e_avanco(raiz, topo, alvo):
        _dizer(FORA_DO_AVANCO)
        return None
    _dizer(f"{alvo[:CURTO]} baixada: entra quando a janela fechar")
    return alvo


def o_que_a_faixa_pede(caminhos: Iterable[str]) -> str:
    """``install``, ``serviço`` ou vazio, pelos arquivos que a faixa de commits mudou.

    O que o install copia para fora da árvore (o broker, em área de root, e os de ``bin``) pede
    install mesmo morando em ``src/``: a cópia não anda com a árvore.
    """
    nomes = list(caminhos)
    if any(n in PEDEM_INSTALL or n.startswith(PASTAS_DO_INSTALL) for n in nomes):
        return "install"
    return "serviço" if any(n.startswith(PASTA_DO_SERVICO) for n in nomes) else ""


def _nota_do_install() -> Path:
    from hefesto_dualsense4unix.utils.xdg_paths import state_dir

    return state_dir(ensure=True) / ANOTACAO_DO_INSTALL


def _linhas_da_nota() -> list[str] | None:
    with contextlib.suppress(OSError, ValueError):
        return _nota_do_install().read_text(encoding="utf-8").splitlines()
    return None


def _faixas_da_nota() -> list[str]:
    return [linha for linha in _linhas_da_nota() or [] if not linha.startswith(PREFIXO_DO_MOTIVO)]


def _gravar_a_nota(*linhas: str) -> None:
    with contextlib.suppress(OSError):
        _nota_do_install().write_text("".join(f"{linha}\n" for linha in linhas), encoding="utf-8")


def _anotar_o_install(antes: str, alvo: str) -> None:
    """A faixa nova reabre a tentativa: o motivo da anterior sai, e o fecho volta a retomar."""
    _gravar_a_nota(*_faixas_da_nota(), f"{antes[:CURTO]}..{alvo[:CURTO]}")


def _motivo_da_nota(linhas: Iterable[str]) -> str:
    return next((
        linha.removeprefix(PREFIXO_DO_MOTIVO) for linha in linhas
        if linha.startswith(PREFIXO_DO_MOTIVO)), "")


def pendencia_do_install() -> tuple[str, str] | None:
    """A linha que a aba Sistema e o ``doctor`` dizem: só o install que parou com um motivo."""
    from hefesto_dualsense4unix.utils.repo_files import como_atualizar_esta_instalacao

    motivo = _motivo_da_nota(_linhas_da_nota() or [])
    if not motivo:
        return None
    return ("[WARN]",
            f"A versão nova não terminou de entrar ({motivo}): "
            f"{como_atualizar_esta_instalacao()}.")


def _a_trava_do_install() -> int | None:
    """Um install só: quem acha a trava presa sai. A trava cai com o processo que a tomou."""
    from hefesto_dualsense4unix.utils.xdg_paths import runtime_dir

    with contextlib.suppress(OSError):
        fd = os.open(runtime_dir(ensure=True) / TRAVA_DO_INSTALL, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(fd)
            raise
        return fd
    return None


def _install_de_fora() -> bool:
    """O ``install.sh`` que alguém rodou: o PID que ele anota, se ainda é um ``install.sh``."""
    from hefesto_dualsense4unix.utils.xdg_paths import runtime_dir

    with contextlib.suppress(OSError, ValueError):
        pid = int((runtime_dir() / MARCA_DO_INSTALL).read_text(encoding="utf-8"))
        return "install.sh" in Path(f"/proc/{pid}/cmdline").read_text(errors="replace")
    return False


def _install_em_curso() -> bool:
    """O fim do install fecha a janela aberta, e esse fecho não pode avançar a árvore que ele lê."""
    if _install_de_fora():
        return True
    trava = _a_trava_do_install()
    if trava is None:
        return True
    os.close(trava)
    return False


def _encerrar_o_install(processo: subprocess.Popen[str]) -> None:
    """Primeiro o SIGTERM: é o ``trap EXIT`` do install que reabre a Steam e religa o vigia."""
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(processo.pid, signal.SIGTERM)
    with contextlib.suppress(subprocess.TimeoutExpired):
        processo.wait(timeout=FOLGA_DO_FIM_DO_INSTALL_S)
    _encerrar(processo)


def _sai_bem(*comando: str) -> bool:
    try:
        return subprocess.run(
            comando, stdin=subprocess.DEVNULL, capture_output=True, check=False,
            timeout=TETO_DO_GIT_S,
        ).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _ha_autorizacao() -> bool:
    """As duas portas do install que não pedem digitar nada: a credencial em cache e o askpass."""
    if shutil.which("sudo") is None:
        return False
    if _sai_bem("sudo", "-n", "true"):
        return True
    return bool(os.environ.get("SUDO_ASKPASS")) and _sai_bem("sudo", "-A", "-v")


def _escolhas_do_install() -> list[str]:
    """As flags do último install que terminou: o do fecho não desfaz o que a pessoa escolheu."""
    from hefesto_dualsense4unix.utils.xdg_paths import state_dir

    with contextlib.suppress(OSError, ValueError):
        return (state_dir() / ESCOLHAS_DO_INSTALL).read_text(encoding="utf-8").split()
    return []


def _rodar_o_install(raiz: Path) -> str:
    """Roda o install do clone, com o registro no state do produto. Devolve o motivo, ou vazio."""
    from hefesto_dualsense4unix.integrations.ambiente_do_jogo import ambiente_limpo
    from hefesto_dualsense4unix.utils.xdg_paths import state_dir

    try:
        with (state_dir(ensure=True) / REGISTRO_DO_INSTALL).open("w", encoding="utf-8") as registro:
            processo = subprocess.Popen(
                [str(raiz / "install.sh"), *dict.fromkeys(("--yes", *_escolhas_do_install()))],
                stdin=subprocess.DEVNULL, stdout=registro, stderr=subprocess.STDOUT, text=True,
                cwd=raiz, env=ambiente_limpo(os.environ), start_new_session=True,
            )
            try:
                saiu = processo.wait(timeout=TETO_DO_INSTALL_S)
            except subprocess.TimeoutExpired:
                _encerrar_o_install(processo)
                return f"o install passou de {TETO_DO_INSTALL_S / 60:.0f} minutos"
    except OSError as erro:
        return f"o install não abriu: {erro.strerror or erro}"
    return "" if saiu == 0 else f"o install saiu com o código {saiu}"


def _instalar(raiz: Path, rodar: Callable[[Path], str]) -> None:
    """Roda o install e devolve a nota, que ele apaga ao fim, se algo ficou por fazer."""
    faixas = _faixas_da_nota()
    autorizado = _ha_autorizacao()
    saida = rodar(raiz)
    motivo = saida if autorizado else SEM_AUTORIZACAO
    if not motivo:
        _dizer("o install terminou")
        return
    _dizer(f"o install ficou pendente ({motivo})")
    _gravar_a_nota(*faixas, f"{PREFIXO_DO_MOTIVO}{motivo}")


def _janela_aberta() -> bool:
    from hefesto_dualsense4unix.app.actions.recarga_do_install import janelas_abertas

    return bool(janelas_abertas())


def _por_que_nao_instalar(raiz: Path, jogo_aberto: Callable[[], bool]) -> str:
    """A guarda do avanço, repetida na hora, o Parar da aba Sistema e a janela que voltou.

    O fim do install fecha e reabre a janela aberta: a que voltou fica, e o próximo fecho retoma.
    """
    from hefesto_dualsense4unix.utils.marca_do_parar import marca_do_parar

    motivo = por_que_nao(raiz, jogo_aberto)
    if motivo:
        return motivo
    if _install_de_fora():
        return "install em curso"
    if marca_do_parar().exists():
        return "serviço parado de propósito"
    return "janela aberta" if _janela_aberta() else ""


def esperar_e_instalar(
    raiz: Path,
    *,
    jogo_aberto: Callable[[], bool] = _jogo_aberto,
    rodar: Callable[[Path], str] = _rodar_o_install,
    relogio: Callable[[], float] = time.monotonic,
    dormir: Callable[[float], None] = time.sleep,
    prazo_s: float | None = None,
) -> int:
    """Espera o jogo fechar de vez, como a troca no fim do jogo, e roda o install uma vez.

    A nota é a fila: quem a acha vazia sai, e o install de quem usa também a apaga. No prazo, ou
    com a guarda fechada, a nota fica como está e o próximo fecho da janela retoma.
    """
    from hefesto_dualsense4unix.app.actions.troca_no_fim_do_jogo import (
        PASSO_DA_VIGIA_S,
        PRAZO_DA_VIGIA_S,
        EsperaSemJogo,
    )

    trava = _a_trava_do_install()
    if trava is None:
        return 0
    try:
        espera = EsperaSemJogo()
        inicio = relogio()
        while relogio() - inicio < (PRAZO_DA_VIGIA_S if prazo_s is None else prazo_s):
            if not _linhas_da_nota():
                return 0
            if espera.fechou_de_vez(jogo_aberto(), relogio()):
                motivo = _por_que_nao_instalar(raiz, jogo_aberto)
                if not motivo:
                    _instalar(raiz, rodar)
                    return 0
                if motivo != JOGO_ABERTO:
                    _dizer(f"o install fica para depois ({motivo})")
                    return 0
                espera.zerar()
            dormir(PASSO_DA_VIGIA_S)
        return 0
    finally:
        os.close(trava)


def _disparar_a_troca(itens: Sequence[str]) -> None:
    from hefesto_dualsense4unix.app.actions.troca_no_fim_do_jogo import disparar

    disparar(itens)


def _a_suite_esta_rodando() -> bool:
    from hefesto_dualsense4unix.integrations.fora_do_servico import _a_suite_esta_rodando as rodando

    return rodando()


def soltar_o_install(raiz: Path, *, abrir: Callable[..., Any] | None = None) -> None:
    """Abre ``python -m …versao_ao_abrir --install`` numa unidade própria, que a janela não leva."""
    from hefesto_dualsense4unix.integrations import fora_do_servico
    from hefesto_dualsense4unix.integrations.ambiente_do_jogo import ambiente_limpo

    if abrir is None and _a_suite_esta_rodando():
        return
    contexto = fora_do_servico.contexto_atual()
    (abrir or fora_do_servico.abrir)(
        [sys.executable, "-m", MODULO, PEDIDO_DO_INSTALL, str(raiz)],
        env=ambiente_limpo(os.environ),
        aplicativo="install-ao-fechar",
        contexto=dataclasses.replace(
            contexto, herdaria=contexto.herdaria or "a janela está fechando"),
    )


def retomar_o_install(raiz: Path, *, instalar: Callable[[Path], Any] = soltar_o_install) -> bool:
    """A faixa anotada que nenhum install atendeu volta no fecho. A que parou com motivo, não."""
    linhas = _linhas_da_nota()
    if not linhas or _motivo_da_nota(linhas) or por_que_nao(raiz, lambda: False):
        return False
    instalar(raiz)
    return True


def aplicar(
    raiz: Path,
    alvo: str,
    *,
    jogo_aberto: Callable[[], bool] = _jogo_aberto,
    disparar: Callable[[Sequence[str]], Any] = _disparar_a_troca,
    instalar: Callable[[Path], Any] = soltar_o_install,
) -> bool:
    """Avança a árvore até ``alvo``, só por avanço rápido, e faz o que a faixa pede. Diz se avançou.

    A guarda volta: entre a abertura e o fecho a árvore pode ter sujado e um jogo pode ter aberto.
    O avanço não tem teto: morto no meio, ele deixaria a árvore pela metade.
    """
    from hefesto_dualsense4unix.utils.marca_do_parar import marca_do_parar

    motivo = por_que_nao(raiz, jogo_aberto) or ("install em curso" if _install_em_curso() else "")
    if motivo:
        _dizer(f"a baixada fica para depois ({motivo})")
        return False
    antes = _git(raiz, "rev-parse", "HEAD")
    if antes is None or not _e_avanco(raiz, antes, alvo):
        _dizer(FORA_DO_AVANCO)
        return False
    caminhos = _git(raiz, "diff", "--name-only", "--no-renames", antes, alvo)
    avanco = None
    if caminhos is not None:
        avanco = _git(
            raiz, "merge", "--quiet", "--ff-only", "--no-overwrite-ignore", alvo, com_teto=False)
    if caminhos is None or avanco is None:
        _dizer("o avanço não coube: fica como está")
        return False
    pede = o_que_a_faixa_pede(caminhos.splitlines())
    if pede == "install":
        _anotar_o_install(antes, alvo)
        instalar(raiz)
        _dizer(f"{alvo[:CURTO]} entrou: o install roda fora da janela")
    elif pede == "serviço" and not marca_do_parar().exists():
        disparar(("daemon",))
        _dizer(f"{alvo[:CURTO]} entrou: o serviço reinicia")
    else:
        _dizer(f"{alvo[:CURTO]} entrou")
    return True


def baixar_ao_abrir(raiz: Path) -> threading.Thread | None:
    """Solta o fio que baixa e deixa o avanço para o fim do processo. Nada aqui espera a rede."""
    if not (raiz / ".git").exists() or _a_suite_esta_rodando():
        return None
    baixada: list[str] = []

    def _baixar() -> None:
        try:
            alvo = baixar(raiz)
        except Exception as erro:
            _dizer(f"fica como está ({erro})")
            return
        if alvo:
            baixada.append(alvo)

    def _aplicar() -> None:
        try:
            if not (baixada and aplicar(raiz, baixada[0])):
                retomar_o_install(raiz)
        except Exception as erro:
            _dizer(f"o fecho parou no meio ({erro})")

    atexit.register(_aplicar)
    fio = threading.Thread(target=_baixar, name="versao-ao-abrir", daemon=True)
    fio.start()
    return fio


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) == 2 and args[0] == PEDIDO_DO_INSTALL:
        return esperar_e_instalar(Path(args[1]))
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

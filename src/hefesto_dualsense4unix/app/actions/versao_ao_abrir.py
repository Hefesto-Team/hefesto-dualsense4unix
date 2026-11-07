"""A versão mais recente do ``dev``: baixa ao abrir a janela e entra quando a janela fecha.

Só numa instalação pelo código, em ``dev``, com a árvore limpa, sem trabalho em voo e sem jogo
aberto; qualquer outra coisa para em silêncio, com uma linha no diário. A rede fica num fio que a
janela não espera. O avanço fica para o fecho porque a janela importa código sob demanda: aberta,
um avanço de cem commits quebra um import da aba Conexões. Só avanço rápido: nada de troca
de ramo nem de reset, e o trabalho de quem desenvolve nunca sai do lugar.
"""
from __future__ import annotations

import atexit
import contextlib
import os
import re
import signal
import subprocess
import threading
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import Any

RAMO = "dev"
MARCA_DE_VOO = "hefesto-em-voo"
ANOTACAO_DO_INSTALL = "install-pendente"
TETO_DO_GIT_S = 15.0
CURTO = 9
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
        return "jogo aberto"
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


def _anotar_o_install(antes: str, alvo: str) -> None:
    from hefesto_dualsense4unix.utils.xdg_paths import state_dir

    with contextlib.suppress(OSError), (
        state_dir(ensure=True) / ANOTACAO_DO_INSTALL
    ).open("a", encoding="utf-8") as nota:
        nota.write(f"{antes[:CURTO]}..{alvo[:CURTO]}\n")


def _disparar_a_troca(itens: Sequence[str]) -> None:
    from hefesto_dualsense4unix.app.actions.troca_no_fim_do_jogo import disparar

    disparar(itens)


def aplicar(
    raiz: Path,
    alvo: str,
    *,
    jogo_aberto: Callable[[], bool] = _jogo_aberto,
    disparar: Callable[[Sequence[str]], Any] = _disparar_a_troca,
) -> bool:
    """Avança a árvore até ``alvo``, só por avanço rápido, e faz o que a faixa pede. Diz se avançou.

    A guarda volta: entre a abertura e o fecho a árvore pode ter sujado e um jogo pode ter aberto.
    O avanço não tem teto: morto no meio, ele deixaria a árvore pela metade.
    """
    from hefesto_dualsense4unix.utils.marca_do_parar import marca_do_parar

    motivo = por_que_nao(raiz, jogo_aberto)
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
        _dizer(f"{alvo[:CURTO]} entrou: o próximo install completa")
    elif pede == "serviço" and not marca_do_parar().exists():
        disparar(("daemon",))
        _dizer(f"{alvo[:CURTO]} entrou: o serviço reinicia")
    else:
        _dizer(f"{alvo[:CURTO]} entrou")
    return True


def _a_suite_esta_rodando() -> bool:
    from hefesto_dualsense4unix.integrations.fora_do_servico import _a_suite_esta_rodando as rodando

    return rodando()


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
        if not baixada:
            return
        try:
            aplicar(raiz, baixada[0])
        except Exception as erro:
            _dizer(f"o fecho parou no meio ({erro})")

    atexit.register(_aplicar)
    fio = threading.Thread(target=_baixar, name="versao-ao-abrir", daemon=True)
    fio.start()
    return fio

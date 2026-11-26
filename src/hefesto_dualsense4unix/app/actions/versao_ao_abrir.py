"""A versão mais recente do ``dev``: baixa ao abrir a janela e entra quando a janela fecha.

Só numa instalação pelo código, em ``dev``, com a árvore limpa, sem trabalho em voo e sem jogo
aberto; qualquer outra coisa para em silêncio, com uma linha no diário. A rede fica num fio que a
janela não espera, e o avanço, só rápido e só com cada commit da faixa assinado por chave da lista
que vale nele (a do ``HEAD`` de agora, trocada só por commit aceito), fica para o fecho, só com a
«Atualização automática» ligada (desligada, a versão baixada espera o «Atualizar tudo») e com a
cópia datada da configuração antes de mudar perfis ou extensões. A faixa que pede install o solta
fora do cgroup da janela (``--install``): ele espera o jogo fechar de vez, roda uma vez só e nunca
guarda senha; a falha fica em ``install-pendente``.
"""
from __future__ import annotations

import atexit
import contextlib
import dataclasses
import fcntl
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Callable, Iterable, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

RAMO = "dev"
MARCA_DE_VOO = "hefesto-em-voo"
ANOTACAO_DO_INSTALL = "install-pendente"
ESCOLHAS_DO_INSTALL = "install-escolhas"
PULOS_DE_ROOT_DO_INSTALL = "install-pulou-root"
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
TRABALHO_EM_VOO = "trabalho em voo"
INSTALL_EM_CURSO = "install em curso"
ESPERAS = (TRABALHO_EM_VOO, JOGO_ABERTO, INSTALL_EM_CURSO)
SEM_AUTORIZACAO = "sem autorização de administrador"
FORA_DO_AVANCO = "o ramo local tem o que o remoto não tem: fica como está"
SEM_ASSINATURA = "sem a assinatura do projeto"
LISTA_DE_QUEM_ASSINA = "assets/assinaturas/quem-assina"
RECUSA_DA_ASSINATURA = "versao-sem-assinatura"
INICIO_DA_ASSINATURA_SSH = "gpgsig -----BEGIN SSH SIGNATURE-----"
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
    f"{_PACOTE}/utils/arquivo_de_terceiro.py",
)
PASTAS_DO_INSTALL = ("assets/", "locale/", "packaging/", "scripts/")
ARQUIVO_DA_BAIXA = "versao-baixada.json"
(AVANCA, ATUAL, ESPERA, FORA_DO_RAMO, ARVORE_MUDADA, SEM_REMOTO, SEM_REDE, DIVERGIU,
 SEM_A_ASSINATURA) = (
    "avança", "atual", "espera", "fora-do-ramo", "árvore-mudada", "sem-remoto", "sem-rede",
    "divergiu", "sem-assinatura")
VEREDITO_DO_MOTIVO = {f"fora de {RAMO}": FORA_DO_RAMO, "árvore com mudança": ARVORE_MUDADA}
FRASES_DA_BAIXA = {
    FORA_DO_RAMO: f"O clone não está no ramo {RAMO}: volte para ele para a versão nova entrar",
    ARVORE_MUDADA: "O clone tem mudança sem commit: guarde ou desfaça para a versão nova entrar",
    SEM_REMOTO: "O clone não tem o remoto do projeto: acrescente-o para a versão nova chegar",
    SEM_A_ASSINATURA: f"A versão nova ficou de fora ({SEM_ASSINATURA}): confira o remoto do clone",
    DIVERGIU: f"O ramo {RAMO} do clone tem história que o do projeto não tem: fica como está",
}
PEDEM_COPIA = (f"{_PACOTE}/profiles/", f"{_PACOTE}/mods/")
PASTA_DAS_COPIAS = "copias-da-configuracao"
COPIAS_GUARDADAS = 3


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


def _arvores_vivas(raiz: Path) -> set[str] | None:
    """Os nomes que uma linha da marca pode ter: a pasta de cada árvore que existe e o seu ramo
    ``voo/<nome>``. ``None``: o git não respondeu."""
    saida = _git(raiz, "worktree", "list", "--porcelain")
    if saida is None:
        return None
    nomes: set[str] = set()
    caminho: Path | None = None
    for linha in [*saida.splitlines(), ""]:
        if linha.startswith("worktree "):
            caminho = Path(linha.removeprefix("worktree "))
        elif linha.startswith("branch ") and caminho is not None and caminho.is_dir():
            nomes.add(linha.removeprefix("branch refs/heads/").removeprefix("voo/"))
        elif not linha and caminho is not None:
            if caminho.is_dir():
                nomes.add(caminho.name)
            caminho = None
    return nomes


def _tirar_da_marca(marca: Path, mortas: set[str]) -> None:
    """Regrava a marca sem as linhas de árvore que sumiu, relida na hora: o despacho só
    acrescenta."""
    with contextlib.suppress(OSError, ValueError):
        linhas = marca.read_text(encoding="utf-8").splitlines()
        ficam = [linha for linha in linhas if linha.strip() not in mortas]
        if ficam == linhas:
            return
        temporaria = marca.with_name(f".{marca.name}.{os.getpid()}")
        temporaria.write_text("".join(f"{linha}\n" for linha in ficam), encoding="utf-8")
        temporaria.replace(marca)


def _ha_voo(raiz: Path, comum: Path) -> bool:
    """A marca tem uma linha por conjunto em voo: vazia, ausente ou só de árvores que sumiram,
    nada voa. A linha de árvore que sumiu sai da marca."""
    marca = comum / MARCA_DE_VOO
    try:
        linhas = {linha.strip() for linha in marca.read_text(encoding="utf-8").splitlines()}
    except FileNotFoundError:
        return False
    except (OSError, ValueError):
        return True
    linhas.discard("")
    if not linhas:
        return False
    vivas = _arvores_vivas(raiz)
    if vivas is None:
        return True
    mortas = linhas - vivas
    if mortas:
        _tirar_da_marca(marca, mortas)
    return bool(linhas & vivas)


def por_que_nao(raiz: Path, jogo_aberto: Callable[[], bool] = _jogo_aberto) -> str:
    """A guarda, a mais barata antes: o motivo de parar, ou vazio."""
    if not (raiz / ".git").exists():
        return "instalação sem clone"
    if _git(raiz, "symbolic-ref", "--short", "-q", "HEAD") != RAMO:
        return f"fora de {RAMO}"
    if _git(raiz, "--no-optional-locks", "status", "--porcelain", "--untracked-files=no") != "":
        return "árvore com mudança"
    comum = _git(raiz, "rev-parse", "--git-common-dir")
    if comum is None or _ha_voo(raiz, raiz / comum):
        return TRABALHO_EM_VOO
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


def _assinado_por_ssh(commit: str) -> bool:
    """Uma assinatura só, e SSH: o git junta dois cabeçalhos ``gpgsig`` e confere pelo primeiro."""
    cabecalho = commit.split("\n\n", 1)[0].splitlines()
    return [linha for linha in cabecalho if linha.startswith("gpgsig")] == [
        INICIO_DA_ASSINATURA_SSH]


def _assinado_pela_lista(raiz: Path, commit: str, lista: str) -> bool:
    texto = _git(raiz, "cat-file", "commit", commit)
    if texto is None or not _assinado_por_ssh(texto):
        return False
    descritor, caminho = tempfile.mkstemp(prefix="hefesto-quem-assina-")
    try:
        with os.fdopen(descritor, "w", encoding="utf-8") as arquivo:
            arquivo.write(f"{lista}\n")
        return _git(
            raiz, "-c", "gpg.format=ssh", "-c", f"gpg.ssh.allowedSignersFile={caminho}",
            "-c", "gpg.minTrustLevel=fully", "verify-commit", commit) is not None
    finally:
        with contextlib.suppress(OSError):
            os.unlink(caminho)


def _a_lista(raiz: Path, commit: str) -> str | None:
    return _git(raiz, "show", f"{commit}:{LISTA_DE_QUEM_ASSINA}")


def _a_linhagem_aceita(raiz: Path, de: str, alvo: str, *, fixa: str | None = None) -> bool:
    """A lista parte do commit ``de``, já aceito, e anda commit a commit pelo primeiro pai até o
    ``alvo``: cada commit vem assinado por uma chave da lista do pai dele, e só depois de aceito a
    lista dele passa a valer. Não há salto: a chave que um commit tirou da lista não assina nada
    depois dele. O alvo que não descende de ``de`` pelo primeiro pai e o commit recusado no meio
    deixam a faixa inteira de fora. Com a lista ``fixa``, cada commit vem assinado também por uma
    chave dessa lista."""
    lista = _a_lista(raiz, de)
    faixa = _git(raiz, "rev-list", "--first-parent", "--reverse", "--parents",
                 f"{de}..{alvo}") if lista else None
    if not faixa:
        return False
    for linha in faixa.splitlines():
        commit, pai = [*linha.split(), ""][:2]
        if pai != de or not lista or not _assinado_pela_lista(raiz, commit, lista):
            return False
        if fixa is not None and not _assinado_pela_lista(raiz, commit, fixa):
            return False
        de, lista = commit, _a_lista(raiz, commit)
    return True


def _a_reescrita_se_aceita(raiz: Path, topo: str, alvo: str) -> bool:
    """O ``alvo`` que divergiu do ``topo`` ganha a oferta de refazer só se o ramo reescrito anda
    pela linhagem desde o commit comum, cada commit assinado também por uma chave da lista do
    ``topo``, e se a própria faixa do comum ao ``topo`` anda pela linhagem: a chave que o clone
    já retirou não volta pela reescrita desde antes da retirada. Na dúvida, não há oferta."""
    comum = _git(raiz, "merge-base", topo, alvo)
    agora = _a_lista(raiz, topo)
    return bool(comum and agora and _a_linhagem_aceita(raiz, comum, topo)
                and _a_linhagem_aceita(raiz, comum, alvo, fixa=agora))


def sem_a_assinatura_da_casa(raiz: Path, alvo: str) -> bool:
    """A faixa do ``HEAD`` de agora até o ``alvo`` não anda pela linhagem assinada; o ``alvo`` que
    já é o ``HEAD`` não traz faixa a conferir."""
    de = _git(raiz, "rev-parse", "HEAD")
    return not (de and (de == alvo or _a_linhagem_aceita(raiz, de, alvo)))


def _recusa_da_assinatura() -> Path:
    from hefesto_dualsense4unix.utils.xdg_paths import state_dir

    return state_dir(ensure=True) / RECUSA_DA_ASSINATURA


def _recusar_sem_assinatura(alvo: str) -> None:
    _dizer(f"fica como está ({SEM_ASSINATURA})")
    with contextlib.suppress(OSError):
        _recusa_da_assinatura().write_text(f"{alvo}\n", encoding="utf-8")


def _esquecer_a_recusa() -> None:
    with contextlib.suppress(OSError):
        _recusa_da_assinatura().unlink(missing_ok=True)


def _registrar_a_baixa(topo: str, veredito: str, **resto: Any) -> None:
    """O que a última baixada conferiu, para a peça Hefesto ler: o ``HEAD`` de então, o veredito e
    o que mais ele traz (``commit``, ``origem``, ``motivo``, ``oferta``)."""
    with contextlib.suppress(OSError):
        arquivo = _estado_da_baixa()
        temporaria = arquivo.with_name(f".{arquivo.name}.{os.getpid()}")
        temporaria.write_text(
            json.dumps({"topo": topo, "veredito": veredito, "em": time.time(), **resto}),
            encoding="utf-8")
        temporaria.replace(arquivo)


def _estado_da_baixa() -> Path:
    from hefesto_dualsense4unix.utils.xdg_paths import state_dir

    return state_dir(ensure=True) / ARQUIVO_DA_BAIXA


def ler_a_baixa() -> dict[str, Any]:
    with contextlib.suppress(OSError, ValueError):
        dado = json.loads(_estado_da_baixa().read_text(encoding="utf-8"))
        if isinstance(dado, dict):
            return dado
    return {}


def frase_da_baixa(baixa: dict[str, Any]) -> str:
    """O que a peça Hefesto diz de uma baixada que não pôde avançar, e o que fazer; vazio se a
    baixada não trouxe motivo de revisão."""
    veredito = baixa.get("veredito")
    if veredito == DIVERGIU and baixa.get("oferta"):
        origem = baixa.get("origem") or f"origin/{RAMO}"
        guardado = f"{RAMO}-antes-{time.strftime('%Y%m%d')}"
        return (f"O {RAMO} do projeto foi reescrito: guarde o seu num ramo datado "
                f"(git branch {guardado}) e refaça pelo publicado (git reset --hard {origem})")
    return FRASES_DA_BAIXA.get(str(veredito), "")


def baixar(raiz: Path, *, jogo_aberto: Callable[[], bool] = _jogo_aberto) -> str | None:
    """Traz o ``dev`` do remoto sem tocar na árvore. Devolve o commit, se ele é outro; o que
    conferiu fica em ``versao-baixada.json``."""
    topo = _git(raiz, "rev-parse", "HEAD") or ""
    motivo = por_que_nao(raiz, jogo_aberto)
    if motivo:
        _dizer(f"fica como está ({motivo})")
        _registrar_a_baixa(topo, VEREDITO_DO_MOTIVO.get(motivo, ESPERA), motivo=motivo)
        return None
    remoto = remoto_do_produto(raiz)
    if remoto is None:
        _dizer("fica como está (sem o remoto do produto)")
        _registrar_a_baixa(topo, SEM_REMOTO)
        return None
    origem = f"{remoto}/{RAMO}"
    if _git(raiz, "fetch", "--quiet", "--no-tags", remoto, RAMO) is None:
        _dizer("fica como está (o remoto não respondeu)")
        _registrar_a_baixa(topo, SEM_REDE, origem=origem, motivo="o remoto não respondeu")
        return None
    alvo = _git(raiz, "rev-parse", "--verify", "FETCH_HEAD^{commit}")
    if alvo is not None and alvo == topo:
        _esquecer_a_recusa()
        _dizer("já é a mais recente")
        _registrar_a_baixa(topo, ATUAL, commit=alvo, origem=origem)
        return None
    if alvo is None or not topo or not _e_avanco(raiz, topo, alvo):
        _dizer(FORA_DO_AVANCO)
        if alvo is not None and _e_avanco(raiz, alvo, topo):
            _registrar_a_baixa(topo, ATUAL, commit=alvo, origem=origem)
            return None
        oferta = bool(alvo and topo and _a_reescrita_se_aceita(raiz, topo, alvo))
        _registrar_a_baixa(topo, DIVERGIU, commit=alvo or "", origem=origem, oferta=oferta)
        return None
    if sem_a_assinatura_da_casa(raiz, alvo):
        _recusar_sem_assinatura(alvo)
        _registrar_a_baixa(topo, SEM_A_ASSINATURA, commit=alvo, origem=origem)
        return None
    _dizer(f"{alvo[:CURTO]} baixada: entra quando a janela fechar")
    _registrar_a_baixa(topo, AVANCA, commit=alvo, origem=origem)
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


def guardar_a_configuracao(antes: str) -> Path | None:
    """Copia a configuração de quem usa para o state, com a hora e o commit de ``antes`` no nome, e
    guarda só as ``COPIAS_GUARDADAS`` mais novas. ``None``: não há configuração a guardar; a cópia
    que não coube levanta ``OSError`` e não deixa metade no lugar de uma cópia inteira."""
    from hefesto_dualsense4unix.utils.xdg_paths import config_dir, state_dir

    origem = config_dir()
    if not origem.is_dir():
        return None
    pasta = state_dir(ensure=True) / PASTA_DAS_COPIAS
    pasta.mkdir(mode=0o700, exist_ok=True)
    carimbo = datetime.now().strftime("%Y%m%dT%H%M%S%f")
    destino = pasta / f"{carimbo}-{antes[:CURTO]}"
    try:
        shutil.copytree(origem, destino, symlinks=True)
    except OSError:
        shutil.rmtree(destino, ignore_errors=True)
        raise
    for velha in sorted(p for p in pasta.iterdir() if p.is_dir())[:-COPIAS_GUARDADAS]:
        shutil.rmtree(velha, ignore_errors=True)
    return destino


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
    """A linha que a aba Sistema e o ``doctor`` dizem: o install que parou com um motivo, ou o
    commit novo que ficou de fora sem a assinatura do projeto."""
    from hefesto_dualsense4unix.utils.repo_files import como_atualizar_esta_instalacao

    motivo = _motivo_da_nota(_linhas_da_nota() or [])
    if not motivo:
        with contextlib.suppress(OSError):
            if _recusa_da_assinatura().exists():
                return ("[WARN]", f"A versão nova ficou de fora ({SEM_ASSINATURA}).")
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


def _pulos_de_root() -> Path:
    from hefesto_dualsense4unix.utils.xdg_paths import state_dir

    return state_dir() / PULOS_DE_ROOT_DO_INSTALL


def _o_install_pulou_o_root() -> bool:
    """O ``install.sh`` é o único que sabe se um passo de administrador ficou por fazer: ele grava
    cada pulo no state e apaga o arquivo se não pulou nenhum."""
    with contextlib.suppress(OSError, ValueError):
        return bool(_pulos_de_root().read_text(encoding="utf-8").strip())
    return False


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
    """Roda o install e devolve a nota, que ele apaga ao fim, se algo ficou por fazer.

    O motivo é o erro real quando o install falhou, e só sem erro e com passo de root pulado é a
    falta de autorização."""
    faixas = _faixas_da_nota()
    with contextlib.suppress(OSError):
        _pulos_de_root().unlink(missing_ok=True)
    motivo = rodar(raiz)
    if not motivo and _o_install_pulou_o_root():
        motivo = SEM_AUTORIZACAO
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
        return INSTALL_EM_CURSO
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

    motivo = por_que_nao(raiz, jogo_aberto) or (INSTALL_EM_CURSO if _install_em_curso() else "")
    if motivo:
        _dizer(f"a baixada fica para depois ({motivo})")
        return False
    antes = _git(raiz, "rev-parse", "HEAD")
    if antes is None or not _e_avanco(raiz, antes, alvo):
        _dizer(FORA_DO_AVANCO)
        return False
    if sem_a_assinatura_da_casa(raiz, alvo):
        _recusar_sem_assinatura(alvo)
        return False
    caminhos = _git(raiz, "diff", "--name-only", "--no-renames", antes, alvo)
    if caminhos is not None and any(n.startswith(PEDEM_COPIA) for n in caminhos.splitlines()):
        try:
            copia = guardar_a_configuracao(antes)
        except OSError as erro:
            _dizer(f"a baixada fica para depois (a cópia da configuração não coube: {erro})")
            return False
        if copia is not None:
            _guardada_no_registro(copia)
    avanco = None
    if caminhos is not None:
        avanco = _git(
            raiz, "merge", "--quiet", "--ff-only", "--no-overwrite-ignore", alvo, com_teto=False)
    if caminhos is None or avanco is None:
        _dizer("o avanço não coube: fica como está")
        return False
    _esquecer_a_recusa()
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


def _atualizacao_automatica() -> bool:
    from hefesto_dualsense4unix.app.actions.atualizador import ler_a_escolha

    return ler_a_escolha().sozinho


def _guardada_no_registro(copia: Path) -> None:
    from hefesto_dualsense4unix.app.actions.atualizador import _anotar

    _anotar(f"configuração guardada em {copia}")
    _dizer(f"a configuração ficou guardada em {copia}")


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
            if baixada and not _atualizacao_automatica():
                _dizer(f"{baixada[0][:CURTO]} baixada: espera o «Atualizar tudo» em Atualizações")
                retomar_o_install(raiz)
            elif not (baixada and aplicar(raiz, baixada[0])):
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

"""As peças do atualizador: de onde cada uma lê a versão, e como baixa, instala e aplica.

O que pede root passa pelo ajudante do install (``AJUDANTE``), por ``sudo -n``, com verbo de lista
fechada e sem argumento livre: sem a regra, a etapa falha com o porquê, e nada pede senha. O resto
roda como quem usa. A reinstalação refaz a versão da máquina pelo caminho da subida, com verbos
fechados no ajudante.

O que só pode depois (a Steam aberta, o voo, um install em curso) levanta ``EsperaError``, com a
pergunta que diz quando passou; a receita da casa cuja cura já está em cima é «Atualizado».
"""
from __future__ import annotations

import codecs
import contextlib
import dataclasses
import hashlib
import json
import os
import re
import selectors
import shutil
import signal
import subprocess
import sys
import tarfile
import time
import urllib.request
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from hefesto_dualsense4unix.app.actions.atualizador import (
    EsperaError,
    Etapa,
    EtapaFalhouError,
    NadaAFazerError,
    Passo,
    Peca,
    Reinstalacao,
    Versoes,
    _anotar,
    data_do_github,
    ordem,
    passou_a_quarentena,
)
from hefesto_dualsense4unix.utils import repo_files

AJUDANTE = Path("/usr/local/lib/hefesto-dualsense4unix/atualizador-raiz")
RAIZ_DO_REPOSITORIO = Path(__file__).resolve().parents[4]
API_DO_GITHUB = "https://api.github.com/repos/{}/releases/latest"
API_DA_TAG = "https://api.github.com/repos/{}/releases/tags/{}"
REPO_DO_MANGOHUD = "flightlessmango/MangoHud"
REPO_DO_UMU = "Open-Wine-Components/umu-launcher"
PRAZO_DA_REDE_S = 30
TETO_DO_COMANDO_S = 3 * 3600.0
TETO_DA_PERGUNTA_S = 60.0
PRAZO_DO_ENCERRAMENTO_S = 5.0
VALIDADE_DA_LISTA_DO_APT_S = 600.0
PACOTE_DO_PRODUTO = "hefesto-dualsense4unix"
RC_NADA_A_CONSTRUIR = 9
RC_TRAVA_OCUPADA = 11
OUTRO_INSTALADOR = "outro instalador está usando o sistema de pacotes"
GERENCIADORES_DA_DISTRO = (
    (("steamos",), ""),
    (("fedora", "rhel", "centos", "rocky", "almalinux", "nobara"), "sudo dnf upgrade"),
    (("arch", "manjaro", "cachyos", "endeavouros"), "sudo pacman -Syu"),
    (("opensuse", "suse", "sles"), "sudo zypper update"),
    (("debian", "ubuntu"), "sudo apt upgrade"),
)
OS_RELEASE = (Path("/run/host/os-release"), Path("/etc/os-release"))
MARCA_DO_OSTREE = Path("/run/ostree-booted")
GRUPO_NVIDIA = re.compile(r"^(?:nvidia-|libnvidia-|xserver-xorg-video-nvidia)")
GRUPO_KERNEL = re.compile(r"^linux-(?:system76|generic|image-|headers-|modules-|signed-)")
METAS_DO_KERNEL = ("linux-system76", "linux-generic", "linux-image-generic")
_STATUS_DO_APT = re.compile(r"^(?:dlstatus|pmstatus):[^:]*:(?P<pct>[0-9.]+):")

_apt_lido_em: list[float] = []


def _encerrar(processo: subprocess.Popen[bytes]) -> None:
    for sinal in (signal.SIGTERM, signal.SIGKILL):
        with contextlib.suppress(OSError):
            os.killpg(processo.pid, sinal)
        with contextlib.suppress(subprocess.TimeoutExpired):
            processo.wait(timeout=PRAZO_DO_ENCERRAMENTO_S)
            return


def _comando(argv: Sequence[str], *, linha: Callable[[str], None] | None = None,
             env: dict[str, str] | None = None,
             teto_s: float = TETO_DO_COMANDO_S) -> tuple[int, str]:
    """Roda ``argv`` sem terminal, linha a linha. Devolve o código e a última linha não vazia.

    O teto vale com ou sem saída, e a leitura para no teto mesmo que um processo fora do alcance
    de quem chama (o root atrás do ``sudo``) ainda segure a saída: a fila nunca se prende.
    """
    try:
        processo = subprocess.Popen(
            list(argv), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, env=env, start_new_session=True)
    except OSError as erro:
        return 127, erro.strerror or str(erro)
    assert processo.stdout is not None
    saida = processo.stdout
    decodificar = codecs.getincrementaldecoder("utf-8")(errors="replace")
    prazo = time.monotonic() + teto_s
    ultima, resto, estourou = "", "", False

    def _entregar(texto: str) -> None:
        nonlocal ultima
        if texto.strip():
            ultima = texto.strip()
        if linha is not None:
            linha(texto)

    with selectors.DefaultSelector() as olho:
        olho.register(saida, selectors.EVENT_READ)
        while True:
            falta = prazo - time.monotonic()
            if falta <= 0:
                estourou = True
                break
            if not olho.select(falta):
                continue
            bloco = os.read(saida.fileno(), 65536)
            if not bloco:
                break
            resto += decodificar.decode(bloco).replace("\r\n", "\n").replace("\r", "\n")
            *linhas, resto = resto.split("\n")
            for texto in linhas:
                _entregar(texto)
    resto += decodificar.decode(b"", final=True)
    if resto:
        _entregar(resto)
    if not estourou:
        try:
            rc = processo.wait(timeout=max(prazo - time.monotonic(), 0.0))
        except subprocess.TimeoutExpired:
            estourou = True
    saida.close()
    if estourou:
        _encerrar(processo)
        return 124, f"passou de {teto_s / 60:.0f} minutos"
    return rc, ultima


def _saida(argv: Sequence[str]) -> str | None:
    try:
        feito = subprocess.run(list(argv), stdin=subprocess.DEVNULL, capture_output=True,
                               text=True, check=False, timeout=TETO_DA_PERGUNTA_S)
    except (OSError, subprocess.TimeoutExpired) as erro:
        _anotar(f"{argv[0]} não respondeu: {erro}")
        return None
    return feito.stdout if feito.returncode == 0 else None


def _ler(url: str) -> bytes:
    pedido = urllib.request.Request(url, headers={
        "User-Agent": PACOTE_DO_PRODUTO, "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(pedido, timeout=PRAZO_DA_REDE_S) as resposta:
        return bytes(resposta.read(4 * 1024 * 1024))


def _baixar(url: str, destino: Path, passo: Passo, sha256: str = "") -> None:
    """Baixa com a barra andando; com ``sha256`` (o ``digest`` do GitHub), só fica se bater."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    parcial = destino.with_name(f"{destino.name}.hefesto-download")
    soma = hashlib.sha256()
    pedido = urllib.request.Request(url, headers={"User-Agent": PACOTE_DO_PRODUTO})
    try:
        with urllib.request.urlopen(pedido, timeout=PRAZO_DA_REDE_S) as resposta, \
                parcial.open("wb") as saida:
            tamanho = int(resposta.headers.get("Content-Length") or 0)
            lidos = 0
            for bloco in iter(lambda: resposta.read(1024 * 1024), b""):
                saida.write(bloco)
                soma.update(bloco)
                lidos += len(bloco)
                if tamanho:
                    passo.fracao(lidos / tamanho)
    except OSError as erro:
        parcial.unlink(missing_ok=True)
        raise EtapaFalhouError(f"o download de {url} parou: {erro}") from None
    if sha256 and soma.hexdigest() != sha256.lower():
        parcial.unlink(missing_ok=True)
        raise EtapaFalhouError(f"o sha256 de {destino.name} não é o publicado")
    parcial.replace(destino)
    passo.fracao(1.0)


def _cache() -> Path:
    from hefesto_dualsense4unix.utils.xdg_paths import cache_dir

    return cache_dir(ensure=True) / "atualizador"


def _dados() -> Path:
    from hefesto_dualsense4unix.utils.xdg_paths import data_dir

    return data_dir(ensure=True)


def _release(repo: str) -> dict[str, Any]:
    release = json.loads(_ler(API_DO_GITHUB.format(repo)).decode("utf-8"))
    if not isinstance(release, dict):
        raise ValueError("a release não veio")
    return release


def publicada_em(release: dict[str, Any]) -> float:
    """O ``published_at`` da release do GitHub, em segundos; 0 se não veio."""
    return data_do_github(str(release.get("published_at") or ""))


def _corte(dados: dict[str, Any]) -> float | None:
    """O corte da quarentena que a subida automática traz nos dados da peça; ``None``: na hora."""
    corte = dados.get("corte")
    return float(corte) if isinstance(corte, (int, float)) else None


def _release_da_vez(repo: str, dados: dict[str, Any]) -> dict[str, Any]:
    """A release que o download leva: a última; na subida automática, só a publicada antes do
    corte, e a peça fica como está nesta vez se a última ainda está na quarentena."""
    release = _release(repo)
    if not passou_a_quarentena(publicada_em(release), _corte(dados)):
        _anotar(f"{repo}: {release.get('tag_name') or '?'} na quarentena; fica para a próxima")
        raise NadaAFazerError("")
    return release


def _ativo(release: dict[str, Any], casa: Callable[[str], bool]) -> tuple[str, str, str]:
    """(nome, url, sha256) do primeiro ativo que casa; o sha256 vem do ``digest`` do GitHub."""
    for ativo in release.get("assets") or []:
        if not isinstance(ativo, dict):
            continue
        nome = str(ativo.get("name", ""))
        digest = str(ativo.get("digest", ""))
        if casa(nome) and digest.startswith("sha256:"):
            return nome, str(ativo.get("browser_download_url", "")), digest.split(":", 1)[1]
    raise EtapaFalhouError("a release não traz o arquivo com a soma publicada")


def _sem_v(tag: str) -> str:
    return tag[1:] if tag[:1] in ("v", "V") and tag[1:2].isdigit() else tag


class RaizSaiuError(EtapaFalhouError):
    """O ajudante saiu com um código que não é zero: o código vai junto do porquê."""

    def __init__(self, motivo: str, codigo: int) -> None:
        super().__init__(motivo)
        self.codigo = codigo


def _raiz(acao: str, *args: str, passo: Passo | None = None,
          teto_s: float = TETO_DO_COMANDO_S) -> str:
    """O ajudante root, sem senha: falha com o porquê se a regra do install não está lá. A trava
    do dpkg que outro instalador segura além do prazo do apt é espera, não falha."""
    if not AJUDANTE.is_file():
        raise EtapaFalhouError("o ajudante do install não está instalado: rode o install")

    def linha(texto: str) -> None:
        if passo is not None and texto.startswith("removido: "):
            passo.dizer(texto.strip())
        achado = _STATUS_DO_APT.match(texto)
        if achado and passo is not None:
            with contextlib.suppress(ValueError):
                passo.fracao(float(achado.group("pct")) / 100.0)

    rc, ultima = _comando(["sudo", "-n", str(AJUDANTE), acao, *args], linha=linha, teto_s=teto_s)
    if rc == RC_TRAVA_OCUPADA:
        raise EsperaError(OUTRO_INSTALADOR, lambda: True)
    if rc != 0:
        raise RaizSaiuError(ultima or f"{acao} saiu com {rc}", rc)
    return ultima


def _resposta_da_raiz(acao: str, *args: str) -> tuple[str, str]:
    """O ajudante responde sem mexer em nada: o porquê (vazio se sim) e a última linha."""
    try:
        return "", _raiz(acao, *args, teto_s=TETO_DA_PERGUNTA_S) or ""
    except EtapaFalhouError as erro:
        texto = str(erro)
        if texto.startswith("sudo:"):
            return "a regra do sudo não traz a reinstalação: rode o install", ""
        return re.sub(r"^[\w.-]+: ", "", texto) or acao, ""


def _pergunta_da_raiz(acao: str, *args: str) -> str:
    return _resposta_da_raiz(acao, *args)[0]


def _do_ajudante(acao: str, *args: str) -> Etapa:
    def etapa(passo: Passo, _dados_: dict[str, Any]) -> None:
        _raiz(acao, *args, passo=passo)
        passo.fracao(1.0)

    return etapa


def _ajudante_pronto() -> bool:
    return AJUDANTE.is_file() and _saida(["sudo", "-n", "-l", str(AJUDANTE), "apt-lista"]) \
        is not None


def _atualizar_a_lista_do_apt(rede: bool) -> None:
    if not rede or not _ajudante_pronto():
        return
    if _apt_lido_em and time.monotonic() - _apt_lido_em[0] < VALIDADE_DA_LISTA_DO_APT_S:
        return
    with contextlib.suppress(EtapaFalhouError):
        _raiz("apt-lista")
    _apt_lido_em[:] = [time.monotonic()]


def _atualizaveis() -> dict[str, tuple[str, str]]:
    """``apt list --upgradable``, fora o segurado e o da casa: pacote -> (instalada, candidata)."""
    texto = _saida(["apt", "list", "--upgradable"])
    segurados = set((_saida(["apt-mark", "showhold"]) or "").split())
    saida: dict[str, tuple[str, str]] = {}
    for linha in (texto or "").splitlines():
        achado = re.match(r"^(?P<p>[^/\s]+)/\S+\s+(?P<nova>\S+)\s+\S+\s+"
                          r"\[[^:\]]*:\s*(?P<velha>[^\]\s]+)\]", linha)
        if achado and achado.group("p") not in segurados and not _da_casa(achado.group("velha")):
            saida[achado.group("p")] = (achado.group("velha"), achado.group("nova"))
    return saida


def _instalados(*padroes: str) -> dict[str, str]:
    texto = _saida(["dpkg-query", "-W", "-f", "${Package}\t${Version}\t${db:Status-Abbrev}\n",
                    *padroes])
    saida = {}
    for linha in (texto or "").splitlines():
        partes = linha.split("\t")
        if len(partes) == 3 and partes[2].startswith("ii"):
            saida[partes[0]] = partes[1]
    return saida


def _a_montante(versao: str) -> str:
    sem_epoca = versao.split(":", 1)[-1]
    return sem_epoca.split("-", 1)[0]


def _do_apt(grupo: str, nome: str) -> Callable[[Passo, dict[str, Any]], None]:
    def baixar(passo: Passo, _dados_: dict[str, Any]) -> None:
        _raiz_do_grupo("apt-baixar", grupo, passo)

    def instalar(passo: Passo, _dados_: dict[str, Any]) -> None:
        _raiz_do_grupo("apt-instalar", grupo, passo)

    return baixar if nome == "baixar" else instalar


def _raiz_do_grupo(verbo: str, grupo: str, passo: Passo) -> None:
    try:
        _raiz(verbo, grupo, passo=passo)
    except RaizSaiuError as erro:
        if erro.codigo == RC_NADA_A_CONSTRUIR:
            raise NadaAFazerError(str(erro)) from None
        raise


def _limpar(passo: Passo, _dados_: dict[str, Any]) -> None:
    _raiz("apt-limpar", passo=passo)
    passo.fracao(1.0)


def versoes_da_nvidia(rede: bool) -> Versoes:
    if not AJUDANTE.is_file():
        return Versoes(existe=False)
    _atualizar_a_lista_do_apt(rede)
    drivers = {p: v for p, v in _instalados("nvidia-driver-*").items()
               if p.startswith("nvidia-driver-")}
    if not drivers:
        return Versoes(existe=False)
    pacote, versao = sorted(drivers.items())[0]
    novas = {p: n for p, (_v, n) in _atualizaveis().items() if GRUPO_NVIDIA.match(p)}
    candidata = novas.get(pacote, versao)
    return Versoes(_a_montante(versao), _a_montante(candidata) if rede or novas else None,
                   dica=pacote, nova=bool(novas),
                   completa=f"{versao} → {candidata}" if novas else versao)


def _kernel_do_pacote(versao: str) -> str:
    achado = re.match(r"^(\d+\.\d+(?:\.\d+)?-\d+)", versao.split(":", 1)[-1])
    return achado.group(1) if achado else ""


def versoes_do_kernel(rede: bool) -> Versoes:
    if shutil.which("apt-get") is None or not AJUDANTE.is_file():
        return Versoes(existe=False)
    _atualizar_a_lista_do_apt(rede)
    rodando = os.uname().release
    agora = _kernel_do_pacote(rodando) or rodando
    novas = {p: n for p, (_v, n) in _atualizaveis().items() if GRUPO_KERNEL.match(p)}
    metas = _metas_do_kernel()
    meta = next((novas[m] for m in metas if m in novas), "")
    candidata = _kernel_do_pacote(meta) if meta else agora
    dica = next(iter(metas), "") or rodando
    return Versoes(agora.split("-", 1)[0], candidata.split("-", 1)[0], dica=dica,
                   nova=bool(meta), completa=f"{agora} → {candidata}" if meta else agora)


def _metas_do_kernel() -> list[str]:
    """As metas instaladas do kernel, pelo ajudante: as do Pop, do Ubuntu e do Debian."""
    try:
        texto = subprocess.run([str(AJUDANTE), "kernel-metas"], check=False, text=True,
                               capture_output=True, timeout=TETO_DA_PERGUNTA_S).stdout
    except (OSError, subprocess.SubprocessError):
        texto = ""
    return [m for m in texto.split() if GRUPO_KERNEL.match(m)] \
        or list(_instalados(*METAS_DO_KERNEL))


def _pacotes(n: int) -> str:
    return f"{n} pacote{'s' if n != 1 else ''}"


def _os_release() -> dict[str, str]:
    """Os campos do os-release do sistema: o do host visto de dentro do Flatpak (``/run/host``),
    senão o do ``/etc``."""
    for caminho in OS_RELEASE:
        with contextlib.suppress(OSError):
            linhas = caminho.read_text(encoding="utf-8").splitlines()
            return {c: v.strip().strip('"') for c, _, v in (x.partition("=") for x in linhas)}
    return {}


def _versao_da_distro() -> str:
    return _os_release().get("VERSION_ID", "")


def _nome_da_distro() -> str:
    return _os_release().get("PRETTY_NAME", "")


def _ids_da_distro() -> list[str]:
    campos = _os_release()
    return f"{campos.get('ID', '')} {campos.get('ID_LIKE', '')}".lower().split()


def _gesto_do_sistema() -> str:
    """O gesto de quem usa onde o Hefesto não sobe os pacotes: o gerenciador da distribuição, com o
    comando lido do ``ID`` e do ``ID_LIKE`` do os-release; o sistema de imagem (ostree, SteamOS)
    não leva comando."""
    ids = _ids_da_distro()
    comando = "" if MARCA_DO_OSTREE.exists() else next(
        (c for nomes, c in GERENCIADORES_DA_DISTRO if any(i in nomes for i in ids)), "")
    base = "Atualize pelo gerenciador da distribuição"
    return f"{base}: {comando}" if comando else base


def versoes_do_sistema(rede: bool) -> Versoes:
    _atualizar_a_lista_do_apt(rede)
    if shutil.which("apt-get") is None or not AJUDANTE.is_file():
        distro = _versao_da_distro()
        return Versoes(distro, distro, rotulo="Pela distribuição", dica=_nome_da_distro(),
                       gesto=_gesto_do_sistema())
    resto = [p for p in _atualizaveis() if not GRUPO_NVIDIA.match(p) and not GRUPO_KERNEL.match(p)]
    distro = _versao_da_distro()
    if resto:
        return Versoes(distro, str(len(resto)), rotulo=_pacotes(len(resto)),
                       dica=" · ".join(sorted(resto)[:12]), nova=True)
    return Versoes(distro, distro, dica=_nome_da_distro())


def _dkms_status() -> list[tuple[str, str, str, str]]:
    texto = _saida(["dkms", "status"])
    saida = []
    for linha in (texto or "").splitlines():
        achado = re.match(r"^(?P<m>[^/,]+)/(?P<v>[^,]+),\s*(?P<k>[^,]+),\s*[^:]+:\s*(?P<e>\S+)",
                          linha)
        if achado:
            saida.append((achado.group("m"), achado.group("v"), achado.group("k").strip(),
                          achado.group("e")))
    return saida


def _kernels_com_headers() -> list[str]:
    raiz = Path("/lib/modules")
    with contextlib.suppress(OSError):
        return sorted((p.name for p in raiz.iterdir() if (p / "build").exists()),
                      key=lambda k: [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", k)])
    return []


def versoes_do_dkms(rede: bool) -> Versoes:
    status = [s for s in _dkms_status() if s[0].startswith(f"{PACOTE_DO_PRODUTO.split('-')[0]}-")]
    if not status:
        return Versoes(existe=False)
    modulos = sorted({s[0] for s in status})
    versao = status[0][1]
    kernels = _kernels_com_headers()
    alvo = kernels[-1] if kernels else os.uname().release
    prontos = {s[0] for s in status if s[2] == alvo and s[3] == "installed"}
    faltam = [m for m in modulos if m not in prontos]
    curto = alvo.split("-", 1)[0]
    return Versoes(versao, versao, dica=f"{len(modulos)} módulos · {curto}", nova=bool(faltam))


def _refazer_o_dkms(passo: Passo, _dados_: dict[str, Any]) -> None:
    _raiz("dkms-refazer", passo=passo)
    passo.fracao(1.0)


def _aplicar_o_kernel(passo: Passo, dados: dict[str, Any]) -> None:
    _raiz("dkms-refazer", passo=passo)
    passo.fracao(0.5)
    _limpar(passo, dados)


def _instalar_o_kernel(passo: Passo, _dados_: dict[str, Any]) -> dict[str, Any]:
    _raiz("apt-instalar", "kernel", passo=passo)
    return {"kernel": os.uname().release}


def _voltar_o_kernel(_anterior: dict[str, Any]) -> None:
    _raiz("kernel-anterior")


def _proton() -> Any:
    from hefesto_dualsense4unix.integrations import proton_pin as pp

    return pp


def _steam_livre() -> bool:
    return not _proton()._steam_gate()


def _esperar_a_steam(barra: str) -> EsperaError:
    """A Steam lê a pasta dos Protons ao abrir: aberta, a peça espera o fecho e segue sozinha."""
    pp = _proton()
    return EsperaError(pp._PORQUE_A_STEAM_BARRA.get(barra, barra), _steam_livre)


def _curto_do_ge(nome: str) -> str:
    return nome.removeprefix("GE-Proton").removesuffix("-x86_64")


def versoes_do_proton(rede: bool) -> Versoes:
    pp = _proton()
    from hefesto_dualsense4unix.integrations import qualificar_proton as qp

    conf = pp._load_conf(None)
    vale = pp.pino_que_vale(conf, pp.default_compat_dir())
    if not rede:
        return Versoes(_curto_do_ge(vale), None)
    release = json.loads(pp._ler_da_rede(pp.GE_ULTIMA_API).decode("utf-8"))
    achada = pp.a_ultima_do_ge(release) if isinstance(release, dict) else None
    if achada is None:
        return Versoes(_curto_do_ge(vale), None)
    nome = achada[0]
    registro = pp._ler_registro(pp.default_cache_dir())
    revisar = pp.reprovada_no_registro(registro) if registro.get("name") == nome else ""
    return Versoes(_curto_do_ge(vale), _curto_do_ge(nome),
                   nova=qp.ordem_da_versao(nome) > qp.ordem_da_versao(vale), revisar=revisar,
                   publicada_em=publicada_em(release))


def _baixar_o_proton(passo: Passo, dados: dict[str, Any]) -> None:
    pp = _proton()
    feito = pp.baixar_a_ultima_do_ge(
        pp.default_cache_dir(), forcar=True, corte=_corte(dados),
        baixar=lambda url, destino: _baixar(url, destino, passo))
    if feito.estado == "em_quarentena":
        _anotar(f"proton: {feito.detalhe}; fica para a próxima")
        raise NadaAFazerError("")
    if feito.estado not in ("baixada", "em_cache"):
        raise EtapaFalhouError(feito.detalhe or feito.estado)


def _instalar_o_proton(passo: Passo, _dados_: dict[str, Any]) -> None:
    pp = _proton()
    feito = pp.instalar_a_ultima_do_cache(pp._load_conf(None), compat_dir=pp.default_compat_dir(),
                                          cache_dir=pp.default_cache_dir())
    if feito.estado == "espera_a_steam":
        raise EsperaError(feito.detalhe or feito.estado, _steam_livre)
    if feito.estado not in ("instalada", "em_dia"):
        raise EtapaFalhouError(feito.detalhe or feito.estado)
    passo.fracao(1.0)


def _aplicar_o_proton(passo: Passo, _dados_: dict[str, Any]) -> None:
    pp = _proton()
    from hefesto_dualsense4unix.integrations import censo_dos_lancadores as censo

    conf = pp._load_conf(None)
    jogos = len(pp.list_installed_appids())
    passo.contagem("Steam", 0, jogos)
    travado = pp.lock_proton_for_all_games(conf=conf, todos=True)
    if travado.get("status") == "recusado" and travado.get("reason") in pp._PORQUE_A_STEAM_BARRA:
        raise _esperar_a_steam(str(travado["reason"]))
    if travado.get("status") in ("erro", "recusado"):
        raise EtapaFalhouError(str(travado.get("reason") or travado.get("status")))
    passo.contagem("Steam", jogos, jogos)
    passo.fracao(0.5)
    casas = len(censo.casas_do_heroic()[0])
    passo.contagem("Heroic", 0, casas)
    pp.apontar_os_lancadores_para_o_pino(conf=conf)
    passo.contagem("Heroic", casas, casas)
    pp.apagar_as_sobras()
    passo.fracao(1.0)


def _conf_da_reinstalacao() -> dict[str, str] | None:
    """O pino que vale, com a url e o sha256 que o conf ou o registro da última guardaram."""
    pp = _proton()
    conf = pp._load_conf(None)
    vale = pp.pino_que_vale(conf, pp.default_compat_dir())
    registro = pp._ler_registro(pp.default_cache_dir())
    for fonte in (conf, registro):
        if str(fonte.get("name", "")) == vale and fonte.get("sha256") and fonte.get("url"):
            return {"name": vale, "url": str(fonte["url"]), "sha256": str(fonte["sha256"])}
    return None


def _proton_sem_reinstalar(_versoes: Versoes) -> str:
    if _conf_da_reinstalacao() is None:
        return "a versão de agora não tem a soma guardada: a reinstalação espera a próxima subida"
    return ""


def _tarball_da_reinstalacao(conf: dict[str, str], baixar: Callable[[str, Path], None] | None,
                             ) -> Path:
    pp = _proton()
    feito = pp.adiantar_para_o_cache(conf, cache_dir=pp.default_cache_dir(), downloader=baixar)
    if feito.state != "em_cache":
        raise EtapaFalhouError(feito.detail or feito.state)
    return Path(feito.detail)


def _baixar_de_novo_o_proton(passo: Passo, _dados_: dict[str, Any]) -> dict[str, Any]:
    conf = _conf_da_reinstalacao()
    if conf is None:
        raise EtapaFalhouError("a versão de agora não tem a soma guardada")
    _tarball_da_reinstalacao(conf, lambda url, destino: _baixar(url, destino, passo))
    passo.fracao(1.0)
    return {"conf": conf}


def _reinstalar_o_proton(passo: Passo, dados: dict[str, Any]) -> None:
    pp = _proton()
    conf = dados.get("conf") or {}
    if not conf.get("name"):
        raise EtapaFalhouError("o tarball da versão de agora não veio")
    tarball = _tarball_da_reinstalacao(conf, None)
    barra = pp._steam_gate()
    if barra:
        raise _esperar_a_steam(barra)
    try:
        pp._extract_verified_tarball(tarball, conf["name"], pp.default_compat_dir())
    except (OSError, tarfile.TarError) as erro:
        raise EtapaFalhouError(f"o {conf['name']} não se refez: {erro}") from None
    passo.fracao(1.0)


def _anterior_do_proton() -> dict[str, Any] | None:
    """A anterior que quem instalou guardou no registro do cache, se ainda volta."""
    pp = _proton()
    compat, cache = pp.default_compat_dir(), pp.default_cache_dir()
    registro = pp._ler_registro(cache)
    velha = str(registro.get("anterior", ""))
    if not velha or not (pp.pinned_proton_installed(velha, compat)
                         or (registro.get("anterior_sha256")
                             and (cache / f"{velha}.tar.gz").is_file())):
        return None
    vale = pp.pino_que_vale(pp._load_conf(None), compat)
    if vale == velha:
        return None
    return {"nome": "GE-Proton", "anterior": _curto_do_ge(velha), "agora": _curto_do_ge(vale),
            "desde": registro.get("anterior_em", 0)}


def _voltar_o_proton(_anterior: dict[str, Any]) -> None:
    """Volta à anterior do registro (o jogo, quem pergunta é o ``atualizador.voltar``): com a
    Steam e a nova livres, sob a trava; os jogos vão para a velha antes de a nova sair, e o que
    barra devolve o porquê sem mexer em nada."""
    pp = _proton()
    compat, cache = pp.default_compat_dir(), pp.default_cache_dir()
    registro = pp._ler_registro(cache)
    velha, sha = str(registro.get("anterior", "")), str(registro.get("anterior_sha256", ""))
    if not velha:
        raise EtapaFalhouError("sem versão anterior")
    barra = pp._steam_gate()
    if barra:
        raise EtapaFalhouError(pp._PORQUE_A_STEAM_BARRA.get(barra, barra))
    with pp.trava_do_compat(compat):
        conf = pp._load_conf(None)
        nova = pp.pino_que_vale(conf, compat)
        if nova == velha:
            raise EtapaFalhouError("a anterior já é a de agora")
        if pp._em_uso(compat / nova):
            raise EtapaFalhouError(f"{nova} está em uso agora")
        if not pp.pinned_proton_installed(velha, compat):
            if not sha:
                raise EtapaFalhouError(f"{velha} não está no cache")
            pp.ensure_pinned_proton({"name": velha, "url": "", "sha256": sha}, compat_dir=compat,
                                    cache_dir=cache, downloader=None)
            if not pp.pinned_proton_installed(velha, compat):
                raise EtapaFalhouError(f"{velha} não voltou do cache")
        travado = pp.lock_proton_for_all_games(conf=conf, todos=True, pino=velha)
        if travado.get("status") in ("erro", "recusado"):
            motivo = str(travado.get("reason") or travado.get("status"))
            raise EtapaFalhouError(pp._PORQUE_A_STEAM_BARRA.get(motivo, motivo))
        pp.segurar(cache, nova)
        pp._gravar_registro(cache, {**pp._ler_registro(cache), "anterior": ""})
        shutil.rmtree(compat / nova, ignore_errors=True)
        pp.apontar_os_lancadores_para_o_pino(conf=conf)


def versoes_do_mangohud(rede: bool) -> Versoes:
    texto = _saida(["mangohud", "--version"]) if shutil.which("mangohud") else None
    instalada = _sem_v((texto or "").strip().split()[0]) if (texto or "").strip() else ""
    if not rede:
        return Versoes(instalada, None)
    release = _release(REPO_DO_MANGOHUD)
    publicada = _sem_v(str(release.get("tag_name", "")))
    return Versoes(instalada, publicada or None, publicada_em=publicada_em(release))


def _pasta_do_mangohud() -> Path:
    return Path.home() / ".cache" / PACOTE_DO_PRODUTO / "atualizador" / "mangohud"


def _e_o_binario_do_mangohud(nome: str) -> bool:
    return nome.startswith("MangoHud-") and nome.endswith(".tar.gz") and "Source" not in nome


def _baixar_o_mangohud(passo: Passo, dados: dict[str, Any]) -> None:
    nome, url, sha = _ativo(_release_da_vez(REPO_DO_MANGOHUD, dados), _e_o_binario_do_mangohud)
    pasta = _pasta_do_mangohud()
    if pasta.is_dir():
        for velho in pasta.iterdir():
            if velho.name != nome:
                velho.unlink(missing_ok=True)
    _baixar(url, pasta / nome, passo, sha)


def _instalar_o_mangohud(passo: Passo, _dados_: dict[str, Any]) -> None:
    _raiz("mangohud-instalar", passo=passo)
    passo.fracao(1.0)


def _mangohud_sem_reinstalar(versoes: Versoes) -> str:
    if not versoes.instalada:
        return "o MangoHud não está instalado"
    motivo, resposta = _resposta_da_raiz("mangohud-reinstalavel")
    if motivo:
        return motivo
    nome = resposta.removeprefix("reinstala: ")
    guardada = nome.removeprefix("MangoHud-").removesuffix(".tar.gz")
    if not _e_o_binario_do_mangohud(nome) or _sem_v(guardada) != versoes.instalada:
        return "o MangoHud que o ajudante guardou não é a versão instalada"
    return ""


def _voltar_o_mangohud(_anterior: dict[str, Any]) -> None:
    _raiz("mangohud-voltar")


def _pasta_do_umu() -> Path:
    return _dados() / "umu"


def _umu_na_casa() -> Path:
    return Path.home() / ".local" / "bin" / "umu-run"


def _umu_e_nosso(caminho: Path) -> bool:
    with contextlib.suppress(OSError):
        return caminho.is_symlink() and _pasta_do_umu() in caminho.resolve().parents
    return False


def versoes_do_umu(rede: bool) -> Versoes:
    achado = shutil.which("umu-run")
    caminho = Path(achado) if achado else None
    nosso = caminho is not None and _umu_e_nosso(_umu_na_casa()) and \
        caminho.resolve() == _umu_na_casa().resolve()
    instalada = ""
    if caminho is not None:
        texto = _saida([str(caminho), "--version"]) or ""
        achada = re.search(r"(\d+(?:\.\d+)+)", texto)
        instalada = achada.group(1) if achada else ""
    release = _release(REPO_DO_UMU) if rede else {}
    publicada = _sem_v(str(release.get("tag_name", ""))) if rede else None
    if caminho is None or not nosso:
        return Versoes(instalada, publicada, nova=publicada is not None and bool(publicada),
                       dica="" if caminho is None else str(caminho),
                       publicada_em=publicada_em(release))
    return Versoes(instalada, publicada or None, publicada_em=publicada_em(release))


def _e_o_zipapp(nome: str) -> bool:
    return nome.startswith("umu-launcher-") and nome.endswith("-zipapp.tar")


def _baixar_o_umu(passo: Passo, dados: dict[str, Any]) -> dict[str, Any]:
    release = _release_da_vez(REPO_DO_UMU, dados)
    nome, url, sha = _ativo(release, _e_o_zipapp)
    destino = _cache() / "umu" / nome
    _baixar(url, destino, passo, sha)
    return {"tar": str(destino), "tag": _sem_v(str(release.get("tag_name", "")))}


def _extrair_sem_sair(tar: tarfile.TarFile, pasta: Path) -> None:
    for m in tar.getmembers():
        elo = str(Path(m.name).parent / m.linkname) if m.issym() else m.linkname or m.name
        if not all((pasta / n).resolve().is_relative_to(pasta.resolve()) for n in (m.name, elo)):
            raise EtapaFalhouError(f"o pacote do umu traz um caminho de fora: {m.name}")
    tar.extractall(pasta, filter="data")


def _instalar_o_umu(passo: Passo, dados: dict[str, Any]) -> dict[str, Any]:
    tar_path, versao = Path(str(dados.get("tar", ""))), str(dados.get("tag", ""))
    if not tar_path.is_file() or not versao:
        raise EtapaFalhouError("o pacote do umu não está no cache")
    pasta = _pasta_do_umu() / versao
    temporaria = pasta.with_name(f".{versao}.hefesto")
    shutil.rmtree(temporaria, ignore_errors=True)
    temporaria.mkdir(parents=True)
    try:
        with tarfile.open(tar_path) as tar:
            _extrair_sem_sair(tar, temporaria)
    except (OSError, tarfile.TarError) as erro:
        shutil.rmtree(temporaria, ignore_errors=True)
        raise EtapaFalhouError(f"o pacote do umu não abriu: {erro}") from None
    if not any(temporaria.rglob("umu-run")):
        shutil.rmtree(temporaria, ignore_errors=True)
        raise EtapaFalhouError("o pacote do umu não traz o umu-run")
    shutil.rmtree(pasta, ignore_errors=True)
    temporaria.replace(pasta)
    passo.fracao(1.0)
    atual = _pasta_do_umu() / "atual"
    anterior = atual.resolve().name if atual.is_symlink() else ""
    return {"anterior_dir": anterior}


def _apontar_o_umu(versao: str) -> None:
    pasta = _pasta_do_umu() / versao
    executavel = next(iter(sorted(pasta.rglob("umu-run"))), None)
    if executavel is None:
        raise EtapaFalhouError(f"o umu {versao} não está no disco")
    atual = _pasta_do_umu() / "atual"
    for link, alvo in ((atual, pasta), (_umu_na_casa(), executavel)):
        link.parent.mkdir(parents=True, exist_ok=True)
        novo = link.with_name(f".{link.name}.hefesto")
        novo.unlink(missing_ok=True)
        novo.symlink_to(alvo)
        novo.replace(link)


def _aplicar_o_umu(passo: Passo, dados: dict[str, Any]) -> None:
    casa = _umu_na_casa()
    if casa.exists() and not _umu_e_nosso(casa):
        raise EtapaFalhouError(f"{casa} não é do Hefesto")
    _apontar_o_umu(str(dados.get("tag", "")))
    for velha in sorted(_pasta_do_umu().iterdir()):
        if velha.name not in ("atual", str(dados.get("tag", "")),
                              str(dados.get("anterior_dir", ""))) and velha.is_dir():
            shutil.rmtree(velha, ignore_errors=True)
    baixado = Path(str(dados.get("tar", "")))
    with contextlib.suppress(OSError):
        for pacote in (_cache() / "umu").glob("*.tar"):
            if pacote.name != baixado.name and _e_o_zipapp(pacote.name):
                pacote.unlink()
    passo.fracao(1.0)


def _tag_do_umu_de_agora() -> str:
    atual = _pasta_do_umu() / "atual"
    tag = atual.resolve().name if atual.is_symlink() else ""
    return tag if re.fullmatch(r"\d+(?:\.\d+)+", tag) else ""


def _umu_sem_reinstalar(_versoes: Versoes) -> str:
    if not _umu_e_nosso(_umu_na_casa()):
        return "o umu-run desta máquina não é o do Hefesto"
    if not _tag_do_umu_de_agora():
        return "a versão de agora do umu não está no disco"
    return ""


def _baixar_de_novo_o_umu(passo: Passo, _dados_: dict[str, Any]) -> dict[str, Any]:
    tag = _tag_do_umu_de_agora()
    if not tag or not _umu_e_nosso(_umu_na_casa()):
        raise EtapaFalhouError("o umu de agora não é o do Hefesto")
    release: dict[str, Any] = {}
    for nome in (tag, f"v{tag}"):
        with contextlib.suppress(OSError, ValueError):
            achada = json.loads(_ler(API_DA_TAG.format(REPO_DO_UMU, nome)).decode("utf-8"))
            if isinstance(achada, dict) and _sem_v(str(achada.get("tag_name", ""))) == tag:
                release = achada
                break
    if not release:
        raise EtapaFalhouError(f"a release do umu {tag} não veio")
    nome, url, sha = _ativo(release, _e_o_zipapp)
    destino = _cache() / "umu" / nome
    _baixar(url, destino, passo, sha)
    return {"tar": str(destino), "tag": tag}


def _reapontar_o_umu(passo: Passo, dados: dict[str, Any]) -> None:
    _apontar_o_umu(str(dados.get("tag", "")))
    passo.fracao(1.0)


def _voltar_o_umu(anterior: dict[str, Any]) -> None:
    dados = anterior.get("dados") or {}
    velha = str(dados.get("anterior_dir", ""))
    if not velha:
        raise EtapaFalhouError("sem versão anterior")
    _apontar_o_umu(velha)


def _dependencias_do_produto() -> list[str]:
    from importlib import metadata

    try:
        pedidos = metadata.requires(PACOTE_DO_PRODUTO) or []
    except metadata.PackageNotFoundError:
        return []
    nomes = []
    for pedido in pedidos:
        if "extra ==" in pedido:
            continue
        achado = re.match(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)", pedido)
        if achado:
            nomes.append(achado.group(1).lower().replace("_", "-"))
    return sorted(set(nomes))


def _no_venv() -> bool:
    return sys.prefix != sys.base_prefix and os.access(sys.prefix, os.W_OK)


def _pip(*args: str, linha: Callable[[str], None] | None = None) -> tuple[int, str]:
    return _comando([sys.executable, "-m", "pip", "--disable-pip-version-check", *args],
                    linha=linha)


def _so_antes_de(corte: float | None) -> list[str]:
    """O ``--uploaded-prior-to`` da quarentena: a subida automática só vê o que saiu antes."""
    if corte is None:
        return []
    quando = datetime.fromtimestamp(corte, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return ["--uploaded-prior-to", quando]


def _atrasadas(corte: float | None = None) -> dict[str, tuple[str, str]]:
    """As bibliotecas do produto com versão nova, fora a versão que já não montou aqui; com
    ``corte``, só as publicadas antes dele."""
    texto = _saida([sys.executable, "-m", "pip", "--disable-pip-version-check", "list",
                    "--outdated", "--format=json", *_so_antes_de(corte)])
    if texto is None:
        raise ValueError("o pip não respondeu")
    deps = set(_dependencias_do_produto())
    nao_montam = _as_que_nao_montam()
    saida = {}
    for item in json.loads(texto or "[]"):
        nome = str(item.get("name", "")).lower().replace("_", "-")
        ultima = str(item.get("latest_version", ""))
        visto = nao_montam.get(nome)
        if isinstance(visto, dict) and visto.get("nova") == ultima:
            continue
        if nome in deps:
            saida[nome] = (str(item.get("version", "")), ultima)
    return saida


def versoes_do_python(rede: bool) -> Versoes:
    if not _no_venv():
        return Versoes(existe=False)
    if not rede:
        return Versoes("", None, rotulo="")
    atrasadas = _atrasadas()
    dica = " · ".join(f"{n} {v} → {u}" for n, (v, u) in sorted(atrasadas.items()))
    conferidas = len(set(_dependencias_do_produto()))
    rotulo = _pacotes(len(atrasadas)) if atrasadas else \
        f"{conferidas} biblioteca{'s' if conferidas != 1 else ''} em dia"
    alvo = " · ".join(f"{n} {u}" for n, (_v, u) in sorted(atrasadas.items()))
    return Versoes("", alvo, rotulo=rotulo, dica=dica, nova=bool(atrasadas))


PROVA_DO_PRODUTO = (
    "import inspect\n"
    "import evdev\n"
    "import hefesto_dualsense4unix.cli.app\n"
    "import hefesto_dualsense4unix.daemon.lifecycle\n"
    "import hefesto_dualsense4unix.daemon.main\n"
    "from hefesto_dualsense4unix.integrations.uinput_gamepad import _uinput_sem_no_proprio\n"
    "_uinput_sem_no_proprio(evdev.UInput)\n"
    "if '_find_device' not in inspect.getsource(evdev.UInput.__init__):\n"
    "    raise SystemExit('o evdev novo não chama o _find_device que a cura do pad usa')\n"
)


def _pasta_do_python() -> Path:
    return _cache() / "python"


def _rodas(pasta: Path, alvo: Sequence[str], corte: float | None = None) -> None:
    rc, ultima = _pip("wheel", "--wheel-dir", str(pasta), *_so_antes_de(corte), *alvo)
    if rc != 0:
        raise EtapaFalhouError(ultima or "o pip não montou as rodas")


def _roda_de_um(pasta: Path, pedido: str, corte: float | None = None) -> str:
    """A roda de um pacote só: com o build isolado, e senão com as ferramentas de build do próprio
    ambiente (o setuptools que já está nele); com ``corte``, o pip só vê o que saiu antes. Vazio
    se montou; o porquê senão."""
    antes = _so_antes_de(corte)
    rc, ultima = _pip("wheel", "--no-deps", *antes, "--wheel-dir", str(pasta), pedido)
    if rc == 0:
        return ""
    rc, ultima = _pip("wheel", "--no-deps", "--no-build-isolation", *antes, "--wheel-dir",
                      str(pasta), pedido)
    return "" if rc == 0 else (ultima or f"o pip não montou {pedido}")


ARQUIVO_DAS_QUE_NAO_MONTAM = "python-sem-roda.json"


def _as_que_nao_montam() -> dict[str, Any]:
    try:
        dado = json.loads((_cache() / ARQUIVO_DAS_QUE_NAO_MONTAM).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return dado if isinstance(dado, dict) else {}


def _anotar_as_que_nao_montam(falhas: dict[str, tuple[str, str]]) -> None:
    dado = {**_as_que_nao_montam(),
            **{n: {"nova": v, "motivo": m} for n, (v, m) in falhas.items()}}
    with contextlib.suppress(OSError):
        (_cache() / ARQUIVO_DAS_QUE_NAO_MONTAM).write_text(
            json.dumps(dado, ensure_ascii=False), encoding="utf-8")


ARQUIVO_DAS_PROVADAS = "python-provado.txt"


def _anotar_as_que_provou() -> None:
    """Grava as versões das bibliotecas do produto que acabaram de provar que o Hefesto sobe, como
    piso de trava do pip (``nome>=versão``): o install as lê como ``-c`` e nunca rebaixa o que se
    provou, e a árvore nova que pedir mais que a versão provada ainda instala."""
    linhas = [f"{nome}>={versao}" for nome, versao in sorted(_rodas_de_agora().items())]
    if linhas:
        with contextlib.suppress(OSError):
            (_cache() / ARQUIVO_DAS_PROVADAS).write_text("\n".join(linhas) + "\n",
                                                          encoding="utf-8")


def _instalar_rodas(pasta: Path, alvo: Sequence[str]) -> tuple[int, str]:
    return _pip("install", "--no-index", "--only-binary", ":all:", "--find-links", str(pasta),
                *alvo)


def _o_produto_sobe() -> str:
    """Um processo novo importa o serviço e a linha de comando: vazio se sobe, senão o porquê."""
    rc, ultima = _comando([sys.executable, "-c", PROVA_DO_PRODUTO], teto_s=TETO_DA_PERGUNTA_S)
    return "" if rc == 0 else (ultima or f"o Hefesto não importou ({rc})")


def _baixar_o_python(passo: Passo, dados: dict[str, Any]) -> dict[str, Any]:
    """As rodas das versões novas e das de agora. Se o conjunto não monta, cada pacote se monta
    sozinho; o que não monta (nem a nova nem a de agora, para voltar) fica na versão de agora e
    não se oferece de novo nessa versão. A subida automática leva o corte da quarentena."""
    corte = _corte(dados)
    atrasadas = _atrasadas(corte)
    if not atrasadas:
        raise NadaAFazerError("")
    pasta = _pasta_do_python()
    shutil.rmtree(pasta, ignore_errors=True)
    (pasta / "antes").mkdir(parents=True)
    try:
        _rodas(pasta, [f"{n}=={u}" for n, (_v, u) in sorted(atrasadas.items())], corte)
        passo.fracao(0.5)
        _rodas(pasta / "antes", [f"{n}=={v}" for n, (v, _u) in sorted(atrasadas.items())],
               corte)
    except EtapaFalhouError:
        falhas: dict[str, tuple[str, str]] = {}
        for nome, (velha, nova) in sorted(atrasadas.items()):
            motivo = _roda_de_um(pasta, f"{nome}=={nova}", corte) or _roda_de_um(
                pasta / "antes", f"{nome}=={velha}", corte)
            if motivo:
                falhas[nome] = (nova, motivo)
        if len(falhas) == len(atrasadas):
            raise EtapaFalhouError(next(iter(falhas.values()))[1]) from None
        _anotar_as_que_nao_montam(falhas)
        for nome in falhas:
            _anotar(f"python: {nome} {atrasadas.pop(nome)[1]} fica na de agora "
                    f"({falhas[nome][1]})")
    passo.fracao(1.0)
    return {"pacotes": {n: [v, u] for n, (v, u) in atrasadas.items()}}


def _voltar_as_de_antes(pacotes: dict[str, Any],
                        corte: float | None = None) -> tuple[int, str]:
    alvo = [f"{n}=={v}" for n, (v, _u) in sorted(pacotes.items())]
    antes = _pasta_do_python() / "antes"
    if antes.is_dir():
        return _instalar_rodas(antes, alvo)
    return _pip("install", *_so_antes_de(corte), *alvo)


def _a_volta(pacotes: dict[str, Any], corte: float | None = None) -> str:
    """Volta às rodas de antes e confere que o produto sobe: a frase do que se viu."""
    rc, ultima = _voltar_as_de_antes(pacotes, corte)
    if rc != 0:
        return f"e não voltou: {ultima}"
    motivo = _o_produto_sobe()
    return "voltou às versões de antes" if not motivo else \
        f"voltou às versões de antes, e o Hefesto não sobe com as de antes ({motivo})"


def _canonico(nome: str) -> str:
    return re.sub(r"[-_.]+", "-", nome).lower()


def _instalar_o_python(passo: Passo, dados: dict[str, Any]) -> None:
    """As rodas novas ficam prontas no cache, uma por biblioteca; a troca na venv é a da fila,
    logo antes do reinício (:func:`_trocar_o_python`)."""
    prontas = {(_canonico(r.name.split("-")[0]), r.name.split("-")[1])
               for r in _pasta_do_python().glob("*.whl") if r.name.count("-") >= 2}
    for nome, (_v, nova) in sorted((dados.get("pacotes") or {}).items()):
        if (_canonico(nome), str(nova)) not in prontas:
            raise EtapaFalhouError(f"a roda de {nome} {nova} não ficou pronta")
    passo.fracao(1.0)


def _trocar_o_python(dados: dict[str, Any]) -> None:
    """A troca das rodas na venv, logo antes do reinício do serviço: o pip que falha no meio e o
    produto que não sobe voltam às de antes, e a volta também se prova."""
    pacotes, corte = dados.get("pacotes") or {}, _corte(dados)
    if not pacotes:
        return
    alvo = [f"{n}=={u}" for n, (_v, u) in sorted(pacotes.items())]
    rc, ultima = _instalar_rodas(_pasta_do_python(), alvo)
    if rc != 0:
        raise EtapaFalhouError(f"o pip não instalou ({ultima or rc}); {_a_volta(pacotes, corte)}")
    motivo = _o_produto_sobe()
    if motivo:
        raise EtapaFalhouError(f"o Hefesto não sobe com as versões novas ({motivo}); "
                               f"{_a_volta(pacotes, corte)}")
    _anotar_as_que_provou()


def _rodas_de_agora() -> dict[str, str]:
    from importlib import metadata

    saida = {}
    for nome in _dependencias_do_produto():
        with contextlib.suppress(metadata.PackageNotFoundError):
            saida[nome] = metadata.version(nome)
    return saida


def _pasta_da_reinstalacao_do_python() -> Path:
    return _cache() / "python-de-agora"


def _baixar_de_novo_o_python(passo: Passo, _dados_: dict[str, Any]) -> dict[str, Any]:
    rodas = _rodas_de_agora()
    if not rodas:
        raise EtapaFalhouError("as bibliotecas do Hefesto não estão instaladas")
    pasta = _pasta_da_reinstalacao_do_python()
    shutil.rmtree(pasta, ignore_errors=True)
    pasta.mkdir(parents=True)
    _rodas(pasta, [f"{n}=={v}" for n, v in sorted(rodas.items())])
    passo.fracao(1.0)
    return {"rodas": rodas}


def _reinstalar_o_python(passo: Passo, dados: dict[str, Any]) -> None:
    rodas = dados.get("rodas") or {}
    if not rodas:
        raise EtapaFalhouError("as rodas de agora não vieram")
    rc, ultima = _pip("install", "--no-index", "--only-binary", ":all:", "--force-reinstall",
                      "--no-deps", "--find-links", str(_pasta_da_reinstalacao_do_python()),
                      *(f"{n}=={v}" for n, v in sorted(rodas.items())))
    if rc != 0:
        raise EtapaFalhouError(ultima or "o pip não reinstalou")
    passo.fracao(0.8)
    motivo = _o_produto_sobe()
    if motivo:
        raise EtapaFalhouError(f"o Hefesto não sobe depois da reinstalação ({motivo})")
    passo.fracao(1.0)


def _voltar_o_python(anterior: dict[str, Any]) -> None:
    """Volta às rodas de antes, prova que o produto sobe e reinicia o serviço; a versão recusada
    de cada biblioteca não se oferece de novo (a seguinte, sim)."""
    from hefesto_dualsense4unix.app.actions.atualizador import _reiniciar_o_servico

    pacotes = (anterior.get("dados") or {}).get("pacotes") or {}
    if not pacotes:
        raise EtapaFalhouError("sem versão anterior")
    rc, ultima = _voltar_as_de_antes(pacotes)
    if rc != 0:
        raise EtapaFalhouError(ultima or "o pip não voltou")
    _anotar_as_que_nao_montam({n: (str(u), "voltou a pedido") for n, (_v, u) in pacotes.items()})
    motivo = _o_produto_sobe()
    if motivo:
        raise EtapaFalhouError(f"voltou, e o Hefesto não sobe ({motivo})")
    _anotar_as_que_provou()
    if not _reiniciar_o_servico():
        _anotar("python: voltou, e o serviço não reiniciou")


def _versao_do_pyproject(texto: str) -> str:
    achado = re.search(r'^version\s*=\s*"([^"]+)"', texto, re.MULTILINE)
    return achado.group(1) if achado else ""


def _vao() -> Any:
    from hefesto_dualsense4unix.app.actions import versao_ao_abrir as vao

    return vao


def _versoes_do_hefesto_sem_clone(rede: bool, forma: str) -> Versoes:
    """Sem clone, a última release publicada diz a versão nova, e o gesto da forma de instalação
    diz como instalá-la; o Hefesto não a sobe."""
    from importlib import metadata

    instalada = ""
    with contextlib.suppress(OSError):
        instalada = _versao_do_pyproject(
            (RAIZ_DO_REPOSITORIO / "pyproject.toml").read_text(encoding="utf-8"))
    with contextlib.suppress(metadata.PackageNotFoundError):
        instalada = metadata.version(PACOTE_DO_PRODUTO)
    if not rede:
        return Versoes(instalada, None)
    release = _release(REPO_DO_PRODUTO)
    versoes = Versoes(instalada, _sem_v(str(release.get("tag_name", ""))) or None,
                      publicada_em=publicada_em(release))
    if not versoes.tem_nova():
        return versoes
    return dataclasses.replace(versoes, gesto=repo_files.gesto_de_subir_a_versao_nova(forma))


def versoes_do_hefesto(rede: bool) -> Versoes:
    vao = _vao()
    raiz = RAIZ_DO_REPOSITORIO
    forma = repo_files.forma_da_instalacao(raiz)
    if forma != repo_files.FORMA_CLONE:
        return _versoes_do_hefesto_sem_clone(rede, forma)
    instalada = ""
    with contextlib.suppress(OSError):
        instalada = _versao_do_pyproject((raiz / "pyproject.toml").read_text(encoding="utf-8"))
    if not rede:
        return Versoes(instalada, None)
    return _o_que_a_baixada_conferiu(vao, raiz, instalada)


def _o_que_a_baixada_conferiu(vao: Any, raiz: Path, instalada: str) -> Versoes:
    """A peça Hefesto lê o que a última baixada conferiu, não o ``FETCH_HEAD``, que é o último
    ``fetch`` de qualquer um: sem baixada deste ``HEAD`` a peça não sabe (``publicada=None``)."""
    baixa = vao.ler_a_baixa()
    topo = vao._git(raiz, "rev-parse", "HEAD") or ""
    commit, veredito = str(baixa.get("commit") or ""), baixa.get("veredito")
    if veredito == vao.AVANCA and commit and commit == topo:
        return Versoes(instalada, instalada)
    if not baixa or baixa.get("topo") != topo:
        return Versoes(instalada, None)
    if veredito == vao.ATUAL:
        return Versoes(instalada, instalada)
    if veredito == vao.AVANCA:
        nova = _versao_do_pyproject(vao._git(raiz, "show", f"{commit}:pyproject.toml") or "")
        if not nova or nova == instalada:
            nova = f"{instalada}+{commit[:7]}"
        return Versoes(instalada, nova, nova=True)
    frase = vao.frase_da_baixa(baixa)
    if frase:
        return Versoes(instalada, None, revisar=frase)
    return Versoes(instalada, None, dica=str(baixa.get("motivo") or ""))


def _o_hefesto_pode(motivo: str) -> None:
    """O voo, o jogo aberto e o install em curso passam: a peça espera; o resto é falha."""
    vao = _vao()
    if not motivo:
        return
    if motivo in vao.ESPERAS:
        raise EsperaError(motivo, lambda: _por_que_o_hefesto_espera() not in vao.ESPERAS)
    raise EtapaFalhouError(motivo)


def _por_que_o_hefesto_espera() -> str:
    vao = _vao()
    return vao.por_que_nao(RAIZ_DO_REPOSITORIO) or (
        vao.INSTALL_EM_CURSO if vao._install_em_curso() else "")


def _baixar_o_hefesto(passo: Passo, _dados_: dict[str, Any]) -> dict[str, Any]:
    vao = _vao()
    raiz = RAIZ_DO_REPOSITORIO
    _o_hefesto_pode(vao.por_que_nao(raiz))
    alvo = vao.baixar(raiz)
    if not alvo:
        raise EtapaFalhouError("o remoto não trouxe versão nova")
    passo.fracao(1.0)
    return {"alvo": alvo}


def _instalar_o_hefesto(passo: Passo, dados: dict[str, Any]) -> dict[str, Any]:
    vao = _vao()
    pedidos: list[str] = []
    feito = vao.aplicar(RAIZ_DO_REPOSITORIO, str(dados.get("alvo", "")),
                        disparar=lambda _itens: pedidos.append("daemon"),
                        instalar=lambda _raiz_: pedidos.append("install"))
    if not feito:
        _o_hefesto_pode(_por_que_o_hefesto_espera())
        raise EtapaFalhouError("o avanço não coube")
    passo.fracao(1.0)
    return {"pedidos": pedidos}


def _aplicar_o_hefesto(passo: Passo, dados: dict[str, Any]) -> dict[str, Any]:
    vao = _vao()
    if "install" in (dados.get("pedidos") or []):
        vao._instalar(RAIZ_DO_REPOSITORIO, vao._rodar_o_install)
        motivo = vao._motivo_da_nota(vao._linhas_da_nota() or [])
        if motivo:
            raise EtapaFalhouError(motivo)
        passo.fracao(1.0)
        return {"reiniciou": True}
    passo.fracao(1.0)
    return {}


def _hefesto_sem_reinstalar(_versoes: Versoes) -> str:
    clone = repo_files.forma_da_instalacao(RAIZ_DO_REPOSITORIO) == repo_files.FORMA_CLONE
    return "" if clone else "instalação sem clone"


def _reinstalar_o_hefesto(passo: Passo, _dados_: dict[str, Any]) -> dict[str, Any]:
    vao = _vao()
    _o_hefesto_pode(_por_que_o_hefesto_espera())
    vao._instalar(RAIZ_DO_REPOSITORIO, vao._rodar_o_install)
    motivo = vao._motivo_da_nota(vao._linhas_da_nota() or [])
    if motivo:
        raise EtapaFalhouError(motivo)
    passo.fracao(1.0)
    return {"reiniciou": True}


INDICE_DO_BLUEZ = "https://www.kernel.org/pub/linux/bluetooth/"
API_DO_GITLAB = "https://gitlab.freedesktop.org/api/v4/projects/pipewire%2F{}/releases?per_page=40"
PRECISA_REVISAR = "a casa precisa revisar os patches"
PACOTE_DO_PORTAL = "xdg-desktop-portal-cosmic"
MARCA_DA_VERSAO_NO_PINO = "{versao}"
ARQUIVOS_DA_GDK = (
    ("xgameruntime.dll", "sha256", "url", ("x86_64-windows", "xgameruntime.dll")),
    ("gameinput.dll", "gameinput_sha256", "gameinput_url", ("nativa", "gameinput.dll")),
)


def _da_casa(versao: str) -> bool:
    return "~hefesto" in versao


def _curta(versao: str) -> str:
    achado = re.match(r"\d+(?:\.\d+)*", versao.split(":", 1)[-1])
    return achado.group(0) if achado else versao


def _dpkg_maior(a: str, b: str) -> bool:
    try:
        feito = subprocess.run(["dpkg", "--compare-versions", a, "gt", b], check=False,
                               capture_output=True, timeout=TETO_DA_PERGUNTA_S)
    except (OSError, subprocess.TimeoutExpired):
        return ordem(a) > ordem(b)
    return feito.returncode == 0


def ultima_do_bluez(indice: str) -> str | None:
    """A versão mais nova no índice do kernel.org, por partes (``5.9`` antes de ``5.10``)."""
    versoes = set(re.findall(r"bluez-(\d+\.\d+)\.tar\.xz", indice))
    return max(versoes, key=ordem) if versoes else None


def versoes_do_bluetooth(rede: bool) -> Versoes:
    instalada = _instalados("bluez").get("bluez", "")
    if not _da_casa(instalada):
        return Versoes(existe=False)
    curta = _curta(instalada)
    if not rede:
        return Versoes(curta, None, completa=instalada)
    publicada = ultima_do_bluez(_ler(INDICE_DO_BLUEZ).decode("utf-8", "replace"))
    if publicada is None:
        return Versoes(curta, None, completa=instalada)
    nova = ordem(publicada) > ordem(curta)
    completa = f"{instalada} → {publicada}, com as correções da casa" if nova else instalada
    if nova and ordem(publicada)[:1] != ordem(curta)[:1]:
        return Versoes(curta, publicada, completa=completa,
                       revisar=f"o BlueZ {publicada} abre uma série nova: {PRECISA_REVISAR}")
    return Versoes(curta, publicada, completa=completa, nova=nova)


def _tags_do_gitlab(projeto: str) -> list[str]:
    lancamentos = json.loads(_ler(API_DO_GITLAB.format(projeto)).decode("utf-8"))
    tags = [str(item.get("tag_name", "")) for item in lancamentos
            if isinstance(item, dict)] if isinstance(lancamentos, list) else []
    return [tag for tag in tags if re.fullmatch(r"\d+\.\d+\.\d+", tag)]


def mesma_serie(tags: Sequence[str], atual: str) -> tuple[str, str | None]:
    """(a mais nova da série de ``atual``, a mais nova de uma série acima, se houver)."""
    serie = [tag for tag in tags if ordem(tag)[:2] == ordem(atual)[:2]]
    acima = [tag for tag in tags if ordem(tag)[:2] > ordem(atual)[:2]]
    return (max([*serie, atual], key=ordem), max(acima, key=ordem) if acima else None)


NOMES_DO_SOM = {"pipewire": "PipeWire", "wireplumber": "WirePlumber"}
SOMAS_REVISADAS_DO_SOM = RAIZ_DO_REPOSITORIO / "assets" / "pipewire-backport" / "SOMAS-REVISADAS"
REVISAR_A_VERSAO_NOVA = "a casa precisa revisar a versão nova"


def _revisadas_do_som() -> set[tuple[str, str]]:
    try:
        texto = SOMAS_REVISADAS_DO_SOM.read_text(encoding="utf-8")
    except OSError:
        return set()
    return {(partes[0], partes[1]) for partes in map(str.split, texto.splitlines())
            if len(partes) == 3}


def versoes_do_som(rede: bool) -> Versoes:
    instalados = _instalados("pipewire", "wireplumber")
    pw, wp = instalados.get("pipewire", ""), instalados.get("wireplumber", "")
    if not _da_casa(pw):
        return Versoes(existe=False)
    atuais = {"pipewire": _curta(pw), "wireplumber": _curta(wp) if _da_casa(wp) else ""}
    de = " · ".join(v for v in atuais.values() if v)
    completa = f"PipeWire {pw} · WirePlumber {wp or '—'}"
    if not rede:
        return Versoes(de, None, completa=completa)
    novas: dict[str, str] = {}
    series: list[str] = []
    for projeto, atual in atuais.items():
        if not atual:
            continue
        novas[projeto], acima = mesma_serie(_tags_do_gitlab(projeto), atual)
        if acima:
            series.append(f"{NOMES_DO_SOM[projeto]} {acima}")
    para = " · ".join(novas[p] for p in atuais if p in novas)
    nova = any(ordem(novas[p]) > ordem(atuais[p]) for p in novas)
    if nova:
        completa += " → " + " · ".join(f"{NOMES_DO_SOM[p]} {novas[p]}" for p in novas)
    if not nova and series:
        return Versoes(de, para, completa=completa,
                       revisar=f"{', '.join(series)} é série nova: {PRECISA_REVISAR}")
    revisadas = _revisadas_do_som()
    sem_soma = [f"{NOMES_DO_SOM[p]} {novas[p]}" for p in novas
                if ordem(novas[p]) > ordem(atuais[p]) and (p, novas[p]) not in revisadas]
    if sem_soma:
        return Versoes(de, para, completa=completa, nova=False,
                       revisar=f"{', '.join(sem_soma)} sem a soma que a casa revisou: "
                               f"{REVISAR_A_VERSAO_NOVA}")
    return Versoes(de, para, completa=completa, nova=nova)


def _base_do_portal(versao: str) -> str:
    return re.sub(r"\+0~hefesto.*$", "", versao)


def _portal_no_apt() -> str:
    texto = _saida(["apt-cache", "madison", PACOTE_DO_PORTAL]) or ""
    melhor = ""
    for linha in texto.splitlines():
        partes = [p.strip() for p in linha.split("|")]
        if len(partes) < 2 or _da_casa(partes[1]) or not partes[1]:
            continue
        if not melhor or _dpkg_maior(partes[1], melhor):
            melhor = partes[1]
    return melhor


def versoes_do_portal(rede: bool) -> Versoes:
    instalada = _instalados(PACOTE_DO_PORTAL).get(PACOTE_DO_PORTAL, "")
    if not _da_casa(instalada):
        return Versoes(existe=False)
    base = _base_do_portal(instalada)
    _atualizar_a_lista_do_apt(rede)
    no_apt = _portal_no_apt() if rede else ""
    if not no_apt:
        return Versoes(_curta(base), None, completa=instalada)
    nova = _dpkg_maior(no_apt, base)
    completa = f"{instalada} → {no_apt}, com a correção da casa" if nova else instalada
    return Versoes(_curta(base), _curta(no_apt) if nova else _curta(base),
                   completa=completa, nova=nova)


def _pino_da_gdk() -> dict[str, str]:
    from hefesto_dualsense4unix.integrations import receitas_de_ambiente as receitas

    try:
        texto = receitas.PINO_DA_PECA.read_text(encoding="utf-8")
    except OSError:
        return {}
    pino = {}
    for linha in texto.splitlines():
        chave, igual, valor = linha.partition("=")
        if igual and not chave.startswith("#"):
            pino[chave.strip()] = valor.strip()
    return pino


def _sha_do_arquivo(caminho: Path) -> str:
    try:
        return hashlib.sha256(caminho.read_bytes()).hexdigest()
    except OSError:
        return ""


def _pasta_da_gdk() -> Path:
    from hefesto_dualsense4unix.integrations import receitas_de_ambiente as receitas

    return receitas.pasta_da_peca()


def versoes_da_gdk(_rede: bool) -> Versoes:
    pino = _pino_da_gdk()
    pasta = _pasta_da_gdk()
    if not pino or not (pasta / "x86_64-windows" / "xgameruntime.dll").is_file():
        return Versoes(existe=False)
    nome = pino.get("name", "")
    curto = nome.rsplit("-", 1)[-1]
    instaladas = {arquivo: _sha_do_arquivo(pasta.joinpath(*destino))
                  for arquivo, _, _, destino in ARQUIVOS_DA_GDK}
    faltam = [arquivo for arquivo, chave, _, _ in ARQUIVOS_DA_GDK
              if instaladas[arquivo] != pino.get(chave, "")]
    gravada = ""
    with contextlib.suppress(OSError):
        gravada = (pasta / "versao.txt").read_text(encoding="utf-8").strip()
    de = curto if not faltam else (gravada.rsplit("-", 1)[-1] if gravada else "antiga")
    completa = " · ".join(f"{arquivo} {instaladas[arquivo][:12] or '—'}"
                          for arquivo, _, _, _ in ARQUIVOS_DA_GDK)
    if faltam:
        completa += f" → {nome}: " + " · ".join(
            f"{arquivo} {pino.get(chave, '')[:12]}" for arquivo, chave, _, _ in ARQUIVOS_DA_GDK)
    return Versoes(de, curto, completa=completa, nova=bool(faltam))


COMPILADOR_DA_GDK = "x86_64-w64-mingw32-gcc-posix"
REPO_DO_PRODUTO = "Hefesto-Team/hefesto-dualsense4unix"


def _compilar_a_gdk(pasta: Path, arquivo: str, sha: str) -> tuple[Path | None, str]:
    """A peça compilada aqui, se bate com o pino; senão, o porquê de não ter dado."""
    if not shutil.which(COMPILADOR_DA_GDK):
        return None, f"sem o {COMPILADOR_DA_GDK} para compilar aqui"
    construida = pasta / "construida"
    if not (construida / arquivo).is_file():
        shutil.rmtree(construida, ignore_errors=True)
        rc, ultima = _comando(["bash", str(RAIZ_DO_REPOSITORIO / "assets" / "gdk-runtime"
                                            / "construir.sh"), str(construida)])
        if rc != 0:
            return None, f"a compilação aqui parou ({ultima or rc})"
    feito = construida / arquivo
    soma = _sha_do_arquivo(feito)
    if soma != sha:
        return None, (f"o {arquivo} compilado aqui tem outro sha256 ({soma[:12]}, o pino diz "
                      f"{sha[:12]}): o compilador desta máquina não é o do pino")
    return feito, ""


def _ja_na_maquina(arquivo: str, sha: str, destino: tuple[str, ...]) -> Path | None:
    """Uma cópia que já bate com o pino: a instalada, a baixada antes ou a guardada."""
    cache = _cache() / "gdk"
    for caminho in (_pasta_da_gdk().joinpath(*destino), cache / "nova" / arquivo,
                    cache / "anterior" / arquivo):
        if caminho.is_file() and _sha_do_arquivo(caminho) == sha:
            return caminho
    return None


def _da_release_com_a_soma(arquivo: str, sha: str) -> str:
    """O endereço do ``arquivo`` em qualquer release publicada cuja soma é a do pino."""
    with contextlib.suppress(OSError, ValueError):
        lancamentos = json.loads(_ler(
            f"https://api.github.com/repos/{REPO_DO_PRODUTO}/releases?per_page=20"
        ).decode("utf-8"))
        for release in lancamentos if isinstance(lancamentos, list) else []:
            for ativo in (release.get("assets") or []) if isinstance(release, dict) else []:
                if isinstance(ativo, dict) and ativo.get("name") == arquivo \
                        and ativo.get("digest") == f"sha256:{sha}":
                    return str(ativo.get("browser_download_url", ""))
    return ""


def _baixar_a_gdk(passo: Passo, _dados_: dict[str, Any]) -> None:
    """Cada arquivo do pino, da cópia que já bate, do release da versão, de outro release com a
    mesma soma, ou compilado aqui; o porquê de cada caminho que não deu vai junto da falha."""
    pino = _pino_da_gdk()
    try:
        versao = _versao_do_pyproject(
            (RAIZ_DO_REPOSITORIO / "pyproject.toml").read_text(encoding="utf-8"))
    except OSError:
        versao = ""
    pasta = _cache() / "gdk"
    shutil.rmtree(pasta / "construida", ignore_errors=True)
    prontos: dict[str, Path] = {}
    for arquivo, chave_sha, chave_url, destino in ARQUIVOS_DA_GDK:
        sha = pino.get(chave_sha, "")
        if not re.fullmatch(r"[0-9a-f]{64}", sha):
            raise EtapaFalhouError(f"o pino da peça não traz o {chave_sha}")
        local = _ja_na_maquina(arquivo, sha, destino)
        if local is not None:
            prontos[arquivo] = local
            continue
        porques: list[str] = []
        da_versao = pino.get(chave_url, "").replace(MARCA_DA_VERSAO_NO_PINO, versao)
        for url in (da_versao, None):
            url = url if url is not None else _da_release_com_a_soma(arquivo, sha)
            if not url or (url == da_versao and porques):
                continue
            try:
                _baixar(url, pasta / "baixada" / arquivo, passo, sha)
            except EtapaFalhouError as erro:
                porques.append(str(erro))
                continue
            prontos[arquivo] = pasta / "baixada" / arquivo
            break
        else:
            compilada, porque = _compilar_a_gdk(pasta, arquivo, sha)
            if compilada is None:
                raise EtapaFalhouError("; ".join([*porques, porque]))
            prontos[arquivo] = compilada
    nova = pasta / "nova"
    for arquivo, origem in prontos.items():
        if origem != nova / arquivo:
            nova.mkdir(parents=True, exist_ok=True)
            temporario = nova / f".{arquivo}.hefesto"
            shutil.copy2(origem, temporario)
            temporario.replace(nova / arquivo)
    shutil.rmtree(pasta / "baixada", ignore_errors=True)
    passo.fracao(1.0)


def _por_no_lugar(origem: Path, destino: Path) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = destino.with_name(f".{destino.name}.hefesto")
    shutil.copy2(origem, temporario)
    temporario.chmod(0o644)
    temporario.replace(destino)


def _instalar_a_gdk(passo: Passo, _dados_: dict[str, Any]) -> dict[str, Any]:
    pino = _pino_da_gdk()
    cache = _cache() / "gdk"
    pasta = _pasta_da_gdk()
    for arquivo, chave, _, _ in ARQUIVOS_DA_GDK:
        if _sha_do_arquivo(cache / "nova" / arquivo) != pino.get(chave, ""):
            raise EtapaFalhouError(f"o {arquivo} baixado não é o do pino")
    shutil.rmtree(cache / "anterior", ignore_errors=True)
    guardadas = []
    for arquivo, _, _, destino in ARQUIVOS_DA_GDK:
        if pasta.joinpath(*destino).is_file():
            (cache / "anterior").mkdir(parents=True, exist_ok=True)
            shutil.copy2(pasta.joinpath(*destino), cache / "anterior" / arquivo)
            guardadas.append(arquivo)
    for arquivo, _, _, destino in ARQUIVOS_DA_GDK:
        _por_no_lugar(cache / "nova" / arquivo, pasta.joinpath(*destino))
    (pasta / "versao.txt").write_text(pino.get("name", "") + "\n", encoding="utf-8")
    passo.fracao(1.0)
    return {"guardadas": guardadas}


def _reinstalar_a_gdk(passo: Passo, _dados_: dict[str, Any]) -> None:
    pino = _pino_da_gdk()
    cache = _cache() / "gdk"
    pasta = _pasta_da_gdk()
    for arquivo, chave, _, _ in ARQUIVOS_DA_GDK:
        if _sha_do_arquivo(cache / "nova" / arquivo) != pino.get(chave, ""):
            raise EtapaFalhouError(f"o {arquivo} baixado não é o do pino")
    for arquivo, _, _, destino in ARQUIVOS_DA_GDK:
        _por_no_lugar(cache / "nova" / arquivo, pasta.joinpath(*destino))
    passo.fracao(1.0)


def _voltar_a_gdk(anterior: dict[str, Any]) -> None:
    cache = _cache() / "gdk" / "anterior"
    pasta = _pasta_da_gdk()
    guardadas = set(anterior.get("guardadas") or [])
    for arquivo, _, _, destino in ARQUIVOS_DA_GDK:
        if arquivo in guardadas and (cache / arquivo).is_file():
            _por_no_lugar(cache / arquivo, pasta.joinpath(*destino))
    (pasta / "versao.txt").unlink(missing_ok=True)


def _etapas_da_casa(
        backport: str) -> tuple[Etapa, Etapa, None, Callable[[dict[str, Any]], None]]:
    def construir(passo: Passo, _dados_: dict[str, Any]) -> None:
        try:
            _raiz("backport-construir", backport, passo=passo)
        except RaizSaiuError as erro:
            if erro.codigo == RC_NADA_A_CONSTRUIR:
                raise NadaAFazerError(str(erro)) from None
            raise
        passo.fracao(1.0)

    def instalar(passo: Passo, _dados_: dict[str, Any]) -> dict[str, Any]:
        _raiz("backport-instalar", backport, passo=passo)
        passo.fracao(1.0)
        return {"backport": backport}

    def voltar(_anterior: dict[str, Any]) -> None:
        _raiz("backport-voltar", backport)

    return construir, instalar, None, voltar


def _reinstalacao_da_casa(backport: str) -> Reinstalacao:
    return Reinstalacao(
        None, _do_ajudante("backport-reinstalar", backport), None,
        lambda _versoes: _pergunta_da_raiz("backport-reinstalavel", backport))


def _reinstalacao_do_apt(grupo: str, aplicar: Etapa | None) -> Reinstalacao:
    return Reinstalacao(_do_ajudante("apt-baixar-de-novo", grupo),
                        _do_ajudante("apt-reinstalar", grupo), aplicar)


def registro() -> list[Peca]:
    """As peças, na ordem da fila: o kernel antes dos módulos, o repositório por último."""
    return [
        Peca("bluetooth", "Bluetooth", "BlueZ, com as correções do Hefesto",
             "O serviço do Bluetooth", versoes_do_bluetooth,
             *_etapas_da_casa("bluez"), reinstalacao=_reinstalacao_da_casa("bluez")),
        Peca("som", "Som", "PipeWire e WirePlumber", "No próximo início da sessão",
             versoes_do_som, *_etapas_da_casa("pipewire"),
             reinstalacao=_reinstalacao_da_casa("pipewire")),
        Peca("portal", "Portal do COSMIC", "A captura de tela do COSMIC, com a correção do Hefesto",
             "No próximo início da sessão", versoes_do_portal, *_etapas_da_casa("portal"),
             reinstalacao=_reinstalacao_da_casa("portal")),
        Peca("gdk", "GameInput", "A peça GDK e o GameInput dos jogos do Xbox no PC",
             "Os jogos com a peça", versoes_da_gdk, _baixar_a_gdk, _instalar_a_gdk, None,
             _voltar_a_gdk, reinstalacao=Reinstalacao(_baixar_a_gdk, _reinstalar_a_gdk)),
        Peca("python", "Python", "As bibliotecas do Hefesto", "O serviço e a janela",
             versoes_do_python, _baixar_o_python, _instalar_o_python, None, _voltar_o_python,
             reinstalacao=Reinstalacao(_baixar_de_novo_o_python, _reinstalar_o_python),
             trocar=_trocar_o_python),
        Peca("nvidia", "Driver Nvidia", "O driver da placa de vídeo", "No próximo início",
             versoes_da_nvidia, _do_apt("nvidia", "baixar"), _do_apt("nvidia", "instalar"),
             _limpar, reinstalacao=_reinstalacao_do_apt("nvidia", None)),
        Peca("kernel", "Kernel", "O kernel do sistema", "No próximo início",
             versoes_do_kernel, _do_apt("kernel", "baixar"), _instalar_o_kernel,
             _aplicar_o_kernel, _voltar_o_kernel,
             reinstalacao=_reinstalacao_do_apt("kernel", _refazer_o_dkms)),
        Peca("dkms", "Módulos do kernel", "Os módulos do Hefesto", "Os kernels instalados",
             versoes_do_dkms, None, _refazer_o_dkms, None,
             reinstalacao=Reinstalacao(None, _do_ajudante("dkms-reinstalar"))),
        Peca("sistema", "Pacotes do sistema", "Os pacotes da distribuição", "O sistema",
             versoes_do_sistema, _do_apt("sistema", "baixar"), _do_apt("sistema", "instalar"),
             _limpar, reinstalacao=Reinstalacao(None, _do_ajudante("apt-consertar"))),
        Peca("mangohud", "MangoHud", "O painel por cima do jogo", "Todos os jogos",
             versoes_do_mangohud, _baixar_o_mangohud, _instalar_o_mangohud, None,
             _voltar_o_mangohud,
             reinstalacao=Reinstalacao(None, _do_ajudante("mangohud-reinstalar"), None,
                                       _mangohud_sem_reinstalar)),
        Peca("umu", "umu", "Os jogos de fora da Steam no Proton", "Os jogos de fora da Steam",
             versoes_do_umu, _baixar_o_umu, _instalar_o_umu, _aplicar_o_umu, _voltar_o_umu,
             reinstalacao=Reinstalacao(_baixar_de_novo_o_umu, _instalar_o_umu, _reapontar_o_umu,
                                       _umu_sem_reinstalar)),
        Peca("proton", "GE-Proton", "Os jogos da Steam e do Heroic",
             "Todos os jogos da Steam e do Heroic", versoes_do_proton,
             _baixar_o_proton, _instalar_o_proton, _aplicar_o_proton, _voltar_o_proton,
             reinstalacao=Reinstalacao(_baixar_de_novo_o_proton, _reinstalar_o_proton,
                                       _aplicar_o_proton, _proton_sem_reinstalar),
             anterior=_anterior_do_proton, steam_fechada=True),
        Peca("hefesto", "Hefesto", "Interface, serviço e correções", "O serviço e a janela",
             versoes_do_hefesto, _baixar_o_hefesto, _instalar_o_hefesto, _aplicar_o_hefesto,
             grupo="hefesto", steam_fechada=True,
             reinstalacao=Reinstalacao(None, _reinstalar_o_hefesto, None,
                                       _hefesto_sem_reinstalar)),
    ]

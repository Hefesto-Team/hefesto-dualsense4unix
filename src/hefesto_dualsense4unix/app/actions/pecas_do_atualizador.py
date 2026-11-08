"""As peças do atualizador: de onde cada uma lê a versão, e como baixa, instala e aplica.

O que pede root passa pelo ajudante que o install põe em ``AJUDANTE``, por ``sudo -n``, com um
verbo de lista fechada e nenhum argumento livre; sem a regra no sudoers, a etapa falha com o
porquê, e nada pede senha. O que é de quem usa (o Proton, o umu, as bibliotecas do Python e o
repositório) roda como quem usa.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.request
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from hefesto_dualsense4unix.app.actions.atualizador import (
    EtapaFalhouError,
    Passo,
    Peca,
    Versoes,
    _anotar,
)

AJUDANTE = Path("/usr/local/lib/hefesto-dualsense4unix/atualizador-raiz")
RAIZ_DO_REPOSITORIO = Path(__file__).resolve().parents[4]
API_DO_GITHUB = "https://api.github.com/repos/{}/releases/latest"
REPO_DO_MANGOHUD = "flightlessmango/MangoHud"
REPO_DO_UMU = "Open-Wine-Components/umu-launcher"
PRAZO_DA_REDE_S = 30
TETO_DO_COMANDO_S = 3 * 3600.0
TETO_DA_PERGUNTA_S = 60.0
VALIDADE_DA_LISTA_DO_APT_S = 600.0
PACOTE_DO_PRODUTO = "hefesto-dualsense4unix"
GRUPO_NVIDIA = re.compile(r"^(?:nvidia-|libnvidia-|xserver-xorg-video-nvidia)")
GRUPO_KERNEL = re.compile(r"^linux-(?:system76|generic|image-|headers-|modules-|signed-)")
METAS_DO_KERNEL = ("linux-system76", "linux-generic", "linux-image-generic")
_STATUS_DO_APT = re.compile(r"^(?:dlstatus|pmstatus):[^:]*:(?P<pct>[0-9.]+):")

_apt_lido_em: list[float] = []


def _comando(argv: Sequence[str], *, linha: Callable[[str], None] | None = None,
             env: dict[str, str] | None = None,
             teto_s: float = TETO_DO_COMANDO_S) -> tuple[int, str]:
    """Roda ``argv`` sem terminal, linha a linha. Devolve o código e a última linha não vazia."""
    try:
        processo = subprocess.Popen(
            list(argv), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, env=env, start_new_session=True)
    except OSError as erro:
        return 127, erro.strerror or str(erro)
    ultima = ""
    inicio = time.monotonic()
    assert processo.stdout is not None
    for texto in processo.stdout:
        texto = texto.rstrip("\n")
        if texto.strip():
            ultima = texto.strip()
        if linha is not None:
            linha(texto)
        if time.monotonic() - inicio > teto_s:
            processo.kill()
            return 124, f"passou de {teto_s / 60:.0f} minutos"
    return processo.wait(), ultima


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


def _raiz(acao: str, *args: str, passo: Passo | None = None) -> None:
    """O ajudante root, sem senha: falha com o porquê se a regra do install não está lá."""
    if not AJUDANTE.is_file():
        raise EtapaFalhouError("o ajudante do install não está instalado: rode o install")

    def linha(texto: str) -> None:
        achado = _STATUS_DO_APT.match(texto)
        if achado and passo is not None:
            with contextlib.suppress(ValueError):
                passo.fracao(float(achado.group("pct")) / 100.0)

    rc, ultima = _comando(["sudo", "-n", str(AJUDANTE), acao, *args], linha=linha)
    if rc != 0:
        raise EtapaFalhouError(ultima or f"{acao} saiu com {rc}")


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
    """``apt list --upgradable``: pacote -> (instalada, candidata). Sem root."""
    texto = _saida(["apt", "list", "--upgradable"])
    saida: dict[str, tuple[str, str]] = {}
    for linha in (texto or "").splitlines():
        achado = re.match(r"^(?P<p>[^/\s]+)/\S+\s+(?P<nova>\S+)\s+\S+\s+"
                          r"\[[^:\]]*:\s*(?P<velha>[^\]\s]+)\]", linha)
        if achado:
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
        _raiz("apt-baixar", grupo, passo=passo)

    def instalar(passo: Passo, _dados_: dict[str, Any]) -> None:
        _raiz("apt-instalar", grupo, passo=passo)

    return baixar if nome == "baixar" else instalar


def _limpar(passo: Passo, _dados_: dict[str, Any]) -> None:
    _raiz("apt-limpar", passo=passo)
    passo.fracao(1.0)


def versoes_da_nvidia(rede: bool) -> Versoes:
    _atualizar_a_lista_do_apt(rede)
    drivers = {p: v for p, v in _instalados("nvidia-driver-*").items()
               if p.startswith("nvidia-driver-")}
    if not drivers:
        return Versoes(existe=False)
    pacote, versao = sorted(drivers.items())[0]
    novas = {p: n for p, (_v, n) in _atualizaveis().items() if GRUPO_NVIDIA.match(p)}
    candidata = novas.get(pacote, versao)
    return Versoes(_a_montante(versao), _a_montante(candidata) if rede or novas else None,
                   dica=pacote, nova=bool(novas))


def _kernel_do_pacote(versao: str) -> str:
    achado = re.match(r"^(\d+\.\d+(?:\.\d+)?-\d+)", versao.split(":", 1)[-1])
    return achado.group(1) if achado else ""


def versoes_do_kernel(rede: bool) -> Versoes:
    _atualizar_a_lista_do_apt(rede)
    rodando = os.uname().release
    agora = _kernel_do_pacote(rodando) or rodando
    novas = {p: n for p, (_v, n) in _atualizaveis().items() if GRUPO_KERNEL.match(p)}
    meta = next((novas[m] for m in METAS_DO_KERNEL if m in novas), "")
    candidata = _kernel_do_pacote(meta) if meta else agora
    metas = _instalados(*METAS_DO_KERNEL)
    dica = next(iter(metas), "") or rodando
    return Versoes(agora.split("-", 1)[0], candidata.split("-", 1)[0], dica=dica,
                   nova=bool(novas))


def _pacotes(n: int) -> str:
    return f"{n} pacote{'s' if n != 1 else ''}"


def _versao_da_distro() -> str:
    with contextlib.suppress(OSError):
        for linha in Path("/etc/os-release").read_text(encoding="utf-8").splitlines():
            if linha.startswith("VERSION_ID="):
                return linha.split("=", 1)[1].strip().strip('"')
    return ""


def _nome_da_distro() -> str:
    with contextlib.suppress(OSError):
        for linha in Path("/etc/os-release").read_text(encoding="utf-8").splitlines():
            if linha.startswith("PRETTY_NAME="):
                return linha.split("=", 1)[1].strip().strip('"')
    return ""


def versoes_do_sistema(rede: bool) -> Versoes:
    _atualizar_a_lista_do_apt(rede)
    if shutil.which("apt-get") is None:
        return Versoes(existe=False)
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
    return Versoes(_curto_do_ge(vale), _curto_do_ge(nome),
                   nova=qp.ordem_da_versao(nome) > qp.ordem_da_versao(vale))


def _baixar_o_proton(passo: Passo, _dados_: dict[str, Any]) -> None:
    pp = _proton()
    feito = pp.baixar_a_ultima_do_ge(
        pp.default_cache_dir(), forcar=True,
        baixar=lambda url, destino: _baixar(url, destino, passo))
    if feito.estado not in ("baixada", "em_cache"):
        raise EtapaFalhouError(feito.detalhe or feito.estado)


def _instalar_o_proton(passo: Passo, _dados_: dict[str, Any]) -> dict[str, Any]:
    pp = _proton()
    conf = pp._load_conf(None)
    compat, cache = pp.default_compat_dir(), pp.default_cache_dir()
    antes = pp.pino_que_vale(conf, compat)
    tarball = cache / f"{antes}.tar.gz"
    sha = ""
    with contextlib.suppress(OSError):
        sha = pp.sha256_of_file(tarball) if tarball.is_file() else ""
    feito = pp.instalar_a_ultima_do_cache(conf, compat_dir=compat, cache_dir=cache)
    if feito.estado not in ("instalada", "em_dia"):
        raise EtapaFalhouError(feito.detalhe or feito.estado)
    passo.fracao(1.0)
    return {"anterior": antes, "sha256": sha, "nova": feito.versao}


def _aplicar_o_proton(passo: Passo, _dados_: dict[str, Any]) -> None:
    pp = _proton()
    from hefesto_dualsense4unix.integrations import censo_dos_lancadores as censo

    conf = pp._load_conf(None)
    jogos = len(pp.list_installed_appids())
    passo.contagem("Steam", 0, jogos)
    travado = pp.lock_proton_for_all_games(conf=conf, todos=True)
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


def _voltar_o_proton(anterior: dict[str, Any]) -> None:
    pp = _proton()
    dados = anterior.get("dados") or {}
    velha, sha, nova = str(dados.get("anterior", "")), str(dados.get("sha256", "")), \
        str(dados.get("nova", ""))
    if not velha or not nova:
        raise EtapaFalhouError("sem versão anterior")
    compat, cache = pp.default_compat_dir(), pp.default_cache_dir()
    if not pp.pinned_proton_installed(velha, compat):
        if not sha:
            raise EtapaFalhouError(f"{velha} não está no cache")
        pp.ensure_pinned_proton({"name": velha, "url": "", "sha256": sha}, compat_dir=compat,
                                cache_dir=cache, downloader=None)
        if not pp.pinned_proton_installed(velha, compat):
            raise EtapaFalhouError(f"{velha} não voltou do cache")
    pp.segurar(cache, nova)
    shutil.rmtree(compat / nova, ignore_errors=True)
    pp.lock_proton_for_all_games(conf=pp._load_conf(None), todos=True)
    pp.apontar_os_lancadores_para_o_pino(conf=pp._load_conf(None))


def versoes_do_mangohud(rede: bool) -> Versoes:
    texto = _saida(["mangohud", "--version"]) if shutil.which("mangohud") else None
    instalada = _sem_v((texto or "").strip().split()[0]) if (texto or "").strip() else ""
    if not rede:
        return Versoes(instalada, None)
    publicada = _sem_v(str(_release(REPO_DO_MANGOHUD).get("tag_name", "")))
    return Versoes(instalada, publicada or None)


def _pasta_do_mangohud() -> Path:
    return Path.home() / ".cache" / PACOTE_DO_PRODUTO / "atualizador" / "mangohud"


def _e_o_binario_do_mangohud(nome: str) -> bool:
    return nome.startswith("MangoHud-") and nome.endswith(".tar.gz") and "Source" not in nome


def _baixar_o_mangohud(passo: Passo, _dados_: dict[str, Any]) -> None:
    nome, url, sha = _ativo(_release(REPO_DO_MANGOHUD), _e_o_binario_do_mangohud)
    pasta = _pasta_do_mangohud()
    if pasta.is_dir():
        for velho in pasta.iterdir():
            if velho.name != nome:
                velho.unlink(missing_ok=True)
    _baixar(url, pasta / nome, passo, sha)


def _instalar_o_mangohud(passo: Passo, _dados_: dict[str, Any]) -> None:
    _raiz("mangohud-instalar", passo=passo)
    passo.fracao(1.0)


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
    publicada = _sem_v(str(_release(REPO_DO_UMU).get("tag_name", ""))) if rede else None
    if caminho is None or not nosso:
        return Versoes(instalada, publicada or (instalada if caminho else None), nova=False,
                       dica="" if caminho is None else str(caminho))
    return Versoes(instalada, publicada or None)


def _e_o_zipapp(nome: str) -> bool:
    return nome.startswith("umu-launcher-") and nome.endswith("-zipapp.tar")


def _baixar_o_umu(passo: Passo, _dados_: dict[str, Any]) -> dict[str, Any]:
    release = _release(REPO_DO_UMU)
    nome, url, sha = _ativo(release, _e_o_zipapp)
    destino = _cache() / "umu" / nome
    _baixar(url, destino, passo, sha)
    return {"tar": str(destino), "tag": _sem_v(str(release.get("tag_name", "")))}


def _extrair_sem_sair(tar: tarfile.TarFile, pasta: Path) -> None:
    for membro in tar.getmembers():
        alvo = (pasta / membro.name).resolve()
        if pasta.resolve() not in (alvo, *alvo.parents) or membro.issym() or membro.islnk():
            raise EtapaFalhouError(f"o pacote do umu traz um caminho de fora: {membro.name}")
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


def _atrasadas() -> dict[str, tuple[str, str]]:
    texto = _saida([sys.executable, "-m", "pip", "--disable-pip-version-check", "list",
                    "--outdated", "--format=json"])
    if texto is None:
        raise ValueError("o pip não respondeu")
    deps = set(_dependencias_do_produto())
    saida = {}
    for item in json.loads(texto or "[]"):
        nome = str(item.get("name", "")).lower().replace("_", "-")
        if nome in deps:
            saida[nome] = (str(item.get("version", "")), str(item.get("latest_version", "")))
    return saida


def versoes_do_python(rede: bool) -> Versoes:
    if not _no_venv():
        return Versoes(existe=False)
    if not rede:
        return Versoes("", None, rotulo="")
    atrasadas = _atrasadas()
    dica = " · ".join(f"{n} {v} → {u}" for n, (v, u) in sorted(atrasadas.items()))
    rotulo = _pacotes(len(atrasadas)) if atrasadas else ""
    return Versoes("", str(len(atrasadas)), rotulo=rotulo, dica=dica, nova=bool(atrasadas))


def _baixar_o_python(passo: Passo, _dados_: dict[str, Any]) -> dict[str, Any]:
    atrasadas = _atrasadas()
    if not atrasadas:
        return {"pacotes": {}}
    pasta = _cache() / "python"
    shutil.rmtree(pasta, ignore_errors=True)
    pasta.mkdir(parents=True)
    alvo = [f"{n}=={u}" for n, (_v, u) in sorted(atrasadas.items())]
    rc, ultima = _pip("download", "--dest", str(pasta), *alvo)
    if rc != 0:
        raise EtapaFalhouError(ultima or "o pip não baixou")
    passo.fracao(1.0)
    return {"pacotes": {n: [v, u] for n, (v, u) in atrasadas.items()}}


def _instalar_o_python(passo: Passo, dados: dict[str, Any]) -> None:
    pacotes = dados.get("pacotes") or {}
    if not pacotes:
        return
    alvo = [f"{n}=={u}" for n, (_v, u) in sorted(pacotes.items())]
    rc, ultima = _pip("install", "--no-index", "--find-links", str(_cache() / "python"), *alvo)
    if rc != 0:
        raise EtapaFalhouError(ultima or "o pip não instalou")
    passo.fracao(1.0)


def _voltar_o_python(anterior: dict[str, Any]) -> None:
    pacotes = (anterior.get("dados") or {}).get("pacotes") or {}
    if not pacotes:
        raise EtapaFalhouError("sem versão anterior")
    rc, ultima = _pip("install", *(f"{n}=={v}" for n, (v, _u) in sorted(pacotes.items())))
    if rc != 0:
        raise EtapaFalhouError(ultima or "o pip não voltou")


def _versao_do_pyproject(texto: str) -> str:
    achado = re.search(r'^version\s*=\s*"([^"]+)"', texto, re.MULTILINE)
    return achado.group(1) if achado else ""


def _vao() -> Any:
    from hefesto_dualsense4unix.app.actions import versao_ao_abrir as vao

    return vao


def versoes_do_hefesto(rede: bool) -> Versoes:
    vao = _vao()
    raiz = RAIZ_DO_REPOSITORIO
    instalada = ""
    with contextlib.suppress(OSError):
        instalada = _versao_do_pyproject((raiz / "pyproject.toml").read_text(encoding="utf-8"))
    if not (raiz / ".git").exists():
        from importlib import metadata

        with contextlib.suppress(metadata.PackageNotFoundError):
            instalada = metadata.version(PACOTE_DO_PRODUTO)
        return Versoes(instalada, None)
    topo = vao._git(raiz, "rev-parse", "HEAD")
    alvo = vao._git(raiz, "rev-parse", "--verify", "-q", "FETCH_HEAD^{commit}")
    if not topo or not alvo or alvo == topo or not vao._e_avanco(raiz, topo, alvo):
        return Versoes(instalada, instalada)
    nova = _versao_do_pyproject(vao._git(raiz, "show", f"{alvo}:pyproject.toml") or "")
    if not nova or nova == instalada:
        nova = f"{instalada}+{alvo[:7]}"
    return Versoes(instalada, nova, nova=True)


def _baixar_o_hefesto(passo: Passo, _dados_: dict[str, Any]) -> dict[str, Any]:
    vao = _vao()
    raiz = RAIZ_DO_REPOSITORIO
    motivo = vao.por_que_nao(raiz)
    if motivo:
        raise EtapaFalhouError(motivo)
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
        raise EtapaFalhouError(vao.por_que_nao(RAIZ_DO_REPOSITORIO) or "o avanço não coube")
    passo.fracao(1.0)
    return {"pedidos": pedidos}


def _aplicar_o_hefesto(passo: Passo, dados: dict[str, Any]) -> None:
    vao = _vao()
    if "install" in (dados.get("pedidos") or []):
        vao._instalar(RAIZ_DO_REPOSITORIO, vao._rodar_o_install)
        motivo = vao._motivo_da_nota(vao._linhas_da_nota() or [])
        if motivo:
            raise EtapaFalhouError(motivo)
    passo.fracao(1.0)


def versoes_do_bluetooth(_rede: bool) -> Versoes:
    texto = _saida(["bluetoothd", "--version"]) if shutil.which("bluetoothd") else None
    return Versoes((texto or "").strip(), None, existe=bool(texto))


def versoes_do_som(_rede: bool) -> Versoes:
    texto = _saida(["pipewire", "--version"]) if shutil.which("pipewire") else None
    achado = re.search(r"libpipewire\s+(\S+)\s*$", (texto or "").strip())
    return Versoes(achado.group(1) if achado else "", None, existe=achado is not None)


PACOTE_DO_PORTAL = "xdg-desktop-portal-cosmic"


def versoes_do_portal(_rede: bool) -> Versoes:
    versao = _instalados(PACOTE_DO_PORTAL).get(PACOTE_DO_PORTAL, "")
    return Versoes(_a_montante(versao), None, dica=versao, existe=bool(versao))


def versoes_da_gdk(_rede: bool) -> Versoes:
    from hefesto_dualsense4unix.integrations import receitas_de_ambiente as receitas

    if not receitas.peca_do_hefesto_instalada():
        return Versoes(existe=False)
    try:
        texto = receitas.PINO_DA_PECA.read_text(encoding="utf-8")
    except OSError:
        return Versoes(existe=False)
    achado = re.search(r"^name=(\S+)$", texto, re.MULTILINE)
    nome = achado.group(1) if achado else ""
    return Versoes(nome.rsplit("-", 1)[-1], None, dica=nome, existe=bool(nome))


def registro() -> list[Peca]:
    """As peças, na ordem da fila: o kernel antes dos módulos, o repositório por último."""
    return [
        Peca("proton", "GE-Proton", "Os jogos da Steam e do Heroic",
             "Todos os jogos da Steam e do Heroic", versoes_do_proton,
             _baixar_o_proton, _instalar_o_proton, _aplicar_o_proton, _voltar_o_proton),
        Peca("bluetooth", "Bluetooth", "BlueZ, com as correções do Hefesto",
             "O serviço do Bluetooth", versoes_do_bluetooth, volta=2),
        Peca("som", "Som", "PipeWire e WirePlumber", "O PipeWire e o WirePlumber da sessão",
             versoes_do_som, volta=2),
        Peca("portal", "Portal do COSMIC", "A captura de tela do COSMIC, com a correção do Hefesto",
             "A sessão", versoes_do_portal, volta=2),
        Peca("gdk", "GameInput", "A peça GDK e o GameInput dos jogos do Xbox no PC",
             "Os jogos com a peça", versoes_da_gdk, volta=2),
        Peca("python", "Python", "As bibliotecas do Hefesto", "O serviço e a janela",
             versoes_do_python, _baixar_o_python, _instalar_o_python, None, _voltar_o_python),
        Peca("nvidia", "Driver NVIDIA", "O driver da placa de vídeo", "No próximo início",
             versoes_da_nvidia, _do_apt("nvidia", "baixar"), _do_apt("nvidia", "instalar"),
             _limpar),
        Peca("kernel", "Kernel", "O kernel do sistema", "No próximo início",
             versoes_do_kernel, _do_apt("kernel", "baixar"), _instalar_o_kernel,
             _aplicar_o_kernel, _voltar_o_kernel),
        Peca("dkms", "Módulos do kernel", "Os módulos do Hefesto", "Os kernels instalados",
             versoes_do_dkms, None, _refazer_o_dkms, None),
        Peca("sistema", "Pacotes do sistema", "Os pacotes da distribuição", "O sistema",
             versoes_do_sistema, _do_apt("sistema", "baixar"), _do_apt("sistema", "instalar"),
             _limpar),
        Peca("mangohud", "MangoHud", "O painel por cima do jogo", "Todos os jogos",
             versoes_do_mangohud, _baixar_o_mangohud, _instalar_o_mangohud, None,
             _voltar_o_mangohud),
        Peca("umu", "umu", "Os jogos de fora da Steam no Proton", "Os jogos de fora da Steam",
             versoes_do_umu, _baixar_o_umu, _instalar_o_umu, _aplicar_o_umu, _voltar_o_umu),
        Peca("hefesto", "Hefesto", "Interface, serviço e correções", "O serviço e a janela",
             versoes_do_hefesto, _baixar_o_hefesto, _instalar_o_hefesto, _aplicar_o_hefesto,
             grupo="hefesto"),
    ]

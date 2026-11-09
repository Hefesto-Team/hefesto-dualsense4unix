"""As peças do atualizador: de onde cada uma lê a versão, e como baixa, instala e aplica.

O que pede root passa pelo ajudante que o install põe em ``AJUDANTE``, por ``sudo -n``, com um
verbo de lista fechada e nenhum argumento livre; sem a regra no sudoers, a etapa falha com o
porquê, e nada pede senha. O que é de quem usa (o Proton, o umu, as bibliotecas do Python e o
repositório) roda como quem usa.

A reinstalação refaz a versão que está na máquina pelo mesmo caminho da subida, com verbos
fechados no ajudante: o apt só com os pacotes e as versões que o próprio ajudante lê, e o
backport da casa só da entrega que ele mesmo instalou, conferida de novo.
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
    Etapa,
    EtapaFalhouError,
    Passo,
    Peca,
    Reinstalacao,
    Versoes,
    _anotar,
    ordem,
)

AJUDANTE = Path("/usr/local/lib/hefesto-dualsense4unix/atualizador-raiz")
RAIZ_DO_REPOSITORIO = Path(__file__).resolve().parents[4]
API_DO_GITHUB = "https://api.github.com/repos/{}/releases/latest"
API_DA_TAG = "https://api.github.com/repos/{}/releases/tags/{}"
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


def _raiz(acao: str, *args: str, passo: Passo | None = None,
          teto_s: float = TETO_DO_COMANDO_S) -> None:
    """O ajudante root, sem senha: falha com o porquê se a regra do install não está lá."""
    if not AJUDANTE.is_file():
        raise EtapaFalhouError("o ajudante do install não está instalado: rode o install")

    def linha(texto: str) -> None:
        achado = _STATUS_DO_APT.match(texto)
        if achado and passo is not None:
            with contextlib.suppress(ValueError):
                passo.fracao(float(achado.group("pct")) / 100.0)

    rc, ultima = _comando(["sudo", "-n", str(AJUDANTE), acao, *args], linha=linha, teto_s=teto_s)
    if rc != 0:
        raise EtapaFalhouError(ultima or f"{acao} saiu com {rc}")


def _pergunta_da_raiz(acao: str, *args: str) -> str:
    """O ajudante responde sem mexer em nada: vazio se sim, senão o porquê."""
    try:
        _raiz(acao, *args, teto_s=TETO_DA_PERGUNTA_S)
    except EtapaFalhouError as erro:
        texto = str(erro)
        if texto.startswith("sudo:"):
            return "a regra do sudo não traz a reinstalação: rode o install"
        return re.sub(r"^[\w.-]+: ", "", texto) or acao
    return ""


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
        raise EtapaFalhouError(pp._PORQUE_A_STEAM_BARRA.get(barra, barra))
    try:
        pp._extract_verified_tarball(tarball, conf["name"], pp.default_compat_dir())
    except (OSError, tarfile.TarError) as erro:
        raise EtapaFalhouError(f"o {conf['name']} não se refez: {erro}") from None
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


def _mangohud_sem_reinstalar(versoes: Versoes) -> str:
    if not versoes.instalada:
        return "o MangoHud não está instalado"
    if versoes.publicada != versoes.instalada:
        return "a reinstalação traz só a versão publicada, que não é a instalada"
    return ""


def _baixar_de_novo_o_mangohud(passo: Passo, dados: dict[str, Any]) -> None:
    texto = _saida(["mangohud", "--version"]) if shutil.which("mangohud") else None
    instalada = _sem_v((texto or "").strip().split()[0]) if (texto or "").strip() else ""
    publicada = _sem_v(str(_release(REPO_DO_MANGOHUD).get("tag_name", "")))
    if not instalada or publicada != instalada:
        raise EtapaFalhouError("a versão publicada não é a instalada: nada se reinstala")
    _baixar_o_mangohud(passo, dados)


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


def _rodas(pasta: Path, alvo: Sequence[str]) -> None:
    rc, ultima = _pip("wheel", "--wheel-dir", str(pasta), *alvo)
    if rc != 0:
        raise EtapaFalhouError(ultima or "o pip não montou as rodas")


def _instalar_rodas(pasta: Path, alvo: Sequence[str]) -> tuple[int, str]:
    return _pip("install", "--no-index", "--only-binary", ":all:", "--find-links", str(pasta),
                *alvo)


def _o_produto_sobe() -> str:
    """Um processo novo importa o serviço e a linha de comando: vazio se sobe, senão o porquê."""
    rc, ultima = _comando([sys.executable, "-c", PROVA_DO_PRODUTO], teto_s=TETO_DA_PERGUNTA_S)
    return "" if rc == 0 else (ultima or f"o Hefesto não importou ({rc})")


def _baixar_o_python(passo: Passo, _dados_: dict[str, Any]) -> dict[str, Any]:
    atrasadas = _atrasadas()
    if not atrasadas:
        return {"pacotes": {}}
    pasta = _pasta_do_python()
    shutil.rmtree(pasta, ignore_errors=True)
    (pasta / "antes").mkdir(parents=True)
    _rodas(pasta, [f"{n}=={u}" for n, (_v, u) in sorted(atrasadas.items())])
    passo.fracao(0.5)
    _rodas(pasta / "antes", [f"{n}=={v}" for n, (v, _u) in sorted(atrasadas.items())])
    passo.fracao(1.0)
    return {"pacotes": {n: [v, u] for n, (v, u) in atrasadas.items()}}


def _voltar_as_de_antes(pacotes: dict[str, Any]) -> tuple[int, str]:
    alvo = [f"{n}=={v}" for n, (v, _u) in sorted(pacotes.items())]
    antes = _pasta_do_python() / "antes"
    if antes.is_dir():
        return _instalar_rodas(antes, alvo)
    return _pip("install", *alvo)


def _instalar_o_python(passo: Passo, dados: dict[str, Any]) -> None:
    pacotes = dados.get("pacotes") or {}
    if not pacotes:
        return
    alvo = [f"{n}=={u}" for n, (_v, u) in sorted(pacotes.items())]
    rc, ultima = _instalar_rodas(_pasta_do_python(), alvo)
    if rc != 0:
        raise EtapaFalhouError(ultima or "o pip não instalou")
    passo.fracao(0.8)
    motivo = _o_produto_sobe()
    if motivo:
        rc, ultima = _voltar_as_de_antes(pacotes)
        volta = "voltou às versões de antes" if rc == 0 else f"e não voltou: {ultima}"
        raise EtapaFalhouError(f"o Hefesto não sobe com as versões novas ({motivo}); {volta}")
    passo.fracao(1.0)


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
    pacotes = (anterior.get("dados") or {}).get("pacotes") or {}
    if not pacotes:
        raise EtapaFalhouError("sem versão anterior")
    rc, ultima = _voltar_as_de_antes(pacotes)
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


def _hefesto_sem_reinstalar(_versoes: Versoes) -> str:
    return "" if (RAIZ_DO_REPOSITORIO / ".git").exists() else "instalação sem clone"


def _reinstalar_o_hefesto(passo: Passo, _dados_: dict[str, Any]) -> None:
    vao = _vao()
    motivo = vao.por_que_nao(RAIZ_DO_REPOSITORIO)
    if motivo:
        raise EtapaFalhouError(motivo)
    vao._instalar(RAIZ_DO_REPOSITORIO, vao._rodar_o_install)
    motivo = vao._motivo_da_nota(vao._linhas_da_nota() or [])
    if motivo:
        raise EtapaFalhouError(motivo)
    passo.fracao(1.0)


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


def _compilar_a_gdk(pasta: Path, arquivo: str, sha: str) -> Path | None:
    if not shutil.which("x86_64-w64-mingw32-gcc-posix"):
        return None
    construida = pasta / "construida"
    if not (construida / arquivo).is_file():
        shutil.rmtree(construida, ignore_errors=True)
        rc, _ultima = _comando(["bash", str(RAIZ_DO_REPOSITORIO / "assets" / "gdk-runtime"
                                            / "construir.sh"), str(construida)])
        if rc != 0:
            return None
    feito = construida / arquivo
    return feito if _sha_do_arquivo(feito) == sha else None


def _baixar_a_gdk(passo: Passo, _dados_: dict[str, Any]) -> None:
    pino = _pino_da_gdk()
    try:
        versao = _versao_do_pyproject(
            (RAIZ_DO_REPOSITORIO / "pyproject.toml").read_text(encoding="utf-8"))
    except OSError:
        versao = ""
    pasta = _cache() / "gdk"
    shutil.rmtree(pasta / "nova", ignore_errors=True)
    shutil.rmtree(pasta / "construida", ignore_errors=True)
    for arquivo, chave_sha, chave_url, _destino in ARQUIVOS_DA_GDK:
        sha = pino.get(chave_sha, "")
        if not re.fullmatch(r"[0-9a-f]{64}", sha):
            raise EtapaFalhouError(f"o pino da peça não traz o {chave_sha}")
        url = pino.get(chave_url, "").replace(MARCA_DA_VERSAO_NO_PINO, versao)
        try:
            _baixar(url, pasta / "nova" / arquivo, passo, sha)
        except EtapaFalhouError as erro:
            compilada = _compilar_a_gdk(pasta, arquivo, sha)
            if compilada is None:
                raise EtapaFalhouError(
                    f"{erro}; e a compilação aqui não deu o sha256 do pino") from None
            shutil.copy2(compilada, pasta / "nova" / arquivo)


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
        _raiz("backport-construir", backport, passo=passo)
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
        Peca("proton", "GE-Proton", "Os jogos da Steam e do Heroic",
             "Todos os jogos da Steam e do Heroic", versoes_do_proton,
             _baixar_o_proton, _instalar_o_proton, _aplicar_o_proton, _voltar_o_proton,
             reinstalacao=Reinstalacao(_baixar_de_novo_o_proton, _reinstalar_o_proton,
                                       _aplicar_o_proton, _proton_sem_reinstalar)),
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
             reinstalacao=Reinstalacao(_baixar_de_novo_o_python, _reinstalar_o_python)),
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
             reinstalacao=Reinstalacao(_baixar_de_novo_o_mangohud,
                                       _do_ajudante("mangohud-reinstalar"), None,
                                       _mangohud_sem_reinstalar)),
        Peca("umu", "umu", "Os jogos de fora da Steam no Proton", "Os jogos de fora da Steam",
             versoes_do_umu, _baixar_o_umu, _instalar_o_umu, _aplicar_o_umu, _voltar_o_umu,
             reinstalacao=Reinstalacao(_baixar_de_novo_o_umu, _instalar_o_umu, _reapontar_o_umu,
                                       _umu_sem_reinstalar)),
        Peca("hefesto", "Hefesto", "Interface, serviço e correções", "O serviço e a janela",
             versoes_do_hefesto, _baixar_o_hefesto, _instalar_o_hefesto, _aplicar_o_hefesto,
             grupo="hefesto",
             reinstalacao=Reinstalacao(None, _reinstalar_o_hefesto, None,
                                       _hefesto_sem_reinstalar)),
    ]

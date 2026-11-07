"""Instalar, atualizar, ligar, desligar e remover uma modificação.

Os três lugares de uma modificação (``utils/xdg_paths.py``):

* o código, em ``~/.local/share/hefesto-dualsense4unix/mods/<id>/``;
* os dados, em ``~/.local/state/hefesto-dualsense4unix/mods/<id>/``;
* a linha da extensão no registro, ``~/.config/hefesto-dualsense4unix/mods.json``.

O registro é a única fonte do que está instalado e ligado: a linha de comando
o escreve, e o supervisor do serviço o lê e obedece (abre o que está ligado,
para o que não está). O commit instalado é a identidade de uma modificação.

«Oficial» é só a tag assinada que o ``git verify-tag`` confere contra
:data:`CHAVES_OFICIAIS`, as chaves que o produto carrega; o endereço sozinho
não basta. Tudo o mais que vem de git é «comunidade», e o que vem de uma
pasta é «local».
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from hefesto_dualsense4unix.mods import API_DAS_MODIFICACOES, meu_css
from hefesto_dualsense4unix.mods.manifesto import (
    Manifesto,
    ManifestoRecusadoError,
    ler_manifesto,
    permissoes_novas,
)
from hefesto_dualsense4unix.utils import xdg_paths
from hefesto_dualsense4unix.utils.maquina import _CHAVE_DE_LANCADOR

Origem = Literal["oficial", "comunidade", "local"]

CHAVES_OFICIAIS: tuple[str, ...] = ()

PRAZO_PARA_PARAR_S = 5.0

CADENCIA_DA_ESPERA_S = 0.05

SINAIS_DO_FIM: tuple[tuple[signal.Signals, float], ...] = (
    (signal.SIGTERM, 2.0),
    (signal.SIGKILL, 1.0),
)

_PRAZO_DO_GIT_S = 300.0

_PRAZO_DO_LS_REMOTE_S = 60.0

INTERVALO_DA_ATUALIZACAO_S = 6 * 3600.0

_ESTADOS_VIVOS = frozenset({"ligando", "rodando", "voltando"})

PRAZO_DO_PREPARO_S = 600.0

DIARIO_DO_PREPARO = "preparo.log"
TETO_DO_DIARIO_DO_PREPARO_BYTES = 256 * 1024

DIARIO_DOS_GESTOS = "gestos-das-extensoes.log"
TETO_DO_DIARIO_DOS_GESTOS_BYTES = 64 * 1024

PASTA_DOS_DIARIOS = ".diarios"

_DA_SESSAO_NO_PREPARO = (
    "PATH", "LANG", "HOME", "USER", "LOGNAME",
    "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME", "XDG_CACHE_HOME", "XDG_RUNTIME_DIR",
    "http_proxy", "https_proxy", "no_proxy", "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY",
)


class InstalacaoRecusadaError(Exception):
    """O gesto não pôde ser feito; ``frase`` é a linha que a pessoa lê."""

    def __init__(self, frase: str) -> None:
        super().__init__(frase)
        self.frase = frase


class AvisoParaVerError(InstalacaoRecusadaError):
    """O manifesto traz um ``aviso`` que quem instala ainda não viu: nada se gravou.

    Quem chama mostra ``aviso`` e repete o gesto com ``aviso_visto=aviso``.
    """

    def __init__(self, nome: str, aviso: str) -> None:
        super().__init__(f"«{nome}» avisa: {aviso}")
        self.aviso = aviso


def aviso_por_ver(entrada: Entrada, manifesto: Manifesto) -> str:
    """O ``aviso`` do manifesto que esta instalação ainda não aceitou; vazio quando não há."""
    return manifesto.aviso if manifesto.aviso and manifesto.aviso != entrada.aviso_aceito else ""


@dataclass(frozen=True)
class Lugares:
    """Os três lugares de toda modificação, e o estado vivo que o serviço escreve."""

    codigo: Path
    dados: Path
    registro: Path
    estado: Path

    @classmethod
    def do_xdg(cls) -> Lugares:
        return cls(
            codigo=xdg_paths.mods_codigo_dir(),
            dados=xdg_paths.mods_dados_dir(),
            registro=xdg_paths.mods_registro_path(),
            estado=xdg_paths.mods_estado_path(),
        )

    @property
    def diario_dos_gestos(self) -> Path:
        """O diário dos gestos que mudam o lar, ao lado da pasta dos dados."""
        return self.dados.parent / DIARIO_DOS_GESTOS

    def pasta_do_diario(self, mod_id: str) -> Path:
        """A pasta do supervisor para o diário de ``mod_id``: a caixa só monta ``<dados>/<id>``."""
        return self.dados / PASTA_DOS_DIARIOS / mod_id


class Entrada(BaseModel):
    """A linha de uma modificação no registro."""

    model_config = ConfigDict(extra="ignore")

    id: str
    nome: str
    versao: str
    origem: Origem
    endereco: str
    ref: str | None = None
    commit: str = ""
    permissoes_aceitas: list[str] = []
    ligada: bool = False
    instalada_em: str = ""
    ligada_em: str = ""
    atualiza_sozinha: bool = True
    intervalo_da_atualizacao_s: float = INTERVALO_DA_ATUALIZACAO_S
    versao_esperando: str = ""
    commit_esperando: str = ""
    motivo_da_espera: str = ""
    aviso_aceito: str = ""
    preparo_aceito: list[str] = []
    preparada_em: str = ""
    motivo_do_preparo: str = ""
    em_troca: str = ""


@dataclass(frozen=True)
class Resultado:
    """O que a instalação ou a atualização fez."""

    entrada: Entrada
    manifesto: Manifesto
    permissoes_novas: list[str]
    trocou: bool = True
    substituidas: list[str] = field(default_factory=list)


def _conferir_id(mod_id: str) -> str:
    if not _CHAVE_DE_LANCADOR.match(mod_id or ""):
        raise InstalacaoRecusadaError(f"«{mod_id}» não é um id de modificação.")
    return mod_id


def ler_registro(caminho: Path) -> dict[str, Entrada]:
    """As modificações instaladas, por id. Sem arquivo, nenhuma."""
    try:
        bruto = json.loads(caminho.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InstalacaoRecusadaError(f"O registro {caminho} não pôde ser lido.") from exc
    linhas = bruto.get("mods", []) if isinstance(bruto, dict) else []
    registro: dict[str, Entrada] = {}
    for linha in linhas if isinstance(linhas, list) else []:
        with contextlib.suppress(ValidationError):
            entrada = Entrada.model_validate(linha)
            if _CHAVE_DE_LANCADOR.match(entrada.id):
                registro[entrada.id] = entrada
    return registro


def gravar_registro(caminho: Path, registro: dict[str, Entrada]) -> None:
    """Grava o registro inteiro de uma vez (arquivo novo e ``rename``), em ``0600``."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    corpo = {
        "forma": 1,
        "mods": [registro[k].model_dump() for k in sorted(registro)],
    }
    fd, nome = tempfile.mkstemp(prefix=".mods-", suffix=".json", dir=caminho.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as arquivo:
            json.dump(corpo, arquivo, ensure_ascii=False, indent=2)
            arquivo.write("\n")
        os.chmod(nome, 0o600)
        os.replace(nome, caminho)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(nome)
        raise


def anotar_o_gesto(lg: Lugares, verbo: str, ids: Sequence[str], *,
                   tocados: Sequence[Path] | None = None) -> None:
    """Uma linha ``[gesto]`` com os caminhos que o gesto vai tocar, antes de tocá-los.

    O canário da suíte lê o diário do lar de verdade e reconhece por essa linha a escrita de
    quem usa. Sem ``tocados``, os caminhos são o código e os dados de cada id e o registro; com
    ele, só os que o gesto toca. A volta passa do teto para o ``.1``; o diário que não abre nunca
    barra o gesto.
    """
    if tocados is None:
        caminhos = [str(p) for mod_id in ids for p in (
            lg.codigo / mod_id, lg.dados / mod_id, lg.pasta_do_diario(mod_id))]
        caminhos.append(str(lg.registro))
    else:
        caminhos = [str(p) for p in tocados]
    diario = lg.diario_dos_gestos
    with contextlib.suppress(OSError):
        linha = (f"{time.strftime('%Y-%m-%d %H:%M:%S')} [gesto] mod {verbo} {' '.join(ids)} → "
                 f"{json.dumps(caminhos, ensure_ascii=False)}\n")
        diario.parent.mkdir(parents=True, exist_ok=True)
        with contextlib.suppress(FileNotFoundError):
            if diario.stat().st_size > TETO_DO_DIARIO_DOS_GESTOS_BYTES:
                os.replace(diario, diario.with_name(f"{diario.name}.1"))
        with diario.open("a", encoding="utf-8") as arquivo:
            arquivo.write(linha)


def ler_estado(caminho: Path) -> dict[str, dict[str, Any]]:
    """O estado vivo que o supervisor escreve; vazio sem serviço."""
    try:
        bruto = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    mods = bruto.get("mods") if isinstance(bruto, dict) else None
    return {str(k): v for k, v in mods.items() if isinstance(v, dict)} if isinstance(
        mods, dict) else {}


def _ambiente_do_git(extra: dict[str, str] | None = None) -> dict[str, str]:
    """As credenciais que a máquina já tem, e nenhuma pergunta: sem terminal,
    sem senha digitada. O Hefesto nunca guarda senha."""
    ambiente = dict(os.environ)
    ambiente["GIT_TERMINAL_PROMPT"] = "0"
    ambiente.setdefault("GIT_SSH_COMMAND", "ssh -o BatchMode=yes")
    ambiente["LC_ALL"] = "C"
    if extra:
        ambiente.update(extra)
    return ambiente


def _git(
    args: Sequence[str],
    *,
    cwd: Path | None = None,
    extra: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        env=_ambiente_do_git(extra),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=_PRAZO_DO_GIT_S,
        check=False,
    )


FRASE_SEM_REDE = (
    "Não deu para chegar ao endereço da extensão. "
    "Confira a internet e se o endereço está escrito certo.")
FRASE_SEM_CONEXAO_SEGURA = (
    "O endereço da extensão não tem conexão segura válida. "
    "Confira o endereço ou tente em outra rede.")
FRASE_SEM_EXTENSAO = (
    "Não há extensão nesse endereço. "
    "Confira se ele está escrito certo e se o repositório é público.")
FRASE_PEDE_LOGIN = (
    "Esse endereço pede login. "
    "Confira se ele está escrito certo e se o repositório é público.")
FRASE_SEM_VERSAO = (
    "A versão «{ref}» não existe nesse endereço. Confira o nome da versão.")
FRASE_SEM_CAUSA = (
    "Não deu para baixar a extensão. Confira o endereço e a internet e tente de novo.")
FRASE_DO_PRAZO = (
    "O download da extensão passou de {minutos} minutos. "
    "Confira a internet e tente de novo.")

_CAUSAS_DO_GIT: tuple[tuple[tuple[str, ...], str], ...] = (
    (("remote branch",), FRASE_SEM_VERSAO),
    (("permission denied", "authentication failed", "could not read username",
      "could not read password", "terminal prompts disabled", "access denied",
      "returned error: 401", "returned error: 403"), FRASE_PEDE_LOGIN),
    (("repository not found", "not found", "does not exist",
      "does not appear to be a git repository", "not a git repository",
      "returned error: 404"), FRASE_SEM_EXTENSAO),
    (("certificate", "ssl_connect", "gnutls", "tls connection"), FRASE_SEM_CONEXAO_SEGURA),
    (("could not resolve", "failed to connect", "couldn't connect", "connection refused",
      "timed out", "network is unreachable", "no route to host", "name or service not known",
      "temporary failure in name resolution", "connection reset", "connection closed",
      "early eof", "the remote end hung up"), FRASE_SEM_REDE),
)


def frase_da_recusa_do_git(erro: str, ref: str | None = None) -> str:
    """A frase de quem usa para o erro do ``git clone``: a causa e o gesto, sem o inglês do git.

    O trecho entre aspas sai antes da leitura, porque traz o endereço e o caminho, que
    podem ter qualquer palavra.
    """
    texto = re.sub(r"'[^'\n]*'", "", erro).lower()
    for marcas, frase in _CAUSAS_DO_GIT:
        if any(marca in texto for marca in marcas):
            return frase.format(ref=ref or "")
    return FRASE_SEM_CAUSA


def _clonar(endereco: str, ref: str | None, destino: Path) -> str:
    """``git clone --depth 1`` e o commit que ficou; recusa com a causa e o gesto."""
    args = ["clone", "--depth", "1", "--quiet"]
    if ref:
        args += ["--branch", ref]
    try:
        feito = _git([*args, "--", endereco, str(destino)])
    except subprocess.TimeoutExpired as exc:
        raise InstalacaoRecusadaError(
            FRASE_DO_PRAZO.format(minutos=round(_PRAZO_DO_GIT_S / 60))) from exc
    if feito.returncode != 0:
        raise InstalacaoRecusadaError(frase_da_recusa_do_git(feito.stderr, ref))
    commit = _git(["rev-parse", "HEAD"], cwd=destino).stdout.strip()
    if not commit:
        raise InstalacaoRecusadaError("O git baixou a modificação sem commit.")
    return commit


def commit_remoto(endereco: str, ref: str | None) -> str | None:
    """O commit que o ``ref`` aponta no endereço (``HEAD`` sem ``ref``), sem baixar nada.

    ``None`` quando o endereço não responde (sem rede, endereço que sumiu); o git que não
    roda ou passa do prazo é recusa. Nos dois, quem pergunta tenta de novo depois, e a
    extensão instalada fica como está.
    """
    padroes = (
        [f"refs/tags/{ref}", f"refs/tags/{ref}^{{}}", f"refs/heads/{ref}"] if ref else ["HEAD"]
    )
    try:
        feito = subprocess.run(
            ["git", "ls-remote", "--", endereco, *padroes],
            env=_ambiente_do_git(),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=_PRAZO_DO_LS_REMOTE_S,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise InstalacaoRecusadaError(f"O git não respondeu: {exc}") from exc
    if feito.returncode != 0:
        return None
    achados: dict[str, str] = {}
    for linha in feito.stdout.splitlines():
        partes = linha.split()
        if len(partes) == 2:
            achados[partes[1]] = partes[0]
    if not ref:
        return achados.get("HEAD")
    for nome in (f"refs/tags/{ref}^{{}}", f"refs/tags/{ref}", f"refs/heads/{ref}"):
        if nome in achados:
            return achados[nome]
    return None


def origem_da_tag(pasta: Path, ref: str | None, chaves: Sequence[str]) -> Origem:
    """«oficial» só com tag assinada por uma das ``chaves``, apontando para o HEAD."""
    if not ref or not chaves:
        return "comunidade"
    tipo = _git(["cat-file", "-t", f"refs/tags/{ref}"], cwd=pasta)
    if tipo.returncode != 0 or tipo.stdout.strip() != "tag":
        return "comunidade"
    with tempfile.TemporaryDirectory(prefix="hefesto-chaves-") as tmp:
        lista = Path(tmp) / "allowed_signers"
        lista.write_text("\n".join(chaves) + "\n", encoding="utf-8")
        gnupg = Path(tmp) / "gnupg"
        gnupg.mkdir(mode=0o700)
        conferida = _git(
            ["-c", f"gpg.ssh.allowedSignersFile={lista}", "verify-tag", ref],
            cwd=pasta,
            extra={"GNUPGHOME": str(gnupg)},
        )
    if conferida.returncode != 0:
        return "comunidade"
    da_tag = _git(["rev-parse", f"refs/tags/{ref}^{{commit}}"], cwd=pasta).stdout.strip()
    cabeca = _git(["rev-parse", "HEAD"], cwd=pasta).stdout.strip()
    return "oficial" if da_tag and da_tag == cabeca else "comunidade"


def _commit_da_pasta(pasta: Path) -> str:
    with contextlib.suppress(OSError, subprocess.SubprocessError):
        feito = _git(["rev-parse", "HEAD"], cwd=pasta)
        if feito.returncode == 0:
            return feito.stdout.strip()
    return ""


def _conferir_o_lancador(manifesto: Manifesto, pasta: Path) -> None:
    """O tipo, o bloco e a permissão ``lancador`` andam juntos, e o bloco passa no conferidor.

    É o mesmo conferidor do censo da aba: o que ele recusaria calado recusa aqui, com a frase.
    """
    tem_tipo, tem_bloco = "lancador" in manifesto.tipos, manifesto.lancador is not None
    if tem_tipo and not tem_bloco:
        raise InstalacaoRecusadaError(
            "O hefesto-mod.json tem o tipo «lancador» sem o bloco «lancador».")
    if tem_bloco and not tem_tipo:
        raise InstalacaoRecusadaError(
            "O hefesto-mod.json tem o bloco «lancador» sem o tipo «lancador».")
    if not tem_bloco:
        return
    if "lancador" not in manifesto.permissoes:
        raise InstalacaoRecusadaError(
            "O hefesto-mod.json tem o bloco «lancador» sem a permissão «lancador».")
    from hefesto_dualsense4unix.integrations.censo_dos_lancadores import lancador_da_modificacao

    try:
        lancador_da_modificacao(manifesto.id, manifesto.lancador, pasta)
    except ValueError as exc:
        raise InstalacaoRecusadaError(f"O hefesto-mod.json tem {exc}.") from exc


def _ambiente_do_preparo(lg: Lugares, mod_id: str) -> dict[str, str]:
    ambiente = {k: os.environ[k] for k in _DA_SESSAO_NO_PREPARO if k in os.environ}
    ambiente.setdefault("PATH", "/usr/bin:/bin")
    ambiente.setdefault("LANG", "C.UTF-8")
    ambiente.update({
        "HEFESTO_MOD_ID": mod_id,
        "HEFESTO_MOD_DADOS": str(lg.dados / mod_id),
        "HEFESTO_MOD_API": str(API_DAS_MODIFICACOES),
    })
    return ambiente


def _aparar_o_diario_do_preparo(diario: Path) -> None:
    """Fica só o fim do diário, até o teto: o preparo que fala demais não enche o disco."""
    with contextlib.suppress(OSError):
        if diario.stat().st_size > TETO_DO_DIARIO_DO_PREPARO_BYTES:
            with diario.open("rb") as arquivo:
                arquivo.seek(-TETO_DO_DIARIO_DO_PREPARO_BYTES, os.SEEK_END)
                fim = arquivo.read()
            diario.write_bytes(fim)


def _parar_o_preparo(processo: subprocess.Popen[bytes]) -> None:
    """O ``SIGKILL`` ao grupo do preparo (o PID é o do ``Popen`` deste instalador) e a espera."""
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(processo.pid, signal.SIGKILL)
    processo.wait()


def _preparar(lg: Lugares, manifesto: Manifesto) -> str:
    """Roda o ``preparar`` fora da caixa, como quem usa: o motivo da falha, ou vazio.

    Nunca como root. A pasta de trabalho é a do código, a entrada é vazia (sem terminal, vale o
    padrão do comando) e a saída vai a :data:`DIARIO_DO_PREPARO`. Passado o prazo, o grupo de
    processos que o instalador abriu recebe o ``SIGKILL``, pelo PID que ele mesmo guardou.
    """
    from hefesto_dualsense4unix.mods.supervisor import _resolver_o_comando, ultima_linha_do_diario

    assert manifesto.preparar
    nome = manifesto.nome
    if os.geteuid() == 0:
        return f"O preparo de «{nome}» não roda como root."
    codigo = lg.codigo / manifesto.id
    comando = _resolver_o_comando(codigo, manifesto.preparar)
    if comando is None:
        return f"O preparo de «{nome}» não achou o comando {manifesto.preparar[0]}."
    diario = lg.dados / manifesto.id / DIARIO_DO_PREPARO
    try:
        diario.parent.mkdir(parents=True, exist_ok=True)
        with diario.open("wb") as saida:
            processo = subprocess.Popen(
                comando,
                cwd=codigo,
                env=_ambiente_do_preparo(lg, manifesto.id),
                stdin=subprocess.DEVNULL,
                stdout=saida,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            saiu: int | None = None
            try:
                saiu = processo.wait(timeout=PRAZO_DO_PREPARO_S)
            except subprocess.TimeoutExpired:
                _parar_o_preparo(processo)
            except BaseException:
                _parar_o_preparo(processo)
                raise
    except OSError as exc:
        return f"O preparo de «{nome}» não abriu: {exc.strerror or exc}."
    finally:
        _aparar_o_diario_do_preparo(diario)
    if saiu is None:
        return f"O preparo de «{nome}» passou de {PRAZO_DO_PREPARO_S:.0f} s e foi parado."
    if saiu != 0:
        ultima = ultima_linha_do_diario(diario)
        return f"O preparo de «{nome}» falhou (código {saiu})" + (f": {ultima}" if ultima else ".")
    return ""


def _rodar_o_preparo(lg: Lugares, manifesto: Manifesto, entrada: Entrada) -> None:
    """O preparo com o «sim» já dado: grava na ``entrada`` o que ele fez; a falha a desliga."""
    entrada.preparo_aceito = list(manifesto.preparar or [])
    entrada.motivo_do_preparo = _preparar(lg, manifesto)
    entrada.preparada_em = "" if entrada.motivo_do_preparo else entrada.instalada_em
    if entrada.motivo_do_preparo:
        entrada.ligada = False


def _preparo_novo(lg: Lugares, anterior: Entrada, manifesto: Manifesto) -> bool:
    """O ``preparar`` da versão nova é outro que o aceito e que o da versão instalada?"""
    if not manifesto.preparar:
        return False
    ja_pedidos = [anterior.preparo_aceito]
    with contextlib.suppress(ManifestoRecusadoError):
        ja_pedidos.append(ler_manifesto(lg.codigo / anterior.id, exigir_api=False).preparar or [])
    return manifesto.preparar not in ja_pedidos


def instalar(
    origem: str,
    *,
    ref: str | None = None,
    lugares: Lugares | None = None,
    chaves: Sequence[str] = CHAVES_OFICIAIS,
    sozinha: bool = False,
    aviso_visto: str | None = None,
) -> Resultado:
    """Instala de um endereço git (``--ref`` para a tag) ou de uma pasta, sem ligar.

    Reinstalar é atualizar: segue ligada sem permissão nem aviso novos. ``sozinha`` é a que
    ninguém pediu: permissão, aviso ou preparo novos, a tag que não confere e o ``substitui``
    esperam o «Atualizar» em ``versao_esperando``. ``aviso_visto`` é o da tela (outro aviso recusa
    com :class:`AvisoParaVerError` antes de gravar; ``None`` o deixa para o ligar). O ``preparar``
    roda depois da troca do código quando ele já teve o «sim» e nada mais o espera (senão, no
    ligar, e sempre no ligar na primeira instalação); o que falha deixa a extensão instalada e
    desligada, com o motivo, e recusa com a frase.
    """
    lg = lugares or Lugares.do_xdg()
    pasta_local = Path(origem).expanduser()
    lg.codigo.mkdir(parents=True, exist_ok=True)
    temporaria = Path(tempfile.mkdtemp(prefix=".baixando-", dir=lg.codigo))
    troca: tuple[str, str] | None = None
    trocou = False
    try:
        baixada = temporaria / "mod"
        tipo: Origem
        if pasta_local.is_dir():
            if ref:
                raise InstalacaoRecusadaError("O --ref só vale para endereço git.")
            shutil.copytree(
                pasta_local, baixada, symlinks=True, ignore=shutil.ignore_patterns(".git")
            )
            commit = _commit_da_pasta(pasta_local)
            tipo = "local"
            endereco = str(pasta_local.resolve())
        else:
            commit = _clonar(origem, ref, baixada)
            tipo = origem_da_tag(baixada, ref, chaves)
            endereco = origem
            shutil.rmtree(baixada / ".git", ignore_errors=True)
        try:
            manifesto = ler_manifesto(baixada)
        except ManifestoRecusadoError as exc:
            raise InstalacaoRecusadaError(exc.frase) from exc
        _conferir_o_lancador(manifesto, baixada)
        registro = ler_registro(lg.registro)
        anterior = registro.get(manifesto.id)
        if anterior is not None and anterior.endereco != endereco:
            raise InstalacaoRecusadaError(
                f"Já existe «{manifesto.id}» instalada de {anterior.endereco}; remova antes."
            )
        aceitas = anterior.permissoes_aceitas if anterior is not None else []
        novas = permissoes_novas(aceitas, manifesto.permissoes)
        aviso_aceito = anterior.aviso_aceito if anterior is not None else ""
        if aviso_visto is not None and manifesto.aviso:
            if aviso_visto != manifesto.aviso and manifesto.aviso != aviso_aceito:
                raise AvisoParaVerError(manifesto.nome, manifesto.aviso)
            aviso_aceito = manifesto.aviso
        a_substituir = [i for i in manifesto.substitui if i in registro]
        anotar_o_gesto(lg, "instalar" if anterior is None else "atualizar",
                       [manifesto.id, *a_substituir])
        if sozinha and anterior is not None:
            motivo = _o_que_segura_a_atualizacao(lg, anterior, tipo, manifesto, a_substituir)
            if motivo:
                return Resultado(
                    _marcar_a_espera(lg, manifesto, commit, motivo), manifesto, novas, trocou=False
                )
        seguia_ligada = anterior is not None and anterior.ligada
        antigas_ligadas = _parar_as_substituidas(lg, a_substituir)
        if seguia_ligada:
            troca = (manifesto.id, _marcar_a_troca(lg, manifesto.id))
            if not esperar_parar(manifesto.id, lugares=lg):
                _religar_a_que_seguia(lg, manifesto.id)
                for mod_id in antigas_ligadas:
                    _religar_a_que_seguia(lg, mod_id)
                raise InstalacaoRecusadaError(
                    f"A versão anterior de «{manifesto.id}» não parou; "
                    "não troquei o código."
                )
        _trocar_o_codigo(baixada, lg.codigo / manifesto.id)
        trocou = True
        pronta = not novas and manifesto.aviso in ("", aviso_aceito)
        prepara_agora = bool(manifesto.preparar) and pronta and anterior is not None and (
            anterior.ligada and (not sozinha or anterior.preparo_aceito == manifesto.preparar))
        entrada = Entrada(
            id=manifesto.id,
            nome=manifesto.nome,
            versao=manifesto.versao,
            origem=tipo,
            endereco=endereco,
            ref=ref,
            commit=commit,
            permissoes_aceitas=list(aceitas),
            ligada=(seguia_ligada or bool(antigas_ligadas)) and pronta
            and (prepara_agora or not manifesto.preparar),
            aviso_aceito=aviso_aceito,
            instalada_em=datetime.now(timezone.utc).isoformat(timespec="microseconds"),
        )
        if anterior is not None:
            entrada.atualiza_sozinha = anterior.atualiza_sozinha
            entrada.intervalo_da_atualizacao_s = anterior.intervalo_da_atualizacao_s
            entrada.preparo_aceito = list(anterior.preparo_aceito)
        if prepara_agora:
            _rodar_o_preparo(lg, manifesto, entrada)
        if a_substituir:
            from hefesto_dualsense4unix.mods import opcoes

            opcoes.herdar(manifesto, a_substituir, lg, ligadas=antigas_ligadas)
            _levar_o_meu_css(lg, manifesto, a_substituir)
        registro = ler_registro(lg.registro)
        registro[manifesto.id] = entrada
        gravar_registro(lg.registro, registro)
        troca = None
        _mandar_embora(lg, manifesto, a_substituir)
        if entrada.motivo_do_preparo:
            raise InstalacaoRecusadaError(
                f"«{manifesto.nome}» foi instalada e ficou desligada. {entrada.motivo_do_preparo}")
        return Resultado(entrada, manifesto, novas, substituidas=a_substituir)
    finally:
        if troca is not None:
            _desfazer_a_troca(lg, *troca, desligar=trocou)
        shutil.rmtree(temporaria, ignore_errors=True)


def _parar_as_substituidas(lg: Lugares, ids: Sequence[str]) -> list[str]:
    """Desliga e espera parar cada extensão que o ``substitui`` manda embora.

    Devolve as que estavam ligadas. A que não para recusa a troca inteira: as que já foram
    desligadas voltam a seguir ligadas, e nada se troca (a nova dividiria a porta com a antiga).
    """
    ligadas: list[str] = []
    for mod_id in ids:
        antiga = ler_registro(lg.registro)[mod_id]
        if antiga.ligada:
            ligadas.append(mod_id)
            desligar(mod_id, lugares=lg)
        if not esperar_parar(mod_id, lugares=lg):
            for religar in ligadas:
                _religar_a_que_seguia(lg, religar)
            raise InstalacaoRecusadaError(
                f"«{antiga.nome}», que esta extensão substitui, não parou; não troquei nada."
            )
    return ligadas


def _levar_o_meu_css(lg: Lugares, manifesto: Manifesto, ids: Sequence[str]) -> None:
    """O ``meu.css`` da substituída vai para a nova que aceita o CSS e ainda não tem o seu: o
    arquivo é da pessoa, e a troca de extensão não o deixa para trás."""
    destino = meu_css.caminho(manifesto.id, lg)
    if manifesto.opcao_do_css is None or destino.exists():
        return
    for mod_id in ids:
        origem = meu_css.caminho(mod_id, lg)
        if origem.is_file() and not origem.is_symlink():
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(origem, destino)
            os.chmod(destino, 0o600)
            return


def _mandar_embora(lg: Lugares, manifesto: Manifesto, ids: Sequence[str]) -> None:
    """A extensão substituída sai pelo caminho do ``remover``: para, apaga e confere."""
    for mod_id in ids:
        restos = remover(mod_id, lugares=lg)
        if restos:
            raise InstalacaoRecusadaError(
                f"«{manifesto.nome}» foi instalada, mas «{mod_id}» não saiu por completo: "
                + "; ".join(restos)
            )


def _o_que_segura_a_atualizacao(
    lg: Lugares, anterior: Entrada, tipo: Origem, manifesto: Manifesto,
    a_substituir: Sequence[str] = (),
) -> str:
    """Por que a atualização sozinha não troca o código; vazio quando troca.

    A permissão nova é a que nem o «sim» dado nem a versão instalada pedem: a extensão que
    nunca foi ligada não espera por uma permissão que o «ligar» ainda vai mostrar.
    """
    ja_pedidas = list(anterior.permissoes_aceitas)
    with contextlib.suppress(ManifestoRecusadoError):
        ja_pedidas += ler_manifesto(lg.codigo / anterior.id, exigir_api=False).permissoes
    novas = permissoes_novas(ja_pedidas, manifesto.permissoes)
    if novas:
        return f"A versão {manifesto.versao} pede {', '.join(novas)}."
    if aviso_por_ver(anterior, manifesto):
        return f"A versão {manifesto.versao} traz outro aviso."
    if _preparo_novo(lg, anterior, manifesto):
        return f"A versão {manifesto.versao} traz um preparo novo."
    if anterior.origem == "oficial" and tipo != "oficial":
        return f"A tag da versão {manifesto.versao} não confere com a chave oficial."
    if a_substituir:
        registro = ler_registro(lg.registro)
        nomes = ", ".join(f"«{registro[i].nome if i in registro else i}»" for i in a_substituir)
        return f"A versão {manifesto.versao} toma o lugar de {nomes}."
    return ""


def _marcar_a_espera(lg: Lugares, manifesto: Manifesto, commit: str, motivo: str) -> Entrada:
    """Grava na linha da extensão a versão que espera o «Atualizar»; o código fica."""
    registro = ler_registro(lg.registro)
    entrada = registro[manifesto.id]
    entrada.versao_esperando = manifesto.versao
    entrada.commit_esperando = commit
    entrada.motivo_da_espera = motivo
    gravar_registro(lg.registro, registro)
    return entrada


def _religar_a_que_seguia(lg: Lugares, mod_id: str) -> None:
    """Desfaz o ``desligar`` (ou a marca da troca) do instalar que não chegou a trocar o código."""
    registro = ler_registro(lg.registro)
    entrada = registro.get(mod_id)
    if entrada is not None and (not entrada.ligada or entrada.em_troca):
        entrada.ligada = True
        entrada.em_troca = ""
        gravar_registro(lg.registro, registro)


def _inicio_do_processo(pid: int) -> str:
    try:
        corpo = Path(f"/proc/{pid}/stat").read_text(encoding="ascii", errors="replace")
    except OSError:
        return ""
    campos = corpo.rpartition(")")[2].split()
    return campos[19] if len(campos) > 19 else ""


def troca_viva(entrada: Entrada) -> bool:
    """A linha está em troca do código, e quem a começou (PID e início) ainda vive.

    A extensão em troca segue ligada no registro: o supervisor a para e a mostra
    «atualizando», nunca «desligada». A marca de quem morreu no meio não vale.
    """
    pid, _, inicio = entrada.em_troca.partition(":")
    if not pid.isdigit() or int(pid) <= 1 or not _pid_vivo(int(pid)):
        return False
    return _inicio_do_processo(int(pid)) == inicio


def _marcar_a_troca(lg: Lugares, mod_id: str) -> str:
    """Pede ao serviço que pare a versão viva sem desligá-la: a marca é deste processo."""
    marca = f"{os.getpid()}:{_inicio_do_processo(os.getpid())}"
    registro = ler_registro(lg.registro)
    registro[mod_id].em_troca = marca
    gravar_registro(lg.registro, registro)
    return marca


def _desfazer_a_troca(lg: Lugares, mod_id: str, marca: str, *, desligar: bool) -> None:
    """A troca que não chegou ao registro novo tira a marca; com o código já trocado, desliga."""
    with contextlib.suppress(InstalacaoRecusadaError, OSError):
        registro = ler_registro(lg.registro)
        entrada = registro.get(mod_id)
        if entrada is None or entrada.em_troca != marca:
            return
        entrada.em_troca = ""
        entrada.ligada = entrada.ligada and not desligar
        gravar_registro(lg.registro, registro)


def _trocar_o_codigo(nova: Path, final: Path) -> None:
    velha: Path | None = None
    if final.exists() or final.is_symlink():
        velha = final.with_name(f".{final.name}.velha-{os.getpid()}-{time.monotonic_ns()}")
        final.rename(velha)
    nova.rename(final)
    if velha is not None:
        shutil.rmtree(velha, ignore_errors=True)


def atualizar(
    mod_id: str,
    *,
    ref: str | None = None,
    lugares: Lugares | None = None,
    chaves: Sequence[str] = CHAVES_OFICIAIS,
    sozinha: bool = False,
) -> Resultado:
    """Baixa de novo do endereço gravado (a tag nova, se ``ref``).

    ``sozinha`` é a do supervisor (ver :func:`instalar`); a origem «local» a recusa.
    """
    lg = lugares or Lugares.do_xdg()
    entrada = ler_registro(lg.registro).get(_conferir_id(mod_id))
    if entrada is None:
        raise InstalacaoRecusadaError(f"«{mod_id}» não está instalada.")
    if sozinha and entrada.origem == "local":
        raise InstalacaoRecusadaError(
            f"«{entrada.nome}» veio de uma pasta e não se atualiza sozinha."
        )
    return instalar(
        entrada.endereco,
        ref=None if entrada.origem == "local" else (ref or entrada.ref),
        lugares=lg,
        chaves=chaves,
        sozinha=sozinha,
    )


def commit_novo(entrada: Entrada) -> str | None:
    """O commit do endereço quando ele é outro que o instalado e o que já espera.

    ``None`` sem novidade ou para a origem «local», que nunca pergunta ao git; o git que
    não responde (sem rede) é recusa, para quem pergunta tentar de novo mais cedo.
    """
    if entrada.origem == "local":
        return None
    remoto = commit_remoto(entrada.endereco, entrada.ref)
    if not remoto:
        raise InstalacaoRecusadaError(f"O git não respondeu sobre «{entrada.nome}».")
    if remoto in (entrada.commit, entrada.commit_esperando):
        return None
    return remoto


def manifesto_instalado(mod_id: str, *, lugares: Lugares | None = None) -> Manifesto:
    """O manifesto da cópia instalada (o que a tela mostra antes do «sim»)."""
    lg = lugares or Lugares.do_xdg()
    try:
        return ler_manifesto(lg.codigo / _conferir_id(mod_id), exigir_api=False)
    except ManifestoRecusadoError as exc:
        raise InstalacaoRecusadaError(exc.frase) from exc


def ligar(
    mod_id: str,
    *,
    permissoes_vistas: Sequence[str],
    aviso_visto: str = "",
    lugares: Lugares | None = None,
) -> Entrada:
    """Liga, aceitando as permissões que quem chama mostrou e ouviu o «sim».

    ``permissoes_vistas`` é a lista que a linha de comando (ou a tela) mostrou.
    Se o manifesto do disco, relido agora, pede outra lista, recusa: o «sim» foi
    a um manifesto, e o código trocado entre o mostrar e o ligar não herda o «sim».
    O ``aviso`` que esta instalação ainda não aceitou vale igual: ``aviso_visto``.
    """
    lg = lugares or Lugares.do_xdg()
    registro = ler_registro(lg.registro)
    entrada = registro.get(_conferir_id(mod_id))
    if entrada is None:
        raise InstalacaoRecusadaError(f"«{mod_id}» não está instalada.")
    try:
        manifesto = ler_manifesto(lg.codigo / mod_id)
    except ManifestoRecusadoError as exc:
        raise InstalacaoRecusadaError(exc.frase) from exc
    if set(permissoes_vistas) != set(manifesto.permissoes):
        raise InstalacaoRecusadaError(
            f"«{manifesto.nome}» pede outras permissões do que as que você viu; "
            "veja de novo antes de ligar."
        )
    if aviso_por_ver(entrada, manifesto) and aviso_visto != manifesto.aviso:
        raise AvisoParaVerError(manifesto.nome, manifesto.aviso)
    _conferir_o_tema(manifesto, lg.codigo / mod_id)
    anotar_o_gesto(lg, "ligar", [mod_id])
    entrada.permissoes_aceitas = list(manifesto.permissoes)
    entrada.aviso_aceito = manifesto.aviso
    if manifesto.preparar and entrada.preparada_em != entrada.instalada_em:
        _rodar_o_preparo(lg, manifesto, entrada)
        if entrada.motivo_do_preparo:
            gravar_registro(lg.registro, registro)
            raise InstalacaoRecusadaError(entrada.motivo_do_preparo)
    entrada.ligada = True
    entrada.ligada_em = datetime.now(timezone.utc).isoformat(timespec="microseconds")
    gravar_registro(lg.registro, registro)
    return entrada


def _conferir_o_tema(manifesto: Manifesto, pasta: Path) -> None:
    """O tema que a régua da janela recusaria não liga: a frase de produto vai a quem ligou."""
    if "tema" not in manifesto.tipos or not manifesto.tema:
        return
    from hefesto_dualsense4unix.mods import tema

    try:
        tema.conferir_o_bloco(manifesto.tema, pasta)
    except tema.TemaRecusadoError as exc:
        raise InstalacaoRecusadaError(
            f"O tema de «{manifesto.nome}» não liga. {exc.frase}") from exc


def desligar(mod_id: str, *, lugares: Lugares | None = None) -> Entrada:
    lg = lugares or Lugares.do_xdg()
    registro = ler_registro(lg.registro)
    entrada = registro.get(_conferir_id(mod_id))
    if entrada is None:
        raise InstalacaoRecusadaError(f"«{mod_id}» não está instalada.")
    if entrada.ligada:
        anotar_o_gesto(lg, "desligar", [mod_id])
        entrada.ligada = False
        gravar_registro(lg.registro, registro)
    return entrada


def _pid_vivo(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _e_da_modificacao(pid: int, mod_id: str) -> bool:
    """O PID é um processo que o supervisor abriu para ``mod_id``? (pelo ambiente)"""
    try:
        ambiente = Path(f"/proc/{pid}/environ").read_bytes()
    except OSError:
        return False
    return f"HEFESTO_MOD_ID={mod_id}".encode() in ambiente.split(b"\0")


def esperar_parar(
    mod_id: str, *, lugares: Lugares | None = None, prazo: float = PRAZO_PARA_PARAR_S
) -> bool:
    """Espera o serviço parar ``mod_id``; no prazo, para pelo PID conferido.

    Nunca por nome: o PID vem do estado que o supervisor escreveu, e só recebe
    o sinal se o ambiente dele disser que é o processo daquela modificação.
    """
    lg = lugares or Lugares.do_xdg()
    limite = time.monotonic() + prazo
    pid: int | None = None
    while True:
        linha = ler_estado(lg.estado).get(mod_id, {})
        valor = linha.get("pid")
        pid = valor if isinstance(valor, int) and valor > 1 else None
        if pid is None or not _pid_vivo(pid) or linha.get("estado") not in _ESTADOS_VIVOS:
            return True
        if time.monotonic() >= limite:
            break
        time.sleep(CADENCIA_DA_ESPERA_S)
    if not _e_da_modificacao(pid, mod_id):
        return not _pid_vivo(pid)
    for sinal, espera in SINAIS_DO_FIM:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(pid, sinal)
        fim = time.monotonic() + espera
        while time.monotonic() < fim:
            if not _pid_vivo(pid):
                return True
            time.sleep(CADENCIA_DA_ESPERA_S)
    return not _pid_vivo(pid)


def _apagar_o_codigo(lg: Lugares, mod_id: str) -> None:
    shutil.rmtree(lg.codigo / mod_id, ignore_errors=True)


def _apagar_os_dados(lg: Lugares, mod_id: str) -> None:
    """Apaga ``<dados>/<id>`` menos o ``meu.css``: ele é escrita da pessoa, e reinstalar a
    extensão o encontra (``meu_css.garantir`` nunca reescreve). O diário sai junto."""
    shutil.rmtree(lg.pasta_do_diario(mod_id), ignore_errors=True)
    pasta = lg.dados / mod_id
    if pasta.is_symlink() or not pasta.is_dir():
        shutil.rmtree(pasta, ignore_errors=True)
        return
    for item in pasta.iterdir():
        if item.name == meu_css.NOME_DO_ARQUIVO:
            continue
        if item.is_dir() and not item.is_symlink():
            shutil.rmtree(item, ignore_errors=True)
        else:
            with contextlib.suppress(OSError):
                item.unlink()
    if not any(pasta.iterdir()):
        with contextlib.suppress(OSError):
            pasta.rmdir()


def o_css_que_fica(mod_id: str, *, lugares: Lugares | None = None) -> Path | None:
    """O ``meu.css`` que a remoção deixa no disco, ou ``None`` quando a pessoa não escreveu um."""
    alvo = meu_css.caminho(mod_id, lugares or Lugares.do_xdg())
    return alvo if alvo.exists() or alvo.is_symlink() else None


def _tirar_do_registro(lg: Lugares, mod_id: str) -> None:
    registro = ler_registro(lg.registro)
    if registro.pop(mod_id, None) is not None:
        gravar_registro(lg.registro, registro)


def _so_o_css_da_pessoa(pasta: Path) -> bool:
    if pasta.is_symlink() or not pasta.is_dir():
        return False
    return [item.name for item in pasta.iterdir()] == [meu_css.NOME_DO_ARQUIVO]


def conferir_remocao(mod_id: str, *, lugares: Lugares | None = None) -> list[str]:
    """O que ainda existe de ``mod_id`` nos três lugares; vazio = removida. O ``meu.css`` não
    conta: ele é da pessoa e fica (``o_css_que_fica``)."""
    lg = lugares or Lugares.do_xdg()
    restos: list[str] = []
    for pasta in (lg.codigo / mod_id, lg.dados / mod_id, lg.pasta_do_diario(mod_id)):
        if pasta.exists() or pasta.is_symlink():
            if pasta == lg.dados / mod_id and _so_o_css_da_pessoa(pasta):
                continue
            restos.append(str(pasta))
    if mod_id in ler_registro(lg.registro):
        restos.append(f"{lg.registro} (a linha «{mod_id}»)")
    return restos


def remover(
    mod_id: str, *, lugares: Lugares | None = None, prazo: float = PRAZO_PARA_PARAR_S
) -> list[str]:
    """Para, apaga e confere. Devolve o que sobrou; só a lista vazia é «removida»."""
    lg = lugares or Lugares.do_xdg()
    _conferir_id(mod_id)
    if not conferir_remocao(mod_id, lugares=lg):
        raise InstalacaoRecusadaError(f"«{mod_id}» não está instalada.")
    anotar_o_gesto(lg, "remover", [mod_id])
    if mod_id in ler_registro(lg.registro):
        desligar(mod_id, lugares=lg)
    if not esperar_parar(mod_id, lugares=lg, prazo=prazo):
        return [f"o processo de «{mod_id}» não parou"]
    _apagar_o_codigo(lg, mod_id)
    _apagar_os_dados(lg, mod_id)
    _tirar_do_registro(lg, mod_id)
    return conferir_remocao(mod_id, lugares=lg)


__all__ = [
    "CHAVES_OFICIAIS",
    "DIARIO_DOS_GESTOS",
    "DIARIO_DO_PREPARO",
    "INTERVALO_DA_ATUALIZACAO_S",
    "PRAZO_DO_PREPARO_S",
    "PRAZO_PARA_PARAR_S",
    "AvisoParaVerError",
    "Entrada",
    "InstalacaoRecusadaError",
    "Lugares",
    "Resultado",
    "anotar_o_gesto",
    "atualizar",
    "aviso_por_ver",
    "commit_novo",
    "commit_remoto",
    "conferir_remocao",
    "desligar",
    "esperar_parar",
    "gravar_registro",
    "instalar",
    "ler_estado",
    "ler_registro",
    "ligar",
    "manifesto_instalado",
    "o_css_que_fica",
    "origem_da_tag",
    "remover",
    "troca_viva",
]

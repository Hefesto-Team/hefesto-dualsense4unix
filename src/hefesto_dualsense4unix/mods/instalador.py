"""Instalar, atualizar, ligar, desligar e remover uma modificação.

Os três lugares de uma modificação (``utils/xdg_paths.py``):

* o código, em ``~/.local/share/hefesto-dualsense4unix/mods/<id>/``;
* os dados, em ``~/.local/state/hefesto-dualsense4unix/mods/<id>/``;
* a linha dela no registro, ``~/.config/hefesto-dualsense4unix/mods.json``.

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
import shutil
import signal
import subprocess
import tempfile
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from hefesto_dualsense4unix.mods.manifesto import (
    Manifesto,
    ManifestoRecusadoError,
    ler_manifesto,
    permissoes_novas,
)
from hefesto_dualsense4unix.utils import xdg_paths
from hefesto_dualsense4unix.utils.maquina import _CHAVE_DE_LANCADOR

Origem = Literal["oficial", "comunidade", "local"]

#: As chaves públicas do time, no formato ``allowed_signers`` do ``ssh-keygen``
#: (``<principal> <tipo> <chave>``). Vazia enquanto o time não publica a chave
#: de assinatura: até lá, nada instala como «oficial».
CHAVES_OFICIAIS: tuple[str, ...] = ()

#: Quanto a remoção espera o serviço parar o processo antes de ela mesma
#: mandar o sinal ao PID conferido.
PRAZO_PARA_PARAR_S = 5.0

#: A linha de comando não fala com o serviço: ela relê o estado que o supervisor
#: grava, nesta cadência, até o processo sair.
CADENCIA_DA_ESPERA_S = 0.05

#: Quando o serviço não para a tempo: o ``SIGTERM`` e, depois, o ``SIGKILL``, cada
#: um com a sua espera.
SINAIS_DO_FIM: tuple[tuple[signal.Signals, float], ...] = (
    (signal.SIGTERM, 2.0),
    (signal.SIGKILL, 1.0),
)

_PRAZO_DO_GIT_S = 300.0

_ESTADOS_VIVOS = frozenset({"ligando", "rodando", "voltando"})


class InstalacaoRecusadaError(Exception):
    """O gesto não pôde ser feito; ``frase`` é a linha que a pessoa lê."""

    def __init__(self, frase: str) -> None:
        super().__init__(frase)
        self.frase = frase


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


@dataclass(frozen=True)
class Resultado:
    """O que a instalação ou a atualização fez."""

    entrada: Entrada
    manifesto: Manifesto
    permissoes_novas: list[str]


def _conferir_id(mod_id: str) -> str:
    if not _CHAVE_DE_LANCADOR.match(mod_id or ""):
        raise InstalacaoRecusadaError(f"«{mod_id}» não é um id de modificação.")
    return mod_id


# -- o registro --------------------------------------------------------------


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


def ler_estado(caminho: Path) -> dict[str, dict[str, Any]]:
    """O estado vivo que o supervisor escreve; vazio sem serviço."""
    try:
        bruto = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    mods = bruto.get("mods") if isinstance(bruto, dict) else None
    return {str(k): v for k, v in mods.items() if isinstance(v, dict)} if isinstance(
        mods, dict) else {}


# -- o git -------------------------------------------------------------------


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


def _clonar(endereco: str, ref: str | None, destino: Path) -> str:
    """``git clone --depth 1`` e o commit que ficou; recusa com a última linha do git."""
    args = ["clone", "--depth", "1", "--quiet"]
    if ref:
        args += ["--branch", ref]
    try:
        feito = _git([*args, "--", endereco, str(destino)])
    except subprocess.TimeoutExpired as exc:
        raise InstalacaoRecusadaError("O git não terminou de baixar a modificação.") from exc
    if feito.returncode != 0:
        linhas = [ln for ln in feito.stderr.splitlines() if ln.strip()]
        motivo = linhas[-1].strip() if linhas else f"código {feito.returncode}"
        raise InstalacaoRecusadaError(f"O git não baixou a modificação: {motivo}")
    commit = _git(["rev-parse", "HEAD"], cwd=destino).stdout.strip()
    if not commit:
        raise InstalacaoRecusadaError("O git baixou a modificação sem commit.")
    return commit


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
        # Um chaveiro GPG vazio: assinatura GPG nunca confere aqui, porque a
        # lista que vale é a do produto, e não o chaveiro de quem instala.
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


# -- instalar e atualizar ----------------------------------------------------


def instalar(
    origem: str,
    *,
    ref: str | None = None,
    lugares: Lugares | None = None,
    chaves: Sequence[str] = CHAVES_OFICIAIS,
) -> Resultado:
    """Instala de um endereço git (``--ref`` para a tag) ou de uma pasta.

    Instalar não liga: a modificação nova nasce desligada, e ligar é o gesto
    que mostra as permissões. Reinstalar a mesma modificação é atualizar: ela
    segue ligada, a não ser que peça permissão nova, que volta a pedir o «sim».
    """
    lg = lugares or Lugares.do_xdg()
    pasta_local = Path(origem).expanduser()
    lg.codigo.mkdir(parents=True, exist_ok=True)
    temporaria = Path(tempfile.mkdtemp(prefix=".baixando-", dir=lg.codigo))
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
        registro = ler_registro(lg.registro)
        anterior = registro.get(manifesto.id)
        if anterior is not None and anterior.endereco != endereco:
            raise InstalacaoRecusadaError(
                f"Já existe «{manifesto.id}» instalada de {anterior.endereco}; remova antes."
            )
        aceitas = anterior.permissoes_aceitas if anterior is not None else []
        novas = permissoes_novas(aceitas, manifesto.permissoes)
        seguia_ligada = anterior is not None and anterior.ligada
        if seguia_ligada:
            desligar(manifesto.id, lugares=lg)
            esperar_parar(manifesto.id, lugares=lg)
        _trocar_o_codigo(baixada, lg.codigo / manifesto.id)
        entrada = Entrada(
            id=manifesto.id,
            nome=manifesto.nome,
            versao=manifesto.versao,
            origem=tipo,
            endereco=endereco,
            ref=ref,
            commit=commit,
            permissoes_aceitas=list(aceitas),
            ligada=seguia_ligada and not novas,
            instalada_em=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
        registro = ler_registro(lg.registro)
        registro[manifesto.id] = entrada
        gravar_registro(lg.registro, registro)
        return Resultado(entrada, manifesto, novas)
    finally:
        shutil.rmtree(temporaria, ignore_errors=True)


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
) -> Resultado:
    """Baixa de novo do endereço gravado (a tag nova, se ``ref``)."""
    lg = lugares or Lugares.do_xdg()
    entrada = ler_registro(lg.registro).get(_conferir_id(mod_id))
    if entrada is None:
        raise InstalacaoRecusadaError(f"«{mod_id}» não está instalada.")
    return instalar(
        entrada.endereco,
        ref=None if entrada.origem == "local" else (ref or entrada.ref),
        lugares=lg,
        chaves=chaves,
    )


# -- ligar e desligar --------------------------------------------------------


def manifesto_instalado(mod_id: str, *, lugares: Lugares | None = None) -> Manifesto:
    """O manifesto da cópia instalada (o que a tela mostra antes do «sim»)."""
    lg = lugares or Lugares.do_xdg()
    try:
        return ler_manifesto(lg.codigo / _conferir_id(mod_id), exigir_api=False)
    except ManifestoRecusadoError as exc:
        raise InstalacaoRecusadaError(exc.frase) from exc


def ligar(mod_id: str, *, lugares: Lugares | None = None) -> Entrada:
    """Liga, aceitando as permissões que o manifesto instalado pede.

    Quem chama mostrou as permissões e ouviu o «sim» antes: a linha de comando
    pergunta, e a tela tem o mesmo gesto.
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
    entrada.permissoes_aceitas = list(manifesto.permissoes)
    entrada.ligada = True
    gravar_registro(lg.registro, registro)
    return entrada


def desligar(mod_id: str, *, lugares: Lugares | None = None) -> Entrada:
    lg = lugares or Lugares.do_xdg()
    registro = ler_registro(lg.registro)
    entrada = registro.get(_conferir_id(mod_id))
    if entrada is None:
        raise InstalacaoRecusadaError(f"«{mod_id}» não está instalada.")
    if entrada.ligada:
        entrada.ligada = False
        gravar_registro(lg.registro, registro)
    return entrada


# -- parar e remover ---------------------------------------------------------


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
    shutil.rmtree(lg.dados / mod_id, ignore_errors=True)


def _tirar_do_registro(lg: Lugares, mod_id: str) -> None:
    registro = ler_registro(lg.registro)
    if registro.pop(mod_id, None) is not None:
        gravar_registro(lg.registro, registro)


def conferir_remocao(mod_id: str, *, lugares: Lugares | None = None) -> list[str]:
    """O que ainda existe de ``mod_id`` nos três lugares; vazio = removida."""
    lg = lugares or Lugares.do_xdg()
    restos: list[str] = []
    for pasta in (lg.codigo / mod_id, lg.dados / mod_id):
        if pasta.exists() or pasta.is_symlink():
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
    "PRAZO_PARA_PARAR_S",
    "Entrada",
    "InstalacaoRecusadaError",
    "Lugares",
    "Resultado",
    "atualizar",
    "conferir_remocao",
    "desligar",
    "esperar_parar",
    "gravar_registro",
    "instalar",
    "ler_estado",
    "ler_registro",
    "ligar",
    "manifesto_instalado",
    "origem_da_tag",
    "remover",
]

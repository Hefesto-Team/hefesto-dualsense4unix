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
from dataclasses import dataclass, field
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

#: O ``git ls-remote`` da atualização sozinha só pergunta o commit: sem rede, ele
#: desiste antes de segurar a volta seguinte.
_PRAZO_DO_LS_REMOTE_S = 60.0

#: De quanto em quanto tempo a extensão instalada pelo git pergunta ao endereço dela se há
#: commit novo (decisão D-1910-A-EXTENSAO-DO-GIT-CONFERE-A-CADA-SEIS-HORAS, por delegação, a
#: validar por ela). Cada extensão guarda o seu no registro.
INTERVALO_DA_ATUALIZACAO_S = 6 * 3600.0

_ESTADOS_VIVOS = frozenset({"ligando", "rodando", "voltando"})


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
    #: A hora do último «ligar»: ligar de novo a que parou reabre o processo.
    ligada_em: str = ""
    #: A chave e o intervalo da atualização sozinha; a origem «local» nunca se atualiza.
    atualiza_sozinha: bool = True
    intervalo_da_atualizacao_s: float = INTERVALO_DA_ATUALIZACAO_S
    #: A versão nova que a atualização sozinha baixou e não instalou (pede permissão nova,
    #: ou a tag deixou de ser a oficial): espera o «Atualizar». Vazio quando nada espera.
    versao_esperando: str = ""
    commit_esperando: str = ""
    motivo_da_espera: str = ""
    #: O ``aviso`` do manifesto que teve o «sim» (no instalar ou no ligar).
    aviso_aceito: str = ""


@dataclass(frozen=True)
class Resultado:
    """O que a instalação ou a atualização fez."""

    entrada: Entrada
    manifesto: Manifesto
    permissoes_novas: list[str]
    #: ``False`` quando a atualização sozinha deixou a versão nova esperando o «Atualizar».
    trocou: bool = True
    #: Os ids que o ``substitui`` do manifesto mandou embora nesta instalação.
    substituidas: list[str] = field(default_factory=list)


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
    # A tag anotada aponta para o objeto da tag; o commit é o «descascado» (``^{}``).
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

    Reinstalar é atualizar: segue ligada, a não ser que peça permissão nova ou traga
    outro aviso. ``sozinha`` é a atualização que ninguém pediu: a versão com permissão
    nova, aviso novo ou tag que não confere com a chave oficial fica em
    ``versao_esperando`` até o «Atualizar». ``aviso_visto`` é o da tela: outro ``aviso``
    no manifesto recusa com :class:`AvisoParaVerError` antes de gravar; ``None`` deixa
    o aviso para o «sim» do ligar.
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
        if sozinha and anterior is not None:
            motivo = _o_que_segura_a_atualizacao(lg, anterior, tipo, manifesto, a_substituir)
            if motivo:
                return Resultado(
                    _marcar_a_espera(lg, manifesto, commit, motivo), manifesto, novas, trocou=False
                )
        seguia_ligada = anterior is not None and anterior.ligada
        antigas_ligadas = _parar_as_substituidas(lg, a_substituir)
        if seguia_ligada:
            desligar(manifesto.id, lugares=lg)
            if not esperar_parar(manifesto.id, lugares=lg):
                # Trocar o código debaixo do processo vivo não é atualizar. O código
                # antigo fica como está, e a que seguia ligada segue ligada.
                _religar_a_que_seguia(lg, manifesto.id)
                for mod_id in antigas_ligadas:
                    _religar_a_que_seguia(lg, mod_id)
                raise InstalacaoRecusadaError(
                    f"A versão anterior de «{manifesto.id}» não parou; "
                    "não troquei o código."
                )
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
            ligada=(seguia_ligada or bool(antigas_ligadas)) and not novas
            and manifesto.aviso in ("", aviso_aceito),
            aviso_aceito=aviso_aceito,
            instalada_em=datetime.now(timezone.utc).isoformat(timespec="microseconds"),
        )
        if anterior is not None:
            entrada.atualiza_sozinha = anterior.atualiza_sozinha
            entrada.intervalo_da_atualizacao_s = anterior.intervalo_da_atualizacao_s
        if a_substituir:
            from hefesto_dualsense4unix.mods import opcoes

            opcoes.herdar(manifesto, a_substituir, lg)
        registro = ler_registro(lg.registro)
        registro[manifesto.id] = entrada
        gravar_registro(lg.registro, registro)
        _mandar_embora(lg, manifesto, a_substituir)
        return Resultado(entrada, manifesto, novas, substituidas=a_substituir)
    finally:
        shutil.rmtree(temporaria, ignore_errors=True)


def _parar_as_substituidas(lg: Lugares, ids: Sequence[str]) -> list[str]:
    """Desliga e espera parar cada extensão que o ``substitui`` manda embora.

    Devolve as que estavam ligadas. A que não para recusa a troca inteira: as que já foram
    desligadas voltam a seguir ligadas, e nada se troca (a nova dividiria a porta com ela).
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
    nunca foi ligada não espera por uma permissão que o «ligar» dela ainda vai mostrar.
    """
    ja_pedidas = list(anterior.permissoes_aceitas)
    with contextlib.suppress(ManifestoRecusadoError):
        ja_pedidas += ler_manifesto(lg.codigo / anterior.id, exigir_api=False).permissoes
    novas = permissoes_novas(ja_pedidas, manifesto.permissoes)
    if novas:
        return f"A versão {manifesto.versao} pede {', '.join(novas)}."
    if aviso_por_ver(anterior, manifesto):
        return f"A versão {manifesto.versao} traz outro aviso."
    if anterior.origem == "oficial" and tipo != "oficial":
        return f"A tag da versão {manifesto.versao} não confere com a chave oficial."
    if a_substituir:
        # Tirar uma extensão do ar é gesto de quem usa, não de quem atualiza sozinho. A frase vai
        # à dica do «Atualizar», e quem usa conhece a extensão pelo nome, não pelo id.
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
    """Desfaz o ``desligar`` do instalar que não chegou a trocar o código."""
    registro = ler_registro(lg.registro)
    entrada = registro.get(mod_id)
    if entrada is not None and not entrada.ligada:
        entrada.ligada = True
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


# -- ligar e desligar --------------------------------------------------------


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
    entrada.permissoes_aceitas = list(manifesto.permissoes)
    entrada.aviso_aceito = manifesto.aviso
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
    "INTERVALO_DA_ATUALIZACAO_S",
    "PRAZO_PARA_PARAR_S",
    "AvisoParaVerError",
    "Entrada",
    "InstalacaoRecusadaError",
    "Lugares",
    "Resultado",
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
    "origem_da_tag",
    "remover",
]

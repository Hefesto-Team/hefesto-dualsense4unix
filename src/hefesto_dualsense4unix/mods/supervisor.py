"""O supervisor das modificações: abre, vigia, reabre e para os processos.

O registro (``mods.json``) diz o que está ligado; o supervisor obedece. Cada
modificação ligada do tipo ``processo`` vira um processo filho do serviço:

* num grupo próprio (``setsid``), com ``PR_SET_PDEATHSIG``: se o serviço
  morre, o filho morre junto;
* com caixa quando o ``bwrap`` existe: raiz só de leitura, ``HOME`` vazia,
  código só de leitura, dados graváveis, o diretório de execução da sessão
  escondido (só a porta das modificações aparece), os processos num espaço de
  PID próprio (o que a modificação abrir morre com ela) e ``--unshare-net``
  quando a rede é ``nenhuma``. Sem ``bwrap``, roda sem caixa, e o estado diz
  isso numa linha;
* reaberto com espera crescente (:data:`ESPERAS_PARA_VOLTAR`) nas três
  primeiras quedas; na quarta, fica «parou», com a última linha do diário;
* parado com ``SIGTERM`` ao grupo e ``SIGKILL`` no fim do prazo, pelo PID que o
  supervisor criou, nunca por nome (o gesto ``para`` sem ``ligado: false`` em 300 ms também).

O estado vivo de cada uma vai para ``mods-estado.json`` no diretório de
execução, que a linha de comando e a tela leem.
"""
from __future__ import annotations

import asyncio
import contextlib
import ctypes
import json
import os
import secrets
import shutil
import signal
import time
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from hefesto_dualsense4unix.core.events import EventBus, EventTopic
from hefesto_dualsense4unix.mods import API_DAS_MODIFICACOES
from hefesto_dualsense4unix.mods.instalador import (
    CHAVES_OFICIAIS,
    Entrada,
    InstalacaoRecusadaError,
    Lugares,
    atualizar,
    aviso_por_ver,
    commit_novo,
    ler_registro,
)
from hefesto_dualsense4unix.mods.manifesto import (
    Manifesto,
    ManifestoRecusadoError,
    ler_manifesto,
    permissoes_novas,
)
from hefesto_dualsense4unix.mods.porta import (
    Controles,
    Escritor,
    OJogoEscreve,
    Porta,
    Pulsador,
    UniqDoPosto,
)
from hefesto_dualsense4unix.utils.logging_config import get_logger
from hefesto_dualsense4unix.utils.xdg_paths import (
    IPC_SOCKET_DEFAULT_NAME,
    ipc_socket_name,
    mods_socket_path,
)

logger = get_logger(__name__)

DIARIO_DA_MODIFICACAO = "diario.log"

TETO_DO_DIARIO_BYTES = 1 << 20

ESPERA_DO_DIARIO_S = 1.0

ESPERAS_PARA_VOLTAR: tuple[float, ...] = (1.0, 2.0, 4.0)

ESTAVEL_DEPOIS_DE_S = 60.0

PRAZO_PARA_PARAR_S = 3.0

INTERVALO_DO_REGISTRO_S = 1.0

PRAZO_DO_PARAR_CURTO_S = 0.3

PISO_DA_ATUALIZACAO_S = 60.0

ESPERA_DEPOIS_DA_FALHA_S = 600.0

ESPERA_DEPOIS_DO_SIGKILL_S = 2.0

ESPERA_DA_VIGIA_S = 1.0

ESCONDIDO_SEM_A_PERMISSAO: dict[str, tuple[str, ...]] = {
    "bluetooth": ("/run/dbus",),
}

_PR_SET_PDEATHSIG = 1


def _prctl() -> Callable[..., int] | None:
    """O ``prctl`` da libc já carregada no processo (a do próprio Python)."""
    funcao: Callable[..., int] | None = getattr(ctypes.CDLL(None, use_errno=True), "prctl", None)
    return funcao


def _comandos_do_lancador(manifesto: Manifesto) -> tuple[str, ...]:
    """Os ``lancador.comandos`` do manifesto: os únicos que um jogo de ``lancador.jogos`` abre."""
    if "lancador" not in manifesto.tipos or not isinstance(manifesto.lancador, dict):
        return ()
    comandos = manifesto.lancador.get("comandos")
    if not isinstance(comandos, list):
        return ()
    return tuple(c for c in comandos if isinstance(c, str) and c.strip())


def _acoes_dos_aparelhos(manifesto: Manifesto) -> tuple[str, ...]:
    """Os ids das ``aparelhos_acoes``: a porta recusa o controle de aparelho que repete um deles."""
    geridos = manifesto.aparelhos_acoes
    return tuple(a.id for a in geridos.acoes) if geridos else ()


def _morre_com_o_pai(prctl: Callable[..., int] | None) -> Callable[[], None]:
    """O ``preexec_fn`` do filho: ``PR_SET_PDEATHSIG`` com ``SIGKILL``.

    A função da libc é resolvida ANTES do ``fork``: no filho só a chamada roda.
    """

    def antes_de_executar() -> None:
        if prctl is not None:
            prctl(_PR_SET_PDEATHSIG, int(signal.SIGKILL), 0, 0, 0)

    return antes_de_executar


@dataclass
class EstadoDaModificacao:
    """A linha de uma modificação no ``mods-estado.json``."""

    estado: str
    pid: int | None = None
    caixa: str = ""
    motivo: str = ""
    ultima_linha: str = ""
    quedas: int = 0


@dataclass
class _Vigiada:
    mod_id: str
    tarefa: asyncio.Task[None] | None = None
    processo: asyncio.subprocess.Process | None = None
    copia: asyncio.Task[None] | None = None
    ficha: str = ""
    instalacao: tuple[str, str, str] = ("", "", "")
    quer_parar: asyncio.Event = field(default_factory=asyncio.Event)


def ultima_linha_do_diario(caminho: Path, *, teto: int = 200) -> str:
    """A última linha não vazia do diário (o que a tela mostra quando parou)."""
    try:
        with caminho.open("rb") as arquivo:
            arquivo.seek(0, os.SEEK_END)
            tamanho = arquivo.tell()
            arquivo.seek(max(0, tamanho - 4096))
            fim = arquivo.read().decode("utf-8", errors="replace")
    except OSError:
        return ""
    for linha in reversed(fim.splitlines()):
        if linha.strip():
            return linha.strip()[:teto]
    return ""


def _aparar_o_diario(caminho: Path, chegando: int = 0) -> None:
    """Com ``chegando`` bytes a mais passaria do teto: fica só a metade nova, de linha inteira.

    O diário é do supervisor: ninguém mais o abre, e só a cópia dele escreve.
    """
    if not caminho.is_file():
        return
    tamanho = caminho.stat().st_size
    if tamanho + chegando <= TETO_DO_DIARIO_BYTES:
        return
    corte = tamanho - TETO_DO_DIARIO_BYTES // 2
    if corte <= 0:
        return
    with caminho.open("rb") as arquivo:
        arquivo.seek(corte)
        resto = arquivo.read()
    quebra = resto.find(b"\n")
    caminho.write_bytes(resto[quebra + 1:] if quebra >= 0 else b"")


async def _copiar_para_o_diario(leitor: asyncio.StreamReader, caminho: Path) -> None:
    """A saída e o erro do processo vão para o diário sem passar do teto, até o fim do cano.

    O cano é lido até o fim mesmo quando o disco recusa a escrita: um cano parado trava o
    processo no ``print`` seguinte. A recusa vai ao log uma vez.
    """
    pedaco_max = max(1, TETO_DO_DIARIO_BYTES // 4)
    recusou = False
    while pedaco := await leitor.read(pedaco_max):
        try:
            _aparar_o_diario(caminho, len(pedaco))
            with caminho.open("ab") as diario:
                diario.write(pedaco)
        except OSError as exc:
            if not recusou:
                logger.warning("mods_diario_recusado", diario=str(caminho), err=str(exc))
            recusou = True


async def _esvaziar_a_copia(copia: asyncio.Task[None] | None, prazo: float) -> None:
    """Espera a cópia ler o que sobrou no cano; quem segura o cano além do prazo perde a cópia."""
    if copia is None:
        return
    await asyncio.wait({copia}, timeout=prazo)
    if not copia.done():
        copia.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await copia
    elif not copia.cancelled() and (erro := copia.exception()) is not None:
        logger.warning("mods_diario_falhou", err=str(erro))


def comando_na_caixa(
    *,
    bwrap: str,
    comando: list[str],
    codigo: Path,
    dados: Path,
    porta: Path,
    manifesto: Manifesto,
    casa: Path,
    execucao: tuple[Path, ...],
) -> list[str]:
    """A linha do ``bwrap`` para ``comando``.

    Os ``tmpfs`` vêm antes das pastas montadas por cima deles: a ``HOME`` e os
    diretórios de execução nascem vazios, e só o código (leitura), os dados
    (escrita) e a porta das modificações aparecem dentro deles.

    O ``--unshare-pid`` dá à caixa um espaço de PID próprio: quando o ``bwrap``
    sai, o kernel leva junto TUDO o que a modificação abriu. Sem ele, o
    ``--new-session`` põe o filho fora do grupo do PID criado, e o neto que a
    modificação deixasse de fundo sobrevivia ao «parar» (medido em 10/10/2026).
    """
    argv = [
        bwrap,
        "--ro-bind", "/", "/",
        "--unshare-pid",
        "--proc", "/proc",
        "--tmpfs", "/tmp",
        "--tmpfs", str(casa),
    ]
    for pasta in execucao:
        argv += ["--tmpfs", str(pasta)]
    if "aparelhos" in manifesto.permissoes:
        argv += ["--dev-bind", "/dev", "/dev"]
    else:
        argv += ["--dev", "/dev"]
    for permissao, caminhos in ESCONDIDO_SEM_A_PERMISSAO.items():
        if permissao not in manifesto.permissoes:
            argv += [arg for c in caminhos if Path(c).is_dir() for arg in ("--tmpfs", c)]
    argv += [
        "--ro-bind", str(codigo), str(codigo),
        "--bind", str(dados), str(dados),
        "--ro-bind", str(porta), str(porta),
    ]
    if manifesto.rede == "nenhuma":
        argv.append("--unshare-net")
    argv += ["--die-with-parent", "--new-session", "--chdir", str(codigo), "--", *comando]
    return argv


def _execucao_da_sessao(xdg: str | None, porta: Path) -> tuple[Path, ...]:
    """Os diretórios de execução que a caixa esconde.

    A porta mora em ``<execução da sessão>/<produto>/mods.sock``, ao lado do
    socket principal. Sem ``XDG_RUNTIME_DIR`` no ambiente, o ``platformdirs``
    ainda resolve ``/run/user/<uid>``, e não a ``HOME``: o avô da porta é o
    diretório que guarda o socket principal e os da sessão (barramento,
    servidor de som, Wayland), e ele se esconde junto com o ``XDG_RUNTIME_DIR``.
    """
    pastas: list[Path] = []
    for pasta in (Path(xdg) if xdg else None, porta.parent.parent):
        if pasta is not None and pasta != Path(pasta.anchor) and pasta not in pastas:
            pastas.append(pasta)
    return tuple(pastas)


def _resolver_o_comando(codigo: Path, executar: list[str]) -> list[str] | None:
    primeiro = codigo / executar[0]
    if primeiro.is_file():
        return [str(primeiro), *executar[1:]]
    if "/" not in executar[0]:
        achado = shutil.which(executar[0])
        if achado:
            return [achado, *executar[1:]]
    return None


def _instalacao(entrada: Entrada) -> tuple[str, str, str]:
    return (entrada.commit, entrada.instalada_em, entrada.ligada_em)


class Supervisor:
    """Obedece ao registro: abre o que está ligado, para o que não está."""

    def __init__(
        self,
        bus: EventBus,
        *,
        escritor: Escritor,
        o_jogo_escreve: OJogoEscreve,
        uniq_do_posto: UniqDoPosto,
        pulsador: Pulsador | None = None,
        controles: Controles | None = None,
        lugares: Lugares | None = None,
        porta: Path | None = None,
        bwrap: str | None = None,
        procurar_bwrap: bool = True,
        esperas: tuple[float, ...] = ESPERAS_PARA_VOLTAR,
        estavel_s: float = ESTAVEL_DEPOIS_DE_S,
        prazo_para_parar_s: float = PRAZO_PARA_PARAR_S,
        intervalo_s: float = INTERVALO_DO_REGISTRO_S,
        chaves: Sequence[str] = CHAVES_OFICIAIS,
    ) -> None:
        self.lugares = lugares or Lugares.do_xdg()
        self.porta = Porta(
            porta or mods_socket_path(),
            bus,
            escritor=escritor,
            o_jogo_escreve=o_jogo_escreve,
            uniq_do_posto=uniq_do_posto,
            pulsador=pulsador,
            controles=controles,
        )
        self.bwrap = bwrap or (shutil.which("bwrap") if procurar_bwrap else None)
        self.esperas = esperas
        self.estavel_s = estavel_s
        self.prazo_para_parar_s = prazo_para_parar_s
        self.intervalo_s = intervalo_s
        self._vigiadas: dict[str, _Vigiada] = {}
        self._estados: dict[str, EstadoDaModificacao] = {}
        self._laco: asyncio.Task[None] | None = None
        self._marca_do_registro: tuple[int, int] | None = None
        self._prctl = _prctl()
        self._gravou_o_estado = False
        self.bus = bus
        self.prazo_do_parar_curto_s = PRAZO_DO_PARAR_CURTO_S
        self._ouvinte_do_parar: asyncio.Task[None] | None = None
        self._parar_curtos: set[asyncio.Task[bool]] = set()
        self.chaves = tuple(chaves)
        self.piso_da_atualizacao_s = PISO_DA_ATUALIZACAO_S
        self.espera_depois_da_falha_s = ESPERA_DEPOIS_DA_FALHA_S
        self._proxima_conferencia: dict[str, float] = {}
        self._registro_lido: dict[str, Entrada] = {}
        self._atualizando: asyncio.Task[bool] | None = None

    def estado_de(self, mod_id: str) -> EstadoDaModificacao | None:
        return self._estados.get(mod_id)

    def pid_de(self, mod_id: str) -> int | None:
        vigiada = self._vigiadas.get(mod_id)
        processo = vigiada.processo if vigiada else None
        return processo.pid if processo is not None and processo.returncode is None else None

    def _marcar(self, mod_id: str, estado: EstadoDaModificacao) -> None:
        self._estados[mod_id] = estado
        self._gravar_estado()

    def _gravar_estado(self) -> None:
        corpo = {
            "api": API_DAS_MODIFICACOES,
            "caixa": "bwrap" if self.bwrap else "",
            "mods": {k: asdict(v) for k, v in sorted(self._estados.items())},
        }
        caminho = self.lugares.estado
        try:
            caminho.parent.mkdir(parents=True, exist_ok=True)
            temporario = caminho.with_name(f".{caminho.name}.{os.getpid()}")
            temporario.write_text(json.dumps(corpo, ensure_ascii=False), encoding="utf-8")
            os.chmod(temporario, 0o600)
            os.replace(temporario, caminho)
            self._gravou_o_estado = True
        except OSError as exc:
            logger.warning("mods_estado_nao_gravou", err=str(exc))

    async def iniciar(self) -> None:
        await self.reconciliar()
        self._laco = asyncio.create_task(self._vigiar_o_registro(), name="mods-registro")
        fila = self.bus.subscribe(EventTopic.ACESSORIOS_GESTO)
        self._ouvinte_do_parar = asyncio.create_task(
            self._ouvir_o_parar(fila), name="mods-parar-curto"
        )

    async def parar(self) -> None:
        laco, self._laco = self._laco, None
        ouvinte, self._ouvinte_do_parar = self._ouvinte_do_parar, None
        atualizando, self._atualizando = self._atualizando, None
        for tarefa in (laco, ouvinte, atualizando, *self._parar_curtos):
            if tarefa is not None:
                tarefa.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await tarefa
        await asyncio.gather(
            *(self._parar_uma(mod_id) for mod_id in list(self._vigiadas)),
            return_exceptions=True,
        )
        await self.porta.parar()
        if self._gravou_o_estado:
            with contextlib.suppress(FileNotFoundError):
                self.lugares.estado.unlink()

    async def _ouvir_o_parar(self, fila: asyncio.Queue[Any]) -> None:
        """O gesto ``para`` abre uma conferência de :attr:`prazo_do_parar_curto_s`."""
        try:
            while True:
                gesto = await fila.get()
                if isinstance(gesto, dict) and gesto.get("gesto") == "para":
                    alvo = gesto.get("mod") if isinstance(gesto.get("mod"), str) else None
                    tarefa = asyncio.create_task(
                        self.conferir_o_parar(alvo), name="mods-parar-curto-1"
                    )
                    self._parar_curtos.add(tarefa)
                    tarefa.add_done_callback(self._parar_curtos.discard)
        finally:
            self.bus.unsubscribe(EventTopic.ACESSORIOS_GESTO, fila)

    async def conferir_o_parar(self, mod: str | None = None) -> bool:
        """Depois do ``para``, a modificação devolveu ``ligado: false`` a tempo? Senão, é encerrada.

        Devolve ``True`` quando o supervisor a encerrou. Quem já estava desligada (``ligado: false``
        antes do gesto) ou não tem processo do supervisor fica como está. Sempre pelo PID que o
        supervisor criou, nunca por nome; a vigia reabre a modificação como reabre qualquer queda.
        ``mod`` é o alvo do «Parar tudo» da janela: o estado de outra extensão não é conferido.
        """
        antes = self._estado_para_o_parar(mod)
        if not isinstance(antes, dict) or antes.get("ligado") is False:
            return False
        await asyncio.sleep(self.prazo_do_parar_curto_s)
        depois = self._estado_para_o_parar(mod)
        if isinstance(depois, dict) and depois is not antes and depois.get("ligado") is False:
            return False
        vigiada = self._vigiadas.get(str(antes.get("mod", "")))
        processo = vigiada.processo if vigiada is not None else None
        if processo is None or processo.returncode is not None:
            return False
        logger.warning("mods_parar_curto", mod=antes.get("mod"), pid=processo.pid)
        await parar_o_grupo(processo, self.prazo_para_parar_s)
        return True

    def _estado_para_o_parar(self, mod: str | None) -> Any:
        """O último estado que o parar confere: o do barramento, ou o da extensão ``mod``."""
        if mod is None:
            return self.bus.ultimo(EventTopic.ACESSORIOS_ESTADO)
        return self.porta.ultimo_estado_de(mod)

    async def _vigiar_o_registro(self) -> None:
        while True:
            await asyncio.sleep(self.intervalo_s)
            await self._conferir_o_registro()
            self._talvez_atualizar()

    def _talvez_atualizar(self) -> None:
        """Abre a conferência da primeira extensão do git cujo intervalo passou.

        Uma por vez, numa tarefa à parte: o ``atualizar`` desliga a extensão viva e espera
        a vigia pará-la, e a vigia é esta volta, que não pode esperar por ele.
        """
        if self._atualizando is not None and not self._atualizando.done():
            return
        registro = self._registro_lido
        agora = time.monotonic()
        for mod_id in [m for m in self._proxima_conferencia if m not in registro]:
            self._proxima_conferencia.pop(mod_id, None)
        for entrada in registro.values():
            if entrada.origem == "local" or not entrada.atualiza_sozinha:
                continue
            if agora < self._proxima_conferencia.get(entrada.id, agora):
                continue
            self._atualizando = asyncio.create_task(
                self.atualizar_sozinha(entrada), name="mods-atualizar-sozinha"
            )
            return

    async def atualizar_sozinha(self, entrada: Entrada) -> bool:
        """Pergunta ao endereço se há commit novo e, havendo, atualiza como o «Atualizar».

        Devolve ``True`` quando o código trocou. Sem rede, sem novidade ou com a versão nova
        esperando o «Atualizar» (permissão nova, tag que deixou de ser a oficial), a extensão
        fica na versão de agora, viva como estava.
        """
        intervalo = max(float(entrada.intervalo_da_atualizacao_s), self.piso_da_atualizacao_s)
        self._proxima_conferencia[entrada.id] = time.monotonic() + intervalo
        try:
            novo = await asyncio.to_thread(commit_novo, entrada)
            if novo is None:
                return False
            feito = await asyncio.to_thread(
                atualizar, entrada.id, lugares=self.lugares, chaves=self.chaves, sozinha=True
            )
        except InstalacaoRecusadaError as exc:
            logger.warning("mods_atualizacao_recusada", mod=entrada.id, err=exc.frase)
        except Exception as exc:
            logger.warning("mods_atualizacao_falhou", mod=entrada.id, err=str(exc), exc_info=True)
        else:
            if feito.trocou:
                logger.info("mods_atualizada_sozinha", mod=entrada.id, versao=feito.entrada.versao)
            else:
                logger.info(
                    "mods_versao_esperando", mod=entrada.id, motivo=feito.entrada.motivo_da_espera
                )
            return feito.trocou
        espera = min(intervalo, max(self.espera_depois_da_falha_s, self.piso_da_atualizacao_s))
        self._proxima_conferencia[entrada.id] = time.monotonic() + espera
        return False

    async def _conferir_o_registro(self) -> None:
        """Uma volta da vigia: o registro mudou (outro mtime ou outro inode)?"""
        try:
            if self._marca() != self._marca_do_registro:
                await self.reconciliar()
        except Exception as exc:
            logger.warning("mods_registro_falhou", err=str(exc), exc_info=True)

    def _marca(self) -> tuple[int, int] | None:
        if not self.lugares.registro.is_file():
            return None
        st = self.lugares.registro.stat()
        return (st.st_mtime_ns, st.st_ino)

    async def reconciliar(self) -> None:
        """Lê o registro e põe os processos de acordo com ele."""
        self._marca_do_registro = self._marca()
        try:
            registro = ler_registro(self.lugares.registro)
        except InstalacaoRecusadaError as exc:
            logger.warning("mods_registro_ilegivel", err=exc.frase)
            self._registro_lido = {}
            return
        self._registro_lido = registro
        ligadas = {k: v for k, v in registro.items() if v.ligada}
        for mod_id in [m for m in self._vigiadas if m not in ligadas]:
            await self._parar_uma(mod_id)
        for mod_id in [m for m in self._estados if m not in registro]:
            self._estados.pop(mod_id, None)
        for mod_id, entrada in registro.items():
            if not entrada.ligada:
                self._estados[mod_id] = EstadoDaModificacao("desligada")
        for mod_id, entrada in ligadas.items():
            vigiada = self._vigiadas.get(mod_id)
            if vigiada is None or vigiada.instalacao != _instalacao(entrada):
                await self._comecar(entrada)
        if self._estados or self._gravou_o_estado:
            self._gravar_estado()

    def _o_que_impede(self, entrada: Entrada) -> tuple[str, Manifesto | None]:
        try:
            manifesto = ler_manifesto(self.lugares.codigo / entrada.id)
        except ManifestoRecusadoError as exc:
            return exc.frase, None
        novas = permissoes_novas(entrada.permissoes_aceitas, manifesto.permissoes)
        if novas:
            return (
                f"«{manifesto.nome}» pede {', '.join(novas)}, que ainda não teve o «sim».",
                None,
            )
        if aviso_por_ver(entrada, manifesto):
            return f"«{manifesto.nome}» traz um aviso que ainda não teve o «sim».", None
        return "", manifesto

    async def _comecar(self, entrada: Entrada) -> None:
        if entrada.id in self._vigiadas:
            await self._parar_uma(entrada.id)
        motivo, manifesto = self._o_que_impede(entrada)
        if manifesto is None:
            self._estados[entrada.id] = EstadoDaModificacao("recusada", motivo=motivo)
            return
        if manifesto.processo is None:
            self._estados[entrada.id] = EstadoDaModificacao("declarativa")
            return
        if not self.porta.aberta:
            await self.porta.iniciar()
        vigiada = _Vigiada(entrada.id, instalacao=_instalacao(entrada))
        self._vigiadas[entrada.id] = vigiada
        vigiada.tarefa = asyncio.create_task(
            self._cuidar(vigiada, manifesto), name=f"mods-{entrada.id}"
        )

    async def _cuidar(self, vigiada: _Vigiada, manifesto: Manifesto) -> None:
        mod_id = vigiada.mod_id
        quedas = 0
        diario = self.lugares.dados / mod_id / DIARIO_DA_MODIFICACAO
        caixa = "bwrap" if self.bwrap else ""
        sem_caixa = "" if self.bwrap else "Roda sem caixa: o bwrap não está instalado."
        while not vigiada.quer_parar.is_set():
            self._marcar(mod_id, EstadoDaModificacao(
                "ligando" if quedas == 0 else "voltando",
                caixa=caixa, motivo=sem_caixa, quedas=quedas))
            try:
                processo = await self._abrir(vigiada, manifesto, diario)
            except (OSError, ValueError) as exc:
                self._marcar(mod_id, EstadoDaModificacao(
                    "parou", caixa=caixa, motivo=f"Não abriu: {exc}", quedas=quedas))
                return
            self._marcar(mod_id, EstadoDaModificacao(
                "rodando", pid=processo.pid, caixa=caixa, motivo=sem_caixa, quedas=quedas))
            aberto_em = time.monotonic()
            codigo = await processo.wait()
            copia, vigiada.copia = vigiada.copia, None
            await _esvaziar_a_copia(copia, ESPERA_DO_DIARIO_S)
            self.porta.esquecer(vigiada.ficha)
            if vigiada.quer_parar.is_set():
                return
            if time.monotonic() - aberto_em >= self.estavel_s:
                quedas = 0
            quedas += 1
            ultima = ultima_linha_do_diario(diario)
            logger.warning("mods_caiu", mod=mod_id, codigo=codigo, quedas=quedas)
            if quedas > len(self.esperas):
                self._marcar(mod_id, EstadoDaModificacao(
                    "parou",
                    caixa=caixa,
                    motivo=f"Caiu {quedas} vezes seguidas (código {codigo}).",
                    ultima_linha=ultima,
                    quedas=quedas,
                ))
                return
            self._marcar(mod_id, EstadoDaModificacao(
                "voltando", caixa=caixa, motivo=f"Caiu (código {codigo}).",
                ultima_linha=ultima, quedas=quedas))
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(
                    vigiada.quer_parar.wait(), timeout=self.esperas[quedas - 1]
                )

    async def _abrir(
        self, vigiada: _Vigiada, manifesto: Manifesto, diario: Path
    ) -> asyncio.subprocess.Process:
        assert manifesto.processo is not None
        codigo = self.lugares.codigo / manifesto.id
        dados = self.lugares.dados / manifesto.id
        dados.mkdir(parents=True, exist_ok=True)
        comando = _resolver_o_comando(codigo, manifesto.processo.executar)
        if comando is None:
            raise ValueError(f"o comando {manifesto.processo.executar[0]} não existe")
        vigiada.ficha = secrets.token_urlsafe(32)
        casa = Path(os.environ.get("HOME") or "/nonexistent")
        execucao_bruta = os.environ.get("XDG_RUNTIME_DIR")
        ambiente = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "LANG": os.environ.get("LANG", "C.UTF-8"),
            "HOME": str(casa),
            "PYTHONDONTWRITEBYTECODE": "1",
            "HEFESTO_MOD_ID": manifesto.id,
            "HEFESTO_MOD_SOCKET": str(self.porta.caminho),
            "HEFESTO_MOD_FICHA": vigiada.ficha,
            "HEFESTO_MOD_DADOS": str(dados),
            "HEFESTO_MOD_API": str(API_DAS_MODIFICACOES),
        }
        if execucao_bruta:
            ambiente["XDG_RUNTIME_DIR"] = execucao_bruta
        if self.bwrap:
            argv = comando_na_caixa(
                bwrap=self.bwrap,
                comando=comando,
                codigo=codigo,
                dados=dados,
                porta=self.porta.caminho,
                manifesto=manifesto,
                casa=casa,
                execucao=_execucao_da_sessao(execucao_bruta, self.porta.caminho),
            )
        else:
            argv = comando
        _aparar_o_diario(diario)
        processo = await asyncio.create_subprocess_exec(
            *argv,
            cwd=str(codigo),
            env=ambiente,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            start_new_session=True,
            preexec_fn=_morre_com_o_pai(self._prctl),
        )
        vigiada.processo = processo
        assert processo.stdout is not None
        vigiada.copia = asyncio.create_task(
            _copiar_para_o_diario(processo.stdout, diario), name=f"mods-diario-{manifesto.id}"
        )
        self.porta.registrar(vigiada.ficha, manifesto.id, processo.pid, manifesto.permissoes,
                             comandos=_comandos_do_lancador(manifesto),
                             acoes_dos_aparelhos=_acoes_dos_aparelhos(manifesto))
        logger.info("mods_aberta", mod=manifesto.id, pid=processo.pid, caixa=bool(self.bwrap))
        return processo

    async def _parar_uma(self, mod_id: str) -> None:
        vigiada = self._vigiadas.pop(mod_id, None)
        if vigiada is None:
            return
        vigiada.quer_parar.set()
        processo = vigiada.processo
        if processo is not None and processo.returncode is None:
            await parar_o_grupo(processo, self.prazo_para_parar_s)
        if vigiada.tarefa is not None:
            await asyncio.wait({vigiada.tarefa}, timeout=ESPERA_DA_VIGIA_S)
        copia, vigiada.copia = vigiada.copia, None
        await _esvaziar_a_copia(copia, 0)
        self.porta.esquecer(vigiada.ficha)
        self._marcar(mod_id, EstadoDaModificacao("desligada"))


async def parar_o_grupo(processo: asyncio.subprocess.Process, prazo: float) -> int | None:
    """``SIGTERM`` ao grupo do PID criado; ``SIGKILL`` no fim do prazo."""
    pid = processo.pid
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(pid, signal.SIGTERM)
    espera = asyncio.ensure_future(processo.wait())
    await asyncio.wait({espera}, timeout=prazo)
    if not espera.done():
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(pid, signal.SIGKILL)
        await asyncio.wait({espera}, timeout=ESPERA_DEPOIS_DO_SIGKILL_S)
    if not espera.done():
        espera.cancel()
        return None
    return espera.result()


def supervisor_do_servico(daemon: Any) -> Supervisor | None:
    """O supervisor ligado ao serviço vivo (barramento, IPC e estado do jogo).

    ``None`` na instância isolada (o ``--fake`` e todo socket de nome próprio):
    ela divide a casa com o serviço de verdade, e abrir as modificações dali
    trocaria a porta dele pela sua e abriria cada modificação duas vezes. É a
    mesma regra que já isola o socket e a trava de instância do ``--fake``.
    """
    if ipc_socket_name() != IPC_SOCKET_DEFAULT_NAME:
        logger.info("mods_fora_da_instancia_isolada", socket=ipc_socket_name())
        return None
    from hefesto_dualsense4unix.mods.porta import (
        controles_no_servico,
        escritor_do_servico,
        o_jogo_escreve_no_servico,
        pulsar_no_servico,
        uniq_do_posto_no_servico,
    )

    return Supervisor(
        daemon.bus,
        escritor=escritor_do_servico(daemon),
        o_jogo_escreve=o_jogo_escreve_no_servico(daemon),
        uniq_do_posto=uniq_do_posto_no_servico(daemon),
        pulsador=pulsar_no_servico(daemon),
        controles=controles_no_servico(daemon),
    )


__all__ = [
    "DIARIO_DA_MODIFICACAO",
    "ESCONDIDO_SEM_A_PERMISSAO",
    "ESPERAS_PARA_VOLTAR",
    "ESPERA_DA_VIGIA_S",
    "ESPERA_DEPOIS_DO_SIGKILL_S",
    "ESPERA_DO_DIARIO_S",
    "ESTAVEL_DEPOIS_DE_S",
    "PRAZO_DO_PARAR_CURTO_S",
    "PRAZO_PARA_PARAR_S",
    "EstadoDaModificacao",
    "Supervisor",
    "comando_na_caixa",
    "parar_o_grupo",
    "supervisor_do_servico",
    "ultima_linha_do_diario",
]

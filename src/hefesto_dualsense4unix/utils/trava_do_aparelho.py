"""A trava que impede os DOIS Hefestos de segurarem o mesmo controle.

Pedido dela, 29/08/2026, e é o que ela marcou como mais importante dos três:
*"E temos que evitar estar rodando os daemon ao mesmo tempo que a versão
dev."* A exigência que veio junto é estrutural: **não pode depender de ela
lembrar de desligar**.

O QUE JÁ EXISTIA, E POR QUE NÃO ALCANÇA — MEDIDO EM 29/08/2026
---------------------------------------------------------------
O ``utils/single_instance.py`` trava por ``flock`` num pid file, e funciona.
Só que o pid file sai do ``runtime_dir()``, que sai do slug da variante
(``utils/xdg_paths.py``). Com as duas casas separadas, os caminhos são::

    estável : /run/user/1000/hefesto-dualsense4unix/daemon.pid
    dev     : /run/user/1000/hefesto-dev-dualsense4unix/daemon.pid

Dois arquivos, dois ``flock``: o estável no ar e o de dev subindo **não se
veem**. A separação de casas isolou perfis, config e socket — o que é certo —
e no mesmo gesto isolou o lock, que é o que este módulo devolve.

As outras candidatas foram medidas e nenhuma serve:

- **``O_EXCL`` no hidraw não existe** — o caminho é ``os.open(path,
  os.O_RDWR)`` (``core/backend_pydualsense.py``, ``core/physical_report_
  reader.py``). Não há exclusividade a herdar.
- **O broker não arbitra: ele foi DESENHADO para tolerar dois**
  (``broker/hidraw_broker.py``: *"Dois daemons em takeover convivem"*). Os
  dois pedem o fd, os dois recebem.
- **Os sockets IPC não colidem** — caminhos distintos pelos mesmos slugs, de
  modo que o segundo daemon não acha o socket do primeiro e não desiste.
- **``Conflicts=`` na unit** só enxerga systemd. Não vê o ``Popen`` da GUI
  (``app/actions/daemon_actions.py:_start_service_blocking``) nem o
  ``run.sh``, que é como ela e um agente testam — e "parar a outra calada" é
  o defeito que esta casa recusa.

Sobra o ``flock`` num caminho **sem slug**, que é o que está aqui: um arquivo
só para as duas casas, e por isso alcança systemd, ``Popen``, ``run.sh`` e o
comando no terminal com a mesma régua.

A ARMADILHA, E ELA É A RAZÃO DE ESTE MÓDULO SER "CIENTE DA CASA"
-----------------------------------------------------------------
Uma trava ingênua ("se o arquivo está travado, recuse") **quebra o produto
dela**: o reinício normal do daemon dela — ``systemctl --user restart``, a
GUI subindo o daemon, o ``BUG-MULTI-INSTANCE-01`` de sempre — é exatamente
"um segundo daemon subindo com o primeiro no ar". Recusar ali seria trocar
uma disputa que ela nunca vê por um daemon que não sobe mais.

Por isso o arquivo guarda **pid e casa**, e a decisão é por casa:

- dono da **mesma** casa → segue o caminho de sempre (``acquire_or_takeover``
  mata o predecessor e a vida continua);
- dono da **outra** casa → **recusa**, dizendo o nome do outro Hefesto, o pid
  dele e o gesto exato que o desliga.

A ORDEM DAS DUAS FASES TAMBÉM É REQUISITO
------------------------------------------
``conferir_antes_do_takeover`` roda **antes** do ``acquire_or_takeover``, pela
mesma razão já escrita em ``daemon/main.py``: quem vai recusar não pode ter
matado o predecessor da própria casa primeiro. ``tomar`` roda **depois**,
quando o predecessor da própria casa já saiu e soltou o ``flock``.

O QUE A TRAVA COBRE E O QUE ELA NÃO COBRE
------------------------------------------
Cobre o caso perigoso por construção: o daemon **pausado** segura a trava
igual, porque ``daemon.pause`` não solta nada (``daemon/lifecycle.py``: *"O
daemon segue vivo: lê estado/bateria, publica STATE_UPDATE e atende o IPC"*).
Medido: um dono congelado com ``SIGSTOP`` continua recusando, porque o
``flock`` é do processo e não do "está despachando"; e ``kill -9`` no dono
**não** deixa lixo, porque o kernel solta o ``flock`` na saída.

Não cobre daemon **fake** nem socket isolado, de propósito: ``run.sh --fake``,
os smokes e a suíte sobem daemons que não tocam hardware nenhum, e uma trava
global tomada por eles bloquearia o daemon de verdade dela. O critério é o
mesmo do ``single_instance``: só o socket de PRODUÇÃO trava.

FALHA ABERTA, SEMPRE
---------------------
Erro inesperado aqui (runtime dir somente-leitura, ``flock`` indisponível,
arquivo ilegível) **não** impede o daemon de subir: registra e segue, que é
exatamente o comportamento de antes deste módulo. Uma trava que brica o
daemon dela seria pior que a disputa que ela evita.
"""
from __future__ import annotations

import contextlib
import errno
import fcntl
import importlib
import os
import time
from dataclasses import dataclass
from pathlib import Path

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: O nome é uma frase curta e não uma sigla: quem topar com este arquivo num
#: ``ls`` do runtime dir tem de entender na hora o que ele guarda.
NOME_DA_TRAVA = "hefesto-o-aparelho.lock"

#: As duas casas. O valor é o que vai gravado no arquivo — sem acento, para
#: que a leitura não dependa de encoding de ninguém.
CASA_ESTAVEL = "estavel"
CASA_DEV = "dev"

#: Como cada casa se chama numa frase para ela ler.
NOME_DA_CASA = {
    CASA_ESTAVEL: "Hefesto ESTÁVEL",
    CASA_DEV: "Hefesto de DESENVOLVIMENTO",
}

#: O slug do ``platformdirs`` de cada casa — é por ele que se acha o
#: ``config_dir`` da OUTRA casa (para saber se ela está pausada). Espelha
#: ``utils/identidade.py``; ``test_o_slug_da_casa_estavel_e_o_que_o_produto_usa``
#: amarra o do estável ao slug que o produto realmente usa.
SLUG_DA_CASA = {
    CASA_ESTAVEL: "hefesto-dualsense4unix",
    CASA_DEV: "hefesto-dev-dualsense4unix",
}

#: O gesto que desliga cada casa, escrito na frase da recusa.
GESTO_QUE_LIBERA = {
    CASA_ESTAVEL: (
        'o botão "Desligar até eu reativar", na aba Status do Hefesto estável\n'
        "               (ou, no terminal:  scripts/hefesto-chave.sh estavel off)"
    ),
    CASA_DEV: "scripts/hefesto-chave.sh dev off",
}

#: Segundos que ``tomar`` espera o ``flock`` da própria casa ser solto. O
#: predecessor já foi morto pelo ``acquire_or_takeover`` (SIGTERM com 2 s de
#: graça, depois SIGKILL) antes de chegarmos aqui, então isto é folga, não
#: espera de verdade.
ESPERA_MAXIMA_S = 2.5
_INTERVALO_S = 0.05

#: Segundos que ``dono_agora`` insiste quando o arquivo está travado mas o
#: conteúdo ainda não foi escrito (a janela entre o ``flock`` e o ``write`` do
#: dono). Sem isto, uma corrida de milissegundos viraria recusa por engano.
ESPERA_DO_CONTEUDO_S = 0.2

#: O fd que este processo segura enquanto vive. Global pelo mesmo motivo do
#: ``single_instance``: fechar o fd solta o ``flock``, e o GC fecharia.
_FD_SEGURO: int | None = None

VARIANTE_ENV = "HEFESTO_VARIANTE"


@dataclass(frozen=True)
class Dono:
    """Quem está com o aparelho agora, segundo o arquivo da trava."""

    casa: str
    pid: int | None

    @property
    def nome(self) -> str:
        return NOME_DA_CASA.get(self.casa, f"Hefesto ({self.casa})")


class OutraCasaComOAparelhoError(RuntimeError):
    """O outro Hefesto está com o controle. Carrega o recado pronto."""

    def __init__(self, dono: Dono, recado: str) -> None:
        super().__init__(recado)
        self.dono = dono
        self.recado = recado


# --------------------------------------------------------------------------
# Onde a trava mora, e de quem é este processo
# --------------------------------------------------------------------------
def caminho_da_trava() -> Path:
    """O arquivo da trava — **fora** do slug das duas casas, de propósito.

    ``xdg_paths.runtime_dir()`` não serve aqui: ele já é ``…/<slug>/``, que é
    justamente a separação que faz as duas casas não se enxergarem. O que se
    quer é o diretório PAI, comum às duas.
    """
    bruto = os.environ.get("XDG_RUNTIME_DIR", "").strip()
    if bruto:
        return Path(bruto) / NOME_DA_TRAVA
    padrao = Path(f"/run/user/{os.getuid()}")
    if padrao.is_dir():
        return padrao / NOME_DA_TRAVA
    import tempfile

    return Path(tempfile.gettempdir()) / f"hefesto-o-aparelho-{os.getuid()}.lock"


def casa_atual() -> str:
    """A casa DESTE processo: ``"estavel"`` ou ``"dev"``.

    Prefere ``utils/identidade.py`` quando ele existe — é o dono do assunto.
    O fallback repete a MESMA regra (``strip().casefold() == "dev"``) para
    esta trava valer também nas instalações que ainda não têm o módulo, sem
    criar uma segunda verdade sobre o que é a casa de dev.
    """
    try:
        identidade = importlib.import_module(
            "hefesto_dualsense4unix.utils.identidade"
        )
    except Exception:  # pragma: no cover - só nas árvores sem o módulo
        pass
    else:
        variante = getattr(identidade.atual(), "variante", "")
        return CASA_DEV if variante == CASA_DEV else CASA_ESTAVEL
    bruto = os.environ.get(VARIANTE_ENV, "") or ""
    return CASA_DEV if bruto.strip().casefold() == CASA_DEV else CASA_ESTAVEL


def a_trava_se_aplica() -> bool:
    """False para daemon fake / socket isolado — e isso é decisão medida.

    A suíte, os smokes e o ``run.sh --fake`` sobem daemons que **não tocam
    hardware nenhum**. Se eles tomassem a trava global, um teste rodando
    impediria o daemon de verdade dela de subir. O critério é o mesmo que o
    ``single_instance`` já usa para não deixar um fake matar o real: só o
    socket de PRODUÇÃO conta.
    """
    from hefesto_dualsense4unix.utils.xdg_paths import (
        IPC_SOCKET_DEFAULT_NAME,
        ipc_socket_name,
    )

    return ipc_socket_name() == IPC_SOCKET_DEFAULT_NAME


# --------------------------------------------------------------------------
# Ler quem está com o aparelho
# --------------------------------------------------------------------------
def _analisar(texto: str) -> Dono | None:
    linhas = [ln.strip() for ln in texto.splitlines() if ln.strip()]
    if len(linhas) < 2:
        return None
    pid_bruto, casa = linhas[0], linhas[1]
    pid = int(pid_bruto) if pid_bruto.isdigit() else None
    if casa not in NOME_DA_CASA:
        return None
    return Dono(casa=casa, pid=pid)


# --------------------------------------------------------------------------
# A SEGUNDA RÉGUA: o pid file da outra casa
# --------------------------------------------------------------------------
# POR QUE DUAS, E POR QUE ESTA É A QUE FUNCIONA HOJE (29/08/2026)
# ----------------------------------------------------------------
# O ``flock`` acima só enxerga quem TOMA a trava — isto é, quem já tem este
# módulo. Medido em 29/08: o Hefesto de dev roda na máquina dela AGORA
# (`hefesto-dev-dualsense4unix.service`, ativo), a partir de uma árvore que
# ainda não tem este arquivo. Uma trava que dependesse só do ``flock`` seria
# uma cura escrita e nunca ligada — o defeito mais caro desta casa — até o
# outro lado ser atualizado.
#
# Esta régua não precisa da colaboração do outro: ela lê o ``daemon.pid`` que o
# ``single_instance`` de QUALQUER versão já escreve, e confere no ``/proc`` que
# o processo está vivo e é mesmo da outra casa. Duas réguas independentes é
# regra desta casa, e aqui elas se cobrem em direções diferentes: o ``flock``
# pega o caso do daemon avulso sem pid file confiável; o pid file pega o
# daemon que ainda não conhece a trava.
def _casa_do_processo(pid: int) -> str | None:
    """A casa de um pid vivo, pela MESMA regra de ``casa_atual`` — ou ``None``.

    Lê ``/proc/<pid>/environ``, que é onde o ``Environment=HEFESTO_VARIANTE=dev``
    da unit de dev chega (conferido na máquina dela em 29/08). Exige antes que
    a linha de comando diga ``hefesto`` **e** ``daemon``: sem isso, um pid
    RECICLADO por um processo qualquer viraria uma recusa falsa, e recusa falsa
    aqui é o daemon dela não subir.

    As DUAS palavras, e não só a primeira — medido em 29/08: ``hefesto``
    sozinho não filtra nada nesta bancada, porque o interpretador mora em
    ``…/hefesto-dualsense4unix/.venv/bin/python`` e QUALQUER script dela casa.
    ``daemon`` está nas três formas de subir o daemon (unit, console script e
    o ``python -m … daemon start`` do fallback da GUI) e em nenhuma outra.
    """
    try:
        bruto = Path(f"/proc/{pid}/cmdline").read_bytes().lower()
    except OSError:
        return None
    if b"hefesto" not in bruto or b"daemon" not in bruto:
        return None
    try:
        ambiente = Path(f"/proc/{pid}/environ").read_bytes()
    except OSError:
        # Sem o environ não dá para saber a casa. Não se chuta: quem chama
        # confere o resultado contra a casa que esperava, e ``None`` = calado.
        return None
    alvo = (VARIANTE_ENV + "=").encode()
    for item in ambiente.split(b"\0"):
        if item.startswith(alvo):
            valor = item[len(alvo):].decode("utf-8", "replace")
            return CASA_DEV if valor.strip().casefold() == CASA_DEV else CASA_ESTAVEL
    return CASA_ESTAVEL


def _dono_pelo_pid_file(casa: str, base: Path) -> Dono | None:
    """O daemon da casa ``casa`` está vivo, segundo o pid file dele?"""
    alvo = base / SLUG_DA_CASA[casa] / "daemon.pid"
    try:
        bruto = alvo.read_text(encoding="ascii", errors="replace").strip()
    except OSError:
        return None
    if not bruto.isdigit():
        return None
    pid = int(bruto)
    from hefesto_dualsense4unix.utils.single_instance import is_alive

    if not is_alive(pid):
        return None
    if _casa_do_processo(pid) != casa:
        return None
    return Dono(casa=casa, pid=pid)


def dono_agora(
    caminho: Path | None = None, espera_do_conteudo: float | None = None
) -> Dono | None:
    """Quem segura a trava agora, ou ``None`` se ela está livre.

    Testa por ``flock`` não-bloqueante, que é a única leitura honesta: o
    conteúdo do arquivo sozinho mentiria depois de um ``kill -9`` (o kernel
    solta o ``flock``, o texto fica). Se o ``flock`` está livre, o texto é
    lixo de um dono que já morreu, e a resposta é ``None``.
    """
    alvo = caminho if caminho is not None else caminho_da_trava()
    paciencia = (
        ESPERA_DO_CONTEUDO_S if espera_do_conteudo is None else espera_do_conteudo
    )
    limite = time.monotonic() + paciencia
    while True:
        try:
            fd = os.open(str(alvo), os.O_CREAT | os.O_RDWR, 0o600)
        except OSError as exc:
            logger.warning("trava_do_aparelho_sem_arquivo", erro=str(exc))
            return None
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                if exc.errno not in (errno.EWOULDBLOCK, errno.EAGAIN):
                    logger.warning("trava_do_aparelho_flock_indisponivel",
                                   erro=str(exc))
                    return None
                # Travado por alguém. Quem?
                with contextlib.suppress(OSError):
                    os.lseek(fd, 0, os.SEEK_SET)
                bruto = os.read(fd, 4096).decode("utf-8", "replace")
                dono = _analisar(bruto)
                if dono is not None:
                    return dono
                # Conteúdo ainda não escrito (a janela entre o `flock` e o
                # `write` do dono). Insiste um pouco; desistir aqui é FALHAR
                # ABERTO de propósito — não se recusa o boot dela por causa
                # de um arquivo que não deu para ler.
                if time.monotonic() >= limite:
                    logger.warning("trava_do_aparelho_dono_ilegivel")
                    return None
            else:
                # Conseguimos travar: ninguém segurava. Solta na hora — esta
                # função é só uma sonda, quem toma de verdade é `tomar`.
                with contextlib.suppress(OSError):
                    fcntl.flock(fd, fcntl.LOCK_UN)
                # O flock livre NÃO quer dizer "ninguém com o aparelho": quer
                # dizer "ninguém que conheça esta trava". A segunda régua.
                return _outra_casa_pelo_pid_file(alvo.parent)
        finally:
            with contextlib.suppress(OSError):
                os.close(fd)
        time.sleep(_INTERVALO_S)


def _outra_casa_pelo_pid_file(base: Path) -> Dono | None:
    """A outra casa está com o aparelho, mesmo sem tomar a trava?"""
    minha = casa_atual()
    for casa in (CASA_ESTAVEL, CASA_DEV):
        if casa == minha:
            continue
        dono = _dono_pelo_pid_file(casa, base)
        if dono is not None:
            return dono
    return None


def _esta_pausado(casa: str) -> bool:
    """A outra casa está PAUSADA? (só para escrever a frase certa)

    Best-effort e calado: qualquer erro devolve False e a recusa sai na sua
    forma simples.
    """
    try:
        from platformdirs import PlatformDirs

        slug = SLUG_DA_CASA.get(casa)
        if slug is None:
            return False
        return (Path(PlatformDirs(slug).user_config_dir) / "paused.flag").exists()
    except Exception:
        return False


def recado_da_recusa(dono: Dono, casa_que_pediu: str | None = None) -> str:
    """O quê, por quê e o que fazer — nesta ordem, que é a regra desta casa.

    A frase NOMEIA o outro Hefesto e dá o pid: sem isso ela lê "não subiu" e
    não tem como saber qual dos dois está segurando o quê.

    A variante de PAUSADO existe porque é a confusão que custa a noite: a tela
    do outro app diz "pausado", e pausado ele **continua** com o aparelho. Sem
    esta frase, o gesto óbvio (despausar, ou pausar de novo) não resolve e não
    explica.
    """
    quem = casa_que_pediu if casa_que_pediu is not None else casa_atual()
    eu = NOME_DA_CASA.get(quem, "Hefesto")
    pid = f" (pid {dono.pid})" if dono.pid else ""
    linhas = [
        f"O daemon do {eu} NÃO subiu: o {dono.nome} está com o aparelho{pid}.",
    ]
    if _esta_pausado(dono.casa):
        linhas.append(
            "Ele está PAUSADO — e pausado ele CONTINUA segurando o controle: a\n"
            "pausa só para de despachar botões, não solta o aparelho. Despausar\n"
            "não resolve, e desligar pela pausa também não."
        )
    else:
        linhas.append(
            "Dois daemons no mesmo controle brigam pelo hidraw — o sintoma é o\n"
            "controle parar de responder sem erro nenhum na tela."
        )
    linhas.append(f"Para liberar:  {GESTO_QUE_LIBERA.get(dono.casa, '')}")
    return "\n".join(linhas)


# --------------------------------------------------------------------------
# As duas fases
# --------------------------------------------------------------------------
def conferir_antes_do_takeover() -> None:
    """Levanta ``OutraCasaComOAparelhoError`` se o OUTRO Hefesto está com o controle.

    Silenciosa quando a trava está livre, quando o dono é da própria casa (o
    reinício de sempre) e quando a trava não se aplica (fake / socket
    isolado).
    """
    if not a_trava_se_aplica():
        return
    try:
        dono = dono_agora()
    except Exception as exc:  # pragma: no cover - falha aberta
        logger.warning("trava_do_aparelho_sonda_falhou", erro=str(exc))
        return
    if dono is None:
        return
    minha = casa_atual()
    if dono.casa == minha:
        # BUG-MULTI-INSTANCE-01 preservado: o predecessor da PRÓPRIA casa é
        # assunto do `acquire_or_takeover`, não desta trava.
        logger.debug("trava_do_aparelho_mesma_casa", casa=minha, pid=dono.pid)
        return
    raise OutraCasaComOAparelhoError(dono, recado_da_recusa(dono, minha))


def tomar() -> bool:
    """Segura a trava para esta casa. Chamar DEPOIS do ``acquire_or_takeover``.

    Devolve True se tomou. False significa "não deu, e seguimos assim mesmo" —
    falha aberta: nunca derruba o boot.
    """
    global _FD_SEGURO
    if not a_trava_se_aplica():
        return False
    if _FD_SEGURO is not None:
        return True
    alvo = caminho_da_trava()
    try:
        fd = os.open(str(alvo), os.O_CREAT | os.O_RDWR, 0o600)
    except OSError as exc:
        logger.warning("trava_do_aparelho_nao_abriu", erro=str(exc), caminho=str(alvo))
        return False
    limite = time.monotonic() + ESPERA_MAXIMA_S
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except OSError as exc:
            if exc.errno not in (errno.EWOULDBLOCK, errno.EAGAIN):
                logger.warning("trava_do_aparelho_flock_erro", erro=str(exc))
                with contextlib.suppress(OSError):
                    os.close(fd)
                return False
            if time.monotonic() >= limite:
                logger.warning("trava_do_aparelho_ocupada_apos_takeover")
                with contextlib.suppress(OSError):
                    os.close(fd)
                return False
            time.sleep(_INTERVALO_S)
    try:
        os.ftruncate(fd, 0)
        os.write(fd, f"{os.getpid()}\n{casa_atual()}\n".encode())
        os.fsync(fd)
    except OSError as exc:
        logger.warning("trava_do_aparelho_nao_gravou", erro=str(exc))
    _FD_SEGURO = fd
    logger.info("trava_do_aparelho_tomada", casa=casa_atual(), caminho=str(alvo))
    return True


def soltar() -> None:
    """Solta a trava. O kernel já faz isto na saída do processo — existe para
    o teste medir duas tomadas no mesmo processo sem inventar um subprocesso.
    """
    global _FD_SEGURO
    fd, _FD_SEGURO = _FD_SEGURO, None
    if fd is None:
        return
    with contextlib.suppress(OSError):
        fcntl.flock(fd, fcntl.LOCK_UN)
    with contextlib.suppress(OSError):
        os.close(fd)


__all__ = [
    "CASA_DEV",
    "CASA_ESTAVEL",
    "ESPERA_MAXIMA_S",
    "GESTO_QUE_LIBERA",
    "NOME_DA_CASA",
    "NOME_DA_TRAVA",
    "SLUG_DA_CASA",
    "Dono",
    "OutraCasaComOAparelhoError",
    "a_trava_se_aplica",
    "caminho_da_trava",
    "casa_atual",
    "conferir_antes_do_takeover",
    "dono_agora",
    "recado_da_recusa",
    "soltar",
    "tomar",
]

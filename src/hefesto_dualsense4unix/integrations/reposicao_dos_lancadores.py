"""Fechar e reabrir o lançador que estava aberto — REPOR-O-LANCADOR-01.

**Por que isto existe, e o pedido é dela (21/09/2026):** *"tenho pensando sobre
o botão de reiniciar daemon. Acho que além do que ele já faz seria importante
ele fechar e reabrir o launcher, seja steam, epic, heroic ou qualquer outro."*
<!-- noqa-acento: citação literal dela -->
E, quando lhe foram postas três formas: *"Faz automático mesmo"*.

**O QUE O REINÍCIO DEIXA PARA TRÁS, medido quatro vezes** (`STEAM-NO-FISICO-01`):
o lançador que subiu ANTES do daemon segura o controle físico — a barra de luz
apaga e o jogo passa a ver o aparelho de verdade em vez do virtual. Reiniciar o
serviço sem repor o lançador devolve a máquina exatamente ao estado que o
reinício queria desfazer. A Steam ainda apaga sozinha o wrapper da Launch
Option, e só uma reabertura o devolve ao lugar.

**A REGRA DO JOGO ABERTO NÃO É NOVA E NÃO É MINHA.** Está escrita no produto
desde 18/09/2026, em `steam_launch_options._fechar_a_steam_uma_vez`: *"o jogo
aberto vem ANTES de qualquer decisão — fechar a Steam com um jogo aberto o
mataria"*. Este módulo aplica a MESMA regra a todos os lançadores, e é o único
caso em que "automático" não fecha nada: o recibo diz por quê, e o reinício
vale a partir do próximo lançamento.

**O AMBIENTE É LIMPO EM TODA ABERTURA**, e é lição paga: um lançador aberto do
shell de quem chamou herda `CLAUDECODE`, `VIRTUAL_ENV` e o `PATH` da venv, e
contamina TODO jogo que ele abrir depois. `ambiente_do_jogo.ambiente_limpo` é o
dono disso.

**NADA AQUI MATA POR PADRÃO DE LINHA DE COMANDO.** Os pids vêm de `pgrep -x`
(nome EXATO) e do `flatpak ps`, e o sinal vai para cada pid conferido, um a um.
Um `pkill -f` já derrubou o compositor desta máquina.

**O `pgrep -f` FOI TENTADO E CAIU NA HORA, 21/09/2026.** A primeira versão
perguntava `pgrep -f com.heroicgameslauncher.hgl` para achar o Heroic de
flatpak, e a resposta foi **o próprio shell que estava perguntando** — o id da
aplicação estava na cmdline dele. O módulo respondeu *"Heroic e Lutris
abertos"* numa máquina com os dois FECHADOS; um `fechar()` ali teria mandado
`SIGTERM` no terminal de quem chamou. É o mesmo defeito que já prendeu onze
shells desta casa por 21 horas: **um laço que casa por linha de comando casa a
si mesmo.** Quem responde por flatpak é o `flatpak ps`, que lista instâncias e
não texto.
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import time
from dataclasses import dataclass

from hefesto_dualsense4unix.integrations.ambiente_do_jogo import ambiente_limpo
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: Quanto se espera um lançador fechar com jeito antes de insistir. A Steam tem
#: caminho próprio (`stop_steam`, até 30 s); os outros são aplicações comuns e
#: fecham em segundos.
ESPERA_PARA_FECHAR_S: float = 12.0

#: O passo entre as perguntas de "já fechou?". Não é `sleep(12)`: um lançador
#: que fecha em 1 s não pode custar 12 ao reinício dela.
PASSO_DA_ESPERA_S: float = 0.5


@dataclass(frozen=True)
class Lancador:
    """Um lançador que esta casa sabe fechar e reabrir.

    `processos` são nomes EXATOS para `pgrep -x`. `flatpak` é o id da
    aplicação, e quando ele existe é por ele que se pergunta e se abre — um
    flatpak não tem o nome do processo que o `.desktop` sugere.
    """

    chave: str
    nome: str
    processos: tuple[str, ...]
    flatpak: str | None = None
    #: O executável da instalação NATIVA (fora do flatpak). Sem acento no nome
    #: do campo de propósito: nenhum identificador desta casa leva acento, e o
    #: portão da acentuação cobra a palavra em português do comentário — não do
    #: símbolo.
    nativo: str | None = None


#: A TABELA É EXPLÍCITA, e não um glob por `.desktop`: acrescentar um lançador
#: é um ato que se vê no diff. Um glob passaria a fechar, sozinho e sem
#: ninguém decidir, qualquer coisa que se parecesse com um lançador — e fechar
#: é destrutivo.
#:
#: A Steam não declara executável nativo porque o abrir dela tem dono
#: (`steam_launcher.open_or_focus_steam`), que ainda FOCA a janela quando ela
#: já está de pé.
LANCADORES: tuple[Lancador, ...] = (
    Lancador("steam", "Steam", ("steamwebhelper",)),
    Lancador("heroic", "Heroic", ("heroic",),
             flatpak="com.heroicgameslauncher.hgl", nativo="heroic"),
    Lancador("lutris", "Lutris", ("lutris",),
             flatpak="net.lutris.Lutris", nativo="lutris"),
)


def _rodar(args: list[str], *, timeout: float = 5.0) -> subprocess.CompletedProcess[str] | None:
    """Um comando de LEITURA, com o idioma preso em C.

    `LC_ALL=C` em toda leitura, e é regra desta casa desde que um leitor
    traduzido respondeu *"não há"* sobre aparelho de pé — duas vezes.
    """
    try:
        return subprocess.run(
            args, capture_output=True, text=True, timeout=timeout, check=False,
            env={**os.environ, "LC_ALL": "C", "LANG": "C"})
    except (OSError, subprocess.SubprocessError):
        return None


def _pids_de_flatpak(app_id: str) -> list[int]:
    """Os pids de wrapper das instâncias vivas desta aplicação flatpak.

    `flatpak ps` lista INSTÂNCIAS, não texto de cmdline — por isso ele não tem
    como casar quem pergunta. O `pid` é o do processo **wrapper**, e é nele que
    o `SIGTERM` fecha a aplicação inteira.

    `LC_ALL=C` porque o `flatpak` desta máquina responde em português (o `help`
    das colunas sai traduzido); as linhas de dado não são, mas um leitor que
    depende do idioma da máquina já respondeu *"não há"* sobre aparelho de pé
    duas vezes nesta casa.
    """
    if shutil.which("flatpak") is None:
        return []
    proc = _rodar(["flatpak", "ps", "--columns=application,pid"])
    if proc is None or proc.returncode != 0:
        return []
    achados: list[int] = []
    for linha in proc.stdout.splitlines():
        campos = linha.split()
        if len(campos) >= 2 and campos[0] == app_id and campos[1].isdigit():
            achados.append(int(campos[1]))
    return achados


def pids_de(lancador: Lancador) -> list[int]:
    """Os pids vivos deste lançador — lista vazia quando ele não está aberto.

    DUAS PERGUNTAS, e nenhuma delas lê linha de comando: `pgrep -x` casa o
    nome EXATO do processo (a instalação nativa) e o `flatpak ps` responde pela
    instalação em flatpak. Ver o cabeçalho do módulo para o que aconteceu com a
    terceira, que lia cmdline.
    """
    achados: set[int] = set()
    for nome in lancador.processos:
        proc = _rodar(["pgrep", "-x", nome])
        if proc is not None and proc.returncode == 0:
            achados.update(int(x) for x in proc.stdout.split() if x.isdigit())
    if lancador.flatpak:
        achados.update(_pids_de_flatpak(lancador.flatpak))
    # O PRÓPRIO PROCESSO NUNCA ENTRA NA LISTA, e é cinto de segurança: hoje
    # nenhuma das duas perguntas pode devolvê-lo, e a terceira que puder tem de
    # esbarrar aqui antes de chegar ao `os.kill`.
    achados.discard(os.getpid())
    return sorted(achados)


def esta_aberto(lancador: Lancador) -> bool:
    return bool(pids_de(lancador))


def abertos() -> list[Lancador]:
    """Os lançadores de pé agora, na ordem da tabela."""
    return [x for x in LANCADORES if esta_aberto(x)]


def jogo_aberto() -> bool:
    """Há jogo rodando? — a pergunta que vem ANTES de qualquer fechamento.

    DELEGADA ao dono, e é o mesmo que o install consulta: `steam_game_running`
    varre `/proc` procurando o `reaper SteamLaunch AppId=<id>` que embrulha
    todo jogo lançado pela Steam. **E ele alcança o Heroic e o Lutris**, porque
    os dois lançam pelo `umu`, que se anuncia como Steam — medido em
    20/09/2026, `steam_app_<N>`.

    A FOTO É INVALIDADA ANTES, e isso não é zelo: a varredura vale 5 s por
    desempenho, e decidir um ato destrutivo sobre uma foto de 5 s atrás é
    decidir sobre um jogo que já fechou — ou não ver um que acabou de abrir.
    """
    from hefesto_dualsense4unix.integrations.steam_launch_options import (
        invalidar_varredura_de_proc,
        steam_game_running,
    )

    invalidar_varredura_de_proc()
    return steam_game_running()


def fechar(lancador: Lancador) -> bool:
    """Fecha com jeito e confirma. `True` = está fechado quando esta função sai.

    A STEAM TEM CAMINHO PRÓPRIO (`stop_steam`): ela responde a `steam
    -shutdown`, que salva a nuvem e fecha o runtime inteiro. Mandar TERM nos
    processos dela seria um segundo dono de um ato que já tem um.

    OS OUTROS LEVAM `SIGTERM` NOS PIDS CONFERIDOS, um a um. Não há `SIGKILL`
    aqui de propósito: um lançador morto à força pode deixar a biblioteca a
    meio caminho, e esta função é chamada por um botão de CONSERTO. Quem não
    fechar em :data:`ESPERA_PARA_FECHAR_S` fica aberto, e o recibo o nomeia.
    """
    if lancador.chave == "steam":
        from hefesto_dualsense4unix.integrations.steam_launch_options import stop_steam

        return stop_steam()

    for pid in pids_de(lancador):
        try:
            os.kill(pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError) as erro:
            logger.info("repor_lancador_sinal_recusado",
                        lancador=lancador.chave, pid=pid, erro=str(erro))

    limite = time.monotonic() + ESPERA_PARA_FECHAR_S
    while time.monotonic() < limite:
        if not esta_aberto(lancador):
            return True
        time.sleep(PASSO_DA_ESPERA_S)
    return not esta_aberto(lancador)


def abrir(lancador: Lancador) -> bool:
    """Reabre, com o ambiente LIMPO. `True` = o pedido de abertura saiu.

    NÃO ESPERA A JANELA. Um lançador leva de segundos a dezenas de segundos
    para pintar, e segurar o reinício dela nisso faria o botão parecer travado
    — que é o defeito que a leva de 15/09 curou na janela inteira.
    """
    if lancador.chave == "steam":
        from hefesto_dualsense4unix.integrations.steam_launcher import (
            open_or_focus_steam,
        )

        return bool(open_or_focus_steam())

    comando: list[str] | None = None
    if lancador.flatpak and shutil.which("flatpak") is not None:
        comando = ["flatpak", "run", lancador.flatpak]
    elif lancador.nativo and shutil.which(lancador.nativo) is not None:
        comando = [lancador.nativo]
    if comando is None:
        logger.info("repor_lancador_sem_caminho", lancador=lancador.chave)
        return False

    try:
        subprocess.Popen(
            comando,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            env=ambiente_limpo(os.environ),
        )
    except (OSError, subprocess.SubprocessError) as erro:
        logger.warning("repor_lancador_nao_abriu",
                       lancador=lancador.chave, erro=str(erro))
        return False
    return True


@dataclass(frozen=True)
class Recibo:
    """O que aconteceu — para a tela dizer, e para o registro guardar."""

    #: Nomes dos lançadores que estavam abertos quando se olhou.
    estavam_abertos: tuple[str, ...] = ()
    #: Os que fecharam e reabriram.
    repostos: tuple[str, ...] = ()
    #: Os que não fecharam no prazo (e por isso não foram reabertos).
    nao_fecharam: tuple[str, ...] = ()
    #: Os que fecharam mas não reabriram.
    nao_reabriram: tuple[str, ...] = ()
    #: `True` quando havia jogo rodando e NADA foi fechado.
    barrado_por_jogo: bool = False


def repor() -> Recibo:
    """Fecha e reabre todo lançador que estava aberto. O ato inteiro.

    A ORDEM É: pergunta pelo jogo, tira a foto de quem está aberto, fecha
    todos, reabre os que fecharam. Fechar-e-reabrir um a um faria o segundo
    lançador subir enquanto o primeiro ainda disputa o controle físico.
    """
    if jogo_aberto():
        return Recibo(barrado_por_jogo=True)

    de_pe = abertos()
    if not de_pe:
        return Recibo()

    fechados = [x for x in de_pe if fechar(x)]
    nao_fecharam = tuple(x.nome for x in de_pe if x not in fechados)

    repostos: list[str] = []
    nao_reabriram: list[str] = []
    for lancador in fechados:
        (repostos if abrir(lancador) else nao_reabriram).append(lancador.nome)

    return Recibo(
        estavam_abertos=tuple(x.nome for x in de_pe),
        repostos=tuple(repostos),
        nao_fecharam=nao_fecharam,
        nao_reabriram=tuple(nao_reabriram),
    )


def frase_do_recibo(recibo: Recibo) -> str:
    """O recibo em português — função PURA, e o único lugar onde ele vira texto.

    Escrever a frase na aba criaria o segundo dono que esta casa enterra toda
    semana: a aba Sistema e o registro diriam coisas diferentes sobre o mesmo
    ato.
    """
    if recibo.barrado_por_jogo:
        return ("Tem jogo aberto, então não mexi no lançador — fechá-lo "
                "fecharia o jogo junto. O reinício vale a partir do próximo "
                "que você abrir.")
    if not recibo.estavam_abertos:
        return "Nenhum lançador estava aberto — não havia o que repor."

    partes: list[str] = []
    if recibo.repostos:
        partes.append(f"Fechei e reabri: {', '.join(recibo.repostos)}.")
    if recibo.nao_fecharam:
        partes.append(
            f"Não consegui fechar: {', '.join(recibo.nao_fecharam)} — "
            "ficou aberto do jeito que estava.")
    if recibo.nao_reabriram:
        partes.append(
            f"Fechei mas não consegui reabrir: {', '.join(recibo.nao_reabriram)}.")
    return " ".join(partes)


__all__ = [
    "LANCADORES",
    "Lancador",
    "Recibo",
    "abertos",
    "abrir",
    "esta_aberto",
    "fechar",
    "frase_do_recibo",
    "jogo_aberto",
    "pids_de",
    "repor",
]

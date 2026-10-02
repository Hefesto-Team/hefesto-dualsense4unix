"""audio_saida.py — o som de confirmação e a rota de saída (SOM-04).

Duas entregas que respondem a duas frases dela, e uma raiz só: **o registrador
de volume do DualSense não tem leitura.** O firmware aceita o valor e não o
devolve — está escrito na SOM-02 como o preço da camada 2. Consequência
medida: depois de mover o controle deslizante, nada na tela pode confirmar que
a mudança valeu, porque o número que aparece é o que NÓS mandamos. O som é a
leitura que falta.

**Entrega 1 — o som de confirmação.** Um som curto no alto-falante do
controle depois de cada ação do bloco (mover o volume, ``Silenciar``,
``Ativar``, ``Devolver``). É o mesmo padrão de todo controle de volume de
sistema operacional, e aqui ele não é enfeite: é a única prova disponível.

**Entrega 2 — a rota de saída.** *"na hora do jogo vai funcionar a vera?"* —
hoje não: o som do sistema vai para o HDMI e o controle deslizante ajusta um
alto-falante que não está recebendo áudio nenhum. A rota manda a saída padrão
do sistema para o sink do controle, e desfaz.

O FATO QUE ORGANIZA ESTE MÓDULO INTEIRO, medido nesta bancada em 01/08/2026::

    $ paplay --device=nao_existe_mesmo bell.oga ; echo $?
    0
    $ pw-play --target=nao_existe_mesmo bell.oga ; echo $?
    0
    $ paplay --device= bell.oga ; echo $?
    0

**Os dois tocadores aceitam um sink inexistente, saem com zero e tocam no sink
PADRÃO.** Não há mensagem de erro, não há código de saída. Com o padrão dela no
HDMI, um som "de confirmação do controle" sairia pela televisão e ela concluiria
que o alto-falante quebrou. Por isso a regra desta casa aqui é dura e vale para
todo caminho de código: **o sink é resolvido na lista viva de sinks antes de
tocar, e sem casamento não se toca.** Ver :func:`tocar_confirmacao`, que recusa
com :data:`MOTIVO_SEM_SINK` em vez de mandar o argumento adiante.

Três disciplinas herdadas do `mic_monitor.py`, que é o leitor de PipeWire desta
janela e que este módulo REUSA em vez de duplicar:

* **nada de subprocess na thread do GTK.** Tudo aqui é bloqueante de propósito
  e roda em thread worker (``ipc_bridge.run_in_thread``, o padrão do card);
* **`LC_ALL=C` em tudo**, porque a saída do `pactl` é traduzida;
* **nada de escrever no estado do WirePlumber.** A SOM-02 proíbe com motivo:
  o mudo persistido é escolha dela e o `doctor` o trata como legítimo. O
  caminho é `pactl`, que é o que a própria dona usaria.

Sobre a CHAVE de desligar o som (SOM-04, entrega 1, regra 6). Ela existe e
mora em ``gui_preferences.json``, na chave :data:`CHAVE_PREF_SOM`, ligada por
padrão. As duas metades da decisão:

* **por que ligada por padrão**: sem o som não há confirmação nenhuma, e a
  ausência de leitura é justamente o defeito que esta leva vem tapar;
* **por que sem interruptor na tela NESTA rodada**: a aba Status abre com 32px
  de folga em 1180 e o card mais alto com 11px em 467 — medido nesta leva, com
  o card montado e alocado. Um interruptor pertence à aba de preferências, que
  hoje não existe como superfície de opções da janela, e abri-la é uma leva
  própria. A chave no arquivo dá a saída a quem quer silêncio sem esperar
  release nenhuma, e o dia em que a aba existir ela ganha o widget sem tocar
  aqui.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Final, NamedTuple

from hefesto_dualsense4unix.core.ds_output_report import (
    SAIDA_ESTEREO_NO_FONE,
    SAIDA_L_FONE_R_ALTO_FALANTE,
    SAIDA_SO_NO_ALTO_FALANTE,
)

from hefesto_dualsense4unix.integrations.alto_falante_bt import (
    sink_do_controle as _sink_do_controle,
)
from hefesto_dualsense4unix.integrations.alto_falante_bt import (
    sufixo_do_sink_do_som,
)
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

CHAVE_PREF_SOM: Final[str] = "som_de_confirmacao"

CHAVE_PREF_ROTA_ANTERIOR: Final[str] = "rota_de_som_anterior"

_TIMEOUT_LEITURA_S: Final[float] = 2.0

_TIMEOUT_TOCADOR_S: Final[float] = 5.0


_RAIZES_DE_SOM: Final[tuple[str, ...]] = (
    "/usr/share/sounds",
    "/usr/local/share/sounds",
    "/app/share/sounds",
)

_CANDIDATOS_DE_SOM: Final[tuple[str, ...]] = (
    "freedesktop/stereo/audio-volume-change.oga",
    "freedesktop/stereo/bell.oga",
    "freedesktop/stereo/dialog-information.oga",
    "alsa/Front_Center.wav",
)

_TAMANHO_MINIMO_DE_SOM: Final[int] = 256

_TOCADORES: Final[tuple[tuple[str, str], ...]] = (
    ("paplay", "--device={sink}"),
    ("pw-play", "--target={sink}"),
)


MOTIVO_TOCOU: Final[str] = "tocou"
MOTIVO_DESLIGADO: Final[str] = "desligado"
MOTIVO_OCUPADO: Final[str] = "ocupado"
MOTIVO_SEM_SINK: Final[str] = "sem_sink"
MOTIVO_SAIDA_MUDA: Final[str] = "saida_muda"
MOTIVO_SEM_ARQUIVO: Final[str] = "sem_arquivo"
MOTIVO_SEM_TOCADOR: Final[str] = "sem_tocador"
MOTIVO_FALHOU: Final[str] = "falhou"

RECADOS: Final[dict[str, str]] = {
    MOTIVO_TOCOU: "",
    MOTIVO_DESLIGADO: "",
    MOTIVO_OCUPADO: "",
    MOTIVO_SEM_SINK: (
        "Sem confirmação: o sistema não publica saída de áudio deste controle"
    ),
    MOTIVO_SAIDA_MUDA: (
        "Sem confirmação: a saída do controle está muda no sistema"
    ),
    MOTIVO_SEM_ARQUIVO: "Sem confirmação: nenhum som de sistema instalado",
    MOTIVO_SEM_TOCADOR: "Sem confirmação: falta paplay ou pw-play na máquina",
    MOTIVO_FALHOU: "Sem confirmação: o tocador de som falhou",
}


@dataclass(frozen=True)
class ResultadoDoSom:
    """O que aconteceu com o pedido de tocar, e o que a tela deve dizer."""

    tocou: bool
    motivo: str
    recado: str = ""
    sink: str = ""

    @classmethod
    def de(cls, motivo: str, sink: str = "") -> ResultadoDoSom:
        return cls(
            tocou=(motivo == MOTIVO_TOCOU),
            motivo=motivo,
            recado=RECADOS.get(motivo, ""),
            sink=sink,
        )


def nomes_de_sinks(saida_pactl: str) -> list[str]:
    """Todos os nomes de `pactl list sinks short`, na ordem em que vieram.

    A contraparte com filtro de DualSense é ``mic_monitor.sinks_dualsense``, e
    ela continua sendo a dona de "qual sink é do controle" — aqui a lista é
    INTEIRA porque as duas perguntas deste módulo são sobre o sistema: "este
    nome existe mesmo?" (a guarda do tocador) e "o sink que eu guardei ainda
    está lá?" (a guarda do desfazer).
    """
    fora: list[str] = []
    for linha in saida_pactl.splitlines():
        partes = linha.split("\t")
        if len(partes) < 2:
            continue
        nome = partes[1].strip()
        if nome:
            fora.append(nome)
    return fora


def sink_padrao_da_saida(saida_pactl: str) -> str:
    """Nome do sink padrão em `pactl get-default-sink`; "" se ilegível."""
    for linha in saida_pactl.splitlines():
        nome = linha.strip()
        if nome and not nome.startswith("Failure"):
            return nome
    return ""


CANAL_ACORDADO: Final[str] = "acordado"
CANAL_DORMINDO: Final[str] = "dormindo"
CANAL_SEM_LEITURA: Final[str] = ""

_ESTADOS_DO_PACTL: Final[dict[str, str]] = {
    "RUNNING": CANAL_ACORDADO,
    "IDLE": CANAL_ACORDADO,
    "SUSPENDED": CANAL_DORMINDO,
}


def estados_crus_dos_sinks(saida_pactl: str) -> dict[str, str]:
    """``{nome do sink: ESTADO cru do pactl}``. **O único parser da coluna.**"""
    fora: dict[str, str] = {}
    for linha in saida_pactl.splitlines():
        partes = linha.split("\t")
        if len(partes) < 5:
            continue
        nome = partes[1].strip()
        if nome:
            fora[nome] = partes[-1].strip().upper()
    return fora


def estados_dos_sinks(saida_pactl: str) -> dict[str, str]:
    """``{nome do sink: acordado|dormindo}`` de `pactl list sinks short`."""
    fora: dict[str, str] = {}
    for nome, cru in estados_crus_dos_sinks(saida_pactl).items():
        estado = _ESTADOS_DO_PACTL.get(cru, CANAL_SEM_LEITURA)
        if estado:
            fora[nome] = estado
    return fora


def estado_do_canal(saida_pactl: str, sink: str) -> str:
    """Estado de UM sink; ``""`` quando não há linha dele ou não dá para ler."""
    if not sink:
        return CANAL_SEM_LEITURA
    return estados_dos_sinks(saida_pactl).get(sink, CANAL_SEM_LEITURA)


def acordar_sink(sink: str, *, runner: Callable[[list[str]], str] | None = None) -> bool:
    """Tira o sink da suspensão ANTES de alguém tocar nele. Best-effort.

    Devolve ``True`` quando o sink terminou **acordado** — conferido relendo a
    lista, e não pela ausência de erro do `pactl`, que é a mesma disciplina do
    :meth:`RotaDeSaida._trocar` (a janela que acredita na própria escrita é a
    janela que mente na tela).

    **Por que isto não atropela escolha dela.** `set-sink-suspend 0` não muda
    volume, não muda rota, não muda o sink padrão e não desfaz mudo: ele só
    impede que o PipeWire solte o hardware. Quem chega aqui é um gesto que
    pede som NAQUELE controle — e a suspensão não é opinião sobre esse pedido,
    é ociosidade.

    **Por que ela é a cura certa para o bipe curto.** O som de confirmação
    desta janela tem **67 ms** (`audio-volume-change.oga`, o mais curto dos
    candidatos, escolhido de propósito para não atrapalhar quem ajusta o
    volume). Num nó suspenso, "o começo do som" é o som inteiro.
    """
    if not sink:
        return False
    rodar = runner if runner is not None else rodar_leitura
    rodar(["pactl", "set-sink-suspend", sink, "0"])
    return estado_do_canal(
        rodar(["pactl", "list", "sinks", "short"]), sink
    ) == CANAL_ACORDADO


def apelido_do_sink(nome: str) -> str:
    """Pedaço legível do nome de um sink, para caber numa dica."""
    limpo = nome.strip()
    if not limpo:
        return ""
    segmento = limpo.rsplit(".", 1)[-1]
    return segmento or limpo


def arquivo_de_confirmacao(
    *,
    raizes: tuple[str, ...] = _RAIZES_DE_SOM,
    candidatos: tuple[str, ...] = _CANDIDATOS_DE_SOM,
    tamanho: Callable[[str], int] | None = None,
) -> str:
    """Primeiro som utilizável da lista de candidatos; "" se não houver nenhum."""
    medir = tamanho if tamanho is not None else _tamanho_do_arquivo
    for relativo in candidatos:
        for raiz in raizes:
            caminho = os.path.join(raiz, relativo)
            if medir(caminho) >= _TAMANHO_MINIMO_DE_SOM:
                return caminho
    return ""


def _tamanho_do_arquivo(caminho: str) -> int:
    try:
        return os.path.getsize(caminho)
    except OSError:
        return 0


def argv_do_tocador(
    sink: str, arquivo: str, *, achar: Callable[[str], str | None] | None = None
) -> list[str]:
    """Linha de comando do primeiro tocador instalado; [] se não houver nenhum.

    O sink vai **explícito e não vazio** — a checagem de que ele existe é de
    quem chama (:func:`tocar_confirmacao`), e a de que ele não é vazio é aqui,
    porque ``--device=`` vazio é aceito pelo `paplay` e cai no sink padrão.
    """
    if not sink or not arquivo:
        return []
    which = achar if achar is not None else shutil.which
    for binario, modelo in _TOCADORES:
        if which(binario):
            return [binario, modelo.format(sink=sink), arquivo]
    return []


def garantir_saida_audivel(
    sink: str, *, runner: Callable[[list[str]], str] | None = None
) -> bool:
    """Tira o mute do sink do controle. Devolve True se havia o que tirar.

    SOM-SAIDA-MUDA-01, 04/08/2026 — MEDIDO com ela. Ela clicou nos dois
    estados do seletor, o `pactl` obedeceu, e não saiu som nenhum: o sink do
    DualSense estava `MUTED` no PipeWire, por estado que o WirePlumber
    PERSISTE por rota (``~/.local/state/wireplumber/default-routes``) e
    restaura a cada conexão **sem escrever nada em log nenhum**.

    A casa já tinha a doutrina escrita, no próprio card:

        *"A camada 1 vence a camada 2: volume e rota perfeitos num sink mudo
        é trabalho invisível."*

    ...e já cobria o espelho disto do lado da CAPTURA — a "camada 1" do
    microfone mudo, que o ``doctor.sh`` confere e cura. O que faltava era
    alguém AGIR sobre a saída, e não só saber.

    **Por que desmutar não atropela escolha dela.** Quem chega aqui é um gesto
    que pede som NO CONTROLE — trocar o canal, mandar o som do PC para lá. Um
    mute herdado de outra sessão não é opinião sobre este pedido. E o desfazer
    continua ao alcance: o mute do sistema é dela, e o próximo gesto dela
    vence este.

    **Por que não bastava recusar.** O ``tocar_confirmacao`` já recusa com
    recado quando o mute foi lido (``MOTIVO_SAIDA_MUDA``), mas o mapa de mudos
    só guarda o que foi lido COM CERTEZA: ausência é "não sei". E "não sei"
    seguia para o tocador, que gastava um processo para produzir silêncio e
    devolvia sucesso. Recusar bem é metade; a outra metade é o sink audível.
    """
    if not sink:
        return False
    from hefesto_dualsense4unix.app.mic_monitor import muted_de_saida

    rodar = runner if runner is not None else rodar_leitura
    antes = muted_de_saida(rodar(["pactl", "get-sink-mute", sink]))
    rodar(["pactl", "set-sink-mute", sink, "0"])
    return antes is True


_tocando = threading.Lock()


def tocar_confirmacao(
    sink: str,
    *,
    saida_muda: bool | None = None,
    ligado: bool | None = None,
    runner: Callable[[list[str]], str] | None = None,
    tocador: Callable[[list[str]], int] | None = None,
    achar: Callable[[str], str | None] | None = None,
) -> ResultadoDoSom:
    """Toca o som curto NO SINK DO CONTROLE. Nunca no padrão, nunca calado.

    Bloqueante de propósito: quem chama é ``ipc_bridge.run_in_thread``, como o
    resto do bloco do alto-falante.

    A ordem das recusas não é arbitrária — cada degrau é mais barato que o
    seguinte, e o mais caro (abrir um fluxo de áudio) é o último:

    1. **desligado** pela chave dela: sai sem dizer nada;
    2. **ocupado**: já há um som tocando; o antirrajada;
    3. **sem sink**: nome vazio. É o que chega quando o
       ``mic_monitor.escolher_sink`` não fecha o casamento — pelo RÁDIO o
       DualSense não publica placa de som nenhuma (medido 15/08/2026: a placa
       segue o transporte). No cabo ele fecha, mesmo com quatro controles, pelo
       dispositivo USB em que a placa e o HID penduram juntos;
    4. **saída muda** (a camada 1): tocar aqui gastaria um processo para
       produzir silêncio e ela leria o silêncio como defeito do controle;
    5. **o sink não está na lista viva** — a guarda que o cabeçalho deste
       módulo explica. Medido: `paplay --device=<inexistente>` sai com ZERO e
       toca no sink PADRÃO. Sem esta linha, a confirmação do alto-falante do
       controle sairia pela televisão dela;
    6. **sem arquivo** e **sem tocador**: nada instalado;
    7. o tocador rodou e devolveu erro.

    Nenhum caminho devolve "deu certo" sem ter tocado, e nenhum falha calado:
    todo motivo que não seja escolha dela carrega um recado para a tela.

    REGRESSÃO-DO-BIPE-01, 16/08/2026 — *"hoje em dia na interface nem por cabo
    esse bip tá saindo"*, tendo saído antes. **O passo 6.5 é a cura**: com o
    sink DORMINDO, este som não tinha como sair.

    Os degraus 1 a 7 conferiam tudo menos o único estado do sistema que
    silencia um som de 67 ms — o nó suspenso. E os dois lados da conta são
    medidos, cada um do seu lado:

    * o arquivo escolhido tem **0,067 s** (ver :data:`_CANDIDATOS_DE_SOM`, e o
      "mais curto dos candidatos" é escolha registrada, não acaso);
    * o PipeWire suspende o nó ocioso, e **o religar do hardware come o começo
      do som** — medido com a orelha dela em 15-16/08/2026, no cabo, mesmo
      canal, mesmo volume e mesma rota: "não saiu" com o nó ocioso, "tuuuuuuuu"
      com ele acordado (ver :func:`estados_dos_sinks`).

    Num som de 67 ms, "o começo" é o som inteiro. E a suspensão é o estado
    NORMAL entre dois gestos dela: os dois sinks de DualSense desta bancada
    estavam `SUSPENDED` na leitura desta data, com os controles ligados no
    cabo. Nada disto aparecia como falha — o `paplay` abria o fluxo, saía com
    zero, e o tocador devolvia :data:`MOTIVO_TOCOU`.

    O acordar entra DEPOIS das recusas baratas, de propósito: quem não vai
    tocar não paga por ele. E ele só roda quando a lista viva — já lida no
    degrau 5, sem subprocesso a mais — disser `SUSPENDED`.
    """
    if ligado is None:
        ligado = som_ligado()
    if not ligado:
        return ResultadoDoSom.de(MOTIVO_DESLIGADO)
    if not _tocando.acquire(blocking=False):
        return ResultadoDoSom.de(MOTIVO_OCUPADO)
    try:
        if not sink:
            return ResultadoDoSom.de(MOTIVO_SEM_SINK)
        if saida_muda is True:
            return ResultadoDoSom.de(MOTIVO_SAIDA_MUDA, sink)
        ler = runner if runner is not None else rodar_leitura
        lista_viva = ler(["pactl", "list", "sinks", "short"])
        if sink not in nomes_de_sinks(lista_viva):
            return ResultadoDoSom.de(MOTIVO_SEM_SINK, sink)
        arquivo = arquivo_de_confirmacao()
        if not arquivo:
            return ResultadoDoSom.de(MOTIVO_SEM_ARQUIVO, sink)
        argv = argv_do_tocador(sink, arquivo, achar=achar)
        if not argv:
            return ResultadoDoSom.de(MOTIVO_SEM_TOCADOR, sink)
        if estados_dos_sinks(lista_viva).get(sink) == CANAL_DORMINDO:
            acordar_sink(sink, runner=ler)
        rodar = tocador if tocador is not None else _rodar_tocador
        if rodar(argv) != 0:
            return ResultadoDoSom.de(MOTIVO_FALHOU, sink)
        return ResultadoDoSom.de(MOTIVO_TOCOU, sink)
    finally:
        _tocando.release()


def som_ligado(carregar: Callable[[], dict[str, Any]] | None = None) -> bool:
    """A confirmação sonora está ligada? Ligada por padrão (ver o cabeçalho)."""
    ler = carregar if carregar is not None else _carregar_prefs
    try:
        valor = ler().get(CHAVE_PREF_SOM, True)
    except Exception as exc:
        logger.debug("audio_saida_pref_som_ilegivel", err=str(exc))
        return True
    return bool(valor) if isinstance(valor, bool) else True


TEXTO_ROTA_PARA_O_CONTROLE: Final[str] = "Ouvir no controle"
TEXTO_ROTA_VOLTAR: Final[str] = "Voltar ao anterior"

DICA_ROTA_INICIAL: Final[str] = (
    "Manda o som do sistema para o alto-falante do controle, e desfaz. O "
    "rótulo do botão diz o que o próximo clique faz, e a dica muda junto com "
    "ele assim que a janela ler a saída de áudio."
)

DICA_ROTA_PARA_O_CONTROLE: Final[str] = (
    "Manda o som do sistema INTEIRO para o alto-falante do controle: jogo, "
    "navegador, notificações, tudo. É a mesma troca de saída padrão que as "
    "configurações de som do sistema fazem, e ela continua valendo depois de "
    "fechar esta janela. Onde o som sai depois de chegar ao controle — "
    "alto-falante ou fone — é o canal, no bloco Alto-falante. A janela guarda "
    "a saída de agora para o botão de volta."
)
DICA_ROTA_VOLTAR: Final[str] = (
    "Devolve o som do sistema para {apelido}, que era a saída antes de a "
    "janela mandá-lo para o controle. O alto-falante do controle continua "
    "existindo: ela só deixa de receber o áudio do sistema."
)
#: dizia que sinks de vários DualSense não se distinguem. Eles se distinguem
DICA_ROTA_SEM_SINK: Final[str] = (
    "Não há uma saída de áudio única para mandar o som. Pelo rádio o "
    "DualSense não publica placa de som nenhuma — ela só aparece no cabo. "
    "Com mais de um controle no cabo há mais de uma placa, e este botão é um "
    "só: escolher uma por você seria a janela decidindo em que controle o som "
    "sai. Use o seletor Alto-falante do card do controle que você quer."
)
DICA_ROTA_SEM_VOLTA: Final[str] = (
    "O som do sistema já está saindo no controle, e não foi esta janela que o "
    "mandou para lá — não há como saber para onde voltar. Escolha a saída nas "
    "configurações de som do sistema."
)


@dataclass(frozen=True)
class EstadoDaRota:
    """Onde o som do sistema está, para onde ele pode ir, e de onde ele veio."""

    sink_padrao: str = ""
    sink_do_controle: str = ""
    anterior: str = ""
    no_controle: bool = False
    canais: Mapping[str, str] = field(default_factory=dict)


class AcaoRota(NamedTuple):
    """O que o botão da rota diz, se ele responde, e o que o clique faz."""

    rotulo: str
    sensivel: bool
    dica: str
    alvo: str


def acao_da_rota(estado: EstadoDaRota) -> AcaoRota:
    """Estado do botão da rota — função pura, e o coração da entrega 2."""
    if estado.no_controle:
        if estado.anterior:
            return AcaoRota(
                TEXTO_ROTA_VOLTAR,
                True,
                DICA_ROTA_VOLTAR.format(apelido=apelido_do_sink(estado.anterior)),
                estado.anterior,
            )
        return AcaoRota(TEXTO_ROTA_VOLTAR, False, DICA_ROTA_SEM_VOLTA, "")
    if not estado.sink_do_controle:
        return AcaoRota(TEXTO_ROTA_PARA_O_CONTROLE, False, DICA_ROTA_SEM_SINK, "")
    return AcaoRota(
        TEXTO_ROTA_PARA_O_CONTROLE,
        True,
        DICA_ROTA_PARA_O_CONTROLE,
        estado.sink_do_controle,
    )


class RotaDeSaida:
    """Lê e troca a saída padrão do sistema — por `pactl`, e reversível."""

    def __init__(
        self,
        *,
        runner: Callable[[list[str]], str] | None = None,
        ler_memoria: Callable[[], str] | None = None,
        gravar_memoria: Callable[[str], None] | None = None,
    ) -> None:
        self._runner = runner if runner is not None else rodar_leitura
        self._ler_memoria = ler_memoria if ler_memoria is not None else _ler_anterior
        self._gravar_memoria = (
            gravar_memoria if gravar_memoria is not None else _gravar_anterior
        )

    def estado(self, sink_do_controle: str) -> EstadoDaRota:
        """Fotografia da rota AGORA. Leitura pura de PipeWire, sem escrita."""
        padrao = sink_padrao_da_saida(self._runner(["pactl", "get-default-sink"]))
        no_controle = bool(sink_do_controle) and padrao == sink_do_controle
        lista_viva = self._runner(["pactl", "list", "sinks", "short"])
        anterior = ""
        if no_controle:
            guardado = self._ler_memoria()
            if (
                guardado
                and guardado != sink_do_controle
                and guardado in nomes_de_sinks(lista_viva)
            ):
                anterior = guardado
        return EstadoDaRota(
            sink_padrao=padrao,
            sink_do_controle=sink_do_controle,
            anterior=anterior,
            no_controle=no_controle,
            canais=estados_dos_sinks(lista_viva),
        )

    def mandar_para_o_controle(self, sink_do_controle: str) -> bool:
        """Saída padrão -> controle, **guardando de onde veio ANTES de trocar**."""
        if not sink_do_controle:
            return False
        lista_viva = self._runner(["pactl", "list", "sinks", "short"])
        vivos = nomes_de_sinks(lista_viva)
        if sink_do_controle not in vivos:
            return False
        atual = sink_padrao_da_saida(self._runner(["pactl", "get-default-sink"]))
        guardar = bool(atual) and atual != sink_do_controle
        if guardar and e_saida_de_controle(atual, lista_viva) and self._ler_memoria():
            guardar = False
        if guardar:
            self._gravar_memoria(atual)
        # O sink do DualSense estava `MUTED` no PipeWire, por estado que o
        # default-routes`) e restaura a cada conexão sem escrever nada em log
        garantir_saida_audivel(sink_do_controle, runner=self._runner)
        return self._trocar(sink_do_controle)

    def voltar_ao_anterior(self) -> bool:
        """Devolve a saída padrão ao sink guardado e ESQUECE a memória."""
        guardado = self._ler_memoria()
        if not guardado:
            return False
        vivos = nomes_de_sinks(self._runner(["pactl", "list", "sinks", "short"]))
        if guardado not in vivos:
            return False
        if not self._trocar(guardado):
            return False
        self._gravar_memoria("")
        return True

    def _trocar(self, sink: str) -> bool:
        """`pactl set-default-sink` e a CONFERÊNCIA de que pegou."""
        self._runner(["pactl", "set-default-sink", sink])
        return sink_padrao_da_saida(self._runner(["pactl", "get-default-sink"])) == sink


# `card.definir_pedido_de_rota(self._aplicar_rota_do_sistema)`, e aquele método


@dataclass(frozen=True)
class DesfechoDaRota:
    """O que aconteceu com o pedido de camada 1. `motivo` vazio = deu certo."""

    ok: bool
    motivo: str = ""
    sink: str = ""


#: Ela dizia *"este controle não publica placa de som — pelo rádio o DualSense
#: * a primeira continua exata — o DualSense **não** expõe placa ALSA própria
MOTIVO_ROTA_SEM_SINK: Final[str] = (
    "não achei a saída de som deste controle agora, então não há para onde "
    "mandar o som do computador. Se ele acabou de chegar, espere alguns "
    "segundos e clique de novo; se o Hefesto estiver parado, ligue-o na aba "
    "Sistema."
)

MOTIVO_ROTA_NAO_PEGOU: Final[str] = (
    "pedi ao PipeWire para mandar o som do PC a este controle e a saída padrão "
    "não mudou — o sink pode ter saído da lista entre o pedido e a conferência."
)

MOTIVO_ROTA_SEM_VOLTA: Final[str] = (
    "não há saída anterior guardada para devolver o som — ou ele não foi o "
    "Hefesto que o trouxe para cá, ou aquela saída não está mais na máquina."
)

MOTIVO_A_SAIDA_NAO_E_DESTE: Final[str] = (
    "a saída do PC não está neste controle, então não há o que devolver daqui."
)


def sink_do_controle(
    uniq: str,
    uniqs_na_mesa: list[str] | tuple[str, ...] = (),
    *,
    runner: Callable[[list[str]], str] | None = None,
) -> str:
    """O sink de SAÍDA deste controle — ``""`` quando não dá para saber."""
    ler = runner if runner is not None else rodar_leitura
    return _sink_do_controle(uniq, tuple(uniqs_na_mesa), runner=ler)


def mandar_o_som_do_pc(
    uniq: str,
    uniqs_na_mesa: list[str] | tuple[str, ...] = (),
    *,
    rota: RotaDeSaida | None = None,
    runner: Callable[[list[str]], str] | None = None,
) -> DesfechoDaRota:
    """Camada 1: a saída PADRÃO do sistema passa a ser o alto-falante deste controle."""
    alvo = sink_do_controle(uniq, uniqs_na_mesa, runner=runner)
    if not alvo:
        return DesfechoDaRota(False, MOTIVO_ROTA_SEM_SINK)
    motor = rota if rota is not None else RotaDeSaida(runner=runner)
    if not motor.mandar_para_o_controle(alvo):
        return DesfechoDaRota(False, MOTIVO_ROTA_NAO_PEGOU, alvo)
    return DesfechoDaRota(True, "", alvo)


def devolver_o_som_do_pc(
    *,
    de: str = "",
    uniqs_na_mesa: list[str] | tuple[str, ...] = (),
    rota: RotaDeSaida | None = None,
    runner: Callable[[list[str]], str] | None = None,
) -> DesfechoDaRota:
    """Camada 1, o desfazer: a saída padrão volta para onde estava.

    Recusa em vez de chutar um destino — ver :data:`MOTIVO_ROTA_SEM_VOLTA`.

    **SÓ DEVOLVE QUEM ESTÁ COM ELA — 24/09/2026, O-TERCEIRO-NOME-DELA-01.**
    Com ``de`` (o `uniq` de quem clicou), a saída só volta se ela estiver NESTE
    controle agora. O quarto botão da fileira do som («Tudo no Controle e Nada
    no PC») voltou por decisão dela de 23/09, e com ele uma mesa de quatro pode
    ter um controle segurando a saída do PC enquanto outro troca de botão.
    Sem esta pergunta, o «Efeitos do Jogo e Áudio do PC no Controle» do P3
    devolvia à TV a saída que o P1 tinha acabado de pedir — o clique de um
    jogador desfazendo o do outro, sem uma palavra na tela.

    Sem ``de`` o comportamento é o de antes, letra por letra: é quem não sabe
    de controle nenhum (o ensaio da rota, a porta da CLI).
    """
    if de:
        ler = runner if runner is not None else rodar_leitura
        deste = sink_do_controle(de, uniqs_na_mesa, runner=ler)
        padrao = sink_padrao_da_saida(ler(["pactl", "get-default-sink"]))
        if not deste or padrao != deste:
            return DesfechoDaRota(False, MOTIVO_A_SAIDA_NAO_E_DESTE)
    motor = rota if rota is not None else RotaDeSaida(runner=runner)
    if not motor.voltar_ao_anterior():
        return DesfechoDaRota(False, MOTIVO_ROTA_SEM_VOLTA)
    return DesfechoDaRota(True)


BYTE_SONS_DO_JOGO: Final[int] = SAIDA_L_FONE_R_ALTO_FALANTE

BYTE_TODO_O_SOM_DO_PC: Final[int] = SAIDA_SO_NO_ALTO_FALANTE

BYTE_NADA_NO_CONTROLE: Final[int] = SAIDA_ESTEREO_NO_FONE

MOTIVO_ROTA_SO_NO_BYTE: Final[str] = (
    "o alto-falante deste controle está roteado para receber todo o som, mas "
    "a saída padrão do sistema não é ele — o som continua saindo onde estava."
)


def botao_da_rota_aceso(
    byte: Any, sink_do_controle: str, sink_padrao: str
) -> str:
    """Qual dos dois botões acende: ``"jogo"``, ``"pc"`` ou ``""``. Função PURA.

    **ELA LÊ AS DUAS CAMADAS, e é essa a entrega.** Até 04/09/2026 a tela
    acendia "Todo o som do PC" pelo FIRMWARE e mais nada
    (`a02_controles.rota_na_tela`), e o resultado foi medido em 03/09: o card 2
    com o botão aceso e o som saindo na TV. O byte é a camada 2; quem decide
    onde o som sai é a camada 1, e *"a camada 1 vence a camada 2 — volume e
    rota perfeitos num sink mudo é trabalho invisível"* (`controller_card.py`).

    A tabela inteira, e cada linha tem razão:

    =====================  =========================  ==============
    byte                   camada 1                   acende
    =====================  =========================  ==============
    3 (todo o som do PC)   padrão É este controle     ``"pc"``
    3 (todo o som do PC)   padrão é outra saída       ``""`` (recado)
    2 (sons do jogo)       qualquer                   ``"jogo"``
    0 (nada no controle)   qualquer                   ``"nada"``
    1 ou ausente           qualquer                   ``""``
    =====================  =========================  ==============

    A segunda linha é a que não se adivinha: apagar OS DOIS é mais honesto que
    acender o errado, porque nenhum dos dois descreve o que está acontecendo —
    o firmware quer uma coisa e o sistema faz outra. Quem diz isso em palavras
    é :func:`recado_da_rota`.

    **A ROTA 0 GANHOU BOTÃO EM 21/09/2026** e deixou esta lista: ela é «Tudo
    na TV e Nada no Controle», o terceiro nome dela. A rota 1 (mono no fone)
    continua apagando os três de propósito — é rota legítima do protocolo que
    a fileira não representa, e acender a mais parecida seria arredondar.

    ``sink_do_controle`` vazio é o RÁDIO — o DualSense não publica placa de som
    por Bluetooth. Aí a camada 1 não tem como estar no controle, e "pc" nunca
    acende: a recusa honesta já está em :data:`MOTIVO_ROTA_SEM_SINK`.
    """
    if isinstance(byte, bool) or not isinstance(byte, int):
        return ""
    if byte == BYTE_SONS_DO_JOGO:
        return "jogo"
    if byte == BYTE_NADA_NO_CONTROLE:
        return "nada"
    if byte != BYTE_TODO_O_SOM_DO_PC:
        return ""
    if sink_do_controle and sink_padrao == sink_do_controle:
        return "pc"
    return ""


def recado_da_rota(byte: Any, sink_do_controle: str, sink_padrao: str) -> str:
    """A frase para o cartão quando as duas camadas discordam; ``""`` senão."""
    if isinstance(byte, bool) or not isinstance(byte, int):
        return ""
    if byte != BYTE_TODO_O_SOM_DO_PC:
        return ""
    if sink_do_controle and sink_padrao == sink_do_controle:
        return ""
    return MOTIVO_ROTA_SO_NO_BYTE


@dataclass(frozen=True)
class RotaDasDuasCamadas:
    """O que as duas camadas dizem sobre a saída de UM controle.

    `byte` é a camada 2 (o `speaker.rota` do `state_full`), `sink_do_controle`
    e `sink_padrao` são a camada 1 (o PipeWire). Os três juntos são a única
    resposta honesta a *"o som deste controle está recebendo o quê"*.
    """

    byte: int | None = None
    sink_do_controle: str = ""
    sink_padrao: str = ""

    @property
    def botao_aceso(self) -> str:
        """``"jogo"``, ``"pc"`` ou ``""`` — o que a tela pode afirmar."""
        return botao_da_rota_aceso(self.byte, self.sink_do_controle, self.sink_padrao)

    @property
    def no_controle(self) -> bool:
        """A saída padrão do sistema É a placa deste controle (camada 1)."""
        return bool(self.sink_do_controle) and self.sink_padrao == self.sink_do_controle

    @property
    def concordam(self) -> bool:
        """As duas camadas contam a mesma história."""
        return not recado_da_rota(self.byte, self.sink_do_controle, self.sink_padrao)

    @property
    def recado(self) -> str:
        """A frase do cartão quando elas discordam; ``""`` quando concordam."""
        return recado_da_rota(self.byte, self.sink_do_controle, self.sink_padrao)


def ler_as_duas_camadas(
    uniq: str,
    byte: Any,
    uniqs_na_mesa: list[str] | tuple[str, ...] = (),
    *,
    runner: Callable[[list[str]], str] | None = None,
) -> RotaDasDuasCamadas:
    """Junta o byte (que quem chama já tem) com o que o PipeWire diz. Bloqueante.

    O byte vem do `state_full` e NÃO se relê aqui: quem o publica é o daemon,
    e uma segunda leitura seria a segunda verdade. O que falta é a camada 1, e
    ela sai dos dois donos que já existem — `sink_do_controle` (o mesmo
    casamento por dispositivo USB que o `MicMonitor` faz) e a saída padrão do
    sistema, pela mesma leitura de `pactl` que `RotaDeSaida` usa.

    Bloqueante como todo este módulo: quem chama é `ipc_bridge.run_in_thread`.
    """
    ler = runner if runner is not None else rodar_leitura
    padrao = sink_padrao_da_saida(ler(["pactl", "get-default-sink"]))
    do_controle = sink_do_controle(uniq, uniqs_na_mesa, runner=ler)
    lido = byte if isinstance(byte, int) and not isinstance(byte, bool) else None
    return RotaDasDuasCamadas(
        byte=lido, sink_do_controle=do_controle, sink_padrao=padrao
    )


def _ambiente_c() -> dict[str, str]:
    """Ambiente com locale neutro — a saída do `pactl` é TRADUZIDA."""
    env = dict(os.environ)
    env["LC_ALL"] = "C"
    env["LANG"] = "C"
    return env


def rodar_leitura(argv: list[str]) -> str:
    """Roda um `pactl` curto e devolve o stdout ("" em qualquer falha)."""
    from hefesto_dualsense4unix.integrations import retrato_do_som

    resposta = retrato_do_som.responder(argv)
    if resposta is not None:
        return resposta if isinstance(resposta, str) else ""
    if shutil.which(argv[0]) is None:
        return ""
    try:
        proc = subprocess.run(
            argv,
            timeout=_TIMEOUT_LEITURA_S,
            check=False,
            capture_output=True,
            text=True,
            env=_ambiente_c(),
        )
    except Exception as exc:
        logger.debug("audio_saida_comando_falhou", argv=argv[0], err=str(exc))
        return ""
    finally:
        retrato_do_som.escreveu(argv)
    return proc.stdout or ""


def _rodar_tocador(argv: list[str]) -> int:
    """Roda o tocador e devolve o código de saída (não-zero em qualquer falha)."""
    try:
        proc = subprocess.run(
            argv,
            timeout=_TIMEOUT_TOCADOR_S,
            check=False,
            capture_output=True,
            env=_ambiente_c(),
        )
    except Exception as exc:
        logger.debug("audio_saida_tocador_falhou", argv=argv[0], err=str(exc))
        return -1
    return int(proc.returncode)


def _carregar_prefs() -> dict[str, Any]:
    from hefesto_dualsense4unix.app.gui_prefs import load_gui_prefs

    return load_gui_prefs()


def _ler_anterior() -> str:
    valor = _carregar_prefs().get(CHAVE_PREF_ROTA_ANTERIOR, "")
    return valor if isinstance(valor, str) else ""


def _gravar_anterior(sink: str) -> None:
    from hefesto_dualsense4unix.app.gui_prefs import set_pref

    set_pref(CHAVE_PREF_ROTA_ANTERIOR, sink)


NOME_REGRA_NUNCA_DORME: Final[str] = "54-hefesto-dualsense-alto-falante-nunca-dorme.conf"

ESTADO_SUSPENSO: Final[str] = "SUSPENDED"

TEXTO_SONO_ACORDADO: Final[str] = "Alto-falante acordado — o som sai desde o primeiro instante"

TEXTO_SONO_ATRASADO: Final[str] = (
    "Alto-falante ainda dormindo — a regra entrou depois deste controle; "
    "reconecte-o para valer"
)

#: Não há placa de som do controle na mesa. Não é defeito: por rádio o DualSense
TEXTO_SONO_SEM_PLACA: Final[str] = (
    "Sem placa de som do controle (no rádio o DualSense não publica placa ALSA)"
)

TEXTO_SONO_PODE_DORMIR: Final[str] = (
    "Alto-falante pode dormir — o primeiro som depois do silêncio se perde"
)


def caminho_regra_nunca_dorme(home: str | None = None) -> str:
    """Onde o drop-in 54 mora depois de instalado (não garante que exista)."""
    base = home if home is not None else os.path.expanduser("~")
    return os.path.join(
        base, ".config", "wireplumber", "wireplumber.conf.d", NOME_REGRA_NUNCA_DORME
    )


def regra_nunca_dorme_instalada(home: str | None = None) -> bool:
    """A regra que impede o sono do alto-falante está no lugar?"""
    return os.path.isfile(caminho_regra_nunca_dorme(home))


def e_saida_de_controle(sink: str, saida_pactl: str) -> bool:
    """Este sink é a saída de um controle? PURA sobre `pactl list sinks short`.

    Os dois donos que já respondem isso, juntos: a placa de um DualSense no
    cabo (``mic_monitor.sinks_dualsense``) e o nó que esta casa publica por
    controle (``hefesto_som_<hex6>``, a saída no rádio). Quem precisa dela é a
    memória da :class:`RotaDeSaida` — ver `mandar_para_o_controle`.

    **O NOME DO NÓ SE LÊ PELO DONO DELE** (28/09/2026):
    ``alto_falante_bt.sufixo_do_sink_do_som``, o leitor do que
    ``nome_do_sink`` escreve. Até aqui esta função casava o prefixo à mão, e
    qualquer ``hefesto_som_…`` sem o rabo de endereço passava por nó de
    controle.
    """
    from hefesto_dualsense4unix.app.mic_monitor import sinks_dualsense

    if not sink:
        return False
    return bool(sufixo_do_sink_do_som(sink)) or sink in sinks_dualsense(saida_pactl)


def sono_dos_sinks_do_controle(saida_pactl: str) -> dict[str, str]:
    """``{nome do sink do controle: ESTADO}`` a partir de `pactl list sinks short`.

    Quem decide "este sink é de um DualSense" continua sendo
    ``mic_monitor.sinks_dualsense`` — o dono desse critério nesta janela. Aqui
    só se acrescenta a coluna que faltava: o ESTADO, que quem lê é
    :func:`estados_crus_dos_sinks`, o parser único da coluna (SOM-ACORDADO-01
    juntou os dois que tinham nascido no mesmo dia).
    """
    from hefesto_dualsense4unix.app.mic_monitor import sinks_dualsense

    do_controle = set(sinks_dualsense(saida_pactl))
    return {
        nome: cru
        for nome, cru in estados_crus_dos_sinks(saida_pactl).items()
        if nome in do_controle
    }


def texto_do_sono(instalada: bool, estados: dict[str, str]) -> str:
    """O que a aba Status escreve, dados os dois fatos que ela consegue saber."""
    if not instalada:
        return TEXTO_SONO_PODE_DORMIR
    if not estados:
        return TEXTO_SONO_SEM_PLACA
    if any(estado == ESTADO_SUSPENSO for estado in estados.values()):
        return TEXTO_SONO_ATRASADO
    return TEXTO_SONO_ACORDADO


def estado_do_sono(home: str | None = None) -> str:
    """A leitura completa numa frase só. BLOQUEIA — rode em worker.

    Mesma disciplina do resto do módulo: nada de subprocess na thread do GTK
    (use ``ipc_bridge.run_in_thread``, o padrão do card).

    NOTA DATADA — 18/08/2026: **a tela já diz isto, por outro caminho, e esta
    composição não tem chamador de propósito.** O item 6 da
    ``SOM-QUE-NAO-DORME-01`` (*"a aba Status consegue dizer o estado —
    inclusive denunciar a cura arrancada"*) foi entregue pela
    ``SOM-ACORDADO-01``, que mediu o desenho e escolheu dizer o estado POR
    CONTROLE, no rótulo da moldura de cada card, em vez de uma frase global:
    ``RotaDeSaida.estado`` publica os canais (:786 e :817 acima, via
    :func:`estados_dos_sinks`), ``status_actions.py``:1038 lê a regra na MESMA
    worker, :1249 entrega os dois ao card por ``definir_estado_do_canal``, e
    ``controller_card.py``:4216-4224 escreve as frases — inclusive a
    ``dica_canal_sem_a_regra()``, que é a cura arrancada sendo denunciada.

    Por isso ela **não deve ganhar chamador na janela**: seria um segundo
    leitor de PipeWire aqui dentro (`controller_card.py`:4044-4049 escreve por que
    isso é defeito) para repetir o que já está na tela. O corpo fica de pé
    porque é a única forma de perguntar as duas coisas de uma vez fora da
    janela, e porque podar símbolo público é decisão DELA, não deste módulo.
    """
    saida = rodar_leitura(["pactl", "list", "sinks", "short"])
    return texto_do_sono(regra_nunca_dorme_instalada(home), sono_dos_sinks_do_controle(saida))


__all__ = [
    "BYTE_SONS_DO_JOGO",
    "BYTE_TODO_O_SOM_DO_PC",
    "CANAL_ACORDADO",
    "CANAL_DORMINDO",
    "CANAL_SEM_LEITURA",
    "CHAVE_PREF_ROTA_ANTERIOR",
    "CHAVE_PREF_SOM",
    "DICA_ROTA_PARA_O_CONTROLE",
    "DICA_ROTA_SEM_SINK",
    "DICA_ROTA_SEM_VOLTA",
    "DICA_ROTA_VOLTAR",
    "ESTADO_SUSPENSO",
    "MOTIVO_A_SAIDA_NAO_E_DESTE",
    "MOTIVO_DESLIGADO",
    "MOTIVO_FALHOU",
    "MOTIVO_OCUPADO",
    "MOTIVO_ROTA_NAO_PEGOU",
    "MOTIVO_ROTA_SEM_SINK",
    "MOTIVO_ROTA_SEM_VOLTA",
    "MOTIVO_ROTA_SO_NO_BYTE",
    "MOTIVO_SAIDA_MUDA",
    "MOTIVO_SEM_ARQUIVO",
    "MOTIVO_SEM_SINK",
    "MOTIVO_SEM_TOCADOR",
    "MOTIVO_TOCOU",
    "NOME_REGRA_NUNCA_DORME",
    "RECADOS",
    "TEXTO_ROTA_PARA_O_CONTROLE",
    "TEXTO_ROTA_VOLTAR",
    "TEXTO_SONO_ACORDADO",
    "TEXTO_SONO_ATRASADO",
    "TEXTO_SONO_PODE_DORMIR",
    "TEXTO_SONO_SEM_PLACA",
    "AcaoRota",
    "DesfechoDaRota",
    "EstadoDaRota",
    "ResultadoDoSom",
    "RotaDasDuasCamadas",
    "RotaDeSaida",
    "acao_da_rota",
    "acordar_sink",
    "apelido_do_sink",
    "argv_do_tocador",
    "arquivo_de_confirmacao",
    "botao_da_rota_aceso",
    "caminho_regra_nunca_dorme",
    "devolver_o_som_do_pc",
    "e_saida_de_controle",
    "estado_do_canal",
    "estado_do_sono",
    "estados_crus_dos_sinks",
    "estados_dos_sinks",
    "ler_as_duas_camadas",
    "mandar_o_som_do_pc",
    "nomes_de_sinks",
    "recado_da_rota",
    "regra_nunca_dorme_instalada",
    "rodar_leitura",
    "sink_do_controle",
    "sink_padrao_da_saida",
    "som_ligado",
    "sono_dos_sinks_do_controle",
    "texto_do_sono",
    "tocar_confirmacao",
]

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
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final, NamedTuple

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: Chave em ``gui_preferences.json`` que desliga o som de confirmação.
CHAVE_PREF_SOM: Final[str] = "som_de_confirmacao"

#: Chave em ``gui_preferences.json`` com o sink que estava valendo ANTES de a
#: janela mandar o som para o controle. Persiste entre execuções de propósito:
#: a troca de saída padrão é do SISTEMA e sobrevive ao fechamento da janela
#: (é a mesma troca que as configurações de som fazem). Guardar só em memória
#: deixaria a saída dela presa no controle sem nenhum caminho de volta pela
#: janela depois de um simples fechar-e-abrir.
CHAVE_PREF_ROTA_ANTERIOR: Final[str] = "rota_de_som_anterior"

#: Tempo máximo de um `pactl`. Um PipeWire morto não pode segurar a worker.
_TIMEOUT_LEITURA_S: Final[float] = 2.0

#: Tempo máximo do tocador. O som escolhido tem 67ms e o gasto medido de ponta
#: a ponta foi de 0,35s (o resto é abrir o fluxo). Cinco segundos é folga de
#: uma ordem de grandeza e ainda assim mata um tocador pendurado.
_TIMEOUT_TOCADOR_S: Final[float] = 5.0

# ---------------------------------------------------------------------------
# O som: qual arquivo, por quê, e quanto ele dura
# ---------------------------------------------------------------------------

#: Raízes onde o tema de sons do freedesktop pode estar. A primeira é a de
#: qualquer distribuição; `/usr/local` cobre instalação à mão e `/app` cobre o
#: Flatpak, que este projeto empacota (`flatpak/`).
_RAIZES_DE_SOM: Final[tuple[str, ...]] = (
    "/usr/share/sounds",
    "/usr/local/share/sounds",
    "/app/share/sounds",
)

#: Os candidatos, na ordem, com a duração MEDIDA nesta bancada (ffprobe):
#:
#: ===============================  =========  ==========================
#: arquivo                          duração    por que nesta posição
#: ===============================  =========  ==========================
#: freedesktop/audio-volume-change  0,067s     é o nome que a especificação
#:                                             de sons do freedesktop dá a
#:                                             "mudou o volume" — o som certo
#:                                             para o gesto certo, e o mais
#:                                             curto dos candidatos
#: freedesktop/bell                 0,139s     o clássico, presente em todo
#:                                             tema que se diga freedesktop
#: freedesktop/dialog-information   0,061s     terceiro sinal do mesmo tema
#: alsa/Front_Center.wav            ~1,0s      NÃO é do tema: vem do pacote
#:                                             `alsa-utils`, e entra como
#:                                             último recurso para máquina sem
#:                                             tema de som nenhum
#: ===============================  =========  ==========================
#:
#: ``complete.oga`` (1,09s) e ``message.oga`` (0,31s) foram medidos e ficaram
#: de fora: um som longo atrapalha exatamente quem está ajustando o volume,
#: que é o gesto que mais dispara este som. E ``window-attention.oga`` desta
#: máquina tem 18 bytes — existe e não toca —, que é a razão de o teto de
#: tamanho mínimo estar em :data:`_TAMANHO_MINIMO_DE_SOM`.
_CANDIDATOS_DE_SOM: Final[tuple[str, ...]] = (
    "freedesktop/stereo/audio-volume-change.oga",
    "freedesktop/stereo/bell.oga",
    "freedesktop/stereo/dialog-information.oga",
    "alsa/Front_Center.wav",
)

#: Piso de bytes para um arquivo de som contar como utilizável. Medido: o
#: `window-attention.oga` desta máquina tem 18 bytes e o tocador sai com zero
#: sem emitir som — exatamente a falha calada que esta leva não pode ter.
_TAMANHO_MINIMO_DE_SOM: Final[int] = 256

#: Tocadores, na ordem de preferência, com o modelo de argumentos. O sink entra
#: como ARGUMENTO próprio e nunca por texto de comando (nada de ``shell=True``,
#: invariante do projeto).
_TOCADORES: Final[tuple[tuple[str, str], ...]] = (
    ("paplay", "--device={sink}"),
    ("pw-play", "--target={sink}"),
)

# ---------------------------------------------------------------------------
# Motivos — o vocabulário de "por que não deu para confirmar"
# ---------------------------------------------------------------------------

MOTIVO_TOCOU: Final[str] = "tocou"
MOTIVO_DESLIGADO: Final[str] = "desligado"
MOTIVO_OCUPADO: Final[str] = "ocupado"
MOTIVO_SEM_SINK: Final[str] = "sem_sink"
MOTIVO_SAIDA_MUDA: Final[str] = "saida_muda"
MOTIVO_SEM_ARQUIVO: Final[str] = "sem_arquivo"
MOTIVO_SEM_TOCADOR: Final[str] = "sem_tocador"
MOTIVO_FALHOU: Final[str] = "falhou"

#: O que a tela diz em cada motivo. String vazia = **nada a dizer**, e os dois
#: casos vazios são de propósito:
#:
#: * ``tocou`` — o som É o recado; escrever "toquei" ao lado dele é ruído;
#: * ``desligado`` — ela desligou a confirmação; avisar que não confirmou seria
#:   discutir a escolha dela a cada gesto;
#: * ``ocupado`` — o som anterior ainda está tocando. Não é falha: é o
#:   antirrajada, e ele já vai ser ouvido.
#:
#: Os demais SÃO recados: um clique que promete som e não entrega é pior que
#: nenhum som, e errar calado é a falha que esta leva não pode ter.
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
    """O que aconteceu com o pedido de tocar, e o que a tela deve dizer.

    ``recado`` vazio quer dizer **não há o que dizer** (ver :data:`RECADOS`),
    e nunca "deu tudo certo": quem quer saber se saiu som lê ``tocou``.
    """

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


# ---------------------------------------------------------------------------
# Leitura do PipeWire — pura, e sobre a lista INTEIRA de sinks
# ---------------------------------------------------------------------------


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
    """Nome do sink padrão em `pactl get-default-sink`; "" se ilegível.

    A resposta é uma linha só com o nome. Qualquer outra coisa vira "" — e ""
    aqui significa **não sei**, que é o que mantém o botão da rota parado em
    vez de chutar.
    """
    for linha in saida_pactl.splitlines():
        nome = linha.strip()
        if nome and not nome.startswith("Failure"):
            return nome
    return ""


def apelido_do_sink(nome: str) -> str:
    """Pedaço legível do nome de um sink, para caber numa dica.

    ``alsa_output.pci-0000_0a_00.1.hdmi-stereo`` vira ``hdmi-stereo``. É o
    último segmento pontuado, que no esquema de nomes do PipeWire é justamente
    o perfil da porta — a parte que uma pessoa reconhece. Sem casamento,
    devolve o nome inteiro: melhor longo que errado.
    """
    limpo = nome.strip()
    if not limpo:
        return ""
    segmento = limpo.rsplit(".", 1)[-1]
    return segmento or limpo


# ---------------------------------------------------------------------------
# Entrega 1 — o som de confirmação
# ---------------------------------------------------------------------------


def arquivo_de_confirmacao(
    *,
    raizes: tuple[str, ...] = _RAIZES_DE_SOM,
    candidatos: tuple[str, ...] = _CANDIDATOS_DE_SOM,
    tamanho: Callable[[str], int] | None = None,
) -> str:
    """Primeiro som utilizável da lista de candidatos; "" se não houver nenhum.

    A ordem dos candidatos manda mais que a das raízes: um `bell.oga` de
    `/usr/share` vence um `audio-volume-change.oga` de `/app/share`? **Não** —
    o laço externo é o do CANDIDATO, e é isso que garante que a máquina com o
    tema completo toque o som semanticamente certo (o de "mudou o volume") e
    não o primeiro que aparecer.

    "Utilizável" inclui um piso de tamanho: ver
    :data:`_TAMANHO_MINIMO_DE_SOM` e o `window-attention.oga` de 18 bytes que
    o motivou.
    """
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
    # `None` = ilegível. Desmuta-se do mesmo jeito (o pedido dela é o mesmo) e
    # devolve-se False, porque "não sei se estava mudo" não é "estava".
    antes = muted_de_saida(rodar(["pactl", "get-sink-mute", sink]))
    rodar(["pactl", "set-sink-mute", sink, "0"])
    return antes is True


#: Trava de UM som por vez. É a segunda camada do antirrajada: a primeira é o
#: repouso de 250ms do controle deslizante, no card. Esta existe porque o
#: repouso é por WIDGET e o tocador leva ~0,35s — sem ela, um gesto longo
#: enfileiraria processos no executor de uma worker só do `ipc_bridge` e os
#: sons chegariam depois do gesto, fora de hora.
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
    3. **sem sink**: nome vazio. Com mais de um controle o
       ``mic_monitor.escolher_sink`` devolve ``None`` de propósito (o ``-00``
       do nome é desempate posicional do PipeWire, não identidade), e é isso
       que chega aqui como "";
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
        if sink not in nomes_de_sinks(ler(["pactl", "list", "sinks", "short"])):
            # A guarda-mãe deste módulo. Ver o cabeçalho: os dois tocadores
            # aceitam sink inexistente, saem com zero e tocam no PADRÃO.
            return ResultadoDoSom.de(MOTIVO_SEM_SINK, sink)
        arquivo = arquivo_de_confirmacao()
        if not arquivo:
            return ResultadoDoSom.de(MOTIVO_SEM_ARQUIVO, sink)
        argv = argv_do_tocador(sink, arquivo, achar=achar)
        if not argv:
            return ResultadoDoSom.de(MOTIVO_SEM_TOCADOR, sink)
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
    except Exception as exc:  # preferência ilegível nunca cala a janela
        logger.debug("audio_saida_pref_som_ilegivel", err=str(exc))
        return True
    return bool(valor) if isinstance(valor, bool) else True


# ---------------------------------------------------------------------------
# Entrega 2 — a rota de saída do sistema
# ---------------------------------------------------------------------------

TEXTO_ROTA_PARA_O_CONTROLE: Final[str] = "Ouvir no controle"
TEXTO_ROTA_VOLTAR: Final[str] = "Voltar ao anterior"

#: A dica que o botão carrega NO GLADE, antes da primeira leitura do `pactl`.
#: Ela existe por uma regra desta casa que tem teste próprio
#: (`test_palavra_a_janela_fala_a_lingua`): nenhum controle que muda alguma
#: coisa fica mudo na tela.
#:
#: O texto é o único que é verdade nos QUATRO estados do botão, e por isso não
#: é uma cópia de :data:`DICA_ROTA_PARA_O_CONTROLE`: nos dois primeiros
#: segundos a janela ainda não sabe onde o som está, e prometer "manda para o
#: controle" ali seria afirmar a ação de um botão que pode nascer insensível
#: (mais de um DualSense, ou som já no controle sem memória de quem o pôs lá).
#: Assim que a leitura chega, `acao_da_rota` troca por uma das três dicas
#: específicas.
DICA_ROTA_INICIAL: Final[str] = (
    "Manda o som do sistema para o alto-falante do controle, e desfaz. O "
    "rótulo do botão diz o que o próximo clique faz, e a dica muda junto com "
    "ele assim que a janela ler a saída de áudio."
)

#: A dica do estado "manda para o controle". Ela diz, ANTES do clique, as duas
#: coisas que uma pessoa não adivinha: que a troca vale para o sistema INTEIRO
#: (não só para o jogo) e que ela sobrevive ao fechamento da janela — porque é
#: literalmente a mesma troca que as configurações de som do sistema fazem.
DICA_ROTA_PARA_O_CONTROLE: Final[str] = (
    "Manda o som do sistema INTEIRO para o alto-falante do controle: jogo, "
    "navegador, notificações, tudo. É a mesma troca de saída padrão que as "
    "configurações de som do sistema fazem, e ela continua valendo depois de "
    "fechar esta janela. A janela guarda a saída de agora para o botão de "
    "volta."
)
DICA_ROTA_VOLTAR: Final[str] = (
    "Devolve o som do sistema para {apelido}, que era a saída antes de a "
    "janela mandá-lo para o controle. O alto-falante do controle continua "
    "existindo: ele só deixa de receber o áudio do sistema."
)
#: Sem sink atribuível. Com um controle só isso quer dizer que o sistema não
#: publicou saída nenhuma para ele; com dois ou mais é a recusa DELIBERADA do
#: `escolher_sink`, e a dica diz por quê em vez de deixar o botão morto e mudo.
DICA_ROTA_SEM_SINK: Final[str] = (
    "Não há saída de áudio atribuível a este controle. Com mais de um "
    "DualSense ligado o sistema publica sinks com o mesmo nome (o número no "
    "fim é a ordem de conexão, não o número de série do controle) e mandar o "
    "som para o controle errado é pior que não mandar."
)
#: O som JÁ está no controle e não fomos nós. Não dá para desfazer o que não
#: fizemos: qualquer sink que a janela escolhesse aqui seria chute sobre a
#: saída que ela usava antes.
DICA_ROTA_SEM_VOLTA: Final[str] = (
    "O som do sistema já está saindo no controle, e não foi esta janela que o "
    "mandou para lá — não há como saber para onde voltar. Escolha a saída nas "
    "configurações de som do sistema."
)


@dataclass(frozen=True)
class EstadoDaRota:
    """Onde o som do sistema está, para onde ele pode ir, e de onde ele veio.

    ``anterior`` só tem valor quando **a janela** foi quem mandou o som para o
    controle e o sink guardado ainda existe. É a diferença entre poder desfazer
    e poder chutar.
    """

    sink_padrao: str = ""
    sink_do_controle: str = ""
    anterior: str = ""
    no_controle: bool = False


class AcaoRota(NamedTuple):
    """O que o botão da rota diz, se ele responde, e o que o clique faz.

    ``alvo`` é o sink que o clique escreveria — "" quando não há clique a dar.
    O rótulo diz a AÇÃO, no padrão da casa (o botão do microfone e o
    ``Devolver`` do alto-falante são o molde): nada de "Ativar/Desativar",
    que não diz em que estado se está nem para onde se vai.
    """

    rotulo: str
    sensivel: bool
    dica: str
    alvo: str


def acao_da_rota(estado: EstadoDaRota) -> AcaoRota:
    """Estado do botão da rota — função pura, e o coração da entrega 2.

    A tabela inteira, e cada linha tem razão medida:

    ==================================  ===================  ==============
    situação                            rótulo               sensível
    ==================================  ===================  ==============
    sem sink do controle                Ouvir no controle    **não**
    som fora do controle                Ouvir no controle    sim
    som no controle, fomos nós          Voltar ao anterior   sim
    som no controle, não fomos nós      Voltar ao anterior   **não**
    ==================================  ===================  ==============

    A última linha é a que não se adivinha: com o som já no controle e sem
    memória de quem o pôs lá, **não existe desfazer honesto**. Escolher um sink
    qualquer para "voltar" seria a janela decidindo qual é a saída dela — a
    mesma família de erro que produziu "a config que eu deixo nunca é
    respeitada". O botão fica insensível e a dica manda para as configurações
    do sistema, que é quem sabe.
    """
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
    """Lê e troca a saída padrão do sistema — por `pactl`, e reversível.

    Tudo bloqueante: quem chama é ``ipc_bridge.run_in_thread``.

    **Não inventa um segundo leitor do sink do controle.** Quem sabe qual sink
    é de qual controle continua sendo o ``mic_monitor`` (``escolher_sink``),
    que já roda fora da thread do GTK com cadência própria; o nome chega aqui
    pronto, pelo argumento ``sink_do_controle``. O que este objeto lê por conta
    própria é o que o ``mic_monitor`` não tem por que saber: **qual é a saída
    PADRÃO do sistema** — um fato global, não um fato do controle.

    ``memoria`` é o par ler/gravar do sink anterior. O padrão é
    ``gui_preferences.json``; o teste injeta um dicionário.
    """

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
        """Fotografia da rota AGORA. Leitura pura de PipeWire, sem escrita.

        A memória do sink anterior é conferida contra a lista viva: um sink
        guardado que sumiu (o monitor foi desligado, o dongle saiu) não pode
        virar destino de um clique — voltar para um sink inexistente é o
        `pactl` recusando em silêncio e a janela achando que desfez.
        """
        padrao = sink_padrao_da_saida(self._runner(["pactl", "get-default-sink"]))
        no_controle = bool(sink_do_controle) and padrao == sink_do_controle
        anterior = ""
        if no_controle:
            guardado = self._ler_memoria()
            if guardado and guardado != sink_do_controle:
                vivos = nomes_de_sinks(
                    self._runner(["pactl", "list", "sinks", "short"])
                )
                if guardado in vivos:
                    anterior = guardado
        return EstadoDaRota(
            sink_padrao=padrao,
            sink_do_controle=sink_do_controle,
            anterior=anterior,
            no_controle=no_controle,
        )

    def mandar_para_o_controle(self, sink_do_controle: str) -> bool:
        """Saída padrão -> controle, **guardando de onde veio ANTES de trocar**.

        A ordem é a entrega: gravar depois de trocar deixaria uma janela de
        tempo em que o `pactl` já mudou e a memória ainda não — e uma queda ali
        dentro apagaria para sempre o caminho de volta. Guarda-se primeiro, e
        só então se escreve.

        Recusa quando o sink não está na lista viva, pelo mesmo motivo do
        tocador: `pactl set-default-sink <inexistente>` não é um caminho que
        esta janela deva exercitar às cegas.
        """
        if not sink_do_controle:
            return False
        vivos = nomes_de_sinks(self._runner(["pactl", "list", "sinks", "short"]))
        if sink_do_controle not in vivos:
            return False
        atual = sink_padrao_da_saida(self._runner(["pactl", "get-default-sink"]))
        if atual and atual != sink_do_controle:
            self._gravar_memoria(atual)
        # SOM-SAIDA-MUDA-01, 04/08/2026 — MEDIDO com ela: o seletor mandava o
        # som para o controle, o `pactl` obedecia, e NÃO SAÍA NADA.
        #
        # O sink do DualSense estava `MUTED` no PipeWire, por estado que o
        # WirePlumber PERSISTE por rota (`~/.local/state/wireplumber/
        # default-routes`) e restaura a cada conexão sem escrever nada em log
        # nenhum. Era a saída padrão do sistema, muda, e a tela dizia que o som
        # tinha ido para o controle — porque tinha mesmo.
        #
        # A casa já conhecia este mecanismo do lado da CAPTURA: é a "camada 1"
        # do microfone mudo, que o `doctor.sh` confere e cura. Faltava o
        # espelho na SAÍDA, e é o furo que este bloco fecha.
        #
        # Desmutar aqui não atropela escolha dela: o gesto que chega até esta
        # linha é ela pedindo o som NO CONTROLE. Um mute herdado de outra
        # sessão não é uma opinião sobre este pedido — e deixá-lo de pé faria
        # o produto obedecer pela metade, que foi exatamente o sintoma.
        #
        # Best-effort, e nesta ordem: se o `set-mute` falhar, a troca de sink
        # ainda vale (o som pode estar audível por outro caminho), e é o
        # `_trocar` que decide o retorno — não queremos que "não consegui
        # desmutar" vire "não troquei".
        garantir_saida_audivel(sink_do_controle, runner=self._runner)
        return self._trocar(sink_do_controle)

    def voltar_ao_anterior(self) -> bool:
        """Devolve a saída padrão ao sink guardado e ESQUECE a memória.

        Esquecer é parte do desfazer: uma memória que sobrevive ao retorno
        faria o próximo ``estado()`` oferecer "voltar" para um lugar onde o som
        já está.
        """
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
        """`pactl set-default-sink` e a CONFERÊNCIA de que pegou.

        Conferir relendo não é zelo: o `pactl` responde sem erro em casos em
        que a troca não vale, e a janela que acredita na própria escrita é a
        janela que mente na tela.
        """
        self._runner(["pactl", "set-default-sink", sink])
        return sink_padrao_da_saida(self._runner(["pactl", "get-default-sink"])) == sink


# ---------------------------------------------------------------------------
# Bordas com o sistema
# ---------------------------------------------------------------------------


def _ambiente_c() -> dict[str, str]:
    """Ambiente com locale neutro — a saída do `pactl` é TRADUZIDA."""
    env = dict(os.environ)
    env["LC_ALL"] = "C"
    env["LANG"] = "C"
    return env


def rodar_leitura(argv: list[str]) -> str:
    """Roda um `pactl` curto e devolve o stdout ("" em qualquer falha).

    Mesma disciplina do runner do ``mic_monitor``: nunca ``shell=True``,
    sempre com timeout, e a checagem de disponibilidade da ferramenta mora
    AQUI — assim um runner dublado no teste não depende do que está instalado
    na máquina que roda a suíte.
    """
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
    return proc.stdout or ""


def _rodar_tocador(argv: list[str]) -> int:
    """Roda o tocador e devolve o código de saída (não-zero em qualquer falha).

    O ``-1`` de exceção existe porque um timeout aqui é falha de verdade: o som
    tem 67ms e o teto é de 5s. Ficar preso é o tocador pendurado, e a tela tem
    de saber que não houve confirmação.
    """
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


__all__ = [
    "CHAVE_PREF_ROTA_ANTERIOR",
    "CHAVE_PREF_SOM",
    "DICA_ROTA_PARA_O_CONTROLE",
    "DICA_ROTA_SEM_SINK",
    "DICA_ROTA_SEM_VOLTA",
    "DICA_ROTA_VOLTAR",
    "MOTIVO_DESLIGADO",
    "MOTIVO_FALHOU",
    "MOTIVO_OCUPADO",
    "MOTIVO_SAIDA_MUDA",
    "MOTIVO_SEM_ARQUIVO",
    "MOTIVO_SEM_SINK",
    "MOTIVO_SEM_TOCADOR",
    "MOTIVO_TOCOU",
    "RECADOS",
    "TEXTO_ROTA_PARA_O_CONTROLE",
    "TEXTO_ROTA_VOLTAR",
    "AcaoRota",
    "EstadoDaRota",
    "ResultadoDoSom",
    "RotaDeSaida",
    "acao_da_rota",
    "apelido_do_sink",
    "argv_do_tocador",
    "arquivo_de_confirmacao",
    "nomes_de_sinks",
    "rodar_leitura",
    "sink_padrao_da_saida",
    "som_ligado",
    "tocar_confirmacao",
]

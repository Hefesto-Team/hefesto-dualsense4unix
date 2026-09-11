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
    SAIDA_L_FONE_R_ALTO_FALANTE,
    SAIDA_SO_NO_ALTO_FALANTE,
)

# O DONO DA ROTA MUDOU DE ENDEREÇO EM 09/09/2026, e este bloco é a ponte.
# `integrations/alto_falante_bt` é quem responde *"onde este nó entrega?"*,
# porque o DAEMON precisa da resposta e não importa nada de `app/`. Este módulo
# continua sendo a porta de quem já importava daqui — molde `app/usb_pai.py`.
from hefesto_dualsense4unix.integrations.alto_falante_bt import (
    CANAIS_DO_ALTO_FALANTE as _CANAIS_DO_ALTO_FALANTE,
)
from hefesto_dualsense4unix.integrations.alto_falante_bt import (
    FONTE_MIX,
    FONTE_PADRAO,
    FONTE_SFX,
    NOME_DO_ALTO_FALANTE_DO_CONTROLE,
    RotaDoNo,
    argv_das_rotas,
    argv_para_ligar_o_mix,
    argv_para_ligar_o_no,
    monitor_da_saida_padrao,
    nome_do_sink,
    propriedades_do_sink,
)
from hefesto_dualsense4unix.integrations.alto_falante_bt import (
    MOTIVO_NO_SEM_ASSENTO as _MOTIVO_NO_SEM_ASSENTO,
)
from hefesto_dualsense4unix.integrations.alto_falante_bt import (
    MOTIVO_NO_SEM_PLACA_NO_CABO as _MOTIVO_NO_SEM_PLACA_NO_CABO,
)
from hefesto_dualsense4unix.integrations.alto_falante_bt import (
    MOTIVO_NO_SEM_PONTE_NO_RADIO as _MOTIVO_NO_SEM_PONTE_NO_RADIO,
)
from hefesto_dualsense4unix.integrations.alto_falante_bt import (
    POR_CABO as _POR_CABO,
)
from hefesto_dualsense4unix.integrations.alto_falante_bt import (
    POR_RADIO as _POR_RADIO,
)
from hefesto_dualsense4unix.integrations.alto_falante_bt import (
    TRANSPORTE_CABO as _TRANSPORTE_CABO,
)
from hefesto_dualsense4unix.integrations.alto_falante_bt import (
    TRANSPORTE_RADIO as _TRANSPORTE_RADIO,
)
from hefesto_dualsense4unix.integrations.alto_falante_bt import (
    rota_do_no as _rota_do_no,
)
from hefesto_dualsense4unix.integrations.alto_falante_bt import (
    sink_do_controle as _sink_do_controle,
)
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


#: O canal está aberto no PipeWire — o próximo som sai do primeiro
#: milissegundo. Cobre `RUNNING` (há fluxo) e `IDLE` (não há fluxo, mas o nó
#: continua aberto): nos dois o hardware NÃO precisa ser religado, e é o
#: religar que come o começo do som.
CANAL_ACORDADO: Final[str] = "acordado"
#: `SUSPENDED` — o PipeWire soltou o hardware por ociosidade.
CANAL_DORMINDO: Final[str] = "dormindo"
#: Não há linha para este sink, ou a última coluna não é um estado conhecido.
#: "" é **não sei**, e é o que mantém a tela calada em vez de chutar.
CANAL_SEM_LEITURA: Final[str] = ""

#: O vocabulário do `pactl`, traduzido para o desta casa. Os nomes vêm da
#: última coluna de `pactl list sinks short`, que NÃO é traduzida (o runner
#: força `LC_ALL=C` de todo jeito).
_ESTADOS_DO_PACTL: Final[dict[str, str]] = {
    "RUNNING": CANAL_ACORDADO,
    "IDLE": CANAL_ACORDADO,
    "SUSPENDED": CANAL_DORMINDO,
}


def estados_crus_dos_sinks(saida_pactl: str) -> dict[str, str]:
    """``{nome do sink: ESTADO cru do pactl}``. **O único parser da coluna.**

    Existe para não haver dois. Esta casa já pagou por leitores paralelos do
    mesmo dado (os três escritores de perfil, os dois leitores de PipeWire), e
    aqui a coluna de estado tem DOIS consumidores com necessidades diferentes:
    :func:`estados_dos_sinks` quer o vocabulário da tela e
    :func:`sono_dos_sinks_do_controle` quer o literal do `pactl` para decidir
    se a regra do WirePlumber pegou. Um parser, duas vistas.

    O formato é ``índice nome driver formato ESTADO``, separado por TAB e não
    traduzido. Linha com menos de cinco campos é descartada: sem a quinta
    coluna, o "último campo" seria o driver, e ``PipeWire`` lido como estado é
    exatamente o tipo de leitura que produz alarme convincente e falso.
    """
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
    """``{nome do sink: acordado|dormindo}`` de `pactl list sinks short`.

    SOM-ACORDADO-01, 15-16/08/2026 — a segunda medição da madrugada, e a que
    ela transformou em pergunta de produto: *"como garantimos durante um jogo
    que o som sempre saia?"*.

    O que foi medido, com a orelha dela, no cabo, mesmo arquivo e mesma rota:

    ==================================  ==========================
    passada                             ela relatou
    ==================================  ==========================
    canal 1 sozinho, nó OCIOSO          "não saiu"
    os quatro timbres logo depois       "saiu no controle"
    canal 1 sozinho, nó já ACORDADO     "tuuuuuuuu"
    ==================================  ==========================

    Nada mais mudou entre as três. **O PipeWire suspende o nó ocioso, e o
    religar do hardware come o começo do som** — três leituras da primeira
    rodada foram descartadas por causa disto antes de alguém entender o que
    estava acontecendo.

    A leitura é a última coluna da lista curta::

        35872<TAB>alsa_output.usb-...analog-surround-40<TAB>PipeWire<TAB>\
s16le 4ch 48000Hz<TAB>SUSPENDED

    **Só o que estiver no vocabulário conhecido conta.** Um nome de sink na
    última coluna (linha curta, formato de outra versão do `pactl`) seria lido
    como estado e viraria "não sei" — que é o certo. Inventar "acordado" a
    partir de uma coluna que não reconhecemos seria a tela prometendo que o
    som sai inteiro.
    """
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
            # A guarda-mãe deste módulo. Ver o cabeçalho: os dois tocadores
            # aceitam sink inexistente, saem com zero e tocam no PADRÃO.
            return ResultadoDoSom.de(MOTIVO_SEM_SINK, sink)
        arquivo = arquivo_de_confirmacao()
        if not arquivo:
            return ResultadoDoSom.de(MOTIVO_SEM_ARQUIVO, sink)
        argv = argv_do_tocador(sink, arquivo, achar=achar)
        if not argv:
            return ResultadoDoSom.de(MOTIVO_SEM_TOCADOR, sink)
        # REGRESSÃO-DO-BIPE-01 — o degrau 6.5. A lista já está lida (degrau 5):
        # o estado sai dela sem um subprocesso a mais, e o `set-sink-suspend`
        # só roda no caso que precisa dele.
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
#: (mais de uma placa na mesa, controle no rádio, ou som já no controle sem
#: memória de quem o pôs lá). Assim que a leitura chega, `acao_da_rota` troca
#: por uma das três dicas específicas.
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
    "fechar esta janela. Onde o som sai depois de chegar ao controle — "
    "alto-falante ou fone — é o canal, no bloco Alto-falante. A janela guarda "
    "a saída de agora para o botão de volta."
)
DICA_ROTA_VOLTAR: Final[str] = (
    "Devolve o som do sistema para {apelido}, que era a saída antes de a "
    "janela mandá-lo para o controle. O alto-falante do controle continua "
    "existindo: ela só deixa de receber o áudio do sistema."
)
#: Sem alvo ÚNICO para este botão, que é um só e vale para a aba inteira.
#: Dois motivos, e a dica nomeia os dois em vez de deixar o botão morto e mudo:
#: o controle está no rádio e não publica placa de som nenhuma (medido em
#: 15/08/2026 — a placa segue o transporte), ou há mais de uma placa na mesa e
#: escolher uma seria a janela decidindo em que controle ela quer ouvir.
#:
#: O primeiro motivo é FATO NOVO desta data e SUBSTITUIU o texto anterior, que
#: dizia que sinks de vários DualSense não se distinguem. Eles se distinguem
#: desde a mesma data, pelo dispositivo USB em que a placa e o HID penduram
#: juntos (`app/usb_pai.py`) — manter a frase velha faria a próxima pessoa
#: procurar uma cura que já existe.
DICA_ROTA_SEM_SINK: Final[str] = (
    "Não há uma saída de áudio única para mandar o som. Pelo rádio o "
    "DualSense não publica placa de som nenhuma — ela só aparece no cabo. "
    "Com mais de um controle no cabo há mais de uma placa, e este botão é um "
    "só: escolher uma por você seria a janela decidindo em que controle o som "
    "sai. Use o seletor Alto-falante do card do controle que você quer."
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

    ``canais`` é o estado de TODOS os sinks da máquina — acordado ou dormindo —
    e ele viaja junto porque a leitura é a mesma (SOM-ACORDADO-01). A aba já
    lê a rota a 0,5 Hz numa thread worker; pendurar aqui o mapa de estados dá
    o dado a cada card **sem um segundo leitor de PipeWire** e sem um
    subprocesso por controle: é universal por construção, serve 1 ou 7
    controles com a mesma leitura, e não depende de MAC, de ordem de conexão
    nem de o daemon publicar nada.
    """

    sink_padrao: str = ""
    sink_do_controle: str = ""
    anterior: str = ""
    no_controle: bool = False
    canais: Mapping[str, str] = field(default_factory=dict)


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

        SOM-ACORDADO-01: a lista viva passou a ser lida SEMPRE, e não só
        quando o som já está no controle. O custo é UM subprocesso a mais por
        ciclo de 0,5 Hz, no pior caso — e o que ele compra é o estado de todos
        os canais de uma vez, para todos os cards, com leitor único. Ler por
        card seria um `pactl` por controle por ciclo, e a mesa dela tem quatro.
        """
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
# A CAMADA 1 SEM JANELA — o dono que a interface nova não tinha (04/09/2026)
# ---------------------------------------------------------------------------
#
# QUEIXA 7 DELA: *"e os botoes do autofalante"*. Medido: o botão "Todo o som do
# PC" da aba 02 RECUSAVA SEMPRE, com esta frase —
#
#     "'Todo o som do PC' ainda não tem dono nesta janela: metade dele é a saída
#      padrão do PipeWire (pactl set-default-sink), que não é IPC (…)"
#
# A recusa era HONESTA e o diagnóstico estava certo: mandar só o byte do
# firmware acenderia o botão sem mover uma nota de som. O que faltava não era
# protocolo — era **um dono da camada 1 fora da janela GTK**.
#
# NA JANELA ANTIGA O DONO EXISTE E É INJETADO: `status_actions` chama
# `card.definir_pedido_de_rota(self._aplicar_rota_do_sistema)`, e aquele método
# junta duas coisas que a janela nova não tem — a `RotaDeSaida` viva
# (`self._rota_de_som`) e o SINK daquele controle, que vem do `MicMonitor`
# (`monitor.sink_de(uniq)`), o leitor de PipeWire da janela antiga.
#
# ENTÃO O QUE ESTAS DUAS FUNÇÕES FAZEM É JUNTAR AS DUAS METADES SEM GTK e sem
# `MicMonitor`: a resolução do sink usa os MESMOS donos que o monitor usa por
# dentro (`fontes_de_captura.sinks_dualsense` + `escolher_sink`, com o casamento
# por dispositivo USB de `integrations/usb_pai`), e a troca usa a MESMA
# `RotaDeSaida`. Nenhuma regra nova, nenhuma segunda leitura do PipeWire — é a
# forma que esta casa chama de *reusar o que está abaixo do mixin*.
#
# É BLOQUEANTE, e isso é declarado: três `pactl` curtos, cada um com o teto de
# `_TIMEOUT_LEITURA_S`. Quem chamar de dentro do GTK deve estar numa worker (é o
# que a janela antiga faz com `run_in_thread`); o gesto da janela nova já chama
# o `ipc_bridge` bloqueante no mesmo lugar, então o custo aqui é da mesma ordem
# do que já existe naquele clique.


@dataclass(frozen=True)
class DesfechoDaRota:
    """O que aconteceu com o pedido de camada 1. `motivo` vazio = deu certo.

    NÃO É `bool`, e a razão é a queixa: um `False` cru vira *"não aconteceu
    nada"* na tela, que é exatamente o silêncio que ela reclamou. Quem recebe
    isto tem a frase pronta para pôr no cartão do controle.
    """

    ok: bool
    motivo: str = ""
    sink: str = ""


#: Não há saída de som atribuível a este controle AGORA.
#:
#: **A FRASE MUDOU EM 10/09/2026, e o que caducou foi a CONCLUSÃO, não o fato.**
#: Ela dizia *"este controle não publica placa de som — pelo rádio o DualSense
#: não expõe nenhuma, e é por isso que 'Todo o som do PC' não tem para onde
#: mandar"*, e ELA a fotografou na tela **com o som do PC saindo pelo controle,
#: por rádio**. As duas metades tiveram destinos diferentes:
#:
#: * a primeira continua exata — o DualSense **não** expõe placa ALSA própria
#:   pelo rádio, e a célula `audio.alto_falante@dualsense` do mapa registra o
#:   mesmo;
#: * a segunda caiu no mesmo dia: o produto passou a publicar um nó de som POR
#:   CONTROLE (`hefesto_som_<hex6>`) e a ponte `0x35` o carrega ao aparelho,
#:   então **há, sim, para onde mandar** — e `sink_do_controle` o reconhece.
#:
#: O que sobra é um estado, e a frase agora descreve SÓ o estado: é o que se lê
#: nos primeiros segundos depois de o controle chegar (o nó ainda nascendo), com
#: o Hefesto parado, ou numa máquina sem `pactl`. Ensinar uma regra de
#: transporte aqui foi o que fez a tela contradizer o que ela estava ouvindo.
MOTIVO_ROTA_SEM_SINK: Final[str] = (
    "não achei a saída de som deste controle agora, então não há para onde "
    "mandar o som do computador. Se ele acabou de chegar, espere alguns "
    "segundos e clique de novo; se o Hefesto estiver parado, ligue-o na aba "
    "Sistema."
)

#: O `pactl` não confirmou a troca. Reler é a régua desta casa: o `pactl`
#: responde sem erro em casos em que a troca não vale.
MOTIVO_ROTA_NAO_PEGOU: Final[str] = (
    "pedi ao PipeWire para mandar o som do PC a este controle e a saída padrão "
    "não mudou — o sink pode ter saído da lista entre o pedido e a conferência."
)

#: Não há para onde voltar. `voltar_ao_anterior` recusa em vez de chutar um
#: destino, e a razão está no `acao_da_rota`: se o som já estava no controle e
#: não fomos NÓS que o pusemos lá, não há sink anterior guardado.
MOTIVO_ROTA_SEM_VOLTA: Final[str] = (
    "não há saída anterior guardada para devolver o som — ou ele não foi o "
    "Hefesto que o trouxe para cá, ou aquela saída não está mais na máquina."
)


def sink_do_controle(
    uniq: str,
    uniqs_na_mesa: list[str] | tuple[str, ...] = (),
    *,
    runner: Callable[[list[str]], str] | None = None,
) -> str:
    """O sink de SAÍDA deste controle — ``""`` quando não dá para saber.

    Mesmas quatro regras do `escolher_sink`, porque é ELE quem decide: aqui só
    se juntam os ingredientes que o `MicMonitor` juntaria (a lista viva de
    sinks e o casamento por dispositivo USB). Escrever uma segunda regra de
    atribuição seria dar ao alto-falante do controle errado o som do PC — e é
    o defeito que `escolher_fonte` foi escrita para não cometer.

    ``""`` é resposta honesta e frequente: é o RÁDIO.

    ADAPTADOR desde 09/09/2026: o corpo mudou para
    ``integrations/alto_falante_bt.sink_do_controle`` **sem uma linha de
    diferença**, porque o daemon precisa da mesma resposta e não importa
    `app/`. Quem chamava daqui continua chamando daqui.

    **E O LEITOR PADRÃO CONTINUA SENDO O DAQUI**, que é o costurar do adaptador
    e não um detalhe: quem chama sem `runner` neste lado espera
    :func:`rodar_leitura`, e há régua da aba 02 que TROCA aquele nome por um
    `pactl` de mentira (``monkeypatch.setattr(audio_saida, "rodar_leitura",
    …)``). Deixar o padrão cair no `_rodar` do módulo de integração moveria a
    costura debaixo dela — medido nesta árvore em 09/09: o gesto «Todo o som do
    PC» passou a perguntar ao PipeWire de verdade e a recusar com *"este
    controle não publica placa de som"*.
    """
    ler = runner if runner is not None else rodar_leitura
    return _sink_do_controle(uniq, tuple(uniqs_na_mesa), runner=ler)


def mandar_o_som_do_pc(
    uniq: str,
    uniqs_na_mesa: list[str] | tuple[str, ...] = (),
    *,
    rota: RotaDeSaida | None = None,
    runner: Callable[[list[str]], str] | None = None,
) -> DesfechoDaRota:
    """Camada 1: a saída PADRÃO do sistema passa a ser o alto-falante deste controle.

    É a metade que faltava ao botão "Todo o som do PC" da janela nova, e ela é
    a que MANDA: *"a camada 1 vence a camada 2 — volume e rota perfeitos num
    sink mudo é trabalho invisível"* (`controller_card.py:4218`).
    """
    alvo = sink_do_controle(uniq, uniqs_na_mesa, runner=runner)
    if not alvo:
        return DesfechoDaRota(False, MOTIVO_ROTA_SEM_SINK)
    motor = rota if rota is not None else RotaDeSaida(runner=runner)
    if not motor.mandar_para_o_controle(alvo):
        return DesfechoDaRota(False, MOTIVO_ROTA_NAO_PEGOU, alvo)
    return DesfechoDaRota(True, "", alvo)


def devolver_o_som_do_pc(
    *,
    rota: RotaDeSaida | None = None,
    runner: Callable[[list[str]], str] | None = None,
) -> DesfechoDaRota:
    """Camada 1, o desfazer: a saída padrão volta para onde estava.

    Recusa em vez de chutar um destino — ver :data:`MOTIVO_ROTA_SEM_VOLTA`.
    """
    motor = rota if rota is not None else RotaDeSaida(runner=runner)
    if not motor.voltar_ao_anterior():
        return DesfechoDaRota(False, MOTIVO_ROTA_SEM_VOLTA)
    return DesfechoDaRota(True)


# ---------------------------------------------------------------------------
# A LEITURA DE VOLTA, e ela é das DUAS camadas
# (ALTO-FALANTE-DOIS-CANAIS-01, 04/09/2026)
# ---------------------------------------------------------------------------

#: O `OUTPUT_PATH_SEL` de "Sons do jogo": canal esquerdo para o fone/TV e o
#: direito para o alto-falante do controle. Nomes importados do dono do byte
#: (`core/ds_output_report`) para não haver uma segunda tabela de rotas.
BYTE_SONS_DO_JOGO: Final[int] = SAIDA_L_FONE_R_ALTO_FALANTE

#: O `OUTPUT_PATH_SEL` de "Todo o som do PC": só o alto-falante interno.
BYTE_TODO_O_SOM_DO_PC: Final[int] = SAIDA_SO_NO_ALTO_FALANTE

#: A frase do cartão quando as duas camadas DISCORDAM: o firmware está roteado
#: para "Todo o som do PC" e a saída padrão do sistema não é este controle.
#: Foi o estado medido em 03/09 — o botão aceso com o som saindo na TV.
MOTIVO_ROTA_SO_NO_BYTE: Final[str] = (
    "o alto-falante deste controle está roteado para receber todo o som, mas "
    "a saída padrão do sistema não é ele — o som continua saindo onde estava. "
    "Clique em 'Todo o som do PC' para mandá-lo para cá."
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
    0, 1 ou ausente        qualquer                   ``""``
    =====================  =========================  ==============

    A segunda linha é a que não se adivinha: apagar OS DOIS é mais honesto que
    acender o errado, porque nenhum dos dois descreve o que está acontecendo —
    o firmware quer uma coisa e o sistema faz outra. Quem diz isso em palavras
    é :func:`recado_da_rota`.

    As rotas 0 e 1 (tudo no fone, mono no fone) apagam os dois de propósito:
    são rotas legítimas do protocolo que estes dois botões não representam, e
    acender um deles ali seria arredondar o byte para o botão mais parecido.

    ``sink_do_controle`` vazio é o RÁDIO — o DualSense não publica placa de som
    por Bluetooth. Aí a camada 1 não tem como estar no controle, e "pc" nunca
    acende: a recusa honesta já está em :data:`MOTIVO_ROTA_SEM_SINK`.
    """
    if isinstance(byte, bool) or not isinstance(byte, int):
        return ""
    if byte == BYTE_SONS_DO_JOGO:
        return "jogo"
    if byte != BYTE_TODO_O_SOM_DO_PC:
        return ""
    if sink_do_controle and sink_padrao == sink_do_controle:
        return "pc"
    return ""


def recado_da_rota(byte: Any, sink_do_controle: str, sink_padrao: str) -> str:
    """A frase para o cartão quando as duas camadas discordam; ``""`` senão.

    Só existe UM desacordo que precisa de palavras: o byte diz "todo o som do
    PC" e a saída padrão do sistema é outra. O contrário — a saída padrão ser
    este controle com o byte em "sons do jogo" — **não** é desacordo: é o
    estado de quem mandou o som para cá pelas configurações do sistema, e o
    botão "Todo o som do PC" apagado descreve isso sem mentir.
    """
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


# ---------------------------------------------------------------------------
# SOM-QUE-NAO-DORME-01 — a leitura que a aba Status precisa para dizer se o
# alto-falante do controle ainda pode dormir.
#
# A cura mora fora do Python: é o drop-in 54 do WirePlumber
# (`assets/wireplumber/54-hefesto-dualsense-alto-falante-nunca-dorme.conf`), que
# o `install.sh` põe SEM FLAG. O que falta aqui é o que esta casa mais erra —
# **a casa saber e o produto não mostrar**. Estas funções são a ponte, e são
# PURAS de propósito: quem lê o `pactl` é o runner de sempre, quem decide o
# texto não toca em disco nem em processo, e o portão exercita as duas sem
# hardware nenhum.
# ---------------------------------------------------------------------------

#: O nome do drop-in, em UM lugar só. O portão compara este literal com o
#: arquivo que existe em `assets/wireplumber/` — se um for renomeado sem o
#: outro, a tela passaria a afirmar "pode dormir" com a cura instalada.
NOME_REGRA_NUNCA_DORME: Final[str] = "54-hefesto-dualsense-alto-falante-nunca-dorme.conf"

#: Estado que o `pactl list sinks short` mostra num nó que o WirePlumber pôs
#: para dormir. É neste estado que o começo do som se perde (medido na orelha
#: dela em 15/08/2026 23h45, ensaio `sfx-no-suspenso-come-o-comeco`).
ESTADO_SUSPENSO: Final[str] = "SUSPENDED"

#: A cura está no lugar e o controle está com a placa de som acordada.
TEXTO_SONO_ACORDADO: Final[str] = "Alto-falante acordado — o som sai desde o primeiro instante"

#: A cura está no lugar, mas o nó ainda está suspenso: ele nasceu ANTES de o
#: WirePlumber reler a regra. Não é falha da cura, e o texto diz o que fazer.
TEXTO_SONO_ATRASADO: Final[str] = (
    "Alto-falante ainda dormindo — a regra entrou depois deste controle; "
    "reconecte-o para valer"
)

#: Não há placa de som do controle na mesa. Não é defeito: por rádio o DualSense
#: não publica placa ALSA nenhuma (medido em 15/08/2026 — a placa segue o
#: transporte), e no cabo isto também aparece com o controle desligado.
#:
#: **A frase dizia "no rádio não existe alto-falante", e isso é FALSO** — trocado
#: em 17/08/2026. O alto-falante existe no aparelho e ela o OUVIU: rota 3 medida
#: com a orelha dela em 02/08/2026, com controle negativo. O que não existe no
#: rádio é a PLACA ALSA — e a diferença não é sutil, é a diferença entre "o seu
#: controle não tem isso" e "o caminho até ele não está montado agora".
#:
#: Ela já derrubou esta confusão uma vez, em 15/08, quando um texto medido foi
#: enfraquecido de "alto-falante" para "placa de som": *"falso, no próprio
#: projeto já fizemos isso, deveria tá mapeado inclusive no specs"*. O comentário
#: acima sempre esteve certo; era a frase da TELA que contradizia a medição.
TEXTO_SONO_SEM_PLACA: Final[str] = (
    "Sem placa de som do controle (no rádio o DualSense não publica placa ALSA)"
)

#: A cura foi arrancada. É o estado que a tela TEM de denunciar, porque o
#: sintoma no jogo é silencioso: o efeito sonoro simplesmente não sai.
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
    """O que a aba Status escreve, dados os dois fatos que ela consegue saber.

    A ordem das perguntas não é arbitrária: **a cura arrancada vence tudo**. Um
    nó pode estar acordado por acaso (alguém acabou de tocar algo) com a regra
    fora do lugar, e chamar isso de "acordado" seria a tela dando por curado o
    que só está momentaneamente de pé.
    """
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
    ``DICA_CANAL_SEM_A_REGRA``, que é a cura arrancada sendo denunciada.

    Por isso ela **não deve ganhar chamador na janela**: seria um segundo
    leitor de PipeWire aqui dentro (`controller_card.py`:4044-4049 escreve por que
    isso é defeito) para repetir o que já está na tela. O corpo fica de pé
    porque é a única forma de perguntar as duas coisas de uma vez fora da
    janela, e porque podar símbolo público é decisão DELA, não deste módulo.
    """
    saida = rodar_leitura(["pactl", "list", "sinks", "short"])
    return texto_do_sono(regra_nunca_dorme_instalada(home), sono_dos_sinks_do_controle(saida))


# ---------------------------------------------------------------------------
# O ALTO-FALANTE VIRTUAL — um nó por controle (O-ALTO-FALANTE-VIRTUAL-01)
#
# O PEDIDO DELA, 29/08/2026: alto-falante virtual "no estilo do gamepad
# virtual", para o som do controle funcionar **independente da máscara e do
# transporte**. É o mesmo contrato do vpad: o jogo escolhe um gamepad, não um
# transporte; aqui quem escolhe a saída escolhe um CONTROLE, não um sink.
#
# O QUE ESTA SEÇÃO É, e o que ela não é. Ela é a SUPERFÍCIE: o nome do nó, o id
# do nó, a decisão de para onde ele entrega, e o PLANO de comandos que o publica
# no PipeWire. Ela **não carrega módulo nenhum**: quem executa o plano é o dono
# da camada 1 (a próxima sprint), e nada aqui toca o PipeWire vivo de ninguém.
# A separação é de propósito — decisão pura de um lado, efeito do outro é o que
# deixa a mordida rodar sem áudio real na suíte.
#
# **FATO SUBSTITUÍDO em 09/09/2026, e o antigo era decisão por DELEGAÇÃO.**
# Estas linhas diziam que o nome do nó era `Alto-falante · P1` … `P4` e que
# *"«Controle 1» NÃO é a palavra desta casa"*. **Ela decidiu o contrário**
# (`D-0909-OS-NOS-SE-CHAMAM-ALTO-FALANTE-E-MICROFONE-DO-CONTROLE-N`, palavra
# dela: *"4a"*): o rótulo é **«Alto-falante do Controle N»**, par de «Microfone
# do Controle N», e o número continua sendo o do ASSENTO. O par está em
# `docs/A-LINGUA-DESTA-CASA-…`, que foi a condição que ela pôs.
#
# **E o nome INTERNO tinha DOIS donos, o que é pior que estar errado.** Esta
# seção montava `hefesto_alto_falante_<assento>` e
# `integrations/alto_falante_bt.nome_do_sink` montava `hefesto_som_<hex6>` —
# dois `sink_name` para o mesmo nó, e o instrumento
# `scripts/ensaios/os_nos_de_som_por_controle.py` procura o SEGUNDO. Sobrou um:
# o do aparelho (`hefesto_som_<hex6>`), que é o que sobrevive à troca de
# assento, exatamente como o `hefesto_mic_<hex6>` do microfone. O rótulo segue
# o assento; o nome interno segue o aparelho.
#
# AS TRÊS INVARIANTES, e cada uma tem régua em
# `tests/unit/test_o_alto_falante_virtual_esconde_o_transporte.py`:
#
#   1. **o nome e o id não sabem do transporte.** O mesmo controle no cabo e no
#      rádio é o MESMO nó, com o mesmo nome e o mesmo id. Um nó que muda de nome
#      quando ela troca o cabo é o defeito que ele existe para não ter;
#   2. **o sink é resolvido pela IDENTIDADE**, nunca pelo texto do nome — quem
#      decide é :func:`sink_do_controle`, que é quem já sabia (casamento por
#      dispositivo USB, `integrations/usb_pai`). Casar por prefixo de nome
#      entrega o som do P2 no alto-falante do P1 assim que há dois no cabo;
#   3. **a máscara não participa.** `flavor` não entra em nenhuma assinatura
#      desta seção. Som não é entrada, e a máscara é do gamepad.
#
# E A QUARTA, que é a queixa histórica dela — *"tínhamos algo para o cabo e na
# hora do vamos ver a versão de BT não funcionava"*: **sem rota, o nó DIZ.** Ele
# não nasce como um sink mudo e calado. "Não sei" é resposta válida; sink que
# engole som em silêncio **e não conta a ninguém** não é.
#
#   **METADE DESTA INVARIANTE CAIU — 08/09/2026, e quem a derrubou foi ELA.**
#   Ela dizia também *"sem rota não se carrega módulo nenhum"*, e a razão era a
#   decisão de 06/09 tomada por DELEGAÇÃO (*"o nó vive só enquanto há
#   controle"*), declarada reversível numa frase. Ela reverteu:
#   `D-0809-O-NO-DE-SOM-POR-CONTROLE-VIVE-SEMPRE` — *"nó que some quebra o jogo
#   que o escolheu"*. **O nó é publicado mesmo sem rota**, e o que vai e volta
#   é o `module-loopback`. O que fica de pé da invariante é o DIZER: o
#   `PlanoDoNo` sai com `vai_publicar=True` **e** `motivo` cheio, e a tela é
#   quem mostra a frase.
#
# ONDE MORA A RESPOSTA, desde 09/09/2026: em
# `integrations/alto_falante_bt.py`, e esta seção REEXPORTA. O daemon precisa
# da rota e **não importa nada de `app/`** (`integrations/fontes_de_captura.py`
# escreve a régua); deixar a resposta aqui obrigaria o `AltoFalanteSubsystem` a
# escrever a segunda. O molde é o `app/usb_pai.py` → `integrations/usb_pai.py`.
# ---------------------------------------------------------------------------

#: Os quatro assentos, na ordem. O conjunto congelado do lado da TELA é
#: `interface/pacotes.TODOS_OS_LUGARES`, e os dois têm de concordar — há régua
#: comparando os dois, porque duas listas de assentos é como esta casa fabrica
#: divergência silenciosa. Aqui é tupla porque a ordem importa para quem monta
#: a lista de saída; lá é `frozenset` porque a conta é de conjunto.
ASSENTOS: Final[tuple[str, ...]] = ("p1", "p2", "p3", "p4")

#: Os dois transportes. **Um dono, e ele é o `integrations/alto_falante_bt`** —
#: aqui é reexportação, para quem já importava daqui não ter de mudar de porta.
TRANSPORTE_CABO: Final[str] = _TRANSPORTE_CABO
TRANSPORTE_RADIO: Final[str] = _TRANSPORTE_RADIO


def nome_do_alto_falante(assento: str) -> str:
    """O que aparece na lista de saída do sistema — ``""`` para assento inválido.

    «Alto-falante do Controle 1». O número é o ASSENTO (o jogador), nunca o
    aparelho: decisão dela de 09/09/2026 (*"4a"*,
    ``D-0909-OS-NOS-SE-CHAMAM-ALTO-FALANTE-E-MICROFONE-DO-CONTROLE-N``).

    **FATO SUBSTITUÍDO:** até 09/09 esta função devolvia ``Alto-falante · P1``,
    por delegação de 06/09. As palavras são dela agora, e o par com «Microfone
    do Controle N» está na LÍNGUA DESTA CASA.

    **Não recebe transporte nem máscara**, e não é omissão: é a invariante 1
    desta seção. Quem quiser o nome só precisa saber de que jogador ele é.

    Quem monta o rótulo a partir do ``uniq`` — que é o caminho do DAEMON, onde
    o assento vem por gancho — é
    ``integrations/alto_falante_bt.descricao_do_alto_falante``. As palavras são
    as mesmas porque a constante é a mesma; duas grafias do rótulo poriam dois
    nomes diferentes para o mesmo nó, um por caminho de código.
    """
    if assento not in ASSENTOS:
        return ""
    return f"{NOME_DO_ALTO_FALANTE_DO_CONTROLE} {assento[1:]}"


@dataclass(frozen=True)
class NoDeAltoFalante:
    """Um alto-falante virtual: de que assento é, de que controle, e por onde ele fala.

    `transporte` está aqui porque a ROTA precisa dele — e só ela. O `nome` e o
    `id_do_no` são calculados sem olhar para este campo, que é o que a régua
    trava: derivar qualquer um dos dois do transporte faz o nó mudar de nome no
    meio da sessão.
    """

    assento: str
    uniq: str = ""
    transporte: str = TRANSPORTE_CABO
    #: ``mix`` (todo o som do PC cai aqui também) ou ``sfx`` (só o que o jogo
    #: mandar). Nasce em ``sfx`` por decisão dela de 08/09/2026
    #: (``D-0809-NO-CABO-O-PADRAO-DO-SOM-E-SFX``).
    fonte: str = FONTE_PADRAO

    @property
    def nome(self) -> str:
        """O texto da lista de saída — ver :func:`nome_do_alto_falante`."""
        return nome_do_alto_falante(self.assento)

    @property
    def id_do_no(self) -> str:
        """O ``sink_name`` no PipeWire — ``""`` quando o ``uniq`` é ilegível.

        **É o nome do APARELHO, não o do assento** (``hefesto_som_<hex6>``,
        ``integrations.alto_falante_bt.nome_do_sink``), e a razão é o gesto que
        esta seção existe para não quebrar: ela troca o P2 de assento com o P3
        no meio da sessão e o jogo continua com a saída que escolheu. Um id por
        assento faria o nó trocar de nome ali, que é o mesmo defeito do nome
        com transporte dentro, com outra roupa.

        **FATO SUBSTITUÍDO em 09/09/2026**: até aqui esta propriedade devolvia
        ``hefesto_alto_falante_<assento>``, um SEGUNDO ``sink_name`` para o
        mesmo nó — o outro é o que o produto de fato publica e o que o
        instrumento de bancada procura.
        """
        return nome_do_sink(self.uniq)


def assento_do_controle(entry: Mapping[str, Any]) -> str:
    """O assento (`p1`…`p4`) de uma entrada de ``state_full.controllers``.

    **Quem decide o número é `actions.base.numero_do_controle`**, e não uma
    segunda regra escrita aqui: ele é a fonte única de *"com que número este
    controle se identifica na interface inteira"* (COR-01/D6), e uma cópia da
    conta é como a janela passou a dizer "Controle 1" e "Sony 3" sobre o mesmo
    aparelho.

    O import é PREGUIÇOSO de propósito: aquele módulo puxa GTK, e este aqui é
    consumido pela interface nova, que não pode ganhar GTK por tabela. Quem só
    quer nome e id de um assento não paga esse preço — chame
    :func:`nome_do_alto_falante` direto.

    Assento fora de 1..4 devolve ``""``: o desenho tem QUATRO lugares, e
    inventar um `p5` seria pôr na lista de saída um nó que a tela não desenha.
    """
    from hefesto_dualsense4unix.app.actions.base import numero_do_controle

    numero = numero_do_controle(dict(entry))
    assento = f"p{numero}"
    return assento if assento in ASSENTOS else ""


def no_do_controle(
    entry: Mapping[str, Any], *, fonte: str = FONTE_PADRAO
) -> NoDeAltoFalante | None:
    """O nó deste controle — ``None`` quando não dá para dizer de que assento ele é.

    **A MÁSCARA NÃO É LIDA AQUI, e é a invariante 3.** Um `entry` traz
    ``gamepad.flavor`` (`dualsense`, `xbox`, `nintendo`) e esta função não o
    toca: o nó existe igual nos três, porque som não é entrada. É o pedido dela
    literal, e é o que a régua cobra.

    **A FONTE NÃO SAI DO `entry`, e é de propósito.** Ela é escolha DELA, por
    controle, e mora no perfil (``ControllerOverrides.speaker.fonte``) — não no
    estado que o daemon publica a cada tique. Lê-la daqui faria o mix ligar e
    desligar sozinho ao sabor do que o aparelho reporta; quem sabe a escolha
    passa-a por :paramref:`fonte`, e quem não sabe recebe o padrão dela
    (``sfx``).
    """
    assento = assento_do_controle(entry)
    if not assento:
        return None
    uniq = entry.get("uniq")
    transporte = entry.get("transport")
    return NoDeAltoFalante(
        assento=assento,
        uniq=uniq if isinstance(uniq, str) else "",
        transporte=transporte if isinstance(transporte, str) else TRANSPORTE_CABO,
        fonte=fonte if fonte in (FONTE_MIX, FONTE_SFX) else FONTE_PADRAO,
    )


#: Por onde o nó entrega, quando entrega. `""` é "não entrega". **Um dono, e
#: ele é `integrations/alto_falante_bt`**; aqui é reexportação.
POR_CABO: Final[str] = _POR_CABO
POR_RADIO: Final[str] = _POR_RADIO

#: As três frases de recusa do nó, e as três dizem o quê, por quê e o que
#: fazer. Reexportadas de `integrations/alto_falante_bt`, que é onde a rota
#: mora desde 09/09/2026 — o daemon precisa delas e não importa `app/`.
MOTIVO_NO_SEM_PONTE_NO_RADIO: Final[str] = _MOTIVO_NO_SEM_PONTE_NO_RADIO
MOTIVO_NO_SEM_PLACA_NO_CABO: Final[str] = _MOTIVO_NO_SEM_PLACA_NO_CABO
MOTIVO_NO_SEM_ASSENTO: Final[str] = _MOTIVO_NO_SEM_ASSENTO

#: Os canais do sink do controle por onde o alto-falante interno toca — ver o
#: dono, `integrations/alto_falante_bt.CANAIS_DO_ALTO_FALANTE`.
CANAIS_DO_ALTO_FALANTE: Final[str] = _CANAIS_DO_ALTO_FALANTE


def rota_do_no(
    no: NoDeAltoFalante | None,
    uniqs_na_mesa: list[str] | tuple[str, ...] = (),
    *,
    ponte_do_radio: Callable[[], bool] | None = None,
    runner: Callable[[list[str]], str] | None = None,
) -> RotaDoNo:
    """Onde este nó entrega o áudio — ou a frase de por que ele não entrega.

    ADAPTADOR: a decisão inteira mora em
    ``integrations/alto_falante_bt.rota_do_no``, que é quem o daemon também
    chama. Aqui só se desembrulha o :class:`NoDeAltoFalante` — a forma que a
    JANELA tem em mãos, porque foi ela quem leu o ``state_full``.
    """
    if no is None or not no.assento:
        return RotaDoNo(False, motivo=MOTIVO_NO_SEM_ASSENTO)
    return _rota_do_no(
        no.uniq,
        no.transporte,
        tuple(uniqs_na_mesa),
        fonte=no.fonte,
        ponte_do_radio=ponte_do_radio,
        # O leitor padrão é o DESTE lado — ver a nota em `sink_do_controle`.
        runner=runner if runner is not None else rodar_leitura,
    )


def argv_para_publicar_o_no(no: NoDeAltoFalante) -> tuple[str, ...]:
    """O comando que cria o nó na lista de saída do sistema.

    Um `module-null-sink` com nome interno estável (`sink_name`) e nome de
    gente (`device.description`). O sink nasce sem destino — quem o liga ao
    aparelho é :func:`argv_para_ligar_o_no`.

    **O NOME DAS PROPRIEDADES TEM UM DONO**, e é
    ``alto_falante_bt.propriedades_do_sink``: é ele que põe as aspas duplas que
    impedem o parser do `pipewire-pulse` de cortar o valor no primeiro espaço
    — e «Alto-falante do Controle 1» tem dois. Montar o argumento à mão aqui
    publicaria um nó chamado «Alto-falante».
    """
    return (
        "pactl",
        "load-module",
        "module-null-sink",
        f"sink_name={no.id_do_no}",
        propriedades_do_sink(no.nome),
    )


def argv_para_retirar_o_no(indice: int) -> tuple[str, ...]:
    """O comando que tira da lista de saída um módulo que publicamos."""
    return ("pactl", "unload-module", str(indice))


@dataclass(frozen=True)
class PlanoDoNo:
    """O que fazer para pôr este nó de pé — e a frase quando não há rota.

    **A INVARIANTE 4 MUDOU DE FORMA EM 08/09/2026, e quem a mudou foi ELA.**
    Ela dizia *"sem rota não se carrega módulo nenhum"*, e por isso `argv`
    vazio com `motivo` cheio era o desfecho honesto. A decisão
    `D-0809-O-NO-DE-SOM-POR-CONTROLE-VIVE-SEMPRE` inverteu a metade do
    ciclo de vida: **o nó é publicado sempre**, e o que falta quando não há
    rota é o `module-loopback`. O que continua valendo é o DIZER — um plano com
    `vai_publicar=True` e `motivo` cheio é um nó que existe e não tem para onde
    ir, e a tela mostra a frase.
    """

    vai_publicar: bool
    nome: str = ""
    id_do_no: str = ""
    sink: str = ""
    por_onde: str = ""
    fonte: str = FONTE_PADRAO
    motivo: str = ""
    argv: tuple[tuple[str, ...], ...] = ()

    @property
    def tem_rota(self) -> bool:
        """O nó entrega em algum lugar? `vai_publicar` NÃO responde isto.

        Desde a decisão dela de 08/09 os dois se separaram, e confundi-los é o
        defeito seguinte: o nó existe (`vai_publicar`) sem entregar nada
        (`tem_rota` falso), e é exatamente esse par que a tela precisa dizer.
        """
        return bool(self.por_onde)


def plano_de_publicacao(
    no: NoDeAltoFalante | None,
    uniqs_na_mesa: list[str] | tuple[str, ...] = (),
    *,
    ponte_do_radio: Callable[[], bool] | None = None,
    runner: Callable[[list[str]], str] | None = None,
) -> PlanoDoNo:
    """O plano completo do alto-falante virtual deste controle.

    BLOQUEIA quando cai no ramo do cabo (é `pactl` de leitura, com o teto de
    :data:`_TIMEOUT_LEITURA_S`) — rode em worker, como todo o resto do módulo.

    Ele **não executa nada**. Devolve os comandos, e quem os roda é o dono da
    camada 1 — o `AltoFalanteSubsystem`, por `SinkVirtualPipeWire`.
    """
    if no is None or not no.assento:
        return PlanoDoNo(False, motivo=MOTIVO_NO_SEM_ASSENTO)
    if not no.id_do_no:
        return PlanoDoNo(False, nome=no.nome, motivo=MOTIVO_NO_SEM_ASSENTO)
    rota = rota_do_no(
        no, uniqs_na_mesa, ponte_do_radio=ponte_do_radio, runner=runner
    )
    comandos: list[tuple[str, ...]] = [argv_para_publicar_o_no(no)]
    comandos.extend(argv_das_rotas(no.id_do_no, rota))
    return PlanoDoNo(
        True,
        nome=no.nome,
        id_do_no=no.id_do_no,
        sink=rota.sink,
        por_onde=rota.por_onde,
        fonte=rota.fonte,
        motivo=rota.motivo,
        argv=tuple(comandos),
    )


__all__ = [
    "ASSENTOS",
    "BYTE_SONS_DO_JOGO",
    "BYTE_TODO_O_SOM_DO_PC",
    "CANAIS_DO_ALTO_FALANTE",
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
    "FONTE_MIX",
    "FONTE_PADRAO",
    "FONTE_SFX",
    "MOTIVO_DESLIGADO",
    "MOTIVO_FALHOU",
    "MOTIVO_NO_SEM_ASSENTO",
    "MOTIVO_NO_SEM_PLACA_NO_CABO",
    "MOTIVO_NO_SEM_PONTE_NO_RADIO",
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
    "NOME_DO_ALTO_FALANTE_DO_CONTROLE",
    "NOME_REGRA_NUNCA_DORME",
    "POR_CABO",
    "POR_RADIO",
    "RECADOS",
    "TEXTO_ROTA_PARA_O_CONTROLE",
    "TEXTO_ROTA_VOLTAR",
    "TEXTO_SONO_ACORDADO",
    "TEXTO_SONO_ATRASADO",
    "TEXTO_SONO_PODE_DORMIR",
    "TEXTO_SONO_SEM_PLACA",
    "TRANSPORTE_CABO",
    "TRANSPORTE_RADIO",
    "AcaoRota",
    "DesfechoDaRota",
    "EstadoDaRota",
    "NoDeAltoFalante",
    "PlanoDoNo",
    "ResultadoDoSom",
    "RotaDasDuasCamadas",
    "RotaDeSaida",
    "RotaDoNo",
    "acao_da_rota",
    "acordar_sink",
    "apelido_do_sink",
    "argv_das_rotas",
    "argv_do_tocador",
    "argv_para_ligar_o_mix",
    "argv_para_ligar_o_no",
    "argv_para_publicar_o_no",
    "argv_para_retirar_o_no",
    "arquivo_de_confirmacao",
    "assento_do_controle",
    "botao_da_rota_aceso",
    "caminho_regra_nunca_dorme",
    "devolver_o_som_do_pc",
    "estado_do_canal",
    "estado_do_sono",
    "estados_crus_dos_sinks",
    "estados_dos_sinks",
    "ler_as_duas_camadas",
    "mandar_o_som_do_pc",
    "monitor_da_saida_padrao",
    "no_do_controle",
    "nome_do_alto_falante",
    "nome_do_sink",
    "nomes_de_sinks",
    "plano_de_publicacao",
    "propriedades_do_sink",
    "recado_da_rota",
    "regra_nunca_dorme_instalada",
    "rodar_leitura",
    "rota_do_no",
    "sink_do_controle",
    "sink_padrao_da_saida",
    "som_ligado",
    "sono_dos_sinks_do_controle",
    "texto_do_sono",
    "tocar_confirmacao",
]

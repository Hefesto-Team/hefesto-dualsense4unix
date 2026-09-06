"""Quem é a source/sink de ÁUDIO de cada controle — a resolução `uniq → nome`.

MIC-DA-MESA-ELEICAO-01 (01/09/2026). Esta peça nasceu dentro de
`app/mic_monitor.py` porque foi a JANELA que precisou dela primeiro: o medidor
de nível da aba Status tinha de saber qual das sources do PipeWire é do
controle daquele card.

Só que a ELEIÇÃO DE MICROFONE precisa exatamente da mesma resposta, e ela mora
no daemon — que **não importa nada de `app/`** (a camada é limpa e vai
continuar sendo: `grep -r "from hefesto_dualsense4unix.app" src/…/daemon/`
devolve zero). Duplicar a lógica criaria duas verdades sobre a mesma pergunta,
que é como esta casa fabrica divergência silenciosa.

O molde já estava executado e escrito: `app/usb_pai.py` é a ponte,
`integrations/usb_pai.py` é o dono (MIC-DA-MESA-CHEIA-01, 20/08). Aqui é o
mesmo movimento, e `app/mic_monitor.py` continua reexportando tudo.

Nada mudou de comportamento: é o mesmo código, com outro endereço.

**E o prefixo da ponte BT ganhou UM dono.** Ele era montado por f-string em
`integrations/dualsense_bt_audio.py` e digitado de novo, à mão, como constante
no `app/mic_monitor.py`. Dois donos do mesmo nome: quem trocasse um lado
deixaria o outro procurando um prefixo que não existe mais, em silêncio. Agora
o dono é :data:`PREFIXO_SOURCE_PONTE_BT`, e a ponte o importa daqui.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: Marcadores no NOME da source que identificam um DualSense. O PipeWire monta
#: o nome a partir das strings USB do device ("Sony Interactive Entertainment
#: Wireless Controller"), então o casamento é por substring normalizada.
MARCADORES_DUALSENSE: tuple[str, ...] = (
    "wireless_controller",
    "wireless controller",
    "dualsense",
)

#: Prefixo do nome que a ponte de mic por Bluetooth publica no PipeWire:
#: ``hefesto_dualsense_bt_<hex>``, onde ``<hex>`` são os SEIS últimos dígitos
#: hex do MAC do controle (`PontePyDualSenseBT`, via `NoHidraw.nome_curto`).
#:
#: **DONO ÚNICO.** Este valor era montado por f-string na ponte e redigitado
#: como constante do lado da janela. Quem lê e quem escreve o nome agora leem
#: daqui — a regra da casa: se você precisa digitar um nome que já existe
#: noutro arquivo, LEIA de lá.
PREFIXO_SOURCE_PONTE_BT = "hefesto_dualsense_bt_"

#: Prefixo do nome do CANAL POR CONTROLE: ``hefesto_mic_<hex6>``, o nó que
#: :mod:`integrations.canal_do_microfone` publica (ONDA5-MIC-VIRTUAL-01).
#:
#: **DONO ÚNICO, e ele mora AQUI pela mesma razão de
#: :data:`PREFIXO_SOURCE_PONTE_BT`:** quem LÊ o nome é este módulo
#: (:func:`fontes_dualsense`, :func:`escolher_fonte`) e quem o ESCREVE é o dono
#: do canal. Se o prefixo morasse lá, este arquivo teria de importá-lo — e
#: `canal_do_microfone` já importa daqui (``so_hex``, ``MIN_HEX_SUFIXO_BT``),
#: o que fecharia um ciclo. A regra da casa resolve sem ciclo: **o nome mora
#: com quem o lê, e quem o escreve LÊ de lá.**
#:
#: **Por que um prefixo NOVO e não o da ponte.** ``hefesto_dualsense_bt_`` diz o
#: TRANSPORTE no próprio nome, e é esse o defeito que o canal por controle
#: existe para curar: troque o cabo pelo rádio e o microfone daquele controle
#: mudava de nome. Reusar aquele prefixo apenas mudaria o defeito de lugar.
#: Enquanto o rádio publicar o nome velho, os dois prefixos convivem e os dois
#: leitores discriminam — é o preço declarado da transição, e a
#: ONDA5-MIC-VIRTUAL-02 é quem o paga.
PREFIXO_SOURCE_CANAL_DO_MIC = "hefesto_mic_"

#: Tamanho mínimo do sufixo hex aceito como identidade. Seis dígitos são os
#: três últimos octetos do MAC — o que a ponte publica. Menos que isso não
#: distingue controles, e a ponte tem um caminho de fallback (nó sem
#: ``HID_UNIQ``) em que o sufixo é o nome do nó e não um MAC: por isso o
#: sufixo também precisa ser hex INTEIRO para valer.
MIN_HEX_SUFIXO_BT = 6


@dataclass(frozen=True)
class CasamentoUSB:
    """Quem pendura em qual dispositivo USB — a identidade que o NOME não tem.

    Dois mapas do mesmo fato, montados por :mod:`integrations.usb_pai`: o
    dispositivo USB pai de cada controle (pelo hidraw) e o de cada nó de áudio
    (pelo ``sysfs.path`` que o PipeWire publica). ``""`` de qualquer lado quer
    dizer "não pendura em USB nenhum" — o caso do controle por rádio, que não
    tem placa de som, e o de todo nó virtual, como a ponte de mic por
    Bluetooth.

    Por que isto existe: com dois DualSense no cabo os nomes dos sinks são
    ``...-00...`` e ``...-00.2...``, desempate posicional do PipeWire e não
    número de série. A janela recusava atribuir sink a QUALQUER um deles, e o
    botão "Ouvir no controle" nascia morto na mesa de quatro controles. O
    dispositivo USB responde a pergunta sem olhar nome, MAC, ordem de conexão
    nem quantidade de controles — vale igual para 1, 2, 4 ou 7.
    """

    por_uniq: dict[str, str] = field(default_factory=dict)
    por_no: dict[str, str] = field(default_factory=dict)

    def casar(self, nomes: list[str], uniq: str) -> str | None:
        """O nó que pendura no MESMO dispositivo USB deste controle, ou None.

        Sem dispositivo USB do lado do controle não há o que casar (rádio):
        devolve None e deixa a decisão para as outras regras — nunca chuta o
        primeiro nó da lista, que seria emprestar a placa do vizinho.

        Empate (dois nós do mesmo controle, uma placa com dois perfis) resolve
        pelo menor nome, e não é arbitrário: os dois nós SÃO daquele controle,
        então qualquer um leva ao aparelho certo, e ordenar é o que faz a
        janela mostrar o mesmo nó a cada ciclo em vez de piscar entre dois.
        """
        meu = self.por_uniq.get(uniq, "")
        if not meu:
            return None
        candidatos = sorted(n for n in nomes if self.por_no.get(n, "") == meu)
        return candidatos[0] if candidatos else None

    def veta(self, nome: str, uniq: str) -> bool:
        """True quando este nó NÃO pode ser deste controle. A guarda do 1-para-1.

        A regra do "um nó, um controle, só pode ser ele" é boa aritmética e má
        física: um controle no RÁDIO não tem placa de som (medido 15/08/2026 —
        a placa segue o transporte), e se sobra na tela um nó de áudio USB de
        outro aparelho, o um-para-um o entregaria a ele. Aqui o casamento por
        USB é o que diz "este nó tem dono, e não é você".

        Nó sem dispositivo USB não veta nada: é o caso da ponte de mic por
        Bluetooth, que é virtual e legítima justamente para quem está no rádio.
        """
        do_no = self.por_no.get(nome, "")
        if not do_no:
            return False
        return do_no != self.por_uniq.get(uniq, "")


def fontes_dualsense(saida_pactl: str) -> list[str]:
    """Nomes das sources de CAPTURA de DualSense em `pactl list sources short`.

    O formato é ``índice\\tnome\\tdriver\\tformato\\testado`` (não traduzido).
    Monitores de saída (``.monitor``) são descartados: são o áudio que SAI
    pelo alto-falante do controle, não o microfone dele — medir aquilo faria
    o "nível do mic" subir com a trilha do jogo.

    **O CANAL POR CONTROLE ENTRA POR IDENTIDADE, NÃO POR MARCADOR** — e a razão
    foi medida em 06/09/2026, com o nó de pé no PipeWire desta máquina: o nome
    ``hefesto_mic_000001`` não contém NENHUM dos
    :data:`MARCADORES_DUALSENSE` (o da ponte de rádio contém, porque tem a
    palavra ``dualsense`` dentro). Sem esta linha o nó novo nunca chegava à
    lista, :func:`escolher_fonte` nunca o via, e a regra 0 dele seria código
    morto que dá verde — o defeito que esta casa chama de instrumento falso.
    """
    out: list[str] = []
    for linha in saida_pactl.splitlines():
        partes = linha.split("\t")
        if len(partes) < 2:
            continue
        nome = partes[1].strip()
        alvo = nome.lower()
        if alvo.endswith(".monitor"):
            continue
        if sufixo_do_canal_do_mic(nome) or any(marca in alvo for marca in MARCADORES_DUALSENSE):
            out.append(nome)
    return out


def sinks_dualsense(saida_pactl: str) -> list[str]:
    """Nomes dos sinks de SAÍDA de DualSense em `pactl list sinks short`.

    Mesmo formato tabulado da lista de sources (``índice\\tnome\\tdriver\\t...``,
    não traduzido) e os mesmos marcadores de nome — o PipeWire monta os dois
    lados a partir das mesmas strings USB do device.

    Dois descartes, ambos defensivos contra receber a lista errada por engano:
    ``.monitor`` (que é a saída vista de dentro, não um destino) e qualquer
    nome ``alsa_input.`` (um nó de CAPTURA nunca é por onde sai som — tratá-lo
    como sink faria o selo da saída falar do microfone).
    """
    out: list[str] = []
    for linha in saida_pactl.splitlines():
        partes = linha.split("\t")
        if len(partes) < 2:
            continue
        nome = partes[1].strip()
        alvo = nome.lower()
        if alvo.endswith(".monitor") or alvo.startswith("alsa_input."):
            continue
        if any(marca in alvo for marca in MARCADORES_DUALSENSE):
            out.append(nome)
    return out


def escolher_fonte(
    fontes: list[str],
    uniq: str,
    uniqs_com_audio: list[str],
    usb: CasamentoUSB | None = None,
) -> str | None:
    """Source atribuível ao controle `uniq` — ou None quando não dá para saber.

    CINCO regras, nesta ordem — e a regra 0 nasceu depois das outras quatro,
    que NÃO saíram:

    0. **O nó com IDENTIDADE vence** (ONDA5-MIC-VIRTUAL-01, 06/09/2026). O
       canal por controle publica ``hefesto_mic_<hex6>``
       (:data:`PREFIXO_SOURCE_CANAL_DO_MIC`), e aqueles seis dígitos são os
       três últimos octetos do MAC — a identidade DO CONTROLE, que não muda
       quando ele troca de transporte. Quando ele está no ar, a pergunta *"qual
       nó é o microfone deste controle"* tem resposta exata e ela não custa
       censo de USB nenhum.

       **AS QUATRO ABAIXO FICAM, e a razão é medida:** o nó com identidade só
       existe DEPOIS que alguém pede o canal (o botão do microfone), e antes
       disso as quatro são o único caminho — inclusive o da janela estável, que
       abre esta mesma função. Uma regra 0 que substituísse as quatro apagaria o
       microfone de todo controle que ninguém pediu ainda.

       **E ela cobre os quatro chamadores de uma vez**, porque a cura está
       DENTRO da função que os quatro chamam: a eleição, a luz, o áudio da
       janela e o ``escolher_sink``. Curar um só deixaria a próxima pessoa
       remedindo o mesmo defeito, e foi o que aconteceu duas vezes em 05/09.
    1. **O nome carrega o MAC inteiro.** Sources de Bluetooth nascem como
       ``bluez_input.XX_XX_XX_XX_XX_XX``; ali o MAC está no nome e a
       atribuição é certa mesmo com vários controles. A busca por MAC é
       restrita a esses nomes DE PROPÓSITO: em nomes ALSA o "hex" que sobra
       ao filtrar letras é lixo de palavra ("Interactive" vira "eac"), e um
       casamento por acaso ali apontaria o mic do controle errado.
    2. **O nome carrega o RABO do MAC** (MIC-BT-01). A ponte de mic por
       Bluetooth deste projeto publica ``hefesto_dualsense_bt_<hex6>``, e
       esses seis dígitos são os três últimos octetos do MAC. O casamento é
       por sufixo, e só quando o que vem depois do prefixo é hex INTEIRO com
       ao menos :data:`MIN_HEX_SUFIXO_BT` dígitos — a ponte tem um caminho
       de fallback, para nó sem ``HID_UNIQ``, em que ali vai o nome do nó
       (``hidraw3``) e não um MAC. Sem esta regra o medidor NUNCA aparecia
       por Bluetooth com dois controles ou mais.
    3. **O MESMO DISPOSITIVO USB** (``usb``). A placa de som e o HID do mesmo
       controle penduram no mesmo nó USB — a interface ``:1.0`` é o áudio, a
       ``:1.3`` é o HID. É a única identidade que existe no cabo, porque o
       nome do nó não tem nenhuma: o ``-00``/``-00.2`` é desempate posicional
       do PipeWire, e o próprio ``/dev/snd/by-id`` só guarda um link para os
       dois. Sem esta regra o mic e o botão de saída sumiam de TODOS os
       controles assim que havia dois no cabo. Ver :mod:`integrations.usb_pai`.
    4. **Um para um.** Uma única source de DualSense e um único controle
       candidato: só pode ser ele — **desde que o casamento por USB não
       desminta** (:meth:`CasamentoUSB.veta`). Um controle no rádio não tem
       placa de som, e o um-para-um sozinho lhe daria a placa de outro
       aparelho com a maior confiança do mundo.

    Fora disso devolve None — e ``None`` é a resposta certa para o controle no
    RÁDIO, que não publica placa nenhuma (medido 15/08/2026: a placa segue o
    transporte). Exibir o mic do controle errado é pior que não exibir nenhum:
    é a regra do "não invente dado na interface".

    ``usb=None`` mantém o comportamento antigo, palavra por palavra. É o que
    deixa a função utilizável sem ir ao sysfs — e o que faz o teste que arranca
    a cura reprovar em vez de explodir.
    """
    alvo = so_hex(uniq)
    if alvo:
        for fonte in fontes:
            sufixo = sufixo_do_canal_do_mic(fonte)
            if sufixo and alvo.endswith(sufixo):
                return fonte
        for fonte in fontes:
            if fonte.lower().startswith("bluez") and alvo in so_hex(fonte):
                return fonte
        for fonte in fontes:
            sufixo = sufixo_da_ponte_bt(fonte)
            if sufixo and alvo.endswith(sufixo):
                return fonte
    if usb is not None:
        casada = usb.casar(fontes, uniq)
        if casada is not None:
            return casada
    if len(fontes) == 1 and len(uniqs_com_audio) == 1 and uniqs_com_audio[0] == uniq:
        if usb is not None and usb.veta(fontes[0], uniq):
            return None
        return fontes[0]
    return None


def escolher_sink(
    sinks: list[str],
    uniq: str,
    uniqs_com_audio: list[str],
    usb: CasamentoUSB | None = None,
) -> str | None:
    """Sink de SAÍDA atribuível ao controle `uniq` — None quando não dá para saber.

    Delega a :func:`escolher_fonte` porque o problema é literalmente o mesmo,
    e as regras dele valem aqui inteiras. O nome do sink continua sem
    identidade — medido nesta máquina, ele é
    ``alsa_output.usb-Sony_Interactive_Entertainment_DualSense_Wireless_Controller-00.analog-surround-40``
    e o ``-00`` é desempate posicional do PipeWire (a string USB de serial do
    DualSense é a mesma em todos) —, mas desde 15/08/2026 a identidade não vem
    mais do nome: vem do dispositivo USB em que a placa e o HID penduram
    juntos. Acender "saída muda" no card do controle errado continua sendo
    pior que não acender; a diferença é que agora dá para saber qual é o card
    certo, em vez de recusar todos.

    A regra do prefixo da ponte BT (:func:`sufixo_da_ponte_bt`) vem junto e
    hoje é INERTE do lado da saída: a ponte publica uma source (o mic chega
    como Opus tunelado em HID) e nenhum sink começa com aquele prefixo. Fica
    porque é a regra certa se um dia houver um sink com identidade no nome.

    **A regra 0 (o canal por controle) é inerte aqui pelo mesmo motivo, e de
    propósito:** ``hefesto_mic_<hex6>`` é um nó de CAPTURA e
    :func:`sinks_dualsense` nunca o devolve. O microfone não sai por lugar
    nenhum; se ele aparecesse numa lista de sinks, o defeito estaria antes
    daqui.
    """
    return escolher_fonte(sinks, uniq, uniqs_com_audio, usb)


def sufixo_da_ponte_bt(fonte: str) -> str:
    """Rabo hex do MAC no nome da source da ponte BT — "" se não for uma.

    Recorta o prefixo ANTES de filtrar hex, e a ordem não é detalhe: o
    próprio prefixo ``hefesto_dualsense_bt_`` é cheio de letras hex
    (``e``, ``f``, ``d``, ``a``, ``b``), e passar o nome inteiro por
    :func:`so_hex` produziria um "MAC" com lixo do prefixo grudado na
    frente — casamento por acaso, que é exatamente o que a regra 1 evita.
    """
    baixa = fonte.lower()
    if not baixa.startswith(PREFIXO_SOURCE_PONTE_BT):
        return ""
    resto = baixa[len(PREFIXO_SOURCE_PONTE_BT) :]
    if len(resto) < MIN_HEX_SUFIXO_BT or so_hex(resto) != resto:
        return ""
    return resto


def sufixo_do_canal_do_mic(fonte: str) -> str:
    """Rabo hex do MAC no nome do CANAL POR CONTROLE — "" se não for um.

    De que controle é este nó. Mesma forma de :func:`sufixo_da_ponte_bt` e
    mesma armadilha evitada do mesmo jeito: recorta o prefixo ANTES de filtrar
    hex, porque ``hefesto_mic_`` tem letras hex dentro (``e``, ``f``, ``c``) e
    passar o nome inteiro por :func:`so_hex` produziria um "MAC" com lixo
    grudado na frente — casamento por acaso.

    **ESTA FUNÇÃO MOROU EM `canal_do_microfone.sufixo_do_canal` ATÉ 06/09/2026**,
    e desceu para cá quando a regra 0 de :func:`escolher_fonte` passou a
    precisar dela. Não é cópia: lá ela não existe mais. Duas verdades sobre "de
    que controle é este nó" é como esta casa fabrica divergência silenciosa.
    """
    baixa = fonte.lower()
    if not baixa.startswith(PREFIXO_SOURCE_CANAL_DO_MIC):
        return ""
    resto = baixa[len(PREFIXO_SOURCE_CANAL_DO_MIC) :]
    if len(resto) < MIN_HEX_SUFIXO_BT or so_hex(resto) != resto:
        return ""
    return resto


def so_hex(valor: str) -> str:
    """Só os dígitos hex minúsculos — mesma normalização de MAC do projeto."""
    return "".join(ch for ch in valor.lower() if ch in "0123456789abcdef")


__all__ = [
    "MARCADORES_DUALSENSE",
    "MIN_HEX_SUFIXO_BT",
    "PREFIXO_SOURCE_CANAL_DO_MIC",
    "PREFIXO_SOURCE_PONTE_BT",
    "CasamentoUSB",
    "escolher_fonte",
    "escolher_sink",
    "fontes_dualsense",
    "sinks_dualsense",
    "so_hex",
    "sufixo_da_ponte_bt",
    "sufixo_do_canal_do_mic",
]

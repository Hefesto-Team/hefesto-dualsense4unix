"""varredura_do_radio.py — quais adaptadores estão VARRENDO, e o que isso custa.

RESERVA-DO-RADIO-01 (20/09/2026). A sprint nasceu querendo **reservar** um
adaptador para os controles e deixar outro para o resto do mundo. A medição de
20/09 derrubou a premissa: não existe *"o adaptador onde o COSMIC varre"*.

    **A varredura é do adaptador que a PESSOA ABRE. Um só, o que ela escolheu,
    e nenhum enquanto ela não escolhe.**

Quatro corridas com a mão dela, a última conferida por foto da tela no instante
da medição. A tela de Bluetooth do ``cosmic-settings`` **lista** os adaptadores
sem varrer nenhum; a busca mora um nível abaixo, dentro do adaptador em que ela
entra, e a lista "Dispositivos próximos" **é** a busca.

Uma reserva estática teria de adivinhar em qual adaptador ela vai clicar — e
erraria. No dia da medição o arranjo dela estava certo **por acaso**: ela entrou
no único adaptador vazio. Bastava ter clicado no primeiro da lista pelo nome,
que hospeda um DualSense, para a perda ser real e silenciosa.

**Este módulo não adivinha: ele PERGUNTA.** ``Discovering`` é propriedade
pública do ``org.bluez.Adapter1``, não custa privilégio nenhum, responde pelo
estado de agora e cobre de graça a **cauda** — na corrida 3 o adaptador varreu
por mais 21 segundos depois de a janela fechar.

E ele não pressupõe bancada nenhuma. A ordem dela de 11/09 é que o produto é
para qualquer usuário; uma reserva que pressupõe três adaptadores é a bancada
dela escrita no código, e é por isso que a reserva morreu e esta leitura ficou.

AUSÊNCIA É RESPOSTA, E É O CONTRATO INTEIRO DESTE MÓDULO
=========================================================
``set()`` vazio quer dizer **duas coisas opostas**: "nenhum adaptador está
varrendo" e "eu não consegui olhar". Devolver as duas com a mesma string é o
defeito que esta casa persegue há um mês — *o instrumento respondia sobre outra
coisa que não o produto*.

Por isso a resposta é a :class:`Varredura`, e não um ``set``: sem ``busctl``,
sem ``bluetoothd`` ou sem permissão ela vem com :attr:`Varredura.motivo`
preenchido e :attr:`Varredura.sei` em ``False``. Quem lê **tem de** olhar o
``sei`` antes de escrever "nenhum" em qualquer lugar.

O DONO DO NÚMERO MORA AQUI
===========================
:data:`QUEDA_MINIMA_MEDIDA` e :data:`QUEDA_MAXIMA_MEDIDA` são as duas corridas
em que a varredura correu **no mesmo adaptador do controle**. Elas são o único
lugar do produto onde esse par de números é dado, e não prosa: o aviso do
``scripts/doctor.sh`` cita os dois, e
``tests/unit/test_a_varredura_do_radio_se_le_e_custa.py`` reprova se os dois
lados divergirem. Número digitado em dois donos diverge na primeira remedição.

O QUE ELE NÃO FAZ
==================
Não liga nem desliga busca. ``StartDiscovery`` e ``StopDiscovery`` são contados
**por cliente** pelo BlueZ (medido em 19/09: ``StopDiscovery`` de terceiro
devolve ``No discovery started`` e a busca continua), então não há alavanca de
fora — só quem ligou desliga. Ler é tudo o que se pode fazer daqui, e é o
bastante para o motor escolher outro destino.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from hefesto_dualsense4unix.integrations import bluez_dbus
from hefesto_dualsense4unix.integrations.conexao_zumbi import mac_limpo

#: A queda de pacotes medida quando a varredura corre **no mesmo adaptador que
#: hospeda o controle**, em percentual. São as duas corridas de 19/09/2026 com
#: um DualSense no rádio do adaptador medido, instrumentadas pelo evdev de
#: MOVIMENTO — a IMU publica ~500 pacotes/s com o controle parado na mesa.
#:
#: O instrumento ANTERIOR contava o ``poll.tick`` do daemon e teria dito "sem
#: dano" nas cinco corridas: ele conta as voltas do laço, que rodam pelo
#: relógio, não os pacotes que chegam do controle (54,8 tiques/s no rádio contra
#: 57,4 no cabo — a mesma taxa). O par abaixo é do instrumento que MEDE o fio.
QUEDA_MINIMA_MEDIDA = 32.5
QUEDA_MAXIMA_MEDIDA = 43.4

# O ORÁCULO do par acima são as três corridas CRUZADAS — varrendo num adaptador,
# medindo em outro —, que deram +5,1%, -4,2% e -3,5%: ruído, e duas delas para o
# lado positivo. É o que autoriza o motor a mexer só no adaptador que varre, e
# ele está escrito por extenso no `scripts/doctor.sh`, que é quem o diz a ela.
# Aqui ele foi uma constante que chamador nenhum lia — a segunda grafia do mesmo
# fato, podada em 20/09/2026 na conferência.

#: ``/org/bluez/hciN`` e nada mais. Os nós de DEVICE (``.../dev_AA_BB_...``)
#: ficam de fora pela forma: eles não têm ``org.bluez.Adapter1``.
_NO_DO_ADAPTADOR = re.compile(r"^/org/bluez/(hci[0-9]+)$")

#: Sem ``busctl`` não há como perguntar — e não perguntar não é "nenhum".
SEM_BUSCTL = "não há `busctl` nesta máquina — não consigo perguntar ao BlueZ"

#: ``busctl tree org.bluez`` mudo: o ``bluetoothd`` não está de pé, o barramento
#: de sistema não está acessível (um sandbox sem o ``org.bluez``), ou o
#: serviço não respondeu. Nenhuma dessas é "nenhum adaptador varre".
SEM_BLUEZ = "o `org.bluez` não respondeu no barramento — não sei quem varre"

#: A árvore respondeu e NENHUM adaptador dela respondeu ao ``Discovering``.
#: Medido em 20/09/2026 com um ``busctl`` travado: sem esta linha a leitura
#: voltava com ``sei=True`` e ``varrendo`` vazio — ou seja, dizendo "ninguém
#: está varrendo" sobre uma mesa em que ninguém foi ouvido. É o `set()` ambíguo
#: que este módulo inteiro existe para matar, entrando pela porta dos fundos.
MESA_TODA_MUDA = "nenhum adaptador respondeu ao `Discovering` — não sei quem varre"

#: O orçamento estourou no meio da leitura: parte da mesa não foi ouvida, e uma
#: leitura interrompida não pode dizer "ninguém varre".
SEM_RESPOSTA_A_TEMPO = (
    "o `org.bluez` não respondeu dentro do orçamento — não sei quem varre"
)

#: QUANTO A LEITURA INTEIRA PODE CUSTAR, em segundos — e quem paga é a thread
#: do GTK. :func:`varredura_recente` é chamada de ``_aplicar_estado``, que o
#: ``ipc_bridge.call_async`` reposta por ``GLib.idle_add``: ela corre na thread
#: do desenho, e o que ela segurar a janela inteira segura junto.
#:
#: **MEDIDO em 20/09/2026, com um `busctl` que não responde: 15,1 s.** Três
#: adaptadores, uma pergunta travada por adaptador, cada uma esperando os 5 s
#: do ``busctl``. É o travamento de 15/09/2026 escrito de novo, com a
#: lembrança segurando só a FREQUÊNCIA e não a DURAÇÃO.
#:
#: Meio segundo é SESSENTA vezes a leitura inteira medida contra o BlueZ vivo
#: desta bancada (8,2 ms de mediana, 8,7 ms no pior caso, sete subprocessos):
#: barramento são não chega perto dele, e barramento travado não passa dele.
ORCAMENTO_DA_LEITURA = 0.5

#: O que uma pergunta recebe quando o orçamento já acabou. Não é zero porque
#: ``subprocess.run(timeout=0)`` mata antes de o processo nascer, e o que se
#: quer aqui é a recusa rápida, não a exceção.
_MINIMO_POR_PERGUNTA = 0.02


@dataclass(frozen=True)
class Varredura:
    """Quem está varrendo agora, e a confissão de quem eu não consegui olhar.

    ``varrendo`` traz o **endereço** do adaptador, minúsculo e com dois-pontos —
    a mesma grafia que o ``HID_PHYS`` do uevent publica e que
    :func:`plano_de_radio.plano_por_adaptador` usa de chave. Nunca ``hciN``: o
    índice é a VAGA, não o aparelho, e ele inverte entre boots (medido em
    24/08/2026). Um filtro por ``hciN`` acertaria hoje e erraria no próximo
    boot, calado.

    ``mudos`` são os ``hciN`` que apareceram na árvore e cuja leitura falhou —
    adaptador em ``down``, ``rfkill``, ou que sumiu entre a árvore e a pergunta.
    Eles não entram em ``varrendo`` **e não entram em "não varre"**: são a parte
    da resposta que não existe.

    ``motivo`` vazio é o único estado em que "não está em ``varrendo``" pode ser
    lido como "não está varrendo" — e é por isso que a mesa INTEIRA muda também
    preenche ``motivo`` (:data:`MESA_TODA_MUDA`): ela é uma leitura que não
    ouviu ninguém, e sem essa linha ela voltava dizendo "ninguém varre".
    """

    varrendo: frozenset[str] = field(default_factory=frozenset)
    mudos: frozenset[str] = field(default_factory=frozenset)
    motivo: str = ""

    @property
    def sei(self) -> bool:
        """``False`` quando a leitura inteira falhou — "não sei", nunca "nenhum"."""
        return not self.motivo

    @property
    def completa(self) -> bool:
        """A leitura respondeu por TODOS os adaptadores que a árvore listou."""
        return self.sei and not self.mudos


def _resta(fim: float) -> float:
    """O que sobra do orçamento para a próxima pergunta, nunca menos do que o mínimo."""
    return max(_MINIMO_POR_PERGUNTA, fim - time.monotonic())


def quem_esta_varrendo(*, orcamento: float = ORCAMENTO_DA_LEITURA) -> Varredura:
    """Os adaptadores com ``Discovering=true``, por endereço — ou "não sei".

    Quatro degraus, e cada um que falha tem resposta PRÓPRIA. A pergunta é ao
    dono do BlueZ (``bluez_dbus.dono()``, BLUEZ-UM-DONO-01): pela foto do
    ``ObjectManager`` quando ele está vivo — sem subprocesso —, pelo ``busctl``
    quando não:

    1. o dono pode perguntar? Não → :data:`SEM_BUSCTL`;
    2. a árvore do ``org.bluez`` lista adaptadores? Nada → :data:`SEM_BLUEZ`;
    3. por adaptador, ``Discovering`` e o endereço (o do kernel, ou o
       ``Address`` quando o kernel não diz). O que não responder entra
       em :attr:`Varredura.mudos`, não em "não varre". Se NENHUM responder, a
       leitura inteira é :data:`MESA_TODA_MUDA` — não ouvir ninguém não é ouvir
       "ninguém";
    4. o ``orcamento`` estourou no meio? → :data:`SEM_RESPOSTA_A_TEMPO`, com o
       que já se soube. Quem chama é a thread do desenho, e ela não pode ficar
       presa num barramento travado: ver :data:`ORCAMENTO_DA_LEITURA`.

    **O endereço é obrigatório para entrar em ``varrendo``.** Um adaptador que
    diz ``Discovering=true`` e não diz ``Address`` é um adaptador que eu não sei
    casar com plano nenhum: ele vai para ``mudos``. Pôr ``hciN`` ali no lugar
    faria o motor comparar maçã com laranja e nunca casar — um filtro que não
    casa é um filtro que não filtra, e ninguém veria.
    """
    leitor = bluez_dbus.dono()
    if not leitor.pode_perguntar():
        return Varredura(motivo=SEM_BUSCTL)

    ate = time.monotonic() + orcamento
    arvore = leitor.caminhos(espera=_resta(ate)) or ()
    adaptadores = [
        (achado.group(1), caminho)
        for caminho in arvore
        if (achado := _NO_DO_ADAPTADOR.match(caminho)) is not None
    ]
    if not adaptadores:
        # Zero adaptadores numa máquina COM BlueZ de pé e zero adaptadores numa
        # máquina SEM BlueZ dão a mesma árvore vazia por este caminho, e a
        # diferença não muda nada para quem lê: nos dois casos eu não tenho
        # notícia de varredura nenhuma, e dizer "ninguém varre" seria inventar.
        return Varredura(motivo=SEM_BLUEZ)

    varrendo: set[str] = set()
    mudos: set[str] = set()
    ouvidos = 0
    estourou = False
    for hci, caminho in adaptadores:
        if time.monotonic() >= ate:
            estourou = True
            mudos.add(hci)
            continue
        estado = bluez_dbus.como_booleano(
            leitor.propriedade(caminho, bluez_dbus.ADAPTADOR, "Discovering", espera=_resta(ate))
        )
        if estado is None:
            mudos.add(hci)
            continue
        ouvidos += 1
        if not estado:
            continue
        endereco = mac_limpo(leitor.endereco_do_adaptador(caminho, espera=_resta(ate)))
        if endereco is None:
            mudos.add(hci)
            continue
        varrendo.add(endereco)
    if estourou:
        motivo = SEM_RESPOSTA_A_TEMPO
    elif ouvidos == 0:
        # A mesa inteira muda. `mudos` já diria isso a quem olhasse, mas o
        # contrato deste módulo é que `sei` responda sozinho — e o único leitor
        # do produto pega só `varrendo`.
        motivo = MESA_TODA_MUDA
    else:
        motivo = ""
    return Varredura(
        varrendo=frozenset(varrendo), mudos=frozenset(mudos), motivo=motivo
    )


#: Por quanto tempo uma leitura serve. **Medido em 20/09/2026 contra o BlueZ
#: vivo desta bancada, com três adaptadores: 8,4 ms de mediana, 9,2 ms no pior
#: caso** (sete leituras). Isso é barato, mas não é de graça, e quem chama é a
#: thread do GTK, que é redesenhada a cada resposta do daemon (~500 ms) — a
#: mesma thread cujo travamento por IPC síncrono custou a esta casa a leva de
#: 15/09/2026 (19 voltas em 40 s contra 117 com a leitura fora do laço).
#:
#: Três segundos não perdem nada: a varredura começa quando uma PESSOA abre uma
#: tela e dura enquanto ela fica lá — dezenas de segundos, no mínimo. E a cauda
#: medida depois de fechar é de 21 s.
SEGUNDOS_DE_VALIDADE = 3.0

#: ``(instante, leitura)`` da última pergunta ao barramento, ou ``None``.
_LEMBRANCA: tuple[float, Varredura] | None = None


def varredura_recente(
    *,
    validade: float = SEGUNDOS_DE_VALIDADE,
    relogio: Callable[[], float] = time.monotonic,
) -> Varredura:
    """Como :func:`quem_esta_varrendo`, mas no máximo uma pergunta por ``validade``.

    É o que a tela chama. Pelo ``busctl``, a leitura crua abre até sete
    subprocessos numa mesa de três adaptadores; repeti-la a cada pintura seria
    pôr o rádio no caminho do desenho, que é a forma exata do defeito de
    15/09/2026.

    **A lembrança segura a FREQUÊNCIA; quem segura a DURAÇÃO é o
    :data:`ORCAMENTO_DA_LEITURA`.** Sem ele, uma leitura a cada 3 s ainda podia
    prender a thread do desenho por 15,1 s — medido em 20/09/2026 —, e é a
    conta das duas juntas que torna esta chamada segura na thread do GTK.

    O relógio é o ``monotonic``, nunca o de parede: mudança de fuso ou ajuste de
    NTP não pode congelar nem invalidar a lembrança.
    """
    global _LEMBRANCA
    agora = relogio()
    lembranca = _LEMBRANCA
    if lembranca is not None and 0.0 <= agora - lembranca[0] < validade:
        return lembranca[1]
    leitura = quem_esta_varrendo()
    _LEMBRANCA = (agora, leitura)
    return leitura



__all__ = [
    "MESA_TODA_MUDA",
    "ORCAMENTO_DA_LEITURA",
    "QUEDA_MAXIMA_MEDIDA",
    "QUEDA_MINIMA_MEDIDA",
    "SEGUNDOS_DE_VALIDADE",
    "SEM_BLUEZ",
    "SEM_BUSCTL",
    "SEM_RESPOSTA_A_TEMPO",
    "Varredura",
    "quem_esta_varrendo",
    "varredura_recente",
]

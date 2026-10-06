"""Registro de identidade MAC→posição na mesa (COR-01, sprint cores-e-led).

O "Controle N" que a usuária vê (rótulos, cor automática da lightbar, LED do
número do controle) era a POSIÇÃO no dict de handles do backend (+1) — replug
reinsere no fim e o número embaralhava. Este registro dá a cada DualSense um
lugar ESTÁVEL na fila, keyed pelo MAC normalizado (12 hex — o mesmo
``norm_mac`` do backend, estável entre USB e BT):

- 1ª aparição de um MAC → entra no FIM da ordem de preferência, atribuição
  LAZY na primeira consulta (``slot_for``) — é isto que faz a cor automática
  nascer certa no MESMO tick de hotplug em que o backend abre o handle (D1);
- desconectar mantém o lugar do MAC na fila — replug recupera o mesmo
  número (D2). Sem roubo LRU (cortado: YAGNI);
- R-15 (auditoria 23/07): DENTRO de um boot, número é do MAC e NINGUÉM
  expira. A expiração por "sessão esvaziou" (o ramo ``_saw_connected`` do
  ``sync_connected``) foi REMOVIDA: ela era assimétrica (só o lado
  DualSense expirava; o registro dos externos nunca expirou) e trocava
  cor/número de dono conforme a ORDEM DE WAKE — desligar os dois DualSense
  e religar em ordem invertida devolvia o 1 ao que voltasse primeiro. Pior:
  entre a expiração e a reatribuição, ``_ds_reserve()`` (external_identity)
  lia piso 0 no meio do tick externo e abria janela de DUPLICATA — a queixa
  "dois player 1, dois player 2";
- R-23 (auditoria 25/07): o número TAMBÉM sobrevive ao BOOT. Era aqui que a
  queixa "ao abrir os jogos ou o perfil, os controles se reenumeram e nunca
  sei o que é o quê" nascia: o ``load`` descartava o ``controllers.json``
  inteiro quando o ``boot_id`` do arquivo diferia do da máquina, então TODO
  reboot renumerava por ordem de conexão. Pior em contêiner/Flatpak, onde
  ``/proc/sys/kernel/random/boot_id`` some: sem boot_id o load abortava e
  bastava REINICIAR O DAEMON para renumerar tudo. O mapa é keyed por MAC —
  e MAC não muda no reboot: ele é IDENTIDADE, não sessão. A única
  renumeração automática que sobrou é a de SCHEMA (arquivo gravado por uma
  versão que numerava de outro jeito, ver Persistência); renumerar por
  vontade dela continua sendo o GESTO explícito ("Renumerar agora" →
  ``compact``);
- R-24 (auditoria 25/07): a atribuição deixou de ser SÓ lazy. ``slot_for``
  só é chamado pelo provider de cor (caminho de output); enquanto nenhum
  DualSense tivesse sido consultado, o registro ficava VAZIO e o piso que
  os externos leem (``_ds_reserve``) valia 0 — o Pro Nintendo tomava o slot
  1 no primeiro tick de externo e os DualSense herdavam 2 e 3 (o "não
  existe Controle 1" medido ao vivo). Agora ``sync_connected`` (tick lento,
  que roda ANTES do tick dos externos no mesmo laço do lifecycle) ATRIBUI
  lugar a todo DualSense conectado que ainda não tem — quem está na mesa
  ocupa 1..N antes de qualquer externo pedir número;
- NUM-01 (25/07): **o que se persiste deixa de ser um número absoluto**.
  R-15 e R-23 curaram a instabilidade ("cor e número trocavam de dono")
  prendendo o NÚMERO ao endereço para sempre; o preço apareceu medido no
  ``controllers.json`` dela: com um só DualSense ligado, ele exibia 2 —
  porque o 1 estava RESERVADO a um endereço que não estava na mesa
  ("ninguém aceita ser o jogador 2 de si mesmo"). Os dois requisitos são
  verdadeiros ao mesmo tempo, e a saída é separar os dois conceitos que
  eram o MESMO inteiro:

  - IDENTIDADE é o endereço, e o que fica gravado dele é o LUGAR NA FILA
    (a ordem de preferência: A vem antes de B) — permanente, estável entre
    sessões e entre boots, exatamente como R-15/R-23 exigem;
  - POSIÇÃO NA MESA é 1..N entre QUEM ESTÁ PRESENTE AGORA — derivada a cada
    consulta (``slot_for``), nunca persistida como número.

  Com os dois na mesa, a fila ``[A, B]`` dá A=1 e B=2 (estabilidade); com só
  o B ligado, a MESMA fila dá B=1 (naturalidade), e quando A volta cada um
  recupera o seu. Fechar a lacuna deixa de ser um gesto e passa a ser
  aritmética. O critério que resume: **nunca existe um jogador 2 sem um
  jogador 1**;
- **D-30 / ORDEM-DE-CHEGADA-01 (decisão, 15/08/2026, 03:54)**: o número
  segue a **ordem de conexão daquele momento**, e não mais o lugar que o
  endereço ganhou num dia qualquer do passado — *"deve ser lembrado por ordem
  de conexão naquele momento apenas. Não uma imagem fixa salva por mec"*. Isto
  REVERTE em parte R-15 e R-23, e por isso vem com as duas garantias que
  aquelas auditorias compraram, escritas aqui como invariante:

  - a **FILA DO MOMENTO** (``_chegada``) é o que ordena a exibição. Ela
    guarda, por key, a **ONDA** em que a casa VIU aquele controle chegar
    (:data:`JANELA_DE_ONDA_SEC`) — não um carimbo de relógio de parede, e
    nada disso vai para o disco;
  - **empate de onda desempata pelo GRAVADO** (o ``rank``). Dois controles
    vistos na MESMA olhada para a mesa (o mesmo ``sync_connected``, o mesmo
    tick do provider) chegaram, para a casa, ao mesmo tempo: aí o registro
    NÃO inventa uma ordem, ele lê a que já tinha. É este degrau que faz o
    restart do daemon com quatro controles já ligados não embaralhar nada
    (R-23) — quem sobrevive ao restart é o gravado, e é dele que a ordem
    renasce;
  - **a marca de chegada NUNCA é solta dentro da sessão** — quem cai e volta
    recupera a onda que tinha, e portanto o MESMO número (D2/R-15). É a
    diferença entre esta entrega e a renumeração por ORDEM DE WAKE que R-15
    arrancou em 23/07: lá, religar dois controles em ordem invertida trocava
    o dono do 1; aqui, os dois voltam ao que eram porque a onda deles é a de
    quando chegaram, não a de quando voltaram;
  - **CONGELAR é gravar** (:meth:`_congelar_locked`): quando a mesa fica
    :data:`JANELA_MESA_ESTAVEL_SEC` sem entrar nem sair ninguém, a ordem do
    momento é escrita na FILA GRAVADA — os ``rank`` dos PRESENTES são
    permutados entre si, na ordem de chegada. O conjunto de ``rank`` não
    muda, só o dono de cada um: nenhum posto some, nenhum vale 0 no meio do
    caminho, e por isso a janela de DUPLICATA que R-15 mediu
    (``_ds_reserve`` lendo piso 0) não pode reabrir. Depois de congelada, a
    ordem do momento e a gravada dizem a MESMA coisa — e é a gravada que
    atravessa o restart e o reboot, exatamente como R-23 exige.

  O que continua valendo de R-15/R-23, sem asterisco: nada expira, o lugar
  do ausente não é dropado, e o "Renumerar agora" (``compact``) segue sendo
  o gesto explícito dela;
.. note::

   **"D9" AQUI NÃO É O "D9" DO DESENHO.** Neste módulo ``D9`` é a decisão do
   *slot volátil* (abaixo). Em
   o registro «O-QUE-ELA-DESENHOU-o-todo-por-aba» de 26/08/2026 ``D9`` é
   outra coisa — a decisão dos três botões de sensor na aba Controles. Os dois
   documentos estão entre os primeiros que quem chega abre, e a colisão já
   custa uma busca errada por leitura; registrada em 29/08/2026 para não custar
   duas.

- o vpad (MAC forjado ``02:fe:...``) NUNCA ganha slot (D9) — o filtro
  existe aqui além do filtro de enumeração do backend, porque outros
  chamadores (describe/co-op) também consultam;
- key sem MAC 12-hex (fallback ``path:...`` de firmware sem serial) ganha
  slot VOLÁTIL: vale na sessão, nunca é persistido (D9 — path muda entre
  boots).

  **O QUE ISSO CUSTA A UM USUÁRIO, escrito em 29/08/2026 porque a mesa desta
  casa NÃO TEM COMO REVELAR:** para quem tem um controle sem serial de 12 hex,
  a memória por identidade **não funciona nunca** — nem os LEDs, nem os
  gatilhos, nem a vibração, nem o alto-falante voltam como ele deixou, em jogo
  nenhum, em sessão nenhuma. Não é degradação: é o recurso inteiro ausente, em
  silêncio, sem uma linha na tela dizendo por quê. Os cinco controles desta
  bancada têm MAC de 12 hex, então **toda prova feita aqui passa** — é a
  amostra mais favorável possível, e é exatamente o que a
  ``D-A-REGUA-E-QUALQUER-MESA-NAO-A-DELA`` (decisão, 29/08/2026) condena. Dono:
  ``O-CONTROLE-SEM-MAC-01``.

  A decisão de não persistir continua CERTA — um path que muda entre boots
  persistido é pior que nada, porque devolve a configuração de um aparelho a
  outro. O que falta não é gravar o path: é uma chave estável para quem não tem
  MAC, e é isso que a sprint procura;

- **O SEGUNDO CONDUÍTE (O-CONTROLE-SEM-MAC-01, 06/09/2026).** A key deixou de
  cair DIRETO no volátil: quando o serial falta, o registro pergunta ao
  ``cracha_provider`` (:meth:`ControllerIdentityRegistry.set_cracha_provider`),
  e só desiste depois dele — e a desistência passou a ser ANUNCIADA
  (:data:`FRASE_SEM_CRACHA`, :meth:`avisos_sem_cracha`).

  **A FORMA DA CHAVE NOVA É A FORMA DA CHAVE VELHA: 12 hex canônicos**, e isso
  não é economia de código, é o requisito. O que o crachá devolve é o MESMO
  endereço que o serial devolveria — outra estrada para o mesmo valor —, então
  o perfil, o ``sysfs_leds``, o co-op e o disco não aprendem forma nenhuma.
  Quem vem depois (``QUEM-E-QUEM-04``) abre a porta do perfil para uma forma
  que já existe.

  **QUAL crachá, e por que não os cinco.** O ensaio de 15/08 achou cinco
  candidatos que saem nos dois transportes e são estáveis byte a byte
  (``0x05``, ``0x09``, ``0x0b``, ``0x20``, ``0x22``); a MESMA linha do mapa
  (``docs/data/mapa-controles.csv``, ``identidade.cracha_nos_dois_transportes``,
  célula ``cabo_detalhe``) já dizia que quatro deles **só pareciam servir**: o
  ``0x20`` agrupa por REVISÃO DE PLACA (a data de compilação colide em PARES
  nos quatro controles desta casa), o ``0x05`` é calibração de IMU e é
  REESCRIVÍVEL pela família ``0x80``, e o ``0x22`` só distingue porque EMBUTE o
  endereço (``buf[17..22]``). Sobra o ``0x09`` — ``buf[1..6]``, o endereço
  invertido —, que é de onde o próprio ``hid_playstation`` tira o ``HID_UNIQ``.
  Por isso o provider devolve **um endereço**, não "um crachá": as duas
  estradas honestas (``0x09`` e o ``0x22`` que o embute) chegam ao mesmo valor,
  e as outras duas não são identidade de unidade.

  **Este módulo não fala com o aparelho, e não vai passar a falar.** Ler
  ``0x09`` é I/O de hidraw, e a docstring da classe promete um ``slot_for`` sem
  I/O (ele roda sob o ``_io_lock`` do backend). O provider é seam: quem sabe
  ler o aparelho é o backend; aqui só se guarda o que ele respondeu. A pergunta
  acontece no TICK LENTO (``sync_connected``, ~2 s, fora do lock) e o caminho
  quente lê só o cache;

- **o crachá NUNCA vence o serial.** Se a key já é um MAC 12-hex, o provider
  não é nem consultado — trocar a chave de quem já é lembrado apagaria a
  memória de toda mesa que hoje funciona, que é exatamente o estrago que esta
  frente existe para evitar;

- **o cache do crachá é esquecido na saída.** Ele é indexado pelo ``uniq``
  CRU (o path), e um path volta a circular: ``/dev/hidraw3`` liberado pode ser
  reocupado por OUTRO aparelho na mesma sessão. Guardar o crachá do primeiro
  não interromperia a identificação — CORROMPERIA, que é pior, e é o único
  desfecho que a ressalva do mapa exclui (*"trocar de braço, cair o rádio ou
  desligar o controle INTERROMPEM a identificação — não a corrompem"*). Então
  quem sai da mesa perde o cache, e volta perguntando de novo;
- DualSense-only (D10) é garantido pelo CHAMADOR por construção: os uniqs
  que chegam aqui vêm dos handles físicos do backend (a enumeração filtra
  por VID/PID da Sony e descarta hidraw virtual). O registro não conhece
  hardware — só strings.

Separação D3 (Refutado 2 do sprint): este slot é EXIBIÇÃO/LED. O índice de
alocação do vpad do co-op (``_next_player_index`` + ``player=1`` do
primário) fica intacto. O MAC do vpad só sai dele sem identidade de aparelho
(E3), e dois vivos nunca o repetem (``uhid_gamepad._MacsDosVpadsVivos``,
O-VPAD-DO-P1-NAO-REPETE-O-MAC-01). R-24 precisou o limite: o índice do vpad é
do JOGO (contíguo, reusado quando alguém sai) e o slot daqui é da EXIBIÇÃO; o
defeito era a LÂMPADA acender o primeiro. Hoje ``CoopManager._numero_exibido``
lê ESTE registro para a barra de player e o índice do vpad nunca chega a um LED.

Persistência (``controllers.json`` no config do app, escrita atômica
mkstemp+os.replace — padrão ``utils/session.py``): cobre o restart do daemon
E o reboot da máquina (R-23). O que governa o load é o
:data:`CONTROLLERS_SCHEMA_VERSION` do arquivo, não mais o ``boot_id``:

- versão IGUAL → a ORDEM DE PREFERÊNCIA (campo :data:`ORDER_FIELD`) é
  restaurada INTEIRA. Entradas voláteis (sem MAC 12-hex) nunca chegam ao
  disco (D9), então "descartar o volátil" é invariante do save, não
  trabalho do load;
- versão DIFERENTE/ausente → arquivo escrito por uma versão que numerava
  por outra regra; é descartado UMA vez e a sessão seguinte renumera. É o
  que cura, sozinha, a numeração torta já gravada na máquina do usuário (o
  externo segurando o slot 1 enquanto os dois DualSense exibiam 2 e 3, e
  depois o ``{"a0fa…": 1, "143a…": 2}`` que fazia o controle sozinho na
  mesa nascer jogador 2 — NUM-01);
- o ``boot_id`` continua GRAVADO, agora como âncora de diagnóstico
  (:func:`_session_anchor`, resiliente: boot_id → machine-id → ``None``).
  Ele não pode mais decidir nada sozinho — foi exatamente a fragilidade
  que renumerava tudo onde ``/proc/sys/kernel/random/boot_id`` não existe.

NUM-01: o arquivo tem UMA fila só, não duas paralelas. O campo
:data:`ORDER_FIELD` é uma LISTA ordenada de ``{"addr", "kind", "rank"}``
onde ``kind`` diz de qual registro é a entrada (:data:`KIND_DUALSENSE` /
:data:`KIND_EXTERNAL`) e ``rank`` é o lugar na fila GLOBAL — os dois lados
dividem um espaço de postos único (era esse compartilhamento que os campos
``slots``/``externals`` do schema 2 escondiam, e é dele que sai a garantia
de nunca haver dois "Controle 1"). Cada save é read-modify-write: preserva
as entradas do OUTRO ``kind`` byte a byte (:func:`merged_order_payload`) e
reescreve só as suas. O ``rank`` é GRAVADO, nunca inferido da posição na
lista: se cada save recompactasse os postos, o lado que não salvou ficaria
com valores obsoletos e a ordem RELATIVA entre um DualSense e um externo
podia inverter sozinha entre dois saves.

O ``config_dir`` é importado LAZY dentro das funções de I/O — preserva
o ponto de monkeypatch dos testes (``xdg_paths.config_dir``), padrão
``save_active_marker``. O arquivo é COMPARTILHADO com o registro dos
externos (``external_identity.py``): ``load`` e ``_save_locked`` dos DOIS
lados adquirem o mesmo ``CONTROLLERS_FILE_LOCK`` (NUMA-04) em volta do
read→``os.replace`` — fecha o lost-update dos dois escritores
independentes sem unificar os dois registros.

Hierarquia de locks (NUM-01 tornou-a explícita porque agora há travessia
nos DOIS sentidos): ``ControllerIdentityRegistry._lock`` → ``External
IdentityRegistry._lock`` → ``CONTROLLERS_FILE_LOCK``. Este registro CHAMA
os providers do lado externo segurando o próprio lock (``_assign_locked``,
``_posicao_locked``); o lado externo, por isso, é PROIBIDO de consultar
este registro segurando o dele — ``ExternalIdentityRegistry`` resolve o que
precisa daqui ANTES de adquirir o próprio ``_lock``. Inverter isso fecha um
ciclo com o ``identity.renumber``, que toma os dois na ordem canônica.

Config do automático (COR-03): o registro também guarda o estado vigente do
toggle ``auto_player_colors`` e do brilho do perfil ativo (D11), configurados
pelo ``ProfileManager.apply`` a cada ativação e consultados pelo provider de
cor injetado no backend (``make_auto_output_provider``).

R-14 (auditoria 23/07) — o automático são DUAS coisas, não uma:

- **ATRIBUIÇÃO de slot** (quem é o Controle N) acontece SEMPRE, com o
  automático ligado ou desligado. Antes, o provider fazia o early-return do
  flag ANTES de ``slot_for`` e o DualSense simplesmente não ganhava número
  enquanto o perfil tivesse ``auto_player_colors:false`` (o ``fps.json``
  dela) — sem número no registro, o piso dos externos (``_ds_reserve``)
  também mentia e a numeração global congelava. Atribuir é identidade;
  desligar o automático é uma opinião sobre APARÊNCIA.
- **APARÊNCIA** tem dois eixos independentes: ``auto_colors`` (a paleta da
  lightbar) e ``auto_numbers`` (o padrão de player-LED do NÚMERO do
  controle, e o LED de número dos externos). Eram o MESMO flag, então um
  clique de cor na GUI apagava a numeração de todo mundo — inclusive a dos
  externos. ``configure(enabled=…)`` mapeia o campo ANTIGO do perfil
  (``auto_player_colors``) para o eixo COR apenas; ``auto_numbers`` nasce
  ``True`` e só muda por ``configure(numbers=…)``. É a migração de default
  compatível: perfil salvo com ``auto_player_colors:false`` perde a paleta,
  nunca a numeração.
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import tempfile
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any

from hefesto_dualsense4unix.utils.logging_config import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from hefesto_dualsense4unix.core.backend_pydualsense import _DesiredOutput

logger = get_logger(__name__)

_CONTROLLERS_FILE = "controllers.json"

#: dela: externo com o slot 1, DualSense em 2 e 3) sobreviveria para sempre,
CONTROLLERS_SCHEMA_VERSION = 3

ORDER_FIELD = "order"

KIND_DUALSENSE = "dualsense"
KIND_EXTERNAL = "external"

_MAX_PERSISTED_SLOTS = 16

JANELA_DE_ONDA_SEC = 0.5

JANELA_MESA_ESTAVEL_SEC = 4.0


def prazo_do_lugar_guardado() -> float:
    """Por quanto tempo o lugar de quem saiu fica guardado — O-ASSENTO-GUARDADO-NAO-ANDA-01."""
    from hefesto_dualsense4unix.core.backend_pydualsense import PRIMARIO_RESERVA_SEC

    return float(PRIMARIO_RESERVA_SEC)


_MACHINE_ID_PATHS = ("/etc/machine-id", "/var/lib/dbus/machine-id")

_MAC_RE = re.compile(
    r"^(?:[0-9a-fA-F]{12}|(?:[0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2})$"
)

_VPAD_MAC_PREFIX = "02fe"

FRASE_SEM_CRACHA = (
    "Este controle não tem identificação estável: o Hefesto não vai "
    "lembrar dele no próximo jogo."
)

#: dois namespaces podia sumir quando o tick do externo e o sync do DualSense
#: salvavam intercalados). ``external_identity.py`` IMPORTA e usa este MESMO
CONTROLLERS_FILE_LOCK = threading.Lock()


def _read_boot_id() -> str | None:
    """boot_id do kernel — identifica ESTE boot da máquina (None se ilegível)."""
    try:
        with open("/proc/sys/kernel/random/boot_id", encoding="utf-8") as fh:
            value = fh.read().strip()
        return value or None
    except OSError:
        return None


def _read_machine_id() -> str | None:
    """machine-id do host (None se ilegível) — 2º degrau da âncora (R-23)."""
    for caminho in _MACHINE_ID_PATHS:
        try:
            with open(caminho, encoding="utf-8") as fh:
                bruto = fh.read().strip()
        except OSError:
            continue
        if bruto:
            return bruto
    return None


def order_entries(data: Any) -> list[tuple[str, str, int]]:
    """Entradas ``(endereço, kind, rank)`` da fila do arquivo, por rank (NUM-01).

    FONTE ÚNICA de leitura do campo :data:`ORDER_FIELD` — os DOIS registros a
    usam (o dos externos importa esta função, nunca escreve a sua). Toda
    entrada malformada é IGNORADA em silêncio, sem derrubar o load: arquivo
    editado à mão, truncado por queda de energia ou escrito por uma versão
    futura não pode custar a numeração da casa inteira (o pior caso é a
    sessão renumerar, que é o que o bump de schema já faz de propósito).

    Ordenar aqui por ``rank`` é contrato, não conveniência: quem carrega
    aplica o teto :data:`_MAX_PERSISTED_SLOTS` cortando pelo FIM da fila, e
    "o fim" só existe se a lista chegar ordenada.

    **A FAIXA SINTÉTICA NÃO É EXPURGADA AQUI, e a decisão é de 18/09/2026.**
    Na bancada havia quatro endereços ``aa:bb:cc:00:00:0{1..4}`` na fila,
    escritos por uma corrida da suíte em 22/08, ocupando os postos 4 a 7 e
    empurrando um DualSense real para o **oitavo**. A primeira cura escrita
    descartava-os aqui — e foi RECUADA no mesmo dia, medida contra a suíte:
    duas dezenas de réguas desta casa usam ``aa:bb:cc`` como endereço de
    controle de verdade, e 236 arquivos de teste a citam. Expurgá-la no
    produto é uma regra sobre a NOSSA suíte, não sobre o aparelho — o alcance
    universal é só o do vpad (``02:fe``), que o ``load`` já recusa.

    Quem cura a máquina que já tem a sujeira é
    ``scripts/check_faixa_sintetica.py --limpar``, gesto explícito e com dono,
    chamado pelo ``doctor``. É o lugar onde esta casa conserta máquina.
    """
    if not isinstance(data, dict):
        return []
    bruto = data.get(ORDER_FIELD)
    if not isinstance(bruto, list):
        return []
    entradas: list[tuple[str, str, int]] = []
    for item in bruto:
        if not isinstance(item, dict):
            continue
        addr = item.get("addr")
        kind = item.get("kind")
        rank = item.get("rank")
        if not isinstance(addr, str) or not addr:
            continue
        if kind not in (KIND_DUALSENSE, KIND_EXTERNAL):
            continue
        if not isinstance(rank, int) or isinstance(rank, bool) or rank < 1:
            continue
        entradas.append((addr, kind, rank))
    entradas.sort(key=lambda e: (e[2], 0 if e[1] == KIND_DUALSENSE else 1, e[0]))
    return entradas


def merged_order_payload(
    existente: Any, kind: str, ranks: dict[str, int]
) -> list[dict[str, Any]]:
    """Fila nova: as entradas do OUTRO ``kind`` preservadas + as do ``kind`` atual (NUM-01).

    O read-modify-write que os dois registros já faziam por namespace
    (``slots`` e ``externals``), agora sobre a fila única. ``existente`` é o
    JSON lido do disco (``None``/lixo = fila vazia — o chamador só o passa
    quando a versão do arquivo BATE, senão estaria recarimbando com selo de
    válida uma numeração que o ``load`` acabou de recusar — R-23).

    Empate de ``rank`` entre os dois lados só pode vir de corrupção herdada;
    a desempate é a MESMA regra do cross-check do load — DualSense primeiro —
    para que a ordem gravada e a ordem exibida nunca discordem. Endereço
    repetido nos dois ``kind`` (arquivo degenerado) fica com o dono desta
    escrita: quem está salvando é quem tem o estado vivo.
    """
    meus = {str(addr): int(rank) for addr, rank in ranks.items()}
    juntos: list[tuple[str, str, int]] = [
        (addr, k, rank)
        for addr, k, rank in order_entries(existente)
        if k != kind and addr not in meus
    ]
    juntos.extend((addr, kind, rank) for addr, rank in meus.items())
    juntos.sort(key=lambda e: (e[2], 0 if e[1] == KIND_DUALSENSE else 1, e[0]))
    return [{"addr": addr, "kind": k, "rank": rank} for addr, k, rank in juntos]


def _session_anchor() -> str | None:
    """Âncora de sessão RESILIENTE: boot_id → machine-id → ``None`` (R-23)."""
    valor = _read_boot_id()
    if valor:
        return valor
    machine_id = _read_machine_id()
    return f"machine:{machine_id}" if machine_id else None


class ControllerIdentityRegistry:
    """MAC normalizado → lugar na FILA; a exibição é 1..N entre os presentes."""

    def __init__(self, *, clock: Callable[[], float] | None = None) -> None:
        self._lock = threading.RLock()
        self._clock: Callable[[], float] = clock or relogio_do_lugar_guardado
        self._chegada: dict[str, int] = {}
        self._onda = 0
        self._onda_aberta_em: float | None = None
        self._mesa_mudou_em: float = self._clock()
        self._mesa_congelada = False
        self._ordem: dict[str, int] = {}
        self._volatile: set[str] = set()
        self._connected: set[str] = set()
        self._lampadas: dict[str, int] = {}
        self._guardados: dict[str, float] = {}
        self._entrada: dict[str, int] = {}
        self._entradas = 0
        self._entradas_no_ultimo_tique = 0
        self._dirty = False
        self._loaded = False
        self._vpad_logged: set[str] = set()
        #: ``uniq`` cru de um controle SEM serial e devolve o endereço que o
        self._cracha_provider: Callable[[str], str | None] | None = None
        self._cracha: dict[str, str] = {}
        self._sem_cracha: set[str] = set()
        #: a fila é ÚNICA entre DualSense e externos, então a atribuição une
        #: esses lugares ao ``ocupados`` — um DualSense que entra DEPOIS de um
        self._extra_reserved: Callable[[], set[int]] | None = None
        #: nenhum DualSense pode exibir), mas ``_extra_reserved`` não sabe
        self._external_present: Callable[[], set[int]] | None = None
        self._soltar_os_externos: Callable[[], object] | None = None
        self._auto_colors = True
        self._auto_numbers = True
        self._auto_brightness = 1.0
        #: provider lê sem I/O e o `state_full` lê também. Só a RESPOSTA
        self._fabrica: dict[str, Any] = {}
        self._agenda_da_fabrica: Any = None
        self._perguntar_a_fabrica: Callable[[str], Any] | None = None
        self._ao_chegar_o_plastico: Callable[[], object] | None = None


    def configure(
        self,
        *,
        enabled: bool | None = None,
        brightness: float | None = None,
        numbers: bool | None = None,
    ) -> None:
        """Configura o estado vigente do automático (chamado na ativação de perfil).

        ``enabled`` = ``profile.leds.auto_player_colors`` — R-14: mapeia SÓ o
        eixo COR (o campo do schema é literalmente sobre cor; o acoplamento
        com a numeração era o defeito). ``numbers`` é o eixo da NUMERAÇÃO
        (padrão de player-LED do DualSense e LED de número dos externos): sem
        campo no schema ainda, fica ``True`` até alguém pedir o contrário —
        default compatível com todo perfil já salvo. ``brightness`` =
        ``profile.leds.lightbar_brightness`` (a cor automática respeita o
        brilho do perfil — D11). ``None`` preserva o valor atual (chamada
        parcial). Perfil SEM seção ``leds`` no JSON valida com os defaults do
        schema (``LedsConfig()``) → auto ON e brilho 1.0 — decisão documentada
        do COR-03: sem seção = sem opinião = o default do campo (True).
        """
        with self._lock:
            if enabled is not None:
                self._auto_colors = bool(enabled)
            if numbers is not None:
                self._auto_numbers = bool(numbers)
            if brightness is not None:
                self._auto_brightness = max(0.0, min(1.0, float(brightness)))

    @property
    def auto_enabled(self) -> bool:
        """True quando as cores automáticas por controle estão ligadas."""
        with self._lock:
            return self._auto_colors

    @property
    def auto_numbers_enabled(self) -> bool:
        """True quando a NUMERAÇÃO automática (player-LED) está ligada (R-14)."""
        with self._lock:
            return self._auto_numbers

    @property
    def auto_brightness(self) -> float:
        """Brilho vigente [0.0, 1.0] que escala a cor automática (D11)."""
        with self._lock:
            return self._auto_brightness


    @staticmethod
    def _canonical(uniq: str) -> tuple[str, bool]:
        """Devolve ``(key, persistível)`` — MAC 12-hex canônico ou key volátil."""
        value = uniq.strip()
        if _MAC_RE.match(value):
            return value.lower().replace(":", "").replace("-", ""), True
        return value, False

    def _chave(self, uniq: str) -> tuple[str, bool]:
        """``_canonical`` mais o CRACHÁ já resolvido (O-CONTROLE-SEM-MAC-01)."""
        key, persistable = self._canonical(uniq)
        if persistable or not key:
            return key, persistable
        with self._lock:
            do_cracha = self._cracha.get(uniq)
        if do_cracha:
            return do_cracha, True
        return key, False

    def resolver_crachas(self, uniqs: Iterable[str]) -> None:
        """Pergunta o CRACHÁ de quem não tem serial — TICK LENTO, fora do lock."""
        with self._lock:
            provider = self._cracha_provider
            ja_sabidos = set(self._cracha)
        pendentes: list[str] = []
        for uniq in uniqs:
            if not uniq or not isinstance(uniq, str):
                continue
            _, persistable = self._canonical(uniq)
            if persistable or uniq in ja_sabidos or uniq in pendentes:
                continue
            pendentes.append(uniq)
        for uniq in pendentes:
            achado: str | None = None
            if provider is not None:
                try:
                    achado = provider(uniq)
                except Exception as exc:
                    logger.info("identity_cracha_falhou", uniq=uniq, err=str(exc))
                    achado = None
            key: str | None = None
            if achado and isinstance(achado, str):
                candidata, ok = self._canonical(achado)
                if ok and not candidata.startswith(_VPAD_MAC_PREFIX):
                    key = candidata
                elif achado:
                    logger.warning(
                        "identity_cracha_recusado — o crachá não é um "
                        "endereço de 12 hex de controle real",
                        uniq=uniq,
                    )
            if key is not None:
                with self._lock:
                    self._cracha[uniq] = key
                    self._sem_cracha.discard(uniq)
                logger.info("identity_cracha_resolvido", uniq=uniq, key=key)
                continue
            with self._lock:
                novo = uniq not in self._sem_cracha
                self._sem_cracha.add(uniq)
            if novo:
                logger.warning(
                    "identity_sem_cracha_nao_sera_lembrado",
                    uniq=uniq,
                    frase=FRASE_SEM_CRACHA,
                )

    def _esquecer_cracha_locked(self, uniqs_vivos: set[str]) -> None:
        """Solta o crachá de quem saiu da mesa (já sob ``self._lock``)."""
        for uniq in list(self._cracha):
            if uniq not in uniqs_vivos:
                del self._cracha[uniq]
        self._sem_cracha &= uniqs_vivos

    def avisos_sem_cracha(self) -> list[dict[str, str]]:
        """Os controles que a casa DESISTIU de lembrar, com a frase (leitura)."""
        with self._lock:
            return [
                {"uniq": uniq, "frase": FRASE_SEM_CRACHA}
                for uniq in sorted(self._sem_cracha)
            ]

    def set_cracha_provider(
        self, provider: Callable[[str], str | None] | None
    ) -> None:
        """Injeta o SEGUNDO CONDUÍTE da identidade (O-CONTROLE-SEM-MAC-01).

        ``provider(uniq_cru)`` recebe o ``uniq`` de um controle cujo firmware
        NÃO expôs serial — a key que hoje cai direto no volátil — e devolve o
        endereço que o aparelho respondeu (o feature ``0x09``: ``buf[1..6]``,
        o endereço invertido; é de onde o ``hid_playstation`` tira o
        ``HID_UNIQ``), em qualquer grafia que ``_canonical`` aceite. Devolve
        ``None`` quando o aparelho não responde, e é isso que faz a
        desistência ser ANUNCIADA em vez de calada.

        **Ele custa I/O de hidraw, e por isso só é chamado no TICK LENTO**
        (``sync_connected``, ~2 s) e FORA do ``_lock``. O caminho quente
        (``slot_for``, sob o ``_io_lock`` do backend) lê só o cache — a
        promessa "sem I/O de disco nem de aparelho" da docstring da classe
        continua inteira. Se o provider levantar, o controle segue volátil:
        nenhum caminho de identidade morre porque o aparelho não respondeu.

        Sem fiação (``None``) o registro se comporta como sempre — o segundo
        conduíte é ADITIVO, nunca uma troca de regra.
        """
        with self._lock:
            self._cracha_provider = provider

    def set_external_reserve_provider(
        self, provider: Callable[[], set[int]] | None
    ) -> None:
        """Injeta o provider dos lugares já detidos pelos EXTERNOS (EXT-04).

        A fila é um espaço ÚNICO: os externos já leem o piso dos DualSense
        (``reserve``) ao entrar; este provider fecha o laço no sentido
        inverso — a atribuição de um DualSense NOVO une os lugares dos
        externos aos ``ocupados``, para não colidir com um externo que entrou
        antes. Fiado por ``lifecycle._wire_external_registry`` só no backend
        real; ``None`` (FakeController) preserva o comportamento histórico.
        NÃO reordena quem já tem lugar — só evita colisões NOVAS.
        """
        with self._lock:
            self._extra_reserved = provider

    def set_external_presence_provider(
        self, provider: Callable[[], set[int]] | None
    ) -> None:
        """Injeta o provider dos lugares dos externos PRESENTES agora (NUM-01)."""
        with self._lock:
            self._external_present = provider

    def set_external_release_provider(
        self, provider: Callable[[], object] | None
    ) -> None:
        """Injeta quem solta o lugar guardado dos externos (O-ASSENTO-GUARDADO-NAO-ANDA-01)."""
        with self._lock:
            self._soltar_os_externos = provider

    def slot_for(
        self,
        uniq: str | None,
        *,
        assign: bool = True,
        autoridade_de_presenca: bool = True,
    ) -> int | None:
        """Número EXIBIDO do controle ``uniq`` — 1..N entre os PRESENTES.

        NUM-01: o que se guarda de ``uniq`` é o lugar dele na fila; o que se
        devolve aqui é a COLOCAÇÃO desse lugar contando só quem está presente
        (incluindo os externos, via provider — a mesa é uma só). Um controle
        cujo lugar na fila é o terceiro exibe 1 quando é o único ligado, e
        volta a exibir 3 quando os dois da frente acordam. Era o mesmo
        inteiro até a versão 2 do schema, e é por isso que o único DualSense
        ligado da mantenedora nascia jogador 2. Quem saiu há menos de
        :func:`prazo_do_lugar_guardado` ainda conta: o lugar dele fica vazio e
        ninguém anda (O-ASSENTO-GUARDADO-NAO-ANDA-01).

        LAZY por decisão (D1): a primeira consulta de um uniq válido (feita
        pelo provider de cor dentro do reconcile do backend, ou por quem
        rotula) é o que dá o lugar na fila — a cor/número nascem certos no
        MESMO tick de hotplug. ``assign=False`` só consulta (leitura pura:
        não atribui, não marca conectado) e, para um uniq AUSENTE que já tem
        lugar, devolve a colocação que ele teria se estivesse na mesa.

        ``autoridade_de_presenca=False`` — QUATRO-NA-MESA-01, defeito 1
        (06/09/2026): quem chama é uma LEITURA, não o tique. Ele continua
        podendo ATRIBUIR lugar na fila (identidade, R-14 §1) e continua
        pondo na mesa um endereço que ESTREIA nesta consulta (D1: a cor e o
        número nascem certos no mesmo tique de hotplug) — mas **não
        RESSUSCITA** quem o ``sync_connected`` já declarou ausente. Ver o
        bloco *"Os dois escritores de ``_connected``"* na docstring de
        :func:`make_auto_output_provider` para o que isso custava.

        Guardas: ``None``/vazio → None; MAC de vpad (``02:fe:...``) → None
        com log (D9 — o vpad jamais é "Controle N"). SEM I/O de disco — o
        provider roda sob o ``_io_lock`` do backend; a persistência fica com
        o ``sync_connected`` (tick lento).
        """
        if not uniq or not isinstance(uniq, str):
            return None
        key, persistable = self._chave(uniq)
        if not key:
            return None
        if key.startswith(_VPAD_MAC_PREFIX) and persistable:
            with self._lock:
                if key not in self._vpad_logged:
                    self._vpad_logged.add(key)
                    logger.warning("identity_slot_vpad_ignorado", uniq=key)
            return None
        chegou_gente_nova = False
        with self._lock:
            self._avaliar_mesa_locked()
            estreia = key not in self._ordem
            if estreia:
                if not assign:
                    return None
                self._assign_locked(key, persistable)
            if (
                assign
                and key not in self._connected
                and (autoridade_de_presenca or estreia)
            ):
                dono_de_lugar = key in self._guardados_locked()
                self._connected.add(key)
                self._mesa_mexeu_locked()
                self._marcar_chegada_locked(key)
                self._entrou_na_mesa_locked(key)
                self._retomar_o_lugar_locked(key)
                if not dono_de_lugar and persistable:
                    chegou_gente_nova = True
                    self._quem_chega_novo_refaz_a_mesa_locked()
            numero = self._posicao_locked(key)
        if chegou_gente_nova:
            self._soltar_os_lugares_dos_externos()
        return numero

    def _assign_locked(self, key: str, persistable: bool) -> int:
        """Põe ``key`` no FIM da fila (já sob ``self._lock``). Fonte ÚNICA."""
        ocupados = set(self._ordem.values())
        prov = self._extra_reserved
        if prov is not None:
            # externos detêm (um DualSense que conecta DEPOIS de um externo
            with contextlib.suppress(Exception):
                ocupados |= {int(s) for s in prov()}
        rank = max(ocupados) + 1 if ocupados else 1
        self._ordem[key] = rank
        if persistable:
            self._dirty = True
        else:
            self._volatile.add(key)
        logger.info(
            "identity_lugar_atribuido",
            uniq=key,
            rank=rank,
            volatil=not persistable,
        )
        return rank


    def _mesa_mexeu_locked(self) -> None:
        """Alguém entrou ou saiu — a mesa volta a se mexer (já sob o lock)."""
        self._mesa_mudou_em = self._clock()
        self._mesa_congelada = False

    def _marcar_chegada_locked(self, key: str) -> None:
        """Carimba a ONDA de chegada de ``key`` NESTA sessão (já sob o lock)."""
        if key in self._chegada:
            return
        agora = self._clock()
        aberta = self._onda_aberta_em
        if aberta is None or agora - aberta >= JANELA_DE_ONDA_SEC:
            self._onda += 1
            self._onda_aberta_em = agora
        self._chegada[key] = self._onda

    def _ordem_do_momento_locked(self, presentes: list[str]) -> list[str]:
        """``presentes`` ordenados pela FILA DO MOMENTO (já sob o lock)."""
        return sorted(
            presentes,
            key=lambda k: (self._chegada.get(k, 0), self._ordem.get(k, 0), k),
        )

    def _avaliar_mesa_locked(self) -> bool:
        """Congela a ordem do momento se a mesa já está estável (sob o lock)."""
        if self._mesa_congelada or not self._connected:
            return False
        if self._clock() - self._mesa_mudou_em < JANELA_MESA_ESTAVEL_SEC:
            return False
        self._mesa_congelada = True
        self._congelar_locked()
        return True

    def _congelar_locked(self, na_mesa: list[str] | None = None) -> None:
        """Grava a ordem do momento na FILA GRAVADA — CONGELAR (já sob o lock)."""
        presentes = (
            [k for k in self._connected if k in self._ordem]
            if na_mesa is None
            else na_mesa
        )
        if len(presentes) < 2:
            return
        postos = sorted(self._ordem[k] for k in presentes)
        mudou = False
        for key, posto in zip(
            self._ordem_do_momento_locked(presentes), postos, strict=True
        ):
            if self._ordem[key] != posto:
                self._ordem[key] = posto
                mudou = True
        if not mudou:
            return
        self._dirty = True
        logger.info(
            "identity_ordem_do_momento_congelada",
            ordem={k: self._ordem[k] for k in presentes},
        )

    def snapshot_chegada(self) -> dict[str, int]:
        """Cópia da FILA DO MOMENTO: key → onda de chegada (D-30). Leitura pura."""
        with self._lock:
            return dict(self._chegada)

    def mesa_congelada(self) -> bool:
        """True quando a ordem do momento já foi gravada para esta mesa (D-30)."""
        with self._lock:
            return self._mesa_congelada


    def _guardar_o_lugar_locked(self, key: str) -> None:
        """``key`` saiu da mesa: o lugar dele fica guardado (já sob o lock)."""
        if key not in self._ordem or key in self._volatile:
            return
        prazo = prazo_do_lugar_guardado()
        self._guardados[key] = self._clock() + prazo
        logger.info("lugar_guardado", uniq=key, prazo_s=prazo)

    def _retomar_o_lugar_locked(self, key: str) -> None:
        """``key`` voltou para a mesa: o lugar deixa de estar guardado."""
        if self._guardados.pop(key, None) is not None:
            logger.info("lugar_guardado_retomado", uniq=key)

    def _guardados_locked(self) -> list[str]:
        """Quem tem o lugar guardado AGORA. Leitura pura, sob o lock."""
        agora = self._clock()
        return [
            key
            for key, ate in self._guardados.items()
            if ate > agora and key in self._ordem and key not in self._connected
        ]

    def _vencer_os_guardados_locked(self) -> None:
        """Esquece o lugar guardado cujo prazo passou (tique lento, sob o lock)."""
        agora = self._clock()
        for key in [k for k, ate in self._guardados.items() if ate <= agora]:
            del self._guardados[key]
            logger.info("lugar_guardado_venceu", uniq=key)

    def soltar_os_lugares_guardados(self, *, motivo: str = "renumerar") -> bool:
        """Solta todo lugar guardado, dos dois registros. Devolve se havia."""
        with self._lock:
            havia = bool(self._guardados)
            self._guardados.clear()
        if havia:
            logger.info("lugares_guardados_soltos", motivo=motivo)
        return self._soltar_os_lugares_dos_externos() or havia

    def _soltar_os_lugares_dos_externos(self) -> bool:
        """O mesmo, do lado dos externos — SEMPRE fora do ``_lock``.

        A hierarquia de locks é DualSense → externos, e quem chama isto já
        soltou o daqui: o registro dos externos pode estar, na mesma hora,
        pedindo os lugares dos DualSense.
        """
        externos = self._soltar_os_externos
        if externos is None:
            return False
        with contextlib.suppress(Exception):
            return bool(externos())
        return False

    def _entrou_na_mesa_locked(self, key: str) -> None:
        """Carimba a ENTRADA de ``key`` em ``_connected`` (sob o lock)."""
        self._entradas += 1
        self._entrada[key] = self._entradas

    def _quem_chega_novo_refaz_a_mesa_locked(self) -> bool:
        """Gente NOVA chegou: todo lugar guardado se solta (sob o lock)."""
        if not self._guardados:
            return False
        self._guardados.clear()
        logger.info("lugares_guardados_soltos", motivo="chegou_gente_nova")
        return True

    def guardados(self) -> dict[str, float]:
        """Cópia de quem tem o lugar guardado agora → segundos que faltam."""
        with self._lock:
            agora = self._clock()
            return {k: self._guardados[k] - agora for k in self._guardados_locked()}

    def _external_present_ranks_locked(self) -> set[int]:
        """Lugares dos externos que contam para a exibição (já sob o lock).

        NUM-01: com o provider de presença fiado, são os externos LIGADOS —
        a contagem 1..N é da mesa inteira. Sem ele, degrada para
        ``_extra_reserved`` (todos os lugares de externo, ligados ou não):
        conservador de propósito, porque a falha aceitável é um buraco na
        numeração e a inaceitável é dois controles exibindo o mesmo número.

        Lugares que ESTE registro também detém são descontados: os dois lados
        dividem a fila, então uma sobreposição só pode ser corrupção ou um
        dublê de teste — e contá-la empurraria um DualSense para cima sem
        ninguém do outro lado na mesa.
        """
        bruto: set[int] = set()
        for prov in (self._external_present, self._extra_reserved):
            if prov is None:
                continue
            with contextlib.suppress(Exception):
                bruto = {int(s) for s in prov()}
                break
        return bruto - set(self._ordem.values())

    def _numeros_da_mesa_locked(self) -> dict[str, int]:
        """Número EXIBIDO de CADA presente, numa leitura só (sob ``self._lock``)."""
        return {
            chave: numero
            for chave, numero in self._assentos_locked().items()
            if chave in self._connected
        }

    def _assentos_locked(self) -> dict[str, int]:
        """O número de cada ASSENTO da mesa — os presentes e os guardados."""
        na_mesa = [k for k in self._connected if k in self._ordem]
        na_mesa += self._guardados_locked()
        if not na_mesa:
            return {}
        postos = sorted(self._ordem[k] for k in na_mesa)
        externos = self._external_present_ranks_locked()
        numeros: dict[str, int] = {}
        for posicao, (chave, posto) in enumerate(
            zip(self._ordem_do_momento_locked(na_mesa), postos, strict=True)
        ):
            numeros[chave] = posicao + sum(1 for r in externos if r < posto) + 1
        return numeros

    def numeros_da_mesa(self) -> dict[str, int]:
        """Tabela key→número de TODOS os presentes agora. Leitura pura."""
        with self._lock:
            self._avaliar_mesa_locked()
            return self._numeros_da_mesa_locked()

    def _numeros_das_lampadas_locked(self) -> dict[str, int]:
        """O número que cada presente pode MOSTRAR NO APARELHO (sob ``_lock``).

        APARELHO-NAO-SE-CONTRADIZ-01, decisão de 20/09/2026, verbatim:
        *"As lâmpadas esperam a cor"*.

        **O QUE FOI MEDIDO, e é a razão desta função existir.** Ela desligou o
        P3 e olhou o P4, com os quatro DualSense na mesa::

            23:56:17.747  controller_disconnected
                  ~4 s    as LÂMPADAS do aparelho mudam para três
            23:56:47.765  numeracao_da_mesa_mudou arma o gatilho
            23:56:49.284  gatilho_da_cor_escrito: rosa → verde

        Por **27 segundos** o mesmo controle mostrava três lâmpadas de Player 3
        e a barra do Player 4. A palavra de produto, confirmando a predição: *"Rosa e
        só verde meio minuto depois"*.

        A assimetria não era de desenho: as lâmpadas saem por rotas que não
        esperam nada (o `set_players` do sysfs, o `0x31` só com o número do
        co-op), e a cor por rádio só chega pelo report que o gatilho escreve.
        **A cura é anterior às rotas**: os dois campos da camada automática
        saem do MESMO número, e esse número é este — o que já foi LIBERADO.

        **QUEM ESTREIA NÃO ESPERA.** Uma key sem linha congelada é um controle
        que acabou de chegar: ele não tem número velho para contradizer, então
        recebe o de agora na hora (é a D1 de sempre — *"a cor nasce certa no
        tique do hotplug"*). O que espera é só a MUDANÇA.

        **E A ESTREIA NUNCA SENTA NO COLO DE NINGUÉM.** Se o número de agora do
        que estreia já está congelado com OUTRO, ele fica sem opinião (ausente
        da tabela) até a liberação. Esta guarda não é zelo: sem ela, o caminho
        *"o P3 sai, o P5 chega antes do gatilho"* poria dois controles no mesmo
        jogador — que é exatamente o defeito de 27/08/2026 que a
        ``numero_da_lampada`` existe para ter matado. Congelar nunca pode
        ressuscitar uma colisão.

        **ESTA LEITURA NÃO CONGELA NADA**, e é o ponto de desenho desta cura.
        A única coisa que ela escreve em ``self._lampadas`` é a PODA de quem
        saiu da mesa; quem põe número ali é só :meth:`liberar_as_lampadas`. Uma
        leitura que congelasse gravaria o número da mesa PELA METADE — o lote
        que o ``_assentar_mesa_locked`` e a MESA-NO-MEIO-DO-LOTE-01 vieram
        curar —, e ele ficaria preso até a liberação seguinte. Com a tabela
        vazia (daemon recém-subido, registro de teste, dublê sem gatilho) a
        resposta é a mesa de agora, byte a byte como antes desta sprint.

        E quem saiu da mesa some daqui junto: a tabela nunca guarda ausente,
        pela mesma razão que ``numero_da_lampada`` devolve ``None`` para ele.
        """
        agora = self._numeros_da_mesa_locked()
        for key in [k for k in self._lampadas if k not in agora]:
            del self._lampadas[key]
        if not self._lampadas:
            return agora
        fora = dict(self._lampadas)
        tomados = set(fora.values())
        for key, numero in agora.items():
            if key in fora or numero in tomados:
                continue
            fora[key] = numero
            tomados.add(numero)
        return fora

    def liberar_as_lampadas(self) -> bool:
        """Solta o número novo para o APARELHO. Devolve se algo se mexeu."""
        with self._lock:
            self._avaliar_mesa_locked()
            agora = self._numeros_da_mesa_locked()
            if agora == self._lampadas:
                return False
            self._lampadas = dict(agora)
        logger.info("lampadas_liberadas", numeros=dict(agora))
        return True

    def numero_da_lampada(
        self,
        uniq: str | None,
        *,
        assign: bool = True,
        autoridade_de_presenca: bool = True,
    ) -> int | None:
        """Número que ``uniq`` pode ACENDER agora — None quando não há um.

        Irmão de ``slot_for``, e a diferença é a PERGUNTA que cada um responde:

        - ``slot_for`` responde *"que número este endereço tem — ou TERIA se
          estivesse na mesa"*. Para um AUSENTE a resposta sai do LUGAR
          GRAVADO, que é um número de OUTRO espaço: o da fila de preferência,
          onde o ausente continua contando. É a resposta certa para um
          rótulo de GUI ("Controle 1" continua sendo dele) e a resposta
          ERRADA para uma lâmpada;
        - aqui a pergunta é *"que número este controle acende AGORA"*, e ela
          só tem resposta para quem está na mesa. Ausente devolve ``None``,
          que o provider de cor lê como "sem opinião" — o controle segue com
          o que já tinha até o próximo batimento, em vez de acender um
          número que outro já está acendendo.

        MEDIDO em 27/08/2026, com os quatro DualSense do usuário no rádio: o link
        de um caiu e voltou entre dois ``sync_connected``. Ele continuou
        recebendo escrita (o handle voltou antes do batimento) e acendeu o
        LUGAR GRAVADO dele, que era 1; o primeiro da mesa também acendia 1.
        Dois controles no jogador 1, nenhum no 4, e assim ficou por 28
        minutos — porque a lâmpada só é reescrita quando algo acontece.

        ``assign=True`` (padrão) mantém o contrato do R-14 §1: ATRIBUIR lugar
        na fila é identidade, não aparência, e acontece pelo mesmo caminho de
        sempre (``slot_for``) antes de qualquer teste de presença.

        ``autoridade_de_presenca`` é repassado ao ``slot_for`` sem tradução —
        é o provider de cor que o desliga (QUATRO-NA-MESA-01, defeito 1).

        **A RESPOSTA É A DO APARELHO, e não a da mesa — 20/09/2026.** O nome
        desta função sempre foi o da LÂMPADA, e desde a
        APARELHO-NAO-SE-CONTRADIZ-01 ele é literal: sai de
        :meth:`_numeros_das_lampadas_locked`, a tabela que só avança quando a
        cor avança. Quem quer a mesa de AGORA — a TELA — chama
        :meth:`numeros_da_mesa`, que não espera nada.

        **E ELA GOVERNA OS DOIS CAMPOS DA CAMADA AUTOMÁTICA**, a cor e o
        número (``make_auto_output_provider``), porque é isso que impede a
        contradição: fossem dois números, a cura seria uma corrida entre duas
        rotas de escrita — que é justamente o defeito medido.
        """
        if assign:
            self.slot_for(uniq, autoridade_de_presenca=autoridade_de_presenca)
        if not uniq or not isinstance(uniq, str):
            return None
        key, persistable = self._chave(uniq)
        if not key or (persistable and key.startswith(_VPAD_MAC_PREFIX)):
            return None
        with self._lock:
            self._avaliar_mesa_locked()
            return self._numeros_das_lampadas_locked().get(key)

    def _posicao_locked(self, key: str) -> int | None:
        """Colocação de ``key`` entre os PRESENTES (já sob ``self._lock``).

        O coração do NUM-01: 1 + quantos controles presentes vêm ANTES dele.
        Empate de lugar com um externo (só possível por corrupção do arquivo)
        resolve a favor do DualSense — a MESMA regra do cross-check do
        ``load`` e da gravação da fila, para que a ordem exibida nunca
        discorde da ordem gravada.

        D-30 mudou UMA coisa: quem decide "antes" entre os DualSense
        presentes é a FILA DO MOMENTO, não o ``rank``. O mecanismo é uma
        permutação, e ela é o que mantém o resto da casa intacto: os postos
        que os presentes ocupam são os MESMOS (``postos``), só muda de quem é
        cada um. O conjunto que ``present_ranks()`` publica para o lado dos
        externos não se mexe, então a contagem 1..N da mesa inteira continua
        fechando sem buraco e sem duplicata — e um controle AUSENTE segue
        sendo colocado pelo lugar gravado dele, que é a resposta à pergunta
        "que número ele teria se estivesse na mesa".

        **Os dois ramos abaixo são dois ESPAÇOS DE NUMERAÇÃO diferentes**, e
        misturá-los na mesma mesa foi o defeito de 27/08/2026 (ver
        ``numero_da_lampada``): o presente é colocado entre os presentes, o
        ausente é colocado pelo gravado. Quem acende lâmpada NÃO chama isto
        — chama ``numero_da_lampada``, que só conhece o primeiro ramo.
        """
        rank = self._ordem.get(key)
        if rank is None:
            return None
        numero = self._assentos_locked().get(key)
        if numero is not None:
            return numero
        presentes = [k for k in self._connected if k in self._ordem]
        presentes += self._guardados_locked()
        antes = sum(1 for k in presentes if self._ordem[k] < rank)
        antes += sum(1 for r in self._external_present_ranks_locked() if r < rank)
        return antes + 1

    def mark_disconnected(self, uniq: str | None) -> None:
        """Marca ``uniq`` desconectado — o LUGAR NA FILA fica com o MAC (D2)."""
        if not uniq or not isinstance(uniq, str):
            return
        key, _ = self._chave(uniq)
        with self._lock:
            self._avaliar_mesa_locked()
            if key in self._connected:
                self._connected.discard(key)
                self._mesa_mexeu_locked()
                self._guardar_o_lugar_locked(key)

    def sync_connected(self, uniqs: Iterable[str]) -> None:
        """Reconcilia com os uniqs CONECTADOS agora e ATRIBUI quem falta (~2s).

        - quem chegou SEM lugar entra no fim da fila, na ORDEM em que o
          chamador entrega (R-24 — ver abaixo), e entra também na FILA DO
          MOMENTO, todos os desta olhada na MESMA onda (D-30 — ver abaixo);
        - quem saiu do conjunto mantém o LUGAR (D2) e, pelo prazo do lugar
          guardado, também o assento: ninguém anda (O-ASSENTO-GUARDADO-NAO-
          ANDA-01). Passado o prazo, a exibição dos que ficaram fecha a lacuna
          sozinha (NUM-01 — a "compactação automática" não é um passo, é
          consequência de contar só os presentes);
        - persiste (atômico) quando o mapa mudou desde o último save. É o
          ÚNICO ponto de escrita em disco fora do ``load()`` — nunca no
          caminho quente por evento.

        R-15 (auditoria 23/07): o ramo de EXPIRAÇÃO por sessão esvaziada saiu
        daqui. Ele existia só deste lado (o registro dos externos nunca
        expirou nada), e a assimetria era medível: com os dois DualSense
        desligados, o primeiro a acordar levava o slot 1 — cor e número
        trocavam de dono. Renumerar por vontade dela é o ``compact`` do
        "Renumerar agora"; por schema novo, o ``load``.

        R-24 (auditoria 25/07) — por que ATRIBUIR aqui e não só no
        ``slot_for`` lazy: o lazy é do PROVIDER DE COR, que só roda no
        caminho de output do backend. Enquanto ele não rodava, o registro
        ficava vazio e o piso lido pelos externos (``_ds_reserve``) valia 0 —
        o Pro Nintendo USB tomava o slot 1 no primeiro tick de externo e os
        dois DualSense herdavam 2 e 3 (o "não existe Controle 1" medido
        na bancada). O lifecycle chama ESTE método ANTES de agendar o tick
        dos externos no MESMO ciclo do poll loop, então quem está na mesa
        ocupa 1..N primeiro. A ORDEM do iterável é significativa (o
        lifecycle entrega em ordem de ``describe_controllers``, primário
        primeiro) — nunca passar um ``set``, que numeraria por hash.

        D-30 (decisão, 15/08) — este método é o BATIMENTO da fila do
        momento, e faz três coisas novas, todas baratas:

        1. carimba a onda de chegada de quem entrou AGORA (quem já estava na
           mesa não é recarimbado — é isso que devolve o número a quem volta);
        2. reconhece que a mesa se mexeu quando a composição muda, o que
           reinicia a contagem de estabilidade;
        3. quando nada muda por :data:`JANELA_MESA_ESTAVEL_SEC`, CONGELA: a
           ordem do momento é gravada na fila persistida e este mesmo tick a
           leva ao disco. É o único ponto de escrita, como sempre foi.

        A ordem do iterável NÃO decide sozinha o número: quem chega na mesma
        olhada divide a onda, e o desempate ali é o GRAVADO. É por isso que
        reiniciar o daemon com quatro controles já ligados (todos vistos na
        mesma primeira olhada) não embaralha nada — R-23 continua de pé.
        """
        na_mesa = [u for u in uniqs if u and isinstance(u, str)]
        self.resolver_crachas(na_mesa)
        vivos: list[tuple[str, bool]] = []
        vistos: set[str] = set()
        crus_vivos = set(na_mesa)
        a_perguntar: list[tuple[str, str]] = []
        for uniq in na_mesa:
            key, persistable = self._chave(uniq)
            if not key or key in vistos:
                continue
            if persistable and key.startswith(_VPAD_MAC_PREFIX):
                continue
            vistos.add(key)
            vivos.append((key, persistable))
            if persistable:
                a_perguntar.append((key, uniq))
        with self._lock:
            self._esquecer_cracha_locked(crus_vivos)
            self._avaliar_mesa_locked()
            anteriores = self._connected
            donos_de_lugar = set(self._guardados_locked())
            self._connected = vistos
            if vistos != anteriores:
                self._mesa_mexeu_locked()
            for key in vistos - anteriores:
                self._entrou_na_mesa_locked(key)
            self._vencer_os_guardados_locked()
            chegou_gente_nova = any(
                key not in donos_de_lugar
                and self._entrada.get(key, 0) > self._entradas_no_ultimo_tique
                for key in vistos
            )
            if chegou_gente_nova:
                self._quem_chega_novo_refaz_a_mesa_locked()
            else:
                for key in anteriores - vistos:
                    self._guardar_o_lugar_locked(key)
            for key in vistos:
                self._retomar_o_lugar_locked(key)
            self._entradas_no_ultimo_tique = self._entradas
            for key, persistable in vivos:
                if key not in self._ordem:
                    self._assign_locked(key, persistable)
                if key not in anteriores:
                    self._marcar_chegada_locked(key)
            if self._dirty:
                self._save_locked()
                self._dirty = False
        if chegou_gente_nova:
            self._soltar_os_lugares_dos_externos()
        for key, uniq in a_perguntar:
            self._agendar_a_pergunta_de_fabrica(key, uniq)

    def armar_a_pergunta_de_fabrica(
        self, perguntar: Callable[[str], Any] | None
    ) -> None:
        """Arma (ou desarma, com None) quem pergunta o serial ao aparelho."""
        self._perguntar_a_fabrica = perguntar

    def avisar_quando_o_plastico_chegar(
        self, fn: Callable[[], object] | None
    ) -> None:
        """Pendura (ou tira, com None) quem converge a luz quando o plástico chega."""
        self._ao_chegar_o_plastico = fn

    @property
    def pergunta_de_fabrica_armada(self) -> bool:
        return self._perguntar_a_fabrica is not None

    def _agenda_de_fabrica(self) -> Any:
        agenda = self._agenda_da_fabrica
        if agenda is None:
            from hefesto_dualsense4unix.integrations.cor_do_plastico import (
                AgendaDaPergunta,
            )

            agenda = AgendaDaPergunta()
            self._agenda_da_fabrica = agenda
        return agenda

    def identidade_de_fabrica(self, uniq: str | None) -> Any:
        """A `IdentidadeDeFabrica` definitiva de `uniq`, ou None. Leitura pura."""
        if not uniq:
            return None
        key, _persistable = self._canonical(uniq)
        with self._lock:
            return self._fabrica.get(key)

    def tom_do_plastico(self, uniq: str) -> tuple[int, int, int] | None:
        """O tom de luz do plástico de `uniq`, sem I/O — None quando não se sabe."""
        achado = self.identidade_de_fabrica(uniq)
        if achado is None:
            return None
        from hefesto_dualsense4unix.integrations.cor_do_plastico import tom_da_luz

        return tom_da_luz(getattr(achado, "cor", None))

    def agendar_a_pergunta_de_fabrica(self, uniq: str) -> None:
        """Agenda a pergunta de `uniq` (o `state_full` chama; o tique também)."""
        key, persistable = self._canonical(uniq)
        if key and persistable:
            self._agendar_a_pergunta_de_fabrica(key, uniq)

    def _agendar_a_pergunta_de_fabrica(self, key: str, uniq: str) -> None:
        perguntar = self._perguntar_a_fabrica
        if perguntar is None:
            return
        with self._lock:
            if key in self._fabrica:
                return
        if not self._agenda_de_fabrica().reservar(key):
            return
        try:
            threading.Thread(
                target=self._perguntar_a_fabrica_agora,
                args=(perguntar, key, uniq),
                name=f"fabrica-{key[:6]}",
                daemon=True,
            ).start()
        except Exception:
            from hefesto_dualsense4unix.integrations.cor_do_plastico import (
                IdentidadeDeFabrica,
            )

            self._agenda_de_fabrica().registrar(
                key, IdentidadeDeFabrica(motivo="a thread não nasceu")
            )

    def _perguntar_a_fabrica_agora(
        self, perguntar: Callable[[str], Any], key: str, uniq: str
    ) -> None:
        """A leitura, fora do laço. Só a resposta definitiva entra no cache."""
        from hefesto_dualsense4unix.integrations.cor_do_plastico import (
            IdentidadeDeFabrica,
        )

        achado: Any = IdentidadeDeFabrica(motivo="a leitura não devolveu")
        try:
            achado = perguntar(uniq)
        except Exception as erro:
            achado = IdentidadeDeFabrica(
                motivo=f"a leitura levantou {type(erro).__name__}"
            )
        finally:
            if getattr(achado, "definitiva", False):
                with self._lock:
                    self._fabrica[key] = achado
                logger.info(
                    "plastico_do_controle_lido",
                    modelo=getattr(getattr(achado, "cor", None), "nome", None),
                )
            self._agenda_de_fabrica().registrar(key, achado)
        aviso = self._ao_chegar_o_plastico
        if aviso is not None and getattr(achado, "definitiva", False):
            from hefesto_dualsense4unix.integrations.cor_do_plastico import tom_da_luz

            if tom_da_luz(getattr(achado, "cor", None)) is not None:
                try:
                    aviso()
                except Exception as erro:
                    logger.warning("plastico_aviso_falhou", err=str(erro))

    def snapshot(self) -> dict[str, int]:
        """Cópia do mapa key→LUGAR NA FILA (presentes + ausentes). Leitura pura."""
        with self._lock:
            return dict(self._ordem)

    def present_ranks(self) -> set[int]:
        """Lugares da fila ocupados por controles PRESENTES agora (NUM-01)."""
        with self._lock:
            return {
                rank
                for key, rank in self._ordem.items()
                if key in self._connected
            }

    def lugares_da_mesa(self) -> set[int]:
        """Lugares da fila que CONTAM na mesa agora: os presentes e os guardados.

        O-ASSENTO-GUARDADO-NAO-ANDA-01: é isto, e não ``present_ranks``, que o
        registro dos externos conta — com um DualSense fora dentro do prazo, o
        externo que vem depois dele também não anda. ``present_ranks`` segue
        dizendo só quem está ligado.
        """
        with self._lock:
            chaves = [*self._connected, *self._guardados_locked()]
            return {self._ordem[k] for k in chaves if k in self._ordem}

    def snapshot_connected(self) -> set[str]:
        """Keys CONECTADAS agora (subconjunto de ``snapshot()``). Leitura pura."""
        with self._lock:
            return set(self._connected)

    def lock_for_renumber(self) -> threading.RLock:
        """Expõe o `RLock` de instância — SÓ para `identity.renumber` (fix TOCTOU)."""
        return self._lock

    def compact(self, mapping: dict[str, int]) -> None:
        """Reordena a FILA conforme ``mapping`` (``identity.renumber``, ONDA-U).

        Distinta da atribuição LAZY de ``slot_for``: é uma reescrita
        EXPLÍCITA, disparada só pelo handler IPC (gate de sessão vazia é
        responsabilidade do CHAMADOR — este método não sabe de
        ``display_authority``). Só reescreve chaves que já existem NESTE
        registro — o chamador monta ``mapping`` a partir de um ``snapshot()``
        deste mesmo objeto (a reordenação é GLOBAL entre DualSense e externos,
        cada registro aplica só a fatia que é dele). Não mexe em
        presença/voláteis (``_volatile`` continua intocado — ``_save_locked``
        já filtra por ele). Persiste sob ``CONTROLLERS_FILE_LOCK`` via
        ``_save_locked`` (mesmo NUMA-04 do save do tick lento) quando algo de
        fato mudou.

        NUM-01: os valores de ``mapping`` são LUGARES NA FILA, não números
        exibidos. Escrever aqui não repinta ninguém sozinho — muda a ordem de
        quem exibe o quê quando estiver na mesa.

        D-30 estreitou o alcance deste gesto e a nota fica aqui para a E3 não
        reaprender: com a exibição saindo da FILA DO MOMENTO, reescrever o
        gravado mexe no DESEMPATE (quem chegou junto) e no que atravessa o
        restart — não na ordem de quem a casa viu chegar em momentos
        diferentes. A fila do momento NÃO é tocada aqui de propósito: um
        gesto que a apagasse mandaria todo mundo para o fim da fila no
        replug seguinte, que é o defeito de ORDEM DE WAKE de R-15. O que o
        botão "Renumerar agora" deve significar depois de D-30 é decisão da
        E3, não desta função.

        O-ASSENTO-GUARDADO-NAO-ANDA-01: renumerar é fechar a fila agora, por
        vontade dela — o lugar guardado não sobrevive ao gesto.
        """
        self.soltar_os_lugares_guardados()
        with self._lock:
            changed = False
            for key, novo_rank in mapping.items():
                if key in self._ordem and self._ordem[key] != novo_rank:
                    self._ordem[key] = novo_rank
                    changed = True
            if changed:
                self._dirty = True
                self._save_locked()
                self._dirty = False


    def alinhar_gravado_com_a_tela(self) -> bool:
        """Grava a fila do momento AGORA, sem esperar a janela de estabilidade.

        Existe para UM chamador — ``identity.number.set``, a escolha à mão —
        e a razão é que o clique do usuário é sobre **o que ela está vendo**. Quem
        planeja a troca lê os lugares GRAVADOS (``snapshot``); quem pinta a
        tela lê a FILA DO MOMENTO (``_ordem_do_momento_locked``). Enquanto os
        dois discordam, o plano é calculado sobre uma mesa que não é a da
        tela — e foi assim que o comando devolvia ``{"ok": true, "changed":
        {}}`` sem mover nada.

        MEDIDO em 29/08/2026, dois DualSense, o gravado dizendo ``A=1, B=2``
        e ela ligando o **B** primeiro (a tela mostra ``B=1, A=2``): pedir o
        1 para o A devolvia ``changed={}`` e a tela não se mexia. Com o
        alinhamento antes do plano, o mesmo gesto move os dois.

        Não é gesto novo nem regra nova: é o MESMO
        :meth:`_congelar_locked` que a mesa estável dispara sozinha 4,0 s
        depois (D-30) — só que adiantado para o instante do clique. A regra
        automática de quem vira jogador 1 quando os controles chegam fica
        INTACTA; o que muda é só o momento em que ela é gravada.

        Devolve ``True`` quando algo mudou de lugar.

        O-ASSENTO-GUARDADO-NAO-ANDA-01: o que ela vê tem o BURACO de quem
        saiu dentro do prazo — o P3 continua 3 com o P2 fora —, então o lugar
        guardado entra no alinhamento e NÃO se solta. Soltá-lo (a primeira
        escrita desta sprint) fechava a fila no instante do clique, e a troca
        saía sobre outra mesa: pedir o 3 para o P4 mandava o P3 para o 2, e
        não para o 4 — contra a regra de 28/08, *"os dois trocam, os
        outros não se mexem"* —, e o 4 que a aba oferecia era recusado como
        fora da mesa. Conferência de 24/09/2026.
        """
        with self._lock:
            antes = dict(self._ordem)
            self._congelar_locked(
                [k for k in self._connected if k in self._ordem]
                + self._guardados_locked()
            )
            if self._ordem == antes:
                return False
            self._save_locked()
            self._dirty = False
            return True

    def escolha_da_mao(self, ranks: dict[str, int]) -> None:
        """Aplica a escolha do usuário — e a fila do momento passa a concordar.

        A forma é a que ela já fixou para o microfone
        (``D-O-MICROFONE-A-MAQUINA-DA-O-PADRAO-O-PERFIL-SOBREPOE``): **a
        máquina dá o padrão, a escolha sobrepõe.** Aqui o padrão é a ordem de
        chegada (D-30), que continua decidindo quem nasce jogador 1; o que
        esta função faz é deixar a escolha à mão VALER por cima dela.

        Por que ``compact`` não serve, e a própria docstring dele já dizia:
        *"a fila do momento NÃO é tocada aqui de propósito"*. Escrever só o
        ``rank`` mexe no DESEMPATE de quem chegou junto — e nada mais. Com os
        controles chegando em ondas diferentes (ligar um por um, o caso
        normal dela), a exibição é decidida pela ONDA, o ``rank`` nem é
        consultado, e a escolha ficava invisível. Pior: 4,0 s depois o
        :meth:`_congelar_locked` reescrevia os ``rank`` a partir das ondas e
        **apagava a escolha da memória e do disco**.

        MEDIDO em 29/08/2026, três DualSense ligados um a um, pedindo o 1
        para o último::

            rank gravado depois do comando : {A: 2, B: 3, C: 1}
            NA TELA                        : {A: 1, B: 2, C: 3}   <- não mexeu
            rank depois do congelamento    : {A: 1, B: 2, C: 3}   <- apagou

        **A cura, e ela é uma permutação:** as ONDAS que os presentes já
        detêm são redistribuídas ENTRE ELES, na ordem dos lugares novos —
        exatamente o que :meth:`_congelar_locked` faz com os ``postos``, no
        sentido inverso. O conjunto de ondas não muda, então nenhuma onda é
        inventada e quem conectar DEPOIS continua caindo no fim da fila (a
        onda dele é maior que todas).

        **Por que isso basta, e a prova é de ordenação, não de teste:** o
        chamador entrega ``ranks`` estritamente crescentes na ordem desejada
        (ele redistribui os MESMOS lugares, ordenados). Redistribuir as ondas
        ordenadas na mesma sequência deixa a onda NÃO-DECRESCENTE nessa
        ordem. Logo a chave ``(onda, rank)`` de
        :meth:`_ordem_do_momento_locked` é estritamente crescente na ordem
        desejada — e ordenar por ela devolve exatamente essa ordem. O
        congelamento seguinte encontra ``_ordem`` já igual à fila do momento
        e não escreve nada: **a escolha sobrevive ao tempo**, que é o que os
        testes verdes de antes não viam (nenhum deles injetava relógio).

        Ausente não é tocado (só os presentes entram na redistribuição), e o
        replug devolve a onda que a escolha deu — ``mark_disconnected``
        preserva a marca de chegada de propósito (D2/R-15). A exceção é o
        LUGAR GUARDADO (O-ASSENTO-GUARDADO-NAO-ANDA-01): ele é parte da mesa
        que ela vê, a troca pode ser com ele, e sem a onda junto a exibição o
        poria de volta onde estava.
        """
        with self._lock:
            changed = False
            for key, novo_rank in ranks.items():
                if key in self._ordem and self._ordem[key] != novo_rank:
                    self._ordem[key] = novo_rank
                    changed = True
            presentes = [
                k
                for k in [*self._connected, *self._guardados_locked()]
                if k in self._ordem and k in self._chegada
            ]
            if len(presentes) >= 2:
                ondas = sorted(self._chegada[k] for k in presentes)
                for key, onda in zip(
                    sorted(presentes, key=lambda k: self._ordem[k]),
                    ondas,
                    strict=True,
                ):
                    if self._chegada[key] != onda:
                        self._chegada[key] = onda
                        changed = True
            if not changed:
                return
            logger.info(
                "identity_escolha_da_mao",
                ordem={k: self._ordem[k] for k in presentes},
                chegada={k: self._chegada[k] for k in presentes},
            )
            self._dirty = True
            self._save_locked()
            self._dirty = False


    def load(self) -> None:
        """Carrega ``controllers.json`` — a FILA ATRAVESSA o boot (R-23/NUM-01)."""
        with self._lock:
            if self._loaded:
                return
            self._loaded = True
            with CONTROLLERS_FILE_LOCK:
                try:
                    data = json.loads(self._path().read_text(encoding="utf-8"))
                except (FileNotFoundError, json.JSONDecodeError, OSError):
                    return
                except Exception as exc:
                    logger.debug("identity_load_falhou", err=str(exc))
                    return
            if not isinstance(data, dict):
                return
            if data.get("version") != CONTROLLERS_SCHEMA_VERSION:
                # sempre, agora que nada mais expira. NUM-01 é exatamente um
                logger.info(
                    "identity_arquivo_de_schema_antigo_descartado",
                    versao_arquivo=data.get("version"),
                    versao_atual=CONTROLLERS_SCHEMA_VERSION,
                )
                return
            entradas = [
                (addr, rank)
                for addr, kind, rank in order_entries(data)
                if kind == KIND_DUALSENSE
            ]
            if not entradas:
                return
            anchor = _session_anchor()
            if anchor is not None and data.get("boot_id") != anchor:
                logger.info(
                    "identity_slots_restaurados_de_outro_boot",
                    arquivo_boot=data.get("boot_id"),
                )
            usados: set[int] = set()
            for raw_key, raw_rank in entradas:
                key, persistable = self._canonical(raw_key)
                if not persistable or key.startswith(_VPAD_MAC_PREFIX):
                    continue
                if key in self._ordem or raw_rank in usados:
                    continue
                if len(self._ordem) >= _MAX_PERSISTED_SLOTS:
                    logger.warning(
                        "identity_slots_truncados", teto=_MAX_PERSISTED_SLOTS
                    )
                    break
                self._ordem[key] = raw_rank
                usados.add(raw_rank)
            if self._ordem:
                logger.info("identity_fila_restaurada", ordem=dict(self._ordem))

    @staticmethod
    def _path() -> Path:
        """Path do ``controllers.json`` — import LAZY do ``config_dir``."""
        from hefesto_dualsense4unix.utils.xdg_paths import config_dir

        return config_dir(ensure=True) / _CONTROLLERS_FILE

    def _save_locked(self) -> None:
        """Grava a fila persistível (atômico: mkstemp + os.replace). Sob lock."""
        try:
            with CONTROLLERS_FILE_LOCK:
                path = self._path()
                existente: Any = None
                with contextlib.suppress(Exception):
                    bruto = json.loads(path.read_text(encoding="utf-8"))
                    if (
                        isinstance(bruto, dict)
                        and bruto.get("version") == CONTROLLERS_SCHEMA_VERSION
                    ):
                        existente = bruto
                payload: dict[str, Any] = {}
                payload["version"] = CONTROLLERS_SCHEMA_VERSION
                payload["boot_id"] = _session_anchor()
                payload[ORDER_FIELD] = merged_order_payload(
                    existente,
                    KIND_DUALSENSE,
                    {
                        key: rank
                        for key, rank in self._ordem.items()
                        if key not in self._volatile
                    },
                )
                data = json.dumps(payload, ensure_ascii=False)
                fd, tmp = tempfile.mkstemp(
                    dir=os.path.dirname(os.fspath(path)), prefix=".controllers_"
                )
                try:
                    os.write(fd, data.encode())
                finally:
                    os.close(fd)
                os.replace(tmp, path)
                logger.debug("identity_fila_salva", ordem=payload[ORDER_FIELD])
        except Exception as exc:
            logger.debug("identity_save_falhou", err=str(exc))


    def o_lugar_espera(self, uniq: str | None) -> bool:
        """O lugar de ``uniq`` ainda está na mesa? — ligado, ou guardado no prazo."""
        if not uniq or not isinstance(uniq, str):
            return False
        key, _persistable = self._chave(uniq)
        if not key:
            return False
        with self._lock:
            if key not in self._ordem:
                return False
            return key in self._connected or key in self._guardados_locked()

    def posto_na_fila(self, uniq: str | None) -> int | None:
        """O lugar GRAVADO de ``uniq`` na fila — ou None. Leitura pura."""
        if not uniq or not isinstance(uniq, str):
            return None
        key, persistable = self._chave(uniq)
        if not key or (persistable and key.startswith(_VPAD_MAC_PREFIX)):
            return None
        with self._lock:
            return self._ordem.get(key)


def make_auto_output_provider(
    registry: ControllerIdentityRegistry,
) -> Callable[[str], _DesiredOutput | None]:
    """Provider de cor automática por controle para o backend (COR-03).

    Injetado via ``PyDualSenseController.set_auto_output_provider`` na fiação
    do daemon. O backend o chama em ``_merged_desired_for_key`` — SOB o
    ``_io_lock``, portanto ele é barato e sem I/O de disco (o ``slot_for``
    lazy só toca memória; a persistência fica com o ``sync_connected``).

    Devolve um ``_DesiredOutput`` com ``led`` (cor do slot, escalada pelo
    brilho vigente — D11, pelo MESMO caminho do global:
    ``LedSettings.apply_brightness``) e/ou ``player_leds`` (padrão canônico
    do NÚMERO DO CONTROLE — D7). ``None`` = sem opinião (uniq sem slot,
    vpad, ou os DOIS eixos do automático desligados) → o merge cai no default
    global (comportamento histórico, D5).

    R-14 (auditoria 23/07), duas mudanças de ordem/granularidade:

    1. ``slot_for`` roda ANTES de qualquer teste de flag — ATRIBUIR número é
       identidade, não aparência. Com o early-return antigo, um perfil com
       ``auto_player_colors:false`` deixava o DualSense sem entrada no
       registro, e o piso que os externos leem (``_ds_reserve``) passava a
       mentir: o 8BitDo ganhava um número que outro controle já exibia.
    2. Os campos saem SEPARADOS: cor sob ``auto_enabled``, padrão de número
       sob ``auto_numbers_enabled``. Desligar a paleta não pode apagar o
       número do controle.

    Os dois escritores de ``_connected`` — QUATRO-NA-MESA-01, defeito 1
    (medido em 06/09/2026, com quatro endereços na mesa):

      ``_connected`` decide QUEM CONTA para a numeração 1..N
      (:meth:`_numeros_da_mesa_locked`), e até aqui tinha DOIS escritores em
      cadências diferentes:

      - o **tique lento** (:meth:`sync_connected`, ~2,0 s pelo ``lifecycle``)
        SUBSTITUI o conjunto inteiro pelo que o backend reporta conectado;
      - a **leitura de cor** (:func:`make_auto_output_provider` →
        :meth:`numero_da_lampada` → :meth:`slot_for`) ADICIONAVA — e ela roda a
        **10 Hz** enquanto a aba Status está aberta.

      A janela é exatamente a de um controle que piscou no Bluetooth: o tique o
      tira da mesa, e a leitura o devolve dez vezes por segundo até o próximo
      tique tirá-lo de novo. **Medido antes da cura**, com quatro endereços e o
      terceiro ausente: o quarto ia de ``3`` para ``4`` e a lightbar dele de
      verde para rosa a cada leitura — *"quando um controle pisca, os outros
      trocam de cor e de número sozinhos"*.

      A cura NÃO é chamar :meth:`mark_disconnected` (ele está sem chamador de
      produção **de propósito** — R-15/D2, o lugar na fila sobrevive ao
      disconnect). O defeito é ``_connected`` ser escrito por uma LEITURA: uma
      consulta de cor não pode ter efeito colateral sobre quem está na mesa.
      ``slot_for(autoridade_de_presenca=False)`` é o que separa os dois atos — o
      provider continua ATRIBUINDO lugar (R-14 §1) e continua apresentando um
      endereço que ESTREIA (D1: a cor nasce certa no tique do hotplug), mas quem
      RESSUSCITA um ausente passa a ser só o tique.
    """
    from hefesto_dualsense4unix.core.backend_pydualsense import _DesiredOutput
    from hefesto_dualsense4unix.core.led_control import (
        LedSettings,
        cor_automatica,
        player_led_pattern,
        player_slot_color,
    )
    from hefesto_dualsense4unix.integrations import cor_do_plastico

    registry.armar_a_pergunta_de_fabrica(
        lambda uniq: cor_do_plastico.ler_identidade_pelo_cabo(uniq)
    )

    def provider(uniq: str) -> _DesiredOutput | None:
        slot = registry.numero_da_lampada(uniq, autoridade_de_presenca=False)
        if slot is None:
            return None
        campos: dict[str, Any] = {}
        if registry.auto_enabled:
            brilho = registry.auto_brightness
            settings = LedSettings(
                lightbar=cor_automatica(slot, registry.tom_do_plastico(uniq)),
                brightness_level=brilho,
            )
            campos["led"] = settings.apply_brightness(brilho).lightbar
        if registry.auto_numbers_enabled:
            campos["player_leds"] = player_led_pattern(slot)
        if not campos:
            return None
        return _DesiredOutput(**campos)

    def numero_do_slot(uniq: str) -> int | None:
        """O NÚMERO de `uniq` agora — a companheira do provider de cor."""
        return registry.numero_da_lampada(uniq, autoridade_de_presenca=False)

    def uniqs_da_mesa() -> list[str]:
        """QUEM está na mesa agora — a segunda companheira do provider de cor."""
        return list(registry.numeros_da_mesa())

    def cor_do_numero(uniq: str) -> tuple[int, int, int] | None:
        """A cor do NÚMERO de `uniq`, no brilho do perfil — a queda do plástico."""
        slot = registry.numero_da_lampada(uniq, autoridade_de_presenca=False)
        if slot is None or not registry.auto_enabled:
            return None
        brilho = registry.auto_brightness
        return LedSettings(lightbar=player_slot_color(slot)).apply_brightness(
            brilho
        ).lightbar

    provider.numero_do_slot = numero_do_slot  # type: ignore[attr-defined]
    provider.uniqs_da_mesa = uniqs_da_mesa  # type: ignore[attr-defined]
    provider.tom_do_plastico = registry.tom_do_plastico  # type: ignore[attr-defined]
    provider.avisar_quando_a_automatica_mudar = (  # type: ignore[attr-defined]
        registry.avisar_quando_o_plastico_chegar
    )
    provider.cor_do_numero = cor_do_numero  # type: ignore[attr-defined]
    provider.posto_na_fila = registry.posto_na_fila  # type: ignore[attr-defined]
    return provider


_registry: ControllerIdentityRegistry | None = None
_registry_lock = threading.Lock()


def get_identity_registry() -> ControllerIdentityRegistry:
    """Registro de identidade do processo (singleton, criado sob demanda)."""
    global _registry
    with _registry_lock:
        if _registry is None:
            _registry = ControllerIdentityRegistry()
        return _registry


def reset_identity_registry() -> None:
    """Descarta o singleton (APENAS testes — isola estado entre casos)."""
    global _registry
    with _registry_lock:
        _registry = None


def relogio_do_lugar_guardado() -> float:
    """O relógio do lugar guardado — o MESMO do posto de primário.

    O-ASSENTO-GUARDADO-NAO-ANDA-02. Não é um segundo relógio: pergunta ao dono,
    ``core.backend_pydualsense.relogio_do_prazo`` (o ``CLOCK_BOOTTIME``, que
    anda enquanto a máquina dorme), pelo mesmo import tardio de
    :func:`prazo_do_lugar_guardado`. É o relógio padrão dos dois registros (o
    dos DualSense e o dos externos), e por isso o prazo de um controle que saiu
    antes de a máquina suspender vence junto com o posto de primário, contando o
    tempo em que ela dormiu.

    Mora no fim do módulo porque o mapa de canais cita este arquivo por linha.
    """
    from hefesto_dualsense4unix.core.backend_pydualsense import relogio_do_prazo

    return relogio_do_prazo()


__all__ = [
    "CONTROLLERS_FILE_LOCK",
    "CONTROLLERS_SCHEMA_VERSION",
    "JANELA_DE_ONDA_SEC",
    "JANELA_MESA_ESTAVEL_SEC",
    "KIND_DUALSENSE",
    "KIND_EXTERNAL",
    "ORDER_FIELD",
    "ControllerIdentityRegistry",
    "get_identity_registry",
    "make_auto_output_provider",
    "merged_order_payload",
    "order_entries",
    "reset_identity_registry",
]

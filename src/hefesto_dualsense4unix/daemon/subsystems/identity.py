"""Registro de identidade MAC→slot de SESSÃO (COR-01, sprint cores-e-led).

O "Controle N" que a usuária vê (rótulos, cor automática da lightbar, LED do
número do controle) era a POSIÇÃO no dict de handles do backend (+1) — replug
reinsere no fim e o número embaralhava. Este registro dá a cada DualSense um
slot ESTÁVEL DE SESSÃO, keyed pelo MAC normalizado (12 hex — o mesmo
``norm_mac`` do backend, estável entre USB e BT):

- 1ª aparição de um MAC → MENOR slot livre (1..N), atribuição LAZY na
  primeira consulta (``slot_for``) — é isto que faz a cor automática nascer
  certa no MESMO tick de hotplug em que o backend abre o handle (D1);
- desconectar RESERVA o slot ao MAC dentro da sessão — replug recupera o
  mesmo número (D2). Sem roubo LRU (cortado: YAGNI);
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
  slot a todo DualSense conectado que ainda não tem — quem está na mesa
  ocupa 1..N antes de qualquer externo pedir número;
- o vpad (MAC forjado ``02:fe:...``) NUNCA ganha slot (D9) — o filtro
  existe aqui além do filtro de enumeração do backend, porque outros
  chamadores (describe/co-op) também consultam;
- key sem MAC 12-hex (fallback ``path:...`` de firmware sem serial) ganha
  slot VOLÁTIL: vale na sessão, nunca é persistido (D9 — path muda entre
  boots);
- DualSense-only (D10) é garantido pelo CHAMADOR por construção: os uniqs
  que chegam aqui vêm dos handles físicos do backend (a enumeração filtra
  por VID/PID da Sony e descarta hidraw virtual). O registro não conhece
  hardware — só strings.

Separação D3 (Refutado 2 do sprint): este slot é EXIBIÇÃO/LED. O índice de
alocação do vpad do co-op (``_next_player_index`` + ``player=1`` do
primário) fica intacto — slot repetido no MAC do vpad uhid mataria o probe
com ``-EEXIST`` e degradaria o co-op em silêncio. R-24 precisou o limite: o
índice do vpad é do JOGO (contíguo, reusado quando alguém sai) e o slot
daqui é da EXIBIÇÃO; o que era defeito é que a LÂMPADA acendia o primeiro.
Hoje ``CoopManager._numero_exibido`` lê ESTE registro para a barra de player
e o índice do vpad nunca mais chega a um LED.

Persistência (``controllers.json`` no config do app, escrita atômica
mkstemp+os.replace — padrão ``utils/session.py``): cobre o restart do daemon
E o reboot da máquina (R-23). O que governa o load é o
:data:`CONTROLLERS_SCHEMA_VERSION` do arquivo, não mais o ``boot_id``:

- versão IGUAL → o mapa MAC→slot é restaurado INTEIRO. Entradas voláteis
  (sem MAC 12-hex) nunca chegam ao disco (D9), então "descartar o volátil"
  é invariante do save, não trabalho do load;
- versão DIFERENTE/ausente → arquivo escrito por uma versão que numerava
  por outra regra; é descartado UMA vez e a sessão seguinte renumera. É o
  que cura, sozinha, a numeração torta já gravada na máquina dela (o
  externo segurando o slot 1 enquanto os dois DualSense exibiam 2 e 3);
- o ``boot_id`` continua GRAVADO, agora como âncora de diagnóstico
  (:func:`_session_anchor`, resiliente: boot_id → machine-id → ``None``).
  Ele não pode mais decidir nada sozinho — foi exatamente a fragilidade
  que renumerava tudo onde ``/proc/sys/kernel/random/boot_id`` não existe.

O ``config_dir`` é importado LAZY dentro das funções de I/O — preserva
o ponto de monkeypatch dos testes (``xdg_paths.config_dir``), padrão
``save_active_marker``. O arquivo é COMPARTILHADO com o registro dos
externos (``external_identity.py``, namespace ``externals``): ``load`` e
``_save_locked`` dos DOIS lados adquirem o mesmo ``CONTROLLERS_FILE_LOCK``
(NUMA-04) em volta do read→``os.replace`` — fecha o lost-update dos dois
escritores independentes sem unificar os dois registros.

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

#: Arquivo de persistência (no ``config_dir`` do app — padrão ``session.json``).
_CONTROLLERS_FILE = "controllers.json"

#: R-23: versão do SCHEMA de ``controllers.json``. É o que decide se o mapa
#: gravado ainda vale — o ``boot_id`` deixou de decidir (ver docstring). Bump
#: OBRIGATÓRIO sempre que a REGRA de numeração mudar: um arquivo de versão
#: diferente é descartado UMA vez e a sessão seguinte renumera com a regra
#: nova. Sem isso, a numeração torta gravada pela versão anterior (na máquina
#: dela: externo com o slot 1, DualSense em 2 e 3) sobreviveria para sempre,
#: justamente porque agora o mapa NÃO morre mais no reboot.
#: 2 = R-23/R-24 (slot sobrevive ao boot + espaço de numeração único).
CONTROLLERS_SCHEMA_VERSION = 2

#: R-23: teto defensivo de entradas restauradas do disco. Como nada expira
#: mais (nem no reboot), um casal que passe anos trocando de controle veria o
#: arquivo crescer sem fim e a numeração começar cada vez mais alto. 16 é
#: ordens de magnitude acima de qualquer setup real (4 no co-op + externos);
#: acima disso, as entradas de slot MAIS ALTO caem (são as menos
#: estabelecidas — quem tem slot baixo é quem a casa usa).
_MAX_PERSISTED_SLOTS = 16

#: R-23: fallbacks da âncora de sessão quando ``/proc`` não está montado
#: (contêiner/Flatpak). machine-id não é por-boot, e tudo bem: depois do R-23
#: a âncora é DIAGNÓSTICO, não gate — só precisa ser estável e barata.
_MACHINE_ID_PATHS = ("/etc/machine-id", "/var/lib/dbus/machine-id")

#: MAC "de verdade": 12 dígitos hex, com ou sem separadores ``:``/``-``.
#: Mais estrito que o ``norm_mac`` do backend de propósito: um PATH exótico
#: pode conter 12 chars hex espalhados e viraria um pseudo-MAC persistível.
_MAC_RE = re.compile(
    r"^(?:[0-9a-fA-F]{12}|(?:[0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2})$"
)

#: Prefixo (canônico, 12-hex) dos MACs forjados dos vpads uhid — D9.
_VPAD_MAC_PREFIX = "02fe"

#: Lock de MÓDULO (NUMA-04, sprint 2026-07-19): protege TODO acesso
#: read→``os.replace`` ao ``controllers.json`` COMPARTILHADO pelos dois
#: registros independentes — este (namespace ``slots``) e o dos externos
#: (``external_identity.py``, namespace ``externals``). Cada registro tinha
#: só o próprio ``RLock`` de INSTÂNCIA, que não protege contra o OUTRO objeto
#: fazendo read-modify-write ao MESMO tempo — um lost-update latente (um dos
#: dois namespaces podia sumir quando o tick do externo e o sync do DualSense
#: salvavam intercalados). ``external_identity.py`` IMPORTA e usa este MESMO
#: Lock — nunca cria o seu. Um `threading.Lock` de PROCESSO basta (o daemon é
#: singleton); `flock` inter-processo foi avaliado e REJEITADO como
#: sobre-engenharia (não há dois processos daemon concorrentes a proteger).
CONTROLLERS_FILE_LOCK = threading.Lock()


def _read_boot_id() -> str | None:
    """boot_id do kernel — identifica ESTE boot da máquina (None se ilegível).

    R-23: NÃO é mais um gate. Depois que o mapa MAC→slot passou a sobreviver
    ao reboot, o boot_id só ANOTA em que boot o arquivo foi escrito (útil no
    log de diagnóstico). Monkeypatchável nos testes.
    """
    try:
        with open("/proc/sys/kernel/random/boot_id", encoding="utf-8") as fh:
            value = fh.read().strip()
        return value or None
    except OSError:
        return None


def _read_machine_id() -> str | None:
    """machine-id do host (None se ilegível) — 2º degrau da âncora (R-23).

    Compartilhado com ``external_identity._session_anchor``: os dois
    registros escrevem o MESMO ``controllers.json`` e não podem discordar do
    valor do campo ``boot_id`` (um sobrescreveria o do outro a cada save).
    """
    for caminho in _MACHINE_ID_PATHS:
        try:
            with open(caminho, encoding="utf-8") as fh:
                bruto = fh.read().strip()
        except OSError:
            continue
        if bruto:
            return bruto
    return None


def _session_anchor() -> str | None:
    """Âncora de sessão RESILIENTE: boot_id → machine-id → ``None`` (R-23).

    A âncora antiga era só o ``_read_boot_id``, e ela FALHAVA FECHADA: sem
    ``/proc/sys/kernel/random/boot_id`` (contêiner/Flatpak, ``/proc`` não
    montado) o ``load`` abortava e a numeração inteira renascia — bastava
    reiniciar o daemon para os controles trocarem de número. Aqui a ausência
    degrada em CASCATA e, no pior caso, devolve ``None`` sem nenhuma
    consequência: quem decide o que restaurar é o
    :data:`CONTROLLERS_SCHEMA_VERSION`, não a âncora.

    Nunca levanta (todo caminho de I/O é ``OSError``-safe).
    """
    valor = _read_boot_id()
    if valor:
        return valor
    machine_id = _read_machine_id()
    # Prefixado para nunca ser confundido com um boot_id de verdade num
    # arquivo antigo (e para o log dizer de onde veio).
    return f"machine:{machine_id}" if machine_id else None


class ControllerIdentityRegistry:
    """MAC normalizado → slot de exibição (1..N), com reserva de SESSÃO (D2).

    Thread-safe (RLock próprio): o provider de cor consulta ``slot_for`` sob
    o ``_io_lock`` do backend (thread do executor) enquanto ``sync_connected``
    roda no event loop. Nenhum método faz I/O de disco EXCETO ``load()``
    (chamado uma vez na fiação do daemon, fora do caminho quente) e o save
    interno do ``sync_connected`` (tick lento ~2s, só quando algo mudou) —
    ``slot_for`` apenas marca o estado como sujo (o provider roda sob o
    ``_io_lock`` do backend e DEVE ser barato, sem I/O).
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        #: key canônica (MAC 12-hex, ou a key volátil crua) → slot. Contém
        #: conectados E reservados — a reserva É a permanência aqui (D2).
        self._slots: dict[str, int] = {}
        #: keys de slots VOLÁTEIS (sem MAC 12-hex) — nunca persistidas (D9).
        self._volatile: set[str] = set()
        #: keys atualmente conectadas (subset das que reportaram presença).
        #: R-15: lido por ``snapshot_connected`` (o "Renumerar agora" compacta
        #: os CONECTADOS em 1..N e só depois anexa as reservas offline) —
        #: antes era escrito e nunca lido.
        self._connected: set[str] = set()
        #: mapa mudou desde o último save (o sync persiste no tick lento).
        self._dirty = False
        self._loaded = False
        #: vpads já logados (evita spam — o provider consulta a cada reassert).
        self._vpad_logged: set[str] = set()
        #: provider OPCIONAL dos slots já reservados pelos EXTERNOS (EXT-04):
        #: o espaço de numeração é ÚNICO entre DualSense e externos, então a
        #: atribuição une essas reservas ao ``used`` — um DualSense que entra
        #: DEPOIS de um externo numerado pula o slot dele. None (não fiado /
        #: FakeController) = comportamento histórico, hermético.
        self._extra_reserved: Callable[[], set[int]] | None = None
        # -- estado do automático (COR-03, configurado pelo ProfileManager) --
        # R-14: dois eixos INDEPENDENTES (ver docstring do módulo). Cor é o
        # campo antigo do perfil; numeração nasce ligada e não tem campo no
        # schema ainda — quem quiser desligá-la usa ``configure(numbers=…)``.
        self._auto_colors = True
        self._auto_numbers = True
        self._auto_brightness = 1.0

    # ------------------------------------------------------------------
    # Config do automático (COR-03 / D11)
    # ------------------------------------------------------------------

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
        """True quando as cores automáticas por controle estão ligadas.

        Nome histórico (``auto_player_colors``) mantido: é o que o resto do
        código e os testes leem. Depois de R-14 ele significa exatamente o
        eixo COR — para a numeração existe ``auto_numbers_enabled``.
        """
        with self._lock:
            return self._auto_colors

    @property
    def auto_numbers_enabled(self) -> bool:
        """True quando a NUMERAÇÃO automática (player-LED) está ligada (R-14).

        Independente da cor: desligar a paleta não pode apagar o número do
        controle nem congelar a numeração dos externos — era exatamente o que
        acontecia com o flag único ("dois player 1, dois player 2").
        """
        with self._lock:
            return self._auto_numbers

    @property
    def auto_brightness(self) -> float:
        """Brilho vigente [0.0, 1.0] que escala a cor automática (D11)."""
        with self._lock:
            return self._auto_brightness

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    @staticmethod
    def _canonical(uniq: str) -> tuple[str, bool]:
        """Devolve ``(key, persistível)`` — MAC 12-hex canônico ou key volátil.

        Persistível = a string INTEIRA parece um MAC (12 hex, com ou sem
        ``:``/``-``). Qualquer outra coisa (``path:...``, node de device) é
        identidade VOLÁTIL de sessão — vale para numerar, nunca para gravar
        em disco (D9: path muda entre boots).
        """
        value = uniq.strip()
        if _MAC_RE.match(value):
            return value.lower().replace(":", "").replace("-", ""), True
        return value, False

    def set_external_reserve_provider(
        self, provider: Callable[[], set[int]] | None
    ) -> None:
        """Injeta o provider dos slots já detidos pelos EXTERNOS (EXT-04).

        A numeração global é um espaço ÚNICO: os externos já leem o piso dos
        DualSense (``reserve``) ao numerar; este provider fecha o laço no
        sentido inverso — a atribuição de um DualSense NOVO une os slots
        reservados pelos externos ao ``used``, para não colidir com um externo
        que numerou antes. Fiado por ``lifecycle._wire_external_registry`` só
        no backend real; ``None`` (FakeController) preserva o comportamento
        histórico. NÃO renumera quem já tem slot — só evita colisões NOVAS.
        """
        with self._lock:
            self._extra_reserved = provider

    def slot_for(self, uniq: str | None, *, assign: bool = True) -> int | None:
        """Slot do controle ``uniq`` — atribui o MENOR livre na 1ª consulta.

        LAZY por decisão (D1): a primeira consulta de um uniq válido (feita
        pelo provider de cor dentro do reconcile do backend, ou por quem
        rotula) é o que atribui o slot — a cor/número nascem certos no MESMO
        tick de hotplug. ``assign=False`` só consulta (leitura pura: não
        atribui, não marca conectado).

        Guardas: ``None``/vazio → None; MAC de vpad (``02:fe:...``) → None
        com log (D9 — o vpad jamais é "Controle N"). SEM I/O de disco — o
        provider roda sob o ``_io_lock`` do backend; a persistência fica com
        o ``sync_connected`` (tick lento).
        """
        if not uniq or not isinstance(uniq, str):
            return None
        key, persistable = self._canonical(uniq)
        if not key:
            return None
        if key.startswith(_VPAD_MAC_PREFIX) and persistable:
            with self._lock:
                if key not in self._vpad_logged:
                    self._vpad_logged.add(key)
                    logger.warning("identity_slot_vpad_ignorado", uniq=key)
            return None
        with self._lock:
            slot = self._slots.get(key)
            if slot is not None:
                if assign:
                    self._connected.add(key)
                return slot
            if not assign:
                return None
            slot = self._assign_locked(key, persistable)
            self._connected.add(key)
            return slot

    def _assign_locked(self, key: str, persistable: bool) -> int:
        """MENOR slot livre para ``key`` (já sob ``self._lock``). Fonte ÚNICA.

        Extraída de ``slot_for`` no R-24 porque ``sync_connected`` passou a
        atribuir também: duas cópias da regra "menor livre" seriam duas
        chances de divergir do espaço de numeração global (o defeito que esta
        onda inteira existe para matar).
        """
        used = set(self._slots.values())
        prov = self._extra_reserved
        if prov is not None:
            # EXT-04: numeração global ÚNICA — pula os slots que os externos
            # já detêm (um DualSense que conecta DEPOIS de um externo
            # numerado não pode reivindicar o slot dele).
            with contextlib.suppress(Exception):
                used |= {int(s) for s in prov()}
        slot = 1
        while slot in used:
            slot += 1
        self._slots[key] = slot
        if persistable:
            self._dirty = True
        else:
            self._volatile.add(key)
        logger.info(
            "identity_slot_atribuido",
            uniq=key,
            slot=slot,
            volatil=not persistable,
        )
        return slot

    def mark_disconnected(self, uniq: str | None) -> None:
        """Marca ``uniq`` desconectado — o slot fica RESERVADO ao MAC (D2).

        Replug dentro da sessão recupera o mesmo número. R-15: a reserva vale
        pelo BOOT inteiro — nada aqui (nem no ``sync_connected``) expira slot
        por sessão esvaziada, então flap de BT, suspend e "desliguei os dois
        controles pra jantar" devolvem o MESMO número a cada MAC.
        """
        if not uniq or not isinstance(uniq, str):
            return
        key, _ = self._canonical(uniq)
        with self._lock:
            self._connected.discard(key)

    def sync_connected(self, uniqs: Iterable[str]) -> None:
        """Reconcilia com os uniqs CONECTADOS agora e ATRIBUI quem falta (~2s).

        - quem chegou SEM slot ganha o menor livre, na ORDEM em que o
          chamador entrega (R-24 — ver abaixo);
        - quem saiu do conjunto vira RESERVA (slot preso ao MAC — D2);
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
        dois DualSense herdavam 2 e 3 (o "não existe Controle 1" medido na
        máquina dela). O lifecycle chama ESTE método ANTES de agendar o tick
        dos externos no MESMO ciclo do poll loop, então quem está na mesa
        ocupa 1..N primeiro. A ORDEM do iterável é significativa (o
        lifecycle entrega em ordem de ``describe_controllers``, primário
        primeiro) — nunca passar um ``set``, que numeraria por hash.
        """
        vivos: list[tuple[str, bool]] = []
        vistos: set[str] = set()
        for uniq in uniqs:
            if not uniq or not isinstance(uniq, str):
                continue
            key, persistable = self._canonical(uniq)
            if not key or key in vistos:
                continue
            if persistable and key.startswith(_VPAD_MAC_PREFIX):
                continue  # D9: vpad não é controle
            vistos.add(key)
            vivos.append((key, persistable))
        with self._lock:
            self._connected = vistos
            for key, persistable in vivos:
                if key not in self._slots:
                    self._assign_locked(key, persistable)
            if self._dirty:
                self._save_locked()
                self._dirty = False

    def snapshot(self) -> dict[str, int]:
        """Cópia do mapa key→slot atual (conectados + reservas). Leitura pura."""
        with self._lock:
            return dict(self._slots)

    def snapshot_connected(self) -> set[str]:
        """Keys CONECTADAS agora (subconjunto de ``snapshot()``). Leitura pura.

        R-15: o "Renumerar agora" compactava sobre o mapa inteiro — incluindo
        reserva de controle OFFLINE. Com o 8BitDo desligado segurando um slot
        baixo, a compactação era um no-op que ainda respondia "4 controle(s)
        renumerado(s)". Quem está na mesa desce para 1..N; a reserva vai para
        o fim da fila sem ser dropada (a promessa D2 continua de pé).
        """
        with self._lock:
            return set(self._connected)

    def lock_for_renumber(self) -> threading.RLock:
        """Expõe o `RLock` de instância — SÓ para `identity.renumber` (fix TOCTOU).

        Achado MEDIUM da corretora final (2026-07-20): entre o `snapshot()` e
        o `compact()` do handler IPC não havia lock nenhum cobrindo o span
        inteiro plan→apply — um `slot_for(assign=True)` concorrente (hotplug
        real sob o `_io_lock` do backend) podia ler `used` ainda
        NÃO-compactado e reivindicar o slot-alvo que o `compact()` estava
        prestes a devolver a outro controle, gerando dois controles com o
        MESMO slot. O `RLock` é reentrante: o handler mantém isto tomado
        durante `snapshot()`+plano+`compact()` do MESMO thread sem
        autodeadlock; qualquer `slot_for` de OUTRO thread bloqueia até o
        handler soltar. Não usar para mais nada — vazar o lock de instância é
        exceção deliberada, não precedente.
        """
        return self._lock

    def compact(self, mapping: dict[str, int]) -> None:
        """Reatribui slots conforme ``mapping`` (``identity.renumber``, ONDA-U/U2).

        Distinta da atribuição LAZY de ``slot_for``: é uma reescrita
        EXPLÍCITA, disparada só pelo handler IPC (gate de sessão vazia é
        responsabilidade do CHAMADOR — este método não sabe de
        ``display_authority``). Só reescreve chaves que já existem NESTE
        registro — o chamador monta ``mapping`` a partir de um
        ``snapshot()`` deste mesmo objeto (a compactação é GLOBAL entre
        DualSense e externos, cada registro aplica só a fatia que é dele).
        Não mexe em reserva/expiração/voláteis (``_volatile`` continua
        intocado — ``_save_locked`` já filtra por ele); só troca o número do
        slot. Persiste sob ``CONTROLLERS_FILE_LOCK`` via ``_save_locked``
        (mesmo NUMA-04 do save do tick lento) quando algo de fato mudou.
        """
        with self._lock:
            changed = False
            for key, new_slot in mapping.items():
                if key in self._slots and self._slots[key] != new_slot:
                    self._slots[key] = new_slot
                    changed = True
            if changed:
                self._dirty = True
                self._save_locked()
                self._dirty = False

    # ------------------------------------------------------------------
    # Persistência (restart do daemon com controles presentes)
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Carrega ``controllers.json`` — o mapa MAC→slot ATRAVESSA o boot (R-23).

        Chamado UMA vez na fiação do daemon (fora do caminho quente).
        Entradas carregadas entram como RESERVAS: o primeiro reconcile com
        controles presentes as reivindica. O gate NÃO é mais o ``boot_id``
        (era ele que renumerava a casa inteira a cada reboot — e a cada
        restart do daemon onde ``/proc`` não existe): é o
        :data:`CONTROLLERS_SCHEMA_VERSION`. Idempotente; nunca propaga
        exceção. NUMA-04: a leitura roda sob ``CONTROLLERS_FILE_LOCK`` — o
        mesmo lock que ``external_identity.py`` usa para o próprio load/save
        do MESMO arquivo.
        """
        with self._lock:
            if self._loaded:
                return
            self._loaded = True
            with CONTROLLERS_FILE_LOCK:
                try:
                    data = json.loads(self._path().read_text(encoding="utf-8"))
                except (FileNotFoundError, json.JSONDecodeError, OSError):
                    return
                except Exception as exc:  # defensivo — load jamais derruba o boot
                    logger.debug("identity_load_falhou", err=str(exc))
                    return
            if not isinstance(data, dict):
                return
            if data.get("version") != CONTROLLERS_SCHEMA_VERSION:
                # R-23: única renumeração AUTOMÁTICA que sobrou. Arquivo
                # escrito por uma versão com outra regra de numeração (ou
                # anterior ao campo) não pode congelar a regra velha para
                # sempre, agora que nada mais expira.
                logger.info(
                    "identity_arquivo_de_schema_antigo_descartado",
                    versao_arquivo=data.get("version"),
                    versao_atual=CONTROLLERS_SCHEMA_VERSION,
                )
                return
            slots = data.get("slots")
            if not isinstance(slots, dict):
                return
            anchor = _session_anchor()
            if anchor is not None and data.get("boot_id") != anchor:
                # Só DIAGNÓSTICO (R-23): reboot não renumera mais. Fica no log
                # para o dia em que alguém perguntar "de onde veio este número".
                logger.info(
                    "identity_slots_restaurados_de_outro_boot",
                    arquivo_boot=data.get("boot_id"),
                )
            usados: set[int] = set()
            # Slot mais baixo primeiro: se o teto podar, quem cai é a entrada
            # menos estabelecida (slot alto), nunca quem a casa usa todo dia.
            candidatos = sorted(
                slots.items(),
                key=lambda kv: kv[1] if isinstance(kv[1], int) else 0,
            )
            for raw_key, raw_slot in candidatos:
                if not isinstance(raw_key, str) or not isinstance(raw_slot, int):
                    continue
                if isinstance(raw_slot, bool) or raw_slot < 1:
                    continue
                key, persistable = self._canonical(raw_key)
                if not persistable or key.startswith(_VPAD_MAC_PREFIX):
                    continue  # voláteis/vpad jamais deveriam estar no disco
                if key in self._slots or raw_slot in usados:
                    continue  # arquivo degenerado: 1º ganha, sem duplicatas
                if len(self._slots) >= _MAX_PERSISTED_SLOTS:
                    logger.warning(
                        "identity_slots_truncados", teto=_MAX_PERSISTED_SLOTS
                    )
                    break
                self._slots[key] = raw_slot
                usados.add(raw_slot)
            if self._slots:
                logger.info("identity_slots_restaurados", slots=dict(self._slots))

    @staticmethod
    def _path() -> Path:
        """Path do ``controllers.json`` — import LAZY do ``config_dir``.

        Lazy para preservar o ponto de monkeypatch dos testes
        (``monkeypatch.setattr(xdg_paths, "config_dir", ...)``), o mesmo
        padrão de ``utils.session.save_active_marker``.
        """
        from hefesto_dualsense4unix.utils.xdg_paths import config_dir

        return config_dir(ensure=True) / _CONTROLLERS_FILE

    def _save_locked(self) -> None:
        """Grava o mapa persistível (atômico: mkstemp + os.replace). Sob lock.

        Só entradas com MAC 12-hex (voláteis ficam de fora — D9). Nunca
        propaga exceção (paridade com ``utils.session``): perder um save
        significa, no pior caso, renumerar no próximo boot — inócuo.

        EXT-04: o arquivo é COMPARTILHADO com o registro dos externos
        (namespace ``externals`` — ``subsystems/external_identity.py``);
        read-modify-write para preservar o namespace do outro lado. NUMA-04:
        o span INTEIRO read→``os.replace`` roda sob ``CONTROLLERS_FILE_LOCK``
        — fecha o lost-update entre os dois escritores independentes (cada
        um só tinha o próprio RLock de instância, que não protegia o outro).
        """
        try:
            with CONTROLLERS_FILE_LOCK:
                path = self._path()
                payload: dict[str, Any] = {}
                with contextlib.suppress(Exception):
                    existente = json.loads(path.read_text(encoding="utf-8"))
                    # R-23: só se carrega o namespace do OUTRO quando o
                    # arquivo é do MESMO schema. Preservá-lo às cegas num
                    # bump de versão re-carimbava a versão nova sobre a
                    # numeração VELHA do outro lado: o `externals` do regime
                    # antigo (na máquina dela, o Pro segurando o slot 1)
                    # ressuscitava com selo de válido no boot seguinte.
                    if (
                        isinstance(existente, dict)
                        and existente.get("version") == CONTROLLERS_SCHEMA_VERSION
                        and isinstance(existente.get("externals"), dict)
                    ):
                        payload["externals"] = existente["externals"]
                # R-23: a VERSÃO é o que o load consulta; o boot_id vira
                # anotação (âncora resiliente — nunca mais um gate).
                payload["version"] = CONTROLLERS_SCHEMA_VERSION
                payload["boot_id"] = _session_anchor()
                payload["slots"] = {
                    key: slot
                    for key, slot in self._slots.items()
                    if key not in self._volatile
                }
                data = json.dumps(payload, ensure_ascii=False)
                fd, tmp = tempfile.mkstemp(
                    dir=os.path.dirname(os.fspath(path)), prefix=".controllers_"
                )
                try:
                    os.write(fd, data.encode())
                finally:
                    os.close(fd)
                os.replace(tmp, path)
                logger.debug("identity_slots_salvos", slots=payload["slots"])
        except Exception as exc:
            logger.debug("identity_save_falhou", err=str(exc))


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
    """
    from hefesto_dualsense4unix.core.backend_pydualsense import _DesiredOutput
    from hefesto_dualsense4unix.core.led_control import (
        LedSettings,
        player_led_pattern,
        player_slot_color,
    )

    def provider(uniq: str) -> _DesiredOutput | None:
        # R-14 §1: a ATRIBUIÇÃO acontece sempre (ver docstring).
        slot = registry.slot_for(uniq)
        if slot is None:
            return None
        campos: dict[str, Any] = {}
        if registry.auto_enabled:
            brilho = registry.auto_brightness
            settings = LedSettings(
                lightbar=player_slot_color(slot), brightness_level=brilho
            )
            campos["led"] = settings.apply_brightness(brilho).lightbar
        if registry.auto_numbers_enabled:
            campos["player_leds"] = player_led_pattern(slot)
        if not campos:
            return None  # os dois eixos desligados = sem opinião nenhuma
        return _DesiredOutput(**campos)

    return provider


_registry: ControllerIdentityRegistry | None = None
_registry_lock = threading.Lock()


def get_identity_registry() -> ControllerIdentityRegistry:
    """Registro de identidade do processo (singleton, criado sob demanda).

    Singleton deliberado: o ``ProfileManager`` é instanciado em ≥3 lugares
    (restore de boot, hotkey, IPC) e todos precisam configurar o MESMO
    estado do automático que o provider (injetado no backend pela fiação do
    daemon) consulta — sem parâmetro novo em cada callsite. A criação não
    faz I/O (o ``load()`` é chamado explicitamente só pela fiação do
    daemon), então testes que ativam perfis continuam herméticos.
    """
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


__all__ = [
    "CONTROLLERS_FILE_LOCK",
    "CONTROLLERS_SCHEMA_VERSION",
    "ControllerIdentityRegistry",
    "get_identity_registry",
    "make_auto_output_provider",
    "reset_identity_registry",
]

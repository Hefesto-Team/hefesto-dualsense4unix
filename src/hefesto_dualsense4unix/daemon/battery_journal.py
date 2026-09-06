"""Diário da bateria — o daemon para de medir a carga no escuro.

Entrega 1 do
``docs/process/estudos/2026-08-07-PROTOCOLO-o-controle-que-cai-sozinho.md``.

O buraco que isto tapa, MEDIDO em 07/08/2026: o daemon **lê** a carga a cada
tique (``core/backend_pydualsense.py`` → ``BATTERY_CHANGE`` em
``daemon/lifecycle.py``) e **não escrevia uma linha no journal** — só o contador
``battery.change.emitted`` no store. Sem linha no journal, a pergunta *"o
controle desligou sozinho ou a carga acabou?"* é indecidível **por falta de
instrumento**, não por falta de análise.

Duas réguas, sempre declaradas na mesma linha
-----------------------------------------------
Regra da casa: todo instrumento declara contra o que mede. Cada amostra sai com
as **duas** leituras:

``pct_kernel``
    ``/sys/class/power_supply/ps-controller-battery-<mac>/capacity`` — driver
    ``hid-playstation``, e o irmão ``status`` (``Charging``/``Discharging``/
    ``Full``/``Unknown``) que diz de que lado da curva estamos.
``pct_handle``
    a leitura própria do handle da pydualsense, a mesma que alimenta a GUI.

Se as duas discordarem em mais de um degrau, **o resultado é sobre o
instrumento**, não sobre a bateria — e é por isso que as duas vão para o
journal, não a "melhor" delas.

A cadência, e por que ela é esta
--------------------------------
- **A cada tique (60 Hz) polui e some no ruído**: seriam ~5,2 milhões de linhas
  por dia. E o ``BatteryDebouncer`` do ``subsystems/poll.py`` também não serve
  de gatilho: ele dispara a cada 5 s mesmo sem mudança nenhuma (~17 mil linhas
  por dia).
- **Só na queda perde a CURVA** — e a curva é justamente o que decide entre
  "bateria" e "link".

Então: **sonda a cada 30 s** (resolução do instante da queda, custo de dois
``read`` de sysfs por meio minuto) e **linha só quando há o que dizer**:

1. ``abertura`` — a primeira leitura de cada controle (nascimento da curva);
2. ``faixa`` — a carga mudou de faixa, com ``borda=queda`` ou ``borda=subida``;
3. ``status`` — o ``status`` do kernel mudou (é a borda do cabo entrando/saindo);
4. ``ancora`` — a cada 30 min mesmo sem mudança, para que um trecho reto da
   curva seja distinguível de *"o daemon parou de olhar"*.

As faixas (:data:`FAIXAS`) são de 10 pontos no alto e de 5 embaixo: os limiares
que o protocolo usa para decidir são 10% e 40%, e é embaixo que a curva decide.
O ``hid-playstation`` reporta a carga do DualSense em degraus de 10 deslocados
de 5 (5, 15, 25, … 95) — com estas faixas, **todo** degrau do hardware cruza uma
fronteira, então nenhum se perde.

Volume esperado numa sessão de 16 h: ~10 linhas de faixa + ~32 âncoras + as
bordas de cabo, algo como 45 linhas. O evento mais frequente do journal dela
(``hidraw_broker_hidden``) teve 14.105 ocorrências em 7 dias — este diário é
0,3% disso. GRAU: MEDIDO (contagem do protocolo de 07/08).

O endereço NÃO vai cru
----------------------
O journal dela já publica ``uniq=`` cru hoje, e o repositório é público: o
endereço de rádio identifica o aparelho. Toda linha daqui sai com a **máscara da
casa** — octetos 4 e 5 zerados (``OUI:00:00:NN``), a mesma convenção que o
portão ``tests/unit/test_docs_mac_anonimato.py`` cobra dos arquivos versionados.
A máscara preserva o que a análise precisa (fabricante + último octeto
distinguem os dois DualSense da bancada) e apaga o que identifica o aparelho.

A linha da queda
----------------
``bateria_na_queda`` é o dado que transforma o próximo *"desligou sozinho"* em
resposta: a última capacidade conhecida, com a **idade** dessa leitura. Sai em
dois momentos, e o segundo é o que enxerga o que o ``probe_offline`` não vê:

- na desconexão do último controle (``daemon/connection.py`` e o caminho de
  erro de leitura do ``daemon/lifecycle.py``);
- e quando **um** controle some do backend com outros ainda de pé — o
  ``probe_offline`` nasce de um ``any()`` sobre os handles e por isso só dispara
  quando o ÚLTIMO cai (é por isso que "18 quedas" é piso, não total).
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: Raiz dos nós de bateria do kernel (driver ``hid-playstation``).
RAIZ_POWER_SUPPLY = Path("/sys/class/power_supply")

#: Prefixo do nó de UM controle PlayStation. O sufixo é o endereço com ``:``.
PREFIXO_NO_KERNEL = "ps-controller-battery-"

#: Prefixo do MAC FORJADO dos nossos gamepads virtuais, sem separador.
#:
#: BATERIA-PARADA-01 (B2). **NÃO É BATERIA, E O NÚMERO DELE NUNCA MUDA.**
#: Medido em 26/08/2026 e reconferido em 06/09/2026 na bancada dela: o sysfs
#: tinha QUATRO nós de ``ps-controller-battery-*`` para DOIS controles, e dois
#: eram nossos — os vpads do ``integrations/uhid_gamepad.player_mac()``, cujo
#: nó diz ``Charging`` para sempre porque é valor de inicialização do uhid, não
#: medição de aparelho nenhum. Quem casar pelo nó errado lê um número que
#: **nunca muda** e conclui que a bateria congelou.
#:
#: O valor é ESPELHADO de propósito, como o ``VPAD_UNIQ_PREFIX`` do
#: ``broker/hidraw_broker.py`` e o ``_VPAD_UNIQ_PREFIX`` do
#: ``core/backend_pydualsense.py`` — este módulo é leve por contrato (stdlib +
#: logger) e roda no tique lento do daemon. **O que impede o espelho de
#: divergir em silêncio é o portão**
#: ``tests/unit/test_a_bateria_nao_le_o_no_do_vpad.py``, que confronta as três
#: cópias com o ``player_mac(1)`` que as forja: no dia em que o prefixo mudar,
#: ele NOMEIA em vez de a varredura voltar a ler o nó errado calada.
#:
#: A VARREDURA DESTA CASA É :meth:`DiarioDaBateria.observar` + :func:`ler_no_do_kernel`,
#: e é onde a exclusão mora. Uma função pública que ENUMERASSE
#: ``/sys/class/power_supply`` chegou a existir aqui em 06/09 e foi apagada
#: antes do commit: nada em produção a chamava, e o
#: ``portao_a_casa_sabe_e_o_produto_nao_faz`` a acusou pelo nome. Ela tem lugar
#: no dia em que alguém fechar `controles_sem_driver` — um controle cuja probe
#: abortou não tem handle e some da lista, mas o nó de bateria dele fica —,
#: e nesse dia ela nasce COM o chamador.
PREFIXO_DO_VPAD = "02fe"

#: Intervalo entre sondas (segundos). Duas leituras de sysfs por sonda.
INTERVALO_SONDA_S = 30.0

#: Intervalo da âncora periódica (segundos) — a linha que sai mesmo sem mudança
#: nenhuma, para que "curva reta" não se confunda com "instrumento parado".
INTERVALO_ANCORA_S = 1800.0

#: Fronteiras das faixas de carga, em ordem crescente. A faixa de um valor é a
#: MAIOR fronteira menor ou igual a ele. Passo de 5 abaixo de 20% (é lá que a
#: curva decide, e os limiares do protocolo são 10% e 40%), de 10 acima.
FAIXAS: tuple[int, ...] = (0, 5, 10, 15, 20, 30, 40, 50, 60, 70, 80, 90, 100)

#: Janela em que uma segunda queda SEM leitura nenhuma cala, para não desmentir
#: a linha boa que a primeira acabou de escrever. Ver `registrar_queda`.
JANELA_DEDUP_QUEDA_S = 60.0

#: O que sai no lugar do endereço quando não há endereço reconhecível.
SEM_ENDERECO = "desconhecido"


def faixa_de(pct: int | None) -> int | None:
    """Faixa de :data:`FAIXAS` em que ``pct`` cai, ou None se não há leitura."""
    if pct is None:
        return None
    escolhida = FAIXAS[0]
    for limite in FAIXAS:
        if pct >= limite:
            escolhida = limite
        else:
            break
    return escolhida


def mascarar_endereco(valor: str | None) -> str:
    """Endereço na máscara da casa: ``OUI:00:00:NN`` (octetos 4 e 5 zerados).

    Aceita as duas grafias que circulam no produto — a colada, que é como o
    endereço sai do ``controllers.json`` e do journal (``a0fa9c…``), e a com
    separador. Qualquer coisa que não tenha 12 dígitos hex vira
    :data:`SEM_ENDERECO`: é preferível uma linha sem identidade a uma linha com
    um pseudo-endereço inventado a partir de um path.
    """
    if not valor:
        return SEM_ENDERECO
    digitos = "".join(ch for ch in valor.lower() if ch in "0123456789abcdef")
    if len(digitos) != 12:
        return SEM_ENDERECO
    octetos = [digitos[i : i + 2] for i in range(0, 12, 2)]
    octetos[3] = "00"
    octetos[4] = "00"
    return ":".join(octetos)


def _endereco_com_dois_pontos(uniq: str) -> str | None:
    """``a0fa9c…`` → ``a0:fa:9c:…`` (o formato do nome do nó do kernel)."""
    digitos = "".join(ch for ch in uniq.lower() if ch in "0123456789abcdef")
    if len(digitos) != 12:
        return None
    return ":".join(digitos[i : i + 2] for i in range(0, 12, 2))


def e_no_do_vpad(valor: str | None) -> bool:
    """True se este endereço é de um gamepad VIRTUAL nosso (:data:`PREFIXO_DO_VPAD`).

    BATERIA-PARADA-01 (B2). Aceita as duas grafias que circulam — a colada
    (``02fe00000001``) e a com separador (``02:fe:00:00:00:01``) — e também o
    nome inteiro do nó (``ps-controller-battery-02:fe:…``), porque a varredura
    do sysfs entrega o nome e o journal entrega o ``uniq``.

    Endereço irreconhecível devolve ``False``: a dúvida aqui erra para *"pode
    ser controle de verdade"*, e uma leitura a mais custa dois ``read`` de
    sysfs; o erro contrário — chamar controle dela de vpad — o apagaria da
    curva da bateria sem deixar rastro.
    """
    if not valor:
        return False
    digitos = "".join(ch for ch in valor.lower() if ch in "0123456789abcdef")
    # A comparação é pelos ÚLTIMOS 12 dígitos, e isso não é zelo: o nome do nó
    # é `ps-controller-battery-<mac>`, e o próprio prefixo tem letras a-f
    # ("controller" dá `c`,`e`; "battery" dá `b`,`a`,`e`). Filtrar hex do nome
    # inteiro e olhar o COMEÇO leria "cebae…" e nunca casaria; o endereço mora
    # no fim.
    if len(digitos) < 12:
        return False
    return digitos[-12:].startswith(PREFIXO_DO_VPAD)


def ler_no_do_kernel(
    uniq: str, *, raiz: Path = RAIZ_POWER_SUPPLY
) -> tuple[int | None, str | None]:
    """``(capacity, status)`` do nó do kernel deste controle.

    ``(None, None)`` quando o nó não existe (controle por USB em algumas
    versões do driver, controle que acabou de sumir, kernel sem
    ``hid-playstation``). O nome do nó usa o endereço em minúsculas; tentamos
    também a grafia em maiúsculas porque o formato do nome é do driver, não
    nosso. Nunca levanta: leitura de sysfs falha por corrida (o nó some entre o
    ``exists`` e o ``read``) e isso não pode derrubar o poll loop.

    **E ``(None, None)`` também para o nosso vpad** (B2): o nó dele existe e
    responde, e é justamente por isso que ele engana — ver :func:`e_no_do_vpad`.
    """
    if e_no_do_vpad(uniq):
        return (None, None)
    endereco = _endereco_com_dois_pontos(uniq)
    if endereco is None:
        return (None, None)
    for grafia in (endereco, endereco.upper()):
        no = raiz / f"{PREFIXO_NO_KERNEL}{grafia}"
        capacity = _ler_int(no / "capacity")
        status = _ler_texto(no / "status")
        if capacity is not None or status is not None:
            return (capacity, status)
    return (None, None)


def _ler_texto(caminho: Path) -> str | None:
    try:
        return caminho.read_text(encoding="utf-8", errors="ignore").strip() or None
    except (OSError, ValueError):
        return None


def _ler_int(caminho: Path) -> int | None:
    bruto = _ler_texto(caminho)
    if bruto is None:
        return None
    try:
        valor = int(bruto)
    except ValueError:
        return None
    return max(0, min(100, valor))


@dataclass
class _Leitura:
    """A última amostra conhecida de UM controle."""

    pct_kernel: int | None
    pct_handle: int | None
    status: str | None
    faixa: int | None
    fonte: str
    #: Instante (mesmo relógio do ``observar``) em que a amostra foi lida.
    vista_em: float
    #: Instante da última LINHA escrita para este controle.
    logada_em: float
    #: O estado de carga que o HANDLE leu (`backend_pydualsense.ESTADO_DE_CARGA`),
    #: a régua irmã do ``status`` do kernel. BATERIA-PARADA-01.
    estado_handle: str | None = None


class DiarioDaBateria:
    """Decide quando a carga vira linha de journal — e com que identidade.

    Sem estado global: uma instância por daemon, criada sob demanda por
    :func:`diario_da_bateria`. Os relógios são passados de fora (o poll loop já
    tem o ``loop.time()`` do tique), o que torna a classe testável sem esperar
    meia hora de âncora.
    """

    def __init__(
        self,
        *,
        raiz: Path = RAIZ_POWER_SUPPLY,
        intervalo_sonda: float = INTERVALO_SONDA_S,
        intervalo_ancora: float = INTERVALO_ANCORA_S,
        store: Any = None,
    ) -> None:
        self._raiz = raiz
        self._intervalo_sonda = intervalo_sonda
        self._intervalo_ancora = intervalo_ancora
        self._store = store
        self._ultimas: dict[str, _Leitura] = {}
        self._proxima_sonda: float = 0.0
        #: Instante da última linha de queda escrita — só para a dedup da
        #: queda dupla (ver `registrar_queda`). None = nenhuma ainda.
        self._ultima_queda_em: float | None = None

    # -- escrita -------------------------------------------------------

    def observar(
        self, controles: Iterable[Mapping[str, Any]], agora: float
    ) -> int:
        """Sonda os controles conectados e escreve as linhas que couberem.

        ``controles`` é a saída de ``describe_controllers()`` do backend (os
        mesmos getattrs baratos do tique lento). Devolve quantas linhas foram
        escritas — só para teste e diagnóstico; ninguém gateia por isto.
        """
        if agora < self._proxima_sonda:
            return 0
        self._proxima_sonda = agora + self._intervalo_sonda

        linhas = 0
        vistos: set[str] = set()
        for info in controles:
            if not isinstance(info, Mapping) or not info.get("connected"):
                continue
            uniq = info.get("uniq")
            if not isinstance(uniq, str) or not uniq:
                # Sem endereço não há nó do kernel nem identidade estável entre
                # sondas — uma linha aqui não seria atribuível a controle nenhum.
                continue
            if e_no_do_vpad(uniq):
                # B2: o gamepad VIRTUAL não tem bateria. Se um dia ele entrar
                # nesta lista, a curva dele seria uma reta em 100% `Charging` —
                # e a reta se lê como "o instrumento parou de olhar".
                continue
            vistos.add(uniq)
            linhas += self._observar_um(
                uniq, info.get("battery_pct"), info.get("battery_state"), agora
            )

        # Um controle que some do backend com outros ainda de pé NÃO gera
        # `probe_offline` (o `is_connected()` é um any() sobre os handles) —
        # é a queda que hoje não deixa rastro nenhum. Aqui ela deixa.
        for uniq in sorted(set(self._ultimas) - vistos):
            linhas += self._escrever_queda(uniq, self._ultimas.pop(uniq), "sumiu_do_backend", agora)
        return linhas

    def registrar_queda(self, motivo: str, agora: float) -> int:
        """Escreve a última capacidade conhecida de cada controle na queda.

        Tenta uma leitura FRESCA do nó do kernel antes de cair no cache: nas
        quedas de link o nó costuma sobreviver alguns instantes ao handle, e
        essa amostra vale mais que a de até 30 s atrás. ``idade_s`` diz de qual
        das duas se trata — 0.0 é fresca.

        Sem nenhuma leitura acumulada (queda antes da primeira sonda), escreve
        **mesmo assim** uma linha sem carga: *"caiu e ninguém tinha medido"* é
        informação, e o silêncio aqui é justamente o defeito que esta entrega
        cura.

        A exceção é a queda DUPLA, e ela é real: um controle que some de vez
        passa primeiro pelo `poll_read_failed` (o poll loop perdendo a leitura)
        e, segundos depois, pelo `probe_offline` (o probe confirmando). A
        segunda chamada já não tem leitura nenhuma — o cache foi consumido pela
        primeira — e escreveria *"ninguém tinha medido"* logo abaixo da linha
        boa, dizendo o contrário dela. Dentro de
        :data:`JANELA_DEDUP_QUEDA_S` a segunda cala.
        """
        if not self._ultimas:
            if (
                self._ultima_queda_em is not None
                and agora - self._ultima_queda_em < JANELA_DEDUP_QUEDA_S
            ):
                return 0
            self._ultima_queda_em = agora
            logger.info(
                "bateria_na_queda",
                controle=SEM_ENDERECO,
                pct_kernel=None,
                pct_handle=None,
                status=None,
                estado_handle=None,
                faixa=None,
                idade_s=None,
                motivo=motivo,
            )
            self._bump("battery.journal.drop")
            return 1
        linhas = 0
        for uniq in sorted(self._ultimas):
            linhas += self._escrever_queda(uniq, self._ultimas[uniq], motivo, agora)
        self._ultimas.clear()
        self._ultima_queda_em = agora
        return linhas

    # -- internos ------------------------------------------------------

    def _observar_um(
        self,
        uniq: str,
        bruto_handle: object,
        estado_handle: object,
        agora: float,
    ) -> int:
        pct_handle = _como_pct(bruto_handle)
        estado = estado_handle if isinstance(estado_handle, str) and estado_handle else None
        pct_kernel, status = ler_no_do_kernel(uniq, raiz=self._raiz)
        if pct_kernel is None and pct_handle is None:
            # Nada medido por nenhuma das duas réguas: não há o que afirmar.
            return 0
        fonte = "kernel" if pct_kernel is not None else "handle"
        pct = pct_kernel if pct_kernel is not None else pct_handle
        faixa = faixa_de(pct)

        anterior = self._ultimas.get(uniq)
        motivo, borda = _motivo_da_linha(anterior, faixa, status, agora, self._intervalo_ancora)
        leitura = _Leitura(
            pct_kernel=pct_kernel,
            pct_handle=pct_handle,
            status=status,
            faixa=faixa,
            fonte=fonte,
            vista_em=agora,
            logada_em=anterior.logada_em if anterior is not None else agora,
            estado_handle=estado,
        )
        if motivo is None:
            self._ultimas[uniq] = leitura
            return 0
        leitura.logada_em = agora
        self._ultimas[uniq] = leitura
        logger.info(
            "bateria_amostra",
            controle=mascarar_endereco(uniq),
            pct_kernel=pct_kernel,
            pct_handle=pct_handle,
            status=status,
            # BATERIA-PARADA-01: o estado de carga tem DUAS réguas, como o
            # percentual — `status` é o do kernel (`Charging`/`Full`/…) e
            # `estado_handle` é o do byte que o handle leu
            # (`backend_pydualsense.ESTADO_DE_CARGA`). As duas vão juntas, pela
            # mesma disciplina que já vale para `pct_kernel`/`pct_handle`: se
            # discordarem, o resultado é sobre o instrumento, não sobre a carga.
            estado_handle=estado,
            faixa=faixa,
            fonte=fonte,
            motivo=motivo,
            borda=borda,
        )
        self._bump("battery.journal.sample")
        return 1

    def _escrever_queda(
        self, uniq: str, leitura: _Leitura, motivo: str, agora: float
    ) -> int:
        pct_kernel, status = ler_no_do_kernel(uniq, raiz=self._raiz)
        if pct_kernel is not None:
            idade = 0.0
            pct_handle = leitura.pct_handle
            faixa = faixa_de(pct_kernel)
            fonte = "kernel"
        else:
            idade = round(max(0.0, agora - leitura.vista_em), 1)
            pct_kernel = leitura.pct_kernel
            pct_handle = leitura.pct_handle
            status = leitura.status
            faixa = leitura.faixa
            fonte = leitura.fonte
        logger.info(
            "bateria_na_queda",
            controle=mascarar_endereco(uniq),
            pct_kernel=pct_kernel,
            pct_handle=pct_handle,
            status=status,
            estado_handle=leitura.estado_handle,
            faixa=faixa,
            fonte=fonte,
            idade_s=idade,
            motivo=motivo,
        )
        self._bump("battery.journal.drop")
        return 1

    def _bump(self, contador: str) -> None:
        bump = getattr(self._store, "bump", None)
        if callable(bump):
            try:
                bump(contador)
            except Exception:  # observabilidade nunca derruba o poll loop
                logger.debug("bateria_contador_falhou", contador=contador)


def _como_pct(bruto: object) -> int | None:
    if isinstance(bruto, bool) or not isinstance(bruto, int):
        return None
    return max(0, min(100, bruto))


def _motivo_da_linha(
    anterior: _Leitura | None,
    faixa: int | None,
    status: str | None,
    agora: float,
    intervalo_ancora: float,
) -> tuple[str | None, str | None]:
    """``(motivo, borda)`` — None no motivo quer dizer "não há o que dizer"."""
    if anterior is None:
        return ("abertura", None)
    if status != anterior.status:
        return ("status", _borda_de_carga(status))
    if faixa != anterior.faixa:
        if faixa is None or anterior.faixa is None:
            return ("faixa", None)
        return ("faixa", "queda" if faixa < anterior.faixa else "subida")
    if agora - anterior.logada_em >= intervalo_ancora:
        return ("ancora", None)
    return (None, None)


def _borda_de_carga(status: str | None) -> str | None:
    """Traduz o ``status`` do kernel para o lado da curva, quando ele decide."""
    if status is None:
        return None
    normal = status.strip().lower()
    if normal == "charging":
        return "subida"
    if normal == "discharging":
        return "queda"
    return None


def diario_da_bateria(daemon: Any) -> DiarioDaBateria:
    """Diário do daemon, criado no primeiro uso (espelho do ``get_coop_manager``)."""
    diario = getattr(daemon, "_diario_bateria", None)
    if diario is None:
        diario = DiarioDaBateria(store=getattr(daemon, "store", None))
        daemon._diario_bateria = diario
    return diario


def registrar_queda_da_bateria(daemon: Any, motivo: str, agora: float) -> None:
    """Gancho da borda de desconexão. Best-effort: nunca levanta ao chamador."""
    try:
        diario_da_bateria(daemon).registrar_queda(motivo, agora)
    except Exception as exc:  # pragma: no cover - defesa de borda
        logger.debug("bateria_na_queda_falhou", err=str(exc))


__all__ = [
    "FAIXAS",
    "INTERVALO_ANCORA_S",
    "INTERVALO_SONDA_S",
    "JANELA_DEDUP_QUEDA_S",
    "PREFIXO_DO_VPAD",
    "PREFIXO_NO_KERNEL",
    "RAIZ_POWER_SUPPLY",
    "SEM_ENDERECO",
    "DiarioDaBateria",
    "diario_da_bateria",
    "e_no_do_vpad",
    "faixa_de",
    "ler_no_do_kernel",
    "mascarar_endereco",
    "registrar_queda_da_bateria",
]

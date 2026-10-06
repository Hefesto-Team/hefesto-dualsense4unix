"""O canal de captura de UM controle, com o nome DELE — não o do transporte."""

from __future__ import annotations

import contextlib
import logging
import subprocess
import threading
from typing import Any

from hefesto_dualsense4unix.integrations.dualsense_bt_audio import (
    MIC_AMOSTRAS_POR_QUADRO,
    MIC_BYTES_POR_AMOSTRA,
    MIC_CANAIS,
    MIC_TAXA_HZ,
    PRIORIDADE_SESSAO_DA_PONTE,
    SourceVirtualPipeWire,
    marca_do_aparelho,
    rotulo_envelheceu,
)
from hefesto_dualsense4unix.integrations.filho_de_som import (
    derrubar_leitor_de_pipe,
    lancar_leitor,
)
from hefesto_dualsense4unix.integrations.fontes_de_captura import (
    PREFIXO_SOURCE_CANAL_DO_MIC,
    so_hex,
)
from hefesto_dualsense4unix.integrations.quem_ouve_o_microfone import (
    PREFIXO_PROPRIEDADE_HEFESTO,
)

logger = logging.getLogger(__name__)

PREFIXO_CANAL = PREFIXO_SOURCE_CANAL_DO_MIC


_HEX_DE_UM_ENDERECO = 12

_SEPARADORES = (":", "-", ".", " ")

PAPEL_DO_ALIMENTADOR = "canal-do-microfone"

_ALIMENTADOR = "parec"

NOME_DO_CLIENTE_ALIMENTADOR = "hefesto-canal-do-microfone"

def pedaco_do_bombeador(*, taxa_hz: int, canais: int) -> int:
    """Quanto o bombeador lê por vez, na duração do quadro do RÁDIO."""
    taxa = max(1, int(taxa_hz))
    canais_n = max(1, int(canais))
    amostras = max(1, round(taxa * MIC_AMOSTRAS_POR_QUADRO / MIC_TAXA_HZ))
    return amostras * canais_n * MIC_BYTES_POR_AMOSTRA

_LATENCIA_DO_ALIMENTADOR_MS = 40

_ESPERA_PELO_FIM_S = 2.0

_JUNTA_DO_BOMBEADOR_S = 0.5

_TIMEOUT_PACTL_S = 5.0


def sufixo_do_controle(uniq: str) -> str:
    """A marca do aparelho deste `uniq` — "" se ele não for um endereço.

    OS-NOS-DE-SOM-SEM-O-ENDERECO-NO-NOME-01 (02/10/2026): o nome do canal
    levava os seis últimos dígitos do endereço; leva a marca do aparelho
    (`dualsense_bt_audio.marca_do_aparelho`), a mesma do cabo e do rádio. **Sem
    identidade não se batiza um canal**, e ele EXIGE UM ENDEREÇO INTEIRO, não
    "seis dígitos hex em algum lugar" (medido em 05/09/2026: ``so_hex`` sobre
    ``"sem-identidade"`` devolve ``"emdedade"``).
    """
    limpo = uniq.lower()
    for separador in _SEPARADORES:
        limpo = limpo.replace(separador, "")
    if len(limpo) < _HEX_DE_UM_ENDERECO or so_hex(limpo) != limpo:
        return ""
    return marca_do_aparelho(limpo)


def nome_do_canal(uniq: str) -> str:
    """`hefesto_mic_<marca>` para este controle — "" se ele não tem identidade."""
    sufixo = sufixo_do_controle(uniq)
    return f"{PREFIXO_CANAL}{sufixo}" if sufixo else ""


def propriedades_do_canal(uniq: str) -> dict[str, str]:
    """As propriedades do ALIMENTADOR — no ESPAÇO DE NOME, nunca combinadas."""
    return {
        f"{PREFIXO_PROPRIEDADE_HEFESTO}papel": PAPEL_DO_ALIMENTADOR,
        f"{PREFIXO_PROPRIEDADE_HEFESTO}uniq": uniq,
    }


def argv_do_alimentador(uniq: str, fonte: str, *, taxa_hz: int, canais: int) -> list[str]:
    """A linha de comando do leitor que enche o fifo — nunca uma string de shell."""
    argv = [
        _ALIMENTADOR,
        f"--device={fonte}",
        "--raw",
        "--format=s16le",
        f"--rate={taxa_hz}",
        f"--channels={canais}",
        f"--latency-msec={_LATENCIA_DO_ALIMENTADOR_MS}",
        f"--client-name={NOME_DO_CLIENTE_ALIMENTADOR}",
    ]
    props = sorted(propriedades_do_canal(uniq).items())
    argv += [f"--property={chave}={valor}" for chave, valor in props]
    return argv


class _Alimentador:
    """O leitor do cabo e o bombeador — as duas metades de "o cabo entra no nó"."""

    def __init__(self, uniq: str, fonte: str, source: Any, *, lancar: Any = None) -> None:
        self.uniq = uniq
        self.fonte = fonte
        self.source = source
        self._lancar = lancar or _lancar_processo
        self._proc: Any = None
        self._pedaco = pedaco_do_bombeador(taxa_hz=MIC_TAXA_HZ, canais=MIC_CANAIS)
        self._bomba: threading.Thread | None = None
        self._parando = threading.Event()

    def _formato_do_no(self) -> tuple[int, int]:
        """A taxa e os canais com que o nó foi carregado — PERGUNTADOS a ele."""
        return (
            int(getattr(self.source, "taxa_hz", MIC_TAXA_HZ)),
            int(getattr(self.source, "canais", MIC_CANAIS)),
        )

    def iniciar(self) -> bool:
        taxa_hz, canais = self._formato_do_no()
        self._pedaco = pedaco_do_bombeador(taxa_hz=taxa_hz, canais=canais)
        argv = argv_do_alimentador(
            self.uniq,
            self.fonte,
            taxa_hz=taxa_hz,
            canais=canais,
        )
        try:
            self._proc = self._lancar(argv)
        except (OSError, ValueError):
            logger.warning("canal_do_mic_alimentador_nao_lancou", exc_info=True)
            return False
        if self._proc is None or self._proc.stdout is None:
            return False
        self._bomba = threading.Thread(
            target=self._bombear, name=f"canal-do-mic-{self.uniq}", daemon=True
        )
        self._bomba.start()
        return True

    def _bombear(self) -> None:
        fluxo = self._proc.stdout
        try:
            while not self._parando.is_set():
                pedaco = fluxo.read(self._pedaco)
                if not pedaco:
                    break
                self.source.escrever(pedaco)
        except (OSError, ValueError):
            logger.debug("canal_do_mic_bomba_terminou", exc_info=True)

    def parar(self) -> None:
        """Mata o alimentador PELO PROCESSO QUE NÓS LANÇAMOS, nunca por padrão."""
        self._parando.set()
        proc = self._proc
        bomba = self._bomba
        if proc is not None:
            como = derrubar_leitor_de_pipe(
                proc,
                leitor=bomba,
                junta_s=_JUNTA_DO_BOMBEADOR_S,
                espera_s=_ESPERA_PELO_FIM_S,
            )
            logger.debug(
                "canal_do_mic_alimentador_colhido",
                extra={"uniq": self.uniq, "rc": como.codigo, "por": como.por,
                       "ms": como.ms},
            )
        elif bomba is not None and bomba.is_alive():
            bomba.join(timeout=_ESPERA_PELO_FIM_S)
        self._proc = None
        self._bomba = None


def _lancar_processo(argv: list[str]) -> Any:
    """O `Popen` de verdade, pelo dono único. Isolado para a régua trocá-lo."""
    return lancar_leitor(argv)


def _rodar_pactl(argv: list[str]) -> bool:
    """Um `pactl` curto, com teto. Isolado para a régua trocá-lo por um dublê:"""
    from hefesto_dualsense4unix.integrations import retrato_do_som

    try:
        return (
            subprocess.run(
                argv, capture_output=True, timeout=_TIMEOUT_PACTL_S, check=False
            ).returncode
            == 0
        )
    finally:
        retrato_do_som.escreveu(argv)


def desmutar(nome: str, *, rodar: Any = None) -> bool:
    """Tira o mudo DE FÁBRICA do nó que acabamos de criar."""
    try:
        return bool((rodar or _rodar_pactl)(["pactl", "set-source-mute", nome, "0"]))
    except Exception:
        logger.warning("canal_do_mic_nao_desmutou", exc_info=True)
        return False


_DE_PE: dict[str, SourceVirtualPipeWire] = {}

_ALIMENTANDO: dict[str, _Alimentador] = {}

_FONTE_PEDIDA: dict[str, str] = {}
_TRANCA = threading.Lock()


def _passar_a_escolha_dela(uniq: str, nome: str) -> None:
    """A fonte padrão gravada no nome velho deste canal passa ao nome novo. Nunca levanta."""
    from hefesto_dualsense4unix.integrations.eleicao_de_microfone import (
        passar_a_escolha_gravada_ao_nome_novo,
    )

    with contextlib.suppress(Exception):
        passar_a_escolha_gravada_ao_nome_novo(uniq, nome, prefixo=PREFIXO_CANAL)


def abrir(
    uniq: str,
    descricao: str,
    *,
    fonte: str | None = None,
    fabrica: Any = None,
    lancar: Any = None,
    rodar: Any = None,
) -> SourceVirtualPipeWire | None:
    """Sobe o canal deste controle, ou devolve o que já estava de pé."""
    nome = nome_do_canal(uniq)
    if not nome:
        logger.debug("canal_do_mic_sem_identidade", extra={"uniq": uniq})
        return None
    with _TRANCA:
        ja = _DE_PE.get(uniq)
        if ja is not None:
            return ja
        construir = fabrica or SourceVirtualPipeWire
        try:
            source = construir(nome=nome, descricao=descricao)
            source.controle = uniq
            if not source.iniciar():
                return None
        except Exception:
            logger.warning("canal_do_mic_nao_subiu", exc_info=True)
            return None
        _DE_PE[uniq] = source
        _FONTE_PEDIDA[uniq] = str(fonte or "")
        _passar_a_escolha_dela(uniq, nome)
        if not desmutar(nome, rodar=rodar):
            logger.warning("canal_do_mic_nasceu_mudo", extra={"source": nome})
        if fonte:
            alimentador = _Alimentador(uniq, fonte, source, lancar=lancar)
            if alimentador.iniciar():
                _ALIMENTANDO[uniq] = alimentador
        return source


def renomear(
    uniq: str,
    descricao: str,
    *,
    fabrica: Any = None,
    lancar: Any = None,
    rodar: Any = None,
) -> SourceVirtualPipeWire | None:
    """O canal deste controle RENASCE com o rótulo de agora.

    Devolve o canal que está DE PÉ agora — `None` = não há canal de pé.

    **O GÊMEO DO ALTO-FALANTE, e ele mentia PIOR** — medido na bancada em
    20/09/2026, com os quatro DualSense de pé e o daemon respondendo
    ``2, 4, 3, 1``::

        hefesto_mic_0000ab → «Microfone do Controle»    (sem número nenhum)
        hefesto_mic_0000f0 → «Microfone do Controle 2»  (o Player é 4)
        hefesto_mic_0000d8 → «Microfone do Controle 1»  (o Player é 3)
        hefesto_mic_000003 → «Microfone do Controle 3»  (o Player é 1)

    Três dos quatro errados, contra dois de quatro do lado da saída. A causa é
    a mesma e está escrita uma vez só, em
    :func:`~integrations.dualsense_bt_audio.rotulo_envelheceu`: o rótulo é a
    fotografia do assento de quando o nó nasceu, e **não há renomear no lugar**
    — o ``device.description`` de um ``module-pipe-source`` é fixado no
    ``load-module``. Renomear é republicar.

    **QUEM CHAMA É O DONO DO CANAL, e nunca um terceiro.** A tabela ``_DE_PE``
    é a única memória de quem abriu o quê; um canal republicado por quem não o
    abriu deixaria o dono anunciando de pé um objeto morto — é a mesma razão
    pela qual :meth:`PonteMicBluetooth._fechar_a_source` só fecha o que ela
    abriu. Por isso isto **devolve a source que ficou de pé**: quem guardava a
    velha troca a referência na mesma linha.

    **O ALIMENTADOR VOLTA PELA MESMA FONTE.** Ela é lida de
    :data:`_FONTE_PEDIDA`, não perguntada de novo a ``escolher_fonte`` — depois
    que o canal está no ar aquela função responde o PRÓPRIO canal (a regra 0),
    e reabrir por essa resposta poria o ``parec`` a ler o nó que ele mesmo
    enche. E não de :data:`_ALIMENTANDO`, pela razão escrita lá: o canal do
    cabo cujo ``parec`` não subiu renasceria MUDO.

    **O QUE O RETORNO QUER DIZER, e é UMA regra só:** é o canal que está DE PÉ
    agora para este ``uniq``. ``None`` quer dizer **não há canal de pé** — e
    nunca *"não fiz nada"*. Quem chama guarda a referência devolvida, sempre:
    o mesmo objeto quando o rótulo já estava certo, o objeto novo quando ele
    renasceu, o da VOLTA quando o renascimento não subiu, e ``None`` quando
    nem a volta subiu.

    A regra anterior — ``None`` = *"nada feito"* — foi medida pelo conferente
    em 20/09/2026 e é um defeito silencioso: ela obriga o dono a ficar com a
    referência que tinha, e a referência que ele tinha estava PARADA (o
    ``fechar`` abaixo já aconteceu). A ponte seguiria escrevendo PCM num nó
    morto — *"o microfone mudo com tudo aparentemente de pé"*.

    **E HÁ VOLTA.** Renomear é fechar e abrir, e entre os dois há uma janela em
    que o canal não existe. Se o ``abrir`` com o rótulo de agora não subir, o
    canal é reerguido com o rótulo que estava NO AR — desfazer, e não repetir
    o ato que acabou de falhar. Um rótulo velho é melhor que microfone nenhum.
    """
    with _TRANCA:
        ja = _DE_PE.get(uniq)
        fonte = _FONTE_PEDIDA.get(uniq) or None
    if ja is None:
        return None
    no_ar = str(getattr(ja, "descricao", "") or "")  # (noqa-acento) nome de atributo
    if not rotulo_envelheceu(no_ar, descricao):
        return ja
    logger.info(
        "canal_do_mic_rotulo_envelheceu",
        extra={"uniq": uniq, "de_agora": descricao},
    )
    fechar(uniq)
    novo = abrir(
        uniq, descricao, fonte=fonte, fabrica=fabrica, lancar=lancar, rodar=rodar
    )
    if novo is not None:
        return novo
    logger.warning(
        "canal_do_mic_nao_renasceu", extra={"uniq": uniq, "no_ar": no_ar}
    )
    de_volta = abrir(
        uniq, no_ar, fonte=fonte, fabrica=fabrica, lancar=lancar, rodar=rodar
    )
    if de_volta is None:
        logger.warning("canal_do_mic_sumiu_ao_renomear", extra={"uniq": uniq})
    return de_volta


def canal_de_pe(uniq: str) -> SourceVirtualPipeWire | None:
    """O canal DESTE controle que está de pé — `None` quando não há."""
    with _TRANCA:
        return _DE_PE.get(uniq)


def fechar(uniq: str) -> bool:
    """Derruba o canal deste controle. False = não havia nada de pé."""
    with _TRANCA:
        source = _DE_PE.pop(uniq, None)
        alimentador = _ALIMENTANDO.pop(uniq, None)
        _FONTE_PEDIDA.pop(uniq, None)
    if alimentador is not None:
        try:
            alimentador.parar()
        except Exception:
            logger.warning("canal_do_mic_alimentador_nao_parou", exc_info=True)
    if source is None:
        return False
    try:
        source.parar()
    except Exception:
        logger.warning("canal_do_mic_nao_parou", exc_info=True)
    return True


def de_pe() -> dict[str, str]:
    """`{uniq: nome do nó}` do que está publicado agora. Cópia, não a tabela."""
    with _TRANCA:
        return {uniq: source.nome for uniq, source in _DE_PE.items()}


def prioridade() -> int:
    """A `priority.session` do canal — a MESMA faixa do cabo, lida do dono."""
    return PRIORIDADE_SESSAO_DA_PONTE

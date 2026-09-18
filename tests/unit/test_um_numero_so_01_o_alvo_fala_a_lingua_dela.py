"""UM-NUMERO-SO-01 — o daemon e as lâmpadas param de discordar sobre quem é quem.

**A MEDIÇÃO QUE ORIGINOU ISTO, 18/09/2026, na mesa dela com os quatro
DualSense ligados pelo rádio.** Pintei um controle de cada cor pelo
``controller.target.set {index}`` e pedi a ela o que via. A resposta dela, e
o instrumento que lê ``/sys/class/leds/*:white:player-N`` depois, concordaram::

    índice do daemon   0=vermelho  1=azul   2=roxo   3=branco
    lâmpada acesa      2=vermelho  1=azul   3=roxo   4=branco

Duas listas sobre a mesma mesa. Quem traduzisse "o Controle 1 dela" para
``index=0`` mandaria a cor para o controle que acende **jogador 2**.

As três réguas deste arquivo travam as três pontas da cura, e cada uma MORDE:
a faixa sintética que morava na fila dela desde 22/08, o número que o
``controller.list`` não publicava, e a língua que o ``target.set`` não falava.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hefesto_dualsense4unix.core.faixa_sintetica import (
    FAIXAS_SINTETICAS,
    e_endereco_sintetico,
)
from hefesto_dualsense4unix.daemon.subsystems.identity import (
    KIND_DUALSENSE,
    ORDER_FIELD,
    merged_order_payload,
    order_entries,
)

#: A FAIXA DOS "REAIS" DESTA PROVA, e ela não podia ser a de fixture.
#:
#: Aqui há uma tensão que vale escrever: a régua de anonimato desta casa quer
#: endereço sintético em ``tests/``, e o produto agora EXPURGA endereço
#: sintético da fila. Um controle de prova escrito em ``aa:bb:cc`` seria comido
#: pela própria cura, e a régua mediria o nada.
#:
#: A saída é ``02:``, o bit localmente administrado: nenhum fabricante o usa,
#: então ele não identifica aparelho de ninguém — e ``scripts/check_endereco_de_radio``
#: o isenta por isso mesmo (``sintetico``: *"fabricado pelo driver"*). Do lado
#: do produto ele é um endereço como outro qualquer, que é o que a prova pede.
#: O ``02:fe:00`` do vpad fica de fora por três octetos.
_RAIZ = Path(__file__).resolve().parents[2]

_REAL = "02001a0000"


#: A fila EXATA que estava no ``controllers.json`` de produção dela em
#: 18/09/2026 — os fantasmas ficam como estavam, porque são o objeto da
#: medição. Os postos são os medidos: os reais em 1, 2, 3 e **8**.
_FILA_PODRE = {
    "version": 3,
    ORDER_FIELD: [
        {"addr": f"{_REAL}01", "kind": KIND_DUALSENSE, "rank": 1},
        {"addr": f"{_REAL}02", "kind": KIND_DUALSENSE, "rank": 2},
        {"addr": f"{_REAL}03", "kind": KIND_DUALSENSE, "rank": 3},
        {"addr": "aabbcc000001", "kind": KIND_DUALSENSE, "rank": 4},
        {"addr": "aabbcc000002", "kind": KIND_DUALSENSE, "rank": 5},
        {"addr": "aabbcc000003", "kind": KIND_DUALSENSE, "rank": 6},
        {"addr": "aabbcc000004", "kind": KIND_DUALSENSE, "rank": 7},
        {"addr": f"{_REAL}04", "kind": KIND_DUALSENSE, "rank": 8},
    ],
}


# ---------------------------------------------------------------------------
# PONTA 1 — a fila de fixture sai da máquina, e o gesto tem dono
# ---------------------------------------------------------------------------
# **A CURA RECUOU NO MESMO DIA, e o recuo é o achado.** A primeira versão
# descartava a faixa sintética dentro do `identity.order_entries` — a fonte
# única de leitura da fila —, e a suíte mediu o preço: VINTE E SETE réguas
# desta casa usam `aa:bb:cc` como endereço de controle de verdade, e 236
# arquivos de teste a citam. Expurgá-la no produto é uma regra sobre a NOSSA
# suíte, não sobre o aparelho; o único alcance universal é o do vpad
# (`02:fe`), que o `load` já recusava.
#
# O gesto ficou onde esta casa conserta máquina: `check_faixa_sintetica.py
# --limpar`, chamado pelo `doctor --fix`. O portão acusava desde 24/08 e não
# tinha como curar — `A-CASA-SABE-E-O-PRODUTO-NÃO-FAZ` na forma mais pura.


def test_o_dono_conhece_as_tres_faixas_nas_duas_grafias() -> None:
    assert FAIXAS_SINTETICAS == ("aabbcc", "02fe00", "e8473a")
    for faixa in FAIXAS_SINTETICAS:
        colada = f"{faixa}000001"
        separada = ":".join(colada[i : i + 2] for i in range(0, 12, 2))
        assert e_endereco_sintetico(colada), colada
        assert e_endereco_sintetico(separada.upper()), separada


def test_endereco_real_nunca_e_lixo() -> None:
    """Um DualSense que dormiu seis meses continua tendo lugar na fila."""
    for real in (f"{_REAL}01", f"{_REAL}fe", f"{_REAL}aa", f"{_REAL}bb"):
        assert not e_endereco_sintetico(real), real
    assert not e_endereco_sintetico("")
    assert not e_endereco_sintetico(None)


def test_o_produto_nao_expurga_a_faixa_na_leitura_da_fila() -> None:
    """O RECUO, travado: `order_entries` devolve tudo, inclusive a fixture.

    Esta régua existe para a próxima pessoa não refazer o caminho que a suíte
    já reprovou. Se um dia o expurgo voltar para dentro do produto, ela cai — e
    o vermelho é o aviso certo.
    """
    assert len(order_entries(_FILA_PODRE)) == 8
    payload = merged_order_payload(_FILA_PODRE, "external", {f"{_REAL}e1": 1})
    assert len([e for e in payload if e["kind"] == KIND_DUALSENSE]) == 8


def test_o_gesto_do_portao_tira_a_fixture_e_preserva_o_resto(tmp_path) -> None:
    """A CURA, onde ela ficou: um gesto explícito, com dono."""
    import json as _json
    import sys

    sys.path.insert(0, str(_RAIZ / "scripts"))
    from check_faixa_sintetica import limpar

    alvo = tmp_path / "controllers.json"
    alvo.write_text(_json.dumps(_FILA_PODRE), encoding="utf-8")

    relato = limpar(tmp_path)

    gravado = _json.loads(alvo.read_text(encoding="utf-8"))
    assert len(relato) == 4, relato
    assert len(gravado[ORDER_FIELD]) == 4
    assert not any(e_endereco_sintetico(e["addr"]) for e in gravado[ORDER_FIELD])
    assert gravado["version"] == _FILA_PODRE["version"], "o resto do documento mudou"


def test_o_gesto_nao_toca_arquivo_limpo(tmp_path) -> None:
    """Sem sujeira, nenhuma escrita: um os.replace por boot perde arquivo."""
    import json as _json
    import sys

    sys.path.insert(0, str(_RAIZ / "scripts"))
    from check_faixa_sintetica import limpar

    limpo = {
        "version": 3,
        ORDER_FIELD: [
            {"addr": f"{_REAL}0{n}", "kind": KIND_DUALSENSE, "rank": n}
            for n in (1, 2, 3)
        ],
    }
    alvo = tmp_path / "controllers.json"
    alvo.write_text(_json.dumps(limpo), encoding="utf-8")
    antes = alvo.stat().st_mtime_ns

    assert limpar(tmp_path) == []
    assert alvo.stat().st_mtime_ns == antes


def test_mordida_da_ponta_1_sem_o_gesto_a_fila_podre_fica(tmp_path) -> None:
    """Arranca o gesto: o arquivo continua com os oito, como estava na mesa dela."""
    import json as _json

    alvo = tmp_path / "controllers.json"
    alvo.write_text(_json.dumps(_FILA_PODRE), encoding="utf-8")
    gravado = _json.loads(alvo.read_text(encoding="utf-8"))
    assert len(gravado[ORDER_FIELD]) == 8, "a mordida não morde"


# ---------------------------------------------------------------------------
# PONTAS 2 e 3 — o número no `list`, e a língua dela no `target.set`
# ---------------------------------------------------------------------------


class _MesaDela:
    """A mesa MEDIDA: quatro controles, índice e jogador em ordens diferentes."""

    #: (uniq, índice do handle, lugar na fila de identidade)
    MESA = (
        (f"{_REAL}01", 0, 2),  # a casca vermelha: índice 0, jogador 2
        (f"{_REAL}02", 1, 1),  # a casca azul:     índice 1, jogador 1
        (f"{_REAL}03", 2, 3),
        (f"{_REAL}04", 3, 4),
    )

    def __init__(self) -> None:
        self.alvo: int | None = None

    def describe_controllers(self) -> list[dict[str, object]]:
        return [
            {"index": i, "uniq": u, "connected": True, "transport": "bt"}
            for u, i, _ in self.MESA
        ]

    def set_output_target(self, index: int | None) -> int | None:
        self.alvo = index
        return index


class _RegistroDaFila:
    def slot_for(self, uniq: str, *, assign: bool = True) -> int | None:
        for u, _, slot in _MesaDela.MESA:
            if u == uniq:
                return slot
        return None


@pytest.fixture
def handlers():
    """Os handlers com a mesa dela, sem daemon nem aparelho."""
    from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin

    class _Daemon:
        identity_registry = _RegistroDaFila()

    class _Handlers(IpcHandlersMixin):
        def __init__(self) -> None:
            self.controller = _MesaDela()
            self.daemon = _Daemon()

    return _Handlers()


@pytest.mark.asyncio
async def test_o_list_publica_o_mesmo_numero_que_a_lampada(handlers) -> None:
    """A PONTA 2: quem lê a lista vê o número, não só o índice."""
    r = await handlers._handle_controller_list({})
    por_indice = {c["index"]: c for c in r["controllers"]}
    assert por_indice[0]["numero"] == 2, "o índice 0 acende jogador 2 na mesa dela"
    assert por_indice[1]["numero"] == 1
    assert por_indice[2]["numero"] == 3
    assert por_indice[3]["numero"] == 4
    assert [c["player_slot"] for c in r["controllers"]] == [2, 1, 3, 4]


@pytest.mark.asyncio
async def test_mordida_da_ponta_2_o_indice_sozinho_mente(handlers) -> None:
    """Sem o carimbo, o único número publicado seria o índice — e ele mente.

    Esta régua é a razão de ser da ponta 2: ela AFIRMA a divergência. Se um
    dia o ``index`` passar a seguir a fila, ela reprova — e é o aviso certo,
    porque aí o carimbo virou redundância e a casa precisa saber.
    """
    r = await handlers._handle_controller_list({})
    indices_mais_um = [c["index"] + 1 for c in r["controllers"]]
    numeros = [c["numero"] for c in r["controllers"]]
    assert indices_mais_um != numeros, (
        "o índice passou a bater com o jogador: a tradução virou redundância"
    )


@pytest.mark.asyncio
async def test_o_alvo_aceita_o_numero_que_ela_ve(handlers) -> None:
    """A PONTA 3: «Controle 1» mira o controle que ACENDE 1, não o índice 0."""
    r = await handlers._handle_controller_target_set({"jogador": 1})
    assert handlers.controller.alvo == 1, "o jogador 1 é o índice 1 nesta mesa"
    assert r["target_index"] == 1


@pytest.mark.asyncio
async def test_o_alvo_aceita_o_endereco(handlers) -> None:
    await handlers._handle_controller_target_set({"uniq": "02:00:1A:00:00:01"})
    assert handlers.controller.alvo == 0


@pytest.mark.asyncio
async def test_o_indice_continua_valendo_byte_a_byte(handlers) -> None:
    """Ninguém que já falava por índice pode quebrar."""
    r = await handlers._handle_controller_target_set({"index": 3})
    assert handlers.controller.alvo == 3
    assert r == {"status": "ok", "target_index": 3}
    r = await handlers._handle_controller_target_set({"index": None})
    assert handlers.controller.alvo is None


@pytest.mark.asyncio
async def test_dois_alvos_juntos_recusam_em_vez_de_escolher(handlers) -> None:
    """Escolher em silêncio é como um clique dela vai parar no aparelho errado."""
    with pytest.raises(ValueError, match="UM alvo só"):
        await handlers._handle_controller_target_set({"index": 0, "jogador": 1})


@pytest.mark.asyncio
async def test_numero_fora_da_mesa_recusa_e_nao_pinta_os_quatro(handlers) -> None:
    """A recusa é a cura: cair no broadcast pintaria todos num gesto de um."""
    with pytest.raises(ValueError, match="não há Controle 9"):
        await handlers._handle_controller_target_set({"jogador": 9})
    assert handlers.controller.alvo is None, "o alvo não pode ter virado broadcast"


@pytest.mark.asyncio
async def test_endereco_fora_da_mesa_recusa(handlers) -> None:
    with pytest.raises(ValueError, match="não está na mesa"):
        await handlers._handle_controller_target_set({"uniq": f"{_REAL}99"})
    assert handlers.controller.alvo is None


def test_a_fila_podre_desta_regua_e_a_fila_medida() -> None:
    """Guarda de anonimato: a prova usa a faixa sintética, nunca o MAC dela."""
    from tests.unit.test_docs_mac_anonimato import _OUIS_COLADOS

    bruto = json.dumps(_FILA_PODRE).lower()
    for oui in _OUIS_COLADOS:
        assert oui not in bruto, f"OUI desta bancada na prova: {oui}"
    assert bruto.count("aabbcc") == 4, "os quatro fantasmas medidos, e só eles"
    assert bruto.count(_REAL) == 4, "os quatro reais, na faixa que não identifica"


# ---------------------------------------------------------------------------
# PONTA 4 — o roteador do BACKEND, que é onde a classe fecha
# ---------------------------------------------------------------------------
# Os nove chamadores de `_handle_for` são os atos de ÁUDIO por controle, e
# todos caíam no primário sem endereço — enquanto `led.set`, `rumble.set` e
# `trigger.*` obedeciam ao seletor. MEDIDO na mesa dela: `mic.set`,
# `mic.led.set` e `speaker.set` respondiam `ok` para o jogador 3 mexendo no 1.


class _BackendDeMentira:
    """O `_handle_for` real, com os handles e os locks de mentira."""

    def __init__(self) -> None:
        import threading

        self._io_lock = threading.Lock()
        self._handles = {"k1": "handle-do-1", "k2": "handle-do-2"}
        self._primary_key = "k1"
        self._output_target_key: str | None = None

    def _key_to_uniq(self, key: str) -> str:
        return {"k1": f"{_REAL}01", "k2": f"{_REAL}02"}[key]

    _handle_for = None  # preenchido abaixo


def _backend():
    from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController

    b = _BackendDeMentira()
    b._handle_for = PyDualSenseController._handle_for.__get__(b)  # type: ignore[method-assign]
    return b


def test_sem_endereco_e_sem_alvo_cai_no_primario() -> None:
    """O caso de quem tem um controle só — e ele NÃO pode mudar."""
    b = _backend()
    assert b._handle_for(None) == "handle-do-1"


def test_sem_endereco_o_alvo_de_saida_ganha_do_primario() -> None:
    """A CURA: apontar para o jogador 2 e mandar `mic.set` mexe no 2."""
    b = _backend()
    b._output_target_key = "k2"
    assert b._handle_for(None) == "handle-do-2"


def test_o_endereco_explicito_continua_vencendo_tudo() -> None:
    b = _backend()
    b._output_target_key = "k2"
    assert b._handle_for(f"{_REAL}01") == "handle-do-1"


def test_alvo_que_saiu_da_mesa_cai_no_primario_em_vez_de_sumir() -> None:
    """O controle apontado caiu do rádio: o ato vai para o primário, não some."""
    b = _backend()
    b._output_target_key = "k9-que-nao-existe"
    assert b._handle_for(None) == "handle-do-1"


def test_mordida_da_ponta_4_sem_o_alvo_o_ato_vai_para_o_primario() -> None:
    """Arranca a consulta ao alvo: volta o defeito medido na mesa dela."""
    b = _backend()
    b._output_target_key = "k2"
    # o que a versão de antes fazia, em duas linhas:
    antigo = b._handles.get(b._primary_key)
    assert antigo == "handle-do-1"
    assert b._handle_for(None) == "handle-do-2", "a cura não está no lugar"

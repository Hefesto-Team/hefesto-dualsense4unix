"""CONSERTO 1.7 — o ramo de compatibilidade com dente, e o doctor EXECUTADO.

Três defeitos, todos medidos por céticos independentes em 14/08/2026, e nenhum
deles no miolo da entrega MESA-CHEIA-11/E1 (que é boa):

**A — o ramo `conhece_a_mesa` não tinha mordida.** Em
`daemon/ipc_handlers.py`, o bloco::

    result["native_bt_fragil"] = bool(
        frageis if conhece_a_mesa
        else (result["native_mode"] and result["transport"] == "bt")
    )

O `else` é a REGRA ANTIGA — a que olha só o primário — e existe para o backend
que não sabe QUEM está na mesa (sem `describe_controllers`: o `FakeController`,
um `MagicMock`, um daemon de versão anterior). Dois céticos o arrancaram por
caminhos diferentes (`bool(frageis)` e `bool(frageis and conhece_a_mesa)`) e a
suíte inteira ficou verde nos dois: 105 e 109 testes passando com a regra
antiga no lixo. O comportamento estava CERTO; era a rede que não existia.

**B — o texto do doctor tinha plural fixo.** Com UM controle frágil ele
imprimia *"Modo Nativo com os Controles 3 em BLUETOOTH ... se o jogo não vir
esses controles"*. A janela, no mesmo estado, acerta (tem dois moldes). Para
quem tem um controle só no rádio — exatamente quem este aviso nasceu para
socorrer — a frase tinha PIORADO: antes da entrega era "o controle", singular
e correto.

**C — o teste do doctor era substring de fonte.** O antigo
`test_o_doctor_le_a_lista_nova` era `assert "native_bt_quais" in doctor`; um
cético arrancou a cura inteira do shell (o ramo que nomeia, a variável e o
`sed` que a extrai, deixando só o `print` do trecho python) e 722 testes
seguiram verdes, esse inclusive. É o anti-padrão que esta casa condenou POR
ESCRITO para ESTA MESMA flag, em
`docs/process/sprints/2026-07-31-TESTE-HONESTO-01-os-297-verdes-que-nao-medem-interface.md`
(linhas 155-161). Aqui o doctor é EXECUTADO: a função `check_dedup_ipc` sai do
`scripts/doctor.sh` por `awk` e roda contra um socket UNIX de mentira que fala
JSON-RPC — o mesmo desenho de `tests/unit/test_doctor_justworks_comportamento.py`.

Nada aqui abre janela nem toca hardware: os dois bancos são o handler IPC real
por socket e o shell real por subprocesso.
"""

from __future__ import annotations

import asyncio
import json
import socket
import subprocess
import threading
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.core.controller import ControllerState
from tests.conftest import arvore_congelada

# ---------------------------------------------------------------------------
# A — o ramo `conhece_a_mesa`, pelos DOIS lados, com IpcServer de verdade
# ---------------------------------------------------------------------------


def _estado_do_primario(transporte: str | None) -> ControllerState:
    """O `_last_state` do poll loop — é dele que sai `result["transport"]`."""
    return ControllerState(
        battery_pct=70,
        l2_raw=0,
        r2_raw=0,
        connected=transporte is not None,
        transport=transporte,  # type: ignore[arg-type]
    )


def _state_full(
    *,
    nativo: bool,
    transporte_do_primario: str | None,
    controllers: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """`daemon.state_full` por um IpcServer real; `controllers=None` = backend
    SEM `describe_controllers` (o caso que o ramo antigo protege)."""
    from hefesto_dualsense4unix.cli.ipc_client import IpcClient
    from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
    from hefesto_dualsense4unix.daemon.state_store import StateStore
    from hefesto_dualsense4unix.profiles.manager import ProfileManager
    from hefesto_dualsense4unix.testing import FakeController

    async def corpo(caminho: Path) -> dict[str, Any]:
        fc = FakeController(transport=transporte_do_primario or "usb")
        fc.connect()
        # O `FakeController` NÃO tem `describe_controllers` — é o backend que
        # não conhece a mesa. Só ganha o método quando o caso pede.
        assert not hasattr(FakeController, "describe_controllers"), (
            "o FakeController passou a descrever a mesa: este banco perdeu o "
            "único backend de teste que exercita o ramo de compatibilidade"
        )
        if controllers is not None:
            fc.describe_controllers = lambda: [dict(c) for c in controllers]  # type: ignore[attr-defined]
        store = StateStore()
        daemon = MagicMock()
        daemon._last_state = _estado_do_primario(transporte_do_primario)
        daemon.is_native_mode.return_value = nativo
        daemon.is_paused.return_value = False
        server = IpcServer(
            controller=fc,
            store=store,
            profile_manager=ProfileManager(controller=fc, store=store),
            socket_path=caminho,
            daemon=daemon,
        )
        await server.start()
        try:
            async with IpcClient.connect(caminho) as client:
                resultado = await client.call("daemon.state_full")
        finally:
            await server.stop()
        assert isinstance(resultado, dict)
        return resultado

    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        return asyncio.run(corpo(Path(tmp) / "hefesto.sock"))


#: Mesa CONHECIDA e inteira no cabo. O `transport` do topo (o do primário) vem
#: em "bt" de propósito: é o discriminante entre "a lista manda" e "a regra
#: antiga manda". Com a mesa conhecida, ninguém é frágil — e o aviso CALA.
MESA_TODA_NO_CABO = [
    {"index": 0, "connected": True, "transport": "usb",
     "is_primary": True, "uniq": "aabbcc0000d8"},
    {"index": 1, "connected": True, "transport": "usb",
     "is_primary": False, "uniq": "aabbcc000003"},
]

#: Mesa conhecida como LISTA, mas sem ninguém conectado — é a mesa que o daemon
#: enxerga entre a desconexão e a próxima varredura.
MESA_TODA_OFFLINE = [
    {"index": 0, "connected": False, "transport": None,
     "is_primary": True, "uniq": "aabbcc0000d8"},
]


class TestORamoDaMesaDesconhecida:
    """A regra ANTIGA (só o primário) sobrevive para quem não conhece a mesa."""

    def test_sem_describe_controllers_o_primario_em_bt_ainda_acende(self) -> None:
        """A MORDIDA que faltava: `bool(frageis)` deixava isto MUDO.

        Backend sem `describe_controllers` + Modo Nativo + primário no rádio: a
        lista de frágeis é vazia porque não há mesa para varrer, e é a regra
        antiga que tem de acender a flag. A lista sai `[]` DE PROPÓSITO — a
        janela cai no texto genérico em vez de nomear um controle que ninguém
        sabe qual é.
        """
        resultado = _state_full(
            nativo=True, transporte_do_primario="bt", controllers=None
        )

        assert "controllers" not in resultado, (
            "o backend deste caso não pode descrever a mesa — se descreve, o "
            "teste deixou de exercitar o ramo de compatibilidade"
        )
        assert resultado["transport"] == "bt"
        assert resultado["native_bt_fragil_controles"] == []
        assert resultado["native_bt_fragil"] is True, (
            "o aviso de BT frágil SUMIU para backend que não conhece a mesa — "
            "é a regra antiga (só o primário) arrancada, a mutação que dois "
            "céticos passaram sem que um teste reclamasse em 14/08/2026"
        )

    def test_sem_describe_controllers_o_primario_no_cabo_cala(self) -> None:
        """O outro lado do mesmo ramo: no cabo não há fragilidade a avisar."""
        resultado = _state_full(
            nativo=True, transporte_do_primario="usb", controllers=None
        )

        assert resultado["native_bt_fragil_controles"] == []
        assert resultado["native_bt_fragil"] is False

    def test_sem_describe_controllers_fora_do_modo_nativo_cala(self) -> None:
        """Fora do Modo Nativo o jogo vê o gamepad virtual — nada a avisar.

        Guarda a metade `native_mode` da regra antiga: sem ela, quem usa a
        emulação com o controle no rádio levaria um susto que não é dele.
        """
        resultado = _state_full(
            nativo=False, transporte_do_primario="bt", controllers=None
        )

        assert resultado["native_bt_fragil"] is False

    def test_a_mesa_conhecida_manda_mais_que_o_transporte_do_topo(self) -> None:
        """Quem conhece a mesa NÃO consulta a regra antiga.

        Este é o caso que separa `frageis if conhece_a_mesa else (...)` de um
        `frageis or (...)`: a mesa está inteira no cabo, então o aviso cala —
        mesmo com o `transport` do topo dizendo "bt". Se o `or` entrasse no
        lugar do `if/else`, a mesa toda no cabo acenderia um aviso falso.
        """
        resultado = _state_full(
            nativo=True, transporte_do_primario="bt", controllers=MESA_TODA_NO_CABO
        )

        assert [c["transport"] for c in resultado["controllers"]] == ["usb", "usb"]
        assert resultado["transport"] == "bt", "o topo é o do primário, e mente aqui"
        assert resultado["native_bt_fragil_controles"] == []
        assert resultado["native_bt_fragil"] is False, (
            "a lista por controle diz que ninguém está no rádio; o transporte "
            "do topo não pode passar por cima dela"
        )

    def test_lista_sem_ninguem_conectado_volta_para_a_regra_antiga(self) -> None:
        """Uma lista VAZIA de gente não é uma mesa conhecida.

        Guarda a definição de `conhece_a_mesa` (`any(... connected)`): trocá-la
        por um mero `isinstance(entradas, list)` faria o aviso apagar toda vez
        que a varredura chegasse antes da conexão.
        """
        for mesa in (MESA_TODA_OFFLINE, []):
            resultado = _state_full(
                nativo=True, transporte_do_primario="bt", controllers=mesa
            )
            assert resultado["native_bt_fragil_controles"] == []
            assert resultado["native_bt_fragil"] is True, (
                f"mesa {mesa!r} não diz quem está no rádio — quem responde "
                "ainda é a regra antiga, e ela diz que o primário está em BT"
            )


# ---------------------------------------------------------------------------
# B e C — o doctor EXECUTADO contra um socket de mentira
# ---------------------------------------------------------------------------

RAIZ = arvore_congelada()
DOCTOR = RAIZ / "scripts" / "doctor.sh"
FUNCAO = "check_dedup_ipc"


def _extrair_funcao() -> str:
    """A função tal como está no `doctor.sh` de hoje — nunca uma cópia.

    Extração por `awk`, como em `test_doctor_justworks_comportamento.py`: se
    alguém renomear `check_dedup_ipc`, o harness não a acha e TODOS os testes
    deste bloco ficam vermelhos. Renomear não é rota de fuga.
    """
    proc = subprocess.run(
        [
            "awk",
            f"/^{FUNCAO}\\(\\) \\{{/ {{ dentro = 1 }} dentro {{ print }} "
            "dentro && /^\\}$/ { exit }",
            str(DOCTOR),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    corpo = proc.stdout
    assert corpo.startswith(f"{FUNCAO}() {{"), (
        f"não achei a função {FUNCAO} em {DOCTOR} — se ela foi renomeada, o "
        "aviso de BT frágil do doctor perdeu a bancada que o exercita"
    )
    assert corpo.rstrip().endswith("}"), "a extração da função não fechou"
    return corpo


class _DaemonDeMentira:
    """Socket UNIX que responde UM `daemon.state_full` e morre.

    Não é dublê do doctor: é dublê do DAEMON. O trecho python embutido no
    `doctor.sh` roda de verdade, com o `sendall`/`recv` dele, e o shell de
    verdade fatia a saída com os `sed` dele.
    """

    def __init__(self, caminho: Path, payload: dict[str, Any]) -> None:
        self.caminho = caminho
        self.payload = payload
        self._srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._srv.bind(str(caminho))
        self._srv.listen(4)
        # Espera CURTA no accept, com bandeira: um `settimeout` longo faria o
        # `join` do encerramento pendurar a bancada por segundos a cada caso.
        self._srv.settimeout(0.1)
        self._parar = threading.Event()
        self._thread = threading.Thread(target=self._servir, daemon=True)

    def _servir(self) -> None:
        while not self._parar.is_set():
            try:
                conexao, _ = self._srv.accept()
            except TimeoutError:
                continue
            except OSError:
                return
            with conexao:
                conexao.settimeout(10.0)
                try:
                    pedido = b""
                    while not pedido.endswith(b"\n"):
                        pedaco = conexao.recv(65536)
                        if not pedaco:
                            break
                        pedido += pedaco
                    resposta = {
                        "jsonrpc": "2.0",
                        "id": json.loads(pedido or b"{}").get("id", 1),
                        "result": self.payload,
                    }
                    conexao.sendall(json.dumps(resposta).encode("utf-8") + b"\n")
                except OSError:
                    return

    def __enter__(self) -> _DaemonDeMentira:
        self._thread.start()
        return self

    def __exit__(self, *_: object) -> None:
        self._parar.set()
        self._thread.join(timeout=5.0)
        self._srv.close()


def _rodar_doctor(tmp_path: Path, payload: dict[str, Any]) -> str:
    """Executa `check_dedup_ipc` do doctor.sh contra o daemon de mentira."""
    sock = tmp_path / "hefesto.sock"
    script = tmp_path / "harness.sh"
    script.write_text(
        "#!/usr/bin/env bash\n"
        "set -uo pipefail\n"
        "pass() { printf '[ OK ] %s\\n' \"$*\"; }\n"
        "fail() { printf '[FAIL] %s\\n' \"$*\"; }\n"
        "warn() { printf '[WARN] %s\\n' \"$*\"; }\n"
        "info() { printf '       %s\\n' \"$*\"; }\n"
        f"runtime_socket() {{ printf '%s\\n' '{sock}'; }}\n"
        + _extrair_funcao()
        + f"\n{FUNCAO}\n",
        encoding="utf-8",
    )
    with _DaemonDeMentira(sock, payload):
        proc = subprocess.run(
            ["bash", str(script)], capture_output=True, text=True, timeout=60
        )
    assert proc.returncode == 0, f"o harness do doctor caiu: {proc.stderr}"
    assert "IPC não respondeu" not in proc.stdout, (
        f"o doctor não conseguiu falar com o daemon de mentira: {proc.stdout}"
    )
    return proc.stdout


def _payload(
    *, fragil: bool, quais: list[int] | None, emulacao: bool = False
) -> dict[str, Any]:
    corpo: dict[str, Any] = {
        "native_bt_fragil": fragil,
        "gamepad_emulation": {"enabled": emulacao, "dedup_ok": None, "dedup_motivo": ""},
    }
    if quais is not None:
        corpo["native_bt_fragil_controles"] = quais
    return corpo


class TestODoctorFalaDoBtFragilDeVerdade:
    """O doctor EXECUTADO — não o fonte do doctor lido como texto."""

    def test_um_fragil_sai_no_singular(self, tmp_path: Path) -> None:
        """O DEFEITO B: "com os Controles 3 ... esses controles", plural para um.

        Quem tem um controle só no rádio é justamente quem este aviso nasceu
        para socorrer, e para ela a frase tinha REGREDIDO — antes da entrega o
        doctor dizia "o controle", singular e correto.
        """
        saida = _rodar_doctor(tmp_path, _payload(fragil=True, quais=[3]))

        assert "o Controle 3 em BLUETOOTH" in saida, saida
        assert "esse controle" in saida
        assert "os Controles" not in saida, (
            "plural mecânico: um controle frágil não são 'os Controles'"
        )
        assert "esses controles" not in saida

    def test_varios_frageis_saem_no_plural_e_com_a_grafia_da_janela(
        self, tmp_path: Path
    ) -> None:
        """"2, 3 e 4" — a mesma grafia da janela, não "2, 3, 4"."""
        saida = _rodar_doctor(tmp_path, _payload(fragil=True, quais=[2, 3, 4]))

        assert "os Controles 2, 3 e 4 em BLUETOOTH" in saida, saida
        assert "esses controles" in saida
        assert "2, 3, 4" not in saida, (
            "a mesma mesa escrita de dois jeitos em duas telas da mesma casa"
        )

    def test_daemon_antigo_sem_a_lista_cai_no_texto_generico(
        self, tmp_path: Path
    ) -> None:
        """Sem `native_bt_fragil_controles` o aviso sai, mas sem nomear."""
        saida = _rodar_doctor(tmp_path, _payload(fragil=True, quais=None))

        assert "[WARN]" in saida
        assert "com o controle em BLUETOOTH" in saida, saida
        assert "Controles" not in saida

    def test_lista_suja_nao_vira_frase_torta(self, tmp_path: Path) -> None:
        """Payload com lixo (booleano, texto, nulo) não pode nomear "True"."""
        saida = _rodar_doctor(
            tmp_path, _payload(fragil=True, quais=[True, "dois", None])
        )

        assert "[WARN]" in saida
        assert "com o controle em BLUETOOTH" in saida, saida
        assert "True" not in saida

    def test_sem_fragilidade_o_doctor_nao_inventa_aviso(self, tmp_path: Path) -> None:
        saida = _rodar_doctor(tmp_path, _payload(fragil=False, quais=[]))

        assert "BLUETOOTH" not in saida, saida


# ---------------------------------------------------------------------------
# A mesa REAL — os dois bancos atravessados pela captura de 14/08/2026
# ---------------------------------------------------------------------------

#: `tests/fixtures/state_full_quatro_controles.json`: payload REAL, com quatro
#: controles na mesa (dois no cabo, dois no rádio), capturado com a mesa cheia.
#: É a única mesa desta casa em que `player_slot` NÃO é `index + 1` — o handle
#: 2 é o Controle 3 e o handle 3 é o Controle 2 —, e por isso é a única capaz de
#: separar "o número que a jogadora vê" de "a ordem em que o kernel abriu".
MESA_REAL: dict[str, Any] = json.loads(
    (
        Path(__file__).resolve().parents[1]
        / "fixtures"
        / "state_full_quatro_controles.json"
    ).read_text(encoding="utf-8")
)


class TestAMesaDeVerdadeAtravessaOsDoisBancos:
    """A captura real, do `controles_bt_frageis` até a frase do doctor."""

    def test_a_captura_nomeia_os_dois_do_radio_pelo_numero_da_jogadora(
        self, tmp_path: Path
    ) -> None:
        """Handles 2 e 3, Controles 3 e 2 — e a frase tem de dizer "2 e 3".

        Contra a mesa real, trocar `player_slot` pelo `index + 1` nomearia
        "Controles 3 e 4": dois cards que existem na fileira e NÃO são os que
        estão no rádio. Nenhum dublê escrito à mão pega isso, porque em todos
        eles `player_slot` é ausente e o índice acerta por coincidência.

        Aqui a régua é a função pura, e não o `IpcServer`, por medição e não
        por gosto: atravessando o servidor com um `daemon` dublado o registry
        não tem sessão nenhuma, `_player_slot_for` devolve `None` (NUMA-05,
        "null honesto > número errado") e a numeração cai no `index + 1` — a
        lista sairia `[3, 4]` por artefato da bancada, não do produto.
        """
        from hefesto_dualsense4unix.daemon.ipc_handlers import controles_bt_frageis

        controllers = MESA_REAL["controllers"]
        assert [c["transport"] for c in controllers] == ["usb", "usb", "bt", "bt"]
        assert [c["player_slot"] for c in controllers] == [4, 1, 3, 2]
        assert MESA_REAL["transport"] == "usb", "o primário desta mesa está no cabo"

        frageis = controles_bt_frageis(controllers, native_mode=True)
        assert frageis == [2, 3], (
            "os dois no rádio são os Controles 3 e 2 (handles 2 e 3), e a "
            "frase os lê em ordem crescente"
        )
        # A régua do defeito E1 na mesa REAL: a regra antiga olha o transporte
        # do primário, que aqui é "usb" — ela calaria para os dois no rádio.
        regra_antiga = MESA_REAL["transport"] == "bt"
        assert regra_antiga is False, "a flag velha calaria nesta mesa"

        saida = _rodar_doctor(tmp_path, _payload(fragil=True, quais=frageis))

        assert "os Controles 2 e 3 em BLUETOOTH" in saida, saida
        assert "esses controles" in saida
        assert "2, 3" not in saida, "dois controles se juntam com 'e', sem vírgula"


@pytest.mark.parametrize(
    "trecho",
    [
        "native_bt_fragil_controles",  # a chave que ele lê do daemon
        "native_bt_quantos",  # o contador que escolhe o molde
    ],
)
def test_o_doctor_ainda_le_a_lista_e_conta(trecho: str) -> None:
    """Rede de segurança do RENOME, e só isso — a prova é a execução acima.

    Este assert de fonte existe para dar uma mensagem legível quando alguém
    renomear a chave do contrato IPC; ele NÃO é a mordida (TESTE-HONESTO-01:
    substring de fonte sobrevive à cura arrancada, e sobreviveu, em 14/08).
    """
    assert trecho in DOCTOR.read_text(encoding="utf-8")

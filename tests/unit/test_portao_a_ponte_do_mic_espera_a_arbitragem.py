"""O portão 5.b — a ponte do mic não ganha porta nova antes da arbitragem.

QUATRO-MICROFONES-01/E3, 25/08/2026. **Este portão é a régua que o
`O-QUE-FICOU-ABERTO-01` tabelou em 16/08 e que ninguém escreveu.** A linha dele,
textual: *"`bt_mic_enabled` não ganha escritor antes de 5.a"*.

O QUE ELE VIGIA, E POR QUE NÃO É "A ENTREGA DE 22/08 ERA ERRADA"
----------------------------------------------------------------
O 5.b **já foi violado uma vez**, e de propósito: em 22/08 ela pediu o
interruptor por controle, ele foi entregue, e o preço — o pré-requisito 5.a —
não estava na mesa. A nota datada de 23/08 no topo da sprint registra isso, e a
decisão de manter a entrega é dela. **Um portão que reprovasse essa entrega
seria um portão vermelho todo dia, e portão vermelho todo dia é portão que
alguém apaga na segunda-feira** — é o argumento medido do
`portao_a_casa_sabe_e_o_produto_nao_faz`, e ele vale aqui.

Então o que este portão faz é o que ainda dá para fazer com honestidade:
**congela o tamanho da dívida.** Enquanto a arbitragem não existir, as portas de
produção que sobem a ponte são EXATAMENTE as declaradas aqui, cada uma com
razão e data. A terceira porta reprova. A janela alcançando a ponte reprova. E o
dia em que a arbitragem chegar, ele reprova também — para o registro sair daqui
em vez de apodrecer verde.

AS TRÊS MEDIÇÕES, e nenhuma delas é uma frase
----------------------------------------------
1. **A arbitragem existe?** Medida no COMPORTAMENTO do `BrokerState` real: duas
   conexões pedem `open` do MESMO nó. Hoje as duas são servidas com um fd cru e
   nada na resposta as distingue — `_cmd_open` diz, textual, que *"`open` NÃO
   altera lease/refcount"*. A régua sabe dizer "existe" também: ela é exercida
   contra um broker dublê que RECUSA o segundo pedido (armadilha A2 — régua que
   só sabe passar não é régua).
2. **Quantas portas sobem a ponte?** Varredura de AST sobre `src/`: quem importa
   de `integrations.dualsense_bt_audio` um nome que ABRE o hidraw e escreve
   `0x32`. Constante de protocolo e leitor não contam — `backend_pydualsense`
   importa três flags de status e não sobe ponte nenhuma.
3. **A janela alcança a ponte?** Nenhum módulo de `app/` pode importar um desses
   nomes. É a promessa que a docstring de
   `secao_controles._ao_alternar_o_microfone` faz — *"o processo da janela não
   pode ter esse gesto ao alcance de um clique enquanto a posse do hidraw não
   for arbitrada"* — e uma promessa em docstring não tem quem a cobre.

COMO MORDE (exercido em 25/08/2026)
------------------------------------
* acrescente `GerenciadorMicBluetooth` ao import de qualquer módulo de `src/`
  fora da lista -> `test_a_ponte_nao_ganhou_porta_nova` reprova nomeando-o;
* acrescente-o a um módulo de `app/` -> `test_a_janela_nao_alcanca_a_ponte`
  reprova;
* apague uma porta declarada sem tirá-la da lista -> reprova, porque a lista é
  IGUALDADE, não continência: dívida que sumiu tem de sair do registro.
"""
from __future__ import annotations

import ast
import os
from pathlib import Path
from typing import Any

SRC = Path(__file__).resolve().parents[2] / "src" / "hefesto_dualsense4unix"
MODULO_DA_PONTE = "hefesto_dualsense4unix.integrations.dualsense_bt_audio"

#: Os nomes que ABREM o hidraw em RDWR e/ou escrevem o report `0x32`. Importar
#: um destes é "poder subir a ponte"; importar `INPUT_FLAG_AUDIO` não é.
_QUEM_SOBE_A_PONTE = frozenset(
    {"GerenciadorMicBluetooth", "PonteMicBluetooth", "abrir_hidraw_rw"}
)

#: AS PORTAS DECLARADAS — o tamanho da dívida, congelado em 25/08/2026.
#: Caminho relativo a `src/hefesto_dualsense4unix` -> por que ela existe.
_PORTAS_DECLARADAS: dict[str, str] = {
    "daemon/subsystems/bt_mic.py": (
        "a porta do PRODUTO. Gate: `DaemonConfig.bt_mic_uniqs` (o que ela ligou "
        "no card, via `maquina.json`) ou `HEFESTO_DUALSENSE4UNIX_BT_MIC=1`. "
        "Entrou em 22/08/2026 a pedido dela, e o preço 5.a não estava na mesa — "
        "ver a nota datada de 23/08 no topo da sprint QUATRO-MICROFONES-01."
    ),
    "cli/cmd_mic.py": (
        "a porta À MÃO (`mic bt`). Desde 25/08/2026 ela ARBITRA na entrada: lê "
        "`daemon.state_full` -> `bt_mic.uniqs` e não sobe ponte em cima de quem "
        "já tem uma. Fecha o sentido CLI -> daemon; o outro sentido é o 5.a."
    ),
}

#: O módulo da própria ponte não é porta: ele É a ponte.
_A_PROPRIA_PONTE = "integrations/dualsense_bt_audio.py"


# ---------------------------------------------------------------------------
# Medição 1 — a arbitragem do nó existe?
# ---------------------------------------------------------------------------


class _OpsQueAbre:
    """Dublê de fs cujo `open_node` abre um arquivo comum REAL (fd de verdade)."""

    def __init__(self, alvo: str) -> None:
        self.alvo = alvo

    def hide(self, node: str, base: str) -> None:  # pragma: no cover - não usado
        pass

    def restore(self, node: str, base: str, uid: int) -> None:  # pragma: no cover
        pass

    def is_exposed_to(self, node: str, uid: int) -> bool:  # pragma: no cover
        return True

    def open_node(self, node: str, base: str) -> int:
        return os.open(self.alvo, os.O_RDONLY | os.O_CLOEXEC)


def _broker_de_bancada(tmp_path: Path) -> Any:
    from hefesto_dualsense4unix.broker.hidraw_broker import BrokerState

    alvo = tmp_path / "no-de-bancada"
    alvo.write_bytes(b"reports")
    return BrokerState(
        allowed_uid=1000,
        ops=_OpsQueAbre(str(alvo)),
        validator=lambda no: "hidraw9" if no.endswith("hidraw9") else None,
        log=lambda *a, **k: None,
        sleep_fn=lambda _s: None,
    )


def arbitragem_do_no(estado: Any) -> bool:
    """MEDE, no comportamento: o segundo pedido do mesmo nó é arbitrado?

    Duas conexões DIFERENTES pedem `open` do mesmo nó. É arbitrado quando o
    segundo **não** volta como um fd cru indistinguível do primeiro: recusado,
    sem fd, ou com a resposta carregando algo que o primeiro não tinha (um dono,
    uma marca de multiplexação).

    O LIMITE DA RÉGUA, declarado: ela não sabe o nome que a arbitragem futura vai
    dar à sua chave, então usa a FORMA da resposta. Uma chave nova por outro
    motivo a faria dizer "existe" — e o portão reprova pedindo que alguém leia.
    """
    pedido = b'{"cmd": "open", "node": "/dev/hidraw9"}\n'
    fds: list[int] = []
    try:
        r1, fd1 = estado.handle_line(1, 1000, pedido)
        if fd1 is not None:
            fds.append(fd1)
        r2, fd2 = estado.handle_line(2, 1000, pedido)
        if fd2 is not None:
            fds.append(fd2)
    finally:
        for fd in fds:
            os.close(fd)
    servido_cru = bool(r2.get("ok")) and fd2 is not None and set(r2) == set(r1)
    return not servido_cru


class _BrokerQueArbitra:
    """Dublê de broker COM arbitragem — a régua tem de saber dizer "existe"."""

    def __init__(self) -> None:
        self._dono: int | None = None

    def handle_line(
        self, conn_id: int, _uid: int, _linha: bytes
    ) -> tuple[dict[str, object], int | None]:
        if self._dono is not None and self._dono != conn_id:
            return ({"ok": False, "cmd": "open", "error": "reject_node_em_uso"}, None)
        self._dono = conn_id
        return ({"ok": True, "cmd": "open", "node": "/dev/hidraw9"}, None)


def test_a_regua_da_arbitragem_sabe_dizer_que_existe():
    """Armadilha A2: régua que só sabe passar não é régua."""
    assert arbitragem_do_no(_BrokerQueArbitra()) is True


def test_a_arbitragem_do_no_ainda_nao_existe(tmp_path):
    """A dívida 5.a, medida no comportamento do broker REAL — não por grep.

    Quando esta linha ficar vermelha, a arbitragem chegou: feche o 5.a no
    `O-QUE-FICOU-ABERTO-01`, tire o registro `_PORTAS_DECLARADAS` daqui e apague
    este arquivo. Um portão que sobrevive à dívida que vigia vira mobília.
    """
    assert arbitragem_do_no(_broker_de_bancada(tmp_path)) is False, (
        "o broker passou a arbitrar o segundo `open` do mesmo nó — o portão 5.a "
        "existe. Este portão cumpriu o papel dele e sai; ver a docstring."
    )


# ---------------------------------------------------------------------------
# Medição 2 e 3 — quem pode subir a ponte
# ---------------------------------------------------------------------------


def _portas_de(raiz: Path) -> dict[str, set[str]]:
    """Módulos que importam de `dualsense_bt_audio` um nome que SOBE a ponte."""
    achadas: dict[str, set[str]] = {}
    for arquivo in sorted(raiz.rglob("*.py")):
        try:
            arvore = ast.parse(arquivo.read_text(encoding="utf-8"), filename=str(arquivo))
        except SyntaxError:  # pragma: no cover - árvore quebrada é outro portão
            continue
        nomes: set[str] = set()
        for no in ast.walk(arvore):
            if isinstance(no, ast.ImportFrom) and no.module == MODULO_DA_PONTE:
                nomes |= {a.name for a in no.names} & _QUEM_SOBE_A_PONTE
        if nomes:
            achadas[arquivo.relative_to(SRC).as_posix()] = nomes
    return achadas


def test_a_ponte_nao_ganhou_porta_nova():
    """5.b: enquanto o 5.a não existir, as portas são EXATAMENTE as declaradas."""
    achadas = {k: v for k, v in _portas_de(SRC).items() if k != _A_PROPRIA_PONTE}
    novas = sorted(set(achadas) - set(_PORTAS_DECLARADAS))
    sumidas = sorted(set(_PORTAS_DECLARADAS) - set(achadas))
    assert not novas, (
        "PORTA NOVA para a ponte do microfone, e a arbitragem do hidraw (portão "
        f"5.a) não existe: {', '.join(novas)}.\n"
        "Duas portas no mesmo controle são dois donos da sequência do report "
        "0x32 — o quadro do estudo 2026-08-16-O-PS-PRESO. Se a porta é "
        "deliberada, ela entra em `_PORTAS_DECLARADAS` com razão e data, e o "
        "preço vai à mesa dela antes."
    )
    assert not sumidas, (
        f"porta declarada que não existe mais: {', '.join(sumidas)}. Dívida que "
        "sumiu sai do registro — senão o próximo a ler paga por um risco que já "
        "não corre."
    )


def test_a_janela_nao_alcanca_a_ponte():
    """A promessa que a docstring de `_ao_alternar_o_microfone` faz, cobrada.

    O processo da janela não pode ter o gesto de abrir o hidraw ao alcance de um
    clique enquanto a posse não for arbitrada. A janela DECLARA no
    `maquina.json`; quem sobe a ponte é o daemon.
    """
    dentro_da_janela = sorted(
        caminho for caminho in _portas_de(SRC / "app")
    )
    assert not dentro_da_janela, (
        "a JANELA passou a alcançar a ponte do microfone: "
        f"{', '.join(dentro_da_janela)}.\n"
        "A janela declara no `maquina.json` e o daemon é quem sobe — é o que "
        "mantém o gesto fora do processo que ela clica."
    )


def test_as_portas_declaradas_existem_no_disco():
    """Registro com caminho podre é registro que ninguém confere."""
    faltando = [p for p in _PORTAS_DECLARADAS if not (SRC / p).is_file()]
    assert not faltando, f"caminho declarado inexistente: {', '.join(faltando)}"

"""O «Reconectar controles» mexe no RÁDIO — ordem dela, 22/09/2026.

**A PALAVRA DELA:** *"pera o reconectar deveria sim tocar no radio. não faz
sentido ele ficar de fora."* <!-- noqa-acento: citação literal dela -->

Ela revoga a regra de 12/08 que o módulo carregava — *"Não reconectar é decisão
dela; o botão PS é dela"* —, e o dia mediu por quê: a mesa dela caiu num estado
em que o BlueZ dizia `Connected: true` para os quatro controles com o kernel
**sem HID nenhum deles**. O botão PS não resolve esse estado, porque para o
rádio já está tudo certo; quem destrava é derrubar o elo morto.

O QUE ESTA RÉGUA COBRA:

1. o elo morto cai e o controle é chamado de volta (`reconectar`);
2. o `Connect` recusado vira *"aperte PS"*, e não *"não deu"* — um DualSense
   dormindo não atende chamado, e isso foi medido no mesmo dia
   (`br-connection-create-socket`, três vezes);
3. **quem está na mesa não é tocado** — mexer no rádio de quem está jogando
   seria trocar um problema que não existe por três segundos sem controle;
4. **A SUÍTE NÃO FALA COM O RÁDIO DELA.** Esta é a régua do estrago do dia: o
   passo nasceu sem guarda e a primeira corrida de 457 testes derrubou os
   QUATRO DualSense da mesa dela, ao vivo.
"""

from __future__ import annotations

import sys
from typing import Any

from hefesto_dualsense4unix.integrations import bluez_dbus
from hefesto_dualsense4unix.integrations import gesto_de_reconexao as radio

#: A faixa sintética da casa — octetos 4 e 5 zerados.
P1 = "aa:bb:cc:00:00:01"
P2 = "aa:bb:cc:00:00:02"

_CAMINHO = "/org/bluez/hci0/dev_AA_BB_CC_00_00_02"


class _Bus:
    """O `busctl` de mentira: sabe a árvore, as propriedades e as chamadas."""

    def __init__(self, *, conectado: str = "true", connect_ok: bool = True) -> None:
        self.conectado = conectado
        self.connect_ok = connect_ok
        self.chamadas: list[str] = []

    def __call__(self, argumentos: Any) -> str | None:
        args = list(argumentos)
        if args[0] == "tree":
            return f"{_CAMINHO}\n/org/bluez/hci0/dev_AA_BB_CC_00_00_09\n"
        if args[0] == "get-property" and args[-1] == "Connected":
            return f"b {self.conectado}"
        if args[0] == "get-property" and args[-1] == "Modalias":
            if args[2] == _CAMINHO:
                return 's "usb:v054Cp0CE6d0100"'
            return 's "usb:v046DpC52Bd0100"'  # um receptor qualquer, não-DualSense
        if args[0] == "call":
            self.chamadas.append(args[-1])
            if args[-1] == "Connect" and not self.connect_ok:
                return None
            return ""
        return None


# ---------------------------------------------------------------------------
# 1 e 2. os dois passos, e o que cada desfecho diz
# ---------------------------------------------------------------------------
def test_o_elo_morto_cai_e_o_controle_e_chamado_de_volta() -> None:
    """MORDIDA: tire o `Disconnect` de `reconectar` — a chamada some da lista.

    A ORDEM IMPORTA: um `Connect` por cima do elo morto responde *"já está
    conectado"* e não levanta sessão de entrada nenhuma. Medido na mesa dela,
    quatro vezes, com o kernel sem HID o tempo todo.
    """
    bus = _Bus(conectado="true")
    desfecho = radio.reconectar(P2, executar=bus)

    assert bus.chamadas == ["Disconnect", "Connect"], bus.chamadas
    assert desfecho.estado == radio.ESTADO_VOLTOU
    assert desfecho.endereco == radio.mascarar(P2)


def test_o_controle_fora_do_radio_nao_leva_disconnect() -> None:
    """Quem já está fora só precisa ser chamado — derrubar o que não está de pé
    gastaria um `busctl` para não fazer nada."""
    bus = _Bus(conectado="false")
    desfecho = radio.reconectar(P2, executar=bus)

    assert bus.chamadas == ["Connect"], bus.chamadas
    assert desfecho.estado == radio.ESTADO_VOLTOU


def test_o_connect_recusado_devolve_o_ps_para_ela() -> None:
    """Um DualSense dormindo não atende chamado — medido em 22/09/2026.

    MORDIDA: faça o `Connect` recusado devolver `ESTADO_NAO_DEU` e a tela volta
    a dizer *"não sei se caiu"* sobre um elo que ela acabou de ver cair.
    """
    bus = _Bus(conectado="true", connect_ok=False)
    desfecho = radio.reconectar(P2, executar=bus)

    assert bus.chamadas == ["Disconnect", "Connect"]
    assert desfecho.estado == radio.ESTADO_SO_O_PS
    assert "PS" in desfecho.porque


def test_a_lista_do_radio_so_traz_dualsense() -> None:
    """Pelo `Modalias`, nunca pelo nome: a mesa dela tem quatro com o mesmo."""
    bus = _Bus()
    achados = radio.dualsenses_do_radio(executar=bus)

    assert [mac for mac, _ in achados] == [P2], achados


# ---------------------------------------------------------------------------
# 3. quem está na mesa não é tocado
# ---------------------------------------------------------------------------
def test_quem_esta_na_mesa_nao_e_tocado(monkeypatch: Any) -> None:
    """O controle que o daemon já enxerga não perde o rádio por um clique.

    MORDIDA: tire o `if (norm_mac(mac) or "") in na_mesa: continue` do
    `_o_radio_de_volta` — o controle que está jogando cai junto.
    """
    raiz = __import__("pathlib").Path(__file__).resolve().parents[2]
    interface = raiz / "src" / "hefesto_dualsense4unix" / "interface"
    if str(interface) not in sys.path:
        sys.path.insert(0, str(interface))
    from pacotes import Contexto
    from pacotes import a01_jogar as a01

    tocados: list[str] = []

    def _lista(**_k: Any) -> list[tuple[str, bool | None]]:
        return [(P1, True), (P2, True)]

    def _reconectar(mac: str, **_k: Any) -> Any:
        tocados.append(mac)
        return radio.Resultado(radio.ESTADO_VOLTOU, radio.FRASE_VOLTOU, mac)

    monkeypatch.setattr(radio, "dualsenses_do_radio", _lista)
    monkeypatch.setattr(radio, "reconectar", _reconectar)

    ctx = Contexto(
        state={}, mesa=[{"uniq": P1, "jogador": 1}], conectados=[], estados={}
    )
    voltaram, esperam = a01._o_radio_de_volta(ctx)

    assert tocados == [P2], "o controle da mesa foi mexido"
    assert (voltaram, esperam) == (1, 0)


# ---------------------------------------------------------------------------
# 4. a suíte não fala com o rádio dela — a régua do estrago do dia
# ---------------------------------------------------------------------------
def test_a_suite_nunca_alcanca_o_bus_de_verdade() -> None:
    """O `busctl` do dono recusa o barramento dela enquanto a suíte estiver no ar.

    **O ESTRAGO QUE A PRODUZIU:** a primeira corrida que alcançou o passo do
    rádio chamou `Disconnect` e `Connect` nos quatro DualSense da mesa dela, ao
    vivo. O recado saiu no relatório do teste: *"Aperte PS em 4 controle(s)"*.

    A guarda nasceu neste módulo e subiu para a borda do dono do BlueZ
    (BLUEZ-UM-DONO-01), que é por onde o gesto lê e escreve agora.

    MORDIDA: tire a guarda da suíte de `bluez_dbus.busctl` e esta régua
    reprova — e a próxima corrida derruba a mesa dela de novo.
    """
    assert bluez_dbus.a_suite_esta_rodando() is True
    assert bluez_dbus.busctl(["tree", bluez_dbus.SERVICO, "--list"]) is None
    # E o gesto inteiro, sem dublê nenhum, não toca em nada e não mente: sem
    # árvore não há lista, e sem lista não há controle a mexer.
    assert radio.dualsenses_do_radio() == []
    assert radio.reconectar(P2).estado == radio.ESTADO_SEM_ALVO


def test_a_porta_de_fuga_existe_e_e_declarada(monkeypatch: Any) -> None:
    """Quem precisa medir o bus de verdade declara — e assume o rádio dela."""
    monkeypatch.setenv(radio.RADIO_DE_VERDADE_NA_SUITE, "1")
    assert bluez_dbus.a_suite_esta_rodando() is False

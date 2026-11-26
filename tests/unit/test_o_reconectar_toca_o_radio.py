"""O «Reconectar controles» mexe no RÁDIO — ordem, 22/09/2026.

**A DECISÃO DO PRODUTO:** o reconectar toca o rádio também; não faz sentido ele ficar de fora.

A decisão revoga a regra de 12/08 que o módulo carregava — *"Não reconectar é decisão
de produto; o botão PS é do usuário"* —, e o dia mediu por quê: a máquina de teste caiu num estado
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
4. **A SUÍTE NÃO FALA COM O RÁDIO DO USUÁRIO.** Esta é a régua do estrago do dia: o
   passo nasceu sem guarda e a primeira corrida de 457 testes derrubou os
   QUATRO DualSense da máquina de teste, ao vivo.
5. **A porta de fuga é do teste que a pede (A-SUITE-NUNCA-HERDA-O-BARRAMENTO-REAL-DO-BLUEZ-01,
   25/11/2026).** Medido: com a porta aberta por um teste, o fio que outro teste deixou vivo
   chamava ``dono()``, abria o barramento real e o deixava no global ``_DONO``; o teste seguinte
   recebia os controles de verdade. Agora só o fio do próprio teste vê a porta aberta, o dono
   real nunca é entregue sob a suíte e o dono real que um caso abriu fecha com o caso.

MORDIDAS: sem o fio principal em ``a_suite_esta_rodando``, os dois primeiros testes da porta
reprovam; sem a recusa do dono real em ``dono()``, ``test_o_dono_real_herdado_nao_e_entregue_...``
reprova; sem a fixture ``_o_dono_do_bluez_de_verdade_nao_atravessa``, o par de testes do dono
aberto pela porta reprova no segundo.
"""

from __future__ import annotations

import sys
import threading
from typing import Any

from hefesto_dualsense4unix.integrations import bluez_dbus
from hefesto_dualsense4unix.integrations import gesto_de_reconexao as radio

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
            return 's "usb:v046DpC52Bd0100"'
        if args[0] == "call":
            self.chamadas.append(args[-1])
            if args[-1] == "Connect" and not self.connect_ok:
                return None
            return ""
        return None


def test_o_elo_morto_cai_e_o_controle_e_chamado_de_volta() -> None:
    """MORDIDA: tire o `Disconnect` de `reconectar` — a chamada some da lista."""
    bus = _Bus(conectado="true")
    desfecho = radio.reconectar(P2, executar=bus)

    assert bus.chamadas == ["Disconnect", "Connect"], bus.chamadas
    assert desfecho.estado == radio.ESTADO_VOLTOU
    assert desfecho.endereco == radio.mascarar(P2)


def test_o_controle_fora_do_radio_nao_leva_disconnect() -> None:
    """Quem já está fora só precisa ser chamado — derrubar o que não está de pé"""
    bus = _Bus(conectado="false")
    desfecho = radio.reconectar(P2, executar=bus)

    assert bus.chamadas == ["Connect"], bus.chamadas
    assert desfecho.estado == radio.ESTADO_VOLTOU


def test_o_connect_recusado_devolve_o_ps_para_o_usuario() -> None:
    """Um DualSense dormindo não atende chamado — medido em 22/09/2026.

    MORDIDA: faça o `Connect` recusado devolver `ESTADO_NAO_DEU` e a tela volta
    a dizer *"não sei se caiu"* sobre um elo que quem usa acabou de ver cair.
    """
    bus = _Bus(conectado="true", connect_ok=False)
    desfecho = radio.reconectar(P2, executar=bus)

    assert bus.chamadas == ["Disconnect", "Connect"]
    assert desfecho.estado == radio.ESTADO_SO_O_PS
    assert "PS" in desfecho.porque


def test_a_lista_do_radio_so_traz_dualsense() -> None:
    """Pelo `Modalias`, nunca pelo nome: a máquina de teste tem quatro com o mesmo."""
    bus = _Bus()
    achados = radio.dualsenses_do_radio(executar=bus)

    assert [mac for mac, _ in achados] == [P2], achados


def test_quem_esta_na_mesa_nao_e_tocado(monkeypatch: Any) -> None:
    """O controle que o daemon já enxerga não perde o rádio por um clique."""
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


def test_a_suite_nunca_alcanca_o_bus_de_verdade() -> None:
    """O `busctl` do dono recusa o barramento real enquanto a suíte estiver no ar.

    **O ESTRAGO QUE A PRODUZIU:** a primeira corrida que alcançou o passo do
    rádio chamou `Disconnect` e `Connect` nos quatro DualSense da máquina de teste, ao
    vivo. O recado saiu no relatório do teste: *"Aperte PS em 4 controle(s)"*.

    A guarda nasceu neste módulo e subiu para a borda do dono do BlueZ
    (BLUEZ-UM-DONO-01), que é por onde o gesto lê e escreve agora.

    MORDIDA: tire a guarda da suíte de `bluez_dbus.busctl` e esta régua
    reprova — e a próxima corrida derruba a máquina de teste de novo.
    """
    assert bluez_dbus.a_suite_esta_rodando() is True
    assert bluez_dbus.busctl(["tree", bluez_dbus.SERVICO, "--list"]) is None
    assert radio.dualsenses_do_radio() == []
    assert radio.reconectar(P2).estado == radio.ESTADO_SEM_ALVO


def test_a_porta_de_fuga_existe_e_e_declarada(monkeypatch: Any) -> None:
    """Quem precisa medir o bus de verdade declara — e assume o rádio do usuário."""
    monkeypatch.setenv(radio.RADIO_DE_VERDADE_NA_SUITE, "1")
    assert bluez_dbus.a_suite_esta_rodando() is False


def _dono_real_de_mentira(monkeypatch: Any) -> bluez_dbus.DonoVivo:
    """Um dono cujo barramento é o ``BarramentoGio`` do sistema, sem abrir conexão nenhuma."""
    barramento = bluez_dbus.BarramentoGio()
    monkeypatch.setattr(bluez_dbus.BarramentoGio, "vivo", lambda self: True)
    return bluez_dbus.DonoVivo(barramento)


def test_o_fio_de_outro_teste_nao_ve_a_porta_aberta(monkeypatch: Any) -> None:
    monkeypatch.setenv(radio.RADIO_DE_VERDADE_NA_SUITE, "1")
    visto: list[bool] = []
    fio = threading.Thread(target=lambda: visto.append(bluez_dbus.a_suite_esta_rodando()))
    fio.start()
    fio.join(5)
    assert visto == [True], "o fio vazado viu o rádio aberto"
    assert bluez_dbus.a_suite_esta_rodando() is False


def test_o_fio_vazado_com_a_porta_aberta_nao_abre_o_barramento_real(monkeypatch: Any) -> None:
    abriu: list[str] = []
    monkeypatch.setattr(bluez_dbus, "_DONO", None)
    monkeypatch.setattr(bluez_dbus, "_GIO_FALHOU_EM", None)

    def _abrir() -> None:
        abriu.append("abriu")

    monkeypatch.setattr(bluez_dbus, "_ligar_o_dono_do_sistema", _abrir)
    monkeypatch.setenv(radio.RADIO_DE_VERDADE_NA_SUITE, "1")
    entregue: list[Any] = []
    fio = threading.Thread(target=lambda: entregue.append(bluez_dbus.dono()))
    fio.start()
    fio.join(5)
    assert abriu == [] and isinstance(entregue[0], bluez_dbus.PeloBusctl), (abriu, entregue)
    bluez_dbus.dono()
    assert abriu == ["abriu"], "a porta não abre para o próprio teste que a pediu"


def test_o_dono_real_herdado_nao_e_entregue_sob_a_suite(monkeypatch: Any) -> None:
    real = _dono_real_de_mentira(monkeypatch)
    monkeypatch.setattr(bluez_dbus, "_DONO", real)
    assert bluez_dbus.e_o_dono_de_verdade(real)
    entregue = bluez_dbus.dono()
    assert entregue is not real and isinstance(entregue, bluez_dbus.PeloBusctl)


def test_o_dubles_que_se_diz_do_sistema_segue_sendo_entregue(monkeypatch: Any) -> None:
    from tests.unit import bluez_de_mentira as bm

    dubles = bluez_dbus.DonoVivo(bm.BarramentoDeMentira(e_do_sistema=True))
    monkeypatch.setattr(bluez_dbus, "_DONO", dubles)
    assert not bluez_dbus.e_o_dono_de_verdade(dubles)
    assert bluez_dbus.dono() is dubles


def test_o_dono_aberto_pela_porta_deixa_o_global_como_estava_1(monkeypatch: Any) -> None:
    """Par com o seguinte: este deixa um dono real no global, sem desfazer, como o vazamento."""
    assert bluez_dbus._DONO is None or not bluez_dbus.e_o_dono_de_verdade(bluez_dbus._DONO)
    real = _dono_real_de_mentira(monkeypatch)
    bluez_dbus._DONO = real
    _DEIXADOS.append(real)


def test_o_dono_aberto_pela_porta_deixa_o_global_como_estava_2() -> None:
    assert _DEIXADOS, "o par só vale depois do primeiro"
    assert not bluez_dbus.e_o_dono_de_verdade(bluez_dbus._DONO), "o dono real atravessou o caso"


_DEIXADOS: list[Any] = []

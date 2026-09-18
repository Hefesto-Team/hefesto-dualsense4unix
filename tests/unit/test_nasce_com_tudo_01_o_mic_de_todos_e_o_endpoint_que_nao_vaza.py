"""NASCE-COM-TUDO-01 — o microfone de todo controle, e o nó que parava de cair.

**A ORDEM DELA, 18/09/2026:** *"todos os controles tem que nascer com tudo mic,
giroscopio e afins"*, *"alem de som"*.

**O QUE ESTAVA MEDIDO quando ela disse isso**, com os quatro DualSense no rádio:

    giroscópio · acelerômetro · alto-falante   4 de 4   ✓
    microfone                                  2 de 4   ✗

Os dois sem microfone nunca haviam sido DECLARADOS no `maquina.json`, e a aba
respondia *"o sistema não vê um microfone neste controle"* — uma recusa que a
pessoa não tinha como resolver, porque o botão que a resolveria estava atrás de
uma declaração que ninguém sabia existir. Vinte e sete dessas no diário dela.

E a varredura do mesmo dia achou o segundo: **vinte e dois `module-null-sink`
de háptica onde deviam existir quatro**, porque a idempotência olhava a memória
do processo e o servidor de som sobrevive ao restart do daemon.
"""

from __future__ import annotations

from types import SimpleNamespace

from hefesto_dualsense4unix.daemon.subsystems.bt_mic import (
    uniqs_negados,
    uniqs_recusados,
)
from hefesto_dualsense4unix.integrations.endpoint_de_haptica import (
    Ancora,
    EndpointDeHaptica,
    endpoints_de_pe,
    nome_do_endpoint,
    varrer_endpoints_orfaos,
)

_REAL = "02001a0000"
_A, _B = f"{_REAL}01", f"{_REAL}02"


# ---------------------------------------------------------------------------
# O MICROFONE — a ausência de opinião passou a LIGAR
# ---------------------------------------------------------------------------


def _maquina(**controles: bool | None) -> SimpleNamespace:
    return SimpleNamespace(
        controles={k: SimpleNamespace(microfone=v) for k, v in controles.items()}
    )


def test_so_o_false_explicito_e_recusa() -> None:
    m = _maquina(**{_A: False, _B: True, f"{_REAL}03": None})
    assert uniqs_recusados(m) == frozenset({_A})


def test_mesa_sem_declaracao_nenhuma_nao_recusa_ninguem() -> None:
    """É a máquina nova, e é o caso que mais importa: nada declarado = tudo liga."""
    assert uniqs_recusados(None) == frozenset()
    assert uniqs_recusados(_maquina()) == frozenset()


def test_a_fonte_que_explode_vale_como_ninguem_desligou() -> None:
    """O lado seguro INVERTEU com o default: erro de leitura não pode calar."""

    def explode() -> frozenset[str]:
        raise RuntimeError("o maquina.json sumiu")

    assert uniqs_negados(SimpleNamespace(bt_mic_recusados=explode)) == frozenset()
    assert uniqs_negados(SimpleNamespace()) == frozenset()


class _Subsystem:
    """O `alvos()` real, com a config e o registro dublados."""

    def __init__(self, negados: frozenset[str] = frozenset()) -> None:
        from hefesto_dualsense4unix.daemon.subsystems.bt_mic import BtMicSubsystem

        self.s = BtMicSubsystem()
        self.s._config = SimpleNamespace(
            bt_mic_uniqs=frozenset, bt_mic_recusados=lambda: negados
        )
        self.s._registro = SimpleNamespace(abertos=frozenset)

    def alvos(self, *uniqs: str) -> list[str]:
        nos = [SimpleNamespace(uniq=u) for u in uniqs]
        return [n.uniq for n in self.s.alvos(nos)]


def test_todo_controle_do_radio_ganha_canal_sem_declarar_nada() -> None:
    """A INVERSÃO: antes isto devolvia [] — a queixa dela, em uma linha."""
    assert _Subsystem().alvos(_A, _B) == [_A, _B]


def test_quem_ela_desligou_fica_de_fora() -> None:
    assert _Subsystem(frozenset({_A})).alvos(_A, _B) == [_B]


def test_no_sem_endereco_nunca_entra() -> None:
    """Sem endereço não há de quem é o microfone — nem como desligá-lo depois."""
    assert _Subsystem().alvos("", _A) == [_A]


# ---------------------------------------------------------------------------
# O ENDPOINT — a idempotência mudou de alvo
# ---------------------------------------------------------------------------

_ANCORA = Ancora(
    syspath="/sys/devices/pci0000:00/usb3/3-4",
    declarado="/devices/pci0000:00/usb3/3-4",
    nome="DualSense",
)
#: A SEGUNDA âncora é o coração do vazamento medido: o mesmo controle tinha
#: nós com `3-4:1.0` e `3-4.1:1.0`, porque a âncora escolhida muda entre
#: reconciliações e o nome do sink não.
_OUTRA = Ancora(
    syspath="/sys/devices/pci0000:00/usb3/3-4/3-4.1",
    declarado="/devices/pci0000:00/usb3/3-4/3-4.1",
    nome="DualSense",
)


class _Pactl:
    """Um servidor de som de mentira, com os módulos que ELE lembra."""

    def __init__(self, modulos: list[tuple[str, str, str]]) -> None:
        #: (module_id, sink_name, sysfs_path)
        self.modulos = list(modulos)
        self.comandos: list[list[str]] = []
        self._proximo = 900

    def __call__(self, argv: list[str]) -> str | None:
        self.comandos.append(argv)
        if argv[:3] == ["pactl", "list", "short"]:
            return "\n".join(
                f"{mid}\tmodule-null-sink\tsink_name={nome} sysfs.path={caminho}\t"
                for mid, nome, caminho in self.modulos
            )
        if argv[:2] == ["pactl", "unload-module"]:
            self.modulos = [m for m in self.modulos if m[0] != argv[2]]
            return ""
        if argv[:2] == ["pactl", "load-module"]:
            self._proximo += 1
            nome = next(a[len("sink_name=") :] for a in argv if a.startswith("sink_name="))
            self.modulos.append((str(self._proximo), nome, "novo"))
            return str(self._proximo)
        return ""


def test_o_endpoint_de_pe_com_a_mesma_ancora_e_adotado() -> None:
    """O restart do daemon não pode trocar um nó vivo por outro idêntico."""
    nome = nome_do_endpoint(_A)
    pactl = _Pactl([("77", nome, _ANCORA.declarado)])
    e = EndpointDeHaptica(uniq=_A, ancora=_ANCORA, runner=pactl)
    assert e.iniciar() is True
    assert e.module_id == "77", "carregou um novo em vez de adotar o de pé"
    assert not any(c[:2] == ["pactl", "load-module"] for c in pactl.comandos)


def test_os_duplicados_da_mesma_ancora_caem_na_adocao() -> None:
    """Cinco do mesmo controle era o estado REAL da mesa dela."""
    nome = nome_do_endpoint(_A)
    pactl = _Pactl([(str(70 + i), nome, _ANCORA.declarado) for i in range(5)])
    EndpointDeHaptica(uniq=_A, ancora=_ANCORA, runner=pactl).iniciar()
    assert len(pactl.modulos) == 1, pactl.modulos


def test_ancora_diferente_derruba_e_recria() -> None:
    """A âncora é o que o jogo lê para o ContainerId: a velha responde errado."""
    nome = nome_do_endpoint(_A)
    pactl = _Pactl([("77", nome, _OUTRA.declarado)])
    e = EndpointDeHaptica(uniq=_A, ancora=_ANCORA, runner=pactl)
    assert e.iniciar() is True
    assert e.module_id != "77"
    assert len(pactl.modulos) == 1
    assert ["pactl", "unload-module", "77"] in pactl.comandos


def test_o_orfao_de_controle_que_saiu_e_derrubado() -> None:
    pactl = _Pactl(
        [
            ("77", nome_do_endpoint(_A), _ANCORA.declarado),
            ("78", nome_do_endpoint(_B), _ANCORA.declarado),
        ]
    )
    caidos = varrer_endpoints_orfaos([_A], pactl)
    assert caidos == ["78"]
    assert [m[0] for m in pactl.modulos] == ["77"]


def test_a_varredura_nao_toca_o_sink_de_um_dualsense_no_cabo() -> None:
    """Sem a marca `HEFESTO` no nome, o nó não é nosso para derrubar."""
    do_kernel = (
        "alsa_output.usb-Sony_Interactive_Entertainment_Wireless_Controller-00"
        ".HiFi__Speaker__sink"
    )
    pactl = _Pactl([("77", do_kernel, "")])
    assert varrer_endpoints_orfaos([], pactl) == []
    assert len(pactl.modulos) == 1


def test_mordida_do_endpoint_sem_perguntar_ao_servidor_ele_soma() -> None:
    """Arranca a consulta: o comportamento de antes volta — mais um por restart.

    O `_module_id` de instância nasce None a cada processo, então a versão
    antiga carregava sempre. Esta régua reproduz o vazamento MEDIDO.
    """
    nome = nome_do_endpoint(_A)
    pactl = _Pactl([("77", nome, _ANCORA.declarado)])
    for _ in range(4):  # quatro "restarts do daemon"
        e = EndpointDeHaptica(uniq=_A, ancora=_ANCORA, runner=pactl)
        e._module_id = None
        pactl(["pactl", "load-module", "module-null-sink", f"sink_name={nome}"])
    assert len(pactl.modulos) == 5, "a mordida não reproduz o vazamento"
    # e a cura, no mesmo servidor sujo, devolve UM:
    EndpointDeHaptica(uniq=_A, ancora=_ANCORA, runner=pactl).iniciar()
    assert len(endpoints_de_pe(pactl)[nome]) == 1

"""MIC-O-CANAL-DO-OUTRO-01 — o canal de outro controle não é meu (13/09/2026).

O journal do teste dela de 12/09 (15:52 a 17:22) mostrou três defeitos que régua
nenhuma via, e esta régua é dos três:

1. **o microfone de um controle eleito no canal de OUTRO** — o ``…:ab`` saiu da
   mesa às 16:35:04, e às 16:40:06 a eleição deu ao ``…:03`` o canal
   ``hefesto_mic_0000ab``. A regra 4 de `escolher_fonte` (um para um) entregava
   o único nó da lista sem ler o nome dele;
2. **o canal órfão sobrevive ao controle e ao daemon** — ninguém derrubava o
   `module-pipe-source` de um controle que saiu;
3. **o `pactl` mudo e o supervisor martelando** — medido por quem coordena em
   13/09, das 01:53 às 02:40: 699 prazos estourados e 509 `load-module` sem
   resposta.

NENHUM TESTE AQUI FALA COM O SERVIDOR DE SOM DA MÁQUINA. Todo `pactl` é dublê;
o único contato com o sistema é ler o ``/proc`` DESTE processo para um fifo que
o próprio teste cria em ``tmp_path``.

COMO MORDE (exercido em 13/09/2026, as saídas estão na entrega)
----------------------------------------------------------------
* arranque o ``if not sem_nome_alheio: return None`` de `escolher_fonte` e
  devolva ``usb.casar(fontes, …)`` → reprova a seção 1;
* arranque a chamada ``self._varrer_os_orfaos(nos)`` do `_loop` → reprova o
  laço da seção 2; arranque a prova do escritor do varredor → reprova
  ``test_canal_com_escritor_fica_mesmo_sem_pedido``;
* arranque os dois ``pactl_mudo()`` de `_orfaos_se_o_pactl_responde` → reprova
  a seção 3.

Endereços sintéticos da faixa ``e8:47:3a`` com a máscara da casa.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import bt_mic
from hefesto_dualsense4unix.integrations import canal_do_microfone as canal
from hefesto_dualsense4unix.integrations import dualsense_bt_audio as bt
from hefesto_dualsense4unix.integrations import eleicao_de_microfone as elm
from hefesto_dualsense4unix.integrations.fontes_de_captura import (
    CasamentoUSB,
    e_de_outro_controle,
    escolher_fonte,
    identidade_no_nome,
)

#: Quem apertou o botão do microfone.
DELE = "e8:47:3a:00:00:5c"
#: Quem saiu da mesa e deixou o canal para trás.
VIZINHO = "e8:47:3a:00:00:9e"

CANAL_DELE = "hefesto_mic_00005c"
CANAL_DO_VIZINHO = "hefesto_mic_00009e"
PONTE_DO_VIZINHO = "hefesto_dualsense_bt_00009e"
BLUEZ_DO_VIZINHO = "bluez_input.E8_47_3A_00_00_9E.0"
CABO = (
    "alsa_input.usb-Sony_Interactive_Entertainment_DualSense_Wireless_Controller-00."
    "iec958-stereo"
)


def _hex(uniq: str) -> str:
    return uniq.replace(":", "").lower()


# ===========================================================================
# 1. O NOME DE OUTRO CONTROLE DIZ NÃO
# ===========================================================================


@pytest.mark.parametrize("alheio", [CANAL_DO_VIZINHO, PONTE_DO_VIZINHO, BLUEZ_DO_VIZINHO])
def test_o_no_do_vizinho_sozinho_na_lista_nao_e_dele(alheio: str) -> None:
    """A cena do journal: uma fonte na lista, um controle conectado, e ela é do outro."""
    assert escolher_fonte([alheio], DELE, [DELE]) is None, (
        f"o um-para-um entregou {alheio} ao controle errado"
    )
    assert escolher_fonte([alheio], DELE, [DELE], CasamentoUSB()) is None


@pytest.mark.parametrize(
    "do_dono", [CANAL_DELE, "hefesto_dualsense_bt_00005c", "bluez_input.E8_47_3A_00_00_5C.0"]
)
def test_o_no_dele_continua_sendo_dele(do_dono: str) -> None:
    """A cura não pode apagar o microfone de quem TEM microfone."""
    assert escolher_fonte([do_dono], DELE, [DELE]) == do_dono
    assert escolher_fonte([CANAL_DO_VIZINHO, do_dono], DELE, [DELE]) == do_dono


@pytest.mark.parametrize("sem_identidade", [CABO, "hefesto_dualsense_bt_hidraw3"])
def test_no_sem_identidade_continua_no_um_para_um(sem_identidade: str) -> None:
    """O nó ALSA do cabo não tem nome de controle: sobre ele o nome não sabe nada."""
    assert escolher_fonte([sem_identidade], DELE, [DELE]) == sem_identidade


def test_o_casamento_usb_nao_entrega_no_com_nome_alheio() -> None:
    """A regra 3 também não lê nome — e não pode ser a outra porta do mesmo defeito."""
    usb = CasamentoUSB(por_uniq={DELE: "1-2"}, por_no={CANAL_DO_VIZINHO: "1-2"})
    assert escolher_fonte([CANAL_DO_VIZINHO], DELE, [DELE, VIZINHO], usb) is None


def test_a_identidade_que_o_nome_carrega() -> None:
    assert identidade_no_nome(CANAL_DO_VIZINHO) == "00009e"
    assert identidade_no_nome(PONTE_DO_VIZINHO) == "00009e"
    assert identidade_no_nome(BLUEZ_DO_VIZINHO) == _hex(VIZINHO)
    assert identidade_no_nome(CABO) == ""
    assert identidade_no_nome("hefesto_dualsense_bt_hidraw3") == ""
    assert e_de_outro_controle(CANAL_DO_VIZINHO, DELE) is True
    assert e_de_outro_controle(CANAL_DELE, DELE) is False
    assert e_de_outro_controle(CABO, DELE) is False
    # Sem endereço legível não se diz que o nó é dele.
    assert e_de_outro_controle(CANAL_DELE, "nao-e-um-mac") is True


def test_a_eleicao_pede_o_canal_dele_em_vez_de_eleger_o_do_vizinho(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O caminho EXATO do journal: `eleicao_mic_ok alvo=hefesto_mic_0000ab` para o ``…:03``.

    Com só o órfão do vizinho publicado, `_canal_no_ar` achava canal atribuível
    — o do vizinho — e nem pedia o canal de quem apertou.
    """
    publicadas = [CANAL_DO_VIZINHO]
    pedidos: list[str] = []

    def _pedidor(uniq: str) -> bool:
        pedidos.append(uniq)
        publicadas.append(CANAL_DELE)
        return True

    anterior = elm.registrar_pedidor_de_canal(_pedidor)
    try:
        monkeypatch.setattr(elm, "fontes_de_captura_agora", lambda: list(publicadas))
        monkeypatch.setattr(elm, "casamento_usb_agora", lambda _u: None)
        monkeypatch.setattr(elm, "ESPERA_DO_CANAL_PASSO_S", 0.0)
        fontes, usb = elm.EleitorDeMicrofone()._canal_no_ar(DELE, [DELE])
    finally:
        elm.registrar_pedidor_de_canal(anterior)

    assert pedidos == [DELE], "o canal dele nunca foi pedido: o do vizinho respondeu antes"
    assert escolher_fonte(fontes, DELE, [DELE], usb) == CANAL_DELE


# ===========================================================================
# 2. O CANAL ÓRFÃO SAI — e só ele
# ===========================================================================


class _Servidor:
    """Dublê do servidor para o varredor: módulos, escritores, e quem sabe recusar."""

    def __init__(self) -> None:
        self.modulos: dict[str, bt.ModuloDeCaptura] = {}
        self.escritor: dict[str, bool | None] = {}
        self.descarregados: list[str] = []
        self.recusa_descarregar = False
        self.mudo = False
        self.listagens = 0

    def pôr(self, module_id: str, nome: str, *, escreve: bool | None = False) -> None:
        fifo = f"/run/user/1000/hefesto-{nome}.fifo"
        self.modulos[module_id] = bt.ModuloDeCaptura(module_id=module_id, nome=nome, fifo=fifo)
        self.escritor[fifo] = escreve

    def listar(self) -> list[bt.ModuloDeCaptura] | None:
        self.listagens += 1
        return list(self.modulos.values())

    def alguem_escreve(self, fifo: str) -> bool | None:
        return self.escritor.get(fifo)

    def descarregar(self, module_id: str) -> bool:
        if self.recusa_descarregar:
            return False
        self.descarregados.append(module_id)
        self.modulos.pop(module_id, None)
        return True

    def varredor(self) -> bt_mic.VarredorDeCanaisOrfaos:
        return bt_mic.VarredorDeCanaisOrfaos(
            listar=self.listar,
            alguem_escreve=self.alguem_escreve,
            descarregar=self.descarregar,
            mudo=lambda: self.mudo,
        )


NINGUEM: frozenset[str] = frozenset()


def test_o_orfao_sem_pedido_e_sem_escritor_cai_na_segunda_varredura() -> None:
    servidor = _Servidor()
    servidor.pôr("536870930", CANAL_DO_VIZINHO)
    varredor = servidor.varredor()

    assert varredor.varrer(querem=NINGUEM, de_pe=NINGUEM) == []
    assert servidor.descarregados == [], "caiu na primeira varredura, sem a segunda prova"
    assert varredor.varrer(querem=NINGUEM, de_pe=NINGUEM) == [CANAL_DO_VIZINHO]
    assert servidor.descarregados == ["536870930"]


def test_o_canal_de_quem_esta_pedido_fica() -> None:
    servidor = _Servidor()
    servidor.pôr("536870931", CANAL_DELE)
    varredor = servidor.varredor()
    for _ in range(3):
        varredor.varrer(querem=frozenset({_hex(DELE)}), de_pe=NINGUEM)
    assert servidor.descarregados == []


def test_o_canal_de_pe_neste_processo_fica() -> None:
    servidor = _Servidor()
    servidor.pôr("536870932", CANAL_DO_VIZINHO)
    varredor = servidor.varredor()
    for _ in range(3):
        varredor.varrer(querem=NINGUEM, de_pe=frozenset({CANAL_DO_VIZINHO}))
    assert servidor.descarregados == []


def test_canal_com_escritor_fica_mesmo_sem_pedido() -> None:
    """O canal vivo de OUTRO processo — o `mic bt` do CLI, ou o daemon dela."""
    servidor = _Servidor()
    servidor.pôr("536870933", CANAL_DO_VIZINHO, escreve=True)
    varredor = servidor.varredor()
    for _ in range(3):
        varredor.varrer(querem=NINGUEM, de_pe=NINGUEM)
    assert servidor.descarregados == [], "derrubou um canal que alguém estava enchendo"


def test_nao_sei_nunca_derruba() -> None:
    servidor = _Servidor()
    servidor.pôr("536870934", CANAL_DO_VIZINHO, escreve=None)
    varredor = servidor.varredor()
    for _ in range(3):
        varredor.varrer(querem=NINGUEM, de_pe=NINGUEM)
    assert servidor.descarregados == []


def test_o_modulo_que_trocou_de_id_recomeca_a_contagem() -> None:
    """A segunda prova é do MESMO módulo, não do mesmo nome."""
    servidor = _Servidor()
    servidor.pôr("536870935", CANAL_DO_VIZINHO)
    varredor = servidor.varredor()
    varredor.varrer(querem=NINGUEM, de_pe=NINGUEM)
    servidor.modulos.clear()
    servidor.pôr("536870936", CANAL_DO_VIZINHO)
    varredor.varrer(querem=NINGUEM, de_pe=NINGUEM)
    assert servidor.descarregados == []
    varredor.varrer(querem=NINGUEM, de_pe=NINGUEM)
    assert servidor.descarregados == ["536870936"]


def test_com_o_servidor_mudo_nao_se_varre() -> None:
    servidor = _Servidor()
    servidor.pôr("536870937", CANAL_DO_VIZINHO)
    servidor.mudo = True
    varredor = servidor.varredor()
    for _ in range(3):
        varredor.varrer(querem=NINGUEM, de_pe=NINGUEM)
    assert servidor.listagens == 0, "varreu um servidor que não está atendendo"
    assert servidor.descarregados == []


def test_o_descarregar_que_recusa_tenta_de_novo_na_proxima() -> None:
    servidor = _Servidor()
    servidor.pôr("536870938", CANAL_DO_VIZINHO)
    servidor.recusa_descarregar = True
    varredor = servidor.varredor()
    varredor.varrer(querem=NINGUEM, de_pe=NINGUEM)
    assert varredor.varrer(querem=NINGUEM, de_pe=NINGUEM) == []
    servidor.recusa_descarregar = False
    assert varredor.varrer(querem=NINGUEM, de_pe=NINGUEM) == [CANAL_DO_VIZINHO]


class _GerenciadorDeMentira:
    def __init__(self) -> None:
        self.pontes: dict[str, Any] = {}

    def reconciliar(self, _nos: list[Any]) -> None:
        return None

    def dormir(self, _segundos: float) -> bool:
        return True

    def parar(self) -> None:
        self.pontes.clear()


def _uma_volta(sub: bt_mic.BtMicSubsystem, monkeypatch: pytest.MonkeyPatch) -> None:
    """O `_loop` DE PRODUÇÃO, uma volta — é o laço que tem de chamar a varredura."""
    monkeypatch.setattr(bt, "nos_dualsense_bluetooth", lambda: [])
    # O canal do cabo de quem pediu lê as fontes do servidor: nunca o de verdade.
    monkeypatch.setattr(elm, "fontes_de_captura_agora", lambda: [])
    sub._registro.novidade.set()
    sub._loop()


def test_o_laco_do_supervisor_derruba_o_orfao(monkeypatch: pytest.MonkeyPatch) -> None:
    servidor = _Servidor()
    servidor.pôr("536870939", CANAL_DO_VIZINHO)
    sub = bt_mic.BtMicSubsystem(
        registro=bt_mic.RegistroDePedidosDeCanal(), varredor=servidor.varredor()
    )
    sub._gerenciador = _GerenciadorDeMentira()
    _uma_volta(sub, monkeypatch)
    _uma_volta(sub, monkeypatch)
    assert servidor.descarregados == ["536870939"], (
        "o laço do supervisor não varre: o canal do controle que saiu fica para sempre"
    )


def test_o_laco_nao_derruba_o_canal_de_quem_pediu(monkeypatch: pytest.MonkeyPatch) -> None:
    servidor = _Servidor()
    servidor.pôr("536870940", CANAL_DELE)
    registro = bt_mic.RegistroDePedidosDeCanal()
    registro.pedir(DELE)
    sub = bt_mic.BtMicSubsystem(registro=registro, varredor=servidor.varredor())
    sub._gerenciador = _GerenciadorDeMentira()
    sub._backend = type(
        "Backend", (), {"describe_controllers": lambda self: [{"uniq": DELE, "connected": True}]}
    )()
    for _ in range(3):
        _uma_volta(sub, monkeypatch)
    assert servidor.descarregados == []


def test_sem_varredor_injetado_o_gerenciador_de_mentira_nao_varre_nada() -> None:
    """A suíte roda na máquina onde o daemon dela está de pé: laço de teste não varre."""
    sub = bt_mic.BtMicSubsystem(gerenciador=_GerenciadorDeMentira())
    contexto = type("Ctx", (), {"config": None, "controller": None})()
    asyncio.run(sub.start(contexto))  # type: ignore[arg-type]
    try:
        assert sub._varredor is None
    finally:
        asyncio.run(sub.stop())


_MODULOS = (
    "536870912\tmodule-null-sink\tsink_name=hefesto_som_00009e\t\n"
    "536870919\tmodule-pipe-source\tsource_name=hefesto_mic_00009e"
    " file=/run/user/1000/hefesto-hefesto_mic_00009e.fifo format=s16le"
    " rate=48000 channels=1 source_properties=\"device.description='Microfone"
    " do Controle' priority.session=1500\"\t\n"
    "536870920\tmodule-pipe-source\tsource_name=hefesto_dualsense_bt_00005c"
    " file=/run/user/1000/hefesto-hefesto_dualsense_bt_00005c.fifo format=s16le\t\n"
    "536870921\tmodule-pipe-source\tsource_name=outro_programa file=/tmp/x.fifo\t\n"
)


@pytest.fixture()
def recuo(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> Any:
    """Um recuo PRÓPRIO, com relógio de mentira — nunca o do processo."""

    class _Relogio:
        agora = 1000.0

        def __call__(self) -> float:
            return self.agora

    relogio = _Relogio()
    monkeypatch.setattr(bt, "PACTL", bt.RecuoDoPactl(relogio=relogio))
    monkeypatch.setattr(bt.shutil, "which", lambda _n: "/usr/bin/pactl")
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    return relogio


def test_a_lista_de_modulos_da_casa_le_os_dois_prefixos(recuo: Any) -> None:
    modulos = bt.modulos_de_captura_da_casa(lambda _argv: _MODULOS)
    assert modulos == [
        bt.ModuloDeCaptura(
            "536870919", "hefesto_mic_00009e", "/run/user/1000/hefesto-hefesto_mic_00009e.fifo"
        ),
        bt.ModuloDeCaptura(
            "536870920",
            "hefesto_dualsense_bt_00005c",
            "/run/user/1000/hefesto-hefesto_dualsense_bt_00005c.fifo",
        ),
    ]


def test_quem_escreve_no_fifo_e_o_o_wronly_de_verdade(tmp_path: Any) -> None:
    """O /proc DESTE processo, com um fifo deste teste: servidor em O_RDWR não conta."""
    fifo = str(tmp_path / "hefesto-hefesto_mic_00009e.fifo")
    os.mkfifo(fifo)
    como_o_servidor = os.open(fifo, os.O_RDWR | os.O_NONBLOCK)
    try:
        assert bt.alguem_escreve_no_fifo(fifo) is False
        escritor = os.open(fifo, os.O_WRONLY | os.O_NONBLOCK)
        try:
            assert bt.alguem_escreve_no_fifo(fifo) is True
            os.unlink(fifo)  # o `parar()` apaga o caminho; o fd continua valendo
            assert bt.alguem_escreve_no_fifo(fifo) is True
        finally:
            os.close(escritor)
        assert bt.alguem_escreve_no_fifo(fifo) is False
    finally:
        os.close(como_o_servidor)
    assert bt.alguem_escreve_no_fifo("") is None


# ===========================================================================
# 3. O `pactl` MUDO: RECUO, E NÃO LAÇO FIXO
# ===========================================================================


class _PactlQueTrava:
    """`pactl` dublado. `mudo=True` levanta o prazo estourado, como o `subprocess.run`."""

    def __init__(self) -> None:
        self.chamadas: list[list[str]] = []
        self.mudo = False

    def __call__(self, argv: list[str]) -> str | None:
        self.chamadas.append(argv)
        if self.mudo:
            raise subprocess.TimeoutExpired(argv, 5.0)
        if argv[:2] == ["pactl", "load-module"]:
            return "42\n"
        return ""

    def verbos(self) -> list[str]:
        return [argv[1] for argv in self.chamadas if len(argv) > 1]


class _PactlQueTravaNoLoad(_PactlQueTrava):
    def __call__(self, argv: list[str]) -> str | None:
        if argv[:2] == ["pactl", "load-module"]:
            self.chamadas.append(argv)
            raise subprocess.TimeoutExpired(argv, 5.0)
        return super().__call__(argv)


def test_o_recuo_cresce_ate_o_teto_e_zera_na_resposta(recuo: Any) -> None:
    esperas = []
    for _ in range(6):
        bt.PACTL.estourou()
        esperas.append(bt.PACTL.espera_s)
    assert esperas == [5.0, 10.0, 20.0, 40.0, 60.0, 60.0]
    assert bt.pactl_mudo() is True
    recuo.agora += 61.0
    assert bt.pactl_mudo() is False
    bt.PACTL.respondeu()
    assert bt.PACTL.espera_s == 0.0


def test_load_module_que_estoura_o_prazo_nao_se_repete_no_ciclo_seguinte(recuo: Any) -> None:
    pactl = _PactlQueTravaNoLoad()
    primeira = bt.SourceVirtualPipeWire(nome=CANAL_DELE, descricao="Teste", runner=pactl)
    assert primeira.iniciar() is False
    assert pactl.verbos().count("load-module") == 1
    assert bt.pactl_mudo() is True

    antes = len(pactl.chamadas)
    # O CICLO SEGUINTE constrói uma source NOVA — a memória não pode ser dela.
    seguinte = bt.SourceVirtualPipeWire(nome=CANAL_DELE, descricao="Teste", runner=pactl)
    assert seguinte.iniciar() is False
    assert len(pactl.chamadas) == antes, "o ciclo seguinte perguntou ao servidor mudo"


def test_vencido_o_recuo_a_sondagem_vem_antes_do_load(recuo: Any) -> None:
    pactl = _PactlQueTrava()
    pactl.mudo = True
    bt.PACTL.estourou()
    recuo.agora += bt.RECUO_PISO_S
    source = bt.SourceVirtualPipeWire(nome=CANAL_DELE, descricao="Teste", runner=pactl)
    assert source.iniciar() is False
    assert pactl.verbos() == ["list"], "o load-module saiu sem a sondagem responder"
    assert bt.PACTL.espera_s == 10.0

    recuo.agora += 10.0
    pactl.mudo = False
    source = bt.SourceVirtualPipeWire(nome=CANAL_DELE, descricao="Teste", runner=pactl)
    source._abrir_fifo = lambda: True  # type: ignore[method-assign]
    assert source.iniciar() is True
    assert pactl.verbos()[-2:] == ["list", "load-module"]
    assert bt.PACTL.espera_s == 0.0


def test_parar_e_estado_com_o_servidor_mudo_nao_perguntam(recuo: Any) -> None:
    pactl = _PactlQueTrava()
    source = bt.SourceVirtualPipeWire(nome=CANAL_DELE, descricao="Teste", runner=pactl)
    source._module_id = "77"
    bt.PACTL.estourou()
    assert source.estado() is None
    source.parar()
    assert pactl.chamadas == []
    assert source._module_id is None


class _Decodador:
    def decodificar(self, _quadro: bytes) -> bytes | None:
        return None

    def close(self) -> None:
        return None


def test_o_supervisor_nao_repete_o_load_module_no_ciclo_seguinte(
    recuo: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Dois ciclos do gerenciador com o servidor travando no `load-module`.

    Sem a cura: o canal por controle e o caminho de volta pelo nome do
    transporte tentam cada um, a cada ciclo — QUATRO `load-module` em dois
    ciclos, a mesma cadência do journal de 13/09. Com a cura: UM.
    """
    pactl = _PactlQueTravaNoLoad()
    real = bt.SourceVirtualPipeWire

    def _source(**kw: Any) -> Any:
        return real(runner=pactl, **kw)

    monkeypatch.setattr(bt, "SourceVirtualPipeWire", _source)
    monkeypatch.setattr(canal, "SourceVirtualPipeWire", _source)
    monkeypatch.setattr(canal, "_rodar_pactl", lambda _argv: True)

    def _ponte(no: bt.NoDualSenseBT) -> bt.PonteMicBluetooth:
        return bt.PonteMicBluetooth(
            no, opener=lambda _c: os.open(os.devnull, os.O_RDWR), decodificador=_Decodador()
        )

    gerenciador = bt.GerenciadorMicBluetooth(fabrica=_ponte)
    no = bt.NoDualSenseBT(caminho="/dev/hidraw-5c", uniq=DELE, produto=0x0CE6)
    try:
        gerenciador.reconciliar([no])
        gerenciador.reconciliar([no])
    finally:
        gerenciador.parar()
        for uniq in list(canal.de_pe()):
            canal.fechar(uniq)
    assert pactl.verbos().count("load-module") == 1, pactl.verbos()


def test_o_canal_do_cabo_espera_o_servidor_voltar(
    recuo: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    perguntas: list[str] = []
    monkeypatch.setattr(elm, "fontes_de_captura_agora", lambda: perguntas.append("fontes") or [])
    sub = bt_mic.BtMicSubsystem(registro=bt_mic.RegistroDePedidosDeCanal())
    bt.PACTL.estourou()
    sub._abrir_os_canais_do_cabo([_hex(DELE)])
    assert perguntas == [], "o supervisor perguntou ao servidor mudo pelo canal do cabo"
    recuo.agora += bt.RECUO_PISO_S
    sub._abrir_os_canais_do_cabo([_hex(DELE)])
    assert perguntas == ["fontes"]

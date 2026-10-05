# ruff: noqa: RUF001
"""O receptor 2.4G se reconhece e diz quando sofre.

O-RECEPTOR-2-4G-SE-RECONHECE-E-DIZ-QUANDO-SOFRE-01 (05/10/2026).

Tudo com fixture: um sysfs de mentira em disco (o filho HID entre a interface e o ``input``, como
no kernel de verdade), pipes no lugar do ``/dev/input`` e relógio de mentira. Nada aqui abre
evdev, hidraw nem barramento de verdade; faixa forjada nos endereços.

MORDIDAS, uma por vez: a segunda interface de arranque (``e_receptor``); o ``speed`` do receptor;
o «solta» que desfaz a tecla presa; o limite relativo do buraco; o filho HID da busca de nós de
input; o ``diff`` da banda por eliminação.
"""

from __future__ import annotations

import contextlib
import json
import os
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import receptor_sem_fio as rx
from hefesto_dualsense4unix.integrations.censo_do_barramento import ler_o_barramento

# --- 1. reconhecer: só pelo que o kernel publica ---------------------------------------------

DUAS = ("030101", "030102")


@pytest.mark.parametrize(
    ("interfaces", "velocidade", "textos", "esperado"),
    [
        (DUAS, 12.0, ("2.4G Wireless Receiver", "Compx"), True),
        (("030102", "030101"), 12.0, ("2.4G Dual Mode Mouse", ""), True),
        (DUAS, 12.0, ("USB Receiver", ""), True),
        (DUAS, 12.0, ("", "Acme Wireless"), True),
        # um mouse com fio tem UMA interface de arranque
        (("030102",), 12.0, ("2.4G Wireless Receiver", ""), False),
        # teclado de jogo de cabo: duas interfaces, mas rápido demais e sem a palavra
        (DUAS, 480.0, ("Gaming Keyboard", ""), False),
        (DUAS, 480.0, ("2.4G Wireless Receiver", ""), False),
        (DUAS, 12.0, ("Gaming Keyboard", "BY Tech"), False),
        (DUAS, 0.0, ("2.4G Wireless Receiver", ""), False),
        (("030100", "030000"), 12.0, ("2.4G Wireless Receiver", ""), False),
    ],
)
def test_o_receptor_se_reconhece_pelas_duas_interfaces_de_arranque_o_full_speed_e_o_nome(
    interfaces: tuple[str, ...], velocidade: float, textos: tuple[str, str], esperado: bool
) -> None:
    assert rx.e_receptor(interfaces, velocidade, textos) is esperado


def _no_usb(raiz: Path, nome: str, atributos: dict[str, str],
            interfaces: dict[str, tuple[str, str, str, list[str]]]) -> None:
    """Um nó USB e as interfaces dele em ``devices/``; o link em ``bus/usb/devices``.

    ``interfaces``: ``{"1.0": (classe, subclasse, protocolo, [event…])}``; os ``input`` moram
    DENTRO do filho HID (``0003:VVVV:PPPP.NNNN``), como no kernel.
    """
    no = raiz / "devices" / "usb1" / nome
    no.mkdir(parents=True, exist_ok=True)
    for chave, valor in atributos.items():
        (no / chave).write_text(valor + "\n")
    (raiz / "devices" / "usb1" / "busnum").write_text("1\n")
    barramento = raiz / "bus" / "usb" / "devices"
    barramento.mkdir(parents=True, exist_ok=True)
    (barramento / nome).symlink_to(no)
    for sufixo, (classe, sub, proto, eventos) in interfaces.items():
        iface = no / f"{nome}:{sufixo}"
        iface.mkdir()
        (iface / "bInterfaceClass").write_text(classe + "\n")
        (iface / "bInterfaceSubClass").write_text(sub + "\n")
        (iface / "bInterfaceProtocol").write_text(proto + "\n")
        (barramento / f"{nome}:{sufixo}").symlink_to(iface)
        filho = iface / f"0003:AAAA:BBBB.{sufixo[-1]:0>4}"
        for i, evento in enumerate(eventos):
            entrada = filho / "input" / f"input{i + 1}"
            (entrada / "capabilities").mkdir(parents=True)
            (entrada / evento).mkdir()


def _receptor_de_mentira(raiz: Path, nome: str = "1-6", *, velocidade: str = "12",
                         produto: str = "2.4G Wireless Receiver",
                         interfaces: dict[str, tuple[str, str, str, list[str]]] | None = None
                         ) -> None:
    _no_usb(raiz, nome, {
        "idVendor": "aaaa", "idProduct": "bbbb", "speed": velocidade, "busnum": "1",
        "devpath": nome.split("-")[1], "manufacturer": "Acme", "product": produto,
        "bDeviceClass": "00",
    }, interfaces if interfaces is not None else {
        "1.0": ("03", "01", "02", ["event8"]),
        "1.1": ("03", "01", "01", ["event9", "event10", "event11"]),
    })


def _censo(raiz: Path) -> Any:
    return ler_o_barramento(raiz_usb=str(raiz / "bus" / "usb" / "devices"))


def test_o_censo_reconhece_o_receptor_e_acha_os_nos_de_evento_sob_o_filho_hid(
    tmp_path: Path,
) -> None:
    _receptor_de_mentira(tmp_path)
    (a,) = [x for x in _censo(tmp_path).aparelhos if x.nome_do_kernel == "1-6"]
    assert a.receptor is True
    assert sorted(a.interfaces) == ["030101", "030102"]
    assert sorted(a.eventos, key=lambda e: int(e[5:])) == ["event8", "event9", "event10", "event11"]
    # a interface 0 já diz «Mouse»: essa palavra (a sugestão de tipo da tela) fica
    assert a.especie == "Mouse"


def test_o_receptor_cuja_interface_zero_nao_diz_nada_vira_receptor_e_nao_aparelho(
    tmp_path: Path,
) -> None:
    _receptor_de_mentira(tmp_path, interfaces={
        "1.0": ("03", "00", "00", ["event8"]), "1.1": ("03", "01", "01", []),
        "1.2": ("03", "01", "02", [])})
    (a,) = [x for x in _censo(tmp_path).aparelhos if x.nome_do_kernel == "1-6"]
    assert a.receptor is True
    assert (a.especie, a.grau) == ("Receptor 2.4G", "lido")


def test_o_mouse_com_fio_e_o_teclado_de_cabo_nao_sao_receptor(tmp_path: Path) -> None:
    _receptor_de_mentira(tmp_path, "1-6", interfaces={"1.0": ("03", "01", "02", ["event8"])})
    _receptor_de_mentira(tmp_path, "1-7", velocidade="480", produto="Gaming Keyboard",
                         interfaces={"1.0": ("03", "01", "01", ["event9"]),
                                     "1.1": ("03", "01", "02", ["event10"])})
    achados = {a.nome_do_kernel: a for a in _censo(tmp_path).aparelhos}
    assert not achados["1-6"].receptor and not achados["1-7"].receptor


def test_o_controle_hid_se_conhece_pelo_botao_sul_mesmo_sob_o_filho_hid(tmp_path: Path) -> None:
    """Medido em 05/10/2026: o `input` do HID mora no filho `0003:…`, não na interface."""
    _no_usb(tmp_path, "1-3", {"idVendor": "cccc", "idProduct": "dddd", "speed": "12",
                              "busnum": "1", "devpath": "3", "bDeviceClass": "00"},
            {"1.0": ("ff", "00", "00", ["event3"])})
    caps = next((tmp_path / "devices").rglob("capabilities"))
    (caps / "key").write_text(f"{1 << 48:x} 0 0 0 0\n")
    (a,) = [x for x in _censo(tmp_path).aparelhos if x.nome_do_kernel == "1-3"]
    assert a.ligado_como == "controle"


# --- 2. a saúde: tecla presa e buraco no movimento -------------------------------------------

CODIGO_DA_TECLA = 30


def _contador() -> rx.ContadorDaSaude:
    return rx.ContadorDaSaude(sal=7)


def test_tecla_apertada_repetindo_sem_soltar_por_mais_de_um_segundo_e_uma_presa() -> None:
    c = _contador()
    c.tecla(1, CODIGO_DA_TECLA, 100.0)
    for t in (100.5, 100.9):
        c.tecla(2, CODIGO_DA_TECLA, t)
    assert c.saude(101.0).teclas_presas == 0, "menos de 1 s é a mão segurando"
    c.tecla(2, CODIGO_DA_TECLA, 101.5)
    assert c.saude(101.6).teclas_presas == 1
    c.tecla(2, CODIGO_DA_TECLA, 101.6)
    assert c.saude(101.7).teclas_presas == 1, "a mesma tecla conta uma vez só"


def test_a_tecla_que_solta_pelo_proprio_solta_nao_e_presa() -> None:
    c = _contador()
    c.tecla(1, CODIGO_DA_TECLA, 100.0)
    c.tecla(2, CODIGO_DA_TECLA, 101.5)
    assert c.saude(101.6).teclas_presas == 1
    c.tecla(0, CODIGO_DA_TECLA, 101.8)
    assert c.saude(102.0).teclas_presas == 0, "soltou: era a mão, e a conta se desfaz"


def test_duas_teclas_presas_sao_duas_e_a_hora_passa() -> None:
    c = _contador()
    for codigo, t in ((30, 100.0), (48, 200.0)):
        c.tecla(1, codigo, t)
        c.tecla(2, codigo, t + 1.2)
    assert c.saude(300.0).teclas_presas == 2
    assert c.saude(100.0 + rx.JANELA_S + 5).teclas_presas == 1, "a primeira saiu da última hora"


def test_o_contador_nunca_guarda_o_codigo_da_tecla() -> None:
    c = _contador()
    c.tecla(1, CODIGO_DA_TECLA, 100.0)
    c.tecla(2, CODIGO_DA_TECLA, 101.5)
    assert CODIGO_DA_TECLA not in c._apertadas, "a identidade é um token, não o código"
    publicado = json.dumps(c.saude(102.0).publicar())
    assert set(json.loads(publicado)) == {"teclas_presas", "buracos", "janela_s", "lendo"}
    for chave in ("code", "codigo", "tecla", "key"):  # (noqa-acento): nome de campo, ASCII
        assert chave not in publicado.replace("teclas_presas", "")


def _corrida(c: rx.ContadorDaSaude, ini: float, n: int, passo: float) -> float:
    t = ini
    for _ in range(n):
        c.movimento(t)
        t += passo
    return t


def test_buraco_so_conta_no_meio_de_movimento_continuo() -> None:
    c = _contador()
    t = _corrida(c, 10.0, 40, 0.001)
    c.movimento(t + 0.012)  # 12 ms sem report, no meio do movimento
    assert c.saude(20.0).buracos == 1


def test_a_mao_parada_nao_e_buraco() -> None:
    c = _contador()
    t = _corrida(c, 10.0, 40, 0.001)
    c.movimento(t + 0.3)  # parou e recomeçou: HID só manda report quando algo muda
    assert c.saude(20.0).buracos == 0
    c.movimento(t + 0.3 + 0.012)  # a corrida recomeçou do zero: 12 ms logo depois não é buraco
    assert c.saude(20.0).buracos == 0


def test_sem_movimento_continuo_nao_ha_o_que_medir() -> None:
    c = _contador()
    c.movimento(10.0)
    c.movimento(10.012)
    assert c.saude(20.0).buracos == 0


def test_o_mouse_de_125_hz_nao_tem_buraco_a_cada_report() -> None:
    """O limite é relativo ao intervalo do PRÓPRIO mouse: 8 ms é o normal dele."""
    c = _contador()
    t = _corrida(c, 10.0, 40, 0.008)
    c.movimento(t + 0.008)
    assert c.saude(20.0).buracos == 0
    c.movimento(t + 0.008 + 0.040)  # cinco intervalos: aí sim falhou
    assert c.saude(20.0).buracos == 1


def test_o_mesmo_report_nao_e_buraco_nem_intervalo() -> None:
    c = _contador()
    for k in range(40):  # REL_X e REL_Y do mesmo report chegam com o mesmo instante
        c.movimento(10.0 + k * 0.001)
        c.movimento(10.0 + k * 0.001)
    c.movimento(10.0 + 39 * 0.001 + 0.002)
    assert c.saude(20.0).buracos == 0


# --- 3. o monitor lê o evdev (aqui, um pipe) --------------------------------------------------


class Pipes:
    """Um `/dev/input` de mentira: cada caminho é um pipe onde a régua escreve eventos."""

    def __init__(self) -> None:
        self.por_caminho: dict[str, tuple[int, int]] = {}
        self.recusados: set[str] = set()

    def abrir(self, caminho: str) -> int:
        if caminho in self.recusados:
            raise PermissionError(13, "sem o grupo input", caminho)
        if caminho not in self.por_caminho:
            r, w = os.pipe()
            os.set_blocking(r, False)
            self.por_caminho[caminho] = (r, w)
        return self.por_caminho[caminho][0]

    def escrever(self, caminho: str, *eventos: tuple[int, int, int, float]) -> None:
        os.write(self.por_caminho[caminho][1],
                 b"".join(rx.empacotar_evento(*e) for e in eventos))

    def fechar_tudo(self) -> None:
        for r, w in self.por_caminho.values():
            for fd in (r, w):
                with contextlib.suppress(OSError):
                    os.close(fd)


@pytest.fixture
def pipes() -> Any:
    p = Pipes()
    yield p
    p.fechar_tudo()


CHAVE = "usb:aaaa:bbbb"
TECLADO = "/dev/input/event9"
MOUSE = "/dev/input/event8"


def _monitor(pipes: Pipes, varrer: Any = None, agora: float = 500.0) -> rx.MonitorDosReceptores:
    varrer = varrer or (lambda: {CHAVE: (MOUSE, TECLADO)})
    return rx.MonitorDosReceptores(
        varrer, abrir=pipes.abrir, fechar=lambda fd: None, relogio=lambda: agora, varredura_s=0.0)


def _volta(m: rx.MonitorDosReceptores, n: int = 3) -> None:
    for _ in range(n):
        m.passo(0.01)


def test_o_monitor_conta_a_tecla_presa_e_o_buraco_lidos_do_evdev(pipes: Pipes) -> None:
    m = _monitor(pipes)
    _volta(m, 1)
    pipes.escrever(TECLADO, (rx.EV_KEY, 30, 1, 100.0), (rx.EV_KEY, 30, 2, 101.5))
    pipes.escrever(MOUSE, *[(rx.EV_REL, rx.REL_X, 1, 200.0 + k * 0.001) for k in range(40)],
                   (rx.EV_REL, rx.REL_X, 1, 200.0 + 39 * 0.001 + 0.015))
    _volta(m)
    assert m.publicar() == {CHAVE: {"teclas_presas": 1, "buracos": 1, "janela_s": rx.JANELA_S,
                                    "lendo": True}}


def test_o_botao_do_mouse_e_a_rolagem_nao_contam_como_tecla_nem_movimento(pipes: Pipes) -> None:
    m = _monitor(pipes)
    _volta(m, 1)
    btn_left, rel_wheel = 0x110, 8
    pipes.escrever(MOUSE, (rx.EV_KEY, btn_left, 1, 100.0), (rx.EV_KEY, btn_left, 2, 105.0),
                   *[(rx.EV_REL, rel_wheel, 1, 200.0 + k * 0.001) for k in range(40)],
                   (rx.EV_REL, rel_wheel, 1, 200.1))
    _volta(m)
    assert m.publicar()[CHAVE]["teclas_presas"] == 0
    assert m.publicar()[CHAVE]["buracos"] == 0


def test_sem_permissao_para_abrir_o_receptor_nao_publica_numero_nenhum(pipes: Pipes) -> None:
    pipes.recusados = {MOUSE, TECLADO}
    m = _monitor(pipes)
    _volta(m)
    # sem leitura não há número: «sem falhas» seria dizer o que não se mediu
    assert m.publicar() == {}


def test_o_receptor_que_sai_do_censo_sai_do_estado(pipes: Pipes) -> None:
    onde = {CHAVE: (MOUSE, TECLADO)}
    m = _monitor(pipes, varrer=lambda: onde)
    _volta(m, 1)
    assert CHAVE in m.publicar()
    onde.clear()
    _volta(m, 1)
    assert m.publicar() == {}


def test_o_estado_publicado_nunca_leva_o_codigo_da_tecla(pipes: Pipes) -> None:
    m = _monitor(pipes)
    _volta(m, 1)
    codigo = 4242 % 0x100
    pipes.escrever(TECLADO, (rx.EV_KEY, codigo, 1, 100.0), (rx.EV_KEY, codigo, 2, 102.0))
    _volta(m)
    texto = json.dumps(m.publicar())
    assert str(codigo) not in texto
    assert "codigo" not in texto and "code" not in texto  # (noqa-acento): nome de campo, ASCII


# --- 4. o IPC: a chave do estado e a guarda da suíte -------------------------------------------


def test_o_state_full_publica_a_saude_pela_chave_radio_receptores(
    monkeypatch: pytest.MonkeyPatch, pipes: Pipes
) -> None:
    from tests.unit.test_os_hz_de_cada_controle import _handlers

    handlers = _handlers(monkeypatch)[1]
    handlers._monitor_de_receptores = _monitor(pipes)  # type: ignore[attr-defined]
    handlers._monitor_de_receptores.passo(0.01)  # type: ignore[attr-defined]
    pipes.escrever(TECLADO, (rx.EV_KEY, 30, 1, 100.0), (rx.EV_KEY, 30, 2, 101.5))
    handlers._monitor_de_receptores.passo(0.01)  # type: ignore[attr-defined]
    publicado = handlers._os_receptores_publicam()  # type: ignore[attr-defined]
    assert publicado[CHAVE]["teclas_presas"] == 1


def test_o_enriquecimento_do_state_full_leva_a_chave_dos_receptores(
    monkeypatch: pytest.MonkeyPatch, pipes: Pipes
) -> None:
    from tests.unit.test_os_hz_de_cada_controle import _handlers

    handlers = _handlers(monkeypatch)[1]
    handlers._monitor_de_receptores = _monitor(pipes)  # type: ignore[attr-defined]
    handlers._monitor_de_receptores.passo(0.01)  # type: ignore[attr-defined]
    resultado: dict[str, Any] = {}
    handlers._enriquecer_e_medir_o_ar(resultado, [], None)  # type: ignore[attr-defined]
    assert CHAVE in resultado["radio_receptores"]


def test_sob_a_suite_o_daemon_nao_abre_evdev_nenhum(monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.unit.test_os_hz_de_cada_controle import _handlers

    handlers = _handlers(monkeypatch)[1]
    chamadas: list[str] = []
    handlers._varrer_os_receptores = None  # type: ignore[attr-defined]
    handlers._receptores_do_censo = lambda: chamadas.append("censo") or {}  # type: ignore[attr-defined,method-assign]
    assert handlers._os_receptores_publicam() == {}  # type: ignore[attr-defined]
    assert chamadas == [] and handlers._monitor_de_receptores is None  # type: ignore[attr-defined]


# --- 5. a palavra do selo ---------------------------------------------------------------------


def test_o_teclado_fala_em_teclas_presas_e_o_mouse_em_engasgos() -> None:
    lendo = {"lendo": True, "janela_s": 3600}
    assert rx.selo_da_saude({**lendo, "teclas_presas": 3, "buracos": 0}, "teclado") == (
        "sofrendo", "3 teclas presas", "em 1 h")
    assert rx.selo_da_saude({**lendo, "teclas_presas": 1, "buracos": 0}, "teclado") == (
        "apertada", "1 tecla presa", "em 1 h")
    assert rx.selo_da_saude({**lendo, "teclas_presas": 0, "buracos": 0}, "teclado") == (
        "boa", "sem falhas", "")
    assert rx.selo_da_saude({**lendo, "teclas_presas": 9, "buracos": 25}, "mouse") == (
        "sofrendo", "engasgou 25×", "em 1 h")
    assert rx.selo_da_saude({**lendo, "teclas_presas": 0, "buracos": 0}, "mouse") == (
        "boa", "sem falhas", "")


def test_sem_leitura_nao_ha_selo() -> None:
    assert rx.selo_da_saude({"lendo": False, "teclas_presas": 0, "buracos": 0}, "teclado") is None
    assert rx.selo_da_saude(None, "mouse") is None


# --- 6. achar a faixa por eliminação ------------------------------------------------------------


def test_a_banda_e_a_diferenca_dos_canais_que_o_adaptador_passou_a_evitar() -> None:
    sem = {"L1": tuple(range(49, 71)), "L2": ()}
    com = {"L1": tuple(range(49, 71)) + tuple(range(18, 35)), "L2": tuple(range(20, 30))}
    assert rx.banda_por_eliminacao(sem, com) == (18, 35)


def test_o_canal_solto_e_o_proprio_afh_e_a_resposta_e_nao_achei() -> None:
    assert rx.banda_por_eliminacao({"L1": ()}, {"L1": (5, 40)}) is None
    assert rx.banda_por_eliminacao({"L1": ()}, {"L1": ()}) is None


def test_o_adaptador_que_nao_mede_nao_entra_na_conta() -> None:
    assert rx.banda_por_eliminacao({"L1": None, "L2": ()}, {"L1": tuple(range(10, 20)),
                                                            "L2": ()}) is None


def _evitados(estado: dict[str, Any]) -> Any:
    return lambda: estado["agora"]


def test_o_gesto_guiado_tire_mede_ponha_mede_e_acha_a_faixa() -> None:
    d = rx.Descoberta()
    estado: dict[str, Any] = {"agora": {"L1": tuple(range(49, 71))}}
    d.iniciar(CHAVE, 0.0)
    assert d.passo == rx.PASSO_TIRE and d.ativa
    d.andar(100.0, _evitados(estado))
    assert d.passo == rx.PASSO_TIRE, "o gesto dela é quem anda aqui"
    d.avancar(10.0)
    assert d.passo == rx.PASSO_MEDINDO_SEM
    d.andar(10.0 + rx.ESPERA_DA_MEDIDA_S - 1, _evitados(estado))
    assert d.passo == rx.PASSO_MEDINDO_SEM, "o adaptador ainda está aprendendo"
    d.andar(10.0 + rx.ESPERA_DA_MEDIDA_S, _evitados(estado))
    assert d.passo == rx.PASSO_PONHA
    d.avancar(60.0)
    estado["agora"] = {"L1": tuple(range(49, 71)) + tuple(range(18, 35))}
    d.andar(60.0 + rx.ESPERA_DA_MEDIDA_S, _evitados(estado))
    assert (d.passo, d.banda, d.ativa) == (rx.PASSO_ACHOU, (18, 35), False)


def test_o_gesto_que_nao_acha_diz_que_nao_achou() -> None:
    d = rx.Descoberta()
    estado: dict[str, Any] = {"agora": {"L1": ()}}
    d.iniciar(CHAVE, 0.0)
    d.avancar(1.0)
    d.andar(1.0 + rx.ESPERA_DA_MEDIDA_S, _evitados(estado))
    d.avancar(50.0)
    d.andar(50.0 + rx.ESPERA_DA_MEDIDA_S, _evitados(estado))
    assert (d.passo, d.banda) == (rx.PASSO_NADA, None)


def test_a_banda_medida_cabe_no_maquina_json() -> None:
    from hefesto_dualsense4unix.utils.maquina import RadioDeclarado

    ok = RadioDeclarado(banda=[18, 35], banda_em="2026-10-05")
    assert ok.banda == [18, 35]
    for ruim in ([35, 18], [0, 80], [5], [-1, 4]):
        with pytest.raises(ValueError):
            RadioDeclarado(banda=ruim)
    with pytest.raises(ValueError):
        RadioDeclarado(banda_em="ontem")

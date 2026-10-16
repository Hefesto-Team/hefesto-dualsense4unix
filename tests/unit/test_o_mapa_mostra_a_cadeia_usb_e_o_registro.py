"""O Mapa das Conexões mostra a cadeia USB e o registro do que entra e sai.

O-MAPA-DAS-CONEXOES-MOSTRA-A-CADEIA-USB-E-O-REGISTRO-DELA-01. O ``/sys`` de mentira
(``tests/fixtures/cadeia_usb/``) é o da sprint de produto; o diário é o que o ouvido do USB
escreve de verdade, lido pelo arquivo, sem IPC.

Mordidas (cada uma arrancada, vista reprovar e devolvida):

* ``_a_cadeia_usb`` sem ``hubs_fisicos``: o hub volta a ser vários chips e
  :func:`test_o_hub_de_dois_lados_e_um_chip_de_sete_entradas` reprova;
* ``enlace_abaixo`` sem a exigência de ``sabe_superspeed``: o receptor e o Bluetooth ganham a
  marca e :func:`test_a_marca_do_enlace_so_no_aparelho_que_publica_superspeed` reprova;
* ``_o_registro`` sem a janela de 5 s do hub: ele que sai vira duas linhas e
  :func:`test_o_hub_que_sai_e_uma_linha_so` reprova;
* sem o ``reversed``: a mais velha sobe e os dois testes de ordem e de teto reprovam;
* ``_os_que_sumiram`` sem o filtro do boot (ou sem a recusa do boot desconhecido):
  :func:`test_quem_nao_apareceu_fica_esmaecido_ate_entrar` reprova;
* ``_o_registro`` que monta linha quando o diário está vazio:
  :func:`test_o_diario_vazio_nao_inventa_linha` reprova.
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import ouvido_do_usb as ou
from hefesto_dualsense4unix.integrations import diario_do_usb as du
from hefesto_dualsense4unix.integrations.censo_do_barramento import ler_o_barramento
from hefesto_dualsense4unix.interface import arranjo_desta_maquina, pagina_do_mapa
from hefesto_dualsense4unix.utils.maquina import (
    FaceDeclarada,
    MapaDaMesa,
    MaquinaConfig,
    PortaDeclarada,
    RadioDeclarado,
)
from tests.fixtures.cadeia_usb.montar import SysDeMentira, carregar

BASE_DO_RELOGIO = 1_700_000_000.0
ADAPTADOR = "3-1.1.3"
WIFI = "3-1.4"
ENTRADA_DO_WIFI = "5"


class Relogio:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


@pytest.fixture
def sys_usb(tmp_path: Path) -> SysDeMentira:
    return SysDeMentira(tmp_path / "sys")


@pytest.fixture
def relogio() -> Relogio:
    return Relogio()


def _documento(**radios: RadioDeclarado) -> MaquinaConfig:
    mapa = MapaDaMesa(
        faces=[FaceDeclarada(nome="Traseira", portas=["1", ENTRADA_DO_WIFI])],
        portas={"1": PortaDeclarada(nos=["usb3-port1"]),
                ENTRADA_DO_WIFI: PortaDeclarada.model_validate({"caminho": WIFI})},
    )
    documento = MaquinaConfig(mapa=mapa)
    documento.mesa.radios.update(radios)
    return documento


def _arranjo(
    sys_usb: SysDeMentira, *, documento: MaquinaConfig | None = None,
    diario: list[dict[str, Any]] | None = None, boot: str = "boot-b",
    agora: float = BASE_DO_RELOGIO + 200,
) -> dict[str, Any]:
    dado = arranjo_desta_maquina.arranjo(
        agora=_dt.datetime.fromtimestamp(agora),
        carregar=lambda: documento or _documento(),
        ler_o_barramento=lambda: ler_o_barramento(**sys_usb.fontes()),
        ler_o_diario=lambda: [] if diario is None else diario,
        boot_id=lambda: boot,
    )
    assert dado is not None
    return dado


def _por_modelo(dado: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    saida: dict[str, list[dict[str, Any]]] = {}
    for aparelho in dado["aparelhos"]:
        saida.setdefault(aparelho["modelo"], []).append(aparelho)
    return saida


def _ouvido(sys_usb: SysDeMentira, tmp_path: Path, relogio: Relogio, boot: str) -> ou.Ouvido:
    return ou.Ouvido(
        ler_censo=lambda: ler_o_barramento(**sys_usb.fontes()),
        diario=tmp_path / "estado" / du.NOME_DO_DIARIO,
        boot_id=boot,
        relogio=relogio,
        agora=lambda: BASE_DO_RELOGIO + relogio.t,
    )


def _hora(carimbo: float) -> str:
    return _dt.datetime.fromtimestamp(carimbo).astimezone().strftime("%H:%M")


# ── a cadeia ────────────────────────────────────────────────────────────────


def test_o_hub_de_dois_lados_e_um_chip_de_sete_entradas(sys_usb: SysDeMentira) -> None:
    dado = _arranjo(sys_usb)
    hubs = [a for a in dado["aparelhos"] if a["classe"] == "hub"]
    assert len(hubs) == 4, "o /sys de mentira enumera quatro nós para o hub de plástico"

    chips = [a for a in hubs if "hubFisico" in a]
    assert [a["hubFisico"] for a in chips] == ["Hub USB 3 · 7 entradas"], (
        f"o hub tem de ser UM chip com as sete entradas: {[a.get('hubFisico') for a in hubs]}")
    (chip,) = chips
    resto = [a for a in hubs if a is not chip]
    assert all(a.get("parteDe") == chip["id"] for a in resto), (
        "os outros três nós são partes do mesmo hub, e a página não os desenha")

    pendem = [a for a in dado["aparelhos"] if a["classe"] != "hub"]
    assert len(pendem) == 4
    assert all(a.get("dentroDe") == chip["id"] for a in pendem), (
        "todo aparelho de baixo pende do hub físico, não de um dos nós internos")


def test_o_hub_so_com_o_lado_20_diz_usb_2(sys_usb: SysDeMentira) -> None:
    for lado in ("4-1.1", "4-1"):
        sys_usb.tirar(lado)
    (chip,) = [a for a in _arranjo(sys_usb)["aparelhos"] if "hubFisico" in a]
    assert chip["hubFisico"].startswith("Hub USB 2 · "), chip["hubFisico"]


def test_a_marca_do_enlace_so_no_aparelho_que_publica_superspeed(sys_usb: SysDeMentira) -> None:
    dado = _arranjo(sys_usb)
    com_enlace = {a["modelo"]: a["enlace"] for a in dado["aparelhos"] if "enlace" in a}
    assert com_enlace == {"f0e2:0811": "480 Mb/s · Sabe 5 Gb/s"}, (
        "só o Wi-Fi sabe 5 Gb/s e negociou 480 Mb/s; o receptor e o Bluetooth a 12 Mb/s "
        f"não publicam SuperSpeed: {com_enlace}")
    (wifi,) = _por_modelo(dado)["f0e2:0811"]
    assert "480 Mb/s · Sabe 5 Gb/s" in wifi["etiquetas"]
    assert "USB 2.0" not in wifi["etiquetas"], "o enlace diz o fato no lugar do «USB 2.0»"

    sys_usb.nos[WIFI].pop("bos")
    sys_usb.montar()
    sem_bos = _arranjo(sys_usb)
    assert not [a for a in sem_bos["aparelhos"] if "enlace" in a], (
        "sem o BOS não se sabe que ele sabe 5 Gb/s: sem marca")


def test_o_apelido_dela_vence_o_nome_da_maquina(sys_usb: SysDeMentira) -> None:
    documento = _documento(**{"f0e2:0811": RadioDeclarado(apelido="Minha antena")})
    (wifi,) = _por_modelo(_arranjo(sys_usb, documento=documento))["f0e2:0811"]
    assert wifi["nomeDeclarado"] == "Minha antena"
    assert wifi["nome"] == "Placa de rede sem fio", "o nome da máquina segue na linha de baixo"


def test_o_nome_da_base_so_entra_quando_o_descritor_calou(sys_usb: SysDeMentira) -> None:
    (antes,) = _por_modelo(_arranjo(sys_usb))["f0e4:0b70"]
    assert antes["nome"] == "Adaptador de rádio", "o descritor fala: vale o descritor"

    sys_usb.nos[ADAPTADOR]["attrs"].pop("product")
    sys_usb.dados["base"][ADAPTADOR]["ID_MODEL_FROM_DATABASE"] = "Adaptador da Base"
    sys_usb.montar()
    (depois,) = _por_modelo(_arranjo(sys_usb))["f0e4:0b70"]
    assert depois["nome"] == "Adaptador da Base"


# ── o registro ──────────────────────────────────────────────────────────────


def _uma_noite(sys_usb: SysDeMentira, tmp_path: Path, relogio: Relogio) -> Path:
    """Um boot com o adaptador Bluetooth fora e, depois, as cinco formas e a volta dele."""
    _ouvido(sys_usb, tmp_path, relogio, "boot-a").comecar(com_netlink=True)
    adaptador = dict(sys_usb.nos[ADAPTADOR])
    wifi = dict(sys_usb.nos[WIFI])
    sys_usb.tirar(ADAPTADOR)

    relogio.t = 0.0
    ouvido = _ouvido(sys_usb, tmp_path, relogio, "boot-b")
    ouvido.comecar(com_netlink=True)
    relogio.t = 61.0
    ouvido.conferir_ausentes()  # Não apareceu
    relogio.t = 70.0
    sys_usb.tirar(WIFI)
    ouvido.reler()  # Saiu
    relogio.t = 72.0
    sys_usb.por(WIFI, wifi)
    sys_usb.mudar(WIFI, devnum="31", speed="12")
    ouvido.reler()  # Voltou, Ficou mais lento
    relogio.t = 80.0
    sys_usb.mudar(WIFI, speed="480")
    ouvido.reler()  # Ficou mais rápido
    relogio.t = 90.0
    sys_usb.por(ADAPTADOR, adaptador)
    ouvido.reler()  # Entrou
    return tmp_path / "estado" / du.NOME_DO_DIARIO


def test_o_registro_tem_as_seis_formas_de_evento_a_mais_nova_em_cima(
        sys_usb: SysDeMentira, tmp_path: Path, relogio: Relogio) -> None:
    arquivo = _uma_noite(sys_usb, tmp_path, relogio)
    dado = _arranjo(sys_usb, diario=du.ler(arquivo), agora=BASE_DO_RELOGIO + 100)

    linhas = dado["registro"]["linhas"]
    assert [(linha["evento"], linha["tipo"], linha["onde"]) for linha in linhas] == [
        ("Entrou", "Bluetooth", "Sem entrada marcada"),
        ("Ficou mais rápido", "Wi-Fi", f"Entrada {ENTRADA_DO_WIFI}"),
        ("Ficou mais lento", "Wi-Fi", f"Entrada {ENTRADA_DO_WIFI}"),
        ("Voltou", "Wi-Fi", f"Entrada {ENTRADA_DO_WIFI}"),
        ("Saiu", "Wi-Fi", f"Entrada {ENTRADA_DO_WIFI}"),
        ("Não apareceu", "Bluetooth", "—"),
    ], [(linha["evento"], linha["tipo"]) for linha in linhas]
    assert {linha["tom"] for linha in linhas} == {"", "sai", "lento", "sumiu"}
    assert linhas[0]["hora"] == _hora(BASE_DO_RELOGIO + 90)
    assert linhas[0]["nome"] == "Adaptador de rádio"
    assert dado["registro"]["ouvindo"] == "Ouvindo desde " + _hora(BASE_DO_RELOGIO)
    assert all("serial" not in linha for linha in linhas) and "no" not in linhas[0], (
        "nenhum endereço nem caminho vai à tela")


def test_o_apelido_vence_tambem_no_registro(
        sys_usb: SysDeMentira, tmp_path: Path, relogio: Relogio) -> None:
    arquivo = _uma_noite(sys_usb, tmp_path, relogio)
    documento = _documento(**{"f0e2:0811": RadioDeclarado(apelido="Minha antena")})
    linhas = _arranjo(sys_usb, documento=documento, diario=du.ler(arquivo))["registro"]["linhas"]
    assert {linha["nome"] for linha in linhas if linha["tipo"] == "Wi-Fi"} == {"Minha antena"}


def test_quem_nao_apareceu_fica_esmaecido_ate_entrar(
        sys_usb: SysDeMentira, tmp_path: Path, relogio: Relogio) -> None:
    arquivo = _uma_noite(sys_usb, tmp_path, relogio)
    todo = du.ler(arquivo)
    ate_o_aviso = [e for e in todo if e["o_que"] != du.ENTROU]

    sys_usb.tirar(ADAPTADOR)
    assert _arranjo(sys_usb, diario=ate_o_aviso)["sumiram"] == [
        {"tipo": "Bluetooth", "nome": "Adaptador de rádio", "cor": "#bd93f9"}]
    assert _arranjo(sys_usb, diario=ate_o_aviso, boot="boot-c")["sumiram"] == [], (
        "o aviso é do início daquele boot: noutro boot ele não vale")
    sem_boot = [{**e, "boot_id": ""} for e in ate_o_aviso]
    assert _arranjo(sys_usb, diario=sem_boot, boot="")["sumiram"] == [], (
        "sem saber o boot não se afirma que algo não apareceu")

    sys_usb.por(ADAPTADOR, carregar()["nos"][ADAPTADOR])
    assert _arranjo(sys_usb, diario=todo)["sumiram"] == [], "quem entrou depois não sumiu"


def test_o_diario_vazio_nao_inventa_linha(sys_usb: SysDeMentira, tmp_path: Path) -> None:
    sem_nada = _arranjo(sys_usb, diario=[])
    assert sem_nada["registro"] == {"ouvindo": "Ainda sem registro", "linhas": []}
    assert sem_nada["sumiram"] == []

    so_comeco = [{
        "quando": "", "carimbo": BASE_DO_RELOGIO, "quem": du.QUEM, "o_que": du.COMECOU_A_OUVIR,
        "boot_id": "boot-b"}]
    assert _arranjo(sys_usb, diario=so_comeco)["registro"] == {
        "ouvindo": "Ouvindo desde " + _hora(BASE_DO_RELOGIO), "linhas": []}


def test_depois_de_parar_o_registro_diz_desde_quando_nao_ouve(sys_usb: SysDeMentira) -> None:
    diario = [
        {"carimbo": BASE_DO_RELOGIO, "quem": du.QUEM, "o_que": du.COMECOU_A_OUVIR},
        {"carimbo": BASE_DO_RELOGIO + 60, "quem": du.QUEM, "o_que": du.PAROU_DE_OUVIR},
    ]
    assert _arranjo(sys_usb, diario=diario)["registro"]["ouvindo"] == (
        "Sem ouvir desde " + _hora(BASE_DO_RELOGIO + 60))


def test_o_registro_leva_no_maximo_trinta_linhas(sys_usb: SysDeMentira) -> None:
    diario = [{"carimbo": BASE_DO_RELOGIO + i, "quem": du.QUEM, "o_que": du.ENTROU,
               "tipo": "Wi-Fi", "vid": "f0e2", "pid": "0811", "no": WIFI, "produto": "Antena"}
              for i in range(45)]
    linhas = _arranjo(sys_usb, diario=diario)["registro"]["linhas"]
    assert len(linhas) == arranjo_desta_maquina.LIMITE_DO_REGISTRO == 30
    assert linhas[0]["hora"] == _hora(BASE_DO_RELOGIO + 44), "a mais nova vem primeiro"


def test_o_hub_que_sai_e_uma_linha_so(
        sys_usb: SysDeMentira, tmp_path: Path, relogio: Relogio) -> None:
    ouvido = _ouvido(sys_usb, tmp_path, relogio, "boot-a")
    ouvido.comecar(com_netlink=True)
    relogio.t = 5.0
    sys_usb.tirar("4-1")  # leva o lado SuperSpeed e a cascata dele: dois nós de hub
    ouvido.reler()

    saidas = [e for e in du.ler(tmp_path / "estado" / du.NOME_DO_DIARIO)
              if e["o_que"] == du.SAIU and e["tipo"] == "Hub"]
    assert len(saidas) == 2, "o kernel enumerou dois nós do mesmo hub de plástico"
    linhas = _arranjo(
        sys_usb, diario=du.ler(tmp_path / "estado" / du.NOME_DO_DIARIO),
        boot="boot-a")["registro"]["linhas"]
    assert [(linha["evento"], linha["tipo"]) for linha in linhas] == [("Saiu", "Hub")]


# ── a página ────────────────────────────────────────────────────────────────


def test_a_pagina_da_bancada_tem_a_cadeia_e_a_quarta_aba() -> None:
    texto = pagina_do_mapa.pagina()
    assert 'data-modo="registro"' in texto and 'id="registro"' in texto
    assert "Conectado agora</h3>" not in texto, "a lista é a cadeia"
    assert ">A cadeia</h3>" in texto
    assert 'id="registro-copiar"' in texto and ">Copiar</button>" in texto
    assert pagina_do_mapa.DICA_DO_ENLACE in texto
    assert "Pode ser a entrada, o hub, o cabo, o extensor ou o próprio aparelho." in texto


def test_a_cadeia_espera_a_sessao_dela_e_nao_entra_na_copia_do_produto() -> None:
    publicada = pagina_do_mapa.pagina(False)
    assert 'data-modo="registro"' not in publicada
    assert ">Conectado agora</h3>" in publicada


def test_o_que_a_pagina_le_do_registro_e_o_que_o_produtor_manda(sys_usb: SysDeMentira) -> None:
    dado = _arranjo(sys_usb)
    for chave in ("sumiram", "registro"):
        assert f"fonte.{chave}" in pagina_do_mapa.JS_DA_CADEIA_E_DO_REGISTRO
        assert chave in dado
    for campo in ("hubFisico", "parteDe", "dentroDe", "enlace"):
        assert f"a.{campo}" in pagina_do_mapa.JS_DA_CADEIA_E_DO_REGISTRO, (
            f"o produtor manda `{campo}` e a página não o lê")

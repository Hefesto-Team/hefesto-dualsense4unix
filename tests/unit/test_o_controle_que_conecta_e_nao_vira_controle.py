"""CONEXAO-ZUMBI-01 — o controle que conecta e NÃO vira controle.

Ela viu quatro coisas com dois DualSense ligados (18/09/2026): *"o lightbar tá
sem a solução"*, *"a mudança dos leds e afins não foram aplicadas pros demais
controles"*, *"ambos conectados, ambos como player 1 e ambos com lightbar
azul"*, *"com dois ou mais controles conectados a interface do app para de
funcionar"*. As quatro são UMA causa: o segundo controle tinha conexão de rádio
de pé e **nenhum registro no BlueZ** — sem HID, sem `hidraw`, sem nó de LED. O
controle ficava no padrão de fábrica, que é literalmente barra azul e jogador 1.

ESTE ARQUIVO COBRA AS DUAS METADES, e a segunda é a que importa mais:

  1. o produto DERRUBA o link que não virou controle;
  2. o produto **não toca** em nada que esteja funcionando.

A segunda é a metade cara. *Derrubar quem está funcionando é pior que o
defeito* — e um portão que só sabe acusar passa verde com o detector trocado
por "tudo é zumbi".

O TEMPO É PARTE DA REGRA, E POR ISSO ELE É MEDIDO AQUI DE DUAS FORMAS
----------------------------------------------------------------------
Uma régua que olha uma vez mede um INSTANTE, não um comportamento (em 29/08 uma
regressão só apareceu aos 181 segundos, com 67 testes verdes). Então:

* :func:`test_o_relogio_do_vigia_atravessa_minutos` viaja **quatro minutos** com
  o relógio injetado, sem dormir — e prova que o mesmo link oscilando NÃO soma
  instantes soltos até virar zumbi;
* :func:`test_o_laco_do_subsystem_mede_o_tempo_de_verdade` roda o laço REAL, com
  `time.monotonic` de verdade e uma thread de verdade, e exige que ele só cure
  depois de a janela passar — o instante inicial tem de sair sem cura.

A MESA DELA NÃO É TOCADA. Todos os leitores entram por injeção, e os endereços
são da faixa sintética da casa (`aa:bb:cc:…`). Nenhum teste chama `hcitool`,
`busctl` ou `sudo` de verdade — o `desconectar` corta rádio, e cortar o rádio
dela no meio de uma partida é exatamente o defeito que esta sprint cura.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import SUBSYSTEM_REGISTRY
from hefesto_dualsense4unix.daemon.subsystems.conexoes import (
    ConexoesSubsystem,
    ler_o_diario,
)
from hefesto_dualsense4unix.integrations.conexao_zumbi import (
    LinkDeRadio,
    PedidoAPonte,
    PontePrivilegiada,
    VigiaDeZumbis,
    adaptadores_na_mesa,
    enderecos_que_o_bluez_conhece,
    links_de_pe,
    mac_limpo,
    uniqs_com_hid,
    zumbis,
)

RAIZ = Path(__file__).resolve().parents[2]

DONGLE_A = "aa:bb:cc:00:00:11"
DONGLE_B = "aa:bb:cc:00:00:33"
SAO = "aa:bb:cc:00:00:22"
ZUMBI = "aa:bb:cc:00:00:44"

LINK_SAO = LinkDeRadio(hci="hci0", adaptador=DONGLE_A, controle=SAO)
LINK_ZUMBI = LinkDeRadio(hci="hci1", adaptador=DONGLE_B, controle=ZUMBI)

CONHECIDOS = {("hci0", SAO)}


class PonteDeMentira:
    """Uma ponte que ANOTA em vez de cortar o rádio de alguém."""

    def __init__(self, *, funciona: bool = True, impede: list[str] | None = None) -> None:
        self.pedidos: list[tuple[str, str, str]] = []
        self._funciona = funciona
        self._impede = impede or []

    def impedimentos(self) -> list[str]:
        return list(self._impede)

    def desconectar(self, link: LinkDeRadio) -> tuple[bool, str]:
        self.pedidos.append((link.hci, link.adaptador, link.controle))
        return (True, "") if self._funciona else (False, "a ponte saiu com 1")


def _vigia(ponte: Any, **kwargs: Any) -> VigiaDeZumbis:
    return VigiaDeZumbis(ponte=ponte, **kwargs)


def test_o_link_sem_hid_e_sem_bluez_e_zumbi() -> None:
    """As três condições juntas — o caso que ela viu."""
    achados = zumbis([LINK_SAO, LINK_ZUMBI], {SAO}, CONHECIDOS)
    assert [z.controle for z in achados] == [ZUMBI]


def test_o_link_com_hidraw_nunca_e_zumbi() -> None:
    """A MORDIDA que mais importa: quem virou controle não se toca.

    Sem esta, o detector poderia acusar todo link do rádio — e a cura seria
    derrubar os quatro DualSense da mesa dela.
    """
    assert zumbis([LINK_SAO], {SAO}, CONHECIDOS) == []
    assert zumbis([LINK_ZUMBI], {SAO, ZUMBI}, CONHECIDOS | {("hci1", ZUMBI)}) == []


def test_o_conectado_que_o_bluez_conhece_e_outro_defeito() -> None:
    """Sem `hidraw` mas COM objeto no BlueZ não é este defeito — é o cache SDP."""
    conhecidos = CONHECIDOS | {("hci1", ZUMBI)}
    assert zumbis([LINK_ZUMBI], {SAO}, conhecidos) == []


def test_sem_a_leitura_do_bluez_ninguem_e_acusado() -> None:
    """Ausência de leitura é *"não sei"*, e "não sei" nunca autoriza agir."""
    assert zumbis([LINK_SAO, LINK_ZUMBI], set(), set()) == []


def test_o_adaptador_viaja_junto_com_o_endereco() -> None:
    """O rádio é POR ADAPTADOR, e a cura precisa saber em qual dongle agir."""
    ponte = PonteDeMentira()
    vigia = _vigia(ponte, segundos_para_zumbi=0.0)
    vigia.observar(100.0, [LINK_ZUMBI], {SAO}, CONHECIDOS)
    assert ponte.pedidos == [("hci1", DONGLE_B, ZUMBI)]


def test_o_suspeito_novo_ainda_nao_e_zumbi() -> None:
    """Todo controle passa instantes com link de pé e sem HID enquanto sobe."""
    ponte = PonteDeMentira()
    vigia = _vigia(ponte, segundos_para_zumbi=20.0)
    veredito = vigia.observar(0.0, [LINK_ZUMBI], {SAO}, CONHECIDOS)
    assert veredito.suspeitos and not veredito.zumbis
    assert ponte.pedidos == []


def test_o_relogio_do_vigia_atravessa_minutos() -> None:
    """Quatro minutos de relógio, sem dormir — e o que oscila NÃO soma."""
    ponte = PonteDeMentira()
    vigia = _vigia(ponte, segundos_para_zumbi=20.0)
    momento = 0.0
    for _ in range(12):
        vigia.observar(momento, [LINK_ZUMBI], {SAO}, CONHECIDOS)
        momento += 10.0
        vigia.observar(momento, [], {SAO, ZUMBI}, CONHECIDOS)
        momento += 10.0
    assert ponte.pedidos == [], "oscilar por quatro minutos virou zumbi por acumulação"

    vigia.observar(momento, [LINK_ZUMBI], {SAO}, CONHECIDOS)
    veredito = vigia.observar(momento + 21.0, [LINK_ZUMBI], {SAO}, CONHECIDOS)
    assert veredito.derrubados and ponte.pedidos


def test_a_cura_tem_teto_por_controle() -> None:
    """Uma derrubada por controle por janela — e o que sobra é um GESTO."""
    ponte = PonteDeMentira()
    vigia = _vigia(ponte, segundos_para_zumbi=0.0, janela_do_teto_s=600.0)
    primeiro = vigia.observar(100.0, [LINK_ZUMBI], {SAO}, CONHECIDOS)
    assert primeiro.derrubados

    segundo = vigia.observar(200.0, [LINK_ZUMBI], {SAO}, CONHECIDOS)
    assert not segundo.derrubados
    assert [z.controle for z in segundo.segurados_pelo_teto] == [ZUMBI]
    assert len(ponte.pedidos) == 1
    assert any("reparea" in linha or "repareá" in linha for linha in segundo.diario), (
        "o teto segurou a cura e não disse o gesto que resta — recusa sem gesto "
        "é exatamente o que a sprint proíbe"
    )

    terceiro = vigia.observar(100.0 + 601.0, [LINK_ZUMBI], {SAO}, CONHECIDOS)
    assert terceiro.derrubados
    assert len(ponte.pedidos) == 2


def test_sem_a_ponte_o_produto_nao_age_e_diz_por_que() -> None:
    """Sem ponte, sem sudo ou sem `hcitool`: não age, e o diário diz o motivo."""
    ponte = PonteDeMentira(impede=["a ponte privilegiada não está instalada"])
    vigia = _vigia(ponte, segundos_para_zumbi=0.0)
    veredito = vigia.observar(10.0, [LINK_ZUMBI], {SAO}, CONHECIDOS)
    assert veredito.zumbis and not veredito.derrubados
    assert ponte.pedidos == []
    assert veredito.impedimentos
    assert any(ZUMBI in linha for linha in veredito.diario)


def test_a_ponte_que_falha_vira_recado_e_nao_silencio() -> None:
    ponte = PonteDeMentira(funciona=False)
    vigia = _vigia(ponte, segundos_para_zumbi=0.0)
    veredito = vigia.observar(10.0, [LINK_ZUMBI], {SAO}, CONHECIDOS)
    assert not veredito.derrubados
    assert any("falhou" in linha for linha in veredito.diario)
    outro = vigia.observar(11.0, [LINK_ZUMBI], {SAO}, CONHECIDOS)
    assert len(ponte.pedidos) == 2, outro


def _executor(saidas: dict[tuple[str, ...], str]) -> Any:
    def correr(args: Any, *resto: Any) -> Any:
        return saidas.get(tuple(args), "")

    return correr


def test_o_leitor_de_links_le_a_saida_do_hcitool_por_adaptador() -> None:
    """O formato é o REAL, medido em 20/09/2026 (endereços trocados pela faixa"""
    saidas = {
        ("hcitool", "-i", "hci0", "con"): (
            "Connections:\n"
            f"\t> ACL {SAO.upper()} handle 5 state 1 lm CENTRAL AUTH ENCRYPT \n"
        ),
        ("hcitool", "-i", "hci1", "con"): (
            "Connections:\n"
            f"\t> ACL {ZUMBI.upper()} handle 7 state 1 lm PERIPHERAL AUTH ENCRYPT \n"
        ),
    }
    achados, impedimentos = links_de_pe(
        {"hci0": DONGLE_A, "hci1": DONGLE_B}, executor=_executor(saidas)
    )
    assert impedimentos == []
    assert {(link.hci, link.controle) for link in achados} == {
        ("hci0", SAO),
        ("hci1", ZUMBI),
    }
    assert {link.adaptador for link in achados} == {DONGLE_A, DONGLE_B}


def test_o_leitor_do_bluez_le_a_arvore_do_busctl() -> None:
    saida = (
        "/org/bluez/hci0\n"
        f"/org/bluez/hci0/dev_{SAO.upper().replace(':', '_')}\n"
        "/org/bluez/hci1\n"
    )
    conhecidos = enderecos_que_o_bluez_conhece(
        executor=_executor({("busctl", "tree", "org.bluez", "--list"): saida})
    )
    assert conhecidos == {("hci0", SAO)}


def test_o_leitor_de_adaptadores_desce_para_o_hcitool_quando_o_sysfs_cala(
    tmp_path: Path,
) -> None:
    """O degrau de cima NÃO EXISTE nesta máquina — medido, kernel 7.1.5."""
    mudo = tmp_path / "bluetooth"
    (mudo / "hci0").mkdir(parents=True)
    (mudo / "hci0:5").mkdir()
    saida = f"Devices:\n\thci0\t{DONGLE_A.upper()}\n\thci1\t{DONGLE_B.upper()}\n"
    achados = adaptadores_na_mesa(mudo, executor=_executor({("hcitool", "dev"): saida}))
    assert achados == {"hci0": DONGLE_A, "hci1": DONGLE_B}

    falante = tmp_path / "bluetooth-falante"
    (falante / "hci0").mkdir(parents=True)
    (falante / "hci0" / "address").write_text(DONGLE_A.upper() + "\n", encoding="utf-8")
    (falante / "hci0:5").mkdir()

    def explode(*_args: Any, **_kwargs: Any) -> str:
        msg = "o sysfs respondeu e ainda assim chamou processo"
        raise AssertionError(msg)

    assert adaptadores_na_mesa(falante, executor=explode) == {"hci0": DONGLE_A}


def test_o_no_de_link_nao_e_confundido_com_adaptador(tmp_path: Path) -> None:
    """`hci0:5` é uma CONEXÃO, não um dongle — e o `uevent` dele não tem"""
    raiz = tmp_path / "bluetooth"
    (raiz / "hci0:5").mkdir(parents=True)
    (raiz / "hci0:5" / "address").write_text(SAO.upper(), encoding="utf-8")
    assert adaptadores_na_mesa(raiz, executor=_executor({})) == {}


def test_uniqs_com_hid_le_o_uevent(tmp_path: Path) -> None:
    raiz = tmp_path / "hidraw"
    for nome, uniq in (("hidraw0", SAO.upper()), ("hidraw1", "")):
        (raiz / nome / "device").mkdir(parents=True)
        (raiz / nome / "device" / "uevent").write_text(
            f"DRIVER=playstation\nHID_UNIQ={uniq}\n", encoding="utf-8"
        )
    assert uniqs_com_hid(raiz) == {SAO}


@pytest.mark.parametrize(
    "sujo",
    ["", "path:/dev/input/event9", "/dev/hidraw4", "aa:bb:cc:00:00", "xyz", None],
)
def test_mac_limpo_recusa_o_que_nao_e_endereco(sujo: str | None) -> None:
    """Estrita de propósito: o valor vira argumento de comando privilegiado."""
    assert mac_limpo(sujo) is None


def test_a_ponte_monta_o_comando_com_o_adaptador_e_o_controle() -> None:
    """O que vai ao `sudo` é só o verbo; os dois MACs vão pelo stdin."""
    capturado: list[PedidoAPonte] = []

    def espia(pedido: PedidoAPonte) -> tuple[bool, str]:
        capturado.append(pedido)
        return True, ""

    ponte = PontePrivilegiada(caminho="/caminho/ponte.sh", executor=espia)
    assert ponte.impedimentos() == []
    assert ponte.desconectar(LINK_ZUMBI) == (True, "")
    [pedido] = capturado
    assert pedido.argv == ("sudo", "-n", "--", "/caminho/ponte.sh", "desconectar")
    assert pedido.entrada == f"{DONGLE_B}\n{ZUMBI}\n"
    assert pedido.sonda == ("sudo", "-n", "-l", "--", "/caminho/ponte.sh", "desconectar")


def test_a_ponte_nao_instalada_e_impedimento_declarado() -> None:
    ponte = PontePrivilegiada(caminho="/nao/existe/ponte.sh")
    motivos = ponte.impedimentos()
    assert motivos and any("não está instalada" in m for m in motivos)


def test_o_verbo_desconectar_existe_no_script_e_na_regra_do_sudoers() -> None:
    """A ponte é o único caminho de root desta cura — e ele tem de existir."""
    texto = (RAIZ / "scripts" / "bt_ponte_privilegiada.sh").read_text(encoding="utf-8")
    assert "verbo_desconectar" in texto
    assert "desconectar)" in texto


def test_o_subsystem_esta_nas_tres_pontas() -> None:
    """Lista + `_safe_start` no `run()` + `_stop_*` no `shutdown()`."""
    assert ConexoesSubsystem in SUBSYSTEM_REGISTRY
    ciclo = RAIZ / "src" / "hefesto_dualsense4unix" / "daemon"
    vida = (ciclo / "lifecycle.py").read_text(encoding="utf-8")
    assert '_safe_start("conexoes"' in vida  # (noqa-acento): nome do subsystem
    assert "async def _start_conexoes" in vida
    assert "async def _stop_conexoes" in vida
    queda = (ciclo / "connection.py").read_text(encoding="utf-8")
    assert "_stop_conexoes" in queda


def test_o_vigia_nasce_ligado_e_a_chave_desliga(monkeypatch: Any) -> None:
    """Ligado por default — ordem dela: *"o produto precisa ser inteligente"*."""
    vigia = ConexoesSubsystem()
    monkeypatch.delenv("HEFESTO_DUALSENSE4UNIX_CONEXAO_ZUMBI", raising=False)
    assert vigia.is_enabled(object()) is True  # type: ignore[arg-type]
    monkeypatch.setenv("HEFESTO_DUALSENSE4UNIX_CONEXAO_ZUMBI", "0")
    assert vigia.is_enabled(object()) is False  # type: ignore[arg-type]


def test_o_diario_chega_ao_disco_com_o_recado(tmp_path: Any) -> None:
    """*"A recusa com motivo não é resposta"* — a aba precisa do que aconteceu."""
    ponte = PonteDeMentira()
    subsystem = ConexoesSubsystem(
        vigia=_vigia(ponte, segundos_para_zumbi=0.0),
        olhador=lambda: ([LINK_ZUMBI], {SAO}, CONHECIDOS, []),
    )
    veredito = subsystem.uma_volta(50.0)
    assert veredito.derrubados
    gravado = ler_o_diario()
    assert gravado["agiu"] is True
    assert gravado["derrubados"][0]["controle"] == ZUMBI
    assert gravado["diario"] and ZUMBI in gravado["diario"][0]


@pytest.mark.asyncio
async def test_o_laco_do_subsystem_mede_o_tempo_de_verdade() -> None:
    """O laço REAL, com relógio real e thread real."""
    ponte = PonteDeMentira()
    subsystem = ConexoesSubsystem(
        vigia=_vigia(ponte, segundos_para_zumbi=0.6),
        olhador=lambda: ([LINK_ZUMBI], {SAO}, CONHECIDOS, []),
        intervalo_s=0.05,
    )
    await subsystem.start(object())  # type: ignore[arg-type]
    try:
        time.sleep(0.2)
        assert ponte.pedidos == [], "curou antes de a janela de tempo fechar"
        prazo = time.monotonic() + 5.0
        while not ponte.pedidos and time.monotonic() < prazo:
            time.sleep(0.05)
        assert ponte.pedidos == [("hci1", DONGLE_B, ZUMBI)]
    finally:
        await subsystem.stop()
    quantos = len(ponte.pedidos)
    time.sleep(0.3)
    assert len(ponte.pedidos) == quantos


class _PonteDoServico:
    """A ponte do pedido ao rádio: anota o pedido e a central aceita."""

    def __init__(self) -> None:
        self.pedidos: list[tuple[str, dict[str, Any]]] = []

    def resultado(self, metodo: str, **parametros: Any) -> dict[str, Any]:
        self.pedidos.append((metodo, parametros))
        if metodo == "radio.busca.set":
            busca = ({"adaptador": parametros.get("destino"), "desde": 0.0, "ate": 120.0}
                     if parametros.get("ligada") else None)
            return {"status": "ok", "busca": busca}
        return {"status": "ok"}


@pytest.fixture()
def a08(monkeypatch: pytest.MonkeyPatch) -> Any:
    """A aba 08 com dois adaptadores na tela, lidos na hora, sem BlueZ de verdade."""
    from hefesto_dualsense4unix.integrations.bluez_dbus import AdaptadorDoBluez
    from hefesto_dualsense4unix.integrations.mesa_de_radio import Mesa
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes
    from hefesto_dualsense4unix.utils.maquina import MaquinaConfig

    lidos = (
        AdaptadorDoBluez("/org/bluez/hci0", "hci0", DONGLE_A.upper(), lugar="3-1",
                         varrendo=False),
        AdaptadorDoBluez("/org/bluez/hci1", "hci1", DONGLE_B.upper(), lugar="3-2",
                         varrendo=False),
    )
    monkeypatch.setattr(a08_conexoes, "LER_NA_HORA", True)
    monkeypatch.setattr(a08_conexoes, "_FUNDO", {})
    monkeypatch.setattr(a08_conexoes, "_ABERTO", {})
    monkeypatch.setattr(a08_conexoes, "_CENA_NA_TELA", {})
    monkeypatch.setattr(a08_conexoes, "_DISPENSADOS", set())
    monkeypatch.setattr(a08_conexoes, "_mesa_do_radio", lambda recarregar=False: Mesa())
    monkeypatch.setattr(a08_conexoes, "_ler_o_historico", lambda: {})
    monkeypatch.setattr(a08_conexoes, "_ler_o_bluez", lambda: (lidos, ()))
    monkeypatch.setattr(a08_conexoes, "_ler_a_maquina", lambda: (MaquinaConfig(), {}))
    return a08_conexoes


def _cena_da_aba(a08: Any) -> dict[str, Any]:
    from hefesto_dualsense4unix.interface.pacotes import Contexto

    a08._FUNDO.clear()
    estado = {"controllers": [], "radio_central": {"movimentos": [], "proposta": None}}
    a08.campos_do_radio(Contexto(state=estado, conectados=[], mesa=[]))
    return dict(a08._CENA_NA_TELA)


def _na_tela(endereco: str) -> str:
    """O adaptador como a aba o endereça: os doze dígitos, em maiúscula."""
    return endereco.replace(":", "").upper()


def _presos(cena: dict[str, Any]) -> list[dict[str, Any]]:
    return [a for a in cena["aparelhos"]
            if a.get("nao_conectou") and str(a.get("chave") or "").startswith("zumbi|")]


def _volta(ponte: Any, links: list[LinkDeRadio], *, quando: float | None = None,
           vigia: VigiaDeZumbis | None = None) -> ConexoesSubsystem:
    subsystem = ConexoesSubsystem(
        vigia=vigia or _vigia(ponte, segundos_para_zumbi=0.0),
        olhador=lambda: (links, {SAO}, CONHECIDOS, []),
    )
    subsystem.uma_volta(time.monotonic() if quando is None else quando)
    return subsystem


def test_o_zumbi_que_o_vigia_nao_cura_vira_nao_conectou_na_caixa_dele(a08: Any) -> None:
    """Sem a ponte que corta o link, a linha «Não Conectou» nasce na caixa do"""
    _volta(PonteDeMentira(impede=["a ponte privilegiada não está instalada"]), [LINK_ZUMBI])
    cena = _cena_da_aba(a08)
    presos = _presos(cena)
    assert len(presos) == 1, cena["aparelhos"]
    linha = presos[0]
    assert linha["lugar"] == _na_tela(DONGLE_B)
    assert linha["tipo"] == "controle" and linha["aparelho"] == ""
    caixas = {lug["id"]: lug.get("nao_conectou") for lug in cena["lugares"]}
    assert caixas == {_na_tela(DONGLE_A): False, _na_tela(DONGLE_B): True}
    assert cena["aberto"] == _na_tela(DONGLE_B), "a caixa de quem não chegou abre"
    html = a08.html_da_linha(linha, cena)
    assert a08.NAO_CONECTOU in html and 'data-gesto="tentar-de-novo"' in html
    assert 'data-abre="conectar"' in html and "Tirar esta linha" in html
    texto = re.sub(r"<[^>]+>", " ", html)
    assert ZUMBI.upper() not in texto.upper() and ZUMBI.replace(":", "") not in texto


def test_o_teto_e_a_derrubada_que_falha_tambem_deixam_a_linha(a08: Any) -> None:
    """Os três jeitos de a cura não bastar dão a mesma linha: o impedimento"""
    _volta(PonteDeMentira(funciona=False), [LINK_ZUMBI])
    assert len(_presos(_cena_da_aba(a08))) == 1, "a derrubada falhou e a tela calou"

    ponte = PonteDeMentira()
    vigia = _vigia(ponte, segundos_para_zumbi=0.0)
    agora = time.monotonic()
    _volta(ponte, [LINK_ZUMBI], vigia=vigia, quando=agora - 1.0)
    assert ponte.pedidos, "a primeira volta tinha de derrubar"
    _volta(ponte, [LINK_ZUMBI], vigia=vigia, quando=agora)
    assert len(ponte.pedidos) == 1, "o teto não segurou a segunda derrubada"
    assert len(_presos(_cena_da_aba(a08))) == 1, "o teto segurou e a tela calou"


def test_o_zumbi_derrubado_nao_ganha_linha(a08: Any) -> None:
    """A cura andou: o controle volta a procurar o adaptador dele sozinho."""
    _volta(PonteDeMentira(), [LINK_ZUMBI])
    assert _presos(_cena_da_aba(a08)) == []


def test_a_volta_velha_do_vigia_nao_vale(a08: Any) -> None:
    """Um minuto sem volta nova é o daemon parado: o arquivo é passado. E um"""
    ponte = PonteDeMentira(impede=["a ponte privilegiada não está instalada"])
    _volta(ponte, [LINK_ZUMBI], quando=time.monotonic() - 60.0)
    assert _presos(_cena_da_aba(a08)) == []
    _volta(ponte, [LINK_ZUMBI], quando=time.monotonic() + 3600.0)
    assert _presos(_cena_da_aba(a08)) == []


def test_o_zumbi_de_adaptador_fora_da_tela_nao_aparece(a08: Any) -> None:
    fora = LinkDeRadio(hci="hci7", adaptador="aa:bb:cc:00:00:77", controle=ZUMBI)
    _volta(PonteDeMentira(impede=["a ponte privilegiada não está instalada"]), [fora])
    assert _presos(_cena_da_aba(a08)) == []


def test_o_x_tira_a_linha_ate_o_episodio_acabar(a08: Any) -> None:
    """O X (`dispensar-linha`) tira a linha sem esquecer nada, e ela não volta"""
    from hefesto_dualsense4unix.interface.pacotes import Contexto

    ponte = PonteDeMentira(impede=["a ponte privilegiada não está instalada"])
    _volta(ponte, [LINK_ZUMBI])
    linha = _presos(_cena_da_aba(a08))[0]
    ctx = Contexto(state={}, conectados=[], mesa=[])
    assert a08.dispensar_linha(ctx, {"alvo": linha["id"], "lugar": linha["lugar"]},
                               None) == {"armou": True}
    assert _presos(_cena_da_aba(a08)) == [], "o X não tirou a linha"
    _volta(ponte, [])
    assert _presos(_cena_da_aba(a08)) == []
    _volta(ponte, [LINK_ZUMBI])
    assert len(_presos(_cena_da_aba(a08))) == 1, "o episódio novo ficou dispensado"


def test_tentar_de_novo_abre_o_conectar_no_adaptador_do_preso(a08: Any) -> None:
    """«Tentar de Novo» é o «Conectar» naquele adaptador: a busca ligada com o"""
    from hefesto_dualsense4unix.interface.pacotes import Contexto

    _volta(PonteDeMentira(impede=["a ponte privilegiada não está instalada"]), [LINK_ZUMBI])
    _cena_da_aba(a08)
    servico = _PonteDoServico()
    ctx = Contexto(state={}, conectados=[], mesa=[])
    a08.tentar_de_novo(ctx, {"alvo": _na_tela(DONGLE_B)}, servico)
    assert servico.pedidos == [
        ("radio.busca.set", {"ligada": True, "destino": _na_tela(DONGLE_B)})]
    assert _presos(_cena_da_aba(a08)) == [], "a linha refeita continuou na tela"

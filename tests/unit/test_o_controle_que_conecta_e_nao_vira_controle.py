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

#: Faixa sintética da casa. NUNCA a máscara de um endereço real — a máscara
#: preserva o OUI, e `tests/unit/test_anonimato_de_fixtures.py` reprova.
DONGLE_A = "aa:bb:cc:00:00:11"
DONGLE_B = "aa:bb:cc:00:00:33"
SAO = "aa:bb:cc:00:00:22"
ZUMBI = "aa:bb:cc:00:00:44"

LINK_SAO = LinkDeRadio(hci="hci0", adaptador=DONGLE_A, controle=SAO)
LINK_ZUMBI = LinkDeRadio(hci="hci1", adaptador=DONGLE_B, controle=ZUMBI)

#: O BlueZ conhece o são naquele adaptador, e ninguém mais.
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


# --- a regra pura: as três condições -----------------------------------------


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
    #: E o zumbi ganhando um `hidraw` deixa de ser zumbi na mesma volta.
    assert zumbis([LINK_ZUMBI], {SAO, ZUMBI}, CONHECIDOS | {("hci1", ZUMBI)}) == []


def test_o_conectado_que_o_bluez_conhece_e_outro_defeito() -> None:
    """Sem `hidraw` mas COM objeto no BlueZ não é este defeito — é o cache SDP.

    O `doctor.sh:check_bt_connected_sem_hidraw` já pega esse, e a cura dele não
    é derrubar link nenhum (SDP-CACHE-01). Confundir os dois faria o produto
    derrubar um controle cuja causa a derrubada não resolve, em laço.
    """
    conhecidos = CONHECIDOS | {("hci1", ZUMBI)}
    assert zumbis([LINK_ZUMBI], {SAO}, conhecidos) == []


def test_sem_a_leitura_do_bluez_ninguem_e_acusado() -> None:
    """Ausência de leitura é *"não sei"*, e "não sei" nunca autoriza agir.

    É a trava que impede o produto de derrubar o fone, o mouse e o teclado dela
    no dia em que o `busctl` não responder.
    """
    assert zumbis([LINK_SAO, LINK_ZUMBI], set(), set()) == []


def test_o_adaptador_viaja_junto_com_o_endereco() -> None:
    """O rádio é POR ADAPTADOR, e a cura precisa saber em qual dongle agir.

    `hcitool dc` sem `-i` cai no primeiro adaptador que o kernel rotear — numa
    malha de três dongles isso derruba o link de OUTRO adaptador, de quem
    estava jogando.
    """
    ponte = PonteDeMentira()
    vigia = _vigia(ponte, segundos_para_zumbi=0.0)
    vigia.observar(100.0, [LINK_ZUMBI], {SAO}, CONHECIDOS)
    assert ponte.pedidos == [("hci1", DONGLE_B, ZUMBI)]


# --- o tempo -----------------------------------------------------------------


def test_o_suspeito_novo_ainda_nao_e_zumbi() -> None:
    """Todo controle passa instantes com link de pé e sem HID enquanto sobe."""
    ponte = PonteDeMentira()
    vigia = _vigia(ponte, segundos_para_zumbi=20.0)
    veredito = vigia.observar(0.0, [LINK_ZUMBI], {SAO}, CONHECIDOS)
    assert veredito.suspeitos and not veredito.zumbis
    assert ponte.pedidos == []


def test_o_relogio_do_vigia_atravessa_minutos() -> None:
    """Quatro minutos de relógio, sem dormir — e o que oscila NÃO soma.

    Um link que entra e sai da suspeita tem o relógio ZERADO a cada saída. Sem
    isso, um controle que pisca durante a tarde viraria zumbi por acumulação, e
    a cura cairia em cima de quem está só com o rádio ruim.
    """
    ponte = PonteDeMentira()
    vigia = _vigia(ponte, segundos_para_zumbi=20.0)
    momento = 0.0
    for _ in range(12):
        # 10 s suspeito, 10 s de volta à mesa — 20 s de ciclo, 12 ciclos = 4 min.
        vigia.observar(momento, [LINK_ZUMBI], {SAO}, CONHECIDOS)
        momento += 10.0
        vigia.observar(momento, [], {SAO, ZUMBI}, CONHECIDOS)
        momento += 10.0
    assert ponte.pedidos == [], "oscilar por quatro minutos virou zumbi por acumulação"

    #: E agora, PARADO no defeito, ele vira zumbi — senão o teste acima passaria
    #: com o vigia trocado por "nunca cura".
    vigia.observar(momento, [LINK_ZUMBI], {SAO}, CONHECIDOS)
    veredito = vigia.observar(momento + 21.0, [LINK_ZUMBI], {SAO}, CONHECIDOS)
    assert veredito.derrubados and ponte.pedidos


# --- o teto ------------------------------------------------------------------


def test_a_cura_tem_teto_por_controle() -> None:
    """Uma derrubada por controle por janela — e o que sobra é um GESTO.

    Sem teto, um controle que não consegue parear em adaptador nenhum entra em
    laço de reconexão com o produto empurrando. Um laço que o produto alimenta
    é pior que o zumbi parado.
    """
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

    #: Passada a janela, ele pode tentar de novo.
    terceiro = vigia.observar(100.0 + 601.0, [LINK_ZUMBI], {SAO}, CONHECIDOS)
    assert terceiro.derrubados
    assert len(ponte.pedidos) == 2


# --- ausência é resposta ------------------------------------------------------


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
    #: E o teto NÃO conta uma tentativa que falhou: senão um erro transitório
    #: da ponte compraria dez minutos de silêncio.
    outro = vigia.observar(11.0, [LINK_ZUMBI], {SAO}, CONHECIDOS)
    assert len(ponte.pedidos) == 2, outro


# --- os leitores: eles LEEM, não digitam --------------------------------------


def _executor(saidas: dict[tuple[str, ...], str]) -> Any:
    def correr(args: Any, *resto: Any) -> Any:
        return saidas.get(tuple(args), "")

    return correr


def test_o_leitor_de_links_le_a_saida_do_hcitool_por_adaptador() -> None:
    """O formato é o REAL, medido em 20/09/2026 (endereços trocados pela faixa
    sintética da casa). Uma régua que digita o que devia ler não mede nada."""
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
    #: E o adaptador de cada link é o do dongle certo, não o primeiro da lista.
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
    """O degrau de cima NÃO EXISTE nesta máquina — medido, kernel 7.1.5.

    `/sys/class/bluetooth/hci0/` não tem `address`. Quem só lê o sysfs devolve
    ZERO adaptadores com três dongles de pé, e "nenhum adaptador" se lê como
    "nenhum zumbi".
    """
    mudo = tmp_path / "bluetooth"
    (mudo / "hci0").mkdir(parents=True)
    (mudo / "hci0:5").mkdir()
    saida = f"Devices:\n\thci0\t{DONGLE_A.upper()}\n\thci1\t{DONGLE_B.upper()}\n"
    achados = adaptadores_na_mesa(mudo, executor=_executor({("hcitool", "dev"): saida}))
    assert achados == {"hci0": DONGLE_A, "hci1": DONGLE_B}

    #: E quando o sysfs RESPONDE, ele ganha — nenhum processo é chamado.
    falante = tmp_path / "bluetooth-falante"
    (falante / "hci0").mkdir(parents=True)
    (falante / "hci0" / "address").write_text(DONGLE_A.upper() + "\n", encoding="utf-8")
    (falante / "hci0:5").mkdir()

    def explode(*_args: Any, **_kwargs: Any) -> str:
        msg = "o sysfs respondeu e ainda assim chamou processo"
        raise AssertionError(msg)

    assert adaptadores_na_mesa(falante, executor=explode) == {"hci0": DONGLE_A}


def test_o_no_de_link_nao_e_confundido_com_adaptador(tmp_path: Path) -> None:
    """`hci0:5` é uma CONEXÃO, não um dongle — e o `uevent` dele não tem
    endereço (medido: só `DEVTYPE=link`)."""
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
    """Estrita de propósito: o valor vira argumento de comando privilegiado.

    `core.sysfs_leds.norm_mac` recolhe dígitos hex de qualquer texto
    (`norm_mac("/dev/hidraw4")` devolve `'deda4'`, medido em 04/09/2026). Aqui
    um endereço aproximado é pior que nenhum.
    """
    assert mac_limpo(sujo) is None


# --- a ponte de verdade, sem tocar no rádio -----------------------------------


def test_a_ponte_monta_o_comando_com_o_adaptador_e_o_controle() -> None:
    """O que vai ao `sudo` é exatamente o verbo novo, com os dois MACs.

    Nada é executado: o executor injetado captura a linha. Um teste que rodasse
    isto de verdade cortaria o rádio dela.
    """
    capturado: list[list[str]] = []

    def espia(args: list[str], link: LinkDeRadio) -> tuple[bool, str]:
        capturado.append(list(args))
        return True, ""

    ponte = PontePrivilegiada(caminho="/caminho/ponte.sh", executor=espia)
    assert ponte.impedimentos() == []
    assert ponte.desconectar(LINK_ZUMBI) == (True, "")
    assert capturado == [
        ["sudo", "-n", "--", "/caminho/ponte.sh", "desconectar", DONGLE_B, ZUMBI]
    ]


def test_a_ponte_nao_instalada_e_impedimento_declarado() -> None:
    ponte = PontePrivilegiada(caminho="/nao/existe/ponte.sh")
    motivos = ponte.impedimentos()
    assert motivos and any("não está instalada" in m for m in motivos)


def test_o_verbo_desconectar_existe_no_script_e_na_regra_do_sudoers() -> None:
    """A ponte é o único caminho de root desta cura — e ele tem de existir.

    O portão de paridade entre o `case` e a regra do sudoers vive em
    `test_a_ponte_privilegiada_entra_e_sai_do_install.py`; aqui só se trava que
    o módulo Python e o script falam do MESMO verbo.
    """
    texto = (RAIZ / "scripts" / "bt_ponte_privilegiada.sh").read_text(encoding="utf-8")
    assert "verbo_desconectar" in texto
    assert "desconectar)" in texto


# --- o subsystem: as três pontas da receita -----------------------------------


def test_o_subsystem_esta_nas_tres_pontas() -> None:
    """Lista + `_safe_start` no `run()` + `_stop_*` no `shutdown()`.

    A receita de DUAS metades sobe o subsystem e nunca o para — e aqui isso
    seria uma thread chamando `sudo` com o daemon já morto.
    """
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
    """*"A recusa com motivo não é resposta"* — a aba precisa do que aconteceu.

    O `conftest` desvia `HOME` e os quatro `XDG_*`, então isto grava num lar de
    mentira, nunca no dela.
    """
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
    """O laço REAL, com relógio real e thread real.

    Uma régua que chama `uma_volta` uma vez mede um INSTANTE. Esta sobe o laço,
    espera a janela passar no relógio de parede e exige que a cura tenha
    acontecido DEPOIS — e não na primeira volta.
    """
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
    #: E o `stop` para DE VERDADE: nenhuma volta nova depois dele.
    quantos = len(ponte.pedidos)
    time.sleep(0.3)
    assert len(ponte.pedidos) == quantos

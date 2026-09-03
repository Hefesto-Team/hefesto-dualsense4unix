"""ONDA-TRANSPORTE-IDENTIDADE — a rede do que 03/09/2026 mediu na identidade.

O QUE ESTA CASA PROCUROU, E COM QUE PERGUNTA
---------------------------------------------

Pedido dela, 03/09/2026: *"a ideia é ver o que no código tá setado pra funcionar
só via cabo e não BT. e verificar no specs o caminho do Bt pra garantir que lá
ele possa funcionar em ambos os modos."*

O molde é o da ``ONDA-CONEXOES-11``, do dia anterior: **o aparelho aceita, e
quem recusa é o filtro nosso**. Este arquivo é a rede dos três achados da área
de IDENTIDADE E COR, e cada classe abaixo morde um deles.

1. A COR NA GTK PERGUNTAVA SÓ NO CABO — e o filtro era nosso
-------------------------------------------------------------

``app/actions/config/secao_controles.py::_perguntar_as_cores`` tinha
``transporte != "usb"``: a aba Configurações não perguntava a cor de fábrica a
nenhum controle de rádio. Era a IRMÃ do filtro que a ``ONDA-CONEXOES-11``
arrancou de ``cor_do_plastico.alvo_do_controle`` em 02/09 — mesma razão herdada
(*"por rádio o SET_FEATURE 0x80 devolve EIO"*), refutada em 27/08 (era a semente
do NOSSO CRC) e medida de novo em 02/09 com o controle dela respondendo pelo
produto. Arrancado o filtro de lá, este ficou de pé sozinho, e a GTK continuava
mostrando "Não sei" no card que a interface nova já sabia nomear.

**A cura não foi apagar o ``if``: foi trocá-lo pelo MAPA.** É o mecanismo que
ela descreveu — *"quando colocarmos o caminho certo no specs o script original
vai fazer uso desse place holder setado e automaticamente parear"*. E é por isso
que :class:`TestACorNaAbaSegueOMapa` não se contenta em ver a pergunta sair no
rádio: ela TROCA a resposta do mapa e exige que o produto mude junto, nos dois
sentidos. Um ``if`` de barramento reescrito à mão passaria no primeiro nó e
reprovaria no segundo.

2. O ENABLE-IMU RECUSA O RÁDIO — e a RAZÃO escrita estava derrubada
--------------------------------------------------------------------

``daemon/subsystems/external_identity.py`` tem
``_IMU_ENABLE_ALLOWED_BUS = "usb"``, e a nota dele dizia que o rádio era
território não medido (*"falta medição de campo com o kernel-watch [JOYCON]
limpo"*). A leitura do fonte derrubou a premissa: o ``ENABLE_IMU`` (subcomando
``0x40``) é disparado pelo PRÓPRIO ``hid-nintendo`` dentro do ``joycon_init``,
**em todo barramento**, sob o único porteiro ``joycon_has_imu()``, que olha o
TIPO do controle e nunca o ``hdev->bus``.

**O gate FICA — o que mudou foi a razão**, e a diferença é operacional: com a
razão velha, quem chegasse ali iria MEDIR O RÁDIO; com a nova, sabe que por
rádio o kernel já mandou o mesmo pacote e que a dívida aberta é outra (ninguém
mediu se algum Pro fica em STANDBY depois do ``joycon_init``).
:class:`TestOEnableImuERecusadoPorNos` morde as duas metades — que o filtro é
NOSSO, e que o fonte do driver continua dizendo o que a razão nova afirma.

3. O CADERNO CULPAVA O TRANSPORTE PELA COR
-------------------------------------------

``scripts/ensaios/README.md`` ainda carregava *"por rádio, medido-negativo (…)
o `SET 0x80` volta `EIO` imediato — e a causa é o TRANSPORTE, não a unidade"*.
Fato derrubado em 27/08 e de novo em 02/09. Sai de TODOS os lugares onde
aparece — é a regra da casa, e o caderno é um deles.

NADA AQUI ENCOSTA EM APARELHO. O ``enable_imu`` entra por espião, o transporte
da cor entra por injeção, e o mapa é lido do disco.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions.config import secao_controles
from hefesto_dualsense4unix.app.fatos_do_mapa import FATOS
from hefesto_dualsense4unix.daemon.subsystems import external_identity

RAIZ = Path(__file__).resolve().parents[2]
MAPA = RAIZ / "docs" / "data" / "mapa-controles.csv"
CADERNO = RAIZ / "scripts" / "ensaios" / "README.md"
DRIVER = RAIZ / "assets" / "dkms" / "hid-nintendo" / "hid-nintendo.c"

#: MAC FORJADO na faixa sintética que os portões de anonimato reconhecem, com a
#: máscara da casa (octetos 4 e 5 zerados). Fora das faixas de clone, logo
#: `e_pro_genuino` diz sim — que é o que põe a entrada no caminho do gate.
_UNIQ_PRO = "aa:bb:cc:00:00:11"
_HIDRAW = "/dev/hidraw9"


def _entrada(bus: str) -> dict[str, Any]:
    """Um Pro genuíno no inventário, com o barramento que se pedir."""
    return {
        "uniq": _UNIQ_PRO,
        "name": "Pro Controller",
        "vid": "057e",
        "pid": "2009",
        "bus": bus,
        "hidraw": _HIDRAW,
    }


@pytest.fixture
def enable_imu_espiao(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Troca o `enable_imu` por um espião. Nenhum byte sai para aparelho."""
    from hefesto_dualsense4unix.core import external_leds

    vistos: list[str] = []

    def _espiao(hidraw: str, **_kw: Any) -> bool:
        vistos.append(hidraw)
        return True

    monkeypatch.setattr(external_leds, "enable_imu", _espiao)
    return vistos


# ---------------------------------------------------------------------------
# 2. O enable-IMU: o porteiro é NOSSO, e a razão nova tem de bater com o fonte
# ---------------------------------------------------------------------------
class TestOEnableImuERecusadoPorNos:
    def test_no_cabo_o_enable_imu_sai(self, enable_imu_espiao: list[str]) -> None:
        """O controle positivo. Sem ele, o nó do rádio abaixo não mede nada:
        um gate que recusasse TUDO daria verde lá e seria régua morta."""
        external_identity.ExternalImuEnabler().tick([_entrada("usb")], now=100.0)
        assert enable_imu_espiao == [_HIDRAW]

    def test_no_radio_quem_recusa_e_o_nosso_if(
        self, enable_imu_espiao: list[str]
    ) -> None:
        """O MESMO controle, o MESMO comando: só o barramento muda, e nada sai.

        Este é o gate. Ele FICA — mas a razão dele passou a ser "o kernel já
        mandou o mesmo pacote lá", e não "o rádio é território desconhecido".
        """
        external_identity.ExternalImuEnabler().tick([_entrada("bt")], now=100.0)
        assert enable_imu_espiao == []

    def test_a_constante_diz_que_o_aparelho_aceita_nos_dois(self) -> None:
        """A razão escrita não pode voltar a chamar o rádio de não medido.

        SUBSTITUÍDO em 03/09/2026. A nota dizia *"falta medição de campo com o
        kernel-watch [JOYCON] limpo antes de liberar por rádio"* — e quem lesse
        aquilo iria medir o rádio, que é trabalho já respondido pelo fonte.
        """
        fonte = Path(external_identity.__file__).read_text(encoding="utf-8")
        cabeca = fonte.split('_IMU_ENABLE_ALLOWED_BUS = "usb"')[0]
        # A frase derrubada PODE aparecer — desde que ENTERRADA, isto é, depois
        # da marca que a enterra. É o contrato de
        # `test_o_mapa_nao_guarda_fato_derrubado`: quem enterra anuncia
        # primeiro e cita depois; quem afirma primeiro está afirmando.
        assert cabeca.index("SUBSTITUÍDO") < cabeca.index("kernel-watch"), (
            "a razão derrubada voltou VIVA: o rádio não é território não medido "
            "— o driver desta árvore manda o ENABLE_IMU nos dois barramentos"
        )
        assert "aceita pelos DOIS transportes" in cabeca, (
            "a razão nova tem de dizer que o APARELHO aceita — sem isso a "
            "próxima pessoa lê o gate como limitação do controle"
        )

    def test_o_driver_desta_arvore_manda_o_enable_imu_sem_olhar_o_bus(self) -> None:
        """A régua da razão nova, lida no C que esta árvore instala.

        Se um dia o driver ganhar um ramo por barramento aqui, a razão do gate
        muda de novo — e é este nó que avisa, em vez de a docstring envelhecer
        calada.
        """
        c = DRIVER.read_text(encoding="utf-8", errors="replace").splitlines()
        # O porteiro da chamada olha o TIPO, nunca o `hdev->bus`.
        porteiro = "\n".join(c[838:844])
        assert "joycon_has_imu" in porteiro
        assert "bus" not in porteiro, (
            "`joycon_has_imu` passou a olhar o barramento: a razão do nosso "
            "gate depende de ele NÃO olhar"
        )
        # E a chamada continua dentro do `joycon_init`, sob aquele porteiro só.
        bloco = "\n".join(c[2923:2937])
        assert "joycon_has_imu(ctlr)" in bloco
        assert "joycon_enable_imu(ctlr)" in bloco


# ---------------------------------------------------------------------------
# 1. A cor na aba Configurações: o mapa decide, e o produto obedece
# ---------------------------------------------------------------------------
ID_DA_COR = secao_controles.ID_DA_COR_NO_MAPA


class _PainelFalso:
    """O mínimo de que `_perguntar_as_cores` precisa. Sem GTK, sem janela."""

    def __init__(self) -> None:
        self._host = object()
        self._cores: dict[str, Any] = {}

    def _chegou_a_cor(self, _resultado: Any) -> bool:
        return False


def _perguntados(
    monkeypatch: pytest.MonkeyPatch, transportes: list[str]
) -> list[str]:
    """Quem o painel chegou a PERGUNTAR, com a mesa que se pedir."""
    saiu: list[str] = []

    def _run_in_thread(trabalho: Any, _quando_voltar: Any) -> None:
        saiu.append(trabalho()[0])

    monkeypatch.setattr(secao_controles, "run_in_thread", _run_in_thread)
    monkeypatch.setattr(secao_controles, "ler_pelo_cabo", lambda uniq: None)
    painel = _PainelFalso()
    mesa = [
        {"uniq": f"aa:bb:cc:00:00:{i:02d}", "transport": t}
        for i, t in enumerate(transportes, start=1)
    ]
    secao_controles._PainelDosControles._perguntar_as_cores(painel, mesa)  # type: ignore[arg-type]
    return saiu


class TestACorNaAbaSegueOMapa:
    def test_o_controle_de_radio_passou_a_ser_perguntado(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O achado do dia, na forma mais curta: antes, esta lista vinha vazia.

        Medido em 02/09/2026 no controle dela (`hidraw5`): eco `[1, 19, 2]`,
        código `04` — Galactic Purple — em 13,6 ms, com o mesmo comando do cabo
        assinado com a semente `0x53`.
        """
        assert _perguntados(monkeypatch, ["bt"]) == ["aa:bb:cc:00:00:01"]

    def test_o_do_cabo_continua_sendo_perguntado(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Nada do que já funcionava mudou — a regra da casa sobre hipóteses."""
        assert _perguntados(monkeypatch, ["usb"]) == ["aa:bb:cc:00:00:01"]

    def test_a_mesa_inteira_e_perguntada_seja_qual_for_o_transporte(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A MORDIDA da forma, e é a razão de esta classe existir.

        Um `if` de barramento reescrito à mão — em qualquer sentido — derruba
        este nó: a mesa mista tem de sair INTEIRA, na ordem em que chegou.
        Quem decide se o nó responde é `cor_do_plastico.alvo_do_controle`, o
        dono único do envelope; um segundo porteiro aqui é o defeito.
        """
        assert _perguntados(monkeypatch, ["usb", "bt", "bt", "usb"]) == [
            "aa:bb:cc:00:00:01",
            "aa:bb:cc:00:00:02",
            "aa:bb:cc:00:00:03",
            "aa:bb:cc:00:00:04",
        ]

    def test_ninguem_e_perguntado_duas_vezes_na_mesma_sessao(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O cache é o que protege os controles dela: o pedido é um
        `SET_FEATURE` da família `0x80`, a mesma em que `[1, 1]` RESETA o
        aparelho. Tirar o filtro de barramento não pode ter tirado o cache."""
        saiu: list[str] = []
        monkeypatch.setattr(
            secao_controles, "run_in_thread", lambda t, _q: saiu.append(t()[0])
        )
        monkeypatch.setattr(secao_controles, "ler_pelo_cabo", lambda uniq: None)
        painel = _PainelFalso()
        mesa = [{"uniq": "aa:bb:cc:00:00:01", "transport": "bt"}]
        for _ in range(3):
            secao_controles._PainelDosControles._perguntar_as_cores(painel, mesa)  # type: ignore[arg-type]
        assert saiu == ["aa:bb:cc:00:00:01"]

    def test_o_mapa_publica_a_cor_pelos_dois_transportes(self) -> None:
        """A metade de DADO do par, e o endereço dela está no produto.

        `secao_controles.ID_DA_COR_NO_MAPA` existe para que quem for mexer no
        comportamento saiba qual célula conferir antes. Se ela voltar para
        `não` no rádio, é aqui que a divergência aparece — e não numa tela
        mostrando "Não sei" sem ninguém saber por quê.
        """
        celula = FATOS[ID_DA_COR]
        assert celula["cabo"]["aciona"] == "sim"  # type: ignore[index]
        assert celula["radio"]["aciona"] == "sim"  # type: ignore[index]

    def test_o_produto_nao_importa_o_dicionario_gerado_do_mapa(self) -> None:
        """O custo medido em 03/09/2026, preso para não ser pago sem querer.

        Ler `app/fatos_do_mapa` de dentro de `src/` põe as CHAVES do dicionário
        gerado (`canal`, `aciona`, `existe`, `cabo`, `radio`…) ao alcance da
        régua PLANA do portão `casa-sabe` — que conta literal de texto de
        módulo alcançado como referência. Medido: com o import em
        `secao_controles`, `interface/pacotes/mapa.py::canal` passou a contar
        como ALCANÇADA sem ter ganhado um chamador, e o portão reprovou pedindo
        para apagar uma lápide verdadeira.

        Não é proibição eterna: é um preço que quem decidir pagar tem de pagar
        de olho aberto, e com o dono do `casa-sabe` na conversa.
        """
        import ast

        for modulo in (secao_controles, external_identity):
            fonte = Path(modulo.__file__ or "").read_text(encoding="utf-8")
            for no in ast.walk(ast.parse(fonte)):
                alvo = getattr(no, "module", None)
                assert alvo != "hefesto_dualsense4unix.app.fatos_do_mapa", (
                    f"{modulo.__name__} importou o dicionário gerado do mapa — "
                    "leia a docstring de `_perguntar_as_cores` antes"
                )


# ---------------------------------------------------------------------------
# 3. O mapa e o caderno: o caminho do rádio escrito, e o fato derrubado fora
# ---------------------------------------------------------------------------
def _linha_do_mapa(ident: str) -> dict[str, str]:
    import csv

    with MAPA.open(newline="", encoding="utf-8") as arquivo:
        for linha in csv.DictReader(arquivo):
            if linha["id"] == ident:
                return linha
    pytest.fail(f"o mapa perdeu a linha {ident}")


@pytest.mark.parametrize(
    ("ident", "canal", "pedaco"),
    [
        ("identidade.req_dev_info@sn30", "hidraw", "0x02"),
        ("identidade.req_dev_info.fallback@sn30", "outro", "bt_probe_retries"),
        ("identidade.req_dev_info.fallback@pro", "outro", "bt_probe_retries"),
    ],
)
def test_o_mapa_guarda_o_caminho_do_radio(
    ident: str, canal: str, pedaco: str
) -> None:
    """As linhas que estavam MUDAS por rádio passaram a ter caminho e dono.

    Muda lê-se como "ninguém olhou". Estas foram olhadas: duas têm o caminho
    (é o mesmo do cabo, porque o `hid-nintendo` não ramifica por barramento) e
    uma tem a razão de NÃO ter caminho — a síntese de identidade é do cabo por
    decisão escrita no patch desta casa, e a cura do rádio é `bt_probe_retries`.
    """
    linha = _linha_do_mapa(ident)
    assert linha["radio_canal"] == canal
    assert pedaco in linha["radio_comando"]
    assert linha["radio_de_onde_sei"] == "inferido-do-codigo", (
        "quem escreve um lado declara de onde sabe — é a regra 19 do portão de "
        "paridade, e é ela que separa 'medi' de 'li no fonte'"
    )
    assert linha["radio_codigo_ref"].strip(), "caminho sem endereço não é caminho"


def test_o_mapa_nao_chama_mais_o_radio_do_imu_de_nao_medido() -> None:
    """A célula que carregava a razão derrubada do gate do enable-IMU."""
    linha = _linha_do_mapa("plataforma.escrita_crua@pro")
    assimetria = linha["assimetria_declarada"]
    assert "SUBSTITU" in assimetria, (
        "a frase antiga só pode aparecer DEPOIS da marca que a enterra — sem a "
        "marca ela está viva, que é o defeito que o mapa existe para pegar"
    )
    assert assimetria.index("SUBSTITU") < assimetria.index("kernel-watch"), (
        "quem enterra anuncia primeiro e cita depois; quem afirma primeiro "
        "está afirmando"
    )
    assert linha["radio_por_que_nao_aciona"] == "decisao-tomada", (
        "a causa é NOSSA — culpar o aparelho aqui seria a mentira que a "
        "correção do lado da cor desfez em 29/08/2026"
    )


def test_o_caderno_nao_culpa_mais_o_transporte_pela_cor() -> None:
    """A frase que caiu em 27/08/2026 e sobreviveu no caderno até 03/09.

    Ela dizia que o ``SET 0x80`` por rádio devolvia ``EIO`` *"e a causa é o
    TRANSPORTE, não a unidade"*. A causa era a semente do nosso CRC — ``0xA3``
    onde sai ``0x53``. Se alguém reescrever a linha para a versão antiga, esta
    régua reprova.
    """
    linhas = [
        linha
        for linha in CADERNO.read_text(encoding="utf-8").splitlines()
        if "a cor de fábrica está nos caracteres" in linha
    ]
    assert len(linhas) == 1, "a linha da cor no caderno tem de ter UM dono"
    linha = linhas[0]
    assert "0x53" in linha, "a semente que faz o rádio responder tem de estar lá"
    assert "medido POR RÁDIO" in linha, (
        "o grau do rádio virou POSITIVO: `hidraw8` em 27/08 e `hidraw5` em "
        "02/09, duas unidades"
    )
    # O fato derrubado sai, mas a lápide fica — e ela vem ANTES da citação.
    # Uma frase que some sem rastro volta pela mão de quem não sabe que caiu.
    marca = linha.find("SUBSTITUÍDO")
    assert marca >= 0, "a lápide sumiu: sem ela, a frase citada está VIVA"
    for morta in ("medido-negativo", "é o TRANSPORTE"):
        onde = linha.find(morta)
        assert onde < 0 or marca < onde, (
            f"{morta!r} só pode aparecer DEPOIS da marca que o enterra; na "
            "frente dela, ele é uma afirmação viva"
        )

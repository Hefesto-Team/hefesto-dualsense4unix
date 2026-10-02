"""ONDA-TRANSPORTE-IDENTIDADE — a rede do que 03/09/2026 mediu na identidade."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `app.actions.config`, que carrega o GTK")

from hefesto_dualsense4unix.app.actions.config import secao_controles
from hefesto_dualsense4unix.daemon.subsystems import external_identity

RAIZ = Path(__file__).resolve().parents[2]
MAPA = RAIZ / "docs" / "data" / "mapa-controles.csv"
CADERNO = RAIZ / "scripts" / "ensaios" / "README.md"
DRIVER = RAIZ / "assets" / "dkms" / "hid-nintendo" / "hid-nintendo.c"

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


class TestOEnableImuERecusadoPorNos:
    def test_no_cabo_o_enable_imu_sai(self, enable_imu_espiao: list[str]) -> None:
        """O controle positivo. Sem ele, o nó do rádio abaixo não mede nada:"""
        external_identity.ExternalImuEnabler().tick([_entrada("usb")], now=100.0)
        assert enable_imu_espiao == [_HIDRAW]

    def test_no_radio_quem_recusa_e_o_nosso_if(
        self, enable_imu_espiao: list[str]
    ) -> None:
        """O MESMO controle, o MESMO comando: só o barramento muda, e nada sai."""
        external_identity.ExternalImuEnabler().tick([_entrada("bt")], now=100.0)
        assert enable_imu_espiao == []

    def test_a_constante_diz_que_o_aparelho_aceita_nos_dois(self) -> None:
        """A razão escrita não pode voltar a chamar o rádio de não medido."""
        fonte = Path(external_identity.__file__).read_text(encoding="utf-8")
        cabeca = fonte.split('_IMU_ENABLE_ALLOWED_BUS = "usb"')[0]
        assert cabeca.index("SUBSTITUÍDO") < cabeca.index("kernel-watch"), (
            "a razão derrubada voltou VIVA: o rádio não é território não medido "
            "— o driver desta árvore manda o ENABLE_IMU nos dois barramentos"
        )
        assert "aceita pelos DOIS transportes" in cabeca, (
            "a razão nova tem de dizer que o APARELHO aceita — sem isso a "
            "próxima pessoa lê o gate como limitação do controle"
        )

    def test_o_driver_desta_arvore_manda_o_enable_imu_sem_olhar_o_bus(self) -> None:
        """A régua da razão nova, lida no C que esta árvore instala."""
        c = DRIVER.read_text(encoding="utf-8", errors="replace").splitlines()
        porteiro = "\n".join(c[838:844])
        assert "joycon_has_imu" in porteiro
        assert "bus" not in porteiro, (
            "`joycon_has_imu` passou a olhar o barramento: a razão do nosso "
            "gate depende de ele NÃO olhar"
        )
        bloco = "\n".join(c[2923:2937])
        assert "joycon_has_imu(ctlr)" in bloco
        assert "joycon_enable_imu(ctlr)" in bloco


class _PainelFalso:
    """O mínimo de que `_perguntar_as_cores` precisa. Sem GTK, sem janela."""

    def __init__(self) -> None:
        self._host = object()
        self._cores: dict[str, Any] = {}

    def _chegou_a_cor(self, _resultado: Any) -> bool:
        return False


class TestACorNaAbaSegueOMapa:


    def test_o_produto_nao_importa_o_dicionario_gerado_do_mapa(self) -> None:
        """O custo medido em 03/09/2026, preso para não ser pago sem querer."""
        import ast

        for modulo in (secao_controles, external_identity):
            fonte = Path(modulo.__file__ or "").read_text(encoding="utf-8")
            for no in ast.walk(ast.parse(fonte)):
                alvo = getattr(no, "module", None)
                assert alvo != "hefesto_dualsense4unix.app.fatos_do_mapa", (
                    f"{modulo.__name__} importou o dicionário gerado do mapa — "
                    "leia a docstring de `_perguntar_as_cores` antes"
                )


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
    """As linhas que estavam MUDAS por rádio passaram a ter caminho e dono."""
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
    """A frase que caiu em 27/08/2026 e sobreviveu no caderno até 03/09."""
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
    marca = linha.find("SUBSTITUÍDO")
    assert marca >= 0, "a lápide sumiu: sem ela, a frase citada está VIVA"
    for morta in ("medido-negativo", "é o TRANSPORTE"):
        onde = linha.find(morta)
        assert onde < 0 or marca < onde, (
            f"{morta!r} só pode aparecer DEPOIS da marca que o enterra; na "
            "frente dela, ele é uma afirmação viva"
        )

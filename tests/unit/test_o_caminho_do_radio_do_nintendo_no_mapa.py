"""O caminho do RÁDIO das famílias Nintendo Pro e 8BitDo, no mapa de canais."""

from __future__ import annotations

import csv
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MAPA = REPO_ROOT / "docs" / "data" / "mapa-controles.csv"
DRIVER = REPO_ROOT / "assets" / "dkms" / "hid-nintendo" / "hid-nintendo.c"
LEDS = REPO_ROOT / "src" / "hefesto_dualsense4unix" / "core" / "external_leds.py"

COLUNAS_DO_CAMINHO = (
    "radio_canal",
    "radio_comando",
    "radio_de_onde_sei",
    "radio_codigo_ref",
)

LINHAS_E_SEUS_GATES = {
    "plataforma.udev_autosuspend@pro": None,
    "identidade.req_dev_info.fallback@sn30": "usb_probe_degrade && joycon_using_usb(ctlr)",
    "plataforma.handshake_usb@sn30": "return ctlr->hdev->bus == BUS_USB;",
    "plataforma.probe@sn30": "if (ret && !joycon_using_usb(ctlr))",
    "plataforma.taxa_relatorios@sn30": "JC_SUBCMD_RATE_LIMITER_BT_MS",
}


@pytest.fixture(scope="module")
def mapa() -> dict[str, dict[str, str]]:
    with MAPA.open(newline="", encoding="utf-8") as fh:
        return {linha["id"]: linha for linha in csv.DictReader(fh)}


@pytest.fixture(scope="module")
def fonte_do_driver() -> str:
    return DRIVER.read_text(encoding="utf-8", errors="replace")


class TestOCaminhoEstaEscrito:
    """Metade 1 da mordida: apagar a célula reprova."""

    @pytest.mark.parametrize("identificador", sorted(LINHAS_E_SEUS_GATES))
    def test_as_quatro_colunas_do_caminho_estao_preenchidas(
        self, mapa: dict[str, dict[str, str]], identificador: str
    ) -> None:
        linha = mapa.get(identificador)
        assert linha is not None, f"linha sumiu do mapa: {identificador}"
        vazias = [c for c in COLUNAS_DO_CAMINHO if not linha[c].strip()]
        assert not vazias, (
            f"{identificador}: o caminho do rádio voltou a ser mudo em {vazias}. "
            "Estas células foram escritas em 03/09/2026 lendo o fonte do "
            "hid-nintendo; esvaziá-las devolve a linha ao estado 'ninguém "
            "respondeu', que é o que a leva daquele dia existia para fechar."
        )

    @pytest.mark.parametrize("identificador", sorted(LINHAS_E_SEUS_GATES))
    def test_a_proveniencia_e_leitura_de_fonte_e_nao_medicao(
        self, mapa: dict[str, dict[str, str]], identificador: str
    ) -> None:
        assert mapa[identificador]["radio_de_onde_sei"].strip() == "inferido-do-codigo"

    def test_o_veredito_do_clone_por_radio_continua_mudo(
        self, mapa: dict[str, dict[str, str]]
    ) -> None:
        linha = mapa["plataforma.probe@sn30"]
        assert linha["radio_aciona"].strip() == ""
        assert linha["radio_aceita"].strip() == ""
        assert "8BITDO-NO-RÁDIO-01" in linha["radio_ressalva"]


class TestOFonteAindaSustentaOQueOMapaAfirma:
    """Metade 2 da mordida: tirar o gate do driver reprova."""

    @pytest.mark.parametrize(
        "identificador,gate",
        sorted((k, v) for k, v in LINHAS_E_SEUS_GATES.items() if v),
    )
    def test_o_gate_de_barramento_continua_no_driver(
        self, fonte_do_driver: str, identificador: str, gate: str
    ) -> None:
        assert gate in fonte_do_driver, (
            f"o gate `{gate}` sumiu de {DRIVER.name}, e a linha "
            f"`{identificador}` do mapa ainda o descreve. Se o gate caiu de "
            "propósito, ATUALIZE a célula de rádio no mesmo gesto — senão o "
            "docs/specs.html publica como fato um caminho que o fonte não tem "
            "mais."
        )

    def test_joycon_may_degrade_recusa_o_radio_pelo_e_logico(
        self, fonte_do_driver: str
    ) -> None:
        corpo = _corpo_da_funcao(fonte_do_driver, "joycon_may_degrade")
        assert "usb_probe_degrade" in corpo and "joycon_using_usb" in corpo

    def test_o_driver_nunca_le_o_endereco_que_o_radio_ja_lhe_deu(
        self, fonte_do_driver: str
    ) -> None:
        leituras = [
            linha
            for linha in fonte_do_driver.splitlines()
            if "uniq" in linha and "->uniq" in linha and "=" in linha.split("uniq")[1]
        ]
        escritas = [linha for linha in leituras if re.search(r"->uniq\s*=", linha)]
        assert len(leituras) == len(escritas), (
            "apareceu uma LEITURA de `uniq` no hid-nintendo. Se ela é a cura da "
            "identidade por rádio, atualize a `radio_ressalva` de "
            "`identidade.req_dev_info.fallback@sn30`: a dívida deixou de existir."
        )

    def test_o_enable_imu_sai_da_probe_em_todo_barramento(
        self, fonte_do_driver: str
    ) -> None:
        corpo_has_imu = _corpo_da_funcao(fonte_do_driver, "joycon_has_imu")
        assert "bus" not in corpo_has_imu, (
            "`joycon_has_imu` passou a olhar o barramento — a afirmação do mapa "
            "de que o Enable-IMU sai em todo fio precisa ser remedida."
        )
        corpo_init = _corpo_da_funcao(fonte_do_driver, "joycon_init")
        assert "joycon_enable_imu(ctlr)" in corpo_init


class TestAArmadilhaDosOitoMilissegundos:
    """O fato que a leitura apressada derruba, e por isso ficou escrito."""

    def test_o_comentario_do_driver_se_contradiz_e_o_mapa_diz_isso(
        self, fonte_do_driver: str, mapa: dict[str, dict[str, str]]
    ) -> None:
        assert "pro controller (bluetooth): every 8 ms" in fonte_do_driver
        assert "every 11ms or every 15ms" in fonte_do_driver
        ressalva = mapa["plataforma.taxa_relatorios@sn30"]["radio_ressalva"]
        assert "8 ms" in ressalva and "11ms" in ressalva, (
            "a armadilha dos 8 ms saiu da `radio_ressalva`. Ela está lá porque "
            "o comentário do driver se contradiz onze linhas depois de si mesmo."
        )


class TestOFatoSubstituidoNaoVolta:
    """`declara mas não ativa` era falso, e a regra da casa manda substituir."""

    def test_a_docstring_nao_atribui_mais_o_standby_ao_driver(self) -> None:
        texto = LEDS.read_text(encoding="utf-8")
        assert "FATO SUBSTITUÍDO em 03/09/2026" in texto
        for achado in re.finditer("declara mas não ativa", texto):
            vizinhanca = texto[achado.start() : achado.end() + 200]
            assert "É FALSO" in vizinhanca, (
                "voltou AFIRMANDO a frase que 03/09/2026 substituiu: o "
                "`hid-nintendo` desta árvore ATIVA a IMU na probe, em todo "
                "barramento (`joycon_enable_imu` chamado de `joycon_init`, sob "
                "um `if` de TIPO). O standby medido continua de pé; a causa "
                "atribuída ao driver é que caiu."
            )


def _corpo_da_funcao(fonte: str, nome: str) -> str:
    """O corpo da função C ``nome``, do ``{`` de abertura ao ``}`` da coluna 0."""
    padrao = re.compile(rf"^[\w \t*]*\b{re.escape(nome)}\s*\(", re.MULTILINE)
    achado = padrao.search(fonte)
    assert achado is not None, f"função não encontrada no fonte: {nome}"
    abre = fonte.index("{", achado.end())
    fecha = fonte.index("\n}", abre)
    return fonte[abre:fecha]

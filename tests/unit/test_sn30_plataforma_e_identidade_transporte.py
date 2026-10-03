"""A fatia SN30 (plataforma/combinação/identidade) das células mudas, 03/09/2026."""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(REPO_ROOT / "scripts"))
from check_paridade_transporte import DE_ONDE_SEI_FORTE
MAPA = REPO_ROOT / "docs" / "data" / "mapa-controles.csv"
DRIVER = REPO_ROOT / "assets" / "dkms" / "hid-nintendo" / "hid-nintendo.c"
COOP = REPO_ROOT / "src" / "hefesto_dualsense4unix" / "daemon" / "subsystems" / "coop.py"
EXTERNAL_IDENTITY = (
    REPO_ROOT / "src" / "hefesto_dualsense4unix" / "daemon" / "subsystems" / "external_identity.py"
)
TROUBLESHOOTING_8BITDO = REPO_ROOT / "docs" / "usage" / "troubleshooting-8bitdo.md"

LINHAS_RESPONDIDAS: dict[str, dict[str, str | None]] = {
    "identidade.pareamento@sn30": {"cabo_aciona": "não", "radio_aciona": "sim"},
    "plataforma.camera_ir@sn30": {"cabo_aciona": "não", "radio_aciona": "não"},
    "plataforma.referencias_nintendo@sn30": {"cabo_aciona": "não", "radio_aciona": "não"},
    "plataforma.diagnostico_morte_radio@sn30": {"cabo_aciona": "não", "radio_aciona": "sim"},
    "plataforma.link_parametros@sn30": {"cabo_aciona": "não", "radio_aciona": "não"},
    "plataforma.sniff@sn30": {"cabo_aciona": "não", "radio_aciona": "sim"},
    "plataforma.taxa_relatorios.botao@sn30": {"cabo_aciona": "não", "radio_aciona": "não"},
    "plataforma.transporte_radio@sn30": {"cabo_aciona": "não", "radio_aciona": "não"},
    "plataforma.vigia_zumbi@sn30": {"cabo_aciona": "não", "radio_aciona": "parcial"},
    "plataforma.vpad@sn30": {"cabo_aciona": "sim", "radio_aciona": "sim"},
}

LINHAS_COM_ASSIMETRIA_DECLARADA = (
    "identidade.pareamento@sn30",
    "plataforma.diagnostico_morte_radio@sn30",
    "plataforma.sniff@sn30",
    "plataforma.vigia_zumbi@sn30",
)


@pytest.fixture(scope="module")
def mapa() -> dict[str, dict[str, str]]:
    with MAPA.open(newline="", encoding="utf-8") as fh:
        return {linha["id"]: linha for linha in csv.DictReader(fh)}


@pytest.fixture(scope="module")
def fonte_do_driver() -> str:
    return DRIVER.read_text(encoding="utf-8", errors="replace")


def _a_prosa_numa_linha(fonte: str) -> str:
    """O comentário de várias linhas vira uma linha só."""
    return re.sub(r"\s*\n\s*#\s*", " ", fonte)


@pytest.fixture(scope="module")
def fonte_do_external_identity() -> str:
    return _a_prosa_numa_linha(EXTERNAL_IDENTITY.read_text(encoding="utf-8"))


class TestAsDezCelulasContinuamEscritas:
    """Metade 1 da mordida: apagar qualquer uma das dez reprova."""

    @pytest.mark.parametrize("identificador", sorted(LINHAS_RESPONDIDAS))
    def test_cabo_aciona_e_radio_aciona_batem_com_o_que_esta_leva_escreveu(
        self, mapa: dict[str, dict[str, str]], identificador: str
    ) -> None:
        linha = mapa.get(identificador)
        assert linha is not None, f"linha sumiu do mapa: {identificador}"
        esperado = LINHAS_RESPONDIDAS[identificador]
        for lado, valor in esperado.items():
            assert linha[lado].strip() == valor, (
                f"{identificador}: `{lado}` era {valor!r} e virou "
                f"{linha[lado]!r}. Se a mudança é uma medição nova (bancada "
                "dela), ótimo — mas então ela merece `de_onde_sei = medido` "
                "e um `teste_que_morde` seu, não a queda silenciosa desta "
                "célula."
            )

    @pytest.mark.parametrize("identificador", sorted(LINHAS_RESPONDIDAS))
    def test_o_lado_respondido_tem_de_onde_sei_preenchido(
        self, mapa: dict[str, dict[str, str]], identificador: str
    ) -> None:
        linha = mapa[identificador]
        for lado in ("cabo", "radio"):
            if linha[f"{lado}_aciona"].strip():
                assert linha[f"{lado}_de_onde_sei"].strip(), (
                    f"{identificador}: `{lado}_aciona` respondido "
                    f"({linha[f'{lado}_aciona']!r}) com `{lado}_de_onde_sei` "
                    "vazio — a regra 19 do portão (`lado-sem-regua`) existe "
                    "exatamente para isto."
                )

    @pytest.mark.parametrize("identificador", sorted(LINHAS_RESPONDIDAS))
    def test_o_lado_que_esta_leva_escreveu_nao_afirma_medido_sem_bancada(
        self, mapa: dict[str, dict[str, str]], identificador: str
    ) -> None:
        linha = mapa[identificador]
        lados_desta_leva = (
            ("cabo", "radio") if identificador == "plataforma.vpad@sn30" else ("cabo",)
        )
        for lado in lados_desta_leva:
            assert linha[f"{lado}_de_onde_sei"].strip() != "medido", (
                f"{identificador}: {lado}_de_onde_sei virou `medido` sem "
                "bancada — esta leva só leu fonte."
            )

    def test_as_quatro_assimetrias_continuam_declaradas(
        self, mapa: dict[str, dict[str, str]]
    ) -> None:
        for identificador in LINHAS_COM_ASSIMETRIA_DECLARADA:
            assert mapa[identificador]["assimetria_declarada"].strip(), (
                f"{identificador}: `assimetria_declarada` voltou a ficar "
                "vazia — cabo e rádio divergem aqui, e calar sobre a "
                "divergência é o defeito que esta coluna existe para pegar "
                "(regra 7 do portão)."
            )

    def test_as_nove_linhas_de_combinacao_nunca_afirmam_medido_sem_bancada(
        self, mapa: dict[str, dict[str, str]]
    ) -> None:
        """As nove `combinacao.*` do SN30 respondem — e nenhuma diz `medido`."""
        combinacoes = [
            r
            for r in mapa.values()
            if r["controle"] == "sn30" and r["chave"].startswith("combinacao.")
        ]
        assert len(combinacoes) == 9
        for linha in combinacoes:
            for lado in ("cabo", "radio"):
                procedencia = linha[f"{lado}_de_onde_sei"].strip()
                assert procedencia != DE_ONDE_SEI_FORTE, (
                    f"{linha['id']}: {lado}_de_onde_sei virou "
                    f"{DE_ONDE_SEI_FORTE!r} sem bancada do SN30 — só o "
                    "aparelho na mesa fecha uma linha de combinação, e o "
                    "ensaio dela mora em `docs/data/ensaios.csv`."
                )
                if linha[f"{lado}_aciona"].strip():
                    assert procedencia, (
                        f"{linha['id']}: `{lado}_aciona` respondido "
                        f"({linha[f'{lado}_aciona']!r}) com "
                        f"`{lado}_de_onde_sei` vazio — a régua 19 do portão "
                        "(`lado-sem-regua`) existe exatamente para isto."
                    )


class TestOFonteAindaSustentaOQueEstaLevaAfirmou:
    """Metade 2 da mordida: tirar o fato do código reprova."""

    def test_as_tres_subcomandos_de_pareamento_continuam_so_declaradas(
        self, fonte_do_driver: str
    ) -> None:
        for nome in (
            "JC_SUBCMD_MANUAL_BT_PAIRING",
            "JC_SUBCMD_RESET_PAIRING_INFO",
            "JC_SUBCMD_LOW_POWER_MODE",
        ):
            ocorrencias = len(re.findall(re.escape(nome), fonte_do_driver))
            assert ocorrencias == 1, (
                f"`{nome}` aparece {ocorrencias} vezes em {DRIVER.name} — "
                "era 1 (só o #define). Se cresceu, alguém passou a EMITIR "
                "este subcomando, e `identidade.pareamento@sn30` (cabo) "
                "precisa ser remedida, não só reescrita."
            )

    def test_o_driver_continua_sem_uma_palavra_de_camera_ou_infravermelho(
        self, fonte_do_driver: str
    ) -> None:
        assert not re.search(r"camera|infrared", fonte_do_driver, re.IGNORECASE), (
            f"{DRIVER.name} passou a mencionar câmera/infravermelho — "
            "plataforma.camera_ir@sn30 precisa ser reaberta."
        )

    def test_o_promote_player_continua_tratando_8bitdo_e_pro_como_uma_classe_so(self) -> None:
        """`_promote_player` não ramifica por família: DualSense, 8BitDo e Pro passam igual."""
        import ast

        arvore = ast.parse(COOP.read_text(encoding="utf-8"))
        funcao = next(
            n for n in ast.walk(arvore)
            if isinstance(n, ast.FunctionDef) and n.name == "_promote_player")
        palavras = {
            n.id if isinstance(n, ast.Name) else n.attr if isinstance(n, ast.Attribute)
            else str(n.value)
            for n in ast.walk(funcao)
            if isinstance(n, ast.Name | ast.Attribute)
            or (isinstance(n, ast.Constant) and isinstance(n.value, str))
        }
        familias = [p for p in palavras for marca in ("8bitdo", "nintendo", "pro_", "vendor",
                                                     "external", "dualsense")
                    if marca in p.lower()]
        assert not familias, (
            f"`_promote_player` passou a olhar a família do controle {sorted(familias)}: "
            "o vpad uhid Edge deixou de ser o mesmo para 8BitDo e Pro")

    def test_o_led_de_jogador_externo_continua_desligado_por_flag(
        self, fonte_do_external_identity: str
    ) -> None:
        assert "EXTERNAL_PLAYER_LED_ENABLED = False" in fonte_do_external_identity

    def test_a_doc_do_8bitdo_continua_corrigida_sobre_as_referencias_em_src(
        self,
    ) -> None:
        texto = TROUBLESHOOTING_8BITDO.read_text(encoding="utf-8")
        assert "mais de uma centena de linhas" in texto

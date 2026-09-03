"""A fatia SN30 (plataforma/combinação/identidade) das células mudas, 03/09/2026.

Nasceu do pedido dela — *"pqah ok então dispara agentes pra isso então"* —
sobre as 79 linhas com `aciona` mudo em pelo menos um transporte. Esta fatia é
o 8BitDo SN30 nas famílias `plataforma`, `combinacao` e `identidade`.

**Das 37 mudas do SN30 nessas três famílias, DEZ foram respondidas aqui** —
todas por leitura de fonte (o driver `hid-nintendo` desta árvore + `src/`),
sem bancada. O teto do que se afirma sem a mesa dela é `MONTOU`, e nenhuma
célula tocada aqui usa `de_onde_sei = medido`.

As NOVE `combinacao.*` e as três (`identidade.req_dev_info`,
`plataforma.limitador_subcomando`, `plataforma.probe`/`probe.retry`, lado
pendente) continuam mudas DE PROPÓSITO — a própria `nota` de cada uma explica
por quê (bancada dela, ou convenção em disputa entre linhas irmãs), e
preenchê-las por analogia destruiria o valor do mapa. Este arquivo não as
cobre.

Morde nos DOIS sentidos:

1. **apagou a célula, reprova** — uma das dez volta a ler-se como "ninguém
   respondeu", que é o estado de onde saiu.
2. **mudou o fonte, reprova** — cada célula cita um fato do driver ou do
   produto (uma linha que só existe como `#define`, uma ausência de bytes, um
   comentário de código). Se o fato mudar, a célula publicada no
   `html/specs.html` vira mentira, e o teste manda atualizar o mapa no mesmo
   gesto.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MAPA = REPO_ROOT / "docs" / "data" / "mapa-controles.csv"
DRIVER = REPO_ROOT / "assets" / "dkms" / "hid-nintendo" / "hid-nintendo.c"
COOP = REPO_ROOT / "src" / "hefesto_dualsense4unix" / "daemon" / "subsystems" / "coop.py"
EXTERNAL_IDENTITY = (
    REPO_ROOT / "src" / "hefesto_dualsense4unix" / "daemon" / "subsystems" / "external_identity.py"
)
TROUBLESHOOTING_8BITDO = REPO_ROOT / "docs" / "usage" / "troubleshooting-8bitdo.md"

#: As DEZ linhas que esta leva respondeu, com o que cada uma tem de continuar
#: dizendo. `None` = não comparo o valor exato daquele lado (a linha não
#: mexeu nele), só exijo que não volte a ficar vazio se `de_onde_sei` daquele
#: lado estiver preenchido.
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

#: As 4 linhas com `assimetria_declarada` preenchida nesta leva — a régua do
#: portão só AVISA quando falta, então a régua "não sobrescreve o vazio" é
#: quem morde aqui.
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


@pytest.fixture(scope="module")
def fonte_do_coop() -> str:
    return COOP.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def fonte_do_external_identity() -> str:
    return EXTERNAL_IDENTITY.read_text(encoding="utf-8")


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
        # Regra 19 do portão (`lado-sem-regua`): todo lado com `aciona`
        # respondido e conteúdo escrito precisa do `de_onde_sei` daquele
        # lado. Aqui a régua é mais estreita: exige que ele CONTINUE
        # preenchido, não que seja um valor específico — a promoção para
        # `medido` é legítima no dia em que ela medir.
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
        # Nada aqui foi medido no aparelho. Promover o lado que esta leva
        # escreveu para `medido` sem ensaio no caderno
        # (`docs/data/ensaios.csv`) é afirmar prova que esta leva não tem.
        # O lado escrito por esta leva é sempre CABO — exceto em
        # `plataforma.vpad@sn30`, a única das dez onde os dois lados são
        # novos.
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

    def test_as_nove_linhas_de_combinacao_continuam_mudas_de_proposito(
        self, mapa: dict[str, dict[str, str]]
    ) -> None:
        # Estas NÃO foram respondidas por esta leva, e não devem ser — a
        # nota de cada uma diz "só o aparelho na mesa fecha esta linha".
        # Preencher por leitura de código seria exatamente a analogia que a
        # nota adverte que destruiria o valor do mapa. Este teste é o
        # espelho negativo dos de cima: aqui a mordida é NÃO responder.
        combinacoes = [
            r
            for r in mapa.values()
            if r["controle"] == "sn30" and r["chave"].startswith("combinacao.")
        ]
        assert len(combinacoes) == 9
        for linha in combinacoes:
            assert not linha["cabo_aciona"].strip() and not linha["radio_aciona"].strip(), (
                f"{linha['id']}: uma linha de combinação SN30 ganhou "
                "`aciona` sem bancada dela — se foi medição real, ótimo, "
                "mas então ajuste este teste com o mesmo commit."
            )


class TestOFonteAindaSustentaOQueEstaLevaAfirmou:
    """Metade 2 da mordida: tirar o fato do código reprova."""

    def test_as_tres_subcomandos_de_pareamento_continuam_so_declaradas(
        self, fonte_do_driver: str
    ) -> None:
        # identidade.pareamento@sn30 (cabo): o driver TEM os três nomes, mas
        # nenhum tem chamador — é essa ausência que sustenta `cabo_aciona =
        # não`. Se um dia alguém emitir um deles, a contagem sobe para 2+ e
        # este teste cai.
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
        # plataforma.camera_ir@sn30: a ausência de 'camera'/'infrared' no
        # driver inteiro é a evidência negativa que sustenta `existe =
        # nao-tem`. Uma ocorrência nova muda a pergunta.
        assert not re.search(r"camera|infrared", fonte_do_driver, re.IGNORECASE), (
            f"{DRIVER.name} passou a mencionar câmera/infravermelho — "
            "plataforma.camera_ir@sn30 precisa ser reaberta."
        )

    def test_o_promote_player_continua_tratando_8bitdo_e_pro_como_uma_classe_so(
        self, fonte_do_coop: str
    ) -> None:
        # plataforma.vpad@sn30: a evidência é o próprio comentário do
        # produto dizendo que 8BitDo e Pro Controller ganham vpad igual, sem
        # gate por VID/PID. Some o comentário (ou o texto mudar de sentido),
        # a célula perde o chão.
        assert "também ganha vpad uhid Edge" in fonte_do_coop
        assert "8BitDo, Pro Controller" in fonte_do_coop

    def test_o_led_de_jogador_externo_continua_desligado_por_flag(
        self, fonte_do_external_identity: str
    ) -> None:
        # plataforma.referencias_nintendo@sn30: uma das duas funções que
        # tocam externo (apply_player_number) está desligada por este
        # interruptor. Se ele virar True, a prosa da célula (que descreve a
        # superfície de escrita como duas funções, uma desligada) envelhece.
        assert "EXTERNAL_PLAYER_LED_ENABLED = False" in fonte_do_external_identity

    def test_o_enable_imu_continua_escopado_a_oui_que_exclui_8bitdo(
        self, fonte_do_external_identity: str
    ) -> None:
        # A outra metade do mesmo achado: `enable_imu` (a segunda função que
        # toca externo) só dispara para o Pro GENUÍNO — nunca o clone, porque
        # o clone mente VID/PID mas não o MAC/OUI.
        assert "nunca o" in fonte_do_external_identity
        assert "8BitDo, que mente VID/PID mas nunca o MAC" in fonte_do_external_identity

    def test_a_doc_do_8bitdo_continua_corrigida_sobre_as_referencias_em_src(
        self,
    ) -> None:
        # plataforma.referencias_nintendo@sn30 cita esta doc como já
        # corrigida (ao contrário da linha irmã @pro, cujo `cabo_ressalva`
        # registra uma prova CADUCADA). Se a frase sumir, a doc regrediu
        # para a afirmação falsa que a nota de @pro já documentou como
        # caducada — e aí as DUAS linhas (@pro e @sn30) citam uma fonte
        # errada.
        texto = TROUBLESHOOTING_8BITDO.read_text(encoding="utf-8")
        assert "mais de uma centena de linhas" in texto

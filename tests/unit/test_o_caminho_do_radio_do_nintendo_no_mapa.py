"""O caminho do RÁDIO das famílias Nintendo Pro e 8BitDo, no mapa de canais.

Nasceu em 03/09/2026, do pedido dela: *"a ideia é ver o que no código tá setado
pra funcionar só via cabo e não BT. e verificar no specs o caminho do Bt pra
garantir que lá ele possa funcionar em ambos os modos."*

O que este arquivo guarda são CINCO células de rádio que estavam vazias no
``docs/data/mapa-controles.csv`` e agora carregam o caminho medido no fonte do
``hid-nintendo`` que ESTA árvore instala. Ele morde nos DOIS sentidos, e é essa
a razão de existir:

1. **apagou a célula, reprova.** Uma célula de rádio esvaziada volta a ler-se
   como "ninguém respondeu" — que é exatamente o estado de onde ela saiu.
2. **mudou o fonte, reprova.** Cada célula afirma um GATE DE BARRAMENTO do
   driver. Se alguém tirar o gate (por exemplo, deixar ``joycon_may_degrade``
   valer no rádio), a célula vira mentira publicada no ``html/specs.html`` — e
   o teste manda atualizar o mapa no mesmo gesto.

**Nada aqui mede o aparelho.** Todo o conteúdo é leitura de fonte, e é por isso
que as cinco células saíram com ``radio_de_onde_sei = inferido-do-codigo``. O
teto do que se pode afirmar sem a mesa dela é ``MONTOU``.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MAPA = REPO_ROOT / "docs" / "data" / "mapa-controles.csv"
DRIVER = REPO_ROOT / "assets" / "dkms" / "hid-nintendo" / "hid-nintendo.c"
LEDS = REPO_ROOT / "src" / "hefesto_dualsense4unix" / "core" / "external_leds.py"

#: As colunas que compõem "o caminho do rádio" de uma linha, na ordem em que a
#: régua as cobra. `report_id` e `offset` ficam de fora do exigido: nem toda
#: linha tem report ou byte (uma regra udev não tem), e cobrá-los produziria
#: célula preenchida por obrigação, que é pior que célula muda.
COLUNAS_DO_CAMINHO = (
    "radio_canal",
    "radio_comando",
    "radio_de_onde_sei",
    "radio_codigo_ref",
)

#: As CINCO linhas que ganharam caminho de rádio em 03/09/2026, com o gate do
#: driver que cada uma afirma. O gate é uma string que TEM de continuar no
#: fonte; some ela, e a célula do mapa deixou de descrever esta árvore.
LINHAS_E_SEUS_GATES = {
    "plataforma.udev_autosuspend@pro": None,  # o gate é do udev, não do driver
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
        # Nenhuma destas células foi medida no aparelho. Promover qualquer uma
        # para `medido` sem ensaio no caderno é afirmar prova que não houve —
        # e o teto do que se afirma sem a mesa dela é MONTOU.
        assert mapa[identificador]["radio_de_onde_sei"].strip() == "inferido-do-codigo"

    def test_o_veredito_do_clone_por_radio_continua_mudo(
        self, mapa: dict[str, dict[str, str]]
    ) -> None:
        # `plataforma.probe@sn30` ganhou o CAMINHO e não o VEREDITO: o 8BitDo
        # nunca foi pareado nesta casa em modo Switch (`8BITDO-NO-RÁDIO-01`), e
        # isso é sessão dela. Preencher `radio_aciona` por leitura de fonte
        # seria exatamente o defeito que o caminho escrito existe para evitar.
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
            "html/specs.html publica como fato um caminho que o fonte não tem "
            "mais."
        )

    def test_joycon_may_degrade_recusa_o_radio_pelo_e_logico(
        self, fonte_do_driver: str
    ) -> None:
        # É este `&&` que faz a identidade de último recurso ser só do cabo. O
        # aparelho não recusa nada; quem recusa é o operador.
        corpo = _corpo_da_funcao(fonte_do_driver, "joycon_may_degrade")
        assert "usb_probe_degrade" in corpo and "joycon_using_usb" in corpo

    def test_o_driver_nunca_le_o_endereco_que_o_radio_ja_lhe_deu(
        self, fonte_do_driver: str
    ) -> None:
        # A DÍVIDA que a `radio_ressalva` de `identidade.req_dev_info.fallback
        # @sn30` registra: por rádio o BD_ADDR chega ao driver em `hdev->uniq`
        # (é o `HID_UNIQ` que as nossas regras 82 e 84 casam), e o driver não o
        # lê — só ESCREVE `uniq` nos dois nós de input. No dia em que alguém
        # construir a leitura, este teste cai e a célula do mapa muda com ele.
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
        # O fato que sustenta a `radio_ressalva` de `plataforma.escrita_crua
        # @pro`: o driver já manda o 0x40 nos dois fios, então o gate
        # `_IMU_ENABLE_ALLOWED_BUS` guarda uma escrita provavelmente redundante.
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
        # :1652 (engenharia reversa da comunidade) diz 8 ms por rádio; :1659-1664
        # (o teste do próprio autor do driver) diz 11 ou 15 ms. Quem citar só a
        # primeira publica um número que a própria fonte desmente — e a medição
        # desta casa (89,2 relatórios/s = 11,2 ms) concorda com a segunda.
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
        # A frase pode aparecer — CITADA, para dizer o que caiu. O que não pode
        # é aparecer AFIRMANDO: toda ocorrência tem de vir acompanhada do
        # desmentido, senão a versão velha volta a viver ao lado da certa, que é
        # o defeito que a lei do fato errado existe para matar.
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
    """O corpo da função C ``nome``, do ``{`` de abertura ao ``}`` da coluna 0.

    Régua deliberadamente boba — o fonte do driver é kernel style, com a chave
    de fechamento sempre na coluna zero. Um parser de C aqui seria uma segunda
    régua para o mesmo dado, que é dívida com nome.
    """
    padrao = re.compile(rf"^[\w \t*]*\b{re.escape(nome)}\s*\(", re.MULTILINE)
    achado = padrao.search(fonte)
    assert achado is not None, f"função não encontrada no fonte: {nome}"
    abre = fonte.index("{", achado.end())
    fecha = fonte.index("\n}", abre)
    return fonte[abre:fecha]

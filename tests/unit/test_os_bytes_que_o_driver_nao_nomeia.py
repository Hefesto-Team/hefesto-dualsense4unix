"""A régua do levantamento de 03/09/2026 — o que NÃO é canal, e os bytes que o
driver não nomeia.

O documento `docs/protocol/dualsense-o-que-nao-e-canal-e-os-bytes-que-o-driver-nao-nomeia.md`
publica offsets do DualSense levantados em repositório público. Um número
publicado sem régua é um número que envelhece calado — foi exatamente assim que
esta casa descobriu, em 31/08/2026, que o portão do mapa é CEGO ao conteúdo das
colunas sem domínio: um byte de LED trocado de 11 para 47 passou com `rc=0`.

Esta régua fecha essa porta para o documento novo. Ela NÃO confere o que a
internet disse — isso ninguém pode conferir sem o aparelho. Ela confere a
ÂNCORA: cada offset que o documento publica como sendo `reserved` no driver é
recalculado A PARTIR DO FONTE C compilado nesta máquina, e comparado com o que
está escrito na página. Se o driver mudar, ou se alguém editar um número na
página, a régua reprova.

MORDIDA — as quatro foram arrancadas em 03/09/2026, e as quatro reprovaram:

===========================================  ==================================
o que se estraga                             quem reprova
===========================================  ==================================
`55-62` -> `55-61` no documento              `..._as_faixas_que_o_driver_declara`
`0x1F` -> `0x1E` no documento                `..._mascara_dos_leds_de_jogador...`
`medido` numa das seis linhas do mapa        `..._nenhuma_linha_..._ter_medido`
`camera_ir` de volta a `desconhecido`        `..._camera_ir_..._com_a_razao`
===========================================  ==================================
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
DRIVER = RAIZ / "assets/dkms/hid-playstation/hid-playstation.c"
DOC = RAIZ / "docs/protocol/dualsense-o-que-nao-e-canal-e-os-bytes-que-o-driver-nao-nomeia.md"
MAPA = RAIZ / "docs/data/mapa-controles.csv"

#: As seis chaves do tema, todas do controle `dualsense`.
CHAVES_DO_TEMA = (
    "plataforma.camera_ir",
    "plataforma.transporte_radio",
    "plataforma.vigia_zumbi",
    "plataforma.adocao",
    "plataforma.slot_jogador",
    "plataforma.vpad",
)

#: Tamanho em bytes de cada tipo que aparece nas duas structs lidas. Um tipo
#: novo no fonte reprova por `KeyError` em vez de calcular offset errado em
#: silêncio — que é o defeito que esta régua existe para não repetir.
TAMANHOS = {
    "u8": 1,
    "__le16": 2,
    "__le32": 4,
    "struct dualsense_touch_point": 4,
}

#: Uma DECLARAÇÃO inteira: o tipo e tudo até o `;`. A lista de nomes vem
#: depois, porque o driver escreve `u8 x, y;` — três linhas assim (`x, y`,
#: `rx, ry`, `z, rz`) valem 6 bytes, e um leitor que só aceite um nome por
#: linha os perde e desloca a struct inteira em 6. Aconteceu na primeira
#: versão desta régua, e o sintoma foi `buttons` aparecer no offset 1.
_DECLARACAO = re.compile(
    r"^\s*(u8|__le16|__le32|struct dualsense_touch_point)\s+([^;]+);"
)
_DECLARADOR = re.compile(r"^(\w+)\s*(?:\[\s*(\d+)\s*\])?$")


def _campos_da_struct(fonte: str, nome: str) -> tuple[dict[str, tuple[int, int]], int]:
    """Offsets `(primeiro, último)` de cada campo, e o tamanho total da struct.

    Lê do fonte C, não de uma tabela redigitada: a lista tem UM dono, e ele é o
    driver que está compilado nesta máquina.
    """
    inicio = fonte.index(f"struct {nome} {{")
    corpo = fonte[inicio:]
    corpo = corpo[: corpo.index("\n} __packed;")]

    campos: dict[str, tuple[int, int]] = {}
    posicao = 0
    for linha in corpo.splitlines()[1:]:
        casada = _DECLARACAO.match(linha)
        if casada is None:
            continue
        tipo, declaradores = casada.groups()
        for bruto in declaradores.split(","):
            casado = _DECLARADOR.match(bruto.strip())
            assert casado is not None, (
                f"declarador que esta régua não sabe ler em `{nome}`: "
                f"{bruto.strip()!r}. Ensine-a antes de confiar nos offsets — um "
                "campo pulado desloca a struct inteira em silêncio"
            )
            campo, quantos = casado.groups()
            largura = TAMANHOS[tipo] * (int(quantos) if quantos else 1)
            campos[campo] = (posicao, posicao + largura - 1)
            posicao += largura
    return campos, posicao


@pytest.fixture(scope="module")
def entrada() -> tuple[dict[str, tuple[int, int]], int]:
    return _campos_da_struct(DRIVER.read_text(encoding="utf-8"), "dualsense_input_report")


@pytest.fixture(scope="module")
def saida() -> tuple[dict[str, tuple[int, int]], int]:
    return _campos_da_struct(
        DRIVER.read_text(encoding="utf-8"), "dualsense_output_report_common"
    )


@pytest.fixture(scope="module")
def doc() -> str:
    return DOC.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def linhas_do_tema() -> dict[str, dict[str, str]]:
    with MAPA.open(encoding="utf-8", newline="") as fp:
        todas = list(csv.DictReader(fp))
    achadas = {
        linha["chave"]: linha
        for linha in todas
        if linha["controle"] == "dualsense" and linha["chave"] in CHAVES_DO_TEMA
    }
    assert set(achadas) == set(CHAVES_DO_TEMA), (
        "o mapa deixou de ter uma das seis linhas do tema: "
        f"faltam {sorted(set(CHAVES_DO_TEMA) - set(achadas))}"
    )
    return achadas


# ─────────────────────────────────────────────────────────────────────────
# A ÂNCORA: o fonte C decide, o documento obedece.
# ─────────────────────────────────────────────────────────────────────────


def test_o_corpo_de_entrada_tem_63_bytes_e_o_common_de_saida_tem_47(entrada, saida):
    """Os dois números que sustentam o argumento de que não sobra endereço.

    Se a struct crescer, o argumento da §2 do documento ("não há vaga onde uma
    câmera caberia") deixa de valer sozinho e alguém tem de reabrir a conta.
    """
    _, total_entrada = entrada
    _, total_saida = saida
    assert total_entrada == 63, (
        f"o corpo do report de entrada mudou para {total_entrada} B no driver; "
        "o documento publica 63 e a conta de endereços da §2 precisa ser refeita"
    )
    assert total_saida == 47, (
        f"o `common` de saída mudou para {total_saida} B no driver; "
        "o documento publica 47"
    )


def test_o_doc_publica_as_faixas_que_o_driver_declara(entrada, doc):
    """Cada faixa `reserved` da §3 tem de ser a faixa que o driver declara.

    Este é o teste que morde de verdade: a tabela do documento foi escrita à
    mão, e um dígito trocado nela não é pego por portão nenhum desta casa.
    """
    campos, _ = entrada
    esperado = {
        "reserved": "11-14",
        "reserved3": "40-51",
        "reserved4": "55-62",
    }
    for campo, faixa_publicada in esperado.items():
        primeiro, último = campos[campo]
        faixa_do_driver = f"{primeiro}-{último}"
        assert faixa_do_driver == faixa_publicada, (
            f"`{campo}` está em {faixa_do_driver} no driver, e o documento "
            f"publica {faixa_publicada}"
        )
        assert faixa_do_driver in doc, (
            f"o documento não cita a faixa {faixa_do_driver} de `{campo}`"
        )


def test_as_duas_posicoes_vivas_que_o_vpad_zera_sao_as_que_o_doc_nomeia(entrada, doc):
    """O achado central da linha `plataforma.vpad`: 10 e 54 não são reserva.

    O vpad zera 26 posições; 24 são `reserved` no driver e DUAS carregam dado —
    `buttons[3]` (o quarto byte de botão, que o driver declara e nunca lê) e
    `status[2]`. Se o driver passar a nomear qualquer uma delas, o texto do
    documento vira mentira e esta régua avisa.
    """
    campos, _ = entrada
    assert campos["buttons"] == (7, 10), (
        f"`buttons[4]` saiu de 7-10 para {campos['buttons']}: a posição 10, que o "
        "documento chama de dado vivo zerado pelo vpad, mudou de endereço"
    )
    assert campos["status"] == (52, 54), (
        f"`status[3]` saiu de 52-54 para {campos['status']}: a posição 54 mudou"
    )
    assert campos["reserved2"] == (31, 31), (
        "`reserved2` deixou de ser o byte 31 — é a posição que o mapeamento "
        f"público chama de temperatura; agora é {campos['reserved2']}"
    )


def test_os_offsets_de_luz_do_report_de_saida_batem_com_o_driver(saida, doc):
    """A §6 publica `common[41..46]`. O driver é quem diz onde eles estão."""
    campos, _ = saida
    esperado = {
        "lightbar_setup": 41,
        "led_brightness": 42,
        "player_leds": 43,
        "lightbar_red": 44,
        "lightbar_green": 45,
        "lightbar_blue": 46,
    }
    for campo, offset_publicado in esperado.items():
        primeiro, _ = campos[campo]
        assert primeiro == offset_publicado, (
            f"`{campo}` está em common[{primeiro}] no driver, e o documento "
            f"publica common[{offset_publicado}]"
        )
    assert f"common[{esperado['player_leds']}]" in doc, (
        "o documento deixou de citar `common[43]`, que é onde mora o byte dos "
        "LEDs de jogador — o endereço que a linha `plataforma.slot_jogador` "
        "manda procurar em `luz.led_jogador*`"
    )


def test_a_mascara_dos_leds_de_jogador_bate_com_o_driver(doc):
    """A §4 afirma CONFIRMAÇÃO INDEPENDENTE de 0x04, 0x0A, 0x15, 0x1B, 0x1F.

    O lado de fora (o `WinUHid`) não dá para conferir daqui. O lado de dentro
    dá: os cinco valores saem de `player_ids[]` no driver desta máquina. Se
    eles divergirem, a confirmação que o documento anuncia deixa de existir.
    """
    fonte = DRIVER.read_text(encoding="utf-8")
    trecho = fonte[fonte.index("static const int player_ids[5]") :]
    trecho = trecho[: trecho.index("};")]

    mascaras = []
    for linha in trecho.splitlines()[1:]:
        bits = [int(b) for b in re.findall(r"BIT\((\d)\)", linha)]
        if bits:
            valor = 0
            for bit in bits:
                valor |= 1 << bit
            mascaras.append(valor)

    assert mascaras == [0x04, 0x0A, 0x15, 0x1B, 0x1F], (
        f"`player_ids[]` no driver virou {[hex(m) for m in mascaras]}; o "
        "documento publica 0x04, 0x0A, 0x15, 0x1B, 0x1F como o valor que uma "
        "segunda implementação confirma"
    )
    for mascara in mascaras:
        assert f"0x{mascara:02X}" in doc, (
            f"o documento não cita a máscara 0x{mascara:02X} de `player_ids[]`"
        )


# ─────────────────────────────────────────────────────────────────────────
# A HONESTIDADE DE GRAU: nada foi ao aparelho nesta leva.
# ─────────────────────────────────────────────────────────────────────────


def test_nenhuma_linha_do_tema_afirma_ter_medido(linhas_do_tema):
    """`medido` é o vocabulário mais forte do mapa, e esta leva não o ganhou.

    O levantamento de 03/09 foi feito em repositório público com a máquina dela
    ocupada por dois controles vivos. Nenhuma célula pode dizer `medido` por
    causa dele — e o portão do mapa não pega isso, porque `medido` é valor de
    domínio válido em qualquer linha.
    """
    for chave, linha in linhas_do_tema.items():
        for lado in ("cabo", "radio"):
            de_onde_sei = (linha[f"{lado}_de_onde_sei"] or "").strip()
            if de_onde_sei != "medido":
                continue
            provado = (linha["provado_em"] or "").strip()
            assert provado, (
                f"`{chave}` diz `{lado}_de_onde_sei = medido` sem `provado_em`: "
                "o levantamento de 03/09/2026 é leitura de fonte pública, e "
                "nenhuma das seis linhas do tema mediu coisa alguma"
            )


def test_o_que_veio_de_fora_declara_a_fonte(linhas_do_tema):
    """Célula com `de_onde_sei = afirmado-no-doc` tem de dizer de qual doc.

    A regra 19 do portão cobra que exista PROVENIÊNCIA quando há conteúdo
    escrito. Ela não cobra o contrário: um `afirmado-no-doc` com
    `fonte_externa` vazia afirma sobre o aparelho apontando para lugar nenhum.
    """
    for chave, linha in linhas_do_tema.items():
        de_fora = any(
            (linha[f"{lado}_de_onde_sei"] or "").strip() == "afirmado-no-doc"
            for lado in ("cabo", "radio")
        )
        if not de_fora:
            continue
        fonte = (linha["fonte_externa"] or "").strip()
        assert fonte, (
            f"`{chave}` diz `afirmado-no-doc` e deixou `fonte_externa` vazia: "
            "a afirmação não tem endereço"
        )
        assert DOC.name in fonte, (
            f"`{chave}` não aponta para `{DOC.name}`, que é onde o levantamento "
            f"de 03/09/2026 está por extenso; aponta para {fonte!r}"
        )


def test_a_camera_ir_do_dualsense_esta_respondida_com_a_razao(linhas_do_tema):
    """A entrega desta linha é dizer NÃO com endereço, não achar um offset.

    Ela viveu como `desconhecido` com as células mudas de propósito desde
    11/08/2026. Voltar para `desconhecido` seria perder o trabalho de ir buscar
    a resposta fora; voltar para `tem` seria inventar um canal.
    """
    linha = linhas_do_tema["plataforma.camera_ir"]
    assert linha["existe"] == "nao-tem", (
        f"`plataforma.camera_ir@dualsense` voltou a `existe = {linha['existe']!r}`"
    )
    for lado in ("cabo", "radio"):
        assert linha[f"{lado}_aciona"] == "não"
        assert linha[f"{lado}_por_que_nao_aciona"] == "nada-a-acionar", (
            f"`{lado}_por_que_nao_aciona` ficou {linha[f'{lado}_por_que_nao_aciona']!r}: "
            "uma linha que não aciona porque o aparelho NÃO TEM a peça precisa "
            "nomear a causa, senão a tela pode culpar o nosso código por ela"
        )
        assert "não-localizado" in (linha[f"{lado}_comando"] or ""), (
            f"`{lado}_comando` perdeu a razão escrita da ausência"
        )


def test_nada_desta_leva_subiu_degrau_de_escada(linhas_do_tema):
    """`ate_onde_foi` mede o que FOI AO APARELHO. Nada foi.

    As duas células que já tinham `MONTOU` (a linha do vpad) são de 19/08/2026 e
    ficam. O que esta régua proíbe é uma leva de LEITURA subir degrau — e
    `O APARELHO OBEDECEU` é o degrau que um levantamento em documento jamais
    pode escrever.
    """
    proibidos = {"SAIU NO FIO", "O APARELHO OBEDECEU", "O JOGO RECEBEU", "O JOGO REAGIU"}
    for chave, linha in linhas_do_tema.items():
        for lado in ("cabo", "radio"):
            degrau = (linha[f"{lado}_ate_onde_foi"] or "").strip()
            assert degrau not in proibidos, (
                f"`{chave}` tem `{lado}_ate_onde_foi = {degrau!r}`, um degrau que "
                "só se ganha tocando o aparelho — e o levantamento de 03/09/2026 "
                "não tocou"
            )

"""As seis regras de topologia — o que cada uma acusa, e o que ela CALA.

Uma regra que cala é resultado, não ausência. Metade destes testes afirma
silêncio: a webcam de cabo que não pode ser acusada, o dongle que não acusa
outro dongle, o teclado que já está fora do hub. Foi um falso positivo — a
`HD Pro Webcam C920` publicada como vizinhança apertada — que fez esta sprint
existir, e um catálogo cujas regras todas disparam não distingue nada.

POR QUE NÃO HÁ ÁRVORE DE ARQUIVOS AQUI
---------------------------------------

Nenhum teste deste arquivo cria diretório nem lê `/sys`. As regras de
`ordens_da_mesa` são puras sobre um `Censo` e uma lista de `NoDeEntrada`, e os
dois são dataclasses: montá-los à mão testa a REGRA, e não o leitor de sysfs,
que tem bateria própria (`test_o_censo_le_o_barramento_inteiro.py` e
`test_entradas_do_gabinete.py`). A bancada mora em `bancada_das_ordens.py`.
"""
from __future__ import annotations

from tests.unit import bancada_das_ordens as bancada
import pytest

from hefesto_dualsense4unix.integrations import ordens_da_mesa as ordens
from hefesto_dualsense4unix.integrations.censo_do_barramento import Censo


def leitura(**campos: object) -> ordens.Leitura:
    """A bancada inteira como `Leitura`, com o que o teste quiser por cima."""
    base: dict[str, object] = {
        "censo": bancada.censo(),
        "entradas": bancada.entradas(),
    }
    base.update(campos)
    return ordens.Leitura(**base)  # type: ignore[arg-type]


def chaves(catalogo: tuple[ordens.Ordem, ...]) -> tuple[str, ...]:
    return tuple(ordem.chave for ordem in catalogo)


# ---------------------------------------------------------------------------
# O catálogo inteiro, contra o que a sprint mediu em 24/08/2026.
# ---------------------------------------------------------------------------


def test_o_catalogo_dispara_exatamente_o_que_foi_medido() -> None:
    """R1, R3 e R4 acusam; R2, R5 e R6 calam — e o silêncio é o resultado.

    É a medição da §2.7 da sprint: nesta mesa todo `power/control` responde
    `on` e todo `over_current_count` responde `0`. Se R5 ou R6 aparecerem aqui,
    a comparação delas foi invertida em algum lugar.
    """
    achadas = chaves(ordens.catalogo(leitura()))
    assert achadas == (
        ordens.R1_RADIO_LARGO_NO_MESMO_HUB,
        ordens.R3_DONGLE_ATRAS_DE_HUB,
        ordens.R4_TECLADO_SO_NO_HUB,
    )


def test_uma_regra_produz_no_maximo_uma_ordem() -> None:
    """Duas ordens da mesma regra dariam duas dispensas para a mesma decisão."""
    achadas = chaves(ordens.catalogo(leitura()))
    assert len(achadas) == len(set(achadas))


# ---------------------------------------------------------------------------
# R1 — e a régua de "mesmo plástico", que é o coração da sprint.
# ---------------------------------------------------------------------------


def test_r1_ve_atraves_do_busnum() -> None:
    """O aparelho de 5 Gbps e o dongle estão em `busnum` 3 e 4, e R1 os vê.

    É o par que `mesa_de_radio.vizinhancas_apertadas` recusa no
    `if primeiro.busnum != segundo.busnum: continue`.
    """
    ordem = ordens.radio_largo_no_mesmo_hub(leitura())
    assert ordem is not None
    assert "4-1.1.2" in ordem.arranjo
    assert "3-1.1.4" in ordem.arranjo


def test_r1_ve_o_hub_cujos_dois_lados_tem_numeros_diferentes() -> None:
    """A MORDIDA DA ORDEM-1: quem costura os dois lados é o `peer`, não a conta.

    Medido nesta máquina em 25/08/2026: `usb1-port5 peer -> usb2-port1`,
    `usb1-port6 -> usb2-port2`, `usb1-port7 -> usb2-port3`. **Os números dos
    dois lados divergem**, e esses buracos são `hotplug` — são justamente as
    entradas que R1 recomenda como destino.

    Um hub encaixado ali enumera `1-3` (`devpath` "3") e `2-1` (`devpath` "1").
    Trocar o `peer` por uma comparação de `devpath` faz R1 ficar cega aqui, e
    este teste é o que reprova.
    """
    censo, entradas = bancada.bancada_do_hub_em_numeros_diferentes()
    ordem = ordens.radio_largo_no_mesmo_hub(
        ordens.Leitura(censo=censo, entradas=entradas)
    )
    assert ordem is not None, (
        "R1 ficou cega num hub cujos dois lados têm números diferentes — "
        "a régua voltou a casar os lados por número em vez de pelo `peer`"
    )


def test_r1_cala_quando_o_peer_nao_costura_nada() -> None:
    """Sem `peer`, o produto não SABE que os dois hubs são um só — e cala.

    Não saber que dois hubs são o mesmo plástico não é o mesmo que saber que
    eles são plásticos diferentes, mas a ordem manda uma pessoa se ajoelhar
    atrás do gabinete: na dúvida ela não nasce.
    """
    sem_peer = tuple(
        no_de_entrada
        for no_de_entrada in bancada.entradas()
        if not no_de_entrada.no.startswith(("3-1", "4-1"))
    )
    assert ordens.radio_largo_no_mesmo_hub(leitura(entradas=sem_peer)) is None


def test_r1_nao_chuta_wifi() -> None:
    """Classe `ff` e sem declaração dela: a ordem NÃO escreve "Wi-Fi".

    O `product` deste aparelho diz "802.11ac NIC" e isso não o torna Wi-Fi para
    o produto — o kernel declinou de classificar, e adivinhar por texto é como
    se erra com confiança. Ler o `product` para nomear faz a palavra aparecer, e
    este teste reprova.
    """
    ordem = ordens.radio_largo_no_mesmo_hub(leitura())
    assert ordem is not None
    todo_o_texto = " ".join(
        [ordem.acao] + [linha.texto for linha in ordem.linhas]
    ).lower()
    assert "wi-fi" not in todo_o_texto
    assert "wifi" not in todo_o_texto
    assert "802.11" not in todo_o_texto
    assert "você ainda não identificou" in todo_o_texto


def test_r1_chama_pelo_nome_que_ela_declarou() -> None:
    """Declarado por ela, o aparelho passa a ter nome — e é o nome DELA."""
    ordem = ordens.radio_largo_no_mesmo_hub(
        leitura(nomes_declarados={"2357:012d": "o adaptador de rede"})
    )
    assert ordem is not None
    assert "o adaptador de rede" in ordem.acao


# ---------------------------------------------------------------------------
# R2 — a webcam que fez esta sprint existir.
# ---------------------------------------------------------------------------


def test_r2_nao_acusa_a_webcam() -> None:
    """Webcam de cabo colada a um dongle: ZERO ordens.

    É o falso positivo real desta bancada — a tela publicou `▲ Vizinhança das
    portas` acusando uma `HD Pro Webcam C920`, classe `0e/01/00`, que não
    irradia 2,4 GHz. Tirar o filtro de espécie faz a ordem nascer, e reprova.
    """
    webcam = bancada.aparelho(
        "3-3", pai="usb3", busnum=3, devpath="3", pci=bancada.PCI_DO_HUB,
        classe="0e", subclasse="01", protocolo="00", vid="046d", pid="082d",
        produto="HD Pro Webcam C920",
    )
    ordem = ordens.dois_radios_colados(
        leitura(
            censo=bancada.censo(mais=(webcam,)),
            vizinhas=(("7", "8"),),
            ocupante_da_entrada={"7": "3-1.2", "8": "3-3"},
        )
    )
    assert ordem is None


def test_r2_acusa_quando_os_dois_lados_irradiam() -> None:
    """Dois adaptadores Bluetooth colados no desenho dela: uma ordem."""
    ordem = ordens.dois_radios_colados(
        leitura(
            vizinhas=(("7", "8"),),
            ocupante_da_entrada={"7": "3-1.2", "8": "3-1.1.4"},
        )
    )
    assert ordem is not None
    assert ordem.chave == ordens.R2_DOIS_RADIOS_COLADOS


def test_r2_cala_sem_o_desenho_dela() -> None:
    """Sem desenho não há vizinhança, e isso NÃO é "está tudo certo"."""
    assert ordens.dois_radios_colados(leitura(vizinhas=())) is None


# ---------------------------------------------------------------------------
# R3 — e a contra-regra, que é metade da regra.
# ---------------------------------------------------------------------------


def test_r3_nao_acusa_dongle_de_dongle() -> None:
    """Três adaptadores no mesmo hub é o arranjo que o GUIA manda comprar.

    R3 conta que o CAMINHO até o computador passa por um hub. Ela nunca diz que
    um dongle atrapalha outro — comparar dongle com dongle faria três ordens
    nascerem, e reprova.
    """
    ordem = ordens.dongle_atras_de_hub(leitura())
    assert ordem is not None
    texto = " ".join(linha.texto for linha in ordem.linhas).lower()
    assert "um do outro" not in texto
    assert "outro adaptador" not in texto
    assert "hub" in texto


def test_r3_calada_sem_buraco_livre() -> None:
    """Sem entrada livre, a ordem nasce SEM AÇÃO — e diz por quê.

    Um imperativo que manda mover para lugar nenhum é pior que silêncio.
    Ignorar a contagem de livres faz a ação nascer assim mesmo, e reprova.
    """
    ordem = ordens.dongle_atras_de_hub(
        leitura(entradas=bancada.entradas(sem=bancada.NOS_LIVRES))
    )
    assert ordem is not None
    assert ordem.destino == ""
    assert ordem.acao == ""
    assert ordem.tem_acao is False
    assert ordens.SEM_DESTINO in ordem.ganho_esperado.texto


def test_r3_nao_oferece_destino_dentro_do_proprio_hub() -> None:
    """O buraco vazio do hub externo NÃO é destino: `unknown` não é `hotplug`.

    `3-1-port3` está vazio e é do mesmo hub de onde a ordem manda tirar o
    dongle. Oferecê-lo seria mandar mudar de buraco dentro do hub e chamar isso
    de conserto.
    """
    ordem = ordens.dongle_atras_de_hub(
        leitura(entradas=bancada.entradas(sem=bancada.NOS_LIVRES))
    )
    assert ordem is not None
    assert "3-1-port3" not in ordem.acao
    assert ordem.acao == ""


# ---------------------------------------------------------------------------
# R4 — a única regra que não fala de rádio.
# ---------------------------------------------------------------------------


def test_r4_cala_com_teclado_direto() -> None:
    """Um teclado fora do hub e R4 cala: a casa não fica sem teclado.

    Contar só os teclados que estão em hub faz a ordem nascer, e reprova.
    """
    direto = bancada.aparelho(
        "1-1", pai="usb1", busnum=1, devpath="1", pci=bancada.PCI_DA_PLACA,
        classe="03", subclasse="01", protocolo="01", vid="04d9", pid="0169",
    )
    assert ordens.teclado_so_no_hub(
        leitura(censo=bancada.censo(mais=(direto,)))
    ) is None


def test_r4_nao_promete_radio() -> None:
    """R4 é a única que não fala de rádio, e a terceira linha diz isso."""
    ordem = ordens.teclado_so_no_hub(leitura())
    assert ordem is not None
    assert "não muda o rádio" in ordem.ganho_esperado.texto


def test_r4_cala_sem_teclado_nenhum() -> None:
    assert ordens.teclado_so_no_hub(
        leitura(censo=bancada.censo(sem=("3-1.4",)))
    ) is None


# ---------------------------------------------------------------------------
# R5 e R6 — as duas que calam nesta bancada, e o que as faz falar.
# ---------------------------------------------------------------------------


def test_r5_r6_calam_nesta_bancada() -> None:
    """Tudo `on` e `over_current_count` zero: nenhuma das duas nasce.

    Inverter a comparação faz as duas nascerem, e reprova.
    """
    assert ordens.dongle_dorme(leitura()) is None
    assert ordens.entrada_reclamou_de_corrente(leitura()) is None


@pytest.mark.parametrize(
    ("regra", "campo", "valor", "chave"),
    [
        (ordens.dongle_dorme, "controle", "auto", ordens.R5_DONGLE_DORME),
        (
            ordens.entrada_reclamou_de_corrente,
            "excesso",
            3,
            ordens.R6_ENTRADA_RECLAMOU_DE_CORRENTE,
        ),
    ],
)
def test_r5_r6_falam_quando_o_numero_muda(
    regra: object, campo: str, valor: object, chave: str
) -> None:
    """A prova de que o silêncio de R5/R6 é medição, e não regra morta."""
    doente = bancada.aparelho(
        "3-1.1.4", pai="3-1.1", busnum=3, devpath="1.1.4",
        pci=bancada.PCI_DO_HUB, atras_de_hub=True, classe="e0", subclasse="01",
        protocolo="01", vid="2357", pid="0604", **{campo: valor},  # type: ignore[arg-type]
    )
    sadios = tuple(
        a for a in bancada.APARELHOS if a.nome_do_kernel != "3-1.1.4"
    )
    ordem = regra(  # type: ignore[operator]
        leitura(censo=Censo(aparelhos=(*sadios, doente)))
    )
    assert ordem is not None
    assert ordem.chave == chave


# ---------------------------------------------------------------------------
# O que NENHUMA ordem pode dizer.
# ---------------------------------------------------------------------------


def test_nenhuma_ordem_publica_serial() -> None:
    """O serial identifica a unidade dela tão bem quanto o MAC, e a tela é PNG.

    `scripts/check_anonymity.sh` diz isso por escrito, e a tela desta aba é
    fotografada e versionada por `scripts/gui-captura/retratar_abas.py`.
    """
    seriais = set(bancada.SERIAIS.values())
    for ordem in ordens.catalogo(leitura()):
        texto = " ".join([ordem.acao, ordem.arranjo] + [
            linha.texto for linha in ordem.linhas
        ])
        for serial in seriais:
            assert serial.lower() not in texto.lower()


def test_a_identidade_nao_carrega_o_serial() -> None:
    """O serial entra em `identidades`, decide a ambiguidade, e morre lá."""
    achadas = ordens.identidades(
        bancada.censo(), ler_serial=bancada.ler_serial
    )
    for identidade in achadas.values():
        for serial in bancada.SERIAIS.values():
            assert serial.lower() not in repr(identidade).lower()


def test_dois_dongles_de_mesmo_vid_pid_sao_separados_pelo_serial() -> None:
    """`2357:0604` são dois, e só o serial os separa — nenhum é ambíguo."""
    achadas = ordens.identidades(
        bancada.censo(), ler_serial=bancada.ler_serial
    )
    assert achadas["3-1.1.4"].ambigua is False
    assert achadas["3-1.2"].ambigua is False


def test_sem_serial_a_tripla_colapsa_e_a_identidade_fica_ambigua() -> None:
    """Dois aparelhos que o sysfs não sabe separar são, de fato, ambíguos."""
    achadas = ordens.identidades(bancada.censo(), ler_serial=lambda _no: "")
    assert achadas["3-1.1.4"].ambigua is True
    assert achadas["3-1.2"].ambigua is True


def test_nenhuma_ordem_cita_milimetro_nem_altura() -> None:
    """O GUIA é raciocínio, e ela já disse que não sabe o que isso quer dizer."""
    proibidas = ("mm", "milímetro", "centímetro", "altura da antena", "visada")
    for ordem in ordens.catalogo(leitura()):
        texto = " ".join(
            [ordem.acao] + [linha.texto for linha in ordem.linhas]
        ).lower()
        for palavra in proibidas:
            assert palavra not in texto


# ---------------------------------------------------------------------------
# A ausência tem duas palavras, e elas não colapsam.
# ---------------------------------------------------------------------------


def test_nao_medi_e_nao_declarado_sao_frases_diferentes() -> None:
    """F7: "olhei e não sei" não é "só você sabe, e você não me disse"."""
    assert ordens.NAO_MEDI != ordens.NAO_DECLARADO
    assert ordens.NAO_MEDI not in ordens.NAO_DECLARADO
    assert ordens.NAO_DECLARADO not in ordens.NAO_MEDI


def test_sem_desenho_a_acao_diz_o_que_falta_para_apontar() -> None:
    """Sem mapa a ordem MANDA, e diz exatamente o que falta para ela apontar."""
    ordem = ordens.radio_largo_no_mesmo_hub(leitura())
    assert ordem is not None
    assert ordens.NAO_DECLARADO in ordem.acao
    assert "há 4 livres" in ordem.acao


def test_com_desenho_a_acao_aponta_o_numero_dela() -> None:
    """Declarado o mapa, a ordem troca a contagem pelo número que ela escreveu."""
    ordem = ordens.radio_largo_no_mesmo_hub(
        leitura(entradas_livres_declaradas=("4",))
    )
    assert ordem is not None
    assert ordem.destino == "4"
    assert ordem.acao.endswith("para a entrada 4")
    assert ordens.NAO_DECLARADO not in ordem.acao


def test_a_terceira_linha_existe_sempre() -> None:
    """`D-LINHA-DO-GANHO-NAO-MEDIDO`: ela nunca mora só no tooltip."""
    for ordem in ordens.catalogo(leitura()):
        assert ordem.ganho_esperado.texto.strip()
        assert len(ordem.linhas) == 3

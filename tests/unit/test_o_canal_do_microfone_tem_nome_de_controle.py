"""O canal de captura tem o nome do CONTROLE, e não o do transporte.

ONDA5-MIC-VIRTUAL-01. A decisão é dela, 05/09/2026:

    *"se o Mic do dualsense passa a ser lido a parte via Mic virtual. Usaríamos
    essa feature do controle mesmo no Xbox. Mesmo problema BT."*

O DEFEITO QUE ESTA RÉGUA GUARDA é de NOME: hoje o microfone do mesmo controle se
chama ``hefesto_dualsense_bt_<hex6>`` no rádio e um nó ALSA com desempate
posicional (``-00``, ``-00.2``) no cabo. Troque o transporte e o microfone muda
de nome; um app que fixou o device perde a fonte.

A MORDIDA, e ela é a do enunciado da sprint: apague o sufixo do nome (deixe
``hefesto_mic``) e ponha DOIS controles. `test_dois_controles_nao_dividem_o_nome`
reprova, porque os dois nós disputariam um nome só — e o segundo sobrescreveria
o primeiro em silêncio, que é pior que não ter canal.

NADA AQUI TOCA O PIPEWIRE DA MÁQUINA. O mecanismo entra por `fabrica`, que é o
parâmetro que existe para isto: a régua troca o `SourceVirtualPipeWire` por um
dublê e mede o CICLO DE VIDA, que é o que este módulo possui. Uma régua que
carregasse `module-pipe-source` de verdade mexeria no áudio dela.
"""

from __future__ import annotations

from typing import ClassVar

import pytest

from hefesto_dualsense4unix.integrations import canal_do_microfone as canal
from hefesto_dualsense4unix.integrations.dualsense_bt_audio import (
    PRIORIDADE_SESSAO_DA_PONTE,
)
from hefesto_dualsense4unix.integrations.fontes_de_captura import (
    PREFIXO_SOURCE_PONTE_BT,
    sufixo_da_ponte_bt,
)
from hefesto_dualsense4unix.integrations.quem_ouve_o_microfone import (
    PREFIXO_PROPRIEDADE_HEFESTO,
)

P1 = "aa:bb:cc:00:00:01"
P2 = "aa:bb:cc:00:00:02"


class SourceDeMentira:
    """O mecanismo, sem PipeWire. Conta o que foi pedido e o que foi desfeito."""

    vivas: ClassVar[list[SourceDeMentira]] = []

    def __init__(self, *, nome: str, descricao: str, **_: object) -> None:
        self.nome = nome
        self.descricao = descricao
        self.iniciou = 0
        self.parou = 0
        SourceDeMentira.vivas.append(self)

    def iniciar(self) -> bool:
        self.iniciou += 1
        return True

    def parar(self) -> None:
        self.parou += 1


class SourceQueRecusa(SourceDeMentira):
    """O mecanismo que não sobe — e o contrato diz que nada fica pela metade."""

    def iniciar(self) -> bool:
        self.iniciou += 1
        return False


@pytest.fixture(autouse=True)
def _mesa_limpa():
    SourceDeMentira.vivas = []
    for uniq in list(canal.de_pe()):
        canal.fechar(uniq)
    yield
    for uniq in list(canal.de_pe()):
        canal.fechar(uniq)


# ---------------------------------------------------------------------------
# 1. O NOME
# ---------------------------------------------------------------------------
def test_o_nome_carrega_a_identidade_do_controle() -> None:
    assert canal.nome_do_canal(P1) == "hefesto_mic_000001"
    assert canal.nome_do_canal(P2) == "hefesto_mic_000002"


def test_dois_controles_nao_dividem_o_nome() -> None:
    """A régua da mordida do enunciado: sem sufixo, os dois nós colidem."""
    assert canal.nome_do_canal(P1) != canal.nome_do_canal(P2), (
        "dois controles na mesa geraram o MESMO nome de source — o segundo "
        "sobrescreveria o primeiro em silêncio")


def test_o_separador_do_endereco_nao_muda_o_nome() -> None:
    """O mesmo aparelho, escrito de três jeitos, é o mesmo canal."""
    nomes = {canal.nome_do_canal(f) for f in (P1, P1.upper(), P1.replace(":", "-"))}
    assert len(nomes) == 1, nomes


def test_sem_endereco_nao_ha_canal() -> None:
    """Sem identidade não se batiza um canal — e hex POR ACASO não vale.

    Medido em 05/09/2026: `so_hex("sem-identidade")` devolve `"emdedade"`,
    porque `e`, `d` e `a` são dígitos hex. Sem esta régua o canal nasceria
    `hefesto_mic_dedade` sobre uma string que não é endereço nenhum.
    """
    for lixo in ("sem-identidade", "", "abc", "DualSense Wireless Controller"):
        assert canal.nome_do_canal(lixo) == "", lixo


def test_o_caminho_de_volta_reconhece_so_o_nosso() -> None:
    """De que controle é este nó — e o prefixo do rádio NÃO é este."""
    assert canal.sufixo_do_canal(canal.nome_do_canal(P1)) == "000001"
    assert canal.sufixo_do_canal(f"{PREFIXO_SOURCE_PONTE_BT}000001") == ""
    assert canal.sufixo_do_canal("alsa_input.usb-Sony_DualSense-00") == ""


def test_os_dois_prefixos_convivem_e_nao_se_confundem() -> None:
    """Enquanto o rádio publicar o nome velho, os dois leitores discriminam.

    Dois prefixos vivos é o preço declarado da transição, e a MIC-VIRTUAL-02 é
    quem o paga. O que não pode é um leitor achar que o nó do outro é seu.
    """
    do_radio = f"{PREFIXO_SOURCE_PONTE_BT}000001"
    do_canal = canal.nome_do_canal(P1)
    assert sufixo_da_ponte_bt(do_radio) == "000001"
    assert sufixo_da_ponte_bt(do_canal) == ""
    assert canal.sufixo_do_canal(do_canal) == "000001"
    assert canal.sufixo_do_canal(do_radio) == ""


# ---------------------------------------------------------------------------
# 2. O QUE NÃO SE DIGITA DUAS VEZES
# ---------------------------------------------------------------------------
def test_a_prioridade_vem_do_dono_e_nao_de_um_literal() -> None:
    """A faixa do cabo, com a medição de 03/09 na máquina dela por trás.

    Um literal aqui repetiria, na íntegra, o defeito que
    `PRIORIDADE_SESSAO_DA_PONTE` registra: um número catorze dias atrás da
    doutrina que ele espelhava.
    """
    assert canal.prioridade() == PRIORIDADE_SESSAO_DA_PONTE


def test_as_propriedades_ficam_no_espaco_de_nome_do_hefesto() -> None:
    """Não se combina nome com a peça que reconhece — reconhece-se o PREFIXO.

    `quem_ouve_o_microfone` conta ouvintes e **não pode contar o Hefesto**: se
    contar, a luz vermelha do microfone dela acende sozinha e a peça inteira
    mente. A junta entre os dois é o espaço de nome, lido do dono.
    """
    props = canal.propriedades_do_canal(P1)
    assert props, "o nó subiria sem marca nenhuma do Hefesto"
    assert all(k.startswith(PREFIXO_PROPRIEDADE_HEFESTO) for k in props), props
    assert props[f"{PREFIXO_PROPRIEDADE_HEFESTO}uniq"] == P1


# ---------------------------------------------------------------------------
# 3. O CICLO DE VIDA — o que este módulo POSSUI
# ---------------------------------------------------------------------------
def test_pedir_duas_vezes_sobe_um_no_so() -> None:
    """Duas abas, dois cliques: é o caminho normal, não o excepcional.

    Dois `module-pipe-source` com o mesmo `source_name` publicariam dois nós
    disputando um nome só.
    """
    a = canal.abrir(P1, "Microfone do P1", fabrica=SourceDeMentira)
    b = canal.abrir(P1, "Microfone do P1", fabrica=SourceDeMentira)
    assert a is not None and a is b
    assert len(SourceDeMentira.vivas) == 1, SourceDeMentira.vivas
    assert canal.de_pe() == {P1: "hefesto_mic_000001"}


def test_dois_controles_sobem_dois_nos() -> None:
    canal.abrir(P1, "P1", fabrica=SourceDeMentira)
    canal.abrir(P2, "P2", fabrica=SourceDeMentira)
    assert canal.de_pe() == {
        P1: "hefesto_mic_000001",
        P2: "hefesto_mic_000002",
    }


def test_fechar_derruba_so_o_pedido() -> None:
    canal.abrir(P1, "P1", fabrica=SourceDeMentira)
    canal.abrir(P2, "P2", fabrica=SourceDeMentira)
    assert canal.fechar(P1) is True
    assert canal.fechar(P1) is False, "fechar o que não está de pé disse que fechou"
    assert list(canal.de_pe()) == [P2]


def test_o_que_nao_subiu_nao_fica_pela_metade() -> None:
    """`None` e a tabela vazia — o contrato do `iniciar` que devolve False."""
    assert canal.abrir(P1, "P1", fabrica=SourceQueRecusa) is None
    assert canal.de_pe() == {}


def test_o_gesto_dela_nunca_vira_traceback() -> None:
    """O caminho até aqui é o botão do microfone. Uma recusa, nunca um erro."""

    class SourceQueExplode(SourceDeMentira):
        def iniciar(self) -> bool:
            raise RuntimeError("o pactl não estava lá")

    assert canal.abrir(P1, "P1", fabrica=SourceQueExplode) is None
    assert canal.de_pe() == {}


def test_sem_identidade_nao_sobe_no_nenhum() -> None:
    assert canal.abrir("sem-identidade", "?", fabrica=SourceDeMentira) is None
    assert SourceDeMentira.vivas == [], "subiu um nó sem nome de controle"

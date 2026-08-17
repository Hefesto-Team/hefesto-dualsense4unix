"""O interruptor da ponte de mic por BT — o portão que o mantém FORA da janela.

Este arquivo mudou de lado em **16/08/2026**. Ele nasceu em 07/08 cobrando que
o interruptor "Pelo rádio" existisse; hoje ele cobra que **não exista**, e a
troca não é capricho de rótulo — é o que duas medições da bancada mandaram.

## Por que o interruptor saiu

**1. É o desenho dela.** Olhando a aba Status: *"esse botão de silenciar some.
dá espaço a um slicer de microfone pra definir o volume do microfone real
(independente de saber se tá via bt ou via cabo), o app deve ser inteligente
pra saber qual caminho usar. Ali onde temos o botão por rádio trocamos por
Silenciar"*. O interruptor punha na tela uma decisão TÉCNICA que é do
aplicativo: no rádio o áudio vem em Opus dentro dos reports HID, no cabo vem
por placa de som USB. É o mesmo microfone, e ela não deveria precisar saber
disso para falar.

**2. A ponte não é segura** — medido DUAS vezes em 16/08. Com ela de pé, o
botão PS aparece pressionado em pulsos de ~17 ms (`held_ms=17.6 / 17.5 / 17.9`,
um ciclo de leitura a 60 Hz) e o daemon tenta abrir a Steam em laço. A segunda
rodada já tinha o filtro do bit de áudio no lugar e travou igual. Ela descreveu
como *"o teclado e o mouse com vida própria"* e desligou o controle, com medo.
Log e sequência inteira em
`docs/process/estudos/2026-08-16-O-PS-PRESO-a-ponte-do-mic-e-o-laco-que-abria-a-steam-sozinho.md`.

**Um interruptor que oferece um gesto perigoso é pior que interruptor nenhum.**

## O que este arquivo cobra hoje, e por que vale travar

1. **A janela não oferece a ponte.** É o invariante, e ele é de SEGURANÇA: uma
   sessão futura que "reative o widget do mic BT" sem fechar a arbitragem do
   hidraw refaz o susto dela. Este teste é o que a faz parar e ler o estudo.
2. **A capacidade continua inteira.** O que saiu foi o BOTÃO, não a ponte: o
   módulo, o subsystem, o `mic bt` da linha de comando e o gate
   `HEFESTO_DUALSENSE4UNIX_BT_MIC` seguem de pé para quem quiser subi-la à mão.
   Sem esta metade, "some o interruptor" viraria licença para apagar a ponte —
   e ela FUNCIONA: publicou o source no PipeWire em 16/08.
3. **O caminho de volta está escrito.** Cura removida sem a condição de retorno
   anotada vira conhecimento perdido, que é a dívida mais cara desta casa.

O irmão de GTK real (`test_o_interruptor_do_mic_no_card.py`) faz a mesma
pergunta à árvore de widgets montada — porque um módulo pode não exportar nada
e a janela ainda assim pendurar um `Gtk.Switch` no bloco do microfone.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from hefesto_dualsense4unix.app.widgets import controller_card as cc

#: O estudo que julgou a ponte. Se ele sumir, o motivo da remoção some junto —
#: e a próxima sessão religa o interruptor achando que foi frescura.
ESTUDO = Path("docs/process/estudos") / (
    "2026-08-16-O-PS-PRESO-a-ponte-do-mic-e-o-laco-que-abria-a-steam-sozinho.md"
)

#: Tudo que o interruptor levava consigo. A lista é nominal de propósito: um
#: `hasattr` genérico não diria QUAL peça voltou.
PECAS_DO_INTERRUPTOR = (
    "TEXTO_MIC_BT_ROTULO",
    "DICA_MIC_BT_LIGAR",
    "DICA_MIC_BT_DESLIGAR",
    "DICA_MIC_BT_NO_CABO",
    "DICA_MIC_BT_IMPEDIDA",
    "AcaoPonteBt",
    "acao_ponte_bt",
    "ligar_ponte_bt",
    "desligar_ponte_bt",
)


def _raiz() -> Path:
    return Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# O invariante: a janela não oferece a ponte
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("peca", PECAS_DO_INTERRUPTOR)
def test_o_card_nao_carrega_mais_nenhuma_peca_do_interruptor(peca: str) -> None:
    """A MORDIDA: devolva qualquer uma delas ao módulo e este teste reprova.

    Elas não são cinco constantes e quatro funções soltas: juntas são a única
    forma de a JANELA subir a ponte. Enquanto o dono do hidraw não for
    arbitrado, o processo da janela não pode ter esse gesto ao alcance de um
    clique — foi assim que o PS ficou preso, duas vezes.
    """
    assert not hasattr(cc, peca), (
        f"`{peca}` voltou ao card: a ponte de mic por BT prende o botão PS em "
        f"pulsos de ~17 ms e o daemon abre a Steam em laço. Antes de religar "
        f"qualquer parte disto, leia {ESTUDO} e feche a arbitragem do hidraw."
    )


def test_o_card_nao_fala_com_o_modulo_da_ponte() -> None:
    """Nem por importação indireta: o gesto tem de estar fora do processo.

    Sem esta, alguém religa a ponte chamando `dualsense_bt_audio` direto de um
    handler novo, sem recriar nenhum dos nomes de cima, e a suíte fica verde
    com o defeito de volta.
    """
    fonte = inspect.getsource(cc)
    linhas_de_codigo = [
        linha
        for linha in fonte.splitlines()
        if "dualsense_bt_audio" in linha and not linha.lstrip().startswith("#")
    ]

    assert linhas_de_codigo == [], (
        "o card voltou a falar com o módulo da ponte: "
        f"{linhas_de_codigo}. A ponte é capacidade de linha de comando e de "
        "daemon enquanto a posse do hidraw não for arbitrada."
    )


def test_a_tela_nao_diz_mais_pelo_radio() -> None:
    """O rótulo era o convite; some o convite, some o gesto perigoso.

    E é também o desenho dela: a tela não pergunta por onde o som anda, porque
    a escolha do caminho é do aplicativo.
    """
    codigo = [
        linha
        for linha in inspect.getsource(cc).splitlines()
        if "Pelo rádio" in linha and not linha.lstrip().startswith("#")
    ]

    assert codigo == [], (
        f"a tela voltou a oferecer a ponte pelo rótulo 'Pelo rádio': {codigo}"
    )


# ---------------------------------------------------------------------------
# A outra metade: a CAPACIDADE não saiu junto
# ---------------------------------------------------------------------------


def test_a_ponte_continua_existindo_inteira() -> None:
    """Saiu o botão, não a ponte — ela publicou o source no PipeWire em 16/08.

    A MORDIDA desta metade: apague `integrations/dualsense_bt_audio.py` (ou o
    subsystem) achando que "removemos o mic BT" e este teste reprova. É a
    diferença entre tirar um gesto perigoso da janela e jogar fora semanas de
    trabalho que funcionam.
    """
    from hefesto_dualsense4unix.integrations import dualsense_bt_audio as bt

    assert hasattr(bt, "GerenciadorMicBluetooth")
    assert hasattr(bt, "nos_dualsense_bluetooth")
    assert hasattr(bt, "diagnosticar")

    from hefesto_dualsense4unix.daemon.subsystems import bt_mic

    assert hasattr(bt_mic, "BtMicSubsystem")


def test_o_gate_de_ambiente_continua_sendo_o_caminho_a_mao() -> None:
    """`HEFESTO_DUALSENSE4UNIX_BT_MIC` é como a ponte sobe hoje, e só assim.

    Ele não era o caminho bonito — o interruptor existia justamente para poupar
    o terminal. Mas com a ponte julgada insegura, um gesto que exige uma
    variável de ambiente é exatamente a fricção certa: ninguém o dá sem querer.
    """
    fonte = (
        _raiz() / "src/hefesto_dualsense4unix/daemon/subsystems/bt_mic.py"
    ).read_text(encoding="utf-8")

    assert "HEFESTO_DUALSENSE4UNIX_BT_MIC" in fonte, (
        "o gate sumiu: sem ele não há NENHUMA forma de subir a ponte, e aí a "
        "remoção do interruptor virou remoção da capacidade"
    )


# ---------------------------------------------------------------------------
# O caminho de volta, escrito
# ---------------------------------------------------------------------------


def test_o_estudo_que_derrubou_o_interruptor_esta_no_lugar() -> None:
    """Sem o estudo, sobra "alguém tirou" — e a próxima sessão devolve."""
    caminho = _raiz() / ESTUDO

    assert caminho.is_file(), f"o estudo sumiu: {ESTUDO}"
    texto = caminho.read_text(encoding="utf-8")
    assert "held_ms=17.6" in texto, "o número que derrubou a hipótese do áudio saiu"
    assert "Arbitrar o hidraw" in texto, "a condição de volta saiu do estudo"


def test_o_card_diz_no_codigo_como_o_interruptor_volta() -> None:
    """O comentário no lugar da remoção é o mapa, e ele tem de ter endereço.

    A lição do próprio episódio: *"a casa tinha o aviso escrito, no comentário
    do widget, e eu subi a ponte assim mesmo"*. Um aviso sem a condição
    objetiva de retorno é só lamento — este teste exige as duas coisas, o
    porquê e o quando.
    """
    fonte = inspect.getsource(cc)

    assert "O-PS-PRESO" in fonte, "o comentário não aponta para o estudo"
    assert "hidraw" in fonte, "o comentário não diz qual é a condição de volta"
    assert "0x32" in fonte, "o comentário não nomeia a disputa do contador"

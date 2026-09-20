"""A BANCADA DO RÁDIO — e a guarda que separa «sem dano» de «sem alvo».

Encomenda dela, 19/09/2026: *"Prepara todos os testes (…) pra vc ir conduzindo
tudo em software e eu ir executando as etapas do mundo físico"*.

A ARMADILHA QUE ESTAS RÉGUAS GUARDAM é a que esta casa já pagou: **zero com o
alvo fora da mesa não é zero**. Sem controle conectado no adaptador, a
varredura não tem o que atrapalhar — e a medição devolve «sem dano», que se lê
como «a busca não atrapalha». Quem ler o número arquiva o assunto.

Medido em 19/09, com a mesa dela sem controle no rádio: `dano hci0` devolveu
queda de -3% (a taxa SUBIU) e teria fechado a pergunta com um falso negativo.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
CONDUTOR = RAIZ / "scripts" / "bancada_do_radio.py"


def _rodar(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CONDUTOR), *args],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(RAIZ),
    )


def test_o_condutor_existe_e_tem_ajuda() -> None:
    assert CONDUTOR.is_file()
    fim = _rodar("--help")
    assert fim.returncode == 0
    assert "bancada_do_radio" in fim.stdout


def test_a_etapa_desconhecida_recusa_em_vez_de_calar() -> None:
    fim = _rodar("etapa-que-nao-existe")
    assert fim.returncode != 0, "aceitou etapa inexistente — silêncio lê-se como sucesso"


def test_o_dano_recusa_adaptador_inexistente() -> None:
    # Dentro da suíte a trava do rádio age ANTES desta recusa, e está certo
    # assim: a guarda mais forte primeiro. O que este teste garante é que
    # `dano` com adaptador inventado NUNCA devolve sucesso.
    fim = _rodar("dano", "hci99", "1")
    assert fim.returncode != 0, "aceitou medir num adaptador que não existe"
    assert "RECUSADO" in fim.stdout or "não existe" in fim.stdout


def test_a_suite_nao_toca_o_radio_dela() -> None:
    """RADIO-DELA-01 — e este teste nasceu de um vermelho de verdade.

    A primeira régua escrita aqui chamava `dano` sem trava. O canário do
    `casa-sabe` acusou na mesma corrida: a varredura subiu, o daemon reagiu e
    regravou `~/.config/hefesto-dualsense4unix/controllers.json` na máquina
    dela, com ela usando a máquina.

    É a TELA-DELA-01 com outro aparelho: *a suíte não toca o que é dela.*
    """
    fim = _rodar("dano", "hci0", "1")
    assert fim.returncode == 7, (
        f"a etapa que LIGA a varredura não recusou dentro da suíte (rc={fim.returncode}). "
        "O rádio dela não é bancada de teste."
    )
    assert "RECUSADO" in fim.stdout
    assert "HEFESTO_BANCADA_PODE_TOCAR_O_RADIO" in fim.stdout, (
        "recusou sem declarar o escape — guarda sem porta vira contorno"
    )


def test_as_guardas_vem_antes_de_ligar_a_varredura() -> None:
    """A ORDEM é a cura, e ela se lê no arquivo — não se mede ligando o rádio.

    Três guardas têm de estar ANTES da primeira linha que liga a busca:
    a trava da suíte, o adaptador inexistente e a mesa vazia. Uma guarda que
    corre depois de o rádio subir não guarda nada.
    """
    corpo = CONDUTOR.read_text(encoding="utf-8")
    trecho = corpo.split("def etapa_dano", 1)[-1].split("\ndef ", 1)[0]
    # A LINHA QUE LIGA, e não a palavra: o docstring desta etapa CITA o
    # `bluetoothctl` para explicar por que o `busctl` não serve, e medir
    # contra a citação punha a prosa antes das guardas. É a mesma família do
    # comentário que virou a primeira ocorrência do padrão que descrevia.
    liga = trecho.index("subprocess.Popen(")
    for agulha, porque in (
        ("PYTEST_CURRENT_TEST", "a trava da suíte"),
        ("não existe. Há:", "a recusa de adaptador inexistente"),
        ("NENHUM CONTROLE CONECTADO", "a guarda da mesa vazia"),
    ):
        onde = trecho.index(agulha)
        assert onde < liga, (
            f"{porque} corre DEPOIS de a varredura subir — ela não guarda nada."
        )


def test_a_mesa_vazia_recusa_com_codigo_proprio() -> None:
    """Zero com o alvo fora da mesa não é zero.

    A guarda devolve um código PRÓPRIO (4), e não 0: quem encadeia etapas
    precisa distinguir «medi e não houve dano» de «não tinha o que medir».
    Esta é a diferença que faz «sem dano» virar «a busca não atrapalha».
    """
    corpo = CONDUTOR.read_text(encoding="utf-8")
    trecho = corpo.split("def etapa_dano", 1)[-1].split("\ndef ", 1)[0]
    # A guarda é a PRIMEIRA das duas ocorrências de `if not no_alvo` — a
    # segunda é o ramo da medição cruzada, que vem depois e é outra coisa.
    bloco = trecho.split("if not no_alvo and not cruzado:", 1)
    assert len(bloco) == 2, "a guarda da mesa vazia sumiu"
    corpo_da_guarda = bloco[1].split("if not no_alvo:", 1)[0]
    assert "return 4" in corpo_da_guarda, (
        "a guarda da mesa vazia não devolve código próprio — quem encadeia "
        "etapas não distingue «sem dano» de «sem alvo»"
    )
    assert "Conecte um DualSense" in corpo_da_guarda, "recusa sem dizer o gesto"


def test_o_limpar_recusa_ambiguidade_e_ausencia() -> None:
    fim = _rodar("limpar", "hci0", "AA:BB:CC:00:00:99")
    assert fim.returncode != 0, (
        "aceitou apagar um bond que não existe — apagar bond é destruir "
        "pareamento, e o que não foi encontrado não se apaga em silêncio"
    )


def test_o_condutor_nunca_deixa_o_radio_varrendo() -> None:
    # A busca do BlueZ morre com o cliente que a pediu — é disso que o `dano`
    # depende para não deixar o rádio dela ligado se o processo cair. O
    # `finally` é o que garante isso mesmo com exceção no meio.
    corpo = CONDUTOR.read_text(encoding="utf-8")
    trecho = corpo.split("def etapa_dano", 1)[-1].split("\ndef ", 1)[0]
    assert "finally:" in trecho, (
        "a etapa que LIGA a varredura não tem `finally` — uma exceção no meio "
        "deixaria o rádio dela varrendo."
    )
    assert "scan off" in trecho and "terminate()" in trecho, (
        "o `finally` não desliga a busca nem mata o cliente"
    )


def test_o_mac_real_nao_vaza_na_tabela() -> None:
    # A saída vai para o terminal dela, e daí para a conversa. A tabela mostra
    # o MAC MASCARADO; só o comando que ela vai executar traz o real.
    corpo = CONDUTOR.read_text(encoding="utf-8")
    assert "def _mascarar" in corpo
    bonds = corpo.split("def etapa_bonds", 1)[-1].split("\ndef ", 1)[0]
    listagem = bonds.split("for mac, hcis in sorted(onde.items()):", 1)[-1]
    listagem = listagem.split("if not dobrados", 1)[0]
    assert "_mascarar(mac)" in listagem, (
        "a tabela de bonds imprime o MAC cru — a máscara da casa zera os "
        "octetos 4 e 5 justamente para esta saída poder ser colada."
    )

"""GATILHO-DA-COR-01 — o debounce conta o FIM DA SEQUÊNCIA, não os controles.

Este arquivo existe por causa de um ensaio que FALHOU, e o modo como ele falhou
é o desenho inteiro.

12/08/2026, mesa dela, três DualSense no rádio, Steam viva. A primeira versão do
gatilho esperava 1,5 s depois de CADA conexão e escrevia só naquele controle:
`.0034` às 23:55:53, `.0035` às 23:55:54, `.0036` às 23:55:56. Resultado, literal
dela: *"só o player 4 que é o controle azul o resto tá no padrão da steam"*.

A leitura (ensaio `gatilho-1500ms-por-controle` em `docs/data/ensaios.csv`): a
rajada da Steam **não é por controle, é por evento** — cada conexão nova faz ela
repintar todos. Escrever 1,5 s depois do controle A não adianta se o B conecta
depois. O `.0036` sobreviveu apenas porque ninguém conectou depois dele.

A correção (ensaio `gatilho-escrever-no-silencio`, aceite dela: *"perfeito"*):
armar a cada conexão, disparar quando o rádio SOSSEGA, escrever em todos.

O que estes testes travam, e cada um corresponde a uma linha de ensaio:
- uma conexão sozinha dispara depois do atraso, e não antes;
- **a segunda conexão RE-ADIA o disparo** — é a cura que a versão de 23:55 não
  tinha, e é o teste que reprova se alguém a arrancar;
- a sequência dispara UMA vez, nunca uma por controle.

A segunda metade do arquivo cobre o REGISTRO, que é o mecanismo virando
reusável: decisão dela de 12/08, com três defeitos da mesma família já medidos
(rumble, lightbar e o `IGNORE` do co-op).
"""
from __future__ import annotations

import pytest

from hefesto_dualsense4unix.core.gatilho_fim_de_sequencia import (
    GatilhoDeFimDeSequencia,
    RegistroDeGatilhos,
)
from hefesto_dualsense4unix.core.lightbar_gatilho import (
    ATRASO_APOS_A_ULTIMA_CONEXAO_S,
    NOME_DO_GATILHO,
)


def _gatilho(atraso_s: float) -> GatilhoDeFimDeSequencia:
    """O mecanismo com uma ação inerte — aqui se mede o TEMPO, não o conteúdo."""
    return GatilhoDeFimDeSequencia("teste", lambda: None, atraso_s=atraso_s)


def test_sem_conexao_nenhuma_nunca_dispara() -> None:
    """Gatilho desarmado é silêncio — nada de repintar por timer.

    Repintar sem motivo seria a `defend_display` do flash azul que esta casa já
    baniu uma vez: escrita periódica em cima de quem tem o claim intacto.
    """
    gatilho = _gatilho(1.5)

    assert gatilho.armado is False
    assert gatilho.consumir_se_a_sequencia_acabou(0.0) == 0
    assert gatilho.consumir_se_a_sequencia_acabou(1000.0) == 0
    assert gatilho.falta_para_disparar(0.0) is None


def test_uma_conexao_dispara_depois_do_atraso_e_nao_antes() -> None:
    """A janela medida: dentro dela a Steam ainda está pintando; depois, silêncio."""
    gatilho = _gatilho(1.5)
    gatilho.armar(100.0)

    assert gatilho.armado is True
    # 1,49 s ainda é a rajada — escrever aqui é chegar junto e perder.
    assert gatilho.consumir_se_a_sequencia_acabou(101.49) == 0
    assert gatilho.consumir_se_a_sequencia_acabou(101.5) == 1
    # Consumiu: a mesma sequência não dispara duas vezes.
    assert gatilho.armado is False
    assert gatilho.consumir_se_a_sequencia_acabou(200.0) == 0


def test_a_segunda_conexao_readia_o_disparo() -> None:
    """A CURA. É esta linha que a versão de 1,5 s por controle não tinha.

    Cronograma do ensaio de 23:55, com os números dele: conexões em t=0, t=1 e
    t=3. Um debounce por CONTROLE teria disparado em t=1,5 (pelo primeiro) e
    pego a rajada que a conexão de t=3 ainda ia trazer. Um debounce por FIM DE
    SEQUÊNCIA só dispara em t=4,5 — depois da última.
    """
    gatilho = _gatilho(1.5)
    gatilho.armar(0.0)
    gatilho.armar(1.0)

    # t=1,5: já passou 1,5 s da PRIMEIRA conexão. Não pode disparar — foi
    # exatamente aqui que os dois controles se perderam na mesa dela.
    assert gatilho.consumir_se_a_sequencia_acabou(1.5) == 0
    assert gatilho.falta_para_disparar(1.5) == 1.0

    gatilho.armar(3.0)
    assert gatilho.consumir_se_a_sequencia_acabou(2.6) == 0
    assert gatilho.consumir_se_a_sequencia_acabou(4.4) == 0
    # t=4,5 = 1,5 s depois da ÚLTIMA. Agora sim, e de uma vez só.
    assert gatilho.consumir_se_a_sequencia_acabou(4.5) == 3


def test_a_sequencia_dispara_uma_vez_so() -> None:
    """Uma escrita por sequência — não uma por controle.

    É o requisito de barateza e é também o que a bancada mostrou bastar: UMA
    escrita em cada um dos três pintou os três.
    """
    gatilho = _gatilho(1.5)
    for instante in (0.0, 0.5, 1.0, 1.2):
        gatilho.armar(instante)

    assert gatilho.eventos_armados == 4
    assert gatilho.consumir_se_a_sequencia_acabou(2.7) == 4
    assert gatilho.consumir_se_a_sequencia_acabou(2.7) == 0
    assert gatilho.consumir_se_a_sequencia_acabou(99.0) == 0


def test_desarmar_esquece_a_sequencia_sem_disparar() -> None:
    """Mesa vazia (todo mundo desconectou) não deixa disparo pendurado."""
    gatilho = _gatilho(1.5)
    gatilho.armar(0.0)
    gatilho.desarmar()

    assert gatilho.armado is False
    assert gatilho.consumir_se_a_sequencia_acabou(10.0) == 0


def test_o_atraso_padrao_e_o_numero_medido() -> None:
    """1,5 s é dela e é medido — não é constante de gosto.

    *"muito tempo. desce pra um segundo e meio"* (12/08). Se alguém mudar este
    número sem um ensaio novo, este teste é onde a conversa começa.
    """
    assert ATRASO_APOS_A_ULTIMA_CONEXAO_S == 1.5


# ---------------------------------------------------------------------------
# O REGISTRO — a porta pela qual o segundo e o terceiro usuários entram.
#
# Decisão dela, 12/08: *"reafirmar o que o produto quer no fim da sequência,
# seja cor, número ou o IGNORE do ambiente"*. Já são três os defeitos da mesma
# família (rumble curado, lightbar aqui, `IGNORE` do co-op medido no ensaio
# `coop-ignore-avaliado-cedo`), e o mecanismo tem de servir aos três sem cópia.
# ---------------------------------------------------------------------------


def test_o_registro_da_um_relogio_para_varios_gatilhos() -> None:
    """Dois nomes, duas sequências independentes, um só relógio.

    É o requisito que o caso do co-op traz: o número dele é outro (a subida dos
    quatro vpads levou ONZE segundos), e ele não pode nem herdar o 1,5 s da
    lightbar nem criar um laço próprio.
    """
    feitos: list[str] = []
    registro = RegistroDeGatilhos()
    registro.registrar("cor", lambda: feitos.append("cor"), atraso_s=1.5)
    registro.registrar("ignore", lambda: feitos.append("ignore"), atraso_s=11.0)

    registro.armar("cor", 0.0)
    registro.armar("ignore", 0.0)

    # t=2: só a cor sossegou.
    for gatilho, _eventos in registro.devidos(2.0):
        gatilho.tarefa()
    assert feitos == ["cor"]

    # t=12: o do co-op também.
    for gatilho, _eventos in registro.devidos(12.0):
        gatilho.tarefa()
    assert feitos == ["cor", "ignore"]


def test_armar_nome_nao_registrado_nao_levanta() -> None:
    """Um subsistema que arma antes de registrar não pode derrubar quem o chamou."""
    registro = RegistroDeGatilhos()

    assert registro.armar("ninguem", 0.0) is False
    assert registro.devidos(99.0) == []


def test_registrar_de_novo_nao_perde_a_sequencia_armada() -> None:
    """Tolerante a ordem: registrar tarde é caso normal, não erro.

    Sem isto, a ordem de fiação dos subsistemas viraria regra escondida — e uma
    sequência armada no meio de um hotplug se perderia calada.
    """
    feitos: list[str] = []
    registro = RegistroDeGatilhos()
    registro.registrar("cor", lambda: feitos.append("velha"), atraso_s=1.0)
    registro.armar("cor", 0.0)
    registro.registrar("cor", lambda: feitos.append("nova"))

    prontos = registro.devidos(2.0)
    assert len(prontos) == 1
    prontos[0][0].tarefa()
    assert feitos == ["nova"], "re-registrar perdeu a sequência ou a tarefa nova"


def test_gatilho_novo_sem_numero_medido_e_recusado() -> None:
    """O mecanismo não inventa o número de ninguém — ele é medido por quem chama."""
    registro = RegistroDeGatilhos()
    with pytest.raises(ValueError, match="atraso_s"):
        registro.registrar("sem_numero", lambda: None)


def test_o_nome_do_gatilho_da_lightbar_e_o_do_modulo_dela() -> None:
    """O nome viaja pelo módulo, não por string solta em cada chamador.

    Um nome digitado errado num armador não daria erro nenhum: daria silêncio
    naquele gatilho — a pior falha possível para uma cura.
    """
    assert NOME_DO_GATILHO == "lightbar"

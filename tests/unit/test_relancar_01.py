"""O diálogo só aparece quando a mudança de fato exige o jogo reabrir.

RELANCAR-01 (08/08/2026). O wrapper termina em `exec env "$@"`
(`assets/hefesto-launch.sh:320`): o jogo recebe as variáveis **uma vez**, na
abertura. Mudar depois não chega até ele, e mexer no grab/vpad ao vivo é pior —
MEDIDO em 08/08, isso deixou ela **sem controle nenhum no meio da partida**.

Ela recusou as duas saídas que evitavam o problema (recusar o gesto, ou fazê-lo
valer só depois) e propôs a que o resolve: *"se implementarmos e dermos um
restart… o tempo de reconexão seria um bom pagamento pra termos ele
funcionando"*. Se a mudança exige relançar, o produto **oferece** relançar.

A METADE QUE É FÁCIL ERRAR
==========================
A lista do que **NÃO** exige é entrega tanto quanto o diálogo. Se ele aparecer
quando ela troca a cor da luz, vira ruído, ela aprende a clicar sem ler — e aí o
diálogo que importa não é lido. A fronteira vem da medição dela de 06/08
(`CONTROLE-SONY-MEDIDO-01`, *A INVERSÃO*): dentro de um jogo, a **saída**
continua sendo do Hefesto; o que não muda ao vivo é a **entrada**.
"""

from __future__ import annotations

import pytest

from hefesto_dualsense4unix.app.actions import relancar as r


# --- quando perguntar ---------------------------------------------------------


@pytest.mark.parametrize("mudanca", sorted(r.EXIGEM_RELANCAR))
def test_com_jogo_aberto_as_mudancas_de_entrada_perguntam(mudanca: str) -> None:
    """ARRANQUE a mudança da lista e este teste REPROVA.

    Cada uma destas mexe em quem entrega os eventos ao jogo — pelo
    `compose_env` ou pela borda da exceção de Steam Input. Aplicar em silêncio é
    o que produziu o "Jogador 3" fantasma e a partida sem inputs.
    """
    assert r.precisa_perguntar(mudanca=mudanca, jogo_aberto=True) is True


@pytest.mark.parametrize("mudanca", sorted(r.MUDA_NA_HORA))
def test_o_que_muda_na_hora_nunca_pergunta(mudanca: str) -> None:
    """O contrapeso, e é o que impede o diálogo de virar ruído.

    Se algum destes passar a perguntar, ela aprende a clicar sem ler — e o
    diálogo que importa deixa de ser lido. É a forma mais fácil de estragar esta
    entrega enquanto ela parece mais completa.
    """
    assert r.precisa_perguntar(mudanca=mudanca, jogo_aberto=True) is False


@pytest.mark.parametrize("mudanca", sorted(r.EXIGEM_RELANCAR))
def test_sem_jogo_aberto_nunca_pergunta(mudanca: str) -> None:
    """Sem jogo, a mudança aplica direto — como sempre fez.

    O diálogo custa uma interrupção, e só se paga quando há um jogo para o qual
    a mudança não chegaria.
    """
    assert r.precisa_perguntar(mudanca=mudanca, jogo_aberto=False) is False


def test_mudanca_desconhecida_nao_interrompe() -> None:
    """Tela nova que esqueça de se registrar segue como antes, sem incomodar.

    A falha é para o lado de não interromper: uma tela que passasse a
    interromper a partida dela por engano é pior que uma que não pergunta. Quem
    acusa a ausência é o teste de cobertura abaixo, e é lá que deve doer.
    """
    assert r.precisa_perguntar(mudanca="algo_que_ninguem_escreveu", jogo_aberto=True) is False


def test_as_duas_listas_nao_se_cruzam() -> None:
    """Nenhuma mudança pode estar nas duas listas.

    Cruzamento aqui significa que alguém escreveu a mesma coisa em dois lugares
    com respostas opostas — e a lista que vence passa a ser acidente de leitura.
    """
    cruzamento = r.EXIGEM_RELANCAR & r.MUDA_NA_HORA
    assert not cruzamento, f"mudança em AMBAS as listas: {sorted(cruzamento)}"


# --- o que o diálogo diz ------------------------------------------------------


def test_o_corpo_diz_as_tres_coisas() -> None:
    """O corpo tem de dizer o que mudou, por que não chega, e o que muda na hora.

    A terceira é a que mais se perde num "enxugar o texto" — e sem ela ela
    conclui que precisa fechar o jogo para trocar a cor da luz, que é falso e
    contradiz a medição dela de 06/08.
    """
    corpo = r.corpo_do_dialogo(
        mudanca="mascara", valor="Xbox 360", jogo="Sackboy: A Big Adventure"
    )
    assert "O jogo vê o controle como: Xbox 360" in corpo, "não diz o que ela mudou"
    assert "não chega até ele" in corpo, "não diz por que não alcança o jogo aberto"
    assert "sem controle nenhum" in corpo, (
        "sumiu o custo MEDIDO de aplicar ao vivo — é a frase que impede alguém de "
        "'melhorar' isto para aplicar na marra."
    )
    assert "continuam mudando na hora" in corpo, (
        "sumiu a metade da INVERSÃO: cor, gatilhos e vibração seguem valendo com "
        "o jogo aberto."
    )
    assert "Sackboy: A Big Adventure" in corpo, "não nomeia o jogo que vai fechar"


def test_o_corpo_avisa_da_perda_do_que_nao_foi_salvo() -> None:
    """Fechar o jogo tem preço, e ele vai escrito antes de ela escolher."""
    corpo = r.corpo_do_dialogo(mudanca="modo", valor="Jogar pelo Hefesto", jogo=None)
    assert "o que você não salvou se perde" in corpo


@pytest.mark.parametrize(
    ("mudanca", "valor", "esperado"),
    [
        ("modo", "Jogar pelo Hefesto", "O que o controle faz agora: Jogar pelo Hefesto"),
        ("mascara", "DualSense (botões PlayStation)", "O jogo vê o controle como:"),
        ("steam_input_do_jogo", "marcado", "a entrada dele passa a vir da Steam"),
        ("steam_input_do_jogo", "desmarcado", "volta a ver o controle virtual"),
    ],
)
def test_a_frase_usa_o_lexico_da_janela(mudanca: str, valor: str, esperado: str) -> None:
    """Nenhuma palavra nova: os rótulos são os que já estão na tela.

    Ela recusa vocabulário que não deriva do que o produto já usa — nome novo
    que não deriva do que há é sinal de conceito errado.
    """
    assert esperado in r.frase_da_mudanca(mudanca, valor)


def test_o_titulo_pergunta_em_vez_de_avisar() -> None:
    """A janela PEDE, no padrão do HONESTIDADE-STEAM-01."""
    assert r.TITULO.endswith("?"), (
        "o título deixou de ser pergunta. Fechar o jogo dela é consequência "
        "pesada: o produto pede, não anuncia."
    )


# --- as três saídas -----------------------------------------------------------


def test_cada_saida_tem_a_sua_frase_honesta() -> None:
    """E nenhuma delas promete o que não aconteceu."""
    assert "Nada mudou" in r.toast_da_escolha("cancelar")

    depois = r.toast_da_escolha("na_proxima_abertura", jogo="Sackboy")
    assert "Guardado" in depois and "Sackboy" in depois, (
        "o toast de adiar não diz o que foi guardado nem para qual jogo — estado "
        "pendente invisível é o defeito que a casa mais paga."
    )

    agora = r.toast_da_escolha("fechar_e_abrir")
    assert "fechou" in agora and "pedi a abertura" in agora, (
        "o toast do caminho destrutivo tem de dizer o que ELE fez — inclusive "
        "que quem abre de novo é a Steam, não nós."
    )


def test_os_tres_rotulos_existem_e_sao_distintos() -> None:
    """Três saídas, e a de cancelar é a primeira (vira o default do diálogo)."""
    rotulos = (r.ROTULO_CANCELAR, r.ROTULO_DEPOIS, r.ROTULO_FECHAR)
    assert len(set(rotulos)) == 3, "dois botões com o mesmo rótulo"
    assert all(rotulos), "rótulo vazio"
    assert "próxima abertura" in r.ROTULO_DEPOIS, (
        "o botão de adiar não diz QUANDO vale — sem isso ela não sabe o que está "
        "escolhendo."
    )

"""O diálogo só aparece quando a mudança de fato exige o jogo reabrir."""

from __future__ import annotations

import pytest

from hefesto_dualsense4unix.app.actions import relancar as r


@pytest.mark.parametrize("mudanca", sorted(r.EXIGEM_RELANCAR))
def test_com_jogo_aberto_as_mudancas_de_entrada_perguntam(mudanca: str) -> None:
    """ARRANQUE a mudança da lista e este teste REPROVA."""
    assert r.precisa_perguntar(mudanca=mudanca, jogo_aberto=True) is True


@pytest.mark.parametrize("mudanca", sorted(r.MUDA_NA_HORA))
def test_o_que_muda_na_hora_nunca_pergunta(mudanca: str) -> None:
    """O contrapeso, e é o que impede o diálogo de virar ruído."""
    assert r.precisa_perguntar(mudanca=mudanca, jogo_aberto=True) is False


@pytest.mark.parametrize("mudanca", sorted(r.EXIGEM_RELANCAR))
def test_sem_jogo_aberto_nunca_pergunta(mudanca: str) -> None:
    """Sem jogo, a mudança aplica direto — como sempre fez."""
    assert r.precisa_perguntar(mudanca=mudanca, jogo_aberto=False) is False


def test_mudanca_desconhecida_nao_interrompe() -> None:
    """Tela nova que esqueça de se registrar segue como antes, sem incomodar."""
    assert r.precisa_perguntar(mudanca="algo_que_ninguem_escreveu", jogo_aberto=True) is False


def test_as_duas_listas_nao_se_cruzam() -> None:
    """Nenhuma mudança pode estar nas duas listas."""
    cruzamento = r.EXIGEM_RELANCAR & r.MUDA_NA_HORA
    assert not cruzamento, f"mudança em AMBAS as listas: {sorted(cruzamento)}"


def test_o_corpo_diz_as_tres_coisas() -> None:
    """O corpo tem de dizer o que mudou, por que não chega, e o que muda na hora."""
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
    """Nenhuma palavra nova: os rótulos são os que já estão na tela."""
    assert esperado in r.frase_da_mudanca(mudanca, valor)


def test_o_titulo_pergunta_em_vez_de_avisar() -> None:
    """A janela PEDE, no padrão do HONESTIDADE-STEAM-01."""
    assert r.TITULO.endswith("?"), (
        "o título deixou de ser pergunta. Fechar o jogo dela é consequência "
        "pesada: o produto pede, não anuncia."
    )


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


def test_o_rotulo_promete_o_fim_e_nao_o_meio() -> None:
    """"Aplicar agora e reiniciar o jogo" — as palavras dela."""
    assert "Aplicar agora" in r.ROTULO_FECHAR, (
        "o rótulo voltou a descrever o meio (fechar) em vez do fim (aplicar). "
        "Quem lê o botão precisa saber o que GANHA, não só o que perde."
    )
    assert "reiniciar o jogo" in r.ROTULO_FECHAR, (
        "o rótulo não diz mais que o jogo reinicia — e reiniciar é o preço que "
        "ela aceita pagar CONSCIENTEMENTE."
    )


def test_o_toast_do_relancamento_diz_o_que_de_fato_aconteceu() -> None:
    """Uma frase por desfecho, e nenhuma promete o que não foi conferido."""
    ok = r.toast_do_relancamento(fechou=True, reabriu=True, appid=1599660)
    assert "fechei o jogo" in ok.lower() and "mudança valeu" in ok
    assert "pode demorar" in ok.lower(), (
        "o toast do caminho feliz não avisa que a Steam demora — sem isso ela "
        "acha que falhou e clica de novo."
    )

    nao_fechou = r.toast_do_relancamento(fechou=False, reabriu=False)
    assert "não fechou" in nao_fechou, "não diz que a Steam resistiu"
    assert "próxima vez" in nao_fechou, (
        "não diz o que ACONTECEU com a mudança dela — ela fica sem saber se "
        "precisa refazer."
    )

    sem_appid = r.toast_do_relancamento(fechou=True, reabriu=False, appid=None)
    assert "não consegui identificar qual jogo" in sem_appid.lower(), (
        "quando o appid não foi descoberto, o toast tem de dizer POR QUE não "
        "reabriu — senão parece defeito aleatório."
    )

    sem_abrir = r.toast_do_relancamento(fechou=True, reabriu=False, appid=1599660)
    assert "abra pela Steam" in sem_abrir, (
        "quando não conseguiu reabrir, o toast tem de dizer o que ELA faz agora."
    )


def test_o_toast_nunca_afirma_que_o_jogo_abriu() -> None:
    """Reabrir é PEDIR à Steam. Afirmar "abriu" seria mentir de novo."""
    ok = r.toast_do_relancamento(fechou=True, reabriu=True, appid=1)
    for promessa in ("o jogo abriu", "jogo aberto", "está aberto"):
        assert promessa not in ok.lower(), (
            f"o toast afirma {promessa!r} — só sabemos que o pedido saiu."
        )


def test_o_modo_pergunta_agora_que_a_decisao_fecha_no_aplicar() -> None:
    """O modo voltou a perguntar — e a ida e a volta são a MESMA decisão dela."""
    assert "modo" in r.EXIGEM_RELANCAR, (
        "`modo` saiu da lista de novo. Com o diálogo no 'Aplicar', trocar o "
        "modo com o jogo aberto voltaria a mexer no `compose_env` ao vivo sem "
        "ela saber — o caminho do 'Jogador 3' fantasma."
    )
    assert r.precisa_perguntar(mudanca="modo", jogo_aberto=True) is True
    assert r.precisa_perguntar(mudanca="modo", jogo_aberto=False) is False


def test_a_mascara_continua_perguntando() -> None:
    """O contrapeso: tirar do modo não pode esvaziar a cura."""
    assert "mascara" in r.EXIGEM_RELANCAR
    assert r.precisa_perguntar(mudanca="mascara", jogo_aberto=True) is True


def test_a_frase_do_modo_continua_existindo() -> None:
    """O texto do modo fica, porque o diálogo pode voltar a usá-lo."""
    assert "O que o controle faz agora" in r.frase_da_mudanca(
        "modo", "Jogar pelo Hefesto"
    )

"""A QUINTA PERGUNTA morde — TUDO-FUNCIONA-01.

**A cobrança dela, 08/09/2026:** *"mas aí me quebra. pq o programa de dias a
fio é de brinquedo? uma prova de conceito? por favor. ele tem que funcionar em
tudo. tudo realmente. é essa a ideia."*
(noqa-acento: citação literal dela, palavra por palavra)

O portão é `scripts/check_ate_onde_a_prova_chegou.py`. As quatro perguntas dela
(cabo? BT? no perfil? por controle?) leem `*_aciona` — *"o Hefesto MEXE
nisso?"*. Esta lê `*_ate_onde_foi` — *"até onde a PROVA chegou?"* —, e a
diferença entre as duas é o preço do primeiro degrau da escada: *tratar MONTOU
como «funciona» é a mentira mais cara desta casa*.

**SETE MORDIDAS**, e cada uma é um jeito real de o inventário envelhecer:

1. a prova parou e ninguém declarou a falta;
2. a falta declarada cuja prova já CHEGOU — vira propaganda se ficar;
3. a declaração para um gesto que a tela já não oferece;
4. custo fora do vocabulário, ou dona que não está no disco;
5. o teto do degrau de ENTRADA: uma célula subiu ao jogo e a constante não;
6. o degrau MUDOU NO MAPA — para baixo a régua acusa a falta nova, para cima
   ela acusa a declaração velha;
7. **o destino não mora na régua.** É a mordida de 09/09/2026, e ela nasceu de
   um defeito: o `destino` de cada feature morava DENTRO da
   `A_PROVA_QUE_FALTA`, a mesma tabela que declara a falta — *uma trava medida
   contra a própria saída*. Apagar a declaração do `sensor` MOVIA o destino
   dele, e a régua imprimia «o destino é O APARELHO OBEDECEU» para uma feature
   cuja prova só termina no jogo. Agora o destino vem do MAPA: mexer nesta
   tabela não move a linha de chegada de nada, e mexer no `canal` do mapa move.
"""
from __future__ import annotations

import copy
import importlib.util
import pathlib

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
PORTAO = RAIZ / "scripts/check_ate_onde_a_prova_chegou.py"


def _regua():
    spec = importlib.util.spec_from_file_location("_quinta_pergunta", PORTAO)
    assert spec and spec.loader
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture(scope="module")
def regua():
    return _regua()


def test_o_inventario_de_hoje_passa(regua, capsys):
    """VERDE — com as oito faltas NOMEADAS, e agrupadas por custo."""
    assert regua.main() == 0
    saida = capsys.readouterr().out
    assert "VERDE" in saida
    for gesto in ("mascara", "sensor", "rota", "mudo"):
        assert gesto in saida, "a falta sai nomeada, nunca em silêncio"
    assert "os custos NÃO se somam" in saida


def test_cada_falta_tem_um_custo_so_e_ele_nao_se_soma(regua):
    """A regra que a sprint deixa, e ela é sobre a FRASE, não sobre o número.

    *Nunca some faltas de custos diferentes numa frase só.* Duas horas de
    trabalho e um bloqueio de transporte não são "não funciona" — e dizer que
    são faz dias de trabalho parecerem uma prova de conceito. O vocabulário é
    fechado justamente para que a soma seja impossível de escrever sem apagar
    a distinção.
    """
    for gesto, (custo, _dona, _razao) in regua.A_PROVA_QUE_FALTA.items():
        assert custo in regua.CUSTOS, f"{gesto} tem custo fora do vocabulário"


def test_morde_a_prova_que_parou_e_ninguem_declarou(regua, monkeypatch, capsys):
    """MORDIDA 1 — arranque a declaração do `sensor` e a régua o nomeia."""
    sem_sensor = {g: v for g, v in regua.A_PROVA_QUE_FALTA.items() if g != "sensor"}
    monkeypatch.setattr(regua, "A_PROVA_QUE_FALTA", sem_sensor)
    assert regua.main() == 1
    saida = capsys.readouterr().out
    assert "sensor" in saida
    assert "parou antes do destino" in saida


def test_morde_a_falta_declarada_cuja_prova_ja_chegou(regua, monkeypatch, capsys):
    """MORDIDA 2 — a linha SAI quando a cura chega, senão vira propaganda."""
    monkeypatch.setitem(
        regua.A_PROVA_QUE_FALTA, "cor",
        ("horas", "2026-09-08-TUDO-FUNCIONA-01-o-que-falta"
         "-para-nada-ser-de-brinquedo.md",
         "esta falta não existe: a cor OBEDECEU nos dois desde 12/08"))
    assert regua.main() == 1
    saida = capsys.readouterr().out
    assert "já chegou ao destino" in saida
    assert "cor" in saida


def test_morde_a_declaracao_de_gesto_que_a_tela_nao_oferece(regua, monkeypatch,
                                                            capsys):
    """MORDIDA 3 — a lista se LÊ da tela; a razão se escreve, e envelhece."""
    monkeypatch.setitem(
        regua.A_PROVA_QUE_FALTA, "lightbar-em-rgb-invertido",
        ("horas", "2026-09-08-TUDO-FUNCIONA-01-o-que-falta"
         "-para-nada-ser-de-brinquedo.md", "gesto que a tela nunca ofereceu"))
    assert regua.main() == 1
    assert "já não oferece" in capsys.readouterr().out


def test_morde_o_custo_fora_do_vocabulario(regua, monkeypatch, capsys):
    """MORDIDA 4a — «um pouco» não é custo: some faltas sem dizer quais."""
    _custo, dona, razao = regua.A_PROVA_QUE_FALTA["rota"]
    monkeypatch.setitem(regua.A_PROVA_QUE_FALTA, "rota",
                        ("um pouco", dona, razao))
    assert regua.main() == 1
    assert "fora do vocabulário" in capsys.readouterr().out


def test_morde_a_dona_que_nao_esta_no_disco(regua, monkeypatch, capsys):
    """MORDIDA 4b — falta sem sprint dona é falta que ninguém vai fechar."""
    custo, _dona, razao = regua.A_PROVA_QUE_FALTA["mudo"]
    monkeypatch.setitem(regua.A_PROVA_QUE_FALTA, "mudo",
                        (custo, "2026-01-01-NAO-EXISTE.md", razao))
    assert regua.main() == 1
    assert "não está em docs/process/sprints" in capsys.readouterr().out


def test_morde_a_celula_que_subiu_ao_jogo_sem_o_teto_descer(regua, monkeypatch,
                                                            capsys):
    """MORDIDA 5 — o teto do degrau de ENTRADA não pode sobrar.

    Hoje são ZERO de 622 células. No dia em que a primeira subir, a régua
    reprova pedindo o número novo: *régua com folga acumulada dá verde sobre o
    defeito seguinte* (cicatriz de 03/09/2026).
    """
    original = regua._linhas_do_mapa()

    def _com_uma_no_jogo() -> dict[str, list[dict[str, str]]]:
        fingido = copy.deepcopy(original)
        for linha in fingido["movimento.giroscopio"]:
            if linha["controle"] == "dualsense":
                linha["cabo_ate_onde_foi"] = regua.GRAU_JOGO_RECEBEU
        return fingido

    monkeypatch.setattr(regua, "_linhas_do_mapa", _com_uma_no_jogo)
    assert regua.main() == 1
    saida = capsys.readouterr().out
    assert "degrau de entrada" in saida
    assert "movimento.giroscopio@dualsense" in saida


def test_degrau_fora_da_escada_nao_e_engolido(regua, monkeypatch):
    """A régua NÃO inventa domínio: quem o guarda é o `paridade-transporte`.

    Engolir aqui um degrau com outra tipografia daria verde sobre exatamente o
    que a régua irmã reprova — e um degrau com tipografia própria já atravessou
    a regra 6 sem ser visto uma vez.
    """
    with pytest.raises(SystemExit):
        regua._degrau({"chave": "x", "cabo_ate_onde_foi": "montou"}, "cabo")


def test_a_escada_desta_regua_e_a_do_dono_dela(regua):
    """O vocabulário é DERIVADO, nunca redigitado — um dono só."""
    from check_paridade_transporte import VALORES_DA_ESCADA

    assert (regua.SEM_REGISTRO, *VALORES_DA_ESCADA) == regua._ORDEM


# ───────────────────────────────────────────────────────────────────────────
# MORDIDA 6 — o degrau muda NO MAPA, e a régua muda de resposta com ele.
# ───────────────────────────────────────────────────────────────────────────
# Ela morde nos DOIS sentidos de propósito. Uma régua que só acusa quando a
# prova DESCE dá verde para sempre depois da primeira cura; uma que só acusa
# quando SOBE deixa a falta nova passar. As duas metades são a mesma pergunta
# feita ao mesmo dado — a coluna `*_ate_onde_foi` do mapa.


def _mapa_com(regua, chave: str, lado: str, degrau: str):
    """O mapa de hoje com UMA célula trocada — cópia, nunca o CSV do disco."""
    original = regua._linhas_do_mapa()

    def _trocado() -> dict[str, list[dict[str, str]]]:
        fingido = copy.deepcopy(original)
        for linha in fingido[chave]:
            if linha["controle"] == "dualsense":
                linha[f"{lado}_ate_onde_foi"] = degrau
        return fingido

    return _trocado


def test_morde_o_degrau_que_desceu_no_mapa(regua, monkeypatch, capsys):
    """MORDIDA 6a — a cor desce a MONTOU no cabo e a régua acusa a falta nova.

    `luz.lightbar.cor@dualsense` responde por CINCO gestos da tela (`cor`,
    `brilho`, `apagar`, `reenviar` e a paleta do `auto-cores`). Baixar um único
    lado dela tem de derrubar os cinco de uma vez — e nenhum está declarado,
    porque hoje os cinco chegaram.
    """
    monkeypatch.setattr(
        regua, "_linhas_do_mapa",
        _mapa_com(regua, "luz.lightbar.cor", "cabo", "MONTOU"))
    assert regua.main() == 1
    saida = capsys.readouterr().out
    assert "parou antes do destino" in saida
    for gesto in ("cor", "brilho", "apagar", "reenviar", "auto-cores"):
        assert gesto in saida, f"{gesto} desceu no mapa e a régua não o nomeou"


def test_morde_o_degrau_que_subiu_no_mapa(regua, monkeypatch, capsys):
    """MORDIDA 6b — a rota sobe no rádio e a declaração dela fica velha.

    É o mesmo caminho da mordida 2, mas puxado pelo MAPA e não pela tabela: a
    prova subiu de verdade, e quem tem de sair é a linha da `A_PROVA_QUE_FALTA`.
    """
    monkeypatch.setattr(
        regua, "_linhas_do_mapa",
        _mapa_com(regua, "audio.alto_falante.rota", "radio",
                  "O APARELHO OBEDECEU"))
    assert regua.main() == 1
    saida = capsys.readouterr().out
    assert "já chegou ao destino" in saida
    assert "rota" in saida


# ───────────────────────────────────────────────────────────────────────────
# MORDIDA 7 — o destino NÃO mora na régua (09/09/2026).
# ───────────────────────────────────────────────────────────────────────────
# O defeito que ela fecha: o `destino` de cada feature morava dentro da
# `A_PROVA_QUE_FALTA`, que é a tabela onde se declara a falta. Quem declarava a
# falta escolhia junto a linha de chegada contra a qual ela é medida — *uma
# trava medida contra a própria saída* —, e apagar a declaração do `sensor`
# fazia a régua imprimir «o destino é O APARELHO OBEDECEU» para uma feature
# cuja prova só termina no jogo.


def test_a_tabela_da_falta_nao_sabe_escrever_um_destino(regua):
    """MORDIDA 7a — não há ONDE escrever um destino aqui, e é estrutural.

    Três campos: custo, dona e razão. Se um degrau da escada aparecer em
    qualquer um deles, alguém devolveu a linha de chegada para dentro da
    tabela — e a régua voltou a se medir contra a própria saída.
    """
    from check_paridade_transporte import VALORES_DA_ESCADA

    for gesto, valores in regua.A_PROVA_QUE_FALTA.items():
        assert len(valores) == 3, (
            f"{gesto} tem {len(valores)} campos: a tabela é (custo, dona, "
            "razão), e um quarto campo é por onde o destino volta")
        custo, dona, _razao = valores
        assert custo not in VALORES_DA_ESCADA, f"{gesto}: degrau no custo"
        assert dona not in VALORES_DA_ESCADA, f"{gesto}: degrau na dona"


def test_o_destino_nao_se_move_mexendo_na_regua(regua, monkeypatch):
    """MORDIDA 7b — ESVAZIE a tabela inteira: nenhum destino se mexe.

    É a reprodução exata do defeito. Antes de 09/09 esta asserção falhava para
    `mascara` e `sensor`: sem a declaração, as duas caíam no destino padrão do
    plástico.
    """
    mapa = regua._linhas_do_mapa()
    antes = {gesto: regua.destino_de(chaves, mapa)
             for gesto, chaves in regua.DO_APARELHO.items()}

    monkeypatch.setattr(regua, "A_PROVA_QUE_FALTA", {})
    depois = {gesto: regua.destino_de(chaves, mapa)
              for gesto, chaves in regua.DO_APARELHO.items()}

    assert antes == depois
    assert antes["sensor"] == regua.GRAU_JOGO_REAGIU, (
        "a feature que termina no jogo perdeu o destino dela")


def test_o_destino_se_move_mexendo_no_mapa(regua):
    """MORDIDA 7c — a outra metade: o MAPA move, e move sozinho.

    Sem esta, a 7b passaria com um destino cravado em constante — que é imóvel
    por ser morto, não por ter dono.
    """
    mapa = regua._linhas_do_mapa()
    assert regua.destino_de(("luz.lightbar.cor",), mapa) == "O APARELHO OBEDECEU"

    fingido = copy.deepcopy(mapa)
    for linha in fingido["luz.lightbar.cor"]:
        if linha["controle"] == "dualsense":
            linha["cabo_canal"] = "uhid"
    assert regua.destino_de(("luz.lightbar.cor",), fingido) == regua.GRAU_JOGO_REAGIU


def test_canal_sem_direcao_declarada_reprova_em_vez_de_escolher(regua):
    """MORDIDA 7d — canal que não diz por onde o dado anda não decide nada.

    `outro` está no domínio da coluna e NÃO está na `DIRECAO_POR_CANAL`, de
    propósito: engolir aqui viraria destino padrão, que é escolher o degrau
    mais barato — a mesma recusa do `SEM_REGISTRO`, que fica abaixo de MONTOU.
    """
    mapa = copy.deepcopy(regua._linhas_do_mapa())
    for linha in mapa["luz.lightbar.cor"]:
        if linha["controle"] == "dualsense":
            linha["radio_canal"] = "outro"
    with pytest.raises(SystemExit):
        regua.destino_de(("luz.lightbar.cor",), mapa)

    mapa = copy.deepcopy(regua._linhas_do_mapa())
    for linha in mapa["luz.lightbar.cor"]:
        if linha["controle"] == "dualsense":
            linha["radio_canal"] = ""
    with pytest.raises(SystemExit):
        regua.destino_de(("luz.lightbar.cor",), mapa)


def test_toda_direcao_do_dominio_de_canal_esta_declarada():
    """A régua da régua: canal novo no domínio TEM de nascer com direção.

    Sem isto, acrescentar um valor a `DOMINIO_POR_SUFIXO["canal"]` deixaria a
    quinta pergunta reprovando em `SystemExit` na primeira linha que o usasse —
    ou, pior, alguém o classificaria por conveniência para calar o erro.
    `outro` é a única ausência declarada, e a razão está escrita ao lado dela.
    """
    from check_paridade_transporte import DIRECAO_POR_CANAL, DOMINIO_POR_SUFIXO

    assert set(DIRECAO_POR_CANAL) | {"", "outro"} == DOMINIO_POR_SUFIXO["canal"]

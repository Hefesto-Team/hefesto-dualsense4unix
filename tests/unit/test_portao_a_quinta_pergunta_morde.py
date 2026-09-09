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

**CINCO MORDIDAS**, e cada uma é um jeito real de o inventário envelhecer:

1. a prova parou e ninguém declarou a falta;
2. a falta declarada cuja prova já CHEGOU — vira propaganda se ficar;
3. a declaração para um gesto que a tela já não oferece;
4. custo fora do vocabulário, ou dona que não está no disco;
5. o teto do degrau de ENTRADA: uma célula subiu ao jogo e a constante não.
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
    for gesto in ("mascara", "sensor", "rota", "player"):
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
    for gesto, (_destino, custo, _dona, _razao) in regua.A_PROVA_QUE_FALTA.items():
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
        (regua.DESTINO_PADRAO, "horas", "2026-09-08-TUDO-FUNCIONA-01-o-que-falta"
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
        (regua.DESTINO_PADRAO, "horas", "2026-09-08-TUDO-FUNCIONA-01-o-que-falta"
         "-para-nada-ser-de-brinquedo.md", "gesto que a tela nunca ofereceu"))
    assert regua.main() == 1
    assert "já não oferece" in capsys.readouterr().out


def test_morde_o_custo_fora_do_vocabulario(regua, monkeypatch, capsys):
    """MORDIDA 4a — «um pouco» não é custo: some faltas sem dizer quais."""
    destino, _custo, dona, razao = regua.A_PROVA_QUE_FALTA["rota"]
    monkeypatch.setitem(regua.A_PROVA_QUE_FALTA, "rota",
                        (destino, "um pouco", dona, razao))
    assert regua.main() == 1
    assert "fora do vocabulário" in capsys.readouterr().out


def test_morde_a_dona_que_nao_esta_no_disco(regua, monkeypatch, capsys):
    """MORDIDA 4b — falta sem sprint dona é falta que ninguém vai fechar."""
    destino, custo, _dona, razao = regua.A_PROVA_QUE_FALTA["mudo"]
    monkeypatch.setitem(regua.A_PROVA_QUE_FALTA, "mudo",
                        (destino, custo, "2026-01-01-NAO-EXISTE.md", razao))
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

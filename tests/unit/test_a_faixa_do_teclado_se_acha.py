"""A-FAIXA-DO-TECLADO-SE-ACHA-01: a procura da faixa diz a causa medida, não um «não achei» só.

Antes da cura (medido em 09/10/2026 sobre os mesmos pares): o par de mapas de um receptor que
salta de canal, o par sem mapa AFH e o par em que nada mudou davam TODOS o mesmo passo ``nada``,
«Não achei a faixa dele» (na tela, a «Faixa não encontrada · Tentar de novo» que ela viu). Agora a
procura (``receptor_sem_fio.classificar`` e ``Descoberta``) responde a faixa, o salto, a falta de
mapa ou o mapa parado, sobre os pares guardados em ``tests/fixtures/a_faixa_do_receptor/``
(sintéticos até a bancada gravar os do teclado do usuário com
``scripts/ensaios/a_faixa_do_receptor.py``).

MORDIDAS (arrancar, ver reprovar, devolver):

1. ``classificar`` sem a pergunta do salto: o par ``salta`` volta ao «Não achei» (test_1).
2. ``classificar`` sem a pergunta do mapa: o par ``sem-mapa`` vira «mapa parado» (test_2).
3. A medida «com ele» sem a espera até o mapa mudar: o par ``devagar`` com 120 s não acha (test_5).
4. O «com» sem a soma das leituras: o par ``salta`` com 120 s não junta os oito canais (test_6).
5. A cura inteira arrancada (a ``Descoberta`` volta a fechar só pela ``banda_por_eliminacao``): o
   par ``salta`` fecha sem causa, e a frase é o «Não achei a faixa dele» de antes (test_1).
6. A volta à medida «com ele» sem zerar o ``com``: a soma de antes do receptor sair vira um
   salto falso (test_8b).
7. A medida «sem ele» de volta a uma leitura só (sem o ``&`` das leituras até
   ``ESPERA_ATE_O_MAPA_SOLTAR_S``): o par ``solta-devagar`` fica no «mapa parado» (test_11).
8. A volta à medida «sem ele» sem zerar o ``sem``: a leitura de antes do receptor voltar segura a
   faixa e ela some do «com» (test_12).

A medida de 19/10/2026 no receptor 25a7:fa07 (a do diário, ``sem=[18] com=[18]``): com uma leitura
só, aos 25 s, o mapa ficou igual. A espera do «com» sobe para 120 s, o «sem» fica com o menor mapa
de 60 s, e a tela pede o teclado e o mouse enquanto mede com ele.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import receptor_sem_fio as rx

RAIZ = Path(__file__).resolve().parents[2]
FIXTURES = RAIZ / "tests" / "fixtures" / "a_faixa_do_receptor"


def _carregar() -> ModuleType:
    caminho = RAIZ / "scripts" / "ensaios" / "a_faixa_do_receptor.py"
    spec = importlib.util.spec_from_file_location("_a_faixa_do_receptor", caminho)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


ensaio = _carregar()


def _fim(nome: str, **trocas: float | None) -> Any:
    return ensaio.reproduzir(ensaio.ler_sessao(FIXTURES / f"{nome}.json"), **trocas)


def test_1_o_receptor_que_salta_de_canal_e_resposta_e_nao_nao_achei() -> None:
    fim = _fim("salta")
    assert (fim.passo, fim.banda, fim.causa) == (rx.PASSO_NADA, None, rx.CAUSA_SALTA)
    assert fim.frase == rx.FRASE_DA_CAUSA[rx.CAUSA_SALTA] == "Salta de canal: passa pela faixa toda"
    assert fim.frase != rx.FRASE_DO_PASSO[rx.PASSO_NADA], "o mesmo par dava «não achei»"
    assert len(fim.canais) >= rx.CANAIS_QUE_PROVAM_O_SALTO
    assert all(b - a > 1 for a, b in zip(fim.canais, fim.canais[1:], strict=False)), "espalhados"


def test_2_sem_mapa_afh_nao_ha_o_que_medir_e_a_frase_diz_o_passo_que_falta() -> None:
    fim = _fim("sem-mapa")
    assert (fim.passo, fim.causa, fim.canais) == (rx.PASSO_NADA, rx.CAUSA_SEM_MAPA, ())
    assert "aparelho no Bluetooth" in fim.frase
    assert rx.classificar({"hci0": None, "hci1": (1, 2)}, {"hci0": (5, 6, 7), "hci1": None}) == (
        rx.Resposta(None, rx.CAUSA_SEM_MAPA, ())), "adaptador que não mediu nos dois não conta"


def test_3_o_canal_solto_e_o_mapa_parado() -> None:
    fim = _fim("parado")
    assert (fim.passo, fim.causa, fim.canais) == (rx.PASSO_NADA, rx.CAUSA_SEM_MUDANCA, (40,))
    assert fim.frase == rx.FRASE_DA_CAUSA[rx.CAUSA_SEM_MUDANCA]


def test_4_a_faixa_fixa_continua_achada_e_guardada_como_antes() -> None:
    fim = _fim("banda")
    assert (fim.passo, fim.banda, fim.causa) == (rx.PASSO_ACHOU, (18, 35), "")
    assert rx.banda_por_eliminacao({"L1": ()}, {"L1": (5, 40)}) is None, "a régua velha vale"


def test_5_o_afh_lento_acha_com_a_espera_e_a_espera_nasce_ligada() -> None:
    assert rx.ESPERA_ATE_O_MAPA_MUDAR_S == 120.0, "a leitura só de 25 s não achou em 19/10"
    assert _fim("devagar", ate=25).causa == rx.CAUSA_SEM_MUDANCA
    fim = _fim("devagar")
    assert (fim.passo, fim.banda) == (rx.PASSO_ACHOU, (40, 53))


def test_6_o_com_soma_as_leituras_da_espera() -> None:
    """Quem salta deixa canais diferentes a cada leitura; a espera junta todos."""
    assert len(_fim("salta").canais) == 7
    assert len(_fim("salta", ate=120, salto=8).canais) == 8


def test_7_os_interruptores_trocam_o_numero_sem_editar_codigo() -> None:
    assert _fim("salta", salto=20).causa == rx.CAUSA_SEM_MUDANCA
    assert _fim("parado", minimos=1).banda == (40, 41)
    assert rx.CANAIS_MINIMOS_DA_BANDA == 3 and rx.CANAIS_QUE_PROVAM_O_SALTO == 6
    assert rx.ESPERA_DA_MEDIDA_S == 25.0, "o ensaio devolve as constantes no fim"


def test_8_o_gesto_que_recomeca_esquece_a_causa_velha() -> None:
    d = rx.Descoberta()
    d.iniciar("1234:5678", 0.0)
    d.passo, d.causa, d.canais = rx.PASSO_NADA, rx.CAUSA_SALTA, (3, 11)
    d.iniciar("1234:5678", 1.0)
    assert d.causa == "" and not d.canais and rx.frase_do_fim(d) == ""


def test_8b_o_receptor_que_sai_no_meio_zera_a_soma_do_com(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tirado no meio da medida «com ele», as leituras de antes não entram na soma da volta."""
    monkeypatch.setattr(rx, "ESPERA_ATE_O_MAPA_MUDAR_S", 120.0)
    monkeypatch.setattr(rx, "ESPERA_ATE_O_MAPA_SOLTAR_S", rx.ESPERA_DA_MEDIDA_S)
    d = rx.Descoberta()
    d.iniciar("1234:5678", 0.0)
    d.andar(1.0, dict, presente=False)
    d.andar(26.0, lambda: {"hci0": ()}, presente=False)
    d.andar(27.0, dict, presente=True)
    d.andar(52.0, lambda: {"hci0": (2, 10, 18, 26, 34)}, presente=True)
    assert d.passo == rx.PASSO_MEDINDO_COM, "cinco canais espalhados ainda esperam"
    d.andar(53.0, dict, presente=False)
    d.andar(54.0, dict, presente=True)
    d.andar(79.0, lambda: {"hci0": (50, 60)}, presente=True)
    assert d.com == {"hci0": (50, 60)}
    assert (d.passo, d.causa) == (rx.PASSO_MEDINDO_COM, ""), "a soma velha virou um salto falso"


def test_9_o_ensaio_recusa_sem_medir_e_grava_sem_endereco(
        tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    saida = tmp_path / "mapas.jsonl"
    assert ensaio.main(["gravar", "--momento", "sem", "--saida", str(saida)]) == 2
    assert not saida.exists() and ensaio.RECUSA_SEM_MEDIR in capsys.readouterr().out

    class _Conexao:
        def __init__(self, handle: int, tipo: int, endereco: str) -> None:
            self.handle, self.tipo, self.endereco = handle, tipo, endereco

    class _Mapa:
        def __init__(self, evitados: tuple[int, ...]) -> None:
            self.evitados = evitados

    from hefesto_dualsense4unix.integrations import ar_do_adaptador as ar

    conexoes = {0: [_Conexao(1, ar.TIPO_ACL, "AA:BB:CC:00:00:01"),
                    _Conexao(2, ar.TIPO_ACL, "AA:BB:CC:00:00:02")], 1: []}
    mapas = {1: _Mapa((20, 21, 22)), 2: _Mapa((21, 22, 40))}

    def ler() -> object:
        return ensaio.mapas_de_agora(lambda: [0, 1], lambda hci: conexoes[hci],
                                     lambda _hci, handle: mapas[handle])

    assert ensaio.main(["gravar", "--momento", "com", "--saida", str(saida), "--medir",
                        "--segundos", "0.02", "--cada", "0.01"], ler=ler) == 0
    texto = saida.read_text(encoding="utf-8")
    assert not re.search(r"([0-9a-f]{2}[:_-]?){5}[0-9a-f]{2}", texto, re.I), "endereço gravado"
    linhas = [json.loads(li) for li in texto.splitlines()]
    assert [li["t"] for li in linhas] == [0, 0.01, 0.02]
    assert linhas[0]["adaptadores"] == {"hci0": [21, 22], "hci1": None}


def test_10_o_ensaio_classifica_numa_linha_curta(capsys: pytest.CaptureFixture[str]) -> None:
    assert ensaio.main(["classificar", str(FIXTURES / "salta.json")]) == 0
    assert capsys.readouterr().out.strip().startswith(f"nada: {rx.FRASE_DA_CAUSA[rx.CAUSA_SALTA]}")


def test_11_o_sem_fica_com_o_menor_mapa_e_acha_a_faixa_que_o_afh_segurava() -> None:
    """A decisão: D-1910-A-FAIXA-ESPERA-O-MAPA-SOLTAR-E-MUDAR."""
    assert _fim("solta-devagar", solta=25).causa == rx.CAUSA_SEM_MUDANCA, "uma leitura só não acha"
    fim = _fim("solta-devagar")
    assert (fim.passo, fim.banda) == (rx.PASSO_ACHOU, (20, 35))


def test_12_o_receptor_que_volta_no_meio_do_sem_zera_o_menor_mapa() -> None:
    d = rx.Descoberta()
    d.iniciar("1234:5678", 0.0)
    d.andar(1.0, dict, presente=False)
    d.andar(26.0, lambda: {"hci0": (20, 21, 22, 23)}, presente=False)
    d.andar(27.0, dict, presente=True)
    assert d.passo == rx.PASSO_TIRE
    d.andar(28.0, dict, presente=False)
    d.andar(28.0 + rx.ESPERA_ATE_O_MAPA_SOLTAR_S, lambda: {"hci0": (60,)}, presente=False)
    assert d.sem == {"hci0": (60,)}, "a leitura de antes da volta segurou a faixa no «sem»"
    assert d.passo == rx.PASSO_PONHA


def test_13_enquanto_mede_com_ele_a_tela_pede_o_teclado_e_o_mouse() -> None:
    assert "teclado e o mouse" in rx.FRASE_DO_PASSO[rx.PASSO_MEDINDO_COM]

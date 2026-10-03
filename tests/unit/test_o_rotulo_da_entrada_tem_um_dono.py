"""Todo texto de tela que diz a entrada pergunta ao dono — O-MAPA-QUE-ELA-CORRIGE-01, passo 3.

Com «Meio» na 1 (e o «2» que o Mapear de antes gravava como nome na 2), cada
superfície diz «Meio» e «Entrada 2» — e nenhuma diz «O 13», «Entrada: 2» ou
«<b>2</b>». O dono da GRAFIA é ``utils/rotulo_da_entrada``; o da LEITURA é
``entrada_a_entrada.nome_da_entrada`` (D-2609-O-NOME-E-DA-POSICAO).

Duas metades, como a sprint pede:

(a) PELO FONTE. A régua do Python é a que já existia
    (``test_a_costura_da_onda_2.test_o_nome_da_porta_tem_um_dono_so``),
    estendida para não distinguir maiúscula. A do JavaScript do mapa mora
    aqui: o único «Entrada» + valor permitido no ``<script>`` é a palavra que o
    gerador injeta (``PALAVRA_DA_ENTRADA`` e ``PALAVRA_NA_FRASE``).
(b) PELO COMPORTAMENTO: a Sugestão, a ordem, a linha de Rádio e Adaptadores, o
    «Já mapeadas», a recusa do governador. O cabeçalho do editor e o plugue
    são medidos no WebKit, em ``test_o_mapa_que_ela_corrige_na_tela``.

A MORDIDA: devolva ao ``ler_o_mapa`` o nome cru do lugar e o
``f"{PALAVRA_DA_ENTRADA} {numero}"`` — o «Já mapeadas» volta a dizer «2»
(:func:`test_o_ja_mapeadas_diz_o_nome_e_a_face`), e a régua do fonte acusa o
``entrada_a_entrada``.

Máquina sintética, a mesma de ``test_o_nome_da_entrada_e_da_posicao``.
"""

from __future__ import annotations

import json
import re
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import entrada_a_entrada as ee
from hefesto_dualsense4unix.integrations import ordens_da_mesa as ordens
from hefesto_dualsense4unix.integrations.censo_do_barramento import Censo
from hefesto_dualsense4unix.interface import arranjo_desta_maquina, onde
from hefesto_dualsense4unix.utils.maquina import MaquinaConfig, lugar_de, migrar_o_documento
from hefesto_dualsense4unix.utils.rotulo_da_entrada import (
    PALAVRA_DA_ENTRADA,
    PALAVRA_NA_FRASE,
)
from tests.unit.test_o_nome_da_entrada_e_da_posicao import (
    PCI_A,
    PCI_B,
    _a_maquina_dela,
    gravar_o_arquivo_de_antes,
)

PAGINA = onde.pagina(arranjo_desta_maquina.PAGINA, publicado=True)

_COMPOE_NO_JS = re.compile(
    r"""(["'])[^"'\n]*\bentradas?\s*\1\s*\+(?=\s*[^\s"'])""", re.IGNORECASE)

_O_QUE_NAO_SE_DIZ = ("O 13", "o 13", "Entrada: 2", "<b>2</b>", "no Meio", "O Meio")


@pytest.fixture()
def documento() -> MaquinaConfig:
    return MaquinaConfig.model_validate(migrar_o_documento(_a_maquina_dela()))


def _limpo(texto: str) -> None:
    for proibido in _O_QUE_NAO_SE_DIZ:
        assert proibido not in texto, f"a tela disse {proibido!r}: {texto!r}"


def _o_script() -> str:
    html = PAGINA.read_text(encoding="utf-8")
    blocos = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
    assert blocos, "a página publicada não tem <script> — a régua passaria por vacuidade"
    return "\n".join(blocos)


def test_o_script_do_mapa_so_compoe_pela_palavra_do_dono() -> None:
    """Nenhum literal «entrada » + valor no JavaScript da página; a palavra que"""
    script = _o_script()
    achados = [m.group(0) for m in _COMPOE_NO_JS.finditer(script)]
    assert not achados, f"a página compõe a palavra fora do dono: {achados}"
    palavra = json.dumps(PALAVRA_DA_ENTRADA, ensure_ascii=False)
    na_frase = json.dumps(PALAVRA_NA_FRASE, ensure_ascii=False)
    assert f"var PALAVRA_DA_ENTRADA = {palavra};" in script
    assert f"var PALAVRA_NA_FRASE = {na_frase};" in script
    assert "PALAVRA_DA_ENTRADA + \" \" + n" in script, (
        "a reserva do rótulo não é mais a palavra injetada — a régua mediria o vazio")


def test_a_linha_de_radio_e_adaptadores_diz_o_nome_da_entrada(
    documento: MaquinaConfig,
) -> None:
    controladores = {1: PCI_A, 3: PCI_B}
    assert ee.rotulo_da_entrada(
        lugar_de(PCI_A, "4"), maquina=documento, controladores=controladores) == "Meio"
    assert ee.rotulo_da_entrada(
        lugar_de(PCI_A, "3"), maquina=documento, controladores=controladores) == "Entrada 2"
    assert ee.nome_da_porta("1-4", maquina=documento, controladores=controladores) == "Meio"
    assert ee.nome_da_porta("3-1.4", maquina=documento, controladores=controladores) == (
        "Entrada 13")


def test_o_ja_mapeadas_diz_o_nome_e_a_face(documento: MaquinaConfig) -> None:
    """O «Já mapeadas» do Mapear: «<b>Meio</b>», a palavra do número e a face,"""
    from tests.conftest import exigir_gi_real

    exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes

    mapa = ee.ler_o_mapa(
        maquina=documento, censo=Censo(), entradas=(), adaptadores=(), storm={})
    portas = mapa.como_dicionario()["portas"]
    assert {p["numero"] for p in portas} >= {"1", "2", "13"}
    rotulos = {p["numero"]: p["rotulo"] for p in portas}
    assert (rotulos["1"], rotulos["2"], rotulos["13"]) == ("Meio", "Entrada 2", "Entrada 13")
    lista = a08_conexoes.html_das_entradas_mapeadas(portas)
    assert "<b>Meio</b><span>Entrada 1 · Frente do gabinete</span>" in lista, lista
    assert "pci-" not in lista, "o endereço do sistema voltou para a lista"
    _limpo(lista)


def test_a_sugestao_diz_as_duas_pontas_pelo_nome(
    documento: MaquinaConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A caixinha da Sugestão: «Meio → Entrada 2», pela declaração dela."""
    from tests.conftest import exigir_gi_real

    exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes

    monkeypatch.setattr(a08_conexoes, "_declaracao", lambda *_a, **_k: documento)
    vazio = ordens.Linha(texto="", selo="")
    ordem = ordens.Ordem(
        chave="teste",
        acao="Mova o adaptador Bluetooth para a Entrada 2",  # (noqa-acento) campo da Ordem
        o_que_eu_vi=vazio, por_que_importa=vazio, ganho_esperado=vazio,
        alvo=ordens.Identidade(caminho="1-4"), destino="2")
    card = a08_conexoes._card_da_ordem(ordem)
    assert '<span class="caixa">Meio</span>' in card, card
    assert '<span class="caixa alvo">Entrada 2</span>' in card, card
    _limpo(card)


def test_a_ordem_manda_para_a_entrada_pelo_nome() -> None:
    """«… para a entrada Meio» com o nome, «… para a Entrada 2» sem ele."""
    from tests.unit.test_ordens_da_mesa import leitura

    com_nome = ordens.radio_largo_no_mesmo_hub(
        leitura(entradas_livres_declaradas=("1",), nomes_das_entradas={"1": "Meio"}))
    sem_nome = ordens.radio_largo_no_mesmo_hub(leitura(entradas_livres_declaradas=("2",)))
    assert com_nome is not None and sem_nome is not None
    assert com_nome.acao.endswith("para a entrada Meio"), com_nome.acao
    assert sem_nome.acao.endswith("para a Entrada 2"), sem_nome.acao
    _limpo(com_nome.acao + sem_nome.acao)


def test_a_recusa_do_governador_concorda_com_entrada() -> None:
    """O artigo concorda com «entrada», não com o nome: «A entrada Meio», «na Entrada 13»."""
    from hefesto_dualsense4unix.daemon.subsystems import governador_do_radio as gov

    recusa = gov.Recusa(
        "controle", "aa:bb:cc:00:00:01", "som", gov.MOTIVO_CHEIO, ("aa:bb:cc:00:00:02",),
        nomear={"aa:bb:cc:00:00:01": "Meio", "aa:bb:cc:00:00:02": "Entrada 13"}.get,
    )
    assert recusa.frase == (
        "A entrada Meio já tem 2 controles com som ou vibração. Há vaga na Entrada 13.")
    _limpo(recusa.frase)


def test_a_leitura_das_ordens_leva_o_nome_das_entradas(
    documento: MaquinaConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``secao_exame.leitura_das_ordens`` preenche ``nomes_das_entradas`` pelo"""
    from tests.conftest import exigir_gi_real

    exigir_gi_real("importa a seção do exame, que carrega o GTK")
    from hefesto_dualsense4unix.app.actions.config import secao_exame
    from hefesto_dualsense4unix.integrations import censo_do_barramento, entradas_do_gabinete

    monkeypatch.setattr(censo_do_barramento, "ler_o_barramento", lambda **_k: Censo())
    monkeypatch.setattr(entradas_do_gabinete, "listar_entradas", lambda **_k: ())
    lida: Any = secao_exame.leitura_das_ordens(documento)
    assert dict(lida.nomes_das_entradas) == {"1": "Meio"}, lida.nomes_das_entradas


def test_o_nome_dado_no_mapa_chega_a_sugestao_e_a_ordem(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """De ponta a ponta: o nome que ela dá no editor do mapa (``dar_nome_a_entrada``,"""
    from tests.conftest import exigir_gi_real

    exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")
    from hefesto_dualsense4unix.app.actions.config import secao_exame
    from hefesto_dualsense4unix.integrations import censo_do_barramento, entradas_do_gabinete
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes
    from hefesto_dualsense4unix.utils.maquina import carregar_maquina

    gravar_o_arquivo_de_antes(tmp_path, _a_maquina_dela())
    assert ee.dar_nome_a_entrada("2", "Frente de cima").gravou
    dela = carregar_maquina()
    assert dela.mapa.portas["2"].nome == "Frente de cima"

    monkeypatch.setattr(censo_do_barramento, "ler_o_barramento", lambda **_k: Censo())
    monkeypatch.setattr(entradas_do_gabinete, "listar_entradas", lambda **_k: ())
    lida: Any = secao_exame.leitura_das_ordens(dela)
    assert dict(lida.nomes_das_entradas) == {"1": "Meio", "2": "Frente de cima"}

    from tests.unit.test_ordens_da_mesa import leitura

    ordem = ordens.radio_largo_no_mesmo_hub(leitura(
        entradas_livres_declaradas=("2",), nomes_das_entradas=lida.nomes_das_entradas))
    assert ordem is not None and ordem.acao.endswith("para a entrada Frente de cima"), ordem

    monkeypatch.setattr(a08_conexoes, "_declaracao", lambda *_a, **_k: dela)
    vazio = ordens.Linha(texto="", selo="")
    card = a08_conexoes._card_da_ordem(ordens.Ordem(
        chave="teste", acao=ordem.acao, o_que_eu_vi=vazio, por_que_importa=vazio,
        ganho_esperado=vazio, alvo=ordens.Identidade(caminho="1-4"), destino="2"))
    assert '<span class="caixa">Meio</span>' in card, card
    assert '<span class="caixa alvo">Frente de cima</span>' in card, card
    _limpo(card)

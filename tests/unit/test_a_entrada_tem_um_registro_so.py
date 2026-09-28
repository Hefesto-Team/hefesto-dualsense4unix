"""A entrada tem um registro só — A-ENTRADA-TEM-UM-REGISTRO-SO-01 (28/09/2026).

O defeito, item 6 da auditoria de 26/09: a mesma entrada morava em DOIS
registros do ``maquina.json`` — ``mapa.portas[N]`` (o caminho de barramento
deste boot, os nós, o nome) e ``lugares[L]`` (a amarra pelo lugar, com uma
cópia do caminho como «testemunha», e um nome). Em 26/09 uma troca feita fora
do produto mexeu num e não no outro, e o Mapa mostrou as entradas erradas até
o reparo à mão. E o adaptador do meio tinha dois nomes em dois registros:
«Centro» em ``lugares`` e «Meio» em ``adaptadores``.

A CURA: a entrada guarda o ``lugar`` (``mapa.portas[N].lugar``); o caminho se
calcula na leitura, com os controladores deste boot; ``lugares`` sai do
esquema; a migração roda ao carregar, inteira, uma vez, e é idempotente.

AS PROVAS DA SPRINT QUE MORAM AQUI (a 3 é da mão dela, no aparelho):

1. a migração reproduz o estado de hoje — o arquivo de antes da troca de 26/09
   com os gestos dela PELO PRODUTO (as trocas 3↔4, 5↔6 e 7↔8 pelo
   ``trocar_as_entradas`` e o «Meio» tirado da entrada 1) dá o MESMO mapa que o
   arquivo reparado à mão, migrado — sem script de reparo;
2. migrar duas vezes dá o mesmo arquivo, byte a byte;
4. um boot com outra numeração dos barramentos: o Mapa diz a mesma entrada.

A MÁQUINA É SINTÉTICA, NA FORMA DA DELA (a de
``test_o_nome_da_entrada_e_da_posicao``): 15 entradas em três faces, os números
gravados como nome, o «Meio» na 1 e três lugares de adaptador com «Centro»,
«Esquerda» e «Direita». Faixa sintética da casa: controladores
``0000:0a:00.0`` e ``0000:0b:00.0``, endereços ``aa:bb:cc``.

AS MORDIDAS (medidas em 28/09, com a cura arrancada e devolvida pelo md5):

* a migração deixa em ``lugares`` o nome do lugar sem entrada (a leitura de
  ``lugares[L].nome`` de volta) — «Centro» volta ao arquivo e à porta do
  adaptador do meio (``test_o_centro_nao_volta_ao_adaptador_do_meio``);
* ``caminho_da_porta`` ignora o lugar e responde pelos nós — o boot com os
  barramentos trocados põe a Entrada 7 no buraco do outro controlador
  (``test_um_boot_com_outra_numeracao_diz_a_mesma_entrada``);
* a migração não leva a testemunha que andou para a entrada que a tem — o
  mapa dos gestos pelo produto sai diferente do reparado à mão
  (``test_os_gestos_dela_pelo_produto_dao_o_mapa_reparado_a_mao``);
* a gravação volta a escrever o ``caminho`` calculado — o arquivo ganha a
  chave (``test_o_caminho_nao_vai_ao_disco``).
"""

from __future__ import annotations

import ast
import copy
import json
from pathlib import Path
from typing import Any

import pytest
import structlog

from hefesto_dualsense4unix.integrations import bluez_dbus
from hefesto_dualsense4unix.integrations import entrada_a_entrada as ee
from hefesto_dualsense4unix.integrations import mapa_das_portas
from hefesto_dualsense4unix.integrations.lugar_declarado import declarar_a_maquina
from hefesto_dualsense4unix.utils import lugar as grafia
from hefesto_dualsense4unix.utils.maquina import (
    MaquinaConfig,
    PortaDeclarada,
    caminho_da_maquina,
    carregar_maquina,
    entrada_do_lugar,
    lugar_de,
    migrar_o_documento,
    nome_dado_ao_adaptador,
)
from tests.unit.test_entrada_a_entrada_02_as_telas_aprovadas import (
    BOOT_1,
    BOOT_2,
    DUALSENSE,
    Gabinete,
)
from tests.unit.test_o_nome_da_entrada_e_da_posicao import (
    _ENTRADAS,
    _ORFAOS,
    PCI_A,
    PCI_B,
    _a_maquina_dela,
)

RAIZ = Path(__file__).resolve().parents[2]
SRC = RAIZ / "src" / "hefesto_dualsense4unix"

#: As três trocas de 26/09 (as entradas que o Mapear tinha posto no número da
#: outra), feitas por ela pelo «Trocar com…».
TROCAS = (("3", "4"), ("5", "6"), ("7", "8"))

#: O adaptador do meio: o lugar dele guardava «Centro» (a D3), e o nome dele é
#: «Meio» (``adaptadores``, 26/09). Endereço da faixa sintética.
LUGAR_DO_MEIO = lugar_de(PCI_B, "4.1.1")
ADAPTADOR_DO_MEIO = "aa:bb:cc:00:00:11"


def _gravar_o_arquivo_de_antes(tmp_path: Path, documento: dict[str, Any]) -> Path:
    """O arquivo como o produto de antes o deixava — escrito CRU, sem migrar."""
    alvo = caminho_da_maquina()
    assert alvo.is_relative_to(tmp_path), f"o maquina.json da régua não está desviado: {alvo}"
    corpo = {"version": 1, **documento}
    alvo.write_text(
        json.dumps(corpo, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
    )
    return alvo


def _a_dela_com_os_nomes_dos_adaptadores() -> dict[str, Any]:
    """A máquina dela, com os três adaptadores nomeados como ela os nomeou."""
    documento = _a_maquina_dela()
    documento["adaptadores"] = {
        "aabbcc000011": {"nome": "Meio"},
        "aabbcc000012": {"nome": "Esquerda"},
        "aabbcc000013": {"nome": "Direita"},
    }
    return documento


# ---------------------------------------------------------------------------
# O esquema: um registro, e o caminho não se guarda
# ---------------------------------------------------------------------------


def test_o_esquema_recusa_os_lugares_depois_de_migrado() -> None:
    """``lugares`` não é campo; cada entrada guarda o lugar, e o caminho dos
    nós é o de antes."""
    assert "lugares" not in MaquinaConfig.model_fields
    with pytest.raises(ValueError, match="lugares"):
        MaquinaConfig.model_validate({"lugares": {lugar_de(PCI_A, "1"): {"entrada": "1"}}})
    migrado = MaquinaConfig.model_validate(migrar_o_documento(_a_maquina_dela()))
    for numero, (pci, devpath, caminho, nos) in _ENTRADAS.items():
        porta = migrado.mapa.portas[numero]
        assert porta.lugar == lugar_de(pci, devpath), f"a {numero} não guardou o lugar"
        assert porta.caminho == caminho, f"o caminho calculado da {numero} não é o de antes"
        assert set(porta.nos) == set(nos)
    assert entrada_do_lugar(migrado, lugar_de(PCI_A, "5")) == "7"
    with pytest.raises(ValueError, match="lugar"):
        PortaDeclarada(lugar=f"pci-{PCI_A}")  # sem cadeia de portas não é entrada


def test_o_caminho_nao_vai_ao_disco(tmp_path: Path) -> None:
    """O caminho é da LEITURA: nenhuma gravação o escreve, e quem ainda o
    declara (o rascunho do mapa) é entendido — o caminho vira o nó do buraco.

    MORDIDA: grave com o ``model_dump`` sem ``exclude_computed_fields`` — o
    arquivo ganha a chave ``caminho`` e esta régua reprova.
    """
    alvo = _gravar_o_arquivo_de_antes(tmp_path, _a_maquina_dela())
    assert carregar_maquina().mapa.portas["3"].caminho == "3-1"
    assert ee.declarar_a_velocidade("3", 3).gravou
    assert '"caminho"' not in alvo.read_text(encoding="utf-8")

    # «este aparelho está nesta entrada»: o buraco passa a ser o dele
    assert declarar_a_maquina({"mapa": {"portas": {"3": {"caminho": "3-4"}}}}).gravou
    tres = carregar_maquina().mapa.portas["3"]
    assert (tres.nos, tres.lugar, tres.caminho) == (["usb3-port4"], None, "3-4")
    # o «tirar» do rascunho: os nós saem, e o lugar do Mapear fica
    assert declarar_a_maquina({"mapa": {"portas": {"7": {"caminho": None}}}}).gravou
    sete = carregar_maquina().mapa.portas["7"]
    assert (sete.nos, sete.lugar) == ([], lugar_de(PCI_A, "5"))
    assert '"caminho"' not in alvo.read_text(encoding="utf-8")


def test_o_rascunho_do_mapa_le_o_caminho_e_a_volta_nao_muda_nada() -> None:
    """A ``LogicaDoMapa`` (o rascunho da aba Conexões) lê o ``caminho`` do
    ``model_dump`` e o manda de volta inteiro: a volta não mexe em entrada
    nenhuma."""
    from hefesto_dualsense4unix.app.widgets.mapa_da_mesa import LogicaDoMapa

    documento = MaquinaConfig.model_validate(migrar_o_documento(_a_maquina_dela()))
    logica = LogicaDoMapa(documento.mapa)
    assert logica.caminho_em("7") == "1-5"
    assert logica.entrada_do_caminho("3-1.1.4") == "9"
    volta = MaquinaConfig.model_validate({"mapa": logica.como_documento()})
    assert volta.mapa == documento.mapa


# ---------------------------------------------------------------------------
# A migração: inteira, ao carregar, uma vez
# ---------------------------------------------------------------------------


def test_a_migracao_roda_ao_carregar_inteira_e_uma_vez(tmp_path: Path) -> None:
    """PROVA 2: a primeira leitura migra e regrava; a cópia de antes fica ao
    lado; migrar de novo dá o mesmo arquivo, byte a byte."""
    alvo = _gravar_o_arquivo_de_antes(tmp_path, _a_maquina_dela())
    antes = alvo.read_bytes()
    carregar_maquina()
    depois = alvo.read_bytes()
    assert depois != antes, "a leitura não migrou o arquivo"
    bruto = json.loads(depois)
    assert "lugares" not in bruto
    assert not any("caminho" in porta for porta in bruto["mapa"]["portas"].values())

    copia = alvo.with_name(alvo.name + ".com-os-lugares")
    assert copia.read_bytes() == antes, "a cópia de antes não é o arquivo de antes"

    carregar_maquina()
    assert alvo.read_bytes() == depois, "a segunda leitura reescreveu o arquivo"
    assert migrar_o_documento(bruto) == bruto
    de_novo = json.dumps(migrar_o_documento(bruto), ensure_ascii=False, indent=2, sort_keys=True)
    assert de_novo.encode() == depois, "migrar o migrado mudou um byte"

    assert ee.declarar_a_velocidade("4", 2).gravou
    assert copia.read_bytes() == antes, "a cópia de antes foi sobrescrita"


def test_a_migracao_leva_o_nome_de_verdade_e_nao_o_numero() -> None:
    """O «Meio» da 1 vai para a posição; os números gravados como nome não vão;
    o nome do lugar sem entrada sai; o do adaptador fica onde é dele."""
    migrado = migrar_o_documento(_a_dela_com_os_nomes_dos_adaptadores())
    portas = migrado["mapa"]["portas"]
    assert portas["1"]["nome"] == "Meio"
    assert [n for n, p in portas.items() if "nome" in p] == ["1"], portas
    assert "lugares" not in migrado
    # os três lugares de adaptador: o nome deles é do adaptador, pelo endereço
    assert set(_ORFAOS.values()) == {"Centro", "Esquerda", "Direita"}
    assert "Centro" not in json.dumps(migrado, ensure_ascii=False)
    assert migrado["adaptadores"]["aabbcc000011"] == {"nome": "Meio"}


def test_o_nome_comprido_bloqueia_a_migracao_daquela_entrada_e_diz_no_log(
    tmp_path: Path,
) -> None:
    """Nada se trunca calado: o nome de mais de 24 caracteres fica no lugar,
    como estava, a entrada dele não migra, e o log diz qual é. O nome que ela
    der à posição destrava. No disco, o resto do arquivo migra e é lido."""
    documento = _a_maquina_dela()
    lugar_5 = lugar_de(PCI_B, "3")
    comprido = "A de trás, perto do cabo de rede"
    documento["lugares"][lugar_5]["nome"] = comprido
    with structlog.testing.capture_logs() as registros:
        migrado = migrar_o_documento(documento)
    assert migrado["lugares"] == {lugar_5: documento["lugares"][lugar_5]}
    assert migrado["lugares"][lugar_5]["nome"] == comprido
    assert "lugar" not in migrado["mapa"]["portas"]["5"]
    assert "nome" not in migrado["mapa"]["portas"]["5"]
    assert migrado["mapa"]["portas"]["6"]["lugar"] == lugar_de(PCI_B, "4"), "as outras pararam"
    assert any(
        r["event"] == "maquina_migracao_bloqueada_nome_comprido" and r["entrada"] == "5"
        for r in registros
    ), registros
    assert migrar_o_documento(migrado) == migrado, "o bloqueio não é idempotente"
    assert MaquinaConfig.model_validate(
        {k: v for k, v in migrado.items() if k != "lugares"}
    ).mapa.portas["5"].lugar is None

    alvo = _gravar_o_arquivo_de_antes(tmp_path, documento)
    lido = carregar_maquina()
    assert lido.mapa.portas["6"].lugar == lugar_de(PCI_B, "4")
    assert lido.mapa.portas["5"].lugar is None and lido.mapa.portas["5"].nome is None
    assert json.loads(alvo.read_text(encoding="utf-8"))["lugares"][lugar_5]["nome"] == comprido

    migrado["mapa"]["portas"]["5"]["nome"] = "Trás"
    liberado = migrar_o_documento(migrado)
    assert "lugares" not in liberado
    assert liberado["mapa"]["portas"]["5"]["lugar"] == lugar_5
    assert liberado["mapa"]["portas"]["5"]["nome"] == "Trás"


def test_o_nao_alcanco_vai_para_o_mapa() -> None:
    documento = _a_maquina_dela()
    vaga = lugar_de(PCI_A, "2")
    documento["lugares"][vaga] = {"fora": True}
    documento["lugares"][lugar_de(PCI_A, "6")]["fora"] = True
    migrado = MaquinaConfig.model_validate(migrar_o_documento(documento))
    assert set(migrado.mapa.fora) == {vaga, lugar_de(PCI_A, "6")}


# ---------------------------------------------------------------------------
# PROVA 1 — os gestos dela pelo produto dão o mapa reparado à mão
# ---------------------------------------------------------------------------


def _o_reparado_a_mao() -> dict[str, Any]:
    """O arquivo depois do reparo à mão de 26/09, no formato de antes: o buraco
    trocado no ``mapa`` E a amarra trocada nos ``lugares`` (o que o
    ``reparo_real.sh`` fez), e o «Meio» tirado do lugar da 1."""
    reparado = copy.deepcopy(_a_maquina_dela())
    portas = reparado["mapa"]["portas"]
    troca = {}
    for um, outro in TROCAS:
        portas[um], portas[outro] = portas[outro], portas[um]
        troca.update({um: outro, outro: um})
    for dele in reparado["lugares"].values():
        if dele.get("entrada") in troca:
            dele["entrada"] = troca[dele["entrada"]]
    del reparado["lugares"][lugar_de(PCI_A, "4")]["nome"]
    return reparado


def test_os_gestos_dela_pelo_produto_dao_o_mapa_reparado_a_mao(tmp_path: Path) -> None:
    """PROVA 1. O arquivo de ANTES da troca, migrado ao carregar, com a
    sequência de gestos de 26/09 pelo produto, dá o mesmo mapa que o arquivo
    reparado à mão, migrado. Sem o script de reparo."""
    alvo = _gravar_o_arquivo_de_antes(tmp_path, _a_maquina_dela())
    carregar_maquina()
    for um, outro in TROCAS:
        assert ee.trocar_as_entradas(um, outro).gravou, (um, outro)
    assert ee.dar_nome_a_entrada("1", "").gravou
    pelo_produto = json.loads(alvo.read_text(encoding="utf-8"))

    reparado = migrar_o_documento(_o_reparado_a_mao())
    assert pelo_produto["mapa"]["portas"] == reparado["mapa"]["portas"]
    documento = MaquinaConfig.model_validate(pelo_produto)
    assert documento == MaquinaConfig.model_validate(reparado)
    for um, outro in TROCAS:
        assert entrada_do_lugar(documento, dict(_LUGAR_DE_ANTES)[um]) == outro


_LUGAR_DE_ANTES = tuple(
    (numero, lugar_de(pci, devpath)) for numero, (pci, devpath, _c, _n) in _ENTRADAS.items()
)


def test_a_troca_feita_fora_do_produto_se_repara_na_migracao() -> None:
    """O estado de 26/09 às 15h43: o ``mapa`` trocou o buraco de 3↔4 e 7↔8
    sem os ``lugares``. A testemunha de cada lugar está na OUTRA entrada, e a
    migração leva a amarra para ela — o que o reparo à mão fez.

    MORDIDA: tire da migração o passo da testemunha que andou — os lugares
    ficam sem entrada, e a 4 não é mais o lugar do hub."""
    documento = _a_maquina_dela()
    portas = documento["mapa"]["portas"]
    for um, outro in (("3", "4"), ("7", "8")):
        portas[um], portas[outro] = portas[outro], portas[um]
    migrado = MaquinaConfig.model_validate(migrar_o_documento(documento))
    assert entrada_do_lugar(migrado, lugar_de(PCI_B, "1")) == "4"
    assert entrada_do_lugar(migrado, lugar_de(PCI_B, "2")) == "3"
    assert entrada_do_lugar(migrado, lugar_de(PCI_A, "5")) == "8"
    assert entrada_do_lugar(migrado, lugar_de(PCI_A, "6")) == "7"
    assert ee.nome_da_porta("3-1", maquina=migrado, controladores=BOOT_1) == "Entrada 4"


# ---------------------------------------------------------------------------
# PROVA 4 — um boot com outra numeração dos barramentos
# ---------------------------------------------------------------------------


def test_um_boot_com_outra_numeracao_diz_a_mesma_entrada(tmp_path: Path) -> None:
    """A máquina dela foi mapeada no boot 1 (a Entrada 7 é ``1-5``); no boot 2
    os controladores subiram na ordem inversa, e o DualSense no cabo da Entrada
    7 enumera como ``3-5``. O Mapear, o nome da porta e o motor do arranjo
    dizem a Entrada 7 — e o ``1-5`` deste boot, que é o OUTRO controlador,
    não é ela."""
    documento = MaquinaConfig.model_validate(migrar_o_documento(_a_maquina_dela()))
    gabinete = Gabinete(tmp_path / "boot2", BOOT_2)
    assert gabinete.plugar(3, "5", DUALSENSE) == "3-5"
    censo = gabinete.ler()

    mapa = ee.ler_o_mapa(
        maquina=documento, censo=censo, entradas=gabinete.entradas(),
        adaptadores=(), storm={},
    )
    sete = mapa.porta("7")
    assert sete is not None and sete.aparelho == "3-5" and sete.e_dualsense, sete
    assert sete.caminho == "3-5"
    assert ee.nome_da_porta("3-5", maquina=documento, controladores=BOOT_2) == "Entrada 7"
    assert ee.nome_da_porta("1-5", maquina=documento, controladores=BOOT_2) != "Entrada 7"
    bancada = mapa_das_portas.mesa_do_motor(documento.mapa, censo)
    assert bancada.mesa.mapa["7"] == "3-5", bancada.mesa.mapa
    assert mapa_das_portas.porta_de(
        documento.mapa, "3-5", mapa_das_portas.controladores_do_censo(censo)) == "7"


# ---------------------------------------------------------------------------
# Um dono do nome do adaptador, e um lugar_de só
# ---------------------------------------------------------------------------


def test_o_centro_nao_volta_ao_adaptador_do_meio(tmp_path: Path) -> None:
    """O adaptador do meio se chama «Meio» (``adaptadores``, pelo endereço), e
    o «Centro» que o lugar dele guardava (a D3) sai do arquivo e da porta."""
    alvo = _gravar_o_arquivo_de_antes(tmp_path, _a_dela_com_os_nomes_dos_adaptadores())
    documento = carregar_maquina()
    assert "Centro" not in alvo.read_text(encoding="utf-8")
    assert nome_dado_ao_adaptador(documento, ADAPTADOR_DO_MEIO) == "Meio"
    porta = ee.nome_da_porta(LUGAR_DO_MEIO, maquina=documento, controladores=BOOT_1)
    assert porta != "Centro" and porta == "Entrada 4.1.1", porta
    linha = ee.com_o_nome_dela(
        {"porta": LUGAR_DO_MEIO, "frase": f"O adaptador da porta {LUGAR_DO_MEIO} travou."},
        maquina=documento,
        controladores=BOOT_1,
    )
    assert "Centro" not in json.dumps(linha, ensure_ascii=False)
    mapa = ee.ler_o_mapa(maquina=documento, censo=None, entradas=(), raiz_usb=str(tmp_path),
                         adaptadores=(), storm={})
    assert "Centro" not in json.dumps(mapa.como_dicionario(), ensure_ascii=False)


def test_o_lugar_de_tem_uma_definicao_so() -> None:
    """Uma definição de ``lugar_de`` no pacote, a de ``utils/lugar.py``; o
    ``bluez_dbus`` IMPORTA a dela.

    MORDIDA: devolva ao ``bluez_dbus`` o ``def lugar_de`` que repassava a
    chamada — esta régua reprova nomeando o arquivo.
    """
    definicoes = []
    for arquivo in sorted(SRC.rglob("*.py")):
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        definicoes.extend(
            f"{arquivo.relative_to(RAIZ)}:{no.lineno}"
            for no in ast.walk(arvore)
            if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)) and no.name == "lugar_de"
        )
    assert len(definicoes) == 1, definicoes
    assert definicoes[0].startswith("src/hefesto_dualsense4unix/utils/lugar.py:"), definicoes
    assert bluez_dbus.lugar_de is grafia.lugar_de

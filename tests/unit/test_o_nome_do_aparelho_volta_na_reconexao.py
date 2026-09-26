"""O nome que ela dá volta na reconexão — O-RADIO-CONECTA-ONDE-ELA-MANDA-01, item 4.

O relato dela, 26/09/2026:

    *«Eu mudei o nome do dispositivo quando eu conectar os dispositivos bt
    novamente eu quero que o nome deles sejam lidos novamente e não voltem todas
    as vezes quie eu mudar»* <!-- noqa-acento: citação literal dela -->

O nome mora no ``Alias`` do BlueZ, UM POR OBJETO — um objeto por adaptador que
conhece o controle. O ``Pair`` num adaptador novo cria um objeto novo, com o
nome de fábrica; e a faxina da central esquece a chave velha logo depois. Era
assim que cada «Conectar» noutro adaptador apagava o nome dela.

O QUE ESTA RÉGUA SEGURA, para qualquer adaptador de origem e de destino:

1. o «Conectar» num adaptador novo leva o nome que ela deu ao objeto NOVO,
   lido de qualquer outro objeto do MESMO controle antes de a chave velha sair
   (o ``_dar_o_nome`` da central). MEDIDO em 26/09: os seis pares de
   adaptadores já passavam antes desta sprint — a régua é a guarda de que o
   destino que agora é o da caixa aberta não perdeu o nome no caminho;
2. o nome de fábrica não é nome: o controle que ela nunca renomeou chega sem
   escrita de ``Alias``, e o nome dela nunca vai para outro controle;
3. a tela mostra o nome dela em toda linha do controle — no ar, desligado, em
   qualquer adaptador em que ele tenha chave.

E O QUE A O-RADIO-CONECTA-ONDE-ELA-MANDA-02 FECHOU (26/09/2026), o E2 dela:
**o nome não depende da chave.** Com a ÚLTIMA chave do controle esquecida, não
sobrava objeto de onde copiar, e o ``Pair`` seguinte nascia com o nome de
fábrica. Agora o nome mora no ``maquina.json`` pelo endereço
(``ControleDeclarado.nome``), e a central (``cuidar_dos_nomes``):

4. guarda o nome quando ela renomeia — pela tela, ou por fora do produto;
5. esquece o guardado quando ela APAGA o nome (o mesmo objeto volta ao de
   fábrica), e não quando o objeto é novo;
6. o devolve em todo ``Pair`` (o dela: ``_quem_e``) e em toda conexão, em
   qualquer adaptador (a volta dos nomes, no fio da faxina) — e o objeto que
   APARECE com um nome velho (o adaptador que volta à porta) recebe o dela,
   não dá;
7. só de CONTROLE: o nome de um fone continua morando no pareamento dele.

Faixa sintética da casa: ``aa:bb:cc``, octetos 4 e 5 zerados.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import bluez_dbus as bd
from hefesto_dualsense4unix.integrations import central_do_radio as cr
from hefesto_dualsense4unix.utils import maquina
from tests.unit import radio_de_mentira as rm
from tests.unit.radio_de_mentira import AZUL, FONE, QUARTO, ROXO, SALA, VARANDA, VERMELHO
from tests.unit.test_o_conectar_pareia_no_adaptador_escolhido import (
    Bancada,
    ela_segura_ps_create,
    id_da_tela,
    preparar_a_tela,
    preparar_o_diario,
)

ADAPTADORES = (SALA, QUARTO, VARANDA)

FABRICA = rm.NOME_DE_FABRICA[rm.CLASSE_DE_CONTROLE]


@pytest.fixture()
def diario(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    return preparar_o_diario(tmp_path, monkeypatch)


@pytest.fixture()
def a08(monkeypatch: pytest.MonkeyPatch) -> Any:
    return preparar_a_tela(monkeypatch)


@pytest.fixture()
def casa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """O ``maquina.json`` numa pasta de teste — o de verdade, pelo dono dele."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    caminho = maquina.caminho_da_maquina()
    assert str(caminho).startswith(str(tmp_path)), "o maquina.json não é o da régua"
    return caminho


def _guardado(casa: Path, aparelho: str) -> str | None:
    """O nome no DISCO, lido do arquivo — não da memória de ninguém."""
    if not casa.exists():
        return None
    documento = json.loads(casa.read_text(encoding="utf-8"))
    return (documento.get("controles", {}).get(rm.uniq(aparelho)) or {}).get("nome")


def _renomear_na_tela(bancada: Bancada, monkeypatch: pytest.MonkeyPatch,
                      aparelho: str, nome: str) -> None:
    """O gesto da tela, o de verdade: o ``Alias`` vai a todo objeto dele no BlueZ."""
    monkeypatch.setattr(bd, "dono", lambda: bancada.dono)
    cena = bancada.cena()
    linha = next(a for a in cena["aparelhos"]
                 if str(a["id"]).replace(":", "").lower() == rm.uniq(aparelho))
    bancada.gesto("aparelho-renomear", alvo=linha["id"], valor=nome)


def _esquecer_em_todos(bancada: Bancada) -> None:
    """O X em cada linha do vermelho, em cada adaptador — ligado ou desligado."""
    for _ in range(len(ADAPTADORES)):
        cena = bancada.cena()
        linhas = [a for a in cena["aparelhos"]
                  if str(a["id"]).replace(":", "").lower() == rm.uniq(VERMELHO)
                  and not a.get("nao_conectou")]
        if not linhas:
            return
        clique = {"alvo": linhas[0]["id"], "lugar": linhas[0]["lugar"]}
        bancada.gesto("esquecer-aparelho", **clique)
        bancada.gesto("confirmar-esquecer", **clique)


def _conectar_em(bancada: Bancada, destino: str, quem: str) -> cr.Movimento:
    """Ela abre ``destino``, clica «Conectar» e segura PS + Create em ``quem``."""
    bancada.cena()
    if bancada.cena().get("aberto") != id_da_tela(destino):
        bancada.gesto("abrir-adaptador", alvo=id_da_tela(destino))
    bancada.cena()
    ela_segura_ps_create(bancada.mundo, bancada.relogio, quem)
    bancada.gesto("conectar-aparelho")
    bancada.esperar_a_central()
    return next(m for m in bancada.central.movimentos() if m.destino == destino)


PARES = [(o, d) for o in (SALA, QUARTO, VARANDA) for d in (SALA, QUARTO, VARANDA) if o != d]


@pytest.mark.parametrize(("origem", "destino"), PARES)
def test_o_conectar_noutro_adaptador_leva_o_nome_dela(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch, origem: str, destino: str,
) -> None:
    """O vermelho se chama «André» na origem. Ela o desliga, abre outro adaptador
    e clica «Conectar»: ele chega com «André» no objeto NOVO, e a tela o mostra
    assim — em qualquer par de adaptadores.

    MORDIDA: faça o ``_dar_o_nome`` da central não escrever — o objeto novo
    nasce com o nome de fábrica e esta régua reprova nos seis pares.
    """
    mundo, relogio = rm.RadioDeMentira(), rm.Relogio()
    mundo.pareado(origem, VERMELHO, nome="André")
    mundo.pareado(origem, AZUL, nome="Vitória")
    mundo.desligar(VERMELHO)
    bancada = Bancada(a08, monkeypatch, mundo, relogio)
    try:
        feito = _conectar_em(bancada, destino, VERMELHO)
        assert (feito.estado, feito.aparelho) == (cr.CHEGOU, VERMELHO)
        assert mundo.objeto(destino, VERMELHO)["Alias"] == "André"
        assert mundo.objeto(origem, AZUL)["Alias"] == "Vitória", "o nome foi para outro"
        cena = bancada.cena()
        (linha,) = [a for a in cena["aparelhos"] if str(a["id"]).lower() == rm.uniq(VERMELHO)
                    and a.get("lugar") == id_da_tela(destino)]
        assert linha["nome"] == "André"
    finally:
        bancada.fechar()


def test_sem_nome_dela_o_objeto_novo_fica_com_o_de_fabrica(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O nome de fábrica não é nome: o controle que ela nunca renomeou chega
    sem escrita de ``Alias`` nenhuma."""
    mundo, relogio = rm.RadioDeMentira(), rm.Relogio()
    mundo.pareado(SALA, VERMELHO)
    mundo.desligar(VERMELHO)
    bancada = Bancada(a08, monkeypatch, mundo, relogio)
    try:
        _conectar_em(bancada, VARANDA, VERMELHO)
        assert mundo.objeto(VARANDA, VERMELHO)["Alias"] == FABRICA
        assert [e for e in mundo.escritas if e[2] == "Alias"] == []
    finally:
        bancada.fechar()


def test_a_tela_mostra_o_nome_dela_em_toda_chave_do_controle(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O roxo se chama «Vitória» só no objeto da varanda; desligado, ele tem
    chave também na sala — e a linha «Desligado» da sala diz «Vitória», não o
    nome de fábrica. O nome é do CONTROLE, lido pelo endereço.

    MORDIDA: faça ``_os_desligados`` ler só o ``Alias`` do próprio objeto — a
    linha da sala volta ao nome de fábrica.
    """
    mundo, relogio = rm.RadioDeMentira(), rm.Relogio()
    mundo.pareado(VARANDA, ROXO, conectado=False, nome="Vitória")
    mundo.pareado(SALA, ROXO, host=False)
    bancada = Bancada(a08, monkeypatch, mundo, relogio)
    try:
        cena = bancada.cena()
        linhas = {a["lugar"]: a for a in cena["aparelhos"] if a.get("desligado")}
        assert set(linhas) == {id_da_tela(VARANDA), id_da_tela(SALA)}
        assert {a["nome"] for a in linhas.values()} == {"Vitória"}
    finally:
        bancada.fechar()


# ---------------------------------------------------------------------------
# O-RADIO-CONECTA-ONDE-ELA-MANDA-02: o nome não depende da chave
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("origem", "destino"), PARES + [(a, a) for a in ADAPTADORES])
def test_renomear_esquecer_em_todos_e_parear_de_novo_o_nome_volta(
    diario: Path, a08: Any, casa: Path, monkeypatch: pytest.MonkeyPatch,
    origem: str, destino: str,
) -> None:
    """E2 da O-RADIO-CONECTA-ONDE-ELA-MANDA-02, pela mão dela e de ponta a ponta.

    Ela renomeia o vermelho na tela («André»), esquece-o com o X em TODOS os
    adaptadores em que ele tem chave, abre outro (ou o mesmo) e clica
    «Conectar»: ele chega com «André» — no objeto novo, na linha da tela e no
    ``maquina.json`` —, sem objeto nenhum no BlueZ de onde copiar.

    MORDIDA: tire o guardado de ``_quem_e`` (o nome só do ``Alias`` de algum
    objeto) — o ``Pair`` nasce com o nome de fábrica, e esta régua reprova nos
    nove casos.
    """
    mundo, relogio = rm.RadioDeMentira(), rm.Relogio()
    mundo.pareado(origem, VERMELHO)
    outro = next(a for a in ADAPTADORES if a != origem)
    mundo.pareado(outro, VERMELHO, host=False)
    mundo.pareado(origem, AZUL, nome="Vitória")
    bancada = Bancada(a08, monkeypatch, mundo, relogio)
    try:
        _renomear_na_tela(bancada, monkeypatch, VERMELHO, "André")
        assert {mundo.objeto(a, VERMELHO)["Alias"] for a in (origem, outro)} == {"André"}
        bancada.central.cuidar_dos_nomes()
        assert _guardado(casa, VERMELHO) == "André"
        assert _guardado(casa, AZUL) == "Vitória"

        _esquecer_em_todos(bancada)
        assert all(mundo.objeto(a, VERMELHO) is None for a in ADAPTADORES), "sobrou chave"
        bancada.central.cuidar_dos_nomes()
        assert _guardado(casa, VERMELHO) == "André", "esquecer a chave apagou o nome"

        feito = _conectar_em(bancada, destino, VERMELHO)
        assert (feito.estado, feito.aparelho) == (cr.CHEGOU, VERMELHO)
        assert mundo.objeto(destino, VERMELHO)["Alias"] == "André"
        (linha,) = [a for a in bancada.cena()["aparelhos"]
                    if str(a["id"]).lower() == rm.uniq(VERMELHO)]
        assert linha["nome"] == "André" and linha["lugar"] == id_da_tela(destino)
        assert mundo.objeto(origem, AZUL)["Alias"] == "Vitória", "o nome foi para outro"
    finally:
        bancada.fechar()


def _central_da_casa(mundo: rm.RadioDeMentira, relogio: rm.Relogio) -> tuple[
        cr.CentralDoRadio, bd.DonoVivo]:
    dono = bd.DonoVivo(mundo)
    assert dono.ligar()
    central = cr.CentralDoRadio(
        dono=dono, onde_esta=mundo.onde_esta, movimento=mundo.hz,
        esquecer_na_ponte=mundo.esquecer_na_ponte, relogio=relogio, dormir=relogio.dormir,
        sysfs={"listar": lambda _p: [], "raiz": "/nao/existe"})
    return central, dono


@pytest.mark.parametrize("destino", ADAPTADORES)
def test_o_controle_que_conecta_por_fora_da_central_recebe_o_nome(
    diario: Path, casa: Path, destino: str,
) -> None:
    """«Reaplicado em toda conexão, em qualquer adaptador»: o nome está no
    ``maquina.json`` e chave nenhuma sobrou; ele é pareado POR FORA da central
    (o ``bluetoothctl``, o sistema) e conecta com o nome de fábrica. A volta
    seguinte dos nomes o devolve — e nenhum outro controle é tocado.

    MORDIDA: tire a escrita do ``Alias`` da volta (``cuidar_dos_nomes``) — o
    objeto fica com o nome de fábrica.
    """
    assert maquina.gravar_o_nome_do_controle(VERMELHO, "André")
    mundo, relogio = rm.RadioDeMentira(), rm.Relogio()
    mundo.pareado(SALA if destino != SALA else QUARTO, AZUL)
    mundo.pareado(destino, VERMELHO)
    central, dono = _central_da_casa(mundo, relogio)
    try:
        assert mundo.objeto(destino, VERMELHO)["Alias"] == FABRICA
        feitos = central.cuidar_dos_nomes()
        assert feitos == ((VERMELHO, "André"),)
        assert mundo.objeto(destino, VERMELHO)["Alias"] == "André"
        assert [e for e in mundo.escritas if e[2] == "Alias"] == [
            (rm.no_de(destino, VERMELHO), bd.APARELHO, "Alias", "André")]
        assert central.cuidar_dos_nomes() == (), "a volta escreveu de novo o que já estava"
    finally:
        central.fechar()
        dono.fechar()


def test_ela_apaga_o_nome_e_ele_nao_volta(
    diario: Path, a08: Any, casa: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Apagar o nome na tela volta ao de fábrica (e a tela ao «Player N»): o
    guardado sai do ``maquina.json``, e o «Conectar» seguinte, noutro
    adaptador e sem chave nenhuma, NÃO o traz de volta.

    MORDIDA: tire o «ela apagou o nome» de ``_o_nome_que_vale`` — a volta
    seguinte devolve «André» aos objetos que ela acabou de limpar.
    """
    mundo, relogio = rm.RadioDeMentira(), rm.Relogio()
    mundo.pareado(SALA, VERMELHO)
    mundo.pareado(QUARTO, VERMELHO, host=False)
    bancada = Bancada(a08, monkeypatch, mundo, relogio)
    try:
        _renomear_na_tela(bancada, monkeypatch, VERMELHO, "André")
        bancada.central.cuidar_dos_nomes()
        assert _guardado(casa, VERMELHO) == "André"

        _renomear_na_tela(bancada, monkeypatch, VERMELHO, "")
        bancada.central.cuidar_dos_nomes()
        assert _guardado(casa, VERMELHO) is None, "o nome apagado ficou guardado"
        bancada.central.cuidar_dos_nomes()
        assert all(not bancada.central._nome_dado(bancada.dono, o)
                   for o in bancada.dono.aparelhos() or () if o.endereco == VERMELHO)

        _esquecer_em_todos(bancada)
        _conectar_em(bancada, VARANDA, VERMELHO)
        assert mundo.objeto(VARANDA, VERMELHO)["Alias"] == FABRICA
    finally:
        bancada.fechar()


def test_o_nome_dado_por_fora_do_produto_tambem_fica(diario: Path, casa: Path) -> None:
    """O produto é para qualquer computador: o nome que ela dá pelo
    ``bluetoothctl`` (ou pelo sistema), num objeto só, é guardado e vai aos
    outros objetos do mesmo controle."""
    mundo, relogio = rm.RadioDeMentira(), rm.Relogio()
    mundo.pareado(SALA, VERMELHO)
    mundo.pareado(VARANDA, VERMELHO, host=False)
    central, dono = _central_da_casa(mundo, relogio)
    try:
        assert central.cuidar_dos_nomes() == ()
        mundo.escrever(rm.no_de(SALA, VERMELHO), bd.APARELHO, "Alias", "s", "Bia", espera=1.0)
        central.cuidar_dos_nomes()
        assert _guardado(casa, VERMELHO) == "Bia"
        assert mundo.objeto(VARANDA, VERMELHO)["Alias"] == "Bia"
    finally:
        central.fechar()
        dono.fechar()


def test_so_o_controle_tem_o_nome_guardado(diario: Path, casa: Path) -> None:
    """DECISÃO desta sprint: o campo é ``ControleDeclarado.nome``, e só controle
    (pela classe) vai ao ``maquina.json``. O fone renomeado continua com o nome
    no pareamento dele, e a volta não o toca.

    MORDIDA: tire o filtro de controle de ``_controles_pelo_endereco`` — o fone
    vira uma entrada de ``controles``.
    """
    mundo, relogio = rm.RadioDeMentira(), rm.Relogio()
    mundo.pareado(SALA, FONE, classe=rm.CLASSE_DE_FONE, nome="Caixa da Sala")
    mundo.pareado(SALA, VERMELHO, nome="André")
    central, dono = _central_da_casa(mundo, relogio)
    try:
        central.cuidar_dos_nomes()
        assert _guardado(casa, VERMELHO) == "André"
        assert _guardado(casa, FONE) is None
        assert mundo.objeto(SALA, FONE)["Alias"] == "Caixa da Sala"
    finally:
        central.fechar()
        dono.fechar()


def test_o_objeto_recriado_no_mesmo_adaptador_nao_e_ela_apagando(
    diario: Path, a08: Any, casa: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O X e o «Conectar» no MESMO adaptador, sem volta dos nomes no meio, e o
    ``Alias`` do ``Pair`` recusado (o ``_dar_o_nome`` não escreve): o objeto
    novo tem o MESMO caminho do velho e nasce de fábrica. Isso não é ela
    apagando o nome — a central lembra o que o ``Pair`` deixou no objeto, e a
    volta seguinte devolve «André».

    MORDIDA: tire o ``_lembrar_o_alias`` do ``_parear_e_conferir`` — a volta lê
    o objeto recriado como o de antes voltando ao de fábrica, e apaga o nome.
    """
    mundo, relogio = rm.RadioDeMentira(), rm.Relogio()
    mundo.pareado(SALA, VERMELHO)
    bancada = Bancada(a08, monkeypatch, mundo, relogio)
    try:
        _renomear_na_tela(bancada, monkeypatch, VERMELHO, "André")
        bancada.central.cuidar_dos_nomes()
        bancada.central.cuidar_dos_nomes()
        assert _guardado(casa, VERMELHO) == "André"

        monkeypatch.setattr(bancada.central, "_dar_o_nome", lambda *_a: None)
        _esquecer_em_todos(bancada)
        _conectar_em(bancada, SALA, VERMELHO)
        assert mundo.objeto(SALA, VERMELHO)["Alias"] == FABRICA

        bancada.central.cuidar_dos_nomes()
        assert _guardado(casa, VERMELHO) == "André", "o objeto novo apagou o nome dela"
        assert mundo.objeto(SALA, VERMELHO)["Alias"] == "André"
    finally:
        bancada.fechar()


def test_o_adaptador_que_volta_com_o_nome_velho_recebe_o_dela(diario: Path, casa: Path) -> None:
    """A varanda estava fora da porta quando ela renomeou o vermelho de «André»
    para «Bia» (a tela só alcança o objeto que existe). Ela volta à porta com a
    chave e o nome de antes: o objeto que APARECE não fala por ela — ele recebe
    «Bia», e o disco continua dizendo «Bia».

    MORDIDA: conte como renomeado também o objeto que a volta nunca viu (a
    lista ``renomeados`` de ``_o_nome_que_vale`` sobre todos os objetos) — o
    nome velho volta ao disco e aos dois objetos.
    """
    mundo, relogio = rm.RadioDeMentira(), rm.Relogio()
    mundo.pareado(SALA, VERMELHO, nome="André")
    central, dono = _central_da_casa(mundo, relogio)
    try:
        central.cuidar_dos_nomes()
        assert _guardado(casa, VERMELHO) == "André"
        mundo.escrever(rm.no_de(SALA, VERMELHO), bd.APARELHO, "Alias", "s", "Bia", espera=1.0)
        central.cuidar_dos_nomes()
        assert _guardado(casa, VERMELHO) == "Bia"

        mundo.pareado(VARANDA, VERMELHO, host=False, nome="André")
        dono._fotografar()
        central.cuidar_dos_nomes()
        assert _guardado(casa, VERMELHO) == "Bia", "o adaptador que voltou trouxe o nome velho"
        assert mundo.objeto(VARANDA, VERMELHO)["Alias"] == "Bia"
        assert mundo.objeto(SALA, VERMELHO)["Alias"] == "Bia"
    finally:
        central.fechar()
        dono.fechar()


def test_o_nome_apagado_sai_tambem_do_objeto_que_ficou_com_ele(diario: Path, casa: Path) -> None:
    """Ela apaga o nome, e a escrita não alcança um dos objetos (o BlueZ recusou
    ali): o guardado sai, e o objeto que ainda dizia «André» volta ao de
    fábrica — senão a linha «Desligado» daquele adaptador mostraria o nome que
    ela apagou.

    MORDIDA: tire o ``novo = ""`` de quem ainda tinha o nome apagado, em
    ``cuidar_dos_nomes`` — a varanda fica com «André».
    """
    mundo, relogio = rm.RadioDeMentira(), rm.Relogio()
    mundo.pareado(SALA, VERMELHO, nome="André")
    mundo.pareado(VARANDA, VERMELHO, host=False, nome="André")
    central, dono = _central_da_casa(mundo, relogio)
    try:
        central.cuidar_dos_nomes()
        assert _guardado(casa, VERMELHO) == "André"
        mundo.escrever(rm.no_de(SALA, VERMELHO), bd.APARELHO, "Alias", "s", "", espera=1.0)
        central.cuidar_dos_nomes()
        assert _guardado(casa, VERMELHO) is None
        assert mundo.objeto(VARANDA, VERMELHO)["Alias"] == ""
        central.cuidar_dos_nomes()
        assert _guardado(casa, VERMELHO) is None, "o nome apagado voltou"
    finally:
        central.fechar()
        dono.fechar()


def test_o_fio_da_faxina_cuida_do_nome(diario: Path, casa: Path) -> None:
    """Ninguém chama a volta à mão no produto: é o fio da faxina, que o daemon
    sobe no arranque, que a roda.

    MORDIDA: tire o ``cuidar_dos_nomes`` de ``_faxinar_sempre`` — o nome nunca
    chega ao disco.
    """
    mundo = rm.RadioDeMentira()
    mundo.pareado(SALA, VERMELHO, nome="André")
    dono = bd.DonoVivo(mundo)
    assert dono.ligar()
    central = cr.CentralDoRadio(
        dono=dono, onde_esta=mundo.onde_esta, movimento=mundo.hz,
        esquecer_na_ponte=mundo.esquecer_na_ponte,
        sysfs={"listar": lambda _p: [], "raiz": "/nao/existe"})
    try:
        central.comecar_a_faxina(intervalo_s=0.05)
        fim = time.monotonic() + 5.0
        while _guardado(casa, VERMELHO) is None and time.monotonic() < fim:
            time.sleep(0.02)
        assert _guardado(casa, VERMELHO) == "André"
    finally:
        central.fechar(espera=2.0)
        dono.fechar()


# ---------------------------------------------------------------------------
# o campo, no dono dele (utils/maquina.py)
# ---------------------------------------------------------------------------


def test_o_nome_no_maquina_json_e_do_controle_e_nao_apaga_o_resto(casa: Path) -> None:
    """O nome entra pela fusão: o microfone e a economia do mesmo controle
    ficam; ``None`` esquece e poda (o arquivo não carrega silêncio); espaço em
    volta sai; o endereço sintetizado (``02``) e o nome maior que o ``Alias``
    não gravam — e nada disso levanta."""
    assert maquina.gravar_maquina({"controles": {rm.uniq(VERMELHO): {
        "microfone": False, "economia": True}}})
    assert maquina.gravar_o_nome_do_controle(VERMELHO.upper(), "  André  ")
    lido = maquina.carregar_maquina().controles[rm.uniq(VERMELHO)]
    assert (lido.nome, lido.microfone, lido.economia) == ("André", False, True)
    assert maquina.nomes_dos_controles(maquina.carregar_maquina()) == {
        rm.uniq(VERMELHO): "André"}

    assert maquina.gravar_o_nome_do_controle(rm.uniq(VERMELHO), "")
    documento = json.loads(casa.read_text(encoding="utf-8"))
    assert documento["controles"][rm.uniq(VERMELHO)] == {"microfone": False, "economia": True}

    assert maquina.gravar_o_nome_do_controle("02:00:1a:00:00:01", "Clone") is False
    assert maquina.gravar_o_nome_do_controle("isto não é endereço", "X") is False
    assert maquina.gravar_o_nome_do_controle(VERMELHO, "é" * 125) is False
    assert maquina.chave_do_controle("AA:BB:CC:00:00:01") == rm.uniq(VERMELHO)
    with pytest.raises(ValueError):
        maquina.ControleDeclarado(nome="x" * 249)
    assert maquina.ControleDeclarado(nome="   ").nome is None

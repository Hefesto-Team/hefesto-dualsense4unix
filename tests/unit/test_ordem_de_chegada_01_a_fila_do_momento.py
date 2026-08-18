"""ORDEM-DE-CHEGADA-01 / D-30 — o número sai da ordem de conexão do MOMENTO.

**Decisão dela, 15/08/2026 às 03:54**, depois de dar reset de fábrica nos
quatro DualSense e re-parear um a um, na ordem **vermelho, azul, branco,
roxo**:

> *"deve ser lembrado por ordem de conexão naquele momento apenas. Não uma
> imagem fixa salva por mec (…) Vermelho, deveria ser o player 1, azul, o
> player 2, branco o player 3, roxo o player 4. mas tá agora, vermelho 1,
> branco 2, roxo 3, azul 4"*

O que ela viu — `vermelho 1, branco 2, roxo 3, azul 4` — é o `controllers.json`
dela sendo obedecido à risca: a fila GRAVADA tinha essa ordem, de um dia
qualquer do passado, e a exibição saía dela. A opção (b) que ela escolheu troca
a fonte, **sem destruir o gravado**: a fila do momento manda, o gravado
desempata.

## As quatro garantias, e por que cada uma tem mordida própria

Esta decisão reverte em parte DUAS medições desta casa (R-15, de 23/07, e
R-23, de 25/07 — as duas escritas no cabeçalho de `daemon/subsystems/
identity.py`). Ela foi escolhida porque paga zero do preço delas, e é
exatamente esse "zero" que os testes daqui existem para cobrar:

1. **o número segue a ordem de conexão daquele momento** —
   `TestOCasoDela`, com a mesa dela sem tradução;
2. **a ordem CONGELA quando a mesa fica estável** — `TestCongelarEGravar`.
   Congelar, aqui, é *gravar*: a ordem do momento é escrita na fila
   persistida, e por isso sobrevive ao restart (R-23);
3. **quem cai e volta recupera o número** — `TestQuemCaiEVolta`, que é o
   cenário literal de R-15 ("desligar os dois DualSense e religar em ordem
   invertida devolvia o 1 ao que voltasse primeiro");
4. **o gravado sobrevive como DESEMPATE, não como fonte primária** —
   `TestOGravadoEDesempate`.

## O que este arquivo NÃO prova

Que a ordem do momento é a resposta certa: isso é decisão dela, tomada, e não
se mede em teste. E não prova nada sobre a mesa com externo ligado além do
invariante de contagem (`TestAMesaMistaContinuaFechando`) — o mapa completo
com Pro Controller e 8BitDo continua sem medição, como a sprint declara.

Nenhum endereço real: faixa forjada `aa:bb:cc:…`, octetos 4 e 5 zerados, a
mesma allowlist de `test_anonimato_de_fixtures.py`. A ORDEM reproduz a mesa
dela; os bytes, não.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from hefesto_dualsense4unix.daemon.subsystems import external_identity as ei_mod
from hefesto_dualsense4unix.daemon.subsystems import identity as id_mod
from hefesto_dualsense4unix.daemon.subsystems.external_identity import (
    ExternalIdentityRegistry,
    ExternalLedSync,
)
from hefesto_dualsense4unix.daemon.subsystems.identity import (
    JANELA_MESA_ESTAVEL_SEC,
    ControllerIdentityRegistry,
    make_auto_output_provider,
)

# --- a mesa dela, mascarada -------------------------------------------------

VERMELHO = "aabbcc000001"
AZUL = "aabbcc000002"
BRANCO = "aabbcc000003"
ROXO = "aabbcc000004"
MAC_EXTERNO = "aabbcc0000fe"

#: A ordem em que ELA conectou, às 03:39, 03:41, 03:45 e 03:47.
ORDEM_DE_CONEXAO = (VERMELHO, AZUL, BRANCO, ROXO)

#: O que ela PEDIU, que é a ordem de conexão numerada 1..4.
O_QUE_ELA_PEDIU = {VERMELHO: 1, AZUL: 2, BRANCO: 3, ROXO: 4}

#: A fila GRAVADA no `controllers.json` dela — a de um dia qualquer do
#: passado. É esta ordem que produzia a queixa "vermelho 1, branco 2, roxo 3,
#: azul 4", e é ela que continua no disco: não se destrói o gravado, ele vira
#: desempate.
FILA_GRAVADA = {VERMELHO: 1, BRANCO: 2, ROXO: 3, AZUL: 4}

#: O que o produto exibia antes desta entrega — a queixa dela, em quatro
#: inteiros. Com a fila do momento arrancada, é aqui que os testes voltam.
O_QUE_ELA_VIU = dict(FILA_GRAVADA)

BOOT = "boot-teste-ordem-de-chegada"


class Relogio:
    """Relógio monotônico de mentira — move o tempo sem dormir um segundo.

    A entrega inteira tem duas janelas de tempo (a ONDA de chegada e a
    ESTABILIDADE da mesa) e nenhuma delas pode ser medida com `sleep`: um
    teste de 4 segundos por caso é um teste que ninguém roda. O registro
    aceita o relógio injetado só por isto.
    """

    def __init__(self, inicio: float = 1000.0) -> None:
        self.agora = inicio

    def __call__(self) -> float:
        return self.agora

    def avancar(self, segundos: float) -> None:
        self.agora += segundos


@pytest.fixture
def config_isolado(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """`config_dir` em tmp + âncora fixa nos DOIS registros (mesmo arquivo)."""
    from hefesto_dualsense4unix.utils import xdg_paths

    def fake_config_dir(ensure: bool = False) -> Path:
        if ensure:
            tmp_path.mkdir(parents=True, exist_ok=True)
        return tmp_path

    monkeypatch.setattr(xdg_paths, "config_dir", fake_config_dir)
    monkeypatch.setattr(id_mod, "_read_boot_id", lambda: BOOT)
    monkeypatch.setattr(ei_mod, "_read_boot_id", lambda: BOOT)
    return tmp_path


def gravar_a_fila_dela(tmp: Path, fila: dict[str, int] | None = None) -> None:
    """Escreve o `controllers.json` no schema vivo, com a fila gravada dela."""
    (tmp / "controllers.json").write_text(
        json.dumps(
            {
                "version": id_mod.CONTROLLERS_SCHEMA_VERSION,
                "boot_id": BOOT,
                id_mod.ORDER_FIELD: [
                    {"addr": addr, "kind": id_mod.KIND_DUALSENSE, "rank": rank}
                    for addr, rank in (fila or FILA_GRAVADA).items()
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def fila_no_disco(tmp: Path) -> dict[str, int]:
    """Endereço → lugar na fila, lidos do arquivo (o que atravessa o restart)."""
    dados = json.loads((tmp / "controllers.json").read_text(encoding="utf-8"))
    return {
        str(e["addr"]): int(e["rank"])
        for e in dados[id_mod.ORDER_FIELD]
        if e.get("kind") == id_mod.KIND_DUALSENSE
    }


def numeros(reg: ControllerIdentityRegistry, *uniqs: str) -> dict[str, int | None]:
    """Os números EXIBIDOS agora — leitura pura, sem mexer na presença."""
    return {uniq: reg.slot_for(uniq, assign=False) for uniq in uniqs}


def conectar_um_a_um(
    reg: ControllerIdentityRegistry,
    relogio: Relogio,
    ordem: tuple[str, ...] = ORDEM_DE_CONEXAO,
    intervalo: float = 60.0,
) -> None:
    """A mesa dela sendo montada: um controle de cada vez, minutos entre eles.

    `intervalo` é generoso de propósito — ela levou de dois a quatro minutos
    entre cada pareamento. O que o registro precisa é só que cada chegada caia
    numa ONDA própria (`JANELA_DE_ONDA_SEC`); o resto do tempo é realismo.
    """
    na_mesa: list[str] = []
    for uniq in ordem:
        na_mesa.append(uniq)
        reg.sync_connected(list(na_mesa))
        relogio.avancar(intervalo)


class TestOCasoDela:
    """MORDIDA 1 — o caso dela, sem tradução: quatro controles, uma ordem.

    Arrancar a fila do momento (ordenar por `rank`, como antes de D-30) faz
    todo este bloco voltar para `O_QUE_ELA_VIU`, que é a queixa de 03:54.
    """

    def test_a_fila_gravada_e_a_queixa_dela(self, config_isolado: Path) -> None:
        """Ancoragem: sem isto, o resto do arquivo não prova nada.

        A fila gravada dela, sozinha, produz exatamente os quatro números da
        queixa. Se esta montagem deixar de reproduzir a queixa, os testes
        abaixo passam a medir outra coisa.
        """
        gravar_a_fila_dela(config_isolado)
        reg = ControllerIdentityRegistry(clock=Relogio())
        reg.load()
        assert reg.snapshot() == FILA_GRAVADA
        # Todos vistos na MESMA olhada: sem informação de ordem, a exibição é
        # a gravada — e a gravada é a queixa.
        reg.sync_connected(list(ORDEM_DE_CONEXAO))
        assert numeros(reg, *ORDEM_DE_CONEXAO) == O_QUE_ELA_VIU

    def test_o_numero_segue_a_ordem_de_conexao_do_momento(
        self, config_isolado: Path
    ) -> None:
        """A mordida principal: vermelho 1, azul 2, branco 3, roxo 4.

        Falha-sem: com a exibição saindo do `rank`, saem os quatro números de
        `O_QUE_ELA_VIU` — o produto funcionando como projetado e contrariando
        a decisão dela.
        """
        gravar_a_fila_dela(config_isolado)
        relogio = Relogio()
        reg = ControllerIdentityRegistry(clock=relogio)
        reg.load()
        conectar_um_a_um(reg, relogio)
        assert numeros(reg, *ORDEM_DE_CONEXAO) == O_QUE_ELA_PEDIU

    def test_a_ordem_do_momento_nao_repete_nem_pula_numero(
        self, config_isolado: Path
    ) -> None:
        """A cada controle que entra, a mesa exibe exatamente 1..N.

        O critério que resume NUM-01 ("nunca existe um jogador 2 sem um
        jogador 1") não pode ser vítima da troca de fonte: ele vale a cada
        passo da montagem, não só no fim.
        """
        gravar_a_fila_dela(config_isolado)
        relogio = Relogio()
        reg = ControllerIdentityRegistry(clock=relogio)
        reg.load()
        na_mesa: list[str] = []
        for uniq in ORDEM_DE_CONEXAO:
            na_mesa.append(uniq)
            reg.sync_connected(list(na_mesa))
            exibidos = sorted(v for v in numeros(reg, *na_mesa).values() if v)
            assert exibidos == list(range(1, len(na_mesa) + 1)), (
                f"mesa de {len(na_mesa)} exibiu {exibidos}"
            )
            relogio.avancar(60.0)

    def test_quem_chega_depois_entra_no_fim_e_nao_no_meio(
        self, config_isolado: Path
    ) -> None:
        """Um quinto controle chegando não empurra ninguém para cima.

        É o outro lado da promessa: a ordem é de CHEGADA, então quem chega
        por último é o último — mesmo tendo lugar baixo no gravado.
        """
        gravar_a_fila_dela(config_isolado, {ROXO: 1, VERMELHO: 2})
        relogio = Relogio()
        reg = ControllerIdentityRegistry(clock=relogio)
        reg.load()
        reg.sync_connected([VERMELHO])
        relogio.avancar(60.0)
        reg.sync_connected([VERMELHO, ROXO])
        # O roxo tem o lugar 1 no gravado e mesmo assim chega em segundo.
        assert numeros(reg, VERMELHO, ROXO) == {VERMELHO: 1, ROXO: 2}


class TestCongelarEGravar:
    """MORDIDA 2 — a ordem congela quando a mesa fica estável, e congelar é GRAVAR.

    O critério de "mesa estável" é `JANELA_MESA_ESTAVEL_SEC` sem ninguém
    entrar nem sair. Enquanto a mesa se mexe, a fila gravada NÃO é tocada
    (ela ainda é o desempate de quem chegar junto); quando estabiliza, a
    ordem do momento é escrita nela — e é por isso que sobrevive ao restart
    do daemon, que é a promessa de R-23.

    Arrancar o critério (congelar na hora) derruba
    `test_enquanto_a_mesa_se_mexe_o_gravado_nao_e_tocado`; arrancar o
    congelamento derruba os outros três.
    """

    def montar(self, tmp: Path) -> tuple[ControllerIdentityRegistry, Relogio]:
        gravar_a_fila_dela(tmp)
        relogio = Relogio()
        reg = ControllerIdentityRegistry(clock=relogio)
        reg.load()
        conectar_um_a_um(reg, relogio, intervalo=1.0)
        return reg, relogio

    def test_enquanto_a_mesa_se_mexe_o_gravado_nao_e_tocado(
        self, config_isolado: Path
    ) -> None:
        """Mesa em montagem: exibe a ordem do momento, grava a antiga.

        Nove segundos de relógio se passam nesta montagem — mais que a janela
        de estabilidade — e mesmo assim nada congela, porque a cada passo
        alguém entrou. Congelar uma mesa em movimento é gravar meia mesa.
        """
        gravar_a_fila_dela(config_isolado)
        relogio = Relogio()
        reg = ControllerIdentityRegistry(clock=relogio)
        reg.load()
        conectar_um_a_um(reg, relogio, intervalo=3.0)
        assert not reg.mesa_congelada()
        assert reg.snapshot() == FILA_GRAVADA
        assert fila_no_disco(config_isolado) == FILA_GRAVADA
        # …e a exibição já é a dela, mesmo com o gravado intacto.
        assert numeros(reg, *ORDEM_DE_CONEXAO) == O_QUE_ELA_PEDIU

    def test_a_mesa_parada_congela_e_a_ordem_do_momento_vira_a_gravada(
        self, config_isolado: Path
    ) -> None:
        """A mordida: um tick depois da janela, a fila gravada é a dela."""
        reg, relogio = self.montar(config_isolado)
        assert not reg.mesa_congelada()
        relogio.avancar(JANELA_MESA_ESTAVEL_SEC)
        reg.sync_connected(list(ORDEM_DE_CONEXAO))  # o tick lento, sem novidade
        assert reg.mesa_congelada()
        assert reg.snapshot() == O_QUE_ELA_PEDIU
        assert fila_no_disco(config_isolado) == O_QUE_ELA_PEDIU
        # Congelar não mexe em número nenhum na tela: a exibição já era esta.
        assert numeros(reg, *ORDEM_DE_CONEXAO) == O_QUE_ELA_PEDIU

    def test_o_congelado_atravessa_o_restart_do_daemon(
        self, config_isolado: Path
    ) -> None:
        """R-23 continua de pé — e agora com a ordem QUE ELA PEDIU.

        O daemon novo não tem fila do momento nenhuma (ela é da sessão): os
        quatro chegam na MESMA olhada, e é o gravado que responde. Se o
        congelamento não tivesse acontecido, o restart devolveria a queixa de
        03:54.
        """
        reg, relogio = self.montar(config_isolado)
        relogio.avancar(JANELA_MESA_ESTAVEL_SEC)
        reg.sync_connected(list(ORDEM_DE_CONEXAO))

        reiniciado = ControllerIdentityRegistry(clock=Relogio())
        reiniciado.load()
        assert reiniciado.snapshot_chegada() == {}, "sessão nova não herda fila"
        reiniciado.sync_connected(list(reversed(ORDEM_DE_CONEXAO)))
        assert numeros(reiniciado, *ORDEM_DE_CONEXAO) == O_QUE_ELA_PEDIU

    def test_congelar_nao_muda_o_conjunto_de_postos(
        self, config_isolado: Path
    ) -> None:
        """A trava que impede a janela de DUPLICATA que R-15 mediu.

        Congelar é uma PERMUTAÇÃO: os postos que os presentes ocupam são os
        mesmos antes e depois, só troca o dono de cada um. Nenhum posto some
        e nenhum vale 0 no meio do caminho — que era exatamente o buraco por
        onde `_ds_reserve()` lia piso 0 e nasciam "dois player 1".
        """
        reg, relogio = self.montar(config_isolado)
        antes = set(reg.snapshot().values())
        piso_antes = max(reg.snapshot().values())
        relogio.avancar(JANELA_MESA_ESTAVEL_SEC)
        reg.sync_connected(list(ORDEM_DE_CONEXAO))
        assert set(reg.snapshot().values()) == antes == {1, 2, 3, 4}
        assert max(reg.snapshot().values()) == piso_antes
        assert reg.present_ranks() == antes


class TestQuemCaiEVolta:
    """MORDIDA 3 — a garantia de R-15, que não pode regredir.

    R-15 (23/07) arrancou a renumeração por ORDEM DE WAKE porque *"desligar
    os dois DualSense e religar em ordem invertida devolvia o 1 ao que
    voltasse primeiro"*. A opção (b) só foi escolhível porque não paga esse
    preço: a marca de chegada de uma sessão NUNCA é solta, então voltar não é
    chegar.

    Arrancar a idempotência de `_marcar_chegada_locked` (recarimbar quem
    volta) derruba os três casos daqui — e derruba junto os testes de replug
    de `test_identity_registry.py` e `test_num01_quem_esta_na_mesa.py`, que
    são as mordidas originais de R-15/D2.
    """

    def mesa_de_dois(self, tmp: Path) -> tuple[ControllerIdentityRegistry, Relogio]:
        """Vermelho e azul, nesta ordem de conexão, mesa já congelada."""
        gravar_a_fila_dela(tmp, {AZUL: 1, VERMELHO: 2})
        relogio = Relogio()
        reg = ControllerIdentityRegistry(clock=relogio)
        reg.load()
        conectar_um_a_um(reg, relogio, ordem=(VERMELHO, AZUL))
        relogio.avancar(JANELA_MESA_ESTAVEL_SEC)
        reg.sync_connected([VERMELHO, AZUL])
        assert numeros(reg, VERMELHO, AZUL) == {VERMELHO: 1, AZUL: 2}
        return reg, relogio

    def test_religar_em_ordem_invertida_nao_troca_o_dono_do_1(
        self, config_isolado: Path
    ) -> None:
        """O cenário LITERAL de R-15, com o relógio andando entre as pontas."""
        reg, relogio = self.mesa_de_dois(config_isolado)
        reg.sync_connected([])  # "desliguei os dois pra jantar"
        relogio.avancar(600.0)
        reg.sync_connected([AZUL])  # o azul acorda PRIMEIRO
        relogio.avancar(30.0)
        reg.sync_connected([AZUL, VERMELHO])
        assert numeros(reg, VERMELHO, AZUL) == {VERMELHO: 1, AZUL: 2}

    def test_a_cor_automatica_tambem_nao_troca_de_dono(
        self, config_isolado: Path
    ) -> None:
        """A queixa de R-15 era sobre COR e número — os dois saem daqui.

        A cor é lida pelo provider de PRODUÇÃO (`make_auto_output_provider`),
        o mesmo que o backend chama no reconcile: se o número trocar de dono,
        a cor troca junto e o teste cai.
        """
        reg, relogio = self.mesa_de_dois(config_isolado)
        provider = make_auto_output_provider(reg)
        antes = {uniq: provider(uniq).led for uniq in (VERMELHO, AZUL)}  # type: ignore[union-attr]

        reg.sync_connected([])
        relogio.avancar(600.0)
        reg.sync_connected([AZUL])
        relogio.avancar(30.0)
        reg.sync_connected([AZUL, VERMELHO])

        depois = {uniq: provider(uniq).led for uniq in (VERMELHO, AZUL)}  # type: ignore[union-attr]
        assert depois == antes
        assert antes[VERMELHO] != antes[AZUL], "as duas cores têm de ser distintas"

    def test_o_replug_no_meio_da_partida_devolve_o_mesmo_numero(
        self, config_isolado: Path
    ) -> None:
        """Mesa de quatro, congelada: um cai e volta, e nada se mexe.

        É a pergunta que a sprint deixou para ela (*"o que acontece com um
        replug no meio da partida?"*) respondida em código: nada acontece.
        E, enquanto o azul está fora, os três que ficaram fecham 1..3 sem
        buraco — a compactação automática do NUM-01 continua valendo.
        """
        gravar_a_fila_dela(config_isolado)
        relogio = Relogio()
        reg = ControllerIdentityRegistry(clock=relogio)
        reg.load()
        conectar_um_a_um(reg, relogio)
        relogio.avancar(JANELA_MESA_ESTAVEL_SEC)
        reg.sync_connected(list(ORDEM_DE_CONEXAO))

        sobraram = [VERMELHO, BRANCO, ROXO]
        reg.sync_connected(sobraram)  # o azul caiu
        assert numeros(reg, *sobraram) == {VERMELHO: 1, BRANCO: 2, ROXO: 3}

        relogio.avancar(20.0)
        reg.sync_connected(list(ORDEM_DE_CONEXAO))  # e voltou
        assert numeros(reg, *ORDEM_DE_CONEXAO) == O_QUE_ELA_PEDIU

    def test_volta_recupera_o_lugar_mesmo_sem_a_mesa_ter_congelado(
        self, config_isolado: Path
    ) -> None:
        """A promessa não depende do congelamento — nem podia.

        Um flap de rádio nos primeiros segundos é justamente quando a mesa
        ainda não estabilizou. Se a marca de chegada fosse solta nessa
        janela, o defeito de ORDEM DE WAKE voltaria pela porta dos fundos, no
        pior momento possível.
        """
        gravar_a_fila_dela(config_isolado, {AZUL: 1, VERMELHO: 2})
        relogio = Relogio()
        reg = ControllerIdentityRegistry(clock=relogio)
        reg.load()
        reg.sync_connected([VERMELHO])
        relogio.avancar(1.0)
        reg.sync_connected([VERMELHO, AZUL])
        relogio.avancar(1.0)
        reg.sync_connected([AZUL])  # flap: o vermelho pisca fora
        relogio.avancar(1.0)
        reg.sync_connected([AZUL, VERMELHO])
        assert not reg.mesa_congelada()
        assert numeros(reg, VERMELHO, AZUL) == {VERMELHO: 1, AZUL: 2}


class TestOGravadoEDesempate:
    """MORDIDA 4 — o gravado sobrevive como desempate, não como fonte.

    Dois controles vistos na MESMA olhada para a mesa chegaram juntos, para a
    casa: aí o registro não inventa ordem, ele lê a que já tinha. Vistos em
    olhadas DIFERENTES, o gravado perde.

    Arrancar a onda (dar uma onda própria a cada chegada, mesmo dentro da
    mesma olhada) derruba `test_quem_chega_na_mesma_olhada_e_desempatado_pelo_
    gravado`: a ordem passaria a sair da iteração de `describe_controllers`,
    que é ordem de enumeração do backend, não de conexão.
    """

    def test_quem_chega_na_mesma_olhada_e_desempatado_pelo_gravado(
        self, config_isolado: Path
    ) -> None:
        """Uma olhada só, entregue na ordem CONTRÁRIA à gravada."""
        gravar_a_fila_dela(config_isolado, {VERMELHO: 1, AZUL: 2})
        reg = ControllerIdentityRegistry(clock=Relogio())
        reg.load()
        reg.sync_connected([AZUL, VERMELHO])  # a ordem do iterável não decide
        assert numeros(reg, VERMELHO, AZUL) == {VERMELHO: 1, AZUL: 2}

    def test_em_olhadas_diferentes_o_gravado_perde(
        self, config_isolado: Path
    ) -> None:
        """A mesma dupla, o mesmo gravado — e a ordem do momento vencendo.

        O par com o teste acima é o que prova que o gravado é DESEMPATE: ele
        só é consultado quando a fila do momento não tem opinião.
        """
        gravar_a_fila_dela(config_isolado, {VERMELHO: 1, AZUL: 2})
        relogio = Relogio()
        reg = ControllerIdentityRegistry(clock=relogio)
        reg.load()
        reg.sync_connected([AZUL])
        relogio.avancar(60.0)
        reg.sync_connected([AZUL, VERMELHO])
        assert numeros(reg, VERMELHO, AZUL) == {VERMELHO: 2, AZUL: 1}

    def test_o_restart_com_a_mesa_cheia_nao_embaralha_nada(
        self, config_isolado: Path
    ) -> None:
        """R-23 em uma linha: reiniciar o daemon não renumera ninguém.

        Era a queixa de 25/07 (*"ao abrir os jogos ou o perfil, os controles
        se reenumeram e nunca sei o que é o quê"*). Com os quatro já ligados,
        o daemon novo vê todos na primeira olhada — uma onda só — e o gravado
        responde inteiro, em qualquer ordem de entrega.
        """
        gravar_a_fila_dela(config_isolado, O_QUE_ELA_PEDIU)
        for entrega in (
            list(ORDEM_DE_CONEXAO),
            list(reversed(ORDEM_DE_CONEXAO)),
            [BRANCO, VERMELHO, ROXO, AZUL],
        ):
            reg = ControllerIdentityRegistry(clock=Relogio())
            reg.load()
            reg.sync_connected(entrega)
            assert numeros(reg, *ORDEM_DE_CONEXAO) == O_QUE_ELA_PEDIU, entrega

    def test_a_fila_gravada_continua_existindo_e_sendo_salva(
        self, config_isolado: Path
    ) -> None:
        """"Não destruir o gravado" é literal: o arquivo continua completo.

        Inclusive as entradas de quem NÃO está na mesa — a promessa D2 (o
        ausente não perde o lugar) não foi tocada por D-30.
        """
        gravar_a_fila_dela(config_isolado)
        relogio = Relogio()
        reg = ControllerIdentityRegistry(clock=relogio)
        reg.load()
        conectar_um_a_um(reg, relogio, ordem=(VERMELHO, AZUL))
        relogio.avancar(JANELA_MESA_ESTAVEL_SEC)
        reg.sync_connected([VERMELHO, AZUL])
        no_disco = fila_no_disco(config_isolado)
        assert set(no_disco) == set(FILA_GRAVADA), "ninguém foi dropado"
        # Os dois ausentes seguem com os lugares que tinham; só os PRESENTES
        # foram permutados entre si.
        assert no_disco[BRANCO] == FILA_GRAVADA[BRANCO]
        assert no_disco[ROXO] == FILA_GRAVADA[ROXO]
        assert (no_disco[VERMELHO], no_disco[AZUL]) == (1, 4)


class TestALampadaEORotuloSeguemJuntos:
    """A união da MESA-CHEIA-12 não se desfaz — ela só muda de fila.

    A cura de 15/08 01h00 pôs `player_indexes()` (o rótulo do card, do
    `state_full`, da CLI) para sair de `numeros_de_jogador()`, a MESMA função
    que escolhe o desenho da lâmpada. D-30 trocou a FONTE dessa função sem
    tocar na união: os dois continuam sendo o mesmo inteiro do mesmo MAC.

    O `player_index` do co-op é montado aqui de propósito numa ordem
    DIFERENTE da de conexão (o grab confirma na ordem que quiser): se o
    número publicado voltasse a sair dele, este teste cai.
    """

    def montar(self, tmp: Path) -> object:
        from hefesto_dualsense4unix.daemon.subsystems.coop import (
            CoopManager,
            _SecondaryPlayer,
        )

        gravar_a_fila_dela(tmp)
        relogio = Relogio()
        reg = ControllerIdentityRegistry(clock=relogio)
        reg.load()
        conectar_um_a_um(reg, relogio)

        coop = CoopManager.__new__(CoopManager)
        coop._daemon = SimpleNamespace(  # type: ignore[assignment]
            identity_registry=reg,
            controller=SimpleNamespace(primary_uniq=VERMELHO),
        )
        coop._players = {
            mac: _SecondaryPlayer(
                identity=mac,
                evdev_path=f"/dev/input/event{200 + i}",
                reader=None,  # type: ignore[arg-type]
                player_index=i + 2,
                vpad=object(),  # type: ignore[arg-type]
            )
            # a ordem em que o grab confirmou — de propósito diferente da de
            # conexão, que é a que ela pediu.
            for i, mac in enumerate((ROXO, AZUL, BRANCO))
        }
        return coop

    def test_o_numero_publicado_e_o_da_ordem_de_conexao(
        self, config_isolado: Path
    ) -> None:
        coop = self.montar(config_isolado)
        assert coop.numeros_de_jogador() == O_QUE_ELA_PEDIU  # type: ignore[attr-defined]
        assert coop.player_indexes() == O_QUE_ELA_PEDIU  # type: ignore[attr-defined]

    def test_a_lampada_e_o_rotulo_continuam_sendo_a_mesma_funcao(
        self, config_isolado: Path
    ) -> None:
        """MESA-CHEIA-12 em uma linha — e sem número repetido na mesa."""
        coop = self.montar(config_isolado)
        publicado = coop.player_indexes()  # type: ignore[attr-defined]
        assert publicado == coop.numeros_de_jogador()  # type: ignore[attr-defined]
        assert sorted(publicado.values()) == [1, 2, 3, 4]


class TestAMesaMistaContinuaFechando:
    """A mesa com externo continua exibindo 1..N — sem buraco, sem repetição.

    A fila é ÚNICA entre DualSense e externos, e a permutação da ordem do
    momento acontece DENTRO dos postos que os DualSense presentes já ocupam:
    o conjunto que o lado externo lê (`present_ranks`) não se mexe. Este teste
    é a prova de que a troca de fonte não vazou para o outro registro.
    """

    def test_1_a_n_com_um_externo_na_mesa(self, config_isolado: Path) -> None:
        gravar_a_fila_dela(config_isolado, {VERMELHO: 1, AZUL: 2})
        relogio = Relogio()
        ds = ControllerIdentityRegistry(clock=relogio)
        ext = ExternalIdentityRegistry()
        ds.set_external_reserve_provider(lambda: set(ext.snapshot().values()))
        ExternalLedSync(SimpleNamespace(identity_registry=ds), ext)
        ds.load()

        # O azul chega primeiro (contra o gravado), depois o vermelho, e o
        # externo entra por último.
        ds.sync_connected([AZUL])
        relogio.avancar(60.0)
        ds.sync_connected([AZUL, VERMELHO])
        piso = max(ds.snapshot().values())
        ext.sync_connected([MAC_EXTERNO])
        exibidos = [ds.slot_for(u, assign=False) for u in (AZUL, VERMELHO)]
        exibidos.append(ext.slot_for(MAC_EXTERNO, reserve=piso))
        assert exibidos == [1, 2, 3]

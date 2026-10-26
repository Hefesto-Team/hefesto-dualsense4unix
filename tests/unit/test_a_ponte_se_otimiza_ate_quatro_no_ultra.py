"""A-PONTE-SE-OTIMIZA-ATE-QUATRO-NO-ULTRA-NUM-ADAPTADOR-01: o limite de pontes sai da capacidade.

O ``n_max`` de cada adaptador é ``piso((C_eff - 250 x n) / custo da ponte)``, nunca acima do teto
que sobreviveu na bancada (``N_MAX_PONTES``); o degrau do meio cede a TAXA da ponte de vibração
antes de cortar qualquer ponte inteira; o chip do mapa do rádio diz N/M com a mesma conta. Régua
pura, sobre a tabela sintética e a gravada da ``A-PONTE-SE-CONTA-EM-FATIAS-NO-AR-01``.

MORDIDAS (arrancar, ver reprovar, devolver):

1. ``ordem_de_ceder`` sem o laço do degrau (o corte direto) reprova o ``test_5``.
2. ``n_max_pela_capacidade`` devolvendo o ``teto`` fixo reprova o ``test_1``.
3. ``n_max_pela_capacidade`` sem o ``min(teto, ...)`` (uma terceira ponte onde a conta não deixa)
   reprova o ``test_1`` e o ``test_7``.
4. O ``mockup/mapa-do-radio.html`` de antes (o chip N/2 fixo) reprova o ``test_8``.
5. O ``GovernadorDoRadio._n_max_de`` devolvendo ``self.n_max`` reprova o ``test_4``.
"""
from __future__ import annotations

import importlib.util
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from hefesto_dualsense4unix.core import ds_output_report as rep
from hefesto_dualsense4unix.daemon.subsystems import governador_do_radio as gov
from hefesto_dualsense4unix.integrations import alto_falante_bt as af
from hefesto_dualsense4unix.integrations import ar_do_adaptador as ar
from hefesto_dualsense4unix.integrations import radio_da_mesa as rm

RAIZ = Path(__file__).resolve().parents[2]
MAPA = RAIZ / "mockup" / "mapa-do-radio.html"
SINTETICAS = RAIZ / "tests" / "fixtures" / "a_ponte_em_fatias_no_ar" / "janelas-sinteticas.json"

ADAPTADOR_A = "aa:bb:cc:00:00:0a"
ADAPTADOR_B = "aa:bb:cc:00:00:0b"


def _carregar(nome: str) -> ModuleType:
    caminho = RAIZ / "scripts" / "ensaios" / f"{nome}.py"
    spec = importlib.util.spec_from_file_location(f"_otimiza_{nome}", caminho)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


fatias = _carregar("a_ponte_em_fatias_no_ar")
dois = _carregar("a_ponte_com_dois_quadros")


def _pela_formula(controles: int, ar_: float, custo: float) -> int:
    return max(0, min(rm.N_MAX_PONTES, math.floor((ar_ - 250 * controles) / custo)))


@pytest.mark.parametrize(
    ("controles", "c_eff", "custo", "esperado"),
    [
        (4, rm.AR_DO_ADAPTADOR_PORTA_DIRETA, 187.5, 2),
        (4, rm.AR_DO_ADAPTADOR_ATRAS_DO_HUB, 187.5, 1),
        (4, rm.AR_DO_ADAPTADOR_PORTA_DIRETA, 375.0, 1),
        (2, 849.0, 187.5, 1),
        (1, rm.AR_DO_ADAPTADOR_PORTA_DIRETA, 187.5, 2),
        (4, 1000.0, 187.5, 0),
    ],
)
def test_1_o_n_max_sai_da_capacidade_e_para_no_teto(
    controles: int, c_eff: float, custo: float, esperado: int
) -> None:
    obtido = rm.n_max_pela_capacidade(controles, ar=c_eff, custo=custo)
    assert obtido == esperado == _pela_formula(controles, c_eff, custo)


def test_1b_a_tabela_sintetica_e_a_gravada_dao_o_m_da_formula() -> None:
    linhas = fatias.tabela(fatias.ler_janelas(SINTETICAS))
    assert fatias.pontes_que_cabem(linhas, 4) == {"1": 2, "2": 0}
    assert fatias.pontes_que_cabem(linhas, 2) == {"1": 2, "2": 2}
    gravada = fatias.gravada()
    if gravada is None:
        return
    gravadas = fatias.tabela(gravada)
    for adaptador, m in fatias.pontes_que_cabem(gravadas, 4).items():
        dele = [li for li in gravadas if li.adaptador == adaptador]
        c_eff = sum(li.entrada_saturada for li in dele) / len(dele)
        custos = [li.custo_por_ponte for li in dele if li.pontes and li.custo_por_ponte]
        assert m == _pela_formula(4, c_eff, sum(custos) / len(custos))


def test_2_o_interruptor_desligado_devolve_o_teto(monkeypatch: pytest.MonkeyPatch) -> None:
    assert rm.N_MAX_PELA_CAPACIDADE is False, "liga só depois da bancada medir o custo da ponte"
    assert rm.n_max_do_adaptador(4, ar=rm.AR_DO_ADAPTADOR_ATRAS_DO_HUB) == rm.N_MAX_PONTES
    assert rm.n_max_do_adaptador(4, ligado=True, ar=rm.AR_DO_ADAPTADOR_ATRAS_DO_HUB) == 1
    monkeypatch.setattr(rm, "N_MAX_PELA_CAPACIDADE", True)
    monkeypatch.setattr(rm, "AR_DO_ADAPTADOR_PORTA_DIRETA", rm.AR_DO_ADAPTADOR_ATRAS_DO_HUB)
    assert rm.n_max_do_adaptador(4) == 1, "a constante trocada vale na hora"


def test_3_o_orcamento_publica_o_m_de_cada_adaptador(monkeypatch: pytest.MonkeyPatch) -> None:
    controles = [
        {"transport": "bt", "uniq": f"aa:bb:cc:00:00:{i:02x}", "adaptador": ADAPTADOR_A}
        for i in range(1, 5)
    ] + [{"transport": "bt", "uniq": "aa:bb:cc:00:00:11", "adaptador": ADAPTADOR_B}]

    def _orcamento() -> dict[str, int]:
        saida = rm.orcamento_por_adaptador(controles, listar=lambda _r: [])
        return {e: o.n_max for e, o in saida.items()}

    assert _orcamento() == {ADAPTADOR_A: 2, ADAPTADOR_B: 2}
    monkeypatch.setattr(rm, "N_MAX_PELA_CAPACIDADE", True)
    monkeypatch.setattr(rm, "AR_DO_ADAPTADOR_PORTA_DIRETA", rm.AR_DO_ADAPTADOR_ATRAS_DO_HUB)
    assert _orcamento() == {ADAPTADOR_A: 1, ADAPTADOR_B: 2}


@dataclass
class _DoisAdaptadores:
    controles_em_a: int

    def amostrar(self) -> dict[str, ar.ArDoAdaptador]:
        def enlaces(n: int, base: int) -> tuple[ar.Enlace, ...]:
            return tuple(
                ar.Enlace(handle=base + i, endereco=f"02:fe:00:00:00:{base + i:02x}",
                          tipo=ar.TIPO_ACL, saida=False, estado=1, link_mode=0)
                for i in range(n)
            )

        return {
            e: ar.ArDoAdaptador(hci=h, endereco=e, entrada_por_s=700.0, saida_por_s=90.0,
                                janela_s=gov.PERIODO_S, conexoes=enlaces(n, 16 * h))
            for h, (e, n) in enumerate(((ADAPTADOR_A, self.controles_em_a), (ADAPTADOR_B, 0)))
        }


def _governador() -> gov.GovernadorDoRadio:
    governador = gov.GovernadorDoRadio(
        medidor=_DoisAdaptadores(controles_em_a=4), adaptador_de=lambda _u: ADAPTADOR_A,
        registrar=lambda *_a, **_k: None, relogio=lambda: 1000.0,
    )
    governador.tique()
    return governador


def test_4_o_governador_le_o_m_do_adaptador(monkeypatch: pytest.MonkeyPatch) -> None:
    desligado = _governador()
    for uniq in ("aa:bb:cc:00:00:01", "aa:bb:cc:00:00:02"):
        assert isinstance(desligado.pedir_vaga(uniq, "som"), gov.Vaga)

    monkeypatch.setattr(rm, "N_MAX_PELA_CAPACIDADE", True)
    monkeypatch.setattr(rm, "AR_DO_ADAPTADOR_PORTA_DIRETA", rm.AR_DO_ADAPTADOR_ATRAS_DO_HUB)
    governador = _governador()
    primeira = governador.pedir_vaga("aa:bb:cc:00:00:01", "som")
    assert isinstance(primeira, gov.Vaga)
    primeira.subiu()
    segunda = governador.pedir_vaga("aa:bb:cc:00:00:02", "som")
    assert isinstance(segunda, gov.Recusa), "quatro controles atrás do hub comportam UMA ponte"
    assert segunda.n_max == 1
    assert governador.publicar()[ADAPTADOR_A]["n_max"] == 1


@dataclass
class _ControlesPorAdaptador:
    em_a: int
    em_b: int

    def amostrar(self) -> dict[str, ar.ArDoAdaptador]:
        return {
            e: ar.ArDoAdaptador(
                hci=h, endereco=e, entrada_por_s=700.0, saida_por_s=90.0, janela_s=gov.PERIODO_S,
                conexoes=tuple(
                    ar.Enlace(handle=16 * h + i, endereco=f"02:fe:00:00:00:{16 * h + i:02x}",
                              tipo=ar.TIPO_ACL, saida=False, estado=1, link_mode=0)
                    for i in range(n)))
            for h, (e, n) in enumerate(((ADAPTADOR_A, self.em_a), (ADAPTADOR_B, self.em_b)))
        }


@pytest.mark.parametrize(("em_b", "b_tem_vaga"), [(4, False), (1, True)])
def test_4b_a_recusa_so_aponta_o_adaptador_onde_a_conta_deixa(
    monkeypatch: pytest.MonkeyPatch, em_b: int, b_tem_vaga: bool
) -> None:
    """A vaga sugerida na recusa segue o M do OUTRO adaptador, não o teto fixo."""
    monkeypatch.setattr(rm, "N_MAX_PELA_CAPACIDADE", True)
    monkeypatch.setattr(rm, "AR_DO_ADAPTADOR_PORTA_DIRETA", rm.AR_DO_ADAPTADOR_ATRAS_DO_HUB)
    em_b_uniq = "aa:bb:cc:00:00:11"
    governador = gov.GovernadorDoRadio(
        medidor=_ControlesPorAdaptador(em_a=4, em_b=em_b),
        adaptador_de=lambda u: ADAPTADOR_B if u == em_b_uniq else ADAPTADOR_A,
        registrar=lambda *_a, **_k: None, relogio=lambda: 1000.0,
    )
    governador.tique()
    for uniq in (em_b_uniq, "aa:bb:cc:00:00:01"):
        vaga = governador.pedir_vaga(uniq, "som")
        assert isinstance(vaga, gov.Vaga)
        vaga.subiu()
    resposta = governador.pedir_vaga("aa:bb:cc:00:00:02", "som")
    if b_tem_vaga:
        assert isinstance(resposta, gov.Recusa) and ADAPTADOR_B in resposta.vagas, resposta
    else:
        assert isinstance(resposta, gov.Vaga) and resposta.alem_do_limite, resposta


def _pontes(modos: tuple[str, ...], parados: tuple[float | None, ...]) -> list[rm.PonteNaFila]:
    return [
        rm.PonteNaFila(uniq=f"P{i + 1}", modo=m, vaga=i + 1, parado_ha_s=p)
        for i, (m, p) in enumerate(zip(modos, parados, strict=True))
    ]


@pytest.mark.parametrize(
    "modos",
    [("haptica",) * 4, ("som", "haptica", "som", "haptica"), ("haptica", "som", "som", "som")],
)
def test_5_o_degrau_cede_a_taxa_antes_de_cortar_uma_ponte(modos: tuple[str, ...]) -> None:
    pontes = _pontes(modos, (None, 30.0, 5.0, 12.0))
    com = rm.ordem_de_ceder(pontes, controles=4, degrau=True)
    sem = rm.ordem_de_ceder(pontes, controles=4, degrau=False)
    acoes = [d.acao for d in com]
    taxas = [d.uniq for d in com if d.acao == rm.ACAO_CEDER_A_TAXA]
    assert taxas == [p.uniq for p in sorted(pontes, key=lambda p: (
        -(p.parado_ha_s or -1.0), -p.vaga)) if p.modo == "haptica"][: len(taxas)]
    assert taxas, "a ponte de vibração tem degrau e não cedeu a taxa"
    if rm.ACAO_CEDER_A_PONTE in acoes:
        assert acoes.index(rm.ACAO_CEDER_A_PONTE) >= len(
            [m for m in modos if m == "haptica"]), "uma ponte saiu inteira com taxa por ceder"
    assert com[-1].hz_depois >= rm.HZ_QUE_ENGASGA
    cortadas = sum(1 for d in com if d.acao == rm.ACAO_CEDER_A_PONTE)
    assert cortadas <= sum(1 for d in sem if d.acao == rm.ACAO_CEDER_A_PONTE)
    assert all(d.acao == rm.ACAO_CEDER_A_PONTE for d in sem)


def test_5b_quatro_vibracoes_cabem_no_degrau_sem_cortar_nenhuma() -> None:
    passos = rm.ordem_de_ceder(
        _pontes(("haptica",) * 4, (None, 30.0, 5.0, 12.0)), controles=4, degrau=True)
    assert [d.acao for d in passos] == [rm.ACAO_CEDER_A_TAXA] * 3
    assert [d.uniq for d in passos] == ["P2", "P4", "P3"], "quem está parado há mais tempo cede"


def test_6_p1_a_p4_sao_iguais() -> None:
    """A vez é do tempo parado e da vaga, nunca do nome do jogador."""
    pontes = _pontes(("haptica",) * 4, (8.0, 8.0, 8.0, 8.0))
    trocadas = [rm.PonteNaFila(uniq=f"X{9 - p.vaga}", modo=p.modo, vaga=p.vaga,
                               parado_ha_s=p.parado_ha_s) for p in pontes]
    vez = [d.uniq for d in rm.ordem_de_ceder(pontes, controles=4, degrau=True)]
    vez_trocada = [d.uniq for d in rm.ordem_de_ceder(trocadas, controles=4, degrau=True)]
    assert vez == ["P4", "P3", "P2"], "empate: a vaga mais nova cede primeiro"
    assert [f"X{9 - int(u[1])}" for u in vez] == vez_trocada


@pytest.mark.parametrize("c_eff", [rm.AR_DO_ADAPTADOR_PORTA_DIRETA,
                                   rm.AR_DO_ADAPTADOR_ATRAS_DO_HUB, 849.0])
def test_7_ninguem_cai_abaixo_de_125_enquanto_cabe(c_eff: float) -> None:
    for controles in range(1, 5):
        m = rm.n_max_pela_capacidade(controles, ar=c_eff)
        assert m <= rm.N_MAX_PONTES
        if m:
            hz = rm.hz_por_controle_na_conta(c_eff, controles, cheias=m)
            assert hz >= rm.HZ_QUE_ENGASGA, f"{controles} controles, {m} pontes: {hz:.1f} Hz"
        acima = rm.hz_por_controle_na_conta(c_eff, controles, cheias=m + 1)
        assert acima < rm.HZ_QUE_ENGASGA or m == rm.N_MAX_PONTES, "o M não é o maior que cabe"


def _const(html: str, nome: str) -> float:
    achado = re.search(rf"const {nome} = ([0-9.]+);", html)
    assert achado, f"{nome} sumiu do mapa"
    return float(achado.group(1))


def test_8_o_chip_do_mapa_diz_n_sobre_m_com_a_mesma_conta() -> None:
    html = MAPA.read_text(encoding="utf-8")
    assert _const(html, "PONTES_POR_ADAPTADOR") == rm.N_MAX_PONTES
    assert _const(html, "MARGINAL_DA_PONTE") == rm.custo_da_ponte()
    assert _const(html, "HZ_QUE_ENGASGA") == rm.HZ_QUE_ENGASGA
    assert _const(html, "FATIAS_POR_RELATORIO_DE_ENTRADA") == rm.FATIAS_POR_RELATORIO_DE_ENTRADA
    corpo = re.search(r"function pontesQueCabem\(lid\) \{(.*?)\n\}", html, re.S)
    assert corpo, "pontesQueCabem sumiu do mapa"
    texto = " ".join(corpo.group(1).split())
    assert "lug.teto - FATIAS_POR_RELATORIO_DE_ENTRADA * HZ_QUE_ENGASGA * controles" in texto
    assert ("Math.max(0, Math.min(PONTES_POR_ADAPTADOR, Math.floor(sobra / MARGINAL_DA_PONTE)))"
            in texto)
    assert "const cabem = pontesQueCabem(lug.id)" in html
    assert "n + '/' + cabem" in html, "o chip voltou ao N/2 fixo"
    assert "n + '/' + PONTES_POR_ADAPTADOR" not in html


def _controle() -> bytes:
    return af.controle_de_audio_035(contador_de_quadros=7)


def test_9_um_bloco_e_o_0x36_de_hoje_byte_a_byte() -> None:
    bloco = bytes(range(64))
    assert dois.montar(seq=3, controle=_controle(), common=af.common_de_audio(),
                       blocos=[bloco]) == af.montar_relatorio_combinado(
        seq=3, controle=_controle(), common=af.common_de_audio(), haptico=bloco)


@pytest.mark.parametrize(("arranjo", "tags"), [("cadeia", (0x92, 0x92)), ("duplo", (0xD2,))])
def test_9b_dois_blocos_seguem_a_onda_sem_buraco(arranjo: str, tags: tuple[int, ...]) -> None:
    proximo = dois.onda(120.0)
    a, b = proximo(), proximo()
    relatorio = dois.montar(seq=0, controle=_controle(), common=af.common_de_audio(),
                            blocos=[a, b], arranjo=arranjo)
    assert len(relatorio) == af.TAMANHO_DO_DEGRAU[af.DEGRAU_COMBINADO]
    assert tuple(relatorio[76 + 66 * i] for i in range(len(tags))) == tags
    dados = relatorio[78:142] + relatorio[144:208] if arranjo == "cadeia" else relatorio[78:206]
    assert dados == a + b
    crc = rep.bt_crc32(relatorio[:-4], seed=rep.BT_CRC_SEED)
    assert crc.to_bytes(4, "little") == relatorio[-4:]
    continua = dois.onda(120.0)
    assert continua() + continua() == a + b, "o segundo bloco não continua o primeiro"


def test_9c_o_contador_anda_por_relatorio_ou_por_bloco() -> None:
    por_relatorio = dois.Escritor(passo_do_contador=1)
    por_bloco = dois.Escritor(passo_do_contador=2)
    for _ in range(3):
        por_relatorio.proximo(2)
        por_bloco.proximo(2)
    assert (por_relatorio.contador, por_bloco.contador) == (3, 6)


def test_9d_as_rodadas_sao_cegas_e_a_chave_sai_no_fim() -> None:
    ordem = dois.sortear_rodadas(6, semente=4)
    assert sorted(ordem) == ["dois"] * 3 + ["um"] * 3
    assert ordem == dois.sortear_rodadas(6, semente=4)
    tela: list[str] = []
    escritas: list[int] = []
    agora = [0.0]

    def relogio() -> float:
        return agora[0]

    def dormir(s: float) -> None:
        agora[0] += s

    def escrever(r: bytes) -> int:
        escritas.append(len(r))
        agora[0] += 0.0001
        return len(r)

    def perguntar(pergunta: str) -> str:
        tela.append(pergunta)
        return "forte"

    rodadas = dois.rodar(ordem, dois.Escritor(), escrever, segundos=2.0,
                         perguntar=perguntar,
                         avisar=tela.append, relogio=relogio, dormir=dormir)
    for linha in tela:
        assert not re.search(r"\bum\b|dois|bloco|46|93", linha), f"a tela entregou a chave: {linha}"
    ritmo = {r.arranjo: r.entregues for r in rodadas}
    assert ritmo["um"] == pytest.approx(2 * rm.HZ_DA_PONTE, abs=2)
    assert ritmo["dois"] == pytest.approx(2 * rm.HZ_DA_PONTE_NO_DEGRAU, abs=2)
    assert [r.arranjo for r in rodadas] == ordem
    assert all("forte" in li for li in dois.linhas_curtas(rodadas))


def test_9e_recusa_com_o_daemon_no_ar_e_sem_o_endereco() -> None:
    args: Any = type("A", (), {"exigir_mac": ""})()
    assert "daemon" in dois.recusa(args, daemon=lambda: True)
    assert "--exigir-mac" in dois.recusa(args, daemon=lambda: False)
    args.exigir_mac = "aa:bb:cc:00:00:01"
    assert dois.recusa(args, daemon=lambda: False) == ""


def test_9f_sem_escrever_nada_vai_ao_aparelho(capsys: pytest.CaptureFixture[str],
                                               monkeypatch: pytest.MonkeyPatch) -> None:
    def _proibido(*_a: object, **_k: object) -> int:
        raise AssertionError("abriu o aparelho em seco")

    monkeypatch.setattr("hefesto_dualsense4unix.integrations.dualsense_bt_audio.abrir_hidraw_rw",
                        _proibido)
    assert dois.main([]) == 0
    saida = capsys.readouterr().out
    assert "EM SECO" in saida and saida.count("CRC certo") == 2

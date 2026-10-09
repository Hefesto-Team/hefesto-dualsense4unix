"""As réguas da A-PONTE-SE-CONTA-EM-FATIAS-NO-AR-01.

`scripts/ensaios/a_ponte_em_fatias_no_ar.py` mede quanto a ponte tira do ar de um adaptador pelo
deslocamento da entrada. Aqui nada toca rádio, daemon nem servidor de som: o ``state_full``, o
medidor de ar, o tocador e o relógio são dublês, e as janelas são as sintéticas de
``tests/fixtures/a_ponte_em_fatias_no_ar/``.

AS MORDIDAS (09/10/2026, uma por vez, md5 conferido na volta):

1. ``deslocamento`` com 4 fatias por relatório no lugar de 2 (o custo dobra, como na leitura bruta):
   a régua do cálculo reprova.
2. a recusa das três pontes arrancada: a régua da recusa reprova (e o tocador é chamado).
3. o ``uniq`` no rótulo do controle: a régua do endereço reprova.
4. ``conferir_a_constante`` sem comparar o ``k`` medido com a constante: a régua do 3 reprova.
5. uma `bancada.json` que mede 5 na fixture, com o 3 na constante: `test_o_orcamento_conta_a_ponte`
   reprova.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.core.formas_do_endereco import formas_do_endereco
from hefesto_dualsense4unix.integrations import radio_da_mesa as rm

_RAIZ = Path(__file__).resolve().parents[2]
_INSTRUMENTO = _RAIZ / "scripts" / "ensaios" / "a_ponte_em_fatias_no_ar.py"
_CHECAGEM = _RAIZ / "scripts" / "check_endereco_de_radio.py"
_FIXTURES = _RAIZ / "tests" / "fixtures" / "a_ponte_em_fatias_no_ar"

UNIQ_1 = "aabbccd4e7a1"
UNIQ_2 = "aabbccd4e7a2"
ADAPTADOR = "aa:bb:cc:e3:f2:01"


def _carregar(caminho: Path, nome: str) -> Any:
    spec = importlib.util.spec_from_file_location(nome, caminho)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[nome] = modulo
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture(scope="module")
def inst() -> Any:
    return _carregar(_INSTRUMENTO, "_regua_a_ponte_em_fatias_no_ar")


def _linhas(inst: Any) -> list[Any]:
    linhas: list[Any] = inst.tabela(inst.ler_janelas(_FIXTURES / "janelas-sinteticas.json"))
    return linhas


def _linha(linhas: list[Any], adaptador: str, controles: int, pontes: int) -> Any:
    achadas = [li for li in linhas
               if (li.adaptador, li.controles, li.pontes) == (adaptador, controles, pontes)]
    assert len(achadas) == 1, (adaptador, controles, pontes)
    return achadas[0]


def test_1_o_deslocamento_sai_da_entrada_e_nao_do_k_suposto(inst: Any) -> None:
    linhas = _linhas(inst)
    um = _linha(linhas, "1", 1, 1)
    assert um.deslocamento == pytest.approx(187.5)
    assert um.k_liquido == pytest.approx(3.0) and um.k_bruto == pytest.approx(1.0)
    assert um.entrada_saturada == pytest.approx(1500.0)
    duas = _linha(linhas, "1", 2, 2)
    assert duas.deslocamento == pytest.approx(375.0)
    assert duas.custo_por_ponte == pytest.approx(187.5)
    assert duas.hz_por_controle == pytest.approx(281.25)
    hub = _linha(linhas, "2", 1, 1)
    assert hub.deslocamento == pytest.approx(375.0)
    assert hub.k_liquido == pytest.approx(5.0) and hub.k_bruto == pytest.approx(3.0)
    assert hub.mestre == "escravo" and um.mestre == "mestre"


def test_1b_a_janela_em_que_a_ponte_caiu_fica_fora(inst: Any) -> None:
    duas = _linha(_linhas(inst), "1", 2, 2)
    assert duas.hz_por_controle == pytest.approx(281.25)


def test_1c_a_linha_curta_diz_cada_variavel(inst: Any) -> None:
    curtas = inst.linhas_curtas(_linhas(inst), 3)
    assert any("1 ponte(s): D = 187,5 fatias/s, k = 3,00 (líquido)" in c for c in curtas)
    assert any("adaptador 2" in c and "k = 5,00 (líquido)" in c for c in curtas)
    md = inst.tabela_em_markdown(_linhas(inst))
    assert md.count("\n") == len(_linhas(inst)) + 1


class _Relogio:
    def __init__(self) -> None:
        self.agora = 0.0

    def __call__(self) -> float:
        return self.agora

    def dormir(self, s: float) -> None:
        self.agora += s


class _Mesa:
    """O daemon de mentira: a ponte de um controle fica de pé enquanto toca sinal nele."""

    def __init__(self, *, jogo: int | None = None, silencio_levanta: bool = False,
                 no_ar: bool = True) -> None:
        self.tocando: dict[str, float | None] = {}
        self.toques: list[tuple[str, float | None]] = []
        self.jogo = jogo
        self.silencio_levanta = silencio_levanta
        self.no_ar = no_ar
        self.relogio = _Relogio()
        self.escrito: list[str] = []

    def estado(self) -> dict[str, Any] | None:
        if not self.no_ar:
            return None
        pontes = {u for u, d in self.tocando.items() if d is not None or self.silencio_levanta}
        base = 750.0 / 2
        controles = []
        for uniq in (UNIQ_1, UNIQ_2):
            hz = base - 93.75 * len(pontes) / 2
            controles.append({
                "uniq": uniq, "transport": "bt", "connected": True, "adaptador": ADAPTADOR,
                "hz_movimento": hz, "ponte_do_radio": "som" if uniq in pontes else None,
            })
        return {"controllers": controles, "jogo_steam": {"lido": True, "appid": self.jogo}}

    def ar(self) -> dict[str, Any]:
        from hefesto_dualsense4unix.integrations.ar_do_adaptador import ArDoAdaptador, Enlace

        enlaces = tuple(
            Enlace(handle=n, endereco=":".join(u[i:i + 2] for i in range(0, 12, 2)), tipo=1,
                   saida=False, estado=1, link_mode=1)
            for n, u in enumerate((UNIQ_1, UNIQ_2)))
        return {ADAPTADOR: ArDoAdaptador(hci=0, endereco=ADAPTADOR, entrada_por_s=700.0,
                                         saida_por_s=93.75, conexoes=enlaces)}

    def tocar(self, uniq: str, dbfs: float | None) -> Any:
        self.toques.append((uniq, dbfs))
        self.tocando[uniq] = dbfs

        def parar() -> None:
            self.tocando.pop(uniq, None)

        return parar

    def portas(self, inst: Any) -> Any:
        return inst.Portas(estado=self.estado, ar=self.ar, tocar=self.tocar,
                           relogio=self.relogio, dormir=self.relogio.dormir,
                           escrever=self.escrito.append)


def _rodar(inst: Any, mesa: _Mesa, tmp_path: Path, *extra: str) -> int:
    return int(inst.main(["medir", "--adaptador", "1", "--rotulo", "porta direta",
                          "--saida", str(tmp_path / "x.jsonl"), "--janela", "6",
                          "--descarte", "1", *extra], portas=mesa.portas(inst)))


def test_2_tres_pontes_recusa_e_nada_toca(inst: Any, tmp_path: Path) -> None:
    mesa = _Mesa()
    assert _rodar(inst, mesa, tmp_path, "--medir", "--pontes", "0,1,3") == 2
    assert any(inst.RECUSA_TRES_PONTES in e for e in mesa.escrito)
    assert mesa.toques == []


def test_2b_sem_daemon_recusa(inst: Any, tmp_path: Path) -> None:
    mesa = _Mesa(no_ar=False)
    assert _rodar(inst, mesa, tmp_path, "--medir") == 2
    assert any(inst.RECUSA_SEM_DAEMON in e for e in mesa.escrito)
    assert mesa.toques == []


def test_2c_sem_medir_so_descreve_e_nao_pergunta_ao_daemon(
    inst: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def proibido(*_a: Any, **_k: Any) -> Any:
        raise AssertionError("sem --medir o ensaio abriu as portas de verdade")

    monkeypatch.setattr(inst, "portas_de_verdade", proibido)
    monkeypatch.setenv("HEFESTO_PONTE_PONTES", "0,1")
    assert inst.main(["medir", "--saida", str(tmp_path / "x.jsonl")]) == 2
    saida = capsys.readouterr().out
    assert inst.RECUSA_SEM_MEDIR in saida and "pontes [0, 1]" in saida
    assert not (tmp_path / "x.jsonl").exists()


def test_2d_jogo_aberto_recusa(inst: Any, tmp_path: Path) -> None:
    mesa = _Mesa(jogo=1086940)
    assert _rodar(inst, mesa, tmp_path, "--medir") == 2
    assert any(inst.RECUSA_JOGO in e for e in mesa.escrito)
    assert mesa.toques == []


def test_2e_o_silencio_nao_levanta_e_o_sinal_mais_baixo_e_o_escolhido(
    inst: Any, tmp_path: Path
) -> None:
    mesa = _Mesa()
    assert _rodar(inst, mesa, tmp_path, "--medir") == 0
    assert mesa.toques[0] == (UNIQ_1, None)
    assert mesa.toques[1] == (UNIQ_1, -60.0)
    assert any("o sinal que mantém a ponte de pé: -60 dBFS" in e for e in mesa.escrito)
    linhas = [json.loads(x) for x in (tmp_path / "x.jsonl").read_text().splitlines()]
    assert [li["pontes"] for li in linhas] == [0, 1, 2]
    assert all(li["valida"] for li in linhas)
    assert linhas[2]["mestre"] == {"controle 1": True, "controle 2": True}


def test_3_nenhum_endereco_nem_no_de_som_na_saida(inst: Any, tmp_path: Path) -> None:
    from hefesto_dualsense4unix.integrations.alto_falante_bt import nome_do_sink

    checagem = _carregar(_CHECAGEM, "_regua_check_endereco_de_radio_ponte")
    mesa = _Mesa()
    assert _rodar(inst, mesa, tmp_path, "--medir") == 0
    saida = (tmp_path / "x.jsonl").read_text() + "\n".join(mesa.escrito)
    baixa = saida.lower()
    for endereco in (UNIQ_1, UNIQ_2, ADAPTADOR):
        vazou = {f for f in formas_do_endereco(endereco) if f.lower() in baixa}
        assert not vazou, f"a forma {sorted(vazou)} do endereço saiu"
    for uniq in (UNIQ_1, UNIQ_2):
        no = nome_do_sink(uniq)
        assert not no or no.lower() not in baixa
    for linha in saida.splitlines():
        assert not checagem.acusa_mac(linha) and not checagem.acusa_serial(linha)
    fixture = (_FIXTURES / "janelas-sinteticas.json").read_text()
    assert not any(checagem.acusa_mac(li) for li in fixture.splitlines())


def test_4_a_constante_segue_a_tabela_gravada(inst: Any) -> None:
    """Sem tabela gravada, o k é provisório; com ela, constante, CSV e desenho dizem o k dela."""
    gravada = inst.gravada()
    procedencia = inst.procedencia_do_k()
    assert inst.conferir_a_constante(
        gravada, fatias=rm.FATIAS_DA_PONTE, procedencia=procedencia,
        marginal=inst.marginal_do_desenho()) == []
    if gravada is None:
        assert procedencia.startswith("provisório")


def _janelas_do_hub(inst: Any) -> list[Any]:
    janelas = inst.ler_janelas(_FIXTURES / "janelas-sinteticas.json")
    return [j for j in janelas if j.adaptador == "2"]


def test_4b_o_3_antigo_reprova_quando_a_tabela_mede_5(inst: Any) -> None:
    hub = _janelas_do_hub(inst)
    assert inst.k_da_bancada(inst.tabela(hub)) == (5, "líquido")
    problemas = inst.conferir_a_constante(hub, fatias=3, procedencia="provisório", marginal=187.5)
    assert len(problemas) == 3
    assert inst.conferir_a_constante(
        hub, fatias=5, procedencia="medido 10/10/2026", marginal=375.0) == []


def test_4c_o_csv_nao_vira_medido_sem_a_tabela(inst: Any) -> None:
    assert inst.conferir_a_constante(
        None, fatias=3, procedencia="medido 09/10/2026", marginal=187.5)


def test_4d_medida_fora_dos_pacotes_nao_escolhe_constante(inst: Any) -> None:
    hub = _janelas_do_hub(inst)
    torta = [j if j.pontes == 0 else type(j)(**{**j.__dict__, "hz": {"controle 1": 600.0}})
             for j in hub]
    assert inst.k_da_bancada(inst.tabela(torta)) is None
    assert inst.conferir_a_constante(torta, fatias=3, procedencia="medido 10/10/2026",
                                     marginal=187.5)


def test_4e_gravar_leva_a_sessao_para_a_tabela_versionada(inst: Any, tmp_path: Path) -> None:
    sessao = tmp_path / "sessao.jsonl"
    sessao.write_text("\n".join(json.dumps(j.linha()) for j in _janelas_do_hub(inst)) + "\n")
    alvo = inst.gravar(sessao, tmp_path / "bancada.json")
    relida = inst.gravada(alvo)
    assert relida is not None and [j.linha() for j in relida] == [
        j.linha() for j in _janelas_do_hub(inst)]
    assert inst.gravada(tmp_path / "nao-ha.json") is None

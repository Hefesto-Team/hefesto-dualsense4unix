"""A perícia do brilho (O-BRILHO-BAIXO-QUE-ELA-NAO-ESCOLHEU-01), num lar de mentira.

O instrumento é `scripts/ensaios/quem_gravou_o_brilho.py`: lê as cópias do perfil
em ordem de hora, diz em que par de cópias o brilho de um controle muda, casa o
intervalo com as gravações do log e nunca imprime um endereço. Aqui as cópias, o
log e o `loader.py` são de mentira, com identidades da faixa forjada `aa:bb:cc`.
"""
from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import re
import sys
from types import ModuleType

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
CAMINHO = RAIZ / "scripts" / "ensaios" / "quem_gravou_o_brilho.py"

UNIQ_A = "aabbcc000001"
UNIQ_B = "aabbcc000002"


def _carregar() -> ModuleType:
    spec = importlib.util.spec_from_file_location("quem_gravou_o_brilho_ensaio", CAMINHO)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture(scope="module")
def ens() -> ModuleType:
    return _carregar()


def _perfil(nome: str, brilho_b: float | None) -> dict:
    leds_b = {} if brilho_b is None else {"leds": {"lightbar_brightness": brilho_b}}
    return {
        "name": nome,
        "leds": {"lightbar_brightness": 1.0},
        "controllers": {UNIQ_A: {"mascara": "dualsense"}, UNIQ_B: leds_b},
    }


def _gravar(caminho: pathlib.Path, dados: dict, quando: float | None = None) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(dados), encoding="utf-8")
    if quando is not None:
        os.utime(caminho, (quando, quando))


@pytest.fixture
def lar(tmp_path: pathlib.Path) -> dict[str, pathlib.Path]:
    """Três cópias de mentira: 0,49 -> 0,49 -> 0,08, e o arquivo de agora."""
    perfis = tmp_path / "config" / "profiles"
    estado = tmp_path / "estado"
    _gravar(perfis / ".historico/personalizado/20260922T100000_000001.json",
            _perfil("Personalizado", 0.49))
    _gravar(perfis / ".historico/personalizado/20260924T172112_000002.json",
            _perfil("Personalizado", 0.49))
    # Uma cópia com o endereço no NOME do arquivo: o rótulo dela vai à saída.
    _gravar(perfis / f"freestyle.json.antes-{UNIQ_B}", _perfil("Freestyle", 0.49),
            dt_para_epoca(2026, 9, 25, 10, 0, 0))
    # A cópia «antes-da-restauracao» não tem hora no nome: vale a do arquivo.
    antes = perfis / "freestyle.json.antes-da-restauracao-2609"
    _gravar(antes, _perfil("Freestyle", 0.08),
            dt_para_epoca(2026, 9, 26, 19, 11, 0))
    _gravar(perfis / ".historico/freestyle/20260929T161035_000003.json",
            _perfil("Freestyle", 1.0))
    _gravar(perfis / "freestyle.json", _perfil("Freestyle", None),
            dt_para_epoca(2026, 10, 8, 1, 39, 21))
    estado.mkdir(parents=True)
    (estado / "interface.log.1").write_text("\n".join([
        "===== a janela abriu em 2026-09-25T17:15:01 =====",
        "2026-09-25T17:15:11.000000 [info     ] perfis_de_jogo_semeados        jogos=1",
        "2026-09-25T17:15:35.100000 [info     ] profile_salvo                  "
        "arquivo=freestyle.json origem=interface-nova pid=60112",
        "2026-09-25T17:15:40.100000 [info     ] profile_salvo                  "
        "arquivo=freestyle.json origem=interface-nova pid=60112",
        "2026-09-25T17:15:44.100000 [info     ] profile_salvo                  "
        "arquivo=freestyle.json origem=interface-nova pid=60112",
        "2026-09-25T17:15:48.100000 [info     ] profile_salvo                  "
        "arquivo=pragmata.json origem=interface-nova pid=60112",
        "===== a janela abriu em 2026-09-28T09:00:00 =====",
        "2026-09-28T09:00:01.000000 [info     ] perfis_de_jogo_semeados        jogos=1",
        "2026-09-28T09:00:01.050000 [info     ] profile_salvo                  "
        "arquivo=freestyle.json origem=interface-nova pid=777",
    ]) + "\n", encoding="utf-8")
    loader = tmp_path / "loader.py"
    loader.write_text(
        "def _trocar_o_personalizado(directory):\n"
        "    dados['name'] = 'Freestyle'\n"
        "    return 'renomeado', None\n\n"
        "def outra():\n    return 'lightbar_brightness'\n", encoding="utf-8")
    a04 = tmp_path / "a04.py"
    a04.write_text(
        "def _com_o_brilho_gravado(prof, uniq, pct):\n    pass\n\n"
        "def gesto():\n"
        "    gravar_pelo_gesto('luz', nome, lambda prof: "
        "_com_o_brilho_gravado(prof, uniq, pct))\n", encoding="utf-8")
    return {"perfis": perfis, "estado": estado, "loader": loader, "a04": a04,
            "raiz": tmp_path}


def dt_para_epoca(ano: int, mes: int, dia: int, h: int, m: int, s: int) -> float:
    import datetime as dt
    return dt.datetime(ano, mes, dia, h, m, s).timestamp()


def _rodar(ens: ModuleType, lar: dict[str, pathlib.Path], capsys: pytest.CaptureFixture,
           *extra: str) -> str:
    rc = ens.main([
        "--perfis", str(lar["perfis"]), "--casa", str(lar["raiz"] / "casa"),
        "--estado", str(lar["estado"]), "--diario", "nenhum",
        "--loader", str(lar["loader"]), "--a04", str(lar["a04"]), *extra])
    assert rc == 0
    return capsys.readouterr().out


def test_acha_o_par_de_copias_em_que_o_brilho_muda(ens, lar, capsys):
    saida = _rodar(ens, lar, capsys)
    assert "Controle B, as mudanças de brilho:" in saida
    assert "0,49 -> 0,08" in saida
    # o par que emoldura: a última cópia a 0,49 e a cópia da restauração
    assert "25/09 10:00:00" in saida
    assert "26/09 19:11:00" in saida
    # a mudança seguinte também aparece, com o par certo
    assert "0,08 -> 1" in saida
    assert "29/09 16:10:35" in saida


def test_diz_quem_mais_mudou_ate_a_mesma_copia(ens, lar, capsys):
    perfil = _perfil("Freestyle", 0.08)
    perfil["controllers"][UNIQ_A] = {"leds": {"lightbar_brightness": 0.5}}
    _gravar(lar["perfis"] / "freestyle.json.antes-da-restauracao-2609", perfil,
            dt_para_epoca(2026, 9, 26, 19, 11, 0))
    saida = _rodar(ens, lar, capsys, "--peca", "B")
    assert "até a mesma cópia mudaram também: A (sem override -> 0,5)" in saida


def test_as_pecas_saem_por_letra_e_o_controle_sem_override_nao_muda(ens, lar, capsys):
    saida = _rodar(ens, lar, capsys)
    assert "Controle A" not in saida
    assert "controles: A, B." in saida


def test_nenhum_endereco_sai_na_saida(ens, lar, capsys):
    saida = _rodar(ens, lar, capsys)
    assert not re.search(r"\b[0-9a-fA-F]{12}\b", saida)
    assert not re.search(r"\b[0-9a-fA-F]{2}(?:[:-][0-9a-fA-F]{2}){5}\b", saida)
    assert UNIQ_A not in saida and UNIQ_B not in saida
    assert "<endereço>" in saida, "o nome de uma cópia trazia um endereço e a máscara o cobriu"


def test_a_mascara_cobre_as_formas_com_separador_e_coladas(ens):
    assert ens.mascarar("aa:bb:cc:00:00:01 e aa-bb-cc-00-00-02 e aabbcc000003") \
        == "<endereço> e <endereço> e <endereço>"


def test_as_cópias_vêm_em_ordem_de_hora_e_nao_em_ordem_de_descoberta(ens, lar):
    copias = ens.ordenar_copias(
        ens.achar_as_copias(lar["perfis"], None, None))
    horas = [c.hora for c in copias]
    assert horas == sorted(horas)
    rotulos = [c.rotulo for c in copias]
    assert rotulos.index("cópia antes-da-restauracao-2609") \
        < rotulos.index("histórico freestyle")


def test_casa_o_intervalo_com_as_gravacoes_do_log(ens, lar, capsys):
    saida = _rodar(ens, lar, capsys)
    # as três do freestyle.json em 25/09 estão no primeiro intervalo (a do pragmata não)
    assert "3 gravação(ões) do freestyle.json" in saida
    assert "janela de 25/09 17:15:01" in saida
    assert "pragmata" not in saida


def test_diz_o_escritor_e_o_que_falta_quando_sao_varias(ens, lar, capsys):
    saida = _rodar(ens, lar, capsys)
    assert "ESCRITOR PROVÁVEL" in saida
    assert "trilho «Brilho»" in saida and "a04_iluminacao.py:1 monta, :5 grava" in saida
    assert "NÃO FECHA a hora" in saida


def test_a_unica_gravacao_do_intervalo_e_a_primeira_leitura_do_perfil(ens, lar, capsys):
    saida = _rodar(ens, lar, capsys)
    assert "28/09 09:00:01" in saida
    assert "primeira leitura de perfil da janela" in saida
    assert "Provável e não provado" in saida


def test_a_migracao_que_nao_fala_de_brilho_nao_e_a_escritora(ens, lar, capsys):
    saida = _rodar(ens, lar, capsys)
    assert "não toca o brilho nem os leds" in saida


def test_a_migracao_que_fala_de_brilho_e_apontada(ens, lar, capsys):
    lar["loader"].write_text(
        "def _trocar_o_personalizado(d):\n    dados['leds']['lightbar_brightness'] *= 0.16\n",
        encoding="utf-8")
    saida = _rodar(ens, lar, capsys)
    assert "FALA de brilho/luz" in saida


def test_so_a_peca_pedida(ens, lar, capsys):
    saida = _rodar(ens, lar, capsys, "--peca", "Z")
    assert "Controle B" not in saida

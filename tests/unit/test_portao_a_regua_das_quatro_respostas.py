"""A régua CABO · BT · PERFIL · CONTROLE morde — CABO-BT-PERFIL-CONTROLE-01."""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
PORTAO = RAIZ / "scripts/check_cabo_bt_perfil_controle.py"


def _regua():
    spec = importlib.util.spec_from_file_location("_regua_das_quatro", PORTAO)
    assert spec and spec.loader
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture(scope="module")
def regua():
    return _regua()


def test_a_tela_de_hoje_passa(regua, capsys):
    """O estado de agora é VERDE — e toda dívida aberta sai NOMEADA."""
    assert regua.main() == 0
    saida = capsys.readouterr().out
    assert "VERDE" in saida
    for gesto in regua.A_DIVIDA_CONHECIDA:
        sprint, _razao = regua.A_DIVIDA_CONHECIDA[gesto]
        assert f"dívida: {gesto}" in saida, (
            f"a dívida `{gesto}` está declarada e não sai nomeada — é uma "
            f"dívida em silêncio, que é o que esta régua existe para impedir")
        assert sprint in saida, (
            f"a dívida `{gesto}` sai sem a dona; sem ela ninguém sabe onde o "
            f"fecho está escrito")


def test_divida_aberta_sai_nomeada_e_nao_reprova(regua, monkeypatch, capsys):
    """A dívida DECLARADA fica verde, mas nunca fica calada."""
    monkeypatch.setitem(regua.DO_APARELHO, "mudo", ("luz.lightbar.brilho",))
    monkeypatch.setitem(
        regua.A_DIVIDA_CONHECIDA, "mudo",
        ("2026-01-01-DE-MENTIRA.md", "dívida de mentira, só para provar que a "
                                     "declarada sai nomeada"))
    quantas = len(regua.A_DIVIDA_CONHECIDA)
    assert regua.main() == 0
    saida = capsys.readouterr().out
    assert f"{quantas} em dívida declarada" in saida
    assert "dívida: mudo" in saida
    assert "2026-01-01-DE-MENTIRA.md" in saida


def test_toda_feature_da_tela_esta_classificada(regua):
    """Nenhum `data-gesto` das dez páginas fica sem razão ou sem chave."""
    na_tela = set(regua.gestos_da_tela())
    declarados = set(regua.NAO_E_DO_APARELHO) | set(regua.DO_APARELHO)
    assert not na_tela - declarados, "gesto da tela sem classificação"


def test_morde_feature_nova_sem_as_quatro_respostas(regua, monkeypatch, capsys):
    """MORDIDA 1 — um gesto novo na tela reprova nomeando."""
    monkeypatch.setattr(regua, "gestos_da_tela",
                        lambda: {**_regua().gestos_da_tela(), "luz-nova": ["04"]})
    assert regua.main() == 1
    assert "luz-nova" in capsys.readouterr().out


def test_morde_divida_declarada_que_ja_fechou(regua, monkeypatch, capsys):
    """MORDIDA 2 — a linha da dívida tem de SAIR quando a cura chega."""
    monkeypatch.setitem(
        regua.A_DIVIDA_CONHECIDA, "cor",
        ("2026-01-01-INVENTADA.md", "esta dívida não existe: o `cor` responde "
                                    "as quatro desde sempre"))
    assert regua.main() == 1
    saida = capsys.readouterr().out
    assert "já respondem as quatro" in saida
    assert "cor" in saida


def test_morde_classificacao_que_a_tela_nao_oferece_mais(regua, monkeypatch,
                                                         capsys):
    """MORDIDA 3 — razão escrita para gesto que saiu da tela reprova."""
    monkeypatch.setitem(regua.NAO_E_DO_APARELHO, "gesto-que-morreu",
                        "razão órfã")
    assert regua.main() == 1
    assert "gesto-que-morreu" in capsys.readouterr().out


def test_parcial_nao_e_nao(regua):
    """`parcial` é `com ressalva` — nunca a resposta negativa."""
    linha = {"controle": "dualsense", "radio_aciona": "parcial",
             "radio_ressalva": "a dívida escrita"}
    assert regua._resposta_de_transporte([linha], "radio") == "com ressalva"
    assert regua._resposta_de_transporte([linha], "radio") != regua.NAO


def test_o_gesto_responde_pela_pior_das_chaves(regua):
    """Um gesto com dois atos no aparelho responde pela metade que FALTA."""
    assert regua._pior(["sim", regua.NAO]) == regua.NAO
    assert regua._pior(["sim", "com ressalva"]) == "com ressalva"
    assert regua._pior([]) == "sem linha"
    assert regua.DO_APARELHO["volume"] == ("audio.microfone.volume",
                                           "audio.alto_falante.volume")


def test_so_o_dualsense_responde(regua):
    """As linhas do `pro` e do `sn30` não respondem pela tela dos quatro.

    Sem o filtro, um `sim` do 8BitDo daria por respondida uma feature que o
    DualSense não tem — e o inverso, um `não` do Pro, reprovaria feature viva.
    """
    outros = [{"controle": "pro", "cabo_aciona": "sim", "cabo_ressalva": ""}]
    assert regua._resposta_de_transporte(outros, "cabo") == "sem linha"


def test_morde_o_campo_arrancado_do_esquema(regua, monkeypatch, capsys):
    """§3 da sprint: tirar `speaker` de `ControllerOverrides` reprova o `rota`."""
    real = regua._campos_do_esquema

    def sem_o_speaker(classe: str, *fonte: object) -> set[str]:
        campos = real(classe, *fonte)
        return campos - {"speaker"} if classe == "ControllerOverrides" else campos

    monkeypatch.setattr(regua, "_campos_do_esquema", sem_o_speaker)
    assert regua.main() == 1
    saida = capsys.readouterr().out
    assert "rota" in saida
    assert "não é por controle" in saida


def test_morde_o_transporte_rebaixado_no_mapa(regua, monkeypatch, capsys):
    """§3 da sprint: `luz.lightbar.cor@dualsense` com `radio_aciona=não`.

    Quatro gestos da 04 dependem dessa linha (`cor`, `brilho`, `apagar`,
    `reenviar`) e a régua tem de nomear os quatro, não um.
    """
    real = regua._linhas_do_mapa()
    for linha in real.get("luz.lightbar.cor", []):
        if linha.get("controle") == "dualsense":
            linha["radio_aciona"] = "não"
    monkeypatch.setattr(regua, "_linhas_do_mapa", lambda: real)
    assert regua.main() == 1
    saida = capsys.readouterr().out
    for gesto in ("cor", "brilho", "apagar", "reenviar"):
        assert f"{gesto}: rádio: {regua.NAO}" in saida


def test_o_mudo_do_microfone_responde_no_controle(regua):
    """O-MUDO-E-DO-CONTROLE-01 (28/09/2026): o mudo não fica no perfil."""
    linhas = {linha[0]: linha for linha in regua.tabela()}
    for gesto in ("mudo", "custo-mic"):
        _g, _abas, _cabo, _radio, perfil, controle, _falta = linhas[gesto]
        assert (perfil, controle) == ("no controle", "sim"), (
            f"o `{gesto}` não responde pelo dono do mudo: {perfil!r}, {controle!r}")
        assert gesto not in regua.NO_PERFIL, (
            f"o `{gesto}` ainda se declara no perfil — o mudo saiu de lá")


def test_morde_o_mudo_arrancado_do_controle(regua, monkeypatch, capsys):
    """Tirar `microfone_mudo` de `ControleDeclarado` reprova o `mudo` e o `custo-mic`."""
    real = regua._campos_do_esquema

    def sem_o_mudo(classe: str, *fonte: object) -> set[str]:
        campos = real(classe, *fonte)
        return campos - {"microfone_mudo"} if classe == "ControleDeclarado" else campos

    monkeypatch.setattr(regua, "_campos_do_esquema", sem_o_mudo)
    assert regua.main() == 1
    saida = capsys.readouterr().out
    for gesto in ("mudo", "custo-mic"):
        assert f"{gesto}: não está no perfil" in saida


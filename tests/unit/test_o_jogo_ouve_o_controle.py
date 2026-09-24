"""A FOLHA DO JOGO — o nosso e o do jogo, lado a lado, no mesmo tom (A-FORJA-VALIDA-O-SOM-01, E7).

`scripts/ensaios/o_jogo_ouve_o_controle.py` é a folha que ELA dirige para dar
ao mapa o degrau que ele não tem: *chegou ao JOGO?* A medição é da orelha e da
mão dela; o que se prova AQUI é o que já enganou esta casa antes de a orelha
entrar.

AS MORDIDAS, uma por teste:

1. troque uma chave `.jogo` de `LINHAS` e a primeira régua cai — as quatro são
   as da sprint;
2. mude o canal do tom, ou o `--hz` do lado do jogo, e o «mesmo tom» deixa de
   ser o mesmo;
3. aponte o jogo por outra coisa que não o nó DESTE controle e a célula mede o
   vizinho;
4. deixe a célula sem a frase quando a Forja falta e ela fica muda — um painel
   calado lê-se como *"não fizeram nada"*;
5. rode um comando ao montar ou listar e a folha toca o som dela antes da
   primeira pergunta;
6. deixe sair linha de caderno sem gesto e o degrau `.jogo` vira opinião; e o
   nome do nó, que leva o rabo do endereço, tem de sair MASCARADO.
"""

from __future__ import annotations

import csv
import os
import struct
import subprocess
import sys
from pathlib import Path

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("a folha do jogo monta uma Gtk.Window de verdade")

import importlib.util

RAIZ = Path(__file__).resolve().parents[2]
ENSAIOS = RAIZ / "scripts" / "ensaios"
MAPA = RAIZ / "docs" / "data" / "mapa-controles.csv"

#: As quatro chaves da sprint (§5, E7) — DIGITADAS: a régua lê a sprint.
_AS_QUATRO = (
    "audio.alto_falante.jogo",
    "audio.microfone.jogo",
    "gatilho.direito.adaptativo.jogo",
    "vibracao.rumble.jogo",
)

#: Faixa sintética da casa. Nenhum destes é um controle desta bancada.
_NO_CABO = "aa:bb:cc:12:34:01"
_NO_RADIO = "aa:bb:cc:56:78:02"


def _instrumento():
    """Carrega a folha pelo caminho, como os irmãos, sem assumir a tela pelos outros."""
    antes = os.environ.get("HEFESTO_NA_TELA")
    os.environ["HEFESTO_NA_TELA"] = "1"
    try:
        if str(ENSAIOS) not in sys.path:
            sys.path.insert(0, str(ENSAIOS))
        apelido = "instrumento_o_jogo_ouve_o_controle"
        caminho = ENSAIOS / "o_jogo_ouve_o_controle.py"
        spec = importlib.util.spec_from_file_location(apelido, caminho)
        assert spec is not None and spec.loader is not None
        modulo = importlib.util.module_from_spec(spec)
        sys.modules[apelido] = modulo
        spec.loader.exec_module(modulo)
        return modulo
    finally:
        if antes is None:
            os.environ.pop("HEFESTO_NA_TELA", None)
        else:
            os.environ["HEFESTO_NA_TELA"] = antes


folha = _instrumento()


def _forja_de_mentira(raiz: Path, *, com_speak: bool = True, com_godot: bool = True):
    (raiz / "bin").mkdir(parents=True, exist_ok=True)
    (raiz / "tools").mkdir(parents=True, exist_ok=True)
    for quer, caminho in ((com_speak, raiz / "bin" / "forja-speak"),
                          (com_godot, raiz / folha.GODOT_DA_FORJA)):
        if quer:
            caminho.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            caminho.chmod(0o755)
    return folha.Forja(raiz)


def _pergunta(chave: str):
    return next(p for p in folha.LINHAS if p.chave == chave)


@pytest.fixture
def sem_godot_de_fora(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GODOT", raising=False)


# ---------------------------------------------------------------------------


def test_as_quatro_chaves_e_o_positivo_de_cada_uma_tem_dono() -> None:
    """As quatro linhas são as da sprint, e a chave BASE de cada uma existe no mapa."""
    assert tuple(p.chave for p in folha.LINHAS) == _AS_QUATRO
    with MAPA.open(encoding="utf-8") as f:
        do_dualsense = {r["chave"] for r in csv.DictReader(f) if r["controle"] == "dualsense"}
    for p in folha.LINHAS:
        assert p.base in do_dualsense, f"o positivo de {p.chave} aponta para {p.base}: não existe"
        assert p.chave == f"{p.base.rsplit('.ff', 1)[0]}.jogo"


def test_o_tom_e_o_da_forja_e_so_no_canal_do_alto_falante() -> None:
    """O PCM do nosso lado: o tom no FR e ZERO no FL, com a rampa da Forja."""
    pcm = folha.tom_da_forja()
    quadros = folha.TAXA * folha.TOM_MS // 1000
    assert len(pcm) == quadros * folha.CANAIS_DO_NO * 2
    amostras = struct.unpack(f"<{quadros * 2}h", pcm)
    esquerda, direita = amostras[0::2], amostras[1::2]
    assert all(v == 0 for v in esquerda), "o tom vazou para o canal do fone"
    assert max(abs(v) for v in direita) > 20000, "o tom não está no alto-falante"
    assert direita[0] == 0, "a rampa começa do zero, como a da Forja"
    assert (folha.TOM_HZ, folha.TOM_MS, folha.AMPLITUDE) == (1300.0, 400, 22000.0)


def test_o_jogo_toca_o_mesmo_tom_pelo_no_deste_controle(tmp_path: Path, sem_godot_de_fora) -> None:
    """O lado do jogo leva o MESMO tom e aponta o nó DESTE controle — nunca o vizinho."""
    forja = _forja_de_mentira(tmp_path)
    p = _pergunta("audio.alto_falante.jogo")
    for mac, transporte in ((_NO_CABO, "cabo"), (_NO_RADIO, "radio")):
        c = folha.Controle(mac, transporte)
        jogo = folha.gesto_do_jogo(p, c, forja)
        nosso = folha.gesto_nosso(p, c)
        assert jogo.argv[:3] == [str(forja.speak), "--nome", c.no_de_som]
        assert jogo.argv[jogo.argv.index("--hz") + 1] == f"{folha.TOM_HZ:g}"
        assert jogo.argv[jogo.argv.index("--ms") + 1] == str(folha.TOM_MS)
        assert f"--target={c.no_de_som}" in nosso.argv
        assert "--channel-map=FL,FR" in nosso.argv
        assert nosso.pcm == folha.tom_da_forja()


def test_sem_a_forja_a_celula_diz_o_que_falta(tmp_path: Path, sem_godot_de_fora) -> None:
    """A recusa é entrega: cada lado que não pode rodar diz por quê, e não mostra botão."""
    c = folha.Controle(_NO_RADIO, "radio")
    som, voz = _pergunta("audio.alto_falante.jogo"), _pergunta("audio.microfone.jogo")

    longe = folha.Forja(tmp_path / "nao-existe")
    assert folha.gesto_do_jogo(som, c, longe).recusa.startswith("a Forja não está em")
    crua = _forja_de_mentira(tmp_path / "crua", com_speak=False, com_godot=False)
    g = folha.gesto_do_jogo(som, c, crua)
    assert not g.argv and "rode make" in g.recusa
    g = folha.gesto_do_jogo(voz, c, crua)
    assert not g.argv and "run-local.sh" in g.recusa
    pronta = _forja_de_mentira(tmp_path / "pronta")
    g = folha.gesto_do_jogo(voz, c, pronta)
    assert g.argv[-1] == "--sala=voz" and g.fica_aberto


def test_o_positivo_do_gatilho_e_da_vibracao_vem_do_mapa() -> None:
    """Sem mandar gatilho pelo daemon — que gravaria no perfil dela —, o nosso é o degrau medido."""
    c = folha.Controle(_NO_CABO, "cabo")
    for chave in ("gatilho.direito.adaptativo.jogo", "vibracao.rumble.jogo"):
        g = folha.gesto_nosso(_pergunta(chave), c)
        assert not g.argv
        assert g.recusa.startswith("o mapa: O APARELHO OBEDECEU"), g.recusa


def test_listar_e_montar_nao_rodam_comando_nenhum(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sem_godot_de_fora
) -> None:
    """A folha se monta e se lista sem tocar o som dela nem abrir o jogo."""

    def _proibido(*_a: object, **_k: object) -> None:
        raise AssertionError("a folha rodou um comando só de ser montada")

    monkeypatch.setattr(subprocess, "run", _proibido)
    monkeypatch.setattr(subprocess, "Popen", _proibido)
    forja = _forja_de_mentira(tmp_path)
    mesa = [folha.Controle(_NO_CABO, "cabo"), folha.Controle(_NO_RADIO, "radio")]
    texto = folha.listar(mesa, forja)
    assert texto.count("nosso:") == len(folha.LINHAS) * len(mesa)
    montada = folha.Folha(mesa, forja)
    montada.janela.destroy()
    monkeypatch.setattr(folha, "mesa", lambda: mesa)
    assert folha.main(["--listar", "--forja", str(tmp_path)]) == 0


def test_veredito_sem_gesto_nao_vira_linha_e_o_no_sai_mascarado(
    tmp_path: Path, sem_godot_de_fora
) -> None:
    """Nenhuma linha de caderno sem data e sem gesto — e sem o rabo cru do endereço."""
    p = _pergunta("audio.alto_falante.jogo")
    c = folha.Controle(_NO_CABO, "cabo")
    forja = _forja_de_mentira(tmp_path)
    assert folha.linha_para_o_caderno(p, c, "obedece", []) == ""
    feitos = [folha.gesto_nosso(p, c), folha.gesto_do_jogo(p, c, forja)]
    linha = folha.linha_para_o_caderno(p, c, "obedece", feitos)
    assert "audio.alto_falante.jogo@dualsense" in linha
    assert ",cabo," in linha and ",obedece," in linha
    assert "pw-cat" in linha and "--nome" in linha
    assert "20" in linha.split(",")[5][:4], "a linha leva a data (quando)"
    # o nó é `hefesto_som_<hex6>`: os octetos 4 e 5 saem zerados, como a máscara da casa
    assert "123401" not in linha
    assert folha.nome_do_sink("aa:bb:cc:00:00:01") in linha

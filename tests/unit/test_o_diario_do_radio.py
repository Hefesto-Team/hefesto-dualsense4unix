"""O diário comum e a trava do rádio — O-DIARIO-DO-RADIO-01.

Três motores mexiam no rádio sem se conhecer: o watchdog root, o vigia de
zumbis do daemon e a central que vai nascer. Esta régua prova as duas peças que
os põem em fila e deixam rastro:

- a TRAVA: dois processos disputando, o segundo espera, e os dois aparecem no
  diário na ordem. **A mordida:** sem o ``flock`` em ``trava_do_radio``, o
  teste de concorrência vê dois ``Connect`` ao mesmo tempo e reprova;
- o DIÁRIO: quem, o quê, por quê, antes e depois; rotação por tamanho; e o
  leitor que junta o diário dela com o do root pela hora.

Nada aqui toca a trava comum (``/run/hefesto-dualsense4unix/radio.lock``) nem o
diário do root: todo caminho vem de ``tmp_path``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import diario_do_radio as diario

RAIZ = Path(__file__).resolve().parents[2]


# --- o diário -------------------------------------------------------------------


def test_uma_acao_vira_uma_linha_com_quem_o_que_por_que_antes_e_depois(
    tmp_path: Path,
) -> None:
    alvo = tmp_path / "radio-diario.jsonl"
    diario.registrar(
        "vigia-de-zumbis",
        "derrubou o link",
        "conectou e não virou controle",
        antes={"link": "de pé"},
        depois={"link": "caiu"},
        caminho=alvo,
        agora=1000.0,
        adaptador="AA:BB:CC:00:00:01",
        controle="AA:BB:CC:00:00:02",
    )
    linhas = alvo.read_text(encoding="utf-8").splitlines()
    assert len(linhas) == 1
    dado = json.loads(linhas[0])
    assert dado["quem"] == "vigia-de-zumbis"
    assert dado["o_que"] == "derrubou o link"
    assert dado["por_que"] == "conectou e não virou controle"
    assert dado["antes"] == {"link": "de pé"}
    assert dado["depois"] == {"link": "caiu"}
    assert dado["carimbo"] == 1000.0
    assert dado["adaptador"] == "AA:BB:CC:00:00:01"
    assert dado["controle"] == "AA:BB:CC:00:00:02"
    assert "quando" in dado


def test_o_leitor_pula_linha_torta_e_ordena_pela_hora(tmp_path: Path) -> None:
    alvo = tmp_path / "radio-diario.jsonl"
    diario.registrar("b", "segundo", "", caminho=alvo, agora=20.0)
    with alvo.open("a", encoding="utf-8") as fh:
        fh.write("isto não é json\n")
        fh.write('{"sem": "carimbo"}\n')
        fh.write("[1, 2]\n")
    diario.registrar("a", "primeiro", "", caminho=alvo, agora=10.0)
    lidas = diario.ler(caminhos=[alvo])
    assert [e["o_que"] for e in lidas] == ["primeiro", "segundo"]


def test_o_diario_gira_por_tamanho_e_o_leitor_ve_os_dois(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(diario, "TAMANHO_MAXIMO", 400)
    monkeypatch.setenv(diario.ENV_DIARIO, str(tmp_path / "radio-diario.jsonl"))
    monkeypatch.delenv(diario.ENV_DIARIO_DO_ROOT, raising=False)
    for n in range(12):
        diario.registrar("central", f"passo {n}", "rotação", agora=float(n))
    atual = tmp_path / "radio-diario.jsonl"
    girado = tmp_path / "radio-diario.jsonl.1"
    assert girado.exists(), "passou do tamanho e não girou"
    assert atual.stat().st_size <= 400
    lidas = diario.ler()
    #: O leitor junta o girado e o atual; o que girou DUAS vezes saiu, e é
    #: o preço declarado da rotação — só as últimas entradas contam.
    passos = [e["o_que"] for e in lidas]
    assert passos == sorted(passos, key=lambda p: int(p.split()[1]))
    assert passos[-1] == "passo 11"


def test_o_leitor_junta_o_diario_dela_com_o_do_root_pela_hora(tmp_path: Path) -> None:
    dela = tmp_path / "dela.jsonl"
    do_root = tmp_path / "root.jsonl"
    diario.registrar("vigia-de-zumbis", "derrubou o link", "", caminho=dela, agora=2.0)
    diario.registrar("bt-watchdog", "Trusted=true", "", caminho=do_root, agora=1.0)
    diario.registrar("central", "moveu", "", caminho=dela, agora=3.0)
    lidas = diario.ler(caminhos=[dela, do_root])
    assert [e["quem"] for e in lidas] == ["bt-watchdog", "vigia-de-zumbis", "central"]


def test_com_a_suite_no_ar_a_trava_e_o_root_nao_sao_os_dela(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(diario.ENV_TRAVA, raising=False)
    monkeypatch.delenv(diario.ENV_DIARIO_DO_ROOT, raising=False)
    assert diario.caminho_da_trava() != diario.TRAVA_COMUM
    assert diario.caminho_do_diario_do_root() is None


def test_as_pontes_de_pe_saem_do_diario(tmp_path: Path) -> None:
    alvo = tmp_path / "d.jsonl"
    for n, (o_que, controle, tipo) in enumerate(
        [
            (diario.PONTE_SUBIU, "aa:bb:cc:00:00:01", "som"),
            (diario.PONTE_SUBIU, "aa:bb:cc:00:00:02", "som"),
            (diario.PONTE_SUBIU, "aa:bb:cc:00:00:03", "vibracao"),
            (diario.PONTE_DESCEU, "aa:bb:cc:00:00:02", "som"),
        ]
    ):
        diario.registrar(
            "governador", o_que, "", caminho=alvo, agora=float(n),
            controle=controle, adaptador="AA:BB:CC:00:00:CE", tipo=tipo,
        )
    lidas = diario.ler(caminhos=[alvo])
    assert diario.pontes_de_pe(lidas, 2.5) == {
        "AA:BB:CC:00:00:CE": {
            ("aa:bb:cc:00:00:01", "som"),
            ("aa:bb:cc:00:00:02", "som"),
            ("aa:bb:cc:00:00:03", "vibracao"),
        }
    }
    assert diario.pontes_de_pe(lidas, 10.0)["AA:BB:CC:00:00:CE"] == {
        ("aa:bb:cc:00:00:01", "som"),
        ("aa:bb:cc:00:00:03", "vibracao"),
    }


# --- a trava --------------------------------------------------------------------

#: O motor de mentira: pega a trava, registra um `Connect`, segura, solta. A
#: marca em disco é o instrumento da colisão — quem entra e já a encontra está
#: agindo AO MESMO TEMPO que outro motor, que é o defeito que a trava existe
#: para impedir.
MOTOR = textwrap.dedent(
    """
    import sys, time
    from pathlib import Path
    from hefesto_dualsense4unix.integrations import diario_do_radio as d

    quem, trava, alvo, marca, segura = sys.argv[1:6]
    with d.trava_do_radio(quem, caminho=Path(trava), diario=Path(alvo), prazo_s=20):
        marca = Path(marca)
        colidiu = marca.exists()
        marca.write_text(quem)
        d.registrar(quem, "Connect", "motor de mentira", caminho=Path(alvo),
                    depois={"colidiu": colidiu})
        time.sleep(float(segura))
        marca.unlink(missing_ok=True)
    """
)


def _motor(tmp_path: Path, quem: str, segura: float) -> subprocess.Popen[str]:
    roteiro = tmp_path / "motor.py"
    roteiro.write_text(MOTOR, encoding="utf-8")
    env = {**os.environ, "PYTHONPATH": str(RAIZ / "src")}
    return subprocess.Popen(
        [
            sys.executable,
            str(roteiro),
            quem,
            str(tmp_path / "radio.lock"),
            str(tmp_path / "radio-diario.jsonl"),
            str(tmp_path / "ocupado"),
            str(segura),
        ],
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _espera_a_entrada(alvo: Path, quem: str, o_que: str, prazo_s: float = 15.0) -> None:
    fim = time.monotonic() + prazo_s
    while time.monotonic() < fim:
        for entrada in diario.ler(caminhos=[alvo]):
            if entrada["quem"] == quem and entrada["o_que"] == o_que:
                return
        time.sleep(0.05)
    raise AssertionError(f"{quem} não registrou {o_que!r} em {prazo_s} s")


def test_dois_motores_disputam_a_trava_e_o_segundo_espera(tmp_path: Path) -> None:
    """O segundo espera, e os dois aparecem no diário na ordem.

    ARRANQUE A CURA — tire o ``fcntl.flock`` de ``trava_do_radio`` — e o
    segundo motor entra com o primeiro ainda dentro: o ``Connect`` dele sai com
    ``colidiu=True`` e este teste reprova dizendo «dois Connect».
    """
    alvo = tmp_path / "radio-diario.jsonl"
    primeiro = _motor(tmp_path, "watchdog", 1.0)
    try:
        _espera_a_entrada(alvo, "watchdog", "Connect")
        segundo = _motor(tmp_path, "central", 0.1)
        saida2 = segundo.communicate(timeout=30)
    finally:
        saida1 = primeiro.communicate(timeout=30)
    assert primeiro.returncode == 0, saida1
    assert segundo.returncode == 0, saida2

    lidas = diario.ler(caminhos=[alvo])
    connects = [e for e in lidas if e["o_que"] == "Connect"]
    assert not any(e["depois"]["colidiu"] for e in connects), (
        "dois Connect ao mesmo tempo — um motor agiu com a trava na mão de outro"
    )
    assert [(e["quem"], e["o_que"]) for e in lidas] == [
        ("watchdog", "Connect"),
        ("central", diario.ESPEROU_A_TRAVA),
        ("central", "Connect"),
    ]
    espera = lidas[1]
    assert espera["antes"]["dono"].startswith("watchdog "), espera
    assert espera["depois"]["espera_s"] > 0.3


def test_quem_nao_consegue_no_prazo_desiste_e_diz(tmp_path: Path) -> None:
    alvo = tmp_path / "radio-diario.jsonl"
    trava = tmp_path / "radio.lock"
    primeiro = _motor(tmp_path, "watchdog", 3.0)
    try:
        _espera_a_entrada(alvo, "watchdog", "Connect")
        with (
            pytest.raises(diario.TravaOcupadaError) as pego,
            diario.trava_do_radio(
                "vigia-de-zumbis", caminho=trava, diario=alvo, prazo_s=0.3
            ),
        ):
            raise AssertionError("entrou com a trava na mão do watchdog")
    finally:
        primeiro.communicate(timeout=30)
    assert pego.value.dono.startswith("watchdog ")
    desistencias = [
        e for e in diario.ler(caminhos=[alvo]) if e["o_que"] == diario.DESISTIU_DA_TRAVA
    ]
    assert len(desistencias) == 1
    assert desistencias[0]["quem"] == "vigia-de-zumbis"


def test_a_trava_livre_nao_registra_espera(tmp_path: Path) -> None:
    alvo = tmp_path / "radio-diario.jsonl"
    with diario.trava_do_radio(
        "central", caminho=tmp_path / "radio.lock", diario=alvo
    ) as espera:
        assert espera == 0.0
    assert not alvo.exists(), "trava livre não é espera, e não vai para o diário"
    assert diario.dono_da_trava(tmp_path / "radio.lock").startswith("central ")


def test_a_trava_sai_quando_o_processo_morre(tmp_path: Path) -> None:
    """O ``flock`` é do kernel: quem caiu não deixa a trava presa."""
    primeiro = _motor(tmp_path, "watchdog", 30.0)
    try:
        _espera_a_entrada(tmp_path / "radio-diario.jsonl", "watchdog", "Connect")
        primeiro.kill()
    finally:
        primeiro.communicate(timeout=30)
    with diario.trava_do_radio(
        "central", caminho=tmp_path / "radio.lock", diario=tmp_path / "d.jsonl",
        prazo_s=2.0,
    ) as espera:
        assert espera < 2.0

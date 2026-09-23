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
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """ARRANQUE A GUARDA da suíte em ``caminho_da_trava`` e este teste reprova.

    A trava comum FINGE estar instalada: sem isso, a régua respondia se o
    install desta máquina já criou ``/run/hefesto-dualsense4unix`` — e não se a
    guarda existe. Medido na conferência de 23/09: com a guarda arrancada e a
    pasta ainda ausente, o teste passava verde.
    """
    comum = tmp_path / "run" / "radio.lock"
    comum.parent.mkdir()
    monkeypatch.setattr(diario, "TRAVA_COMUM", comum)
    monkeypatch.delenv(diario.ENV_TRAVA, raising=False)
    monkeypatch.delenv(diario.ENV_DIARIO_DO_ROOT, raising=False)
    assert diario.caminho_da_trava() != comum
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


# --- as lápides -----------------------------------------------------------------
#
# Mover um controle (a R1 dela) apaga o bond no adaptador antigo. O snapshot de
# antes do gesto ainda o tem, e o autorestore — aditivo — o devolveria no
# primeiro crash do bluetoothd. A lápide é o «esquecido de propósito»: um
# controle num adaptador, escrita pelo `esquecer` da ponte, lida pelo
# autorestore. Faixa sintética `aa:bb:cc`, como manda o anonimato de fixture.

PONTE = RAIZ / "scripts" / "bt_ponte_privilegiada.sh"
AUTORESTORE = RAIZ / "scripts" / "bt_bonds_autorestore.sh"

ADAPTADOR = "AA:BB:CC:00:00:11"
OUTRO_ADAPTADOR = "AA:BB:CC:00:00:33"
VERMELHO = "AA:BB:CC:00:00:22"
AZUL = "AA:BB:CC:00:00:44"


def _info_com_chave() -> str:
    return "[General]\nName=DualSense Wireless Controller\n\n[LinkKey]\nKey=AAAA\nType=4\n"


def _nome_do_snapshot(epoch: int) -> str:
    return time.strftime("%Y%m%d-%H%M%S", time.localtime(epoch)) + "-4242"


def _snapshot(acervo: Path, epoch: int, pares: list[tuple[str, str]]) -> None:
    for adaptador, controle in pares:
        dev = acervo / _nome_do_snapshot(epoch) / adaptador / controle
        dev.mkdir(parents=True, exist_ok=True)
        (dev / "info").write_text(_info_com_chave(), encoding="utf-8")


def _autorestore(acervo: Path, destino: Path, agora: int) -> subprocess.CompletedProcess[str]:
    destino.mkdir(parents=True, exist_ok=True)
    env = {
        **os.environ,
        "HEFESTO_BT_BONDS_SRC": str(acervo),
        "HEFESTO_BT_DST": str(destino),
        "HEFESTO_BT_BOOT_ID": "boot-do-ensaio-lapide",
        "HEFESTO_BT_AGORA": str(agora),
        "HEFESTO_BT_LOG_DEST": "none",
        "SERVICE_RESULT": "core-dump",
    }
    return subprocess.run(
        ["bash", str(AUTORESTORE)], capture_output=True, text=True, timeout=60, env=env
    )


def _voltou(destino: Path, adaptador: str, controle: str) -> bool:
    return (destino / adaptador / controle / "info").exists()


def test_a_lapide_segura_um_controle_e_deixa_os_outros_voltarem(tmp_path: Path) -> None:
    """O crash comeu os dois bonds; só o esquecido de propósito fica fora.

    ARRANQUE A CURA — tire o bloco da LÁPIDE do ``bt_bonds_autorestore.sh`` — e
    o vermelho volta do snapshot: este teste reprova.
    """
    agora = int(time.time())
    acervo, destino = tmp_path / "acervo", tmp_path / "bluetooth"
    _snapshot(acervo, agora - 600, [(ADAPTADOR, VERMELHO), (ADAPTADOR, AZUL)])
    (acervo / ".lapides").write_text(f"{agora - 300} {ADAPTADOR} {VERMELHO}\n", encoding="utf-8")
    resultado = _autorestore(acervo, destino, agora)
    assert resultado.returncode == 0, resultado.stderr
    assert _voltou(destino, ADAPTADOR, AZUL), resultado.stdout
    assert not _voltou(destino, ADAPTADOR, VERMELHO), (
        "o bond esquecido de propósito voltou do snapshot — o controle movido "
        "teria casa em dois adaptadores de novo"
    )
    assert "LÁPIDE" in resultado.stdout
    assert "1 esquecido(s) de propósito" in resultado.stdout


def test_pareado_de_novo_depois_da_lapide_volta(tmp_path: Path) -> None:
    """A lápide só enterra o que existia ANTES dela."""
    agora = int(time.time())
    acervo, destino = tmp_path / "acervo", tmp_path / "bluetooth"
    _snapshot(acervo, agora - 60, [(ADAPTADOR, VERMELHO)])
    (acervo / ".lapides").write_text(f"{agora - 300} {ADAPTADOR} {VERMELHO}\n", encoding="utf-8")
    resultado = _autorestore(acervo, destino, agora)
    assert _voltou(destino, ADAPTADOR, VERMELHO), resultado.stdout


def test_a_lapide_e_de_um_controle_num_adaptador(tmp_path: Path) -> None:
    """Esquecer o vermelho no adaptador 11 não enterra o vermelho no 33."""
    agora = int(time.time())
    acervo, destino = tmp_path / "acervo", tmp_path / "bluetooth"
    _snapshot(acervo, agora - 600, [(ADAPTADOR, VERMELHO), (OUTRO_ADAPTADOR, VERMELHO)])
    (acervo / ".lapides").write_text(f"{agora - 300} {ADAPTADOR} {VERMELHO}\n", encoding="utf-8")
    _autorestore(acervo, destino, agora)
    assert not _voltou(destino, ADAPTADOR, VERMELHO)
    assert _voltou(destino, OUTRO_ADAPTADOR, VERMELHO)


def test_linha_torta_na_lista_nao_enterra_ninguem(tmp_path: Path) -> None:
    agora = int(time.time())
    acervo, destino = tmp_path / "acervo", tmp_path / "bluetooth"
    _snapshot(acervo, agora - 600, [(ADAPTADOR, VERMELHO)])
    (acervo / ".lapides").write_text(
        f"ontem {ADAPTADOR} {VERMELHO}\n{agora} {ADAPTADOR}\n{agora} x y\n", encoding="utf-8"
    )
    _autorestore(acervo, destino, agora)
    assert _voltou(destino, ADAPTADOR, VERMELHO)


def _ambiente_da_ponte(tmp_path: Path, **extra: str) -> dict[str, str]:
    env = {
        chave: valor
        for chave, valor in os.environ.items()
        if chave not in ("SUDO_UID", "SUDO_USER")
    }
    env.update(
        HEFESTO_BT_LIB=str(tmp_path / "bluetooth"),
        HEFESTO_BT_LOG_DEST="none",
        HEFESTO_RADIO_DIARIO_ROOT=str(tmp_path / "diario-root.jsonl"),
        **extra,
    )
    return env


def test_o_esquecer_da_ponte_escreve_a_lapide_que_o_autorestore_le(tmp_path: Path) -> None:
    """De ponta a ponta: o gesto que apaga é o mesmo que enterra."""
    agora = int(time.time())
    acervo = tmp_path / "acervo"
    _snapshot(acervo, agora - 600, [(ADAPTADOR, VERMELHO), (ADAPTADOR, AZUL)])
    bond = tmp_path / "bluetooth" / ADAPTADOR / VERMELHO
    bond.mkdir(parents=True)
    (bond / "info").write_text(_info_com_chave(), encoding="utf-8")

    resultado = subprocess.run(
        ["bash", str(PONTE), "esquecer", ADAPTADOR.lower(), VERMELHO.lower()],
        capture_output=True,
        text=True,
        timeout=60,
        env=_ambiente_da_ponte(tmp_path, HEFESTO_BT_LAPIDES=str(acervo / ".lapides")),
    )
    assert resultado.returncode == 0, resultado.stderr
    assert not bond.exists()
    linhas = (acervo / ".lapides").read_text(encoding="utf-8").splitlines()
    assert len(linhas) == 1, "uma lápide, de UM controle, num adaptador"
    quando, adaptador, controle = linhas[0].split()
    assert (adaptador, controle) == (ADAPTADOR, VERMELHO)
    assert abs(int(quando) - agora) < 60

    [entrada] = diario.ler(caminhos=[tmp_path / "diario-root.jsonl"])
    assert entrada["o_que"] == "esqueceu o controle"
    assert entrada["controle"] == VERMELHO
    assert entrada["depois"] == {"bond": None, "lapide": True}

    destino = tmp_path / "bluetooth-depois-do-crash"
    _autorestore(acervo, destino, agora + 5)
    assert _voltou(destino, ADAPTADOR, AZUL)
    assert not _voltou(destino, ADAPTADOR, VERMELHO)


def test_o_esquecer_a_seco_so_diz_a_lapide(tmp_path: Path) -> None:
    lapides = tmp_path / ".lapides"
    resultado = subprocess.run(
        ["bash", str(PONTE), "--dry-run", "esquecer", ADAPTADOR, VERMELHO],
        capture_output=True,
        text=True,
        timeout=60,
        env=_ambiente_da_ponte(tmp_path, HEFESTO_BT_LAPIDES=str(lapides)),
    )
    assert resultado.returncode == 0, resultado.stderr
    assert "gravaria a lápide" in resultado.stdout
    assert not lapides.exists()


# --- o adaptador travado em laço (família 3) --------------------------------------
#
# O laço de 13/09, com as linhas reais (três por volta, a cada ~2,5 s), sobre
# uma mesa sysfs de mentira: o adaptador travado está na porta 3-1.1.2, e um
# vizinho são, na 3-4.1.4, teve UM timeout solto — que acontece em adaptador são.

LACO_DE_13_09 = "".join(
    f"2026-09-13T01:{13 + (s // 60):02d}:{s % 60:02d}-03:00 maquina kernel: Bluetooth: hci0: {m}\n"
    for s in range(45, 60, 2)
    for m in (
        "command 0xfc61 tx timeout",
        "RTL: RTL: Read reg16 failed (-110)",
        "RTL: Failed to generate devcoredump",
    )
) + "2026-09-13T01:14:10-03:00 maquina kernel: Bluetooth: hci1: command 0x0c03 tx timeout\n"


def _mesa_sysfs(raiz: Path, adaptadores: dict[str, str]) -> Path:
    """``{hciN: porta}`` → um /sys com class/bluetooth, bus/usb/devices e o authorized."""
    for hci, porta in adaptadores.items():
        aparelho = raiz / "devices" / "pci0000:00" / "usb" / porta
        interface = aparelho / f"{porta}:1.0"
        (interface / "bluetooth" / hci).mkdir(parents=True)
        (aparelho / "authorized").write_text("semente", encoding="utf-8")
        classe = raiz / "class" / "bluetooth"
        classe.mkdir(parents=True, exist_ok=True)
        (classe / hci).symlink_to(interface / "bluetooth" / hci)
        barramento = raiz / "bus" / "usb" / "devices"
        barramento.mkdir(parents=True, exist_ok=True)
        (barramento / porta).symlink_to(aparelho)
    return raiz


def _reiniciar(
    tmp_path: Path, sysfs: Path, *args: str, **extra: str
) -> subprocess.CompletedProcess[str]:
    journal = tmp_path / "journal.txt"
    if not journal.exists():
        journal.write_text(LACO_DE_13_09, encoding="utf-8")
    env = _ambiente_da_ponte(
        tmp_path,
        HEFESTO_SYSFS_RAIZ=str(sysfs),
        HEFESTO_BT_JOURNAL=str(journal),
        HEFESTO_PONTE_STAMPS=str(tmp_path / "stamps"),
        HEFESTO_USB_PAUSA_S="0",
        HEFESTO_USB_ESPERA_S="0",
        **extra,
    )
    return subprocess.run(
        ["bash", str(PONTE), "reiniciar-travado", *args],
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )


def _autorizado(sysfs: Path, porta: str) -> str:
    return (sysfs / "bus" / "usb" / "devices" / porta / "authorized").read_text(encoding="utf-8")


def test_o_laco_de_13_09_reinicia_uma_porta_so_e_a_certa(tmp_path: Path) -> None:
    """Exatamente um reinício, na porta do adaptador em laço.

    ARRANQUE O DETECTOR — faça ``_hcis_em_laco`` não imprimir nada — e o teste
    não vê reinício nenhum. Baixe o ``LIMIAR_DO_LACO`` para 1 e o vizinho são
    também é reiniciado: o teste reprova pelos dois.
    """
    sysfs = _mesa_sysfs(tmp_path / "sys", {"hci0": "3-1.1.2", "hci1": "3-4.1.4"})
    resultado = _reiniciar(tmp_path, sysfs)
    assert resultado.returncode == 0, resultado.stderr
    assert resultado.stdout.splitlines() == ["reiniciado\t3-1.1.2\thci0\t8"]
    assert _autorizado(sysfs, "3-1.1.2") == "1", "a porta do travado não foi reautorizada"
    assert _autorizado(sysfs, "3-4.1.4") == "semente", "o vizinho são foi tocado"
    [entrada] = diario.ler(caminhos=[tmp_path / "diario-root.jsonl"])
    assert entrada["o_que"] == "reiniciou o adaptador"
    assert entrada["porta"] == "3-1.1.2"
    assert entrada["familia"] == "3"
    assert entrada["antes"] == {"hci": "hci0", "timeouts": 8}
    assert entrada["depois"] == {"hci": "hci0", "voltou": True}


def test_com_conexao_de_pe_o_reinicio_e_recusado(tmp_path: Path) -> None:
    """Um adaptador com controle ligado não é reiniciado, diga o journal o que disser."""
    sysfs = _mesa_sysfs(tmp_path / "sys", {"hci0": "3-1.1.2"})
    conexao = sysfs / "devices" / "pci0000:00" / "usb" / "3-1.1.2" / "3-1.1.2:1.0"
    (conexao / "bluetooth" / "hci0" / "hci0:256").mkdir()
    (sysfs / "class" / "bluetooth" / "hci0:256").symlink_to(
        conexao / "bluetooth" / "hci0" / "hci0:256"
    )
    resultado = _reiniciar(tmp_path, sysfs)
    assert resultado.returncode == 1
    assert resultado.stdout.splitlines() == ["recusado\t3-1.1.2\thci0\thá conexão de pé"]
    assert _autorizado(sysfs, "3-1.1.2") == "semente"
    [entrada] = diario.ler(caminhos=[tmp_path / "diario-root.jsonl"])
    assert entrada["o_que"] == "recusou reiniciar o adaptador"


def test_o_freio_nao_reinicia_a_mesma_porta_duas_vezes(tmp_path: Path) -> None:
    sysfs = _mesa_sysfs(tmp_path / "sys", {"hci0": "3-1.1.2"})
    assert _reiniciar(tmp_path, sysfs).returncode == 0
    (sysfs / "bus" / "usb" / "devices" / "3-1.1.2" / "authorized").write_text(
        "semente", encoding="utf-8"
    )
    segundo = _reiniciar(tmp_path, sysfs)
    assert segundo.returncode == 0
    assert segundo.stdout.startswith("segurado\t3-1.1.2\thci0\t")
    assert _autorizado(sysfs, "3-1.1.2") == "semente", "reiniciou de novo dentro do freio"
    frases = [e.get("frase") for e in diario.ler(caminhos=[tmp_path / "diario-root.jsonl"])]
    assert "O adaptador da porta 3-1.1.2 travou de novo. Tire e ponha ele." in frases


def test_sem_laco_nada_acontece(tmp_path: Path) -> None:
    sysfs = _mesa_sysfs(tmp_path / "sys", {"hci0": "3-1.1.2"})
    (tmp_path / "journal.txt").write_text(LACO_DE_13_09.splitlines()[0] + "\n", encoding="utf-8")
    resultado = _reiniciar(tmp_path, sysfs)
    assert resultado.returncode == 0
    assert resultado.stdout == ""
    assert _autorizado(sysfs, "3-1.1.2") == "semente"


def test_o_reinicio_nao_aceita_argumento(tmp_path: Path) -> None:
    sysfs = _mesa_sysfs(tmp_path / "sys", {"hci0": "3-1.1.2"})
    resultado = _reiniciar(tmp_path, sysfs, "3-4.1.4")
    assert resultado.returncode == 2
    assert _autorizado(sysfs, "3-1.1.2") == "semente"


def test_os_ganchos_do_reinicio_morrem_sob_sudo(tmp_path: Path) -> None:
    """Sob sudo o /sys de mentira some: o verbo mira o /sys real e exige root."""
    sysfs = _mesa_sysfs(tmp_path / "sys", {"hci0": "3-1.1.2"})
    resultado = _reiniciar(tmp_path, sysfs, SUDO_UID="1000")
    if os.geteuid() == 0:  # pragma: no cover - a suíte não roda como root
        pytest.skip("como root o verbo alcançaria o /sys real")
    assert resultado.returncode == 1
    assert "requer root" in resultado.stderr
    assert _autorizado(sysfs, "3-1.1.2") == "semente"
    assert not (tmp_path / "diario-root.jsonl").exists()


# --- o watchdog root na mesma trava e no mesmo diário ------------------------------

WATCHDOG = RAIZ / "scripts" / "bt_health_watchdog.sh"


def _watchdog(tmp_path: Path, *args: str, prazo: str = "5") -> subprocess.Popen[str]:
    env = {
        **os.environ,
        "HEFESTO_BT_SRC": str(tmp_path / "bluetooth"),
        "HEFESTO_BT_STAMP_DIR": str(tmp_path / "stamps"),
        "HEFESTO_BT_LOG_DEST": "none",
        "HEFESTO_RADIO_TRAVA": str(tmp_path / "radio.lock"),
        "HEFESTO_RADIO_TRAVA_PRAZO_S": prazo,
        "HEFESTO_RADIO_DIARIO_ROOT": str(tmp_path / "diario-root.jsonl"),
    }
    return subprocess.Popen(
        ["bash", str(WATCHDOG), *args],
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def test_o_watchdog_espera_a_trava_que_o_daemon_segura(tmp_path: Path) -> None:
    """O shell root e o Python dela disputam o MESMO arquivo, e a espera vai
    para o diário do root com a palavra que o leitor procura."""
    primeiro = _motor(tmp_path, "central", 1.0)
    try:
        _espera_a_entrada(tmp_path / "radio-diario.jsonl", "central", "Connect")
        watchdog = _watchdog(tmp_path, "--so-a-trava", "0")
        saida = watchdog.communicate(timeout=30)
    finally:
        primeiro.communicate(timeout=30)
    assert watchdog.returncode == 0, saida
    [espera] = diario.ler(caminhos=[tmp_path / "diario-root.jsonl"])
    assert espera["quem"] == "bt-watchdog"
    assert espera["o_que"] == diario.ESPEROU_A_TRAVA
    assert espera["antes"]["dono"].startswith("central ")
    assert espera["depois"]["espera_s"] > 0.3
    assert diario.dono_da_trava(tmp_path / "radio.lock").startswith("bt-watchdog ")


def test_o_watchdog_pula_o_tique_quando_nao_consegue_a_trava(tmp_path: Path) -> None:
    primeiro = _motor(tmp_path, "central", 4.0)
    try:
        _espera_a_entrada(tmp_path / "radio-diario.jsonl", "central", "Connect")
        watchdog = _watchdog(tmp_path, "--so-a-trava", "0", prazo="1")
        watchdog.communicate(timeout=30)
    finally:
        primeiro.communicate(timeout=30)
    assert watchdog.returncode == 3
    [desistencia] = diario.ler(caminhos=[tmp_path / "diario-root.jsonl"])
    assert desistencia["o_que"] == diario.DESISTIU_DA_TRAVA


def test_o_daemon_espera_a_trava_que_o_watchdog_segura(tmp_path: Path) -> None:
    watchdog = _watchdog(tmp_path, "--so-a-trava", "1")
    try:
        fim = time.monotonic() + 15
        while time.monotonic() < fim:
            if diario.dono_da_trava(tmp_path / "radio.lock").startswith("bt-watchdog"):
                break
            time.sleep(0.05)
        with diario.trava_do_radio(
            "vigia-de-zumbis",
            caminho=tmp_path / "radio.lock",
            diario=tmp_path / "dela.jsonl",
            prazo_s=10,
        ) as espera:
            assert espera > 0.3
    finally:
        watchdog.communicate(timeout=30)
    [entrada] = diario.ler(caminhos=[tmp_path / "dela.jsonl"])
    assert entrada["antes"]["dono"].startswith("bt-watchdog ")


def test_o_tique_inteiro_roda_com_a_trava() -> None:
    """O tique pega a trava ANTES da primeira vigia que age.

    Rodar o tique de verdade aqui falaria com o BlueZ dela (``busctl
    set-property``, ``systemctl restart``), então esta régua lê a ORDEM do
    script — é a única forma sem tocar o rádio. Os testes do ``--so-a-trava``
    provam o ``_pegar_a_trava``; este prova que o tique o chama. Medido na
    conferência de 23/09: arrancar a chamada do corpo do script passava verde
    em todas as réguas.

    ARRANQUE A CURA — tire o ``_pegar_a_trava || exit 0`` do corpo, ou desça-o
    para depois da vigia 0 — e este teste reprova.
    """
    linhas = WATCHDOG.read_text(encoding="utf-8").splitlines()
    pega = [n for n, linha in enumerate(linhas) if linha == "_pegar_a_trava || exit 0"]
    assert len(pega) == 1, "o tique não pega a trava do rádio no corpo do script"
    gancho = next(n for n, linha in enumerate(linhas) if '"--so-a-trava"' in linha)
    vigia0 = next(n for n, linha in enumerate(linhas) if linha.startswith("# --- vigia 0"))
    assert gancho < pega[0] < vigia0, "a trava tem de vir antes da primeira vigia"
    #: Chamada no corpo do script (não a definição da função, nem o gancho
    #: ``--sdp-cache-only`` da régua, que é indentado e sai antes).
    for n, linha in enumerate(linhas[: pega[0]]):
        if linha.endswith("() {"):
            continue
        assert not linha.startswith(("vigia_", "systemctl ", "busctl ")), (
            f"linha {n + 1} age no rádio antes de o tique pegar a trava: {linha}"
        )


def test_o_watchdog_na_arvore_de_teste_nao_pega_a_trava_da_maquina(tmp_path: Path) -> None:
    """Com a árvore do BlueZ desviada e sem o gancho, nada de trava comum.

    ARRANQUE A GUARDA — volte o default do ``TRAVA_DO_RADIO`` para a trava
    comum — e o watchdog de teste diz que foi atrás dela.
    """
    env = {
        chave: valor for chave, valor in os.environ.items() if chave != "HEFESTO_RADIO_TRAVA"
    }
    env.update(
        HEFESTO_BT_SRC=str(tmp_path / "bluetooth"),
        HEFESTO_BT_STAMP_DIR=str(tmp_path / "stamps"),
        HEFESTO_BT_LOG_DEST="none",
        HEFESTO_RADIO_DIARIO_ROOT=str(tmp_path / "diario-root.jsonl"),
    )
    resultado = subprocess.run(
        ["bash", str(WATCHDOG), "--so-a-trava", "0"],
        capture_output=True, text=True, timeout=30, env=env,
    )
    assert resultado.returncode == 0, resultado.stderr
    assert "sigo sem a trava" in resultado.stdout
    assert "/run/hefesto-dualsense4unix" not in resultado.stdout


def _bloco_do_diario(texto: str) -> str:
    return texto[texto.index("#: Texto -> string JSON.") : texto.index("_diario_escrever() {")] + (
        texto[texto.index("_diario_escrever() {") :].split("\n}\n", 1)[0]
    )


def test_os_dois_escritores_root_do_diario_sao_a_mesma_copia() -> None:
    """Sem ``source`` de propósito — então a igualdade tem de ser vigiada."""
    ponte = _bloco_do_diario(PONTE.read_text(encoding="utf-8"))
    watchdog = _bloco_do_diario(WATCHDOG.read_text(encoding="utf-8"))
    assert ponte == watchdog, "as duas cópias do escritor root do diário divergiram"


def test_a_linha_do_shell_com_aspas_e_acento_o_python_le(tmp_path: Path) -> None:
    alvo = tmp_path / "root.jsonl"
    roteiro = (
        f'source <(sed -n "/^_json_texto() {{/,/^}}/p; /^_diario_escrever() {{/,/^}}/p" '
        f'"{PONTE}")\n'
        f'_diario_escrever "{alvo}" "bt-ponte" "reiniciou o adaptador" '
        '"três \\"aspas\\" e uma \\\\ barra" "{\\"hci\\": \\"hci0\\"}" null '
        '"\\"porta\\": \\"3-1.1.2\\""\n'
    )
    subprocess.run(["bash", "-c", roteiro], check=True, timeout=30)
    [entrada] = diario.ler(caminhos=[alvo])
    assert entrada["por_que"] == 'três "aspas" e uma \\ barra'
    assert entrada["antes"] == {"hci": "hci0"}
    assert entrada["depois"] is None
    assert entrada["porta"] == "3-1.1.2"


# --- o vigia de zumbis do daemon na mesma trava ------------------------------------


class _PonteDeMentira:
    """A ponte de verdade sem sudo: anota quem pediu, e quando."""

    def __init__(self) -> None:
        self.pedidos: list[str] = []

    def impedimentos(self) -> list[str]:
        return []

    def desconectar(self, link: object) -> tuple[bool, str]:
        self.pedidos.append(link.controle)  # type: ignore[attr-defined]
        return True, ""


def _link() -> object:
    from hefesto_dualsense4unix.integrations.conexao_zumbi import LinkDeRadio

    return LinkDeRadio(hci="hci0", adaptador="AA:BB:CC:00:00:11", controle="AA:BB:CC:00:00:22")


def test_o_vigia_derruba_o_link_com_a_trava_e_deixa_rastro(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hefesto_dualsense4unix.daemon.subsystems.conexoes import PonteComTrava

    monkeypatch.setenv(diario.ENV_TRAVA, str(tmp_path / "radio.lock"))
    monkeypatch.setenv(diario.ENV_DIARIO, str(tmp_path / "radio-diario.jsonl"))
    interna = _PonteDeMentira()
    ponte = PonteComTrava(interna=interna)  # type: ignore[arg-type]
    assert ponte.desconectar(_link()) == (True, "")  # type: ignore[arg-type]
    assert interna.pedidos == ["AA:BB:CC:00:00:22"]
    [entrada] = diario.ler(caminhos=[tmp_path / "radio-diario.jsonl"])
    assert (entrada["quem"], entrada["o_que"]) == ("vigia-de-zumbis", "derrubou o link")
    assert entrada["controle"] == "AA:BB:CC:00:00:22"
    assert entrada["hci"] == "hci0"
    assert diario.dono_da_trava(tmp_path / "radio.lock").startswith("vigia-de-zumbis ")


def test_com_a_trava_na_mao_do_watchdog_o_vigia_nao_derruba_nada(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Dois motores no mesmo rádio: o vigia espera o prazo e desiste da volta.

    ARRANQUE A CURA — faça o ``ConexoesSubsystem`` montar a
    ``PontePrivilegiada`` crua — e ``test_o_daemon_monta_o_vigia_com_a_trava``
    reprova; arranque a trava da ``PonteComTrava`` e este reprova com o link
    derrubado por cima do watchdog.
    """
    from hefesto_dualsense4unix.daemon.subsystems.conexoes import PonteComTrava

    monkeypatch.setenv(diario.ENV_TRAVA, str(tmp_path / "radio.lock"))
    monkeypatch.setenv(diario.ENV_DIARIO, str(tmp_path / "dela.jsonl"))
    watchdog = _watchdog(tmp_path, "--so-a-trava", "3")
    try:
        fim = time.monotonic() + 15
        while not diario.dono_da_trava(tmp_path / "radio.lock").startswith("bt-watchdog"):
            assert time.monotonic() < fim, "o watchdog não pegou a trava"
            time.sleep(0.05)
        interna = _PonteDeMentira()
        ponte = PonteComTrava(interna=interna, prazo_s=0.3)  # type: ignore[arg-type]
        agiu, motivo = ponte.desconectar(_link())  # type: ignore[arg-type]
    finally:
        watchdog.communicate(timeout=30)
    assert (agiu, interna.pedidos) == (False, []), "derrubou o link com o watchdog agindo"
    assert "próxima volta" in motivo
    [desistencia] = diario.ler(caminhos=[tmp_path / "dela.jsonl"])
    assert desistencia["o_que"] == diario.DESISTIU_DA_TRAVA
    assert desistencia["antes"]["dono"].startswith("bt-watchdog ")


def test_o_daemon_monta_o_vigia_com_a_trava() -> None:
    from hefesto_dualsense4unix.daemon.subsystems.conexoes import (
        ConexoesSubsystem,
        PonteComTrava,
    )

    assert isinstance(ConexoesSubsystem()._vigia.ponte, PonteComTrava)


def test_o_watchdog_root_recusa_trava_que_e_link(tmp_path: Path) -> None:
    """Root num arquivo que ela também abre: um link no lugar da trava não leva a
    escrita do root a outro arquivo.

    ARRANQUE A GUARDA — tire o ``[[ -L "${TRAVA_DO_RADIO}" ]]`` de
    ``_pegar_a_trava`` — e o nome do watchdog aparece dentro do alvo do link.
    """
    alvo = tmp_path / "arquivo-de-outra-pessoa"
    alvo.write_text("intocado\n", encoding="utf-8")
    (tmp_path / "radio.lock").symlink_to(alvo)
    watchdog = _watchdog(tmp_path, "--so-a-trava", "0")
    saida, _erro = watchdog.communicate(timeout=30)
    assert watchdog.returncode == 0
    assert "link simbólico" in saida
    assert alvo.read_text(encoding="utf-8") == "intocado\n"

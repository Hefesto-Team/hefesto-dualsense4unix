"""BT-AGENT-TRAVA-O-RESTART-01, E4 e E5 — o gancho de parada não segura o rádio.

Sprint: docs/process/sprints/2026-08-04-BT-AGENT-TRAVA-O-RESTART-01-*.md

O QUE FOI MEDIDO (06/08/2026, journal dela, crash das 21:03):

    21:03:44  bluetooth.service: Watchdog timeout (limit 30s)!
    21:03:51  Main process exited, code=dumped, status=6/ABRT
    21:04:34  Failed with result 'watchdog'                  <- +42,8 s
    21:04:39  Starting bluetooth.service...
    21:04:41  Started bluetooth.service                      <- 57,25 s no total

Os 42,8 s foram gastos DENTRO do `ExecStopPost`. Controle: o mesmo script,
rodado à mão como root sobre a mesma fonte real (3 bonds, cache SDP completo),
custa **0,03 s**; e no ciclo limpo das 21:04:40 o mesmo gancho custou 29 ms.
1.400x entre o custo próprio e o custo no naufrágio — o tempo era CONTENÇÃO.

AS DUAS MORDIDAS:

  E4 — no gancho de parada, o `flock` do snapshot desiste NA HORA (`-n`). O
       systemd só reinicia o `bluetoothd` depois que o `ExecStopPost` sai; cada
       segundo esperando por um lock é segundo de Bluetooth fora do ar. Perder
       o snapshot não custa nada (o timer de 15 min e a borda udev da
       83-hefesto-bond-snapshot.rules cobrem); perder o rádio custa tudo.
       Arranque o `-n` (volte ao `-w 30` de sempre) e
       `test_no_gancho_de_parada_desiste_na_hora` estoura o teto de tempo.

  E4-bis — FORA do gancho ele CONTINUA esperando. Trocar o `-w 30` por `-n`
       global perderia a serialização do SNAPSHOT-LOCK-01 (22/07 22:43:13: dois
       processos no mesmo diretório-timestamp, `install` falhando com "não foi
       possível mudar as permissões"). Ponha `-n` nos dois caminhos e
       `test_fora_do_gancho_espera_a_vez` reprova.

  E5 — o drop-in declara `TimeoutStopSec`. Sem ele vale o padrão de 90 s, que é
       o que deixou os 42,8 s correrem soltos. Arranque a linha e
       `test_dropin_poe_teto_no_tempo_de_parada` reprova.

Nada aqui fala com o systemd da máquina: o E4 roda o script DE VERDADE contra
raízes de teste, o E5 lê o arquivo da unit.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = REPO_ROOT / "scripts" / "bt_bonds_snapshot.sh"
DROPIN = REPO_ROOT / "assets" / "systemd" / "bluetooth-dropin-10-hefesto-resilience.conf"

#: Faixa sintética canônica das fixtures (test_anonimato_de_fixtures.py).
ADAPTER = "AA:BB:CC:00:00:01"
CONTROLE = "AA:BB:CC:00:00:02"

#: Teto de paciência do teste. O caminho curado responde em milissegundos; o
#: `-w 30` arrancado responde em 30 s. Qualquer valor entre os dois separa os
#: dois mundos — 6 s deixa folga para máquina carregada sem chegar perto de 30.
TETO_S = 6.0
#: Quanto tempo o teste espera antes de concluir que o script FICOU esperando.
#: Só o caminho não-gancho passa por aqui, e ele só precisa provar que não
#: desistiu de imediato.
PACIENCIA_S = 3.0


def _fonte_com_um_bond(raiz: Path) -> Path:
    """Uma árvore /var/lib/bluetooth de mentira, com um bond de verdade.

    Sem pelo menos um `info` o script sai antes do `flock` ("zero bonds em
    disco — snapshot recusado"), e o teste mediria o nada.
    """
    dev = raiz / ADAPTER / CONTROLE
    dev.mkdir(parents=True)
    (dev / "info").write_text(
        "[General]\nName=DualSense Wireless Controller\n\n[LinkKey]\nKey=AAAA\n",
        encoding="utf-8",
    )
    return raiz


def _ambiente(
    fonte: Path, acervo: Path, diario: Path, service_result: str | None
) -> dict[str, str]:
    # DIÁRIO-QUE-NAO-MENTE-01 (15/08/2026): o log vai para arquivo, nunca para o
    # journal dela — a suíte roda o script DE VERDADE e sem isto grava linhas
    # que descrevem eventos que nunca aconteceram.
    env = {
        **os.environ,
        "HEFESTO_BT_SRC": str(fonte),
        "HEFESTO_BT_SNAP_ROOT": str(acervo),
        "HEFESTO_BT_LOG_DEST": str(diario),
    }
    env.pop("SERVICE_RESULT", None)
    if service_result is not None:
        env["SERVICE_RESULT"] = service_result
    return env


@pytest.fixture()
def lock_ocupado(tmp_path: Path):  # type: ignore[no-untyped-def]
    """Segura o `.lock` do acervo por um processo de fora, como na vida real.

    É o cenário do SNAPSHOT-LOCK-01: outra instância (timer, borda udev) já
    está fotografando quando o gancho de parada dispara.
    """
    acervo = tmp_path / "bt-bonds"
    acervo.mkdir(parents=True)
    lock = acervo / ".lock"
    lock.touch()
    dono = subprocess.Popen(
        ["flock", str(lock), "sleep", "60"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    # O `flock(1)` abre e tranca antes de executar o `sleep`; esperar o filho
    # aparecer evita a corrida em que o teste corre com o lock ainda livre.
    prazo = time.monotonic() + 5.0
    while time.monotonic() < prazo:
        livre = subprocess.run(
            ["flock", "-n", str(lock), "true"], capture_output=True
        )
        if livre.returncode != 0:
            break
        time.sleep(0.05)
    else:  # pragma: no cover — só numa máquina onde o flock(1) não tranca
        dono.kill()
        pytest.skip("não consegui segurar o .lock com flock(1)")
    yield acervo
    dono.kill()
    dono.wait(timeout=5)


pytestmark = pytest.mark.skipif(
    shutil.which("flock") is None, reason="flock(1) ausente (util-linux)"
)


class TestOGanchoDeParadaNaoEspera:
    def test_no_gancho_de_parada_desiste_na_hora(
        self, tmp_path: Path, lock_ocupado: Path
    ) -> None:
        """E4 — com `$SERVICE_RESULT` na mão, o snapshot não disputa o lock.

        ARRANQUE A CURA: troque o `ESPERA_LOCK=(-n)` do
        `scripts/bt_bonds_snapshot.sh` por `(-w 30)`. O script passa a esperar
        os 30 s do lock e este teste estoura o teto de 6 s — que é, em
        miniatura, o Bluetooth dela fora do ar.
        """
        fonte = _fonte_com_um_bond(tmp_path / "bluetooth")
        diario = tmp_path / "diario.log"
        inicio = time.monotonic()
        try:
            proc = subprocess.run(
                ["bash", str(SNAPSHOT), "--quiet"],
                capture_output=True,
                text=True,
                timeout=TETO_S,
                env=_ambiente(fonte, lock_ocupado, diario, "core-dump"),
            )
        except subprocess.TimeoutExpired:
            pytest.fail(
                f"o gancho de parada ficou >{TETO_S:.0f}s disputando o `.lock`. "
                "Enquanto ele espera, o systemd NÃO reinicia o bluetoothd — foram "
                "42,8 s dos 57,25 s medidos em 06/08. No gancho o `flock` tem de "
                "ser `-n`."
            )
        decorrido = time.monotonic() - inicio
        assert proc.returncode == 0, proc.stderr
        assert decorrido < TETO_S, f"desistir levou {decorrido:.1f}s"
        assert "desisto na hora" in diario.read_text(encoding="utf-8"), (
            "o script saiu rápido, mas não pela porta do gancho de parada — "
            "confira se ele chegou mesmo ao `flock`"
        )
        # E o mais importante: ele NÃO estragou o acervo de quem tem o lock.
        assert not list(lock_ocupado.glob("2*")), (
            "desistir do lock não pode deixar diretório de snapshot pela metade"
        )

    def test_fora_do_gancho_espera_a_vez(self, tmp_path: Path, lock_ocupado: Path) -> None:
        """E4-bis — sem `$SERVICE_RESULT`, o `-w 30` do SNAPSHOT-LOCK-01 fica.

        ARRANQUE A CURA AO CONTRÁRIO: ponha `-n` também no ramo de fora do
        gancho. O timer e a borda udev voltam a poder colidir no mesmo
        diretório-timestamp (medido 22/07 22:43:13) e este teste reprova.
        """
        fonte = _fonte_com_um_bond(tmp_path / "bluetooth")
        diario = tmp_path / "diario.log"
        with pytest.raises(subprocess.TimeoutExpired):
            subprocess.run(
                ["bash", str(SNAPSHOT), "--quiet"],
                capture_output=True,
                text=True,
                timeout=PACIENCIA_S,
                env=_ambiente(fonte, lock_ocupado, diario, None),
            )

    def test_com_o_lock_livre_o_gancho_fotografa(self, tmp_path: Path) -> None:
        """Linha de base: o `-n` não pode ter virado "no gancho, nunca fotografa".

        Sem este teste, um script que desiste SEMPRE passaria nos dois acima —
        e o salva-vidas voltaria a falhar exatamente no naufrágio, que é o
        BT-SNAPSHOT-SANDBOX-01 de novo, por outra porta.
        """
        fonte = _fonte_com_um_bond(tmp_path / "bluetooth")
        acervo = tmp_path / "bt-bonds"
        diario = tmp_path / "diario.log"
        proc = subprocess.run(
            ["bash", str(SNAPSHOT), "--quiet"],
            capture_output=True,
            text=True,
            timeout=TETO_S,
            env=_ambiente(fonte, acervo, diario, "core-dump"),
        )
        assert proc.returncode == 0, proc.stderr
        gravados = [d for d in acervo.glob("2*") if d.is_dir()]
        assert gravados, "com o lock livre o gancho tem de fotografar"
        assert (gravados[0] / ADAPTER / CONTROLE / "info").is_file()


class TestTetoDeParada:
    def test_dropin_poe_teto_no_tempo_de_parada(self) -> None:
        """E5 — sem `TimeoutStopSec` vale o padrão de 90 s.

        ARRANQUE A CURA: apague a linha `TimeoutStopSec=` do drop-in. Nada no
        arquivo passa a limitar quanto tempo os nossos `ExecStopPost` podem
        segurar o `bluetooth.service`, e este teste reprova.

        O teto existe porque o `flock -n` do E4 não cobre tudo: a aritmética de
        06/08 explica no máximo 30 dos 34,4 s parados antes de o diretório ser
        nomeado (e o diretório FOI criado, logo o lock saiu dentro do teto). A
        outra hipótese — inanição de I/O enquanto o apport lia o core — não foi
        separada, e só um teto vale para as duas.
        """
        texto = DROPIN.read_text(encoding="utf-8")
        achado = re.search(r"^TimeoutStopSec=(\S+)$", texto, re.M)
        assert achado, (
            "o drop-in não declara `TimeoutStopSec`. Sem ele vale o "
            "`DefaultTimeoutStopSec` de 90 s — foi por essa porta que os 42,8 s "
            "de ExecStopPost de 06/08 passaram sem que nada os limitasse."
        )
        assert _segundos(achado.group(1)) <= 30, (
            f"`TimeoutStopSec={achado.group(1)}` não é teto: o pior caso já "
            "medido foi de 42,8 s dentro do gancho."
        )
        assert _segundos(achado.group(1)) >= 5, (
            f"`TimeoutStopSec={achado.group(1)}` é apertado demais. A restauração "
            "de bonds também roda no gancho, e um SIGKILL no meio dela deixa o "
            "storage do BlueZ pela metade — o dano que o salva-vidas existe para "
            "evitar."
        )

    def test_o_teto_nao_e_mais_frouxo_que_o_do_agente(self) -> None:
        """O gancho do BlueZ não pode esperar mais que o agente que ele arrasta.

        O `hefesto-bt-agent.service` para em 1 s (AGENTE-QUE-SOME-01). De nada
        adianta ter curado os 90 s DELE se o nosso próprio gancho pode segurar
        o `bluetooth.service` por mais tempo que isso outra vez.
        """
        agente = (REPO_ROOT / "assets" / "systemd" / "hefesto-bt-agent.service").read_text(
            encoding="utf-8"
        )
        do_agente = re.search(r"^TimeoutStopSec=(\S+)$", agente, re.M)
        assert do_agente, "o `hefesto-bt-agent.service` perdeu o `TimeoutStopSec`"
        do_dropin = re.search(
            r"^TimeoutStopSec=(\S+)$", DROPIN.read_text(encoding="utf-8"), re.M
        )
        assert do_dropin
        assert _segundos(do_dropin.group(1)) < 90, (
            "o drop-in voltou ao padrão de 90 s do systemd, que é exatamente o "
            "número que esta sprint existe para tirar do caminho"
        )


def _segundos(valor: str) -> float:
    """`15s`, `1min 30s`, `250ms`, `15` -> segundos."""
    unidades = {"us": 1e-6, "ms": 1e-3, "s": 1.0, "sec": 1.0, "min": 60.0, "m": 60.0, "h": 3600.0}
    total = 0.0
    for numero, unidade in re.findall(r"(\d+(?:\.\d+)?)\s*([a-z]*)", valor):
        total += float(numero) * unidades.get(unidade, 1.0)
    return total

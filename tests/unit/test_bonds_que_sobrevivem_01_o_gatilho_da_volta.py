"""BONDS-QUE-SOBREVIVEM-01 — o gatilho da volta, e o que ele tem de recusar.

Decisão dela, 08/08/2026: *"restauro de bonds tem de ser automático — manual
com `sudo` não é produto"*. O salva-vidas GRAVA sozinho desde 21/07; a volta
era um comando que ela tinha de digitar, e por isso nunca aconteceu.

O QUE APAGA OS BONDS — medido no journal dela em **15/08/2026, 06:29**, com
bluez **5.86** (o backport já aplicado: ele não curou isto):

    06:29:01  snapshot de bonds gravado ... (4 bond(s))
    06:29:41  snapshot de bonds gravado ... (1 bond(s))   <- 3 bonds em 40 s
    06:29:46  bluetoothd: malloc_consolidate(): unaligned fastbin chunk detected
    06:29:49  bluetooth.service: Main process exited, code=dumped, status=6/ABRT
    06:29:50  bluetooth.service: Scheduled restart job, restart counter is at 1
    06:29:56  snapshot de bonds gravado ... (2 bond(s))

A corrupção de heap apaga os diretórios de device de `/var/lib/bluetooth`
**segundos antes** de abortar. O salva-vidas tinha a cópia boa das 06:29:01 e
ninguém a usou: ela ficou com dois dos quatro controles.

O GATILHO é o `ExecStopPost` do `bluetooth.service`, e só na MORTE do daemon.
Ali o `bluetoothd` já saiu (o storage está parado sem que ninguém precise
pará-lo — parar o BlueZ à mão foi o que derrubou o agente de pareamento por
oito horas em 14/08), o systemd reinicia 1 s depois, e a unit roda como root:
nenhum `sudo`, nenhum polkit.

AS MORDIDAS (cada uma tem o "arranque" escrito no docstring do teste):

  1. a varredura por device, do snapshot mais NOVO para o mais velho — sem
     ela, "o último snapshot" é o DEGRADADO, e a volta devolve nada;
  2. o gate `SERVICE_RESULT != success` — sem ele, uma remoção que ela decidiu
     é desfeita pelo produto no desligamento seguinte;
  3. a regra ADITIVA (nunca escrever onde há `[LinkKey]` viva) — é ela que
     transforma o risco da "chave rotacionada" em não-risco, e era esse risco
     que mantinha a restauração manual desde 21/07;
  4. a quarentena por boot (E4 da sprint de 04/08) — sem ela, um bond que não
     para de pé realimenta o laço de autenticação que o crash adora;
  5. a poda por VALOR do acervo (E2) — sem ela, uma fila de snapshots pobres
     expulsa o rico e o gatilho acorda para um acervo cheio e inútil;
  6. o destino do log (DIÁRIO-QUE-NAO-MENTE-01, 15/08) — sem ele, ESTE arquivo
     de teste escreve no journal da máquina dela a linha "bluetooth.service
     morreu", e a próxima pessoa a ler o journal caça um defeito que não houve.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

#: Os scripts da família `bt_*` que registram no journal. Todos passaram a
#: escrever por `_registrar`, e é isso que o portão desta lista guarda.
SCRIPTS_QUE_REGISTRAM = (
    "bt_active_mode.sh",
    "bt_bonds_autorestore.sh",
    "bt_bonds_snapshot.sh",
    "bt_health_watchdog.sh",
    "bt_nosniff_now.sh",
    "bt_rebind_orphans.sh",
)

REPO_ROOT = Path(__file__).resolve().parents[2]
AUTORESTORE = REPO_ROOT / "scripts" / "bt_bonds_autorestore.sh"
SNAPSHOT = REPO_ROOT / "scripts" / "bt_bonds_snapshot.sh"
DROPIN = REPO_ROOT / "assets" / "systemd" / "bluetooth-dropin-10-hefesto-resilience.conf"
INSTALL = REPO_ROOT / "install.sh"
UNINSTALL = REPO_ROOT / "uninstall.sh"

# Faixa sintética canônica das fixtures (test_anonimato_de_fixtures.py).
ADAPTER = "AA:BB:CC:00:00:01"
VERMELHO = "AA:BB:CC:00:00:02"
AZUL = "AA:BB:CC:00:00:03"
PRETO = "AA:BB:CC:00:00:04"
BRANCO = "AA:BB:CC:00:00:05"

#: Um boot fixo, para a quarentena ser determinística. Em produção é o
#: `/proc/sys/kernel/random/boot_id`; para o script é só uma etiqueta opaca, e
#: aqui ela é prosa de propósito — um UUID de mentira casa o detector de MAC do
#: test_anonimato_de_fixtures.py no último grupo de hexa.
BOOT = "boot-do-ensaio-01"
#: 15/08/2026 06:30:00 -03 em epoch, o minuto do crash medido.
AGORA = "1786822200"


def _info(chave: str = "AAAA", com_chave: bool = True) -> str:
    """`info` de device. Sem `[LinkKey]` ele não é bond — é device visto num scan."""
    texto = "[General]\nName=DualSense Wireless Controller\n"
    if com_chave:
        texto += f"\n[LinkKey]\nKey={chave}\nType=4\nPINLength=0\n"
    return texto


def _poe_device(raiz: Path, mac: str, chave: str = "AAAA", com_chave: bool = True) -> Path:
    dev = raiz / ADAPTER / mac
    dev.mkdir(parents=True, exist_ok=True)
    (dev / "info").write_text(_info(chave, com_chave), encoding="utf-8")
    return dev


def _snapshot(acervo: Path, ts: str, macs: dict[str, str]) -> Path:
    """Um snapshot do acervo: `{MAC: chave}`."""
    snap = acervo / ts
    for mac, chave in macs.items():
        _poe_device(snap, mac, chave)
    (snap / ADAPTER / "settings").write_text(
        "[General]\nDiscoverable=false\n", encoding="utf-8"
    )
    return snap


def _rodar(
    acervo: Path,
    destino: Path,
    *args: str,
    service_result: str | None = "core-dump",
    boot: str = BOOT,
    agora: str = AGORA,
    extra: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    # A raiz do storage do BlueZ existe sempre (é o `StateDirectory=bluetooth`
    # da unit do bluez) — inclusive depois do crash, que come os diretórios de
    # device e não a raiz.
    destino.mkdir(parents=True, exist_ok=True)
    env = {
        **os.environ,
        "HEFESTO_BT_BONDS_SRC": str(acervo),
        "HEFESTO_BT_DST": str(destino),
        "HEFESTO_BT_BOOT_ID": boot,
        "HEFESTO_BT_AGORA": agora,
        **(extra or {}),
    }
    env.pop("SERVICE_RESULT", None)
    if service_result is not None:
        env["SERVICE_RESULT"] = service_result
    return subprocess.run(
        ["bash", str(AUTORESTORE), *args],
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )


def _bonds(destino: Path) -> set[str]:
    """Os MACs que têm bond de verdade (`info` com `[LinkKey]`) no destino."""
    return {
        p.parent.name
        for p in destino.glob(f"{ADAPTER}/*/info")
        if "[LinkKey]" in p.read_text(encoding="utf-8")
    }


# ---------------------------------------------------------------------------
# Linha de base — sem ela, um script que recusa TUDO passaria em todo o resto.
# ---------------------------------------------------------------------------
class TestAVoltaAcontece:
    def test_bond_comido_pelo_crash_volta_sozinho(self, tmp_path: Path) -> None:
        """O caso de 15/08, em miniatura: o disco perdeu um, o acervo tem os dois."""
        acervo, destino = tmp_path / "acervo", tmp_path / "bluetooth"
        _snapshot(acervo, "20260815-062901", {VERMELHO: "V1", AZUL: "A1"})
        _poe_device(destino, VERMELHO, "V1")

        proc = _rodar(acervo, destino)

        assert proc.returncode == 0, proc.stderr
        assert _bonds(destino) == {VERMELHO, AZUL}, (
            "o bond que o crash comeu não voltou — o gatilho não fez nada"
        )
        assert "restaurado" in proc.stdout

    def test_nada_faltando_e_no_op(self, tmp_path: Path) -> None:
        acervo, destino = tmp_path / "acervo", tmp_path / "bluetooth"
        _snapshot(acervo, "20260815-062901", {VERMELHO: "V1"})
        _poe_device(destino, VERMELHO, "V1")

        proc = _rodar(acervo, destino)

        assert proc.returncode == 0
        assert "nenhum bond faltando" in proc.stdout


# ---------------------------------------------------------------------------
# MORDIDA 1 (a principal) — o snapshot mais recente é o PIOR deles.
# ---------------------------------------------------------------------------
class TestEscolhaDoSnapshot:
    def test_restaura_do_snapshot_bom_e_nao_do_degradado(self, tmp_path: Path) -> None:
        """A reprodução literal do relógio de 15/08 06:29.

        ARRANQUE: troque a varredura `sort -r` por device pelo "snapshot mais
        recente" (o `--latest` do `bt_bonds_restore.sh`) e este teste fica
        vermelho — porque às 06:29:41 o snapshot mais recente era o de UM bond,
        gravado 5 s depois do crash ter comido três.

        É a mordida principal porque o defeito não é copiar errado: é PERGUNTAR
        errado. A pergunta certa não é "qual foi o último retrato?", é "quando
        foi a última vez que eu vi ESTE bond vivo?".
        """
        acervo, destino = tmp_path / "acervo", tmp_path / "bluetooth"
        # 06:29:01 — os quatro controles da mesa dela.
        _snapshot(
            acervo,
            "20260815-062901",
            {VERMELHO: "V1", AZUL: "A1", PRETO: "P1", BRANCO: "B1"},
        )
        # 06:29:41 — o retrato do estrago, e é ele o MAIS RECENTE.
        _snapshot(acervo, "20260815-062941", {VERMELHO: "V1"})
        # O disco depois do restart: dois de quatro.
        _poe_device(destino, VERMELHO, "V1")
        _poe_device(destino, AZUL, "A1")

        proc = _rodar(acervo, destino)

        assert proc.returncode == 0, proc.stderr
        assert _bonds(destino) == {VERMELHO, AZUL, PRETO, BRANCO}, (
            "o gatilho leu só o snapshot mais recente (o degradado) e devolveu "
            "menos do que o acervo tinha"
        )

    def test_para_cada_device_vence_a_copia_mais_nova(self, tmp_path: Path) -> None:
        """Mais novo por DEVICE, não por snapshot — a chave mais recente é a que serve."""
        acervo, destino = tmp_path / "acervo", tmp_path / "bluetooth"
        _snapshot(acervo, "20260815-062901", {AZUL: "CHAVE-VELHA"})
        _snapshot(acervo, "20260815-062941", {AZUL: "CHAVE-NOVA"})

        proc = _rodar(acervo, destino)

        assert proc.returncode == 0
        texto = (destino / ADAPTER / AZUL / "info").read_text(encoding="utf-8")
        assert "CHAVE-NOVA" in texto, "restaurou uma cópia mais velha do que existia"

    def test_snapshot_velho_demais_nao_ressuscita_nada(self, tmp_path: Path) -> None:
        """Bond que ela removeu envelhece para fora da janela; crash volta em segundos."""
        acervo, destino = tmp_path / "acervo", tmp_path / "bluetooth"
        _snapshot(acervo, "20260701-120000", {AZUL: "A1"})

        proc = _rodar(acervo, destino)

        assert proc.returncode == 0
        assert _bonds(destino) == set(), "snapshot de 45 dias atrás ressuscitou um bond"


# ---------------------------------------------------------------------------
# MORDIDA 2 — o gate da MORTE. É a E1 da sprint: distinguir "perdemos" de
# "ela despareou de propósito".
# ---------------------------------------------------------------------------
class TestSoNaMorteDoDaemon:
    def test_parada_limpa_nao_restaura_nada(self, tmp_path: Path) -> None:
        """ARRANQUE: tire o `case "${SERVICE_RESULT:-}"` e este teste reprova.

        Sem o gate, a sequência "ela roda `bluetoothctl remove`, depois desliga
        o computador" faz o produto RESSUSCITAR o pareamento que ela mandou
        embora — reescrevendo a escolha dela em silêncio, que é exatamente o
        que a E1 da BONDS-QUE-SOBREVIVEM-01 proíbe.
        """
        acervo, destino = tmp_path / "acervo", tmp_path / "bluetooth"
        _snapshot(acervo, "20260815-062901", {VERMELHO: "V1", AZUL: "A1"})
        _poe_device(destino, VERMELHO, "V1")

        proc = _rodar(acervo, destino, service_result="success")

        assert proc.returncode == 0
        assert _bonds(destino) == {VERMELHO}, (
            "restaurou numa parada LIMPA — uma remoção decidida por ela seria desfeita"
        )
        assert "parada limpa" in proc.stdout

    def test_sem_service_result_nao_restaura_nada(self, tmp_path: Path) -> None:
        """Execução fora da unit (linha de comando, cron, engano) também não age."""
        acervo, destino = tmp_path / "acervo", tmp_path / "bluetooth"
        _snapshot(acervo, "20260815-062901", {AZUL: "A1"})

        proc = _rodar(acervo, destino, service_result=None)

        assert proc.returncode == 0
        assert _bonds(destino) == set()
        assert "fora da unit" in proc.stdout

    @pytest.mark.parametrize(
        "resultado", ["core-dump", "signal", "watchdog", "timeout", "oom-kill"]
    )
    def test_toda_forma_de_morte_dispara(self, tmp_path: Path, resultado: str) -> None:
        """As mortes medidas nesta casa: core-dump (15/08) e watchdog (08/08)."""
        acervo, destino = tmp_path / "acervo", tmp_path / "bluetooth"
        _snapshot(acervo, "20260815-062901", {AZUL: "A1"})

        proc = _rodar(acervo, destino, service_result=resultado)

        assert _bonds(destino) == {AZUL}, f"morte por {resultado} não disparou a volta"
        assert proc.returncode == 0

    def test_force_serve_ao_humano_sem_afrouxar_o_gate(self, tmp_path: Path) -> None:
        acervo, destino = tmp_path / "acervo", tmp_path / "bluetooth"
        _snapshot(acervo, "20260815-062901", {AZUL: "A1"})

        proc = _rodar(acervo, destino, "--force", service_result=None)

        assert proc.returncode == 0
        assert _bonds(destino) == {AZUL}


# ---------------------------------------------------------------------------
# MORDIDA 3 — ADITIVO. É o que derruba o motivo de a volta ser manual.
# ---------------------------------------------------------------------------
class TestNuncaPorCimaDeChaveViva:
    def test_nunca_sobrescreve_linkkey_viva(self, tmp_path: Path) -> None:
        """ARRANQUE: tire o `if [[ -f DST_INFO ]] && _tem_chave` e reprova.

        É esta linha, e só ela, que responde ao motivo escrito em três lugares
        para a restauração ser manual desde 21/07: *"se o controle já rotacionou
        a própria chave, reimpor a chave antiga gera um laço de falha de
        autenticação — a mesma classe de gatilho do crash"*. A chave viva em
        disco é sempre a mais nova. Não escrevendo onde há chave, o risco
        deixa de existir — não é mitigado, é ausente.
        """
        acervo, destino = tmp_path / "acervo", tmp_path / "bluetooth"
        _snapshot(acervo, "20260815-062901", {AZUL: "CHAVE-VELHA"})
        _poe_device(destino, AZUL, "CHAVE-QUE-O-CONTROLE-ROTACIONOU")

        proc = _rodar(acervo, destino)

        assert proc.returncode == 0
        texto = (destino / ADAPTER / AZUL / "info").read_text(encoding="utf-8")
        assert "CHAVE-QUE-O-CONTROLE-ROTACIONOU" in texto, (
            "a chave viva foi sobrescrita pela do snapshot — é o laço de "
            "autenticação que a volta manual existia para evitar"
        )
        assert "CHAVE-VELHA" not in texto

    def test_info_sem_chave_nenhuma_pode_ser_completado(self, tmp_path: Path) -> None:
        """`info` sem `[LinkKey]` não tem credencial a perder — ali dá para escrever."""
        acervo, destino = tmp_path / "acervo", tmp_path / "bluetooth"
        _snapshot(acervo, "20260815-062901", {AZUL: "A1"})
        _poe_device(destino, AZUL, com_chave=False)

        proc = _rodar(acervo, destino)

        assert proc.returncode == 0
        assert _bonds(destino) == {AZUL}

    def test_device_sem_chave_no_snapshot_nao_ressuscita(self, tmp_path: Path) -> None:
        """Device só VISTO num scan também tem `info`. Ressuscitá-lo não devolve nada."""
        acervo, destino = tmp_path / "acervo", tmp_path / "bluetooth"
        snap = acervo / "20260815-062901"
        _poe_device(snap, BRANCO, com_chave=False)

        proc = _rodar(acervo, destino)

        assert proc.returncode == 0
        assert not (destino / ADAPTER / BRANCO).exists()


# ---------------------------------------------------------------------------
# MORDIDA 4 — quarentena por boot (E4, 04/08).
# ---------------------------------------------------------------------------
class TestQuarentena:
    def test_o_mesmo_device_nao_volta_duas_vezes_no_mesmo_boot(
        self, tmp_path: Path
    ) -> None:
        """ARRANQUE: tire o `_restauros_neste_boot` e reprova.

        Regra escrita na E4: *"restaurar o mesmo MAC duas vezes no mesmo boot é
        o começo do laço que realimenta o crash — e é PROIBIDO"*. Um bond que
        sumiu DE NOVO logo depois de ter voltado não é vítima do crash: é chave
        velha sendo rejeitada pelo controle. Insistir alimenta o laço.
        """
        acervo, destino = tmp_path / "acervo", tmp_path / "bluetooth"
        _snapshot(acervo, "20260815-062901", {AZUL: "A1"})

        primeira = _rodar(acervo, destino)
        assert _bonds(destino) == {AZUL}, primeira.stdout

        # o controle rejeitou a chave e o bond evaporou outra vez
        for arquivo in (destino / ADAPTER / AZUL).iterdir():
            arquivo.unlink()
        (destino / ADAPTER / AZUL).rmdir()

        segunda = _rodar(acervo, destino)

        assert _bonds(destino) == set(), (
            "restaurou o mesmo device duas vezes no mesmo boot — é o laço de "
            "autenticação que a E4 proíbe"
        )
        assert "QUARENTENA" in segunda.stdout
        assert "bluetoothctl remove" in segunda.stdout, (
            "a quarentena tem de dizer o gesto que resolve, não só recusar"
        )

    def test_boot_novo_libera(self, tmp_path: Path) -> None:
        """A quarentena é do BOOT. Reiniciar a máquina é gesto dela, e recomeça."""
        acervo, destino = tmp_path / "acervo", tmp_path / "bluetooth"
        _snapshot(acervo, "20260815-062901", {AZUL: "A1"})

        _rodar(acervo, destino, boot="boot-antigo")
        for arquivo in (destino / ADAPTER / AZUL).iterdir():
            arquivo.unlink()
        (destino / ADAPTER / AZUL).rmdir()

        _rodar(acervo, destino, boot="boot-novo")

        assert _bonds(destino) == {AZUL}


# ---------------------------------------------------------------------------
# A régua da RADIO-ABERTO-01/E10, agora num caminho que roda SOZINHO.
# ---------------------------------------------------------------------------
class TestSnapshotHostilNaoEhCopiado:
    def test_info_symlink_nao_e_restaurado(self, tmp_path: Path) -> None:
        """`cp -a` preservaria o link, e o bluetoothd escreve como ROOT por dentro dele."""
        acervo, destino = tmp_path / "acervo", tmp_path / "bluetooth"
        snap = _snapshot(acervo, "20260815-062901", {AZUL: "A1"})
        alvo = tmp_path / "alvo_fora_da_arvore"
        alvo.write_text("original\n", encoding="utf-8")
        info = snap / ADAPTER / AZUL / "info"
        info.unlink()
        info.symlink_to(alvo)

        proc = _rodar(acervo, destino)

        assert proc.returncode == 0
        assert not (destino / ADAPTER / AZUL / "info").exists(), (
            "um `info` que é SYMLINK foi restaurado"
        )
        assert alvo.read_text(encoding="utf-8") == "original\n"

    def test_info_com_hardlink_nao_e_restaurado(self, tmp_path: Path) -> None:
        """Hardlink escreve no mesmo inode — bond legítimo nunca tem nlink > 1."""
        acervo, destino = tmp_path / "acervo", tmp_path / "bluetooth"
        snap = _snapshot(acervo, "20260815-062901", {AZUL: "A1"})
        alvo = tmp_path / "alvo_hardlink"
        alvo.write_text(_info("A1"), encoding="utf-8")
        info = snap / ADAPTER / AZUL / "info"
        info.unlink()
        os.link(alvo, info)

        proc = _rodar(acervo, destino)

        assert proc.returncode == 0
        assert not (destino / ADAPTER / AZUL / "info").exists()

    def test_diretorio_com_nome_que_nao_e_mac_e_ignorado(self, tmp_path: Path) -> None:
        acervo, destino = tmp_path / "acervo", tmp_path / "bluetooth"
        snap = acervo / "20260815-062901"
        travesso = snap / ADAPTER / ".." / ".." / "escapou"
        (snap / ADAPTER).mkdir(parents=True)
        travesso.mkdir(parents=True, exist_ok=True)
        (snap / ADAPTER / "nao-e-mac").mkdir()
        (snap / ADAPTER / "nao-e-mac" / "info").write_text(_info(), encoding="utf-8")

        proc = _rodar(acervo, destino)

        assert proc.returncode == 0
        assert not (destino / ADAPTER / "nao-e-mac").exists()

    def test_dry_run_nao_escreve(self, tmp_path: Path) -> None:
        acervo, destino = tmp_path / "acervo", tmp_path / "bluetooth"
        _snapshot(acervo, "20260815-062901", {AZUL: "A1"})
        destino.mkdir()

        proc = _rodar(acervo, destino, "--dry-run")

        assert proc.returncode == 0
        assert "DRY-RUN" in proc.stdout
        assert _bonds(destino) == set()


# ---------------------------------------------------------------------------
# MORDIDA 5 — a poda por VALOR (E2). O gatilho depende do acervo servir.
# ---------------------------------------------------------------------------
class TestPodaPorValor:
    def test_o_melhor_snapshot_nunca_sai_na_poda(self, tmp_path: Path) -> None:
        """ARRANQUE: volte a poda para `sort | head -n -12` puro e reprova.

        MEDIDO em 04/08 às 03:04: o snapshot das 23:51:44 com os QUATRO
        controles já tinha sido podado por doze snapshots de UM bond, gravados
        em série por um `bluetoothd` que caía. O acervo estava cheio e não
        servia para nada — e um gatilho automático que acorda para esse acervo
        restaura o próprio estrago.
        """
        acervo = tmp_path / "acervo"
        fonte = tmp_path / "bluetooth"
        acervo.mkdir()

        rico = _snapshot(
            acervo, "20260810-000001-1", {VERMELHO: "V", AZUL: "A", PRETO: "P", BRANCO: "B"}
        )
        pobres = [
            _snapshot(acervo, f"20260810-0000{n:02d}-1", {VERMELHO: "V"})
            for n in range(2, 14)
        ]
        assert len(list(acervo.iterdir())) == 13

        # o estado de agora é magro, e diferente de tudo que está no acervo
        _poe_device(fonte, VERMELHO, "V-DE-AGORA")

        proc = subprocess.run(
            ["bash", str(SNAPSHOT)],
            capture_output=True,
            text=True,
            timeout=60,
            env={
                **os.environ,
                "HEFESTO_BT_SRC": str(fonte),
                "HEFESTO_BT_SNAP_ROOT": str(acervo),
            },
        )

        assert proc.returncode == 0, proc.stderr
        assert rico.exists(), (
            "a poda jogou fora o melhor snapshot do acervo — doze retratos "
            "pobres expulsaram o rico, que é o defeito medido em 04/08"
        )
        assert not pobres[0].exists(), (
            "a poda não podou nada: o teste não estaria provando a proteção"
        )
        assert "preservado" in proc.stdout


# ---------------------------------------------------------------------------
# A FIAÇÃO — de nada adianta o mecanismo se ele não está ligado em lugar nenhum.
# ---------------------------------------------------------------------------
class TestFiacao:
    def test_o_dropin_arma_o_gatilho_depois_do_snapshot(self) -> None:
        """ARRANQUE: tire o `ExecStopPost` do autorestore do drop-in e reprova.

        A ordem importa e é assertada: o snapshot fotografa o estrago primeiro
        (valor forense; o acervo nunca aceita foto vazia), a restauração corre
        depois, sobre o disco já fotografado.
        """
        texto = DROPIN.read_text(encoding="utf-8")
        linhas = [ln for ln in texto.splitlines() if ln.startswith("ExecStopPost=")]
        alvos = [ln for ln in linhas if "bt_bonds_" in ln]
        assert len(alvos) == 2, f"esperava snapshot + autorestore, achei {alvos}"
        assert "bt_bonds_snapshot.sh" in alvos[0]
        assert "bt_bonds_autorestore.sh" in alvos[1], (
            "o autorestore tem de vir DEPOIS do snapshot"
        )
        for linha in alvos:
            assert linha.startswith("ExecStopPost=-"), (
                "sem o '-', uma falha nossa contamina o resultado do stop do bluez"
            )

    def test_o_gatilho_nao_usa_sudo_nem_para_o_servico(self) -> None:
        """A volta não pode repetir o AGENTE-QUE-NAO-VOLTA-01.

        Parar o `bluetooth.service` derruba o `hefesto-bt-agent.service` junto
        (`Requires=`), e em 14/08 isso custou oito horas de Bluetooth. No
        `ExecStopPost` o daemon já morreu — não há nada a parar.
        """
        codigo = "\n".join(
            linha
            for linha in AUTORESTORE.read_text(encoding="utf-8").splitlines()
            if not linha.lstrip().startswith("#")
        )
        assert "sudo" not in codigo, "restauro automático não pede sudo (roda como root)"
        assert "systemctl stop" not in codigo
        assert "systemctl mask" not in codigo

    def test_o_dry_run_nao_esbarra_no_daemon_vivo(self) -> None:
        """Portão de TEXTO, e assumido como tal: o gate do daemon vivo protege a
        ESCRITA, e o `--dry-run` não escreve. Com a máquina viva é justamente
        quando a pergunta "o que voltaria agora?" serve — e ela tem de poder
        ser feita sem parar nada. O caminho real exige root e não cabe na suíte.
        """
        codigo = AUTORESTORE.read_text(encoding="utf-8")
        assert 'if [[ "${DRY}" -eq 0 ]] \\\n       && command -v systemctl' in codigo, (
            "o gate do bluetooth vivo tem de deixar o --dry-run passar"
        )

    def test_install_instala_e_uninstall_remove(self) -> None:
        assert "bt_bonds_autorestore.sh" in INSTALL.read_text(encoding="utf-8")
        assert "bt_bonds_autorestore.sh" in UNINSTALL.read_text(encoding="utf-8")

    def test_o_install_nao_promete_mais_restauro_manual(self) -> None:
        """A decisão dela de 08/08 contra a linha de `install.sh` que a contradizia.

        `install.sh:1707` dizia *"restauração é MANUAL"*. As duas posições
        ficaram escritas lado a lado desde 08/08 (o mapa de 13/08 registra a
        contradição). Fato errado se SUBSTITUI — e este portão impede que ele
        volte por descuido.
        """
        texto = INSTALL.read_text(encoding="utf-8")
        assert "restauração é MANUAL" not in texto, (
            "o install.sh voltou a prometer restauro manual — contradiz a "
            "decisão dela de 08/08 e o código que está no drop-in"
        )
        assert "automático" in texto

    def test_o_script_e_executavel_e_tem_sintaxe_valida(self) -> None:
        assert AUTORESTORE.stat().st_mode & 0o111, "bt_bonds_autorestore.sh não é executável"
        proc = subprocess.run(
            ["bash", "-n", str(AUTORESTORE)], capture_output=True, text=True
        )
        assert proc.returncode == 0, proc.stderr

    def test_o_diario_nao_mente_e_o_portao_e_da_familia_inteira(self) -> None:
        """DIÁRIO-QUE-NAO-MENTE-01: quem registra, registra por `_registrar`.

        ARRANQUE: troque o `_registrar` de qualquer um dos seis por um
        `logger -t ... "$*"` direto e este portão reprova.

        O critério não é "o script tem uma variável": é que exista UM único
        ponto de saída para o journal em cada script, e que ele seja
        endereçável. Dois pontos de saída significam que um deles vai escapar —
        foi assim no `bt_nosniff_now.sh`, que registrava em duas linhas soltas
        no meio do fluxo, longe de qualquer função de log.
        """
        for nome in SCRIPTS_QUE_REGISTRAM:
            texto = (REPO_ROOT / "scripts" / nome).read_text(encoding="utf-8")
            codigo = [
                ln for ln in texto.splitlines() if not ln.lstrip().startswith("#")
            ]
            chamadas = [ln for ln in codigo if "logger -t" in ln]
            assert len(chamadas) == 1, (
                f"{nome} tem {len(chamadas)} caminhos até o journal; tem de ter "
                f"UM, dentro de `_registrar`: {chamadas}"
            )
            assert 'LOG_DEST="${HEFESTO_BT_LOG_DEST:-}"' in texto, (
                f"{nome} escreve no journal sem destino endereçável — a suíte "
                f"volta a sujar o journal da máquina dela"
            )
            assert "_registrar()" in texto, f"{nome} não define `_registrar`"

    def test_a_suite_inteira_nasce_com_o_log_desviado(self) -> None:
        """O fail-safe: nenhum teste FUTURO precisa lembrar de desviar o log.

        ARRANQUE: tire o `monkeypatch.setenv("HEFESTO_BT_LOG_DEST", ...)` do
        `_hefesto_fake_env` (tests/conftest.py) e este teste reprova.

        Curar só este arquivo deixaria o defeito à espreita: qualquer teste novo
        que rode um `bt_*.sh` voltaria a escrever no journal DELA, e o sintoma
        (uma linha convincente sobre uma morte que não houve) só aparece dias
        depois, para quem está caçando outra coisa. A fixture é autouse, então
        o desvio vale para o processo inteiro — inclusive para os subprocessos,
        que herdam o `os.environ`.
        """
        destino = os.environ.get("HEFESTO_BT_LOG_DEST")
        assert destino, (
            "a suíte não desviou o log dos scripts bt_*: eles vão escrever no "
            "journal do sistema durante o run"
        )
        assert destino != "", destino


# ---------------------------------------------------------------------------
# MORDIDA 6 — DIÁRIO-QUE-NAO-MENTE-01 (15/08/2026).
# ---------------------------------------------------------------------------
# O log de produção é útil e não pode sumir: é ele que conta a história quando
# o bond volta de verdade. O que não pode existir é a linha que descreve um
# evento que NÃO aconteceu. Estes testes fixam as duas metades ao mesmo tempo:
# o journal fica limpo sob teste, e continua escrito em produção.
class TestOLogNaoMenteNoJournalDela:
    @staticmethod
    def _logger_falso(tmp_path: Path) -> tuple[Path, dict[str, str]]:
        """Um `logger` de mentira na frente do PATH.

        É a única régua honesta aqui: perguntar ao journal do sistema tornaria
        o teste dependente da máquina, da retenção e da permissão de leitura —
        e um teste que consulta o journal para provar que não sujou o journal
        já falhou de propósito. O shim responde a pergunta exata: o script
        CHAMOU o `logger`, sim ou não?
        """
        binario = tmp_path / "bin-falso"
        binario.mkdir(exist_ok=True)
        registro = tmp_path / "logger-foi-chamado.txt"
        atalho = binario / "logger"
        atalho.write_text(
            "#!/usr/bin/env bash\n"
            f'printf "%s\\n" "$*" >> "{registro}"\n',
            encoding="utf-8",
        )
        atalho.chmod(0o755)
        return registro, {"PATH": f"{binario}:{os.environ['PATH']}"}

    def test_sob_teste_nenhuma_linha_chega_ao_journal(self, tmp_path: Path) -> None:
        """ARRANQUE: volte o `log()` a chamar `logger -t ... "$*"` direto e reprova.

        O defeito medido: em 15/08 esta suíte gravou 36 linhas dizendo
        "bluetooth.service morreu (SERVICE_RESULT=oom-kill)" no journal DELA —
        oito entre 18h29 e 21h38 — sobre um `bluetoothd` que nunca morreu
        (`systemctl`: Result=success, NRestarts=2, ativo desde as 14:14:32).
        Vinte minutos de investigação foram atrás desse defeito inexistente.
        """
        acervo, destino = tmp_path / "acervo", tmp_path / "bluetooth"
        _snapshot(acervo, "20260815-062901", {AZUL: "A1"})
        registro, caminho = self._logger_falso(tmp_path)
        diario = tmp_path / "diario.log"

        proc = _rodar(
            acervo,
            destino,
            service_result="oom-kill",
            extra={"HEFESTO_BT_LOG_DEST": str(diario), **caminho},
        )

        assert proc.returncode == 0, proc.stderr
        assert _bonds(destino) == {AZUL}, "o desvio do log mudou o que o script FAZ"
        assert not registro.exists(), (
            "o script chamou `logger` durante o teste: "
            f"{registro.read_text(encoding='utf-8') if registro.exists() else ''}"
        )

    def test_o_desvio_registra_a_mesma_linha_em_vez_de_engolir(
        self, tmp_path: Path
    ) -> None:
        """Desviar, não emudecer — senão a cura vira 'apagamos o log'.

        ARRANQUE: troque o ramo do caminho por `:` (silêncio) e reprova. É esta
        asserção que impede a cura preguiçosa: um `--quiet` global limparia o
        journal e destruiria, junto, a única prova de que a restauração
        aconteceu.
        """
        acervo, destino = tmp_path / "acervo", tmp_path / "bluetooth"
        _snapshot(acervo, "20260815-062901", {AZUL: "A1"})
        diario = tmp_path / "diario.log"

        _rodar(acervo, destino, extra={"HEFESTO_BT_LOG_DEST": str(diario)})

        texto = diario.read_text(encoding="utf-8")
        assert "hefesto-bt-autorestore" in texto, "o desvio perdeu a identidade do log"
        assert "restaurado do snapshot" in texto, (
            "a linha que conta a história do bond sumiu — o desvio virou mordaça"
        )

    def test_em_producao_a_linha_continua_indo_para_o_journal(
        self, tmp_path: Path
    ) -> None:
        """O contrapeso: sem `HEFESTO_BT_LOG_DEST`, o journal recebe tudo.

        Produção é exatamente isto: o `ExecStopPost` roda o script sem env
        nenhuma. Se um dia alguém "simplificar" removendo o `logger`, este
        teste é quem reclama.
        """
        acervo, destino = tmp_path / "acervo", tmp_path / "bluetooth"
        _snapshot(acervo, "20260815-062901", {AZUL: "A1"})
        registro, caminho = self._logger_falso(tmp_path)

        _rodar(
            acervo,
            destino,
            service_result="core-dump",
            extra={"HEFESTO_BT_LOG_DEST": "", **caminho},
        )

        assert registro.exists(), (
            "sem HEFESTO_BT_LOG_DEST o script tem de registrar no journal — "
            "é ele que conta a história quando o bond volta de verdade"
        )
        texto = registro.read_text(encoding="utf-8")
        assert "-t hefesto-bt-autorestore" in texto
        assert "bluetooth.service morreu" in texto

    def test_none_nao_registra_em_lugar_nenhum(self, tmp_path: Path) -> None:
        """O terceiro destino, para quem roda o script à mão sem querer rastro."""
        acervo, destino = tmp_path / "acervo", tmp_path / "bluetooth"
        _snapshot(acervo, "20260815-062901", {AZUL: "A1"})
        registro, caminho = self._logger_falso(tmp_path)

        proc = _rodar(
            acervo, destino, extra={"HEFESTO_BT_LOG_DEST": "none", **caminho}
        )

        assert proc.returncode == 0, proc.stderr
        assert not registro.exists()
        assert _bonds(destino) == {AZUL}
        assert "restaurado" in proc.stdout, "o stdout NUNCA depende do destino do log"

    def test_o_snapshot_irmao_tambem_desvia(self, tmp_path: Path) -> None:
        """O `bt_bonds_snapshot.sh` roda neste MESMO arquivo (TestPodaPorValor).

        Ele sozinho pôs 535 linhas no journal dela em 15/08. Curar só o
        autorestore deixaria metade do defeito de pé.
        """
        fonte, acervo = tmp_path / "bluetooth", tmp_path / "acervo"
        acervo.mkdir()
        _poe_device(fonte, AZUL, "A1")
        registro, caminho = self._logger_falso(tmp_path)
        diario = tmp_path / "diario.log"

        proc = subprocess.run(
            ["bash", str(SNAPSHOT)],
            capture_output=True,
            text=True,
            timeout=60,
            env={
                **os.environ,
                "HEFESTO_BT_SRC": str(fonte),
                "HEFESTO_BT_SNAP_ROOT": str(acervo),
                "HEFESTO_BT_LOG_DEST": str(diario),
                **caminho,
            },
        )

        assert proc.returncode == 0, proc.stderr
        assert not registro.exists(), "o bt_bonds_snapshot.sh ainda suja o journal"
        assert "hefesto-bt-bonds" in diario.read_text(encoding="utf-8")

    def test_a_familia_inteira_tem_sintaxe_valida(self) -> None:
        """Seis scripts ganharam o `_registrar` no mesmo dia; seis são checados."""
        for nome in SCRIPTS_QUE_REGISTRAM:
            proc = subprocess.run(
                ["bash", "-n", str(REPO_ROOT / "scripts" / nome)],
                capture_output=True,
                text=True,
            )
            assert proc.returncode == 0, f"{nome}: {proc.stderr}"

"""SDP-CACHE-01 — cache SDP do perfil HID é CRÍTICO, não descartável."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = REPO_ROOT / "scripts" / "bt_bonds_snapshot.sh"
RESTORE = REPO_ROOT / "scripts" / "bt_bonds_restore.sh"
WATCHDOG = REPO_ROOT / "scripts" / "bt_health_watchdog.sh"
DOCTOR = REPO_ROOT / "scripts" / "doctor.sh"

ADAPTER = "AA:BB:CC:00:00:01"
HID_UUID = "00001124-0000-1000-8000-00805f9b34fb"

INFO_HID = f"""[General]
Name=DualSense Wireless Controller
Class=0x002508
Trusted=true
Services={HID_UUID};00001200-0000-1000-8000-00805f9b34fb;

[LinkKey]
Type=4
PINLength=0
"""

CACHE_SAO = """[General]
Name=DualSense Wireless Controller

[ServiceRecords]
0x00010001=36024A0900000A000100010900013503191124090004350D3506190100090011
"""

CACHE_ENVENENADO = """[General]
Name=DualSense Wireless Controller
"""


def _arvore_bluez(raiz: Path, devices: dict[str, str | None]) -> Path:
    """Monta uma árvore /var/lib/bluetooth de mentira."""
    adp = raiz / ADAPTER
    (adp / "cache").mkdir(parents=True)
    (adp / "settings").write_text("[General]\nDiscoverable=false\n", encoding="utf-8")
    for mac, cache in devices.items():
        (adp / mac).mkdir()
        (adp / mac / "info").write_text(INFO_HID, encoding="utf-8")
        if cache is not None:
            (adp / "cache" / mac).write_text(cache, encoding="utf-8")
    return adp


def _roda(
    script: Path, src: Path, *args: str, **extra: str
) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "HEFESTO_BT_SRC": str(src), **extra}
    return subprocess.run(
        ["bash", str(script), *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )


class TestSnapshotPreservaOCacheSDP:
    """O snapshot precisa levar o registro SDP junto — sem ele, restaurar um"""

    def test_cache_de_device_com_bond_entra_no_snapshot(self, tmp_path: Path) -> None:
        src = tmp_path / "bluetooth"
        src.mkdir()
        mac = "AA:BB:CC:00:00:11"
        _arvore_bluez(src, {mac: CACHE_SAO})
        dst = tmp_path / "snap"

        proc = _roda(SNAPSHOT, src, "--quiet", HEFESTO_BT_SNAP_ROOT=str(dst))
        assert proc.returncode == 0, proc.stderr

        snaps = sorted(p for p in dst.iterdir() if p.is_dir())
        assert snaps, f"nenhum snapshot criado (stdout={proc.stdout!r})"
        copiado = snaps[-1] / ADAPTER / "cache" / mac
        assert copiado.exists(), (
            "o cache SDP do device com bond NÃO foi para o snapshot — "
            "restaurar este bond produziria um controle zumbi"
        )
        assert "[ServiceRecords]" in copiado.read_text(encoding="utf-8")
        assert (snaps[-1] / ADAPTER / mac / "info").exists()

    def test_cache_de_device_sem_bond_fica_de_fora(self, tmp_path: Path) -> None:
        """O que era grande e de fato descartável — dezenas de MACs vistos só em"""
        src = tmp_path / "bluetooth"
        src.mkdir()
        com_bond = "AA:BB:CC:00:00:11"
        adp = _arvore_bluez(src, {com_bond: CACHE_SAO})
        so_scan = "AA:BB:CC:00:00:99"
        (adp / "cache" / so_scan).write_text("[General]\nName=Fone\n", encoding="utf-8")
        dst = tmp_path / "snap"

        proc = _roda(SNAPSHOT, src, "--quiet", HEFESTO_BT_SNAP_ROOT=str(dst))
        assert proc.returncode == 0, proc.stderr

        snap = sorted(p for p in dst.iterdir() if p.is_dir())[-1]
        assert (snap / ADAPTER / "cache" / com_bond).exists()
        assert not (snap / ADAPTER / "cache" / so_scan).exists(), (
            "cache de MAC sem bond não deve inchar o snapshot"
        )

    def test_mudanca_so_no_cache_gera_snapshot_novo(self, tmp_path: Path) -> None:
        """SNAPSHOT-SIG-COBRE-TUDO-01 — o dedup precisa enxergar o cache."""
        src = tmp_path / "bluetooth"
        src.mkdir()
        mac = "AA:BB:CC:00:00:11"
        adp = _arvore_bluez(src, {mac: CACHE_SAO})
        dst = tmp_path / "snap"

        assert _roda(SNAPSHOT, src, "--quiet", HEFESTO_BT_SNAP_ROOT=str(dst)).returncode == 0
        primeiro = sorted(p for p in dst.iterdir() if p.is_dir())
        assert len(primeiro) == 1

        assert _roda(SNAPSHOT, src, "--quiet", HEFESTO_BT_SNAP_ROOT=str(dst)).returncode == 0
        assert len(sorted(p for p in dst.iterdir() if p.is_dir())) == 1, (
            "estado idêntico não pode gerar snapshot novo"
        )

        (adp / "cache" / mac).write_text(
            CACHE_SAO + "0x00010002=3600FF0900\n", encoding="utf-8"
        )
        assert _roda(SNAPSHOT, src, "--quiet", HEFESTO_BT_SNAP_ROOT=str(dst)).returncode == 0
        depois = sorted(p for p in dst.iterdir() if p.is_dir())
        assert len(depois) == 2, (
            "mudança só no cache SDP TEM de gerar snapshot — senão o registro "
            "novo nunca é preservado e o restore devolve um controle zumbi"
        )
        assert "0x00010002" in (depois[-1] / ADAPTER / "cache" / mac).read_text(
            encoding="utf-8"
        )

    def test_invariante_de_nunca_fotografar_vazio_segue_de_pe(
        self, tmp_path: Path
    ) -> None:
        """A inclusão do cache não pode ter afrouxado a regra que protege o"""
        src = tmp_path / "bluetooth"
        (src / ADAPTER / "cache").mkdir(parents=True)
        (src / ADAPTER / "cache" / "AA:BB:CC:00:00:11").write_text(
            CACHE_SAO, encoding="utf-8"
        )
        dst = tmp_path / "snap"

        proc = _roda(SNAPSHOT, src, "--quiet", HEFESTO_BT_SNAP_ROOT=str(dst))
        assert proc.returncode == 0
        assert not dst.exists() or not [p for p in dst.iterdir() if p.is_dir()], (
            "cache sem nenhum bond não pode virar snapshot"
        )


class TestRestoreNaoPropagaCacheEnvenenado:
    def test_restore_recusa_entrada_sem_service_records(self) -> None:
        """Restaurar um cache podre por cima de um bom recriaria o zumbi — o"""
        text = RESTORE.read_text(encoding="utf-8")
        assert "[ServiceRecords]" in text, (
            "o restore precisa inspecionar a seção antes de copiar"
        )
        assert "não restaurado" in text


class TestWatchdogCuraOZumbi:
    """Vigia 3: curar sem destruir nada."""

    def test_nao_apaga_o_cache_nem_o_bond(self, tmp_path: Path) -> None:
        src = tmp_path / "bluetooth"
        src.mkdir()
        podre = "AA:BB:CC:00:00:11"
        sao = "AA:BB:CC:00:00:22"
        adp = _arvore_bluez(src, {podre: CACHE_ENVENENADO, sao: CACHE_SAO})

        proc = _roda(
            WATCHDOG,
            src,
            "--sdp-cache-only",
            HEFESTO_HIDRAW_ROOT=str(tmp_path / "hidraw-vazio"),
            HEFESTO_BT_STAMP_DIR=str(tmp_path / "stamps"),
        )
        assert proc.returncode == 0, proc.stderr

        assert (adp / "cache" / podre).exists(), (
            "a vigia NÃO pode apagar o cache: o browse bem-sucedido reescreve o "
            "arquivo, e apagá-lo destruiria o registro recém-obtido"
        )
        assert (adp / "cache" / sao).exists(), "cache íntegro é intocável"
        for mac in (podre, sao):
            assert (adp / mac / "info").exists(), (
                "a cura não pode destruir o bond (LinkKey) — o ponto é "
                "justamente não precisar re-parear"
            )

    def test_documenta_as_duas_causas_e_nao_manda_reparear(self) -> None:
        text = WATCHDOG.read_text(encoding="utf-8")
        assert "SDP-CACHE-01" in text
        assert "ServiceRecords" in text
        vigia3 = text.split("vigia_sdp_cache() {", 1)[1].split("\n}\n", 1)[0]
        assert "Connect" in vigia3, "a cura é Connect() iniciado pelo host"
        assert "rm -f" not in vigia3, (
            "apagar o cache aqui destrói o registro que o browse acabou de gravar"
        )
        assert "Disconnect" not in vigia3, (
            "derrubar o link transforma cura automática em intervenção manual "
            "(o DualSense dorme e só o PS o acorda)"
        )
        assert "00001124" in vigia3, "só device de perfil HID deve ser tocado"
        assert "sdptool browse" in vigia3, (
            "a vigia precisa distinguir 'direção da conexão' de 'device travado' "
            "antes de prescrever qualquer coisa"
        )
        assert "reset de hardware" in vigia3
        codigo = "\n".join(
            linha
            for linha in vigia3.splitlines()
            if not linha.lstrip().startswith("#")
        )
        assert "hci0" not in codigo, (
            "o path D-Bus tem de sair da árvore real (_dbus_device_paths), "
            "não de um adaptador concatenado"
        )
        assert "_dbus_device_paths" in codigo


class TestDoctorNomeiaACausa:
    def test_check_registrado_e_prescricao_correta(self) -> None:
        text = DOCTOR.read_text(encoding="utf-8")
        assert "check_bt_sdp_cache_envenenado" in text
        assert text.count("check_bt_sdp_cache_envenenado") >= 2
        sintoma = text.split("check_bt_connected_sem_hidraw()", 1)[1].split("\n}", 1)[0]
        assert "ANTES de desparear" in sintoma, (
            "o check do sintoma deve apontar para a causa antes de sugerir "
            "destruir o bond"
        )

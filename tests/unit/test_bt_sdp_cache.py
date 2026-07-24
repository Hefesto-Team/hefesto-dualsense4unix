"""SDP-CACHE-01 — cache SDP do perfil HID é CRÍTICO, não descartável.

Diagnóstico (23/07/2026, medido ao vivo com 4 controles conectados):
o registro SDP do perfil HID mora em ``/var/lib/bluetooth/<adapter>/cache/<MAC>``,
seção ``[ServiceRecords]``. É dele que o BlueZ tira o descritor HID em
``profiles/input/device.c:hidp_add_connection()``. Uma entrada de cache SEM essa
seção produz um controle ZUMBI:

    bond íntegro + ACL AUTH/ENCRYPT vivo + Connected=true na GUI
    + ZERO hidraw + ZERO uhid + ZERO input

Medido: 46 bytes no controle quebrado contra 1124..1433 bytes COM
``[ServiceRecords]`` nos três sãos.

Duas causas produzem essa assinatura, e elas pedem respostas diferentes:

(a) **direção da conexão** — o controle reconecta ENTRANTE (PS/SYNC) e esse
    caminho só consulta o cache; o browse só acontece quando o HOST inicia.
    Curável por ``Connect()``: sem ``[ServiceRecords]`` o BlueZ marca
    ``svc_resolved=false`` (src/device.c:4415) e refaz o browse sozinho.
(b) **controle travado** — ele aceita ACL/auth/cripto e não responde mais nada
    acima disso. Aí o cache truncado é CONSEQUÊNCIA (o BlueZ grava o nome e o
    browse não devolve serviço nenhum), e nem ``Connect()`` nem re-pareamento
    resolvem. Discriminador medido: ``sdptool browse`` responde em <1 s no
    controle são e estoura o timeout no travado.

O ``bt_bonds_snapshot.sh`` excluía ``cache/`` de propósito, com a premissa
escrita no cabeçalho de que era "só cache de SDP/nome, grande e não-crítico".
A premissa estava errada e é o que este arquivo trava.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = REPO_ROOT / "scripts" / "bt_bonds_snapshot.sh"
RESTORE = REPO_ROOT / "scripts" / "bt_bonds_restore.sh"
WATCHDOG = REPO_ROOT / "scripts" / "bt_health_watchdog.sh"
DOCTOR = REPO_ROOT / "scripts" / "doctor.sh"

# Faixa sintética canônica das fixtures (test_anonimato_de_fixtures.py).
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

# A assinatura exata do zumbi: só o nome, sem [ServiceRecords].
CACHE_ENVENENADO = """[General]
Name=DualSense Wireless Controller
"""


def _arvore_bluez(raiz: Path, devices: dict[str, str | None]) -> Path:
    """Monta uma árvore /var/lib/bluetooth de mentira.

    ``devices`` mapeia MAC -> conteúdo do cache (None = sem entrada de cache).
    Todo device ganha um ``info`` de perfil HID (é o recorte que importa).
    """
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
    """O snapshot precisa levar o registro SDP junto — sem ele, restaurar um
    bond devolve um controle zumbi (bond válido, HID que nunca sobe)."""

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
        # E o bond em si continua indo junto, claro.
        assert (snaps[-1] / ADAPTER / mac / "info").exists()

    def test_cache_de_device_sem_bond_fica_de_fora(self, tmp_path: Path) -> None:
        """O que era grande e de fato descartável — dezenas de MACs vistos só em
        scan — segue fora. Só o cache de quem tem bond é crítico."""
        src = tmp_path / "bluetooth"
        src.mkdir()
        com_bond = "AA:BB:CC:00:00:11"
        adp = _arvore_bluez(src, {com_bond: CACHE_SAO})
        # MAC visto em scan: existe em cache/ e NÃO tem diretório de bond.
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
        """SNAPSHOT-SIG-COBRE-TUDO-01 — o dedup precisa enxergar o cache.

        A assinatura hasheava SÓ os ``info``. Com o cache passando a ser
        copiado, uma mudança exclusivamente nele caía no no-op de "estado
        idêntico" e nunca virava snapshot — o fix do SDP-CACHE-01 nascia
        inerte. Medido ao vivo em 23/07: o sha256 dos ``info`` batia com o
        ``.last-signature`` e o snapshot mais recente não tinha ``cache/``.
        """
        src = tmp_path / "bluetooth"
        src.mkdir()
        mac = "AA:BB:CC:00:00:11"
        adp = _arvore_bluez(src, {mac: CACHE_SAO})
        dst = tmp_path / "snap"

        assert _roda(SNAPSHOT, src, "--quiet", HEFESTO_BT_SNAP_ROOT=str(dst)).returncode == 0
        primeiro = sorted(p for p in dst.iterdir() if p.is_dir())
        assert len(primeiro) == 1

        # Estado idêntico => no-op (a dedup tem de continuar funcionando).
        assert _roda(SNAPSHOT, src, "--quiet", HEFESTO_BT_SNAP_ROOT=str(dst)).returncode == 0
        assert len(sorted(p for p in dst.iterdir() if p.is_dir())) == 1, (
            "estado idêntico não pode gerar snapshot novo"
        )

        # Só o cache muda (novo registro SDP; os `info` seguem byte-a-byte iguais).
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
        """A inclusão do cache não pode ter afrouxado a regra que protege o
        último backup bom: zero bonds => sair sem tocar em nada."""
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
        """Restaurar um cache podre por cima de um bom recriaria o zumbi — o
        restore tem que pular a entrada e dizer que pulou."""
        text = RESTORE.read_text(encoding="utf-8")
        assert "[ServiceRecords]" in text, (
            "o restore precisa inspecionar a seção antes de copiar"
        )
        assert "não restaurado" in text


class TestWatchdogCuraOZumbi:
    """Vigia 3: curar sem destruir nada.

    A cura é um ``Connect()`` iniciado pelo HOST — sem ``[ServiceRecords]`` o
    BlueZ marca ``svc_resolved=false`` (src/device.c:4415) e é obrigado a
    refazer o browse. Nem o bond nem o cache podem ser tocados: o browse
    bem-sucedido REESCREVE o cache, e apagá-lo depois destrói justamente o
    registro recém-obtido (erro cometido e medido em 23/07).
    """

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
        # Escopo = corpo da função (as vigias 1/2 citam remove legitimamente).
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
        # Caso (b): device que não responde SDP. Mandar re-parear aí é mentira —
        # medido 23/07: sdptool browse estoura 35 s no controle travado.
        assert "sdptool browse" in vigia3, (
            "a vigia precisa distinguir 'direção da conexão' de 'device travado' "
            "antes de prescrever qualquer coisa"
        )
        assert "reset de hardware" in vigia3
        # WATCHDOG-HCI-HARDCODE-01: concatenar o adaptador faz a vigia virar
        # no-op MUDO num hci1 — e hci1 já apareceu nesta máquina. A checagem
        # ignora comentários (que citam o defeito de propósito).
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
        # Registrado na execução, não só definido.
        assert text.count("check_bt_sdp_cache_envenenado") >= 2
        # O check antigo (sintoma) não pode mais mandar desparear de cara.
        sintoma = text.split("check_bt_connected_sem_hidraw()", 1)[1].split("\n}", 1)[0]
        assert "ANTES de desparear" in sintoma, (
            "o check do sintoma deve apontar para a causa antes de sugerir "
            "destruir o bond"
        )

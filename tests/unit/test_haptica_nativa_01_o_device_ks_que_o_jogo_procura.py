"""O device de áudio KS do DualSense — HAPTICA-NATIVA-01.

O PRAGMATA só abre a háptica quando `SetupDiGetClassDevsExW(KSCATEGORY_AUDIO)`
devolve um device com o MESMO `ContainerId` do endpoint de áudio do controle
(medido no trace de 17/09/2026). O GE-Proton exclui o DualSense desse device; o
`audio_ks_dualsense` o grava no `system.reg` a cada lançamento.

Morde em sete alturas:

1. **a conta** — o `ContainerId` do `winepulse`, byte a byte;
2. **o dono manda** — o Data4 que o próprio prefixo já registrou vence o palpite;
3. **o que o `setupapi` exige** — sem `ClassGUID` o device é descartado;
4. **idempotência** — a segunda rodada não escreve, nem depois de o Wine
   reordenar o arquivo; nenhum bloco alheio some;
5. **replug e zero controles** — o device velho sai, não acumula;
6. **N controles** — um device por controle no cabo;
7. **prefixo ocupado** — com o `wineserver` DAQUELE prefixo vivo, não escreve.

Tudo em sysfs e registro sintéticos: a suíte nunca lê o controle dela, e os
seriais das instâncias do winebus estão na faixa sintética `aa:bb:cc`.
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import tempfile
import threading
from pathlib import Path

from hefesto_dualsense4unix.integrations import audio_ks_dualsense as ks

_CABECALHO = "WINE REGISTRY Version 2\n;; All keys relative to REGISTRY\\\\Machine\n\n#arch=win64\n"

#: Blocos ALHEIOS que o módulo nunca pode tocar: o wineusb, o winebus (serial
#: sintético) e uma chave qualquer.
_ALHEIOS = [
    "[System\\\\ControlSet001\\\\Enum\\\\USB\\\\VID_054C&PID_0CE6\\\\512&256&3&3] 1789693594\n"
    '"ClassGUID"="{36FC9E60-C465-11CF-8056-444553540000}"\n',
    "[System\\\\ControlSet001\\\\Enum\\\\USB\\\\VID_054C&PID_0CE6&MI_03"
    "\\\\256&AA:BB:CC:00:00:01&0&0&0] 1789694981\n"
    '"ContainerId"="{0ce6054c-0003-0019-0000-000000000000}"\n',
    "[Software\\\\Wine\\\\Qualquer] 1789600000\n" '"Valor"="1"\n',
]


def _registro(*extra: str) -> str:
    return _CABECALHO + "\n" + "\n".join(_ALHEIOS + list(extra))


def _prefixo(tmp_path: Path, texto: str) -> Path:
    compat = tmp_path / "compatdata" / "3357650"
    (compat / "pfx").mkdir(parents=True)
    (compat / "pfx" / "system.reg").write_text(texto, encoding="utf-8")
    return compat


def _blob_do_endpoint(guid_bytes: bytes) -> str:
    """O `ContainerId` como o mmdevapi guarda: VT_CLSID, dword, 16 bytes."""
    corpo = bytes.fromhex("4800efbe01000000") + guid_bytes
    return ",".join(f"{b:02x}" for b in corpo)


def _guid_bytes(d1: int, d2: int, d3: int, d4: bytes) -> bytes:
    return d1.to_bytes(4, "little") + d2.to_bytes(2, "little") + d3.to_bytes(2, "little") + d4


def _endpoint(d4: bytes, *, bus: int = 3, dev: int = 28) -> str:
    return (
        "[Software\\\\Microsoft\\\\Windows\\\\CurrentVersion\\\\MMDevices\\\\Audio\\\\Render"
        "\\\\{89E4A2D5-34D3-4897-B29D-AABBCC000001}\\\\Properties] 1789695489\n"
        '"{8c7ed206-3f8a-4827-b3ab-ae9e1faefc6c},2"=hex:'
        + _blob_do_endpoint(_guid_bytes(0x0CE6054C, bus, dev, d4))
        + "\n"
    )


def _nossos(texto: str) -> list[str]:
    return [ks._cabecalho(b) for b in ks._blocos(texto) if ks.e_bloco_nosso(b)]


def _ler(compat: Path) -> str:
    return (compat / "pfx" / "system.reg").read_text(encoding="utf-8")


PADRAO = ks.Controle(pid=0x0CE6, bus=3, dev=28, usec=None)


# ---------------------------------------------------------------- 1. a conta


def test_a_conta_do_winepulse_da_o_valor_que_vibrou() -> None:
    """17/09, 23:05: bus 3, dev 28, Data4 zero — o `ContainerId` que casou."""
    assert ks.container_id(PADRAO, bytes(8)) == "{0ce6054c-0003-001c-0000-000000000000}"


def test_o_data4_e_o_usec_em_little_endian() -> None:
    # O byte menos significativo sai primeiro. Os seis finais caem na faixa
    # sintética `aabbcc` de propósito: o fim do GUID tem forma de MAC.
    d4 = (0x030000CCBBAA0201).to_bytes(8, "little")
    assert ks.container_id(PADRAO, d4) == "{0ce6054c-0003-001c-0102-aabbcc000003}"


def test_o_edge_tem_o_pid_dele() -> None:
    edge = ks.Controle(pid=0x0DF2, bus=1, dev=2, usec=None)
    assert ks.container_id(edge, bytes(8)).startswith("{0df2054c-0001-0002-")


def test_o_sysfs_sintetico_da_os_controles_com_placa_de_som(tmp_path: Path) -> None:
    sysfs = tmp_path / "sys"
    udev = tmp_path / "udev"
    udev.mkdir()

    def usb(nome: str, vid: str, pid: str, bus: int, dev: int, *, som: bool, majmin: str) -> None:
        d = sysfs / "bus" / "usb" / "devices" / nome
        d.mkdir(parents=True)
        (d / "idVendor").write_text(vid + "\n")
        (d / "idProduct").write_text(pid + "\n")
        (d / "busnum").write_text(f"{bus}\n")
        (d / "devnum").write_text(f"{dev}\n")
        (d / "dev").write_text(majmin + "\n")
        if som:
            (d / f"{nome}:1.0" / "sound" / "card2").mkdir(parents=True)

    usb("3-2", "054c", "0ce6", 3, 28, som=True, majmin="189:283")
    usb("1-4", "054c", "0df2", 1, 7, som=True, majmin="189:6")
    usb("1-5", "054c", "0ce6", 1, 9, som=False, majmin="189:8")  # sem placa de som
    usb("1-6", "046d", "c52b", 1, 3, som=True, majmin="189:2")  # não é Sony
    (udev / "c189:283").write_text("I:1234567\nE:ID_VENDOR=Sony\n")

    achados = ks.controles_no_cabo(sysfs, udev)
    assert [(c.pid, c.bus, c.dev, c.usec) for c in achados] == [
        (0x0DF2, 1, 7, None),
        (0x0CE6, 3, 28, 1234567),
    ]


# --------------------------------------------------------- 2. o dono manda


def test_o_dono_manda_o_endpoint_diz_zero_e_so_zero_entra(tmp_path: Path) -> None:
    """Mesmo com o USEC do host à mão, o prefixo registrou zero: vale o zero."""
    compat = _prefixo(tmp_path, _registro(_endpoint(bytes(8))))
    com_usec = ks.Controle(pid=0x0CE6, bus=3, dev=28, usec=999)
    ks.aplicar(compat, controles=[com_usec], proc=tmp_path / "proc", carimbo=1)
    texto = _ler(compat)
    assert texto.count("HEFESTOKS&003&028&") and "HEFESTOKS&003&028&1" not in texto
    assert '"ContainerId"="{0ce6054c-0003-001c-0000-000000000000}"' in texto


def test_o_dono_pelo_hid_do_winebus_tambem_vale(tmp_path: Path) -> None:
    d4 = (777).to_bytes(8, "little")
    hid = (
        "[System\\\\ControlSet001\\\\Enum\\\\HID\\\\VID_054C&PID_0CE6&MI_03"
        "\\\\256&AA:BB:CC:00:00:02&0&0&0] 1\n"
        f'"ContainerId"="{ks.container_id(PADRAO, d4)}"\n'
    )
    compat = _prefixo(tmp_path, _registro(hid))
    ks.aplicar(compat, controles=[PADRAO], proc=tmp_path / "proc", carimbo=1)
    assert f'"ContainerId"="{ks.container_id(PADRAO, d4)}"' in "\n".join(
        b for b in ks._blocos(_ler(compat)) if ks.e_bloco_nosso(b)
    )


def test_sem_dono_entram_as_duas_variantes(tmp_path: Path) -> None:
    compat = _prefixo(tmp_path, _registro())
    com_usec = ks.Controle(pid=0x0CE6, bus=3, dev=28, usec=5)
    r = ks.aplicar(compat, controles=[com_usec], proc=tmp_path / "proc", carimbo=1)
    assert r.variantes == 2
    texto = _ler(compat)
    assert "{0ce6054c-0003-001c-0000-000000000000}" in texto
    assert ks.container_id(com_usec, (5).to_bytes(8, "little")) in texto


def test_o_dono_nao_e_a_propria_resposta(tmp_path: Path) -> None:
    """Os nossos blocos saem ANTES da pergunta — senão ela responde a si mesma."""
    compat = _prefixo(tmp_path, _registro())
    com_usec = ks.Controle(pid=0x0CE6, bus=3, dev=28, usec=5)
    ks.aplicar(compat, controles=[com_usec], proc=tmp_path / "proc", carimbo=1)
    r = ks.aplicar(compat, controles=[com_usec], proc=tmp_path / "proc", carimbo=2)
    assert r.variantes == 2


# ------------------------------------------- 3. o que o setupapi exige


def test_o_device_leva_classguid_e_a_interface_ligada(tmp_path: Path) -> None:
    """Sem `ClassGUID` o `setupapi` do Wine descarta o device (medido no trace)."""
    compat = _prefixo(tmp_path, _registro(_endpoint(bytes(8))))
    ks.aplicar(compat, controles=[PADRAO], proc=tmp_path / "proc", carimbo=1)
    blocos = [b for b in ks._blocos(_ler(compat)) if ks.e_bloco_nosso(b)]
    enum = next(b for b in blocos if "\\\\Enum\\\\USB\\\\" in b)
    assert '"ClassGUID"="{36FC9E60-C465-11CF-8056-444553540000}"' in enum
    assert "{4d36e96c" not in enum.lower()  # MEDIA: o GE apagaria
    assert '"HardwareID"=str(7):"USB\\\\VID_054C&PID_0CE6\\0"' in enum
    assert any(b.rstrip().endswith('"Linked"=dword:00000001') for b in blocos)
    assert any(ks.KS in b and '"DeviceInstance"=' in b for b in blocos)


# ------------------------------------------------------ 4. idempotência


def test_a_segunda_rodada_nao_escreve_e_nada_alheio_some(tmp_path: Path) -> None:
    compat = _prefixo(tmp_path, _registro(_endpoint(bytes(8))))
    antes = {ks._cabecalho(b) for b in ks._blocos(_ler(compat))}
    r1 = ks.aplicar(compat, controles=[PADRAO], proc=tmp_path / "proc", carimbo=1)
    r2 = ks.aplicar(compat, controles=[PADRAO], proc=tmp_path / "proc", carimbo=2)
    assert r1.escreveu and not r2.escreveu
    depois = {ks._cabecalho(b) for b in ks._blocos(_ler(compat))}
    assert antes <= depois


def test_o_wine_reordenar_o_arquivo_nao_forca_reescrita(tmp_path: Path) -> None:
    """O `wineserver` regrava em ordem alfabética e põe `#time=` em cada chave."""
    compat = _prefixo(tmp_path, _registro(_endpoint(bytes(8))))
    ks.aplicar(compat, controles=[PADRAO], proc=tmp_path / "proc", carimbo=1)
    blocos = ks._blocos(_ler(compat))
    cabeca, resto = blocos[0], blocos[1:]
    reordenado = [b.replace("\n", "\n#time=1dd46ed50b330b8\n", 1) for b in sorted(resto)]
    (compat / "pfx" / "system.reg").write_text(
        "\n".join([cabeca, *reordenado]), encoding="utf-8"
    )
    assert not ks.aplicar(compat, controles=[PADRAO], proc=tmp_path / "proc", carimbo=9).escreveu


def test_o_legado_da_prova_a_mao_sai(tmp_path: Path) -> None:
    legado = (
        "[System\\\\ControlSet001\\\\Enum\\\\USB\\\\VID_054C&PID_0CE6\\\\4298&85989E60] 1\n"
        '"Class"="USB"\n'
    )
    compat = _prefixo(tmp_path, _registro(legado))
    ks.aplicar(compat, controles=[], proc=tmp_path / "proc", carimbo=1)
    assert "4298&85989E60" not in _ler(compat)
    assert "512&256&3&3" in _ler(compat)  # o do wineusb fica


# -------------------------------------------- 5. replug e zero controles


def test_o_replug_substitui_e_nao_acumula(tmp_path: Path) -> None:
    compat = _prefixo(tmp_path, _registro())
    ks.aplicar(compat, controles=[PADRAO], proc=tmp_path / "proc", carimbo=1)
    replugado = ks.Controle(pid=0x0CE6, bus=3, dev=29, usec=None)
    ks.aplicar(compat, controles=[replugado], proc=tmp_path / "proc", carimbo=2)
    texto = _ler(compat)
    assert "&003&029&" in texto and "&003&028&" not in texto


def test_sem_controle_no_cabo_os_nossos_saem_e_os_alheios_ficam(tmp_path: Path) -> None:
    compat = _prefixo(tmp_path, _registro())
    ks.aplicar(compat, controles=[PADRAO], proc=tmp_path / "proc", carimbo=1)
    ks.aplicar(compat, controles=[], proc=tmp_path / "proc", carimbo=2)
    texto = _ler(compat)
    assert not _nossos(texto)
    for alheio in _ALHEIOS:
        assert alheio.split("\n", 1)[0].split("] ")[0] in texto


# ---------------------------------------------------------- 6. N controles


def test_um_device_por_controle(tmp_path: Path) -> None:
    compat = _prefixo(tmp_path, _registro(_endpoint(bytes(8)), _endpoint(bytes(8), bus=1, dev=7)))
    dois = [PADRAO, ks.Controle(pid=0x0CE6, bus=1, dev=7, usec=None)]
    r = ks.aplicar(compat, controles=dois, proc=tmp_path / "proc", carimbo=1)
    assert r.variantes == 2
    texto = _ler(compat)
    assert "HEFESTOKS&003&028&0" in texto and "HEFESTOKS&001&007&0" in texto


# ------------------------------------------------------ 7. prefixo ocupado


def _wineserver_de_mentira(proc: Path, pid: str, prefixo: str) -> None:
    d = proc / pid
    d.mkdir(parents=True)
    (d / "comm").write_text("wineserver\n")
    (d / "environ").write_bytes(b"HOME=/x\0WINEPREFIX=" + prefixo.encode() + b"\0")


def test_com_o_wineserver_daquele_prefixo_vivo_nao_escreve(tmp_path: Path) -> None:
    compat = _prefixo(tmp_path, _registro())
    antes = _ler(compat)
    _wineserver_de_mentira(tmp_path / "proc", "4242", str(compat / "pfx") + "/")
    r = ks.aplicar(compat, controles=[PADRAO], proc=tmp_path / "proc", carimbo=1)
    assert r.motivo == "ocupado" and not r.escreveu
    assert _ler(compat) == antes


def test_o_wineserver_de_outro_prefixo_nao_segura(tmp_path: Path) -> None:
    compat = _prefixo(tmp_path, _registro())
    _wineserver_de_mentira(tmp_path / "proc", "4243", "/outro/compatdata/1/pfx/")
    assert ks.aplicar(compat, controles=[PADRAO], proc=tmp_path / "proc", carimbo=1).escreveu


def test_sem_system_reg_nao_faz_nada(tmp_path: Path) -> None:
    compat = tmp_path / "compatdata" / "1"
    compat.mkdir(parents=True)
    assert ks.aplicar(compat, controles=[PADRAO], proc=tmp_path / "proc").motivo == "sem-registro"


# ------------------------------------------------------------------ a CLI


def test_a_cli_grava_e_o_remover_tira(tmp_path: Path) -> None:
    compat = _prefixo(tmp_path, _registro(_endpoint(bytes(8))))
    sysfs = tmp_path / "sys"
    d = sysfs / "bus" / "usb" / "devices" / "3-2"
    (d / "3-2:1.0" / "sound" / "card2").mkdir(parents=True)
    campos = {"idVendor": "054c", "idProduct": "0ce6", "busnum": "3", "devnum": "28"}
    for nome, valor in campos.items():
        (d / nome).write_text(valor + "\n")
    base = ["--prefixo", str(compat), "--sysfs", str(sysfs), "--udev-data", str(tmp_path / "udev")]
    assert ks.main(base) == 0
    assert _nossos(_ler(compat))
    assert ks.main([*base, "--remover"]) == 0
    assert not _nossos(_ler(compat))


# ------------------------------------------------ 8. a fiação no lançamento
#
# A cura escrita e nunca ligada é o defeito mais caro desta casa: o wrapper DE
# VERDADE, em `sh`, com um daemon de mentira que responde ao ping, um sysfs e um
# prefixo sintéticos.

RAIZ = Path(__file__).resolve().parents[2]
_WRAPPER = RAIZ / "assets" / "hefesto-launch.sh"
_MODULO = RAIZ / "src" / "hefesto_dualsense4unix" / "integrations" / "audio_ks_dualsense.py"


class _DaemonQueResponde:
    """Um socket que responde `result` ao `daemon.status` — o gate de vida."""

    def __init__(self, caminho: Path) -> None:
        self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._sock.bind(str(caminho))
        self._sock.listen(2)
        self._parar = threading.Event()
        self._fio = threading.Thread(target=self._servir, daemon=True)
        self._fio.start()

    def _servir(self) -> None:
        while not self._parar.is_set():
            try:
                self._sock.settimeout(0.2)
                conexao, _ = self._sock.accept()
            except TimeoutError:
                continue
            except OSError:
                return
            with conexao:
                try:
                    conexao.settimeout(1.0)
                    pedido = json.loads(conexao.recv(4096).decode("utf-8"))
                    resposta = {"jsonrpc": "2.0", "id": pedido.get("id"), "result": {}}
                    conexao.sendall(json.dumps(resposta).encode("utf-8") + b"\n")
                except (OSError, ValueError):
                    pass

    def parar(self) -> None:
        self._parar.set()
        self._sock.close()
        self._fio.join(timeout=2)


def _path_minimo(pasta: Path) -> str:
    pasta.mkdir()
    # O PATH mínimo do teste do acelerômetro, mais o `grep` da limpeza: o
    # passo novo não pode depender de `cat` nem de `sed` (medido: sem `sed` o
    # jogo perdia TODAS as variáveis). E o `timeout` do coreutils, que está em
    # toda máquina: sem ele o wrapper cai no ramo sem teto, e a régua do
    # `pactl` travado mediria o ramo errado.
    for ferramenta in ("sh", "python3", "env", "date", "mkdir", "mv", "grep", "timeout"):
        real = shutil.which(ferramenta)
        assert real is not None, f"ferramenta de teste ausente: {ferramenta}"
        (pasta / ferramenta).symlink_to(real)
    return str(pasta)


def _sysfs_com_dualsense(raiz: Path) -> Path:
    d = raiz / "bus" / "usb" / "devices" / "3-2"
    (d / "3-2:1.0" / "sound" / "card2").mkdir(parents=True)
    campos = {"idVendor": "054c", "idProduct": "0ce6", "busnum": "3", "devnum": "28"}
    for nome, valor in campos.items():
        (d / nome).write_text(valor + "\n")
    return raiz


def _pactl_de_mentira(caminho: Path, sinks: str) -> None:
    """Um `pactl` que responde às DUAS perguntas que o produto faz.

    O gancho pergunta `list short sinks` (uma linha por nó) e o curador
    pergunta `list sinks` (o bloco com o proplist). Um dublê que só responde a
    uma delas daria verde sobre metade do caminho.

    **Só `printf`, que é builtin**: o PATH deste teste é o mínimo do produto, e
    nele não há `cat` — um dublê que precisasse dele sairia com rc=1 e a régua
    leria "não há endpoint" onde havia.
    """
    nomes = [ln.split("Name: ")[1] for ln in sinks.splitlines() if "Name: " in ln]
    curto = [f"{i}\t{nome}\tPipeWire\tfloat32le 4ch 48000Hz\tIDLE" for i, nome in enumerate(nomes)]

    def imprime(linhas: list[str]) -> str:
        return "printf '%s\\n' " + " ".join(f"'{ln}'" for ln in linhas)

    caminho.write_text(
        "#!/bin/sh\n"
        'case "$*" in\n'
        f"    'list short sinks') {imprime(curto)} ;;\n"
        f"    'list sinks') {imprime(sinks.splitlines())} ;;\n"
        "    *) exit 1 ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    caminho.chmod(0o755)


def _sysfs_com_ancora(raiz: Path) -> Path:
    """Um hub USB com a interface dele: a âncora de onde o ContainerId sai.

    O nó declara a INTERFACE (`3-4:1.0`) e o GUID sai do PAI dela — o udev
    devolve um ancestral, nunca o próprio device.
    """
    d = raiz / "devices" / "pci0000:00" / "usb3" / "3-4"
    (d / "3-4:1.0").mkdir(parents=True)
    (raiz / "bus" / "usb" / "devices").mkdir(parents=True)
    for nome, valor in {
        "idVendor": "2357", "idProduct": "0604", "busnum": "3", "devnum": "29",
    }.items():
        (d / nome).write_text(valor + "\n")
    return raiz


#: O nome tem de carregar as três agulhas dos patches do GE, e ele é longo
#: por isso: `Sony_Interactive_Entertainment`, `Wireless_Controller`,
#: `Speaker__sink` — mais o marcador da casa e o rabo do `uniq`.
_NOME_DO_NO_DO_RADIO = (
    "alsa_output.usb-Sony_Interactive_Entertainment_"
    "DualSense_Wireless_Controller_HEFESTOaabbcc-00.HiFi__Speaker__sink"
)

_SINK_DO_RADIO = f"""Sink #7
\tState: IDLE
\tName: {_NOME_DO_NO_DO_RADIO}
\tProperties:
\t\tdevice.bus = "usb"
\t\tdevice.vendor.id = "054c"
\t\tdevice.product.id = "0ce6"
\t\tsysfs.path = "/devices/pci0000:00/usb3/3-4/3-4:1.0"
"""


def _lancar(
    tmp_path: Path,
    *,
    sysfs: Path,
    env_do_daemon: str,
    registro: str,
    sinks: str | None = None,
) -> tuple[str, str]:
    """Roda o wrapper; devolve (o valor da opção do MHWilds no jogo, o system.reg).

    `sinks` põe um `pactl` de mentira no PATH, e é assim que o caso do RÁDIO se
    mede: sem ele o `command -v pactl` falha e a sondagem do endpoint responde
    "não há" — que é o comportamento certo numa máquina sem servidor de som.
    """
    home = tmp_path / "home"
    binario = home / ".local" / "share" / "hefesto-dualsense4unix" / "bin"
    binario.mkdir(parents=True)
    curador = binario / "hefesto-audio-ks"
    curador.write_bytes(_MODULO.read_bytes())
    curador.chmod(0o755)
    estado = tmp_path / "estado"
    pasta = estado / "hefesto-dualsense4unix" / "launch_env"
    pasta.mkdir(parents=True)
    (pasta / "default.env").write_text(env_do_daemon, encoding="utf-8")
    compat = _prefixo(tmp_path, registro)
    caminho = _path_minimo(tmp_path / "bin")
    if sinks is not None:
        _pactl_de_mentira(Path(caminho) / "pactl", sinks)
    runtime = Path(tempfile.mkdtemp(prefix="hefks-"))  # AF_UNIX: caminho curto
    (runtime / "hefesto-dualsense4unix").mkdir()
    daemon = _DaemonQueResponde(runtime / "hefesto-dualsense4unix" / "hefesto-dualsense4unix.sock")
    try:
        feito = subprocess.run(
            ["sh", str(_WRAPPER), "sh", "-c",
             'printf "%s\\n" "${PROTON_ENABLE_MHWILDS_USB_AUDIO:-ausente}"'],
            env={
                "PATH": caminho,
                "HOME": str(home),
                "XDG_RUNTIME_DIR": str(runtime),
                "XDG_STATE_HOME": str(estado),
                "SteamAppId": "3357650",
                "STEAM_COMPAT_DATA_PATH": str(compat),
                "HEFESTO_SYSFS": str(sysfs),
            },
            capture_output=True,
            text=True,
            timeout=30.0,
            check=False,
        )
    finally:
        daemon.parar()
        shutil.rmtree(runtime, ignore_errors=True)
    assert feito.returncode == 0, feito.stderr
    return feito.stdout.strip(), _ler(compat)


_ENV_LIGADO = (
    "PROTON_KEEP_SONY_AUDIO_ENDPOINT_VISIBLE=1\nPROTON_ENABLE_MHWILDS_USB_AUDIO=1\n"
)


def test_o_gancho_chama_o_curador_a_prova_de_falha_e_antes_do_exec() -> None:
    texto = _WRAPPER.read_text(encoding="utf-8")
    assert re.search(r"^curar_audio_ks \|\| true$", texto, re.MULTILINE)
    assert texto.index("curar_audio_ks || true") < texto.rindex('exec env "$@"')
    assert "hefesto-audio-ks" in texto


def test_com_dualsense_no_cabo_o_device_e_gravado_e_a_opcao_chega_ao_jogo(tmp_path: Path) -> None:
    valor, registro = _lancar(
        tmp_path,
        sysfs=_sysfs_com_dualsense(tmp_path / "sys"),
        env_do_daemon=_ENV_LIGADO,
        registro=_registro(_endpoint(bytes(8))),
    )
    assert valor == "1"
    assert '"ContainerId"="{0ce6054c-0003-001c-0000-000000000000}"' in registro
    assert "HEFESTOKS&003&028&0" in registro


def test_sem_dualsense_no_cabo_a_opcao_sai_zero_e_nada_e_gravado(tmp_path: Path) -> None:
    """O Black Desert: sem o controle, a opção só exporia KS falso de headset."""
    vazio = tmp_path / "sys"
    (vazio / "bus" / "usb" / "devices").mkdir(parents=True)
    valor, registro = _lancar(
        tmp_path, sysfs=vazio, env_do_daemon=_ENV_LIGADO, registro=_registro()
    )
    assert valor == "0", "omitir não desliga: o proton preenche do user_settings.py"
    assert "HEFESTOKS" not in registro


def test_sem_a_opcao_o_gancho_so_limpa_o_que_e_nosso(tmp_path: Path) -> None:
    nosso = "\n".join(ks.blocos_do_controle(PADRAO, [bytes(8)], 1))
    valor, registro = _lancar(
        tmp_path,
        sysfs=_sysfs_com_dualsense(tmp_path / "sys"),
        env_do_daemon="PROTON_ENABLE_MHWILDS_USB_AUDIO=0\n",
        registro=_registro(nosso),
    )
    assert valor == "0"
    assert "HEFESTOKS" not in registro
    assert "512&256&3&3" in registro


# -- o rádio (HAPTICA-POR-RADIO-01, P3c) --------------------------------------


def test_com_o_endpoint_do_radio_vivo_a_opcao_chega_ao_jogo(tmp_path: Path) -> None:
    """Sem DualSense no cabo, mas com o nó do rádio de pé: o caminho tem de abrir.

    Sem a opção o `setupapi` não publica interface KSCATEGORY_AUDIO nenhuma
    (patch 0103, `devinst.c`) e o jogo desiste antes de olhar o registro.
    """
    valor, registro = _lancar(
        tmp_path,
        sysfs=_sysfs_com_ancora(tmp_path / "sys"),
        env_do_daemon=_ENV_LIGADO,
        registro=_registro(),
        sinks=_SINK_DO_RADIO,
    )
    assert valor == "1"
    # O ContainerId é o da ÂNCORA (2357/0604, bus 3, dev 29), não o da Sony.
    assert '"ContainerId"="{06042357-0003-001d-0000-000000000000}"' in registro
    assert "HEFESTOKS&003&029&0" in registro
    assert "VID_054C&PID_0CE6" in registro, "o HardwareID continua sendo o do controle"


def test_sem_no_do_radio_nem_cabo_nada_muda(tmp_path: Path) -> None:
    """Um `pactl` que responde, e nenhum nó nosso na lista: a opção sai zero."""
    outro = 'Sink #3\n\tState: IDLE\n\tName: alsa_output.pci-0000_0a_00.1.hdmi-stereo\n'
    valor, registro = _lancar(
        tmp_path,
        sysfs=_sysfs_com_ancora(tmp_path / "sys"),
        env_do_daemon=_ENV_LIGADO,
        registro=_registro(),
        sinks=outro,
    )
    assert valor == "0"
    assert "HEFESTOKS" not in registro


# -- a sonda do nó do rádio não segura o jogo (INSTALL-UNIVERSAL, 18/09) -------
#
# `endpoint_de_mentira_vivo` roda em TODO lançamento com o daemon vivo e sem
# DualSense no cabo. Nasceu sem teto de tempo e com o ambiente do runtime da
# Steam, ao contrário de todo vizinho do arquivo. Um `pipewire-pulse` travado —
# medido nesta casa por horas depois da queda de um controle BT — deixava o
# `pactl` preso e o wrapper nunca chegava ao `exec`: nenhum jogo abria.

def _lancar_com_o_pactl(
    tmp_path: Path,
    *,
    corpo_do_pactl: str,
    env_extra: dict[str, str] | None = None,
    prazo_s: float = 30.0,
    eco: str = "${PROTON_ENABLE_MHWILDS_USB_AUDIO:-ausente}",
) -> str:
    """Roda o wrapper com um `pactl` escrito à mão; devolve o que o jogo viu.

    Separado de :func:`_lancar` por um motivo só: o `pactl` daqui pode TRAVAR, e
    quem estoura o prazo tem de levar junto o processo preso. O wrapper nasce
    numa sessão própria e, se o prazo estourar, o grupo inteiro morre — sem isso
    a régua reprovaria e deixaria um `pactl` pendurado na máquina.
    """
    home = tmp_path / "home"
    (home / ".local" / "share" / "hefesto-dualsense4unix" / "bin").mkdir(parents=True)
    estado = tmp_path / "estado"
    pasta = estado / "hefesto-dualsense4unix" / "launch_env"
    pasta.mkdir(parents=True)
    (pasta / "default.env").write_text(_ENV_LIGADO, encoding="utf-8")
    compat = _prefixo(tmp_path, _registro())
    vazio = tmp_path / "sys"
    (vazio / "bus" / "usb" / "devices").mkdir(parents=True)
    caminho = _path_minimo(tmp_path / "bin")
    pactl = Path(caminho) / "pactl"
    pactl.write_text("#!/bin/sh\n" + corpo_do_pactl, encoding="utf-8")
    pactl.chmod(0o755)
    runtime = Path(tempfile.mkdtemp(prefix="hefks-"))  # AF_UNIX: caminho curto
    (runtime / "hefesto-dualsense4unix").mkdir()
    daemon = _DaemonQueResponde(runtime / "hefesto-dualsense4unix" / "hefesto-dualsense4unix.sock")
    env = {
        "PATH": caminho,
        "HOME": str(home),
        "XDG_RUNTIME_DIR": str(runtime),
        "XDG_STATE_HOME": str(estado),
        "SteamAppId": "3357650",
        "STEAM_COMPAT_DATA_PATH": str(compat),
        "HEFESTO_SYSFS": str(vazio),
        **(env_extra or {}),
    }
    try:
        proc = subprocess.Popen(
            ["sh", str(_WRAPPER), "sh", "-c", f'printf "%s\\n" "{eco}"'],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        try:
            saida, erro = proc.communicate(timeout=prazo_s)
        except subprocess.TimeoutExpired:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(proc.pid, signal.SIGKILL)
            proc.communicate()
            raise AssertionError(
                f"o wrapper não chegou ao `exec` em {prazo_s:.0f} s: um `pactl` "
                "travado segurou o lançamento do jogo"
            ) from None
    finally:
        daemon.parar()
        shutil.rmtree(runtime, ignore_errors=True)
    assert proc.returncode == 0, erro
    return saida.strip()


def test_o_pactl_travado_nao_segura_o_jogo(tmp_path: Path) -> None:
    """O servidor de som que não responde vira "não há nó", e o jogo abre.

    O `pactl` dublê bloqueia para sempre abrindo um fifo que ninguém escreve —
    sem gastar CPU e sem `sleep`, que o PATH mínimo não tem. O prazo de 8 s não
    é relógio cravado: o wrapper ainda gasta até ~1 s no gate de vida, e o teto
    do `pactl` é de 2 s. O que a régua exige é que ele TERMINE, e com a opção
    do MHWilds escrita "0", como numa máquina sem o nó do rádio.

    MORDIDA: arrancar o `timeout 2` de `endpoint_de_mentira_vivo`, e o wrapper
    fica preso até o prazo estourar.
    """
    trava = tmp_path / "trava"
    os.mkfifo(trava)
    valor = _lancar_com_o_pactl(
        tmp_path,
        corpo_do_pactl=f"read -r _ < '{trava}'\nexit 1\n",
        prazo_s=8.0,
    )
    assert valor == "0"


def test_a_sonda_pergunta_em_c_e_sem_o_loader_da_steam(tmp_path: Path) -> None:
    """O `pactl` recebe `LC_ALL=C` e as variáveis do loader limpas; o jogo não.

    O env que chega ao wrapper é o do runtime da Steam, com uma libpulse própria
    no LD_LIBRARY_PATH. O dublê só responde quando as três condições valem — e o
    jogo, no fim, tem de receber o LD_LIBRARY_PATH e o LD_PRELOAD intactos.

    MORDIDA: tirar o `LC_ALL=C` (ou uma das duas limpezas) da sonda, e a opção
    do MHWilds sai "0" com o nó do rádio de pé.
    """
    loader = tmp_path / "runtime-da-steam"
    loader.mkdir()
    preload = str(tmp_path / "nao-existe.so")  # o ld.so avisa e ignora
    linha = f"7\t{_NOME_DO_NO_DO_RADIO}\tPipeWire\tfloat32le 4ch 48000Hz\tIDLE"
    corpo = (
        '[ -z "${LD_LIBRARY_PATH:-}" ] || exit 1\n'
        '[ -z "${LD_PRELOAD:-}" ] || exit 1\n'
        '[ "${LC_ALL:-}" = C ] || exit 1\n'
        'case "$*" in\n'
        f"    'list short sinks') printf '%s\\n' '{linha}' ;;\n"
        "    *) exit 1 ;;\n"
        "esac\n"
    )
    visto = _lancar_com_o_pactl(
        tmp_path,
        corpo_do_pactl=corpo,
        env_extra={"LD_LIBRARY_PATH": str(loader), "LD_PRELOAD": preload},
        eco="${PROTON_ENABLE_MHWILDS_USB_AUDIO:-ausente}|${LD_LIBRARY_PATH:-}|${LD_PRELOAD:-}",
    )
    assert visto == f"1|{loader}|{preload}"

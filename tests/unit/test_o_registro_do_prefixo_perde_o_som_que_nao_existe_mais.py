"""O-REGISTRO-DO-PREFIXO-PERDE-O-SOM-QUE-NAO-EXISTE-MAIS-01 (15/10/2026).

O prefixo guarda toda saída e entrada de som que o Wine já viu (medido em 12/10:
de 9 a 17 Render por prefixo, até 13 ausentes), e o jogo com a biblioteca da Sony
varre todas. O curador do lançamento poda, com as mesmas travas: a chave ausente
(`DeviceState=4`) e a do nó da casa que não está vivo no `pactl`, achada pelo mapa
do `user.reg`. Os registros de mentira têm o formato real do prefixo.
"""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import audio_ks_dualsense as ks

_RAIZ = "Software\\\\Microsoft\\\\Windows\\\\CurrentVersion\\\\MMDevices\\\\Audio"


def _guid(n: int) -> str:
    return f"{{{uuid.UUID(int=0x5EED_0000_0000_4000_8000_0000_0000_0000 + n)}}}".upper()


AUSENTE_1, AUSENTE_2, AUSENTE_3 = _guid(1), _guid(2), _guid(3)
DUALSENSE_VIVO = _guid(4)
PLACA = _guid(5)
CASA_MORTO = _guid(6)
CASA_MORTO_CAPTURA = _guid(7)
CASA_VIVO = _guid(8)
FORA = _guid(9)

NO_MORTO = "hefesto_som_0000ab"
NO_VIVO = "hefesto_som_0000cd"
MONITOR_MORTO = (
    "alsa_output.usb-Sony_Interactive_Entertainment_"
    "DualSense_Wireless_Controller_HEFESTO0000ab-00.HiFi__Speaker__sink.monitor"
)
NO_DO_CABO = (
    "alsa_output.usb-Sony_Interactive_Entertainment_"
    "DualSense_Wireless_Controller-00.analog-surround-40"
)
NO_DA_PLACA = "alsa_output.pci-0000_0c_00.4.iec958-stereo"

VIVOS = {NO_VIVO, NO_DO_CABO, NO_DA_PLACA, NO_DA_PLACA + ".monitor"}


def _endpoint(fluxo: str, guid: str, estado: int, nome: str, *, carimbo: int = 1791398341) -> str:
    chave = f"{_RAIZ}\\\\{fluxo}\\\\{guid}"
    return (
        f"[{chave}] {carimbo}\n"
        "#time=1dd568b1f36bd5e\n"
        f'"DeviceState"=dword:{estado:08x}\n'
        "\n"
        f"[{chave}\\\\Properties] {carimbo}\n"
        "#time=1dd5688e7292660\n"
        f'"{{026e516e-b814-414b-83cd-856d6fef4822}},2"="{nome}"\n'
        '"{1da5d803-d492-4edd-8c23-e0c0ffee7f0e},0"=dword:00000001\n'
    )


def _sistema(*blocos: str) -> str:
    return (
        "WINE REGISTRY Version 2\n;; All keys relative to \\\\Machine\n\n#arch=win64\n\n"
        + "\n".join(blocos)
    )


def _ks_velho() -> str:
    inst = "USB\\\\VID_054C&PID_0CE6\\\\HEFESTOKS&003&028&0"
    return (
        f"[System\\\\ControlSet001\\\\Enum\\\\{inst}] 1789000000\n"
        '"Class"="USB"\n'
        '"ContainerId"="{0ce6054c-0003-001c-0000-000000000000}"\n'
    )


def _fora() -> str:
    return (
        f"[Software\\\\Fabricante\\\\Dispositivos\\\\{FORA}] 1780000000\n"
        '"DeviceState"=dword:00000004\n'
    )


SISTEMA = _sistema(
    _endpoint("Render", AUSENTE_1, 4, "Alto-falante antigo"),
    _endpoint("Render", AUSENTE_2, 4, "HDMI que saiu"),
    _endpoint("Capture", AUSENTE_3, 4, "Microfone que saiu"),
    _endpoint("Render", DUALSENSE_VIVO, 1, "DualSense Wireless Controller"),
    _endpoint("Render", PLACA, 1, "Áudio interno Estéreo"),
    _endpoint("Render", CASA_MORTO, 1, "Alto-falante do Controle 2"),
    _endpoint("Capture", CASA_MORTO_CAPTURA, 1, "Monitor do controle que saiu"),
    _endpoint("Render", CASA_VIVO, 1, "Alto-falante do Controle 1"),
    _fora(),
    _ks_velho(),
)


def _hex_do_guid(guid: str) -> str:
    return ",".join(f"{b:02x}" for b in uuid.UUID(guid).bytes_le)


def _mapa(fluxo: int, no: str, guid: str) -> str:
    return (
        f"[Software\\\\Wine\\\\Drivers\\\\winepulse.drv\\\\devices\\\\{fluxo},{no}] 1789956088\n"
        "#time=1dd496d1d224932\n"
        f'"guid"=hex:{_hex_do_guid(guid)}\n'
    )


def _usuario(*, padrao_saida: str = CASA_MORTO, padrao_entrada: str = DUALSENSE_VIVO) -> str:
    return (
        "WINE REGISTRY Version 2\n;; All keys relative to \\\\User\\\\S-1-5-21-0-0-0-1000\n\n"
        "#arch=win64\n\n"
        + "\n".join([
            "[Software\\\\Wine\\\\Drivers] 1789956088\n"
            f'"DefaultInput"="{{0.0.1.00000000}}.{padrao_entrada.lower()}"\n'
            f'"DefaultOutput"="{{0.0.0.00000000}}.{padrao_saida.lower()}"\n',
            _mapa(0, NO_DA_PLACA, PLACA),
            _mapa(0, NO_DO_CABO, DUALSENSE_VIVO),
            _mapa(0, NO_MORTO, CASA_MORTO),
            _mapa(1, MONITOR_MORTO, CASA_MORTO_CAPTURA),
            _mapa(0, NO_VIVO, CASA_VIVO),
        ])
    )


def _chaves(texto: str) -> list[str]:
    return [ks._cabecalho(b) for b in ks._blocos(texto)][1:]


def _com_guid(texto: str, guid: str) -> list[str]:
    return [c for c in _chaves(texto) if guid in c.upper()]


def _prefixo(tmp_path: Path, sistema: str = SISTEMA, usuario: str | None = None) -> Path:
    compat = tmp_path / "compatdata" / "1599660"
    (compat / "pfx").mkdir(parents=True)
    (compat / "pfx" / "system.reg").write_text(sistema, encoding="utf-8")
    (compat / "pfx" / "user.reg").write_text(
        _usuario() if usuario is None else usuario, encoding="utf-8")
    return compat


class TestAPodaTiraSoOQueNaoExisteMais:
    def test_os_ausentes_e_os_nos_mortos_da_casa_saem_com_o_mapa(self) -> None:
        poda = ks.podar_o_som(SISTEMA, _usuario(), VIVOS)
        for guid in (AUSENTE_1, AUSENTE_2, AUSENTE_3, CASA_MORTO, CASA_MORTO_CAPTURA):
            assert _com_guid(poda.sistema, guid) == [], guid
        assert poda.usuario is not None
        assert NO_MORTO not in poda.usuario and MONITOR_MORTO not in poda.usuario
        assert poda.podados == 5

    def test_os_vivos_a_placa_e_os_blocos_do_ks_ficam_byte_a_byte(self) -> None:
        poda = ks.podar_o_som(SISTEMA, _usuario(), VIVOS)
        for bloco in (
            _endpoint("Render", DUALSENSE_VIVO, 1, "DualSense Wireless Controller"),
            _endpoint("Render", PLACA, 1, "Áudio interno Estéreo"),
            _endpoint("Render", CASA_VIVO, 1, "Alto-falante do Controle 1"),
            _ks_velho(),
        ):
            assert bloco in poda.sistema
        assert poda.usuario is not None
        for fica in (_mapa(0, NO_DA_PLACA, PLACA), _mapa(0, NO_DO_CABO, DUALSENSE_VIVO),
                     _mapa(0, NO_VIVO, CASA_VIVO)):
            assert fica in poda.usuario

    def test_a_chave_fora_do_som_com_devicestate_4_fica(self) -> None:
        """MORDIDA: apague pelo `DeviceState` sem olhar o caminho, e a chave de fora sai."""
        poda = ks.podar_o_som(SISTEMA, _usuario(), VIVOS)
        assert _fora() in poda.sistema

    def test_o_no_vivo_da_casa_fica(self) -> None:
        """MORDIDA: pode sem a lista do `pactl`, e o nó vivo some do registro."""
        poda = ks.podar_o_som(SISTEMA, _usuario(), VIVOS)
        assert _com_guid(poda.sistema, CASA_VIVO)
        assert poda.usuario is not None and NO_VIVO in poda.usuario

    def test_os_nos_mortos_se_acham_pelo_mapa_do_user_reg(self) -> None:
        """MORDIDA: ignore o mapa do `user.reg`, e os dois nós mortos ficam no registro."""
        poda = ks.podar_o_som(SISTEMA, _usuario(), VIVOS)
        assert _com_guid(poda.sistema, CASA_MORTO) == []
        assert _com_guid(poda.sistema, CASA_MORTO_CAPTURA) == []

    def test_o_servidor_calado_poda_so_os_ausentes(self) -> None:
        """Não saber quem está vivo não é saber que morreu."""
        poda = ks.podar_o_som(SISTEMA, _usuario(), None)
        assert poda.podados == 3
        assert _com_guid(poda.sistema, CASA_MORTO) and _com_guid(poda.sistema, CASA_VIVO)
        assert poda.usuario == _usuario()

    def test_o_padrao_que_aponta_para_um_podado_sai_e_o_do_vivo_fica(self) -> None:
        poda = ks.podar_o_som(SISTEMA, _usuario(), VIVOS)
        assert poda.usuario is not None
        assert '"DefaultOutput"' not in poda.usuario
        assert f'"DefaultInput"="{{0.0.1.00000000}}.{DUALSENSE_VIVO.lower()}"' in poda.usuario

    def test_sem_nada_a_podar_os_dois_textos_voltam_iguais(self) -> None:
        sistema = _sistema(_endpoint("Render", PLACA, 1, "Áudio interno Estéreo"), _fora())
        usuario = _usuario(padrao_saida=PLACA)
        poda = ks.podar_o_som(sistema, usuario, VIVOS | {NO_MORTO, MONITOR_MORTO})
        assert (poda.sistema, poda.usuario, poda.podados) == (sistema, usuario, 0)


class TestOCuradorPodaComAsMesmasTravas:
    def test_o_lancamento_poda_os_dois_registros_com_backup(self, tmp_path: Path) -> None:
        compat = _prefixo(tmp_path)
        r = ks.aplicar(compat, controles=[], proc=tmp_path / "proc", carimbo=1,
                       podar=True, vivos=VIVOS)
        assert (r.escreveu, r.podados) == (True, 5)
        pfx = compat / "pfx"
        assert (pfx / "system.reg.bak.hefesto-audio-ks").read_text(encoding="utf-8") == SISTEMA
        assert (pfx / "user.reg.bak.hefesto-audio-ks").read_text(encoding="utf-8") == _usuario()
        usuario = (pfx / "user.reg").read_text(encoding="utf-8")
        assert NO_MORTO not in usuario and NO_VIVO in usuario
        sistema = (pfx / "system.reg").read_text(encoding="utf-8")
        assert _com_guid(sistema, AUSENTE_1) == [] and _com_guid(sistema, CASA_VIVO)

    def test_o_segundo_lancamento_nao_tem_o_que_podar(self, tmp_path: Path) -> None:
        compat = _prefixo(tmp_path)
        ks.aplicar(compat, controles=[], proc=tmp_path / "proc", carimbo=1,
                   podar=True, vivos=VIVOS)
        r = ks.aplicar(compat, controles=[], proc=tmp_path / "proc", carimbo=2,
                       podar=True, vivos=VIVOS)
        assert (r.escreveu, r.podados) == (False, 0)

    def test_com_o_wineserver_vivo_nada_se_escreve(self, tmp_path: Path) -> None:
        compat = _prefixo(tmp_path)
        proc = tmp_path / "proc" / "4242"
        proc.mkdir(parents=True)
        (proc / "comm").write_text("wineserver\n")
        (proc / "environ").write_bytes(f"WINEPREFIX={compat / 'pfx'}\0".encode())
        r = ks.aplicar(compat, controles=[], proc=tmp_path / "proc", carimbo=1,
                       podar=True, vivos=VIVOS)
        assert (r.motivo, r.escreveu, r.podados) == ("ocupado", False, 0)
        assert (compat / "pfx" / "system.reg").read_text(encoding="utf-8") == SISTEMA
        assert (compat / "pfx" / "user.reg").read_text(encoding="utf-8") == _usuario()
        assert not list((compat / "pfx").glob("*.bak.hefesto-audio-ks"))

    def test_sem_podar_o_registro_do_som_fica_como_estava(self, tmp_path: Path) -> None:
        """O uninstall e a carona do daemon chamam sem `podar`: só os blocos do KS mudam."""
        compat = _prefixo(tmp_path)
        r = ks.aplicar(compat, controles=[], proc=tmp_path / "proc", carimbo=1)
        assert r.podados == 0
        sistema = (compat / "pfx" / "system.reg").read_text(encoding="utf-8")
        assert _com_guid(sistema, AUSENTE_1)
        assert (compat / "pfx" / "user.reg").read_text(encoding="utf-8") == _usuario()

    def test_a_cli_do_lancamento_poda_e_diz_a_contagem(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        compat = _prefixo(tmp_path)
        monkeypatch.setattr(ks, "controles_do_registro", lambda *a, **k: [])
        monkeypatch.setattr(ks, "nos_vivos", lambda *a, **k: set(VIVOS))
        monkeypatch.setattr(ks, "wineserver_do_prefixo_vivo", lambda *a, **k: False)
        assert ks.main(["--prefixo", str(compat)]) == 0
        assert "podados=5" in capsys.readouterr().out

    def test_a_lista_dos_vivos_le_sinks_e_sources(self) -> None:
        respostas = {
            "sinks": f'[{{"index": 1, "name": "{NO_VIVO}"}}]',
            "sources": f'[{{"index": 2, "name": "{NO_VIVO}.monitor"}}]',
        }
        assert ks.nos_vivos(lambda argv: respostas[argv[-1]]) == {NO_VIVO, NO_VIVO + ".monitor"}
        assert ks.nos_vivos(lambda argv: None) is None


class TestOData4VelhoNaoMandaNoControleNovo:
    """O GE-Proton11-8 (0207) guarda os endpoints Sony; o par bus/dev se repete."""

    @staticmethod
    def _com_container(d4: bytes) -> str:
        g = (0x0CE6054C).to_bytes(4, "little") + (3).to_bytes(2, "little")
        g += (28).to_bytes(2, "little") + d4
        blob = ",".join(f"{b:02x}" for b in bytes.fromhex("4800efbe01000000") + g)
        chave = f"{_RAIZ}\\\\Render\\\\{DUALSENSE_VIVO}\\\\Properties"
        return (
            f"[{chave}] 1\n"
            f'"{{8c7ed206-3f8a-4827-b3ab-ae9e1faefc6c}},2"=hex:{blob}\n'
        )

    def test_a_entrada_velha_do_mesmo_par_nao_e_colhida(self) -> None:
        """MORDIDA: tire o filtro, e o Data4 do aparelho que saiu vira o do novo."""
        novo = ks.Controle(pid=0x0CE6, bus=3, dev=28, usec=222)
        texto = _sistema(self._com_container((111).to_bytes(8, "little")))
        assert ks.data4_do_dono(texto, novo) == []
        assert ks.variantes_de_data4(novo, ks.data4_do_dono(texto, novo)) == [
            bytes(8), (222).to_bytes(8, "little")]

    def test_a_entrada_do_proprio_controle_continua_mandando(self) -> None:
        novo = ks.Controle(pid=0x0CE6, bus=3, dev=28, usec=222)
        texto = _sistema(self._com_container((222).to_bytes(8, "little")))
        assert ks.data4_do_dono(texto, novo) == [(222).to_bytes(8, "little")]

    def test_o_container_em_texto_tambem_passa_pelo_filtro(self) -> None:
        novo = ks.Controle(pid=0x0CE6, bus=3, dev=28, usec=222)
        velho = ks.container_id(novo, (111).to_bytes(8, "little"))
        texto = _sistema(f'[System\\\\Velho] 1\n"ContainerId"="{velho}"\n')
        assert ks.data4_do_dono(texto, novo) == []

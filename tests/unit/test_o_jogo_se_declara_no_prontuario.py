"""O prontuário diz o que cada jogo declara sobre controle, com a fonte de cada linha."""
from __future__ import annotations

import struct
import subprocess
import sys
from pathlib import Path

import pytest

import hefesto_dualsense4unix as _pacote
from hefesto_dualsense4unix.integrations import ficha_declarada as fd
from hefesto_dualsense4unix.integrations.prontuario_dos_jogos import (
    _tabela,
    levantar_censo,
)

_DUALSENSE, _XBOX, _TRADUCAO, _SO_SUPORTE, _SEM_NADA = "1001", "1002", "1003", "1004", "1005"


def _kv(mapa: dict[str, object], chave: object) -> bytes:
    """O KeyValues binário da Steam: mapa (0x00), texto (0x01), inteiro (0x02), fim (0x08)."""
    saida = b""
    for nome, valor in mapa.items():
        if isinstance(valor, dict):
            saida += b"\x00" + chave(nome) + _kv(valor, chave)  # type: ignore[operator]
        elif isinstance(valor, int):
            saida += b"\x02" + chave(nome) + struct.pack("<i", valor)  # type: ignore[operator]
        else:
            saida += b"\x01" + chave(nome) + str(valor).encode() + b"\0"  # type: ignore[operator]
    return saida + b"\x08"


def _cache(apps: dict[str, dict[str, object]]) -> bytes:
    """Um `appcache` da Steam fabricado, no formato 29 (tabela de textos no fim)."""
    tabela: list[str] = []

    def chave(nome: str) -> bytes:
        if nome not in tabela:
            tabela.append(nome)
        return struct.pack("<I", tabela.index(nome))

    corpo = b""
    for appid, conteudo in apps.items():
        vdf = _kv({"appinfo": conteudo}, chave)
        cabecalho = struct.pack("<IIQ", 2, 0, 0) + b"\0" * 20 + struct.pack("<I", 1) + b"\0" * 20
        entrada = cabecalho + vdf
        corpo += struct.pack("<II", int(appid), len(entrada)) + entrada
    corpo += struct.pack("<I", 0)
    strings = struct.pack("<I", len(tabela)) + b"".join(s.encode() + b"\0" for s in tabela)
    return struct.pack("<IIq", 0x07564429, 1, 16 + len(corpo)) + corpo + strings


def _declaracoes() -> dict[str, dict[str, object]]:
    return {
        _DUALSENSE: {
            "common": {
                "controller_support": "full",
                "controllertagwizard": 1,
                "category": {"category_28": 1, "category_57": 1, "category_58": 1},
            }
        },
        _XBOX: {
            "common": {
                "controller_support": "full",
                "controllertagwizard": 1,
                "category": {"category_28": 1},
            }
        },
        _TRADUCAO: {
            "common": {"category": {"category_28": 1, "category_59": 1}},
            "config": {
                "steamcontrollerconfigdetails": {
                    "111": {"controller_type": "controller_ps5"},
                    "222": {"controller_type": "controller_neptune"},
                }
            },
        },
        _SO_SUPORTE: {"common": {"controller_support": "partial"}},
        _SEM_NADA: {"common": {"name": "Sem declaração"}},
    }


def _steam_de_mentira(home: Path, jogos: dict[str, dict[str, bytes]]) -> Path:
    """Uma Steam nativa com `appcache` e um executável por jogo."""
    raiz = home / ".steam/steam"
    (raiz / "config").mkdir(parents=True)
    (raiz / "appcache").mkdir()
    (raiz / "steam.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    (raiz / "appcache" / "appinfo.vdf").write_bytes(_cache(_declaracoes()))
    for appid, arquivos in jogos.items():
        pasta = raiz / "steamapps" / "common" / f"jogo{appid}"
        pasta.mkdir(parents=True)
        for nome, conteudo in arquivos.items():
            (pasta / nome).write_bytes(conteudo)
        (raiz / "steamapps" / f"appmanifest_{appid}.acf").write_text(
            f'"AppState"\n{{\n\t"appid"\t\t"{appid}"\n\t"name"\t\t"Jogo {appid}"\n'
            f'\t"installdir"\t\t"jogo{appid}"\n}}\n',
            encoding="utf-8",
        )
    return raiz


_VID = b"\x4c\x05"
_PID_0CE6 = b"\xe6\x0c"
_PID_0DF2 = b"\xf2\x0d"


class TestAsCategoriasDizemOVeredito:
    def test_os_tres_vereditos_saem_certos_com_a_fonte(self, tmp_path: Path) -> None:
        raiz = _steam_de_mentira(tmp_path, {})
        achadas = fd.declaracoes_do_cache(
            raiz / "appcache" / "appinfo.vdf",
            [_DUALSENSE, _XBOX, _TRADUCAO, _SO_SUPORTE, _SEM_NADA],
        )
        assert achadas is not None
        fichas = {a: fd.montar_ficha(a, d) for a, d in achadas.items()}

        assert fichas[_DUALSENSE].veredito == fd.ENTENDE_DUALSENSE
        assert "57" in fichas[_DUALSENSE].fontes[0]
        assert fichas[_XBOX].veredito == fd.SO_XBOX_DECLARADO
        assert "28" in fichas[_XBOX].fontes[0]
        assert fichas[_TRADUCAO].veredito == fd.PREVE_TRADUCAO
        assert any("59" in f for f in fichas[_TRADUCAO].fontes)
        assert any("controller_ps5" in f for f in fichas[_TRADUCAO].fontes)
        assert fichas[_SO_SUPORTE].veredito == fd.SO_XBOX_DECLARADO
        assert "controller_support" in fichas[_SO_SUPORTE].fontes[0]
        assert fichas[_SEM_NADA].veredito == fd.NAO_SEI
        assert fichas[_SEM_NADA].fontes == ()

    def test_o_layout_do_dualsense_sozinho_ja_preve_a_traducao(self, tmp_path: Path) -> None:
        decl = fd.DeclaracaoDaSteam(layouts=("controller_ps5",))
        assert fd.montar_ficha("1", decl).veredito == fd.PREVE_TRADUCAO
        outro = fd.DeclaracaoDaSteam(layouts=("controller_neptune", "controller_ps4"))
        assert fd.montar_ficha("1", outro).veredito == fd.NAO_SEI

    def test_a_declaracao_le_o_que_o_desenvolvedor_registrou(self, tmp_path: Path) -> None:
        raiz = _steam_de_mentira(tmp_path, {})
        achadas = fd.declaracoes_do_cache(
            raiz / "appcache" / "appinfo.vdf", [_TRADUCAO, _DUALSENSE]
        )
        assert achadas is not None
        assert achadas[_DUALSENSE].categorias == frozenset({28, 57, 58})
        assert achadas[_DUALSENSE].questionario_respondido
        assert achadas[_TRADUCAO].layouts == ("controller_neptune", "controller_ps5")
        assert not achadas[_TRADUCAO].questionario_respondido

    def test_cache_ilegivel_nao_inventa_declaracao(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        quebrado = tmp_path / "appinfo"
        quebrado.write_bytes(b"\x00" * 40)
        assert fd.declaracoes_do_cache(quebrado, ["1"]) is None
        cortado = tmp_path / "cortado"
        cortado.write_bytes(_cache(_declaracoes())[:12])
        with caplog.at_level("DEBUG", logger=fd.logger.name):
            assert fd.declaracoes_do_cache(cortado, ["1"]) is None
        assert "o cache da Steam não se leu" in caplog.text
        assert fd.declaracoes_do_cache(tmp_path / "nao-existe", ["1"]) is None


class TestOBinarioDiz:
    def test_a_biblioteca_sony_no_executavel_basta_sem_a_steam(self, tmp_path: Path) -> None:
        pasta = tmp_path / "jogo"
        pasta.mkdir()
        (pasta / "Jogo.exe").write_bytes(b"MZ" + b"\0" * 64 + b"WinDualShock" + b"\0" * 64)
        sinais = fd.examinar_o_binario(pasta)
        assert sinais.sony == ("WinDualShock",)
        ficha = fd.montar_ficha("1", None, sinais)
        assert ficha.veredito == fd.ENTENDE_DUALSENSE
        assert "WinDualShock" in ficha.fontes[0]

    def test_a_grafia_em_utf16_tambem_conta(self, tmp_path: Path) -> None:
        pasta = tmp_path / "jogo"
        pasta.mkdir()
        (pasta / "Jogo.exe").write_bytes(b"MZ" + "libscepad.dll".encode("utf-16-le") + b"\0" * 8)
        assert fd.examinar_o_binario(pasta).sony == ("libScePad",)

    def test_a_dll_da_sony_ao_lado_do_executavel_conta(self, tmp_path: Path) -> None:
        pasta = tmp_path / "jogo"
        (pasta / "retail").mkdir(parents=True)
        (pasta / "Jogo.exe").write_bytes(b"MZ" + b"\0" * 64)
        (pasta / "retail" / "libScePad.dll").write_bytes(b"MZ" + b"\0" * 64)
        sinais = fd.examinar_o_binario(pasta)
        assert "libScePad" in sinais.sony
        assert fd.montar_ficha("1", None, sinais).veredito == fd.ENTENDE_DUALSENSE

    def test_o_xinput_sozinho_nao_entende_nada(self, tmp_path: Path) -> None:
        pasta = tmp_path / "jogo"
        pasta.mkdir()
        (pasta / "Jogo.exe").write_bytes(b"MZ" + b"XINPUT1_4.dll" + b"\0" * 64)
        sinais = fd.examinar_o_binario(pasta)
        assert sinais.sony == ()
        assert fd.montar_ficha("1", None, sinais).veredito == fd.NAO_SEI

    def test_0ce6_sem_0df2_gera_o_aviso_e_os_dois_nao(self, tmp_path: Path) -> None:
        so_ce6 = tmp_path / "a"
        so_ce6.mkdir()
        (so_ce6 / "A.exe").write_bytes(b"MZ" + b"\0" * 9 + _VID + _PID_0CE6 + b"\0" * 20)
        ambos = tmp_path / "b"
        ambos.mkdir()
        (ambos / "B.exe").write_bytes(
            b"MZ" + _VID + _PID_0CE6 + b"\0" * 40 + _VID + _PID_0DF2 + b"\0" * 8
        )
        so_df2 = tmp_path / "c"
        so_df2.mkdir()
        (so_df2 / "C.exe").write_bytes(b"MZ" + b"\0" * 9 + _VID + _PID_0DF2 + b"\0" * 20)

        a = fd.montar_ficha("1", None, fd.examinar_o_binario(so_ce6))
        b = fd.montar_ficha("2", None, fd.examinar_o_binario(ambos))
        c = fd.montar_ficha("3", None, fd.examinar_o_binario(so_df2))
        assert a.binario.pids == ("0ce6",)
        assert len(a.avisos) == 1
        assert "0CE6" in a.avisos[0] and "0DF2" in a.avisos[0]
        assert b.binario.pids == ("0ce6", "0df2") and b.avisos == ()
        assert c.binario.pids == ("0df2",) and c.avisos == ()

    def test_o_vid_longe_do_pid_nao_conta(self, tmp_path: Path) -> None:
        pasta = tmp_path / "jogo"
        pasta.mkdir()
        (pasta / "Jogo.exe").write_bytes(b"MZ" + _VID + b"\0" * 64 + _PID_0CE6)
        assert fd.examinar_o_binario(pasta).pids == ()

    def test_o_manifesto_gdk_entra_na_ficha(self, tmp_path: Path) -> None:
        pasta = tmp_path / "jogo"
        pasta.mkdir()
        (pasta / "Jogo.exe").write_bytes(b"MZ")
        (pasta / "MicrosoftGame.config").write_text("<Game/>", encoding="utf-8")
        assert fd.examinar_o_binario(pasta).gdk


class TestOProntuarioMostraAFicha:
    def _censo(self, tmp_path: Path):  # type: ignore[no-untyped-def]
        casa = tmp_path / "casa"
        casa.mkdir()
        _steam_de_mentira(
            casa,
            {
                _DUALSENSE: {"Jogo.exe": b"MZ"},
                _XBOX: {"Jogo.exe": b"MZ"},
                _TRADUCAO: {"Jogo.exe": b"MZ"},
                _SO_SUPORTE: {
                    "Jogo.exe": b"MZ" + b"WinDualShock" + _VID + _PID_0CE6 + b"\0" * 8
                },
            },
        )
        return levantar_censo(casa, allowlist=[], pontes={})

    def test_cada_jogo_ganha_a_ficha_com_a_fonte(self, tmp_path: Path) -> None:
        por_appid = {j.appid: j for j in self._censo(tmp_path).jogos}
        vereditos = {a: j.declarado.veredito for a, j in por_appid.items() if j.declarado}
        assert vereditos == {
            _DUALSENSE: fd.ENTENDE_DUALSENSE,
            _XBOX: fd.SO_XBOX_DECLARADO,
            _TRADUCAO: fd.PREVE_TRADUCAO,
            _SO_SUPORTE: fd.ENTENDE_DUALSENSE,
        }
        saida = por_appid[_SO_SUPORTE].como_dicionario()
        assert saida["declarado"]["veredito"] == fd.ENTENDE_DUALSENSE
        assert saida["declarado"]["pids"] == ["0CE6"]

    def test_a_ficha_nao_mexe_no_veredito_de_impedimento(self, tmp_path: Path) -> None:
        for jogo in self._censo(tmp_path).jogos:
            sem_ficha = type(jogo)(**{**jogo.__dict__, "declarado": None})
            assert jogo.veredito == sem_ficha.veredito
            assert [e.chave for e in jogo.estorvos] == [e.chave for e in sem_ficha.estorvos]

    def test_a_varredura_rapida_le_a_steam_e_nao_o_binario(self, tmp_path: Path) -> None:
        casa = tmp_path / "casa"
        casa.mkdir()
        _steam_de_mentira(casa, {_SO_SUPORTE: {"Jogo.exe": b"MZ" + b"WinDualShock"}})
        (jogo,) = levantar_censo(casa, allowlist=[], pontes={}, examinar=False).jogos
        assert jogo.declarado is not None
        assert not jogo.declarado.binario.examinado
        assert jogo.declarado.veredito == fd.SO_XBOX_DECLARADO

    def test_a_tabela_mostra_a_ficha_e_o_aviso_do_modelo(self, tmp_path: Path) -> None:
        texto = _tabela(self._censo(tmp_path))
        assert "declara" in texto.splitlines()[0]
        assert "O que cada jogo declara sobre controle:" in texto
        assert "categoria 57" in texto
        assert "aviso: o executável conhece o modelo 0CE6" in texto


class TestACapaDaSteam:
    def _ficha(self, **campos: object) -> fd.FichaDeclarada:
        return fd.montar_ficha("1", fd.DeclaracaoDaSteam(**campos))  # type: ignore[arg-type]

    def test_sem_dualsense_declarado_e_com_o_steam_input_desligado_a_capa_se_explica(
        self,
    ) -> None:
        ficha = self._ficha(
            categorias=frozenset({18}), controller_support="partial", questionario_respondido=True
        )
        texto = fd.explicar_a_capa(ficha, steam_input_ligado=False, ps_support_global="0")
        assert texto is not None
        assert "Device Not Supported" in texto
        assert "não declarou DualSense" in texto
        assert "desligado pelo Hefesto" in texto

    def test_o_binario_sony_entra_na_explicacao(self) -> None:
        ficha = fd.montar_ficha(
            "1",
            fd.DeclaracaoDaSteam(
                categorias=frozenset({18}), controller_support="partial",
                questionario_respondido=True,
            ),
            fd.SinaisDoBinario(examinado=True, sony=("WinDualShock",)),
        )
        texto = fd.explicar_a_capa(ficha, steam_input_ligado=False, ps_support_global="0")
        assert texto is not None and "biblioteca Sony" in texto

    def test_jogo_que_declara_o_dualsense_nao_tem_o_que_explicar(self) -> None:
        ficha = self._ficha(
            categorias=frozenset({28, 57}), controller_support="full", questionario_respondido=True
        )
        assert fd.explicar_a_capa(ficha, steam_input_ligado=False, ps_support_global="0") is None

    def test_steam_input_ligado_tambem_nao(self) -> None:
        ficha = self._ficha(
            categorias=frozenset({28}), controller_support="full", questionario_respondido=True
        )
        assert fd.explicar_a_capa(ficha, steam_input_ligado=True, ps_support_global="0") is None

    def test_sem_questionario_a_capa_diz_desconhecido(self) -> None:
        ficha = self._ficha(categorias=frozenset({28}), controller_support="full")
        texto = fd.explicar_a_capa(ficha, steam_input_ligado=False, ps_support_global="0")
        assert texto is not None and "Unknown Controller Support" in texto

    def test_o_desligado_so_e_do_hefesto_quando_o_global_e_zero(self) -> None:
        ficha = self._ficha(
            categorias=frozenset({28}), controller_support="full", questionario_respondido=True
        )
        texto = fd.explicar_a_capa(ficha, steam_input_ligado=False, ps_support_global=None)
        assert texto is not None and "pelo Hefesto" not in texto


class TestAFichaNuncaTrocaAMascara:
    def test_a_mascara_efetiva_nao_importa_a_ficha(self) -> None:
        """A ficha informa a tela e a regra do toque; a máscara é escolha da pessoa."""
        raiz = Path(_pacote.__file__).resolve().parents[1]
        codigo = (
            "import sys\n"
            "import hefesto_dualsense4unix.daemon.subsystems.external_mask\n"
            "nomes = ('ficha_declarada', 'prontuario_dos_jogos')\n"
            "mods = [m for m in sys.modules if m.endswith(nomes)]\n"
            "print(mods)\n"
            "sys.exit(1 if mods else 0)\n"
        )
        rodou = subprocess.run(
            [sys.executable, "-c", codigo],
            env={"PYTHONPATH": str(raiz), "PATH": "/usr/bin:/bin"},
            capture_output=True,
            text=True,
            check=False,
        )
        assert rodou.returncode == 0, rodou.stdout + rodou.stderr
        fonte = (raiz / "hefesto_dualsense4unix/daemon/subsystems/external_mask.py").read_text(
            encoding="utf-8"
        )
        assert "ficha_declarada" not in fonte

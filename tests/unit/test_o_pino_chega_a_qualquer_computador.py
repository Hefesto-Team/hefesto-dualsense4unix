"""O PINO CHEGA A QUALQUER COMPUTADOR — INSTALL-UNIVERSAL, grupo C (18/09/2026).

A ordem dela, citada como ela escreveu:
*"garantir que o install que todas as correções que fizemos nos
ultimos dois dias possam seguir  <!-- noqa-acento: citação literal dela -->
e servir para cada computador não só o meu. ele precisa funcionar como
produto."*

Três lacunas do Proton pinado, confirmadas por auditor e cético, e cada uma
funcionava na máquina DELA por acaso de ordem:

1. **acdb2ea1b** — numa máquina SEM Steam nativa, o `--ensure` do install
   baixava 563 MB e criava `~/.steam/steam` como diretório real; o lançador
   Debian adota essa pasta como casa da Steam, e o produto inteiro passa a
   mirar uma raiz que a Steam não usa. Disco cheio e python sem `filter=` no
   tarfile saíam como *"checksum NÃO bateu"*.
2. **692cf5343** — a trava `--todos` só acontecia no 11c e só com a Steam
   fechada; o install reabria a Steam antes dele, e nada tentava de novo. O
   botão da aba Sistema travava sem `todos`. E "todo jogo" incluía título com
   versão Linux nativa.
3. **7b27bb58d** — a entrada ÓRFÃ só era alcançada pelo 11c, e uma órfã de
   jogo nativo voltava forçada no Proton.

NADA AQUI TOCA A MÁQUINA: todo HOME é `tmp_path`, a Steam é dublê, o download
é uma cópia local e o `appinfo.vdf` é fabricado byte a byte.
"""
from __future__ import annotations

import ast
import fcntl
import io
import os
import re
import struct
import subprocess
import sys
import tarfile
import threading
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import proton_pin as pp
from hefesto_dualsense4unix.integrations import steam_launch_options as slo

RAIZ = Path(__file__).resolve().parents[2]
INSTALL = (RAIZ / "install.sh").read_text(encoding="utf-8")
SERVICO = RAIZ / "assets" / "hefesto-steam-input-guard.service"
DOCTOR = RAIZ / "scripts" / "doctor.sh"

PINO = "GE-Proton11-7-x86_64"
_TAB = "\t"


# ---------------------------------------------------------------------------
# bancada
# ---------------------------------------------------------------------------
def _tarball(onde: Path, nome: str = PINO) -> Path:
    """Tarball mínimo com a forma do release (topo = <nome>/)."""
    src = onde / "tar-src" / nome
    src.mkdir(parents=True)
    (src / "proton").write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    (src / "version").write_text(f"1 {nome}\n", encoding="utf-8")
    tarball = onde / f"{nome}.tar.gz"
    with tarfile.open(tarball, "w:gz") as tar:
        tar.add(src, arcname=nome)
    return tarball


def _conf(tarball: Path, onde: Path) -> Path:
    conf = onde / "proton-pin.conf"
    conf.write_text(
        f"name={PINO}\nurl=https://exemplo.invalido/{PINO}.tar.gz\n"
        f"sha256={pp.sha256_of_file(tarball)}\n",
        encoding="utf-8",
    )
    return conf


def _config_vdf(entradas: dict[str, str] | None) -> str:
    ctm = ""
    if entradas is not None:
        blocos = "".join(
            f'{_TAB * 5}"{appid}"\n{_TAB * 5}{{\n'
            f'{_TAB * 6}"name"{_TAB * 2}"{nome}"\n'
            f'{_TAB * 6}"config"{_TAB * 2}""\n'
            f'{_TAB * 6}"priority"{_TAB * 2}"250"\n'
            f"{_TAB * 5}}}\n"
            for appid, nome in entradas.items()
        )
        ctm = f'{_TAB * 4}"CompatToolMapping"\n{_TAB * 4}{{\n{blocos}{_TAB * 4}}}\n'
    return (
        '"InstallConfigStore"\n{\n'
        f'{_TAB}"Software"\n{_TAB}{{\n'
        f'{_TAB * 2}"Valve"\n{_TAB * 2}{{\n'
        f'{_TAB * 3}"Steam"\n{_TAB * 3}{{\n'
        f"{ctm}"
        f"{_TAB * 3}}}\n{_TAB * 2}}}\n{_TAB}}}\n}}\n"
    )


def _appinfo(apps: dict[str, str | None], formato: int = 29) -> bytes:
    """Um `appcache/appinfo.vdf` fabricado no formato binário da Steam.

    `None` = o app está no cache mas não declara `oslist`. A v29 guarda as
    chaves numa tabela de strings no fim; a v28, inline.
    """
    tabela: list[str] = []

    def chave(nome: str) -> bytes:
        if formato == 28:
            return nome.encode() + b"\0"
        if nome not in tabela:
            tabela.append(nome)
        return struct.pack("<I", tabela.index(nome))

    corpo = b""
    for appid, oslist in apps.items():
        comum = b"\x01" + chave("name") + b"Um Jogo\0"
        if oslist is not None:
            comum += b"\x01" + chave("oslist") + oslist.encode() + b"\0"
        vdf = (
            b"\x00" + chave("appinfo")
            + b"\x02" + chave("appid") + struct.pack("<i", int(appid))
            + b"\x00" + chave("common") + comum + b"\x08"
            + b"\x08" + b"\x08"
        )
        cabecalho = struct.pack("<IIQ", 2, 0, 0) + b"\0" * 20 + struct.pack("<I", 1) + b"\0" * 20
        entrada = cabecalho + vdf
        corpo += struct.pack("<II", int(appid), len(entrada)) + entrada
    corpo += struct.pack("<I", 0)
    magia = 0x07564429 if formato == 29 else 0x07564428
    if formato == 28:
        return struct.pack("<II", magia, 1) + corpo
    inicio = 16
    fim_do_corpo = inicio + len(corpo)
    strings = struct.pack("<I", len(tabela)) + b"".join(s.encode() + b"\0" for s in tabela)
    return struct.pack("<IIq", magia, 1, fim_do_corpo) + corpo + strings


def _steam_de_verdade(home: Path) -> Path:
    """Uma Steam nativa com a cara que a Steam deixa: `steam.sh` e `config.vdf`."""
    raiz = home / ".steam/steam"
    (raiz / "config").mkdir(parents=True)
    (raiz / "steamapps").mkdir(parents=True)
    (raiz / "steam.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    (raiz / "config" / "config.vdf").write_text(_config_vdf(None), encoding="utf-8")
    return raiz


def _jogo(raiz: Path, appid: str, nome: str = "Um Jogo") -> None:
    (raiz / "steamapps" / f"appmanifest_{appid}.acf").write_text(
        f'"AppState"\n{{\n\t"appid"\t\t"{appid}"\n\t"name"\t\t"{nome}"\n}}\n',
        encoding="utf-8",
    )


def _pino_na(raiz: Path, nome: str = PINO) -> Path:
    """O pino INSTALADO na Steam: é o que `pinned_proton_installed` confere."""
    pino = raiz / "compatibilitytools.d" / nome
    pino.mkdir(parents=True)
    (pino / "proton").write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    (pino / "version").write_text(f"1 {nome}\n", encoding="utf-8")
    return pino


@pytest.fixture()
def lar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """HOME e os XDG presos ao tmp; a Steam e o jogo, dublês fechados."""
    casa = tmp_path / "lar"
    casa.mkdir()
    monkeypatch.setenv("HOME", str(casa))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(casa / ".config"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(casa / ".cache"))
    monkeypatch.setenv("XDG_STATE_HOME", str(casa / ".local/state"))
    monkeypatch.setattr(pp, "steam_running", lambda: False)
    monkeypatch.setattr(pp, "steam_game_running", lambda: False)
    return casa


@pytest.fixture()
def download_local(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    """O `curl` do `--ensure` vira uma cópia local, e conta quantas vezes rodou."""
    tarball = _tarball(tmp_path / "release")
    estado = {"baixou": 0, "tarball": tarball, "conf": _conf(tarball, tmp_path)}

    def _baixar(_url: str, destino: Path) -> None:
        estado["baixou"] += 1
        destino.write_bytes(tarball.read_bytes())

    monkeypatch.setattr(pp, "curl_downloader", _baixar)
    return estado


# ---------------------------------------------------------------------------
# 1 — acdb2ea1b: sem Steam nativa, o `--ensure` não cria a casa da Steam
# ---------------------------------------------------------------------------
class TestSemSteamOEnsureNaoEnvenena:
    def test_sem_steam_baixa_so_para_o_cache_e_nao_cria_a_raiz(
        self, lar: Path, download_local: dict, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A LACUNA CENTRAL. MORDIDA: tire a consulta a `steam_root_ou_recusa`
        do `_cmd_ensure`. A segunda muralha (a extração não cria a raiz) ainda
        seguraria o `~/.steam` — e é por isso que a régua cobra também o CAMINHO:
        sem Steam, o ensure nem chega a tentar extrair."""
        cache = lar / ".cache/hefesto-dualsense4unix/proton"
        rc = pp.main(["--ensure", "--conf", str(download_local["conf"]),
                      "--cache-dir", str(cache)])

        saida = capsys.readouterr().out
        assert rc == pp.RC_ADIADO
        assert not (lar / ".steam").exists(), "o ensure criou a casa da Steam"
        assert (cache / f"{PINO}.tar.gz").is_file(), "o download não foi adiantado"
        assert download_local["baixou"] == 1
        assert f"{PINO}: em_cache" in saida, saida
        assert "pino adiado até a Steam nativa existir" in saida, saida

    def test_steam_na_caixa_nao_baixa_nada(
        self, lar: Path, download_local: dict
    ) -> None:
        """Flatpak/Snap: o Proton do host nunca serve lá dentro — 563 MB à toa.

        E o código é PRÓPRIO (7), não o 4 do tarball no cache: o install lê o 4
        prometendo que o vigia extrai do cache, e aqui não há cache nenhum.
        MORDIDA: devolva o `RC_ADIADO` a este ramo do `_cmd_ensure`.
        """
        (lar / ".var/app/com.valvesoftware.Steam/.steam/steam").mkdir(parents=True)
        cache = lar / "cache"
        rc = pp.main(["--ensure", "--conf", str(download_local["conf"]),
                      "--cache-dir", str(cache)])

        assert rc == pp.RC_STEAM_NA_CAIXA
        assert download_local["baixou"] == 0
        assert not (lar / ".steam").exists()

    def test_com_steam_nativa_extrai_como_sempre(
        self, lar: Path, download_local: dict
    ) -> None:
        """O NEGATIVO: onde há Steam, o pino chega — nada foi perdido."""
        raiz = _steam_de_verdade(lar)
        rc = pp.main(["--ensure", "--conf", str(download_local["conf"]),
                      "--cache-dir", str(lar / "cache")])

        assert rc == 0
        assert pp.pinned_proton_installed(PINO, raiz / "compatibilitytools.d")

    def test_a_sobra_nossa_nao_conta_como_steam(self, lar: Path) -> None:
        """`~/.steam/steam` só com o nosso `compatibilitytools.d` não é Steam."""
        sobra = lar / ".steam/steam/compatibilitytools.d" / PINO
        sobra.mkdir(parents=True)
        (sobra / pp.MANIFEST_BASENAME).write_text(
            '{"installed_by": "hefesto-dualsense4unix"}', encoding="utf-8"
        )

        raiz, motivo = pp.steam_root_ou_recusa(lar)
        assert raiz is None and motivo
        assert pp.raiz_envenenada(lar) == lar / ".steam/steam"

    def test_a_maquina_ja_envenenada_ouve_o_gesto_no_install(
        self, lar: Path, download_local: dict, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Reinstalar não tira a sobra; o install passa a DIZER onde ela está.

        MORDIDA: tire o `_avisar_da_raiz_envenenada()` do `_cmd_ensure`.
        """
        sobra = lar / ".steam/steam/compatibilitytools.d" / PINO
        sobra.mkdir(parents=True)
        (sobra / pp.MANIFEST_BASENAME).write_text(
            '{"installed_by": "hefesto-dualsense4unix"}', encoding="utf-8"
        )
        pp.main(["--ensure", "--conf", str(download_local["conf"]),
                 "--cache-dir", str(lar / "cache")])

        saida = capsys.readouterr().out
        assert "sobra de um instalador antigo" in saida, saida
        assert ".sobra-do-hefesto" in saida, saida

    def test_raiz_com_coisa_que_nao_e_nossa_nao_e_acusada(self, lar: Path) -> None:
        """A régua da raiz envenenada é estreita: o que não é nosso, ela não acusa."""
        alheio = lar / ".steam/steam/compatibilitytools.d/Proton-de-outro"
        alheio.mkdir(parents=True)
        assert pp.raiz_envenenada(lar) is None

    def test_a_steam_de_verdade_vence_a_sobra(self, lar: Path) -> None:
        """Sobra em `~/.steam/steam`, Steam em `~/.local/share/Steam`: vale a segunda."""
        (lar / ".steam/steam/compatibilitytools.d").mkdir(parents=True)
        antiga = lar / ".local/share/Steam"
        (antiga / "steamapps").mkdir(parents=True)
        (antiga / "steam.sh").write_text("", encoding="utf-8")

        assert pp.default_steam_root(lar) == antiga
        assert pp.steam_root_ou_recusa(lar).raiz == antiga


class TestAExtracaoNuncaCriaARaiz:
    def test_sem_a_raiz_o_ensure_adia_e_guarda_o_tarball(self, tmp_path: Path) -> None:
        """A segunda muralha: `parents=True` saiu. MORDIDA: devolva-o."""
        tarball = _tarball(tmp_path)
        conf = {"name": PINO, "url": "x", "sha256": pp.sha256_of_file(tarball)}
        cache = tmp_path / "cache"
        cache.mkdir()
        (cache / f"{PINO}.tar.gz").write_bytes(tarball.read_bytes())
        compat = tmp_path / "nao-existe" / "compatibilitytools.d"

        r = pp.ensure_pinned_proton(conf, compat_dir=compat, cache_dir=cache)

        assert r.state == "adiado", r
        assert not compat.parent.exists()
        assert (cache / f"{PINO}.tar.gz").is_file()

    def test_quem_chama_a_extracao_direto_tambem_nao_cria_a_raiz(
        self, tmp_path: Path
    ) -> None:
        """A muralha mora NA função, não só no ensure. MORDIDA: devolva o
        `mkdir(parents=True)` e tire o `FileNotFoundError` da extração."""
        compat = tmp_path / "nao-existe" / "compatibilitytools.d"
        with pytest.raises(FileNotFoundError):
            pp._extract_verified_tarball(_tarball(tmp_path), PINO, compat)
        assert not compat.parent.exists()


def _python_sem_filtro(monkeypatch: pytest.MonkeyPatch) -> None:
    """O python anterior ao 3.10.12/3.11.4: sem `data_filter`, e o
    `extractall(filter=)` é TypeError. O dublê extrai como aquele python
    extraía — sem filtro nenhum."""
    monkeypatch.delattr(tarfile, "data_filter", raising=False)
    original = tarfile.TarFile.extractall

    def _extractall_antigo(self, path=".", members=None, *, numeric_owner=False, **kw):
        if "filter" in kw:
            raise TypeError("extractall() got an unexpected keyword argument 'filter'")
        return original(self, path, members, numeric_owner=numeric_owner,
                        filter="fully_trusted")

    monkeypatch.setattr(tarfile.TarFile, "extractall", _extractall_antigo)


class TestOQueNaoEChecksumNaoSeDizChecksum:
    def test_disco_cheio_e_extracao_falhou_e_nao_checksum(
        self, lar: Path, download_local: dict, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """MORDIDA: tire o `except (OSError, tarfile.TarError)` do ensure."""
        _steam_de_verdade(lar)

        def _cheio(*_a: object) -> None:
            raise OSError(28, "No space left on device")

        monkeypatch.setattr(pp, "_extract_verified_tarball", _cheio)
        rc = pp.main(["--ensure", "--conf", str(download_local["conf"]),
                      "--cache-dir", str(lar / "cache")])

        assert rc == pp.RC_EXTRACAO_FALHOU
        assert rc != pp.RC_CHECKSUM
        # E o estado vem do ensure, não do `except OSError` de reserva do main:
        # quem chama a função (o `--manter`, a GUI) também lê o desfecho certo.
        conf = pp.parse_pin_conf(download_local["conf"].read_text(encoding="utf-8"))
        r = pp.ensure_pinned_proton(
            conf, compat_dir=lar / ".steam/steam/compatibilitytools.d",
            cache_dir=lar / "cache",
        )
        assert r.state == "extracao_falhou", r

    def test_python_sem_filter_no_tarfile_extrai(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Python anterior ao 3.10.12/3.11.4: `extractall(filter=)` é TypeError.

        O dublê reproduz esse python: tira `tarfile.data_filter` e faz o
        `extractall` recusar o argumento. MORDIDA: tire o `hasattr` da extração.
        """
        _python_sem_filtro(monkeypatch)
        tarball = _tarball(tmp_path)
        compat = tmp_path / "compat"

        pp._extract_verified_tarball(tarball, PINO, compat)

        assert pp.pinned_proton_installed(PINO, compat)

    def test_sem_filtro_o_nome_que_foge_do_destino_e_recusado(
        self, tmp_path: Path
    ) -> None:
        """A barreira que o filtro "tar" dava, conferida à mão."""
        ruim = tmp_path / "ruim.tar.gz"
        with tarfile.open(ruim, "w:gz") as tar:
            info = tarfile.TarInfo("../fora.txt")
            info.size = 0
            tar.addfile(info, io.BytesIO(b""))
        with tarfile.open(ruim, "r:gz") as tar, pytest.raises(tarfile.TarError):
            pp._conferir_nomes_do_tar(tar)

    def test_sem_filtro_a_extracao_confere_e_nada_sai_do_destino(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A régua de cima chama a conferência direto; esta prova que a
        extração a chama. MORDIDA: tire o `_conferir_nomes_do_tar(tar)` de
        `_extract_verified_tarball` — o `../fora.txt` cai ao lado do pino."""
        _python_sem_filtro(monkeypatch)
        ruim = tmp_path / "ruim.tar.gz"
        with tarfile.open(ruim, "w:gz") as tar:
            info = tarfile.TarInfo("../fora.txt")
            info.size = 4
            tar.addfile(info, io.BytesIO(b"fora"))
        compat = tmp_path / "steam" / "compatibilitytools.d"
        compat.parent.mkdir()

        with pytest.raises(tarfile.TarError):
            pp._extract_verified_tarball(ruim, PINO, compat)

        assert not (compat / "fora.txt").exists(), "o tar escreveu fora do destino"
        assert list(compat.iterdir()) == []

    @pytest.mark.parametrize(
        ("tipo", "alvo"),
        [(tarfile.SYMTYPE, "/etc/passwd"), (tarfile.SYMTYPE, "../../../fora"),
         (tarfile.LNKTYPE, "../fora")],
        ids=["simbolico-absoluto", "simbolico-que-sobe-demais", "fisico-que-sobe"],
    )
    def test_sem_filtro_o_link_que_aponta_para_fora_e_recusado(
        self, tmp_path: Path, tipo: bytes, alvo: str
    ) -> None:
        """A outra metade do filtro "tar": o nome é inocente, o alvo não.
        MORDIDA: tire a conferência do `linkname`."""
        ruim = tmp_path / "ruim.tar.gz"
        with tarfile.open(ruim, "w:gz") as tar:
            info = tarfile.TarInfo(f"{PINO}/files/um-link")
            info.type = tipo
            info.linkname = alvo
            tar.addfile(info)
        with tarfile.open(ruim, "r:gz") as tar, pytest.raises(tarfile.TarError, match="link"):
            pp._conferir_nomes_do_tar(tar)

    def test_sem_filtro_o_link_interno_que_sobe_cinco_niveis_passa(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O NEGATIVO, e ele é o GE-Proton de verdade: o `start.exe` do
        `default_pfx` sobe cinco níveis e cai dentro de `files/lib/wine/`.
        Recusar todo `..` no alvo quebraria a extração no python antigo.
        MORDIDA: troque a conta pela pasta do link por `'..' in parts`."""
        _python_sem_filtro(monkeypatch)
        tarball = tmp_path / "ge.tar.gz"
        pfx = f"{PINO}/files/share/default_pfx/drive_c/windows/system32"
        with tarfile.open(tarball, "w:gz") as tar:
            for nome, dado in ((f"{PINO}/proton", b"#!/bin/sh\n"),
                               (f"{PINO}/version", b"1\n"),
                               (f"{PINO}/files/lib/wine/start.exe", b"MZ")):
                info = tarfile.TarInfo(nome)
                info.size = len(dado)
                tar.addfile(info, io.BytesIO(dado))
            link = tarfile.TarInfo(f"{pfx}/start.exe")
            link.type = tarfile.SYMTYPE
            link.linkname = "../../../../../lib/wine/start.exe"
            tar.addfile(link)
        compat = tmp_path / "steam" / "compatibilitytools.d"
        compat.parent.mkdir()

        pp._extract_verified_tarball(tarball, PINO, compat)

        extraido = compat / pfx / "start.exe"
        assert extraido.is_symlink()
        assert extraido.resolve() == (compat / PINO / "files/lib/wine/start.exe").resolve()


# ---------------------------------------------------------------------------
# 1b — o install e o doctor falam a língua nova
# ---------------------------------------------------------------------------
def _bloco(inicio: str, fim: str) -> str:
    return INSTALL[INSTALL.index(inicio): INSTALL.index(fim, INSTALL.index(inicio))]


class TestOInstallLeCadaCodigo:
    def test_rc_4_e_5_tem_frase_propria_e_o_1_e_so_checksum(self) -> None:
        bloco = _bloco('step "11a"', 'step "11a-bis"')
        assert re.search(r"^\s+4\)\s*$", bloco, re.M), "o rc 4 (adiado) não tem ramo"
        assert re.search(r"^\s+5\)\s*$", bloco, re.M), "o rc 5 (extração) não tem ramo"
        ramo_1 = bloco[bloco.index("        1)"): bloco.index("        2)")]
        assert "checksum" in ramo_1

    def test_o_rc_7_da_caixa_nao_promete_o_vigia(self) -> None:
        """O `4` diz que o vigia extrai do cache; na caixa não há cache."""
        bloco = _bloco('step "11a"', 'step "11a-bis"')
        ramo_7 = bloco[bloco.index("        7)"):]
        ramo_7 = ramo_7[: ramo_7.index(";;")]
        assert "nada foi baixado" in ramo_7, ramo_7
        assert "vigia" not in ramo_7, ramo_7
        ramo_4 = bloco[bloco.index("        4)"): bloco.index("        5)")]
        assert "vigia da Steam extrai do cache" in ramo_4

    def test_a_trava_do_11c_so_roda_com_o_pino_pronto(self) -> None:
        """A guarda do install (B9 do validador), com régua agora.

        MORDIDA: tire o ramo `elif [[ "${_pp_pronto}" -ne 1 ]]` do 11c, ou
        ponha o `_pp_pronto=1` em outro ramo do 11a que não o `0)`.
        """
        bloco = _bloco('step "11c"', 'step "11d"')
        guarda = bloco.index('elif [[ "${_pp_pronto}" -ne 1 ]]; then')
        trava = bloco.index('python3 "${PROTON_PIN_PY}" --lock --todos || _pl_rc=$?')
        assert guarda < trava
        bloco_a = _bloco('step "11a"', 'step "11a-bis"')
        assert bloco_a.count("_pp_pronto=1") == 1
        assert "_pp_pronto=1" in bloco_a[bloco_a.index("        0)"): bloco_a.index("        1)")]

    def test_o_vigia_estaciona_durante_a_janela_e_volta_no_fim(self) -> None:
        """O vigia escreve os MESMOS arquivos que o 11 ao 11c, pelo mesmo
        `.hefesto-tmp`: rodando junto, um perde a edição do outro.

        MORDIDA: tire o `stop` do 11a-bis, devolva o `enable --now` ao 11, ou
        tire a chamada que o religa depois do 11d.
        """
        unidades = "hefesto-steam-input-guard.path hefesto-steam-input-guard.timer"
        assert f"enable --now {unidades}" not in INSTALL
        ordem = [
            f"systemctl --user stop {unidades}",
            'python3 "${LAUNCH_MIGRATE_PY}" --fechar-steam',
            'step "11/11"',
            f"systemctl --user enable {unidades}",
            'step "11b"', 'step "11c"', 'step "11d"',
            "\n_religar_o_vigia_se_o_install_parou\n",
        ]
        posicoes = [INSTALL.index(marco) for marco in ordem]
        assert posicoes == sorted(posicoes), list(zip(ordem, posicoes, strict=True))
        corpo = INSTALL[INSTALL.index("_religar_o_vigia_se_o_install_parou() {"):]
        corpo = corpo[: corpo.index("\n}\n")]
        assert f"systemctl --user start {unidades}" in corpo, corpo

    def test_o_conselho_de_falha_da_trava_pede_todos(self) -> None:
        """install.sh:4055 dizia `--lock` sem `--todos`."""
        bloco = _bloco('step "11c"', "Conferência final")
        for linha in bloco.splitlines():
            if "rode manualmente" in linha:
                assert "--lock --todos" in linha, linha

    def test_a_ordem_baixa_fecha_uma_vez_edita_trava_e_reabre(self) -> None:
        """692cf5343 (c): o download ANTES da janela, a trava DENTRO dela."""
        ordem = [
            'step "11a"',
            '_pp_saida="$(python3 "${PROTON_PIN_PY}" --ensure 2>&1)"',
            'step "11a-bis"',
            'python3 "${LAUNCH_MIGRATE_PY}" --fechar-steam',
            'step "11/11"', 'step "11b"', 'step "11b-bis"', 'step "11b-ter"',
            'step "11c"',
            'python3 "${PROTON_PIN_PY}" --lock --todos || _pl_rc=$?',
            'step "11d"',
        ]
        posicoes = [INSTALL.index(marco) for marco in ordem]
        assert posicoes == sorted(posicoes), list(zip(ordem, posicoes, strict=True))

    def test_a_steam_fechada_pelo_install_reabre_mesmo_se_ele_morrer(self) -> None:
        bloco = _bloco('step "11a-bis"', "# 11. Steam Input")
        assert (
            "trap '_cleanup_sudo_keepalive; _reabrir_a_steam_se_o_install_fechou; "
            "_religar_o_vigia_se_o_install_parou' EXIT"
        ) in bloco


def test_steam_que_nunca_entrou_numa_conta_adia_e_nao_falha(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Máquina recém-montada: Steam instalada, sem `config.vdf` ainda.

    O install dizia *"trava do Proton falhou"*. MORDIDA: tire o ramo do
    `config_vdf_ausente` de `_travar_e_contar` e isto volta a 1.
    """
    monkeypatch.setattr(pp, "steam_running", lambda: False)
    monkeypatch.setattr(pp, "steam_game_running", lambda: False)
    tarball = _tarball(tmp_path)
    rc = pp.main(["--lock", "--todos", "--conf", str(_conf(tarball, tmp_path)),
                  "--config-vdf", str(tmp_path / "nao-existe" / "config.vdf"),
                  "--appids", "42"])
    assert rc == pp.RC_ADIADO
    assert 'elif [[ "${_pl_rc}" -eq 4 ]]' in INSTALL


class TestOFecharSteamDizOQueFez:
    """O par `--fechar-steam`/`--reabrir-steam` do `steam_launch_options`."""

    def test_aberta_fecha_e_devolve_0(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fechou: list[bool] = []
        monkeypatch.setattr(slo, "steam_game_running", lambda: False)
        monkeypatch.setattr(slo, "steam_running", lambda: True)
        monkeypatch.setattr(slo, "stop_steam", lambda: fechou.append(True) or True)
        assert slo.main(["--fechar-steam"]) == slo.RC_STEAM_FECHADA_AGORA
        assert fechou == [True]

    def test_ja_fechada_nao_pede_reabrir(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(slo, "steam_game_running", lambda: False)
        monkeypatch.setattr(slo, "steam_running", lambda: False)
        monkeypatch.setattr(slo, "stop_steam", lambda: pytest.fail("fechou à toa"))
        assert slo.main(["--fechar-steam"]) == slo.RC_STEAM_JA_FECHADA

    def test_com_jogo_aberto_nada_e_fechado(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(slo, "steam_game_running", lambda: True)
        monkeypatch.setattr(slo, "steam_running", lambda: True)
        monkeypatch.setattr(slo, "stop_steam", lambda: pytest.fail("mataria o jogo"))
        assert slo.main(["--fechar-steam"]) == slo.RC_STEAM_NAO_FECHOU


# ---------------------------------------------------------------------------
# 2 — 692cf5343: o vigia trava quando a Steam sai, e "todo jogo" tem classe
# ---------------------------------------------------------------------------
class TestOVigiaTravaSozinho:
    def _execstarts(self) -> list[str]:
        return [
            linha.split("=", 1)[1].strip()
            for linha in SERVICO.read_text(encoding="utf-8").splitlines()
            if linha.startswith("ExecStart=")
        ]

    def test_o_terceiro_passo_do_vigia_e_o_manter(self) -> None:
        """MORDIDA: tire a linha do `--manter` da unidade."""
        execs = self._execstarts()
        assert len(execs) == 3, execs
        assert execs[2] == "-/usr/bin/env python3 __PROTON_PIN__ --manter"

    def test_o_install_substitui_o_placeholder(self) -> None:
        assert "s#__PROTON_PIN__#${PROTON_PIN_PY}#g" in INSTALL
        # E o caminho já existe quando o passo 11 renderiza a unidade.
        assert INSTALL.index('PROTON_PIN_PY="${ROOT_DIR}') < INSTALL.index("s#__PROTON_PIN__#")

    def test_com_no_proton_pin_so_a_linha_do_pino_sai(self) -> None:
        """A pessoa disse não ao pino: o vigia não pode desdizer a cada meia hora."""
        assert "'/^ExecStart=.*__PROTON_PIN__/d'" in INSTALL
        r = subprocess.run(
            ["sed", "-e", "/^ExecStart=.*__PROTON_PIN__/d", str(SERVICO)],
            capture_output=True, text=True, check=True, timeout=30,
        )
        execs = [ln for ln in r.stdout.splitlines() if ln.startswith("ExecStart=")]
        assert len(execs) == 2 and all("__PROTON_PIN__" not in e for e in execs), execs

    def test_com_keep_steam_input_so_a_linha_do_steam_input_sai(self) -> None:
        """`--keep-steam-input` é opt-out SÓ do PSSupport: o atalho e o pino
        continuam sendo repostos. MORDIDA: tire o `__SCRIPT__/d` do install."""
        assert "'/^ExecStart=.*__SCRIPT__/d'" in INSTALL

        def _execs(*apagar: str) -> list[str]:
            args = [a for linha in apagar for a in ("-e", linha)]
            r = subprocess.run(["sed", *args, str(SERVICO)], capture_output=True,
                               text=True, check=True, timeout=30)
            return [ln for ln in r.stdout.splitlines() if ln.startswith("ExecStart=")]

        so_si = _execs("/^ExecStart=.*__SCRIPT__/d")
        assert len(so_si) == 2 and "__SENTINELA__" in so_si[0], so_si
        assert so_si[1].endswith("__PROTON_PIN__ --manter"), so_si
        os_dois = _execs("/^ExecStart=.*__SCRIPT__/d", "/^ExecStart=.*__PROTON_PIN__/d")
        assert len(os_dois) == 1 and "__SENTINELA__" in os_dois[0], os_dois

    @pytest.mark.parametrize(
        ("keep", "no_pin", "esperado"),
        [(0, 0, 3), (1, 0, 2), (0, 1, 2), (1, 1, 1)],
        ids=["padrão", "keep-steam-input", "no-proton-pin", "os-dois"],
    )
    def test_o_trecho_do_install_renderiza_a_unidade_de_cada_escolha(
        self, tmp_path: Path, keep: int, no_pin: int, esperado: int
    ) -> None:
        """Roda em bash o TRECHO REAL do install, de `_guard_linhas_que_saem=()`
        ao `rm` do temporário, e conta os `ExecStart` da unidade que sai.

        Com o vigia fora do `else` do opt-out, a segurança de quem usa
        `--keep-steam-input` passou a depender de um condicional — antes vinha
        da estrutura: a unidade nem era instalada. As réguas vizinhas só
        conferem que a expressão `sed` EXISTE no install. MORDIDA, nos dois
        sentidos: troque o condicional do `__SCRIPT__/d` por `[[ 0 -eq 1 ]]`
        (o vigia desliga o Steam Input de quem disse não, a cada meia hora) e
        por `true` (toda instalação padrão perde o self-heal do Steam Input).
        """
        inicio = INSTALL.index("    _guard_linhas_que_saem=()\n")
        fim = INSTALL.index('    rm -f "${_guard_tmp}"\n', inicio)
        trecho = INSTALL[inicio:fim] + '    rm -f "${_guard_tmp}"\n'
        unidades = tmp_path / "unidades"
        roteiro = tmp_path / "trecho.sh"
        roteiro.write_text(
            "set -euo pipefail\n"
            "warn() { printf 'WARN %s\\n' \"$*\"; }\n"
            "_guard_ok=1\n" + trecho, encoding="utf-8")
        r = subprocess.run(
            ["bash", str(roteiro)], capture_output=True, text=True, timeout=30,
            check=False, cwd=tmp_path,
            env={"PATH": "/usr/bin:/bin", "ROOT_DIR": str(RAIZ),
                 "USER_UNIT_DIR": str(unidades),
                 "SENTINELA_PY": "/x/sentinela_do_wrapper.py",
                 "PROTON_PIN_PY": "/x/proton_pin.py",
                 "KEEP_STEAM_INPUT": str(keep), "NO_PROTON_PIN": str(no_pin)},
        )
        assert r.returncode == 0, r.stdout + r.stderr

        unidade = (unidades / "hefesto-steam-input-guard.service").read_text(encoding="utf-8")
        execs = [ln for ln in unidade.splitlines() if ln.startswith("ExecStart=")]
        assert len(execs) == esperado, execs
        assert any("disable_steam_input.sh" in e for e in execs) is (keep == 0), execs
        assert any("proton_pin.py --manter" in e for e in execs) is (no_pin == 0), execs
        assert any("sentinela_do_wrapper.py" in e for e in execs), execs
        assert not any(re.search(r"__[A-Z_]+__", e) for e in execs), execs

    def test_o_vigia_nao_mora_dentro_do_opt_out_do_pssupport(self) -> None:
        """Com o vigia dentro do `else` do `--keep-steam-input`, a máquina que
        instalou antes de existir Steam nunca extraía o pino do cache.
        MORDIDA: devolva a instalação das unidades para dentro daquele `if`."""
        bloco = _bloco('step "11/11"', 'step "11b"')
        opt_out = bloco.index('if [[ "${KEEP_STEAM_INPUT}" -eq 1 ]]; then')
        fim_do_opt_out = bloco.index("\nfi\n", opt_out)
        unidade = bloco.index('"${USER_UNIT_DIR}/hefesto-steam-input-guard.service"')
        assert unidade > fim_do_opt_out

    def test_com_a_steam_aberta_o_manter_nem_extrai(
        self, lar: Path, download_local: dict, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O `.timer` de meia hora descompactava ~1,5 GB no meio da partida.
        MORDIDA: tire o `_steam_gate()` que vem antes do ensure no `--manter`."""
        raiz = _steam_de_verdade(lar)
        cache = lar / "cache"
        cache.mkdir()
        (cache / f"{PINO}.tar.gz").write_bytes(download_local["tarball"].read_bytes())
        monkeypatch.setattr(pp, "steam_game_running", lambda: True)

        rc = pp.main(["--manter", "--conf", str(download_local["conf"]),
                      "--cache-dir", str(cache), "--state", str(lar / "estado.json")])

        assert rc == 3
        assert not pp.pinned_proton_installed(PINO, raiz / "compatibilitytools.d")

    def test_sem_cache_o_manter_nao_manda_fechar_a_steam(
        self, lar: Path, download_local: dict, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sem tarball no cache, o `--fix` mandava fechar a Steam (rc 3) e, na
        volta, dizia que o tarball não estava lá (rc 2): o conselho chegava em
        dois saltos. MORDIDA: devolva o `_steam_gate()` para antes da conferência
        do cache no `--manter`."""
        _steam_de_verdade(lar)
        monkeypatch.setattr(pp, "steam_running", lambda: True)

        rc = pp.main(["--manter", "--conf", str(download_local["conf"]),
                      "--cache-dir", str(lar / "cache-vazio"),
                      "--state", str(lar / "estado.json")])

        assert rc == pp.RC_SEM_REDE_E_SEM_CACHE
        assert download_local["baixou"] == 0, "o vigia foi à rede"

    def test_o_manter_repoe_do_cache_e_trava_todo_jogo(
        self, lar: Path, download_local: dict
    ) -> None:
        """De ponta a ponta, sem rede: a Steam apareceu depois do install."""
        raiz = _steam_de_verdade(lar)
        _jogo(raiz, "2497900")
        (raiz / "steamapps" / "compatdata" / "2497900").mkdir(parents=True)
        cache = lar / "cache"
        cache.mkdir()
        (cache / f"{PINO}.tar.gz").write_bytes(download_local["tarball"].read_bytes())
        (raiz / "config" / "config.vdf").write_text(
            _config_vdf({"2497900": "proton_11"}), encoding="utf-8"
        )

        rc = pp.main(["--manter", "--conf", str(download_local["conf"]),
                      "--cache-dir", str(cache),
                      "--state", str(lar / "estado.json")])

        assert rc == 0
        assert download_local["baixou"] == 0, "o vigia foi à rede"
        assert pp.pinned_proton_installed(PINO, raiz / "compatibilitytools.d")
        mapa = pp.extract_compat_tool_mapping(
            (raiz / "config" / "config.vdf").read_text(encoding="utf-8"))
        assert mapa == {"0": PINO, "2497900": PINO}, mapa

    def test_o_manter_respeita_a_excecao_nomeada(
        self, lar: Path, download_local: dict
    ) -> None:
        """MORDIDA: tire o `excluir=ler_jogos_fora_do_pino()` do `--manter`."""
        raiz = _steam_de_verdade(lar)
        _jogo(raiz, "2497900")
        compat = raiz / "compatibilitytools.d"
        pp._extract_verified_tarball(download_local["tarball"], PINO, compat)
        (raiz / "config" / "config.vdf").write_text(
            _config_vdf({"0": PINO, "2497900": "proton_11"}), encoding="utf-8"
        )
        assert pp.main(["--fora-do-pino", "2497900"]) == 0
        texto = pp.fora_do_pino_path().read_text(encoding="utf-8")
        assert re.search(r"# \d\d/\d\d/\d{4} — fora do Proton pinado", texto), texto

        pp.main(["--manter", "--conf", str(download_local["conf"]),
                 "--state", str(lar / "estado.json")])

        mapa = pp.extract_compat_tool_mapping(
            (raiz / "config" / "config.vdf").read_text(encoding="utf-8"))
        assert mapa["2497900"] == "proton_11", "o vigia brigou com a escolha nomeada"

    def test_o_manter_tira_do_pino_quem_entrou_na_excecao_depois(
        self, lar: Path, download_local: dict
    ) -> None:
        """OS-LANCADORES-IGUAIS-E-A-LISTA-DE-EXCLUSAO-01 (21/09/2026). O jogo já
        estava no NOSSO pino quando entrou em `jogos_fora_do_pino.txt` — pela
        mão dela ou pela lista de exclusão. O lock só o PULAVA, e o pino ficava.
        MORDIDA: tire o `destravar_os_de_fora` do `--manter`."""
        raiz = _steam_de_verdade(lar)
        _jogo(raiz, "2497900")
        pp._extract_verified_tarball(
            download_local["tarball"], PINO, raiz / "compatibilitytools.d")
        (raiz / "config" / "config.vdf").write_text(
            _config_vdf({"2497900": "proton_11"}), encoding="utf-8"
        )
        estado = lar / "estado.json"
        pp.main(["--manter", "--conf", str(download_local["conf"]),
                 "--state", str(estado)])
        vdf = raiz / "config" / "config.vdf"
        assert pp.extract_compat_tool_mapping(
            vdf.read_text(encoding="utf-8"))["2497900"] == PINO
        assert pp.main(["--fora-do-pino", "2497900"]) == 0

        pp.main(["--manter", "--conf", str(download_local["conf"]),
                 "--state", str(estado)])

        mapa = pp.extract_compat_tool_mapping(vdf.read_text(encoding="utf-8"))
        assert mapa["2497900"] == "proton_11", "o jogo excluído continua no pino"

    def test_sem_steam_o_manter_nao_faz_nada(self, lar: Path, download_local: dict) -> None:
        assert pp.main(["--manter", "--conf", str(download_local["conf"])]) == 0
        assert not (lar / ".steam").exists()

    def test_com_a_steam_aberta_o_manter_adia(
        self, lar: Path, download_local: dict, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        raiz = _steam_de_verdade(lar)
        pp._extract_verified_tarball(
            download_local["tarball"], PINO, raiz / "compatibilitytools.d")
        antes = (raiz / "config" / "config.vdf").read_text(encoding="utf-8")
        monkeypatch.setattr(pp, "steam_running", lambda: True)

        rc = pp.main(["--manter", "--conf", str(download_local["conf"]),
                      "--state", str(lar / "estado.json")])

        assert rc == 3
        assert (raiz / "config" / "config.vdf").read_text(encoding="utf-8") == antes


def _mapa(raiz: Path) -> dict[str, str]:
    return pp.extract_compat_tool_mapping(
        (raiz / "config" / "config.vdf").read_text(encoding="utf-8"))


@pytest.fixture()
def mesa(lar: Path) -> Path:
    """Uma Steam com o pino instalado, um jogo NATIVO e um só-Windows que já
    rodou pelo Proton — os dois instalados, e nenhum no `CompatToolMapping`."""
    raiz = _steam_de_verdade(lar)
    _pino_na(raiz)
    (raiz / "appcache").mkdir()
    (raiz / "appcache" / "appinfo.vdf").write_bytes(_appinfo({
        "316790": "windows,macos,linux", "2497900": "windows"}))
    for appid in ("316790", "2497900"):
        _jogo(raiz, appid)
    (raiz / "steamapps" / "compatdata" / "2497900").mkdir(parents=True)
    return raiz


class TestTodoJogoTemClasse:
    """(d) do cético: "todo jogo" é todo jogo que roda por Proton."""

    def test_ferramenta_que_nao_e_proton_fica_mesmo_com_todos(self) -> None:
        """MORDIDA: tire o `e_da_familia_proton` do `troca_pedida`."""
        texto, mudancas = pp.build_compat_tool_mapping(
            _config_vdf({"0": PINO, "42": "steamlinuxruntime_sniper", "43": "proton_9"}),
            tool_name=PINO, appids=["42", "43"], pinos_nossos=(PINO,),
            atropelar_escolha_dela=True,
        )
        mapa = pp.extract_compat_tool_mapping(texto)
        assert mapa["42"] == "steamlinuxruntime_sniper"
        assert mudancas["42"]["action"] == "preservado"
        assert mapa["43"] == PINO

    @pytest.mark.parametrize("formato", [28, 29])
    def test_o_appinfo_diz_quem_e_nativo(self, tmp_path: Path, formato: int) -> None:
        arquivo = tmp_path / "appinfo.vdf"
        arquivo.write_bytes(_appinfo(
            {"316790": "windows,macos,linux", "2497900": "windows", "7": None},
            formato=formato,
        ))
        lido = pp.oslist_do_appinfo(arquivo, ["316790", "2497900", "7", "999"])
        assert lido == {"316790": "windows,macos,linux", "2497900": "windows", "7": ""}

    def test_formato_desconhecido_e_ilegivel(self, tmp_path: Path) -> None:
        arquivo = tmp_path / "appinfo.vdf"
        arquivo.write_bytes(struct.pack("<II", 0x0756442A, 1) + b"\0" * 32)
        assert pp.oslist_do_appinfo(arquivo, ["1"]) is None

    @pytest.mark.parametrize("ctm", [None, {"0": PINO}], ids=["sem-bloco", "com-bloco"])
    def test_jogo_nativo_nao_ganha_entrada_nova(
        self, lar: Path, ctm: dict[str, str] | None
    ) -> None:
        """MORDIDA: tire o `if appid in nativos` de qualquer um dos dois ramos
        do build — o que cria o bloco inteiro e o que acrescenta nele."""
        raiz = _steam_de_verdade(lar)
        _pino_na(raiz)
        (raiz / "config" / "config.vdf").write_text(_config_vdf(ctm), encoding="utf-8")
        (raiz / "appcache").mkdir()
        (raiz / "appcache" / "appinfo.vdf").write_bytes(_appinfo({
            "316790": "windows,macos,linux",   # nativo
            "2497900": "windows",              # só Windows
        }))
        for appid in ("316790", "2497900", "555", "556"):
            _jogo(raiz, appid)
        # 555 e 556 fora do appinfo: decide a pegada do Proton.
        (raiz / "steamapps" / "compatdata" / "555").mkdir(parents=True)

        sem = pp.jogos_sem_entrada_nova(["316790", "2497900", "555", "556"], home=lar)
        assert sem == {"316790", "556"}

        r = pp.lock_proton_for_all_games(
            conf={"name": PINO, "url": "x", "sha256": "ab" * 32},
            home=lar, state_path=lar / "estado.json", todos=True,
        )
        mapa = pp.extract_compat_tool_mapping(
            (raiz / "config" / "config.vdf").read_text(encoding="utf-8"))
        assert r["status"] == "locked", r
        assert set(mapa) == {"0", "2497900", "555"}, mapa

    def test_a_entrada_que_ja_existe_nunca_e_apagada(self) -> None:
        """O 316790 dela fica no GE: tirá-lo mudaria os saves de lugar."""
        original = _config_vdf({"0": PINO, "316790": PINO})
        texto, mudancas = pp.build_compat_tool_mapping(
            original, tool_name=PINO, appids=["316790"], pinos_nossos=(PINO,),
            atropelar_escolha_dela=True, sem_entrada_nova={"316790"},
        )
        assert texto == original and mudancas == {}

    def test_o_botao_repassa_o_todos(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`lock_proton_for_all_games` nem tinha o parâmetro. MORDIDA: tire o
        `todos=todos` do repasse."""
        monkeypatch.setattr(pp, "steam_running", lambda: False)
        monkeypatch.setattr(pp, "steam_game_running", lambda: False)
        raiz = tmp_path / ".steam/steam"
        (raiz / "steamapps").mkdir(parents=True)
        _pino_na(raiz)
        _jogo(raiz, "2497900")
        vdf = tmp_path / "config.vdf"
        vdf.write_text(_config_vdf({"0": PINO, "2497900": "proton_11"}), encoding="utf-8")

        pp.lock_proton_for_all_games(
            conf={"name": PINO, "url": "x", "sha256": "ab" * 32},
            home=tmp_path, config_vdf=vdf, state_path=tmp_path / "e.json", todos=True,
        )
        assert pp.extract_compat_tool_mapping(vdf.read_text(encoding="utf-8"))[
            "2497900"] == PINO

    # Os quatro caminhos que QUALQUER computador roda — o install (`--lock
    # --todos`, 11c), o vigia (`--manter`) e o botão (`lock_proton_for_all_
    # games`) —, e não só o do botão: o validador arrancou a classe e a exceção
    # nomeada do `_cmd_lock` e do `_cmd_manter` com 1365 testes verdes.

    def test_o_install_nao_da_entrada_ao_nativo(
        self, mesa: Path, download_local: dict, lar: Path
    ) -> None:
        """MORDIDA (B22b): `sem_entrada_de=None` no `_cmd_lock`."""
        rc = pp.main(["--lock", "--todos", "--conf", str(download_local["conf"]),
                      "--state", str(lar / "estado.json")])
        assert rc == 0
        assert _mapa(mesa) == {"0": PINO, "2497900": PINO}

    def test_o_vigia_nao_da_entrada_ao_nativo(
        self, mesa: Path, download_local: dict, lar: Path
    ) -> None:
        """MORDIDA (B22a): `sem_entrada_de=None` no `_cmd_manter`."""
        rc = pp.main(["--manter", "--conf", str(download_local["conf"]),
                      "--state", str(lar / "estado.json")])
        assert rc == 0
        assert _mapa(mesa) == {"0": PINO, "2497900": PINO}

    def test_o_install_respeita_a_excecao_nomeada(
        self, mesa: Path, download_local: dict, lar: Path
    ) -> None:
        """MORDIDA (B6b): `excluir=()` no `_cmd_lock`."""
        (mesa / "config" / "config.vdf").write_text(
            _config_vdf({"0": PINO, "2497900": "proton_11"}), encoding="utf-8")
        assert pp.main(["--fora-do-pino", "2497900"]) == 0
        rc = pp.main(["--lock", "--todos", "--conf", str(download_local["conf"]),
                      "--state", str(lar / "estado.json")])
        assert rc == 0
        assert _mapa(mesa)["2497900"] == "proton_11", "o install atropelou a exceção"

    def test_o_botao_respeita_a_excecao_nomeada(self, mesa: Path, lar: Path) -> None:
        """MORDIDA (B6a): `excluir=()` em `lock_proton_for_all_games`."""
        (mesa / "config" / "config.vdf").write_text(
            _config_vdf({"0": PINO, "2497900": "proton_11"}), encoding="utf-8")
        assert pp.main(["--fora-do-pino", "2497900"]) == 0
        r = pp.lock_proton_for_all_games(
            conf={"name": PINO, "url": "x", "sha256": "ab" * 32},
            home=lar, state_path=lar / "estado.json", todos=True,
        )
        assert r["status"] in ("locked", "noop"), r
        assert _mapa(mesa)["2497900"] == "proton_11", "o botão atropelou a exceção"


# ---------------------------------------------------------------------------
# 3 — 7b27bb58d: a órfã entra pela ferramenta que ela já tem
# ---------------------------------------------------------------------------
class TestAOrfaEntraPelaFerramenta:
    def test_orfa_num_proton_volta_ao_pino_e_a_nativa_fica(self) -> None:
        """MORDIDA: devolva `ja_no_mapa` a todo appid do mapa, sem o filtro.

        A órfã nativa nem entra no alvo: sem o filtro, a regra da entrada
        existente ainda a preservaria no arquivo, mas ela viraria `preservado`
        no registro — e o registro diria que o produto mirou um jogo nativo.
        """
        texto, mudancas = pp.build_compat_tool_mapping(
            _config_vdf({
                "0": PINO,
                "1245620": "proton_11",                 # órfã de Proton → pino
                "4046520": "steamlinuxruntime_sniper",  # órfã nativa → fica
                "2369580": "GE-Proton10-34",            # órfã num pino velho → pino
            }),
            tool_name=PINO, appids=[], pinos_nossos=(PINO, "GE-Proton10-34"),
            atropelar_escolha_dela=True,
        )
        mapa = pp.extract_compat_tool_mapping(texto)
        assert mapa["1245620"] == PINO
        assert mapa["2369580"] == PINO
        assert mapa["4046520"] == "steamlinuxruntime_sniper"
        assert "4046520" not in mudancas, mudancas

    def test_orfa_nomeada_nao_e_tocada(self) -> None:
        original = _config_vdf({"0": PINO, "1245620": "proton_11"})
        texto, mudancas = pp.build_compat_tool_mapping(
            original, tool_name=PINO, appids=[], pinos_nossos=(PINO,),
            atropelar_escolha_dela=True, excluir={"1245620"},
        )
        assert texto == original and mudancas == {}


# ---------------------------------------------------------------------------
# 4 — o doctor: a raiz envenenada, a exceção nomeada e o `--fix`
# ---------------------------------------------------------------------------
def _doctor(funcao: str, casa: Path) -> str:
    r = subprocess.run(
        ["bash", "-c", f'source "$DOCTOR_SH"; {funcao}'],
        capture_output=True, text=True, timeout=120, check=False,
        env={
            "DOCTOR_SH": str(DOCTOR), "HOME": str(casa),
            "XDG_CONFIG_HOME": str(casa / ".config"),
            "XDG_STATE_HOME": str(casa / ".local/state"),
            "XDG_CACHE_HOME": str(casa / ".cache"),
            "PATH": "/usr/local/bin:/usr/bin:/bin", "LC_ALL": "C.UTF-8", "NO_COLOR": "1",
        },
    )
    return r.stdout + r.stderr


class TestODoctorVeOQueAntesCalava:
    def test_a_raiz_envenenada_e_fail_com_o_gesto(self, tmp_path: Path) -> None:
        """Antes: *"Steam não detectada"* e silêncio. MORDIDA: tire o bloco da
        raiz envenenada do `check_proton_pin`."""
        casa = tmp_path / "casa"
        sobra = casa / ".steam/steam/compatibilitytools.d" / PINO
        sobra.mkdir(parents=True)
        (sobra / pp.MANIFEST_BASENAME).write_text(
            '{"installed_by": "hefesto-dualsense4unix"}', encoding="utf-8")

        saida = _doctor("check_proton_pin", casa)

        linha = next((ln for ln in saida.splitlines() if ln.startswith("[FAIL]")), "")
        assert "instalador antigo do Hefesto" in linha, saida
        assert "mv " in linha and ".sobra-do-hefesto" in linha, linha

    def test_o_fix_roda_o_mesmo_passo_do_vigia(self) -> None:
        """O `--lock --todos` daqui travava sem o pino instalado, e o doctor
        dizia PASS. O `--manter` repõe do cache e só trava com o pino lá."""
        texto = DOCTOR.read_text(encoding="utf-8")
        corpo = re.search(r"^apply_fixes\(\) \{$.*?^\}$", texto, re.M | re.S)
        assert corpo and "fix_proton_pinado" in corpo.group(0)
        dono = re.search(r"^fix_proton_pinado\(\) \{$.*?^\}$", texto, re.M | re.S)
        assert dono and '"${py}" --manter' in dono.group(0)
        assert "--lock" not in dono.group(0)

    @pytest.mark.parametrize("disse_nao", [True, False], ids=["sem-o-pino", "com-o-pino"])
    def test_quem_disse_nao_ao_pino_nao_ganha_a_trava_pelo_fix(
        self, tmp_path: Path, disse_nao: bool
    ) -> None:
        """O `--no-proton-pin` tira o `--manter` da unidade do vigia, e é esse
        o rastro — na linha `ExecStart`, porque o comentário da unidade também
        diz `--manter`. MORDIDA: tire a leitura da unidade do `fix_proton_pinado`.

        O par "com-o-pino" é o negativo: com a linha lá, o `--fix` roda o passo
        (e a saída diz o desfecho dele — sem cache, ou com a Steam aberta).
        """
        casa = tmp_path / "casa"
        _steam_de_verdade(casa)
        unidade = casa / ".config/systemd/user/hefesto-steam-input-guard.service"
        unidade.parent.mkdir(parents=True)
        unidade.write_text("".join(
            ln for ln in SERVICO.read_text(encoding="utf-8").splitlines(keepends=True)
            if not (disse_nao and ln.startswith("ExecStart=") and "__PROTON_PIN__" in ln)
        ), encoding="utf-8")

        saida = _doctor("fix_proton_pinado", casa)

        assert ("instalado sem o passo do pino" in saida) is disse_nao, saida
        assert bool(re.search(r"^\[(PASS|WARN)\]", saida, re.M)) is not disse_nao, saida

    @pytest.mark.parametrize("com_pino", [False, True], ids=["sem-pino", "com-pino"])
    def test_o_check_so_manda_rodar_o_fix_com_o_pino_instalado(
        self, tmp_path: Path, com_pino: bool
    ) -> None:
        """Sem o pino, o `--fix` não tem em que travar: o conselho é o do
        AUSENTE. MORDIDA: `_gesto_da_trava_do_pino` sempre devolvendo o `--fix`."""
        casa = tmp_path / "casa"
        raiz = _steam_de_verdade(casa)
        (raiz / "config" / "config.vdf").write_text(
            _config_vdf({"0": "proton_11"}), encoding="utf-8")
        if com_pino:
            _pino_na(raiz, pp._load_conf(None)["name"])

        saida = _doctor("check_proton_pin", casa)

        linha = next(ln for ln in saida.splitlines() if "default global da Steam" in ln)
        assert ("doctor.sh --fix" in linha) is com_pino, linha

    @pytest.mark.parametrize(
        "disse_nao", [True, False], ids=["vigia-sem-o-pino", "vigia-com-o-pino"])
    def test_com_o_rastro_do_nao_o_conselho_e_reinstalar(
        self, tmp_path: Path, disse_nao: bool
    ) -> None:
        """O conselho e o `--fix` leem o MESMO rastro. Com o pino instalado e a
        unidade do vigia sem a linha do `--manter`, o `--fix` recusa — e o
        conselho mandava rodá-lo: a pessoa só chegava à cura no segundo salto.
        MORDIDA: `_gesto_da_trava_do_pino` sem perguntar ao
        `_o_vigia_recusou_o_pino`."""
        casa = tmp_path / "casa"
        raiz = _steam_de_verdade(casa)
        (raiz / "config" / "config.vdf").write_text(
            _config_vdf({"0": "proton_11"}), encoding="utf-8")
        _pino_na(raiz, pp._load_conf(None)["name"])
        unidade = casa / ".config/systemd/user/hefesto-steam-input-guard.service"
        unidade.parent.mkdir(parents=True)
        unidade.write_text("".join(
            ln for ln in SERVICO.read_text(encoding="utf-8").splitlines(keepends=True)
            if not (disse_nao and ln.startswith("ExecStart=") and "__PROTON_PIN__" in ln)
        ), encoding="utf-8")

        saida = _doctor("check_proton_pin", casa)

        linha = next(ln for ln in saida.splitlines() if "default global da Steam" in ln)
        assert ("doctor.sh --fix" in linha) is not disse_nao, linha
        assert ("instalado sem o passo do pino" in linha) is disse_nao, linha

    def test_sem_steam_o_fix_do_pino_cala(self, tmp_path: Path) -> None:
        casa = tmp_path / "casa"
        casa.mkdir()
        assert _doctor("fix_proton_pinado", casa).strip() == ""

    def test_a_excecao_nomeada_aparece_com_a_data(self, tmp_path: Path) -> None:
        casa = tmp_path / "casa"
        raiz = casa / ".steam/steam"
        (raiz / "config").mkdir(parents=True)
        (raiz / "steamapps").mkdir(parents=True)
        _jogo(raiz, "2497900", "DON'T SCREAM")
        _jogo(raiz, "4046520", "Um Nativo")
        (raiz / "config" / "config.vdf").write_text(_config_vdf({
            "0": pp._load_conf(None)["name"],
            "2497900": "proton_11", "4046520": "steamlinuxruntime_sniper",
        }), encoding="utf-8")
        nomes = casa / ".config/hefesto-dualsense4unix/jogos_fora_do_pino.txt"
        nomes.parent.mkdir(parents=True)
        nomes.write_text("2497900\n", encoding="utf-8")
        os.utime(nomes, (1_758_153_600, 1_758_153_600))  # 18/09/2025 00h UTC

        saida = _doctor("check_proton_pin", casa)

        nomeado = next(ln for ln in saida.splitlines() if "exceção que você nomeou" in ln)
        assert nomeado.startswith("       "), nomeado  # INFO, não WARN
        assert "DON'T SCREAM" in nomeado and "/09/2025" in nomeado, nomeado
        nativo = next(ln for ln in saida.splitlines() if "rodar nativo" in ln)
        assert nativo.startswith("       ") and "steamlinuxruntime_sniper" in nativo
        assert "[WARN] jogo(s) fora do Proton pinado" not in saida, saida


# ---------------------------------------------------------------------------
# 5 — correção do grupo (18/09/2026): SEM O PINO, NADA SE TRAVA
# ---------------------------------------------------------------------------
@pytest.fixture()
def steam_sem_pino(lar: Path) -> Path:
    """Uma Steam de verdade, um jogo só-Windows num outro Proton, e o pino AUSENTE
    — a máquina do install sem rede, ou do install feito antes de existir Steam."""
    raiz = _steam_de_verdade(lar)
    _jogo(raiz, "2497900")
    (raiz / "steamapps" / "compatdata" / "2497900").mkdir(parents=True)
    (raiz / "config" / "config.vdf").write_text(
        _config_vdf({"2497900": "proton_11"}), encoding="utf-8")
    return raiz


class TestSemOPinoNadaSeTrava:
    """Travar num Proton que não existe aponta cada jogo para uma ferramenta
    ausente, e a Steam não abre nenhum. Medido pelo validador num HOME de
    mentira: o `--lock --todos` saía rc 0 com "locked — 2 added", e o doctor
    imprimia PASS. A guarda é do LOCK, e todo chamador a herda."""

    def test_o_lock_todos_recusa_e_o_arquivo_fica_byte_a_byte(
        self, lar: Path, steam_sem_pino: Path, download_local: dict,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """MORDIDA: tire o `compat_dir=` do `_cmd_lock`, ou a pergunta ao pino
        de `lock_games_to_pinned_proton`."""
        vdf = steam_sem_pino / "config" / "config.vdf"
        antes = vdf.read_bytes()

        rc = pp.main(["--lock", "--todos", "--conf", str(download_local["conf"]),
                      "--state", str(lar / "estado.json")])

        assert rc == pp.RC_ADIADO
        assert vdf.read_bytes() == antes, "travou num Proton que não existe"
        assert not (lar / "estado.json").exists()
        assert "não está instalado" in capsys.readouterr().out

    def test_o_botao_recusa_e_a_tela_diz_que_nao_travou(
        self, lar: Path, steam_sem_pino: Path
    ) -> None:
        """O botão da aba Sistema e o worker da GTK. MORDIDA: tire o
        `compat_dir=` de `lock_proton_for_all_games`."""
        from hefesto_dualsense4unix.app.actions.daemon_actions import (
            format_proton_lock_result,
            frase_sem_o_proton_pinado,
        )

        vdf = steam_sem_pino / "config" / "config.vdf"
        antes = vdf.read_bytes()

        r = pp.lock_proton_for_all_games(
            conf={"name": PINO, "url": "x", "sha256": "ab" * 32},
            home=lar, state_path=lar / "estado.json", todos=True,
        )

        assert (r["status"], r["reason"]) == ("recusado", "pino_ausente"), r
        assert vdf.read_bytes() == antes
        # A frase que já existe para o pino ausente — não a recusa sem motivo,
        # que diz "a Steam recusou" sobre uma causa que não é a Steam.
        # MORDIDA: tire o ramo `pino_ausente` de `_frase_de_recusa_do_proton`.
        assert format_proton_lock_result(r) == frase_sem_o_proton_pinado()

    def test_o_vigia_sem_cache_nao_toca_no_arquivo(
        self, lar: Path, steam_sem_pino: Path, download_local: dict
    ) -> None:
        vdf = steam_sem_pino / "config" / "config.vdf"
        antes = vdf.read_bytes()

        rc = pp.main(["--manter", "--conf", str(download_local["conf"]),
                      "--cache-dir", str(lar / "cache-vazio"),
                      "--state", str(lar / "estado.json")])

        assert rc == pp.RC_SEM_REDE_E_SEM_CACHE
        assert vdf.read_bytes() == antes
        assert download_local["baixou"] == 0, "o vigia foi à rede"

    def test_com_o_pino_o_mesmo_lock_trava(
        self, lar: Path, steam_sem_pino: Path, download_local: dict
    ) -> None:
        """O NEGATIVO: a guarda não trava a trava de quem tem o pino."""
        _pino_na(steam_sem_pino)
        rc = pp.main(["--lock", "--todos", "--conf", str(download_local["conf"]),
                      "--state", str(lar / "estado.json")])
        assert rc == 0
        assert _mapa(steam_sem_pino) == {"0": PINO, "2497900": PINO}

    def test_todo_chamador_do_lock_diz_onde_o_pino_mora(self) -> None:
        """A guarda só vale para quem passa `compat_dir`; o chamador novo que
        esquecer volta a travar no vazio. MORDIDA: tire o `compat_dir=` de
        qualquer chamada de `lock_games_to_pinned_proton` em `src/`."""
        chamadas: list[str] = []
        sem_pino: list[str] = []
        for arquivo in sorted((RAIZ / "src").rglob("*.py")):
            texto = arquivo.read_text(encoding="utf-8")
            if "lock_games_to_pinned_proton(" not in texto:
                continue
            for no in ast.walk(ast.parse(texto)):
                if not isinstance(no, ast.Call):
                    continue
                f = no.func
                nome = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", None)
                if nome != "lock_games_to_pinned_proton":
                    continue
                onde = f"{arquivo.relative_to(RAIZ)}:{no.lineno}"
                chamadas.append(onde)
                if not any(k.arg == "compat_dir" for k in no.keywords):
                    sem_pino.append(onde)
        assert len(chamadas) >= 3, chamadas  # o botão, o `--lock` e o `--manter`
        assert sem_pino == [], sem_pino


# ---------------------------------------------------------------------------
# 6 — o leitor do appinfo.vdf não prende o vigia
# ---------------------------------------------------------------------------
class TestOLeitorNaoPrendeOVigia:
    def test_string_larga_sem_fim_e_ilegivel_e_nao_laco_eterno(self, tmp_path: Path) -> None:
        """Medido pelo validador: `_ler_vdf_binario(b'\\x05chave\\x00ab', 0, None)`
        só morria pelo `timeout`. O vigia roda isto dentro da trava do
        `config.vdf`. MORDIDA: devolva o `while buf[fim:fim + 2] != b"\\0\\0"`."""
        vdf = b"\x00appinfo\0\x00common\0\x05oslist\0a\0b"
        cabecalho = (struct.pack("<IIQ", 2, 0, 0) + b"\0" * 20
                     + struct.pack("<I", 1) + b"\0" * 20)
        entrada = cabecalho + vdf
        arquivo = tmp_path / "appinfo.vdf"
        arquivo.write_bytes(
            struct.pack("<II", 0x07564428, 1)
            + struct.pack("<II", 42, len(entrada)) + entrada + struct.pack("<I", 0)
        )
        codigo = (
            "from pathlib import Path\n"
            "from hefesto_dualsense4unix.integrations import proton_pin as pp\n"
            f"print(pp.oslist_do_appinfo(Path({str(arquivo)!r}), ['42']))\n"
        )
        try:
            r = subprocess.run(
                [sys.executable, "-c", codigo], capture_output=True, text=True,
                timeout=30, check=False,
                env={**os.environ, "PYTHONPATH": str(RAIZ / "src")},
            )
        except subprocess.TimeoutExpired:
            pytest.fail("o leitor do appinfo.vdf entrou em laço eterno")
        assert r.returncode == 0, r.stderr
        assert r.stdout.strip() == "None", r.stdout


# ---------------------------------------------------------------------------
# 7 — uma trava por vez no config.vdf, e com prazo
# ---------------------------------------------------------------------------
class TestUmaTravaPorVez:
    """O relatório do implementador dizia *"M23: o flock removido. Reprova no
    teste de trava concorrente"*, e esse teste não existia. Agora existe."""

    @pytest.fixture()
    def vdf(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        monkeypatch.setattr(pp, "steam_running", lambda: False)
        monkeypatch.setattr(pp, "steam_game_running", lambda: False)
        arquivo = tmp_path / "config.vdf"
        arquivo.write_text(_config_vdf(None), encoding="utf-8")
        return arquivo

    @staticmethod
    def _segurar(estado: Path) -> int:
        fd = os.open(estado.with_name(estado.name + ".trava"), os.O_RDWR | os.O_CREAT, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX)
        return fd

    def test_o_segundo_espera_o_primeiro_soltar(self, tmp_path: Path, vdf: Path) -> None:
        """MORDIDA: tire o `flock` de `_uma_trava_por_vez`."""
        estado = tmp_path / "estado.json"
        antes = vdf.read_text(encoding="utf-8")
        resultado: dict[str, object] = {}
        fd = self._segurar(estado)
        try:
            fio = threading.Thread(target=lambda: resultado.update(
                pp.lock_games_to_pinned_proton(
                    tool_name=PINO, appids=[], config_vdf=vdf, state_path=estado)),
                daemon=True)
            fio.start()
            fio.join(0.5)
            assert fio.is_alive(), "a trava não esperou quem já estava editando"
            assert vdf.read_text(encoding="utf-8") == antes
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
        fio.join(10)
        assert not fio.is_alive()
        assert resultado.get("status") == "locked", resultado
        assert pp.extract_compat_tool_mapping(vdf.read_text(encoding="utf-8"))["0"] == PINO

    def test_quem_segura_demais_faz_o_outro_recusar_em_vez_de_prender(
        self, tmp_path: Path, vdf: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O vigia é um oneshot sem prazo: preso, ele para o Steam Input e a
        sentinela junto. MORDIDA: volte ao `LOCK_EX` sem `LOCK_NB`."""
        monkeypatch.setattr(pp, "_PACIENCIA_DA_TRAVA_S", 0.2)
        estado = tmp_path / "estado.json"
        antes = vdf.read_text(encoding="utf-8")
        resultado: dict[str, object] = {}
        fd = self._segurar(estado)
        try:
            fio = threading.Thread(target=lambda: resultado.update(
                pp.lock_games_to_pinned_proton(
                    tool_name=PINO, appids=[], config_vdf=vdf, state_path=estado)),
                daemon=True)
            fio.start()
            fio.join(5)
            assert not fio.is_alive(), "a trava esperou para sempre"
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
        assert (resultado.get("status"), resultado.get("reason")) == (
            "recusado", "outra_trava_em_curso"), resultado
        assert vdf.read_text(encoding="utf-8") == antes

    def test_a_tela_diz_que_era_outra_trava_e_nao_a_steam(self) -> None:
        """A recusa do flock caía na frase sem motivo, "a Steam recusou a
        mudança" — e a Steam nem foi perguntada. MORDIDA: tire a entrada
        `outra_trava_em_curso` de `_RECUSAS_DO_PROTON`."""
        from hefesto_dualsense4unix.app.actions.daemon_actions import (
            format_proton_lock_result,
        )

        frase = format_proton_lock_result({
            "locked": 0, "skipped": 0, "errors": 0, "status": "recusado",
            "reason": "outra_trava_em_curso", "tool": PINO, "detail": {}})

        assert frase.startswith("NÃO travei nada"), frase
        assert "Steam recusou" not in frase and "outro processo do Hefesto" in frase, frase

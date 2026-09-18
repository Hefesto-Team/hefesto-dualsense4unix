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

import io
import os
import re
import struct
import subprocess
import tarfile
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
        """Flatpak/Snap: o Proton do host nunca serve lá dentro — 563 MB à toa."""
        (lar / ".var/app/com.valvesoftware.Steam/.steam/steam").mkdir(parents=True)
        cache = lar / "cache"
        rc = pp.main(["--ensure", "--conf", str(download_local["conf"]),
                      "--cache-dir", str(cache)])

        assert rc == pp.RC_ADIADO
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
        monkeypatch.delattr(tarfile, "data_filter", raising=False)
        original = tarfile.TarFile.extractall

        def _extractall_antigo(self, path=".", members=None, *, numeric_owner=False, **kw):
            if "filter" in kw:
                raise TypeError("extractall() got an unexpected keyword argument 'filter'")
            return original(self, path, members, numeric_owner=numeric_owner,
                            filter="fully_trusted")

        monkeypatch.setattr(tarfile.TarFile, "extractall", _extractall_antigo)
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
        assert "trap '_cleanup_sudo_keepalive; _reabrir_a_steam_se_o_install_fechou' EXIT" in bloco


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
        _jogo(raiz, "2497900")
        vdf = tmp_path / "config.vdf"
        vdf.write_text(_config_vdf({"0": PINO, "2497900": "proton_11"}), encoding="utf-8")

        pp.lock_proton_for_all_games(
            conf={"name": PINO, "url": "x", "sha256": "ab" * 32},
            home=tmp_path, config_vdf=vdf, state_path=tmp_path / "e.json", todos=True,
        )
        assert pp.extract_compat_tool_mapping(vdf.read_text(encoding="utf-8"))[
            "2497900"] == PINO


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

    def test_o_fix_chama_a_trava_com_todos(self) -> None:
        texto = DOCTOR.read_text(encoding="utf-8")
        corpo = re.search(r"^apply_fixes\(\) \{$.*?^\}$", texto, re.M | re.S)
        assert corpo and "fix_proton_pinado" in corpo.group(0)
        dono = re.search(r"^fix_proton_pinado\(\) \{$.*?^\}$", texto, re.M | re.S)
        assert dono and '--lock --todos' in dono.group(0)

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

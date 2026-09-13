"""JOGO-SEM-EXCLUSIVIDADE-01 (13/09/2026) — o Steam Input por jogo segue a lista.

A própria Steam liga o Steam Input POR JOGO sem escrever
`UseSteamControllerConfig`: a configuração do jogo mora em
``steamapps/common/Steam Controller Configs/<conta>/config/`` — entrada com
`autosave` no `configset_controller_ps5.vdf` e pasta `<appid>/`. Medido em
13/09: em toda abertura de um jogo assim a Steam criou controle virtual, e o
jogo passou a ver o espelho do Steam Input em vez da máscara da aba Jogar. O
vigia, o doctor e o prontuário só leem a chave do vdf, que não existe ali.

A lista do Hefesto passa a valer nos dois sentidos, e este arquivo trava:

1. o parser do `configset` — o que conta, e o que o faz FALHAR FECHADO;
2. o `"0"` no texto (a função pura) e as recusas herdadas da ponte;
3. o lar de mentira inteiro: três jogos configurados fora da lista ficam em
   `"0"`, o da lista em `"2"`, o sem configuração sem chave — o vdf relido
   pelo parser antes e depois, e um perfil de jogo byte a byte idêntico;
4. o vigia de verdade (bash), no mesmo instante em que ele já chama o
   `--ligar`, sem que nome de configset vá à saída.

Nenhum id de aparelho entra aqui: o configset "com nome de aparelho" deste
arquivo é um rótulo inventado.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import steam_input_ponte as ponte

#: Três jogos configurados pela Steam FORA da lista, um DENTRO, um sem nada.
_FORA = ("316790", "2111190", "3357650")
_NA_LISTA = "2497900"
_SEM_CONFIG = "4235410"
_CONTA = "10"
#: Rótulo inventado no lugar do id de aparelho que a Steam põe no nome.
_CONFIGSET_DE_APARELHO = "configset_aparelho-de-mentira.vdf"


def _vdf(viva: dict[str, str | None], canonica: tuple[str, ...] = ()) -> str:
    """`localconfig.vdf` com as duas árvores `apps` do layout real.

    Em `viva`, `None` é "o bloco do app existe sem a chave". A irmã
    `SteamController_PSSupport` vem depois do `}` da árvore viva, como no
    arquivo medido em 19/08/2026.
    """
    linhas = ['"UserLocalConfigStore"', "{"]
    linhas += ['\t"Software"', "\t{", '\t\t"Valve"', "\t\t{", '\t\t\t"Steam"', "\t\t\t{"]
    linhas += ['\t\t\t\t"apps"', "\t\t\t\t{"]
    for appid in canonica:
        linhas += [f'\t\t\t\t\t"{appid}"', "\t\t\t\t\t{",
                   '\t\t\t\t\t\t"LaunchOptions"\t\t"%command%"', "\t\t\t\t\t}"]
    linhas += ["\t\t\t\t}", "\t\t\t}", "\t\t}", "\t}"]
    linhas += ['\t"apps"', "\t{"]
    for appid, valor in viva.items():
        linhas += [f'\t\t"{appid}"', "\t\t{"]
        if valor is not None:
            linhas.append(f'\t\t\t"UseSteamControllerConfig"\t\t"{valor}"')
        linhas.append('\t\t\t"SteamControllerRumble"\t\t"-1"')
        linhas.append("\t\t}")
    linhas += ["\t}", '\t"SteamController_PSSupport"\t\t"0"', "}", ""]
    return "\n".join(linhas)


def _configset(entradas: dict[str, dict[str, str]]) -> str:
    """Um `configset_*.vdf` na forma medida em 13/09/2026."""
    linhas = ['"controller_config"', "{"]
    for chave, pares in entradas.items():
        linhas += [f'\t"{chave}"', "\t{"]
        linhas += [f'\t\t"{k}"\t\t"{v}"' for k, v in pares.items()]
        linhas.append("\t}")
    linhas += ["}", ""]
    return "\n".join(linhas)


def _valores(texto: str) -> dict[str, str | None]:
    """appid -> valor da chave na árvore VIVA, relido do zero pelo parser."""
    viva = ponte.arvore_viva(ponte.ler_arvores(texto))
    assert viva is not None, "o parser não achou a árvore viva"
    return {appid: par[0] for appid, par in viva.chaves.items()}


# ---------------------------------------------------------------------------
# 1. O configset: o que conta, e quando falha fechado
# ---------------------------------------------------------------------------
class TestOConfigset:
    def test_so_autosave_de_appid_conta(self) -> None:
        texto = _configset({
            "1599660": {"autosave": "1"},
            "1828690": {"template": "controller_xboxone_gamepad_fps.vdf"},
            "2358720": {"workshop": "123"},
            "2497900-testing": {"autosave": "1"},
            "3357650": {"autosave": "1"},
        })
        assert ponte.appids_com_autosave(texto) == {"1599660", "3357650"}

    def test_o_configset_vazio_da_steam_e_nada_configurado(self) -> None:
        assert ponte.appids_com_autosave('"controller_config"\n{\n}\n') == set()
        assert ponte.appids_com_autosave("") == set()

    @pytest.mark.parametrize(
        "texto",
        [
            '"controller_config"\n{\n\t"1599660"\n\t{\n\t\t"autosave"\t\t"1"\n',
            '"controller_config"\n{\n}\n}\n',
            '"autosave"\t\t"1"\n',
            '"controller_config"\n{\n\t"1599660"\n}\n',
            "{\n}\n",
            '"controller_config" {\n}\n',
            '"a"\n{\n}\n"b"\n{\n}\n',
            "\x00\x01lixo binário\n",
        ],
        ids=[
            "sem-fechar", "fecha-demais", "par-na-raiz", "nome-sem-bloco",
            "bloco-sem-nome", "nome-e-chave-na-mesma-linha", "duas-raizes", "lixo",
        ],
    )
    def test_forma_que_nao_se_entende_devolve_none(self, texto: str) -> None:
        assert ponte.appids_com_autosave(texto) is None

    def test_a_pasta_do_jogo_tambem_conta(self, tmp_path: Path) -> None:
        pasta = tmp_path / "config"
        (pasta / "413090").mkdir(parents=True)
        (pasta / "2497900-testing").mkdir()
        (pasta / "configset_controller_ps5.vdf").write_text(
            _configset({"1599660": {"autosave": "1"}}), encoding="utf-8"
        )
        (pasta / "preferences_qualquer.vdf").write_text("lixo que não é configset")
        assert ponte.configuracao_por_jogo(pasta) == {"413090", "1599660"}

    def test_pasta_que_nao_existe_e_nada_configurado(self, tmp_path: Path) -> None:
        assert ponte.configuracao_por_jogo(tmp_path / "nao-existe") == set()

    def test_um_configset_ilegivel_derruba_a_leitura_inteira(self, tmp_path: Path) -> None:
        pasta = tmp_path / "config"
        pasta.mkdir()
        (pasta / "configset_controller_ps5.vdf").write_text(
            _configset({"1599660": {"autosave": "1"}}), encoding="utf-8"
        )
        (pasta / _CONFIGSET_DE_APARELHO).write_bytes(b"\xff\xfe\x00quebrado")
        assert ponte.configuracao_por_jogo(pasta) is None

    def test_o_endereco_da_conta(self, tmp_path: Path) -> None:
        vdf = tmp_path / "raiz/userdata/77/config/localconfig.vdf"
        assert ponte.pasta_das_configs_por_jogo(vdf) == (
            tmp_path / "raiz/steamapps/common/Steam Controller Configs/77/config"
        )
        assert ponte.pasta_das_configs_por_jogo(tmp_path / "localconfig.vdf") is None


# ---------------------------------------------------------------------------
# 2. O "0" no texto
# ---------------------------------------------------------------------------
class TestODesligarNoTexto:
    def test_os_tres_casos_e_o_que_ja_esta(self) -> None:
        texto = _vdf({"1": "2", "2": None, "4": "0"}, canonica=("3",))
        novo, desligados, pulados = ponte.desligar_no_texto(texto, ["1", "2", "3", "4"])
        assert desligados == ["1", "2", "3"]
        assert pulados == [("4", ponte.JA_DESLIGADO)]
        assert _valores(novo) == {"1": "0", "2": "0", "3": "0", "4": "0"}
        assert ponte.conferir_escrita(texto, novo, desligados, valor=ponte.DESLIGADO) is None

    def test_o_valor_um_tambem_vira_zero(self) -> None:
        novo, desligados, _ = ponte.desligar_no_texto(_vdf({"1": "1"}), ["1"])
        assert desligados == ["1"]
        assert _valores(novo) == {"1": "0"}

    def test_herda_as_recusas_da_ponte(self) -> None:
        texto = _vdf({"1": "2"})
        novo, desligados, pulados = ponte.desligar_no_texto(texto, ["404404"])
        assert (novo, desligados) == (texto, [])
        assert pulados == [("404404", ponte.JOGO_DESCONHECIDO)]

    def test_a_conferencia_nao_aceita_relatorio_sem_escrita(self) -> None:
        texto = _vdf({"1": "2"})
        assert (
            ponte.conferir_escrita(texto, texto, ["1"], valor=ponte.DESLIGADO)
            == "nao_desligou:1"
        )

    def test_o_ligar_continua_o_mesmo(self) -> None:
        """O corpo passou a ser comum aos dois sentidos; o `--ligar` não muda."""
        texto = _vdf({"1": "0", "2": "1"})
        novo, ligados, pulados = ponte.ligar_no_texto(texto, ["1", "2"])
        assert ligados == ["1"]
        assert pulados == [("2", ponte.JA_LIGADO)]
        assert _valores(novo) == {"1": "2", "2": "1"}


# ---------------------------------------------------------------------------
# 3. O lar de mentira inteiro
# ---------------------------------------------------------------------------
def _montar_lar(raiz: Path) -> dict[str, Path]:
    """HOME com Steam, configuração por jogo, lista e um perfil de jogo."""
    home = raiz / "home"
    vdf = home / f".steam/steam/userdata/{_CONTA}/config/localconfig.vdf"
    vdf.parent.mkdir(parents=True)
    # O da lista está em "0" (a exceção inerte); os de fora nem têm a chave, ou
    # têm "2"; o sem configuração tem bloco e nenhuma chave.
    vdf.write_text(
        _vdf(
            {_FORA[0]: None, _FORA[1]: "2", _NA_LISTA: "0", _SEM_CONFIG: None},
            canonica=(_FORA[2],),
        ),
        encoding="utf-8",
    )
    configs = home / (
        f".steam/steam/steamapps/common/Steam Controller Configs/{_CONTA}/config"
    )
    configs.mkdir(parents=True)
    (configs / "configset_controller_ps5.vdf").write_text(
        _configset({appid: {"autosave": "1"} for appid in (*_FORA, _NA_LISTA)}),
        encoding="utf-8",
    )
    (configs / _CONFIGSET_DE_APARELHO).write_text(_configset({}), encoding="utf-8")
    for appid in (*_FORA, _NA_LISTA):
        (configs / appid).mkdir()
        (configs / appid / "controller_ps5.vdf").write_text('"controller_mappings"\n{\n}\n')
    lista = home / ".config/hefesto-dualsense4unix/steam_input_apps.txt"
    lista.parent.mkdir(parents=True)
    lista.write_text(f"# bancada\n{_NA_LISTA}\n", encoding="utf-8")
    perfil = home / ".config/hefesto-dualsense4unix/profiles/jogo_de_mentira.json"
    perfil.parent.mkdir(parents=True)
    perfil.write_text(
        '{"name": "jogo_de_mentira", "match": {"window_class": ["steam_app_316790"]},'
        ' "priority": 80, "mode": {"kind": "gamepad", "gamepad_flavor": "xbox"}}\n',
        encoding="utf-8",
    )
    return {"home": home, "vdf": vdf, "configs": configs, "lista": lista, "perfil": perfil}


def _fotografia(raiz: Path) -> dict[str, str]:
    """caminho relativo -> md5 de todo arquivo do lar."""
    return {
        str(p.relative_to(raiz)): hashlib.md5(p.read_bytes()).hexdigest()
        for p in sorted(raiz.rglob("*"))
        if p.is_file()
    }


def _mudancas(antes: dict[str, str], depois: dict[str, str]) -> set[str]:
    return {k for k in antes.keys() | depois.keys() if antes.get(k) != depois.get(k)}


class TestOLarDeMentira:
    @pytest.fixture()
    def lar(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
        casa = _montar_lar(tmp_path)
        monkeypatch.setenv("XDG_CONFIG_HOME", str(casa["home"] / ".config"))
        monkeypatch.setattr(ponte, "steam_running", lambda: False)
        monkeypatch.setattr(ponte, "steam_game_running", lambda: False)
        return casa

    def _vigia_em_python(self, lar: dict[str, Path]) -> tuple[str, list[dict[str, str]]]:
        """A ordem do vigia: primeiro o `--ligar`, depois o outro sentido."""
        ponte.garantir_ponte(lar["home"])
        return ponte.garantir_fora_da_lista_desligado(lar["home"])

    def test_fora_da_lista_zero_na_lista_dois_sem_config_sem_chave(
        self, lar: dict[str, Path]
    ) -> None:
        """A MORDIDA do outro sentido. Arranque o `desligar_no_texto` de
        `garantir_fora_da_lista_desligado` e os três ficam sem `"0"`; troque a
        lista lida por uma vazia e o jogo da lista cai para `"0"`."""
        antes = _valores(lar["vdf"].read_text(encoding="utf-8"))
        assert antes == {_FORA[1]: "2", _NA_LISTA: "0"}
        perfil_antes = lar["perfil"].read_bytes()
        foto_antes = _fotografia(lar["home"])

        status, detalhe = self._vigia_em_python(lar)

        assert status == ponte.PONTE_DESLIGADA, detalhe
        depois = _valores(lar["vdf"].read_text(encoding="utf-8"))
        assert {a: depois.get(a) for a in _FORA} == {a: "0" for a in _FORA}
        assert depois[_NA_LISTA] == "2"
        assert _SEM_CONFIG not in depois
        assert lar["perfil"].read_bytes() == perfil_antes
        mudou = _mudancas(foto_antes, _fotografia(lar["home"]))
        vdf_rel = str(lar["vdf"].relative_to(lar["home"]))
        assert vdf_rel in mudou
        assert all(m == vdf_rel or m.startswith(vdf_rel + ".bak.") for m in mudou), mudou

    def test_rodar_de_novo_nao_escreve_nem_faz_backup(self, lar: dict[str, Path]) -> None:
        self._vigia_em_python(lar)
        foto = _fotografia(lar["home"])

        status, _ = self._vigia_em_python(lar)

        assert status == ponte.PONTE_NADA
        assert _fotografia(lar["home"]) == foto

    def test_configset_ilegivel_zero_escritas(self, lar: dict[str, Path]) -> None:
        """A MORDIDA da falha fechada. Faça `configuracao_por_jogo` pular o
        configset que não se entende e os três voltam a receber `"0"`."""
        (lar["configs"] / _CONFIGSET_DE_APARELHO).write_text('"controller_config"\n{\n')
        foto = _fotografia(lar["home"])

        status, detalhe = ponte.garantir_fora_da_lista_desligado(lar["home"])

        assert status == ponte.PONTE_INCERTA
        assert [d["desfecho"] for d in detalhe] == [ponte.CONFIG_ILEGIVEL]
        assert _fotografia(lar["home"]) == foto
        assert "aparelho-de-mentira" not in repr(detalhe)

    def test_lista_que_existe_e_nao_se_le_zero_escritas(
        self, lar: dict[str, Path]
    ) -> None:
        """Ler a lista vazia por engano desligaria o jogo que ela pôs lá."""
        lar["lista"].unlink()
        lar["lista"].mkdir()
        foto = _fotografia(lar["home"])

        status, detalhe = ponte.garantir_fora_da_lista_desligado(lar["home"])

        assert status == ponte.PONTE_INCERTA
        assert [d["desfecho"] for d in detalhe] == [ponte.LISTA_ILEGIVEL]
        assert _fotografia(lar["home"]) == foto

    def test_sem_lista_nenhuma_todos_os_configurados_desligam(
        self, lar: dict[str, Path]
    ) -> None:
        """O caso da máquina medida: a lista não existe."""
        lar["lista"].unlink()

        status, _ = ponte.garantir_fora_da_lista_desligado(lar["home"])

        assert status == ponte.PONTE_DESLIGADA
        depois = _valores(lar["vdf"].read_text(encoding="utf-8"))
        assert {a: depois.get(a) for a in (*_FORA, _NA_LISTA)} == {
            a: "0" for a in (*_FORA, _NA_LISTA)
        }

    @pytest.mark.parametrize(
        ("steam", "jogo", "esperado"),
        [
            (True, False, ponte.PONTE_ADIADA_STEAM),
            (True, True, ponte.PONTE_ADIADA_JOGO),
        ],
    )
    def test_com_a_steam_ou_o_jogo_aberto_adia_sem_tocar(
        self,
        lar: dict[str, Path],
        monkeypatch: pytest.MonkeyPatch,
        steam: bool,
        jogo: bool,
        esperado: str,
    ) -> None:
        monkeypatch.setattr(ponte, "steam_running", lambda: steam)
        monkeypatch.setattr(ponte, "steam_game_running", lambda: jogo)
        foto = _fotografia(lar["home"])

        status, _ = ponte.garantir_fora_da_lista_desligado(lar["home"])

        assert status == esperado
        assert _fotografia(lar["home"]) == foto


# ---------------------------------------------------------------------------
# 4. O vigia de verdade
# ---------------------------------------------------------------------------
_BASH = shutil.which("bash") or "/bin/bash"
_GUARDA = Path(__file__).resolve().parents[2] / "scripts" / "disable_steam_input.sh"


def _rodar_o_vigia(
    tmp_path: Path, lar: dict[str, Path], *args: str
) -> subprocess.CompletedProcess[str]:
    """bash de verdade, HOME no lar de mentira, `pgrep`/`steam`/`sleep` stubados."""
    stubs = tmp_path / "stubs"
    stubs.mkdir(exist_ok=True)
    for nome, corpo in (("pgrep", "exit 1"), ("steam", "exit 0"), ("sleep", "exit 0")):
        alvo = stubs / nome
        alvo.write_text(f"#!/bin/sh\n{corpo}\n", encoding="utf-8")
        alvo.chmod(0o755)
    env: dict[str, Any] = dict(os.environ)
    env["HOME"] = str(lar["home"])
    env["XDG_CONFIG_HOME"] = str(lar["home"] / ".config")
    env["PATH"] = f"{stubs}:/usr/bin:/bin"
    return subprocess.run(
        [_BASH, str(_GUARDA), *args],
        capture_output=True, text=True, check=False, env=env, timeout=120,
    )


def test_o_vigia_desliga_o_de_fora_no_mesmo_instante_do_ligar(tmp_path: Path) -> None:
    """A MORDIDA da costura. Arranque a chamada `--desligar-fora-da-lista` de
    `ligar_ponte_da_allowlist` e os três jogos de fora ficam sem `"0"`."""
    lar = _montar_lar(tmp_path)
    perfil_antes = lar["perfil"].read_bytes()
    foto_antes = _fotografia(lar["home"])

    proc = _rodar_o_vigia(tmp_path, lar, "--apply-quiet")

    saida = proc.stdout + proc.stderr
    assert proc.returncode == 0, saida
    depois = _valores(lar["vdf"].read_text(encoding="utf-8"))
    assert {a: depois.get(a) for a in _FORA} == {a: "0" for a in _FORA}, saida
    assert depois[_NA_LISTA] == "2", saida
    assert _SEM_CONFIG not in depois
    assert lar["perfil"].read_bytes() == perfil_antes
    vdf_rel = str(lar["vdf"].relative_to(lar["home"]))
    mudou = _mudancas(foto_antes, _fotografia(lar["home"]))
    assert all(m == vdf_rel or m.startswith(vdf_rel + ".bak.") for m in mudou), mudou
    assert "[steam-input-fora-da-lista] resultado=desligado" in proc.stdout
    assert "aparelho-de-mentira" not in saida
    assert "configset_" not in saida
    assert proc.stdout.rstrip().splitlines()[-1].startswith("[steam-input] resultado=")

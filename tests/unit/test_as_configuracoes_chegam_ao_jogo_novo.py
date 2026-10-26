#!/usr/bin/env python3
"""O jogo novo recebe as configurações quando a Steam fecha, sem ela o abrir antes."""
from __future__ import annotations

from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import opcoes_por_jogo as opj
from hefesto_dualsense4unix.integrations import sentinela_do_wrapper as sdw
from hefesto_dualsense4unix.integrations import steam_input_ponte as ponte
from hefesto_dualsense4unix.integrations import steam_launch_options as slo
from hefesto_dualsense4unix.integrations import vigia_do_jogo_novo as vigia

NOVO = "2222222"
VELHO = "1111111"
CONTA = "1234"
STEAMID64 = str(76561197960265728 + int(CONTA))
OPCOES = "DXVK_ASYNC=1 %command%"


def _vdf(com_blocos: tuple[str, ...] = (VELHO,)) -> str:
    """Um `localconfig.vdf` com a árvore canônica e a árvore de `UseSteamControllerConfig`."""
    blocos = "".join(
        f'\t\t\t\t\t"{a}"\n\t\t\t\t\t{{\n\t\t\t\t\t\t"LaunchOptions"\t\t"{slo._vdf_escape(slo.WRAPPER_LAUNCH)}"\n'
        "\t\t\t\t\t}\n"
        for a in com_blocos
    )
    return (
        '"UserLocalConfigStore"\n{\n\t"Software"\n\t{\n\t\t"Valve"\n\t\t{\n\t\t\t"Steam"\n'
        f"\t\t\t{{\n\t\t\t\t\"apps\"\n\t\t\t\t{{\n{blocos}\t\t\t\t}}\n\t\t\t}}\n\t\t}}\n\t}}\n"
        '\t"apps"\n\t{\n\t\t"' + VELHO + '"\n\t\t{\n\t\t\t"UseSteamControllerConfig"\t\t"2"\n'
        "\t\t}\n\t}\n}\n"
    )


def _manifesto(pasta: Path, appid: str, nome: str) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / f"appmanifest_{appid}.acf").write_text(
        f'"AppState"\n{{\n\t"appid"\t\t"{appid}"\n\t"name"\t\t"{nome}"\n'
        f'\t"installdir"\t\t"{nome}"\n}}\n',
        encoding="utf-8",
    )


class _Casa:
    """Um HOME de mentira: Steam nativa, uma biblioteca fora do lar e o guarda instalado."""

    def __init__(self, raiz: Path) -> None:
        self.home = raiz / "casa"
        self.config = self.home / ".config"
        self.steam = self.home / ".steam" / "steam"
        self.biblioteca = raiz / "biblioteca2"
        self.vdf = self.steam / "userdata" / CONTA / "config" / "localconfig.vdf"
        self.vdf.parent.mkdir(parents=True)
        self.vdf.write_text(_vdf(), encoding="utf-8")
        (self.steam / "config").mkdir()
        (self.steam / "config" / "loginusers.vdf").write_text(
            f'"users"\n{{\n\t"{STEAMID64}"\n\t{{\n\t\t"MostRecent"\t\t"1"\n\t}}\n}}\n',
            encoding="utf-8",
        )
        (self.steam / "steamapps").mkdir()
        (self.biblioteca / "steamapps").mkdir(parents=True)
        (self.steam / "steamapps" / "libraryfolders.vdf").write_text(
            f'"libraryfolders"\n{{\n\t"1"\n\t{{\n\t\t"path"\t\t"{self.biblioteca}"\n\t}}\n}}\n',
            encoding="utf-8",
        )
        _manifesto(self.steam / "steamapps", VELHO, "Jogo Velho")
        self.unidades = self.home / ".config" / "systemd" / "user"
        self.unidades.mkdir(parents=True)
        (self.unidades / "hefesto-steam-input-guard.path").write_text("[Path]\n", encoding="utf-8")

    def instala_o_jogo_novo(self) -> None:
        _manifesto(self.biblioteca / "steamapps", NOVO, "Jogo Novo")

    def desliga(self) -> None:
        (self.config / "hefesto-dualsense4unix").mkdir(parents=True, exist_ok=True)
        vigia.caminho_do_interruptor(self.config).write_text("não\n", encoding="utf-8")

    def dropin(self) -> str:
        return (self.unidades / "hefesto-steam-input-guard.path.d" / "caminhos.conf").read_text(
            encoding="utf-8"
        )

    def texto(self) -> str:
        return self.vdf.read_text(encoding="utf-8")


@pytest.fixture
def casa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> _Casa:
    c = _Casa(tmp_path)
    monkeypatch.setenv("HOME", str(c.home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(c.config))
    for modulo in (opj, sdw, ponte, slo):
        monkeypatch.setattr(modulo, "steam_running", lambda: False)
        monkeypatch.setattr(modulo, "steam_game_running", lambda: False)
    monkeypatch.setattr(opj, "ler_jogos_sem_wrapper", lambda *_a, **_k: [])
    monkeypatch.setattr(sdw, "ler_jogos_sem_wrapper", lambda *_a, **_k: [])
    monkeypatch.setattr(vigia, "_recarregar_o_systemd", lambda: True)
    return c


def test_o_dropin_vigia_o_arquivo_da_conta_e_o_steamapps_de_cada_biblioteca(casa: _Casa) -> None:
    """ARRANQUE: volte o vigia a `userdata/` (a pasta do `.path` de hoje) e este teste cai."""
    chamadas: list[int] = []
    assert vigia.garantir(casa.home, config_home=casa.config,
                          recarregar=lambda: chamadas.append(1) or True) == vigia.ESCRITO
    linhas = casa.dropin().splitlines()
    vigiados = [x.removeprefix("PathChanged=") for x in linhas if x.startswith("PathChanged=")]
    assert f"%h/.steam/steam/userdata/{CONTA}/config/localconfig.vdf" in vigiados
    assert "%h/.steam/steam/steamapps" in vigiados
    assert f"{casa.biblioteca}/steamapps" in vigiados
    assert not any(v.endswith("/userdata") for v in vigiados)
    assert chamadas == [1]
    ritmo = (casa.unidades / "hefesto-steam-input-guard.service.d" / "ritmo.conf").read_text()
    assert "StartLimitBurst" in ritmo


def test_o_dropin_so_se_reescreve_quando_muda_e_so_entao_recarrega(casa: _Casa) -> None:
    chamadas: list[int] = []

    def recarrega() -> bool:
        chamadas.append(1)
        return True

    assert vigia.garantir(casa.home, config_home=casa.config, recarregar=recarrega) == vigia.ESCRITO
    assert vigia.garantir(casa.home, config_home=casa.config, recarregar=recarrega) == vigia.EM_DIA
    assert chamadas == [1]
    outra = casa.steam / "userdata" / "999" / "config"
    outra.mkdir(parents=True)
    assert vigia.garantir(casa.home, config_home=casa.config, recarregar=recarrega) == vigia.ESCRITO
    assert "userdata/999/config/localconfig.vdf" in casa.dropin()
    assert chamadas == [1, 1]


def test_sem_o_guarda_instalado_o_vigia_nao_escreve_nada(casa: _Casa) -> None:
    (casa.unidades / "hefesto-steam-input-guard.path").unlink()
    assert vigia.garantir(casa.home, config_home=casa.config) == vigia.SEM_UNIDADE
    assert not (casa.unidades / "hefesto-steam-input-guard.path.d").exists()


def test_o_interruptor_e_ligado_por_padrao_e_uma_palavra_de_recusa_o_desliga(casa: _Casa) -> None:
    assert vigia.interruptor_ligado(casa.config)
    arquivo = vigia.caminho_do_interruptor(casa.config)
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    for palavra in ("nao", "não", "0", "off", "desligado"):  # (noqa-acento)
        arquivo.write_text(f"# comentário\n{palavra}\n", encoding="utf-8")
        assert not vigia.interruptor_ligado(casa.config), palavra
    for palavra in ("sim", "1", "ligado", ""):
        arquivo.write_text(f"{palavra}\n", encoding="utf-8")
        assert vigia.interruptor_ligado(casa.config), palavra


def test_desligado_o_vigia_nao_escreve_nada_e_nenhum_jogo_novo_e_anunciado(casa: _Casa) -> None:
    casa.instala_o_jogo_novo()
    casa.desliga()
    assert vigia.garantir(casa.home, config_home=casa.config) == vigia.DESLIGADO
    assert not (casa.unidades / "hefesto-steam-input-guard.path.d").exists()
    assert vigia.jogos_novos_a_receber(casa.home, config_home=casa.config) == []


def test_desligar_depois_de_ligado_tira_os_dois_dropins_e_recarrega(casa: _Casa) -> None:
    """Desligar devolve o guarda ao que era: sem isto o drop-in ficava acordando o guarda."""
    chamadas: list[int] = []

    def recarrega() -> bool:
        chamadas.append(1)
        return True

    def garante() -> str:
        return vigia.garantir(casa.home, config_home=casa.config, recarregar=recarrega)

    assert garante() == vigia.ESCRITO
    casa.desliga()
    assert garante() == vigia.DESLIGADO
    assert not (casa.unidades / "hefesto-steam-input-guard.path.d" / "caminhos.conf").exists()
    assert not (casa.unidades / "hefesto-steam-input-guard.service.d" / "ritmo.conf").exists()
    assert chamadas == [1, 1]
    assert garante() == vigia.DESLIGADO
    assert chamadas == [1, 1]


def test_o_appid_do_jogo_novo_vem_do_appmanifest_e_a_ferramenta_da_steam_fica_de_fora(
    casa: _Casa,
) -> None:
    casa.instala_o_jogo_novo()
    _manifesto(casa.steam / "steamapps", "3333333", "Proton 9.0")
    assert sorted(vigia.jogos_novos_a_receber(casa.home, config_home=casa.config)) == [VELHO, NOVO]


def test_o_jogo_instalado_sem_bloco_ganha_o_bloco_na_arvore_canonica_e_so_nela() -> None:
    novo, criados = slo.garantir_blocos_no_texto(_vdf(), [NOVO, VELHO, "abc"])
    assert criados == [NOVO]
    assert set(slo.read_apps_by_appid(novo)) == {VELHO, NOVO}
    assert slo.read_apps_by_appid(novo)[NOVO] is None
    assert novo.count(f'"{NOVO}"') == 1
    assert slo.garantir_blocos_no_texto(novo, [NOVO]) == (novo, [])


def test_arvore_canonica_ausente_ou_duplicada_nao_cria_bloco() -> None:
    assert slo.garantir_blocos_no_texto('"x"\n{\n}\n', [NOVO])[1] == []
    duas = _vdf() + _vdf()
    assert slo.garantir_blocos_no_texto(duas, [NOVO]) == (duas, [])


def test_o_wrapper_chega_ao_jogo_novo_so_com_o_appmanifest() -> None:
    sem, aplicados, _ = slo.apply_wrapper_vdf_text(_vdf())
    assert NOVO not in aplicados and NOVO not in slo.read_apps_by_appid(sem)
    novo, aplicados, _ = slo.apply_wrapper_vdf_text(_vdf(), instalados=[NOVO])
    assert NOVO in aplicados
    assert slo.WRAPPER_PREFIX in (slo.read_apps_by_appid(novo)[NOVO] or "")
    sem_bloco, aplicados, _ = slo.apply_wrapper_vdf_text(
        _vdf(), instalados=[NOVO], excluir=[NOVO])
    assert NOVO not in slo.read_apps_by_appid(sem_bloco) and NOVO not in aplicados


def test_a_ponte_liga_o_steam_input_do_jogo_novo_e_antes_recusava_como_desconhecido() -> None:
    _, ligados, pulados = ponte.ligar_no_texto(_vdf(), [NOVO])
    assert ligados == [] and pulados == [(NOVO, ponte.JOGO_DESCONHECIDO)]
    novo, ligados, pulados = ponte.ligar_no_texto(_vdf(), [NOVO], [NOVO])
    assert ligados == [NOVO] and pulados == []
    assert ponte.conferir_escrita(_vdf(), novo, ligados) is None


def test_a_tabela_chega_ao_jogo_novo_com_a_steam_fechada_e_a_releitura_confere(
    casa: _Casa,
) -> None:
    casa.instala_o_jogo_novo()
    opj.gravar({NOVO: OPCOES}, config_home=casa.config)
    relato = opj.aplicar(casa.home, config_home=casa.config, estado_home=casa.home / "estado")
    assert relato["status"] == opj.APLICADO, relato
    linha = slo.read_launch_options_by_appid(casa.texto())[NOVO]
    assert slo.WRAPPER_PREFIX in linha and "DXVK_ASYNC=1" in linha
    assert opj.conferir(
        casa.home, config_home=casa.config, estado_home=casa.home / "estado")["defeitos"] == []


def test_desligado_a_tabela_nao_cria_bloco_e_o_arquivo_fica_byte_a_byte(casa: _Casa) -> None:
    casa.instala_o_jogo_novo()
    casa.desliga()
    opj.gravar({NOVO: OPCOES}, config_home=casa.config)
    antes = casa.texto()
    relato = opj.aplicar(casa.home, config_home=casa.config, estado_home=casa.home / "estado")
    assert casa.texto() == antes
    assert any(p["reason"] == "jogo_nao_esta_neste_vdf" for p in relato["pulados"])


def test_o_reparo_poe_o_wrapper_no_jogo_novo(casa: _Casa) -> None:
    casa.instala_o_jogo_novo()
    status, _, resultado = sdw.reparar_ou_adiar(casa.home, registro=casa.home / "visto.json")
    assert status == sdw.REPARO_FEITO and resultado is not None
    assert [a["appid"] for a in resultado["applied"]] == [NOVO]
    assert slo.WRAPPER_PREFIX in (slo.read_apps_by_appid(casa.texto())[NOVO] or "")


def test_desligado_o_reparo_nao_toca_o_arquivo(casa: _Casa) -> None:
    casa.instala_o_jogo_novo()
    casa.desliga()
    antes = casa.texto()
    status, _, _ = sdw.reparar_ou_adiar(casa.home, registro=casa.home / "visto.json")
    assert status == sdw.REPARO_NADA and casa.texto() == antes


def test_a_ponte_de_ponta_a_ponta_liga_o_jogo_da_lista_que_a_steam_nao_abriu(casa: _Casa) -> None:
    casa.instala_o_jogo_novo()
    status, _, detalhe = ponte.garantir_ponte(
        casa.home, allowlist=[NOVO], config_home=casa.config)
    assert status == ponte.PONTE_LIGADA, detalhe
    arvores = ponte.ler_arvores(casa.texto())
    viva = ponte.arvore_viva(arvores)
    assert viva is not None and viva.chaves[NOVO][0].strip() == ponte.LIGADO


def test_o_guarda_acorda_o_vigia_primeiro_em_toda_passada_do_reparo(
    casa: _Casa, capsys: pytest.CaptureFixture[str]
) -> None:
    assert sdw.main(["--reparar"]) == 0
    assert "vigia do jogo novo: escrito" in capsys.readouterr().out
    assert f"userdata/{CONTA}/config/localconfig.vdf" in casa.dropin()

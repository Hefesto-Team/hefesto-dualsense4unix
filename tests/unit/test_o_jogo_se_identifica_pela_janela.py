"""**LANCADOR-AGNOSTICO-01 — a derivação que caiu no dia em que ela abriu o jogo.**"""

from __future__ import annotations

import json
import pathlib

from hefesto_dualsense4unix.integrations.identidade_de_janela import (
    classe_de_janela,
    classe_do_umu_id,
    umu_por_chave_do_heroic,
)

UMU_DO_GOTG = "umu-1088850"
JANELA_DO_GOTG = "steam_app_1088850"

EXECUTAVEL_DO_GOTG = "retail/gotg.exe"

APP_NAME = "63a665088eb1480298f1e57943b225d8"


class TestOParQueDerrubouADerivacao:
    def test_o_umu_id_vira_a_classe_da_janela(self):
        """O fato central, e ele é o par medido nas duas pontas."""
        assert classe_do_umu_id(UMU_DO_GOTG) == JANELA_DO_GOTG

    def test_o_executavel_nao_e_a_classe(self):
        """**A RÉGUA QUE IMPEDE A DERIVAÇÃO DE VOLTAR.**"""
        basename = EXECUTAVEL_DO_GOTG.rsplit("/", 1)[-1]
        assert basename == "gotg.exe"
        assert basename != JANELA_DO_GOTG, (
            "a derivação pelo executável voltou — e ela nunca casou com a "
            "janela que o Heroic anuncia")


class TestOsTresDegraus:
    def test_1_o_umu_vence(self):
        """O umu-id vem do lançador que ELA usou; o appid da Steam é o que a"""
        assert classe_de_janela(
            umu_id=UMU_DO_GOTG, appid_da_steam="999999") == JANELA_DO_GOTG

    def test_2_sem_umu_vale_o_appid_da_steam(self):
        """O caminho que já funcionava continua funcionando — toda cura aqui é"""
        assert classe_de_janela(appid_da_steam="3357650") == "steam_app_3357650"

    def test_3_o_nao_sei_e_resposta(self):
        """**O TERCEIRO DEGRAU É ENTREGA, TANTO QUANTO OS OUTROS DOIS.**"""
        assert classe_de_janela() == ""
        assert classe_de_janela(umu_id="", appid_da_steam="") == ""

    def test_o_umu_default_nao_vira_chave(self):
        """`umu-default` é o id que o umu usa quando NÃO conhece o jogo. O"""
        assert classe_do_umu_id("umu-default") == ""
        assert classe_de_janela(umu_id="umu-default") == ""

    def test_lixo_nao_vira_chave(self):
        for entrada in ("", "   ", "1088850", "steam_app_1088850", "umu-"):
            assert classe_do_umu_id(entrada) == "", entrada


class TestOLeitorDoUmuDoHeroic:
    def _cache(self, tmp_path: pathlib.Path, dado: object) -> pathlib.Path:
        (tmp_path / "umu.json").write_text(
            json.dumps(dado), encoding="utf-8")
        return tmp_path

    def test_o_prefixo_do_runner_e_recortado(self, tmp_path):
        """O Heroic guarda `legendary_<app_name>`; o censo conhece o jogo pelo"""
        cache = self._cache(
            tmp_path, {f"legendary_{APP_NAME}": UMU_DO_GOTG})
        assert umu_por_chave_do_heroic(cache) == {APP_NAME: UMU_DO_GOTG}

    def test_o_timestamp_nao_e_jogo(self, tmp_path):
        """**O `__timestamp` DO HEROIC MORA NO MESMO DICIONÁRIO**, e o valor"""
        cache = self._cache(tmp_path, {
            f"legendary_{APP_NAME}": UMU_DO_GOTG,
            "__timestamp": {f"legendary_{APP_NAME}": "Thu Sep 10 2026"},
        })
        assert umu_por_chave_do_heroic(cache) == {APP_NAME: UMU_DO_GOTG}

    def test_sem_arquivo_cai_vazio_e_calado(self, tmp_path):
        """Heroic nunca aberto, ou nenhum jogo que o umu conheça, é estado"""
        assert umu_por_chave_do_heroic(tmp_path) == {}

    def test_arquivo_quebrado_cai_vazio_e_calado(self, tmp_path):
        (tmp_path / "umu.json").write_text("{ isto não é json", encoding="utf-8")
        assert umu_por_chave_do_heroic(tmp_path) == {}
        (tmp_path / "umu.json").write_text("[1, 2, 3]", encoding="utf-8")
        assert umu_por_chave_do_heroic(tmp_path) == {}


class TestOCensoUsaODonoENaoDeriva:
    def test_a_propriedade_delega(self):
        """**A CURA ESCRITA E NUNCA LIGADA** é o defeito mais caro desta casa."""
        from hefesto_dualsense4unix.integrations.censo_dos_lancadores import (
            JogoDoLancador,
        )

        jogo = JogoDoLancador(
            chave=APP_NAME, nome="Marvel's Guardians of the Galaxy",
            loja="Epic", instalado=True,
            executavel=EXECUTAVEL_DO_GOTG, umu_id=UMU_DO_GOTG)
        assert jogo.classe_de_janela == JANELA_DO_GOTG

    def test_a_rom_do_emulador_nao_inventa_chave(self):
        """Os três emuladores (RetroArch, Dolphin, mGBA) são UM processo para"""
        from hefesto_dualsense4unix.integrations.censo_dos_lancadores import (
            JogoDoLancador,
        )

        jogo = JogoDoLancador(
            chave="uma-rom", nome="Uma ROM", loja="RetroArch", instalado=True)
        assert jogo.classe_de_janela == ""

    def test_o_exe_sem_umu_tambem_nao_inventa_chave(self):
        """**O CASO QUE DERRUBOU A DERIVAÇÃO, sem o umu para salvar.**"""
        from hefesto_dualsense4unix.integrations.censo_dos_lancadores import (
            JogoDoLancador,
        )

        jogo = JogoDoLancador(
            chave="sem-umu", nome="Um jogo Windows", loja="Epic",
            instalado=True, executavel="retail/gotg.exe")
        assert jogo.classe_de_janela == ""

    def test_o_nativo_linux_ainda_ganha_o_palpite(self):
        """**O TERCEIRO DEGRAU EXISTE PARA NÃO ENCOLHER O QUE FUNCIONAVA.**"""
        from hefesto_dualsense4unix.integrations.censo_dos_lancadores import (
            JogoDoLancador,
        )

        jogo = JogoDoLancador(
            chave="sea-of-stars", nome="Sea of Stars", loja="Lutris",
            instalado=True, executavel="/jogos/sea-of-stars/seaofstars")
        assert jogo.classe_de_janela == "seaofstars"

    def test_o_heroic_le_o_umu_json(self):
        """MORDIDA: tire o `umu_id=umu.get(chave, "")` do `_heroic`. A leitura"""
        fonte = pathlib.Path(
            "src/hefesto_dualsense4unix/integrations/censo_dos_lancadores.py"
        ).read_text(encoding="utf-8")
        i = fonte.index("def _heroic(")
        corpo = fonte[i : fonte.index("\ndef ", i + 10)]
        assert "umu_por_chave_do_heroic(cache)" in corpo, (
            "o Heroic não lê o mapa do umu")
        assert "umu_id=umu.get(chave" in corpo, (
            "o mapa é lido e não chega ao jogo")


class TestOPerfilQueJaNasceuTortoSeConserta:
    """**Curar a origem faz o PRÓXIMO perfil nascer certo.**"""

    def _perfil(self, classes):
        from hefesto_dualsense4unix.profiles.schema import (
            MatchCriteria,
            Profile,
        )

        return Profile(
            name="Marvel's Guardians of the Galaxy",
            match=MatchCriteria(window_class=list(classes)))

    def _catalogo(self, exe=EXECUTAVEL_DO_GOTG, chave=JANELA_DO_GOTG):
        from hefesto_dualsense4unix.integrations.censo_dos_lancadores import (
            JogoDoLancador,
        )

        jogo = JogoDoLancador(
            chave=APP_NAME, nome="Marvel's Guardians of the Galaxy",
            loja="Epic", instalado=True, executavel=exe,
            umu_id=UMU_DO_GOTG if chave == JANELA_DO_GOTG else "")
        return [("Heroic", jogo)]

    def _rodar(self, monkeypatch, tmp_path, perfis, catalogo):
        """**O DUBLÊ ESCREVE NO DISCO, e a troca foi medida em 21/09/2026.**"""
        from hefesto_dualsense4unix.profiles import loader

        pasta = tmp_path / "perfis"
        pasta.mkdir(exist_ok=True)
        for perfil in perfis:
            (pasta / f"{perfil.name}.json").write_text(
                perfil.model_dump_json(), encoding="utf-8")
        gravados = []
        monkeypatch.setattr(loader, "profiles_dir", lambda ensure=False: pasta)
        monkeypatch.setattr(
            loader, "save_profile",
            lambda p, **k: gravados.append(p) or pathlib.Path("/x"))
        feitos = loader.reapontar_perfis_com_chave_de_executavel(catalogo)
        return feitos, gravados

    def test_o_gotg_exe_vira_a_janela_de_verdade(self, monkeypatch, tmp_path):
        """O caso dela, exato."""
        feitos, gravados = self._rodar(
            monkeypatch, tmp_path, [self._perfil(["gotg.exe"])], self._catalogo())
        assert feitos == ("Marvel's Guardians of the Galaxy",)
        assert list(gravados[0].match.window_class) == [JANELA_DO_GOTG]

    def test_duas_entradas_e_escolha_de_alguem(self, monkeypatch, tmp_path):
        """Uma regra com duas classes ninguém derivou — foi escrita."""
        feitos, gravados = self._rodar(
            monkeypatch, tmp_path, [self._perfil(["gotg.exe", "outra"])],
            self._catalogo())
        assert feitos == () and gravados == []

    def test_o_nativo_nao_e_tocado(self, monkeypatch, tmp_path):
        """Só o `.exe` é suspeito: ele vai por Proton, e aí quem nomeia a"""
        feitos, gravados = self._rodar(
            monkeypatch, tmp_path, [self._perfil(["seaofstars"])],
            self._catalogo(exe="seaofstars", chave="seaofstars"))
        assert feitos == () and gravados == []

    def test_sem_reconhecer_nao_chuta(self, monkeypatch, tmp_path):
        """Sem o jogo no censo não há para onde reapontar, e chutar repetiria o"""
        feitos, gravados = self._rodar(
            monkeypatch, tmp_path, [self._perfil(["outrojogo.exe"])], self._catalogo())
        assert feitos == () and gravados == []

    def test_o_igual_nao_regrava(self, monkeypatch, tmp_path):
        """Regravar um perfil idêntico troca a data do arquivo por nada — a
        mesma guarda do `_lembrar_do_som`.

        MORDIDA: tire a comparação `nova == velha`.
        """
        feitos, gravados = self._rodar(
            monkeypatch, tmp_path, [self._perfil(["mesmo.exe"])],
            self._catalogo(exe="mesmo.exe", chave="mesmo.exe"))
        assert feitos == () and gravados == []

    def test_o_gancho_do_daemon_chama(self):
        """**A CURA ESCRITA E NUNCA LIGADA.**"""
        fonte = pathlib.Path(
            "src/hefesto_dualsense4unix/profiles/loader.py"
        ).read_text(encoding="utf-8")
        assert "reapontar_perfis_com_chave_de_executavel()" in fonte, (
            "a migração existe e ninguém a chama")
        i = fonte.index("semear_perfis_dos_jogos()")
        assert "reapontar_perfis_com_chave_de_executavel()" in fonte[i:i + 900]


class TestJogoEmFocoNaoPerguntaSeEDaSteam:
    """**«É um jogo em foco?» parou de significar «é da Steam?» — 21/09/2026.**"""

    def _daemon(self, classe):
        from hefesto_dualsense4unix.daemon.lifecycle import Daemon

        d = Daemon.__new__(Daemon)
        d.store = type("S", (), {"window_detect_current_class": classe})()
        return d

    def test_o_jogo_da_steam_continua_respondendo_sim(self):
        """Nada do caminho que funcionava mudou — a cura é aditiva."""
        assert self._daemon("steam_app_3357650")._janela_de_jogo_em_foco()

    def test_o_jogo_por_umu_ja_cai_no_primeiro_degrau(self):
        """O Heroic com Proton anuncia `steam_app_<N>` — ele nunca precisou do"""
        assert self._daemon(JANELA_DO_GOTG)._janela_de_jogo_em_foco()

    def test_o_cliente_steam_continua_contando(self):
        """VPAD-NA-JANELA-DA-STEAM-01: conferir um preço no meio da partida não"""
        assert self._daemon("steam")._janela_de_jogo_em_foco()

    def test_o_jogo_nativo_de_outro_lancador_passou_a_contar(self, monkeypatch, tmp_path):
        """**O DEGRAU QUE NASCEU.** Um jogo nativo Linux do Lutris não tem"""
        from hefesto_dualsense4unix.integrations import jogos_locais as jl

        achado = type("J", (), {"nome": "Celeste", "chave": "celeste.x86_64"})()
        monkeypatch.setattr(jl, "jogos_de_janela", lambda *a, **k: [achado])
        monkeypatch.setattr(
            jl, "jogo_da_janela",
            lambda classe, jogos: achado if classe == "Celeste.x86_64" else None)

        assert self._daemon("Celeste.x86_64")._janela_de_jogo_em_foco()

    def test_o_navegador_continua_nao_sendo_jogo(self, monkeypatch, tmp_path):
        """**A RÉGUA QUE IMPEDE A CURA DE PASSAR DO PONTO.** Se tudo virar"""
        from hefesto_dualsense4unix.integrations import jogos_locais as jl

        monkeypatch.setattr(jl, "jogos_de_janela", lambda *a, **k: [])
        monkeypatch.setattr(jl, "jogo_da_janela", lambda *a, **k: None)

        assert not self._daemon("firefox")._janela_de_jogo_em_foco()

    def test_disco_hostil_nao_derruba_o_daemon(self, monkeypatch, tmp_path):
        """Quem chama decide operação de vpad; o lado seguro de uma falha de"""
        from hefesto_dualsense4unix.integrations import jogos_locais as jl

        def _explode(*a, **k):
            raise OSError("disco hostil")

        monkeypatch.setattr(jl, "jogos_de_janela", _explode)
        assert not self._daemon("qualquer")._janela_de_jogo_em_foco()

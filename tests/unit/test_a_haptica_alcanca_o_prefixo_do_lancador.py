"""**A háptica nativa não chegava a jogo nenhum de fora da Steam.**"""

from __future__ import annotations

import ast
import json
import pathlib

from hefesto_dualsense4unix.integrations import camadas_vulkan as cv

HEROIC = ".var/app/com.heroicgameslauncher.hgl/config/heroic"
APP_NAME = "63a665088eb1480298f1e57943b225d8"


def _prefixo(raiz: pathlib.Path, nome: str) -> pathlib.Path:
    alvo = raiz / nome / "pfx"
    alvo.mkdir(parents=True, exist_ok=True)
    (alvo / "system.reg").write_text("WINE REGISTRY\n", encoding="utf-8")
    return raiz / nome


def _heroic_com(lar: pathlib.Path, por_jogo: str = "", raiz_comum: str = ""):
    pasta = lar / HEROIC
    (pasta / "GamesConfig").mkdir(parents=True, exist_ok=True)
    if por_jogo:
        (pasta / "GamesConfig" / f"{APP_NAME}.json").write_text(
            json.dumps({APP_NAME: {"winePrefix": por_jogo}}), encoding="utf-8")
    conf = {"defaultSettings": {"defaultWinePrefix": raiz_comum}} if raiz_comum else {}
    (pasta / "config.json").write_text(json.dumps(conf), encoding="utf-8")
    return pasta


class TestOPrefixoDoHeroicEAchado:
    def test_o_prefixo_por_jogo_entra(self, tmp_path):
        """O `GamesConfig/<app_name>.json` é o mais exato: ele alcança quem"""
        alvo = _prefixo(tmp_path / "Games", "Marvels Guardians of the Galaxy")
        _heroic_com(tmp_path, por_jogo=str(alvo))
        assert cv.prefixos_dos_lancadores(tmp_path) == [alvo]

    def test_a_raiz_comum_alcanca_quem_nunca_abriu_o_gamesconfig(self, tmp_path):
        """MORDIDA: leia só o `GamesConfig`. Um jogo cujo prefixo nasceu no"""
        raiz = tmp_path / "Games/Heroic/Prefixes"
        alvo = _prefixo(raiz, "Um Jogo")
        _heroic_com(tmp_path, raiz_comum=str(raiz))
        assert cv.prefixos_dos_lancadores(tmp_path) == [alvo]

    def test_o_mesmo_prefixo_nao_conta_duas_vezes(self, tmp_path):
        """As duas fontes se sobrepõem no caso comum, e contar em dobro faria a"""
        raiz = tmp_path / "Games/Heroic/Prefixes"
        alvo = _prefixo(raiz, "Marvels Guardians of the Galaxy")
        _heroic_com(tmp_path, por_jogo=str(alvo), raiz_comum=str(raiz))
        assert cv.prefixos_dos_lancadores(tmp_path) == [alvo]

    def test_pasta_sem_system_reg_nao_e_prefixo(self, tmp_path):
        """Uma pasta solta dentro de `Prefixes/` não é prefixo wine. Escrever"""
        raiz = tmp_path / "Games/Heroic/Prefixes"
        (raiz / "vazia").mkdir(parents=True)
        _heroic_com(tmp_path, raiz_comum=str(raiz))
        assert cv.prefixos_dos_lancadores(tmp_path) == []

    def test_sem_heroic_devolve_vazio_e_nao_levanta(self, tmp_path):
        assert cv.prefixos_dos_lancadores(tmp_path) == []

    def test_json_torto_nao_derruba(self, tmp_path):
        """Disco hostil devolve menos prefixos, nunca uma exceção — quem chama"""
        pasta = _heroic_com(tmp_path, raiz_comum="")
        (pasta / "config.json").write_text("{ isto não é json", encoding="utf-8")
        (pasta / "GamesConfig" / "x.json").write_text("[[[", encoding="utf-8")
        assert cv.prefixos_dos_lancadores(tmp_path) == []


class TestAHapticaPercorreTodosOsPrefixos:
    def test_a_haptica_usa_raizes_de_prefixo(self):
        """**A CURA ESCRITA E NUNCA LIGADA.**"""
        fonte = pathlib.Path(
            "src/hefesto_dualsense4unix/integrations/audio_ks_dualsense.py"
        ).read_text(encoding="utf-8")
        i = fonte.index("def prefixos_de_todas_as_bibliotecas(")
        corpo = fonte[i : fonte.index("\ndef ", i + 10)]
        assert "cv.raizes_de_prefixo()" in corpo
        assert "cv.pastas_compatdata()" not in corpo

    def test_o_censo_de_camadas_nao_filtra_por_appid_numerico(self):
        """O `isdigit()` era a assinatura da Steam escrita no filtro: só"""
        fonte = pathlib.Path(
            "src/hefesto_dualsense4unix/integrations/camadas_vulkan.py"
        ).read_text(encoding="utf-8")
        corpo = next(
            ast.get_source_segment(fonte, no) or ""
            for no in ast.walk(ast.parse(fonte))
            if isinstance(no, ast.FunctionDef) and no.name == "censo")
        assert "raizes_de_prefixo(home)" in corpo
        assert "raiz.name.isdigit()" not in corpo

    def test_a_ordenacao_nao_levanta_com_nome_de_pasta(self, monkeypatch, tmp_path):
        """**UMA ORDENAÇÃO QUE LEVANTA DERRUBA A ABA INTEIRA** por causa de um"""
        alvo = _prefixo(tmp_path, "Um Jogo Do Heroic")
        (alvo / "pfx" / "system.reg").write_text(
            'implicit_layer_here\n"VK_LAYER_X"=dword:00000000\n', encoding="utf-8")
        monkeypatch.setattr(cv, "raizes_de_prefixo", lambda *a, **k: [alvo])
        monkeypatch.setattr(
            cv, "prefixo_de_jogo",
            lambda raiz: cv.PrefixoDeJogo(
                appid=raiz.name, raiz=raiz,
                registro=raiz / "pfx/system.reg", camadas=("VK_LAYER_X",)))
        saida = cv.censo(tmp_path)
        assert [c.appid for c in saida] == ["Um Jogo Do Heroic"]
        assert saida[0].nome == "Um Jogo Do Heroic"

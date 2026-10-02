"""**A CURA ESCRITA E NUNCA LIGADA — e esta ficou órfã por ONZE DIAS.**"""

from __future__ import annotations

import pathlib

from hefesto_dualsense4unix.integrations import cura_por_estrada as cpe

LAUNCH_ENV = pathlib.Path("src/hefesto_dualsense4unix/daemon/launch_env.py")


class TestOModuloDeixouDeSerOrfao:
    def test_o_materializador_chama_a_cura(self):
        """**A RÉGUA QUE IMPEDE A ÓRFÃ DE VOLTAR.**"""
        fonte = LAUNCH_ENV.read_text(encoding="utf-8")
        i = fonte.index("def materialize_launch_env(")
        corpo = fonte[i : fonte.index("\n# ---", i)]
        assert "curar_todas_as_estradas()" in corpo, (
            "o materializador não reescreve as estradas dos outros lançadores")

    def test_a_carona_vai_dentro_do_try(self):
        """A função já promete nunca levantar, e o `except` da borda é a"""
        fonte = LAUNCH_ENV.read_text(encoding="utf-8")
        i = fonte.index("def materialize_launch_env(")
        corpo = fonte[i : fonte.index("\n# ---", i)]
        assert corpo.index("curar_todas_as_estradas()") < corpo.index(
            'logger.warning("launch_env_materialize_falhou"'), (
            "a carona saiu de dentro da rede do `try`")


class TestACuraPercorreTodosOsCartoes:
    def test_os_cinco_cartoes_estao_na_lista(self):
        """A Steam NÃO entra — ela tem o atalho de inicialização, que é a"""
        chaves = [c for c, _ in cpe.cartoes_com_estrada()]
        assert "steam" not in chaves
        assert set(chaves) == {"heroic", "lutris", "retroarch", "dolphin", "mgba"}

    def test_a_lista_e_lida_do_censo_e_nao_digitada(self):
        """**UMA SEGUNDA CÓPIA DIVERGIRIA**, e o sintoma seria o pior desta"""
        from hefesto_dualsense4unix.integrations.censo_dos_lancadores import _ONDE

        do_censo = {nome.casefold(): (a, s) for nome, (a, s) in _ONDE.items()}
        assert dict(cpe.cartoes_com_estrada()) == do_censo

    def test_nunca_levanta_com_disco_hostil(self, monkeypatch):
        """Quem chama é a borda de materialização do daemon."""
        def _explode(*a, **k):
            raise OSError("disco hostil")

        monkeypatch.setattr(cpe, "planejar", _explode)
        assert cpe.curar_todas_as_estradas() == ()

    def test_o_cartao_sem_ambiente_e_pulado_sem_levantar(self, monkeypatch, tmp_path):
        """Daemon parado = sem `default.env` = nada a escrever. Não é falha:"""
        escreveu = []
        monkeypatch.setattr(
            cpe, "escrever_a_estrada", lambda p: escreveu.append(p) or "ok")
        assert cpe.curar_todas_as_estradas(pasta_do_ambiente=tmp_path) == ()
        assert escreveu == []

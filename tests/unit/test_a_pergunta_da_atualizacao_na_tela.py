"""A pergunta da atualização, o andamento e a seção da aba Sistema, ligados ao motor.

O-HEFESTO-SE-ATUALIZA-INTEIRO-01, volta 1 (08/11/2026), no desenho de
``mockup/escolha/a-pergunta-da-atualizacao.html`` (arranjo A) e de
``mockup/escolha/09-sistema-com-atualizacoes.html``. O lar é ``tmp_path`` com ``XDG_*`` desviados;
o registro das peças é dublado e a fila não abre processo (``soltar`` dublado).

AS MORDIDAS (feitas na sprint, com a cura devolvida): o «Atualizar N» que conta também as
desmarcadas reprova o caso da contagem; a marca que age no clique e na troca reprova o caso do
duplo; a caixa que repinta a cada tique reprova o caso da ponte; a leitura de antes do fechar que
ainda pinta reprova o caso da leitura velha; o motivo da falha escrito na linha em vez da dica
reprova o caso da falha.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions import atualizador as at
from hefesto_dualsense4unix.interface import atualizacoes as tela
from hefesto_dualsense4unix.interface import pacotes
from hefesto_dualsense4unix.interface.pacotes import atualizacoes as gestos


@pytest.fixture(autouse=True)
def lar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    casa = tmp_path / "casa"
    for var, sub in (("XDG_CONFIG_HOME", ".config"), ("XDG_STATE_HOME", ".local/state"),
                     ("XDG_CACHE_HOME", ".cache"), ("XDG_DATA_HOME", ".local/share"),
                     ("XDG_RUNTIME_DIR", "run")):
        (casa / sub).mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv(var, str(casa / sub))
    monkeypatch.setenv("HOME", str(casa))
    monkeypatch.setattr(gestos, "TELA", {"vista": "", "perguntou": False, "escondida": 0.0,
                                         "lido_em": 0.0, "enviado": "", "aba": "",
                                         "vez": 0, "calculado": None,
                                         "calculando": False})
    return casa


def _peca(ident: str, *, de: str = "1.0", para: str = "1.1", grupo: str = "infra",
          volta: int = 1) -> at.Peca:
    def nada(_passo: at.Passo, _dados: dict[str, Any]) -> None:
        return None

    return at.Peca(ident, ident.capitalize(), f"dica de {ident}", "todos",
                   lambda _rede: at.Versoes(de, para), nada, nada, nada, grupo=grupo,
                   volta=volta)


LISTA = [_peca("hefesto", grupo="hefesto"), _peca("proton"), _peca("python"),
         _peca("kernel", para="1.0"), _peca("bluetooth", volta=2)]


@pytest.fixture
def registro(monkeypatch: pytest.MonkeyPatch) -> list[at.Peca]:
    monkeypatch.setattr(at, "pecas", lambda: list(LISTA))
    at.conferir(rede=True, lista=LISTA)
    return LISTA


class _Ponte:
    def __init__(self) -> None:
        self.scripts: list[str] = []

    def rodar(self, script: str) -> None:
        self.scripts.append(script)


def _ctx() -> pacotes.Contexto:
    return pacotes.Contexto(state={})


def _gesto(nome: str, **o: Any) -> Any:
    return pacotes.GESTOS[("*", nome)](_ctx(), o, None)


def test_a_pergunta_tem_o_hefesto_em_cima_e_o_grupo_marcavel(registro: list[at.Peca]) -> None:
    at.mudar_a_escolha(peca="python", marcada=False)
    corpo = tela.html_da_pergunta(gestos.conferencia_vista(), {"sozinho": False, "dias": 7},
                                  jogo_aberto=False)
    nomes = re.findall(r'class="at-n"[^>]*>([^<]+)<', corpo)
    assert nomes[0] == "Hefesto" and nomes[1] == tela.ROTULO_DO_GRUPO
    assert "Bluetooth" in nomes and "Kernel" in nomes
    assert 'data-v="bluetooth"' not in corpo
    assert re.search(r'Atualizar <span class="n">2</span>', corpo)
    assert re.search(r'<label class="at-l filho de-fora"><input type="checkbox" '
                     r'data-gesto="peca-da-atualizacao" data-v="python">', corpo)
    assert "data-meio" in corpo
    assert gestos.tela.ids_para_atualizar(gestos.conferencia_vista()) == ["hefesto", "proton"]


def test_com_jogo_aberto_a_pergunta_espera(registro: list[at.Peca]) -> None:
    corpo = tela.html_da_pergunta(gestos.conferencia_vista(), {"sozinho": True, "dias": 7},
                                  jogo_aberto=True)
    assert 'class="pendente"' in corpo
    assert "Atualizar ao fechar o jogo" in corpo
    assert 'class="cadeado ligada"' in corpo


def test_a_marca_age_so_na_troca_e_guarda_a_escolha(registro: list[at.Peca]) -> None:
    _gesto("peca-da-atualizacao", v="proton", evento="click")
    assert at.ler_a_escolha().marcadas.get("proton") is None
    _gesto("peca-da-atualizacao", v="proton", evento="change")
    assert at.ler_a_escolha().marcadas["proton"] is False
    _gesto("peca-da-atualizacao", v="proton", evento="change")
    assert at.ler_a_escolha().marcadas["proton"] is True
    with pytest.raises(ValueError):
        _gesto("peca-da-atualizacao", v="bluetooth", evento="change")
    _gesto("pecas-do-grupo", v="0", evento="change")
    assert gestos.tela.ids_para_atualizar(gestos.conferencia_vista()) == ["hefesto"]


def test_o_sozinho_e_o_prazo_ficam_guardados(registro: list[at.Peca]) -> None:
    _gesto("atualizar-sozinho")
    assert at.ler_a_escolha().sozinho is True
    _gesto("prazo-da-atualizacao", v="1")
    assert at.ler_a_escolha().dias == at.DIAS_PADRAO + 1
    for _ in range(at.DIAS_PADRAO + 5):
        _gesto("prazo-da-atualizacao", v="-1")
    assert at.ler_a_escolha().dias == at.DIAS_MINIMO


def test_atualizar_solta_so_as_marcadas(registro: list[at.Peca],
                                        monkeypatch: pytest.MonkeyPatch) -> None:
    soltas: list[list[str]] = []
    monkeypatch.setattr(at, "soltar", lambda ids, **_k: soltas.append(list(ids)) or True)
    at.mudar_a_escolha(peca="proton", marcada=False)
    gestos.TELA["vista"] = "pergunta"
    _gesto("atualizacoes-atualizar")
    assert soltas == [["hefesto", "python"]]
    assert gestos.TELA["vista"] == ""
    assert at.ler_a_escolha().perguntada_em > 0


def _andamento(selo: str, motivo: str = "") -> dict[str, Any]:
    return {"inicio": 123.0, "pecas": [
        {"id": "kernel", "nome": "Kernel", "de": "7.2.15", "para": "7.2.18", "etapas":
         {"baixar": "feito", "instalar": "erro" if selo == "falhou" else "feito"}, "pct": 55,
         "selo": selo, "motivo": motivo, "contagens": []},
        {"id": "proton", "nome": "GE-Proton", "de": "11-7", "para": "11-12", "etapas": {},
         "pct": 90, "selo": "aplicando", "motivo": "", "contagens":
         [{"qual": "Steam", "feitos": 41, "de": 58}]}],
        "total": {"feitas": 0, "de": 2, "pct": 40, "falhas": 1 if selo == "falhou" else 0},
        "reinicio": {"etapas": {}, "pct": 0, "selo": "fila"}}


def test_a_falha_diz_o_porque_na_dica_e_oferece_tentar_de_novo() -> None:
    corpo = tela.html_do_andamento(_andamento("falhou", "o apt não instalou"), rodando=True)
    assert 'data-dica="o apt não instalou"' in corpo
    assert ">o apt não instalou<" not in corpo
    assert 'data-gesto="atualizacoes-tentar"' in corpo
    assert '<span class="etp erro">Instalar</span>' in corpo
    assert "41/58" in corpo and "1 falhou" in corpo
    assert 'data-gesto="atualizacoes-parar"' in corpo
    fim = tela.html_do_andamento(_andamento("pronta"), rodando=False)
    assert "atualizacoes-tentar" not in fim and "atualizacoes-parar" not in fim


def _tique(ponte: _Ponte, pagina: str) -> None:
    gestos.pintar(ponte, pagina, None, em_fundo=False)
    gestos.TELA["lido_em"] = 0.0
    gestos.pintar(ponte, pagina, None, em_fundo=False)


def test_a_caixa_repinta_so_quando_muda(registro: list[at.Peca],
                                        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(at, "hora_da_pergunta", lambda _agora=None: False)
    ponte = _Ponte()
    _tique(ponte, "01-jogar.html")
    _tique(ponte, "01-jogar.html")
    assert ponte.scripts == []
    _gesto("atualizacoes-abrir")
    _tique(ponte, "01-jogar.html")
    _tique(ponte, "01-jogar.html")
    assert len(ponte.scripts) == 1 and "Bibliotecas, drivers e plugins" in ponte.scripts[0]
    _tique(ponte, "09-sistema.html")
    assert len(ponte.scripts) == 2
    _gesto("atualizacoes-fechar")
    _tique(ponte, "09-sistema.html")
    assert len(ponte.scripts) == 3 and '"", "hef-atualizacoes"' in ponte.scripts[2]


def test_a_leitura_velha_nao_reabre_a_caixa_fechada(registro: list[at.Peca]) -> None:
    ponte = _Ponte()
    gestos.TELA["vista"] = "pergunta"
    gestos.pintar(ponte, "01-jogar.html", None, em_fundo=False)
    velho = gestos.TELA["calculado"]
    _gesto("atualizacoes-fechar")
    gestos.TELA["calculado"] = velho
    gestos.pintar(ponte, "01-jogar.html", None, em_fundo=False)
    assert all("Bibliotecas" not in s for s in ponte.scripts)


def test_o_andamento_aparece_em_qualquer_aba_e_o_fim_fechado_nao_volta(
        registro: list[at.Peca], monkeypatch: pytest.MonkeyPatch) -> None:
    andamento = _andamento("pronta")
    andamento["inicio"] = 1000.0
    at._gravar_json(at._estado() / at.ARQUIVO_DO_ANDAMENTO, andamento)
    assert "and-total" in gestos.conteudo(None, agora=1010.0)
    _gesto("atualizacoes-fechar")
    assert at.ler_o_andamento()["visto"] is True
    gestos.TELA["escondida"] = 0.0
    assert gestos.conteudo(None, agora=1020.0) == ""


def test_a_pergunta_nasce_sozinha_uma_vez_quando_o_prazo_vence(
        registro: list[at.Peca], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(at, "hora_da_pergunta", lambda _agora=None: True)
    assert "Agora não" in gestos.conteudo(None)
    _gesto("atualizacoes-agora-nao")
    assert gestos.conteudo(None) == ""


def test_a_grade_da_aba_tem_tres_colunas_e_a_volta_2_sem_marca(registro: list[at.Peca]) -> None:
    grade = tela.grade_da_aba(gestos.conferencia_vista())
    colunas = grade.split('<div class="risco"></div>')
    assert len(colunas) == 3
    assert [c.count('class="saude"') for c in colunas] == [4, 1, 0]
    assert '<input type="checkbox" class="at-marca" disabled>' in grade
    assert grade.count('data-gesto="peca-da-atualizacao"') == 4


def test_a_aba_sistema_tem_a_secao_e_o_reler_atalhos() -> None:
    from hefesto_dualsense4unix.interface import aba09
    from hefesto_dualsense4unix.interface.pacotes import a09_sistema

    assert aba09.ROTULO_ATUALIZAR == "Reler atalhos"
    for campo in (a09_sistema.CAMPO_DO_SOZINHO, a09_sistema.CAMPO_DO_PRAZO,
                  a09_sistema.CAMPO_DAS_NOVAS, a09_sistema.CAMPO_DA_GRADE):
        assert f'data-campo="{campo}"' in aba09.MIOLO
    assert 'data-gesto="atualizacoes-abrir"' in aba09.MIOLO
    campos = a09_sistema.campos_das_atualizacoes()
    assert campos[a09_sistema.CAMPO_DO_PRAZO] == str(at.DIAS_PADRAO)
    assert campos[a09_sistema.CAMPO_DO_SOZINHO] is False

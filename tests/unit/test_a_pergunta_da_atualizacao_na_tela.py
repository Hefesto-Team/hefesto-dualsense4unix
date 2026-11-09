"""O mapa das atualizações, o andamento e a seção da aba Sistema, ligados ao motor.

O-HEFESTO-SE-ATUALIZA-INTEIRO-01, volta 1 (08/11/2026); o mapa é de
AS-ATUALIZACOES-ABREM-NUM-MAPA-COMO-O-DAS-CONEXOES-01 (09/11/2026), no desenho de
``mockup/escolha/o-mapa-das-atualizacoes.html``. O lar é ``tmp_path`` com ``XDG_*`` desviados;
o registro das peças é dublado e a fila não abre processo (``soltar`` dublado).

AS MORDIDAS (feitas na sprint, com a cura devolvida): o «Atualizar N» que conta também as
desmarcadas reprova o caso do mapa; a marca que age no clique e na troca reprova o caso do
duplo; a caixa que repinta a cada tique reprova o caso da ponte; a leitura de antes do fechar que
ainda pinta reprova o caso da leitura velha; o motivo da falha escrito na linha em vez da dica
reprova o caso da falha; o cartão com a versão inteira reprova o caso da versão curta.
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


def test_o_mapa_agrupa_o_que_ha_para_baixar_e_so_a_nova_e_marcavel_inteira(
        registro: list[at.Peca]) -> None:
    at.mudar_a_escolha(peca="python", marcada=False)
    corpo = tela.html_da_pergunta(gestos.conferencia_vista(), {"sozinho": False, "dias": 7},
                                  jogo_aberto=False)
    grupos = re.findall(r'<div class="mp-g ([a-z-]+)"><span>([^<]+)</span>'
                        r'<span class="q">(\d+)</span>', corpo)
    assert grupos == [("nova", "Escolha o que deve ser atualizado", "3"),
                      ("em-dia", "Atualizado", "1"),
                      ("fixa", "Com o Hefesto", "1")]
    nomes = re.findall(r'class="mp-n">([^<]+)<', corpo)
    assert nomes[:3] == ["Hefesto", "Proton", "Python"]
    assert 'data-v="bluetooth"' not in corpo
    assert re.search(r'Atualizar <span class="n">2</span>', corpo)
    assert '<input type="checkbox" class="mp-m" data-gesto="peca-da-atualizacao" ' \
           'data-v="python">' in corpo
    assert re.search(r'<label class="mp-c nova"[^>]*>.*?data-v="proton"', corpo)
    assert re.search(r'<div class="mp-c em-dia"[^>]*>.*?<label class="mp-mx">'
                     r'<input[^>]*data-v="kernel"', corpo)
    assert gestos.tela.ids_para_atualizar(gestos.conferencia_vista()) == ["hefesto", "proton"]


def test_com_jogo_aberto_a_pergunta_espera(registro: list[at.Peca]) -> None:
    corpo = tela.html_da_pergunta(gestos.conferencia_vista(), {"sozinho": True, "dias": 7},
                                  jogo_aberto=True)
    assert 'class="pendente"' in corpo
    assert "Atualizar ao fechar o jogo" in corpo
    assert 'tn-cx mapa auto"' in corpo and "cadeado" not in corpo


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
    assert len(ponte.scripts) == 1 and "Escolha o que deve ser atualizado" in ponte.scripts[0]
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
    assert all("Escolha o que deve ser atualizado" not in s for s in ponte.scripts)


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


def test_o_andamento_ausente_ou_meio_escrito_e_sem_andamento(registro: list[at.Peca]) -> None:
    arquivo = at._estado() / at.ARQUIVO_DO_ANDAMENTO
    for estragado in ('{"pecas": [{"id": "ker', '{"pecas": "x", "inicio": 5}',
                      '{"pecas": [{"id": "k"}], "inicio": "ontem"}', "[]"):
        arquivo.write_text(estragado, encoding="utf-8")
        assert gestos.conteudo(None, agora=10.0) == ""
    arquivo.unlink()
    assert gestos.conteudo(None, agora=10.0) == ""


def test_o_hefesto_nao_tem_voltar_a_anterior() -> None:
    from hefesto_dualsense4unix.app.actions import pecas_do_atualizador as pa

    hefesto = next(p for p in pa.registro() if p.id == "hefesto")
    assert hefesto.voltar is None
    anteriores = {"hefesto": {"nome": "Hefesto", "agora": "0.9.5.2", "anterior": "0.9.5.1"},
                  "kernel": {"nome": "Kernel", "agora": "7.2.18", "anterior": "7.2.15"}}
    voltam = [p.id for p in pa.registro() if p.voltar is not None]
    corpo = tela.html_das_anteriores(anteriores, voltam)
    assert 'data-v="kernel"' in corpo and 'data-v="hefesto"' not in corpo


def test_o_portal_e_a_gdk_sobem_pelo_motor_na_volta_2(monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.app.actions import pecas_do_atualizador as pa

    monkeypatch.setattr(pa, "_instalados", lambda *_p: {
        pa.PACOTE_DO_PORTAL: "1.0.0~1780000000+0~hefesto1"})
    monkeypatch.setattr(pa, "_atualizar_a_lista_do_apt", lambda _rede: None)
    monkeypatch.setattr(pa, "_portal_no_apt", lambda: "1.0.0~1780000000")
    pecas = {p.id: p for p in pa.registro()}
    for ident in ("bluetooth", "som", "portal", "gdk"):
        assert pecas[ident].volta == 1 and pecas[ident].instalar is not None
    versoes = pa.versoes_do_portal(True)
    assert versoes.instalada == "1.0.0"
    assert versoes.completa == "1.0.0~1780000000+0~hefesto1"
    estados = {i["id"]: i["estado"]
               for i in at.conferir(rede=True, lista=[pecas["portal"]])["pecas"]}
    assert estados == {"portal": at.EM_DIA}
    assert tela.ORDEM_NA_TELA.index("gdk") < tela.ORDEM_NA_TELA.index("python")


def test_a_aba_sistema_tem_a_secao_e_o_reler_atalhos() -> None:
    from hefesto_dualsense4unix.interface import aba09
    from hefesto_dualsense4unix.interface.pacotes import a09_sistema

    assert aba09.ROTULO_ATUALIZAR == "Reler atalhos"
    for campo in (a09_sistema.CAMPO_DO_SOZINHO, a09_sistema.CAMPO_DO_PRAZO,
                  a09_sistema.CAMPO_DAS_NOVAS):
        assert f'data-campo="{campo}"' in aba09.MIOLO
    assert 'data-gesto="atualizacoes-abrir"' in aba09.MIOLO
    campos = a09_sistema.campos_das_atualizacoes()
    assert campos[a09_sistema.CAMPO_DO_PRAZO] == str(at.DIAS_PADRAO)
    assert campos[a09_sistema.CAMPO_DO_SOZINHO] is False
    assert campos[a09_sistema.CAMPO_DAS_NOVAS] == ""


def test_no_cartao_a_versao_e_curta_e_a_inteira_vai_a_dica() -> None:
    conferencia = {"pecas": [
        {"id": "nvidia", "nome": "Driver Nvidia", "estado": "nova", "de": "595.104.02",
         "para": "595.110.07", "marcada": True, "volta": 1, "dica": "nvidia-driver-595"},
        {"id": "portal", "nome": "Portal do COSMIC", "estado": "fixa", "volta": 2,
         "de": "1.11.0~1792525517~24.04~f448ddf+0~hefesto1", "dica": "A captura"},
        {"id": "sistema", "nome": "Pacotes do sistema", "estado": "em_dia", "de": "24.04",
         "para": "24.04", "rotulo": "12 pacotes", "marcada": True, "volta": 1}]}
    mapa = tela.html_do_mapa(conferencia)
    assert ('data-dica="nvidia-driver-595 · 595.104.02 → 595.110.07"' in mapa)
    assert ('<span class="mp-v"><span class="par"><span class="de">595.104.02</span>'
            '<span class="seta">→</span></span><span class="nv">595.110.07</span></span>') in mapa
    assert 'data-dica="A captura · 1.11.0~1792525517~24.04~f448ddf+0~hefesto1"' in mapa
    assert '<span class="mp-v"><span class="nv">1.11.0</span></span>' in mapa
    assert '<span class="mp-v"><span class="nv">12 pacotes</span></span>' in mapa
    assert tela.versao_curta("1:2.40-1ubuntu1") == "2.40-1ubuntu1"
    assert tela.versao_curta("11-12") == "11-12"
    caixa = re.sub(r"\s+", "", tela.CSS)
    assert ".hef-atualiza.tn-cx.mapa{width:min(1180px,calc(100vw-32px));" \
           "height:min(668px,calc(100vh-32px));" in caixa


def test_o_jogo_aberto_diz_o_nome_que_a_steam_ja_sabe(registro: list[at.Peca],
                                                     monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    monkeypatch.setattr(slo, "nome_do_appid", lambda appid, home=None:
                        "Jogo um" if appid == "4242" else None)
    monkeypatch.setattr(gestos, "_jogo_aberto", lambda _ctx: True)
    at.conferir(rede=True, lista=LISTA)
    gestos.TELA["vista"] = "pergunta"
    ctx = SimpleNamespace(state={"jogo_steam": {"lido": True, "appid": 4242}})
    html = gestos.conteudo(ctx)
    assert ('<div class="pendente"><span>Jogo aberto:</span><span class="jogo">Jogo um</span>'
            '<span>· espera</span></div>') in html
    for estado in ({"jogo_steam": {"lido": True, "appid": None}}, {}, None):
        html = gestos.conteudo(SimpleNamespace(state=estado))
        assert '<div class="pendente"><span>Jogo aberto</span><span>· espera</span></div>' in html


def test_o_jogo_de_fora_da_steam_diz_o_nome_do_perfil_de_jogo_que_entrou(
        registro: list[at.Peca], monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    from hefesto_dualsense4unix.profiles import schema
    from hefesto_dualsense4unix.profiles.loader import save_profile

    monkeypatch.setattr(schema, "_CLASSES_DE_JOGO_CONHECIDAS",
                        frozenset({"heroic-jogo-de-mentira"}))
    save_profile(schema.Profile(name="Jogo do Heroic",
                                match=schema.MatchCriteria(window_class=["heroic-jogo-de-mentira"]),
                                priority=80))
    save_profile(schema.Profile(name="Outro de jogo", nome_do_jogo="Nome dado na aba",
                                match=schema.MatchCriteria(window_class=["heroic-jogo-de-mentira"]),
                                priority=80))
    save_profile(schema.Profile(name="Só a janela",
                                match=schema.MatchCriteria(window_class=["um-editor"]),
                                priority=10))
    monkeypatch.setattr(gestos, "_jogo_aberto", lambda _ctx: True)
    at.conferir(rede=True, lista=LISTA)
    gestos.TELA["vista"] = "pergunta"

    def pendente(estado: dict[str, Any]) -> str:
        html = gestos.conteudo(SimpleNamespace(state=estado))
        return re.search(r'<div class="pendente">.*?</div>', html).group(0)

    sem_steam = {"jogo_steam": {"lido": True, "appid": None}}
    assert "<span class=\"jogo\">Jogo do Heroic</span>" in pendente(
        {**sem_steam, "active_profile": "Jogo do Heroic"})
    assert "<span class=\"jogo\">Nome dado na aba</span>" in pendente(
        {**sem_steam, "active_profile": "Outro de jogo"})
    for ativo in ("Só a janela", "Perfil que não existe", None):
        assert pendente({**sem_steam, "active_profile": ativo}) == (
            '<div class="pendente"><span>Jogo aberto</span><span>· espera</span></div>')

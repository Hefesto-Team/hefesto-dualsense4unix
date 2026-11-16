"""A janela do Modo imersão sem a coluna «Agora» (16/11/2026).

A-JANELA-DO-MODO-IMERSAO-SEM-A-COLUNA-AGORA-01, decisão D-1611-O-MODO-IMERSAO-TOCA-EM-TODO-JOGO.

O teto do ``mods.acao`` cobre o prazo em que a porta espera a resposta da extensão
(``PRAZO_DA_RESPOSTA_S``, lido da porta): a extensão que responde o «Testar» em 0,6 s chega à
janela, em vez de «O serviço não respondeu. Nada foi enviado.».

A janela troca a coluna pela faixa do alto: a pílula da situação (Tocando, Calado com o
motivo, Esperando um jogo), as ``linhas`` e as três últimas escritas, com o canal e há quanto
tempo. O «Testar» mora no pé do cartão do efeito e mostra o veredito pela cor do plástico; a
``marca`` do efeito vai ao título; cada sentido mostra o medidor das ``leituras``.

MORDIDAS: devolver o ``mods.acao`` ao ``TETO_PADRAO_S`` (0,25 s) reprova a régua da extensão
lenta; a faixa sem a frase da situação reprova o motivo do calado; o ``acoes_por_aba`` com as
ações do cartão reprova o «Testar» repetido na barra; o veredito guardado sem redesenhar a
janela reprova o clique; o cartão com botão que vira a fileira de chaves, o manifesto que aceita o
``cartao`` sem opção, a resposta sem ``{controles}`` lida como «não respondeu» e a faixa calada com
as escritas reprovam cada um a sua régua.
"""
from __future__ import annotations

import contextlib
import json
import pathlib
import re
import shutil
import socket
import tempfile
import threading
import time
from collections.abc import Iterator
from typing import Any

import pytest
from pydantic import ValidationError

from hefesto_dualsense4unix.app import ipc_bridge
from hefesto_dualsense4unix.cli import ipc_client
from hefesto_dualsense4unix.interface import desenho_da_experimental as exp
from hefesto_dualsense4unix.interface.pacotes import ponte
from hefesto_dualsense4unix.mods import porta as modulo_da_porta
from hefesto_dualsense4unix.mods.manifesto import Acao, AcoesDosAparelhos, Opcao
from tests.unit.test_a_aba_lancadores_ganha_as_modificacoes import ctx, lar  # noqa: F401
from tests.unit.test_a_janela_da_extensao_age_e_gere_os_aparelhos import (  # noqa: F401
    _Ponte,
    janela,
)

SITUACAO = "situacao"  # (noqa-acento)
OPCAO = "opcao"  # (noqa-acento)
PADRAO = "padrao"  # (noqa-acento)
ACOES = "acoes"  # (noqa-acento)
ID_DO_CORACAO = "coracao"  # (noqa-acento)
VEREDITO = {"controles": [{"uniq": "aa:bb:cc:00:00:91", "nome": "Cosmic Red", "tocou": True,
                           "motivo": None}]}


@pytest.fixture
def curto() -> Iterator[pathlib.Path]:
    pasta = pathlib.Path(tempfile.mkdtemp(prefix="jm"))
    try:
        yield pasta
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


class _ServicoLento:
    """O serviço de mentira: responde o ``mods.acao`` depois de ``atraso`` segundos, como a porta
    que espera a extensão responder o teste."""

    def __init__(self, caminho: pathlib.Path, atraso: float) -> None:
        self.sock = socket.socket(socket.AF_UNIX)
        self.sock.bind(str(caminho))
        self.sock.listen(4)
        self.atraso = atraso
        self.vivo = True
        self.fio = threading.Thread(target=self._atender, daemon=True)
        self.fio.start()

    def _atender(self) -> None:
        self.sock.settimeout(0.2)
        while self.vivo:
            try:
                con, _ = self.sock.accept()
            except (TimeoutError, OSError):
                continue
            with con:
                arquivo = con.makefile("rb")
                linha = arquivo.readline()
                if not linha:
                    continue
                pedido = json.loads(linha)
                time.sleep(self.atraso)
                corpo = {"enviada": True, "respondeu": True, "resposta": VEREDITO}
                resposta = {"jsonrpc": "2.0", "id": pedido["id"], "result": corpo}
                with contextlib.suppress(OSError):
                    con.sendall(json.dumps(resposta).encode() + b"\n")

    def fechar(self) -> None:
        self.vivo = False
        self.fio.join(2)
        self.sock.close()


def _com_o_servico(curto: pathlib.Path, monkeypatch: pytest.MonkeyPatch,
                   atraso: float) -> tuple[bool, str | None, Any]:
    caminho = curto / "s"
    monkeypatch.setattr(ipc_client, "ipc_socket_path", lambda: caminho)
    servico = _ServicoLento(caminho, atraso)
    try:
        return ponte.chamar_com_o_corpo("mods.acao", mod="imersao", acao="testar_golpe")
    finally:
        servico.fechar()


def test_o_teto_do_mods_acao_cobre_o_prazo_da_resposta_lido_da_porta(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """D-1611-O-MODO-IMERSAO-TOCA-EM-TODO-JOGO: o teto é o prazo da porta mais a folga, e segue
    o prazo da porta quando ele muda (o mesmo número, nunca repetido)."""
    assert ipc_bridge.teto("mods.acao") > modulo_da_porta.PRAZO_DA_RESPOSTA_S
    monkeypatch.setattr(modulo_da_porta, "PRAZO_DA_RESPOSTA_S", 3.0)
    assert ipc_bridge.teto("mods.acao") == 3.0 + ipc_bridge.FOLGA_DA_RESPOSTA_DA_EXTENSAO_S
    assert ipc_bridge.teto("mods.agora") == ipc_bridge.TETO_PADRAO_S


def test_a_extensao_que_responde_em_0_6_s_chega_a_janela(
        curto: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """D-1611-O-MODO-IMERSAO-TOCA-EM-TODO-JOGO: o «Testar» que a extensão responde em 0,6 s
    devolve o veredito, e não «O serviço não respondeu»."""
    ok, motivo, corpo = _com_o_servico(curto, monkeypatch, 0.6)
    assert ok and motivo is None
    assert corpo == {"enviada": True, "respondeu": True, "resposta": VEREDITO}


PILULA = re.compile(r'<span class="est est-(\w+) fx-pilula"( data-situacao="(\w+)")?[^>]*><i></i>'
                    r'([^<]+)</span>')


def _faixa(situacao: dict[str, Any] | None, **estado: Any) -> str:
    base: dict[str, Any] = {"ligado": True, **estado}
    if situacao is not None:
        base[SITUACAO] = situacao
    return exp.faixa_html(["controle", "linhas"], base)


def test_a_faixa_diz_tocando_calado_com_o_motivo_ou_esperando() -> None:
    """D-1611-A-JANELA-DO-IMERSAO-DIZ-O-QUE-SENTE-NO-ALTO: a faixa do alto diz se a extensão
    está tocando (com o jogo), calada (com o motivo, nunca em vermelho) ou esperando um jogo."""
    motivo = "No Modo Nativo o jogo fala direto com o controle"
    calado = _faixa({"estado": "calado", "frase": motivo},
                    linhas=[{"rotulo": "Sentem", "valor": "Cosmic Red"}])
    pilula = PILULA.search(calado)
    assert pilula and pilula.group(1, 3, 4) == ("laranja", "calado", "Calado")
    assert '<div class="fx-l1">No Modo Nativo o jogo fala direto com o controle</div>' in calado
    assert '<span class="fx-par"><span>Sentem</span>Cosmic Red</span>' in calado
    tocando = PILULA.search(_faixa({"estado": "tocando", "frase": "Sackboy"}))
    assert tocando and tocando.group(1, 4) == ("verde", "Tocando")
    esperando = _faixa({"estado": "esperando", "frase": None})
    assert PILULA.search(esperando).group(4) == "Esperando um jogo"  # type: ignore[union-attr]
    assert "fx-l1" not in esperando
    assert PILULA.search(_faixa(None)).group(4) == "Ligada"  # type: ignore[union-attr]
    parada = exp.faixa_html(["controle", "linhas"], {"ligado": False,
                                                     SITUACAO: {"estado": "tocando"}})
    assert "Tocando" not in parada and "Parada" in parada
    assert "vermelho" not in calado


def test_a_faixa_mostra_as_tres_ultimas_escritas_com_o_canal_e_ha_quanto_tempo() -> None:
    estado = {"ligado": True, "ao_vivo": {
        "controles": [{"jogador": 1, "cor": "white"}, {"jogador": 2, "cor": "cosmic-red"}],
        "escritas": [{"canal": "haptica", "controle": 0, "ha_ms": 200},
                     {"canal": "luz", "controle": 1, "ha_ms": 2400},
                     {"canal": "vibracao", "controle": 1, "ha_ms": 900},
                     {"canal": "som", "controle": 0, "ha_ms": 5000, "todos": True},
                     {"canal": "inventado", "controle": 0, "ha_ms": 10}]}}
    html = exp.faixa_html(["controle", "linhas"], estado)
    itens = re.findall(r'<span class="fx-ev[^"]*"><b>([^<]+)</b>([^<]+)<i>([^<]+)</i>', html)
    assert [(c, q) for c, _n, q in itens] == [("Vibração fina", "Agora"), ("Motores", "Agora"),
                                              ("Barra de luz", "2 s")]
    assert len(itens) == exp.ULTIMAS_DA_FAIXA
    assert "fx-feed" not in exp.faixa_html(["linhas"], estado), "sem o controle, sem as escritas"


def test_a_janela_sem_coluna_tem_a_faixa_no_alto_e_a_do_nivel_segue_com_a_coluna() -> None:
    estado = {"ligado": True, SITUACAO: {"estado": "tocando", "frase": "Sackboy"}}
    sem = exp.modificacao_miolo_html("Modo imersão", [], mod="imersao",
                                     agora=("controle", "linhas"), estado=estado)
    assert '<div class="ja-faixa-estado" id="mod-agora">' in sem and "com-estado" in sem
    assert 'class="ja-agora"' not in sem and "Nível" not in sem
    com = exp.modificacao_miolo_html("Toque", [], mod="toque", agora=("nivel", "linhas"),
                                     estado={"ligado": True, "nivel": 4})
    assert 'class="ja-agora" id="mod-agora"' in com and "ja-faixa-estado" not in com


def test_o_veredito_fala_pela_cor_do_plastico_e_nunca_pelo_uniq() -> None:
    uniq = "aa:bb:cc:00:00:92"
    assert exp.veredito_da_resposta(VEREDITO) == exp.Veredito("Tocou no Cosmic Red.", True)
    misto = exp.veredito_da_resposta({"controles": [
        {"uniq": uniq, "nome": "White", "tocou": True, "motivo": None},
        {"uniq": uniq, "nome": "Starlight Blue", "tocou": False,
         "motivo": "o controle está desligado na extensão"}]})
    assert misto == exp.Veredito("Tocou no White. Não tocou no Starlight Blue: o controle está "
                                 "desligado na extensão.", False)
    sem_nome = exp.veredito_da_resposta({"controles": [{"uniq": uniq, "tocou": False}]})
    assert sem_nome is not None and uniq not in sem_nome.frase
    assert sem_nome.frase == f"Não tocou no {exp.NOME_SEM_PLASTICO}."
    assert exp.veredito_da_resposta({"controles": []}) == exp.Veredito(
        exp.NENHUM_CONTROLE_SENTE, False)
    assert exp.veredito_da_resposta("tocou") is None
    assert 'class="mj-veredito nao"' in exp.veredito_html(misto)  # (noqa-acento)


CORACAO = exp.OpcaoDaJanela("imersao", ID_DO_CORACAO, "Coração", "ligado", True, grupo="Efeitos",
                            cartao="Coração", marca="Terror")
GOLPE = exp.OpcaoDaJanela("imersao", "golpe", "Golpe com lado", "ligado", True, grupo="Efeitos",
                          cartao="Golpe com lado")
TESTAR = (exp.AcaoDaJanela("testar_coracao", "Testar", "Efeitos", "testar", "Coração"),
          exp.AcaoDaJanela("ver", "Ver a tela", "Efeitos"))


def test_o_testar_mora_no_pe_do_cartao_e_a_marca_no_titulo() -> None:
    """D-1611-O-MODO-IMERSAO-TOCA-EM-TODO-JOGO: cada efeito tem o «Testar» no próprio cartão,
    com o veredito ao lado, e os do Terror levam a marca."""
    vereditos = {"testar_coracao": exp.Veredito("Tocou no Cosmic Red.", True)}
    html = exp.modificacao_miolo_html("Modo imersão", [CORACAO, GOLPE], mod="imersao",
                                      acoes=TESTAR, abas=("Efeitos",), vereditos=vereditos)
    pe = re.search(r'<div class="mj-ct-pe" id="mod-acoes-c-coracao">(.*?)</div></div>', html)
    assert pe and 'data-v="imersao:testar_coracao"' in pe.group(1)
    assert '<span class="mj-veredito ok"' in pe.group(1) and "Tocou no Cosmic Red." in pe.group(1)
    assert html.count('data-v="imersao:testar_coracao"') == 1, "o Testar repetido na barra"
    assert 'data-v="imersao:ver"' in html
    assert html.count('<span class="mj-marca">Terror</span>') == 1
    assert "mod-acoes-c-golpe-com-lado" not in html
    assert exp.acoes_por_aba([CORACAO], TESTAR, None, abas=("Efeitos",)) == {0: (TESTAR[1],)}
    assert exp.id_do_cartao("Impacto nos gatilhos") == "mod-acoes-c-impacto-nos-gatilhos"


def test_cada_sentido_mostra_o_medidor_do_que_le_e_o_que_nao_le_diz_por_que() -> None:
    estado = {"ligado": True, "leituras": [
        {OPCAO: "som", "nivel": 65, "frase": None, "cego": False},
        {OPCAO: "parado", "nivel": None, "frase": "Este ajuste não usa", "cego": True}]}
    opcoes = [exp.OpcaoDaJanela("imersao", i, r, "ligado", True, grupo="Sentir",
                                cartao="O que ele escuta")
              for i, r in (("som", "Som"), ("parado", "Parado"), ("golpe", "Golpe"))]
    html = exp.modificacao_miolo_html("Modo imersão", opcoes, mod="imersao", estado=estado,
                                      agora=("controle", "linhas"), abas=("Sentir",))
    som = re.search(r'<span class="mj-leitura" id="mod-leitura-som">(.*?)</span></span>', html)
    assert som and 'role="meter"' in som.group(1) and 'aria-valuenow="65"' in som.group(1)
    assert 'id="mod-leitura-parado"><span class="mj-lt-frase cego">Este ajuste não usa' in html
    assert "mod-leitura-golpe" not in html
    assert 'aria-valuenow="0"' in exp.leitura_html({"nivel": 80, "cego": True})
    assert exp.leitura_html(None) == ""


def test_so_a_leitura_de_uma_opcao_do_manifesto_vira_seletor_do_tique() -> None:
    from types import SimpleNamespace

    from hefesto_dualsense4unix.interface.pacotes import a07_lancadores
    manifesto = SimpleNamespace(opcoes=[SimpleNamespace(id="som", tipo="ligado", canal=None)])
    estado = {"ligado": True, "leituras": [{OPCAO: "som", "nivel": 10},
                                           {OPCAO: "fora_do_manifesto", "nivel": 20}]}
    blocos = a07_lancadores._blocos_dos_sentidos(manifesto, estado)
    assert list(blocos) == ["#mod-leitura-som"]


def test_a_trilha_do_canal_nao_veste_a_classe_do_controle_livre() -> None:
    """A barra da trilha que chegou não usa o ``.vivo`` da faixa do controle livre, que a estica
    para 36 px (medido na foto de 16/11/2026, as barras por cima das chaves vizinhas)."""
    html = exp.trilha_html([0.0, 1.0])
    assert html.count("<b") == exp.PONTOS_DA_TRILHA
    assert html.endswith('<b class="chegou" style="height:100%"></b>')
    assert 'class="vivo"' not in html and "#mod-janela .vivo {" in exp.CSS


def test_a_porta_aceita_a_situacao_e_as_leituras_e_recusa_o_torto() -> None:
    aceito = modulo_da_porta.estado_dos_acessorios("imersao", {
        "ligado": True, SITUACAO: {"estado": "calado", "frase": " A intensidade está em zero "},
        "leituras": [{OPCAO: "sentido_som", "nivel": 40}]})
    assert aceito[SITUACAO] == {"estado": "calado", "frase": "A intensidade está em zero"}
    assert aceito["leituras"] == [{OPCAO: "sentido_som", "nivel": 40, "frase": None,
                                   "cego": False}]
    for torto in ({SITUACAO: {"estado": "vermelho"}}, {SITUACAO: "tocando"},
                  {SITUACAO: {"estado": "calado", "frase": "x" * 121}},
                  {"leituras": [{OPCAO: "som", "nivel": 101}]},
                  {"leituras": [{OPCAO: "som", "nivel": True}]},
                  {"leituras": [{OPCAO: "", "nivel": 1}]}, {"leituras": "som"},
                  {"leituras": [{OPCAO: 'som"],#mod-janela [x', "nivel": 1}]},
                  {"leituras": [{OPCAO: "Som de fora", "nivel": 1}]}):
        with pytest.raises(modulo_da_porta.RecusaError):
            modulo_da_porta.estado_dos_acessorios("imersao", {"ligado": True, **torto})


def test_o_manifesto_aceita_o_cartao_da_acao_e_a_marca_da_opcao() -> None:
    assert Acao(id="testar_coracao", rotulo="Testar", grupo="Efeitos", cartao="Coração").cartao \
        == "Coração"
    marca = Opcao.model_validate({"id": ID_DO_CORACAO, "rotulo": "Coração", "tipo": "ligado",
                                  PADRAO: True, "marca": "Terror"})
    assert marca.marca == "Terror"
    with pytest.raises(ValidationError):
        Opcao.model_validate({"id": ID_DO_CORACAO, "rotulo": "Coração", "tipo": "ligado",
                              PADRAO: True, "marca": "x" * 13})
    with pytest.raises(ValidationError, match="não declara grupo nem cartao"):
        AcoesDosAparelhos.model_validate({ACOES: [{"id": "ligar", "rotulo": "Ligar",
                                                     "cartao": "Coração"}]})


class _PonteQueResponde(_Ponte):
    def __init__(self, corpo: dict[str, Any]) -> None:
        super().__init__({"ligado": True, SITUACAO: {"estado": "tocando", "frase": "Sackboy"},
                          "serie": 1})
        self.corpo = corpo

    def chamar_com_o_corpo(self, metodo: str, **params: Any) -> tuple[bool, str | None, Any]:
        self.chamadas.append((metodo, params))
        return True, None, self.corpo


@pytest.mark.parametrize("corpo, frase", [
    ({"enviada": True, "respondeu": True, "resposta": VEREDITO}, "Tocou no Cosmic Red."),
    ({"enviada": True, "respondeu": False}, exp.SEM_RESPOSTA_A_TEMPO)])
def test_o_clique_no_testar_poe_o_veredito_no_cartao(janela: Any, ctx: Any,  # noqa: F811
                                                     corpo: dict[str, Any], frase: str) -> None:
    """D-1611-O-MODO-IMERSAO-TOCA-EM-TODO-JOGO: o clique no «Testar» do cartão volta com a frase
    da extensão no pé do mesmo cartão, sem o uniq."""
    a07, instalar, abrir = janela
    instalar(agora=["controle", "linhas"], abas=["Efeitos"],
             opcoes=[{"id": ID_DO_CORACAO, "rotulo": "Coração", "tipo": "ligado", PADRAO: True,
                      "grupo": "Efeitos", "cartao": "Coração", "marca": "Terror"}],
             acoes=[{"id": "testar_coracao", "rotulo": "Testar", "grupo": "Efeitos",
                     "icone": "testar", "cartao": "Coração"}])
    p = _PonteQueResponde(corpo)
    abrir(p)
    a07.acao_da_modificacao(ctx, {"v": "toque:testar_coracao"}, p)
    assert [x for m, x in p.chamadas if m == "mods.acao"] == [
        {"mod": "toque", "acao": "testar_coracao"}]  # (noqa-acento)
    a07._AGORA.ler("toque", p)
    tique = a07._com_os_aparelhos({"blocos": {}})["blocos"]
    assert frase in tique["#mod-acoes-c-coracao"], "o veredito não chegou ao cartão no tique"
    html = a07._MEXIDA.html_mod
    pe = re.search(r'id="mod-acoes-c-coracao">(.*?)</div>', html, re.S)
    assert pe and frase in pe.group(1), "a janela redesenhada não tem o veredito no cartão"
    assert "aa:bb:cc" not in html + "".join(tique.values())
    assert '<div class="ja-faixa-estado" id="mod-agora">' in html and "Sackboy" in html


SENTIDOS = [exp.OpcaoDaJanela("imersao", i, r, "ligado", True, grupo="Sentir",
                              cartao="O que ele escuta") for i, r in (("som", "Som"),
                                                                       ("parado", "Parado"))]


def test_o_cartao_de_chaves_com_botao_nao_vira_a_fileira_e_o_botao_fica() -> None:
    """D-1611-O-MODO-IMERSAO-TOCA-EM-TODO-JOGO: o cartão «O que ele escuta» só de chaves e sem
    leitura (a extensão desligada, ou antes do primeiro estado) não vira a fileira de chaves, que
    não tem pé: o «Ver a tela» dele segue à vista (medido em 16/11/2026, ele sumia da janela)."""
    ver = (exp.AcaoDaJanela("ver_a_tela", "Ver a tela", "Sentir", "ligar", "O que ele escuta"),)
    for estado in (None, {"ligado": False}):
        html = exp.modificacao_miolo_html("Modo imersão", SENTIDOS, mod="imersao", estado=estado,
                                          agora=("controle", "linhas"), acoes=ver,
                                          abas=("Sentir",), chave=True)
        assert html.count('data-v="imersao:ver_a_tela"') == 1, "o botão do cartão sumiu"
        assert 'id="mod-acoes-c-o-que-ele-escuta"' in html and "mj-fileira" not in html
    solta = (exp.AcaoDaJanela("ver_a_tela", "Ver a tela", "Sentir"),)
    sem_botao = exp.modificacao_miolo_html("Modo imersão", SENTIDOS, mod="imersao", estado=None,
                                           agora=("controle", "linhas"), acoes=solta,
                                           abas=("Sentir",), chave=True)
    assert "mj-fileira" in sem_botao and 'data-v="imersao:ver_a_tela"' in sem_botao


def test_o_manifesto_recusa_a_acao_num_cartao_que_nenhuma_opcao_declara() -> None:
    """D-1611-O-MODO-IMERSAO-TOCA-EM-TODO-JOGO: a ação cujo ``cartao`` nenhuma opção declara
    nunca apareceria na janela; o manifesto é recusado em vez de esconder o botão."""
    from hefesto_dualsense4unix.mods.manifesto import Manifesto

    bruto = json.loads((pathlib.Path(__file__).resolve().parents[2] / "mockup" / "modo-imersao"
                        / "hefesto-mod.json").read_text(encoding="utf-8"))
    assert any(a.cartao for a in Manifesto.model_validate(bruto).acoes)
    torto = {**bruto, ACOES: [{**a, "cartao": "Cartão que não existe"} if a.get("cartao") else a
                              for a in bruto[ACOES]]}
    with pytest.raises(ValidationError, match="nenhuma opção declara"):
        Manifesto.model_validate(torto)


def test_a_resposta_fora_da_forma_do_veredito_nao_diz_que_a_extensao_calou(
        janela: Any, ctx: Any) -> None:  # noqa: F811
    """D-1611-O-MODO-IMERSAO-TOCA-EM-TODO-JOGO: a extensão que respondeu, mas sem
    ``{controles}``, não ganha «não respondeu a tempo» no cartão, e o veredito velho sai."""
    a07, instalar, abrir = janela
    instalar(agora=["controle", "linhas"], abas=["Efeitos"],
             opcoes=[{"id": ID_DO_CORACAO, "rotulo": "Coração", "tipo": "ligado", PADRAO: True,
                      "grupo": "Efeitos", "cartao": "Coração"}],
             acoes=[{"id": "testar_coracao", "rotulo": "Testar", "grupo": "Efeitos",
                     "icone": "testar", "responde": True, "cartao": "Coração"}])
    p = _PonteQueResponde({"enviada": True, "respondeu": True, "resposta": VEREDITO})
    abrir(p)
    a07.acao_da_modificacao(ctx, {"v": "toque:testar_coracao"}, p)
    assert "Tocou no Cosmic Red." in a07._MEXIDA.html_mod
    p.corpo = {"enviada": True, "respondeu": True, "resposta": {"feito": True}}
    a07.acao_da_modificacao(ctx, {"v": "toque:testar_coracao"}, p)
    html = a07._MEXIDA.html_mod
    assert exp.SEM_RESPOSTA_A_TEMPO not in html and "Tocou no Cosmic Red." not in html


def test_calado_ou_esperando_a_faixa_nao_mostra_as_escritas() -> None:
    """D-1611-O-MODO-IMERSAO-TOCA-EM-TODO-JOGO: como no desenho aprovado, as últimas escritas
    saem da faixa fora do «Tocando»: «Calado» ao lado de um efeito de «Agora» se contradiz."""
    ao_vivo = {"controles": [{"jogador": 1, "cor": "white"}],
               "escritas": [{"canal": "haptica", "controle": 0, "ha_ms": 200}]}
    lembradas = [exp.Ultima("haptica", "White", 100)]
    for situacao, mostra in (("tocando", True), ("calado", False), ("esperando", False),
                             (None, True)):
        base: dict[str, Any] = {"ligado": True, "ao_vivo": ao_vivo}
        if situacao is not None:
            base[SITUACAO] = {"estado": situacao, "frase": None}
        for ultimas in (None, lembradas):
            html = exp.faixa_html(["controle", "linhas"], base, ultimas=ultimas)
            assert ("fx-feed" in html) is mostra, (situacao, ultimas)

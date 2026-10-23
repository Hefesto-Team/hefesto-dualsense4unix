"""A aba Sistema do desenho do todo: seis linhas, quatro colunas, um interruptor e o tamanho.

A-ABA-SISTEMA-DO-TODO-01. O desenho anda até o mockup e para ali (o ``--publicar`` é do fecho): a
régua lê ``mockup/09-sistema.html`` e as peças do pacote (``pacotes/a09_sistema.py``), nunca a cópia
publicada. O que o desenho promete e o produto tem de cumprir:

* seis linhas de status, em três colunas (duas do Status, duas colunas de duas do exame), a que
  pede atenção em laranja e a que falha em vermelho;
* quatro colunas de configurações, na ordem de produto, e nenhum «?»;
* UM interruptor (``correcoes-automaticas``) no lugar dos quatro botões das correções;
* o tamanho da interface em três botões (100, 125 e 150 %), gravado em ``interface_escala``;
* o registro é a única faixa que encolhe, e ganha o «Salvar» ao lado do «Copiar».

Mordidas (cada uma arrancada, vista reprovar e devolvida; as vistas estão no relato do bloco):

* devolver o ``min-height:120px`` do ``.registro``:
  :func:`test_o_registro_cabe_em_1212x700`;
* a mudança de ``aviso`` para ``falha`` do exame SAIU em 21/10/2026
  (O-STATUS-DO-SISTEMA-DIZ-O-QUE-ESTA-BEM-EM-VERDE-E-SO-AVISA-O-QUE-PEDE-ACAO-01): o aviso fica
  laranja; a régua dela é `test_o_status_diz_o_que_esta_bem_em_verde.py`;
* trocar a posição do Steam Input ou do Áudio no exame:
  :func:`test_as_posicoes_do_exame_sao_as_do_dono`;
* tirar o predicado ``sem_dono_do_rumble`` da linha do gamepad:
  :func:`test_a_linha_do_gamepad_virtual`;
* o interruptor que não grava o arquivo, ou que não reaplica no duplo clique:
  :func:`test_o_interruptor_alterna_e_o_duplo_clique_reaplica`;
* o ``garantir`` do guarda de volta ao fio do gesto, onde o recarregar do systemd atrasa o
  segundo clique além do meio segundo:
  :func:`test_o_duplo_clique_nao_espera_o_systemd_do_primeiro`;
* o tamanho que aceita valor de fora da lista: :func:`test_o_tamanho_so_aceita_os_tres_da_lista`.
"""

from __future__ import annotations

import json
import pathlib
import re
import threading
from typing import Any

import pytest


from hefesto_dualsense4unix.integrations import storm_doctor as exame_do_dono
from hefesto_dualsense4unix.interface import sistema as tela
from hefesto_dualsense4unix.interface.pacotes import Contexto
from hefesto_dualsense4unix.interface.pacotes import a09_sistema as a09

RAIZ = pathlib.Path(__file__).resolve().parents[2]
DESENHO = RAIZ / "mockup/09-sistema.html"


def _desenho() -> str:
    return DESENHO.read_text(encoding="utf-8")


def _entre(doc: str, abre: str, fecha: str) -> str:
    i = doc.index(abre)
    return doc[i: doc.index(fecha, i)]


# --- o desenho ------------------------------------------------------------------------------


def test_o_status_tem_seis_linhas_em_tres_colunas() -> None:
    """Duas linhas no Status e quatro no exame (duas colunas de duas): seis ao todo."""
    status3 = _entre(_desenho(), '<div class="status3">', "<!-- ---------- 2.")
    colunas = status3.split('<div class="col-lista"')[1:]
    assert len(colunas) == 3, f"o Status tem {len(colunas)} colunas, e o desenho tem três"
    por_coluna = [len(re.findall(r'class="saude(?: vai)?(?: longa)?"', c)) for c in colunas]
    assert por_coluna == [2, 2, 2], f"linhas por coluna: {por_coluna}"
    ids = re.findall(r'data-id="([^"]+)"', status3)
    assert "hefesto-estado" in ids
    assert "hefesto-troca-de-perfil" in ids
    assert "status-bluetooth" in ids


def test_as_quatro_colunas_estao_na_ordem_dela() -> None:
    # D-1610-O-PERFIL-DE-BATERIA-E-SO-O-GLOBAL-NA-SISTEMA
    """Funcionamento do app, Interface, Perfil global de bateria e Saúde do app."""
    doc = _desenho()
    rotulos = re.findall(r"<span[^>]*>([^<]+)</span>",
                         _entre(doc, '<div class="sec-rot sr-avancadas">', "</div>"))
    assert rotulos == ["Funcionamento do app", "Interface", "Perfil global de bateria",
                       "Saúde do app"], rotulos
    avancadas = _entre(doc, '<div class="avancadas">', "<!-- ---------- 3.")
    colunas = re.split(r'<div class="risco"></div>', avancadas)
    assert len(colunas) == 4, f"{len(colunas)} colunas de botões"
    textos = [re.findall(r">([^<>]+)</button>", c) for c in colunas]
    assert textos[0] == ["Parar", "Atualizar", "Corrigir o serviço", "Reiniciar"], textos[0]
    assert textos[1] == ["Padrão", "Confortável", "Espaçoso"], textos[1]
    assert textos[3] == ["Permitir correções automáticas", "Iniciar com o sistema",
                         "Restaurar de fábrica"], textos[3]


def test_um_so_interruptor_e_nenhum_botao_do_doctor_do_proton_nem_do_vulkan() -> None:
    doc = _desenho()
    assert doc.count('data-gesto="correcoes-automaticas"') == 1
    for gesto in ("refazer-consertos", "aplicar-aos-jogos", "fixar-proton", "corrigir-vulkan",
                  "doctor"):
        assert f'data-gesto="{gesto}"' not in doc, f"o botão `{gesto}` voltou à aba"
    for rotulo in ("Reaplicar correções", "Aplicar soluções", "Fixar Proton", "Corrigir Vulkan"):
        assert rotulo not in doc, f"«{rotulo}» voltou à aba"


def test_nenhum_interrogacao_na_aba() -> None:
    doc = _desenho()
    assert not re.search(r"""<span\b[^>]*\bclass=["']ajuda\b""", doc)
    assert 'id="i-ajuda"' not in _entre(doc, '<div class="quadro estica">', "</body>")


def test_o_tamanho_da_interface_tem_tres_botoes_e_um_aceso() -> None:
    botoes = re.findall(
        r'<button class="(on)?"[^>]*data-v="(\d+)"[^>]*>([^<]+)</button>',
        _entre(_desenho(), 'data-id="tamanho-da-interface"', "</div>"))
    assert [(int(v), r) for _o, v, r in botoes] == [(100, "Padrão"), (125, "Confortável"),
                                                    (150, "Espaçoso")]
    assert [v for o, v, _r in botoes if o] == ["100"]


def test_o_registro_e_a_unica_faixa_que_encolhe_e_ganha_o_salvar() -> None:
    doc = _desenho()
    assert re.search(r"\.registro\{[^}]*flex:1 1 0[^}]*min-height:0", doc)
    cabeca = _entre(doc, '<div class="sec-rot sr-log', "</div>")
    assert re.findall(r">([^<>]+)</button>", cabeca) == ["Copiar", "Salvar"]
    assert 'data-gesto="salvar-registro"' in cabeca


def test_o_que_falha_e_vermelho_e_o_que_esta_bem_e_de_contorno() -> None:
    doc = _desenho()
    assert re.search(r"\.selo\.falha\{background:var\(--red\)", doc)
    assert re.search(r"\.selo\.ok\{background:transparent", doc)


def test_os_enderecos_da_pagina_tem_dono_no_pacote() -> None:
    """O interruptor e o tamanho acendem pelo ``data-campo`` que o pacote escreve."""
    doc = _desenho()
    for campo in ("correcoes-automaticas", "tamanho-da-interface"):
        assert f'data-campo="{campo}"' in doc
        assert campo in tela.ENDERECOS, f"`{campo}` não está nos endereços do produto"
    for gesto in ("correcoes-automaticas", "tamanho-da-interface", "salvar-registro"):
        assert gesto in tela.GESTOS
        assert gesto in a09.SEM_ECO, f"`{gesto}` não tem eco no state_full e precisa dizer"


# --- o que o pacote põe nas linhas ----------------------------------------------------------


def _linha(cls: str, txt: str) -> dict[str, Any]:
    selo = {"ok": "OK", "aviso": "AVISO", "nt": "NOTA"}[cls]
    return {"selo": selo, "cls": cls, "g": "x", "txt": txt}


def _exame_completo(**trocas: tuple[str, str]) -> dict[str, Any]:
    """Os seis do ``storm_report``, na ordem do dono, todos bem, com trocas por posição."""
    linhas = [
        _linha("ok", "cura do travamento do USB ativa"),
        _linha("ok", "áudio presente nos 2 controles no cabo"),
        _linha("ok", "quirk anti-storm ativo (054c:0ce6)"),
        _linha("ok", "Steam Input desligado para o DualSense"),
        _linha("ok", "WirePlumber configurado"),
        _linha("ok", "regra áudio-off inativa — o mic e o fone estão liberados."),
    ]
    for posicao, (cls, txt) in trocas.items():
        linhas[int(posicao.removeprefix("p"))] = _linha(cls, txt)
    return {"linhas": linhas, "vazio": ""}


def _estado(controles: int = 2, vpads: int = 2, native: bool = False,
            emulacao: bool = True) -> dict[str, Any]:
    return {"controllers": [{"connected": True, "transport": "usb"} for _ in range(controles)],
            "rumble_ff": {"vpads": vpads}, "native_mode": native,
            "gamepad_emulation": {"enabled": emulacao}}


def _status(state: dict[str, Any]) -> list[dict[str, Any]]:
    return [dict(tela.status_do_bluetooth(1, state))]


def _textos(saida: dict[str, Any]) -> list[tuple[str, str]]:
    return [(a["cls"], a.get("curta") or a["txt"]) for a in saida["linhas"]]


def _do_exame(saida: dict[str, Any]) -> dict[str, Any]:
    """As quatro linhas do exame: as duas primeiras das seis são do Status."""
    return {"linhas": saida["linhas"][len(a09.LINHAS_DO_STATUS):]}


def test_o_exame_so_mostra_os_quatro_temas() -> None:
    """Bluetooth, Steam Input, Áudio e o gamepad virtual; o resto fica calado se está bem."""
    estado = _estado()
    saida = _do_exame(a09._so_o_que_a_tela_mostra(_exame_completo(), _status(estado), estado))
    assert _textos(saida) == [
        ("ok", "Bluetooth: 1 adaptador · 0 controles"),
        ("ok", "Steam Input desligado para o DualSense"),
        ("ok", "Áudio roteado"),
        ("ok", "Um gamepad virtual por jogador"),
    ]
    html_ = a09._html_do_exame(saida)
    assert html_.count('class="saude') == 4
    assert 'href="08-conexoes.html#rd-secao"' in html_
    assert "title=" not in html_, "o exame fala pela dica curta, não pelo `title`"
    assert "Steam Input desligado" in html_


def test_o_aviso_fica_laranja_no_tema_e_fora_dele() -> None:
    estado = _estado()
    exame = _exame_completo(p3=("aviso", "Steam Input ligado para 2 jogos"),
                            p4=("aviso", "o ajuste de áudio do hefesto não está instalado"),
                            p2=("nt", "quirk não aplicável"))
    saida = _do_exame(a09._so_o_que_a_tela_mostra(exame, _status(estado), estado))
    # o aviso de fora da linha do tema entra nela (O-STATUS-DO-SISTEMA-TEM-SEIS-LINHAS-SEMPRE-01):
    # o WirePlumber é do Áudio, que fica laranja
    cls = [a["cls"] for a in saida["linhas"]]
    assert cls == ["ok", "aviso", "aviso", "ok"], cls
    textos = [a.get("curta") or a["txt"] for a in saida["linhas"]]
    assert "o ajuste de áudio do hefesto não está instalado" in saida["linhas"][2]["dica"]
    assert not any("quirk não aplicável" in t for t in textos), "linha de nota fora dos temas"
    html_ = a09._html_do_exame(saida)
    assert html_.count('class="selo aviso"') == 2
    assert 'class="selo falha"' not in html_


def test_o_audio_que_nao_esta_bem_diz_a_frase_e_nao_o_rotulo_do_ok() -> None:
    estado = _estado()
    exame = _exame_completo(p1=("aviso", "áudio ausente em 1 dos 2 controles no cabo"))
    saida = a09._so_o_que_a_tela_mostra(exame, _status(estado), estado)
    audio = saida["linhas"][a09.TEMAS.index("audio")]
    assert audio["cls"] == "aviso"
    assert "Áudio roteado" not in json.dumps(saida, ensure_ascii=False)


def test_exame_incompleto_mostra_o_que_nao_esta_bem_sem_adivinhar_a_posicao() -> None:
    estado = _estado()
    exame = {"linhas": [_linha("ok", "alguma coisa"), _linha("aviso", "algo falhou"),
                        _linha("nt", "uma nota")], "vazio": ""}
    saida = a09._so_o_que_a_tela_mostra(exame, _status(estado), estado)
    # sem posição sabida, o aviso vai à linha do Serviço e os temas do exame dizem «sem leitura»
    assert _textos(saida)[3:] == [("nt", "Steam Input: sem leitura"),
                                  ("nt", "Áudio: sem leitura"),
                                  ("ok", "Um gamepad virtual por jogador")]
    assert _textos(saida)[0] == ("aviso", "Algo falhou"), _textos(saida)
    assert saida["linhas"][3]["dica"] == "uma nota"


def test_exame_que_nao_respondeu_diz_isso_numa_linha_de_nota() -> None:
    estado = _estado()
    exame = {"linhas": [],
             "vazio": "O exame não respondeu — não dá para dizer o que esta máquina tem."}
    saida = a09._so_o_que_a_tela_mostra(exame, _status(estado), estado)
    for tema in ("steam-input", "audio"):
        linha = saida["linhas"][a09.TEMAS.index(tema)]
        assert linha["cls"] == "nt", linha
        assert "O exame não respondeu" in linha["dica"], linha


def test_as_posicoes_do_exame_sao_as_do_dono(tmp_path: pathlib.Path) -> None:
    """O Steam Input é o quarto achado do ``storm_report`` e o Áudio o segundo, medidos no dono."""
    pasta = tmp_path / "vazio"
    pasta.mkdir()
    relatorio = exame_do_dono.storm_report(
        home=pasta, quirks_text="", dropin_dir=pasta, rules_dir=pasta, snd_quirk_text="",
        snd_conf_path=pasta / "x.conf", cards_text="", controles_no_cabo=None)
    assert relatorio[a09.POSICAO_NO_EXAME["steam-input"]] == exame_do_dono.check_steam_input(pasta)
    assert relatorio[a09.POSICAO_NO_EXAME["audio"]] == exame_do_dono.check_snd_audio_healthy(
        "", controles_no_cabo=None)
    assert len(relatorio) >= a09.LINHAS_DO_EXAME_COMPLETO


@pytest.mark.parametrize(("estado", "cls", "texto"), [
    (_estado(2, 2), "ok", "Um gamepad virtual por jogador"),
    (_estado(4, 4), "ok", "Um gamepad virtual por jogador"),
    (_estado(2, 0), "falha", "Nenhum gamepad virtual subiu"),
    (_estado(2, 1), "nt", "1 de 2 controles com gamepad virtual"),
    (_estado(2, 0, native=True), "nt", "Conexão nativa: o jogo fala direto com o controle"),
    (_estado(2, 0, emulacao=False), "nt", "Gamepad virtual: emulação desligada"),
    ({"controllers": []}, "nt", "Gamepads virtuais: sem leitura do serviço"),
    (None, "nt", "Gamepads virtuais: sem leitura do serviço"),
])
def test_a_linha_do_gamepad_virtual(estado: Any, cls: str, texto: str) -> None:
    """Vermelho só no defeito real: emulação ligada, fora do nativo, e NENHUM gamepad subiu."""
    linha = a09.linha_do_gamepad_por_jogador(estado)
    assert (linha["cls"], linha["txt"]) == (cls, texto), linha


@pytest.mark.parametrize("estado", [
    _estado(0, 0), _estado(0, 0, native=True), _estado(0, 0, emulacao=False)])
def test_sem_controle_a_linha_do_gamepad_diz_nenhum_controle(estado: Any) -> None:
    """Sem controle ligado não há gamepad a esperar, em nenhum modo, e a linha diz isso em vez de
    sumir (O-STATUS-DO-SISTEMA-TEM-SEIS-LINHAS-SEMPRE-01). MORDIDA (executada em 21/10/2026): com a
    conta dos controles depois do nativo e da emulação, como nasceu, os dois reprovam."""
    linha = a09.linha_do_gamepad_por_jogador(estado)
    assert (linha["cls"], linha["txt"]) == ("nt", "Nenhum controle ligado"), linha


def test_linha_do_status_e_do_exame_falam_pela_dica_curta() -> None:
    saida = a09.linha_do_status({"id": "hefesto-estado", "selo": "LIGADO", "cls": "ok", "g": "✓",
                                 "txt": "Serviço", "dica": "Roda por trás."})
    assert 'data-dica="Roda por trás."' in saida
    assert "title=" not in saida


# --- o pacote -------------------------------------------------------------------------------


@pytest.fixture
def casa(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> pathlib.Path:
    """Um HOME e uma pasta de configuração de mentira; nada fala com o systemd."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setattr(a09._vigia, "_recarregar_o_systemd", lambda: True)
    a09._LENTO.clear()
    a09._BARATO.clear()
    a09._ULTIMO_CLIQUE_DAS_CORRECOES.clear()
    return tmp_path


def _ctx(estado: dict[str, Any] | None = None) -> Contexto:
    return Contexto(state=estado if estado is not None else _estado(), mesa=[], conectados=[],
                    estados={})


def test_o_pacote_pinta_duas_linhas_de_status_quatro_de_exame_e_os_dois_campos_novos(
        monkeypatch: pytest.MonkeyPatch, casa: pathlib.Path) -> None:
    ctx = _ctx()
    achados = [("[OK]", "cura do travamento do USB ativa"),
               ("[OK]", "áudio presente nos 2 controles no cabo"),
               ("[OK]", "quirk anti-storm ativo (054c:0ce6)"),
               ("[OK]", "Steam Input desligado para o DualSense"),
               ("[OK]", "WirePlumber configurado"),
               ("[OK]", "regra áudio-off inativa — o mic e o fone estão liberados.")]
    leitura = tela.Leitura(status="online_systemd", autostart="enabled", state=ctx.state,
                           achados=achados, deteccao=None, ambiente=None, perfil=None,
                           sessao="Wayland · COSMIC", adaptadores=1)
    monkeypatch.setattr(a09, "_leitura", lambda _c: leitura)
    monkeypatch.setattr(a09, "_faixa_lenta",
                        lambda *_a, **_k: ("enabled", achados, None, "online_systemd", "—"))
    monkeypatch.setattr(a09, "_avisos_do_produto", lambda _c: [])
    monkeypatch.setattr(a09, "_html_da_fita", lambda _m: "")
    fora = a09.pacote(ctx)
    assert fora[a09.CAMPO_DO_STATUS].count('class="saude') == 2
    assert fora["exame-lista"].count('class="saude') == 4
    assert "ambiente" not in fora[a09.CAMPO_DO_STATUS].lower()
    assert fora[a09.CAMPO_DAS_CORRECOES] is True
    assert fora[a09.CAMPO_DO_TAMANHO] == "100"
    for morto in ("proton-fixado", "vulkan-corrigido"):
        assert morto not in fora, f"`{morto}` não tem mais botão e não deve ser pintado"
    a09._guardar_o_interruptor(False)
    a09.guardar_o_tamanho(125)
    outra = a09.pacote(ctx)
    assert outra[a09.CAMPO_DAS_CORRECOES] is False
    assert outra[a09.CAMPO_DO_TAMANHO] == "125"


def test_o_interruptor_alterna_e_o_duplo_clique_reaplica(
        monkeypatch: pytest.MonkeyPatch, casa: pathlib.Path) -> None:
    # D-1610-UM-INTERRUPTOR-SO-PARA-AS-CORRECOES
    clique = [100_000.0]
    reaplicou: list[str] = []
    monkeypatch.setattr(a09, "_reaplicar_as_correcoes",
                        lambda: reaplicou.append("sim") or "Reaplicado.")
    arquivo = a09._vigia.caminho_do_interruptor()
    assert a09._vigia.interruptor_ligado() is True

    a09.correcoes_automaticas(_ctx(), {"carimbo": clique[0]}, None)
    assert arquivo.read_text(encoding="utf-8") == "desligado\n"
    assert a09._vigia.interruptor_ligado() is False
    assert reaplicou == []

    clique[0] += 2000.0
    a09.correcoes_automaticas(_ctx(), {"carimbo": clique[0]}, None)
    assert arquivo.read_text(encoding="utf-8") == "ligado\n"
    assert reaplicou == [], "um clique só liga e deixa o guarda cuidar do resto"

    clique[0] += 2000.0
    a09.correcoes_automaticas(_ctx(), {"carimbo": clique[0]}, None)
    clique[0] += 200.0
    a09.correcoes_automaticas(_ctx(), {"carimbo": clique[0]}, None)
    assert a09._vigia.interruptor_ligado() is True, "o duplo clique termina ligado"
    assert reaplicou == ["sim"], "o duplo clique reaplica uma vez"

    clique[0] += 200.0
    a09.correcoes_automaticas(_ctx(), {"carimbo": clique[0]}, None)
    assert a09._vigia.interruptor_ligado() is False, "o terceiro clique seguido volta a alternar"
    assert reaplicou == ["sim"]


def test_o_duplo_clique_nao_espera_o_systemd_do_primeiro(
        monkeypatch: pytest.MonkeyPatch, casa: pathlib.Path) -> None:
    """O gesto grava o interruptor e volta; o guarda se põe em dia na fila dele.

    A fila de quem grava só solta o segundo clique quando o primeiro termina. Com o recarregar
    do systemd no fio do gesto, o segundo clique esperava esse recarregar antes de voltar.
    """
    clique = [100_000.0]
    reaplicou: list[str] = []
    monkeypatch.setattr(a09, "_reaplicar_as_correcoes",
                        lambda: reaplicou.append("sim") or "Reaplicado.")
    solta = threading.Event()
    vistos: list[bool] = []

    def garantir_lento() -> str:
        solta.wait(5)
        vistos.append(a09._vigia.interruptor_ligado())
        return "escrito"

    monkeypatch.setattr(a09._vigia, "garantir", garantir_lento)
    primeiro = threading.Thread(target=a09.correcoes_automaticas,
                                args=(_ctx(), {"carimbo": clique[0]}, None))
    primeiro.start()
    primeiro.join(1.0)
    voltou = not primeiro.is_alive()
    clique[0] += 200.0
    if voltou:
        a09.correcoes_automaticas(_ctx(), {"carimbo": clique[0]}, None)
    solta.set()
    primeiro.join(5)
    for _ in range(50):
        if len(vistos) >= 2:
            break
        threading.Event().wait(0.05)
    assert voltou, "o clique esperou o guarda (o systemd) antes de voltar"
    assert reaplicou == ["sim"], "o segundo clique em 0,2 s é o duplo e reaplica"
    assert vistos == [True, True], "o guarda roda uma vez por clique, depois de gravado"


def test_reaplicar_roda_o_doctor_os_lancadores_o_vulkan_e_o_proton(
        monkeypatch: pytest.MonkeyPatch, casa: pathlib.Path) -> None:
    from hefesto_dualsense4unix.integrations import camadas_vulkan as cv
    from hefesto_dualsense4unix.integrations import cura_por_estrada as cpe

    chamou: list[str] = []
    monkeypatch.setattr(a09._daemon, "medir_jogos_com_steam_input", lambda: [])
    monkeypatch.setattr(a09, "_rodar_os_consertos",
                        lambda jogos: chamou.append("consertos") or {"ran": 1, "missing": 0,
                                                                     "steam_input": None,
                                                                     "steam_input_jogos": jogos})
    monkeypatch.setattr(cpe, "curar_todas_as_estradas", lambda **k: chamou.append("estradas") or [])
    monkeypatch.setattr(cv, "gravar_camadas_da_steam_fora",
                        lambda fora, *a, **k: chamou.append(f"vulkan={fora}"))
    monkeypatch.setattr(a09, "_o_pino", lambda: (None, None))
    recibo = a09._reaplicar_as_correcoes()
    assert chamou == ["consertos", "estradas", "vulkan=True"], chamou
    assert recibo, "o recibo não pode ser vazio"


def test_o_tamanho_so_aceita_os_tres_da_lista(casa: pathlib.Path) -> None:
    # D-1610-O-TAMANHO-DA-INTERFACE-SE-GRAVA-EM-INTERFACE-ESCALA
    assert a09.tamanho_da_interface() == 100, "sem arquivo, o tamanho é o de hoje"
    for v in (125, 150, 100):
        a09.tamanho_da_interface_gesto(_ctx(), {"v": str(v)}, None)
        assert a09.tamanho_da_interface() == v
    for ruim in ("", "130", "abc", "-100", "0"):
        antes = a09._arquivo_do_tamanho().read_text(encoding="utf-8")
        with pytest.raises(ValueError, match="tamanho"):
            a09.tamanho_da_interface_gesto(_ctx(), {"v": ruim}, None)
        assert a09._arquivo_do_tamanho().read_text(encoding="utf-8") == antes
    a09._arquivo_do_tamanho().write_text("999\n", encoding="utf-8")
    assert a09.tamanho_da_interface() == 100, "valor fora da lista cai no padrão"
    a09._arquivo_do_tamanho().write_text("# nota\n150%\n", encoding="utf-8")
    assert a09.tamanho_da_interface() == 150


class _Ponte:
    def __init__(self, destino: pathlib.Path | None) -> None:
        self.destino = destino
        self.pedidos: list[tuple[str, str]] = []

    def salvar_arquivo(self, titulo: str, sugestao: str = "", **_: Any) -> str | None:
        self.pedidos.append((titulo, sugestao))
        return str(self.destino) if self.destino else None


def test_salvar_o_registro_grava_o_painel_mascarado(
        monkeypatch: pytest.MonkeyPatch, casa: pathlib.Path) -> None:
    mac = "aa:bb:cc:12:34:44"
    estado = _estado()
    estado["controllers"][0]["uniq"] = mac
    a09._para_o_painel(f"controle {mac} ligado")
    destino = casa / "guardado.txt"
    ponte = _Ponte(destino)
    try:
        a09.salvar_registro(_ctx(estado), {}, ponte)
    finally:
        a09._limpar_o_painel()
    texto = destino.read_text(encoding="utf-8")
    assert "ligado" in texto
    assert mac not in texto, "o endereço do controle saiu sem máscara"
    assert ponte.pedidos and ponte.pedidos[0][0] == "Onde guardar o registro"
    assert ponte.pedidos[0][1].endswith("hefesto-registro.txt")


def test_salvar_o_registro_cancelado_nao_grava_nada(casa: pathlib.Path) -> None:
    a09._para_o_painel("algum texto")
    try:
        a09.salvar_registro(_ctx(), {}, _Ponte(None))
    finally:
        a09._limpar_o_painel()
    assert list(casa.glob("*.txt")) == []


# --- a tela viva ----------------------------------------------------------------------------

MEDIR = r"""
(function () {
  const q = document.querySelector('.quadro.estica');
  const log = document.querySelector('.registro > .log');
  const r = (e) => { const b = e.getBoundingClientRect(); return [b.top, b.bottom, b.height]; };
  return JSON.stringify({
    quadro: r(q), log: r(log), innerH: innerHeight,
    scrollH: document.documentElement.scrollHeight,
    linhas: document.querySelectorAll('.status3 .saude').length,
    ajudas: document.querySelectorAll('.ajuda').length,
    cadeados: Array.from(document.querySelectorAll('.cadeado')).map(b => b.textContent.trim()),
  });
})()
"""


def _na_tela(tamanho: tuple[int, int]) -> dict[str, Any]:
    from tests.unit import test_o_mapa_das_conexoes_cabe_na_aba as vizinha

    anterior = vizinha.NA_BANCADA
    vizinha.NA_BANCADA = True
    try:
        lido = vizinha._no_webkit("09-sistema.html", tamanho, [MEDIR])[0]
    finally:
        vizinha.NA_BANCADA = anterior
    assert isinstance(lido, dict), lido
    return lido


@pytest.mark.parametrize("tamanho", [(1212, 700), (1212, 809)])
def test_o_registro_cabe_em_1212x700(tamanho: tuple[int, int]) -> None:
    """O fundo do ``.log`` não passa do quadro, a página não rola e as seis linhas estão lá.

    MORDIDA: devolver o ``min-height:120px`` do ``.registro`` empurra o fundo para fora em 700.
    """
    lido = _na_tela(tamanho)
    assert lido["linhas"] == 6
    assert lido["ajudas"] == 0
    assert lido["log"][1] <= lido["quadro"][1] + 0.5, (
        f"o registro passa do quadro: {lido['log']} contra {lido['quadro']}")
    assert lido["scrollH"] <= lido["innerH"] + 1, f"a aba rola na vertical: {lido}"
    assert lido["log"][2] > 20, "o registro encolheu até sumir"

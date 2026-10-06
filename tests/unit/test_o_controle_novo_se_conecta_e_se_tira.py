"""O controle novo se conecta, e se tira, pela Conexões.

O-CONTROLE-NOVO-SE-CONECTA-E-SE-TIRA-PELA-CONEXOES-01.

A física do diário do rádio do usuário, 06/10/2026, 17:14 e 17:15, no adaptador que já tinha dois
controles no ar: o ``Pair`` do terceiro deu, o ``Connect`` correu com a varredura AINDA de pé no
mesmo adaptador e voltou ``org.bluez.Error.Failed``, o ``StopDiscovery`` só veio depois, e
ninguém chamou o controle de novo — aos 60 s da janela a central tirou a chave que tinha acabado
de fazer como «meia chave», e o controle voltou a pedir PS + Create. Às 17:17, no outro
adaptador, o mesmo controle conectou sozinho três segundos depois do ``Pair``.

O mundo de mentira daqui reproduz isso: o controle aceita o host no ``Pair`` (a chave é inteira),
mas não conecta sozinho; o ``Connect`` falha enquanto o adaptador varre, e, no controle que
«acorda tarde», também nos primeiros segundos depois do ``Pair``.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import bluez_dbus as bd
from hefesto_dualsense4unix.integrations import central_do_radio as cr
from hefesto_dualsense4unix.interface.pacotes import a08_conexoes as a08_tela
from tests.unit import radio_de_mentira as rm
from tests.unit.radio_de_mentira import AZUL, QUARTO, ROXO, SALA, VARANDA, VERDE, VERMELHO
from tests.unit.test_o_conectar_pareia_no_adaptador_escolhido import (
    Bancada,
    id_da_tela,
    mundo_da_madrugada,
    preparar_a_tela,
    preparar_o_diario,
)

ADAPTADORES = (SALA, QUARTO, VARANDA)


@pytest.fixture()
def diario(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    return preparar_o_diario(tmp_path, monkeypatch)


@pytest.fixture()
def a08(monkeypatch: pytest.MonkeyPatch) -> Any:
    return preparar_a_tela(monkeypatch)


def o_controle_do_diario(mundo: rm.RadioDeMentira, relogio: rm.Relogio, aparelho: str, *,
                         acorda_em: float = 0.0) -> dict[str, Any]:
    """O ``aparelho`` com a física de 06/10: o ``Pair`` dá e o controle guarda o host, mas não
    conecta sozinho; o ``Connect`` volta ``Failed`` com a varredura de pé no adaptador, e antes
    de ``acorda_em`` segundos do ``Pair``. Devolve o que se viu (``pareou``: a hora do ``Pair``)."""
    original = mundo._no_aparelho
    visto: dict[str, Any] = {"pareou": None}

    def no_aparelho(caminho: str, metodo: str) -> bd.Escrita:
        adaptador = mundo._endereco_do_hci(caminho.rsplit("/", 1)[0])
        if (bd.endereco_do_aparelho(caminho) or "") != aparelho:
            return original(caminho, metodo)
        fisico = mundo.fisicos[aparelho]
        if metodo == "Pair":
            antes, mundo.pair_mente = mundo.pair_mente, True
            try:
                feito = original(caminho, metodo)
            finally:
                mundo.pair_mente = antes
            if feito.feita:
                fisico.pareando = fisico.chamando = False
                fisico.host = adaptador
                visto["pareou"] = relogio.agora
            return feito
        if metodo == "Connect" and visto["pareou"] is not None:
            varrendo = mundo.mesa[rm.HCIS[adaptador]][bd.ADAPTADOR].get("Discovering")
            if varrendo or relogio.agora < visto["pareou"] + acorda_em:
                mundo.linha_do_tempo.append(("Connect", adaptador, aparelho))
                return bd.Escrita(False, "org.bluez.Error.Failed")
        return original(caminho, metodo)

    mundo._no_aparelho = no_aparelho  # type: ignore[method-assign]
    return visto


def central_sem_tela(mundo: rm.RadioDeMentira,
                     relogio: rm.Relogio) -> tuple[cr.CentralDoRadio, bd.DonoVivo]:
    dono = bd.DonoVivo(mundo)
    assert dono.ligar()
    central = cr.CentralDoRadio(
        dono=dono, onde_esta=mundo.onde_esta, movimento=mundo.hz,
        esquecer_na_ponte=mundo.esquecer_na_ponte, relogio=relogio, dormir=relogio.dormir,
        sysfs={"listar": lambda _p: [], "raiz": "/nao/existe"})
    return central, dono


def a_vigia_por(central: cr.CentralDoRadio, relogio: rm.Relogio, aparelho: str,
                segundos: float) -> cr.Movimento | None:
    """O fio do gesto depois do mover (``_vigiar_ate_resolver``): uma volta por segundo, NO
    TEMPO, até o movimento resolver ou os ``segundos`` passarem."""
    fim = relogio.agora + segundos
    while relogio.agora < fim:
        atual = central.movimento_de(aparelho)
        if atual is None or not atual.em_curso:
            return atual
        relogio.dormir(1.0)
        central.vigiar()
    return central.movimento_de(aparelho)


def _o_quarto_controle() -> rm.RadioDeMentira:
    """Três no ar na sala (o terceiro é o roxo), e o verde novo na mão: o quarto controle."""
    mundo = mundo_da_madrugada()
    mundo.pareado(SALA, ROXO)
    return mundo


def _linha(mundo: rm.RadioDeMentira, metodo: str, aparelho: str = "") -> list[int]:
    return [i for i, (m, _a, ap) in enumerate(mundo.linha_do_tempo)
            if m == metodo and (not aparelho or ap == aparelho)]


@pytest.mark.parametrize("destino", ADAPTADORES)
def test_a_busca_sai_do_destino_antes_do_connect_da_chave_nova(
    diario: Path, destino: str,
) -> None:
    """A ORDEM do diário, invertida: ``Pair`` → ``StopDiscovery`` → ``Connect``. Com a busca
    fechada antes, o primeiro ``Connect`` já encontra o adaptador livre e o controle chega.

    MORDIDA: tire o ``janela.fechar()`` que vem logo depois do ``Pair`` em ``_uma_janela``.
    """
    mundo, relogio = mundo_da_madrugada(), rm.Relogio()
    o_controle_do_diario(mundo, relogio, VERDE)
    central, dono = central_sem_tela(mundo, relogio)
    try:
        rm.ela_pareia(relogio, mundo, central, VERDE)
        feito = central.conectar(destino)
        (pair,) = _linha(mundo, "Pair", VERDE)
        parou = [i for i in _linha(mundo, "StopDiscovery") if i > pair]
        conectou = _linha(mundo, "Connect", VERDE)
        assert parou and conectou, mundo.linha_do_tempo
        assert parou[0] < conectou[0], (
            f"o Connect correu com a busca de pé, como no diário: {mundo.linha_do_tempo}")
        assert len(conectou) == 1, "o primeiro Connect, já sem a busca, não chegou"
        assert (feito.estado, feito.destino) == (cr.CHEGOU, destino)
        assert mundo.onde_esta(rm.uniq(VERDE)) == destino
        assert mundo.lapides == []
    finally:
        central.fechar(espera=5.0)
        dono.fechar()


@pytest.mark.parametrize("mundo_de", (mundo_da_madrugada, _o_quarto_controle),
                         ids=("terceiro", "quarto"))
@pytest.mark.parametrize("destino", ADAPTADORES)
def test_a_chave_nova_que_conecta_tarde_nao_sai_como_meia_chave(
    diario: Path, destino: str, mundo_de: Any,
) -> None:
    """O ciclo do diário: logo depois do ``Pair``, pareado e AINDA não conectado. O controle só
    atende aos 20 s. A central chama de novo (``Trusted`` e ``Connect``), e a chave NÃO sai —
    nem no tique da vigia, nem depois: quem chegou fica, com os outros no ar.

    MORDIDA: faça ``_provocar_a_chave_nova`` voltar logo no começo; a vigia passa os 60 s sem
    chamar o controle e o ``central_esquece_a_meia_chave`` volta (a lápide no destino).
    """
    mundo, relogio = mundo_de(), rm.Relogio()
    o_controle_do_diario(mundo, relogio, VERDE, acorda_em=20.0)
    no_ar_antes = {a: f.conectado_em for a, f in mundo.fisicos.items() if f.conectado_em}
    central, dono = central_sem_tela(mundo, relogio)
    try:
        rm.ela_pareia(relogio, mundo, central, VERDE)
        feito = central.conectar(destino)
        assert (feito.estado, feito.passo) == (cr.ESPERANDO, cr.PASSO_CONFERINDO), (
            "a régua não reproduziu o pareado-e-ainda-não-conectado")
        assert mundo.objeto(destino, VERDE)["Paired"] is True
        assert mundo.objeto(destino, VERDE)["Connected"] is False

        fim = a_vigia_por(central, relogio, VERDE, cr.PRAZO_DO_PENDENTE_S + 5.0)
        assert fim is not None and (fim.estado, fim.destino) == (cr.CHEGOU, destino), (
            f"a chave nova não ficou: {fim} — lápides {mundo.lapides}")
        assert mundo.lapides == [], "a central esqueceu a chave que acabou de fazer"
        assert mundo.objeto(destino, VERDE)["Connected"] is True
        assert len(_linha(mundo, "Connect", VERDE)) >= 2, "ninguém chamou o controle de novo"
        for aparelho, onde in no_ar_antes.items():
            assert mundo.fisicos[aparelho].conectado_em == onde, f"{aparelho} caiu do ar"

        a_vigia_por(central, relogio, VERDE, 10.0)
        assert mundo.lapides == [] and mundo.onde_esta(rm.uniq(VERDE)) == destino
    finally:
        central.fechar(espera=5.0)
        dono.fechar()


@pytest.mark.parametrize("destino", ADAPTADORES)
def test_o_prazo_da_chave_nova_conta_do_pair_e_nao_da_janela(
    diario: Path, destino: str,
) -> None:
    """Ela segura PS + Create aos 50 s da janela (no diário foram 16 s, e a chave viveu só
    os 42 s que sobravam). O controle atende 20 s depois do ``Pair``: aos 70 s da janela,
    depois dos 60 s do prazo velho — e a chave fica, porque o prazo conta do ``Pair``.

    MORDIDA: faça ``Movimento.prazo_desde`` devolver só o ``comecou``.
    """
    mundo, relogio = mundo_da_madrugada(), rm.Relogio()
    visto = o_controle_do_diario(mundo, relogio, VERDE, acorda_em=20.0)
    central, dono = central_sem_tela(mundo, relogio)
    try:
        rm.ela_pareia(relogio, mundo, central, VERDE, depois_de=50.0)
        feito = central.conectar(destino)
        assert visto["pareou"] is not None and visto["pareou"] - feito.comecou >= 50.0
        assert feito.prazo_desde == visto["pareou"]
        assert feito.publicar()["prazo_desde"] >= feito.publicar()["quando"] + 50.0
        fim = a_vigia_por(central, relogio, VERDE, cr.PRAZO_DO_PENDENTE_S + 5.0)
        assert fim is not None and fim.estado == cr.CHEGOU, f"{fim} — lápides {mundo.lapides}"
        assert mundo.lapides == []
    finally:
        central.fechar(espera=5.0)
        dono.fechar()


def test_a_chave_que_nunca_atende_sai_aos_sessenta_segundos_do_pair(diario: Path) -> None:
    # A decisão D-0610-CHAVE-NOVA-PRAZO-DO-PAIR.
    """O outro lado do contrato, que continua: a chave que o controle nunca atende sai como
    meia chave — mas só aos 60 s do ``Pair``, depois de chamada de novo a cada
    :data:`~central_do_radio.REPROVOCAR_S`. E nenhum ``Connect`` da volta espera além do prazo:
    o veredito da central não passa do instante em que a tela diz «Não conectou».

    MORDIDA do teto: chame ``dono.conectar`` sem o ``espera`` em ``_provocar_a_chave_nova``.
    """
    mundo, relogio = mundo_da_madrugada(), rm.Relogio()
    visto = o_controle_do_diario(mundo, relogio, VERDE, acorda_em=1e9)
    central, dono = central_sem_tela(mundo, relogio)
    esperas: list[float] = []
    conectar = dono.conectar

    def conectar_medindo(caminho: str, *, espera: float = bd.ESPERA_DO_CONNECT_S,
                         quem: str = "") -> bd.Escrita:
        if visto["pareou"] is not None:
            esperas.append(relogio.agora + espera - visto["pareou"])
        return conectar(caminho, espera=espera, quem=quem)

    dono.conectar = conectar_medindo  # type: ignore[method-assign]
    try:
        rm.ela_pareia(relogio, mundo, central, VERDE)
        central.conectar(QUARTO)
        fim = a_vigia_por(central, relogio, VERDE, cr.PRAZO_DO_PENDENTE_S + 5.0)
        assert fim is not None and (fim.estado, fim.motivo) == (cr.NAO_CHEGOU, cr.MOTIVO_PRAZO)
        assert relogio.agora - visto["pareou"] >= cr.PRAZO_DO_PENDENTE_S
        assert mundo.lapides == [(QUARTO, VERDE)]
        chamadas = len(_linha(mundo, "Connect", VERDE))
        assert chamadas >= cr.PRAZO_DO_PENDENTE_S // cr.REPROVOCAR_S - 1, chamadas
        tarde = [round(e, 1) for e in esperas[1:] if e > cr.PRAZO_DO_PENDENTE_S]
        assert esperas and not tarde, f"Connect esperando além do prazo do Pair: {tarde}"
        assert mundo.objeto(SALA, VERMELHO) is not None and mundo.objeto(SALA, AZUL) is not None
    finally:
        central.fechar(espera=5.0)
        dono.fechar()


def bancada_no_tempo(a08: Any, monkeypatch: pytest.MonkeyPatch, mundo: rm.RadioDeMentira,
                     relogio: rm.Relogio) -> Bancada:
    """A tela, a central e o tratador REAL do ``radio.dispensar``, com a hora de parede da tela
    andando junto com o relógio da central (o prazo das duas é o mesmo)."""
    base = time.time() - relogio.agora
    monkeypatch.setattr(time, "time", lambda: base + relogio.agora)
    bancada = Bancada(a08, monkeypatch, mundo, relogio)
    pelo_daemon = bancada.ponte.resultado

    def resultado(metodo: str, timeout: float | None = None, **params: Any) -> Any:
        if metodo != "radio.dispensar":
            return pelo_daemon(metodo, timeout, **params)
        bancada.ponte.chamadas.append((metodo, dict(params)))
        return asyncio.run(bancada.ponte.eu._handle_radio_dispensar(params))

    monkeypatch.setattr(bancada.ponte, "resultado", resultado)
    return bancada


def _linhas_de(cena: dict[str, Any], aparelho: str, lugar: str) -> list[dict[str, Any]]:
    return [a for a in cena["aparelhos"] if a.get("lugar") == id_da_tela(lugar)
            and (a.get("aparelho") or "") == id_da_tela(aparelho)]


@pytest.mark.parametrize("mundo_de", (mundo_da_madrugada, _o_quarto_controle),
                         ids=("terceiro", "quarto"))
@pytest.mark.parametrize("destino", ADAPTADORES)
def test_o_tirar_esta_linha_tira_e_a_linha_nao_volta(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch, destino: str, mundo_de: Any,
) -> None:
    # A decisão D-0610-TIRAR-LINHA-FECHA-O-VENCIDO.
    """A cura 2: o «Tirar esta linha» da gaveta tira a linha, e ela não volta em 10 s de tique.

    O caso medido: a tela e a central contam o mesmo prazo, mas quem fala primeiro é a tela (a
    vigia da central dá uma volta por segundo, e o ``Connect`` da volta segura o fio). Nesse
    vão a linha já diz «Não conectou», com o «Tirar esta linha» na gaveta, e o tratador
    respondia ``ocupado``: a tela levantava «a linha não saiu agora» e a linha ficava. Agora o
    clique é o veredito: a central fecha o movimento como a vigia fecharia (a meia chave sai
    antes, e o aparelho não volta como «Desligado») e a linha some.

    MORDIDA: tire o bloco do ``vencido`` de ``CentralDoRadio.dispensar`` (o ``ocupado`` volta),
    ou devolva o ``ocupado`` do ``_handle_radio_dispensar`` antes de perguntar à central.
    """
    mundo, relogio = mundo_de(), rm.Relogio()
    mundo.pareado(destino, VERDE, conectado=False, host=False)
    ligados = sorted(f.endereco for f in mundo.fisicos.values() if f.conectado_em)
    bancada = bancada_no_tempo(a08, monkeypatch, mundo, relogio)
    try:
        prazo = cr.PRAZO_DO_PENDENTE_S
        bancada.central._guardar(cr.Movimento(
            VERDE, destino, cr.ESPERANDO, cr.PASSO_CONFERINDO,
            motivo=cr.MOTIVO_SEM_CONFIRMACAO, pareou_no_destino=True,
            comecou=relogio() - prazo - 0.5, quando=time.time() - prazo - 0.5))
        campos = bancada.tique()
        (linha,) = _linhas_de(dict(a08._CENA_NA_TELA), VERDE, destino)
        assert linha.get("nao_conectou"), linha
        clique = {"alvo": linha["id"], "lugar": linha["lugar"]}
        assert (f'data-gesto="dispensar-linha" data-alvo="{linha["id"]}" '
                f'data-lugar="{linha["lugar"]}"') in campos["radio-moldes"]

        bancada.gesto("aparelho-menu", **clique)
        assert bancada.gesto("dispensar-linha", **clique) == {"armou": True}

        for volta in range(20):
            relogio.dormir(0.5)
            if volta % 2:
                bancada.central.vigiar()
            sobra = _linhas_de(bancada.cena(), VERDE, destino)
            assert not sobra, f"a linha voltou aos {0.5 * (volta + 1):.1f} s de tique: {sobra}"
        assert bancada.central.movimento_de(VERDE) is None
        assert mundo.objeto(destino, VERDE) is None, "a meia chave ficou e volta como Desligado"
        assert sorted(f.endereco for f in mundo.fisicos.values() if f.conectado_em) == ligados
    finally:
        bancada.fechar()


# ---- a página: as curas 3 e 4, no WebKit, na janela do piloto (1212 por 809) ----

MOCKUP_08 = Path(__file__).resolve().parents[2] / "mockup/08-conexoes.html"
A_CAIXA_ESCOLHE = "      if(aCaixaEscolhe(ev)) return;\n"
A_GAVETA_NA_LINHA = "      aGavetaNaLinha(p);\n"
O_PAINEL_DEIXA_OS_MENUS = (
    "      p.style.right = Math.max(0, Math.round(base.right - esquerda + 6)) + 'px';\n")

ABRE_A_GAVETA = r"""
(function(){
  const r = document.getElementById('cx8-3');
  r.checked = true; r.dispatchEvent(new Event('change', {bubbles: true}));
  const t = document.createElement('style');
  t.textContent = '.radio .painel{transition:none !important}';
  document.head.appendChild(t);
  document.querySelector('.radio .abre-lugar[data-alvo="L3"]').click();
  const b = document.querySelector('.radio .linha .menu-da-linha[data-alvo="nao-conectou-L3-P5"]');
  b.scrollIntoView({block: 'center'});
  b.click();
  return 'ok';
})()
"""

MEDE_A_GAVETA = r"""
(function(){
  const p = document.getElementById('rd-painel'), r = p.getBoundingClientRect();
  const b = document.querySelector('.radio .linha .menu-da-linha[data-alvo="nao-conectou-L3-P5"]');
  const rb = b.getBoundingClientRect();
  const livres = [...document.querySelectorAll('.radio .lugar.aberto .linha .menu-da-linha')]
    .map(function(m){
      const q = m.getBoundingClientRect();
      const e = document.elementFromPoint(q.left + q.width / 2, q.top + q.height / 2);
      return e === m || m.contains(e);
    });
  return JSON.stringify({
    aberto: p.classList.contains('aberto'), tipo: p.getAttribute('data-tipo'),
    largura: Math.round(r.width), altura: Math.round(r.height),
    perto_da_linha: Math.abs(r.top - rb.top) <= 12, a_esquerda_do_menu: r.right <= rb.left,
    estado: (p.querySelector('.estado') || {}).textContent || '',
    cor_do_estado: getComputedStyle(p.querySelector('.estado .nao-conectou') || p).color,
    botoes: [...p.querySelectorAll('.escolha .btn')].map(function(x){
      const s = getComputedStyle(x);
      return [x.textContent.trim(), s.backgroundColor, s.color];
    }),
    menus: livres.length, menus_livres: livres.filter(Boolean).length,
  });
})()
"""

O_CONECTAR_E_OUTRA_CAIXA = r"""
(function(){
  const r = document.getElementById('cx8-3');
  r.checked = true; r.dispatchEvent(new Event('change', {bubbles: true}));
  const t = document.createElement('style');
  t.textContent = '.radio .painel{transition:none !important}';
  document.head.appendChild(t);
  document.getElementById('rd-b-conectar').click();
  window.__antes = [...document.querySelectorAll('#rd-painel .op[aria-pressed="true"]')]
    .map(function(o){ return o.dataset.alvo; });
  // a caixa que se abre com o painel já aberto: a coluna dos «⋮» dela nasce depois do painel
  document.querySelector('.radio .abre-lugar[data-alvo="L3"]').click();
  const topo = document.querySelector('.radio .sala .lugar[data-id="L2"] .lugar-topo');
  const q = topo.getBoundingClientRect();
  let alvo = null;
  for (let x = q.right - 8; x > q.left + 40 && !alvo; x -= 6) {
    const e = document.elementFromPoint(x, q.top + q.height / 2);
    if (e && topo.contains(e) && !e.closest('button, input, a, [data-gesto]')) alvo = e;
  }
  window.__clicou = alvo ? (alvo.className || alvo.tagName) : '';
  if (alvo) alvo.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));
  return 'ok';
})()
"""

MEDE_O_ALVO = r"""
(function(){
  const p = document.getElementById('rd-painel');
  const fora = {
    antes: window.__antes, clicou: window.__clicou,
    aberto: p.classList.contains('aberto'), tipo: p.getAttribute('data-tipo'),
    depois: [...p.querySelectorAll('.op[aria-pressed="true"]')].map(function(o){
      return o.dataset.alvo; }),
  };
  // o clique cai onde o dedo cai: o «⋮» tem de ser o elemento daquele ponto, não um painel
  // por cima dele (um .click() direto no botão atravessaria o painel e mentiria)
  const m = document.querySelector('.radio .linha .menu-da-linha[data-alvo="celular-L3"]');
  m.scrollIntoView({block: 'center'});
  const q = m.getBoundingClientRect();
  const e = document.elementFromPoint(q.left + q.width / 2, q.top + q.height / 2);
  fora.no_ponto_do_menu = !!e && m.contains(e);
  fora.no_ponto = e ? (e.id || e.className || e.tagName) : '';
  if (e) e.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));
  fora.outra_linha = [p.getAttribute('data-tipo'),
                      document.getElementById('rd-painel-titulo').textContent];
  return JSON.stringify(fora);
})()
"""


def _a_pagina(tmp_path: Path, sem: str = "") -> Path:
    if not sem:
        return MOCKUP_08
    pagina = MOCKUP_08.read_text(encoding="utf-8")
    assert pagina.count(sem) == 1, sem
    cega = tmp_path / "08-mordida.html"
    cega.write_text(pagina.replace(sem, ""), encoding="utf-8")
    return cega


def _no_webkit_08(pagina: Path, prepara: str, mede: str) -> dict[str, Any]:
    from tests.unit.test_a_secao_cabe_o_painel_aberto import _no_webkit

    return _no_webkit(pagina, 0, prepara=prepara, mede=mede)


def test_com_o_conectar_aberto_a_caixa_de_outro_adaptador_muda_o_alvo(tmp_path: Path) -> None:
    """A cura 3: com o painel do «Conectar» aberto, o clique na caixa de outro adaptador é a
    escolha do chip (o alvo muda e o painel fica), e o «⋮» de outra linha troca a gaveta. Um véu
    cobria a seção e todo clique nela só fechava o painel; sem o véu, o painel ainda cobria a
    coluna dos «⋮», e o clique de verdade (no ponto do botão) caía nele.

    MORDIDAS: :func:`test_mordida_sem_a_caixa_que_escolhe_o_clique_so_fecha_o_painel` e
    :func:`test_mordida_com_o_painel_na_borda_o_menu_da_linha_fica_por_baixo`.
    """
    f = _no_webkit_08(_a_pagina(tmp_path), O_CONECTAR_E_OUTRA_CAIXA, MEDE_O_ALVO)
    assert f["clicou"], f"nenhum ponto vazio na caixa recebeu o clique (um véu por cima?): {f}"
    assert f["antes"] != ["L2"], f
    assert (f["aberto"], f["tipo"], f["depois"]) == (True, "conectar", ["L2"]), f
    assert f["no_ponto_do_menu"] is True, f"o «⋮» está por baixo de {f['no_ponto']!r}: {f}"
    assert f["outra_linha"] == ["menu", "Celular"], f


def test_mordida_com_o_painel_na_borda_o_menu_da_linha_fica_por_baixo(tmp_path: Path) -> None:
    # A decisão D-0610-O-CONECTAR-NAO-COBRE-OS-PONTOS.
    f = _no_webkit_08(_a_pagina(tmp_path, O_PAINEL_DEIXA_OS_MENUS), O_CONECTAR_E_OUTRA_CAIXA,
                      MEDE_O_ALVO)
    assert f["outra_linha"][0] == "conectar" and f["no_ponto_do_menu"] is False, f


def test_mordida_sem_a_caixa_que_escolhe_o_clique_so_fecha_o_painel(tmp_path: Path) -> None:
    f = _no_webkit_08(_a_pagina(tmp_path, A_CAIXA_ESCOLHE), O_CONECTAR_E_OUTRA_CAIXA, MEDE_O_ALVO)
    assert f["aberto"] is False and f["depois"] == f["antes"] != ["L2"], f


def test_a_gaveta_tem_o_tamanho_do_que_mostra_e_mora_ao_lado_da_linha(tmp_path: Path) -> None:
    """A cura 4 (foto 13 dela): a gaveta do «⋮» era a seção inteira, vazia, com o nome solto e um
    botão. Agora: do tamanho do que mostra, na altura da linha e à esquerda do «⋮» (a coluna dos
    «⋮» das outras linhas fica livre), com o estado do aparelho, e o que apaga é vermelho com
    letra branca.

    MORDIDA: :func:`test_mordida_sem_a_gaveta_na_linha_ela_volta_ao_canto`.
    """
    f = _no_webkit_08(_a_pagina(tmp_path), ABRE_A_GAVETA, MEDE_A_GAVETA)
    assert (f["aberto"], f["tipo"]) == (True, "menu"), f
    assert f["largura"] <= 340 and f["altura"] <= 160, f"maior que o que mostra: {f}"
    assert f["perto_da_linha"] and f["a_esquerda_do_menu"], f
    assert f["menus"] >= 3 and f["menus_livres"] == f["menus"], f"cobre «⋮» de outras: {f}"
    assert f["estado"].startswith(a08_tela.NAO_CONECTOU), f
    assert f["cor_do_estado"] != "rgb(255, 85, 85)", f"texto vermelho na gaveta: {f}"
    assert f["botoes"] == [[a08_tela.TIRAR_A_LINHA, "rgb(255, 85, 85)", "rgb(255, 255, 255)"]], f


def test_mordida_sem_a_gaveta_na_linha_ela_volta_ao_canto(tmp_path: Path) -> None:
    f = _no_webkit_08(_a_pagina(tmp_path, A_GAVETA_NA_LINHA), ABRE_A_GAVETA, MEDE_A_GAVETA)
    assert not (f["perto_da_linha"] and f["a_esquerda_do_menu"]), f

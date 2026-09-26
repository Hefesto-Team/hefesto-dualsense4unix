"""O-BRILHO-DAS-LUZES-SOBREVIVE-AO-APLICAR-01 — a pílula, o «Aplicar» e o «Salvar».

A queixa dela, 26/09/2026: *«tentei alterar a força dos leds
fraco medio e forte <!-- noqa-acento: citação literal dela -->
e ao aplicar ele não aplicar e ao salvar ele não salva»*.

**MEDIDO ANTES DA CURA**, na mesa de quatro da A-MARCA (o `IpcServer` real, o
merge do `PyDualSenseController`, o `SysfsLedNode` sobre arquivos, o laranja do
P2 e o ciano do P3 gravados no perfil), com o Forte clicado no P2:

    depois do clique     merge Forte · aparelho Forte · disco Forte · pílula Forte
    depois do «Aplicar»  merge Fraco · pílula Fraco · disco Forte
    depois do «Salvar»   disco Forte · pílula Fraco
    perfil reaplicado    merge Forte · pílula Forte

O valor morria no «Aplicar»: o rascunho não leva o campo, e o `DraftApplier`
troca o mapa inteiro de overrides do daemon (`reset_output_overrides`) pelo do
rascunho. O «Salvar» nunca perdeu o brilho no disco; a tela é que dizia
Fraco, porque a pílula pergunta ao daemon vivo. Dos seis gestos da aba 04 que
gravam no perfil, só este morria no «Aplicar» — e a varredura da seção 2, que
mede os seis, achou a outra metade da classe no «Salvar»: o tom, a caixa
`#RRGGBB` e o interruptor «Cores automáticas» gravam a cor com o número para o
qual ela foi escolhida (`lightbar_para_o_numero`), e o «Salvar» a regravava
sem ele. Sem o número a cor é `LEGADO`, e o tom do número de outro controle
virava fóssil na troca seguinte.

A MATRIZ, a regra dela: os três brilhos, P1 a P4, cabo e rádio.

**AS MORDIDAS**, arrancadas e devolvidas:

* tire o `player_led_brightness` de `DraftConfig._controllers_to_ipc` e a
  seção 1 inteira e a linha `brilho-luzes` da seção 2 reprovam — desde a
  O-APLICAR-NAO-SOLTA-O-TETO-DO-CONTROLE-01 (26/09/2026) a palavra de cada
  controle viaja no rascunho, e a segunda viagem do rodapé saiu;
* tire o `_com_a_procedencia_da_mesma_cor` do `DraftConfig.with_controller_leds`
  e a varredura reprova no tom, na caixa e nas «Cores automáticas» (P2 e P4) e
  em todo gesto do P2, além do tom que vira fóssil;
* tire a comparação das duas cores dela e a cor nova sai com o número da
  antiga (`test_a_cor_que_mudou_nao_leva_o_numero_da_antiga`);
* tire o `is None` do `rodape.aplicar` e o «Aplicar» pisca verde com o daemon
  calado (`test_sem_resposta_do_daemon_o_aplicar_recusa_dizendo`);
* tire o `_com_o_teto_da_economia` do `DraftApplier.apply` e a seção 3
  reprova — o Forte dela venceria a «Bateria longa».

O LAR É DE MENTIRA: o `conftest` desvia o `HOME` e os `XDG_*`; o perfil e o
`maquina.json` gravados aqui moram dentro dele.
"""
from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from hefesto_dualsense4unix.core.led_control import BRILHOS_DAS_LUZES
from tests.unit import test_a_04_pergunta_ao_daemon_vivo as viva
from tests.unit import test_a_barra_nao_escurece_ao_reaplicar as barra
from tests.unit import test_a_marca_da_cor_nao_some as marca
from tests.unit.test_a_marca_da_cor_nao_some import NOME, UNIQS

# O caminho de `pacotes` é posto pela mesa da A-MARCA, importada acima.
import pacotes
from pacotes import a04_iluminacao, rodape

#: O CLIQUE DOS BOTÕES DO RODAPÉ, como o piloto os manda.
CLIQUE = {"tipo": "button", "evento": "click"}

#: O global do perfil em cada caso: uma palavra DIFERENTE da clicada, senão o
#: Fraco clicado sobre o Fraco do perfil passaria sem a cura.
OUTRA = {"fraco": "forte", "medio": "fraco", "forte": "medio"}  # (noqa-acento) chaves ASCII


class _PonteDaAba(viva._Ponte):
    """A ponte da aba 04 com as duas portas do `perfil.gravar_e_reaplicar`, nos handlers REAIS.

    O interruptor «Cores automáticas» grava o perfil e o reaplica
    (`profile.switch`, depois `launch_env.refresh`). A ponte da A-04 recusa as
    duas, e sem elas a varredura da seção 2 não sabia clicar nele.
    """

    def profile_switch(self, nome: str) -> bool:
        self.mesa.rodar(self.mesa.server._handle_profile_switch({"name": nome}))
        return True

    def chamar(self, metodo: str, timeout: float | None = None, **params: Any) -> bool:
        if metodo != "launch_env.refresh":
            raise AttributeError(f"a régua não previu a aba chamar {metodo!r}")
        return isinstance(self.mesa.rodar(
            self.mesa.server._handle_launch_env_refresh(params)), dict)


@pytest.fixture
def mesa_de(tmp_path, monkeypatch):
    """A mesa de quatro da A-04-PERGUNTA-AO-DAEMON-VIVO-01, no transporte pedido."""
    feitas: list[Any] = []

    def montar(alvo: str = "todos", via: str = "usb") -> Any:
        monkeypatch.setattr(marca, "_handle_falso", lambda: viva._handle(via))
        m = viva.MesaViva(tmp_path / f"mesa-{len(feitas)}", pacotes, a04_iluminacao,
                          alvo=alvo)
        m.ponte = _PonteDaAba(m)
        feitas.append(m)
        vias = {m.ctl._detect_transport(h) for h in m.ctl._handles.values()}
        assert vias == {via}, f"a mesa pediu {via} e o backend leu {vias}"
        return m

    yield montar
    for m in feitas:
        m.fechar()


class _PonteDoRodape(barra._PonteDoRodape):
    """A ponte do rodapé, que guarda o rascunho que o «Aplicar» leva ao handler REAL.

    O-APLICAR-NAO-SOLTA-O-TETO-DO-CONTROLE-01 (26/09/2026): o «Aplicar» é UMA
    viagem só, e a palavra de cada controle vai no rascunho. A porta da pílula
    (`led.player_brightness_set`), que era a segunda viagem, é recusada como a
    da A-BARRA recusa o resto: um dublê que aceita tudo mede menos que o
    produto.
    """

    def __init__(self, mesa: Any) -> None:
        super().__init__(mesa)
        self.rascunhos: list[dict[str, Any]] = []

    def apply_draft_detalhado(self, payload: dict[str, Any]) -> Any:
        self.rascunhos.append(payload)
        return super().apply_draft_detalhado(payload)

    @property
    def luzes(self) -> list[dict[str, Any]]:
        """A palavra que o rascunho levou de cada controle — só de quem a escreveu."""
        return [{"brilho": palavra, "uniq": uniq}
                for rascunho in self.rascunhos
                for uniq, entrada in sorted((rascunho.get("controllers") or {}).items())
                if (palavra := ((entrada or {}).get("leds") or {}).get(
                    "player_led_brightness")) is not None]


def _aplicar(mesa: Any) -> _PonteDoRodape:
    ponte = _PonteDoRodape(mesa)
    rodape.aplicar(mesa.ctx(), CLIQUE, ponte)
    return ponte


def _salvar(mesa: Any) -> None:
    rodape.salvar(mesa.ctx(), CLIQUE, None)


def _o_global_das_luzes(mesa: Any, palavra: str) -> None:
    """O «Todos» das luzes no perfil, e o perfil reaplicado pela troca manual."""
    from hefesto_dualsense4unix.profiles.loader import load_profile, save_profile

    prof = load_profile(NOME)
    save_profile(prof.model_copy(update={"leds": prof.leds.model_copy(
        update={"player_led_brightness": palavra})}), origem="regua")
    mesa.trocar(NOME, "manual")


def _global_no_disco() -> str:
    from hefesto_dualsense4unix.profiles.loader import load_profile

    return str(load_profile(NOME).leds.player_led_brightness)


# ---------------------------------------------------------------------------
# 1. E1 — a pílula atravessa o «Aplicar», o «Salvar» e o perfil reaplicado
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("palavra", ["fraco", "medio", "forte"])  # (noqa-acento) chave ASCII
@pytest.mark.parametrize("via", ["usb", "bt"])
@pytest.mark.parametrize("n", [1, 2, 3, 4], ids=["P1", "P2", "P3", "P4"])
def test_a_pilula_sobrevive_ao_aplicar_ao_salvar_e_ao_perfil_reaplicado(
        mesa_de, n: int, via: str, palavra: str) -> None:
    """Clique → «Aplicar» → «Salvar» → perfil reaplicado: a palavra dela em todos.

    Em cada passo, o merge (o que o daemon manda), o que saiu ao aparelho, a
    pílula acesa na coluna dele e o disco. Os outros três seguem no global.
    """
    mesa = mesa_de("todos", via)
    global_ = OUTRA[palavra]
    _o_global_das_luzes(mesa, global_)
    mesa.clicar_na_pilula(n, palavra)
    degrau = BRILHOS_DAS_LUZES[palavra]
    assert mesa.degrau(n) == (degrau, degrau), "a régua precisa da pílula no aparelho"

    ponte = _aplicar(mesa)
    assert mesa.degrau(n) == (degrau, degrau), (
        f"P{n}/{via}: o «Aplicar» levou o aparelho a {mesa.degrau(n)}, e ela "
        f"escolheu {palavra!r}")
    assert mesa.pilula(n) == [palavra], (
        f"P{n}/{via}: depois do «Aplicar» a pílula acende {mesa.pilula(n)}")
    assert ponte.luzes == [{"brilho": palavra, "uniq": UNIQS[n - 1]}], (
        f"o «Aplicar» mandou {ponte.luzes} — só quem escreveu o campo recebe")

    _salvar(mesa)
    leds = mesa.disco(NOME, n)
    assert leds is not None and leds.player_led_brightness == palavra and (
        "player_led_brightness" in leds.model_fields_set), (
        f"P{n}/{via}: o «Salvar» deixou no disco {leds}")
    assert _global_no_disco() == global_, "o «Salvar» mexeu no «Todos» das luzes"
    assert mesa.pilula(n) == [palavra], "depois do «Salvar» a pílula mudou"

    mesa.trocar(NOME, "manual")
    assert mesa.degrau(n) == (degrau, degrau), (
        f"P{n}/{via}: o perfil reaplicado levou o aparelho a {mesa.degrau(n)}")
    assert mesa.pilula(n) == [palavra]
    for outro in {1, 2, 3, 4} - {n}:
        assert mesa.pilula(outro) == [global_], (
            f"a palavra do P{n} vazou para o P{outro}: {mesa.pilula(outro)}")


@pytest.mark.parametrize("via", ["usb", "bt"])
def test_o_aplicar_leva_a_palavra_de_cada_um_e_nao_escreve_em_quem_nao_escolheu(
        mesa_de, via: str) -> None:
    """Dois controles com palavras próprias, dois no global: cada um no seu.

    O controle que não escreveu o campo não ganha opinião no «Aplicar» — ele
    herda o global que a ativação deixou, e a troca de perfil segue mandando.
    """
    mesa = mesa_de("todos", via)
    _o_global_das_luzes(mesa, "medio")  # (noqa-acento) chave ASCII
    mesa.clicar_na_pilula(2, "forte")
    mesa.clicar_na_pilula(4, "fraco")
    ponte = _aplicar(mesa)
    assert sorted(e["uniq"] for e in ponte.luzes) == [UNIQS[1], UNIQS[3]]
    assert [mesa.pilula(n) for n in (1, 2, 3, 4)] == [
        ["medio"], ["forte"], ["medio"], ["fraco"]]  # (noqa-acento) chaves ASCII
    for n in (1, 3):
        assert mesa.disco(NOME, n) is None or (
            "player_led_brightness" not in mesa.disco(NOME, n).model_fields_set)


# ---------------------------------------------------------------------------
# 2. E2 — a varredura da classe: todo gesto da aba 04 que grava no perfil
# ---------------------------------------------------------------------------
def _gestos_que_gravam() -> list[str]:
    """Os gestos da aba 04 que declaram `grava=` — lidos, não digitados.

    TODA porta, e não só a `save_profile`: o interruptor «Cores automáticas»
    declara `grava="gravar_e_reaplicar"` e grava a cor de cada controle COM o
    número dela, que é a outra metade da classe que o «Salvar» perdia. Um
    filtro pela porta deixava de fora um gesto que grava no mesmo perfil.
    """
    return sorted(nome for (pagina, nome) in pacotes.GESTOS_QUE_MEXEM
                  if pagina == a04_iluminacao.PAGINA)


#: COMO A TELA CLICA CADA UM na coluna de um controle. A lista de QUEM entra é
#: a de cima; esta tabela só diz o clique — um gesto novo que grava e não está
#: aqui reprova nomeando (`test_a_varredura_conhece_todo_gesto_que_grava`).
#: O `auto-cores` é da aba inteira: o `uniq` do clique não o endereça, e a
#: coluna medida é a do controle cuja cor ele gravou.
CLIQUES: dict[str, dict[str, Any]] = {
    "cor": {"hex": "8000FF"},
    "reenviar": {"texto": "#12AB34"},
    "brilho": {"valor": "40", "tipo": "input", "evento": "change"},
    "apagar": {},
    "brilho-luzes": {"luzes": "forte"},
    "auto-cores": {"tipo": "input", "evento": "change"},
}

#: O QUE A COLUNA PINTA do gesto — a tela que ela olha depois de cada botão.
PINTADO = ("brilho", "brilho-pct", "hex", "brilho-luzes")


def test_a_varredura_conhece_todo_gesto_que_grava() -> None:
    """A lista sai do pacote; a régua sabe clicar em todos, e em nenhum a mais."""
    derivada = _gestos_que_gravam()
    assert derivada, "a varredura não achou gesto nenhum que grava — a leitura quebrou"
    assert set(derivada) == set(CLIQUES), (
        f"a aba 04 grava por {derivada} e a varredura sabe clicar {sorted(CLIQUES)}")


def _o_que_a_tela_mostra(mesa: Any, n: int) -> dict[str, Any]:
    coluna = mesa.coluna(n)
    return {"luz": mesa.luz(n), "luzes": mesa.degrau(n)[0],
            **{campo: coluna.get(campo) for campo in PINTADO}}


def _o_disco(mesa: Any, n: int) -> dict[str, Any]:
    """Os campos escritos na luz do P<n>, e os dois globais da aba que a coluna lê.

    O interruptor «Cores automáticas» é da aba inteira: no P2, que já tinha a
    cor gravada com o número, o que ele muda no disco é o global.
    """
    from hefesto_dualsense4unix.profiles.loader import load_profile

    globais = load_profile(NOME).leds
    saida = {f"global.{campo}": getattr(globais, campo)
             for campo in ("auto_player_colors", "player_led_brightness")}
    leds = mesa.disco(NOME, n)
    if leds is None:
        return saida
    return {**saida, **{campo: getattr(leds, campo) for campo in leds.model_fields_set}}


@pytest.mark.parametrize("via", ["usb", "bt"])
@pytest.mark.parametrize("n", [2, 4], ids=["P2-com-cor-no-perfil", "P4-sem-opiniao"])
@pytest.mark.parametrize("gesto", _gestos_que_gravam())
def test_todo_gesto_que_grava_atravessa_o_aplicar_e_o_salvar(
        mesa_de, gesto: str, n: int, via: str) -> None:
    """O que a coluna mostra depois do clique é o que ela mostra depois dos botões.

    E o que estava no disco depois do clique continua lá depois do «Salvar»
    (o «Salvar» pode ACRESCENTAR campo, e não trocar nem tirar), e volta quando
    o perfil é reaplicado.
    """
    mesa = mesa_de("todos", via)
    antes = _o_disco(mesa, n)
    fn = pacotes.gesto_da_pagina(a04_iluminacao.PAGINA, gesto)
    fn(mesa.ctx(), {"uniq": UNIQS[n - 1], **CLIQUES[gesto]}, mesa.ponte)
    tela = _o_que_a_tela_mostra(mesa, n)
    gravado = _o_disco(mesa, n)
    assert gravado != antes, f"a régua precisa do {gesto!r} gravando no disco do P{n}"

    _aplicar(mesa)
    assert _o_que_a_tela_mostra(mesa, n) == tela, (
        f"{gesto}/P{n}/{via}: o «Aplicar» mudou a coluna de {tela} para "
        f"{_o_que_a_tela_mostra(mesa, n)}")
    _salvar(mesa)
    assert _o_que_a_tela_mostra(mesa, n) == tela, f"{gesto}/P{n}/{via}: o «Salvar» mudou a coluna"
    disco = _o_disco(mesa, n)
    perdidos = {k: (v, disco.get(k)) for k, v in gravado.items() if disco.get(k) != v}
    assert not perdidos, f"{gesto}/P{n}/{via}: o «Salvar» trocou no disco {perdidos}"
    mesa.trocar(NOME, "manual")
    assert _o_que_a_tela_mostra(mesa, n) == tela, (
        f"{gesto}/P{n}/{via}: o perfil reaplicado mostra {_o_que_a_tela_mostra(mesa, n)}")


@pytest.mark.parametrize("via", ["usb", "bt"])
def test_o_tom_regravado_pelo_salvar_nao_vira_fossil(mesa_de, via: str) -> None:
    """O P4 escolhe o tom do número 2; o «Salvar» o regrava; o perfil reaplicado o mantém.

    O tom da guia grava a cor COM o número para o qual foi escolhida
    (`lightbar_para_o_numero`). Sem ele a cor é `LEGADO`, e o resolvedor a
    prova fóssil pela forma: o tom do número de outro controle da mesa.

    **A MORDIDA:** tire o `_a_procedencia_da_mesma_cor` do `_draft_do_ativo`
    e o P4 acende a cor do número dele depois da troca manual.
    """
    from hefesto_dualsense4unix.core.led_control import player_slot_color

    from tests.unit.test_a_04_pergunta_ao_daemon_vivo import _na
    from tests.unit.test_a_marca_da_cor_nao_some import BRILHO_GLOBAL

    tom = player_slot_color(2)
    mesa = mesa_de("todos", via)
    mesa.clicar_no_tom(4, tom)
    assert mesa.luz(4) == _na(tom, BRILHO_GLOBAL), "a régua precisa do tom no P4"
    _salvar(mesa)
    assert mesa.disco(NOME, 4).lightbar_para_o_numero == 4, (
        f"o «Salvar» tirou do disco o número do tom: {mesa.disco(NOME, 4)}")
    mesa.trocar(NOME, "manual")
    assert mesa.luz(4) == _na(tom, BRILHO_GLOBAL), (
        f"o tom que ela escolheu virou fóssil depois do «Salvar»: o P4 acende {mesa.luz(4)}")


@pytest.mark.parametrize("via", ["usb", "bt"])
def test_a_cor_que_mudou_nao_leva_o_numero_da_antiga(mesa_de, via: str) -> None:
    """A cor viva que difere do disco é gravada SEM o número da cor que ela substitui.

    O P4 escolhe o tom do número 2 (o disco guarda o número 4 com ele); depois
    a luz dele muda só no daemon — é a camada da mão que atravessa a troca
    automática de perfil. O «Salvar» grava a cor viva, e o número 4 era da cor
    antiga: colá-lo na nova afirmaria para qual número ela foi escolhida sem
    ninguém saber.

    **A MORDIDA:** tire a comparação das duas cores de
    `_a_procedencia_da_mesma_cor` e o disco sai com a cor nova e o número velho.
    """
    from hefesto_dualsense4unix.core.led_control import player_slot_color

    from tests.unit.test_a_04_pergunta_ao_daemon_vivo import ROXO, _na
    from tests.unit.test_a_marca_da_cor_nao_some import BRILHO_GLOBAL

    mesa = mesa_de("todos", via)
    mesa.clicar_no_tom(4, player_slot_color(2))
    assert mesa.disco(NOME, 4).lightbar_para_o_numero == 4, "a régua precisa do número no disco"
    mesa.ponte.led_set_detalhado(ROXO, BRILHO_GLOBAL, UNIQS[3])
    assert mesa.luz(4) == _na(ROXO, BRILHO_GLOBAL), "a régua precisa da luz nova no P4"
    _salvar(mesa)
    leds = mesa.disco(NOME, 4)
    assert tuple(leds.lightbar) == ROXO, f"o «Salvar» não gravou a cor viva: {leds}"
    assert leds.lightbar_para_o_numero is None, (
        f"o «Salvar» colou o número da cor antiga na cor nova: {leds}")


@pytest.mark.parametrize("via", ["usb", "bt"])
def test_sem_resposta_do_daemon_o_aplicar_recusa_dizendo(mesa_de, via: str) -> None:
    """O daemon calado: o «Aplicar» recusa com a frase do motor, com ou sem a palavra.

    A frase é a que a pílula já usa (`a04_iluminacao.sem_resposta_do_daemon`):
    nada de recado novo. Até a O-APLICAR-NAO-SOLTA-O-TETO-DO-CONTROLE-01 só
    recusava quem tinha a palavra das luzes, pela segunda viagem; o perfil sem
    ela piscava verde com o daemon desligado.

    **A MORDIDA:** tire o `is None` do `rodape.aplicar` e o «Aplicar» pisca
    verde sem ter chegado a lugar nenhum.
    """
    import re

    class _Calada(_PonteDoRodape):
        def apply_draft_detalhado(self, payload: dict[str, Any]) -> Any:
            self.rascunhos.append(payload)
            return None

    mesa = mesa_de("todos", via)
    frase = re.escape(a04_iluminacao.sem_resposta_do_daemon())
    calada = _Calada(mesa)
    with pytest.raises(RuntimeError, match=frase):
        rodape.aplicar(mesa.ctx(), CLIQUE, calada)
    assert calada.luzes == [], "sem palavra no perfil, o rascunho levou uma"

    mesa.clicar_na_pilula(2, "forte")
    calada = _Calada(mesa)
    with pytest.raises(RuntimeError, match=frase):
        rodape.aplicar(mesa.ctx(), CLIQUE, calada)
    assert calada.luzes == [{"brilho": "forte", "uniq": UNIQS[1]}], calada.luzes


# ---------------------------------------------------------------------------
# 3. A economia de bateria vence a palavra dela, como na ativação
# ---------------------------------------------------------------------------
@pytest.fixture
def economia() -> Iterator[Any]:
    """Liga a economia pelo `maquina.json` do lar de mentira — o daemon e a tela o leem."""
    from hefesto_dualsense4unix.profiles.schema import registrar_declaracao_da_mesa
    from hefesto_dualsense4unix.utils.maquina import carregar_maquina, gravar_maquina

    registrar_declaracao_da_mesa(carregar_maquina)

    def ligar(declaracao: dict[str, Any]) -> None:
        assert gravar_maquina(declaracao), f"o lar de mentira recusou {declaracao}"

    yield ligar
    registrar_declaracao_da_mesa(None)


@pytest.mark.parametrize("via", ["usb", "bt"])
def test_na_bateria_longa_o_aplicar_nao_tira_as_luzes_do_fraco(
        mesa_de, economia, via: str) -> None:
    """A mesa em «Bateria longa»: o Forte do disco não volta pelo «Aplicar».

    A ativação põe as luzes de todos no Fraco (`leds_na_economia`), e o
    «Aplicar» não pode ser a porta que escapa dela. O rascunho leva o Forte
    dela — é o que o disco guarda —, e o teto é posto do outro lado
    (`DraftApplier._com_o_teto_da_economia`, O-APLICAR-NAO-SOLTA-O-TETO-DO-CONTROLE-01).
    """
    fraco, forte = BRILHOS_DAS_LUZES["fraco"], BRILHOS_DAS_LUZES["forte"]
    mesa = mesa_de("todos", via)
    mesa.clicar_na_pilula(2, "forte")
    economia({"orcamento": {"teto": "economia"}})
    mesa.trocar(NOME, "manual")
    assert mesa.degrau(2)[0] == fraco, "a régua precisa da economia pondo o P2 no Fraco"
    ponte = _aplicar(mesa)
    assert ponte.luzes == [{"brilho": "forte", "uniq": UNIQS[1]}], ponte.luzes
    assert mesa.degrau(2) == (fraco, fraco), (
        f"o «Aplicar» tirou o P2 da economia: {mesa.degrau(2)} (Forte é {forte})")


@pytest.mark.parametrize("via", ["usb", "bt"])
def test_a_economia_de_um_controle_so_nao_recebe_a_palavra_e_o_vizinho_recebe(
        mesa_de, economia, via: str) -> None:
    """A economia ligada só no P2: o aparelho do P4 no Forte, e o do P2 no Fraco.

    O rascunho leva o Forte dos dois — é o que o disco guarda —, e o teto do
    P2 é posto do outro lado, pelo mesmo dono da ativação
    (O-APLICAR-NAO-SOLTA-O-TETO-DO-CONTROLE-01).
    """
    from hefesto_dualsense4unix.profiles.schema import declaracao_da_economia

    fraco, forte = BRILHOS_DAS_LUZES["fraco"], BRILHOS_DAS_LUZES["forte"]
    mesa = mesa_de("todos", via)
    mesa.clicar_na_pilula(2, "forte")
    mesa.clicar_na_pilula(4, "forte")
    economia(declaracao_da_economia(UNIQS[1], True))
    mesa.trocar(NOME, "manual")
    ponte = _aplicar(mesa)
    assert ponte.luzes == [{"brilho": "forte", "uniq": UNIQS[1]},
                           {"brilho": "forte", "uniq": UNIQS[3]}], ponte.luzes
    assert mesa.degrau(4) == (forte, forte)
    assert mesa.degrau(2) == (fraco, fraco), "o Forte dela venceu a economia do P2"

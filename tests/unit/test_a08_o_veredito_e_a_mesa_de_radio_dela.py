#!/usr/bin/env python3
"""O CHECK-UP RESPONDE EM UMA LINHA, e a mesa de rádio é a DELA."""
from __future__ import annotations

import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

BANCADA = RAIZ / "mockup/08-conexoes.html"


def _pacote():  # type: ignore[no-untyped-def]
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes

    return a08_conexoes


def _item(estado: str, chave: str = "", ordem: object = None):  # type: ignore[no-untyped-def]
    """Um `Item` do exame — o do PRODUTO, nunca um dublê de forma parecida."""
    from hefesto_dualsense4unix.integrations.exame_da_mesa import Item

    return Item(chave=chave or f"c-{estado}", rotulo="", estado=estado,
                porque="", ordem=ordem)


def _ordem(chave: str, arranjo: str):  # type: ignore[no-untyped-def]
    """Uma `Ordem` do catálogo, com o mínimo que a dispensa endereça."""
    from hefesto_dualsense4unix.integrations.ordens_da_mesa import Linha, Ordem

    vazia = Linha(texto="", selo="medido_aqui")
    return Ordem(
        chave=chave,
        acao="Mova o adaptador",
        o_que_eu_vi=vazia,
        por_que_importa=vazia,
        ganho_esperado=vazia,
        arranjo=arranjo,
    )


def test_a_frase_do_veredito_e_a_do_dono() -> None:
    """A frase NÃO nasce no pacote: ela é de `ordens_da_mesa.cabecalho()`."""
    from hefesto_dualsense4unix.integrations.ordens_da_mesa import cabecalho

    p = _pacote()
    saiu = p._veredito_do_exame([_item("certo"), _item("certo")])
    esperado = cabecalho(ordens=[], conferidas=2, sem_resposta=0, dispensadas=0)
    assert saiu["veredito"] == esperado.texto, (
        f"o veredito disse {saiu['veredito']!r} e o dono escreve "
        f"{esperado.texto!r} — alguém digitou a frase no pacote")


def test_a_cor_e_a_do_pior_achado() -> None:
    """Um `problema` entre cinco `certo` acende o vermelho, e só ele."""
    p = _pacote()
    itens = [_item("certo"), _item("problema"), _item("certo")]
    saiu = p._veredito_do_exame(itens)
    assert saiu["veredito-problema"] == "problema", (
        "a linha de veredito não acendeu no pior achado")
    for estado, endereco in p.ENDERECO_DO_VEREDITO.items():
        if estado == "problema":
            continue
        assert saiu[endereco] == "", (
            f"`{endereco}` acendeu junto com o `problema`. Um instante com dois "
            f"acesos deixa o que está QUEBRADO com a cor do que só podia estar "
            f"melhor, que é a confusão que ela mandou desfazer em 02/09.")


def test_o_veredito_nao_diz_nada_a_mudar_com_uma_linha_grave() -> None:
    """A MORDIDA da cicatriz `6c86e295`, e ela é a razão de a função existir."""
    from hefesto_dualsense4unix.app.actions.config.secao_exame import FRASE_DO_SELO
    from hefesto_dualsense4unix.integrations.ordens_da_mesa import cabecalho

    p = _pacote()
    saiu = p._veredito_do_exame([_item("problema"), _item("certo")])
    verde = cabecalho(ordens=[], conferidas=2, sem_resposta=0, dispensadas=0).texto
    assert saiu["veredito"] != verde, (
        f"com uma linha em `problema` o veredito escreveu {verde!r} — a frase "
        f"do cabeçalho, que não conhece `problema`. É a cicatriz 6c86e295 "
        f"voltando: o verde convivendo com o vermelho na mesma seção.")
    assert saiu["veredito"] == FRASE_DO_SELO["problema"], (
        "quando o estado das linhas vence o do cabeçalho, a frase tem de ser a "
        "do estado — e ela também tem dono (`secao_exame.FRASE_DO_SELO`)")


def test_o_que_ela_calou_nao_segura_a_cor() -> None:
    """A ordem DISPENSADA sai da conta — senão o ⊘ é botão morto."""
    p = _pacote()
    ordem = _ordem("vizinhanca", "arranjo-de-hoje")
    itens = [_item("certo"), _item("atencao", chave="o1", ordem=ordem)]  # (dado) noqa-acento

    antes = dict(p._DISPENSADAS)
    try:
        p._DISPENSADAS = {}
        com_ordem = p._veredito_do_exame(itens)
        p._DISPENSADAS = {"vizinhanca": "arranjo-de-hoje"}
        calada = p._veredito_do_exame(itens)
    finally:
        p._DISPENSADAS = antes

    assert com_ordem["veredito-atencao"] == "atencao", (  # noqa-acento: chave e valor de dado
        "com a ordem aberta o topo tinha de estar em `atencao`")  # noqa-acento: nome do estado
    assert calada["veredito-atencao"] == "", (
        "a ordem que ela dispensou continuou segurando o topo em laranja — o ⊘ "
        "grava e a tela não muda, que é a definição de botão morto")


def test_a_linha_de_veredito_saiu_da_tela() -> None:
    """A LINHA SAIU — 26/09/2026, pedido dela com a janela maximizada."""
    html = BANCADA.read_text()
    assert 'class="veredito"' not in html, (
        "a linha de veredito voltou ao desenho — ela saiu a pedido dela")
    saiu = _pacote().pacote(_ctx())
    assert "veredito" not in saiu, (
        "o `pacote()` emite `veredito` para um endereço que a tela não tem")


def _ctx():  # type: ignore[no-untyped-def]
    from hefesto_dualsense4unix.interface.pacotes import Contexto

    p1, p2 = "aa:bb:cc:00:00:01", "aa:bb:cc:00:00:02"
    mesa = [
        {"pref": "p1", "uniq": p1, "jogador": 1, "cor": "white",
         "nome": "White", "via": "USB", "transporte": "usb", "mascara": "DualSense"},
        {"pref": "p2", "uniq": p2, "jogador": 2, "cor": "galactic-purple",
         "nome": "Galactic Purple", "via": "BT", "transporte": "bt",
         "mascara": "DualSense"},
    ]
    conectados = [
        {"uniq": p1, "transport": "usb", "connected": True, "battery_pct": 100},
        {"uniq": p2, "transport": "bt", "connected": True, "battery_pct": 64},
    ]
    return Contexto(state={"controllers": conectados}, mesa=mesa,
                    conectados=conectados, estados={})


def test_a_dica_da_luz_segue_o_transporte() -> None:
    """As duas frases são do dono, e não a mesma congelada."""
    from hefesto_dualsense4unix.app.actions.config.secao_controles import (
        DICA_NO_CABO,
        DICA_NO_RADIO,
    )

    p = _pacote()
    assert p.dica_da_luz("usb") == DICA_NO_CABO
    assert p.dica_da_luz("bt") == DICA_NO_RADIO
    assert p.dica_da_luz("") == DICA_NO_CABO, (
        "transporte vazio é TRAVA, pela mesma razão do gesto: `Disconnect` "
        "sobre um controle cujo transporte ninguém leu é um pedido no escuro")


def test_a_dica_da_luz_nao_anexa_o_aviso_da_mesa_suja(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """A mesa suja NÃO muda a dica — FRASES-E-DICAS-02, 13/09/2026."""
    from hefesto_dualsense4unix.app.actions.config.secao_controles import DICA_NO_RADIO
    from hefesto_dualsense4unix.integrations import sinal_da_barra as sb

    p = _pacote()
    limpa = p.dica_da_luz("bt")
    monkeypatch.setattr(sb, "limpo_para_conectar",
                        lambda *a, **k: (sb.CONFIANCA_SUSPEITA, "dublê", (4242,)))
    suja = p.dica_da_luz("bt")
    assert suja == limpa == DICA_NO_RADIO, (
        "a dica da luz mudou com outro programa segurando controle — o aviso da "
        f"mesa suja voltou a ser anexado: {suja!r}")


def test_a_razao_do_nascimento_nao_chega_a_dica() -> None:
    """A RAZÃO DO NASCIMENTO SAIU DA DICA — FRASES-E-DICAS-03, 13/09/2026.

    CONTRATO QUE MUDOU: até esta data a condenação escrevia a razão depois do
    que o botão faz. A ordem dela de 13/09
    (`docs/process/sprints/arquivados/2026-09-13-A-TERCEIRA-LISTA-DELA-INDICE.md`) tira da
    tela frase de aviso em toda forma, `title` incluído: a dica fica com o que o
    botão faz, e o carimbo `nascimento` fica no `state_full`, para o diagnóstico.

    PASSA PELO TIQUE: os dois controles desta mesa chegam condenados no estado,
    e o `pacote()` escreve para cada um só a dica do dono.
    """
    from hefesto_dualsense4unix.app.actions.config.secao_controles import (
        DICA_NO_CABO,
        DICA_NO_RADIO,
    )

    p = _pacote()
    porque = "Esta conexão nasceu com outro programa segurando o controle"
    ctx = _ctx()
    for controle in ctx.conectados:
        controle["nascimento"] = {"pede_reconexao": True, "porque": porque}
    dicas = [coluna.get("luz-dica", "") for coluna in p.pacote(ctx)["colunas"].values()]
    assert sorted(dicas) == sorted([DICA_NO_CABO, DICA_NO_RADIO]), (
        "com os dois controles condenados, a dica da luz deixou de ser só a do "
        f"dono — a razão do carimbo de nascimento voltou à tela: {dicas!r}")


def test_o_botao_da_luz_tem_a_dica_e_a_trava_em_nos_diferentes() -> None:
    """Um `data-campo` por nó — a classe no `<i>`, a dica no `<button>`."""
    html = BANCADA.read_text()
    botoes = re.findall(r'<button[^>]*data-gesto="luz-nao-acende"[^>]*>', html)
    assert botoes, "o botão 'A luz não acende' sumiu do desenho"
    for botao in botoes:
        assert 'data-campo="luz-dica"' in botao, (
            "o botão da luz não tem endereço para a dica — ela continua sendo "
            "a do desenho e mente quando o controle troca de transporte")
        assert 'data-hef-atributo="title"' in botao
        assert 'data-campo="luz-trava"' not in botao, (
            "a classe e a dica voltaram para o mesmo nó — o vocabulário é UM "
            "`data-campo` por nó, e uma das duas vai ficar sem endereço")
    irmaos = re.findall(r'<i class="ltrava[^"]*"[^>]*></i><button[^>]*'
                        r'data-gesto="luz-nao-acende"', html)
    assert len(irmaos) == len(botoes), (
        f"{len(irmaos)} dos {len(botoes)} botões da luz têm o interruptor "
        f"colado ANTES deles — o `~` do CSS só alcança irmãos posteriores, e o "
        f"botão sem irmão anterior nunca apaga")
    for irmao in irmaos:
        assert 'data-campo="luz-trava"' in irmao, (
            "o interruptor da trava ficou sem endereço — a classe volta a ser a "
            "do desenho, cravada pela posição no mockup")


def test_a_dica_da_luz_chega_ao_pacote() -> None:
    """A ligação — uma dica por controle, no `colunas`."""
    p = _pacote()
    saiu = p.pacote(_ctx())
    for uniq, coluna in saiu["colunas"].items():
        assert coluna.get("luz-dica"), (
            f"o controle {uniq[:4]}… saiu sem `luz-dica` — o botão fica com o "
            f"`title` do desenho")


def test_o_escopo_le_o_valor_da_maquina() -> None:
    """As duas falas são as do `<select>` que saiu — nem uma palavra nova."""
    p = _pacote()
    assert p.escopo_do_botao_do_mic({"mic_button_toggles_system": True}) == (
        p.FALA_DO_BOTAO_DO_MIC[True])
    assert p.escopo_do_botao_do_mic({"mic_button_toggles_system": False}) == (
        p.FALA_DO_BOTAO_DO_MIC[False])
    assert p.escopo_do_botao_do_mic({}) == "", (
        "sem resposta do daemon a tela afirmou um dos dois — o travessão do "
        "piloto é a resposta honesta")
    assert p.pacote(_ctx())["mic-escopo"] == "", (
        "o `_ctx()` não publica a chave, e o pacote inventou um valor")


def test_o_custo_do_mic_no_radio_nao_e_digitado(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """A MORDIDA do número: mude a constante do medidor e a frase acompanha.

    Os 16,3 do desenho conferiam com `radio_da_mesa` HOJE — eles eram a segunda
    grafia. `frase_da_capacidade_do_mic` deriva os quatro números das constantes
    do medidor, *"que é o mesmo lugar de onde a barra de Rádio em uso tira os
    dela"*.
    """
    from hefesto_dualsense4unix.integrations import radio_da_mesa as rm

    p = _pacote()
    antes = p.dica_do_microfone("bt")
    monkeypatch.setattr(rm, "HZ_AUDIO_COM_MIC", rm.HZ_AUDIO_COM_MIC * 3)
    depois = p.dica_do_microfone("bt")
    assert antes != depois, (
        "a frase do custo do microfone não seguiu a constante do medidor — ela "
        "está digitada, e no dia em que alguém remedir o A/B a janela estável "
        "acompanha e o HTML não")


def test_o_mic_pelo_cabo_nao_cobra_turno_de_radio() -> None:
    """Pelo cabo não há conta a fazer — e "0 turnos" seria um número sem conta."""
    p = _pacote()
    cabo = p.dica_do_microfone("usb")
    assert p._MIC_NAO_CUSTA_RADIO in cabo
    assert "turnos de rádio" not in cabo.replace(p._MIC_NAO_CUSTA_RADIO, ""), (
        "a frase do cabo trouxe a conta do rádio junto")



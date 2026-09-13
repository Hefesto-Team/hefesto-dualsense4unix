#!/usr/bin/env python3
"""A faixa laranja da aba Jogar diz o que ela pediu e o daemon não alcançou.

POR QUE ESTA RÉGUA EXISTE, medido em 02/09/2026 na foto da aba com os dois
controles dela na mesa: a faixa vinha CRAVADA no HTML —

    ● Vai mudar para **Sony DualSense** quando você clicar em **Aplicar**

— e o chip **Sony DualSense** já estava aceso na mesma foto. As duas metades da
frase eram falsas, e por motivos diferentes:

1. o alvo sai de `aba01.MODO_ACESO`, logo a frase só sabe prometer o que já está
   valendo (a cura de 31/08 matou a contradição e deixou uma tautologia);
2. **clicar em "Aplicar" não troca modo nem máscara nesta interface.** O rodapé
   daqui manda `profile.apply_draft`, e o contrato desse payload está escrito no
   produto (`app/draft_config.to_ipc_dict`, PERFIL-SALVA-TUDO-01): *"`mode` e
   `suppress_desktop_emulation` … NÃO viajam no 'Aplicar'"*.

O QUE A RÉGUA COBRA, e cada item é uma forma de a cura morrer calada:

* os DOIS endereços saem do pacote em TODO estado — sem isso a frase cravada
  sobrevive na tela, que é o defeito inteiro;
* a pendência MORRE quando o daemon alcança (a regra é
  `home_actions.reconciliar_pendente`, e sem ela a faixa promete para sempre);
* o daemon calado NÃO apaga a escolha (o ramo `visivel=False` do motor);
* a frase é a do produto (`relancar.texto_do_pendente`), não uma cópia — a
  régua troca a função e cobra que o pacote a siga;
* o rótulo é a palavra que ela LEU na tela, que chega no clique.

NOTA DATADA — 13/09/2026, JOGAR-A-FAIXA-QUE-PULA-01 §3.2: a frase SAIU DA
TELA. Medido no código e em dublê: o chip da fileira pede com
`origin="manual"`, a trava de jogo aberto não segura essa origem, e o chip
acende o `flavor` que o daemon grava — o chip já mostra a escolha. A regra da
pendência continua aqui, medida na dona (`_faixa_do_pendente`); a frase vai ao
diário da janela, e os três endereços do `pacote()` saem vazios.
"""
from __future__ import annotations

import pathlib
import re
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
for _caminho in (str(RAIZ / "src"), str(INTERFACE)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

from hefesto_dualsense4unix.interface import onde
from pacotes import Contexto
from pacotes import a01_jogar as aba

#: O daemon dela em 02/09/2026 às 04:20, nas quatro chaves que esta faixa lê.
VIVO_DUALSENSE: dict[str, Any] = {
    "connected": True,
    "native_mode": False,
    "gamepad_emulation": {"enabled": True, "flavor": "dualsense", "backend": "uhid"},
}
VIVO_XBOX: dict[str, Any] = {
    "connected": True,
    "native_mode": False,
    "gamepad_emulation": {"enabled": True, "flavor": "xbox", "backend": "uinput"},
}
VIVO_NATIVO: dict[str, Any] = {
    "connected": True,
    "native_mode": True,
    "gamepad_emulation": {"enabled": False, "flavor": "xbox", "backend": None},
}


class PonteDeMentira:
    """Aceita qualquer método e guarda o que foi pedido. Não abre socket."""

    def __init__(self) -> None:
        self.chamadas: list[tuple[str, dict[str, Any]]] = []

    def chamar(self, metodo: str, **params: Any) -> bool:
        self.chamadas.append((metodo, params))
        return True


@pytest.fixture(autouse=True)
def _mesa_limpa() -> Any:
    """A memória da escolha é de MÓDULO — sem isto um teste sujaria o próximo."""
    aba._ESCOLHA.clear()
    aba._ROTULO.clear()
    yield
    aba._ESCOLHA.clear()
    aba._ROTULO.clear()


def faixa(state: dict[str, Any]) -> tuple[str, str]:
    """A pendência como a DONA a mede — `_faixa_do_pendente`.

    CONTRATO TROCADO — 13/09/2026, JOGAR-A-FAIXA-QUE-PULA-01 §3.2. Até hoje
    este ajudante lia `pendente` e `pendente-alvo` do `pacote()`, que eram a
    frase na tela. A frase saiu da tela e vai ao diário da janela
    (`_relatar_a_pendencia`); a regra de QUANDO há pendência não mudou, e é ela
    que as réguas abaixo medem. Quem cobra a tela vazia é
    `test_o_reconectar_nao_muda_de_lugar.py`.
    """
    return aba._faixa_do_pendente(state)


# ---------------------------------------------------------------------------
# 1. Os dois endereços existem nos dois lados
# ---------------------------------------------------------------------------
def test_a_pagina_publicada_tem_os_dois_enderecos() -> None:
    """Sem eles na página, pintar é escrever num `querySelector` que dá `null`."""
    # O CAMINHO TEM DONO: `onde.pagina(..., publicado=True)` é quem sabe onde
    # o produto RENDERIZA. Montá-lo à mão aqui seria a segunda cópia dele — e
    # apontar para a bancada daria verde sobre a página que ela ainda não
    # publicou, que é a armadilha do `COMO-OLHAR-A-TELA.md`.
    corpo = onde.pagina("01-jogar.html", publicado=True).read_text(encoding="utf-8")
    for endereco in ("pendente", "pendente-alvo"):
        assert f'data-campo="{endereco}"' in corpo, (
            f"o endereço {endereco!r} sumiu da página publicada — a pintura "
            f"passaria a escrever em lugar nenhum, calada")


def test_o_pacote_emite_os_dois_em_todo_estado() -> None:
    """Emitir só quando HÁ pendência deixaria a frase cravada viva na tela.

    É a forma exata do defeito: o `escrever` do piloto só apaga um texto
    escrevendo outro por cima. Uma chave ausente não apaga nada.
    """
    for state in (VIVO_DUALSENSE, VIVO_XBOX, VIVO_NATIVO, {}):
        fora = aba.pacote(Contexto(state=state, mesa=[], conectados=[], estados={}))
        assert "pendente" in fora and "pendente-alvo" in fora, (
            f"o pacote calou um dos dois endereços com o estado {state!r}")


def test_sem_pedido_nenhum_a_faixa_sai_vazia() -> None:
    """Vazio é `""` de propósito: o piloto escreve `—`, a palavra da casa."""
    assert faixa(VIVO_DUALSENSE) == ("", "")


# ---------------------------------------------------------------------------
# 2. A pendência nasce, e morre quando o daemon alcança
# ---------------------------------------------------------------------------
def test_o_pedido_que_o_daemon_nao_alcancou_aparece_na_faixa() -> None:
    ctx = Contexto(state=VIVO_DUALSENSE, mesa=[], conectados=[], estados={})
    aba.modo_xbox(ctx, {"texto": "Xbox"}, PonteDeMentira())
    frase, alvo = faixa(VIVO_DUALSENSE)
    assert alvo == "Xbox"
    assert "Xbox" in frase


def test_a_faixa_apaga_sozinha_quando_o_daemon_alcanca() -> None:
    """A regra é `reconciliar_pendente`: *"só existe enquanto DIVERGE do vigente"*.

    Sem ela a tela prometeria para sempre uma mudança que já aconteceu.
    """
    ctx = Contexto(state=VIVO_DUALSENSE, mesa=[], conectados=[], estados={})
    aba.modo_xbox(ctx, {"texto": "Xbox"}, PonteDeMentira())
    assert faixa(VIVO_DUALSENSE) != ("", "")
    assert faixa(VIVO_XBOX) == ("", ""), "a faixa não morreu quando o daemon chegou"
    assert faixa(VIVO_XBOX) == ("", ""), "a pendência ressuscitou no tique seguinte"


def test_clicar_no_que_ja_esta_valendo_nao_cria_pendencia() -> None:
    """É o caso dos DOIS gestos desta aba na lista dos dezesseis.

    A prova do aparelho clica a posição **Ligado** com o daemon já em `gamepad`:
    o gesto aplica, nada muda, e a faixa não pode anunciar mudança nenhuma.
    """
    ctx = Contexto(state=VIVO_DUALSENSE, mesa=[], conectados=[], estados={})
    aba.hefesto(ctx, {"modo": "gamepad", "texto": "Ligado"}, PonteDeMentira())
    assert faixa(VIVO_DUALSENSE) == ("", "")


def test_o_daemon_calado_nao_apaga_a_escolha_dela() -> None:
    """O ramo offline do motor: *"o que ela decidiu não pode evaporar"*.

    E há uma armadilha medida: `mode_of_state({})` devolve `desktop` — ele só
    devolve `None` para um não-dicionário. Sem a guarda, um pedido de Navegação
    seria dado por cumprido por um tique sem resposta.
    """
    ctx = Contexto(state=VIVO_DUALSENSE, mesa=[], conectados=[], estados={})
    aba.modo_navegacao(ctx, {"texto": "Navegação"}, PonteDeMentira())
    assert faixa({}) == faixa(VIVO_DUALSENSE) != ("", "")


# ---------------------------------------------------------------------------
# 3. Nada se reescreve: a frase e o rótulo têm dono
# ---------------------------------------------------------------------------
def test_a_frase_e_a_do_produto_e_nao_uma_copia(monkeypatch: Any) -> None:
    """Troca `relancar.texto_do_pendente` e cobra que o pacote a siga.

    Uma frase digitada aqui passaria neste teste com a função original intacta —
    e é por isso que a régua a TROCA em vez de comparar textos.
    """
    from hefesto_dualsense4unix.app.actions import relancar

    monkeypatch.setattr(relancar, "texto_do_pendente",
                        lambda **_k: "● frase de outro dono")
    ctx = Contexto(state=VIVO_DUALSENSE, mesa=[], conectados=[], estados={})
    aba.modo_xbox(ctx, {"texto": "Xbox"}, PonteDeMentira())
    frase, _alvo = faixa(VIVO_DUALSENSE)
    assert frase == "● Frase de outro dono", (
        "o pacote deixou de usar `relancar.texto_do_pendente` — a frase virou cópia")


def test_a_maiuscula_do_comeco_e_regra_dela() -> None:
    """28/08/2026: *"o `●` que vem antes é MARCADOR, não palavra"*.

    A janela estável escreve a mesma frase em minúscula porque lá ela é um
    rótulo entre outros; aqui é a linha inteira, isolada na caixa tracejada.
    """
    from hefesto_dualsense4unix.app.actions.relancar import MARCADOR_PENDENTE

    ctx = Contexto(state=VIVO_DUALSENSE, mesa=[], conectados=[], estados={})
    aba.modo_xbox(ctx, {"texto": "Xbox"}, PonteDeMentira())
    frase, _alvo = faixa(VIVO_DUALSENSE)
    marca = f"{MARCADOR_PENDENTE} "
    assert frase.startswith(marca)
    primeira = frase[len(marca)]
    assert primeira.isupper(), f"a frase começa em minúscula: {frase!r}"


def test_o_rotulo_e_a_palavra_que_ela_leu_na_tela() -> None:
    """O `texto` do clique é o `textContent` do botão — o desenho, sem cópia."""
    ctx = Contexto(state=VIVO_DUALSENSE, mesa=[], conectados=[], estados={})
    aba.hefesto(ctx, {"modo": "native", "texto": "Desligado"}, PonteDeMentira())
    _frase, alvo = faixa(VIVO_DUALSENSE)
    assert alvo == "Desligado", (
        "a faixa deixou de usar a palavra da tela — ela voltaria a dizer "
        "'Conexão Nativa (Sony)', que é o léxico da janela GTK e não do desenho")


def test_sem_o_texto_do_clique_o_rotulo_sai_do_painel() -> None:
    """A rede de segurança: `painel.CHIPS_DA_ESCADA`, nunca a chave crua."""
    ctx = Contexto(state=VIVO_DUALSENSE, mesa=[], conectados=[], estados={})
    aba.modo_xbox(ctx, {}, PonteDeMentira())
    _frase, alvo = faixa(VIVO_DUALSENSE)
    assert alvo == "Xbox", f"o rótulo caiu para a chave crua: {alvo!r}"


def test_um_chip_mexe_num_eixo_so() -> None:
    """A Navegação é um MODO; DualSense e Xbox são MÁSCARAS do mesmo modo.

    Anotar `modo=gamepad` junto com a máscara poria na faixa a palavra do CHIP
    sob o rótulo do INTERRUPTOR — dois nomes diferentes na tela dela, colados.
    """
    ctx = Contexto(state=VIVO_DUALSENSE, mesa=[], conectados=[], estados={})
    aba.modo_xbox(ctx, {"texto": "Xbox"}, PonteDeMentira())
    assert set(aba._ESCOLHA) == {"mascara"}
    aba._ESCOLHA.clear()
    aba._ROTULO.clear()
    aba.modo_navegacao(ctx, {"texto": "Navegação"}, PonteDeMentira())
    assert set(aba._ESCOLHA) == {"modo"}


def test_gesto_que_levanta_nao_deixa_pendencia() -> None:
    """Anotar antes de despachar prometeria o que ninguém pediu ao daemon."""
    ctx = Contexto(state=VIVO_DUALSENSE, mesa=[], conectados=[], estados={})
    with pytest.raises((ValueError, RuntimeError)):
        aba.hefesto(ctx, {"modo": "modo-que-nao-existe", "texto": "X"},
                    PonteDeMentira())
    assert aba._ESCOLHA == {}
    assert faixa(VIVO_DUALSENSE) == ("", "")


# ---------------------------------------------------------------------------
# 4. Os dois da lista dos dezesseis, classificados
# ---------------------------------------------------------------------------
def test_esta_aba_nao_declara_sem_eco_e_diz_por_que() -> None:
    """`SEM_ECO` é *"o daemon não publica este assunto"* — não é o caso aqui.

    Os cinco métodos desta aba mexem em `native_mode`, `gamepad_emulation`,
    `coop` e `controllers[].player`, e as quatro chaves estão no `state_full`.
    Declarar `SEM_ECO` calaria a régua para sempre sobre um caminho que ela mede.
    """
    assert not hasattr(aba, "SEM_ECO"), (
        "a aba Jogar declarou `SEM_ECO` — os gestos dela TÊM eco no `state_full`")
    classificados = aba.OS_DOIS_DA_LISTA_DOS_DEZESSEIS
    assert set(classificados) == {"hefesto", "reconectar"}
    for nome, motivo in classificados.items():
        assert nome in {p["gesto"] for p in aba.PROVAS}, (
            f"{nome!r} saiu das PROVAS e a classificação ficou órfã")
        assert len(motivo) > 60, f"a classificação de {nome!r} não diz o que mediu"


# ---------------------------------------------------------------------------
# 5. O desenho continua sendo o dela
# ---------------------------------------------------------------------------
def test_o_gerador_nao_crava_a_frase_que_o_produto_agora_escreve() -> None:
    """O alvo cravado tem de continuar SAINDO do chip aceso, não digitado.

    Trocar o TEXTO da faixa é decisão dela; o que esta régua impede é alguém
    digitar uma segunda cópia do alvo no gerador e recriar a contradição de
    31/08 (a faixa anunciando um modo e o chip mostrando outro).
    """
    fonte = (INTERFACE / "aba01.py").read_text(encoding="utf-8")
    achado = re.search(r'data-campo=\\"pendente-alvo\\">\{(\w+)\}', fonte)
    assert achado, "o gerador deixou de interpolar o alvo da faixa"
    assert achado.group(1) == "PENDENTE", (
        "o alvo da faixa deixou de sair de `PENDENTE` (que sai de `MODO_ACESO`)")

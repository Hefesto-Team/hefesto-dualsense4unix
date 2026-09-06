"""Uma ordem que ninguém dispensou não pode sumir da tela.

`ordens_novas` e `ordens_caladas` comparam a dispensa dela com o ARRANJO — e não
com o slug da regra —, e isso é decisão medida: a dispensa vale para o que ela
VIU, e se ela mudar os cabos e a mesma regra disparar com um arranjo novo, é
fato novo e a ordem volta.

**O QUE ESTAVA QUEBRADO, medido em 06/09/2026:** `Ordem.arranjo` tem `""` por
padrão, e a `ONDA5-08-01` ensinou o desfazer a gravar `arranjo=""` na dispensa.
As duas pontas vazias casavam. Uma ordem VIVA que chegasse sem arranjo batia com
o vazio guardado e nascia CALADA — para os DOIS consumidores do módulo, a janela
GTK inclusive. A aba nova tinha guarda local (`a08_conexoes._ordem_calada`) e
não sofria, o que é a definição de cura pela metade: o defeito ficou vivo onde
ninguém estava olhando.

TRÊS frentes o relataram sem poder curá-lo (08-01, 08-02 e
CONEXOES-LIGAR-TUDO-01) — o arquivo estava fora da posse das três.

MORDIDA (06/09/2026, as duas metades):
* tire o `not ordem.arranjo or` de `ordens_novas` e
  `test_a_ordem_viva_sem_assinatura_aparece` reprova;
* tire o `ordem.arranjo and` de `ordens_caladas` e
  `test_a_ordem_viva_sem_assinatura_nao_conta_como_dispensada` reprova.
"""
from __future__ import annotations

from hefesto_dualsense4unix.integrations.ordens_da_mesa import (
    Ordem,
    ordens_caladas,
    ordens_novas,
)

CHAVE = "mover-o-p2-para-a-outra-porta"


def _ordem(arranjo: str = "") -> Ordem:
    """Uma ordem com o mínimo que o tipo pede — o `arranjo` é o que se mede."""
    return Ordem(
        chave=CHAVE,
        acao="Mova o segundo controle para a porta de trás",
        o_que_eu_vi="os dois no mesmo barramento",
        por_que_importa="eles dividem o orçamento de relatórios",
        ganho_esperado="cada um com a própria fila",
        alvo="p2",
        arranjo=arranjo,
    )


def test_a_ordem_viva_sem_assinatura_aparece() -> None:
    """Vazio guardado não cala uma ordem que também está vazia."""
    assert ordens_novas((_ordem(),), {CHAVE: ""}) == (_ordem(),)


def test_a_ordem_viva_sem_assinatura_nao_conta_como_dispensada() -> None:
    """E a tela não pode CONTAR uma decisão dela que não existe."""
    assert ordens_caladas((_ordem(),), {CHAVE: ""}) == ()


def test_a_dispensa_de_verdade_continua_calando() -> None:
    """A cura não pode custar a feature: arranjo assinado, dispensa vale."""
    assinada = _ordem("p1:usb|p2:usb")
    assert ordens_novas((assinada,), {CHAVE: "p1:usb|p2:usb"}) == ()
    assert ordens_caladas((assinada,), {CHAVE: "p1:usb|p2:usb"}) == (assinada,)


def test_arranjo_novo_e_fato_novo() -> None:
    """Ela mudou os cabos: a mesma regra volta, e não conta como dispensada."""
    hoje = _ordem("p1:usb|p2:bt")
    assert ordens_novas((hoje,), {CHAVE: "p1:usb|p2:usb"}) == (hoje,)
    assert ordens_caladas((hoje,), {CHAVE: "p1:usb|p2:usb"}) == ()


def test_sem_dispensa_nenhuma_tudo_aparece() -> None:
    """O caso trivial, que é o da primeira vez que ela abre a aba."""
    com = _ordem("p1:usb")
    sem = _ordem()
    assert set(ordens_novas((com, sem), {})) == {com, sem}
    assert ordens_caladas((com, sem), {}) == ()

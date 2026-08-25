"""O perfil de desempenho diz o que faz — e nenhuma dica promete o que o clique não produz.

DESEMPENHO-A-CONTA-DE-SLOTS-01, 25/08/2026. A seção oferecia CINCO botões dos
quais QUATRO tinham efeito idêntico — nenhum —, e um deles prometia na dica um
comportamento que o clique não produzia. A `D-PERFIL-DE-DESEMPENHO` colapsou os
cinco em três perfis; este arquivo é o portão que impede a tela de voltar a
prometer.

AS MORDIDAS, arrancadas e conferidas em 25/08/2026
---------------------------------------------------

1. **Devolver o texto de bateria ao "Auto"** (ou pôr um verbo de efeito na dica
   de um perfil sem teto): reprova `test_nenhuma_dica_promete_o_que_o_botao_nao_faz`
   nomeando o perfil, o teto `None` e a frase.
2. **Trocar `TITULO` sem trocar `_CAMPOS_DA_MAQUINA["orcamento"]`** (ou o
   contrário): reprova
   `test_o_titulo_da_secao_e_o_rotulo_do_rodape_sao_a_mesma_palavra` nomeando a
   ponta que ficou para trás. É o portão contra a meia-correção — o defeito que
   a regra dela de substituição existe para matar.
3. **Tirar uma coluna da tabela**: reprova
   `test_a_tabela_tem_uma_coluna_por_opcao_oferecida` nomeando a que sumiu.
4. **Voltar `ALCANCE_DE_HOJE` para um literal**: reprova
   `test_a_frase_do_alcance_deriva_da_tabela`, que acrescenta uma sexta linha
   sem ponto de aplicação e exige que a frase a nomeie.
5. **Marcar "Gatilhos" como tendo ponto de aplicação**: reprova
   `test_so_a_vibracao_tem_ponto_de_aplicacao_hoje`, que IMPORTA cada ponto
   declarado.
6. **Recalcular a conta de fatias dentro de `app/`**: reprova
   `test_ninguem_em_app_recalcula_a_conta_de_slots` nomeando arquivo e linha.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: a seção monta widgets de verdade, e "pulei porque não
# tenho GTK" é reprovação no job `gtk-real`.
exigir_gi_real("o perfil de desempenho da aba Configurações")

import ast
import importlib
from dataclasses import replace
from pathlib import Path

import pytest

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")

from hefesto_dualsense4unix.app import ipc_bridge
from hefesto_dualsense4unix.app.actions.config import secao_orcamento
from hefesto_dualsense4unix.core.rumble import teto_do_orcamento
from hefesto_dualsense4unix.integrations.radio_da_mesa import (
    HZ_AUDIO_COM_MIC,
    HZ_INPUT_COM_MIC,
    HZ_INPUT_SEM_MIC,
    SLOTS_POR_SEGUNDO,
)

RAIZ = Path(__file__).resolve().parents[2]
APP = RAIZ / "src" / "hefesto_dualsense4unix" / "app"

#: Verbos que AFIRMAM um efeito sobre a intensidade. Uma dica que os use estando
#: sem teto está prometendo o que o clique não produz — que é literalmente o
#: defeito desta sprint.
VERBOS_DE_EFEITO = (
    "cai para",
    "chega com",
    "acompanha a bateria",
    "limita",
    "limitado",
    "reduz",
    "no máximo",
)


# ---------------------------------------------------------------------------
# 1. O renome tem duas pontas, e o portão impede a meia-correção
# ---------------------------------------------------------------------------


def test_o_titulo_da_secao_e_o_rotulo_do_rodape_sao_a_mesma_palavra() -> None:
    """MORDIDA 2. A seção e o rodapé nomeiam o mesmo campo, ou a tela se contradiz.

    O rodapé usa `_CAMPOS_DA_MAQUINA["orcamento"]` para dizer *"o Hefesto
    descartou: ..."*, e essa frase tem de nomear a seção com a palavra que está
    no alto dela. A `D-PERFIL-DE-DESEMPENHO` renomeia as duas para
    "Desempenho"; enquanto isso não acontecer, as duas dizem "Orçamento", e é o
    mesmo invariante.

    **Este portão está de pé ANTES do renome, e de propósito.** `ipc_bridge.py`
    é território de outra frente nesta leva, e trocar só uma das duas pontas
    deixaria o rodapé chamando a seção por um nome que não existe mais. Com o
    portão verde hoje, o renome vira uma edição de duas linhas que ninguém
    consegue fazer pela metade.
    """
    assert ipc_bridge._CAMPOS_DA_MAQUINA["orcamento"] == secao_orcamento.TITULO, (
        "o título da seção e o rótulo do rodapé divergiram — o renome tem DUAS "
        f"pontas: `secao_orcamento.TITULO` = {secao_orcamento.TITULO!r} e "
        "`ipc_bridge._CAMPOS_DA_MAQUINA['orcamento']` = "
        f"{ipc_bridge._CAMPOS_DA_MAQUINA['orcamento']!r}"
    )


def test_a_chave_do_disco_nunca_e_renomeada_junto_com_o_rotulo() -> None:
    """Renomear a chave `orcamento` é renomear campo de disco DELA.

    O renome de "Orçamento" para "Desempenho" muda RÓTULO, e só. As duas chaves
    — a do `maquina.json` e a do dicionário do rodapé — ficam letra por letra:
    trocar a primeira apaga a declaração de quem já a tinha, e trocar a segunda
    faz o rodapé deixar de reconhecer o campo que o daemon descartou.
    """
    from hefesto_dualsense4unix.utils.maquina import MaquinaConfig

    assert "orcamento" in ipc_bridge._CAMPOS_DA_MAQUINA
    assert "orcamento" in MaquinaConfig.model_fields
    assert set(secao_orcamento.TETO_POR_PERFIL.values()) <= {
        *secao_orcamento.CHAVES,
        None,
    }


# ---------------------------------------------------------------------------
# 2. Nenhuma dica promete o que o botão não faz
# ---------------------------------------------------------------------------


def test_nenhuma_dica_promete_o_que_o_botao_nao_faz() -> None:
    """MORDIDA 1. Sem teto, a dica não pode conter verbo de efeito.

    A dica do antigo "Auto" dizia *"a vibração acompanha a bateria: cheia joga
    inteira, pela metade cai para 70%..."* — a escada de `_effective_mult` no
    ramo da política da **aba Rumble**. Clicar naquele botão não ligava a
    escada, não a desligava e não mudava nada.
    """
    achados = []
    for perfil in secao_orcamento.PERFIS:
        chave = secao_orcamento.TETO_POR_PERFIL[perfil]
        teto = teto_do_orcamento(chave) if isinstance(chave, str) else None
        if teto is not None:
            continue
        dica = secao_orcamento.DICAS.get(perfil, "").lower()
        achados += [
            f"perfil {perfil!r} (teto None) promete {verbo!r}: {dica!r}"
            for verbo in VERBOS_DE_EFEITO
            if verbo in dica
        ]
    assert not achados, (
        "uma dica voltou a prometer efeito que o clique não produz:\n  "
        + "\n  ".join(achados)
    )


def test_a_dica_do_auto_saiu_de_vez() -> None:
    """Fato errado se SUBSTITUI: a escada da bateria não fica ao lado do certo.

    A varredura é sobre o FONTE inteiro da seção, e não sobre o dicionário: o
    defeito clássico da substituição pela metade é deixar o texto velho num
    comentário ou numa constante órfã, onde a próxima pessoa o encontra e
    acredita nele. O cabeçalho do módulo CITA a frase, entre aspas, para dizer
    que ela saiu — e por isso a régua olha só o que vira tela.
    """
    for dica in secao_orcamento.DICAS.values():
        assert "acompanha a bateria" not in dica.lower()
    assert "auto" not in {p.lower() for p in secao_orcamento.PERFIS}
    assert secao_orcamento.ROTULOS_DOS_PERFIS.get("auto") is None


def test_a_dica_do_perfil_de_bateria_nao_promete_mais_que_a_tabela() -> None:
    """A palavra dela dizia "barra de luz apagada" — e não há por onde apagá-la.

    A dica é DERIVADA de `LINHAS_DO_TETO`: ela nomeia como "continuam como
    estão" tudo que não tem ponto de aplicação. Escrever "barra de luz apagada"
    à mão seria prometer de novo o que o clique não produz, no mesmo botão e na
    mesma tela em que a tabela diz o contrário.
    """
    dica = secao_orcamento.DICAS[secao_orcamento.PERFIL_BATERIA_LONGA]
    for linha in secao_orcamento.LINHAS_DO_TETO:
        if linha.tem_ponto:
            continue
        assert linha.nome in dica, (
            f"a linha {linha.nome!r} não tem ponto de aplicação e sumiu da "
            "dica — a dica passou a prometer mais do que a tabela mostra"
        )
    assert "apagada" not in dica.lower()


# ---------------------------------------------------------------------------
# 3. A tabela mostra uma coluna por opção oferecida
# ---------------------------------------------------------------------------


def test_a_tabela_tem_uma_coluna_por_opcao_oferecida() -> None:
    """MORDIDA 3. Com todas as colunas na tela, a tabela mostra o que a seção faz.

    Antes eram três colunas para cinco botões, e a tabela calava justamente
    sobre os dois que não faziam nada.
    """
    oferecidos = [secao_orcamento.ROTULOS_DOS_PERFIS[p] for p in secao_orcamento.PERFIS]
    faltando = [rotulo for rotulo in oferecidos if rotulo not in secao_orcamento.COLUNAS]
    assert not faltando, f"a tabela deixou de ter coluna para: {faltando}"
    assert secao_orcamento.COLUNAS[:2] == ("O que", "Vem de")
    assert len(secao_orcamento.COLUNAS) == len(oferecidos) + 2


def test_a_celula_sem_ponto_de_aplicacao_nao_diz_sem_teto() -> None:
    """"Sem teto" é AFIRMAÇÃO sobre um limite; "não há por onde" é outra coisa.

    Uma célula vazia, ou um "Sem teto" numa linha sem ponto de aplicação, seria
    a tela afirmando que aquele item passa livre — quando a verdade é que
    ninguém tem por onde limitá-lo.
    """
    sem_ponto = next(
        linha for linha in secao_orcamento.LINHAS_DO_TETO if not linha.tem_ponto
    )
    for perfil in secao_orcamento.PERFIS:
        celula = secao_orcamento.celula_do_perfil(perfil, sem_ponto)
        assert celula == secao_orcamento.SEM_PONTO_DE_APLICACAO
        assert celula != secao_orcamento.SEM_TETO


def test_a_celula_da_vibracao_continua_derivada_do_daemon() -> None:
    """O número da vibração sai da conta do daemon, nunca digitado aqui."""
    vibracao = secao_orcamento.LINHAS_DO_TETO[0]
    assert vibracao.tem_ponto
    bateria = secao_orcamento.celula_do_perfil(
        secao_orcamento.PERFIL_BATERIA_LONGA, vibracao
    )
    teto = teto_do_orcamento("economia")
    assert teto is not None
    assert f"{round(teto * 100)}%" in bateria
    assert (
        secao_orcamento.celula_do_perfil(secao_orcamento.PERFIL_TUDO_LIGADO, vibracao)
        == secao_orcamento.SEM_TETO
    )
    assert (
        secao_orcamento.celula_do_perfil(secao_orcamento.PERFIL_EU_ESCOLHO, vibracao)
        == secao_orcamento.CADA_ABA_MANDA
    )


# ---------------------------------------------------------------------------
# 4. A frase de apoio DERIVA da tabela
# ---------------------------------------------------------------------------


def test_a_frase_do_alcance_deriva_da_tabela(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MORDIDA 4. Uma sexta linha sem ponto tem de aparecer na frase.

    Com a frase digitada, a tabela mostrava cinco e a frase falava de quatro, e
    as duas podiam divergir sem ninguém notar.
    """
    antes = secao_orcamento.alcance_de_hoje().lower()
    assert "vibração" in antes
    assert "touchpad" not in antes

    monkeypatch.setattr(
        secao_orcamento,
        "LINHAS_DO_TETO",
        (*secao_orcamento.LINHAS_DO_TETO, secao_orcamento.LinhaDoTeto("Touchpad", "Perfis")),
    )
    depois = secao_orcamento.alcance_de_hoje()
    assert "Touchpad" in depois, (
        "a frase de apoio parou de derivar da tabela — uma linha nova entrou na "
        "tabela e a frase não a viu"
    )


def test_a_frase_do_alcance_muda_quando_uma_linha_ganha_ponto(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A régua sabe RECUSAR: linha COM ponto sai da lista dos pendentes."""
    com_ponto = tuple(
        replace(
            linha,
            ponto_de_aplicacao="hefesto_dualsense4unix.core.rumble:_effective_mult",
        )
        for linha in secao_orcamento.LINHAS_DO_TETO
    )
    monkeypatch.setattr(secao_orcamento, "LINHAS_DO_TETO", com_ponto)
    frase = secao_orcamento.alcance_de_hoje()
    assert "entram quando ganharem" not in frase
    assert "Barra de luz" in frase


def test_so_a_vibracao_tem_ponto_de_aplicacao_hoje() -> None:
    """MORDIDA 5. Todo ponto declarado é IMPORTADO — marcar sem existir reprova.

    É o portão contra a tela prometer teto que ninguém impõe. Quando uma linha
    ganhar ponto de aplicação de verdade, ela passa aqui; até lá, marcar o
    campo é reprovar.
    """
    com_ponto = [linha for linha in secao_orcamento.LINHAS_DO_TETO if linha.tem_ponto]
    assert [linha.nome for linha in com_ponto] == ["Vibração"], (
        "uma linha ganhou ponto de aplicação; se ele existe mesmo, o teste é "
        "que muda — mas ele tem de ser IMPORTÁVEL abaixo"
    )
    for linha in com_ponto:
        assert linha.ponto_de_aplicacao is not None
        modulo, _, atributo = linha.ponto_de_aplicacao.partition(":")
        alvo = importlib.import_module(modulo)
        assert hasattr(alvo, atributo), (
            f"a linha {linha.nome!r} declara o ponto "
            f"{linha.ponto_de_aplicacao!r}, e ele não existe"
        )


# ---------------------------------------------------------------------------
# 5. Ninguém em `app/` recalcula a conta de fatias
# ---------------------------------------------------------------------------


def test_ninguem_em_app_recalcula_a_conta_de_slots() -> None:
    """MORDIDA 6. As constantes do rádio têm UM dono, e ele mora em `integrations/`.

    Molde literal de `test_nenhum_modulo_de_app_recalcula_a_escada`
    (`test_orcamento_dono_unico_do_valor_efetivo.py`). A régua é por **AST**, e
    não por texto: os quatro números aparecem em comentário e em docstring em
    vários módulos de `app/` (o selo `NNN/1600`, o "0/1600" da cura da B1), e
    uma varredura textual reprovaria a prosa que documenta a conta em vez do
    código que a refaz.

    Duas seções desenham a mesma conta — Conexões e Desempenho. Se qualquer uma
    delas passar a somar por conta própria, as duas telas divergem na primeira
    remedição do A/B, e a pessoa fica com dois números para o mesmo fato.
    """
    proibidos = {
        float(SLOTS_POR_SEGUNDO),
        HZ_INPUT_SEM_MIC,
        HZ_INPUT_COM_MIC,
        HZ_AUDIO_COM_MIC,
    }
    achados = []
    for caminho in sorted(APP.rglob("*.py")):
        arvore = ast.parse(caminho.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            if (
                isinstance(no, ast.Constant)
                and isinstance(no.value, (int, float))
                and not isinstance(no.value, bool)
                and float(no.value) in proibidos
            ):
                achados.append(
                    f"{caminho.relative_to(RAIZ)}:{no.lineno} → {no.value}"
                )
    assert not achados, (
        "alguém digitou uma constante do rádio dentro de `app/` — a conta tem "
        "um dono, e ele é `integrations/radio_da_mesa.py`:\n  "
        + "\n  ".join(achados)
    )


def test_a_secao_nao_reimplementa_a_conta_e_sim_a_consome() -> None:
    """A seção DESENHA; quem calcula é `plano_de_radio`, que consome o medidor."""
    fonte = Path(secao_orcamento.__file__).read_text(encoding="utf-8")
    assert "plano_de_radio" in fonte
    for proibido in ("HZ_INPUT_SEM_MIC =", "SLOTS_POR_SEGUNDO =", "CORTE_APERTADA ="):
        assert proibido not in fonte, (
            f"a seção passou a definir `{proibido.split(' =')[0]}` — a "
            "constante tem um dono, e ele mora em `integrations/`"
        )


# ---------------------------------------------------------------------------
# 6. A migração da `D-PERFIL-DE-DESEMPENHO` não perde nada
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("gravado", "esperado"),
    [
        ("economia", "bateria_longa"),
        ("balanceado", "tudo_ligado"),
        ("max", "tudo_ligado"),
        ("auto", "tudo_ligado"),
    ],
)
def test_a_migracao_e_um_para_um_e_nao_perde_nada(gravado: str, esperado: str) -> None:
    """Cada valor que o disco aceita tem um perfil, e o teto não muda de mão."""
    assert secao_orcamento.PERFIL_POR_TETO[gravado] == esperado
    antes = teto_do_orcamento(gravado)
    chave = secao_orcamento.TETO_POR_PERFIL[esperado]
    depois = teto_do_orcamento(chave) if isinstance(chave, str) else None
    assert antes == depois, (
        f"migrar {gravado!r} para {esperado!r} mudaria o teto de {antes} para "
        f"{depois} sem ninguém pedir"
    )


def test_o_disco_nao_muda_de_esquema() -> None:
    """Tirar `"auto"` do `Literal` faria o pydantic recusar o DOCUMENTO INTEIRO."""
    from typing import get_args

    from hefesto_dualsense4unix.utils.maquina import OrcamentoDeclarado

    do_schema = {
        valor
        for ramo in get_args(OrcamentoDeclarado.model_fields["teto"].annotation)
        for valor in get_args(ramo)
        if isinstance(valor, str)
    }
    assert do_schema == set(secao_orcamento.CHAVES)
    assert "auto" in do_schema, (
        "quem já declarou `auto` continua sendo LIDO; tirar o valor do Literal "
        "transformaria o `maquina.json` dela em 'não consegui gravar'"
    )

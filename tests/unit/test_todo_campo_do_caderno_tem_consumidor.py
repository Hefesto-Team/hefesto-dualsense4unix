"""T11, CONFIGURAÇÕES-FECHA-01 — todo campo do caderno tem dono fora da aba.

O defeito mais caro desta casa é a cura escrita e nunca ligada
(`_refresh_config_controles` pendurado em `30b2d57`; `MaquinaConfig.ambiente`
sem escritor nem leitor, achado da T1/T2 desta mesma sprint). O portão que
pegou o primeiro caso é estreito — `NOME_DO_REFRESH` cruzado com
`_REFRESH_POR_ABA` — e cobre só um refresher, não o caderno inteiro.

Este arquivo generaliza: **todo campo de `MesaDeclarada`, `ControleDeclarado`
e `OrcamentoDeclarado` tem de ter um consumidor de PRODUÇÃO fora de
`app/actions/config/` e de `utils/maquina.py` (algo que MUDA comportamento,
não só repinta o widget que a pessoa acabou de clicar), OU uma isenção
NOMEADA neste arquivo.** Isenção com nome é decisão registrada; ausência é o
defeito que este portão existe para pegar.

A lista de campos é lida DINAMICAMENTE dos `model_fields` do pydantic — um
campo novo no esquema entra na conta sozinho, sem editar este arquivo (mesmo
desenho de `secoes.SECOES`, `secoes.py:38`).
"""
from __future__ import annotations

from pathlib import Path

from hefesto_dualsense4unix.utils.maquina import (
    ControleDeclarado,
    MesaDeclarada,
    OrcamentoDeclarado,
)

RAIZ = Path(__file__).resolve().parents[2]
SRC = RAIZ / "src/hefesto_dualsense4unix"

#: campo → citação ``arquivo/relativo/a/src.py:algo`` do consumidor de
#: PRODUÇÃO — fora de ``app/actions/config/`` e de ``utils/maquina.py``.
#: Verificado por baixo: o arquivo existe e contém o `algo` citado.
CONSUMIDOR_DE_PRODUCAO: dict[str, str] = {
    "controles.microfone": "daemon/subsystems/bt_mic.py:def uniqs_declarados",
    "orcamento.teto": "core/rumble.py:def _orcamento_declarado",
    # T3, CONFIGURAÇÕES-FECHA-01 (24/08/2026): o exame da mesa passou a
    # RECEBER a declaração por argumento e a citar o que falta declarar.
    "mesa.altura_da_antena": "integrations/exame_da_mesa.py:def vizinhanca_das_portas",
    "mesa.linha_de_visada": "integrations/exame_da_mesa.py:def vizinhanca_das_portas",
}

#: campo → motivo NOMEADO da isenção. Sem consumidor de produção HOJE — a
#: pergunta se deveria ter um é dela, e está registrada em §9 do
#: CONFIGURAÇÕES-FECHA-01 (24/08/2026).
ISENTOS: dict[str, str] = {
    "mesa.radios": (
        "RadioDeclarado.tipo/apelido só repintam a própria seção "
        "(secao_mesa.py:939, achado da CENTRAL-SEM-TELA-01) — sem "
        "consumidor fora dela hoje"
    ),
    "controles.modo": (
        "só repinta external_card.py:347 — se deveria trocar o glifo dos "
        "botões em outras abas é pergunta dela (CONFIG-06, §9 desta sprint)"
    ),
    "controles.botoes": (
        "só repinta external_card.py:363 — mesma pergunta aberta de "
        "controles.modo"
    ),
    "controles.cor": (
        "só repinta a borda do próprio card (secao_controles.py:791,803) — "
        "achado NOVO da T11 desta sprint, fora do censo original da T1: a "
        "cor declarada nunca chega a um consumidor fora da seção"
    ),
    # ORDEM-DE-SERVIÇO-01 · ORDEM-6 (25/08/2026). ISENÇÃO COM PRAZO, e o
    # consumidor já existe — só não está LIGADO ainda:
    # `ordens_da_mesa.ordens_novas` e `ordens_caladas` leem exatamente este
    # campo, e têm bateria própria em `test_a_ordem_confirma_que_ela_moveu.py`.
    # O que falta é a seção chamá-las, e isso é `secao_exame.py` — texto novo
    # na tela e dois botões, que PROVA-DE-TELA-01 manda passar pelo olho dela
    # ANTES. Quando a seção ligar, esta entrada sai daqui e vira
    # CONSUMIDOR_DE_PRODUCAO apontando para `integrations/ordens_da_mesa.py`.
    "mesa.ordens_dispensadas": (
        "o leitor existe e é testado (ordens_da_mesa.ordens_novas / "
        "ordens_caladas) — falta a seção do exame chamá-lo, e essa metade "
        "aguarda o olho dela (PROVA-DE-TELA-01)"
    ),
}


def _campos_do_caderno() -> list[str]:
    """Os campos vivos do esquema, lidos do pydantic — nunca digitados à mão."""
    campos = [f"mesa.{c}" for c in MesaDeclarada.model_fields]
    campos += [f"controles.{c}" for c in ControleDeclarado.model_fields]
    campos += [f"orcamento.{c}" for c in OrcamentoDeclarado.model_fields]
    return campos


def test_todo_campo_do_caderno_tem_consumidor_ou_isencao_nomeada() -> None:
    campos = set(_campos_do_caderno())
    cobertos = set(CONSUMIDOR_DE_PRODUCAO) | set(ISENTOS)

    faltando = campos - cobertos
    assert not faltando, (
        f"campo(s) do caderno sem consumidor de produção NEM isenção "
        f"nomeada: {sorted(faltando)}"
    )

    sobrando = cobertos - campos
    assert not sobrando, (
        f"entrada de campo que o esquema não tem mais (ou dupla, presente "
        f"em CONSUMIDOR_DE_PRODUCAO e ISENTOS ao mesmo tempo): "
        f"{sorted(sobrando)}"
    )

    dois_lugares = set(CONSUMIDOR_DE_PRODUCAO) & set(ISENTOS)
    assert not dois_lugares, (
        f"campo com consumidor E isenção ao mesmo tempo — escolha um: "
        f"{sorted(dois_lugares)}"
    )


def test_o_consumidor_citado_existe_de_verdade() -> None:
    """A citação não pode ser decorativa: o arquivo e o trecho têm de existir."""
    for campo, citacao in CONSUMIDOR_DE_PRODUCAO.items():
        arquivo, _, alvo = citacao.partition(":")
        caminho = SRC / arquivo
        assert caminho.is_file(), f"{campo}: {arquivo!r} não existe em {SRC}"
        assert "app/actions/config/" not in arquivo, (
            f"{campo}: {arquivo!r} está DENTRO de app/actions/config/ — não "
            "é consumidor de produção, é a própria aba"
        )
        assert arquivo != "utils/maquina.py", (
            f"{campo}: utils/maquina.py não conta como consumidor — é o "
            "próprio esquema"
        )
        texto = caminho.read_text(encoding="utf-8")
        assert alvo in texto, (
            f"{campo}: {alvo!r} não está em {arquivo} — a citação está velha"
        )

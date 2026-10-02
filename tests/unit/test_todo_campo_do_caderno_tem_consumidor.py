"""T11, CONFIGURAÇÕES-FECHA-01 — todo campo do caderno tem dono fora da aba."""
from __future__ import annotations

from pathlib import Path

from hefesto_dualsense4unix.utils.maquina import (
    ControleDeclarado,
    MesaDeclarada,
    OrcamentoDeclarado,
)

RAIZ = Path(__file__).resolve().parents[2]
SRC = RAIZ / "src/hefesto_dualsense4unix"

CONSUMIDOR_DE_PRODUCAO: dict[str, str] = {
    "controles.microfone": "daemon/subsystems/bt_mic.py:def uniqs_declarados",
    "controles.economia": "profiles/schema.py:def controles_em_economia",
    "controles.microfone_mudo": "profiles/manager.py:def _mudo_do_controle",
    "controles.nome": "integrations/central_do_radio.py:def cuidar_dos_nomes",
    "orcamento.teto": "core/rumble.py:def _orcamento_declarado",
    "mesa.altura_da_antena": "integrations/exame_da_mesa.py:def vizinhanca_das_portas",
    "mesa.linha_de_visada": "integrations/exame_da_mesa.py:def vizinhanca_das_portas",
}

#: sai com: AS-ISENCOES-QUE-ESPERAM-A-PALAVRA-DELA-01
ISENTOS: dict[str, str] = {
    "mesa.radios": (
        "RadioDeclarado.tipo/apelido só repintam a própria seção "
        "(secao_mesa.py:610, achado da CENTRAL-SEM-TELA-01) — sem "
        "consumidor fora dela hoje"
    ),
    "controles.modo": (
        "só repinta external_card.py:246 — se deveria trocar o glifo dos "
        "botões em outras abas é pergunta dela (CONFIG-06, §9 desta sprint)"
    ),
    "controles.botoes": (
        "só repinta external_card.py:262 — mesma pergunta aberta de "
        "controles.modo"
    ),
    "controles.cor": (
        "só repinta a borda do próprio card (secao_controles.py:496,803) — "
        "achado NOVO da T11 desta sprint, fora do censo original da T1: a "
        "cor declarada nunca chega a um consumidor fora da seção"
    ),
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

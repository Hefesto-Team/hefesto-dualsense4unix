"""O painel encabeça as decisões que esperam a palavra dela.

NASCEU DE UMA OBSERVAÇÃO E DE UM PEDIDO, em 23/08/2026. Foi observado que o
padrão mais caro do dia não era técnico: **as melhores decisões dela são as que
ela toma VENDO**, e havia decisões paradas há dias por não terem tela. A
resposta dela: *"talvez encabeçar isso na nossa specs pra eu ir vendo junto
contigo."*

Este arquivo prende o que faz a seção valer:

1. a fonte é um CSV, editável à mão ou pela bancada;
2. o painel a mostra ANTES de qualquer outra seção — o que espera ela vem
   primeiro, e não depois do estado dos portões;
3. **o preço do outro lado aparece junto com a recomendação** — é o que separa
   isto de uma lista de pendências: decidir vendo inclui ver o custo;
4. decisão respondida NÃO some da página. É a regra da casa: decisão medida não
   se apaga, ganha data.
"""
from __future__ import annotations

import csv
import importlib.util
import subprocess
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
CSV_ = RAIZ / "docs" / "data" / "decisoes-dela.csv"
GERADOR = RAIZ / "scripts" / "gerar-painel.py"

#: As colunas sem as quais a seção não cumpre o que promete.
#: `preco_do_outro_lado` está aqui por decisão, não por simetria: sem ele a
#: seção vira lista de pendências, que é justamente o que ela NÃO pediu.
COLUNAS_QUE_MORDEM = (
    "id",
    "titulo",
    "a_pergunta",
    "recomendacao",
    "preco_do_outro_lado",
    "estado",
)


def _painel():
    spec = importlib.util.spec_from_file_location("gerar_painel", GERADOR)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_a_fonte_existe_e_tem_as_colunas_que_mordem() -> None:
    """MORDE: apagar `preco_do_outro_lado` do CSV."""
    assert CSV_.exists(), f"a fonte única das decisões sumiu: {CSV_}"
    with CSV_.open(newline="", encoding="utf-8") as f:
        linhas = list(csv.DictReader(f))

    assert linhas, "o CSV está vazio: nenhuma decisão chegaria à tela"
    for coluna in COLUNAS_QUE_MORDEM:
        assert coluna in linhas[0], (
            f"a coluna `{coluna}` sumiu do CSV. Sem ela a seção deixa de "
            "cumprir o que foi pedido: decidir VENDO inclui ver o custo do "
            "outro lado, não só a pergunta"
        )


def test_toda_decisao_aberta_traz_o_preco_do_outro_lado() -> None:
    """Uma decisão sem preço é uma pergunta sem contexto.

    MORDE: esvaziar o `preco_do_outro_lado` de qualquer linha aberta.
    """
    with CSV_.open(newline="", encoding="utf-8") as f:
        for d in csv.DictReader(f):
            if (d.get("estado") or "").strip() == "decidida":
                continue
            assert (d.get("preco_do_outro_lado") or "").strip(), (
                f"a decisão {d.get('id')} não diz o preço de decidir para o "
                "outro lado — ela chegaria à tela como pendência, não como "
                "escolha informada"
            )
            assert (d.get("a_pergunta") or "").strip(), (
                f"a decisão {d.get('id')} não faz pergunta nenhuma"
            )


def test_a_secao_vem_antes_do_estado_do_projeto() -> None:
    """Encabeçar é a palavra dela, e ela é literal.

    MORDE: mover o bloco das decisões para baixo, ou tirá-lo do `monta`.
    """
    pagina = (RAIZ / "html" / "painel.html").read_text(encoding="utf-8")

    onde_decisoes = pagina.find("O que espera você")
    onde_portoes = pagina.find("Os portões")

    assert onde_decisoes != -1, "a seção das decisões não está na página"
    assert onde_portoes != -1, "instrumento inválido: a seção dos portões sumiu"
    assert onde_decisoes < onde_portoes, (
        "as decisões dela têm de vir ANTES do estado dos portões: o que espera "
        "a palavra dela é a primeira coisa que ela vê"
    )


def test_toda_decisao_do_csv_chega_a_pagina() -> None:
    """MORDE: filtrar qualquer decisão na renderização."""
    pagina = (RAIZ / "html" / "painel.html").read_text(encoding="utf-8")
    with CSV_.open(newline="", encoding="utf-8") as f:
        for d in csv.DictReader(f):
            assert d["id"] in pagina, (
                f"a decisão {d['id']} está no CSV e não chegou ao painel"
            )


def test_a_decidida_continua_na_pagina() -> None:
    """Decisão respondida não some — é a regra da casa, presa em teste.

    MORDE: fazer `_bloco_das_decisoes` pular as decididas em vez de esmaecê-las.
    """
    mod = _painel()
    html = mod._bloco_das_decisoes(
        [
            {
                "id": "D-TESTE-FEITA",
                "titulo": "uma que já foi respondida",
                "a_pergunta": "?",
                "recomendacao": "r",
                "preco_do_outro_lado": "p",
                "estado": "decidida",
                "escolha": "a primeira",
                "decidida_em": "2026-08-23",
            }
        ]
    )

    assert "D-TESTE-FEITA" in html, (
        "a decisão respondida sumiu da página: nesta casa decisão medida não "
        "se apaga, ela ganha data"
    )
    assert "a primeira" in html, "a escolha dela não aparece"
    assert "feita" in html, "a decidida tem de sair esmaecida, não igual às abertas"


def test_a_foto_so_entra_se_o_arquivo_existir() -> None:
    """Foto que não existe vira imagem quebrada — pior que foto nenhuma.

    MORDE: tirar a checagem de existência do `_fotos`.
    """
    mod = _painel()
    html = mod._bloco_das_decisoes(
        [
            {
                "id": "D-TESTE-FOTO",
                "titulo": "t",
                "a_pergunta": "?",
                "recomendacao": "r",
                "preco_do_outro_lado": "p",
                "estado": "aberta",
                "foto_antes": "docs/usage/assets/nao-existe-de-jeito-nenhum.png",
            }
        ]
    )

    assert "nao-existe-de-jeito-nenhum" not in html, (
        "o painel referenciou uma foto que não existe: abriria com imagem "
        "quebrada, e uma tela quebrada não ajuda ninguém a decidir"
    )


def test_o_check_do_painel_sabe_reprovar() -> None:
    """O `--check` acusa divergência — e é ele que o gancho de pré-commit roda.

    **ESTE TESTE NASCEU ERRADO E FOI CORRIGIDO NO MESMO DIA (23/08/2026).** A
    primeira versão rodava `--check` contra o painel PUBLICADO e cobrava que ele
    estivesse em dia, e reprovou na suíte inteira — e estava certa em reprovar:
    entre gerar o painel e rodar a suíte, um agente escreveu cinco sprints novas,
    e o censo saiu de 272 para 277.

    O `--check` fez o trabalho dele. **Frágil era o teste**, que olhava a árvore
    em MOVIMENTO — exatamente a armadilha registrada em `COMO-REGER-AGENTES.md`
    no mesmo dia, e que já tinha me feito medir a suíte com resultado inválido.

    Manter o painel publicado em dia é trabalho do GANCHO, que regenera antes de
    cada commit. O que a suíte tem de garantir é outra coisa: **que o `--check`
    saiba acusar.** Um check que nunca reprova é um check que não protege nada.

    MORDE: fazer o `--check` comparar mtime em vez de conteúdo, ou devolver
    sempre zero.
    """
    publicado = RAIZ / "html" / "painel.html"
    guardado = publicado.read_bytes()

    def _check() -> int:
        return subprocess.run(
            ["python3", str(GERADOR), "--check"],
            cwd=RAIZ, capture_output=True, text=True, timeout=180,
        ).returncode

    try:
        # 1. Recém-gerado: tem de PASSAR.
        subprocess.run(
            ["python3", str(GERADOR)], cwd=RAIZ, capture_output=True, timeout=180
        )
        assert _check() == 0, (
            "o `--check` reprovou um painel que ele mesmo acabou de gerar"
        )

        # 2. Sujo: tem de REPROVAR. Um número trocado é a divergência mais
        #    difícil de pegar — se ele acusa isto, acusa qualquer coisa.
        texto = publicado.read_text(encoding="utf-8")
        publicado.write_text(
            texto.replace("chaves no mapa de canais", "chaves no mapa de canaes", 1),
            encoding="utf-8",
        )
        assert _check() != 0, (
            "o `--check` NÃO acusou um painel adulterado: ele é decorativo, e o "
            "gancho de pré-commit que o roda não protege nada"
        )
    finally:
        publicado.write_bytes(guardado)
        subprocess.run(
            ["python3", str(GERADOR)], cwd=RAIZ, capture_output=True, timeout=180
        )




def test_a_suite_nao_medida_e_declarada_e_nao_omitida() -> None:
    """Nenhum número NÃO é o mesmo que nenhuma falha — e a página tem de dizer.

    **O DEFEITO, medido em 23/08/2026, e ele era do próprio painel.** O comando
    da suíte trazia `--timeout=300`, e o `pytest-timeout` não está instalado
    neste projeto: o pytest recusa a flag, sai com código 4 e não imprime
    "N passed". O painel engolia isso, gravava `passed: None` no cache e
    **simplesmente omitia o KPI** — a página ficava idêntica à de quem nunca
    rodou a suíte.

    A mesma suíte, rodada à mão, devolvia 11.684 verdes. Ou seja: a régua estava
    quebrada e a página não dizia, que é a mentira por omissão que este painel
    existe para não contar.

    MORDE: voltar a omitir o KPI quando a medição falha.
    """
    mod = _painel()
    rapido = {
        "censo": {
            "arquivos": 1, "diz_aberta": 0, "diz_concluida": 0,
            "indices": 0, "citadas_na_fila": 0, "fora_da_fila": 0,
        },
        "mapa": {"linhas": 1, "chaves": 1, "assimetrias": 0, "sem_teste": 0},
        "git": {"branch": "x", "head": "y", "assunto": "z", "sujos": 0},
        "decisoes": [],
    }
    cache = {
        "medido_em": time.time(),
        "portoes": {},
        "suite": {
            "passed": None, "failed": 0, "ok": False,
            "nao_mediu": True, "porque": "unrecognized arguments: --timeout=300",
        },
    }

    pagina = mod.monta(rapido, cache)

    assert "NÃO foi medida" in pagina, (
        "a página não declarou que a suíte não pôde ser medida — ela fica "
        "igual à de quem nunca rodou, e ausência vira aparência de sucesso"
    )
    assert "unrecognized arguments" in pagina, (
        "a página não mostrou POR QUE não mediu: sem isso ninguém conserta"
    )


def test_a_suite_medida_mostra_o_numero() -> None:
    """O caminho feliz não pode ter sido estragado pela declaração de ausência."""
    mod = _painel()
    rapido = {
        "censo": {
            "arquivos": 1, "diz_aberta": 0, "diz_concluida": 0,
            "indices": 0, "citadas_na_fila": 0, "fora_da_fila": 0,
        },
        "mapa": {"linhas": 1, "chaves": 1, "assimetrias": 0, "sem_teste": 0},
        "git": {"branch": "x", "head": "y", "assunto": "z", "sujos": 0},
        "decisoes": [],
    }
    cache = {
        "medido_em": time.time(),
        "portoes": {},
        "suite": {"passed": 11684, "failed": 0, "ok": True, "nao_mediu": False},
    }

    pagina = mod.monta(rapido, cache)

    assert "11.684" in pagina, "o número dos testes verdes sumiu da página"
    assert "NÃO foi medida" not in pagina, (
        "a página declarou ausência sobre uma suíte que FOI medida"
    )

"""Os portões que o `CLAUDE.md` manda rodar continuam LIGADOS no CI.

Terceiro bloco da PORTÃO-VIVO-01, e o mais barato de todos: preço ZERO hoje.

MEDIDO em 12/08/2026: `tests/unit/test_portao_do_mapa_esta_ligado.py` era o
ÚNICO teste da suíte inteira que abria o `.github/workflows/ci.yml`, e ele só
olha os dois comandos do mapa de canais. Consequência medida: o job
`packaging-parity` podia ser apagado do `ci.yml`, ou ganhar `continue-on-error`,
e NADA na suíte reprovaria — e ele é justamente o portão que cobra "a cura
chegou ao install". O guarda do install não tinha guarda.

Essa é a família exata do defeito que a casa já pagou três vezes:

  - BUG-GATE-TEST-DATA-NAO-RODAVA-01 (25/07): o `check_test_data.sh` existia,
    reprovava, e nenhum workflow o executava — só rodando à mão dava para
    descobrir;
  - PORTÃO-VIVO-01 bloco B (27/07): os quatro hooks do `.pre-commit-config.yaml`
    não rodavam em lugar NENHUM, porque o `core.hooksPath` global da máquina
    dela desvia o git local e nenhum workflow chamava `pre-commit`;
  - ÍCONE-VIVO-01 (03/08): o `scripts/gerar_icones.sh` dizia no próprio cabeçalho
    que o `--check` "é o que o CI roda", e nenhum job o chamava.

A LISTA É DERIVADA, nunca digitada aqui. A fonte é o bloco "Antes de fechar
qualquer leva" do `CLAUDE.md` — a lista que a casa manda rodar antes de fechar
uma leva. Um portão que está lá e não está no CI é uma promessa que só vale na
máquina de quem lembrar dela; um portão novo entra nesta guarda sozinho, no
mesmo commit em que entra no `CLAUDE.md`.

O QUE FICA DE FORA, e por quê. Dos dez comandos do bloco, três não são scripts
de `scripts/`: `pytest`, `ruff` e `mypy`. Eles ficam fora de propósito, e não por
esquecimento — a classe de defeito medida acima é "script da casa que ninguém
chama vira arquivo", e ela precisa de um arquivo no repositório para acontecer.
Ferramenta de terceiro que sai do CI não some calada: a suíte inteira, o lint e
o typecheck desaparecendo do relatório é ruído que qualquer pessoa vê no
primeiro run. Os sete scripts da casa, não — eles somem em silêncio, que é
exatamente o que aconteceu nas três vezes acima.

Dos quinze jobs do `ci.yml`, portanto, esta guarda cobre os sete que carregam
esses scripts (`anonymity` conta dois), e deixa `lint-test`, `typecheck`,
`gtk-real`, `runtime-smoke`, `build-wheel`, `smoke-multi-distro`, `version-sync`
e `pre-commit` sem guarda de existência. `mapa-de-canais` já tem a sua, no
arquivo irmão. Uma lista longa que ninguém mantém é pior que uma curta que
morde — e esta se mantém sozinha, porque deriva.

O que esta guarda NÃO policia: um `if:` no passo. Nenhum dos sete tem `if:`
hoje, e nenhum defeito desta casa nasceu daí — a regra da casa é que cada
portão nasce de um defeito real, e inventar uma regra sem defeito é o começo de
um portão que grita falso. Fica registrado como buraco conhecido: `if: false`
num passo desliga o portão sem que este arquivo perceba.

PROVA DE QUE MORDE (12/08/2026) — arrancado do `ci.yml` o passo
`run: bash scripts/check_packaging_parity.sh` do job `packaging-parity`,
substituído por um `echo`. Reprovou `test_todo_portao_da_casa_e_invocado_no_ci`,
e só ele. Devolvido; a rodada de controle voltou verde. A segunda mordida:
posto `continue-on-error: true` no MESMO passo — reprovou
`test_nenhum_portao_da_casa_virou_aviso`, e só ele. A terceira: tirado o
`continue-on-error` do passo e posto no JOB `packaging-parity` inteiro —
reprovou o mesmo teste, agora pela outra asserção ("o passo parece duro e o job
o perdoa"). Os três arrancamentos foram devolvidos do `ci.yml` original guardado
fora da árvore, com md5 conferido, e a rodada de controle voltou verde.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[2]
CI = RAIZ / ".github" / "workflows" / "ci.yml"
CLAUDE_MD = RAIZ / "CLAUDE.md"

#: O cabeçalho que abre o bloco de portões do `CLAUDE.md`. Se ele mudar, esta
#: guarda tem de saber — daí o teste da âncora logo abaixo.
CABECALHO = "## Antes de fechar qualquer leva"

#: Quantos scripts o bloco listava quando esta guarda nasceu. É trava de
#: encolhimento, não meta: existe para que uma reformatação do `CLAUDE.md` não
#: esvazie a lista derivada em silêncio, deixando todos os testes deste arquivo
#: passarem por vacuidade. Sobe quando alguém quiser subi-lo.
PISO = 7

#: Portão do `CLAUDE.md` que, por decisão registrada, NÃO roda no CI. Vazio em
#: 12/08/2026 — os sete estão todos lá. A chave é o caminho do script; o valor
#: é a razão, com data e com o motivo pelo qual o CI não é o lugar dele.
#: Declarar é honesto e este portão não castiga honestidade — só não deixa a
#: lápide envelhecer calada.
SO_NA_MAQUINA_DELA: dict[str, str] = {}


#: MEDIDO em 13/08/2026, antes do primeiro push desta guarda: o `CLAUDE.md`
#: está em `.gitignore:90` e NÃO é rastreado pelo git. No runner do CI o
#: `actions/checkout` não o traz, e sem ele os cinco testes deste arquivo
#: reprovavam — uma guarda nova derrubaria o `lint-test` no primeiro push, por
#: um arquivo que só existe na máquina dela.
#:
#: `skip` e não `fail`: reprovar ali é acusar o runner de um defeito que é
#: nosso, e um portão que grita onde não pode ser atendido é desligado na
#: semana seguinte. Mas o skip é BARULHENTO — a razão vai na mensagem, com a
#: cura escrita — porque a alternativa (passar calado) é o defeito-mãe desta
#: casa: a guarda que existe, roda, e não guarda nada.
#:
#: A CURA de verdade é decisão dela e está na mesa: versionar a LISTA de
#: portões num arquivo do repositório (`docs/process/`, por exemplo) e fazer o
#: `CLAUDE.md` apontar para ele. Aí a guarda funciona no CI sem que a lei da
#: casa precise ser publicada.
_AUSENTE = (
    "CLAUDE.md não existe nesta árvore (está em `.gitignore:90` e não é "
    "rastreado). No CI ele nunca chega, então esta guarda fica CEGA aqui. "
    "Para ligá-la de verdade: mova a lista de portões do bloco "
    f"'{CABECALHO}' para um arquivo VERSIONADO e aponte esta guarda para ele."
)


def bloco_de_portoes() -> str:
    """O trecho de shell do `CLAUDE.md` que lista o que rodar antes da leva."""
    if not CLAUDE_MD.is_file():
        pytest.skip(_AUSENTE)
    texto = CLAUDE_MD.read_text(encoding="utf-8")
    inicio = texto.find(CABECALHO)
    if inicio < 0:
        return ""
    cerca = texto.find("```", inicio)
    if cerca < 0:
        return ""
    fim = texto.find("```", cerca + 3)
    return texto[cerca:fim] if fim > 0 else ""


def portoes_da_casa() -> list[str]:
    """Os scripts de `scripts/` citados no bloco, na ordem em que aparecem.

    Derivado, nunca digitado: portão novo no `CLAUDE.md` entra aqui sozinho.
    """
    vistos: list[str] = []
    for achado in re.findall(r"scripts/[\w./-]+\.(?:sh|py)", bloco_de_portoes()):
        if achado not in vistos:
            vistos.append(achado)
    return vistos


def passos_do_ci() -> list[dict]:
    """Todo passo de todo job do CI, já com o nome do job e o job inteiro junto.

    O job vem junto porque o `continue-on-error` também existe no NÍVEL DO JOB
    — o `smoke-multi-distro` usa exatamente essa forma (`ci.yml`, matriz
    experimental). Olhar só o passo deixaria de pé a rota mais barata de
    desligar um portão sem apagar linha nenhuma.
    """
    dados = yaml.safe_load(CI.read_text(encoding="utf-8"))
    passos: list[dict] = []
    for nome_do_job, job in (dados.get("jobs") or {}).items():
        for passo in job.get("steps") or []:
            passos.append({**passo, "__job__": nome_do_job, "__do_job__": job})
    return passos


def passos_que_rodam(agulha: str) -> list[dict]:
    """Os passos cujo `run` contém o comando. Comentário do YAML não conta.

    O `yaml.safe_load` já descarta comentário, e é por isso que ele está aqui em
    vez de um `in` no texto cru: comentar o passo é a forma mais barata de
    desligar um portão sem parecer que desligou.
    """
    return [
        passo
        for passo in passos_do_ci()
        if agulha in " ".join(str(passo.get("run", "")).split())
    ]


def test_a_ancora_do_claude_md_continua_de_pe() -> None:
    """Sem esta trava, uma reformatação do `CLAUDE.md` desligaria tudo calada."""
    achados = portoes_da_casa()
    assert len(achados) >= PISO, (
        f"o bloco '{CABECALHO}' do CLAUDE.md rendeu {len(achados)} scripts, "
        f"piso {PISO}: {achados}\n"
        "Se o bloco MUDOU DE LUGAR ou de formato, conserte a âncora deste "
        "arquivo (CABECALHO e `bloco_de_portoes`) — sem ela a lista derivada "
        "nasce vazia e todos os testes daqui passam sem olhar nada.\n"
        "Se um portão SAIU do CLAUDE.md de propósito, baixe o PISO no mesmo "
        "commit, para que a queda fique escrita em vez de descoberta."
    )


def test_todo_portao_da_casa_e_invocado_no_ci() -> None:
    """O que a casa manda rodar antes da leva tem de rodar no CI também."""
    for portao in portoes_da_casa():
        if portao in SO_NA_MAQUINA_DELA:
            continue
        assert passos_que_rodam(portao), (
            f"nenhum passo do ci.yml INVOCA `{portao}`, e o CLAUDE.md manda "
            "rodá-lo antes de fechar qualquer leva.\n"
            "DEVOLVA o passo ao ci.yml, num `run:`. Comentário não conta: o "
            "portão tem de rodar, não de ser mencionado.\n"
            "Foi assim que o check_test_data.sh passou meses existindo, "
            "reprovando e não rodando (BUG-GATE-TEST-DATA-NAO-RODAVA-01).\n"
            "Se ele NÃO deve rodar no CI, declare em `SO_NA_MAQUINA_DELA` "
            "com a razão e a data."
        )


def test_nenhum_portao_da_casa_virou_aviso() -> None:
    """`continue-on-error` transforma portão em decoração com nome de portão."""
    for portao in portoes_da_casa():
        for passo in passos_que_rodam(portao):
            onde = passo.get("name", passo["__job__"])
            assert not passo.get("continue-on-error"), (
                f"o passo '{onde}' roda `{portao}` com continue-on-error: ele "
                "relata, não protege.\n"
                "TIRE o `continue-on-error`. Um portão que não reprova é pior "
                "que portão nenhum, porque a casa passa a confiar num guarda "
                "que dorme."
            )
            assert not passo["__do_job__"].get("continue-on-error"), (
                f"o JOB '{passo['__job__']}' roda `{portao}` e é inteiro "
                "continue-on-error: o passo parece duro e o job o perdoa.\n"
                "TIRE o `continue-on-error` do job, ou mova este portão para "
                "um job duro. Desligar pelo nível do job é a rota mais barata "
                "de todas — não apaga linha nenhuma e não aparece no diff do "
                "passo."
            )


def test_todo_portao_da_casa_aponta_para_arquivo_que_existe() -> None:
    """Portão que chama script inexistente é portão que reprova por engano."""
    for portao in portoes_da_casa():
        assert (RAIZ / portao).is_file(), (
            f"o CLAUDE.md manda rodar `{portao}` e esse arquivo não existe "
            "na árvore. APAGUE a linha do CLAUDE.md, ou devolva o script."
        )


def test_a_lista_de_lacunas_nao_envelhece_calada() -> None:
    """Sem isto, `SO_NA_MAQUINA_DELA` vira o lugar onde se esconde o que incomoda."""
    derivados = portoes_da_casa()
    for chave, razao in SO_NA_MAQUINA_DELA.items():
        assert chave in derivados, (
            f"{chave!r} está declarado como portão de fora do CI e nem consta "
            "mais do CLAUDE.md — APAGUE a entrada."
        )
        assert len(razao) > 120, (
            f"a razão de {chave!r} não diz por que o CI não é o lugar dele: {razao!r}"
        )
        assert re.search(r"\d{2}/\d{2}/\d{4}", razao), (
            f"a lacuna {chave!r} não tem data. Sem data ninguém sabe se ela "
            "envelheceu — e uma lacuna sem idade vira paisagem."
        )

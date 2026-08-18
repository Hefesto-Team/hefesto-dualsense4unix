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

O que esta guarda NÃO policiava, e por quê (nota de 12/08/2026): um `if:` no
passo. O argumento da época era que nenhum dos sete tinha `if:` e que inventar
regra sem defeito é o começo de um portão que grita falso. O buraco ficou
escrito ali mesmo: "`if: false` num passo desliga o portão sem que este arquivo
perceba".

CADUCOU EM 13/08/2026 (P0-FUROS-01). A régua da guarda era um `in` de
substring sobre o `run` inteiro colapsado em espaços, e MEDIDO nesta árvore ela
aprovava QUATRO formas distintas de desligar o `check_anonymity.sh` — as quatro
com os cinco testes deste arquivo verdes:

  1. `run: echo 'era bash scripts/check_anonymity.sh'` — o script vira TEXTO de
     um echo. Nada o executa, e a substring está lá;
  2. o comando dentro de um comentário de shell, no corpo de um `run: |`. O
     docstring de `passos_que_rodam` dizia que o `safe_load` protege disso, e
     essa frase estava ERRADA: o `safe_load` descarta o comentário do YAML, mas
     o corpo de um bloco literal é uma STRING — um `#` ali chega inteiro ao
     valor, e a substring casa;
  3. `run: bash scripts/check_anonymity.sh || true` — roda, reprova, e o shell
     engole. O passo fica verde;
  4. `if: false` no passo — o buraco declarado acima.

O argumento "não há defeito" não vale mais depois de a medição mostrar o
defeito. Hoje a régua exige o script em POSIÇÃO DE COMANDO, numa linha que o
shell executa, sem engolidor de código de saída e num passo (e num job) que não
está desligado por `if`.

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

PROVA DE QUE MORDE (13/08/2026, P0-FUROS-01) — as QUATRO formas listadas acima,
aplicadas uma a uma sobre o passo `- run: bash scripts/check_anonymity.sh` do
job `anonymity`. Antes desta leva: `exit=0, 5 passed` nas quatro. Depois:
reprova nas quatro, e cada uma pelo teste que lhe cabe — 1 e 2 por
`test_todo_portao_da_casa_e_invocado_no_ci` (o portão deixou de ser INVOCADO),
3 por `test_nenhum_portao_da_casa_tem_a_reprovacao_engolida`, 4 por
`test_nenhum_portao_da_casa_esta_desligado_por_if`. Devolvido do `ci.yml`
guardado fora da árvore, com md5 conferido, e a rodada de controle voltou
verde.
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


#: Tokens que podem PRECEDER o script sem tirá-lo da posição de comando: o
#: interpretador que o executa. Derivado do que o `ci.yml` usa hoje
#: (`bash scripts/...`, `python3 scripts/...`, `python scripts/...`) mais as
#: formas que a casa escreve no `CLAUDE.md` (`.venv/bin/python`).
INTERPRETADORES = frozenset(
    {
        "bash",
        "sh",
        "env",
        "sudo",
        "python",
        "python3",
        "python3.10",
        "python3.11",
        "python3.12",
        ".venv/bin/python",
        "./.venv/bin/python",
    }
)

#: Uma atribuição de variável antes do comando (`FOO=1 bash x.sh`) também não
#: tira o script da posição de comando.
_ATRIBUICAO = re.compile(r"[A-Za-z_][A-Za-z_0-9]*=.*")

#: O que engole o código de saída do portão: ele roda, reprova, e o passo fica
#: verde. Medido como forma 3 dos quatro furos de 13/08/2026.
_ENGOLIDOR = re.compile(r"\|\|\s*(true|:|/bin/true|exit\s+0)\b")

#: `if:` que nunca é verdadeiro. Estreito de propósito: cobre a forma que a
#: medição de 13/08/2026 exercitou (`if: false`, que o YAML entrega como o
#: booleano `False`) e as duas grafias equivalentes que o GitHub aceita.
_IF_MORTO = re.compile(r"(?:\$\{\{\s*)?(?:false|0)(?:\s*\}\})?", re.IGNORECASE)


def linhas_de_comando(run: object) -> list[str]:
    """As linhas do `run` que o shell EXECUTA — comentário de shell fora.

    O `yaml.safe_load` descarta o comentário do YAML, e até 13/08/2026 este
    arquivo afirmava que isso bastava. Não bastava: o corpo de um `run: |` é um
    bloco literal, ou seja, uma STRING — um `#` ali dentro não é comentário de
    YAML nenhum, chega inteiro ao valor, e uma busca por substring casava com
    ele. Comentar o portão continuava sendo a forma mais barata de desligá-lo,
    só que pelo outro lado.
    """
    limpas: list[str] = []
    for linha in str(run).splitlines():
        nua = linha.strip()
        if nua and not nua.startswith("#"):
            limpas.append(nua)
    return limpas


def comandos(linha: str) -> list[str]:
    """A linha quebrada nos operadores que começam um comando NOVO."""
    return [pedaco.strip() for pedaco in re.split(r"\|\||&&|[;|&]", linha) if pedaco.strip()]


def em_posicao_de_comando(comando: str, portao: str) -> bool:
    """O script é EXECUTADO neste comando, ou só aparece escrito nele?

    Esta é a pergunta que a régua antiga não fazia. `echo 'era bash
    scripts/check_anonymity.sh'` contém a substring e não roda portão nenhum —
    forma 1 dos quatro furos.
    """
    tokens = comando.split()
    if portao not in tokens:
        return False
    antes = tokens[: tokens.index(portao)]
    return all(t in INTERPRETADORES or _ATRIBUICAO.fullmatch(t) for t in antes)


def linhas_que_rodam(passo: dict, portao: str) -> list[str]:
    """As linhas do passo em que o portão é de fato executado."""
    return [
        linha
        for linha in linhas_de_comando(passo.get("run", ""))
        if any(em_posicao_de_comando(comando, portao) for comando in comandos(linha))
    ]


def desligado_por_if(valor: object) -> bool:
    """O `if:` deste passo (ou deste job) nunca é verdadeiro?"""
    if valor is None:
        return False
    if isinstance(valor, bool):
        return not valor
    return bool(_IF_MORTO.fullmatch(" ".join(str(valor).split())))


def passos_que_rodam(agulha: str) -> list[dict]:
    """Os passos que EXECUTAM o comando — não os que o mencionam.

    Três exigências, uma por furo medido em 13/08/2026: a linha não pode ser
    comentário de shell; o script tem de estar em posição de comando (só um
    interpretador ou uma atribuição pode vir antes); e a comparação é por
    TOKEN, não por substring.
    """
    return [passo for passo in passos_do_ci() if linhas_que_rodam(passo, agulha)]


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


def test_nenhum_portao_da_casa_tem_a_reprovacao_engolida() -> None:
    """`|| true` roda o portão, ouve o "não", e responde "sim" mesmo assim."""
    for portao in portoes_da_casa():
        for passo in passos_que_rodam(portao):
            onde = passo.get("name", passo["__job__"])
            for linha in linhas_que_rodam(passo, portao):
                engolidor = _ENGOLIDOR.search(linha)
                assert not engolidor, (
                    f"o passo '{onde}' roda `{portao}` e engole a reprovação "
                    f"com `{engolidor.group(0)}`:\n    {linha}\n"
                    "TIRE o engolidor. O portão executa, reprova, e o passo "
                    "fica verde — é `continue-on-error` escrito em shell, e "
                    "sem a palavra `continue-on-error` para o diff denunciar."
                )


def test_nenhum_portao_da_casa_esta_desligado_por_if() -> None:
    """`if: false` desliga o portão sem apagar uma linha sequer do `run`."""
    for portao in portoes_da_casa():
        for passo in passos_que_rodam(portao):
            onde = passo.get("name", passo["__job__"])
            assert not desligado_por_if(passo.get("if")), (
                f"o passo '{onde}' roda `{portao}` sob `if: {passo.get('if')!r}`, "
                "que nunca é verdadeiro: o passo aparece PULADO no relatório e "
                "ninguém lê pulo.\n"
                "TIRE o `if`, ou mova o portão para um passo que sempre roda."
            )
            assert not desligado_por_if(passo["__do_job__"].get("if")), (
                f"o JOB '{passo['__job__']}' roda `{portao}` e o job inteiro "
                f"está sob `if: {passo['__do_job__'].get('if')!r}`, que nunca é "
                "verdadeiro.\n"
                "TIRE o `if` do job, ou mova este portão para um job que roda. "
                "Desligar pelo nível do job não aparece no diff do passo."
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

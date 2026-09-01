"""TODO PORTÃO DESTA CASA TEM QUEM O RODE — ou uma dívida declarada e datada.

O DEFEITO, e ele é medido duas vezes:

1. **`scripts/check_faixa_sintetica.py` ficou verde por AUSÊNCIA.** Ele existia
   e não tinha chamador nenhum — nem CI, nem gancho, nem checklist. Foi assim
   que quatro MACs de fixture moraram no `controllers.json` **vivo** dela desde
   22/08/2026, empurrando os DualSense reais para os postos 6, 7 e 8. O portão
   existia o tempo todo. Ninguém o chamava. Curado em 25/08/2026.
2. **`scripts/check_broadcast_proibido.py` está no MESMO estado agora**
   (medido em 25/08/2026, AUDITORIA-DE-PERDA-01/C2): nasceu em `826ee18`, roda
   verde, e a única menção a ele em toda a árvore está no documento de sprint
   que o PROPÔS — marcada `ref-externa` porque, quando aquele texto foi
   escrito, o arquivo ainda não existia. Ver `_SEM_CHAMADOR_HOJE`.

POR QUE ESTE PORTÃO NÃO É REDUNDANTE COM O `test_portao_a_lista_de_portoes_e_
uma_so.py`, e a diferença é estrutural: aquele compara **duas listas entre si**
(`scripts/portoes.sh` ↔ `.github/workflows/ci.yml`) e reprova quando uma tem o
que a outra não tem. Um portão que está **em NENHUMA das duas** não aparece em
diferença nenhuma — ele é invisível para aquela régua, por construção. Este aqui
compara o **DISCO** contra as duas listas, e é por isso que ele vê o que a outra
não pode ver. É a regra desta casa: duas réguas independentes é o que revela.

QUEM CONTA COMO CHAMADOR — só quem RODA sozinho, sem alguém lembrar:
  - a tabela de `scripts/portoes.sh` (as linhas `rapido|`/`completo|`/`suite|`);
  - qualquer job de `.github/workflows/*.yml`;
  - o gancho `scripts/hooks/pre-commit`;
  - o `.pre-commit-config.yaml`.

**As linhas `FORA-DO-LOCAL` / `FORA-DO-CI` do `portoes.sh` NÃO contam.** Elas
declaram uma divergência ENTRE as duas listas, não uma execução — e aceitar uma
declaração como prova de execução seria trocar a pergunta deste portão pela
pergunta do outro.

**`tests/` também NÃO conta**, pela mesma razão que o
`portao_a_casa_sabe_e_o_produto_nao_faz` já mede: um chamador só em `tests/`
prova que o script é exercitável, não que alguma coisa o exerce em produção. Um
portão que só o próprio teste dele chama vigia a si mesmo.

A MORDIDA (arranque a cura, veja reprovar, devolva): `TestOPortaoMorde` fabrica
um `scripts/check_inventado.py` numa árvore de mentira e cobra que ele seja
acusado; depois o fia à tabela de `portoes.sh` e cobra que ele SUMA da acusação.
Régua que só sabe passar não é régua — e uma que grita sempre é desligada na
primeira semana.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]

#: A FORMA que promete vigiar. Um arquivo com um destes nomes afirma, no
#: próprio nome, que reprova alguma coisa — e um vigia que ninguém chama é
#: pior que vigia nenhum, porque a casa acredita estar coberta.
_FORMAS_DE_PORTAO = ("check_", "validar-", "portao_")

#: Toda dívida declarada carrega data. Sem data ninguém sabe se ela envelheceu.
_DATA = re.compile(r"\b\d{2}/\d{2}/\d{4}\b")

#: O mesmo piso do `portao_a_casa_sabe_e_o_produto_nao_faz`: abaixo disto a
#: razão não cabe o endereço de onde o caminho se perde nem a linha exata que
#: fecharia a dívida, e vira "porque sim" com mais letras.
_RAZAO_MINIMA = 120

#: As linhas da tabela de `portoes.sh` — e SÓ elas. As camadas são a primeira
#: coluna; ver o cabeçalho `A TABELA` daquele arquivo.
_CAMADAS = ("rapido|", "completo|", "suite|")


# ===========================================================================
# A dívida declarada — portão que existe e que nada roda ainda
# ===========================================================================

#: Portão no disco, sem chamador automático, com o motivo e o que o fecha.
#: Declarar é honesto e este portão não castiga honestidade: ele só não deixa a
#: dívida envelhecer calada. No dia em que o chamador nascer, a entrada REPROVA
#: e tem de ser apagada (`test_nenhuma_divida_sobreviveu_a_propria_cura`).
_SEM_CHAMADOR_HOJE: dict[str, str] = {
    "scripts/check_bancada_de_bt.py": (
        "MEDIDO em 01/09/2026, e ele NASCEU sem chamador de propósito. A escada "
        "de releases (`docs/process/2026-08-24-A-ESCADA-DE-RELEASES.md`, degrau "
        "0.9.5) o nomeia como o que mede a bancada de BT dela, e o arquivo não "
        "existia — o degrau só era descrito, nunca conferido. Ele lê os dois "
        "CSV (`mapa-controles.csv`, `ensaios.csv`) e roda no CI sem hardware. "
        "RODA VERMELHO hoje, de propósito: `python scripts/check_bancada_de_bt.py`"
        " -> exit=1, com R1=48, R2=30, R3=7, R4=98 — 183 pendências. "
        "POR QUE NÃO ESTÁ NO `portoes.sh`: ele mede o DEGRAU, não o commit. Uma "
        "leva que não toca o mapa de rádio ficaria vermelha por 183 pendências "
        "que não criou, e um portão vermelho permanente é um portão que se "
        "aprende a ignorar — que é o oposto do que este arquivo existe para "
        "fazer. O QUE O LIGA, quando as quatro réguas zerarem: "
        "`completo|bancada-de-bt|py|scripts/check_bancada_de_bt.py` na tabela do "
        "`scripts/portoes.sh`, mais o passo correspondente no `ci.yml` (os dois, "
        "senão o `test_portao_a_lista_de_portoes_e_uma_so.py` reprova). "
        "A régua do próprio script é `tests/unit/test_a_bancada_de_bt_tem_regua.py`, "
        "que roda na suíte e cobre as quatro réguas contra CSV de mentira."
    ),
    "scripts/check_broadcast_proibido.py": (
        "MEDIDO em 25/08/2026 (AUDITORIA-DE-PERDA-01/C2). Nasceu em `826ee18` "
        "(ONDA0-Z3-8) e nenhum runner o chama: não está na tabela de "
        "`scripts/portoes.sh`, nem em `.github/workflows/`, nem no gancho, nem "
        "no `.pre-commit-config.yaml` — a única menção em toda a árvore está no "
        "documento de sprint que o propôs, marcada `ref-externa`. RODA VERDE "
        "hoje: `python scripts/check_broadcast_proibido.py` -> exit=0, 'nenhuma "
        "rota de saída com fan-out sem escopo'. O QUE A FECHA: uma linha na "
        "tabela de `scripts/portoes.sh` — "
        "`rapido|broadcast-proibido|py|scripts/check_broadcast_proibido.py` — e "
        "o passo correspondente no `ci.yml`. NÃO foi feito aqui porque nenhum "
        "dos dois arquivos é posse desta frente na leva de 25/08 (o "
        "`portoes.sh` nasceu esta noite noutra frente, e o `ci.yml` é a "
        "superfície de integração com nove frentes em voo). É DÍVIDA "
        "DECLARADA, não ausência calada."
    ),
}


# ===========================================================================
# A varredura
# ===========================================================================


def portoes_no_disco(raiz: Path | None = None) -> set[str]:
    """Todo arquivo de `scripts/` cujo NOME promete vigiar.

    Pelo nome, e não por conteúdo, de propósito: é o nome que faz a casa
    acreditar que está coberta. Um `check_*.py` que não reprova nada é outro
    defeito, e não é este.
    """
    alvo = (RAIZ if raiz is None else raiz) / "scripts"
    achados: set[str] = set()
    if not alvo.is_dir():
        return achados
    for caminho in sorted(alvo.rglob("*")):
        if not caminho.is_file() or caminho.suffix not in (".py", ".sh"):
            continue
        if "__pycache__" in caminho.parts:
            continue
        if caminho.name.startswith(_FORMAS_DE_PORTAO):
            achados.add(caminho.relative_to(RAIZ if raiz is None else raiz).as_posix())
    return achados


def _linhas_que_rodam(raiz: Path) -> list[str]:
    """Toda linha de todo runner desta casa, sem comentário.

    Comentário fora porque menção em comentário é justamente a forma que
    engana: o `check_faixa_sintetica.py` esteve citado em prosa por dois anos
    sem nunca rodar.
    """
    linhas: list[str] = []

    tabela = raiz / "scripts" / "portoes.sh"
    if tabela.is_file():
        linhas += [
            linha
            for linha in tabela.read_text(encoding="utf-8").splitlines()
            if linha.startswith(_CAMADAS)
        ]

    fontes: list[Path] = []
    fluxos = raiz / ".github" / "workflows"
    if fluxos.is_dir():
        fontes += sorted(fluxos.glob("*.yml")) + sorted(fluxos.glob("*.yaml"))
    ganchos = raiz / "scripts" / "hooks"
    if ganchos.is_dir():
        fontes += sorted(p for p in ganchos.iterdir() if p.is_file())
    pre_commit = raiz / ".pre-commit-config.yaml"
    if pre_commit.is_file():
        fontes.append(pre_commit)

    for fonte in fontes:
        for linha in fonte.read_text(encoding="utf-8").splitlines():
            if linha.lstrip().startswith("#"):
                continue
            linhas.append(re.sub(r"\s#.*$", "", linha))
    return linhas


def portoes_sem_chamador(raiz: Path | None = None) -> set[str]:
    """Os portões do disco que NENHUM runner cita."""
    alvo = RAIZ if raiz is None else raiz
    corpo = "\n".join(_linhas_que_rodam(alvo))
    return {
        portao
        for portao in portoes_no_disco(raiz)
        if portao not in corpo and Path(portao).name not in corpo
    }


# ===========================================================================
# As réguas
# ===========================================================================


class TestTodoPortaoTemChamador:
    """Um vigia que ninguém chama não vigia — e a casa acredita que sim."""

    def test_todo_portao_do_disco_roda_ou_esta_declarado(self) -> None:
        """A pergunta inteira, numa asserção só, nomeando TODOS os órfãos."""
        orfaos = sorted(portoes_sem_chamador() - set(_SEM_CHAMADOR_HOJE))
        assert not orfaos, (
            f"{len(orfaos)} portão(ões) existe(m) em `scripts/` e NADA os "
            f"roda:\n" + "\n".join(f"  - {o}" for o in orfaos) + "\n"
            "É o defeito do `check_faixa_sintetica.py`, que ficou verde por "
            "AUSÊNCIA enquanto quatro MACs de fixture moravam no "
            "`controllers.json` vivo dela.\n"
            "FAÇA UMA DAS DUAS:\n"
            "  1. LIGUE — uma linha na tabela de `scripts/portoes.sh` e o "
            "passo correspondente em `.github/workflows/ci.yml` (as duas, "
            "senão o `test_portao_a_lista_de_portoes_e_uma_so.py` reprova);\n"
            "  2. DECLARE em `_SEM_CHAMADOR_HOJE`, com a data da medição e a "
            "LINHA EXATA que o ligaria. Dívida declarada é decisão; ausência "
            "calada é o defeito."
        )

    def test_nenhuma_divida_cita_portao_que_nao_existe(self) -> None:
        """Registro que cita arquivo apagado é cemitério, não registro."""
        fantasmas = sorted(set(_SEM_CHAMADOR_HOJE) - portoes_no_disco())
        assert not fantasmas, (
            f"`_SEM_CHAMADOR_HOJE` cita {len(fantasmas)} arquivo(s) que não "
            f"existe(m) mais em `scripts/`:\n"
            + "\n".join(f"  - {f}" for f in fantasmas)
            + "\nAPAGUE a entrada, ou corrija o caminho se ele só mudou de lugar."
        )

    def test_nenhuma_divida_sobreviveu_a_propria_cura(self) -> None:
        """O dia em que o chamador nasce é o dia de apagar a entrada.

        Sem isto, `_SEM_CHAMADOR_HOJE` viraria o lugar onde a pergunta deste
        arquivo se esconde: bastaria declarar tudo, uma vez, e o portão calaria
        para sempre. É o mesmo `xfail(strict=True)` do molde da casa.
        """
        soltos = portoes_sem_chamador()
        curados = sorted(set(_SEM_CHAMADOR_HOJE) - soltos)
        assert not curados, (
            f"{len(curados)} dívida(s) declarada(s) como sem chamador, e algum "
            f"runner JÁ os chama:\n" + "\n".join(f"  - {c}" for c in curados) + "\n"
            "APAGUE a entrada. A cura chegou e a lápide ficou — é assim que um "
            "registro honesto vira mentira."
        )

    def test_as_razoes_nao_envelhecem_caladas(self) -> None:
        """Razão curta é isenção fingindo ser decisão; sem data, vira paisagem.

        Acumula e acusa uma vez só — a regra de varredura de 25/08/2026 do
        `portao_a_casa_sabe_e_o_produto_nao_faz`: `assert` dentro do laço corta
        no primeiro achado e esconde o resto.
        """
        queixas: list[str] = []
        for chave, razao in _SEM_CHAMADOR_HOJE.items():
            if len(razao) <= _RAZAO_MINIMA:
                queixas.append(
                    f"{chave}: a razão tem {len(razao)} caracteres e não cabe "
                    "a linha exata que ligaria o portão"
                )
            if not _DATA.search(razao):
                queixas.append(f"{chave}: a razão não tem data (DD/MM/AAAA)")
        assert not queixas, "\n".join(f"  - {q}" for q in queixas)


class TestOPortaoMorde:
    """A régua conferida contra respostas que já se conhece."""

    def _arvore_de_mentira(self, tmp_path: Path) -> Path:
        """Uma casa mínima: a pasta de scripts e a tabela de portões."""
        (tmp_path / "scripts").mkdir()
        (tmp_path / "scripts" / "portoes.sh").write_text(
            "_LISTA() {\n"
            "  cat <<'TABELA'\n"
            "rapido|acentuacao|py|scripts/validar-acentuacao.py --all\n"
            "TABELA\n"
            "}\n",
            encoding="utf-8",
        )
        (tmp_path / "scripts" / "validar-acentuacao.py").write_text(
            "# um portão que a tabela chama\n", encoding="utf-8"
        )
        return tmp_path

    def test_um_portao_fabricado_e_acusado_sem_estar_na_lista(
        self, tmp_path: Path
    ) -> None:
        """A prova que vale: a régua pega o PRÓXIMO, não só os de hoje."""
        casa = self._arvore_de_mentira(tmp_path)
        (casa / "scripts" / "check_inventado.py").write_text(
            "# um vigia que ninguém chama\n", encoding="utf-8"
        )

        soltos = portoes_sem_chamador(casa)
        assert "scripts/check_inventado.py" in soltos, (
            "a régua NÃO acusou o portão fabricado — ela não pega o próximo, "
            f"só cataloga os de hoje. Acusados: {sorted(soltos)}"
        )
        assert "scripts/validar-acentuacao.py" not in soltos, (
            "a régua acusou um portão que a tabela CHAMA — ela grita sempre, e "
            "um portão que grita sempre é desligado na primeira semana"
        )
        assert "scripts/check_inventado.py" not in portoes_sem_chamador(), (
            "a árvore de verdade foi contaminada pela mordida"
        )

    def test_ligar_o_portao_fabricado_o_faz_sumir_da_acusacao(
        self, tmp_path: Path
    ) -> None:
        """A outra metade: a régua CALA quando o chamador chega."""
        casa = self._arvore_de_mentira(tmp_path)
        (casa / "scripts" / "check_inventado.py").write_text(
            "# um vigia que ninguém chama\n", encoding="utf-8"
        )
        assert "scripts/check_inventado.py" in portoes_sem_chamador(casa)

        tabela = casa / "scripts" / "portoes.sh"
        tabela.write_text(
            tabela.read_text(encoding="utf-8").replace(
                "TABELA\n}",
                "rapido|inventado|py|scripts/check_inventado.py\nTABELA\n}",
            ),
            encoding="utf-8",
        )
        assert "scripts/check_inventado.py" not in portoes_sem_chamador(casa), (
            "a régua continuou acusando um portão JÁ LIGADO na tabela"
        )

    def test_a_declaracao_de_divergencia_nao_conta_como_chamador(
        self, tmp_path: Path
    ) -> None:
        """A linha que separa esta régua da do `portoes.sh ↔ ci.yml`.

        MEDIDO: `FORA-DO-LOCAL`/`FORA-DO-CI` declaram uma DIFERENÇA entre as
        duas listas, não uma execução. Se contassem como chamador, bastaria
        declarar um portão divergente para ele nunca mais rodar em lugar
        nenhum e esta régua calar — que é a pergunta do outro portão respondida
        no lugar da desta.
        """
        casa = self._arvore_de_mentira(tmp_path)
        (casa / "scripts" / "check_inventado.py").write_text("# vigia\n", encoding="utf-8")
        tabela = casa / "scripts" / "portoes.sh"
        tabela.write_text(
            tabela.read_text(encoding="utf-8")
            + "_DIVERGENCIAS() {\n  cat <<'DIV'\n"
            "FORA-DO-LOCAL|scripts/check_inventado.py|um motivo qualquer.\n"
            "DIV\n}\n",
            encoding="utf-8",
        )
        assert "scripts/check_inventado.py" in portoes_sem_chamador(casa), (
            "a régua aceitou uma linha de DIVERGÊNCIA como prova de execução — "
            "ela passou a responder a pergunta do outro portão"
        )

    def test_a_mencao_em_comentario_nao_conta_como_chamador(
        self, tmp_path: Path
    ) -> None:
        """Citar não é rodar — é a forma exata que enganou por dois anos."""
        casa = self._arvore_de_mentira(tmp_path)
        (casa / "scripts" / "check_inventado.py").write_text("# vigia\n", encoding="utf-8")
        fluxos = casa / ".github" / "workflows"
        fluxos.mkdir(parents=True)
        (fluxos / "ci.yml").write_text(
            "jobs:\n"
            "  portoes:\n"
            "    steps:\n"
            "      # TODO: ligar scripts/check_inventado.py nesta leva\n"
            "      - run: echo oi\n",
            encoding="utf-8",
        )
        assert "scripts/check_inventado.py" in portoes_sem_chamador(casa), (
            "a régua aceitou um COMENTÁRIO de YAML como chamador"
        )

    def test_a_varredura_enxerga_os_portoes_que_ja_se_conhece(self) -> None:
        """A régua conferida contra a árvore de verdade, e não contra si mesma.

        Se a descoberta quebrar (uma mudança de forma de nome, uma pasta que
        deixou de ser varrida), este caso cai — e sem ele o portão devolveria
        "nenhum órfão" por não ter olhado para lugar nenhum, que é o pior
        desfecho possível.
        """
        disco = portoes_no_disco()
        assert len(disco) >= 15, (
            f"a varredura achou só {len(disco)} portão(ões) em `scripts/`; "
            "eram 18 em 25/08/2026. A descoberta quebrou"
        )
        for conhecido in (
            "scripts/check_anonymity.sh",
            "scripts/validar-referencias-docs.py",
            "scripts/check_broadcast_proibido.py",
        ):
            assert conhecido in disco, f"a varredura perdeu {conhecido}"

    def test_a_regua_sabe_recusar_uma_arvore_vazia(self, tmp_path: Path) -> None:
        """Dublê que só sabe passar não é dublê.

        Uma casa sem `scripts/` tem de dar conjunto vazio, e não estourar — é o
        que garante que a régua está lendo o disco que lhe deram, e não o desta
        árvore por baixo do pano.
        """
        assert portoes_no_disco(tmp_path) == set()
        assert portoes_sem_chamador(tmp_path) == set()


def test_o_registro_e_a_varredura_nao_se_contradizem() -> None:
    """A soma fecha: órfão declarado + órfão acusado = todo órfão do disco."""
    soltos = portoes_sem_chamador()
    declarados = set(_SEM_CHAMADOR_HOJE)
    assert declarados <= soltos or not declarados - soltos, (
        "há entrada declarada que a varredura não considera órfã — o "
        f"`test_nenhuma_divida_sobreviveu_a_propria_cura` explica: {sorted(declarados - soltos)}"
    )


if __name__ == "__main__":  # pragma: no cover - conveniência de bancada
    raise SystemExit(pytest.main([__file__, "-q"]))

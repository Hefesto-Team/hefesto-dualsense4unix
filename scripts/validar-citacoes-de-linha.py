#!/usr/bin/env python3
"""validar-citacoes-de-linha.py — ABRE cada `arquivo:linha` citado e confere.

O `scripts/validar-referencias-docs.py` confere o **arquivo**. Este confere a
**linha**, que é a metade que apodrece sozinha: nenhuma refatoração renomeia
`core/backend_pydualsense.py`, e toda refatoração move o que estava na linha
789 dele.

O CASO QUE ORIGINOU O PORTÃO (medido em 13/08/2026)
----------------------------------------------------
`docs/protocol/dualsense-referencia-canonica.md`, na nota datada de 11/08, dizia:

    | pré-amp, `common[37]` | `core/backend_pydualsense.py:783-790`, com o
    | `VALID_FLAG1_AUDIO_CONTROL2_ENABLE` em `:789` | **ALTA** — lido no código |

A afirmação continua VERDADEIRA. O endereço é que caducou: `:783-790` está no
meio de um docstring, e o flag vive em `:937` e `:939`. Quem foi conferir o
grau **ALTA — lido no código** abriu o arquivo e não achou nada — e uma linha
que não abre vale o mesmo que citação nenhuma.

Não é caso isolado: a mesma varredura achou
`core/physical_report_reader.py:854-865` prometendo `_observe_jack`, que é
definido em `:838`. Dois endereços podres numa árvore que tem portão para
arquivo inexistente desde a PORTÃO-VIVO-01.

AS DUAS PERGUNTAS QUE ELE FAZ
------------------------------
1. **A faixa existe?** `arquivo:N` ou `arquivo:N-M` — o arquivo precisa ter ao
   menos M linhas, e N não pode ser maior que M. Pega o endereço que aponta
   para além do fim depois de o arquivo encolher.
2. **A faixa contém o que a citação promete?** Só quando a citação NOMEIA algo:
   um identificador entre crases colado ao endereço, em uma das duas formas que
   esta casa escreve de verdade —

       `SIMBOLO` em `arquivo:N`      (ou "no"/"na" no lugar de "em")
       `arquivo:N-M` (`SIMBOLO`)

   O nome tem de aparecer no trecho citado. É a pergunta que pega o caso do
   pré-amp, em que a faixa existia e não continha nada do que prometia.

Citação sem nome colado passa pela pergunta 1 e não pela 2: o portão não
adivinha promessa não escrita.

AS TRÊS CONSERVADORIAS, CADA UMA MEDIDA
----------------------------------------
Esta casa já escreveu a régua em `validar-referencias-docs.py`: *"falso
positivo em massa torna o gate inútil"*. As três exclusões daqui saíram de
sondagem na árvore de 13/08/2026, não de precaução genérica:

- **Fonte de fora da árvore é IGNORADA.** Dos 204 endereços de
  `docs/protocol/`, **136** citam `hid-nintendo.c`, `xpad.c`,
  `SDL_hidapi_ps5.c` e companhia — fontes que a casa leu e não versiona (o
  `hid-nintendo.c` é a exceção: ele mora em `assets/dkms/`, resolve, e é
  conferido). Reprovar por elas seria reprovar por ler o kernel.
- **Continuação `:N` só vale ancorada na MESMA LINHA.** A forma curta é
  frequente (183 ocorrências) e o documento a usa esperando que o leitor herde
  o arquivo do contexto — que às vezes está três seções acima. Resolver pela
  "última citação vista no documento" foi tentado e produziu **seis acusações
  falsas** de uma vez em `externos-referencia-canonica.md`, onde `:1644-1646`
  pertence ao `hid-nintendo.c` e a última citação explícita anterior era
  `core/external_leds.py:155`. Ancorar na mesma linha deixa 17 continuações sob
  o portão e as outras 153 fora — menos alcance, zero invenção.
- **Só `docs/protocol/`.** É onde mora a citação de código como PROVA: o grau
  de confiança de cada linha da canônica se apoia num endereço. Em
  `docs/process/` uma sprint cita a árvore do dia em que foi escrita, e
  cobrá-la seria pedir que o registro histórico se atualizasse sozinho.

Uso:

    python3 scripts/validar-citacoes-de-linha.py --all
    python3 scripts/validar-citacoes-de-linha.py docs/protocol/trigger-modes.md
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

#: A pasta que este portão vigia, e só ela. A razão está no cabeçalho.
PASTA = Path("docs") / "protocol"

#: Onde um caminho citado pode estar: na raiz, ou dentro do pacote. A casa cita
#: `core/backend_pydualsense.py` querendo dizer
#: `src/hefesto_dualsense4unix/core/backend_pydualsense.py` o tempo todo.
PREFIXOS = ("", "src/hefesto_dualsense4unix")

EXTENSOES = "py|sh|c|h|md|yml|yaml|toml|rules|glade|css|js"

#: `arquivo.ext:N`, `arquivo.ext:N-M`, e a forma curta `:N` / `:N-M`.
ENDERECO = re.compile(
    rf"`(?P<arq>[A-Za-z0-9_][A-Za-z0-9_./-]*\.(?:{EXTENSOES}))?"
    r":(?P<a>\d+)(?:-(?P<b>\d+))?`"
)

#: `SIMBOLO` em `arquivo:N` — o nome vem ANTES do endereço.
NOME_ANTES = re.compile(r"`(?P<nome>[A-Za-z_][A-Za-z0-9_]{2,})`\s*(?:em|no|na)\s+$")

#: `arquivo:N-M` (`SIMBOLO`) — o nome vem entre parênteses logo DEPOIS.
NOME_DEPOIS = re.compile(r"\s*\(`(?P<nome>[A-Za-z_][A-Za-z0-9_]{2,})`\)")

#: Quanto do texto à esquerda do endereço entra na busca pelo nome prometido.
#: Largo o bastante para "com o `VALID_FLAG1_AUDIO_CONTROL2_ENABLE` em", curto
#: o bastante para não atravessar a célula vizinha de uma tabela.
JANELA_ESQUERDA = 120


@dataclass(frozen=True)
class Achado:
    documento: str
    linha: int
    endereco: str
    motivo: str

    def __str__(self) -> str:
        return f"{self.documento}:{self.linha}: {self.endereco} -- {self.motivo}"


def resolve(arquivo: str, raiz: Path) -> Path | None:
    """O caminho real de um arquivo citado, ou None se ele não é desta árvore."""
    for prefixo in PREFIXOS:
        candidato = raiz / prefixo / arquivo if prefixo else raiz / arquivo
        if candidato.is_file():
            return candidato
    return None


def nomes_prometidos(linha: str, inicio: int, fim: int) -> set[str]:
    """Os identificadores que a citação promete encontrar na faixa."""
    nomes: set[str] = set()
    esquerda = NOME_ANTES.search(linha[max(0, inicio - JANELA_ESQUERDA):inicio])
    if esquerda:
        nomes.add(esquerda.group("nome"))
    direita = NOME_DEPOIS.match(linha[fim:fim + 80])
    if direita:
        nomes.add(direita.group("nome"))
    return nomes


def varrer_documento(documento: Path, raiz: Path) -> tuple[list[Achado], int, int]:
    """Devolve (achados, endereços conferidos, endereços ignorados por serem de fora)."""
    achados: list[Achado] = []
    conferidos = de_fora = 0
    corpos: dict[Path, list[str]] = {}

    texto = documento.read_text(encoding="utf-8")
    relativo = documento.resolve().relative_to(raiz).as_posix()
    for numero, linha in enumerate(texto.splitlines(), 1):
        ancora: str | None = None
        for achado in ENDERECO.finditer(linha):
            explicito = achado.group("arq")
            if explicito:
                ancora = explicito
            arquivo = explicito or ancora
            if arquivo is None:
                # Forma curta sem âncora NESTA linha: ambígua por desenho.
                continue
            alvo = resolve(arquivo, raiz)
            if alvo is None:
                de_fora += 1
                continue
            if alvo not in corpos:
                corpos[alvo] = alvo.read_text(
                    encoding="utf-8", errors="replace").splitlines()
            corpo = corpos[alvo]

            primeira = int(achado.group("a"))
            ultima = int(achado.group("b") or achado.group("a"))
            endereco = f"`{arquivo}:{primeira}" + (
                f"-{ultima}`" if achado.group("b") else "`")
            conferidos += 1

            if primeira < 1 or primeira > ultima:
                achados.append(Achado(relativo, numero, endereco,
                                      "a faixa está invertida ou começa em zero"))
                continue
            if ultima > len(corpo):
                achados.append(Achado(
                    relativo, numero, endereco,
                    f"a linha não existe: {arquivo} tem {len(corpo)} linha(s)"))
                continue

            trecho = "\n".join(corpo[primeira - 1:ultima])
            for nome in sorted(nomes_prometidos(linha, achado.start(), achado.end())):
                if nome not in trecho:
                    achados.append(Achado(
                        relativo, numero, endereco,
                        f"a faixa não contém `{nome}`, que a citação promete"))
    return achados, conferidos, de_fora


def documentos_de(raiz: Path) -> list[Path]:
    pasta = raiz / PASTA
    return sorted(pasta.glob("*.md")) if pasta.is_dir() else []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Reprova citação de linha que não abre ou não contém o que promete.")
    parser.add_argument("arquivos", nargs="*", type=Path, help="documentos a varrer")
    parser.add_argument("--all", action="store_true",
                        help=f"varre {PASTA.as_posix()}/ inteiro")
    parser.add_argument("--root", type=Path,
                        default=Path(__file__).resolve().parent.parent,
                        help="raiz do repositório (padrão: a deste script)")
    args = parser.parse_args(argv)

    raiz = args.root.resolve()
    if not raiz.is_dir():
        print(f"ERRO: raiz inexistente: {raiz}", file=sys.stderr)
        return 2

    if args.all:
        alvos = documentos_de(raiz)
    else:
        alvos = [
            p for p in args.arquivos
            if p.suffix == ".md" and p.is_file()
            and p.resolve().parent == (raiz / PASTA).resolve()
        ]
    if not alvos:
        print("Nenhum documento para varrer.")
        return 0

    achados: list[Achado] = []
    conferidos = de_fora = 0
    for alvo in alvos:
        seus, quantos, fora = varrer_documento(alvo, raiz)
        achados.extend(seus)
        conferidos += quantos
        de_fora += fora

    if achados:
        print(f"{len(achados)} citação(ões) de linha podre(s) em "
              f"{len(alvos)} documento(s):")
        for achado in achados:
            print(str(achado))
        print("")
        print("Cada linha acima cita um endereço que NÃO abre no que promete.")
        print("A afirmação pode continuar verdadeira — o que caducou é o")
        print("endereço. Reaponte-o para onde a coisa está hoje; não apague a")
        print("afirmação, e não troque o endereço por prosa vaga: um grau de")
        print("confiança sem `arquivo:linha` desce de nível nesta casa.")
        return 1

    print(f"OK: {conferidos} citação(ões) de linha conferida(s) em "
          f"{len(alvos)} documento(s); {de_fora} de fontes fora desta árvore "
          "(kernel, SDL, wine) foram ignoradas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

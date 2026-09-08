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
- **De `.md`, só `docs/protocol/`.** É onde mora a citação de código como
  PROVA: o grau de confiança de cada linha da canônica se apoia num endereço.
  Em `docs/process/` uma sprint cita a árvore do dia em que foi escrita, e
  cobrá-la seria pedir que o registro histórico se atualizasse sozinho.

O MAPA ENTROU (31/08/2026) — decisão dela
------------------------------------------
`docs/data/mapa-controles.csv` carrega **762 citações `arquivo:linha`** na
prosa das células, e até hoje **nenhuma tinha portão**: o script varria só
`docs/protocol/` e recusava o CSV até quando nomeado à mão. Uma citação que
aponta para a linha errada depois de um refactor vira afirmação forte e falsa,
e o mapa a propaga — que é o defeito que esta casa mais paga.

**O portão nasce em ZERO**, como a regra 19 do `check_paridade_transporte.py`.
Medido em 31/08/2026, com o mapa em disco: das 762, **723 resolvem nesta
árvore** e **ZERO aponta além do fim**, ZERO tem faixa invertida e ZERO promete
símbolo que a faixa não contém. Nada foi consertado aqui — o que se fecha é o
buraco por onde a primeira podridão entraria calada.

Alcance nas outras planilhas de `docs/data/`, medido no mesmo dia:
`ensaios.csv` 14 citações (11 resolvem), `decisoes-dela.csv` 58 (42), e os
outros quatro CSV zero. Todas em zero podre.

O CSV SE LÊ COM O MÓDULO `csv`, NUNCA COM REGEX SOBRE O ARQUIVO CRU
--------------------------------------------------------------------
A prosa do mapa vive DENTRO de célula: com aspas, com vírgula, com quebra de
linha embutida e com o separador ` · ` entre blocos. Uma célula com vírgula
quebra qualquer varredura por linha física. O número que a linha do achado
imprime é a **primeira linha física do registro**, e o achado vem com o `id` da
linha do mapa e o **nome da coluna** — que é o que quem for consertar precisa
para achar a célula.

A REGRA QUE SEPARA CITAÇÃO VERIFICÁVEL DE CITAÇÃO EXTERNA
----------------------------------------------------------
Ela é por **RESOLUÇÃO**, não por lista de nomes proibidos: uma citação só é
cobrada quando o caminho que ela escreve **existe nesta árvore**, na raiz ou
sob `src/hefesto_dualsense4unix/`. Tudo o mais é contado e calado. Três
consequências, e as três foram medidas nas 39 citações do mapa que não
resolvem:

- **Repositório de fora resolve para nada, logo cala** (11 citações):
  `src/joystick/hidapi/SDL_hidapi_ps5.c`, `src/utils.h`,
  `js/controllers/ds5-controller.js` — a prosa dá o repo e a tag ao lado
  (`libsdl-org/SDL release-3.4.14`), e o caminho é do repo dele, não do nosso.
- **Basename solto NÃO é resolvido por busca na árvore** (28 citações): 11 são
  driver upstream citado como `hid-nintendo.c:1945` / `hid-playstation.c:132`,
  e **17 são arquivo NOSSO** citado sem o caminho (`led_control.py:119`,
  `gamepad.py:1353`, `external_identity.py:194`, `doctor.sh:497`...). Sair
  procurando o basename na árvore casaria o do driver com a cópia de
  `assets/dkms/`, que é outro arquivo em outra versão — e essas 17 ganham
  portão no dia em que alguém escrever o caminho, que é conserto de uma linha.
  Menos alcance, zero invenção: é a mesma escolha da continuação `:N`.
- **Faixa `:N-M` é citação normal** — o `M` é que tem de existir. As 447 faixas
  do mapa (de 762) passam pela mesma pergunta 1 que os endereços simples.

E **a forma curta `:N` NÃO existe no CSV**, nem ancorada na mesma célula. Uma
célula não é uma linha: ela tem até 5.399 caracteres e dezenas de blocos, então
a âncora "da mesma linha" que segura o `.md` não segura aqui. O mapa tem **706**
formas curtas soltas, e ampliar a régua de propósito para resolvê-las dentro da
célula produziu **NOVE acusações falsas** no mapa de 31/08 — o mesmo desfecho
que a tentativa de 13/08 no `.md`, que deu seis. As nove, conferidas uma a uma:

- `(JC_SUBCMD_RATE_LIMITER_MS, :976-980)` e `(guarda em :2591-2599)` em
  `luz.led_home@pro` pertencem ao `hid-nintendo.c`, citado antes na célula; a
  última citação com CAMINHO era `core/external_leds.py:129-133`, de 402 linhas.
- `(canônica :947-960 e :1200-1213)`, `(:855-857)` e `a canônica :915-920` em
  `plataforma.distinguir_clone@sn30` estão ancoradas na palavra **"canônica"**,
  que não é caminho nenhum — e resolveram contra o
  `troubleshooting-8bitdo.md` e a sprint IDENT-01 que apareciam ao lado.

Hora de relógio fecha o argumento: a prosa escreve *"a das 01:51:25 passou 27 s
depois de uma recusa às 01:50:58"*, que daria `:51`, `:25` e `:58`.

O QUE FICA DE FORA DE `docs/data/`, e por quê
----------------------------------------------
A varredura pega **todo** `*.csv` da pasta — planilha nova nasce coberta, que é
o mesmo endurecimento de forma feito no `rglob` da canônica em 26/08. As
exclusões são nominais e estão em `CSV_FORA_DO_PORTAO`, cada uma com o motivo:
os dois `*-v1.csv` são arqueologia da migração, e cobrá-los é o mesmo que
cobrar uma sprint de `docs/process/` — pedir que o registro histórico se
atualize sozinho.

Uso:

    python3 scripts/validar-citacoes-de-linha.py --all
    python3 scripts/validar-citacoes-de-linha.py docs/protocol/trigger-modes.md
    python3 scripts/validar-citacoes-de-linha.py docs/data/mapa-controles.csv
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass
from pathlib import Path

#: A pasta de `.md` que este portão vigia, e só ela. A razão está no cabeçalho.
PASTA = Path("docs") / "protocol"

#: A pasta de planilhas que ele vigia desde 31/08/2026.
PASTA_CSV = Path("docs") / "data"

#: Planilha de `docs/data/` que o portão NÃO cobra, com o motivo escrito. A
#: varredura é por glob de propósito — planilha nova nasce coberta —, então
#: toda exclusão é decisão declarada, nunca omissão.
#: VAZIO desde 05/09/2026, e o vazio é o resultado. As duas entradas que viviam
#: aqui isentavam `mapa-controles-v1.csv` e `ensaios-v1.csv` — os retratos
#: congelados da migração de 11/08. Os dois foram APAGADOS naquele dia, com a
#: razão dela: "a ideia é termos menos arquivos". Isenção para arquivo que não
#: existe é peso morto que engana quem lê. Se um CSV precisar sair do portão de
#: novo, ele entra aqui COM A RAZÃO escrita — toda exclusão é decisão declarada.
CSV_FORA_DO_PORTAO: dict[str, str] = {}

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

#: O mesmo endereço na prosa de uma célula de CSV: as crases são OPCIONAIS
#: (693 das 762 citações do mapa não têm nenhuma) e o **arquivo é obrigatório**
#: — a forma curta `:N` não existe aqui, pelo motivo medido no cabeçalho.
ENDERECO_CSV = re.compile(
    rf"(?<![A-Za-z0-9_./-])`?(?P<arq>[A-Za-z0-9_][A-Za-z0-9_./-]*\.(?:{EXTENSOES}))"
    r":(?P<a>\d+)(?:-(?P<b>\d+))?`?"
)

#: `SIMBOLO` em `arquivo:N` — o nome vem ANTES do endereço.
NOME_ANTES = re.compile(r"`(?P<nome>[A-Za-z_][A-Za-z0-9_]{2,})`\s*(?:em|no|na)\s+$")

#: `arquivo:N-M` (`SIMBOLO`) — o nome vem entre parênteses logo DEPOIS.
#:
#: **A TERCEIRA FORMA ENTROU EM 08/09/2026**, e ela é a que o mapa mais usa:
#: `arquivo:N (`SIMBOLO`, e mais uma frase explicando)`. A régua exigia o `)`
#: colado ao nome, então toda citação que continuava a frase depois da vírgula
#: caía FORA da pergunta 2 — e foi por aí que oito promessas de símbolo
#: apodreceram em 24 citações do backend com o portão VERDE. O conferente da
#: leva de 08/09 nomeou o buraco: *"a pergunta 2 dele só dispara em duas
#: formas sintáticas, e a célula usa a forma `:N (`SIMBOLO` …)`. Portão verde
#: aqui NÃO é prova."*
#:
#: O nome tem de ABRIR o parêntese — é isso que o mantém colado ao endereço.
#: `(o bloco `if not rumble_asserted:`, que apaga…)` continua fora, e é de
#: propósito: ali o parêntese começa com prosa, e o que está entre crases é
#: uma citação de código, não a promessa "este símbolo está nesta faixa".
NOME_DEPOIS = re.compile(
    r"\s*\(`(?P<nome>[A-Za-z_][A-Za-z0-9_]{2,})`\s*(?:[,)]|$)")

#: Quanto do texto à esquerda do endereço entra na busca pelo nome prometido.
#: Largo o bastante para "com o `VALID_FLAG1_AUDIO_CONTROL2_ENABLE` em", curto
#: o bastante para não atravessar a célula vizinha de uma tabela.
JANELA_ESQUERDA = 120

#: Numa célula de CSV a "linha" pode ter milhares de caracteres. A janela da
#: promessa para no bloco: a casa separa blocos por ` · ` e por quebra de linha
#: embutida, e atravessar um deles seria colar o símbolo de um bloco no
#: endereço de outro.
SEPARADORES_DE_BLOCO = ("\n", "·")


@dataclass(frozen=True)
class Achado:
    documento: str
    linha: int
    endereco: str
    motivo: str
    contexto: str = ""

    def __str__(self) -> str:
        onde = f" ({self.contexto})" if self.contexto else ""
        return f"{self.documento}:{self.linha}{onde}: {self.endereco} -- {self.motivo}"


def resolve(arquivo: str, raiz: Path) -> Path | None:
    """O caminho real de um arquivo citado, ou None se ele não é desta árvore.

    É AQUI que mora a regra que separa citação verificável de citação externa,
    e ela não consulta lista de nomes: o caminho escrito ou existe nesta
    árvore, ou o portão cala. Basename solto (`led_control.py:119`) não é
    procurado na árvore de propósito — casar por nome misturaria o
    `hid-nintendo.c` do kernel com a cópia versionada em `assets/dkms/`.
    """
    for prefixo in PREFIXOS:
        candidato = raiz / prefixo / arquivo if prefixo else raiz / arquivo
        if candidato.is_file():
            return candidato
    return None


def nomes_prometidos(
    texto: str,
    inicio: int,
    fim: int,
    separadores: tuple[str, ...] = (),
) -> set[str]:
    """Os identificadores que a citação promete encontrar na faixa."""
    esquerda_bruta = texto[max(0, inicio - JANELA_ESQUERDA):inicio]
    for separador in separadores:
        esquerda_bruta = esquerda_bruta.rpartition(separador)[2]
    nomes: set[str] = set()
    esquerda = NOME_ANTES.search(esquerda_bruta)
    if esquerda:
        nomes.add(esquerda.group("nome"))
    direita = NOME_DEPOIS.match(texto[fim:fim + 80])
    if direita:
        nomes.add(direita.group("nome"))
    return nomes


def confere_endereco(
    origem: str,
    linha: int,
    contexto: str,
    texto: str,
    achado: re.Match[str],
    arquivo: str,
    corpos: dict[Path, list[str]],
    raiz: Path,
    separadores: tuple[str, ...] = (),
) -> tuple[list[Achado], bool, bool]:
    """As duas perguntas, para UM endereço.

    Devolve (achados, conferido, de_fora) — e `conferido` e `de_fora` são
    exclusivos: ou o arquivo resolve nesta árvore e o endereço é cobrado, ou
    ele é de fora e sai contado, não acusado.
    """
    alvo = resolve(arquivo, raiz)
    if alvo is None:
        return [], False, True
    if alvo not in corpos:
        corpos[alvo] = alvo.read_text(encoding="utf-8", errors="replace").splitlines()
    corpo = corpos[alvo]

    primeira = int(achado.group("a"))
    ultima = int(achado.group("b") or achado.group("a"))
    endereco = f"`{arquivo}:{primeira}" + (
        f"-{ultima}`" if achado.group("b") else "`")

    if primeira < 1 or primeira > ultima:
        return ([Achado(origem, linha, endereco,
                        "a faixa está invertida ou começa em zero", contexto)],
                True, False)
    if ultima > len(corpo):
        return ([Achado(origem, linha, endereco,
                        f"a linha não existe: {arquivo} tem {len(corpo)} linha(s)",
                        contexto)],
                True, False)

    trecho = "\n".join(corpo[primeira - 1:ultima])
    achados = [
        Achado(origem, linha, endereco,
               f"a faixa não contém `{nome}`, que a citação promete", contexto)
        for nome in sorted(
            nomes_prometidos(texto, achado.start(), achado.end(), separadores))
        if nome not in trecho
    ]
    return achados, True, False


def varrer_documento(
    documento: Path,
    raiz: Path,
    corpos: dict[Path, list[str]] | None = None,
) -> tuple[list[Achado], int, int]:
    """Devolve (achados, endereços conferidos, endereços ignorados por serem de fora)."""
    achados: list[Achado] = []
    conferidos = de_fora = 0
    if corpos is None:
        corpos = {}

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
            seus, conferido, fora = confere_endereco(
                relativo, numero, "", linha, achado, arquivo, corpos, raiz)
            achados.extend(seus)
            conferidos += conferido
            de_fora += fora
    return achados, conferidos, de_fora


def varrer_planilha(
    planilha: Path,
    raiz: Path,
    corpos: dict[Path, list[str]] | None = None,
) -> tuple[list[Achado], int, int]:
    """O mesmo, célula a célula, lido pelo módulo `csv`.

    Nunca por regex sobre o arquivo cru: a prosa do mapa tem vírgula, aspas e
    quebra de linha DENTRO da célula, e uma varredura por linha física
    despedaçaria a célula no meio de um endereço.
    """
    achados: list[Achado] = []
    conferidos = de_fora = 0
    if corpos is None:
        corpos = {}
    relativo = planilha.resolve().relative_to(raiz).as_posix()

    with planilha.open(encoding="utf-8", newline="") as fluxo:
        leitor = csv.reader(fluxo)
        try:
            cabecalho = next(leitor)
        except StopIteration:
            return achados, conferidos, de_fora
        coluna_id = cabecalho.index("id") if "id" in cabecalho else 0
        # `line_num` é a linha física em que o registro TERMINOU. A que
        # interessa a quem for consertar é onde ele começou.
        fim_do_anterior = leitor.line_num
        for registro in leitor:
            inicio = fim_do_anterior + 1
            fim_do_anterior = leitor.line_num
            chave = registro[coluna_id] if coluna_id < len(registro) else ""
            for indice, celula in enumerate(registro):
                if ":" not in celula:
                    continue
                coluna = (cabecalho[indice] if indice < len(cabecalho)
                          else f"coluna {indice + 1}")
                contexto = f"{chave} · {coluna}" if chave else coluna
                for achado in ENDERECO_CSV.finditer(celula):
                    seus, conferido, fora = confere_endereco(
                        relativo, inicio, contexto, celula, achado,
                        achado.group("arq"), corpos, raiz, SEPARADORES_DE_BLOCO)
                    achados.extend(seus)
                    conferidos += conferido
                    de_fora += fora
    return achados, conferidos, de_fora


def documentos_de(raiz: Path) -> list[Path]:
    """Todo `.md` sob a pasta vigiada, em QUALQUER profundidade.

    ENDURECIMENTO, 26/08/2026 (LEVA-4-E) — e sem defeito vivo para mostrar:
    `docs/protocol/` é plano hoje, então `glob("*.md")` e `rglob("*.md")`
    devolvem a mesma lista de 13 documentos, e NADA estava sendo perdido. O que
    se conserta aqui é o defeito de FORMA: no dia em que a canônica crescer
    para uma subpasta, o `glob` raso passaria a ficar verde por não olhar. É o
    mesmo defeito que a casa achou em 25/08 no `test_nome_citado_como_sprint`,
    e ele não custa nada para fechar antes de morder.
    """
    pasta = raiz / PASTA
    return sorted(pasta.rglob("*.md")) if pasta.is_dir() else []


def planilhas_de(raiz: Path) -> list[Path]:
    """Todo `*.csv` de `docs/data/` menos os declarados em CSV_FORA_DO_PORTAO."""
    pasta = raiz / PASTA_CSV
    if not pasta.is_dir():
        return []
    return sorted(p for p in pasta.glob("*.csv")
                  if p.name not in CSV_FORA_DO_PORTAO)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Reprova citação de linha que não abre ou não contém o que promete.")
    parser.add_argument("arquivos", nargs="*", type=Path,
                        help="documentos ou planilhas a varrer")
    parser.add_argument("--all", action="store_true",
                        help=f"varre {PASTA.as_posix()}/ e {PASTA_CSV.as_posix()}/*.csv")
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
        planilhas = planilhas_de(raiz)
    else:
        #: `is_relative_to`, e não `parent ==`: a mesma correção de forma de
        #: `documentos_de` — passar à mão um `.md` de subpasta da canônica era
        #: descartado em silêncio, sem uma palavra de recusa.
        pasta_vigiada = (raiz / PASTA).resolve()
        pasta_de_dados = (raiz / PASTA_CSV).resolve()
        alvos = [
            p for p in args.arquivos
            if p.suffix == ".md" and p.is_file()
            and p.resolve().is_relative_to(pasta_vigiada)
        ]
        planilhas = [
            p for p in args.arquivos
            if p.suffix == ".csv" and p.is_file()
            and p.resolve().parent == pasta_de_dados
            and p.name not in CSV_FORA_DO_PORTAO
        ]
    if not alvos and not planilhas:
        print("Nenhum documento para varrer.")
        return 0

    achados: list[Achado] = []
    conferidos = de_fora = 0
    corpos: dict[Path, list[str]] = {}
    for alvo in alvos:
        seus, quantos, fora = varrer_documento(alvo, raiz, corpos)
        achados.extend(seus)
        conferidos += quantos
        de_fora += fora
    for planilha in planilhas:
        seus, quantos, fora = varrer_planilha(planilha, raiz, corpos)
        achados.extend(seus)
        conferidos += quantos
        de_fora += fora

    onde = f"{len(alvos)} documento(s) e {len(planilhas)} planilha(s)"
    if achados:
        print(f"{len(achados)} citação(ões) de linha podre(s) em {onde}:")
        for achado in achados:
            print(str(achado))
        print("")
        print("Cada linha acima cita um endereço que NÃO abre no que promete.")
        print("A afirmação pode continuar verdadeira — o que caducou é o")
        print("endereço. Reaponte-o para onde a coisa está hoje; não apague a")
        print("afirmação, e não troque o endereço por prosa vaga: um grau de")
        print("confiança sem `arquivo:linha` desce de nível nesta casa.")
        return 1

    print(f"OK: {conferidos} citação(ões) de linha conferida(s) em {onde}; "
          f"{de_fora} de fontes fora desta árvore (kernel, SDL, wine) "
          "foram ignoradas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

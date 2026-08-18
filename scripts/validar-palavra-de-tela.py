#!/usr/bin/env python3
"""Portão da palavra de tela: a janela fala a língua de quem joga.

PALAVRA-01 / E5, seção "E5. Um gate, para não voltar" de
`docs/process/sprints/2026-07-27-PALAVRA-01-a-janela-fala-a-lingua-de-quem-joga.md`.
A sprint pede um portão que reprove quando:

- um texto de tela começa com letra minúscula, **com lista de exceções
  explícita e justificada, não implícita**;
- um rótulo visível contém termo da lista de jargão banido.

O ALCANCE, declarado e estreito: o `main.glade`, que é onde mora o texto
DECLARATIVO da janela. Rótulo montado em Python (`set_label`, f-string de
status) fica de fora **de propósito** — varrer código atrás de "isto aparece na
tela?" produz falso positivo em cima de nome de variável, chave de perfil e
mensagem de log, e um portão que grita falso é desligado na semana seguinte.
O que o `.glade` não cobre está anotado como lacuna no fim deste docstring.

POR QUE ELE NASCE COM DÍVIDA DECLARADA. A sprint previa que o portão entrasse
JUNTO com a troca dos 24 rótulos (E1 a E4). A troca não veio: MEDIDO em
13/08/2026 nesta árvore, quatro rótulos ainda carregam jargão da tabela E3, e
os três `window_class:` / `title_regex:` / `process_name:` ainda começam em
minúscula. Havia duas saídas ruins e uma boa:

- nascer VERMELHO e derrubar o CI por um trabalho de redação que é dela: não;
- nascer com a lista de jargão vazia, "para não incomodar": isso é decoração
  com nome de portão, e é o defeito-mãe desta casa (PORTÃO-VIVO-01);
- nascer com cada sobrevivente ESCRITO, um a um, com o que ele vira e por que
  ainda não virou. É esta.

A dívida declarada não envelhece calada: se um rótulo declarado aqui sumir ou
mudar, o portão reprova pedindo que a entrada seja APAGADA. E o portão morde
onde a sprint pediu que ele mordesse — "reintroduzir `daemon offline` num
rótulo tem de reprovar de novo": um rótulo NOVO com jargão não está em lista
nenhuma, e reprova.

Uso:
    scripts/validar-palavra-de-tela.py --all
    scripts/validar-palavra-de-tela.py --check-file caminho/arquivo.glade
    scripts/validar-palavra-de-tela.py --mostrar-criterio

Saída: uma linha por achado, em ``arquivo:linha: motivo``. Código de saída 0 se
limpo, 1 se houver achado.

LACUNAS CONHECIDAS (13/08/2026), escritas para não serem confundidas com
cobertura: o texto que a interface monta em Python não é varrido; os catálogos
de tradução (`po/`) não são varridos; e a maiúscula é conferida no primeiro
caractere do rótulo, não frase a frase dentro dele.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from xml.parsers import expat

RAIZ = Path(__file__).resolve().parents[1]
GLADE = RAIZ / "src" / "hefesto_dualsense4unix" / "gui" / "main.glade"

#: As propriedades do Glade que viram texto NA TELA. `label` é o grosso; as
#: outras três entram porque a pessoa lê as quatro do mesmo jeito.
PROPRIEDADES_DE_TELA = frozenset({"label", "title", "text", "tooltip_text"})

#: Rótulo que PODE começar em minúscula, com a justificativa ao lado. Explícita
#: e linha a linha, como a E5 exige — uma lista de exceções sem motivo escrito
#: vira o armário onde se guarda o que incomoda.
EXCECOES_DE_MINUSCULA: dict[str, str] = {
    "window_class:": (
        "13/08/2026 — é o nome LITERAL da chave de perfil que a pessoa digita "
        "no campo ao lado, e trocá-lo por `Janela:` (o que a E3 da PALAVRA-01 "
        "propõe) é redação de tela, que é decisão dela e não deste portão."
    ),
    "title_regex:": (
        "13/08/2026 — mesma razão de `window_class:`: chave literal de perfil. "
        "A E3 da PALAVRA-01 propõe `Título:`; a troca é dela."
    ),
    "process_name:": (
        "13/08/2026 — mesma razão de `window_class:`: chave literal de perfil. "
        "A E3 da PALAVRA-01 propõe `Programa:`; a troca é dela."
    ),
}

#: O jargão que a E3 da PALAVRA-01 aposentou, e o que ele vira. A chave é
#: comparada sem diferenciar maiúscula de minúscula.
JARGAO_BANIDO: dict[str, str] = {
    "daemon offline": "O Hefesto está desligado",
    "daemon pausado": "O Hefesto está em pausa",
    "uinput disponível": "Pronto para usar como mouse",
    "Restaurar Default": "Voltar ao padrão",
    "Travar Proton validado": "Fixar a versão que funciona",
    "Aplicar correções": "Consertar problemas conhecidos",
    "Testar criação de device virtual": "Testar o controle virtual",
    "Gamepads:": "Controles detectados:",
}

#: Os rótulos que AINDA carregam jargão nesta árvore, um a um, medidos em
#: 13/08/2026. Não é perdão: é a dívida da E1-E4 escrita com nome e endereço,
#: para que o portão possa entrar hoje sem derrubar o CI por um trabalho de
#: redação que não é dele. Some daqui no commit que trocar o rótulo — e o
#: portão reprova se alguém esquecer de apagar a entrada.
DIVIDA_DA_PALAVRA_01: dict[str, str] = {
    "Aplicar correções": (
        "13/08/2026 — sobrevivente da E3 da PALAVRA-01, que ainda não foi "
        "executada. Vira `Consertar problemas conhecidos`."
    ),
    "Travar Proton validado": (
        "13/08/2026 — sobrevivente da E3 da PALAVRA-01, que ainda não foi "
        "executada. Vira `Fixar a versão que funciona`."
    ),
    "Gamepads:": (
        "13/08/2026 — sobrevivente da E3 da PALAVRA-01, que ainda não foi "
        "executada. Vira `Controles detectados:`."
    ),
    "Restaurar Default": (
        "13/08/2026 — sobrevivente da E3 da PALAVRA-01, que ainda não foi "
        "executada. Vira `Voltar ao padrão`."
    ),
}


class Rotulo:
    """Um texto de tela, com onde ele mora."""

    def __init__(self, arquivo: Path, linha: int, propriedade: str, texto: str) -> None:
        self.arquivo = arquivo
        self.linha = linha
        self.propriedade = propriedade
        self.texto = " ".join(texto.split())

    def __repr__(self) -> str:  # pragma: no cover - conveniência de depuração
        return f"Rotulo({self.arquivo.name}:{self.linha} {self.texto!r})"


def rotulos_do_glade(caminho: Path) -> list[Rotulo]:
    """Todo texto de tela do arquivo, com a linha em que ele começa.

    O `expat` é usado em vez de expressão regular por dois motivos concretos: a
    propriedade pode ocupar várias linhas, e o valor chega com as entidades XML
    já desfeitas (`&amp;` vira `&`) — que é o texto que a pessoa lê de fato.
    """
    achados: list[Rotulo] = []
    aberta: dict[str, object] = {"nome": "", "linha": 0, "pedacos": []}

    def abriu(nome: str, atributos: dict[str, str]) -> None:
        if nome == "property" and atributos.get("name") in PROPRIEDADES_DE_TELA:
            aberta["nome"] = atributos["name"]
            aberta["linha"] = analisador.CurrentLineNumber
            aberta["pedacos"] = []

    def texto(dados: str) -> None:
        if aberta["nome"]:
            aberta["pedacos"].append(dados)  # type: ignore[union-attr]

    def fechou(nome: str) -> None:
        if nome == "property" and aberta["nome"]:
            achados.append(
                Rotulo(
                    caminho,
                    int(aberta["linha"]),  # type: ignore[call-overload]
                    str(aberta["nome"]),
                    "".join(aberta["pedacos"]),  # type: ignore[arg-type]
                )
            )
            aberta["nome"] = ""

    analisador = expat.ParserCreate()
    analisador.StartElementHandler = abriu
    analisador.CharacterDataHandler = texto
    analisador.EndElementHandler = fechou
    analisador.Parse(caminho.read_bytes(), True)
    return achados


def comeca_em_minuscula(texto: str) -> bool:
    """O rótulo abre com letra minúscula?

    Marcação Pango (`<i>`, `<b>`) e pontuação não contam como primeira letra —
    o que interessa é a primeira LETRA que a pessoa lê.
    """
    sem_marcacao = texto
    while sem_marcacao.startswith("<") and ">" in sem_marcacao:
        sem_marcacao = sem_marcacao[sem_marcacao.index(">") + 1 :].lstrip()
    for caractere in sem_marcacao:
        if caractere.isalpha():
            return caractere.islower()
    return False


def jargao_em(texto: str) -> str | None:
    """O primeiro termo banido que aparece no rótulo, ou None."""
    achatado = texto.lower()
    for termo in JARGAO_BANIDO:
        if termo.lower() in achatado:
            return termo
    return None


def conferir(caminho: Path) -> list[str]:
    """As reprovações do arquivo, em ordem de linha."""
    if not caminho.is_file():
        return [f"{caminho}: arquivo de interface não encontrado"]

    achados: list[str] = []
    rotulos = rotulos_do_glade(caminho)

    for rotulo in rotulos:
        if not rotulo.texto:
            continue

        if comeca_em_minuscula(rotulo.texto) and rotulo.texto not in EXCECOES_DE_MINUSCULA:
            achados.append(
                f"{rotulo.arquivo}:{rotulo.linha}: o rótulo "
                f"{rotulo.texto!r} ({rotulo.propriedade}) começa em "
                "minúscula. A janela fala com quem joga: comece com "
                "maiúscula.\n"
                "    Se for exceção de verdade, declare em "
                "`EXCECOES_DE_MINUSCULA` com a razão e a data — a E5 da "
                "PALAVRA-01 exige lista explícita, não implícita."
            )

        termo = jargao_em(rotulo.texto)
        if termo is not None and rotulo.texto not in DIVIDA_DA_PALAVRA_01:
            achados.append(
                f"{rotulo.arquivo}:{rotulo.linha}: o rótulo "
                f"{rotulo.texto!r} ({rotulo.propriedade}) contém o jargão "
                f"{termo!r}, aposentado pela E3 da PALAVRA-01.\n"
                f"    Diga {JARGAO_BANIDO[termo]!r}. Quem joga não é "
                "obrigado a saber o que é um daemon."
            )

    presentes = {rotulo.texto for rotulo in rotulos}
    for rotulo_declarado in EXCECOES_DE_MINUSCULA:
        if rotulo_declarado not in presentes:
            achados.append(
                f"{caminho}: a exceção de minúscula {rotulo_declarado!r} não "
                "existe mais nesta tela. APAGUE a entrada de "
                "`EXCECOES_DE_MINUSCULA` — lista de exceção que envelhece "
                "calada vira paisagem."
            )
    for rotulo_declarado in DIVIDA_DA_PALAVRA_01:
        if rotulo_declarado not in presentes:
            achados.append(
                f"{caminho}: a dívida {rotulo_declarado!r} não existe mais "
                "nesta tela — o rótulo foi trocado, e é uma boa notícia. "
                "APAGUE a entrada de `DIVIDA_DA_PALAVRA_01`."
            )

    return achados


def mostrar_criterio() -> None:
    """Imprime o critério, para quem quiser conferir sem ler o código."""
    print("Portão da palavra de tela (PALAVRA-01 / E5)")
    print(f"  arquivo varrido: {GLADE.relative_to(RAIZ)}")
    print(f"  propriedades: {', '.join(sorted(PROPRIEDADES_DE_TELA))}")
    print()
    print("Regra 1 — nenhum rótulo começa em minúscula. Exceções declaradas:")
    for rotulo, razao in EXCECOES_DE_MINUSCULA.items():
        print(f"  {rotulo!r}: {razao}")
    print()
    print("Regra 2 — nenhum rótulo contém jargão aposentado:")
    for termo, vira in JARGAO_BANIDO.items():
        print(f"  {termo!r} -> {vira!r}")
    print()
    print("Dívida declarada da E1-E4 (rótulos que ainda não foram trocados):")
    for rotulo, razao in DIVIDA_DA_PALAVRA_01.items():
        print(f"  {rotulo!r}: {razao}")


def main(argumentos: list[str] | None = None) -> int:
    analisador = argparse.ArgumentParser(
        description="Portão da palavra de tela: reprova minúscula e jargão no .glade.",
    )
    analisador.add_argument("--all", action="store_true", help="varre a interface da árvore")
    analisador.add_argument(
        "--check-file", nargs="+", metavar="CAMINHO", help="varre os arquivos indicados"
    )
    analisador.add_argument(
        "--mostrar-criterio", action="store_true", help="imprime o critério e sai"
    )
    analisador.add_argument("arquivos", nargs="*", help="o mesmo que --check-file")
    opcoes = analisador.parse_args(argumentos)

    if opcoes.mostrar_criterio:
        mostrar_criterio()
        return 0

    alvos = [Path(caminho) for caminho in (opcoes.check_file or []) + opcoes.arquivos]
    if opcoes.all or not alvos:
        alvos = [GLADE]

    achados: list[str] = []
    for alvo in alvos:
        if alvo.suffix != ".glade":
            continue
        achados.extend(conferir(alvo))

    for achado in achados:
        print(achado)
    if achados:
        print()
        print(f"{len(achados)} reprovação(ões) da palavra de tela.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Nenhum NÚMERO DE SÉRIE de aparelho em arquivo versionado.

POR QUE ELE NASCEU, e o pedido é dela — 03/09/2026. Ao ver o serial do controle
dela aparecer numa leitura de ``daemon.state_full``, a pergunta foi *"vale um
portão para número de série?"*, e a resposta foi **sim**.

**NÃO É A PRIMEIRA RÉGUA DE SERIAL, E É PRECISO DIZER ISSO.** Ao escrever este
portão, o teste ``test_docs_mac_anonimato.py::test_nenhum_serial_de_fabrica_real_no_repo``
— que existe desde 15/08/2026 — acusou o valor forjado que este arquivo tinha
acabado de criar. Ele estava lá o tempo todo, e é o AUTORITATIVO.

POR QUE DUAS, ENTÃO, e a razão é a mesma das duas réguas de MAC:

* a AUTORITATIVA mede a forma EXATA de um DualSense (``[A-Z][A-Z0-9]{16}``, com
  dígito nas posições que a fábrica usa) e alcança TRÊS formas de escrita —
  texto, hexdump com o serial atravessando a quebra de linha, e corrida
  hexadecimal colada. Custa ~12 s, e é teste de SUÍTE;
* ESTA mede só texto, mas de 15 a 20 caracteres — o que alcança serial de
  aparelho que **não** é DualSense (8BitDo, Pro Controller) — e custa 1,2 s.

**O QUE ESTA COMPRA É A CAMADA**, e a lição é de hoje: a suíte roda no FIM.
Entre o commit que vaza e a reprovação havia um dia inteiro de trabalho — foi
exatamente assim com os 37 endereços de rádio crus desta manhã, que o portão
autoritativo de MAC acusava e ninguém rodava. Esta reprova antes do commit.

O serial de fábrica identifica a unidade dela **tão bem quanto o MAC**, e a
regra desta casa é sobre ARQUIVO VERSIONADO, não sobre a palavra "MAC" — a
docstring de ``cor_do_plastico.mascarar_serial`` registra que ELA MESMA já foi
escrita com o serial verdadeiro de um controle da bancada.

PELA FORMA, E NUNCA POR LISTA
------------------------------
Listar os seriais reais aqui seria exatamente o vazamento que este portão
existe para impedir — é a mesma razão que ``test_anonimato_de_fixtures`` escreve
para o MAC. Então ele mede a FORMA de um serial de aparelho:

* de 15 a 20 caracteres, MAIÚSCULAS e dígitos, sem separador;
* pelo menos DUAS letras e SEIS dígitos — nem sigla, nem carimbo, nem contador.

Medido nesta árvore em 03/09/2026: **catorze tokens** casam essa forma, e nenhum
é serial real — são os exemplos forjados da própria máscara e endereços de
buffer de um log do Proton, todos marcados com a razão.

A MÁSCARA É A QUE JÁ EXISTE, e não uma nova: ``AB1C05###########`` — os SEIS
primeiros caracteres ficam (modelo e planta, compartilhados por lote, que não
identificam unidade nenhuma) e o resto vira ``#``. O dono dela é
``cor_do_plastico.CARACTERES_PUBLICOS_DO_SERIAL``, e este portão o LÊ em vez de
digitar o número.

COMO ISENTAR, quando o token não é serial de verdade
-----------------------------------------------------
Escreva ``serial-de-mentira`` na MESMA linha, com a razão::

    SERIAL_DO_EXEMPLO = "AB1C05D1234567890"  # serial-de-mentira: forjado, é o
                                             # exemplo da própria máscara

A marca vai na linha do token porque a varredura é por linha — escrita na de
baixo ela não alcança nada. É a mesma convenção do ``endereco-de-mentira`` do
``check_endereco_de_radio.py``.

    scripts/check_numero_de_serie.py          # o portão
    scripts/check_numero_de_serie.py --forma  # o que ele considera serial
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

#: A FORMA DE UM SERIAL DE APARELHO. As bordas negativas impedem que um pedaço
#: de um token maior (um hash de 40, uma chave de API) case por dentro.
SERIAL = re.compile(r"(?<![0-9A-Za-z_#])([0-9A-Z]{15,20})(?![0-9A-Za-z_#])")

#: O MÍNIMO DE CADA CLASSE. Sem os dois, a forma pegaria uma sigla longa
#: (``CONFIGURACAOPADRAO``) e um carimbo de tempo (``20260903150000``) — e um
#: portão que acusa o que não é o defeito é um portão que alguém desliga.
MINIMO_DE_LETRAS = 2
MINIMO_DE_DIGITOS = 6

#: A MARCA DE ISENÇÃO, na mesma linha do token.
ISENTO = re.compile(r"serial-de-mentira")

#: O QUE NÃO SE VARRE. Binário não tem linha, e o histórico é de outra régua.
EXCLUIR_SUFIXO = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".mo", ".gz", ".woff", ".woff2",
    ".pdf", ".zip", ".whl", ".so",
}

#: OS SVG FICAM DENTRO, e é deliberado: em 24/08/2026 um endereço de rádio saiu
#: num `.svg` justamente porque a régua o tratava como binário. A mesma porta
#: serve para um serial.


def _e_endereco_de_memoria(token: str) -> bool:
    """``0000000000C2CEF2`` — o ponteiro de um log, e não um serial.

    DUAS CONDIÇÕES, e as duas juntas: o token usa SÓ o alfabeto hexadecimal (um
    serial de aparelho quase sempre traz letras de fora dele — G, W, N…), **e**
    tem uma fileira de seis zeros ou mais, que é como um endereço de 64 bits
    aparece impresso. Exigir as duas é o que impede a isenção de virar porta
    larga: um serial hexadecimal por acaso, mas sem a fileira de zeros,
    continua sendo acusado.
    """
    # serial-de-mentira: o literal abaixo é o ALFABETO hexadecimal, não um
    # serial — e é o único jeito de escrevê-lo. A ironia é o ponto: o portão
    # acusa a si mesmo se a marca sair.
    so_hex = all(c in "0123456789ABCDEF" for c in token)  # serial-de-mentira
    return so_hex and "000000" in token


def _mascarado(token: str) -> bool:
    """Já mascarado não é vazamento — e a máscara tem dono."""
    return "#" in token


def arquivos_versionados() -> list[Path]:
    """O rastreado E o novo, sem o ignorado — portões são cegos a arquivo novo.

    ``--cached --others --exclude-standard`` é o mesmo par que o portão do MAC
    usa: sem o ``--others``, um arquivo recém-criado e ainda não commitado
    passaria calado, que é exatamente quando o vazamento entra.
    """
    saida = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=str(RAIZ), capture_output=True, text=True, check=False).stdout
    fora = []
    for nome in saida.split("\n"):
        if not nome.strip():
            continue
        p = RAIZ / nome
        if p.suffix.lower() in EXCLUIR_SUFIXO or not p.is_file():
            continue
        fora.append(p)
    return fora


def acusa(caminho: Path) -> list[str]:
    """As linhas deste arquivo que trazem serial de aparelho sem máscara."""
    try:
        texto = caminho.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []
    achados = []
    for n, linha in enumerate(texto.split("\n"), start=1):
        if ISENTO.search(linha):
            continue
        for m in SERIAL.finditer(linha):
            token = m.group(1)
            letras = sum(c.isalpha() for c in token)
            digitos = sum(c.isdigit() for c in token)
            if letras < MINIMO_DE_LETRAS or digitos < MINIMO_DE_DIGITOS:
                continue
            if _mascarado(token) or _e_endereco_de_memoria(token):
                continue
            # O CAMINHO RELATIVO É UMA CORTESIA, e não um requisito: quem
            # chama `acusa` com um arquivo de fora da árvore (uma régua que o
            # exercita num lar de mentira) não pode receber um `ValueError` no
            # lugar do achado.
            try:
                rel = caminho.relative_to(RAIZ).as_posix()
            except ValueError:
                rel = caminho.as_posix()
            achados.append(f"{rel}:{n}: {token[:6]}{'…' * 1} ({len(token)} caracteres)")
    return achados


def _mascara_de_exemplo() -> str:
    """A máscara, PERGUNTADA ao dono — nunca digitada aqui.

    Digitar `AB1C05###########` nesta mensagem faria duas verdades sobre a mesma
    regra, e a daqui envelheceria no dia em que ela mudasse o número de
    caracteres públicos.
    """
    sys.path.insert(0, str(RAIZ / "scripts/ensaios"))
    try:
        from cor_do_plastico import mascarar_serial
    except Exception:
        return "os SEIS primeiros ficam, o resto vira `#`"
    return mascarar_serial("AB1C05D1234567890")  # serial-de-mentira: prefixo forjado


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--forma", action="store_true",
                   help="imprime o que este portão considera um serial e sai")
    args = p.parse_args()

    if args.forma:
        print("a forma de um serial de aparelho, para este portão:")
        print(f"  {SERIAL.pattern}")
        print(f"  com pelo menos {MINIMO_DE_LETRAS} letra(s) e "
              f"{MINIMO_DE_DIGITOS} dígito(s)")
        print(f"  a máscara: {_mascara_de_exemplo()}")
        print("  isenta-se com `serial-de-mentira` na MESMA linha, com a razão")
        return 0

    violacoes: list[str] = []
    for caminho in arquivos_versionados():
        violacoes.extend(acusa(caminho))

    if not violacoes:
        print("OK: nenhum número de série de aparelho em arquivo versionado.")
        return 0

    print(f"{len(violacoes)} número(s) de série de aparelho SEM MÁSCARA:")
    for v in violacoes:
        print(f"  {v}")
    print()
    print("O serial de fábrica identifica a unidade dela tão bem quanto o MAC,")
    print("e a regra desta casa é sobre ARQUIVO VERSIONADO — não sobre a")
    print("palavra 'MAC'. A máscara já tem dono:")
    print(f"  {_mascara_de_exemplo()}")
    print("  (`cor_do_plastico.mascarar_serial`, seis caracteres públicos)")
    print()
    print("Se o token NÃO é serial de aparelho, escreva `serial-de-mentira` na")
    print("MESMA linha, com a razão. Isenção sem razão é ponto cego com nome")
    print("bonito — e a marca na linha de baixo não alcança nada.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

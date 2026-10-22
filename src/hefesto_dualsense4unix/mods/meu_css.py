"""O CSS de quem usa: a folha que a pessoa escreve e o Hefesto põe POR CIMA do tema.

Livre (layout e cor), lida do ``<dados>/<id>/meu.css`` da extensão de tema que declara uma opção
``css``. Livre não é aberta: nada busca arquivo nem endereço, nada escapa, e passar de 16 KB não
entra. O recusado não se aplica, e a frase diz a linha. O WebKit só deixa a folha de usuário vencer
a da página com ``!important``: cada declaração sai daqui com ele (menos em ``@keyframes``).
"""
from __future__ import annotations

import re
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any

NOME_DO_ARQUIVO = "meu.css"
#: O mesmo teto do tema.
TAMANHO_MAXIMO = 16 * 1024

#: As regras que se aplicam: as que agrupam regras (``@media``, ``@supports``) e os quadros.
_AGRUPAM = frozenset({"media", "supports"})  # (noqa-acento) nomes de at-rule do CSS
_QUADROS = frozenset({"keyframes", "-webkit-keyframes"})

#: O que o CSS de quem usa nunca pode ter, com a frase de cada um (a linha vem na frente).
_PROIBIDOS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"url\s*\(", re.I), "usa url(), e nada busca arquivo nem endereço"),
    (re.compile(r"@import", re.I), "usa @import, e nada busca arquivo nem endereço"),
    (re.compile(r"(?<![\w-])(?:-webkit-)?(?:image-set|cross-fade|image|src)\s*\(", re.I),
     "usa uma função de imagem, e nada busca arquivo nem endereço"),
    (re.compile(r"expression\s*\(", re.I), "usa expression(), que não roda aqui"),
    (re.compile(r"\\"), "tem uma barra invertida, que não vale aqui"),
    (re.compile(r"<"), "tem um «<», que não vale aqui"),
)
_NAO_LEU = "O seu CSS não foi aplicado: o arquivo não pôde ser lido."
_IMPORTANTE = re.compile(r"\s*!\s*important\s*$", re.I)
_ARROBA = re.compile(r"@([\w-]+)")


class CssRecusadoError(ValueError):
    """O CSS não serve; ``frase`` é a linha que a pessoa lê, com a linha do arquivo."""

    def __init__(self, motivo: str) -> None:
        self.frase = f"O seu CSS não foi aplicado: {motivo}"
        super().__init__(self.frase)


@dataclass(frozen=True)
class FolhaDeQuemUsa:
    """O ``meu.css`` lido: a ``folha`` que se aplica, ou a ``recusa`` que a aba diz."""

    folha: str = ""
    recusa: str = ""


EXEMPLO = """\
/* O meu CSS. O Hefesto aplica este arquivo por cima do tema assim que você salva, sem reabrir a
   janela. Vale cor e layout. Não vale url(), @import, funções de imagem, barra invertida nem «<»;
   passando de 16 KB, ou errando uma chave, o arquivo inteiro fica sem valer e a aba diz a linha.

   Para testar, tire o comentário destas duas regras:

:root { --green: #1d7a3c; }
.quadro { border-radius: 2px; }
*/
"""


def caminho(mod_id: str, lugares: Any) -> Path:
    return Path(lugares.dados) / mod_id / NOME_DO_ARQUIVO


def garantir(mod_id: str, lugares: Any) -> Path:
    """O arquivo da pessoa, criado com o exemplo comentado se ainda não existe (nunca reescreve)."""
    alvo = caminho(mod_id, lugares)
    alvo.parent.mkdir(parents=True, exist_ok=True)
    try:
        with alvo.open("x", encoding="utf-8") as arquivo:
            arquivo.write(EXEMPLO)
    except FileExistsError:
        return alvo
    return alvo


def _sem_comentario(texto: str) -> str:
    """O texto com os comentários trocados por espaço (as quebras ficam, e a linha não anda).

    Um «/*» dentro de uma cadeia não abre comentário: quem o trata como abertura esconderia o que
    vem depois, e o WebKit leria esse resto como CSS. A cadeia acaba na aspa ou na quebra de linha.
    """
    saida: list[str] = []
    i, n = 0, len(texto)
    while i < n:
        c = texto[i]
        if c in "\"'":
            j = i + 1
            while j < n and texto[j] != c and texto[j] != "\n":
                j += 1
            saida.append(texto[i:j + 1])
            i = j + 1
        elif texto.startswith("/*", i):
            fim = texto.find("*/", i + 2)
            fim = n if fim < 0 else fim + 2
            saida.append("".join(x if x == "\n" else " " for x in texto[i:fim]))
            i = fim
        else:
            saida.append(c)
            i += 1
    return "".join(saida)


class _Leitor:
    """Reescreve o CSS já sem comentário, declaração a declaração, e acusa a linha que não serve."""

    def __init__(self, limpo: str) -> None:
        self.t = limpo

    def linha(self, indice: int) -> int:
        return self.t.count("\n", 0, indice) + 1

    def recusar(self, indice: int, motivo: str) -> CssRecusadoError:
        return CssRecusadoError(f"a linha {self.linha(indice)} {motivo}.")

    def _fecha(self, abre: int) -> int:
        """O índice do «}» que fecha o «{» em ``abre`` (cadeias e parênteses respeitados)."""
        fundo, i, n = 0, abre, len(self.t)
        while i < n:
            c = self.t[i]
            if c in "\"'":
                j = i + 1
                while j < n and self.t[j] != c and self.t[j] != "\n":
                    j += 1
                i = j
            elif c == "{":
                fundo += 1
            elif c == "}":
                fundo -= 1
                if fundo == 0:
                    return i
            i += 1
        raise self.recusar(abre, "abre uma chave que nunca fecha")

    def reescrever(self, ini: int, fim: int, modo: str) -> str:
        """``modo``: ``regras`` (folha, ``@media``), ``declaracoes`` (dentro de uma regra) ou
        ``quadros`` (dentro de ``@keyframes``: as regras são quadros, sem ``!important``)."""
        saida: list[str] = []
        inicio, i, parenteses = ini, ini, 0
        while i < fim:
            c = self.t[i]
            if c in "\"'":
                j = i + 1
                while j < fim and self.t[j] != c and self.t[j] != "\n":
                    j += 1
                i = j + 1
                continue
            if c == "(":
                parenteses += 1
            elif c == ")":
                parenteses = max(0, parenteses - 1)
            elif parenteses == 0 and c == "}":
                raise self.recusar(i, "tem uma chave que fecha sem ter aberto")
            elif parenteses == 0 and c == ";":
                saida.append(self._declaracao(inicio, i, modo))
                inicio = i + 1
            elif parenteses == 0 and c == "{":
                fecha = self._fecha(i)
                saida.append(self._regra(inicio, i, fecha, modo))
                inicio, i = fecha + 1, fecha
            i += 1
        saida.append(self._declaracao(inicio, fim, modo))
        return "".join(saida)

    def _regra(self, inicio: int, abre: int, fecha: int, modo: str) -> str:
        bruto = self.t[inicio:abre]
        cabeca = bruto.strip()
        onde = inicio + len(bruto) - len(bruto.lstrip())
        if not cabeca:
            raise self.recusar(abre, "tem uma chave sem seletor antes")
        interno = "quadros-declaracoes" if modo == "quadros" else "declaracoes"
        achado = _ARROBA.match(cabeca)
        if achado is not None:
            nome = achado.group(1).lower()
            if nome in _QUADROS:
                interno = "quadros"
            elif nome in _AGRUPAM:
                interno = "regras" if modo == "regras" else "declaracoes"
            else:
                raise self.recusar(onde, f"usa @{nome}, que o Hefesto não aplica")
        return f"{cabeca}{{{self.reescrever(abre + 1, fecha, interno)}}}"

    def _declaracao(self, inicio: int, fim: int, modo: str) -> str:
        bruto = self.t[inicio:fim]
        texto = bruto.strip()
        if not texto:
            return ""
        onde = inicio + len(bruto) - len(bruto.lstrip())
        if modo in ("regras", "quadros"):
            raise self.recusar(onde, f"tem «{texto[:30]}», e fora de uma regra só cabem regras "
                                     "com chaves")
        nome, dois_pontos, valor = texto.partition(":")
        if not dois_pontos or not nome.strip() or not valor.strip():
            raise self.recusar(onde, f"tem «{texto[:30]}», que não é uma declaração (nome: valor)")
        valor = _IMPORTANTE.sub("", valor).strip()
        marca = "" if modo == "quadros-declaracoes" else " !important"
        return f"{nome.strip()}:{valor}{marca};"


def aplicar(texto: str) -> str:
    """A folha pronta para o WebKit, ou :class:`CssRecusadoError` com a linha que não serve.

    Vazio (ou só comentário) é uma folha vazia, não uma recusa.
    """
    if len(texto.encode("utf-8")) > TAMANHO_MAXIMO:
        raise CssRecusadoError("passa de 16 KB.")
    limpo = _sem_comentario(texto)
    for padrao, motivo in _PROIBIDOS:
        achado = padrao.search(limpo)
        if achado is not None:
            linha = limpo.count("\n", 0, achado.start()) + 1
            raise CssRecusadoError(f"a linha {linha} {motivo}.")
    if not limpo.strip():
        return ""
    return _Leitor(limpo).reescrever(0, len(limpo), "regras")


def ler(mod_id: str, lugares: Any) -> FolhaDeQuemUsa:
    """A folha do ``meu.css`` da extensão: vazia sem arquivo; a recusa dita quando ele não serve.

    Só lê arquivo comum e pequeno: um atalho para um dispositivo ou para uma fila não trava a
    janela. Nada aqui escreve.
    """
    alvo = caminho(mod_id, lugares)
    try:
        modo = alvo.stat()
    except FileNotFoundError:
        return FolhaDeQuemUsa()
    except OSError:
        return FolhaDeQuemUsa(recusa=_NAO_LEU)
    if not stat.S_ISREG(modo.st_mode):
        return FolhaDeQuemUsa(recusa=CssRecusadoError("precisa ser um arquivo comum.").frase)
    if modo.st_size > TAMANHO_MAXIMO:
        return FolhaDeQuemUsa(recusa=CssRecusadoError("passa de 16 KB.").frase)
    try:
        texto = alvo.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return FolhaDeQuemUsa(recusa=_NAO_LEU)
    try:
        return FolhaDeQuemUsa(folha=aplicar(texto))
    except CssRecusadoError as exc:
        return FolhaDeQuemUsa(recusa=exc.frase)


__all__ = ["EXEMPLO", "NOME_DO_ARQUIVO", "TAMANHO_MAXIMO", "CssRecusadoError", "FolhaDeQuemUsa",
           "aplicar", "caminho", "garantir", "ler"]

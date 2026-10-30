"""Os arquivos que quem usa importa numa opção ``importar`` de uma extensão de tema.

O arquivo é dado da pessoa: entra só depois da régua, e a cópia mora em
``<dados>/<id>/<opção>.importado``. O tema importado passa pela mesma régua do tema do pacote
(:func:`tema.validar`, só cores e com contraste) e se grava já reescrito por ela. A logo é PNG, JPEG
ou WebP, conferida pelos bytes, até 256 KB e até 1024 px de lado; SVG nunca, porque roda código.
O valor da opção é o nome do arquivo de origem, só para a tela; vazio é «nada importado».
"""
from __future__ import annotations

import base64
import contextlib
import os
import stat
import struct
import tempfile
from pathlib import Path
from typing import Any

from hefesto_dualsense4unix.mods import meu_css, tema
from hefesto_dualsense4unix.mods.instalador import InstalacaoRecusadaError

SUFIXO = ".importado"
TAMANHO_DA_LOGO = 256 * 1024
LADO_MAXIMO_DA_LOGO = 1024
LADO_MINIMO_DA_LOGO = 16
TAMANHO_DO_NOME = 60
TAMANHO_POR_FORMATO = {"tema": tema.TAMANHO_MAXIMO, "logo": TAMANHO_DA_LOGO,
                       "css": meu_css.TAMANHO_MAXIMO}


def caminho(mod_id: str, opcao_id: str, lugares: Any) -> Path:
    return Path(lugares.dados) / mod_id / f"{opcao_id}{SUFIXO}"


def _ler_pequeno(alvo: Path, teto: int) -> bytes:
    """Os bytes de um arquivo comum até ``teto``; o resto é a recusa dita."""
    try:
        modo = alvo.stat()
    except OSError:
        raise InstalacaoRecusadaError("O arquivo não pôde ser lido.") from None
    if not stat.S_ISREG(modo.st_mode):
        raise InstalacaoRecusadaError("Escolha um arquivo comum.")
    if modo.st_size > teto:
        raise InstalacaoRecusadaError(f"O arquivo passa de {teto // 1024} KB.")
    try:
        with alvo.open("rb") as arquivo:
            dados = arquivo.read(teto + 1)
    except OSError:
        raise InstalacaoRecusadaError("O arquivo não pôde ser lido.") from None
    if len(dados) > teto:
        raise InstalacaoRecusadaError(f"O arquivo passa de {teto // 1024} KB.")
    return dados


def _medidas_do_jpeg(dados: bytes) -> tuple[int, int] | None:
    i = 2
    while i + 9 < len(dados):
        if dados[i] != 0xFF:
            return None
        marca = dados[i + 1]
        if marca in (0xD8, 0x01) or 0xD0 <= marca <= 0xD7:
            i += 2
            continue
        tamanho = struct.unpack(">H", dados[i + 2:i + 4])[0]
        if 0xC0 <= marca <= 0xCF and marca not in (0xC4, 0xC8, 0xCC):
            altura, largura = struct.unpack(">HH", dados[i + 5:i + 9])
            return largura, altura
        i += 2 + tamanho
    return None


def _medidas_do_webp(dados: bytes) -> tuple[int, int] | None:
    pedaco = dados[12:16]
    if pedaco == b"VP8 " and len(dados) >= 30 and dados[23:26] == b"\x9d\x01\x2a":
        largura, altura = struct.unpack("<HH", dados[26:30])
        return largura & 0x3FFF, altura & 0x3FFF
    if pedaco == b"VP8L" and len(dados) >= 25 and dados[20] == 0x2F:
        bits = int.from_bytes(dados[21:25], "little")
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    if pedaco == b"VP8X" and len(dados) >= 30:
        return (int.from_bytes(dados[24:27], "little") + 1,
                int.from_bytes(dados[27:30], "little") + 1)
    return None


def imagem(dados: bytes) -> tuple[str, int, int] | None:
    """``(tipo mime, largura, altura)`` de um PNG, JPEG ou WebP conferido pelos bytes, ou
    ``None`` para qualquer outra coisa."""
    medidas: tuple[int, int] | None = None
    if dados[:8] == b"\x89PNG\r\n\x1a\n" and dados[12:16] == b"IHDR" and len(dados) >= 24:
        mime, medidas = "image/png", struct.unpack(">II", dados[16:24])
    elif dados[:3] == b"\xff\xd8\xff":
        mime, medidas = "image/jpeg", _medidas_do_jpeg(dados)
    elif dados[:4] == b"RIFF" and dados[8:12] == b"WEBP":
        mime, medidas = "image/webp", _medidas_do_webp(dados)
    if medidas is None:
        return None
    return mime, medidas[0], medidas[1]


def logo_valida(dados: bytes) -> str:
    """O tipo mime da logo que passa na régua, ou a recusa dita em uma frase."""
    if len(dados) > TAMANHO_DA_LOGO:
        raise InstalacaoRecusadaError(f"A logo passa de {TAMANHO_DA_LOGO // 1024} KB.")
    achada = imagem(dados)
    if achada is None:
        raise InstalacaoRecusadaError("A logo precisa ser PNG, JPEG ou WebP.")
    mime, largura, altura = achada
    if not (LADO_MINIMO_DA_LOGO <= largura <= LADO_MAXIMO_DA_LOGO
            and LADO_MINIMO_DA_LOGO <= altura <= LADO_MAXIMO_DA_LOGO):
        raise InstalacaoRecusadaError(
            f"A logo tem {largura} por {altura} px; vale de {LADO_MINIMO_DA_LOGO} a "
            f"{LADO_MAXIMO_DA_LOGO} px de lado.")
    return mime


def tema_valido(dados: bytes) -> str:
    """A folha do tema importado já reescrita pela régua, ou a recusa dita."""
    try:
        texto = dados.decode("utf-8")
    except UnicodeDecodeError:
        raise InstalacaoRecusadaError("O tema precisa ser um arquivo de texto (UTF-8).") from None
    try:
        return tema.validar(texto).folha
    except tema.TemaRecusadoError as exc:
        raise InstalacaoRecusadaError(exc.frase) from None


def css_valido(dados: bytes) -> str:
    """O CSS importado como veio (o ``meu.css`` guarda o texto da pessoa), se passa na régua."""
    try:
        texto = dados.decode("utf-8")
    except UnicodeDecodeError:
        raise InstalacaoRecusadaError("O CSS precisa ser um arquivo de texto (UTF-8).") from None
    try:
        meu_css.aplicar(texto)
    except meu_css.CssRecusadoError as exc:
        raise InstalacaoRecusadaError(exc.frase) from None
    return texto


def _gravar(destino: Path, dados: bytes) -> None:
    """Arquivo novo e ``rename``, em ``0600``: o vigia da janela nunca lê a cópia pela metade."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    fd, nome = tempfile.mkstemp(prefix=".importando-", dir=destino.parent)
    try:
        with os.fdopen(fd, "wb") as arquivo:
            arquivo.write(dados)
        os.chmod(nome, 0o600)
        os.replace(nome, destino)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(nome)
        raise


def nome_para_a_tela(origem: Path) -> str:
    """O nome do arquivo de origem, sem caractere de controle e cortado para caber na linha."""
    limpo = "".join(c for c in origem.name if c.isprintable()).strip()
    return (limpo or "Importado")[:TAMANHO_DO_NOME]


def importar(manifesto: Any, opcao_id: str, origem: Path, lugares: Any) -> str:
    """Confere o arquivo de ``origem`` pela régua do formato da opção, grava a cópia e guarda o
    nome dele na opção. A opção ``css`` importa para o ``meu.css``. Devolve o nome guardado."""
    from hefesto_dualsense4unix.mods import opcoes

    opcao = next((o for o in manifesto.opcoes if o.id == opcao_id), None)
    if opcao is None or opcao.tipo not in ("importar", "css"):
        raise InstalacaoRecusadaError(f"«{manifesto.nome}» não importa em «{opcao_id}».")
    formato = "css" if opcao.tipo == "css" else str(opcao.formato)
    dados = _ler_pequeno(origem, TAMANHO_POR_FORMATO[formato])
    if formato == "css":
        _gravar(meu_css.caminho(manifesto.id, lugares), css_valido(dados).encode("utf-8"))
        opcoes.guardar(manifesto, opcao_id, True, lugares)
        return nome_para_a_tela(origem)
    if formato == "tema":
        dados = tema_valido(dados).encode("utf-8")
    else:
        logo_valida(dados)
    _gravar(caminho(manifesto.id, opcao_id, lugares), dados)
    nome = nome_para_a_tela(origem)
    opcoes.guardar(manifesto, opcao_id, nome, lugares)
    return nome


def tirar(manifesto: Any, opcao_id: str, lugares: Any) -> None:
    """Apaga a cópia importada e deixa a opção vazia."""
    from hefesto_dualsense4unix.mods import opcoes

    opcao = next((o for o in manifesto.opcoes if o.id == opcao_id), None)
    if opcao is None or opcao.tipo != "importar":
        raise InstalacaoRecusadaError(f"«{manifesto.nome}» não importa em «{opcao_id}».")
    with contextlib.suppress(FileNotFoundError):
        caminho(manifesto.id, opcao_id, lugares).unlink()
    opcoes.guardar(manifesto, opcao_id, "", lugares)


def _copia(mod_id: str, opcao_id: str, lugares: Any, teto: int) -> bytes | None:
    try:
        return _ler_pequeno(caminho(mod_id, opcao_id, lugares), teto)
    except InstalacaoRecusadaError:
        return None


def ler_o_tema(mod_id: str, opcao_id: str, lugares: Any) -> str:
    """A folha do tema importado (vazia sem cópia). Quem a aplica passa de novo pela régua."""
    dados = _copia(mod_id, opcao_id, lugares, tema.TAMANHO_MAXIMO)
    if dados is None:
        return ""
    try:
        return dados.decode("utf-8")
    except UnicodeDecodeError:
        return ""


def css_da_logo(mod_id: str, opcao_id: str, lugares: Any) -> str:
    """A folha que troca a logo do canto pela importada, montada só de bytes que passam de novo
    pela régua (a cópia pode ter sido trocada à mão); vazia sem logo que sirva."""
    dados = _copia(mod_id, opcao_id, lugares, TAMANHO_DA_LOGO)
    if dados is None:
        return ""
    try:
        mime = logo_valida(dados)
    except InstalacaoRecusadaError:
        return ""
    url = f"data:{mime};base64,{base64.b64encode(dados).decode('ascii')}"
    return (f'.logo{{background-image:url("{url}") !important;background-size:cover !important;'
            "background-position:center !important;background-repeat:no-repeat !important}"
            ".logo svg{visibility:hidden !important}")


__all__ = ["LADO_MAXIMO_DA_LOGO", "SUFIXO", "TAMANHO_DA_LOGO", "caminho", "css_da_logo",
           "css_valido", "imagem", "importar", "ler_o_tema", "logo_valida", "nome_para_a_tela",
           "tema_valido", "tirar"]

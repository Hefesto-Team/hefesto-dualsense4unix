"""Os filtros que a Wiki gerada atravessa antes de subir.

Cada filtro é um portão que a casa já tem, aplicado ao TEXTO GERADO (nunca à fonte): o texto
público, os endereços de rádio e o rastro de autoria. A página que reprova não sobe, e a fonte
é corrigida. Nenhuma mensagem imprime o termo nem a linha que casou: o log do CI é público.

Um filtro que não consegue medir (a lista de termos não chegou) não dá «limpo»: dá `nao_medido`,
e a geração para.
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType

SCRIPTS = Path(__file__).resolve().parent.parent


def carregar(nome: str) -> ModuleType:
    """Um portão da casa, lido de `scripts/`, pelo nome do arquivo."""
    alvo = SCRIPTS / f"{nome}.py"
    spec = importlib.util.spec_from_file_location(f"_wiki_{nome}", alvo)
    if spec is None or spec.loader is None:  # pragma: no cover
        raise ImportError(str(alvo))
    modulo = importlib.util.module_from_spec(spec)
    # O portão pode ter `@dataclass` (que procura o módulo em `sys.modules`) e irmãos em `scripts/`.
    sys.modules[spec.name] = modulo
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec.loader.exec_module(modulo)
    return modulo


@dataclass
class Veredito:
    """O que os filtros acharam: por página, e o que ficou sem medir."""

    seguradas: dict[str, list[str]] = field(default_factory=dict)
    nao_medido: list[str] = field(default_factory=list)

    def segura(self, pagina: str, motivo: str) -> None:
        self.seguradas.setdefault(pagina, []).append(motivo)


def _linhas(texto: str) -> list[tuple[int, str]]:
    return list(enumerate(texto.splitlines(), 1))


def texto_publico(paginas: dict[str, str], veredito: Veredito) -> None:
    """O vocabulário de quem constrói não chega a quem usa (`check_texto_publico`)."""
    expressoes = carregar("check_texto_publico").EXPRESSOES
    for nome, texto in paginas.items():
        for numero, linha in _linhas(texto):
            for expressao, padrao in expressoes:
                if padrao.search(linha):
                    veredito.segura(nome, f"{nome}:{numero}: texto público [{expressao}]")


def endereco_de_radio(paginas: dict[str, str], veredito: Veredito) -> None:
    """Nenhum endereço de rádio real, nas formas que o portão de forma reconhece."""
    portao = carregar("check_endereco_de_radio")
    for nome, texto in paginas.items():
        for numero, linha in _linhas(texto):
            if portao.ISENCAO.search(linha):
                continue
            for rotulo, achou in (
                ("MAC real", portao.acusa_mac(linha)),
                ("serial USB", portao.acusa_serial(linha)),
                ("nó de som", portao.acusa_no(linha)),
            ):
                if achou:
                    veredito.segura(nome, f"{nome}:{numero}: endereço [{rotulo}]")


def endereco_da_maquina(paginas: dict[str, str], veredito: Veredito, lar: Path | None) -> None:
    """Os pedaços escondidos dos endereços DESTA máquina, em toda forma (pergunta ao dono).

    `lar` desvia a pergunta para um lar de mentira (sem `bluetoothctl`); no CI a máquina não
    tem endereço real e a régua diz «não medido» sem reprovar, que é o desenho dela.
    """
    portao = carregar("check_o_endereco_dela_em_toda_forma")
    reais = portao.enderecos_da_maquina(lar)
    if not reais:
        return
    padroes = portao.padrao_das_janelas(reais)
    coladas = portao.janelas_coladas(reais)
    virtuais = portao.pedacos_dos_virtuais(portao.virtuais_da_maquina(reais))
    with tempfile.TemporaryDirectory(prefix="wiki-") as pasta:
        for nome, texto in paginas.items():
            arquivo = Path(pasta) / f"{nome}.md"
            arquivo.write_text(texto, encoding="utf-8")
            for achado in portao.varrer([arquivo], padroes, coladas, virtuais):
                numero = achado.split(":")[1]
                veredito.segura(nome, f"{nome}:{numero}: endereço da máquina [pedaço]")


def rastro(paginas: dict[str, str], veredito: Veredito) -> None:
    """Os termos que não se publicam, da lista de fora do repositório (`check_autoria`)."""
    autoria = carregar("check_autoria")
    lista = autoria._lista()
    if lista is None:
        veredito.nao_medido.append(
            "rastro: a lista de termos não chegou (AUTORIA_VEDADOS ou `git config autoria.vedados`)"
        )
        return
    if lista.invalidas:
        veredito.nao_medido.append("rastro: linhas da lista que não se leem")
        return
    for nome, texto in paginas.items():
        if not lista.pode_ter_termo(texto) and not lista.vedado(nome, 1):
            continue
        for numero, linha in _linhas(texto):
            if lista.vedado(linha, 1):
                veredito.segura(nome, f"{nome}:{numero}: rastro [termo da lista]")


def medir(paginas: dict[str, str], *, lar: Path | None = None) -> Veredito:
    """Todos os filtros sobre as páginas geradas (nome da página → texto)."""
    veredito = Veredito()
    texto_publico(paginas, veredito)
    endereco_de_radio(paginas, veredito)
    endereco_da_maquina(paginas, veredito, lar)
    rastro(paginas, veredito)
    return veredito


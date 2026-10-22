"""O Hefesto é para toda idade: o adulto mora na extensão, em repositório próprio.

Os acessórios Lovense, o servidor Buttplug e o reconhecimento do kit que o jogo traz saíram do
produto em 19/10/2026 para a extensão ``intiface`` (``Hefesto-Team/hefesto-mod-intiface``); a do
KytyPS5 é a ``kytyps5``. No Hefesto ficam a porta neutra (a vibração de cada controle, o pedido
para vibrar um, o ``jogo.acessorio`` de uma extensão a outra) e a janela genérica que desenha o
manifesto de qualquer extensão. A marca «Adulto» dos perfis segue na aba Perfis: é o estilo do
jogo que a pessoa escolhe, não um acessório.

A régua lê o ``src/`` inteiro (menos o publicado, que segue o mockup pelo ``--publicar`` do
fecho) e o desenho da 07. MORDIDAS (executadas aqui): a janela da Lovense devolvida à pasta da
Experimental e a palavra «Adulto» fora da lista do estilo reprovam cada uma o seu caso.
"""
from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SRC = RAIZ / "src" / "hefesto_dualsense4unix"
MOCKUP_07 = RAIZ / "mockup" / "07-lancadores.html"
#: O publicado segue o mockup pelo ``--publicar`` do fecho, e não se edita à mão.
_FORA = ("interface/paginas/",)
_SUFIXOS = {".py", ".json", ".html", ".css", ".js", ".sh", ".csv", ".svg"}
#: O que é da extensão e nunca mora no produto, em lugar nenhum.
DA_EXTENSAO = re.compile(r"lovense|buttplug|intiface|brinquedo", re.I)
ADULTO = re.compile(r"adulto", re.I)
#: Onde «Adulto» é o estilo do perfil (a aba Perfis e quem a lê). O ``manifesto.py``
#: nomeia o estilo no texto da permissão ``luz.pulso``, que só vale nos perfis com ele, e o
#: ``formas_de_haptica.py`` o põe entre os estilos que tocam o rumble sem timbre.
DO_ESTILO = frozenset({
    "profiles/estilos_de_jogo.py", "profiles/loader.py",
    "profiles/schema.py", "interface/aba10.py", "mods/manifesto.py",
    "daemon/subsystems/volta_dos_acessorios.py",
    "profiles/formas_de_haptica.py",
})


def _arquivos(raiz: Path) -> dict[str, str]:
    return {p.relative_to(raiz).as_posix(): p.read_text(encoding="utf-8", errors="replace")
            for p in sorted(raiz.rglob("*")) if p.is_file() and p.suffix in _SUFIXOS
            and not any(f in p.relative_to(raiz).as_posix() for f in _FORA)}


def _o_que_e_da_extensao(arquivos: dict[str, str]) -> list[str]:
    return [f"{nome}:{n}: {linha.strip()[:80]}" for nome, texto in arquivos.items()
            for n, linha in enumerate(texto.splitlines(), 1) if DA_EXTENSAO.search(linha)]


def _adulto_fora_do_estilo(arquivos: dict[str, str]) -> list[str]:
    return [f"{nome}:{n}" for nome, texto in arquivos.items() if nome not in DO_ESTILO
            for n, linha in enumerate(texto.splitlines(), 1) if ADULTO.search(linha)]


def test_nada_do_adulto_mora_no_produto_nem_no_desenho_da_07() -> None:
    """D-1910-O-HEFESTO-E-PARA-TODA-IDADE-E-O-ADULTO-MORA-NA-EXTENSAO."""
    arquivos = _arquivos(SRC)
    arquivos["mockup/07-lancadores.html"] = MOCKUP_07.read_text(encoding="utf-8")
    assert _o_que_e_da_extensao(arquivos) == []
    assert _adulto_fora_do_estilo(arquivos) == []


def test_as_janelas_dos_acessorios_e_os_kits_sairam_do_disco() -> None:
    experimental = SRC / "interface" / "experimental"
    for nome in ("lovense.html", "kyty.html", "buttplug.html", "acessorios.html"):
        assert not (experimental / nome).exists(), nome
    assert not (SRC / "integrations" / "kits_de_brinquedo.py").exists()
    assert not (RAIZ / "docs" / "data" / "kits-de-brinquedo.csv").exists()


def test_a_regua_morde_a_janela_da_lovense_devolvida(tmp_path: Path) -> None:
    pasta = tmp_path / "interface" / "experimental"
    pasta.mkdir(parents=True)
    (pasta / "lovense.html").write_text(
        '<div class="tela-nova" id="lovense"><span class="tn-tit">Lovense</span></div>',
        encoding="utf-8")
    assert _o_que_e_da_extensao(_arquivos(tmp_path)) == [
        "interface/experimental/lovense.html:1: "
        '<div class="tela-nova" id="lovense"><span class="tn-tit">Lovense</span></div>']


def test_a_regua_morde_o_adulto_fora_da_lista_do_estilo(tmp_path: Path) -> None:
    (tmp_path / "interface").mkdir()
    (tmp_path / "interface" / "aba07.py").write_text('ROTULO = "Só para adultos"\n',
                                                    encoding="utf-8")
    (tmp_path / "profiles").mkdir()
    (tmp_path / "profiles" / "estilos_de_jogo.py").write_text('ADULTO = "adulto"\n',
                                                            encoding="utf-8")
    assert _adulto_fora_do_estilo(_arquivos(tmp_path)) == ["interface/aba07.py:1"]


def test_o_publicado_fica_fora_so_ate_o_publicar() -> None:
    """O publicado é do fecho: a régua o deixa de fora, e só ele."""
    lidos = _arquivos(SRC)
    assert lidos and not any(n.startswith("interface/paginas/") for n in lidos)
    assert "interface/desenho_da_experimental.py" in lidos and "mods/porta.py" in lidos

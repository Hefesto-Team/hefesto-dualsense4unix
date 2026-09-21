"""O-VULKAN-VE-TODO-LANCADOR-E-DIZ-O-ESTADO-01 — as duas perguntas dela.

> *"Tá mas o botão vulcan ele identifica todos os jogos que contenham isso? E
> vamos ter o estado de ativado e desativado sobre o funcionamento dele? Pra
> todos os jogos?"* — 21/09/2026

A medição respondeu *quase* à primeira (Steam e Heroic sim, Lutris não) e *não*
à segunda (o estado existia em disco e nunca chegava à tela). As duas entregas
desta sprint são as duas metades dessa resposta.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import camadas_vulkan as cv
from hefesto_dualsense4unix.interface.pacotes.a09_sistema import (
    SELO_INFORMATIVO,
    linha_da_sobreposicao_vulkan,
)

# ---------------------------------------------------------------------------
# E1 — a varredura por FORMA alcança o Lutris (e quem vier depois)
# ---------------------------------------------------------------------------


def _prefixo(raiz: Path, *partes: str) -> Path:
    alvo = raiz.joinpath(*partes)
    (alvo / "pfx").mkdir(parents=True)
    (alvo / "pfx" / "system.reg").write_text("", encoding="utf-8")
    return alvo


def test_o_prefixo_do_lutris_entra_na_varredura(tmp_path: Path) -> None:
    """ARRANQUE a varredura por forma e este teste reprova.

    Um jogo instalado pelo Lutris ficaria invisível para o botão, e o sintoma
    seria o de sempre nesta casa: a AUSÊNCIA de dado, que se lê como
    "funcionou". Medido em 21/09: ela tem o Lutris instalado e sem nenhum
    prefixo — este teste é a trava para o primeiro que nascer.
    """
    nativo = _prefixo(tmp_path, ".local", "share", "lutris", "Um Jogo")
    flatpak = _prefixo(
        tmp_path, ".var", "app", "net.lutris.Lutris", "data", "lutris", "Outro")
    padrao = _prefixo(tmp_path, "Games", "Jogo na Raiz")
    achados = set(cv.prefixos_dos_lancadores(tmp_path))
    assert {nativo, flatpak, padrao} <= achados, (
        f"a varredura achou {achados} — faltou "
        f"{ {nativo, flatpak, padrao} - achados}")


def test_pasta_sem_pfx_nao_vira_prefixo(tmp_path: Path) -> None:
    """ARRANQUE o `is_file()` do `system.reg` e este teste reprova: metade de
    `~/Games` viraria prefixo, e o censo leria `system.reg` inexistente em cada
    um."""
    (tmp_path / "Games" / "uma pasta qualquer").mkdir(parents=True)
    (tmp_path / "Games" / "um arquivo solto.txt").write_text("", encoding="utf-8")
    assert cv.prefixos_dos_lancadores(tmp_path) == []


def test_o_mesmo_prefixo_nao_entra_duas_vezes(tmp_path: Path) -> None:
    """O Heroic declara o prefixo na config E ele mora sob `~/Games`: as duas
    rotas o alcançam. ARRANQUE o `vistos` e o censo o contaria em dobro."""
    import json

    alvo = _prefixo(tmp_path, "Games", "Heroic", "Prefixes", "O Jogo")
    conf = tmp_path / ".config" / "heroic" / "GamesConfig"
    conf.mkdir(parents=True)
    (conf / "x.json").write_text(
        json.dumps({"x": {"winePrefix": str(alvo)}}), encoding="utf-8")
    (tmp_path / ".config" / "heroic" / "config.json").write_text("{}", encoding="utf-8")
    achados = cv.prefixos_dos_lancadores(tmp_path)
    assert achados.count(alvo) <= 1, f"o prefixo entrou {achados.count(alvo)} vezes"


def test_a_varredura_nao_levanta_em_disco_hostil(tmp_path: Path) -> None:
    """NUNCA LEVANTA é contrato da função: ela roda no caminho do lançamento."""
    assert cv.prefixos_dos_lancadores(tmp_path / "nao-existe") == []


def test_a_raiz_gigante_nao_custa_o_censo(tmp_path: Path) -> None:
    """ARRANQUE o `_MAXIMO_DE_FILHOS_POR_RAIZ` e este teste reprova: uma pasta
    `~/Games` usada como despejo custaria um `is_file()` por arquivo, a cada
    censo — e o censo roda no clique do botão e na linha do exame."""
    raiz = tmp_path / "Games"
    raiz.mkdir(parents=True)
    for n in range(cv._MAXIMO_DE_FILHOS_POR_RAIZ + 50):
        (raiz / f"{n:05d}.txt").write_text("", encoding="utf-8")
    assert cv.prefixos_dos_lancadores(tmp_path) == []
    assert cv._MAXIMO_DE_FILHOS_POR_RAIZ < 10_000


# ---------------------------------------------------------------------------
# E2 — a linha permanente, e os três números
# ---------------------------------------------------------------------------


class _Jogo:
    def __init__(self, appid: str, camadas: tuple[Any, ...]) -> None:
        self.appid = appid
        self.camadas = camadas

    @property
    def sobras(self) -> tuple[Any, ...]:
        return tuple(c for c in self.camadas if c.ligada)


class _Camada:
    def __init__(self, chave: str, caminho: str, *, ligada: bool) -> None:
        self.chave = chave
        self.caminho_windows = caminho
        self.ligada = ligada


def _montar(monkeypatch: pytest.MonkeyPatch, *, prefixos: int,
            jogos: list[_Jogo], estado: dict[str, Any]) -> str | None:
    monkeypatch.setattr(cv, "raizes_de_prefixo",
                        lambda home=None: [Path(f"/p/{n}") for n in range(prefixos)])
    monkeypatch.setattr(cv, "censo", lambda home=None, com_nomes=True: jogos)
    monkeypatch.setattr(cv, "ler_estado", lambda home=None: estado)
    linha = linha_da_sobreposicao_vulkan()
    if linha is None:
        return None
    selo, texto = linha
    assert selo == SELO_INFORMATIVO, (
        "a linha não é informativa — um selo de falha sobre um FATO da máquina "
        "ensina que existia algo a corrigir")
    return texto


def test_a_linha_diz_quantos_prefixos_foram_vistos(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """ARRANQUE o terceiro número e este teste reprova.

    Sem ele, «tirada em 1 jogo» não diz se o produto olhou 33 prefixos ou 3 —
    que é LITERALMENTE a primeira pergunta dela.
    """
    camada = _Camada("K", r"C:\a\EOS.json", ligada=False)
    estado = {"1599660": {cv.chave_de_estado("K", r"C:\a\EOS.json"): {"feito": "desligada"}}}
    texto = _montar(monkeypatch, prefixos=33,
                    jogos=[_Jogo("1599660", (camada,))], estado=estado)
    assert texto is not None and "33 prefixos vistos" in texto, texto
    assert "tirada em 1 jogo" in texto, texto


def test_sem_nenhuma_camada_a_linha_continua_saindo(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """ARRANQUE o ramo do zero e este teste reprova.

    «nenhuma tirada · nenhuma posta · 33 prefixos vistos» é informação: ela diz
    que o produto OLHOU. A ausência da linha se leria como «ele não olhou».
    """
    texto = _montar(monkeypatch, prefixos=33, jogos=[], estado={})
    assert texto is not None
    assert "nenhuma tirada" in texto and "nenhuma posta" in texto, texto
    assert "33 prefixos vistos" in texto, texto


def test_camada_que_nunca_foi_nossa_nao_conta_como_trabalho_feito(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """ARRANQUE a consulta ao estado e este teste reprova.

    Uma camada que o próprio jogo nunca ligou é `ligada=False` sem nós termos
    tocado nela. Contá-la como «tirada» seria o número virar elogio a quem não
    fez nada — a forma exata do instrumento que responde sobre outra coisa.
    """
    nunca_nossa = _Camada("K", r"C:\b\Outra.json", ligada=False)
    texto = _montar(monkeypatch, prefixos=5,
                    jogos=[_Jogo("42", (nunca_nossa,))], estado={})
    assert texto is not None and "nenhuma tirada" in texto, texto


def test_a_sobra_aparece_como_posta(monkeypatch: pytest.MonkeyPatch) -> None:
    """A segunda metade da pergunta: o que o botão AINDA faria."""
    texto = _montar(monkeypatch, prefixos=7,
                    jogos=[_Jogo("42", (_Camada("K", r"C:\c\X.json", ligada=True),))],
                    estado={})
    assert texto is not None and "posta em 1" in texto, texto


def test_o_exame_nao_cai_por_causa_de_um_vulkan(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """ARRANQUE o `try/except` e este teste reprova: um `system.reg` torto
    apagaria as SEIS linhas do exame que já estavam prontas."""
    def explode(*a: Any, **k: Any) -> Any:
        raise OSError("disco hostil")

    monkeypatch.setattr(cv, "raizes_de_prefixo", explode)
    assert linha_da_sobreposicao_vulkan() is None


def test_a_linha_entra_no_exame() -> None:
    """A régua de LIGAÇÃO: uma linha que ninguém soma é trabalho que não chega
    à tela dela. ARRANQUE a chamada em `_achados` e ela reprova."""
    import inspect

    from hefesto_dualsense4unix.interface.pacotes import a09_sistema

    fonte = inspect.getsource(a09_sistema._achados)
    assert "linha_da_sobreposicao_vulkan" in fonte, (
        "a linha existe e o exame não a soma")

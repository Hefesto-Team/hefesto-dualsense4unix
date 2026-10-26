"""O «Excluir» da aba Lançadores antiga, guardado só para os testes semearem o disco.

O-QUE-A-07-ANTIGA-FAZIA-SEM-TELA-VOLTA-OU-SAI-01 (19/10/2026, a resposta: «Saem do produto»): o
``lista_de_exclusao.adicionar`` saiu do produto, sem chamador desde a aba antiga. A lista que ele
escreveu continua no disco de quem a usou, e os leitores (a carona, o device KS, o ``tirar``, o
uninstall) continuam lendo-a. Para provar esses leitores, os testes precisam de uma entrada IGUAL à
que a aba antiga deixava, com as cópias do Heroic e os ``.yml`` do Lutris: por isso a função mora
aqui, byte a byte a de antes, e não num dublê mais pobre.

Nenhum código de ``src/`` importa este módulo.
"""

from __future__ import annotations

import json
import re
import sqlite3
import time
from collections.abc import Callable, Iterable
from pathlib import Path

from hefesto_dualsense4unix.integrations import cura_por_estrada as cpe
from hefesto_dualsense4unix.integrations import lista_de_exclusao as lx
from hefesto_dualsense4unix.integrations import proton_pin
from hefesto_dualsense4unix.integrations import steam_launch_options as slo

NOTA_DAS_LISTAS = "posto pela lista de exclusão do Hefesto"

_POR: dict[str, Callable[[str], str]] = {
    "pino": lambda a: proton_pin.nomear_fora_do_pino(a, nota=NOTA_DAS_LISTAS),
    "atalho": lambda a: slo.marcar_jogo_sem_wrapper(a, nota=NOTA_DAS_LISTAS),
}


def adicionar(
    chave: str,
    *,
    lancador: str,
    nome: str,
    nota: str = "",
    config_home: Path | None = None,
    escritas_herdadas: tuple[str, ...] = (),
    janelas: tuple[str, ...] = (),
    lar: Path | None = None,
) -> str:
    """Exclui o jogo.

    Status: ``"adicionado"`` | ``"ja_estava"`` | ``"chave_invalida"`` |
    ``"ocupada"`` (a trava não veio no prazo da janela) | ``"ilegivel"`` (a lista
    existe e não se lê) | ``"erro"`` (o resto). ``"ocupada"`` e ``"ilegivel"`` voltam
    antes de qualquer escrita; no ``"erro"`` a Steam, o Heroic ou o Lutris já podem
    ter recebido a escrita.
    """
    alvo = chave.strip()
    if not alvo:
        return "chave_invalida"
    destino = lx.caminho(config_home)
    with cpe.trava_da_lista(destino) as na_mao:
        if not na_mao:
            return "ocupada"
        return _adicionar_na_trava(
            alvo, destino, lancador=lancador, nome=nome, nota=nota,
            escritas_herdadas=escritas_herdadas, janelas=janelas, lar=lar)


def _adicionar_na_trava(
    alvo: str, destino: Path, *, lancador: str, nome: str, nota: str,
    escritas_herdadas: tuple[str, ...], janelas: tuple[str, ...], lar: Path | None,
) -> str:
    """O corpo de :func:`adicionar`, com a trava na mão."""
    try:
        atuais = lx._ler_cru(destino)
    except lx._ArquivoTortoError:
        return "ilegivel"
    except OSError:
        return "erro"
    if any(e.chave == alvo for e in atuais):
        return "ja_estava"

    escritas = list(escritas_herdadas)
    appid = lx.appid_da_chave(alvo)

    def desfazer_as_listas() -> None:
        if appid is not None:
            for feita in escritas:
                if feita not in escritas_herdadas:
                    lx._TIRAR[feita](appid)

    if appid is not None:
        for lista in lx.LISTAS:
            if lista in escritas:
                continue
            status = _POR[lista](appid)
            if status == "adicionado":
                escritas.append(lista)
            elif status != "ja_estava":
                desfazer_as_listas()
                return "erro"

    janelas_limpas = tuple(j.strip() for j in janelas if j.strip())
    copias: tuple[cpe.CopiaDoJogo, ...] = ()
    ymls: tuple[cpe.YmlDoJogo, ...] = ()
    if appid is not None:
        copias, status = tirar_o_nosso_do_jogo_do_heroic(alvo, lar=lar)
        if status == "erro":
            desfazer_as_listas()
            return "erro"
        ymls, status = tirar_o_nosso_do_jogo_do_lutris(alvo, lar=lar)
        if status == "erro":
            cpe.devolver_ao_jogo_do_heroic(copias)
            desfazer_as_listas()
            return "erro"
    elif lx.e_caixa(alvo) and tirar_o_nosso_da_caixa(janelas_limpas, lar=lar) == "erro":
        return "erro"

    nova = lx.Entrada(
        chave=alvo, lancador=lancador, nome=nome,
        quando=time.strftime("%Y-%m-%dT%H:%M:%S"), nota=nota,
        escritas=tuple(x for x in lx.LISTAS if x in escritas),
        janelas=janelas_limpas,
        heroic=copias,
        lutris=ymls,
    )
    try:
        lx._gravar(destino, [*atuais, nova])
    except OSError:
        desfazer_as_listas()
        cpe.devolver_ao_jogo_do_heroic(copias)
        cpe.devolver_ao_jogo_do_lutris(ymls)
        return "erro"
    return "adicionado"


def jogos_do_heroic_pela_janela(classe: str, lar: Path | None = None) -> list[Path]:
    """As cópias (`GamesConfig/<app>.json`) dos jogos do Heroic com esta janela."""
    alvo = classe.strip()
    if not alvo:
        return []
    from hefesto_dualsense4unix.integrations import censo_dos_lancadores as censo

    vistos: list[Path] = []
    for biblioteca in censo.bibliotecas_por_casa("Heroic", lar):
        if biblioteca.onde is None:
            continue
        pasta = biblioteca.onde / cpe._PASTA_DOS_JOGOS_DO_HEROIC
        for jogo in biblioteca.jogos:
            if jogo.classe_de_janela == alvo and "/" not in jogo.chave:
                arquivo = pasta / f"{jogo.chave}.json"
                if arquivo not in vistos:
                    vistos.append(arquivo)
    return vistos



def tirar_o_nosso_do_jogo_do_heroic(
    classe: str, *, lar: Path | None = None, pasta_do_ambiente: Path | None = None,
) -> tuple[tuple[cpe.CopiaDoJogo, ...], str]:
    """O jogo do Heroic com esta janela passa a ter a lista própria sem o nosso."""
    feitas: list[cpe.CopiaDoJogo] = []
    status = "nada"
    for alvo in jogos_do_heroic_pela_janela(classe, lar):
        st, copia = cpe._sem_o_nosso_no_jogo(alvo, alvo.stem, pasta_do_ambiente)
        if st == "erro" or copia is None:
            cpe.devolver_ao_jogo_do_heroic(feitas)
            return (), "erro"
        feitas.append(copia)
        if st == "feito":
            status = "feito"
    return tuple(feitas), status



def tirar_o_nosso_da_caixa(
    app_ids: Iterable[str], *, lar: Path | None = None,
    pasta_do_ambiente: Path | None = None,
) -> str:
    """A caixa do Flatpak destes `app-id` sem o ambiente que é nosso."""
    lar = Path.home() if lar is None else lar
    try:
        registro = cpe.ler_registro(pasta_do_ambiente)
    except Exception:  # pragma: no cover
        return "erro"
    mexeu_no_registro = False
    status = "nada"
    for app_id in dict.fromkeys(a for a in app_ids if "." in a):
        alvo = cpe._override_da_caixa(app_id, lar)
        if not alvo.is_file():
            continue
        entrada = registro.get(str(alvo), cpe.Entrada(cpe.FLATPAK_OVERRIDE))
        feito = cpe._desfazer_no_arquivo(alvo, entrada)
        if feito.erro:
            return "erro"
        if str(alvo) in registro:
            del registro[str(alvo)]
            mexeu_no_registro = True
        if feito.tiradas or feito.devolvidas or feito.apagado:
            status = "feito"
    if mexeu_no_registro:
        try:
            cpe.gravar_registro(registro, pasta_do_ambiente)
        except OSError:
            return "erro"
    return status



_LUTRIS_FLATPAK = ".var/app/net.lutris.Lutris"


def _janela_do_jogo_do_lutris(dados: Path, runner: str, servico: str, numero: str,
                              yml: Path) -> str:
    """A janela que a aba antiga via no jogo do Lutris: o número da Steam ou o do umu.

    O leitor do Lutris saiu do produto (virou a extensão ``hefesto-mod-lutris``, 19/10/2026); a
    aba antiga perguntava a ele. Aqui fica só o pedaço que semeia o disco: o serviço ``steam``
    dá o número direto; o runner ``wine`` (que abre pelo Proton) dá o do ``umu-games.json``.
    """
    if servico == "steam" and numero.isdigit():
        return f"steam_app_{numero}"
    if runner != "wine" or not yml.is_file():
        return ""
    try:
        tabela = json.loads((dados / "runtime/umu-games/umu-games.json").read_text())
    except (OSError, ValueError):
        return ""
    for linha in tabela if isinstance(tabela, list) else ():
        if (isinstance(linha, dict) and linha.get("store") == servico
                and str(linha.get("appid")) == numero):
            achado = re.fullmatch(r"umu-(\d+)", str(linha.get("umu_id") or ""))
            return f"steam_app_{achado.group(1)}" if achado else ""
    return ""


def jogos_do_lutris_pela_janela(classe: str, lar: Path | None = None) -> list[Path]:
    """Os `.yml` dos jogos do Lutris FLATPAK que anunciam esta janela."""
    alvo = classe.strip()
    raiz = (Path.home() if lar is None else lar) / _LUTRIS_FLATPAK
    dados, config = raiz / "data/lutris", raiz / "config/lutris"
    if not alvo or not (dados / "pga.db").is_file():
        return []
    con = sqlite3.connect(f"file:{dados / 'pga.db'}?mode=ro", uri=True)
    try:
        linhas = list(con.execute(
            "SELECT runner, service, service_id, configpath FROM games WHERE installed"))
    finally:
        con.close()
    vistos: list[Path] = []
    for runner, servico, numero, configpath in linhas:
        if not configpath:
            continue
        yml = (config if config.is_dir() else dados) / "games" / f"{configpath}.yml"
        janela = _janela_do_jogo_do_lutris(dados, str(runner or ""), str(servico or ""),
                                           str(numero or ""), yml)
        if (janela == alvo and yml.is_file() and not yml.is_symlink()
                and yml not in vistos):
            vistos.append(yml)
    return vistos



def _cobrir_no_yml(alvo: Path, pares: dict[str, str]) -> cpe.YmlDoJogo | None:
    """Escreve os pares no `.yml` e devolve o registro da volta. ``None`` = erro."""
    try:
        texto = alvo.read_text(encoding="utf-8")
    except OSError:
        return None
    feito = cpe._com_o_nosso_no_yml(texto, pares)
    if feito is None:
        return None
    novo, postos, moldura = feito
    if novo != texto:
        try:
            cpe._escrever_atomico(alvo, novo)
        except OSError:
            return None
    if cpe._PAR_DO_XALIA & {k for k, _ in postos}:
        cpe._dizer_o_par(alvo, 1)
    return cpe.YmlDoJogo(str(alvo), texto, cpe._sha(novo), postos, moldura)



def tirar_o_nosso_do_jogo_do_lutris(
    classe: str, *, lar: Path | None = None, pasta_do_ambiente: Path | None = None,
) -> tuple[tuple[cpe.YmlDoJogo, ...], str]:
    """O jogo do Lutris Flatpak com esta janela passa a cobrir a caixa."""
    ymls = jogos_do_lutris_pela_janela(classe, lar)
    if not ymls:
        return (), "nada"
    base, por_jogo = cpe._a_camada_da_caixa(lar, pasta_do_ambiente)
    feitos: list[cpe.YmlDoJogo] = []
    for alvo in ymls:
        pares = cpe._com_o_padrao_do_jogo(base, por_jogo,
                                          pelo_proton=cpe._pelo_proton_do_yml(alvo, lar))
        yml = _cobrir_no_yml(alvo, pares)
        if yml is None:
            cpe.devolver_ao_jogo_do_lutris(feitos)
            return (), "erro"
        feitos.append(yml)
    return tuple(feitos), "feito" if any(y.pares for y in feitos) else "nada"

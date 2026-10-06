#!/usr/bin/env python3
"""renomear-o-dela.py — os nomes de arquivo versionados perdem a palavra «dela».

O projeto é de quem usa; um nome de arquivo não aponta para uma pessoa. Este
script faz a parte mecânica, e só ela:

1. ``git mv`` de cada arquivo da ``TABELA`` (o que já foi movido é pulado);
2. toda referência versionada ao nome velho passa ao novo (caminho e nome-base);
3. o marcador de isenção de acento perde o «dela» da razão (``citação literal``;
   ``scripts/validar-acentuacao.py`` ignora qualquer linha
   com ``noqa-acento``, então a razão escrita depois dele pode mudar de forma).

Uso::

    python3 scripts/renomear-o-dela.py --conferir   # diz o que faria; rc=1 se faria algo
    python3 scripts/renomear-o-dela.py --aplicar    # faz; rodar de novo não muda nada
    python3 scripts/renomear-o-dela.py --tsv        # imprime a tabela (velho<TAB>novo)

Contrato das ferramentas da casa: idempotente, ``--conferir``, resumo em UMA linha
(o detalhe vai para ``--detalhe ARQUIVO``). O que não é versionado (``docs/process/``
e o arquivo de instruções da raiz) é reapontado pelo ``reapontar-a-casa.py`` de
a costura, com a mesma tabela.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

_T = "tests/unit/"
TABELA: dict[str, str] = {
    "docs/data/decisoes-dela.csv": "docs/data/decisoes-de-produto.csv",
    "scripts/check_a_conferencia_dela.py": "scripts/check_a_conferencia.py",
    "scripts/check_o_endereco_dela_em_toda_forma.py": "scripts/check_o_endereco_em_toda_forma.py",
    "src/hefesto_dualsense4unix/interface/CORRECOES-DELA.md": "src/hefesto_dualsense4unix/interface/CORRECOES.md",
    _T + "test_a02_os_nomes_da_fileira_sao_os_dela.py": _T + "test_a02_os_nomes_da_fileira.py",
    _T + "test_a08_a_ordem_de_servico_e_a_sala_sao_da_maquina_dela.py": _T + "test_a08_a_ordem_de_servico_e_a_sala_sao_da_maquina.py",
    _T + "test_a08_o_veredito_e_a_mesa_de_radio_dela.py": _T + "test_a08_o_veredito_e_a_mesa_de_radio.py",
    _T + "test_a_06_a_escolha_dela_sobrevive_ao_tique.py": _T + "test_a_06_a_escolha_sobrevive_ao_tique.py",
    _T + "test_a_aba05_publica_os_hexes_do_mapa_dela.py": _T + "test_a_aba05_publica_os_hexes_do_mapa.py",
    _T + "test_a_conexoes_o_que_a_lista_dela_achou.py": _T + "test_a_conexoes_o_que_a_lista_achou.py",
    _T + "test_a_dispensa_mora_na_mesa_dela.py": _T + "test_a_dispensa_mora_na_mesa.py",
    _T + "test_a_fita_da_06_nao_perde_o_titulo_dela.py": _T + "test_a_fita_da_06_nao_perde_o_titulo.py",
    _T + "test_a_janela_nao_nasce_na_tela_dela.py": _T + "test_a_janela_nao_nasce_na_tela.py",
    _T + "test_a_mira_02_as_respostas_dela.py": _T + "test_a_mira_02_as_respostas.py",
    _T + "test_a_prova_automatica_nao_dispensa_ordem_dela.py": _T + "test_a_prova_automatica_nao_dispensa_ordem.py",
    _T + "test_a_prova_nao_grava_no_perfil_dela.py": _T + "test_a_prova_nao_grava_no_perfil_do_usuario.py",
    _T + "test_a_suite_nao_abre_nem_fecha_o_lancador_dela.py": _T + "test_a_suite_nao_abre_nem_fecha_o_lancador_do_usuario.py",
    _T + "test_a_suite_nao_avisa_na_tela_dela.py": _T + "test_a_suite_nao_avisa_na_tela_do_usuario.py",
    _T + "test_a_suite_nao_conversa_com_o_som_dela.py": _T + "test_a_suite_nao_conversa_com_o_som_do_usuario.py",
    _T + "test_a_suite_nao_ve_o_jogo_dela.py": _T + "test_a_suite_nao_ve_o_jogo_do_usuario.py",
    _T + "test_a_tela_dela_nao_recebe_janela_de_teste.py": _T + "test_a_tela_nao_recebe_janela_de_teste.py",
    _T + "test_bateria_que_pula_01_a_voz_dela_nao_e_a_carga.py": _T + "test_bateria_que_pula_01_a_voz_nao_e_a_carga.py",
    _T + "test_empate01_a_cor_volta_a_ser_dela.py": _T + "test_empate01_a_cor_volta_a_ser_a_escolhida.py",
    _T + "test_o_app_id_da_janela_casa_o_desktop_e_nasce_antes_dela.py": _T + "test_o_app_id_da_janela_casa_o_desktop_e_nasce_antes_da_janela.py",
    _T + "test_o_carimbo_da_ponte_segue_a_escolha_dela.py": _T + "test_o_carimbo_da_ponte_segue_a_escolha.py",
    _T + "test_o_eco_da_propria_escrita_nao_e_gesto_dela.py": _T + "test_o_eco_da_propria_escrita_nao_e_gesto_do_usuario.py",
    _T + "test_o_gesto_dela_poe_o_microfone_no_ar.py": _T + "test_o_gesto_poe_o_microfone_no_ar.py",
    _T + "test_o_hefesto_abre_na_escolha_dela.py": _T + "test_o_hefesto_abre_na_escolha.py",
    _T + "test_o_instrumento_nao_abre_na_tela_dela.py": _T + "test_o_instrumento_nao_abre_na_tela_do_usuario.py",
    _T + "test_o_lancador_dela_nasce_na_tela_dela.py": _T + "test_o_lancador_nasce_na_tela.py",
    _T + "test_o_mapa_do_gabinete_e_o_dela.py": _T + "test_o_mapa_do_gabinete_e_do_usuario.py",
    _T + "test_o_par_vem_do_desenho_dela.py": _T + "test_o_par_vem_do_desenho.py",
    _T + "test_o_parear_espera_o_clique_dela.py": _T + "test_o_parear_espera_o_clique.py",
    _T + "test_o_terceiro_nome_dela.py": _T + "test_o_terceiro_nome.py",
    _T + "test_perfil_atual_01_a_linha_dela_tem_cor_e_o_primeiro_lugar.py": _T + "test_perfil_atual_01_a_linha_tem_cor_e_o_primeiro_lugar.py",
    _T + "test_portao_pytest_nao_escreve_na_casa_dela.py": _T + "test_portao_pytest_nao_escreve_na_casa_do_usuario.py",
    _T + "test_salvar_nao_apaga_a_cor_dela.py": _T + "test_salvar_nao_apaga_a_cor.py",
    _T + "test_som_02_o_volume_dela_chega_ao_perfil.py": _T + "test_som_02_o_volume_chega_ao_perfil.py",
    _T + "test_som_eco_02_a_ponte_nao_toca_a_voz_dela.py": _T + "test_som_eco_02_a_ponte_nao_toca_a_voz_do_usuario.py",
    _T + "test_som_mic_replug_01_o_mudo_dela_sobrevive_ao_cabo.py": _T + "test_som_mic_replug_01_o_mudo_sobrevive_ao_cabo.py",
    _T + "test_tray_a_listinha_dela.py": _T + "test_tray_a_listinha.py",
    _T + "test_um_numero_so_01_o_alvo_fala_a_lingua_dela.py": _T + "test_um_numero_so_01_o_alvo_fala_a_lingua.py",
}

#: O marcador de isenção: a razão perde o «dela».
MARCADOR_NOVO = "citação literal"
MARCADOR_VELHO = MARCADOR_NOVO + " " + "dela"

_EXT_TEXTO = {
    ".py", ".sh", ".md", ".yml", ".yaml", ".toml", ".csv", ".txt", ".html", ".css",
    ".js", ".json", ".cfg", ".ini", ".rules", ".service", ".desktop", ".nix", ".po", ".pot",
}


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=RAIZ, capture_output=True, text=True, check=True
    ).stdout


def _versionados() -> list[str]:
    return [f for f in _git("ls-files").split("\n") if f]


def _texto(rel: str) -> bool:
    return Path(rel).suffix in _EXT_TEXTO


def pares_de_nome(tabela: dict[str, str]) -> tuple[re.Pattern[str], dict[str, str]]:
    """Um padrão só (alternância, do nome mais longo ao mais curto) e o mapa velho -> novo."""
    mapa: dict[str, str] = {}
    for velho, novo in tabela.items():
        bv, bn = Path(velho).name, Path(novo).name
        mapa[bv] = bn
        mapa[bv.rsplit(".", 1)[0]] = bn.rsplit(".", 1)[0]
    nomes = sorted(mapa, key=lambda n: -len(n))
    padrao = re.compile(r"(?<![\w-])(?:" + "|".join(re.escape(n) for n in nomes) + r")(?![\w-])")
    return padrao, mapa


#: Arquivos de posse alheia: recebem só a troca do caminho que quebraria, nunca o marcador.
SO_REFERENCIA = (
    "install.sh", "uninstall.sh", "README.md", "docs/usage/", "tests/conftest.py", ".github/",
    # dados que a costura escreve: só o caminho, nunca o marcador dentro das células
    "docs/data/mapa-controles.csv", "docs/data/decisoes-de-produto.csv", "docs/specs.html",
)


def reescrever(texto: str, regras: tuple[re.Pattern[str], dict[str, str]], marcador: bool = True) -> str:
    padrao, mapa = regras
    if "dela" in texto.lower():
        texto = padrao.sub(lambda m: mapa[m.group(0)], texto)
    return texto.replace(MARCADOR_VELHO, MARCADOR_NOVO) if marcador else texto


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    modo = ap.add_mutually_exclusive_group(required=True)
    modo.add_argument("--conferir", action="store_true")
    modo.add_argument("--aplicar", action="store_true")
    modo.add_argument("--tsv", action="store_true")
    ap.add_argument("--detalhe", help="arquivo onde o detalhe é gravado")
    args = ap.parse_args(argv)

    if args.tsv:
        for velho, novo in TABELA.items():
            print(f"{velho}\t{novo}")
        return 0

    presentes = set(_versionados())
    a_mover = [(v, n) for v, n in TABELA.items() if v in presentes]
    colisoes = [n for _, n in a_mover if n in presentes]
    if colisoes:
        print(f"renomear-o-dela: colisão de nome: {colisoes}", file=sys.stderr)
        return 2
    regras = pares_de_nome(TABELA)
    detalhe: list[str] = [f"mv {v} -> {n}" for v, n in a_mover]

    mudados: list[str] = []
    for rel in sorted(presentes):
        if not _texto(rel) or rel.startswith("docs/process/") or rel == "scripts/renomear-o-dela.py":
            continue
        caminho = RAIZ / rel
        if not caminho.is_file():
            continue
        try:
            antigo = caminho.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        novo = reescrever(antigo, regras, not rel.startswith(SO_REFERENCIA))
        if novo != antigo:
            mudados.append(rel)
            if args.aplicar:
                caminho.write_text(novo, encoding="utf-8")
    detalhe += [f"ref {r}" for r in mudados]

    if args.aplicar:
        for velho, novo in a_mover:
            subprocess.run(["git", "mv", velho, novo], cwd=RAIZ, check=True)
    if args.detalhe:
        Path(args.detalhe).write_text("\n".join(detalhe) + "\n", encoding="utf-8")
    faria = bool(a_mover or mudados)
    verbo = "feito" if args.aplicar else "faria"
    print(f"renomear-o-dela: {verbo} {len(a_mover)} renomes e {len(mudados)} arquivos com referência trocada")
    return 1 if (faria and args.conferir) else 0


if __name__ == "__main__":
    sys.exit(main())

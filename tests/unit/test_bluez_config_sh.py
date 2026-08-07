"""RADIO-ABERTO-01/E1-bis — a cura de `confirm` chega mesmo ao disco?

O DEFEITO, MEDIDO em 06/08/2026 na máquina dela:

    /etc/bluetooth/main.conf:25  JustWorksRepairing=always

dentro do bloco ``# >>> hefesto bluetooth >>>`` — ou seja, **escrito por uma
versão anterior deste próprio projeto**. Os assets passaram para ``confirm`` em
05/08 (sprint RADIO-ABERTO-01, entrega E1). O valor perigoso continuou no disco
por quatro dias porque a única coisa que reescreve aquele arquivo é uma
execução do ``install.sh``, e não houve nenhuma entre 02/08 (último backup
gravado pelo install) e 06/08.

**A E1 estava escrita e não chegava à máquina.** Nenhum teste podia acusar
isso: os portões que existiam (``test_radio_aberto_01.py``,
``test_bt_resilience_assets.py``, ``test_plataforma_wiring.py``) leem
``install.sh``/``uninstall.sh`` como TEXTO. Um ``awk`` quebrado, um ``cmp``
invertido ou um caminho que nunca abre o ``main.conf`` passavam verdes.

Esta bancada existe para fechar exatamente esse buraco. Ela roda o mecanismo
de verdade — ``scripts/bluez_config.sh`` — contra uma **raiz falsa** em
``tmp_path`` (``HEFESTO_BT_ETC``), com ``HEFESTO_BT_SUDO`` vazio. Nada em
``/etc`` é lido nem escrito, e a suíte não precisa de root. Precedente da casa:
``test_radio_aberto_e10.py`` faz o mesmo com ``bt_bonds_restore.sh --verificar``
via ``HEFESTO_BT_BONDS_SRC``.

AS MORDIDAS (cada uma arrancável, cada uma fica vermelha)

- troque ``confirm`` por ``always`` em ``assets/bluetooth/hefesto-bt.block`` →
  ``test_bloco_antigo_do_hefesto_com_always_vira_confirm`` fica vermelho;
- apague a regra do ``awk`` que descarta as faixas das sentinelas (o ``_skip``)
  → o bloco antigo com ``always`` sobrevive e o mesmo teste fica vermelho, e
  ``test_rodar_duas_vezes_nao_duplica_o_bloco`` também;
- apague a regra que neutraliza chave ativa fora de bloco →
  ``test_chave_insegura_fora_do_bloco_e_neutralizada`` fica vermelho;
- inverta o ``cmp`` de ``_gravar_se_mudou`` (backup antes de comparar) →
  ``test_rodar_duas_vezes_nao_gera_backup_novo`` fica vermelho;
- devolva o ``aplicar`` ao desenho antigo (``if -d main.conf.d`` … ``elif -f
  main.conf``, um OU outro) → ``test_dropin_presente_nao_deixa_always_no_main_conf``
  fica vermelho — essa é a assimetria que deixava o instalador anunciar
  ``confirm`` com o ``always`` vivo no arquivo que o BlueZ lê;
- troque a recusa da sentinela sem fechamento por um ``sed`` de faixa →
  ``test_sentinela_sem_fechamento_nao_come_o_resto_do_arquivo`` fica vermelho;
- apague a devolução da marca ``#hefesto-desativou# `` no ``remover`` →
  ``test_remover_devolve_a_chave_de_terceiro`` fica vermelho.

AS MORDIDAS DA SEGUNDA LEVA (06/08/2026, os achados da verificação adversarial)

- devolva a chamada de poda automática ao ``_aplicar``/``_remover`` →
  ``test_aplicar_nao_apaga_backup_nenhum`` fica vermelho (é a evidência do
  colapso "404 linhas -> 3 linhas" indo embora);
- tire a proteção do mais antigo ou a proteção por ESTADO no ``podar`` →
  ``test_podar_nunca_apaga_o_mais_antigo`` /
  ``test_podar_nunca_apaga_backup_de_conteudo_unico`` /
  ``test_podar_nunca_faz_um_estado_sumir_do_disco`` ficam vermelhos;
- volte ``_gravar_se_mudou`` para ``install -m644 tmp main.conf`` →
  ``test_escrita_interrompida_nao_trunca_o_main_conf`` fica vermelho (o arquivo
  dela fica cortado NO MEIO DO BLOCO) e
  ``test_falha_na_troca_atomica_devolve_o_arquivo_intacto`` também;
- apague o aviso do ``remover`` → ``test_remover_grita_o_always_que_devolve``
  fica vermelho;
- apague o ``_avisar_alheio_no_bloco`` →
  ``test_aplicar_nomeia_linha_de_terceiro_dentro_do_bloco`` fica vermelho;
- tire o ``else`` do passo 3d do ``install.sh`` →
  ``test_install_anuncia_o_pulo_do_bluez_com_no_udev`` fica vermelho;
- devolva o ``sed`` inline do ``doctor.sh`` →
  ``test_doctor_le_pelo_dono_unico`` fica vermelho;
- troque o ``if [[ -r ... ]]`` do ``_cat_conf`` por leitura direta →
  ``test_leitura_de_arquivo_ilegivel_escala_em_vez_de_desistir`` fica vermelho;
  tire a recusa do ``_conf_ilegivel`` no ``remover`` →
  ``test_remover_recusa_em_vez_de_concluir_que_nao_ha_nada_nosso`` fica vermelho;
- "conserte" o ``awk`` para preservar as linhas em branco do fim →
  ``test_remover_declara_a_excecao_das_linhas_em_branco_do_fim`` fica vermelho
  (a exceção é o preço da idempotência, e por isso é DECLARADA, não corrigida);
- devolva o ``|| true`` que engolia a falha do ``rm`` →
  ``test_podar_nao_anuncia_remocao_que_nao_aconteceu`` fica vermelho.

AS MORDIDAS DA TERCEIRA LEVA (06/08/2026 — a verificação adversarial reprovou
duas de três lentes, e estas são as curas). Todas MEDIDAS: arrancadas, vistas
vermelhas, devolvidas.

- devolva o nome de backup com resolução de um segundo
  (``...hefesto-${rotulo}$(date +%s)``, sem ``mktemp``) →
  ``test_duas_gravacoes_no_mesmo_segundo_nao_comem_o_backup_anterior`` e
  ``test_aplicar_e_remover_seguidos_nao_colidem`` ficam vermelhos: o backup
  destruído é sempre o de MAIOR valor, o estado imediatamente anterior;
- tire a limpeza do backup incompleto →
  ``test_backup_parcial_e_apagado_e_o_main_conf_nao_e_tocado`` fica vermelho;
- tire do ``_ler_chave`` a linha ``if (_grupo != "General") next`` → TRÊS casos
  de ``test_o_dono_unico_le_exatamente_o_que_o_bluez_le``
  (``grupo-errado-nao-conta``, ``so-em-policy-e-ausente-em-general``,
  ``nome-de-grupo-e-exato``) e o ``test_o_veredito_acompanha_o_grupo`` ficam
  vermelhos — quatro falhas ao todo (é o falso negativo do dono único:
  ``verificar`` dizia OK e o GKeyFile lia ``always``). A terceira leva escreveu
  aqui "quatro casos"; recontado em 06/08 numa medição em série, são três casos
  e quatro falhas;
- faça o PRIMEIRO valor vencer em vez do último →
  ``test_o_ultimo_vence_e_nao_o_primeiro`` e dois casos da tabela ficam
  vermelhos (a regra do ``tail -n 1`` não tinha teste que mordesse);
- volte a promessa única do rebaixamento do ``never`` →
  ``test_never_dentro_do_bloco_nao_ganha_promessa_que_nao_se_cumpre`` e
  ``test_never_fora_do_bloco_ganha_a_promessa_e_ela_se_cumpre`` ficam vermelhos;
  o mesmo texto no ``doctor.sh`` derruba
  ``test_o_doctor_nao_promete_devolucao_sem_ressalva``;
- tire a releitura final do disco do ``_aplicar`` →
  ``test_bloco_de_zero_byte_nao_anuncia_garantia`` fica vermelho (rc=0
  anunciando garantia com o arquivo sem a chave);
- tire o ``trap`` de limpeza →
  ``test_um_kill_no_meio_da_troca_nao_deixa_temporario`` fica vermelho; tire o
  ``trap`` E o ``rm -f`` do caminho de falha e
  ``test_a_troca_atomica_nao_deixa_temporario_quando_o_mv_fracassa`` cai junto.

AS MORDIDAS DA QUARTA LEVA (06/08/2026 — e uma RETRATAÇÃO). Todas MEDIDAS em
SÉRIE, sozinhas na árvore, com restauração conferida por md5:

- devolva a proteção por ARQUIVO no ``_podar`` ("nenhum OUTRO backup tem os
  mesmos bytes") → ``test_podar_nunca_faz_um_estado_sumir_do_disco`` fica
  vermelho: com vários estados de poucas cópias, todas fora da retenção, um
  estado inteiro do ``main.conf`` dela some do disco;
- devolva ``install -Dm644`` / ``rm -f`` ao caminho dos drop-ins →
  ``test_aplicar_nao_destroi_dropin_editado_a_mao`` e
  ``test_remover_nao_apaga_dropin_editado_a_mao_sem_copia`` ficam vermelhos;
- tire o ``! -empty`` do ``_lista_backups`` →
  ``test_backup_de_zero_byte_nao_conta_como_backup`` e
  ``test_o_resumo_do_aplicar_nao_soma_backup_vazio`` ficam vermelhos;
- tire SÓ a metade do ``cmp`` do ``_copia_de_seguranca`` →
  ``test_backup_que_mente_ter_copiado_e_pego_pelo_cmp`` fica vermelho.

  A RETRATAÇÃO, e é o motivo de o teste acima existir: a terceira leva afirmou
  aqui que arrancar o ``cmp`` deixava
  ``test_backup_parcial_e_apagado_e_o_main_conf_nao_e_tocado`` vermelho. NÃO
  DEIXA, e foi medido por terceiro e reproduzido aqui: o shim daquele teste faz
  o ``cp`` sair 1, o ``||`` curto-circuita e o ``cmp`` nunca chega a ser
  avaliado — com o ``cmp`` arrancado a bancada inteira segue VERDE. Mordida
  afirmada e não reproduzida é exatamente o defeito que a regra da casa proíbe,
  e a cura foi escrever a bancada que faltava (um ``cp`` que corta o arquivo e
  MENTE saindo 0), não apagar a frase.

A REVALIDAÇÃO DE 06/08/2026 — por que estas linhas foram reconferidas

Um diagnóstico independente MEDIU que as três rodadas anteriores rodaram com
agentes irmãos mutando ``scripts/bluez_config.sh`` e ``scripts/doctor.sh`` na
MESMA árvore, ao vivo: 14 execuções contaminadas só na terceira rodada. Toda
mordida medida naquela janela ficou SUSPEITA, nos dois sentidos — vermelho falso
(mordida afirmada que não existe) e verde falso (um ``cp ORIG`` alheio desfazia
a mutação antes do ``pytest``).

As NOVE mordidas daquela janela foram REFEITAS em série, uma de cada vez,
sozinhas na árvore, com a restauração conferida por md5 e por modo: D1
(``fail``→``pass``), D2 (detector fora do ``main()``), M1 (backup com resolução
de 1 s), o ``if (_grupo != "General") next``, P2 (poda automática de volta), M6
(sem ``trap``), M7 (promessa única do ``never``), a conferência final do disco, e
"o primeiro valor vence". As nove MORDEM, e apenas uma correção de número saiu
disso (a do grupo, acima). A cura estrutural que impede a repetição é a
ARVORE-CONGELADA-01, em ``tests/conftest.py``.

O ORÁCULO É OBRIGATÓRIO. Toda afirmação sobre "qual valor o BlueZ lê" passa
pelo ``_oraculo``, que roda o GLib GKeyFile — o parser REAL do ``bluetoothd`` —
num SUBPROCESSO. A bancada tinha um TERCEIRO parser em Python (o antigo helper
``_valor``), e foi exatamente por ali que a classe de defeito do GRUPO passou
batida: o dono e a bancada erravam do MESMO jeito, então concordavam.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from tests.conftest import arvore_congelada

#: A RAIZ NÃO É A ÁRVORE DE TRABALHO — é uma CÓPIA dela, tirada uma vez no
#: início da sessão (ARVORE-CONGELADA-01, em `tests/conftest.py`).
#:
#: POR QUÊ, MEDIDO em 06/08/2026: esta bancada EXECUTA `scripts/bluez_config.sh`
#: e `scripts/doctor.sh` pelo caminho absoluto. Enquanto ela rodava, outro
#: processo estava mutando esses mesmos arquivos (mutação -> medição -> `cp` de
#: volta), e a bancada lia o produto de outra pessoa NO MEIO DO VOO: 5 falhas
#: em 10 execuções, testes DIFERENTES a cada rodada, incluindo testes de TEXTO
#: que caíam por ler o script pela metade. Com a bancada apontada para uma
#: cópia vizinha e o mesmo mutador rodando, 0 falhas em 10. O canal era o
#: arquivo compartilhado, e não carga nem concorrência (18 `pytest` simultâneos
#: na árvore real: 0 falhas em 18).
#:
#: A MORDIDA NÃO SE PERDE: a cópia sai da árvore como ela está quando o
#: `pytest` começa. Arrancar uma cura ANTES de rodar continua ficando vermelho
#: — é arrancá-la DEPOIS que deixa de ser medido, e isso nunca foi medição.
RAIZ = arvore_congelada()
SCRIPT = RAIZ / "scripts" / "bluez_config.sh"
ASSETS = RAIZ / "assets" / "bluetooth"
INSTALL = RAIZ / "install.sh"
UNINSTALL = RAIZ / "uninstall.sh"

MARCA = "#hefesto-desativou# "

#: O estado EXATO medido em /etc/bluetooth/main.conf na máquina dela em
#: 06/08/2026: um bloco do hefesto, escrito por uma versão anterior, com o
#: valor inseguro. É a fixture que importa — não é um caso hipotético.
MAIN_CONF_DELA = """[General]

# >>> hefesto bluetooth >>>
# hefesto-dualsense4unix — bloco de uma versão anterior.
[General]
FastConnectable=true
JustWorksRepairing=always
# <<< hefesto bluetooth <<<
"""


def _etc(tmp_path: Path, main_conf: str | None = None, com_dropin_dir: bool = False) -> Path:
    """Monta a raiz falsa. NADA aqui encosta em /etc."""
    etc = tmp_path / "bluetooth"
    etc.mkdir()
    if main_conf is not None:
        (etc / "main.conf").write_text(main_conf, encoding="utf-8")
    if com_dropin_dir:
        (etc / "main.conf.d").mkdir()
    return etc


def _rodar(
    etc: Path,
    modo: str,
    manter: str = "10",
    arg: str | None = None,
    path_extra: Path | None = None,
    sudo_falso: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    ambiente = {
        **os.environ,
        "HEFESTO_BT_ETC": str(etc),
        "HEFESTO_BT_ASSETS": str(ASSETS),
        # Vazio = sem prefixo de root. É o que torna a bancada possível.
        "HEFESTO_BT_SUDO": "",
        "HEFESTO_BT_BACKUPS_MANTER": manter,
    }
    if path_extra is not None:
        ambiente["PATH"] = f"{path_extra}:{os.environ.get('PATH', '')}"
    if sudo_falso is not None:
        # NUNCA "sudo": um binário nosso, com outro nome, que só REGISTRA o que
        # seria escalado. É como a bancada prova a escalada sem virar root.
        ambiente["HEFESTO_BT_SUDO"] = str(sudo_falso.name)
        ambiente["HEFESTO_FAKE_SUDO_LOG"] = str(sudo_falso.parent / "escaladas.txt")
        ambiente["PATH"] = f"{sudo_falso.parent}:{ambiente.get('PATH', '')}"
    return subprocess.run(
        ["bash", str(SCRIPT), modo, *([arg] if arg is not None else [])],
        capture_output=True,
        text=True,
        timeout=60,
        env=ambiente,
    )


#: O ORÁCULO. Roda em SUBPROCESSO de propósito, por duas razões medidas:
#: (1) vinte e um arquivos desta suíte plantam um ``gi`` FALSO em
#:     ``sys.modules`` (ver a GUARDA-GI-REAL-01 em ``tests/conftest.py``), e um
#:     oráculo que respondesse pelo stub seria pior que oráculo nenhum;
#: (2) é o mesmo parser que o ``bluetoothd`` usa — GLib GKeyFile — e não uma
#:     imitação dele.
_ORACULO = """
import sys
from gi.repository import GLib
kf = GLib.KeyFile()
try:
    kf.load_from_file(sys.argv[1], GLib.KeyFileFlags.NONE)
except Exception as erro:
    sys.stdout.write("ERRO-DE-CARGA %s" % erro)
    raise SystemExit(0)
try:
    sys.stdout.write("VALOR %s" % kf.get_string(sys.argv[2], sys.argv[3]))
except Exception:
    sys.stdout.write("AUSENTE")
"""


def _oraculo(
    arquivo: Path, grupo: str = "General", chave: str = "JustWorksRepairing"
) -> str | None:
    """O que o GKeyFile — o parser REAL do bluetoothd — lê deste arquivo.

    A bancada tinha um TERCEIRO parser em Python (`ln.split("=", 1)[1].strip()`
    sobre o arquivo inteiro), e foi por ali que a classe de defeito do GRUPO
    passou batida: dono e bancada erravam do MESMO jeito, então concordavam.
    Duas fontes para a mesma regra é o defeito que esta leva veio fechar, e ele
    tinha sobrevivido no dono E na bancada.
    """
    proc = subprocess.run(
        [sys.executable, "-c", _ORACULO, str(arquivo), grupo, chave],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if proc.returncode != 0 or "ModuleNotFoundError" in proc.stderr:
        pytest.skip(
            "sem PyGObject neste ambiente — o oráculo GKeyFile é obrigatório "
            "para toda afirmação sobre 'qual valor o BlueZ lê', e não há "
            "substituto honesto (o job de GTK real do CI cobre estes testes)"
        )
    saida = proc.stdout
    if saida == "AUSENTE" or saida.startswith("ERRO-DE-CARGA"):
        return None
    assert saida.startswith("VALOR "), f"oráculo respondeu algo inesperado: {saida!r}"
    return saida[len("VALOR "):]


def _oraculo_recusa(arquivo: Path) -> str | None:
    """A mensagem com que o GKeyFile RECUSA o arquivo inteiro, ou None.

    O `_oraculo` acima devolve `None` tanto para "a chave não está lá" quanto
    para "o parser abortou a carga", e essas duas coisas são MUITO diferentes:
    na primeira o BlueZ usa o default da distro para uma chave; na segunda ele
    fica sem config NENHUMA, inclusive sem o que já era dela. Toda afirmação
    sobre recusa passa por aqui, e nunca pela réplica em `awk` do dono único.
    """
    proc = subprocess.run(
        [sys.executable, "-c", _ORACULO, str(arquivo), "General", "JustWorksRepairing"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if proc.returncode != 0 or "ModuleNotFoundError" in proc.stderr:
        pytest.skip("sem PyGObject neste ambiente — o oráculo GKeyFile é obrigatório")
    if proc.stdout.startswith("ERRO-DE-CARGA "):
        return proc.stdout[len("ERRO-DE-CARGA "):]
    return None


def _valor(etc: Path, chave: str = "JustWorksRepairing") -> str | None:
    """Valor que o BlueZ leria de `[General]` neste main.conf. Pelo oráculo."""
    return _oraculo(etc / "main.conf", "General", chave)


def _backups(etc: Path) -> list[Path]:
    return sorted(etc.glob("main.conf.bak.hefesto-*"))


# ---------------------------------------------------------------------------
# 1. O defeito real desta máquina: valor inseguro JÁ ESTÁ lá, e é nosso
# ---------------------------------------------------------------------------


def test_bloco_antigo_do_hefesto_com_always_vira_confirm(tmp_path: Path) -> None:
    """O caso que ninguém tratava: RECONHECER e CORRIGIR bloco nosso antigo.

    Não basta "acrescentar o bloco novo" — o bloco velho tem de sair. A prova
    é dupla: `always` some do arquivo E `confirm` fica ATIVO.
    """
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    proc = _rodar(etc, "aplicar")

    assert proc.returncode == 0, proc.stderr
    texto = (etc / "main.conf").read_text(encoding="utf-8")
    assert _valor(etc) == "confirm", (
        "o bloco antigo do hefesto com JustWorksRepairing=always sobreviveu ao "
        "aplicar — é exatamente o defeito medido em 06/08/2026"
    )
    ativas_always = [
        ln for ln in texto.splitlines()
        if ln.strip().startswith("JustWorksRepairing") and ln.strip().endswith("always")
    ]
    assert not ativas_always, f"linha ativa com always sobreviveu: {ativas_always}"


def test_o_aplicar_diz_em_voz_alta_que_corrigiu_valor_do_proprio_hefesto(
    tmp_path: Path,
) -> None:
    """Correção silenciosa foi o que deixou o `always` viver quatro dias.

    Quem roda o install tem de LER que a máquina esteve com o valor perigoso —
    senão a segurança acontece sem ninguém saber que era necessária.
    """
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    proc = _rodar(etc, "aplicar")

    assert "always" in proc.stdout
    assert "ANTERIOR do hefesto" in proc.stdout
    assert "RADIO-ABERTO-01" in proc.stdout


def test_chave_insegura_fora_do_bloco_e_neutralizada(tmp_path: Path) -> None:
    """A chave também existe FORA das sentinelas — e o `always` solto mataria a cura.

    Nosso bloco vai para o FIM do arquivo e o último vence, mas deixar um
    `always` ativo solto é uma bomba-relógio: qualquer edição futura que mova o
    bloco inverte o resultado. Neutralizamos, e o `remover` devolve.
    """
    etc = _etc(tmp_path, "[General]\nJustWorksRepairing = always\nName = BlueZ\n")
    proc = _rodar(etc, "aplicar")

    assert proc.returncode == 0, proc.stderr
    texto = (etc / "main.conf").read_text(encoding="utf-8")
    assert f"{MARCA}JustWorksRepairing = always" in texto, (
        "a chave insegura fora do bloco não foi neutralizada"
    )
    assert _valor(etc) == "confirm"
    assert "fora do bloco hefesto" in proc.stdout


def test_chave_comentada_do_template_upstream_fica_intacta(tmp_path: Path) -> None:
    """`#JustWorksRepairing = never` do template do BlueZ não é chave ativa.

    Sem esta asserção, um neutralizador guloso comentaria comentário e o
    arquivo do dpkg viraria lixo a cada install.
    """
    etc = _etc(tmp_path, "[General]\n#JustWorksRepairing = never\nName = BlueZ\n")
    _rodar(etc, "aplicar")

    texto = (etc / "main.conf").read_text(encoding="utf-8")
    assert "\n#JustWorksRepairing = never\n" in texto
    assert f"{MARCA}#JustWorksRepairing" not in texto


# ---------------------------------------------------------------------------
# 2. Idempotência — o portão que o BUG-INSTALL-MAIN-CONF-CRESCE-01 nunca teve
# ---------------------------------------------------------------------------


def test_rodar_duas_vezes_nao_gera_backup_novo(tmp_path: Path) -> None:
    """BUG-INSTALL-MAIN-CONF-BACKUP-INFINITO-01, agora com portão.

    MEDIDO em 06/08/2026: 37 backups em /etc/bluetooth da máquina dela. O
    `cmp` antes do backup é o que impede o 38.
    """
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    _rodar(etc, "aplicar")
    apos_primeiro = _backups(etc)
    assert len(apos_primeiro) == 1, "a primeira aplicação tem de deixar UM backup"

    proc = _rodar(etc, "aplicar")

    assert _backups(etc) == apos_primeiro, (
        "a segunda aplicação, sem mudança nenhuma, criou backup novo"
    )
    assert "nada a reescrever" in proc.stdout


def test_rodar_duas_vezes_nao_duplica_o_bloco(tmp_path: Path) -> None:
    """BUG-INSTALL-MAIN-CONF-CRESCE-01: nem bloco repetido, nem arquivo crescendo.

    O bug real (medido em série temporal nos backups dela: 27, 28, 29 … 34
    linhas) era +1 linha em branco por execução, porque a separadora ficava
    FORA das sentinelas.
    """
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    _rodar(etc, "aplicar")
    primeiro = (etc / "main.conf").read_text(encoding="utf-8")
    _rodar(etc, "aplicar")
    _rodar(etc, "aplicar")
    terceiro = (etc / "main.conf").read_text(encoding="utf-8")

    assert primeiro == terceiro, "o arquivo mudou entre a 1a e a 3a aplicação"
    assert terceiro.count("# >>> hefesto bluetooth >>>") == 1
    # Só linhas ATIVAS: o próprio comentário do bloco cita a chave em prosa.
    ativas = [
        ln for ln in terceiro.splitlines()
        if ln.strip().startswith("JustWorksRepairing")
    ]
    assert ativas == ["JustWorksRepairing=confirm"]


def test_blocos_legados_de_instalacao_antiga_tambem_saem(tmp_path: Path) -> None:
    """Máquina anterior a 21/07 tinha UM bloco por chave. Os dois têm de sair."""
    etc = _etc(
        tmp_path,
        "[General]\n"
        "# >>> hefesto FastConnectable >>>\n[General]\nFastConnectable=true\n"
        "# <<< hefesto FastConnectable <<<\n"
        "# >>> hefesto JustWorksRepairing >>>\n[General]\nJustWorksRepairing = always\n"
        "# <<< hefesto JustWorksRepairing <<<\n",
    )
    _rodar(etc, "aplicar")

    texto = (etc / "main.conf").read_text(encoding="utf-8")
    assert "# >>> hefesto FastConnectable >>>" not in texto
    assert "# >>> hefesto JustWorksRepairing >>>" not in texto
    assert texto.count("# >>> hefesto bluetooth >>>") == 1
    assert _valor(etc) == "confirm"


# ---------------------------------------------------------------------------
# 3. A assimetria estrutural: o caminho do drop-in abandonava o main.conf
# ---------------------------------------------------------------------------


def test_dropin_presente_nao_deixa_always_no_main_conf(tmp_path: Path) -> None:
    """O furo que o mapa chamou de 4-A, e que é o pior dos dois.

    O desenho antigo era `if -d main.conf.d` … `elif -f main.conf`: com o
    diretório presente, o install gravava os drop-ins, imprimia sucesso e
    RETORNAVA SEM ABRIR o main.conf. Como o bluetoothd desta casa não lê
    main.conf.d (MEDIDO: `strings` do bluez 5.86 do backport tem `%*s/main.conf`
    e ZERO `main.conf.d`), bastava alguém criar o diretório para o instalador
    anunciar `confirm` com o `always` vivo no arquivo que vale.
    """
    etc = _etc(tmp_path, MAIN_CONF_DELA, com_dropin_dir=True)
    proc = _rodar(etc, "aplicar")

    assert proc.returncode == 0, proc.stderr
    assert _valor(etc) == "confirm", (
        "com main.conf.d presente, o main.conf ficou com o valor antigo — o "
        "instalador anunciaria confirm e o BlueZ leria always"
    )
    assert (etc / "main.conf.d" / "hefesto-justworks.conf").exists()
    assert (etc / "main.conf.d" / "hefesto-fastconnectable.conf").exists()


def test_dropin_e_bloco_declaram_o_mesmo_valor(tmp_path: Path) -> None:
    """Os dois lugares dizendo a mesma coisa é o que torna a dúvida inofensiva.

    Não sabemos com certeza qual dos dois este BlueZ lê (a evidência do
    `strings` é forte, mas não é leitura do fonte). Escrever nos dois com o
    MESMO valor faz a resposta não importar.
    """
    etc = _etc(tmp_path, MAIN_CONF_DELA, com_dropin_dir=True)
    _rodar(etc, "aplicar")

    dropin = (etc / "main.conf.d" / "hefesto-justworks.conf").read_text(encoding="utf-8")
    ativos = [
        ln.split("=", 1)[1].strip()
        for ln in dropin.splitlines()
        if ln.strip().startswith("JustWorksRepairing")
    ]
    assert ativos == ["confirm"]
    assert _valor(etc) == "confirm"


# ---------------------------------------------------------------------------
# 3-bis. O caminho do drop-in obedece às MESMAS invariantes do main.conf
#
# ACHADO MÉDIA de 06/08/2026: `aplicar` gravava `main.conf.d/*.conf` com
# `install -Dm644` — sem `cmp`, sem backup, sem aviso — e `remover` fazia `rm -f`
# sem backup. Um arquivo editado à mão nesse caminho era destruído SEM CÓPIA
# NENHUMA, enquanto a mesma função imprimia "drop-ins de main.conf.d gravados"
# como sucesso. Não era regressão (o código inline antigo do install fazia
# igual), mas o arquivo passou a se declarar DONO ÚNICO e a enunciar invariantes
# no cabeçalho que esse caminho violava.
# ---------------------------------------------------------------------------

_DROPIN_DELA = (
    "# escrito à mão por ela em 03/08\n"
    "[General]\n"
    "JustWorksRepairing=never\n"
    "FastConnectable=false\n"
)


def _backups_de_dropin(etc: Path) -> list[Path]:
    return sorted((etc / "main.conf.d").glob("*.bak.hefesto-dropin-*"))


def test_aplicar_nao_destroi_dropin_editado_a_mao(tmp_path: Path) -> None:
    """Reescrever por cima sem cópia é apagar decisão dela — no outro caminho.

    O drop-in tem o NOSSO nome, e é justamente por isso que ela o editaria: é o
    arquivo que a documentação manda olhar. A invariante do `main.conf` vale
    aqui inteira — `cmp`, backup, aviso — e o valor que sobrevive é o nosso.
    """
    etc = _etc(tmp_path, MAIN_CONF_DELA, com_dropin_dir=True)
    alvo = etc / "main.conf.d" / "hefesto-justworks.conf"
    alvo.write_text(_DROPIN_DELA, encoding="utf-8")

    proc = _rodar(etc, "aplicar")

    assert proc.returncode == 0, proc.stderr
    guardados = [b.read_text(encoding="utf-8") for b in _backups_de_dropin(etc)]
    assert _DROPIN_DELA in guardados, (
        "o aplicar reescreveu um drop-in editado à mão SEM guardar cópia: "
        f"backups encontrados = {[b.name for b in _backups_de_dropin(etc)]}"
    )
    assert "hefesto-justworks.conf" in proc.stdout
    assert "conteúdo DIFERENTE do nosso" in proc.stdout, (
        "o arquivo dela foi reescrito em silêncio"
    )
    # E o resultado é o nosso valor: guardar cópia não é desistir de curar.
    # Pelo ORÁCULO, não por `in`: o asset escreve `JustWorksRepairing = confirm`
    # com espaços, e quem decide o que isso vale é o GKeyFile.
    assert _oraculo(alvo) == "confirm"


def test_remover_nao_apaga_dropin_editado_a_mao_sem_copia(tmp_path: Path) -> None:
    """A mesma invariante pelo outro lado: `rm -f` sem backup é perda líquida."""
    etc = _etc(tmp_path, MAIN_CONF_DELA, com_dropin_dir=True)
    alvo = etc / "main.conf.d" / "hefesto-justworks.conf"
    alvo.write_text(_DROPIN_DELA, encoding="utf-8")

    proc = _rodar(etc, "remover")

    assert not alvo.exists(), "o remover deixou o drop-in para trás"
    guardados = [b.read_text(encoding="utf-8") for b in _backups_de_dropin(etc)]
    assert _DROPIN_DELA in guardados, (
        "o remover apagou um drop-in editado à mão SEM guardar cópia: "
        f"backups encontrados = {[b.name for b in _backups_de_dropin(etc)]}"
    )
    assert "conteúdo DIFERENTE do nosso" in proc.stdout


def test_dropin_igual_ao_nosso_asset_nao_gera_backup(tmp_path: Path) -> None:
    """A EXCEÇÃO DECLARADA — e a linha de base dos dois testes acima.

    Igual byte a byte ao asset = nada a perder (o asset está versionado). Sem
    esta metade, uma implementação que fizesse backup de TUDO passaria nos dois
    testes acima e encheria o `main.conf.d` dela de cópias a cada `install.sh`.
    """
    etc = _etc(tmp_path, MAIN_CONF_DELA, com_dropin_dir=True)

    _rodar(etc, "aplicar")
    assert _backups_de_dropin(etc) == [], "a primeira gravação gerou backup do nada"
    _rodar(etc, "aplicar")
    _rodar(etc, "remover")

    assert _backups_de_dropin(etc) == [], (
        "aplicar/aplicar/remover com o nosso próprio conteúdo gerou backup de "
        f"drop-in: {[b.name for b in _backups_de_dropin(etc)]}"
    )


# ---------------------------------------------------------------------------
# 4. O uninstall devolve o arquivo sem chave nossa
# ---------------------------------------------------------------------------


def test_remover_devolve_o_arquivo_sem_chave_nossa(tmp_path: Path) -> None:
    """Ciclo completo: aplicar → remover tem de devolver o arquivo ORIGINAL.

    Byte a byte. Um uninstall que deixa a linha em branco separadora órfã (o
    achado 4-C) ou que come o `[General]` reprova aqui.
    """
    original = "[General]\nName = BlueZ\n\n[Policy]\nAutoEnable=true\n"
    etc = _etc(tmp_path, original)

    _rodar(etc, "aplicar")
    assert _valor(etc) == "confirm"
    proc = _rodar(etc, "remover")

    assert proc.returncode == 0, proc.stderr
    assert (etc / "main.conf").read_text(encoding="utf-8") == original, (
        "o remover não devolveu o main.conf ao estado original"
    )
    assert _valor(etc) is None, "sobrou chave nossa depois do remover"


def test_remover_devolve_a_chave_de_terceiro(tmp_path: Path) -> None:
    """Instalar+desinstalar não pode ser destrutivo líquido sobre config alheia.

    O `awk` antigo do install APAGAVA `JustWorksRepairing = never` de quem
    tivesse escolhido a opção mais segura do template, e o uninstall — que só
    conhecia sentinelas — nunca a devolvia.
    """
    original = "[General]\nJustWorksRepairing = never\nName = BlueZ\n"
    etc = _etc(tmp_path, original)

    _rodar(etc, "aplicar")
    _rodar(etc, "remover")

    assert (etc / "main.conf").read_text(encoding="utf-8") == original


def test_remover_tira_os_dropins(tmp_path: Path) -> None:
    """Simetria do caminho A: o que o aplicar grava em main.conf.d, o remover tira."""
    etc = _etc(tmp_path, MAIN_CONF_DELA, com_dropin_dir=True)
    _rodar(etc, "aplicar")
    _rodar(etc, "remover")

    assert not (etc / "main.conf.d" / "hefesto-justworks.conf").exists()
    assert not (etc / "main.conf.d" / "hefesto-fastconnectable.conf").exists()


def test_remover_deixa_um_unico_backup_mesmo_com_tres_blocos(tmp_path: Path) -> None:
    """Os três removedores antigos faziam um `cp` cada — três arquivos por execução."""
    etc = _etc(
        tmp_path,
        "[General]\n"
        "# >>> hefesto FastConnectable >>>\nFastConnectable=true\n"
        "# <<< hefesto FastConnectable <<<\n"
        "# >>> hefesto JustWorksRepairing >>>\nJustWorksRepairing = always\n"
        "# <<< hefesto JustWorksRepairing <<<\n"
        "# >>> hefesto bluetooth >>>\nJustWorksRepairing=confirm\n"
        "# <<< hefesto bluetooth <<<\n",
    )
    _rodar(etc, "remover")

    assert len(_backups(etc)) == 1, "uma remoção deixou mais de um backup"


def test_remover_duas_vezes_nao_gera_backup_novo(tmp_path: Path) -> None:
    """O `cmp` vale para os dois lados — remover o que já saiu é no-op honesto."""
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    _rodar(etc, "remover")
    apos = _backups(etc)
    _rodar(etc, "remover")

    assert _backups(etc) == apos


# ---------------------------------------------------------------------------
# 5. A faixa sem fechamento — o `sed` que apagava até o fim do arquivo
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("modo", ["aplicar", "remover"])
def test_sentinela_sem_fechamento_nao_come_o_resto_do_arquivo(
    tmp_path: Path, modo: str
) -> None:
    """`sed '/A/,/B/d'` sem B apaga ATÉ O FIM. Aqui a resposta é RECUSAR.

    O removedor antigo do uninstall ancorava o fechamento em `$`: um espaço em
    branco no fim de `# <<< hefesto bluetooth <<<` bastava para a faixa nunca
    fechar. Num main.conf com conteúdo depois do bloco, o estrago não é contido.
    """
    conteudo = (
        "[General]\n"
        "# >>> hefesto bluetooth >>>\n"
        "JustWorksRepairing=confirm\n"
        "ConteudoDeTerceiroDepoisDoBloco=1\n"
    )
    etc = _etc(tmp_path, conteudo)
    proc = _rodar(etc, modo)

    assert proc.returncode != 0, f"{modo} aceitou uma faixa sem fechamento"
    assert (etc / "main.conf").read_text(encoding="utf-8") == conteudo, (
        "o arquivo foi tocado apesar da recusa"
    )
    assert "sem fechamento" in proc.stderr


def test_aplicar_que_recusa_nao_anuncia_garantia(tmp_path: Path) -> None:
    """Anunciar sucesso depois de recusar é o defeito de comunicação da sprint."""
    etc = _etc(
        tmp_path, "[General]\n# >>> hefesto bluetooth >>>\nJustWorksRepairing=always\n"
    )
    proc = _rodar(etc, "aplicar")

    assert proc.returncode != 0
    assert "garantidos" not in proc.stdout


# ---------------------------------------------------------------------------
# 6. Backup: contar é automático, APAGAR nunca é
#
# A primeira versão desta entrega podava dentro do `aplicar`. MEDIDO por
# simulação só-leitura do pipeline exato contra o /etc/bluetooth dela: a
# PRIMEIRA execução apagaria 27 dos 37 backups, entre eles
# `main.conf.bak.hefesto-1784672963` (404 linhas, 14797 bytes, 21/07 19:29) e
# `main.conf.bak.hefesto-1784694261` (3 linhas, 59 bytes, 22/07 01:24) — os dois
# pontos de medição do colapso que a sprint RADIO-ABERTO-01 registra como
# suspeita EM ABERTO, sem cura. Retenção por mtime descarta primeiro o que tem
# MAIS valor: o estado pré-hefesto e o instante do estrago.
# ---------------------------------------------------------------------------

#: Os dois arquivos que a poda automática apagaria primeiro, com os tamanhos e
#: as datas MEDIDOS. Reproduzir os nomes é de propósito: se alguém devolver a
#: poda automática, o teste falha citando a evidência pelo nome real.
_PRE_COLAPSO = "main.conf.bak.hefesto-1784672963"      # 404 linhas, 21/07 19:29
_POS_COLAPSO = "main.conf.bak.hefesto-1784694261"      # 3 linhas, 22/07 01:24


def _povoar_como_a_maquina_dela(etc: Path, quantos: int = 37) -> list[Path]:
    """37 backups, com os dois pontos do colapso entre os MAIS ANTIGOS."""
    criados: list[Path] = []
    momento = 1_784_600_000

    pre = etc / _PRE_COLAPSO
    pre.write_text("linha\n" * 404, encoding="utf-8")
    os.utime(pre, (momento, momento))
    criados.append(pre)

    pos = etc / _POS_COLAPSO
    pos.write_text(
        "[General]\nFastConnectable=true\nJustWorksRepairing=always\n", encoding="utf-8"
    )
    os.utime(pos, (momento + 60, momento + 60))
    criados.append(pos)

    for i in range(quantos - 2):
        alvo = etc / f"main.conf.bak.hefesto-17861{i:05d}"
        # Conteúdo REPETIDO de propósito: são os pós-colapso (de 11 a 1395
        # bytes) que a retenção por mtime guardaria por serem os mais recentes.
        alvo.write_text("[General]\n", encoding="utf-8")
        os.utime(alvo, (momento + 3600 + i * 60, momento + 3600 + i * 60))
        criados.append(alvo)
    return criados


def test_aplicar_nao_apaga_backup_nenhum(tmp_path: Path) -> None:
    """A EVIDÊNCIA NÃO SAI. Nem um arquivo, nem com 37 no diretório.

    "Não se apaga decisão medida" — e os dois pontos do colapso são a única
    medição que existe do único estrago deste projeto ainda sem explicação.
    """
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    antes = _povoar_como_a_maquina_dela(etc)

    proc = _rodar(etc, "aplicar", manter="10")

    assert proc.returncode == 0, proc.stderr
    for backup in antes:
        assert backup.exists(), f"o aplicar apagou {backup.name} — isso é evidência medida"
    assert (etc / _PRE_COLAPSO).read_text(encoding="utf-8").count("\n") == 404
    # 37 preservados + 1 novo (a aplicação mudou o arquivo).
    assert len(_backups(etc)) == 38
    assert "nenhum é apagado automaticamente" in proc.stdout


def test_remover_nao_apaga_backup_nenhum(tmp_path: Path) -> None:
    """O mesmo pelo outro lado: desinstalar também não é hora de faxina."""
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    antes = _povoar_como_a_maquina_dela(etc)

    _rodar(etc, "remover", manter="10")

    for backup in antes:
        assert backup.exists(), f"o remover apagou {backup.name}"


def test_podar_por_padrao_so_simula(tmp_path: Path) -> None:
    """`podar` sem argumento NÃO apaga: diz o que sairia, e para por aí."""
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    antes = _povoar_como_a_maquina_dela(etc)

    proc = _rodar(etc, "podar", manter="10")

    assert proc.returncode == 0, proc.stderr
    for backup in antes:
        assert backup.exists(), "o dry-run apagou arquivo"
    assert "poda SIMULADA" in proc.stdout
    assert "--aplicar" in proc.stdout


def test_podar_nunca_apaga_o_mais_antigo(tmp_path: Path) -> None:
    """O mais antigo é o estado mais próximo do pré-hefesto. Fica, sempre."""
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    _povoar_como_a_maquina_dela(etc)

    proc = _rodar(etc, "podar", manter="1", arg="--aplicar")

    assert proc.returncode == 0, proc.stderr
    assert (etc / _PRE_COLAPSO).exists(), "a poda apagou o backup MAIS ANTIGO"
    assert "MAIS ANTIGO nunca sai" in proc.stdout


def test_podar_nunca_apaga_backup_de_conteudo_unico(tmp_path: Path) -> None:
    """Conteúdo único = única cópia daquele estado. É o instante do estrago.

    Com retenção 1, tudo menos o mais recente vira candidato. O que segura os
    dois pontos do colapso não é a retenção — é a proteção por ESTADO.
    """
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    _povoar_como_a_maquina_dela(etc)

    proc = _rodar(etc, "podar", manter="1", arg="--aplicar")

    assert (etc / _POS_COLAPSO).exists(), (
        "a poda apagou o backup de 3 linhas — o instante do estrago, e a única "
        "cópia daquele estado do main.conf dela"
    )
    assert "ÚNICA cópia deste conteúdo" in proc.stdout
    # E o que saiu foi só o que tinha cópia byte a byte em outro arquivo.
    assert len(_backups(etc)) < 37


def test_podar_nunca_faz_um_estado_sumir_do_disco(tmp_path: Path) -> None:
    """A promessa é sobre ESTADO, não sobre arquivo — e a regra velha não era.

    O CENÁRIO QUE IMPORTA e que nenhum teste exercitava: vários estados
    distintos, cada um com POUCAS cópias, TODAS fora da janela de retenção. A
    proteção anterior era "nenhum OUTRO backup tem os mesmos bytes", isto é, por
    ARQUIVO: um conteúdo repetido em três cópias não era "único" nenhuma vez, as
    três viravam candidatas juntas, e aquele estado do `main.conf` dela sumia do
    disco por completo — enquanto a última linha impressa dizia "os de conteúdo
    único ficam sempre", que se lê como promessa de estado.

    Aqui são 3 estados de 3 cópias cada, com retenção 1. O estado do MEIO é o que a regra
    velha aniquilava: nenhuma das três cópias dele é a mais nova (a retenção
    salva o estado de cima) nem a mais antiga (essa salva o de baixo).
    """
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    momento = 1_784_600_000
    estados = {
        "antigo": "[General]\n# estado A — o mais próximo do pré-hefesto\n",
        "meio": "[General]\nJustWorksRepairing=always\n# estado B — o do meio\n",
        "novo": "[General]\nJustWorksRepairing=confirm\n# estado C\n",
    }
    i = 0
    for nome, conteudo in estados.items():
        for _copia in range(3):
            alvo = etc / f"main.conf.bak.hefesto-{1786100000 + i}"
            alvo.write_text(conteudo, encoding="utf-8")
            os.utime(alvo, (momento + i * 60, momento + i * 60))
            i += 1
        assert nome  # o nome existe para o leitor, não para a asserção

    antes = {b.read_bytes() for b in _backups(etc)}
    assert len(antes) == 3, "a fixture tem de ter TRÊS estados distintos"

    proc = _rodar(etc, "podar", manter="1", arg="--aplicar")

    assert proc.returncode == 0, proc.stderr
    depois = {b.read_bytes() for b in _backups(etc)}
    sumidos = antes - depois
    assert sumidos == set(), (
        "a poda fez um ESTADO do main.conf dela desaparecer inteiro do disco "
        f"({len(sumidos)} de {len(antes)}): "
        f"{[c.decode('utf-8').splitlines()[1] for c in sorted(sumidos)]}. "
        "A proteção era por ARQUIVO ('nenhum outro tem os mesmos bytes') e a "
        "frase impressa prometia ESTADO."
    )
    # E a poda AINDA PODA: um teste que passasse com a poda desligada não
    # provaria nada. Das 9 cópias saem as 6 que têm irmã idêntica sobrevivendo.
    assert len(_backups(etc)) == 3, (
        f"sobraram {len(_backups(etc))} de 9 — a poda parou de podar"
    )
    # A cópia que fica de cada estado é a MAIS ANTIGA dele: entre bytes iguais,
    # a de mtime menor é a que diz quando aquele estado apareceu.
    assert "ÚNICA cópia deste conteúdo" in proc.stdout


def test_podar_nao_toca_backup_que_nao_e_nosso(tmp_path: Path) -> None:
    """Há um backup de OUTRA ferramenta em /etc/bluetooth que não é nosso.

    Retenção que apaga o que não escreveu é perda de dado alheio.
    """
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    alheio = etc / "main.conf.bak.outra-ferramenta-1784689791"
    alheio.write_text("nao-e-nosso\n", encoding="utf-8")
    _povoar_como_a_maquina_dela(etc)

    _rodar(etc, "podar", manter="1", arg="--aplicar")

    assert alheio.exists(), "a poda apagou backup de terceiro"
    assert alheio.read_text(encoding="utf-8") == "nao-e-nosso\n"


def test_retencao_zero_desliga_a_poda(tmp_path: Path) -> None:
    """A retenção é declarada: `0` significa "não apague nada", e tem de valer."""
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    _povoar_como_a_maquina_dela(etc)

    proc = _rodar(etc, "podar", manter="0", arg="--aplicar")

    assert len(_backups(etc)) == 37
    assert "poda desligada" in proc.stdout


def test_podar_com_argumento_desconhecido_recusa(tmp_path: Path) -> None:
    """`podar --forca-tudo` não pode virar `podar --aplicar` por engano."""
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    _povoar_como_a_maquina_dela(etc)

    proc = _rodar(etc, "podar", arg="--forca-tudo")

    assert proc.returncode == 2
    assert len(_backups(etc)) == 37


def test_podar_nao_anuncia_remocao_que_nao_aconteceu(tmp_path: Path) -> None:
    """O `|| true` engolia a falha do `rm` e a frase de sucesso saía igual.

    Diretório sem permissão de escrita: o `rm` falha, e o script tem de DIZER
    que falhou — anunciar remoção que não houve é mentir sobre o disco dela.
    """
    if os.geteuid() == 0:
        pytest.skip("como root o modo do diretório não impede o rm")
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    _povoar_como_a_maquina_dela(etc)
    etc.chmod(0o555)
    try:
        proc = _rodar(etc, "podar", manter="10", arg="--aplicar")
    finally:
        etc.chmod(0o755)

    assert proc.returncode != 0, "a poda falhou em tudo e mesmo assim saiu com 0"
    assert "não consegui remover" in proc.stderr
    assert "0 de 37 backup(s) removido(s)" in proc.stdout


# ---------------------------------------------------------------------------
# 7. `verificar` — o modo de leitura que o doctor consome
# ---------------------------------------------------------------------------


def test_verificar_acusa_o_estado_da_maquina_dela(tmp_path: Path) -> None:
    """Antes desta entrega, NADA no projeto sabia dizer que a máquina estava assim."""
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    proc = _rodar(etc, "verificar")

    assert proc.returncode != 0
    assert "JustWorksRepairing: always" in proc.stdout
    assert "veredito: INSEGURO" in proc.stdout


def test_verificar_nao_escreve_nada(tmp_path: Path) -> None:
    """Modo de leitura que escreve não é modo de leitura."""
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    antes = (etc / "main.conf").read_bytes()
    listagem_antes = sorted(p.name for p in etc.iterdir())

    _rodar(etc, "verificar")

    assert (etc / "main.conf").read_bytes() == antes
    assert sorted(p.name for p in etc.iterdir()) == listagem_antes


def test_verificar_aprova_depois_do_aplicar(tmp_path: Path) -> None:
    """Linha de base — sem ela, um verificador que reprova tudo 'passaria'."""
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    _rodar(etc, "aplicar")
    proc = _rodar(etc, "verificar")

    assert proc.returncode == 0
    assert "veredito: OK" in proc.stdout


def test_sem_bluez_nada_explode(tmp_path: Path) -> None:
    """Máquina sem BlueZ: os três modos saem em paz, sem criar arquivo."""
    etc = _etc(tmp_path)
    for modo in ("aplicar", "remover", "verificar"):
        proc = _rodar(etc, modo)
        assert proc.returncode == 0, f"{modo}: {proc.stderr}"
    assert not (etc / "main.conf").exists()


# ---------------------------------------------------------------------------
# 8. Fiação e invariantes de segurança do próprio script
# ---------------------------------------------------------------------------


def test_o_script_e_executavel_e_tem_sintaxe_valida() -> None:
    """Contrato dos scripts desta casa, e aqui vale dobrado: install e
    uninstall passaram a DEPENDER dele."""
    assert SCRIPT.stat().st_mode & 0o111, "bluez_config.sh não é executável"
    proc = subprocess.run(
        ["bash", "-n", str(SCRIPT)], capture_output=True, text=True, timeout=60
    )
    assert proc.returncode == 0, proc.stderr


def test_modo_desconhecido_nao_faz_nada(tmp_path: Path) -> None:
    """Um erro de digitação no chamador não pode virar reescrita silenciosa."""
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    antes = (etc / "main.conf").read_bytes()
    proc = _rodar(etc, "aplicarr")

    assert proc.returncode == 2
    assert (etc / "main.conf").read_bytes() == antes


def test_install_chama_o_aplicar_e_uninstall_chama_o_remover() -> None:
    """A bancada só vale se o install/uninstall usarem MESMO este mecanismo."""
    assert "scripts/bluez_config.sh\" aplicar" in INSTALL.read_text(encoding="utf-8")
    assert "scripts/bluez_config.sh\" remover" in UNINSTALL.read_text(encoding="utf-8")


def test_o_script_nunca_reinicia_o_bluetoothd() -> None:
    """Provado ao vivo em 2026-07-17: restart derruba os controles conectados."""
    fonte = SCRIPT.read_text(encoding="utf-8")
    assert "systemctl" not in fonte
    assert "bluetoothctl" not in fonte


def test_o_script_diz_com_todas_as_letras_quando_a_mudanca_vale(tmp_path: Path) -> None:
    """Ela precisa saber que o `confirm` só vale no próximo boot."""
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    proc = _rodar(etc, "aplicar")

    assert "PRÓXIMO BOOT" in proc.stdout
    assert "NÃO reiniciamos o bluetoothd" in proc.stdout


def test_todo_caminho_deriva_da_raiz_configuravel() -> None:
    """A bancada é segura porque NENHUM caminho é literal.

    `/etc/bluetooth` só pode aparecer como valor PADRÃO de `HEFESTO_BT_ETC`.
    Um literal solto significaria que algum modo escreve em /etc mesmo com a
    raiz falsa — e a suíte passaria a mexer na máquina dela.
    """
    fonte = SCRIPT.read_text(encoding="utf-8")
    codigo = [
        ln for ln in fonte.splitlines()
        if not ln.lstrip().startswith("#") and "/etc/bluetooth" in ln
    ]
    assert codigo == ['ETC="${HEFESTO_BT_ETC:-/etc/bluetooth}"'], (
        f"caminho literal de /etc fora do padrão configurável: {codigo}"
    )


# ---------------------------------------------------------------------------
# 9. A escrita é ATÔMICA — o beco sem saída que a versão anterior podia criar
#
# `install -m644 tmp /etc/bluetooth/main.conf` escreve NO LUGAR (mesmo inode,
# O_TRUNC). Disco cheio, queda de energia ou um kill no meio deixavam o
# main.conf DELA truncado — e como o bloco fica no FIM, o corte cai DENTRO dele:
# sobra sentinela de abertura sem fechamento, e a partir daí `aplicar` E
# `remover` RECUSAM para sempre, com o doctor mandando rodar exatamente o que
# não pode funcionar.
# ---------------------------------------------------------------------------


def _shim(tmp_path: Path, alvo: Path, comandos: tuple[str, ...], corta: bool) -> Path:
    """Sabota SÓ o que escreve DIRETO no arquivo vivo; o resto passa reto.

    `corta=True` simula a queda no meio da escrita (trunca o destino e sai com
    erro). `corta=False` simula a falha limpa (não escreve nada e sai com erro).
    """
    pasta = tmp_path / f"shim-{'corte' if corta else 'falha'}"
    pasta.mkdir(exist_ok=True)
    for nome in comandos:
        real = shutil.which(nome)
        assert real, f"sem {nome} nesta máquina"
        corpo = "    head -c 60 \"${@: -2:1}\" > \"${alvo}\" 2>/dev/null || true\n" if corta else ""
        (pasta / nome).write_text(
            "#!/usr/bin/env bash\n"
            'alvo="${@: -1}"\n'
            f'if [[ "${{alvo}}" == "{alvo}" ]]; then\n'
            f"{corpo}"
            "    exit 1\n"
            "fi\n"
            f'exec {real} "$@"\n',
            encoding="utf-8",
        )
        (pasta / nome).chmod(0o755)
    return pasta


def test_escrita_interrompida_nao_trunca_o_main_conf(tmp_path: Path) -> None:
    """Nenhuma escrita cai DIRETO sobre o main.conf vivo — nem uma.

    O shim corta pela metade qualquer `cp`/`install` cujo destino seja o
    arquivo vivo. Com a troca atômica, nada nunca tem esse destino: o conteúdo
    novo nasce num temporário do mesmo diretório e entra por `mv`.
    """
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    original = (etc / "main.conf").read_text(encoding="utf-8")
    pasta = _shim(tmp_path, etc / "main.conf", ("cp", "install"), corta=True)

    proc = _rodar(etc, "aplicar", path_extra=pasta)
    texto = (etc / "main.conf").read_text(encoding="utf-8")

    assert texto != original[:60], "o main.conf dela ficou TRUNCADO no meio do bloco"
    assert proc.returncode == 0, proc.stderr
    assert texto.count("# >>> hefesto bluetooth >>>") == 1
    assert "# <<< hefesto bluetooth <<<" in texto, (
        "o arquivo ficou com sentinela de abertura sem fechamento — a partir "
        "daqui aplicar E remover recusam para sempre"
    )
    # E a prova de que o beco não existe: dá para rodar de novo.
    assert _rodar(etc, "aplicar").returncode == 0


def test_falha_na_troca_atomica_devolve_o_arquivo_intacto(tmp_path: Path) -> None:
    """Falha no `mv` = nada aconteceu. O arquivo dela sobrevive BYTE A BYTE."""
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    original = (etc / "main.conf").read_bytes()
    pasta = _shim(tmp_path, etc / "main.conf", ("mv",), corta=False)

    proc = _rodar(etc, "aplicar", path_extra=pasta)

    assert proc.returncode != 0, "a troca falhou e o script disse que deu certo"
    assert (etc / "main.conf").read_bytes() == original, (
        "o main.conf mudou apesar de a escrita ter falhado"
    )
    assert "INTACTO" in proc.stderr
    assert "garantidos" not in proc.stdout
    # O backup daquele estado existe, e é o que sobra quando algo dá errado.
    assert len(_backups(etc)) == 1


def _sobras(etc: Path) -> list[str]:
    return sorted(p.name for p in etc.iterdir() if "hefesto-novo" in p.name)


def test_a_troca_atomica_nao_deixa_temporario_quando_o_mv_fracassa(tmp_path: Path) -> None:
    """ESTE TESTE NÃO MORDIA (achado de 06/08/2026, MEDIDO).

    A versão anterior rodava um `aplicar` que dava CERTO e conferia que não
    havia sobra. Num `aplicar` bem-sucedido o `mv` LEVA o temporário embora — não
    há sobra possível, com ou sem limpeza no código. O teste passava verde com a
    cura arrancada, que é o pior tipo de cobertura: a falsa.

    O caminho que precisa de limpeza é o do FRACASSO. Aqui o `mv` falha, e é aí
    que o temporário sobraria em /etc/bluetooth — no conffile dela, sem ninguém
    para contar nem varrer.

    A MORDIDA (MEDIDA): há DOIS mecanismos cobrindo este caminho — o `rm -f`
    explícito e o `trap` de saída. Arrancar só um deixa este teste verde, porque
    o outro segura a INVARIANTE, que é o que se testa aqui; arrancar os dois o
    deixa vermelho. Quem quiser ver o `trap` morder sozinho tem o
    `test_um_kill_no_meio_da_troca_nao_deixa_temporario`, onde não há `rm -f`
    nenhum para salvar.
    """
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    pasta = _shim(tmp_path, etc / "main.conf", ("mv",), corta=False)

    proc = _rodar(etc, "aplicar", path_extra=pasta)

    assert proc.returncode != 0, "a troca falhou e o script disse que deu certo"
    assert _sobras(etc) == [], (
        f"a troca atômica falhou e deixou temporário para trás: {_sobras(etc)}"
    )


def test_um_kill_no_meio_da_troca_nao_deixa_temporario(tmp_path: Path) -> None:
    """O `trap` que não existia: um kill entre o `mktemp` e o `mv`.

    ACHADO DE 06/08/2026: não havia `trap` nenhum no script. Um SIGTERM (ou um
    Ctrl-C) depois do `mktemp` do temporário deixava
    `.main.conf.hefesto-novo.XXXXXX` órfão em /etc/bluetooth, e nada o contava
    nem o varria.

    O shim aqui é um `chmod` que mata o PRÓPRIO script — mas SÓ quando o alvo é
    o temporário da troca, que é o instante exato do intervalo, entre o
    temporário nascer e o `mv` acontecer. Mirar em `chmod` qualquer NÃO serve: o
    primeiro da execução é o do BACKUP, e ali o temporário ainda nem existe — o
    teste passava sem exercitar nada (foi o primeiro desenho deste teste, e a
    mutação "tira o trap" o deixou verde).
    """
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    original = (etc / "main.conf").read_bytes()
    pasta = tmp_path / "shim-kill"
    pasta.mkdir()
    real = shutil.which("chmod")
    assert real, "sem chmod nesta máquina"
    (pasta / "chmod").write_text(
        "#!/usr/bin/env bash\n"
        'if [[ "${@: -1}" == *".main.conf.hefesto-novo."* ]]; then\n'
        '    kill -TERM "${PPID}"\n'
        "    sleep 5\n"
        "    exit 1\n"
        "fi\n"
        f'exec {real} "$@"\n',
        encoding="utf-8",
    )
    (pasta / "chmod").chmod(0o755)

    proc = _rodar(etc, "aplicar", path_extra=pasta)

    assert proc.returncode != 0, "o script morreu de TERM e anunciou sucesso"
    assert _sobras(etc) == [], (
        f"o kill no meio da troca deixou temporário órfão: {_sobras(etc)} — é o "
        "trap que não existia"
    )
    assert (etc / "main.conf").read_bytes() == original, (
        "o main.conf mudou apesar de o script ter morrido antes do mv"
    )


def test_verificar_reporta_temporario_orfao(tmp_path: Path) -> None:
    """O que um SIGKILL deixar para trás, alguém tem de saber contar.

    `kill -9` não tem trap. O que já está no disco dela hoje também não teve.
    Reportar é obrigação; apagar não fazemos — um temporário órfão pode ser a
    única cópia do que a máquina tentou gravar quando morreu.
    """
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    orfao = etc / ".main.conf.hefesto-novo.aBc123"
    orfao.write_text("[General]\n", encoding="utf-8")

    proc = _rodar(etc, "verificar")

    assert "temporarios-orfaos: 1" in proc.stdout, (
        "o verificador não conta os temporários órfãos que o script pode ter "
        "deixado em /etc/bluetooth"
    )
    assert f"temporario-orfao: {orfao}" in proc.stdout, "não nomeia o órfão"
    assert orfao.exists(), "o verificar APAGOU o órfão — modo de leitura não apaga"


def test_backup_de_zero_byte_nao_conta_como_backup(tmp_path: Path) -> None:
    """O backup nasce vazio do `mktemp`; um SIGKILL antes do `cp` o deixa assim.

    E SIGKILL não tem trap — a limpeza que cobre INT/TERM/HUP não roda. O que
    ficava no disco era um `main.conf.bak.hefesto-...` de ZERO byte que o
    `verificar` contava dentro de `backups-hefesto:` como legítimo e o
    `_resumo_backups` somava na frase do `aplicar`. Ela lia "há backup" onde não
    havia cópia nenhuma do estado do arquivo — e essa frase é justamente a que
    autoriza mexer no conffile.

    O temporário órfão já tinha relatório próprio (`temporarios-orfaos:`); o
    backup vazio não tinha nenhum. Aqui ele deixa de contar E passa a ser dito.
    """
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    vivo = etc / "main.conf.bak.hefesto-1786000001"
    vivo.write_text("[General]\nJustWorksRepairing=always\n", encoding="utf-8")
    morto = etc / "main.conf.bak.hefesto-1786000002"
    morto.touch()
    assert morto.stat().st_size == 0

    proc = _rodar(etc, "verificar")

    assert "backups-hefesto: 1" in proc.stdout, (
        "o backup de ZERO byte foi contado como backup — ela lê 2 e tem 1"
    )
    assert "backups-suspeitos: 1" in proc.stdout, "o vazio sumiu da conta e da vista"
    assert f"backup-suspeito: {morto}" in proc.stdout, "não nomeia o suspeito"
    assert morto.exists(), "o verificar APAGOU o suspeito — modo de leitura não apaga"


def test_o_resumo_do_aplicar_nao_soma_backup_vazio(tmp_path: Path) -> None:
    """A mesma conta na frase que o `aplicar` imprime, que é a que ela lê."""
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    (etc / "main.conf.bak.hefesto-1786000001").write_text("[General]\n", encoding="utf-8")
    (etc / "main.conf.bak.hefesto-1786000002").touch()

    proc = _rodar(etc, "aplicar")

    assert proc.returncode == 0, proc.stderr
    # 1 preexistente com conteúdo + 1 novo (o aplicar mudou o arquivo) = 2.
    assert "2 arquivo(s)" in proc.stdout, (
        f"a frase do resumo somou o backup vazio: {proc.stdout}"
    )
    assert "ZERO byte" in proc.stdout, (
        "o vazio saiu da conta em SILÊNCIO — trocar número errado por silêncio "
        "não é cura"
    )


def test_a_poda_nao_alcanca_backup_vazio(tmp_path: Path) -> None:
    """Não conta como backup, então não é candidato — e continua no disco.

    Mesma regra dos temporários órfãos: reportar é obrigação, apagar não
    fazemos. Um arquivo de 0 byte também é a marca de uma execução que morreu.
    """
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    _povoar_como_a_maquina_dela(etc)
    morto = etc / "main.conf.bak.hefesto-1786099999"
    morto.touch()

    _rodar(etc, "podar", manter="1", arg="--aplicar")

    assert morto.exists(), "a poda apagou um arquivo que ela nem contava"


def test_o_temporario_do_remover_sai_de_mktemp(tmp_path: Path) -> None:
    """Sufixo fixo (`${tmp}.devolvido`) é nome previsível e sem O_EXCL."""
    codigo = [
        ln for ln in SCRIPT.read_text(encoding="utf-8").splitlines()
        if not ln.lstrip().startswith("#")
    ]
    assert not [ln for ln in codigo if ".devolvido" in ln], (
        "o remover voltou ao temporário de sufixo fixo, sem mktemp e sem O_EXCL"
    )
    assert any('devolvido="$(mktemp)"' in ln for ln in codigo)


# ---------------------------------------------------------------------------
# 10. O que a ferramenta DIZ antes de mexer no arquivo de alguém
# ---------------------------------------------------------------------------


def test_aplicar_nomeia_linha_de_terceiro_dentro_do_bloco(tmp_path: Path) -> None:
    """Dentro das sentinelas é o lugar mais óbvio para alguém escrever.

    O bloco inteiro é reescrito, então o que estiver ali dentro SAI. Sair em
    silêncio é o que não pode: `ControllerMode`/`MultiProfile` são exatamente o
    que se põe num main.conf por causa de fone/headset.
    """
    etc = _etc(
        tmp_path,
        "[General]\n"
        "# >>> hefesto bluetooth >>>\n"
        "[General]\n"
        "FastConnectable=true\n"
        "JustWorksRepairing=always\n"
        "ControllerMode = bredr\n"
        "MultiProfile = multiple\n"
        "# <<< hefesto bluetooth <<<\n",
    )
    proc = _rodar(etc, "aplicar")

    assert proc.returncode == 0, proc.stderr
    assert "ControllerMode = bredr" in proc.stdout, "a linha alheia saiu em silêncio"
    assert "MultiProfile = multiple" in proc.stdout
    assert "FORA das sentinelas" in proc.stdout
    # E o comentário do nosso próprio bloco não vira alarme falso.
    assert "sai do arquivo: #" not in proc.stdout


def test_bloco_so_com_o_nosso_conteudo_nao_gera_alarme(tmp_path: Path) -> None:
    """Aviso que sai sempre é aviso que ninguém lê."""
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    proc = _rodar(etc, "aplicar")

    assert "sai do arquivo" not in proc.stdout


def test_remover_grita_o_always_que_devolve(tmp_path: Path) -> None:
    """O `aplicar` grita ao CORRIGIR; o `remover` era mudo ao DEVOLVER.

    Correção silenciosa foi o que deixou o `always` viver quatro dias. A
    operação inversa, muda, devolve ao estado ATIVO o valor que esta mesma
    sprint classifica como injeção de teclas.
    """
    etc = _etc(tmp_path, "[General]\nJustWorksRepairing = always\nName = BlueZ\n")
    _rodar(etc, "aplicar")

    proc = _rodar(etc, "remover")

    assert proc.returncode == 0, proc.stderr
    assert "always" in proc.stdout
    assert "INJEÇÃO DE TECLAS" in proc.stdout
    assert "RADIO-ABERTO-01" in proc.stdout
    assert _valor(etc) == "always", "a linha dela não voltou (o remover apagou config alheia)"


def test_remover_diz_quando_a_chave_deixa_de_existir(tmp_path: Path) -> None:
    """Sem bloco nosso e sem linha dela, quem manda é o default da distro."""
    etc = _etc(tmp_path, "[General]\nName = BlueZ\n")
    _rodar(etc, "aplicar")

    proc = _rodar(etc, "remover")

    assert "default da distro" in proc.stdout


def test_aplicar_avisa_que_rebaixa_um_never(tmp_path: Path) -> None:
    """`never` é MAIS restritivo que o nosso `confirm` — rebaixar em silêncio não.

    Quem escolheu `never` escolheu recusar todo re-pareamento por Just Works de
    quem já tem bond. Rebaixamos (senão o controle dela deixa de re-parear), mas
    dizendo o que estamos fazendo e como ter o valor de volta.
    """
    etc = _etc(tmp_path, "[General]\nJustWorksRepairing = never\nName = BlueZ\n")
    proc = _rodar(etc, "aplicar")

    assert "never" in proc.stdout
    assert "REBAIXAR" in proc.stdout
    assert "remover" in proc.stdout
    assert _valor(etc) == "confirm"


def test_sem_main_conf_o_aplicar_nao_anuncia_garantia(tmp_path: Path) -> None:
    """Com /etc/bluetooth presente e main.conf AUSENTE, nada foi escrito.

    A versão anterior imprimia "JustWorksRepairing=confirm + FastConnectable=true
    garantidos" e saía com 0 sem ter tocado em arquivo nenhum — a mesma mentira
    do instalador que anunciava `confirm` com o `always` vivo, em outra roupa.
    """
    etc = _etc(tmp_path)
    proc = _rodar(etc, "aplicar")

    assert proc.returncode == 0, proc.stderr
    assert "garantidos" not in proc.stdout
    assert "NADA garantido" in proc.stdout


def test_remover_declara_a_excecao_das_linhas_em_branco_do_fim(tmp_path: Path) -> None:
    """A invariante "devolve byte a byte" tem UMA exceção, e ela é declarada.

    Linhas em branco do FIM não voltam: é o preço da idempotência (sem isso,
    cada `aplicar` empurrava o bloco uma linha para baixo — medido, 27 a 34
    linhas em oito execuções). Fica fixado aqui para ninguém descobrir por
    acidente, e a exceção está escrita no comentário do `_despir_main_conf`.
    """
    original = "[General]\nName = BlueZ\n\n\n"
    etc = _etc(tmp_path, original)

    _rodar(etc, "aplicar")
    _rodar(etc, "remover")

    assert (etc / "main.conf").read_text(encoding="utf-8") == "[General]\nName = BlueZ\n"
    assert "A EXCEÇÃO DECLARADA da invariante" in SCRIPT.read_text(encoding="utf-8"), (
        "a exceção deixou de estar declarada no próprio script"
    )


# ---------------------------------------------------------------------------
# 11. Ler o arquivo dela: nem cego, nem pedindo senha à toa
# ---------------------------------------------------------------------------


def test_remover_recusa_em_vez_de_concluir_que_nao_ha_nada_nosso(tmp_path: Path) -> None:
    """main.conf ilegível fazia o `remover` decidir que não havia bloco nosso.

    Três leituras rodavam sem o prefixo de root, ao contrário de todo o resto:
    com um main.conf modo 600 (legítimo num arquivo de config de rádio), o
    `remover` não removia — desinstalar não desinstalava, em silêncio.
    """
    if os.geteuid() == 0:
        pytest.skip("root lê qualquer modo; o cenário não existe")
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    (etc / "main.conf").chmod(0o000)
    try:
        proc = _rodar(etc, "remover")
    finally:
        (etc / "main.conf").chmod(0o644)

    assert proc.returncode != 0, "o remover disse que estava tudo certo sem poder ler o arquivo"
    assert "não consigo LER" in proc.stderr
    # E o bloco continua lá: recusar é honesto, mentir não.
    assert "# >>> hefesto bluetooth >>>" in (etc / "main.conf").read_text(encoding="utf-8")


def test_verificar_nao_inventa_valor_quando_nao_consegue_ler(tmp_path: Path) -> None:
    """"não declarado" e "não consigo ler" são coisas MUITO diferentes."""
    if os.geteuid() == 0:
        pytest.skip("root lê qualquer modo; o cenário não existe")
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    (etc / "main.conf").chmod(0o000)
    try:
        proc = _rodar(etc, "verificar")
    finally:
        (etc / "main.conf").chmod(0o644)

    assert proc.returncode != 0
    assert "JustWorksRepairing: ilegível" in proc.stdout
    assert "veredito: DESCONHECIDO" in proc.stdout


def test_leitura_de_arquivo_ilegivel_escala_em_vez_de_desistir(tmp_path: Path) -> None:
    """Recusar é melhor que mentir; ESCALAR é melhor que recusar.

    Em produção o `remover` roda com prefixo de root. Se a leitura não escalasse,
    todo main.conf modo 600 viraria recusa e o uninstall nunca removeria o bloco
    — a versão mais educada do mesmo defeito. Aqui um `sudo` FALSO (outro nome,
    que só registra e repassa) prova que a escalada é tentada.
    """
    if os.geteuid() == 0:
        pytest.skip("root lê qualquer modo; o cenário não existe")
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    falso = tmp_path / "escalador" / "sudo-de-mentira"
    falso.parent.mkdir()
    falso.write_text(
        "#!/usr/bin/env bash\n"
        'printf "%s\\n" "$*" >> "${HEFESTO_FAKE_SUDO_LOG}"\n'
        'exec "$@"\n',
        encoding="utf-8",
    )
    falso.chmod(0o755)
    (etc / "main.conf").chmod(0o000)
    try:
        _rodar(etc, "verificar", sudo_falso=falso)
    finally:
        (etc / "main.conf").chmod(0o644)

    registro = (falso.parent / "escaladas.txt").read_text(encoding="utf-8")
    assert f"cat {etc / 'main.conf'}" in registro, (
        "a leitura desistiu do arquivo ilegível em vez de escalar — em produção "
        "isso é o uninstall deixando o bloco no disco"
    )


def test_verificar_nao_pede_sudo_para_arquivo_legivel() -> None:
    """O `verificar` é o que o doctor consome: senha em diagnóstico, não.

    A escalada é condicional — só quando o arquivo NÃO é legível. Um `_r` fixo
    em toda leitura transformaria `scripts/doctor.sh` em pedido de senha.
    """
    fonte = SCRIPT.read_text(encoding="utf-8")
    assert 'if [[ -r "${arquivo}" ]]; then' in fonte


# ---------------------------------------------------------------------------
# 12. A fiação com quem chama: install.sh e doctor.sh
# ---------------------------------------------------------------------------


def _secao_3d() -> str:
    """O passo 3d do install.sh, do cabeçalho até o 3d-bis."""
    texto = INSTALL.read_text(encoding="utf-8")
    inicio = texto.index("# 3d. Bluetooth no máximo")
    fim = texto.index("# 3d-bis.")
    return texto[inicio:fim]


def test_install_anuncia_o_pulo_do_bluez_com_no_udev() -> None:
    """`--no-udev` pulava a cura do BlueZ inteira SEM DIZER UMA PALAVRA.

    O passo era gateado por `SKIP_UDEV -eq 0` e não tinha `else`: com a flag,
    nem o `step "3d"` saía. Na máquina dela isso significa que o `always`
    SOBREVIVE ao install — enquanto o detector novo do doctor manda "rode
    ./install.sh" sem ressalva. O vizinho 3d-bis já fazia certo.
    """
    secao = _secao_3d()
    assert '"${SKIP_UDEV}" -eq 1' in secao, "o passo 3d não tem ramo para --no-udev"
    assert "PULADO (--no-udev)" in secao
    assert "bluez_config.sh" in secao.split('"${SKIP_UDEV}" -eq 1')[1].split("elif")[0], (
        "o pulo não diz que a config do BlueZ ficou por fazer"
    )
    # E diz o estado do disco AGORA, pelo dono único, em leitura pura.
    assert "verificar" in secao
    assert "JustWorksRepairing=always AGORA" in secao


def test_install_anuncia_o_pulo_tambem_quando_falta_sudo() -> None:
    """Sem o comando `sudo` o passo também sumia da saída, calado."""
    secao = _secao_3d()
    assert "PULADO (sem sudo nesta máquina)" in secao


def test_doctor_le_pelo_dono_unico() -> None:
    """Duas fontes para a mesma regra é a classe de defeito desta leva.

    O doctor REIMPLEMENTAVA o `sed` do `_valor_ativo`. Hoje ele chama
    `bluez_config.sh verificar` — e o comentário do script, que afirmava isso
    antes de ser verdade, passou a ser verdade.
    """
    doctor = (RAIZ / "scripts" / "doctor.sh").read_text(encoding="utf-8")
    assert '"${dono}" verificar' in doctor
    assert "JustWorksRepairing[[:space:]]*=" not in doctor, (
        "o doctor voltou a ter o próprio parser de JustWorksRepairing"
    )


def test_doctor_avisa_em_vez_de_mentir_quando_o_dono_some() -> None:
    """Sem o `bluez_config.sh`, o doctor não pode dizer "não declarado"."""
    doctor = (RAIZ / "scripts" / "doctor.sh").read_text(encoding="utf-8")
    assert "o dono único da config do BlueZ não está aqui" in doctor


# ---------------------------------------------------------------------------
# 13. O BACKUP QUE SE DESTRUÍA SOZINHO (achado ALTA-1 de 06/08/2026)
#
# O nome era `main.conf.bak.hefesto-${rotulo}$(date +%s)`: resolução de UM
# SEGUNDO, `cp` sem `-n`, sem teste de `-e`, sem mktemp. Duas gravações do MESMO
# rótulo dentro do mesmo segundo faziam a segunda SOBRESCREVER o backup da
# primeira — dentro do `aplicar`/`remover`, sem gesto dela. O `_resumo_backups`
# não via nada (um arquivo morre, outro nasce, a CONTAGEM não muda) e a mesma
# execução imprimia "nenhum é apagado automaticamente".
# ---------------------------------------------------------------------------


def test_duas_gravacoes_no_mesmo_segundo_nao_comem_o_backup_anterior(
    tmp_path: Path,
) -> None:
    """O estado imediatamente anterior é o backup de MAIOR valor. E era o que sumia.

    Reprodução MEDIDA: `aplicar` sobre o estado A, edição para o estado B,
    `aplicar` de novo dentro do mesmo segundo. Antes: UM backup no disco, com o
    estado B — o estado A dela tinha ido embora.
    """
    etc = _etc(tmp_path, "[General]\nName = ESTADO-A-DELA\n")
    _rodar(etc, "aplicar")
    (etc / "main.conf").write_text("[General]\nName = ESTADO-B\n", encoding="utf-8")
    _rodar(etc, "aplicar")

    backups = _backups(etc)
    conteudos = [b.read_text(encoding="utf-8") for b in backups]
    assert len(backups) == 2, (
        f"duas gravações deixaram {len(backups)} backup(s): a segunda comeu a "
        "primeira porque o nome só tem resolução de um segundo"
    )
    assert any("ESTADO-A-DELA" in c for c in conteudos), (
        "o backup do estado imediatamente anterior foi DESTRUÍDO — é sempre o "
        "de maior valor, e era sempre ele que morria"
    )
    assert any("ESTADO-B" in c for c in conteudos)


def test_aplicar_e_remover_seguidos_nao_colidem(tmp_path: Path) -> None:
    """A reprodução do verificador, letra por letra: aplicar; remover; aplicar.

    É a sequência que o próprio doctor sugere, e ela acontece em muito menos de
    um segundo. Três gravações reais = três backups, sempre.
    """
    etc = _etc(tmp_path, "[General]\nName = ESTADO-ORIGINAL\n")
    inicio = time.monotonic()
    _rodar(etc, "aplicar")
    _rodar(etc, "remover")
    _rodar(etc, "aplicar")
    decorrido = time.monotonic() - inicio

    assert len(_backups(etc)) == 3, (
        f"aplicar+remover+aplicar em {decorrido:.2f}s deixou "
        f"{len(_backups(etc))} backup(s) em vez de 3"
    )
    assert any(
        "ESTADO-ORIGINAL" in b.read_text(encoding="utf-8") for b in _backups(etc)
    ), "o estado ORIGINAL dela não sobreviveu ao ciclo"


def test_a_frase_do_resumo_deixou_de_ser_mentira(tmp_path: Path) -> None:
    """"nenhum é apagado automaticamente" saía na MESMA execução que apagava um.

    Não é preciosismo de texto: era a frase que impedia quem lia de desconfiar.
    """
    etc = _etc(tmp_path, "[General]\nName = BlueZ\n")
    _rodar(etc, "aplicar")
    antes = {b.name for b in _backups(etc)}
    (etc / "main.conf").write_text("[General]\nName = OUTRO\n", encoding="utf-8")

    proc = _rodar(etc, "aplicar")

    assert "nenhum é apagado automaticamente" in proc.stdout
    assert antes.issubset({b.name for b in _backups(etc)}), (
        "a execução que imprimiu 'nenhum é apagado automaticamente' apagou um"
    )


# ---------------------------------------------------------------------------
# 14. O BACKUP PARCIAL (achado MÉDIA-7 de 06/08/2026)
#
# A assimetria estava no próprio corpo do `_gravar_se_mudou`: o caminho do
# temporário tinha `rm -f`, o do backup não. Um `cp` que morre no meio deixava
# um arquivo cortado no disco, sem limpeza e sem uma palavra — e todo consumidor
# (o `verificar` que conta, o `podar` que decide) o tratava como legítimo.
# ---------------------------------------------------------------------------


def test_backup_parcial_e_apagado_e_o_main_conf_nao_e_tocado(tmp_path: Path) -> None:
    """Meio backup é pior que backup nenhum: tem cara de cópia fiel.

    O shim corta o `cp` cujo destino é o arquivo de backup. Nada de backup
    cortado sobrevive, e o `main.conf` dela não é reescrito — sem backup íntegro
    não se mexe no conffile.

    O QUE ESTE TESTE MORDE, EXATAMENTE (correção de 06/08/2026 — a rodada
    anterior afirmou uma mordida que NÃO REPRODUZ, e uma medição de terceiro a
    derrubou). A cura tem duas metades:

        if ! _r cp "${origem}" "${backup}" || ! _r cmp -s "${origem}" "${backup}"

    Aqui o shim faz o `cp` sair **1**, então o `||` curto-circuita e o `cmp`
    NUNCA É AVALIADO: este teste morde a metade do `cp` e a limpeza, e arrancar
    o `cmp` o deixa VERDE. A outra metade tem bancada própria e é a de baixo,
    `test_backup_que_mente_ter_copiado_e_pego_pelo_cmp`, onde o `cp` sai 0.
    """
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    original = (etc / "main.conf").read_bytes()
    pasta = tmp_path / "shim-backup-parcial"
    pasta.mkdir()
    real = shutil.which("cp")
    assert real
    (pasta / "cp").write_text(
        "#!/usr/bin/env bash\n"
        'destino="${@: -1}"\n'
        'if [[ "${destino}" == *"main.conf.bak.hefesto-"* ]]; then\n'
        '    head -c 118 "${@: -2:1}" > "${destino}" 2>/dev/null || true\n'
        "    exit 1\n"
        "fi\n"
        f'exec {real} "$@"\n',
        encoding="utf-8",
    )
    (pasta / "cp").chmod(0o755)

    proc = _rodar(etc, "aplicar", path_extra=pasta)

    assert proc.returncode != 0, "o aplicar seguiu adiante com um backup pela metade"
    assert _backups(etc) == [], (
        f"sobrou backup PARCIAL no disco: "
        f"{[(b.name, b.stat().st_size) for b in _backups(etc)]}"
    )
    assert (etc / "main.conf").read_bytes() == original
    assert "INCOMPLETO" in proc.stderr, "o backup parcial sumiu sem uma palavra"
    assert "garantidos" not in proc.stdout


def test_backup_que_mente_ter_copiado_e_pego_pelo_cmp(tmp_path: Path) -> None:
    """A metade do `cmp`, que até 06/08/2026 NÃO TINHA MORDIDA NENHUMA.

    O caso é o pior de todos e o mais silencioso: o `cp` corta o arquivo E SAI
    COM 0. Nada no código anterior desconfia — o `||` já foi satisfeito pelo
    lado esquerdo e o script segue adiante reescrevendo o `main.conf` dela com
    um "backup" de 118 bytes cortado no meio do bloco. Só a conferência byte a
    byte pega isso, e ela existia sem ninguém provar que servia para alguma
    coisa: o teste que dizia cobri-la usava um `cp` que saía 1.

    Não é hipótese de laboratório: `cp` sobre NFS/SMB com escrita adiada, disco
    cheio detectado só no `close()`, e qualquer sistema de arquivos que só
    reporte erro no flush chegam exatamente aqui — saída 0, arquivo curto.
    """
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    original = (etc / "main.conf").read_bytes()
    assert len(original) > 118, "a fixture precisa ser maior que o corte"
    pasta = tmp_path / "shim-cp-que-mente"
    pasta.mkdir()
    real = shutil.which("cp")
    assert real
    (pasta / "cp").write_text(
        "#!/usr/bin/env bash\n"
        'destino="${@: -1}"\n'
        'if [[ "${destino}" == *"main.conf.bak.hefesto-"* ]]; then\n'
        '    head -c 118 "${@: -2:1}" > "${destino}" 2>/dev/null\n'
        "    exit 0\n"
        "fi\n"
        f'exec {real} "$@"\n',
        encoding="utf-8",
    )
    (pasta / "cp").chmod(0o755)

    proc = _rodar(etc, "aplicar", path_extra=pasta)

    assert proc.returncode != 0, (
        "o `cp` mentiu ter copiado, o `cmp` não conferiu, e o aplicar seguiu "
        "adiante para reescrever o conffile dela"
    )
    assert _backups(etc) == [], (
        "sobrou um 'backup' de 118 bytes que passa por cópia fiel: "
        f"{[(b.name, b.stat().st_size) for b in _backups(etc)]}"
    )
    assert (etc / "main.conf").read_bytes() == original, (
        "o main.conf dela foi reescrito com um backup cortado por trás"
    )
    assert "INCOMPLETO" in proc.stderr


def test_backup_integro_e_conferido_byte_a_byte(tmp_path: Path) -> None:
    """A linha de base do teste acima: um backup normal É uma cópia fiel."""
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    _rodar(etc, "aplicar")

    assert len(_backups(etc)) == 1
    assert _backups(etc)[0].read_text(encoding="utf-8") == MAIN_CONF_DELA


# ---------------------------------------------------------------------------
# 15. O GRUPO — o oráculo é o GKeyFile, e o dono único tem de concordar com ele
#
# ACHADO MÉDIA-4 (06/08/2026, MEDIDO): o `_valor_ativo` era um `sed | tail -n 1`
# que varria o arquivo INTEIRO e ignorava o grupo. Com `[General]
# JustWorksRepairing=always` seguido de `[Policy] JustWorksRepairing=confirm`, o
# `verificar` respondia `veredito: OK` e o GKeyFile lia `always`. Falso negativo
# do dono único, consumido pelo doctor E pelo ramo `--no-udev` do install.
#
# E a regra "o último vence" (o `tail -n 1`) não tinha teste que mordesse:
# trocar por `head -n 1` deixava a suíte verde.
# ---------------------------------------------------------------------------

#: (nome, conteúdo do main.conf, valor que o BlueZ lê). A terceira coluna é
#: CONFERIDA contra o GKeyFile de verdade em
#: `test_a_tabela_do_grupo_nao_e_ficcao` — sem isso ela seria só mais um parser
#: em Python escrito à mão, que é exatamente o defeito desta seção.
_TABELA_DO_GRUPO: list[tuple[str, str, str | None]] = [
    (
        "grupo-errado-nao-conta",
        "[General]\nJustWorksRepairing=always\n\n[Policy]\nJustWorksRepairing=confirm\n",
        "always",
    ),
    (
        "so-em-policy-e-ausente-em-general",
        "[General]\nName = BlueZ\n\n[Policy]\nJustWorksRepairing=always\n",
        None,
    ),
    (
        "o-ultimo-de-general-vence",
        "[General]\nJustWorksRepairing=never\nJustWorksRepairing=always\n",
        "always",
    ),
    (
        "general-repetido-faz-merge-e-o-ultimo-vence",
        "[General]\nJustWorksRepairing=never\n[Policy]\nX=1\n[General]\nJustWorksRepairing=always\n",
        "always",
    ),
    (
        "general-repetido-que-nao-redeclara-nao-apaga",
        "[General]\nJustWorksRepairing=always\n[Policy]\nX=1\n[General]\nFastConnectable=true\n",
        "always",
    ),
    (
        "comentario-nao-e-chave-nem-indentado",
        "[General]\n   # JustWorksRepairing=always\nJustWorksRepairing=confirm\n",
        "confirm",
    ),
    (
        "espaco-em-volta-do-igual-some-a-esquerda",
        "[General]\nJustWorksRepairing =   always\n",
        "always",
    ),
    (
        "cerquilha-no-meio-do-valor-NAO-e-comentario",
        "[General]\nJustWorksRepairing=confirm # nota\n",
        "confirm # nota",
    ),
    (
        "nome-de-grupo-e-exato",
        "[General ]\nJustWorksRepairing=always\n",
        None,
    ),
]


@pytest.mark.parametrize(
    ("nome", "conteudo_conf", "esperado"),
    [(n, c, e) for n, c, e in _TABELA_DO_GRUPO],
    ids=[n for n, _, _ in _TABELA_DO_GRUPO],
)
def test_a_tabela_do_grupo_nao_e_ficcao(
    tmp_path: Path, nome: str, conteudo_conf: str, esperado: str | None
) -> None:
    """Primeiro: o que a tabela AFIRMA é mesmo o que o GKeyFile lê."""
    alvo = tmp_path / "main.conf"
    alvo.write_text(conteudo_conf, encoding="utf-8")

    assert _oraculo(alvo) == esperado, (
        f"a tabela mente sobre o caso '{nome}' — corrija a TABELA, nunca o "
        "oráculo, que é o parser do bluetoothd"
    )


@pytest.mark.parametrize(
    ("nome", "conteudo_conf", "esperado"),
    [(n, c, e) for n, c, e in _TABELA_DO_GRUPO],
    ids=[n for n, _, _ in _TABELA_DO_GRUPO],
)
def test_o_dono_unico_le_exatamente_o_que_o_bluez_le(
    tmp_path: Path, nome: str, conteudo_conf: str, esperado: str | None
) -> None:
    """E então: o `verificar` responde a MESMA coisa, caso a caso.

    O caso `grupo-errado-nao-conta` é a reprodução literal do achado: antes
    desta cura o `verificar` dizia `confirm` e o BlueZ lia `always`.
    """
    etc = _etc(tmp_path, conteudo_conf)

    proc = _rodar(etc, "verificar")
    lido = next(
        (
            ln[len("JustWorksRepairing: "):]
            for ln in proc.stdout.splitlines()
            if ln.startswith("JustWorksRepairing: ")
        ),
        None,
    )

    assert lido == (esperado if esperado is not None else "ausente"), (
        f"caso '{nome}': o dono único leu {lido!r} e o BlueZ lê {esperado!r} — "
        "é falso negativo do dono, consumido pelo doctor e pelo install"
    )


def test_o_veredito_acompanha_o_grupo(tmp_path: Path) -> None:
    """O caso MEDIDO, até o veredito: `OK` com `always` vivo era o estrago."""
    etc = _etc(
        tmp_path,
        "[General]\nJustWorksRepairing=always\n\n[Policy]\nJustWorksRepairing=confirm\n",
    )

    proc = _rodar(etc, "verificar")

    assert proc.returncode != 0, "veredito OK com JustWorksRepairing=always em [General]"
    assert "veredito: INSEGURO" in proc.stdout
    assert _valor(etc) == "always", "o oráculo confirma: é always que o BlueZ lê"


def test_o_ultimo_vence_e_nao_o_primeiro(tmp_path: Path) -> None:
    """A regra `tail -n 1` sem teste: trocar por `head -n 1` passava verde.

    Alguém que apense o PRÓPRIO `[General]` DEPOIS do nosso bloco vence — e um
    dono que lesse o primeiro diria `confirm` com `always` no ar.
    """
    etc = _etc(tmp_path, MAIN_CONF_DELA)
    _rodar(etc, "aplicar")
    with (etc / "main.conf").open("a", encoding="utf-8") as fh:
        fh.write("\n[General]\nJustWorksRepairing=always\n")

    proc = _rodar(etc, "verificar")

    assert _valor(etc) == "always", "o oráculo: quem vem depois vence"
    assert "JustWorksRepairing: always" in proc.stdout, (
        "o dono único leu a PRIMEIRA ocorrência — quem apensa depois do nosso "
        "bloco vence, e o veredito sairia OK com always no ar"
    )
    assert proc.returncode != 0


def test_aplicar_corrige_o_caso_do_grupo(tmp_path: Path) -> None:
    """Detectar não basta: depois do `aplicar`, o BlueZ tem de ler `confirm`."""
    etc = _etc(
        tmp_path,
        "[General]\nJustWorksRepairing=always\n\n[Policy]\nJustWorksRepairing=confirm\n",
    )

    proc = _rodar(etc, "aplicar")

    assert proc.returncode == 0, proc.stderr
    assert _valor(etc) == "confirm"


# ---------------------------------------------------------------------------
# 16. A PROMESSA QUE ERA FALSA NO LUGAR MAIS PROVÁVEL (achado MÉDIA-5)
#
# O rebaixamento `never` -> `confirm` vinha com a promessa em voz alta "a sua
# linha é neutralizada, não apagada, e volta inteira". Ela é VERDADE fora do
# bloco. É FALSA quando o `never` está DENTRO do bloco hefesto — que é
# exatamente onde vai escrever quem leu o aviso do doctor e resolveu endurecer o
# valor, porque é ali que a chave já está. Ali o `_despir_main_conf` descarta a
# faixa inteira, nenhuma MARCA é gravada, e o `remover` entrega arquivo SEM a
# chave. E o aviso do alheio tem `FastConnectable|JustWorksRepairing` na lista
# de exceções, então a linha dela sumia sem uma palavra.
# ---------------------------------------------------------------------------


def test_never_fora_do_bloco_ganha_a_promessa_e_ela_se_cumpre(tmp_path: Path) -> None:
    """Fora do bloco a promessa é verdadeira — e o teste cobra o cumprimento."""
    original = "[General]\nJustWorksRepairing = never\nName = BlueZ\n"
    etc = _etc(tmp_path, original)

    proc = _rodar(etc, "aplicar")
    assert "volta inteira" in proc.stdout
    assert "FORA do bloco" in proc.stdout
    assert _valor(etc) == "confirm"

    _rodar(etc, "remover")
    assert (etc / "main.conf").read_text(encoding="utf-8") == original, (
        "a promessa foi feita e não foi cumprida"
    )
    assert _valor(etc) == "never"


def test_never_dentro_do_bloco_nao_ganha_promessa_que_nao_se_cumpre(
    tmp_path: Path,
) -> None:
    """Dentro do bloco a linha SAI e não volta. Então não se promete que volta.

    A prova é dupla: o aviso diz que a linha não volta, E o `remover` de fato
    não a devolve (é a medição do achado, mantida aqui para que ninguém
    "conserte" o aviso sem consertar o mecanismo).
    """
    etc = _etc(
        tmp_path,
        "[General]\nName = BlueZ\n"
        "# >>> hefesto bluetooth >>>\n"
        "[General]\n"
        "FastConnectable=true\n"
        "JustWorksRepairing=never\n"
        "# <<< hefesto bluetooth <<<\n",
    )

    proc = _rodar(etc, "aplicar")

    assert "REBAIXAR" in proc.stdout
    assert "DENTRO do bloco hefesto" in proc.stdout, (
        "o aviso não diz que a linha está dentro do bloco"
    )
    assert "não a devolve" in proc.stdout or "NÃO a devolve" in proc.stdout, (
        "o aviso não nomeia o que vai sumir"
    )
    assert "volta inteira no 'remover'" not in proc.stdout.split("DENTRO do bloco")[0], (
        "a promessa falsa continua sendo feita antes da ressalva"
    )
    assert _valor(etc) == "confirm"

    # E a medição que sustenta o texto: o `never` de dentro do bloco NÃO volta.
    _rodar(etc, "remover")
    assert _valor(etc) is None, (
        "se o `never` de dentro do bloco passou a voltar, a promessa pode ser "
        "feita de novo — mas então este teste é que tem de mudar, de propósito"
    )


def test_o_doctor_nao_promete_devolucao_sem_ressalva() -> None:
    """O mesmo texto vivia no doctor, e é lá que ela lê primeiro."""
    doctor = (RAIZ / "scripts" / "doctor.sh").read_text(encoding="utf-8")
    aviso = next(
        ln for ln in doctor.splitlines()
        if "JustWorksRepairing=never no main.conf" in ln
    )
    assert "FORA das sentinelas" in aviso and "DENTRO do bloco" in aviso, (
        "o doctor voltou a prometer a devolução da linha sem dizer que ela só "
        "vale FORA do bloco hefesto"
    )


# ---------------------------------------------------------------------------
# 17. O asset vazio, e o que o comentário promete
# ---------------------------------------------------------------------------


def test_bloco_de_zero_byte_nao_anuncia_garantia(tmp_path: Path) -> None:
    """Cada passo deu certo e o resultado não existe.

    MEDIDO em 06/08/2026: com `assets/bluetooth/hefesto-bt.block` de ZERO BYTE
    — asset truncado no build, no rsync ou no empacotamento — o `aplicar` saía
    com rc=0 anunciando "garantidos" e o arquivo final não tinha a chave. É a
    mesma família do defeito que abriu a sprint, e a cura estava a uma chamada
    de distância: reler o disco pelo `_verificar`, que já existia.
    """
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "hefesto-bt.block").write_text("", encoding="utf-8")
    for nome in ("hefesto-fastconnectable.conf", "hefesto-justworks.conf"):
        shutil.copy(ASSETS / nome, assets / nome)
    etc = _etc(tmp_path, "[General]\nName = BlueZ\n")

    ambiente = {
        **os.environ,
        "HEFESTO_BT_ETC": str(etc),
        "HEFESTO_BT_ASSETS": str(assets),
        "HEFESTO_BT_SUDO": "",
    }
    proc = subprocess.run(
        ["bash", str(SCRIPT), "aplicar"],
        capture_output=True,
        text=True,
        timeout=60,
        env=ambiente,
    )

    assert proc.returncode != 0, (
        "o aplicar saiu com 0 e o arquivo final não tem a chave nenhuma"
    )
    assert "garantidos" not in proc.stdout
    assert "reli" in proc.stderr, "a conferência final do disco não aconteceu"
    assert _valor(etc) is None


def test_o_comentario_nao_promete_durabilidade_que_nao_entrega() -> None:
    """`rename(2)` dá ATOMICIDADE, não DURABILIDADE — e não há `fsync` aqui.

    O comentário prometia cobrir "queda de energia". Cobre o arquivo pela
    metade (que era o estrago que importava), não a perda do conteúdo novo.
    Promessa a mais num comentário é a semente da próxima hipótese que não
    explica o que já funcionava.
    """
    fonte = SCRIPT.read_text(encoding="utf-8")
    assert "ATOMICIDADE, não DURABILIDADE" in fonte, (
        "o comentário da troca atômica voltou a prometer durabilidade"
    )
    assert "fsync" in fonte, "a ausência do fsync deixou de ser declarada"
    codigo = [
        ln for ln in fonte.splitlines()
        if not ln.lstrip().startswith("#") and "queda de energia" in ln
    ]
    assert codigo == []


def test_verificar_reporta_o_valor_dos_dropins(tmp_path: Path) -> None:
    """O ANEXO da verificação adversarial, avaliado e reportado.

    O `aplicar` grava drop-ins POR CIMA e o `verificar` nunca lia VALOR de lá:
    um drop-in de terceiro que ordene DEPOIS do nosso venceria, e o veredito
    continuaria `OK`.

    MEDIDO em 06/08/2026 nesta máquina, três vezes pelo mesmo lado: `strings` do
    bluetoothd 5.86 do backport tem `%*s/main.conf` e ZERO `main.conf.d`, o
    diretório NÃO EXISTE, e `dpkg -L bluez` não o lista. Aqui o mecanismo do
    drop-in não está ligado — fazer o VEREDITO depender de um arquivo que este
    bluetoothd não lê seria alarme falso, o defeito de costas. Então o valor é
    REPORTADO e nomeado, e o veredito segue saindo do `main.conf`.
    """
    etc = _etc(
        tmp_path,
        "[General]\nFastConnectable=true\nJustWorksRepairing=confirm\n",
        com_dropin_dir=True,
    )
    (etc / "main.conf.d" / "zz-de-terceiro.conf").write_text(
        "[General]\nJustWorksRepairing=always\n", encoding="utf-8"
    )

    proc = _rodar(etc, "verificar")

    assert "dropin-JustWorksRepairing: zz-de-terceiro.conf=always" in proc.stdout, (
        "o verificar continua cego para o VALOR dentro de main.conf.d"
    )
    assert "dropin-em-conflito: zz-de-terceiro.conf declara always" in proc.stdout
    assert "veredito: OK" in proc.stdout, (
        "o veredito passou a depender de main.conf.d — neste BlueZ o diretório "
        "é inerte (MEDIDO), e alarme falso é o defeito de costas"
    )


def test_dropin_nosso_nao_vira_conflito(tmp_path: Path) -> None:
    """Aviso que sai sempre é aviso que ninguém lê."""
    etc = _etc(tmp_path, MAIN_CONF_DELA, com_dropin_dir=True)
    _rodar(etc, "aplicar")

    proc = _rodar(etc, "verificar")

    assert "dropin-JustWorksRepairing: hefesto-justworks.conf=confirm" in proc.stdout
    assert "dropin-em-conflito" not in proc.stdout


def test_a_nota_do_no_udev_nao_alega_o_que_o_ci_nao_faz() -> None:
    """Decisão gravada sobre medição FALSA é pior que decisão sem nota.

    A justificativa do gate do `--no-udev` era "o CI o usa: separar faria o CI
    reescrever /etc/bluetooth/main.conf da máquina de build". MEDIDO em
    06/08/2026 que a premissa não existe: o CI NÃO roda o `install.sh` —
    `grep -rn 'install\\.sh' .github/workflows/` acha só o `shellcheck` da
    ci.yml:136, e nenhuma invocação. A decisão se mantém pelo contrato
    documentado (`--no-udev` pula os passos que tocam /etc, e este escreve em
    /etc/bluetooth/main.conf); a justificativa é que foi corrigida.
    """
    secao = INSTALL.read_text(encoding="utf-8")
    assert "máquina de build" not in secao, (
        "a justificativa falsa voltou: o CI não roda o install.sh"
    )
    assert "o CI não roda o `install.sh`" in secao, "a nota datada sumiu"

    fluxos = RAIZ / ".github" / "workflows"
    invocacoes = []
    for arquivo in sorted(fluxos.glob("*.yml")):
        for numero, linha in enumerate(
            arquivo.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if "install.sh" not in linha or "shellcheck" in linha:
                continue
            if linha.lstrip().startswith("#"):
                continue
            invocacoes.append(f"{arquivo.name}:{numero}: {linha.strip()}")
    assert invocacoes == [], (
        "o CI passou a rodar o install.sh — se isso é de propósito, a nota "
        f"datada tem de ser reescrita (e não apagada): {invocacoes}"
    )


def test_o_caso_do_link_simbolico_esta_dito(tmp_path: Path) -> None:
    """Não é regressão, não é o caso dela — mas merece a linha no comentário.

    Com `main.conf` como LINK SIMBÓLICO, o `mv -f` substitui o link por arquivo
    comum e o alvo do link fica para trás. O código antigo (`install -m644`)
    fazia o oposto: seguia o link e reescrevia o alvo. Nenhum dos dois é
    "certo"; o que não pode é o comportamento ser surpresa.
    """
    assert "LINK SIMBÓLICO" in SCRIPT.read_text(encoding="utf-8")

    alvo = tmp_path / "main.conf.real"
    alvo.write_text("[General]\nName = BlueZ\n", encoding="utf-8")
    etc = tmp_path / "bluetooth"
    etc.mkdir()
    (etc / "main.conf").symlink_to(alvo)

    proc = _rodar(etc, "aplicar")

    assert proc.returncode == 0, proc.stderr
    assert _valor(etc) == "confirm", "o valor seguro não chegou ao arquivo lido"
    assert not (etc / "main.conf").is_symlink(), (
        "se o link passou a ser preservado, ÓTIMO — mas então o comentário e "
        "este teste têm de mudar juntos, de propósito"
    )


# ---------------------------------------------------------------------------
# 20. Os três casos em que o dono único discordava do GKeyFile (06/08/2026)
#
# Nenhum deles é hipótese: os três foram medidos contra o oráculo antes de a
# cura existir, e os três produziam veredito FALSO — em duas direções.
# ---------------------------------------------------------------------------

#: (nome, conteúdo, mensagem que o GKeyFile dá ao recusar — CONFERIDA).
_TABELA_DA_RECUSA: list[tuple[str, str]] = [
    (
        "linha-solta-sem-igual",
        "[General]\nJustWorksRepairing=confirm\nlinha-solta-sem-igual\n",
    ),
    (
        "linha-solta-com-espaco",
        "[General]\nJustWorksRepairing=confirm\nisto tem espaco e nada mais\n",
    ),
    (
        "chave-antes-do-primeiro-grupo",
        "JustWorksRepairing=always\n[General]\nJustWorksRepairing=confirm\n",
    ),
]


@pytest.mark.parametrize(
    ("nome", "conteudo_conf"),
    _TABELA_DA_RECUSA,
    ids=[n for n, _ in _TABELA_DA_RECUSA],
)
def test_a_tabela_da_recusa_nao_e_ficcao(
    tmp_path: Path, nome: str, conteudo_conf: str
) -> None:
    """Primeiro: o GKeyFile RECUSA MESMO estes arquivos, inteiros.

    Sem esta metade, a réplica em `awk` do dono estaria sendo conferida contra
    uma tabela escrita à mão — o terceiro parser de novo, pela porta dos fundos.
    """
    alvo = tmp_path / "main.conf"
    alvo.write_text(conteudo_conf, encoding="utf-8")

    assert _oraculo_recusa(alvo) is not None, (
        f"a tabela afirma que o GKeyFile recusa '{nome}' e ele NÃO recusa — "
        "corrija a TABELA, nunca o oráculo"
    )
    # E o efeito que importa: nem a chave que ESTÁ escrita no arquivo vale.
    assert _oraculo(alvo) is None


@pytest.mark.parametrize(
    ("nome", "conteudo_conf"),
    _TABELA_DA_RECUSA,
    ids=[n for n, _ in _TABELA_DA_RECUSA],
)
def test_o_dono_unico_nao_aprova_arquivo_que_o_bluez_descarta(
    tmp_path: Path, nome: str, conteudo_conf: str
) -> None:
    """O falso `OK` mais silencioso que havia.

    Uma linha malformada em QUALQUER ponto faz o GKeyFile abortar a carga, e o
    `bluetoothd` fica sem config nenhuma — nem a nossa, nem a dela. O dono lia
    `JustWorksRepairing=confirm` normalmente, respondia `veredito: OK` e o doctor
    dava selo verde a um arquivo que o BlueZ descarta inteiro. A direção do
    engano é conservadora (ninguém fica com `always` VALENDO), mas o veredito é
    falso e ela não tem como descobrir.
    """
    etc = _etc(tmp_path, conteudo_conf)

    proc = _rodar(etc, "verificar")

    assert proc.returncode != 0, f"caso '{nome}': o dono aprovou o arquivo"
    assert "veredito: OK" not in proc.stdout, (
        f"caso '{nome}': `veredito: OK` sobre um arquivo que o bluetoothd "
        "descarta inteiro"
    )
    assert "veredito: RECUSADO" in proc.stdout
    assert "recusado pelo parser" in proc.stdout, "não diz QUE linha é"


def test_o_aplicar_nao_anuncia_garantia_sobre_arquivo_recusado(tmp_path: Path) -> None:
    """E a outra boca: escrever a chave num arquivo recusado não garante nada."""
    etc = _etc(
        tmp_path,
        "[General]\nName = BlueZ\nlinha-solta-que-o-parser-recusa\n",
    )

    proc = _rodar(etc, "aplicar")

    assert proc.returncode != 0, "anunciou sucesso sobre um arquivo que o BlueZ descarta"
    assert "garantidos" not in proc.stdout
    assert "RECUSA" in proc.stderr
    assert "linha-solta-que-o-parser-recusa" in proc.stderr, "não nomeia a linha"
    # E o oráculo confirma: depois do aplicar, o arquivo continua sem valer nada.
    assert _oraculo_recusa(etc / "main.conf") is not None


def test_arquivo_valido_com_bloco_nosso_nao_e_acusado_de_recusa(tmp_path: Path) -> None:
    """A linha de base: um detector de recusa que acusa tudo não serve.

    O nosso próprio bloco (comentários, `[General]` repetido, chaves com espaço
    em volta do `=`) tem de passar limpo — e passa, conferido pelo oráculo.
    """
    etc = _etc(tmp_path, MAIN_CONF_DELA)

    _rodar(etc, "aplicar")
    proc = _rodar(etc, "verificar")

    assert _oraculo_recusa(etc / "main.conf") is None, (
        "o arquivo que NÓS escrevemos é recusado pelo GKeyFile de verdade"
    )
    assert "recusado pelo parser" not in proc.stdout
    assert "veredito: OK" in proc.stdout


def test_crlf_o_dono_le_o_mesmo_que_o_bluez(tmp_path: Path) -> None:
    """MEDIDO: o GKeyFile descarta o `\\r` do fim e PRESERVA os espaços.

    `JustWorksRepairing=confirm  \\r\\n` vale `'confirm  '` — dois espaços, sem o
    CR. O dono lia `confirm\\r`, discordava do BlueZ e ainda EMBARALHAVA a
    própria mensagem: o CR volta o cursor e a frase se sobrescreve no terminal
    dela. Um main.conf com CRLF não é exótico — é o que sai de um editor de
    Windows, de um `scp` de máquina Windows ou de um arquivo colado num wiki.
    """
    conteudo = "[General]\r\nJustWorksRepairing=confirm\r\n"
    etc = _etc(tmp_path, conteudo)
    assert _valor(etc) == "confirm", "a premissa do teste mudou — confira o oráculo"

    proc = _rodar(etc, "verificar")

    assert "JustWorksRepairing: confirm\n" in proc.stdout, (
        "o dono leu o CR como parte do valor: discorda do BlueZ E embaralha a "
        f"mensagem no terminal. Saída bruta: {proc.stdout!r}"
    )
    assert "veredito: OK" in proc.stdout, (
        "um main.conf salvo com CRLF virou 'INSEGURO' sem nada de inseguro nele"
    )


def test_valor_vazio_existe_e_nao_e_ausente(tmp_path: Path) -> None:
    """MEDIDO: `JustWorksRepairing=` faz o GKeyFile dizer que a chave EXISTE.

    O valor é `''`. O dono devolvia string vazia, o `verificar` imprimia
    `ausente`, e `ausente` tem tratamento PRÓPRIO no doctor ("o BlueZ cai no
    default da distro") — que é uma afirmação diferente, e falsa: aqui a chave
    está declarada, e declarada com um valor que não é o nosso.
    """
    etc = _etc(tmp_path, "[General]\nJustWorksRepairing=\n")
    assert _valor(etc) == "", "a premissa do teste mudou — confira o oráculo"

    proc = _rodar(etc, "verificar")

    assert "JustWorksRepairing: ausente" not in proc.stdout, (
        "chave declarada com valor vazio foi relatada como AUSENTE"
    )
    assert "JustWorksRepairing: (vazio)" in proc.stdout
    assert "veredito: INSEGURO" in proc.stdout


def test_as_tres_excecoes_do_devolve_byte_a_byte_estao_declaradas(
    tmp_path: Path,
) -> None:
    """A invariante tinha TRÊS exceções e só uma estava escrita (achado (e)).

    Cada uma é MEDIDA aqui contra o próprio script, não afirmada: se alguma
    deixar de acontecer, este teste cai e a declaração tem de ser corrigida —
    declarar exceção que não existe é tão ruim quanto esconder a que existe.
    """
    fonte = SCRIPT.read_text(encoding="utf-8")
    assert "AS TRÊS EXCEÇÕES da promessa" in fonte, (
        "as exceções da invariante 3 deixaram de estar declaradas no cabeçalho"
    )

    # (i) linhas em branco do FIM — já tinha teste próprio; aqui só a medição.
    for sub in ("i", "ii", "iii"):
        (tmp_path / sub).mkdir()
    etc = _etc(tmp_path / "i", "[General]\nName = BlueZ\n\n\n")
    _rodar(etc, "aplicar")
    _rodar(etc, "remover")
    assert (etc / "main.conf").read_text(encoding="utf-8") == "[General]\nName = BlueZ\n"

    # (ii) chave NOSSA que um terceiro escreveu DENTRO do bloco não volta.
    dentro = (
        "[General]\n"
        "# >>> hefesto bluetooth >>>\n"
        "[General]\n"
        "JustWorksRepairing=never\n"
        "# <<< hefesto bluetooth <<<\n"
    )
    etc = _etc(tmp_path / "ii", dentro)
    _rodar(etc, "remover")
    assert "JustWorksRepairing" not in (etc / "main.conf").read_text(encoding="utf-8"), (
        "a exceção (ii) deixou de existir — reveja a declaração do cabeçalho"
    )

    # (iii) linha que JÁ começava com a marca literal é DESCOMENTADA.
    etc = _etc(
        tmp_path / "iii",
        "[General]\n"
        f"{MARCA}JustWorksRepairing=always\n"
        "# >>> hefesto bluetooth >>>\n"
        "# <<< hefesto bluetooth <<<\n",
    )
    _rodar(etc, "remover")
    depois = (etc / "main.conf").read_text(encoding="utf-8")
    assert f"{MARCA}JustWorksRepairing" not in depois, (
        "a exceção (iii) deixou de existir — reveja a declaração do cabeçalho"
    )
    assert "JustWorksRepairing=always" in depois, (
        "a linha marcada nem foi devolvida nem ficou marcada — é um terceiro "
        "comportamento, e nenhum dos três está declarado"
    )

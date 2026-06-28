//! Applet COSMIC do Hefesto - Dualsense4Unix.
//!
//! UI fina: um botão de ícone no painel cujo glifo reflete o estado do daemon
//! (offline = ícone "indisponível"; bateria < 15% = ícone de alerta; conectado
//! = martelo do app). Clicar abre um popover com bateria, transporte, perfil
//! ativo, a lista clicável de perfis (troca via IPC) e "Abrir painel" (spawn da
//! GUI). Enquanto o popover está aberto, um tick ~1.5 Hz reconsulta o daemon via
//! `daemon.state_full`. Sem hardware/daemon, tudo degrada para "offline" — nunca
//! entra em pânico.

use cosmic::app::{Core, Task};
use cosmic::applet::{menu_button, padded_control};
use cosmic::iced::platform_specific::shell::commands::popup::{destroy_popup, get_popup};
use cosmic::iced::{window, Length, Subscription};
use cosmic::widget::{divider, icon, scrollable, text, Column};
use cosmic::Element;

use crate::ipc::{self, DaemonState, IpcError, ProfileInfo};

/// Ícone do painel: a MESMA logo do app usada no `.desktop`
/// (`Icon=hefesto-dualsense4unix`, PNG multi-tamanho em hicolor). Usado SEMPRE,
/// em qualquer estado — assim a logo nunca "some" do painel em transições
/// (onlineoffline). Antes o applet trocava o glifo para um SVG symbolic que
/// não renderizava de forma confiável no tema (parecia sumir). O estado real
/// (offline, bateria, perfil) é mostrado DENTRO do popover, não no ícone.
const ICON_APP: &str = "hefesto-dualsense4unix";
/// Período de refresh do estado enquanto o popover está aberto (~1.5 Hz).
const REFRESH_MS: u64 = 700;
/// Binário da GUI a abrir no "Abrir painel".
const GUI_BIN: &str = "hefesto-dualsense4unix-gui";

pub struct HefestoApplet {
    core: Core,
    /// Id do popup aberto (None = fechado).
    popup: Option<window::Id>,
    /// Último estado conhecido do daemon (None = ainda não consultado).
    state: Option<DaemonState>,
    /// `true` se a última tentativa de IPC falhou (daemon offline).
    offline: bool,
    /// Perfis disponíveis (preenchidos ao abrir o popover).
    profiles: Vec<ProfileInfo>,
    /// Troca de perfil em andamento (suprime cliques repetidos / mostra dica).
    switching: bool,
    /// `true` se o mic embutido do DualSense está liberado (sem drop-ins de
    /// supressão do WirePlumber). FEAT-DUALSENSE-MIC-TOGGLE-01.
    mic_on: bool,
}

#[derive(Debug, Clone)]
pub enum Message {
    /// Clique no ícone do painel: abre/fecha o popover.
    TogglePopup,
    /// O popup foi fechado (pelo compositor ou por nós).
    PopupClosed(window::Id),
    /// Dispara uma rodada de refresh (tick do timer ou abertura do popover).
    Refresh,
    /// Resultado de `daemon.state_full`.
    StateFetched(Result<DaemonState, IpcError>),
    /// Resultado de `profile.list`.
    ProfilesFetched(Result<Vec<ProfileInfo>, IpcError>),
    /// Usuário clicou num perfil da lista.
    SwitchProfile(String),
    /// Resultado de `profile.switch`.
    ProfileSwitched(Result<String, IpcError>),
    /// "Abrir painel" — lança a GUI.
    OpenPanel,
    /// "Fechar painel" — fecha a janela da GUI (o daemon SEGUE rodando).
    ClosePanel,
    /// "Sair (desligar Hefesto)" — para o daemon via systemd; o controle deixa
    /// de ter gatilhos/emulação até religar.
    StopDaemon,
    /// Liga/desliga o "modo jogo": suspende mouse/teclado, mantém o gamepad
    /// (FEAT-DSX-GAMEMODE-SUPPRESS-01, via daemon.emulation.suppress).
    ToggleGameMode,
    /// Resultado de daemon.emulation.suppress (novo estado emulation_suppressed).
    GameModeToggled(Result<bool, IpcError>),
    /// Liga/desliga o mic embutido do DualSense (FEAT-DUALSENSE-MIC-TOGGLE-01).
    ToggleMic,
    /// Usuário escolheu o controle-alvo do output (None = todos/broadcast).
    /// FEAT-DSX-CONTROLLER-SELECTOR-01.
    SetOutputTarget(Option<i64>),
    /// Resultado de controller.target.set (novo output_target_index efetivo).
    OutputTargetSet(Result<Option<i64>, IpcError>),
}

impl cosmic::Application for HefestoApplet {
    type Executor = cosmic::SingleThreadExecutor;
    type Flags = ();
    type Message = Message;
    const APP_ID: &'static str = "com.vitoriamaria.HefestoDualsense4Unix";

    fn core(&self) -> &Core {
        &self.core
    }

    fn core_mut(&mut self) -> &mut Core {
        &mut self.core
    }

    fn init(core: Core, _flags: ()) -> (Self, Task<Self::Message>) {
        (
            Self {
                core,
                popup: None,
                state: None,
                offline: false,
                profiles: Vec::new(),
                switching: false,
                mic_on: mic_is_on(),
            },
            Task::none(),
        )
    }

    fn on_close_requested(&self, id: window::Id) -> Option<Message> {
        Some(Message::PopupClosed(id))
    }

    fn update(&mut self, message: Self::Message) -> Task<Self::Message> {
        match message {
            Message::TogglePopup => {
                if let Some(id) = self.popup.take() {
                    // Fecha o popover.
                    return destroy_popup(id);
                }
                // Abre o popover: cria o surface e dispara o 1º refresh.
                let new_id = window::Id::unique();
                self.popup = Some(new_id);
                self.switching = false;
                self.mic_on = mic_is_on();

                let popup_settings = self.core.applet.get_popup_settings(
                    self.core.main_window_id().unwrap_or(window::Id::RESERVED),
                    new_id,
                    None,
                    None,
                    None,
                );
                let open = get_popup(popup_settings);
                let refresh = self.refresh_task();
                let profiles = Task::perform(ipc::fetch_profiles(), |res| {
                    cosmic::action::app(Message::ProfilesFetched(res))
                });
                Task::batch(vec![open, refresh, profiles])
            }

            Message::PopupClosed(id) => {
                if self.popup == Some(id) {
                    self.popup = None;
                    self.switching = false;
                }
                Task::none()
            }

            Message::Refresh => self.refresh_task(),

            Message::StateFetched(result) => {
                match result {
                    Ok(state) => {
                        self.state = Some(state);
                        self.offline = false;
                    }
                    Err(_) => {
                        self.offline = true;
                    }
                }
                Task::none()
            }

            Message::ProfilesFetched(result) => {
                match result {
                    Ok(profiles) => {
                        self.profiles = profiles;
                        self.offline = false;
                    }
                    Err(_) => {
                        self.offline = true;
                    }
                }
                Task::none()
            }

            Message::SwitchProfile(name) => {
                if self.switching {
                    return Task::none();
                }
                self.switching = true;
                Task::perform(ipc::switch_profile(name), |res| {
                    cosmic::action::app(Message::ProfileSwitched(res))
                })
            }

            Message::ProfileSwitched(result) => {
                self.switching = false;
                if let Ok(active) = result {
                    // Atualização otimista; o refresh seguinte confirma.
                    if let Some(state) = self.state.as_mut() {
                        state.active_profile = Some(active);
                    }
                }
                // Reconsulta imediata para refletir o novo estado (< 500 ms).
                self.refresh_task()
            }

            Message::OpenPanel => {
                spawn_gui();
                // Fecha o popover ao abrir a GUI (UX de menu).
                if let Some(id) = self.popup.take() {
                    return destroy_popup(id);
                }
                Task::none()
            }

            Message::ClosePanel => {
                spawn_close_gui();
                // Fecha o popover (UX de menu); o daemon segue rodando.
                if let Some(id) = self.popup.take() {
                    return destroy_popup(id);
                }
                Task::none()
            }

            Message::StopDaemon => {
                spawn_stop_daemon();
                // Fecha o popover; o próximo refresh mostrará "Daemon desconectado".
                if let Some(id) = self.popup.take() {
                    return destroy_popup(id);
                }
                Task::none()
            }

            Message::ToggleGameMode => {
                // Entrar no modo jogo -> suppressed=true; sair -> false. Lê o
                // estado atual de emulation_suppressed (não paused).
                let want_suppressed = !self
                    .state
                    .as_ref()
                    .map(|s| s.emulation_suppressed)
                    .unwrap_or(false);
                Task::perform(ipc::set_emulation_suppressed(want_suppressed), |res| {
                    cosmic::action::app(Message::GameModeToggled(res))
                })
            }

            Message::GameModeToggled(result) => {
                if let Ok(suppressed) = result {
                    if let Some(state) = self.state.as_mut() {
                        state.emulation_suppressed = suppressed; // otimista; refresh confirma
                    }
                }
                self.refresh_task()
            }

            Message::ToggleMic => {
                let want_on = !self.mic_on;
                spawn_mic(want_on);
                self.mic_on = want_on; // otimista; reconfirmado ao reabrir o popover
                Task::none()
            }

            Message::SetOutputTarget(index) => {
                // Atualização otimista; o refresh seguinte confirma.
                if let Some(state) = self.state.as_mut() {
                    state.output_target_index = index;
                }
                Task::perform(ipc::set_output_target(index), |res| {
                    cosmic::action::app(Message::OutputTargetSet(res))
                })
            }

            Message::OutputTargetSet(result) => {
                if let Ok(index) = result {
                    if let Some(state) = self.state.as_mut() {
                        state.output_target_index = index;
                    }
                }
                self.refresh_task()
            }
        }
    }

    fn view(&self) -> Element<'_, Message> {
        self.core
            .applet
            .icon_button(self.panel_icon())
            .on_press(Message::TogglePopup)
            .into()
    }

    fn view_window(&self, id: window::Id) -> Element<'_, Message> {
        if Some(id) != self.popup {
            return text::body("").into();
        }
        self.core
            .applet
            .popup_container(self.popup_content())
            .into()
    }

    fn subscription(&self) -> Subscription<Message> {
        // Só faz polling enquanto o popover está aberto.
        if self.popup.is_some() {
            cosmic::iced::time::every(std::time::Duration::from_millis(REFRESH_MS))
                .map(|_| Message::Refresh)
        } else {
            Subscription::none()
        }
    }

    fn style(&self) -> Option<cosmic::iced::theme::Style> {
        Some(cosmic::applet::style())
    }
}

impl HefestoApplet {
    /// Task que reconsulta `daemon.state_full`.
    fn refresh_task(&self) -> Task<Message> {
        Task::perform(ipc::fetch_state(), |res| {
            cosmic::action::app(Message::StateFetched(res))
        })
    }

    /// Glifo do painel: SEMPRE a logo do app. O estado (offline/bateria/perfil)
    /// vai no popover — manter o ícone fixo evita que a logo "suma" do painel
    /// quando o daemon fica offline (regressão relatada). Ver `ICON_APP`.
    fn panel_icon(&self) -> &'static str {
        ICON_APP
    }

    /// Conteúdo do popover.
    fn popup_content(&self) -> Element<'_, Message> {
        let spacing = self.core.system_theme().cosmic().spacing;
        let mut content = Column::new().padding([8, 0]).spacing(0);

        // Cabeçalho.
        content =
            content.push(padded_control(text::title4("Hefesto - Dualsense4Unix")).padding([8, 16]));
        content = content.push(padded_control(divider::horizontal::default()));

        // Bloco de status.
        content = content.push(self.status_block());
        content = content.push(padded_control(divider::horizontal::default()));

        // FEAT-DSX-CONTROLLER-SELECTOR-01: seletor de controle-alvo (2+ controles).
        if let Some(target) = self.target_block() {
            content = content.push(target);
            content = content.push(padded_control(divider::horizontal::default()));
        }

        // Lista de perfis.
        content = content.push(self.profiles_block());
        content = content.push(padded_control(divider::horizontal::default()));

        // Ação: modo jogo — suspende mouse/teclado, mantém o gamepad vivo no
        // jogo (FEAT-DSX-GAMEMODE-SUPPRESS-01, via daemon.emulation.suppress).
        // Transitório: não persiste em disco. Lê emulation_suppressed (não paused).
        let game_mode = self
            .state
            .as_ref()
            .map(|s| s.emulation_suppressed)
            .unwrap_or(false);
        let (game_icon, game_label) = if game_mode {
            ("media-playback-start-symbolic", "Sair do modo jogo")
        } else {
            ("input-gaming-symbolic", "Modo jogo")
        };
        content = content.push(
            menu_button(
                cosmic::iced::widget::row![
                    icon::from_name(game_icon).size(16),
                    text::body(game_label),
                ]
                .spacing(spacing.space_xs)
                .align_y(cosmic::iced::Alignment::Center),
            )
            .on_press(Message::ToggleGameMode),
        );

        // Ação: ligar/desligar o mic embutido do DualSense (o quirk segura o storm
        // com o mic ativo). Por padrão fica suprimido; liga sob demanda.
        let mic_label = if self.mic_on {
            "Desligar microfone"
        } else {
            "Ligar microfone"
        };
        content = content.push(
            menu_button(
                cosmic::iced::widget::row![
                    icon::from_name("audio-input-microphone-symbolic").size(16),
                    text::body(mic_label),
                ]
                .spacing(spacing.space_xs)
                .align_y(cosmic::iced::Alignment::Center),
            )
            .on_press(Message::ToggleMic),
        );

        // Ação: abrir painel.
        content = content.push(
            menu_button(
                cosmic::iced::widget::row![
                    icon::from_name("preferences-system-symbolic").size(16),
                    text::body("Abrir painel"),
                ]
                .spacing(spacing.space_xs)
                .align_y(cosmic::iced::Alignment::Center),
            )
            .on_press(Message::OpenPanel),
        );

        // Ação: fechar a janela da GUI (o daemon SEGUE rodando).
        content = content.push(
            menu_button(
                cosmic::iced::widget::row![
                    icon::from_name("window-close-symbolic").size(16),
                    text::body("Fechar painel"),
                ]
                .spacing(spacing.space_xs)
                .align_y(cosmic::iced::Alignment::Center),
            )
            .on_press(Message::ClosePanel),
        );

        // Ação: sair / desligar o daemon (o controle para até religar).
        content = content.push(
            menu_button(
                cosmic::iced::widget::row![
                    icon::from_name("application-exit-symbolic").size(16),
                    text::body("Sair (desligar Hefesto)"),
                ]
                .spacing(spacing.space_xs)
                .align_y(cosmic::iced::Alignment::Center),
            )
            .on_press(Message::StopDaemon),
        );

        content.into()
    }

    /// Linhas de status: conexão, transporte, bateria, perfil ativo.
    fn status_block(&self) -> Element<'_, Message> {
        let mut col = Column::new().spacing(2).padding([4, 0]);

        if self.offline || self.state.as_ref().map(|s| !s.connected).unwrap_or(false) {
            let msg = if self.offline {
                "Daemon desconectado"
            } else {
                "Nenhum controle conectado"
            };
            col = col.push(status_row("Estado", msg.to_string()));
            return col.into();
        }

        let Some(state) = &self.state else {
            col = col.push(status_row("Estado", "Consultando…".to_string()));
            return col.into();
        };

        // Transporte (USB/BT).
        let transport = match state.transport.as_deref() {
            Some("usb") => "USB".to_string(),
            Some("bluetooth") | Some("bt") => "Bluetooth".to_string(),
            Some(other) if !other.is_empty() => other.to_string(),
            _ => "—".to_string(),
        };
        // Bateria.
        let battery = match state.battery_pct {
            Some(pct) => format!("{pct}% ({transport})"),
            None => format!("— ({transport})"),
        };
        col = col.push(status_row("Bateria", battery));

        // Perfil ativo.
        let profile = state
            .active_profile
            .clone()
            .unwrap_or_else(|| "—".to_string());
        col = col.push(status_row("Perfil ativo", profile));

        // FEAT-DSX-MULTI-CONTROLLER-01: com 2+ controles, mostra quantos e os
        // transportes (ex.: "2 (BT + USB)"). Todos recebem o output em
        // broadcast; o input vem só do primário. Daemon antigo sem o bloco
        // `controllers` cai na lista vazia e a linha some.
        let conectados: Vec<_> =
            state.controllers.iter().filter(|c| c.connected).collect();
        if conectados.len() > 1 {
            let transportes: Vec<String> = conectados
                .iter()
                .map(|c| match c.transport.as_deref() {
                    Some("usb") => "USB".to_string(),
                    Some("bluetooth") | Some("bt") => "BT".to_string(),
                    Some(other) if !other.is_empty() => other.to_uppercase(),
                    _ => "?".to_string(),
                })
                .collect();
            col = col.push(status_row(
                "Controles",
                format!("{} ({})", conectados.len(), transportes.join(" + ")),
            ));
        }

        // FEAT-DSX-GAMEMODE-SUPPRESS-01: modo jogo (mouse/teclado suspensos,
        // gamepad vivo). Transitório — distinto do pause persistente do daemon.
        if state.emulation_suppressed {
            col = col.push(status_row(
                "Modo jogo",
                "ligado (mouse/teclado suspensos)".to_string(),
            ));
        }

        // FEAT-DAEMON-PAUSE-RESUME-01: indica pausa dura (daemon vivo, sem input).
        if state.paused {
            col = col.push(status_row(
                "Estado",
                "Pausado (sem enviar input)".to_string(),
            ));
        }

        col.into()
    }

    /// Seletor do controle-alvo das ações de output (FEAT-DSX-CONTROLLER-SELECTOR-01).
    ///
    /// Só aparece com 2+ controles conectados (com 0/1 o broadcast é trivial).
    /// Lista "Todos (broadcast)" + um item por controle; clicar envia
    /// `controller.target.set`. O alvo atual é marcado com "> " e não re-dispara.
    fn target_block(&self) -> Option<Element<'_, Message>> {
        let state = self.state.as_ref()?;
        let conectados: Vec<_> = state.controllers.iter().filter(|c| c.connected).collect();
        if conectados.len() < 2 {
            return None;
        }
        let active = state.output_target_index;

        let mut col = Column::new().spacing(0).padding([4, 0]);
        col = col.push(padded_control(text::caption_heading("CONTROLE-ALVO")).padding([4, 16]));

        // Opção "Todos" (broadcast = padrão).
        let todos_mark = if active.is_none() { "> " } else { "  " };
        let mut todos_btn = menu_button(text::body(format!("{todos_mark}Todos (broadcast)")));
        if active.is_some() {
            todos_btn = todos_btn.on_press(Message::SetOutputTarget(None));
        }
        col = col.push(todos_btn);

        for c in &conectados {
            let is_active = active == Some(c.index);
            let mark = if is_active { "> " } else { "  " };
            let transporte = match c.transport.as_deref() {
                Some("usb") => "USB",
                Some("bluetooth") | Some("bt") => "BT",
                _ => "?",
            };
            let label = format!("{mark}Controle {} — {transporte}", c.index + 1);
            let mut btn = menu_button(text::body(label));
            if !is_active {
                btn = btn.on_press(Message::SetOutputTarget(Some(c.index)));
            }
            col = col.push(btn);
        }

        Some(col.into())
    }

    /// Lista clicável de perfis (click -> profile.switch).
    fn profiles_block(&self) -> Element<'_, Message> {
        let active = self
            .state
            .as_ref()
            .and_then(|s| s.active_profile.clone())
            .unwrap_or_default();

        let mut col = Column::new().spacing(0).padding([4, 0]);
        col = col.push(padded_control(text::caption_heading("PERFIS")).padding([4, 16]));

        if self.profiles.is_empty() {
            let label = if self.offline {
                "Indisponível (daemon offline)"
            } else {
                "Nenhum perfil"
            };
            col = col.push(padded_control(text::body(label)));
            return col.into();
        }

        let mut list = Column::new().spacing(0);
        for profile in &self.profiles {
            let is_active = profile.name == active;
            let mark = if is_active { "> " } else { "  " };
            let label = format!("{mark}{}", profile.name);
            let mut btn = menu_button(text::body(label));
            // Não re-dispara switch no perfil já ativo nem durante uma troca.
            if !is_active && !self.switching {
                btn = btn.on_press(Message::SwitchProfile(profile.name.clone()));
            }
            list = list.push(btn);
        }

        // Rola se houver muitos perfis (limita altura do popover).
        col = col.push(scrollable(list).height(Length::Shrink).width(Length::Fill));
        col.into()
    }
}

/// Linha "rótulo … valor" para o bloco de status.
fn status_row<'a>(label: &'a str, value: String) -> Element<'a, Message> {
    padded_control(
        cosmic::iced::widget::row![
            text::body(label),
            cosmic::widget::Space::new().width(Length::Fill),
            text::body(value),
        ]
        .align_y(cosmic::iced::Alignment::Center),
    )
    .into()
}

/// Lança a GUI desacoplada do applet (best-effort; falha silenciosa).
fn spawn_gui() {
    let _ = std::process::Command::new(GUI_BIN)
        .stdin(std::process::Stdio::null())
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null())
        .spawn();
}

/// Fecha a janela da GUI (SIGTERM via `pkill -f`). O padrão `-gui` casa só a GUI,
/// nunca o daemon (cuja cmdline é "... daemon start"). best-effort; falha silenciosa.
fn spawn_close_gui() {
    let _ = std::process::Command::new("pkill")
        .arg("-f")
        .arg(GUI_BIN)
        .stdin(std::process::Stdio::null())
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null())
        .spawn();
}

/// Para o daemon via systemd --user. Saída limpa: como o serviço é
/// `Restart=on-failure`, o `stop` NÃO o ressuscita (fica parado até religar com
/// `hefesto-dualsense4unix daemon enable`). best-effort; falha silenciosa.
fn spawn_stop_daemon() {
    let _ = std::process::Command::new("systemctl")
        .arg("--user")
        .arg("stop")
        .arg("hefesto-dualsense4unix.service")
        .stdin(std::process::Stdio::null())
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null())
        .spawn();
}

/// Mic liberado quando NÃO há drop-ins de supressão (52/53) do WirePlumber.
/// FEAT-DUALSENSE-MIC-TOGGLE-01. Leitura de filesystem (a verdade do estado).
fn mic_is_on() -> bool {
    let Ok(home) = std::env::var("HOME") else {
        return false;
    };
    let base = std::path::Path::new(&home).join(".config/wireplumber/wireplumber.conf.d");
    let suppressed = [
        "52-hefesto-dualsense-disable-source.conf",
        "53-hefesto-dualsense-disable-output.conf",
    ]
    .iter()
    .any(|name| base.join(name).exists());
    !suppressed
}

/// Liga/desliga o mic do DualSense via CLI (best-effort; falha silenciosa).
fn spawn_mic(on: bool) {
    let action = if on { "on" } else { "off" };
    let _ = std::process::Command::new("hefesto-dualsense4unix")
        .arg("mic")
        .arg(action)
        .stdin(std::process::Stdio::null())
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null())
        .spawn();
}

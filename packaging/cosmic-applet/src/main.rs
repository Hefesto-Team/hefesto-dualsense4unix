mod app;
mod ipc;

fn main() -> cosmic::iced::Result {
    cosmic::applet::run::<app::HefestoApplet>(())
}

// "O impedimento para a acao impulsiona a acao. O que esta no caminho se torna o caminho." - Marco Aurelio

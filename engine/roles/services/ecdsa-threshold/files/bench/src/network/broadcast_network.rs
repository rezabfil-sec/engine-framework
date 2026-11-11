use async_trait::async_trait;

pub type Id = u16;

#[async_trait]
pub trait BroadcastSender {
    async fn send_p2p(&self, to: &Id, msg: &Vec<u8>);
    async fn broadcast(&self, msg: &Vec<u8>);
}

#[async_trait]
pub trait BroadcastReceiver {
    async fn next_msg(&mut self) -> Option<Vec<u8>>;
}

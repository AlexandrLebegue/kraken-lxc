import { execFile } from "node:child_process";

function remote(cmd) {
  execFile("ssh", ["-o", "BatchMode=yes", "-o", "ConnectTimeout=5", "pve55", `/usr/local/bin/kl-notify ${cmd}`],
    { timeout: 10000 },
    (err) => { if (err) console.log(`[kraken-notify] ${cmd} KO: ${err.message}`); });
}

export default function handler(event) {
  if (event.type !== "message") return;
  const ctx = event.context ?? {};
  if (ctx.channelId !== "telegram") return;
  if (event.action === "sent" && ctx.success) remote("add");
  else if (event.action === "received") remote("clear");
}

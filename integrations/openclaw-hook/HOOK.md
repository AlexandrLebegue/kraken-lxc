---
name: kraken-notify
description: "Compteur de notifications sur l'écran du Kraken (Proxmox .55)"
metadata:
  { "openclaw": { "emoji": "🦞", "events": ["message:sent", "message:received"], "requires": { "bins": ["ssh"] } } }
---

# Kraken notify

- `message:sent` réussi sur Telegram : `kl-notify add` sur l'hôte .55 (pastille +1).
- `message:received` sur Telegram : `kl-notify clear` (Chef a répondu, donc lu).

Telegram ne transmet pas d'accusé de lecture aux bots : la réponse de Chef sert
d'indicateur de lecture. Appel SSH via l'alias `pve55` (~/.ssh/config).

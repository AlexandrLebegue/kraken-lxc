# kraken-lxc

Tableau de bord sur l'écran LCD d'un NZXT Kraken 2024 Plus (`1e71:3014`) et couleurs des ventilateurs
et de la carte mère (Gigabyte RGB Fusion 2.0, `048d:5702`) selon l'état d'un hôte Proxmox VE.

## Fonctionnement
- **Écran** (~15 img/s) : état des LXC, pastille de notifications OpenClaw, température CPU,
  barre de température, charge CPU, RAM. Effet **neige** sous 45 °C, **feu** au-dessus de 70 °C.
- **Ventilateur 1 + carte mère** : vert si tous les LXC `onboot: 1` tournent, orange sinon.
- **Ventilateur 2** : température CPU (bleu froid -> rouge chaud), par paliers de 5 °C.
- **Notifications** : `kl-notify add|clear|count` (état dans `/run/kraken-lxc/notify.json`).
  Le hook OpenClaw `integrations/openclaw-hook` incrémente à chaque message envoyé sur Telegram
  et remet à zéro quand l'utilisateur répond (Telegram ne fournit pas d'accusé de lecture aux bots).

## Installation (hôte Proxmox)
```
cp systemd/kraken-lxc.service /etc/systemd/system/ && systemctl enable --now kraken-lxc
ln -sf /opt/kraken-lxc/kl-notify /usr/local/bin/kl-notify
```
Python : venv pipx de liquidctl 1.16 (`--system-site-packages`, + `python3-numpy`).
Test des effets : `python -m kraken_lxc.daemon --temp-override 30` (neige) ou `85` (feu).

## Modules
- `kraken_lxc/hue2.py` : couleurs des ventilateurs (protocole NZXT HUE2 Direct, repris d'OpenKraken, MIT).
- `kraken_lxc/lcd.py` : envoi d'images sans buckets (contourne liquidctl #908), synchronisé sur les
  acquittements `0x37` (méthode reprise de kori, GPL-3.0). GIF natif non supporté sur le Plus.
- `kraken_lxc/render.py`, `metrics.py`, `notify.py`, `daemon.py` : tableau de bord et service.

## Licences tierces
OpenKraken (MIT), kori (GPL-3.0, méthode de synchronisation), liquidctl (GPL-3.0).
Choisir une licence compatible GPL-3.0 avant publication.

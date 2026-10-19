# kraken-lxc

Tableau de bord sur l'écran LCD d'un NZXT Kraken 2024 Plus (`1e71:3014`) et couleurs des ventilateurs
et de la carte mère (Gigabyte RGB Fusion 2.0, `048d:5702`) selon l'état d'un hôte Proxmox VE.

## Fonctionnement
- **Écran** (~15 img/s) : robot (content si tous les LXC `onboot: 1` tournent, sinon triste avec un
  « ! » rouge), homard OpenClaw avec pastille de notifications, température CPU, barre de
  température d'une couleur qui respire (2 s), charge CPU, RAM.
- **Palette de température** (barre, ventilateurs, carte mère) : bleu <-> violet à froid, rouge <->
  orange à chaud, transition progressive entre les deux (25 -> 90 °C).
- **Ventilateurs + carte mère** : même palette, respiration lente (20 s, teinte et éclat), 3,5 màj/s max sur les ventilateurs.
- **Extinction programmée des LED** (ventilateurs + carte mère) : par défaut de 00:00 à 07:00, avec un
  fondu (6 s) de la couleur courante à l'extinction comme au rallumage ; l'écran reste allumé. Options :
  `--lights-off HH:MM` (ou `none`), `--lights-on HH:MM`, `--fade SECONDES` (dans `ExecStart` du service).
- **Notifications** : `kl-notify add|clear|count` (état dans `/run/kraken-lxc/notify.json`).
  Le hook OpenClaw `integrations/openclaw-hook` incrémente à chaque message envoyé sur Telegram
  et remet à zéro quand l'utilisateur répond (Telegram ne fournit pas d'accusé de lecture aux bots).

## Installation (hôte Proxmox)
```
cp systemd/kraken-lxc.service /etc/systemd/system/ && systemctl enable --now kraken-lxc
ln -sf /opt/kraken-lxc/kl-notify /usr/local/bin/kl-notify
```
Python : venv pipx de liquidctl 1.16 (`--system-site-packages`, + `python3-numpy`).
Test des couleurs : `python -m kraken_lxc.daemon --temp-override 30` (froid) ou `85` (chaud).

## Modules
- `kraken_lxc/hue2.py` : couleurs des ventilateurs (protocole NZXT HUE2 Direct, repris d'OpenKraken, MIT).
- `kraken_lxc/lcd.py` : envoi d'images sans buckets (contourne liquidctl #908), synchronisé sur les
  acquittements `0x37` (méthode reprise de kori, GPL-3.0). GIF natif non supporté sur le Plus.
- `kraken_lxc/render.py`, `metrics.py`, `notify.py`, `daemon.py` : tableau de bord et service.

## Licences tierces
OpenKraken (MIT), kori (GPL-3.0, méthode de synchronisation), liquidctl (GPL-3.0).

## Licence
GPL-3.0-or-later (voir `LICENSE`).

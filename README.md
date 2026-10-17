# kraken-lxc

Pilotage des LED et de l'écran d'un NZXT Kraken 2024 Plus (`1e71:3014`) et du RGB de la carte mère
(Gigabyte RGB Fusion 2.0, `048d:5702`) en fonction de l'état des LXC d'un hôte Proxmox VE.

- Kraken (pompe/ventilos/LCD) et RGB carte mère : [liquidctl](https://github.com/liquidctl/liquidctl) 1.16+
- Couleurs anneau de pompe + ventilateurs RGB Core : protocole NZXT HUE2 "Direct", repris
  d'[OpenKraken](https://github.com/davidboulay/OpenKraken) (MIT)

## Statut
Phase de test (`probe.py`).

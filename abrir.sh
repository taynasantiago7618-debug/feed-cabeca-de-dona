#!/bin/bash
# Abre o feed no navegador do seu computador.
# Uso: bash abrir.sh           (busca artigos novos e abre)
#      bash abrir.sh --so-abrir (só abre, sem buscar)
cd "$(dirname "$0")"
if [ "$1" != "--so-abrir" ]; then
  /usr/bin/python3 buscar_artigos.py
fi
(sleep 1 && open "http://localhost:8790") &
/usr/bin/python3 -m http.server 8790

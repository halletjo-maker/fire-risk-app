# Vidéos courtes MM100 (Shorts, Reels, TikTok)

Vidéos verticales 1080×1920, texte animé, sans son. Chaque vidéo = un fichier `v_*.html`
(scènes avec `data-start` / `data-end` en secondes, éléments `data-in`) ; la durée totale est
dans le commentaire `<!-- TOTAL=… -->`.

Fabriquer une vidéo (Chromium/Playwright et ffmpeg nécessaires, polices du frontend installées) :

    python3 build.py v_tob.html            # → out_tob.html
    node make.js "$PWD/out_tob.html" "$PWD/mm100-tob.mp4"

Les kits de publication (titres, descriptions, hashtags, voix off) sont dans `kit-publication-*.md`.
Les fichiers `out_*.html` et `*.mp4` ne sont pas versionnés.

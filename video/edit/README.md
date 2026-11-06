# Aura — монтаж (Remotion)

3 минуттық 1920×1080 промо-ролик: озвучка (Adi, eleven_v4), ElevenLabs музыкасы мен
SFX, телефон мокапы, кинетикалық типографика, сахна ауысулары.

```bash
cd video/edit
npm install
./prepare.sh          # клиптер мен дауысты public/ ішіне көшіреді
npm run studio        # алдын ала көру
npm run render        # → out/aura_promo.mp4
```

Сахналар уақыты `src/Promo.tsx` ішіндегі `SCENES` массивінде және озвучка бөліктеріне
сәйкес келеді (`video/voice/adi/timings.json`). Мәтінді өзгерту — сол файлдағы
`Kinetic` / `Chip` жолдары.

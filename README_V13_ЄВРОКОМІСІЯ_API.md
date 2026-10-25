# V13: Європейська комісія — перший офіційний числовий збирач

- Офіційний API: https://api.tech.ec.europa.eu/agrifood/api/cereal/prices
- Документація: https://agridata.ec.europa.eu/extensions/API_Documentation/cereals.html
- `collect-eu-cereals.mjs` працюватиме раз на добу о 05:40 UTC **лише після деплою**. Зараз живу роботу зовнішнього API з цього середовища не перевірено.
- `eu-cereals-status.mjs`: read-only перевірка: `/.netlify/functions/eu-cereals-status`.
- Збираємо останні 60 днів, зберігаємо власну історію Netlify Blobs; повтори відсіюємо.
- Приймаємо тільки явний €/тонну, дату, державу, тип зерна, назву ринку, базис. Не переводимо ці дані в ціну господарства і не включаємо до економічного рейтингу покупців.
- Повний ряд із 6 культур поки НЕ забезпечено: цей перший потік — зернові, а не олійні. Для сої, соняшнику і ріпаку потрібні окремі підтверджені endpoints.
- USDA FAS PSD потребує API-ключа. Наявний у старіших файлах вторинний USDA snapshot НЕ видавати за прямий USDA API-збір.
- ВАЖЛИВО: пройдені unit-тести — не підтвердження реального Netlify Scheduled Function; до публікації збірка накопичувальна.

Після великого деплою перевірити `/.netlify/functions/eu-cereals-status` — значення `status=ok`, `records_total>0`, `last_success` і sample з правильними `unit`, `stage` та `product_name`. Якщо status=error — звірити logs Netlify, схему API.

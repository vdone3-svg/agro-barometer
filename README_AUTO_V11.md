# AGRO BAROMETER — Auto V11: єдина база транспортних ставок

## Що додано
- `/.netlify/functions/freight-rates` — читання спостережень через GET.
- Захищене внесення 1–50 ставок за запит через POST лише з Netlify Environment Variable `FREIGHT_ADMIN_TOKEN` (мінімум 24 символи). **Не вводьте токен у публічні файли GitHub**.
- Окреме сховище Netlify Blobs `agro-freight-rates / freight-v11`, яке не зачіпає ринкові дані та барометри.
- Публічна таблиця лише для перегляду. Поки що реєстр порожній — ставки не вигадуються.
- Одиниці: UAH за рейс АБО UAH/т; з розрахунком UAH/т і UAH/(т·км).
- Напрямок маршруту фіксується; зворотні ставки не вважаються еквівалентними.
- Без автоматичного скрейпінгу DELLA, DeGruz, Transportica. Дозвіл на використання даних треба з'ясувати окремо.

## Встановлення
1. Розпакуйте архів; завантажте **вміст** у корінь репозиторію GitHub `main` зі збереженням папок.
2. Дочекайтеся Netlify Published. Відкрийте `/.netlify/functions/freight-rates`: очікується `records_total: 0`.
3. На головній сторінці знайдіть «Єдина база транспортних ставок — Auto V11».
4. Для майбутнього внесення встановіть у налаштуваннях Netlify змінну `FREIGHT_ADMIN_TOKEN` зі випадковим секретом 24+ символи. НЕ публікуйте секрет ніде. Запис здійснюється через зовнішній захищений запит POST JSON. Без змінної запис відключений.
5. Нічого не запускати в `collect-morning`: це незалежний реєстр.

## Обов'язкові поля одного запису
`source_name`, `source_url`, `observed_date` (YYYY-MM-DD), `origin_city`, `destination_city`, `distance_km`, `vehicle_type` (`grain_truck` або `other`), `cargo_type`, `load_tonnes`, `payment_type` (`cash`, `bank`, `unknown`), `vat_status` (`included`, `excluded`, `unknown`), `evidence_status` (`unverified_listing`, `carrier_quote`, `verified_document`) і **одне** із `trip_price_uah` або `price_per_tonne_uah`.

Приклад тільки для структури, **не реальна ставка**:
```json
{"records":[{"source_name":"DEMO — не імпортувати","source_url":"https://example.org/quote","observed_date":"2026-10-20","origin_city":"Олександрія","destination_city":"Ізмаїл","distance_km":648,"vehicle_type":"grain_truck","cargo_type":"пшениця","load_tonnes":25,"payment_type":"bank","vat_status":"unknown","evidence_status":"unverified_listing","trip_price_uah":50000}]}
```

## Важлива межа
Наразі це **реєстр ставок, не готовий автоматичний збирач тарифів та не економічний фільтр**. `validated_for_market_model` примусово `false`. Для автоматичних середніх, приховання покупців та рекомендацій потрібні контроль джерел, порівнюваність і достатні спостереження. Не підставляйте у реєстр умовні 3 грн/т·км з попередніх тестів.

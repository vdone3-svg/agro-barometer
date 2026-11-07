"""
AGRO BAROMETER — щоденні висновки по культурах («Резюме по-простому»).

Генерує через Google Gemini API, безкоштовний рівень (ключ з aistudio.google.com, без картки) —
секрет GEMINI_API_KEY у GitHub. 6 запитів на день — далеко в межах безкоштовних лімітів.
(GitHub Models, який планувався спочатку, GitHub закрив 30.07.2026.)

Запобіжники:
  • модель отримує ЛИШЕ зібрані сьогодні цифри й заголовки новин;
  • кожне число ≥1000 у відповіді звіряється з вхідними (допуск 2%) — вигадане число → повтор, далі фолбек;
  • фолбек без моделі — лише факти, без порад «продавати/тримати» (поради не вигадуються правилами).
"""
import json, os, re, time, urllib.request, urllib.error

ENDPOINT = os.environ.get("SUMMARY_ENDPOINT", "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions")
MODELS = [m.strip() for m in os.environ.get("SUMMARY_MODELS", "gemini-2.5-flash,gemini-2.5-flash-lite").split(",") if m.strip()]
TRIP_T = 25
PAUSE_S = float(os.environ.get("SUMMARY_PAUSE_S", "7"))  # безкоштовний рівень: ~10 запитів/хв

VERDICTS = {  # ключ → (ярлик за замовчуванням, css-клас шаблону)
    "sell":  ("Продавати", "v-sell"),
    "split": ("Частину зараз, решту тримати", "v-split"),
    "hold":  ("Тримати, не поспішати", "v-hold"),
    "none":  ("Даних замало для висновку", "v-split"),
}

CROP_NEWS_KW = {
    "ріпак": r"ріпак|рапс|rapeseed|canola",
    "соняшник": r"соняшн|подсолн|sunflower|олі[яї]",
    "соя": r"\bсо[яїю]\b|соєв|soy",
    "кукурудз": r"кукурудз|кукуруз|corn|maize",
    "ячмінь": r"ячмін|ячмен|barley",
    "пшениц": r"пшениц|wheat",
}
GENERAL_NEWS_KW = r"порт|логіст|експорт|USDA|WASDE|дунай|ізмаїл|рені|залізниц|фрахт|коридор|біржа|CBOT|Euronext"

SYSTEM = """Ти — досвідчений аналітик зернового ринку України, пишеш для фермера з Кіровоградщини (господарство біля Олександрії, точки відвантаження Долинське і Копані, найманий зерновоз 25 т).
Пиши українською, простою людською мовою досвідченого агронома: коротко, конкретно, без канцеляриту і загальних фраз.
СТИЛЬ: без привітань і звертань («привіт», «сусіде», «друже»), не згадуй дату і місто господарства. Кожен абзац — до 60 слів.
Не перелічуй усі числа: 2–4 ключові на абзац. Net наводь для однієї точки (кращої), іншу — лише якщо різниця суттєва.
Числа пиши з пробілами між тисячами: **18 990 ₴/т**, за рейс — округлено: **≈475 тис. ₴**. Якщо зміна ціни 0 або даних про зміну немає — не згадуй її.

ЖОРСТКІ ПРАВИЛА:
1. Використовуй ЛИШЕ числа з наданих даних. Не вигадуй цін, ставок, прогнозів, відсотків чи дат. Якщо потрібного числа немає — пиши словами («даних немає»).
2. Ціни — це опубліковані пропозиції, не підписані угоди. Фрахт — орієнтовна оцінка, не оферта перевізника; це треба один раз згадати, якщо спираєшся на net.
3. Новини використовуй лише ті, що надані. Загальні сезонні закономірності можна згадувати лише як «зазвичай», без цифр.
4. Якщо даних мало (немає порівнюваних цін або лише 1–2 пропозиції) — verdict "none" і чесно напиши, чого бракує.
5. Висновок: продавати / частину зараз, решту тримати / тримати. Поясни ЧОМУ — через ціну, net, зміну за тиждень/місяць, новини.

Відповідай СТРОГО JSON без markdown:
{"verdict":"sell|split|hold|none","label":"коротко, до 40 знаків, напр. «Продавати до кінця грудня»","paragraphs":["абзац 1","абзац 2","(необов'язково) абзац 3"],"todo":"Що робити: одне-два речення конкретних дій"}
У абзацах числа виділяй **так**."""


def _num(v):
    return None if v is None else round(float(v))


def build_context(culture, d, delta, news_items, usd_uah, date_str):
    """Компактний контекст однієї культури + множина дозволених чисел."""
    ctx = {"культура": culture, "дата": date_str, "курс_usd_uah": usd_uah}
    allowed = set()

    def keep(*vals):
        for v in vals:
            if isinstance(v, (int, float)) and v:
                allowed.add(abs(round(v)))

    if not d or not d.get("best_price"):
        ctx["ціни"] = "порівнюваних закупівельних цін сьогодні немає" + (
            f" (знайдено {d['records_count']} записів, жоден не пройшов перевірку)" if d else "")
    else:
        b = d["best_price"]
        ctx["найвища_ціна"] = {"₴/т": _num(b["price_uah"]), "пункт": b.get("location"), "регіон": b.get("region_norm"),
                               "джерело": b.get("source"), "базис": b.get("basis"), "дата": b.get("date")}
        keep(b["price_uah"])
        nets = {}
        for farm, key, fk in (("Долинське", "net_dolynske", "freight_dolynske"), ("Копані", "net_kopani", "freight_kopani")):
            r = (d.get("best_net") or {}).get(farm)
            if r:
                net = r[key]
                nets[farm] = {"net_₴/т": _num(net), "ціна_₴/т": _num(r["price_uah"]), "фрахт_оцінка_₴/т": r.get(fk),
                              "пункт": r.get("location"), "джерело": r.get("source"), "за_рейс_25т_₴": _num(net * TRIP_T)}
                keep(net, r["price_uah"], r.get(fk), net * TRIP_T)
            else:
                nets[farm] = "фрахт до покупців невідомий"
        ctx["найкраща_чиста_виручка"] = nets
        ctx["топ_пропозицій"] = [{"₴/т": _num(r["price_uah"]), "пункт": r.get("location"), "регіон": r.get("region_norm"),
                                  "джерело": r.get("source"), "дата": (r.get("date") or "")[:10]} for r in d.get("top", [])[:6]]
        for r in d.get("top", [])[:6]:
            keep(r["price_uah"])
        ctx["діапазон_₴/т"] = [_num(d["price_min"]), _num(d["price_max"])]
        ctx["порівнюваних_пропозицій"] = d.get("eligible_count")
        keep(d["price_min"], d["price_max"], d["price_max"] - d["price_min"])
    if delta:
        ctx["зміна_найвищої_ціни_₴/т"] = {"за_тиждень": delta.get("delta_7"), "за_місяць": delta.get("delta_30"),
                                          "примітка": "порівнюється найвища пропозиція дня, а не одного покупця — шумний показник"}
        keep(delta.get("delta_7"), delta.get("delta_30"))

    kw = next((v for k, v in CROP_NEWS_KW.items() if culture.startswith(k[:5])), culture)
    crop_news = [n for n in news_items if re.search(kw, f"{n.get('title','')} {n.get('summary','')}", re.I)][:6]
    gen_news = [n for n in news_items if n not in crop_news and re.search(GENERAL_NEWS_KW, n.get("title", ""), re.I)][:3]
    ctx["новини_по_культурі"] = [f"{n.get('source','')}: {n.get('title','')} — {(n.get('summary') or '')[:180]}" for n in crop_news] or "немає"
    ctx["загальні_новини_ринку"] = [f"{n.get('source','')}: {n.get('title','')}" for n in gen_news] or "немає"
    for n in crop_news + gen_news:  # числа з новин теж дозволені (включно з «2,4 млн т»)
        for v in _numbers_in(f"{n.get('title','')} {n.get('summary','')}"):
            keep(v)
    keep(usd_uah, TRIP_T)
    return ctx, allowed


def _numbers_in(text):
    """Числа ≥1000 з тексту, з урахуванням «19 700», «19,7 тис.», «1,5 млн»."""
    out = []
    t = text.replace(" ", " ").replace(" ", " ")
    for m in re.finditer(r"(\d+(?:[.,]\d+)?)\s*(тис|млн)", t):
        v = float(m.group(1).replace(",", "."))
        out.append(round(v * (1000 if m.group(2) == "тис" else 1_000_000)))
    t2 = re.sub(r"(\d+(?:[.,]\d+)?)\s*(тис|млн)", " ", t)
    for m in re.finditer(r"\d{1,3}(?: \d{3})+|\d{4,}", t2):
        out.append(int(m.group(0).replace(" ", "")))
    return [n for n in out if n >= 1000 and not (2020 <= n <= 2035)]  # роки не перевіряємо


def invented_numbers(summary, allowed):
    text = " ".join(summary.get("paragraphs", [])) + " " + summary.get("todo", "") + " " + summary.get("label", "")
    bad = []
    for n in _numbers_in(text):
        if not any(abs(n - a) <= max(0.02 * a, 50) for a in allowed):
            bad.append(n)
    return bad


def _call(model, messages, token):
    import requests
    r = requests.post(ENDPOINT, timeout=75, json={"model": model, "messages": messages, "temperature": 0.3,
                                                   "max_tokens": 2500, "reasoning_effort": "low", "response_format": {"type": "json_object"}},
                      headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    if r.status_code >= 400:
        raise urllib.error.HTTPError(ENDPOINT, r.status_code, r.text[:300], {}, None)
    try:
        content = r.json()["choices"][0]["message"]["content"] or ""
    except Exception:
        raise ValueError(f"API не дав JSON: HTTP {r.status_code} {r.text[:200]!r}")
    if "{" not in content:
        raise ValueError(f"у відповіді моделі немає JSON: {content[:300]!r}")
    return content


def _parse(raw):
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip()
    s = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
    v = s.get("verdict") if s.get("verdict") in VERDICTS else "none"
    raw_p = s.get("paragraphs") or []
    if isinstance(raw_p, str):
        raw_p = re.split(r"\n\s*\n|\n", raw_p)
    paras = [str(p).strip() for p in raw_p if str(p).strip()][:3]
    if len(paras) == 1:  # один довгий абзац → ділимо по реченнях навпіл
        sents = re.split(r"(?<=[.!?])\s+", paras[0])
        if len(sents) >= 3:
            k = len(sents) // 2
            paras = [" ".join(sents[:k]), " ".join(sents[k:])]
    if len(paras) < 2:
        raise ValueError("менше двох абзаців")
    todo = str(s.get("todo") or "").strip()
    if todo and not todo.lower().startswith("що робити"):
        todo = "Що робити: " + todo
    return {"verdict": v, "label": (str(s.get("label") or "").strip() or VERDICTS[v][0])[:48],
            "paragraphs": paras, "todo": todo}


def fallback(culture, d):
    """Без моделі: лише факти, без порад."""
    if not d or not d.get("best_price"):
        p = ["Сьогодні по цій культурі немає жодної порівнюваної закупівельної ціни, тож чесного висновку дати не можна."]
    else:
        b = d["best_price"]
        p = [f"Найвища опублікована закупівельна ціна — **{round(b['price_uah']):,} ₴/т** ({b.get('location') or 'пункт не вказано'}, {b.get('source')}). "
             f"Усього порівнюваних пропозицій: {d.get('eligible_count')}.".replace(",", " ")]
    p.append("Автоматичний висновок сьогодні не сформувався (модель недоступна або відповідь не пройшла перевірку цифр), тому порад продавати чи тримати тут немає. Дивіться таблицю цін нижче.")
    label = VERDICTS["none"][0] if not d or not d.get("best_price") else "Висновок сьогодні не сформовано"
    return {"verdict": "none", "label": label, "paragraphs": p, "todo": "", "model": None, "auto": False}


def discover_models(token):
    """Список доступних моделей від Google → Flash (не lite) новіші першими, далі Flash-Lite."""
    import requests
    try:
        r = requests.get(ENDPOINT.rsplit("/chat/", 1)[0] + "/models", timeout=30,
                         headers={"Authorization": f"Bearer {token}"})
        ids = [m["id"].split("/")[-1] for m in r.json().get("data", [])]
    except Exception as e:
        print(f"  ⚠️ список моделей недоступний: {e}")
        return []
    flash = [i for i in ids if "flash" in i and not re.search(r"image|tts|live|audio|embed|thinking|exp|preview", i)]
    def ver(i):
        m = re.search(r"(\d+(?:\.\d+)?)", i); return float(m.group(1)) if m else 0
    full = sorted([i for i in flash if "lite" not in i], key=ver, reverse=True)
    lite = sorted([i for i in flash if "lite" in i], key=ver, reverse=True)
    print(f"  ℹ️ доступні Flash-моделі: {full[:4] + lite[:3]}")
    # Flash-Lite першою: безкоштовна квота ~500 запитів/добу (у повної Flash — ~20, вичерпується)
    return lite[:1] + full[:1] + lite[1:2]


def generate(cultures, prices, deltas, news_items, usd_uah, date_str, emoji=None):
    token = os.environ.get("GEMINI_API_KEY") or os.environ.get("SUMMARY_API_KEY")
    out = {}
    if not token or os.environ.get("SUMMARIES_DISABLED") == "1":
        print("  ⚠️ висновки: немає GEMINI_API_KEY у secrets — показуємо лише факти, без порад")
        return {c: fallback(c, prices.get(c)) for c in cultures}
    global MODELS
    if not os.environ.get("SUMMARY_MODELS"):
        found = discover_models(token)
        if found:
            MODELS = found
    for i, c in enumerate(cultures):
        ctx, allowed = build_context(c, prices.get(c), (deltas or {}).get(c), news_items, usd_uah, date_str)
        user = "Дані на сьогодні (JSON):\n" + json.dumps(ctx, ensure_ascii=False)
        messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]
        result = None
        for model in MODELS:
            for attempt in range(2):
                try:
                    if i or attempt or model != MODELS[0]:
                        time.sleep(PAUSE_S)
                    raw = _call(model, messages, token)
                    s = _parse(raw)
                    bad = invented_numbers(s, allowed)
                    if bad:
                        print(f"  ✂ {c} [{model}]: числа не з даних {bad[:5]} — повтор")
                        messages = messages[:2] + [{"role": "assistant", "content": raw}, {"role": "user", "content":
                                   f"У тексті є числа, яких немає в даних: {bad[:5]}. Перепиши, використовуючи лише надані числа. Тільки JSON."}]
                        continue
                    s.update(model=model, auto=True)
                    result = s
                    break
                except urllib.error.HTTPError as e:
                    if e.code == 503 and attempt == 0:
                        print(f"  ⏳ {c} [{model}]: 503 перевантажено — чекаю 25 с і пробую ще раз")
                        time.sleep(25)
                        continue
                    print(f"  ⚠️ {c} [{model}]: HTTP {e.code} {' '.join(str(e.msg).split())[:220]}")
                    break  # 401/403/429 — до наступної моделі
                except Exception as e:
                    print(f"  ⚠️ {c} [{model}]: {type(e).__name__}: {str(e)[:160]}")
                    break  # таймаут/порожньо — одразу до наступної моделі
            if result:
                break
            messages = messages[:2]
        out[c] = result or fallback(c, prices.get(c))
        print(f"  {'✅' if result else '⚪'} висновок {c}: {out[c]['label']} ({out[c].get('model') or 'фолбек'})")
    return out

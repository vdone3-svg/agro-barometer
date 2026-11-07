"""
AGRO BAROMETER — щоденні висновки по культурах («Резюме по-простому»).

Генерує через GitHub Models (безкоштовно, вбудований GITHUB_TOKEN з правом models:read).
Кожна культура — окремий запит (ліміт безкоштовного рівня ~8k токенів на вхід).

Запобіжники:
  • модель отримує ЛИШЕ зібрані сьогодні цифри й заголовки новин;
  • кожне число ≥1000 у відповіді звіряється з вхідними (допуск 2%) — вигадане число → повтор, далі фолбек;
  • фолбек без моделі — лише факти, без порад «продавати/тримати» (поради не вигадуються правилами).
"""
import json, os, re, time, urllib.request, urllib.error

ENDPOINT = os.environ.get("GH_MODELS_ENDPOINT", "https://models.github.ai/inference/chat/completions")
MODELS = [m.strip() for m in os.environ.get("SUMMARY_MODELS", "openai/gpt-4.1,openai/gpt-4o,openai/gpt-4.1-mini").split(",") if m.strip()]
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
Пиши українською, простою людською мовою, як досвідчений сусід-агроном: коротко, конкретно, без канцеляриту і без загальних фраз.

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
    for n in crop_news + gen_news:  # числа з новин теж дозволені
        for m in re.findall(r"\d[\d\s ]{2,}\d|\d{4,}", f"{n.get('title','')} {n.get('summary','')}"):
            keep(int(re.sub(r"\D", "", m)))
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


ENDPOINTS = [ENDPOINT, "https://models.inference.ai.azure.com/chat/completions"]  # другий — старий шлях (модель без префікса)


def _call(model, messages, token):
    import requests
    last = None
    for ep in ENDPOINTS:
        m = model if "models.github.ai" in ep else model.split("/", 1)[-1]
        r = requests.post(ep, timeout=90, json={"model": m, "messages": messages, "temperature": 0.3, "max_tokens": 1200},
                          headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                                   "Accept": "application/json", "User-Agent": "agro-barometer/1.0"})
        if r.status_code in (401, 403, 429):
            raise urllib.error.HTTPError(ep, r.status_code, r.text[:200], {}, None)
        try:
            content = r.json()["choices"][0]["message"]["content"] or ""
        except Exception:
            last = f"{ep} → HTTP {r.status_code} {r.headers.get('content-type')} {r.text[:200]!r}"
            print(f"    ↪ {last}")
            continue
        if "{" not in content:
            raise ValueError(f"у відповіді моделі немає JSON: {content[:300]!r}")
        return content
    raise ValueError(f"API не дав JSON: {last}")


def _parse(raw):
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip()
    s = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
    v = s.get("verdict") if s.get("verdict") in VERDICTS else "none"
    paras = [str(p).strip() for p in (s.get("paragraphs") or []) if str(p).strip()][:3]
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
    return {"verdict": "none", "label": VERDICTS["none"][0], "paragraphs": p, "todo": "", "model": None, "auto": False}


def generate(cultures, prices, deltas, news_items, usd_uah, date_str, emoji=None):
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_MODELS_TOKEN")
    out = {}
    if not token or os.environ.get("SUMMARIES_DISABLED") == "1":
        print("  ⚠️ висновки: немає GITHUB_TOKEN — фолбек без порад")
        return {c: fallback(c, prices.get(c)) for c in cultures}
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
                    print(f"  ⚠️ {c} [{model}]: HTTP {e.code} {e.read()[:200]!r}")
                    break  # 401/403/429 — до наступної моделі
                except Exception as e:
                    print(f"  ⚠️ {c} [{model}]: {type(e).__name__}: {e}")
            if result:
                break
            messages = messages[:2]
        out[c] = result or fallback(c, prices.get(c))
        print(f"  {'✅' if result else '⚪'} висновок {c}: {out[c]['label']} ({out[c].get('model') or 'фолбек'})")
    return out

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

SYSTEM = """Ти — досвідчений трейдер і аналітик зернового ринку України. Пишеш щоденний висновок для власника агропідприємства
біля Олександрії (Кіровоградщина): 2000 га, власне зберігання, відвантаження найманим зерновозом 25 т з двох точок — Долинське і Копані.
Він фінансист, читає уважно; йому потрібна думка фахівця з аргументами, а не переказ цифр.

ЯК ДУМАТИ (по кожній культурі):
1. Де зараз найвигідніше: порівняй найкращий net (після фрахту) з альтернативою поруч — місцевими покупцями/переробниками
   (дані «поріг_місцевого_покупця»). Якщо далекий порт дає net лише трохи більше за місцевий поріг — скажи, що варто торгуватися з місцевими.
2. Чому ціна така і куди вона, найімовірніше, піде: спирайся на надані новини (порти, експорт, переробка, світові ринки, урожай у світі)
   і сезонність. Сезонні закономірності — лише словами «зазвичай», без цифр.
3. Ризики: що може зламати висновок (порти, погода, курс, тиск нового врожаю, переробка).
4. Рішення: продавати / частину зараз, решту тримати / тримати. Власне зберігання є, тож тримати недорого, але гроші заморожені.
   Тримати радь лише тоді, коли є конкретна причина чекати зростання; якщо причини немає — так і скажи.

ЖОРСТКІ ПРАВИЛА:
- Числа — ЛИШЕ з наданих даних (ціни, net, фрахт, пороги, числа з новин). Не вигадуй цін, прогнозів, відсотків, дат.
  Не обіцяй майбутньої ціни числом.
- Не пиши застережень «ціни — пропозиції, не угоди» чи «фрахт — оцінка»: це вже написано на сайті.
- Без привітань і звертань. Не повторюй назву культури на початку. Без канцеляриту і загальників
  («ринок нестабільний», «слід уважно стежити»). Простою мовою, але як фахівець.
- 3 абзаци, кожен 35–70 слів: (1) ціна і де вигідніше; (2) чому і куди рухається ринок; (3) головний ризик / що змінить рішення.
- Числа з пробілами між тисячами: **18 990 ₴/т**; за рейс округлено: **≈475 тис. ₴**. 2–4 ключові числа на абзац, виділяй **так**.
- «todo» — конкретні дії: яку частку продати, до якого часу, кому подзвонити/з ким торгуватися, на яку ціну орієнтуватися.
- Якщо порівнюваних цін немає — verdict "none": коротко скажи, що бракує даних, і що з новин важливо по культурі.

ПРИКЛАД СТИЛЮ (цифри застарілі — НЕ копіюй їх):
"Ріпак зараз — найдорожча культура на тонну. Порт в Одесі дає 21 200 ₴/т, після фрахту з Долинського лишається ~19 700 ₴/т,
це близько 490 тис. ₴ за машину. Біржа в Парижі стоїть, ціна тримається рівно. / А от далі краще не буде: з літа на ринок заходить
новий ріпак з Європи і тисне ціну. І є важливий момент: ГрадОлія в Кропивницькому сама переробляє ріпак, а везти туди в 5 разів дешевше.
Якщо вони дадуть від 19 975 ₴/т з доставкою — це вже вигідніше за Одесу. / Що робити: першим ділом подзвонити в ГрадОлію.
Продавати в листопаді–грудні, весни не чекати."

Відповідай СТРОГО JSON без markdown:
{"verdict":"sell|split|hold|none","label":"суть рішення до 40 знаків, напр. «Продавати до кінця грудня»","paragraphs":["…","…","…"],"todo":"Що робити: …"}"""


def _num(v):
    return None if v is None else round(float(v))


LOCAL_BUYERS = {  # зі слів власника (29.10.2026) + база джерел; цін їхніх у даних може не бути
    "ріпак": "ГрадОлія (ОЕЗ, Кропивницький — переробляє ріпак і соняшник; основний покупець власника)",
    "соняшник": "ГрадОлія і Kernel Придніпровський ОЕЗ (обидва Кропивницький; основні покупці власника)",
    "кукурудз": "МКО Транс-Сервіс (покупець кукурудзи, працює з власником), місцеві елеватори Кіровоградщини",
}
FREIGHT_LOCAL = {"Долинське": 300, "Копані": 115}  # до Кропивницького, ₴/т — оцінка (FREIGHT у build_barometer)


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
        # Поріг: скільки має дати покупець у Кропивницькому (з доставкою), щоб зрівнятися з найкращим net
        thr = {}
        for farm, key in (("Долинське", "net_dolynske"), ("Копані", "net_kopani")):
            r = (d.get("best_net") or {}).get(farm)
            if r:
                v = round(r[key] + FREIGHT_LOCAL[farm])
                thr[farm] = v; keep(v)
        if thr:
            ctx["поріг_місцевого_покупця_₴/т"] = {"пояснення": "якщо покупець у Кропивницькому дасть не менше цього (CPT завод), це вигідніше за найкращий net",
                                                  **thr}
        diff = None
        nd, nk = (d.get("best_net") or {}).get("Долинське"), (d.get("best_net") or {}).get("Копані")
        if nd and nk:
            diff = round(nk["net_kopani"] - nd["net_dolynske"]); keep(abs(diff))
            ctx["різниця_net_Копані_мінус_Долинське"] = diff
        local = [r for r in d.get("top", []) if r.get("region_norm") == "Кіровоградська"]
        ctx["ціни_Кіровоградщини"] = [{"₴/т": _num(r["price_uah"]), "пункт": r.get("location"), "джерело": r.get("source")} for r in local[:4]] or "у даних сьогодні немає"
        for r in local[:4]: keep(r["price_uah"])
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

    lb = next((v for k, v in LOCAL_BUYERS.items() if culture.startswith(k[:5])), None)
    if lb:
        ctx["місцеві_покупці_власника"] = lb
    ctx["власне_зберігання"] = "є"
    kw = next((v for k, v in CROP_NEWS_KW.items() if culture.startswith(k[:5])), culture)
    crop_news = [n for n in news_items if re.search(kw, f"{n.get('title','')} {n.get('summary','')}", re.I)][:8]
    gen_news = [n for n in news_items if n not in crop_news and re.search(GENERAL_NEWS_KW, n.get("title", ""), re.I)][:5]
    ctx["новини_по_культурі"] = [f"{n.get('source','')}: {n.get('title','')} — {(n.get('summary') or '')[:300]}" for n in crop_news] or "немає"
    ctx["загальні_новини_ринку"] = [f"{n.get('source','')}: {n.get('title','')} — {(n.get('summary') or '')[:160]}" for n in gen_news] or "немає"
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
    r = requests.post(ENDPOINT, timeout=45 if "lite" in model else 110, json={"model": model, "messages": messages, "temperature": 0.3,
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
    # Повна Flash першою (якісніший текст; 6 запитів/день вкладаються в ~20 безкоштовних),
    # при 429/503/таймауті — одразу Flash-Lite (~500/день)
    return full[:1] + lite[:2]


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

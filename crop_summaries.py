"""
AGRO BAROMETER — щоденні висновки по культурах («Резюме по-простому»).

Основний автор — Claude через підписку власника (Claude Code CLI, секрет CLAUDE_CODE_OAUTH_TOKEN).
Запасний — Google Gemini API, безкоштовний рівень (ключ з aistudio.google.com, без картки) —
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

SYSTEM = """Ти — досвідчений аналітик зернового ринку України. Пишеш щоденний короткий аналітичний висновок по культурі
для власника агропідприємства на Кіровоградщині. Він фінансист, читає уважно; йому потрібен аналіз ринку з аргументами.

ГОЛОВНЕ (вимога власника 16.11.2026):
- Конкретні оферти, «найкраща ціна», «найкраща пропозиція», «де/кому найвигідніше продати», чиста виручка, фрахт —
  НЕ пишеш узагалі. Усе це вже є на сайті нижче, в таблицях оферт із Telegram-каналів. Повтор — зайва вода.
- НЕ кажи, куди чи кому дзвонити, у кого що уточнити, з ким торгуватися, яким покупцям продавати. Жодних назв покупців.
- Твоє завдання — проаналізувати новини і загальний рух ринку: що відбувається, чому, куди це, найімовірніше, веде.

ЯК ДУМАТИ:
1. Стан ринку: куди рухається загальний рівень цін (медіана пропозицій, зміни за день/тиждень/місяць, середні по Україні) —
   без прив'язки до конкретних покупців і пунктів.
2. Чинники з новин: порти й логістика, експорт, переробка, урожай в Україні і світі, світові біржі, курс, сезонність
   (сезонні закономірності — лише словами «зазвичай», без цифр). Спирайся ЛИШЕ на надані новини; якщо новин по культурі немає — так і скажи.
3. Ризики: що може зламати висновок.
4. Рішення: продавати / частину зараз, решту тримати / тримати — з аналітичним обґрунтуванням. Власне зберігання є,
   тож тримати недорого, але гроші заморожені. Тримати радь лише з конкретною причиною чекати зростання.

ЖОРСТКІ ПРАВИЛА:
- Числа — ЛИШЕ з наданих даних (медіана, зміни, середні по Україні, бал барометра, числа з новин). Не вигадуй цін,
  прогнозів, відсотків, дат. Не обіцяй майбутньої ціни числом.
- Лапки всередині тексту — лише «ялинки», ніколи не прямі ". Тільки українська, без символів інших алфавітів.
- Не пиши застережень «ціни — пропозиції, не угоди»: це вже написано на сайті.
- Без привітань і звертань. Не повторюй назву культури на початку. Без канцеляриту і загальників
  («ринок нестабільний», «слід уважно стежити»). Простою мовою, але як фахівець.
- 3 абзаци, кожен 30–60 слів: (1) стан і рух ринку; (2) чинники з новин і куди веде; (3) головний ризик / що змінить висновок.
- Числа з пробілами між тисячами: **18 990 ₴/т**. 1–3 ключові числа на абзац, виділяй **так**.
- «todo» — короткий підсумок аналізу (1–2 речення): що з новин найважливіше і яке з цього випливає рішення
  (продавати / частину / тримати і чому). Без дзвінків, покупців, пунктів, цін торгу.
- Якщо даних про рух цін немає — verdict "none": коротко скажи, чого бракує, і що з новин важливо по культурі.
- «орієнтир_середні_по_Україні» — середні ціни ринку (GrainTrade), не оферта: можна згадати як рівень ринку.

ПРИКЛАД СТИЛЮ (цифри й події вигадані для прикладу — НЕ копіюй їх):
"Ринок стоїть: медіана пропозицій за тиждень майже не змінилася, середня по Україні тримається біля **21 000 ₴/т**. /
Підтримку дає Європа: біржа в Парижі росте другий тиждень через менший урожай у Канаді, а переробники в Україні
нарощують завантаження. Зазвичай до зими попит переробки тримає ціну. / Головний ризик — порти: нові обстріли Одещини
швидко знижують експортні ціни. Міцніша гривня теж зменшує ціну в гривні."
todo: "Висновок: зовнішній фон підтримує ціну, причин різкого падіння в новинах немає — частину можна притримати до зими."

Відповідай СТРОГО JSON без markdown:
{"verdict":"sell|split|hold|none","label":"суть рішення до 40 знаків, напр. «Частину тримати до зими»","paragraphs":["…","…","…"],"todo":"Висновок: …"}"""


def _num(v):
    return None if v is None else round(float(v))


# 16.11.2026: місцеві покупці й «планка для торгу» прибрані з висновку на вимогу власника — висновок лише аналітичний.


def build_context(culture, d, delta, news_items, usd_uah, date_str, now=None):
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
        # Лише рівень ринку: конкретні оферти, покупці й net у висновок не йдуть (вони в таблицях оферт нижче)
        seg = d.get("segments") or {}
        ctx["рівень_ринку"] = {
            "увага": "Загальний рівень опублікованих закупівельних пропозицій. НЕ називай конкретних покупців, пунктів, «найкращої ціни». "
                     "Порт/Дунай і внутрішній ринок (елеватори в областях), а також різні класи — НЕПОРІВНЮВАНІ: не зводь їх в одну ціну, "
                     "не називай загальну медіану рівнем ринку; говори про кожен сегмент окремо.",
            "за_ринком": [{"сегмент": x["name"], "медіана_₴/т": _num(x["median"]), "мін_₴/т": _num(x["min"]),
                           "макс_₴/т": _num(x["max"]), "пропозицій": x["n"]} for x in seg.get("market", [])],
            "порівнюваних_пропозицій": d.get("eligible_count"),
        }
        if seg.get("class"):
            ctx["рівень_ринку"]["за_класом"] = [{"сегмент": x["name"], "медіана_₴/т": _num(x["median"]), "пропозицій": x["n"]}
                                               for x in seg["class"]]
        for x in seg.get("market", []) + seg.get("class", []):
            keep(x["median"], x["min"], x["max"])
        keep(d["price_min"], d["price_max"])
    refs = (d or {}).get("reference") or []
    if refs:
        ctx["орієнтир_середні_по_Україні"] = {
            "увага": "Це СЕРЕДНІ закупівельні ціни по Україні за базисом (GrainTrade), а не пропозиція конкретного покупця. "
                     "Використовуй лише як загальний рівень ринку.",
            "дата": (refs[0].get("date") or "")[:10],
            "ціни": [{"базис": r.get("basis"), "якість": r.get("quality"), "₴/т": _num(r["price_uah"])} for r in refs],
        }
        for r in refs:
            keep(r["price_uah"])
    if delta:
        ctx["зміна_загальної_медіани_пропозицій_₴/т"] = {"за_день": delta.get("med_delta_1"), "за_тиждень": delta.get("med_delta_7"),
                                              "за_місяць": delta.get("med_delta_30"),
                                              "увага": "загальна медіана змішує порт і внутрішній ринок; зміна може бути через інший набір пропозицій, а не рух ринку — подавай обережно"}
        keep(delta.get("delta_1"), delta.get("delta_7"), delta.get("delta_30"),
             delta.get("med_delta_1"), delta.get("med_delta_7"), delta.get("med_delta_30"))
    if now:
        if now.get("score") is not None:
            ctx["барометр_зараз_0_100"] = {
                "бал": now["score"], "сигналів": f"{now['n_signals']} з {now.get('of', 3)}",
                "увага": "Розраховано з даних (не прогноз): вище = вигідніше продавати зараз. Назви бал у тексті.",
                # «premium» = найкраща оферта проти ринку — оферти у висновок не йдуть
                "сигнали": {k: v.get("note") for k, v in now["signals"].items() if k != "premium"}}
            keep(now["score"])
            for v in now["signals"].values():
                for k in ("best", "ref", "lo", "hi", "value_pct", "score"):
                    if isinstance(v.get(k), (int, float)):
                        keep(v[k])
        else:
            ctx["барометр_зараз_0_100"] = "не розраховано: " + str(now.get("why_none"))

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
        if not any(abs(n - a) <= max(0.006 * a, 15) for a in allowed):
            bad.append(n)
    return bad


def _call(model, messages, token):
    import requests
    r = requests.post(ENDPOINT, timeout=45 if "lite" in model else 120, json={"model": model, "messages": messages, "temperature": 0.3,
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


CLAUDE_MODELS = [m.strip() for m in os.environ.get("SUMMARY_CLAUDE_MODELS", "opus,sonnet").split(",") if m.strip()]


def _call_claude(model, messages, _token=None):
    """Claude Code CLI у headless-режимі; автентифікація — CLAUDE_CODE_OAUTH_TOKEN (підписка власника)."""
    import subprocess, tempfile
    system = messages[0]["content"]
    convo = "\n\n".join(("АСИСТЕНТ (попередня відповідь):\n" if m["role"] == "assistant" else "") + m["content"]
                         for m in messages[1:])
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(system); sp = f.name
    cmd = ["claude", "-p", "--model", model, "--output-format", "json", "--system-prompt-file", sp,
           "--tools", "", "--no-session-persistence", "--strict-mcp-config", "--setting-sources", ""]
    env = dict(os.environ)
    env["CLAUDE_CODE_OAUTH_TOKEN"] = re.sub(r"\s+", "", env.get("CLAUDE_CODE_OAUTH_TOKEN", ""))  # токен, скопійований з Термінала, буває з переносом рядка
    r = subprocess.run(cmd, input=convo, capture_output=True, text=True, timeout=240, cwd=tempfile.gettempdir(), env=env)
    try:
        out = json.loads(r.stdout)
    except Exception:
        raise ValueError(f"claude CLI rc={r.returncode}: {(r.stderr or r.stdout)[:300]!r}")
    if out.get("is_error") or r.returncode:
        raise ValueError(f"claude CLI помилка: {str(out.get('result') or out)[:300]}")
    content = out.get("result") or ""
    if "{" not in content:
        raise ValueError(f"у відповіді Claude немає JSON: {content[:200]!r}")
    return content


def _parse(raw):
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip()
    body = raw[raw.find("{"): raw.rfind("}") + 1]
    try:
        s = json.loads(body)
    except json.JSONDecodeError:
        from json_repair import repair_json
        s = json.loads(repair_json(body))
    if re.search(r"[\u0590-\u08FF\u0E00-\u0E7F\u3040-\u9FFF]", json.dumps(s, ensure_ascii=False)):
        raise ValueError("у тексті символи іншого алфавіту")
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
    todo = re.sub(r"^\s*(що робити|висновок)\s*:\s*", "", todo, flags=re.I)
    if todo:
        todo = "Висновок: " + todo
    return {"verdict": v, "label": (str(s.get("label") or "").strip() or VERDICTS[v][0])[:48],
            "paragraphs": paras, "todo": todo}


def fallback(culture, d):
    """Без моделі: лише факти, без порад."""
    if not d or not d.get("best_price"):
        p = ["Сьогодні по цій культурі немає жодної порівнюваної пропозиції покупця, тож чесного висновку дати не можна."]
        refs = (d or {}).get("reference") or []
        if refs:
            p.append("Орієнтир — середні ціни по Україні (GrainTrade, " + (refs[0].get("date") or "")[:5] + "): " +
                     "; ".join(f"{r.get('basis')}{' (' + r['quality'] + ')' if r.get('quality') else ''} **{round(r['price_uah']):,} ₴/т**".replace(",", " ")
                               for r in refs[:3]) + ". Це не оферта: пункт і фрахт невідомі.")
    else:
        segs = (d.get("segments") or {}).get("market") or []
        p = ["Рівень опублікованих закупівельних пропозицій: " + "; ".join(
                 f"{x['name']} — медіана **{round(x['median']):,} ₴/т** ({x['n']} проп.)".replace(",", " ") for x in segs)
             + ". Конкретні оферти — у таблицях нижче."] if segs else ["Конкретні оферти — у таблицях нижче."]
    p.append("Автоматичний висновок сьогодні не сформувався (модель недоступна або відповідь не пройшла перевірку цифр), тому порад продавати чи тримати тут немає.")
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
    older = [m for m in full if m != (full[:1] or [None])[0] and re.search(r"3\.5", m)]
    return full[:1] + older[:1] + lite[:1]  # найновіша Flash → стабільніша 3.5 Flash → Flash-Lite


def generate(cultures, prices, deltas, news_items, usd_uah, date_str, emoji=None, now=None):
    token = os.environ.get("GEMINI_API_KEY") or os.environ.get("SUMMARY_API_KEY")
    have_claude = bool(os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"))
    out = {}
    if (not token and not have_claude) or os.environ.get("SUMMARIES_DISABLED") == "1":
        print("  ⚠️ висновки: немає ні CLAUDE_CODE_OAUTH_TOKEN, ні GEMINI_API_KEY — лише факти, без порад")
        return {c: fallback(c, prices.get(c)) for c in cultures}
    global MODELS
    gem = []
    if token:
        gem = MODELS
        if not os.environ.get("SUMMARY_MODELS"):
            gem = discover_models(token) or MODELS
    # ланцюжок: Claude (підписка) → Gemini (безкоштовно) → фолбек
    MODELS = ([f"claude:{m}" for m in CLAUDE_MODELS] if have_claude else []) + gem
    print(f"  ℹ️ порядок моделей: {MODELS}")
    t0 = time.time(); BUDGET = float(os.environ.get("SUMMARY_BUDGET_S", "900"))
    for i, c in enumerate(cultures):
        if time.time() - t0 > BUDGET:  # не даємо висновкам «з'їсти» таймаут job → фолбек, деплой не страждає
            print(f"  ⏱ бюджет часу вичерпано — {c}: фолбек"); out[c] = fallback(c, prices.get(c)); continue
        ctx, allowed = build_context(c, prices.get(c), (deltas or {}).get(c), news_items, usd_uah, date_str,
                                     (now or {}).get(c))
        user = "Дані на сьогодні (JSON):\n" + json.dumps(ctx, ensure_ascii=False)
        messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]
        result = None
        models_c = MODELS if time.time() - t0 < BUDGET * 0.6 else [m for m in MODELS if "lite" in m or m.startswith("claude:sonnet")] or MODELS
        for model in models_c:
            for attempt in range(2):
                try:
                    if (i or attempt or model != MODELS[0]) and not model.startswith("claude:"):
                        time.sleep(PAUSE_S)
                    raw = _call_claude(model.split(":", 1)[1], messages) if model.startswith("claude:") else _call(model, messages, token)
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
                    print(f"  ⚠️ {c} [{model}]: {type(e).__name__}: {str(e)[:200]}")
                    if model.startswith("claude:") and re.search(r"auth|token|401|login|credit|limit", str(e), re.I):
                        MODELS[:] = [m for m in MODELS if not m.startswith("claude:")]  # без токена/ліміту — не мучимо Claude далі
                        print("  ↪ Claude недоступний — далі Gemini")
                    break  # таймаут/порожньо — одразу до наступної моделі
            if result:
                break
            messages = messages[:2]
        out[c] = result or fallback(c, prices.get(c))
        print(f"  {'✅' if result else '⚪'} висновок {c}: {out[c]['label']} ({out[c].get('model') or 'фолбек'})")
    return out

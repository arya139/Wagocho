import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import json, os, uuid, random, csv, threading, urllib.request
from datetime import datetime, timedelta
from pathlib import Path

# path
DATA_DIR = Path.home() / "JapaneseDictionaries"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# colors (im colorblind)
C_LIGHT = {
    "bg":       "#F5F0E8",
    "bg2":      "#EDE8DC",
    "bg3":      "#E2DBCC",
    "sidebar":  "#1F1F2E",
    "sidebar2": "#2A2A3E",
    "sidebar3": "#353550",
    "ink":      "#1A1A2E",
    "ink2":     "#4A4A6A",
    "ink3":     "#8888AA",
    "red":      "#C0392B",
    "red2":     "#E74C3C",
    "green":    "#27AE60",
    "gold":     "#D4A017",
    "blue":     "#2C5F8A",
    "blue2":    "#3A7AB5",
    "white":    "#FFFFFF",
    "sel":      "#D6EAF8",
    "entry_bg": "#FFFFFF",
    "entry_fg": "#1A1A2E",
    "alt_row":  "#F0EDE4",
}

C_DARK = {
    "bg":       "#0C0C0C",
    "bg2":      "#131313",
    "bg3":      "#1C1C1C",
    "sidebar":  "#060606",
    "sidebar2": "#0D0D0D",
    "sidebar3": "#141414",
    "ink":      "#D0D0D0",
    "ink2":     "#9AAABB",
    "ink3":     "#686870",   # lifted from #555555 so sidebar labels are legible
    "red":      "#C0392B",
    "red2":     "#E74C3C",
    "green":    "#6A8759",
    "gold":     "#FFC66D",
    "blue":     "#4A76B2",
    "blue2":    "#3A7AB5",
    "white":    "#FFFFFF",
    "sel":      "#162C4E",
    "entry_bg": "#111111",
    "entry_fg": "#D0D0D0",
    "alt_row":  "#0F0F0F",
}

C = C_LIGHT.copy() # start with light mode


FONT_UI  = ("Segoe UI", 10)
FONT_UIS = ("Segoe UI", 9)
FONT_UIB = ("Segoe UI", 10, "bold")
FONT_H1  = ("Segoe UI", 15, "bold")
FONT_H2  = ("Segoe UI", 12, "bold")

for _cjk in ["Yu Gothic UI","Meiryo UI","Hiragino Sans",
              "Noto Sans CJK JP","MS Gothic","Arial Unicode MS","TkDefaultFont"]:
    FONT_JP   = (_cjk, 13)
    FONT_JPLG = (_cjk, 26, "bold")
    break

# js read the names bro, you cannot be that lazy

def normalize_kana(text):
    result = []
    for ch in text:
        code = ord(ch)
        if 0x30A1 <= code <= 0x30F6:  # katakana range -> shift to hiragana
            result.append(chr(code - 0x60))
        else:
            result.append(ch)
    return "".join(result)

def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")

_SRS_INTERVALS = [0, 1, 2, 4, 8, 16]

def srs_is_due(word):
    due = word.get("srs_due", "")
    if not due:
        return True
    try:
        return datetime.now() >= datetime.strptime(due, "%Y-%m-%d %H:%M")
    except Exception:
        return True

def srs_advance(word, correct):
    """Update srs_level / srs_due on a word dict in-place after an answer."""
    level = word.get("srs_level", 0)
    if correct:
        level = min(5, level + 1)
    else:
        level = max(0, level - 1)
    days  = _SRS_INTERVALS[level]
    due   = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M")
    word["srs_level"] = level
    word["srs_due"]   = due

def srs_label(level):
    return ["New", "Seen", "Learning", "Familiar", "Known", "Mastered"][level]

#JLPT stuff (thank you wkei)
JLPT_CACHE_PATH = DATA_DIR / "jlpt_cache.json"
# REST API by wkei — https://github.com/wkei/jlpt-vocab-api (MIT)
# level param: 5=N5, 4=N4, 3=N3, 2=N2, 1=N1
_JLPT_API_URL = "https://jlpt-vocab-api.vercel.app/api/words/all?level={}"
JLPT_LEVEL_NAMES = ["N5", "N4", "N3", "N2", "N1"]

def load_jlpt_cache():
    if JLPT_CACHE_PATH.exists():
        try:
            with open(JLPT_CACHE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_jlpt_cache(data):
    with open(JLPT_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

def fetch_jlpt_level(n, cache, on_done=None):
    def _run():
        try:
            url = _JLPT_API_URL.format(n)
            req = urllib.request.Request(url, headers={"User-Agent": "Wagacho/1.0"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            raw_words = payload if isinstance(payload, list) else payload.get("words", [])
            cleaned = []
            for e in raw_words:
                w = e.get("word","") or ""
                r = e.get("furigana","") or e.get("reading","") or ""
                m = e.get("meaning","") or ""
                if w or r:
                    cleaned.append({"word": w, "reading": r, "meaning": m})
            level_key = f"N{n}"
            cache[level_key] = cleaned
            save_jlpt_cache(cache)
            if on_done:
                on_done(level_key, len(cleaned), None)
        except Exception as exc:
            if on_done:
                on_done(f"N{n}", 0, str(exc))
    threading.Thread(target=_run, daemon=True).start()

def jlpt_lookup(word_entry, cache):
    w = normalize_kana((word_entry.get("word","") or "").lower())
    r = normalize_kana((word_entry.get("reading","") or "").lower())
    for lvl in JLPT_LEVEL_NAMES:
        for e in cache.get(lvl, []):
            ew = normalize_kana((e.get("word","") or "").lower())
            er = normalize_kana((e.get("reading","") or "").lower())
            if (w and w == ew) or (r and r and r == er):
                return lvl
    return ""

def get_exam_pool(user_words, jlpt_cache, level_key):
    uw = {normalize_kana((w.get("word","") or "").lower()) for w in user_words}
    ur = {normalize_kana((w.get("reading","") or "").lower()) for w in user_words}
    pool = []
    for e in jlpt_cache.get(level_key, []):
        ew = normalize_kana((e.get("word","") or "").lower())
        er = normalize_kana((e.get("reading","") or "").lower())
        if (ew and ew in uw) or (er and er in ur):
            pool.append(e)
    return pool

# static questions :D
GRAMMAR_QUESTIONS = {
"N5": [
  {"sentence":"いつ 東京へ 行く ＿＿＿＿、おしえてください。",
   "translation":"Please tell me _____ you are going to Tokyo.",
   "options":["に","を","と","か"],
   "answer":3,
   "explanation":"か is the indirect-question particle meaning 'if/when'. It turns the clause into an embedded question. に marks time/direction, を marks objects, と marks quotation."},
  {"sentence":"これ ＿＿＿＿ わたしの かばん です。",
   "translation":"This _____ my bag.",
   "options":["を","が","は","も"],
   "answer":2,
   "explanation":"は is the topic marker. It presents これ as the topic of the sentence. を marks direct objects, が marks grammatical subjects, も means 'also'."},
  {"sentence":"まいにち がっこう ＿＿＿＿ いきます。",
   "translation":"I go _____ school every day.",
   "options":["を","で","へ","が"],
   "answer":2,
   "explanation":"へ marks the destination/direction of movement. に also works for destinations, but へ emphasises direction. で marks location of action, を marks objects."},
  {"sentence":"ここ ＿＿＿＿ たばこを すわないでください。",
   "translation":"Please do not smoke _____ here.",
   "options":["に","で","へ","を"],
   "answer":1,
   "explanation":"で marks the location where an action takes place. に marks existence/destination rather than the location of an action."},
  {"sentence":"あの みせ ＿＿＿＿ パンが やすいです。",
   "translation":"The bread _____ that shop is cheap.",
   "options":["が","で","の","を"],
   "answer":2,
   "explanation":"の connects two nouns showing belonging or origin: 'that shop's bread'. が marks subjects, で marks location of action."},
  {"sentence":"にほんご ＿＿＿＿ はなせますか。",
   "translation":"Can you speak _____ Japanese?",
   "options":["が","を","で","に"],
   "answer":0,
   "explanation":"が marks the object of potential-form verbs like はなせる. を would mark the object of the plain form はなす. This is a key grammar distinction for ability expressions."},
  {"sentence":"えき ＿＿＿＿ でて、みぎに まがってください。",
   "translation":"Exit _____ the station and turn right.",
   "options":["を","で","から","に"],
   "answer":2,
   "explanation":"から marks the starting point ('from the station'). を with movement verbs marks the space passed through, not the point of departure."},
  {"sentence":"この えいがは とても おもしろい ＿＿＿＿。",
   "translation":"This movie is very interesting _____ .",
   "options":["ですか","でした","ですね","ではない"],
   "answer":2,
   "explanation":"ね seeks agreement from the listener ('isn't it?'). ですか forms a question, でした is past tense, ではない is negation."},
  {"sentence":"あした ＿＿＿＿ テストが あります。",
   "translation":"There is a test _____ tomorrow.",
   "options":["に","で","から","は"],
   "answer":0,
   "explanation":"に marks specific points in time with days, dates, and clock times. Relative time expressions like あした sometimes omit に, but it's the most natural choice here."},
  {"sentence":"バスで 一時間 ＿＿＿＿ かかります。",
   "translation":"It takes _____ one hour by bus.",
   "options":["が","を","は","ぐらい"],
   "answer":3,
   "explanation":"ぐらい/くらい expresses approximation: 'about / around one hour'. The other options are particles with different grammatical functions."},
  {"sentence":"この りんごを ぜんぶ ＿＿＿＿ ください。",
   "translation":"Please _____ all of these apples.",
   "options":["たべて","たべる","たべた","たべに"],
   "answer":0,
   "explanation":"〜てください is the polite request form. It requires the て-form of the verb. たべる is plain present, たべた is plain past, たべに marks purpose of movement."},
  {"sentence":"わたしは コーヒー ＿＿＿＿ こうちゃ ＿＿＿＿ すきです。",
   "translation":"I like both coffee _____ tea.",
   "options":["や / も","と / も","か / が","に / を"],
   "answer":1,
   "explanation":"と connects items in a complete list; も adds 'also/too'. Together they express 'I like A and I also like B'. や implies a non-exhaustive list."},
],
"N4": [
  {"sentence":"もっと はやく はしれば、まにあった ＿＿＿＿。",
   "translation":"If I had run faster, I would have made it _____ .",
   "options":["のに","から","けど","ので"],
   "answer":0,
   "explanation":"のに after a conditional expresses regret or frustration about a contrary-to-fact outcome. から and ので express cause/reason, けど expresses contrast."},
  {"sentence":"かれは びょうきな ＿＿＿＿、がっこうへ いきました。",
   "translation":"Even _____ being sick, he went to school.",
   "options":["から","ので","のに","ために"],
   "answer":2,
   "explanation":"のに (concession) means 'even though / despite'. から and ので express reason/cause. ために expresses purpose or cause of something that already happened."},
  {"sentence":"あめが ふって ＿＿＿＿ でかけました。",
   "translation":"We went out _____ even though it was raining.",
   "options":["いても","いるから","いるので","いるけど"],
   "answer":0,
   "explanation":"〜ていても is the concessive conditional: 'even if/even though (it is happening)'. It combines て+いる+も for this meaning."},
  {"sentence":"かいぎは 三時に はじまる ＿＿＿＿ です。",
   "translation":"The meeting _____ start at 3 o'clock.",
   "options":["はず","こと","もの","ため"],
   "answer":0,
   "explanation":"はずです expresses reasonable expectation based on known facts: 'it should / it is expected to'. ことです gives advice, ものです expresses generalisation."},
  {"sentence":"くすりを のまない ＿＿＿＿、なおりませんよ。",
   "translation":"If you don't take your medicine, you won't get better.",
   "options":["なら","と","ては","から"],
   "answer":2,
   "explanation":"〜ては with a negative result means 'if you do X (bad thing), bad outcome follows'. It marks an undesirable conditional. なら is a topic-based conditional, と is a natural/inevitable conditional."},
  {"sentence":"あの レストランは たかい ＿＿＿＿、おいしい です。",
   "translation":"That restaurant is expensive, _____ the food is good.",
   "options":["けど","ので","から","ために"],
   "answer":0,
   "explanation":"けど (=けれど) connects contrasting clauses: 'it's expensive, but it's good'. ので and から give a reason, ために expresses purpose."},
  {"sentence":"かのじょに あう ＿＿＿＿ えきへ いきました。",
   "translation":"I went to the station _____ meet her.",
   "options":["ために","から","ので","けど"],
   "answer":0,
   "explanation":"〜ために with a dictionary-form verb expresses purpose: 'in order to do X'. から and ので state reasons for something that already happened, not future purpose."},
  {"sentence":"この しごとは かのじょ ＿＿＿＿ できません。",
   "translation":"This job _____ she cannot do.",
   "options":["には","では","にも","でも"],
   "answer":0,
   "explanation":"には strengthens the topic with the nuance 'specifically for her'. では would refer to a location/situation context rather than a person."},
  {"sentence":"＿＿＿＿ ほど、むずかしい しけんは ありません。",
   "translation":"There is no exam _____ difficult as this one.",
   "options":["これ","こんな","こう","この"],
   "answer":0,
   "explanation":"これほど = 'to this degree / as much as this'. こんな directly modifies a noun, こう is an adverb of manner. これほど is the set phrase for degree comparisons."},
  {"sentence":"このまま にほんご ＿＿＿＿ べんきょうすれば、うまく なりますよ。",
   "translation":"If you keep studying Japanese _____ like this, you will improve.",
   "options":["だけ","ばかり","しか","も"],
   "answer":1,
   "explanation":"ばかり = 'nothing but / only (repeatedly)'. It implies excessive or habitual focus. だけ also means 'only' but lacks the habitual nuance. しか requires negation."},
],
"N3": [
  {"sentence":"さいきん ねむれない ＿＿＿＿、びょういんへ いったほうがいいですよ。",
   "translation":"Since you haven't been able to sleep lately _____ , you should see a doctor.",
   "options":["ようで","らしくて","みたいで","なら"],
   "answer":3,
   "explanation":"なら (conditional) picks up information the speaker was just told and gives advice: 'If that's the case, then…'. ようで, らしくて, and みたいで all express appearance/hearsay, not advice conditions."},
  {"sentence":"もう すこし ねだんが やすければ ＿＿＿＿。",
   "translation":"If only the price were a little cheaper _____ .",
   "options":["かもしれない","かったのに","のに","はずだ"],
   "answer":2,
   "explanation":"〜ければ〜のに expresses a counterfactual wish: 'if it were X (but it's not), that would be good'. のに alone at sentence-end expresses regret."},
  {"sentence":"こんなに べんきょうした ＿＿＿＿、しっぱいするわけがない。",
   "translation":"Having studied this much _____ , there is no way I will fail.",
   "options":["からには","ものの","ところが","くせに"],
   "answer":0,
   "explanation":"からには = 'now that / since (I have committed to this action)'. It implies a logical consequence or obligation. ものの concedes a point, ところが introduces a surprising contrast."},
  {"sentence":"彼女は いつも にこにこして ＿＿＿＿、実は なやみが あるらしい。",
   "translation":"Even though she is always smiling _____ , she apparently has worries.",
   "options":["いるのに","いるから","いるので","いるし"],
   "answer":0,
   "explanation":"〜ているのに expresses surprise or contrast: 'despite always smiling'. から and ので would make smiling the cause of her worries, which is the opposite meaning."},
  {"sentence":"かれは いくら おこっても ＿＿＿＿ かわらない。",
   "translation":"No matter how much he gets angry _____ , nothing changes.",
   "options":["なにも","なんか","どうも","どうせ"],
   "answer":0,
   "explanation":"いくら〜ても、なにも〜ない = 'no matter how much…, nothing changes'. どうせ means 'anyway/regardless (with resignation)' and changes the meaning significantly."},
  {"sentence":"しりょうを みた ＿＿＿＿、ほうこくしてください。",
   "translation":"After reviewing the materials _____ , please submit your report.",
   "options":["うえで","まえに","ために","ものの"],
   "answer":0,
   "explanation":"〜たうえで = 'after doing X, then do Y'. It states that Y must come after X is completed. まえに means 'before', ために means 'in order to'."},
  {"sentence":"この くすりは いちにち ＿＿＿＿ 三回 のんでください。",
   "translation":"Please take this medicine 3 times _____ day.",
   "options":["あたり","ごとに","につき","だけ"],
   "answer":2,
   "explanation":"につき = 'per (unit)'. 一日につき三回 = '3 times per day'. It is the most precise and formal choice here. ごとに = 'every/each', あたり also means 'per' but is slightly less formal."},
  {"sentence":"かれは ゆっくり はなした ＿＿＿＿、よく わからなかった。",
   "translation":"Even though he spoke slowly _____ , I still didn't understand well.",
   "options":["ものの","ものに","ものか","ものを"],
   "answer":0,
   "explanation":"〜たものの = 'although / even though (he did X)'. It introduces a result that contradicts expectations. ものか expresses strong negation, ものを expresses regret."},
  {"sentence":"あの 店は ＿＿＿＿ ながら、なかなか おいしい。",
   "translation":"Although that shop is _____ , it is actually quite good.",
   "options":["やすい","やすく","やすさ","やすかっ"],
   "answer":1,
   "explanation":"〜ながら (concession) attaches to the adverbial form (く-form) of い-adjectives: やすく＋ながら = 'although cheap'. やすい is the plain form, やすさ is a noun."},
  {"sentence":"試験に 合格する ＿＿＿＿、毎日 練習しています。",
   "translation":"_____ pass the exam, I practice every day.",
   "options":["ために","ように","ことに","からに"],
   "answer":0,
   "explanation":"〜ために with a volitional verb expresses purpose: 'in order to pass'. 〜ように is used when the goal is not directly controllable by the speaker."},
],
"N2": [
  {"sentence":"プロジェクトの せいこうは チームワーク ＿＿＿＿ かかっている。",
   "translation":"The success of the project _____ depends on teamwork.",
   "options":["にかけて","にかかって","によって","にとって"],
   "answer":1,
   "explanation":"〜にかかっている = 'depends on X'. によって = 'depending on / by means of'. にとって = 'for (someone's perspective)'. にかけて means 'from X to Y' or 'in terms of'."},
  {"sentence":"その けっか ＿＿＿＿、あらためて かいぎを ひらくことに なった。",
   "translation":"_____ that result, it was decided to hold another meeting.",
   "options":["をふまえて","をもとに","にもとづいて","をうけて"],
   "answer":3,
   "explanation":"〜をうけて = 'in response to / following on from'. をふまえて = 'taking into account'. をもとに = 'based on'. にもとづいて = 'based on (rules or evidence)'."},
  {"sentence":"かれの はつげんは じじつ ＿＿＿＿ している。",
   "translation":"His statement _____ contradicts the facts.",
   "options":["に反","を反","と反","で反"],
   "answer":0,
   "explanation":"〜に反する is a set expression meaning 'to go against / contradict'. The correct particle is に. 事実に反する is the standard collocation."},
  {"sentence":"しめきりが ちかい ＿＿＿＿、まだ ぜんぜん できていない。",
   "translation":"Even though the deadline is close _____ , I have not done anything yet.",
   "options":["というのに","というのは","というより","というか"],
   "answer":0,
   "explanation":"〜というのに = 'even though / despite the fact that'. It expresses indignation or surprise at a stark contrast. というのは introduces a definition/explanation."},
  {"sentence":"けいかくを かえる ＿＿＿＿ じかんが なかった。",
   "translation":"There was no time _____ change the plan.",
   "options":["にあたって","にさいして","いじょう","いとまも"],
   "answer":3,
   "explanation":"〜いとまもない = 'not even the time/leisure to do X'. It expresses extreme time pressure. にあたって/にさいして = 'on the occasion of', which has a completely different meaning."},
  {"sentence":"かれが そんな ことを いう ＿＿＿＿ ない。",
   "translation":"There is no way _____ he would say something like that.",
   "options":["はずが","わけが","ことが","ものが"],
   "answer":0,
   "explanation":"〜はずがない = 'there is no way / it cannot be'. It negates a logical expectation. わけがない also means 'no reason to', but はずがない specifically denies what was expected."},
  {"sentence":"彼女は ピアノが うまい ＿＿＿＿、えいごも ぺらぺらだ。",
   "translation":"On top of being good at piano _____ , she also speaks English fluently.",
   "options":["うえに","ほかに","だけで","くせに"],
   "answer":0,
   "explanation":"〜うえに = 'in addition to / on top of that'. It stacks qualities in the same direction. ほかに = 'besides that (separate item)'. くせに has a critical/accusatory nuance."},
  {"sentence":"その はなしは ほんとうか どうか ＿＿＿＿。",
   "translation":"Whether that story is true or not _____ .",
   "options":["わかりかねます","わかりにくい","わかりようがない","わかりづらい"],
   "answer":0,
   "explanation":"〜かねます is a formal, polite expression of inability: 'I am unable to say / I cannot determine'. わかりにくい means 'hard to understand', わかりようがない means 'no way of knowing'."},
  {"sentence":"どんなに つかれていても、しごとを ＿＿＿＿ わけには いかない。",
   "translation":"No matter how tired I am, I cannot _____ just quit the job.",
   "options":["やめる","やめた","やめて","やめよう"],
   "answer":0,
   "explanation":"〜わけにはいかない uses the dictionary form of the verb: やめる＋わけにはいかない = 'I cannot simply quit'. It expresses that social/moral pressure makes an action impossible."},
  {"sentence":"この けんきゅうは ＿＿＿＿ に たる せいかだ。",
   "translation":"This research is a result worthy _____ of recognition.",
   "options":["みとめる","みとめられる","みとめ","みとめよう"],
   "answer":2,
   "explanation":"〜に足る (にたる) = 'worthy of / sufficient for'. It attaches to the conjunctive (連用形/stem) form of the verb: みとめ＋に足る. Using the stem みとめ is the grammatically correct connection."},
],
}
GRAMMAR_TEMPLATES = {
"N5": [
  {"template":"{W} ＿＿＿＿ いきます。",
   "translation":"I go to {M}.",
   "options":["に","を","で","が"],"answer":0,
   "explanation":"に marks the destination of movement verbs like いく、くる、かえる."},
  {"template":"まいにち {W} ＿＿＿＿ べんきょうします。",
   "translation":"I study {M} every day.",
   "options":["で","に","を","が"],"answer":2,
   "explanation":"を marks the direct object of action verbs like べんきょうする、たべる、のむ."},
  {"template":"{W} ＿＿＿＿ たべたいです。",
   "translation":"I want to eat {M}.",
   "options":["は","が","を","に"],"answer":2,
   "explanation":"〜たい (want to) takes を for its object, just like the plain form of the verb."},
  {"template":"あの {W} ＿＿＿＿ きれいです ね。",
   "translation":"That {M} is beautiful, isn't it.",
   "options":["が","は","を","で"],"answer":1,
   "explanation":"は is the topic marker. It presents the noun as what the sentence is about."},
  {"template":"{W} ＿＿＿＿ ありません。",
   "translation":"There is no {M}.",
   "options":["は","が","を","に"],"answer":1,
   "explanation":"が marks the subject of existence verbs ある and いる. ありません is the negative."},
  {"template":"これは {W} ＿＿＿＿ ほんです。",
   "translation":"This is a book about {M}.",
   "options":["の","を","に","が"],"answer":0,
   "explanation":"の connects two nouns showing relationship: '{W}の本' = 'book of/about {W}'."},
  {"template":"{W} ＿＿＿＿ すきですか？",
   "translation":"Do you like {M}?",
   "options":["が","を","に","は"],"answer":0,
   "explanation":"すき (like) and きらい (dislike) take が for their object."},
  {"template":"{W} を ＿＿＿＿ ください。",
   "translation":"Please show me {M}.",
   "options":["みせて","みせる","みせた","みせに"],"answer":0,
   "explanation":"〜てください is the polite request form. It requires the て-form of the verb."},
  {"template":"きのう {W} ＿＿＿＿ かいました。",
   "translation":"Yesterday I bought {M}.",
   "options":["を","が","は","で"],"answer":0,
   "explanation":"を marks the direct object. かう (to buy) takes を."},
  {"template":"{W} は ＿＿＿＿ です。",
   "translation":"{M} is expensive.",
   "options":["たかい","たかく","たかさ","たかかった"],"answer":0,
   "explanation":"Adjective + です is the polite predicate form. い-adjectives keep their い before です."},
],
"N4": [
  {"template":"{W} に なれる ＿＿＿＿、もっと べんきょうします。",
   "translation":"In order to become good at {M}, I will study more.",
   "options":["ために","ように","ことに","からに"],"answer":1,
   "explanation":"〜ように with a potential verb expresses a goal that isn't directly controllable. 〜ために is used when the subject is the same and the goal is volitional."},
  {"template":"{W} が できる ＿＿＿＿ なりました。",
   "translation":"I have become able to do {M}.",
   "options":["ように","ために","ことに","ながら"],"answer":0,
   "explanation":"〜ようになる expresses a change of state: 'came to be able to'. It is used with potential forms to show a new ability."},
  {"template":"{W} を している ＿＿＿＿ に、友達が 来た。",
   "translation":"While I was doing {M}, a friend came.",
   "options":["あいだ","まえ","あと","とき"],"answer":3,
   "explanation":"〜ているときに = 'while doing / at the time of doing'. あいだ implies a continuous background action, ときに can be either a point in time or a period."},
  {"template":"{W} を 見た ＿＿＿＿ が あります。",
   "translation":"I have had the experience of seeing {M}.",
   "options":["こと","もの","はず","わけ"],"answer":0,
   "explanation":"〜たことがある expresses past experience: 'have done / have seen X before'. こと nominalises the verb phrase."},
  {"template":"{W} は ＿＿＿＿ そうです。",
   "translation":"{M} looks delicious.",
   "options":["おいしい","おいしく","おいしさ","おいし"],"answer":3,
   "explanation":"〜そうだ (appearance) attaches to the い-adjective stem (remove い): おいし＋そう. This is different from the い-form used before です."},
  {"template":"友達に {W} を ＿＿＿＿ もらいました。",
   "translation":"I had my friend do {M} for me.",
   "options":["して","した","する","しよう"],"answer":0,
   "explanation":"〜てもらう = 'receive the favour of someone doing X'. It requires the て-form before もらう."},
  {"template":"{W} を ＿＿＿＿ ほうが いいです。",
   "translation":"You should {M}.",
   "options":["した","する","して","しよう"],"answer":0,
   "explanation":"〜たほうがいい gives advice. It uses the past (た) form of the verb, not the dictionary form."},
  {"template":"{W} が ＿＿＿＿ なら、ここに おいてください。",
   "translation":"If you don't need {M}, please leave it here.",
   "options":["いらない","いらなく","いらなかった","いらなくて"],"answer":0,
   "explanation":"〜なら is a conditional that picks up on a stated or assumed situation. It takes the plain form of the predicate before it."},
],
"N3": [
  {"template":"{W} を 終えた ＿＿＿＿、連絡してください。",
   "translation":"After you have finished {M}, please get in touch.",
   "options":["うえで","まえに","あとで","ために"],"answer":0,
   "explanation":"〜たうえで = 'after completing X, then do Y'. It emphasises that the second action must follow completion of the first."},
  {"template":"この {W} は ＿＿＿＿ にくい。",
   "translation":"This {M} is hard to use.",
   "options":["つかい","つかう","つかって","つかわれ"],"answer":0,
   "explanation":"〜にくい attaches to the conjunctive/stem form of a verb (連用形): つかい＋にくい = 'hard to use'. Similarly, やすい attaches the same way."},
  {"template":"{W} に ＿＿＿＿ かかわらず、参加してください。",
   "translation":"Regardless of {M}, please participate.",
   "options":["かかわらず","もかかわらず","かかわって","かかわる"],"answer":1,
   "explanation":"〜にもかかわらず = 'despite / regardless of'. The も is part of the set expression. Without も, the grammar is slightly different."},
  {"template":"{W} は ＿＿＿＿ つつある。",
   "translation":"{M} is gradually changing.",
   "options":["かわり","かわる","かわって","かわった"],"answer":0,
   "explanation":"〜つつある = 'is in the process of / is gradually doing'. It attaches to the stem (連用形) of the verb: かわり＋つつある."},
  {"template":"{W} に ＿＿＿＿ あたって、準備しましょう。",
   "translation":"In preparation for {M}, let's get ready.",
   "options":["あたって","むけて","かけて","よって"],"answer":1,
   "explanation":"〜にむけて = 'towards / in preparation for (a goal or event)'. にあたって = 'on the occasion of (doing something)'."},
  {"template":"{W} を した ＿＿＿＿ で、疲れました。",
   "translation":"I got tired _____ of doing {M}.",
   "options":["せい","おかげ","ため","わけ"],"answer":0,
   "explanation":"〜せいで = 'because of (negative cause)'. It assigns blame. おかげで is positive ('thanks to'), ため is neutral purpose or reason."},
],
"N2": [
  {"template":"{W} を ＿＿＿＿ にたる 実力がある。",
   "translation":"I have the ability worthy of {M}.",
   "options":["こなし","こなす","こなせ","こなして"],"answer":0,
   "explanation":"〜に足る (にたる) attaches to the stem (連用形) of the verb: こなし＋に足る. This formal expression means 'sufficient to / worthy of'."},
  {"template":"{W} に ＿＿＿＿、準備を 進めた。",
   "translation":"In anticipation of {M}, we moved forward with preparations.",
   "options":["そなえて","むけて","あたって","かかわって"],"answer":0,
   "explanation":"〜にそなえて = 'in preparation for / in anticipation of'. むけて focuses on direction/goal, あたって is used for formal events/actions."},
  {"template":"{W} を ＿＿＿＿ かねない。",
   "translation":"This could potentially cause {M}.",
   "options":["まねき","まねく","まねいて","まねかれ"],"answer":0,
   "explanation":"〜かねない = 'could easily result in (an undesirable outcome)'. It attaches to the stem (連用形) of the verb: まねき＋かねない."},
  {"template":"その {W} は ＿＿＿＿ にすぎない。",
   "translation":"That {M} is nothing more than a temporary measure.",
   "options":["一時的","一時的な","一時的に","一時的で"],"answer":2,
   "explanation":"〜にすぎない = 'nothing more than / merely'. When used with a noun or adjectival noun, the に-form (adverbial) is required: 一時的に＋すぎない."},
  {"template":"{W} の 問題は ＿＿＿＿ をえない。",
   "translation":"The problem of {M} is unavoidable.",
   "options":["みとめ","みとめる","みとめて","みとめた"],"answer":0,
   "explanation":"〜をえない = 'cannot but / cannot help but (do)'. It is a formal, literary pattern that attaches to the stem (連用形)."},
],
}

import copy as _copy

def get_grammar_questions(level_key):
    return _copy.deepcopy(GRAMMAR_QUESTIONS.get(level_key, []))

def build_template_questions(level_key, user_words, max_q=20):
    templates = GRAMMAR_TEMPLATES.get(level_key, [])
    if not templates or not user_words:
        return []

    usable = [w for w in user_words if w.get("word","").strip()]
    if not usable:
        return []

    result = []
    random.shuffle(templates)
    attempts = 0
    while len(result) < max_q and attempts < max_q * 4:
        attempts += 1
        tmpl = random.choice(templates)
        word = random.choice(usable)
        w_str = word.get("word","") or ""
        r_str = word.get("reading","") or w_str
        m_str = word.get("comment","") or word.get("romaji","") or r_str

        sentence    = tmpl["template"].replace("{W}", w_str).replace("{R}", r_str).replace("{M}", m_str)
        translation = tmpl["translation"].replace("{W}", w_str).replace("{R}", r_str).replace("{M}", m_str)

        result.append({
            "sentence":    sentence,
            "translation": translation,
            "options":     list(tmpl["options"]),
            "answer":      tmpl["answer"],
            "explanation": tmpl.get("explanation",""),
            "_from_template": True,
        })

    return result



def dict_path(name):
    return DATA_DIR / f"{name}.json"

def list_dictionaries():
    return sorted(p.stem for p in DATA_DIR.glob("*.json") if p.stem != "jlpt_cache")

def load_dict(name):
    p = dict_path(name)
    if p.exists():
        with open(p, "r", encoding="utf-8") as f:
            d = json.load(f)
            if "name" not in d:       d["name"] = name
            if "created" not in d:    d["created"] = _now()
            if "categories" not in d: d["categories"] = ["Uncategorized"]
            if "words" not in d:      d["words"] = []
            return d
    return {"name": name, "created": _now(), "categories": ["Uncategorized"], "words": []}

def save_dict(data):
    with open(dict_path(data["name"]), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def delete_dict_file(name):
    p = dict_path(name)
    if p.exists():
        p.unlink()

def new_word(word="", reading="", romaji="", category="", comment="", favorite=False):
    return {
        "id":       str(uuid.uuid4()),
        "word":     word.strip(),
        "reading":  reading.strip(),
        "romaji":   romaji.strip(),
        "category": category.strip() or "Uncategorized",
        "comment":  comment.strip(),
        "favorite": favorite,
        "created":  _now(),
    }

# widget nd stuff
class FlatButton(tk.Label):
    def __init__(self, parent, text, command=None,
                 bg=None, fg=None, hover_bg=None,
                 font=None, padx=14, pady=7, **kw):
        self.bg_color = bg or C["red"]
        self.fg_color = fg or C["white"]
        self.hover_bg_color = hover_bg or C["red2"]
        self._cmd = command
        super().__init__(parent, text=text, bg=self.bg_color, fg=self.fg_color,
                         font=font or FONT_UIB,
                         padx=padx, pady=pady, cursor="hand2", **kw)
        self.bind("<Enter>", lambda e: self.config(bg=self.hover_bg_color))
        self.bind("<Leave>", lambda e: self.config(bg=self.bg_color))
        self.bind("<Button-1>", lambda e: self._cmd() if self._cmd else None)
        self.bind("<ButtonRelease-1>", lambda e: self.config(bg=self.hover_bg_color))

    def set_colors(self, bg, fg, hover_bg):
        self.bg_color = bg
        self.fg_color = fg
        self.hover_bg_color = hover_bg
        self.config(bg=self.bg_color, fg=self.fg_color)

def lbl(parent, text="", font=None, fg=None, bg=None, **kw):
    return tk.Label(parent, text=text,
                    font=font or FONT_UI,
                    fg=fg or C["ink"], bg=bg or C["bg"], **kw)

def sep(parent, bg=None):
    return tk.Frame(parent, bg=bg or C["bg3"], height=1)

def _safe_grab(win):
    try:
        win.grab_set()
    except Exception:
        win.after(100, lambda: _safe_grab(win))

# word dialog
class WordDialog(tk.Toplevel):
    def __init__(self, parent, categories, word_data=None):
        super().__init__(parent)
        self.parent = parent
        self.result     = None
        self.categories = list(categories) or ["Uncategorized"]
        editing = word_data is not None

        self.title("Edit Entry" if editing else "New Entry")
        self.resizable(False, False)
        self.after(50, lambda: _safe_grab(self))
        
        self.build_ui(editing, word_data)
        self.update_theme()
        
        self._center(parent)
        self.e_word.focus()

    def build_ui(self, editing, word_data):
        self.hdr = tk.Frame(self, pady=14)
        self.hdr.pack(fill="x")
        self.hdr_lbl = lbl(self.hdr, ("✎  Edit Entry" if editing else "＋  New Entry"),
            font=FONT_H2, fg=C["white"])
        self.hdr_lbl.pack(padx=20, anchor="w")

        self.body = tk.Frame(self, padx=24, pady=12)
        self.body.pack(fill="both", expand=True)

        def field_row(label_text, row_i, f=None):
            l = lbl(self.body, label_text, font=FONT_UIS, fg=C["ink2"])
            l.grid(row=row_i*2, column=0, columnspan=2, sticky="w", pady=(8,1))
            e = tk.Entry(self.body, font=f or FONT_UI, width=36, relief="flat", bd=0, highlightthickness=1)
            e.grid(row=row_i*2+1, column=0, columnspan=2, sticky="ew", ipady=5)
            return e, l

        self.e_word, self.l_word = field_row("Word  （書き方）",  0, FONT_JP)
        self.e_reading, self.l_reading = field_row("Reading  （読み方）",1, FONT_JP)
        self.e_romaji, self.l_romaji = field_row("Romaji", 2)

        self.l_cat = lbl(self.body, "Category", font=FONT_UIS, fg=C["ink2"])
        self.l_cat.grid(row=6, column=0, sticky="w", pady=(8,1))
        self.cat_row = tk.Frame(self.body)
        self.cat_row.grid(row=7, column=0, columnspan=2, sticky="ew")
        self.cat_var = tk.StringVar(value=self.categories[0])
        self.cat_cb = ttk.Combobox(self.cat_row, textvariable=self.cat_var,
                                   values=self.categories, width=22,
                                   font=FONT_UI, state="normal")
        self._style_ttk()
        self.cat_cb.pack(side="left")
        self.new_cat_btn = FlatButton(self.cat_row, "+ New Category", command=self._new_cat,
                   font=FONT_UIS, padx=10, pady=5)
        self.new_cat_btn.pack(side="left", padx=(8,0))

        self.l_comment = lbl(self.body, "Comment / Notes", font=FONT_UIS, fg=C["ink2"])
        self.l_comment.grid(row=8, column=0, sticky="w", pady=(8,1))
        self.t_comment = tk.Text(self.body, font=FONT_UI, width=36, height=4, wrap="word",
                                  relief="flat", bd=0, highlightthickness=1)
        self.t_comment.grid(row=9, column=0, columnspan=2, sticky="ew")

        self.fav_var = tk.BooleanVar()
        self.fav_cb = tk.Checkbutton(self.body, text="  ⭐  Mark as Favourite",
                       variable=self.fav_var, font=FONT_UIS)
        self.fav_cb.grid(row=10, column=0, sticky="w", pady=(8,0))

        self.body.columnconfigure(0, weight=1)

        self.btn_row = tk.Frame(self, padx=20, pady=10)
        self.btn_row.pack(fill="x")
        self.save_btn = FlatButton(self.btn_row, "Save", command=self._save)
        self.save_btn.pack(side="right")
        self.cancel_btn = FlatButton(self.btn_row, "Cancel", command=self.destroy,
                   font=FONT_UI, padx=12, pady=7)
        self.cancel_btn.pack(side="right", padx=(0,8))

        if editing:
            self.e_word.insert(0, word_data.get("word",""))
            self.e_reading.insert(0, word_data.get("reading",""))
            self.e_romaji.insert(0, word_data.get("romaji",""))
            cat = word_data.get("category","")
            if cat not in self.categories:
                self.categories.append(cat)
                self.cat_cb["values"] = self.categories
            self.cat_var.set(cat)
            self.t_comment.insert("1.0", word_data.get("comment",""))
            self.fav_var.set(word_data.get("favorite", False))

    def update_theme(self):
        self.configure(bg=C["bg"])
        self.hdr.config(bg=C["sidebar"])
        self.hdr_lbl.config(bg=C["sidebar"], fg=C["white"])
        self.body.config(bg=C["bg"])

        for w, l in [(self.e_word, self.l_word), (self.e_reading, self.l_reading), (self.e_romaji, self.l_romaji)]:
            w.config(bg=C["entry_bg"], fg=C["entry_fg"], insertbackground=C["entry_fg"],
                     highlightbackground=C["bg3"], highlightcolor=C["red"])
            l.config(bg=C["bg"], fg=C["ink2"])

        self.l_cat.config(bg=C["bg"], fg=C["ink2"])
        self.cat_row.config(bg=C["bg"])
        self._style_ttk()
        self.new_cat_btn.set_colors(bg=C["bg2"], fg=C["ink2"], hover_bg=C["bg3"])

        self.l_comment.config(bg=C["bg"], fg=C["ink2"])
        self.t_comment.config(bg=C["entry_bg"], fg=C["entry_fg"], insertbackground=C["entry_fg"],
                              highlightbackground=C["bg3"], highlightcolor=C["red"])

        self.fav_cb.config(bg=C["bg"], fg=C["ink2"], selectcolor=C["bg2"], activebackground=C["bg"])
        
        self.btn_row.config(bg=C["bg2"])
        self.save_btn.set_colors(bg=C["red"], fg=C["white"], hover_bg=C["red2"])
        self.cancel_btn.set_colors(bg=C["bg3"], fg=C["ink2"], hover_bg=C["bg2"])
        
    def _style_ttk(self):
        s = ttk.Style(self)
        try: s.theme_use("clam")
        except Exception: pass
        s.configure("TCombobox",
                     fieldbackground=C["entry_bg"], background=C["entry_bg"],
                     foreground=C["entry_fg"], selectbackground=C["sel"],
                     bordercolor=C["bg3"], arrowcolor=C["ink2"])
        self.cat_cb.config(style="TCombobox")

    def _new_cat(self):
        name = simpledialog.askstring("New Category", "Category name:", parent=self)
        if name and name.strip():
            name = name.strip()
            if name not in self.categories:
                self.categories.append(name)
                self.cat_cb["values"] = self.categories
            self.cat_var.set(name)

    def _save(self):
        w = self.e_word.get().strip()
        if not w:
            messagebox.showwarning("Required", "Word field cannot be empty.", parent=self)
            return
        self.result = new_word(
            word=w,
            reading=self.e_reading.get(),
            romaji=self.e_romaji.get(),
            category=self.cat_var.get(),
            comment=self.t_comment.get("1.0", "end-1c"),
            favorite=self.fav_var.get(),
        )
        self.destroy()

    def _center(self, parent):
        self.update_idletasks()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        px, py = parent.winfo_x(), parent.winfo_y()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        self.geometry(f"{w}x{h}+{px+pw//2-w//2}+{py+ph//2-h//2}")


class QuizWindow(tk.Toplevel):
    MODES = {
        "Word → Reading":         ("word",    "reading"),
        "Reading → Word":         ("reading", "word"),
        "Word → Romaji":          ("word",    "romaji"),
        "Romaji → Word":          ("romaji",  "word"),
        "Word → Meaning/Comment": ("word",    "comment"),
    }
    TIMER_OPTS = [0, 5, 10, 15, 20]   # 0 = off

    def __init__(self, parent, words, categories=None):
        super().__init__(parent)
        self.title("練習 — Quiz")
        self.geometry("560x620")
        self.minsize(480, 520)
        self.resizable(True, True)
        self.after(50, lambda: _safe_grab(self))

        self.parent_app    = parent
        self.all_words     = [w for w in words if w.get("word")]
        self.categories    = ["All Categories"] + sorted(categories or [])
        self.words         = self.all_words.copy()
        self.deck          = []
        self.idx           = 0
        self.correct       = 0
        self.wrong         = 0
        self._timer_job    = None
        self._time_left    = 0
        self._phase        = "setup"   # setup | quiz | results

        self._build_skeleton()
        self.update_theme()
        self._show_setup()

    def _build_skeleton(self):
        self.hdr = tk.Frame(self)
        self.hdr.pack(fill="x")
        self.hdr_lbl = lbl(self.hdr, "練習  Quiz", font=FONT_H2, fg=C["white"])
        self.hdr_lbl.pack(side="left", padx=16, pady=12)
        self.score_lbl = lbl(self.hdr, "", font=FONT_UIS, fg=C["ink3"])
        self.score_lbl.pack(side="right", padx=16)

        self.sep0 = sep(self)
        self.sep0.pack(fill="x")

        self.content = tk.Frame(self)
        self.content.pack(fill="both", expand=True)

    def _clear_content(self):
        for w in self.content.winfo_children():
            w.destroy()

    def _show_setup(self):
        self._cancel_timer()
        self._phase = "setup"
        self._clear_content()
        self.score_lbl.config(text="")

        pad = tk.Frame(self.content)
        pad.pack(fill="both", expand=True, padx=28, pady=16)
        pad.config(bg=C["bg"])

        def section(title):
            lbl(pad, title, font=FONT_UIB, fg=C["ink2"], bg=C["bg"]).pack(anchor="w", pady=(14,4))
            sep(pad).pack(fill="x", pady=(0,8))

        section("Quiz Mode")
        self._mode_var = tk.StringVar(value=list(self.MODES)[0])
        mode_row = tk.Frame(pad, bg=C["bg"])
        mode_row.pack(fill="x")
        self._mode_btns = {}
        for m in self.MODES:
            short = m.replace(" (kana)", "")
            b = FlatButton(mode_row, short, font=FONT_UIS, padx=8, pady=4,
                           command=lambda mv=m: self._sel_mode(mv))
            b.pack(side="left", padx=(0,5))
            self._mode_btns[m] = b
        self._sel_mode(list(self.MODES)[0])

        section("Answer Format")
        self._fmt_var = tk.StringVar(value="type")
        fmt_row = tk.Frame(pad, bg=C["bg"])
        fmt_row.pack(fill="x")
        self._fmt_btns = {}
        for key, label in [("type","✏  Type-in"), ("mc","☑  Multiple Choice")]:
            b = FlatButton(fmt_row, label, font=FONT_UIS, padx=12, pady=5,
                           command=lambda k=key: self._sel_fmt(k))
            b.pack(side="left", padx=(0,8))
            self._fmt_btns[key] = b
        self._sel_fmt("type")

        section("Timer per Card")
        self._timer_var = tk.IntVar(value=0)
        tmr_row = tk.Frame(pad, bg=C["bg"])
        tmr_row.pack(fill="x")
        self._tmr_btns = {}
        for t in self.TIMER_OPTS:
            lbl_text = "Off" if t == 0 else f"{t}s"
            b = FlatButton(tmr_row, lbl_text, font=FONT_UIS, padx=10, pady=5,
                           command=lambda tv=t: self._sel_timer(tv))
            b.pack(side="left", padx=(0,5))
            self._tmr_btns[t] = b
        self._sel_timer(0)

        section("Deck")
        deck_row = tk.Frame(pad, bg=C["bg"])
        deck_row.pack(fill="x")
        self._srs_var = tk.BooleanVar(value=False)

        due_count = sum(1 for w in self.all_words if srs_is_due(w))
        srs_text   = f"SRS Due Only  ({due_count} due)"
        self._deck_btns = {}
        for key, label in [("all","All Words"), ("srs", srs_text)]:
            b = FlatButton(deck_row, label, font=FONT_UIS, padx=10, pady=5,
                           command=lambda k=key: self._sel_deck(k))
            b.pack(side="left", padx=(0,8))
            self._deck_btns[key] = b
        self._sel_deck("all")

        lbl(pad, "Category", font=FONT_UIB, fg=C["ink2"], bg=C["bg"]).pack(anchor="w", pady=(14,4))
        sep(pad).pack(fill="x", pady=(0,8))
        self._setup_cat_var = tk.StringVar(value="All Categories")
        cat_row = tk.Frame(pad, bg=C["bg"])
        cat_row.pack(fill="x")
        cat_menu = ttk.OptionMenu(cat_row, self._setup_cat_var,
                                  "All Categories", *self.categories)
        cat_menu.pack(side="left")
        self._setup_cat_menu = cat_menu

        btn_row = tk.Frame(pad, bg=C["bg"])
        btn_row.pack(fill="x", pady=(20, 0))
        start_btn = FlatButton(btn_row, "Start Quiz  →", command=self._start_quiz, pady=8, padx=18)
        start_btn.set_colors(C["red"], C["white"], C["red2"])
        start_btn.pack(side="right")

        if not self.all_words:
            lbl(pad, "⚠  No words to quiz. Add some first!", fg=C["red2"], bg=C["bg"],
                font=FONT_UIS).pack(anchor="w", pady=8)
            start_btn.config(state="disabled")

        self.update_theme()

    def _sel_mode(self, mode):
        self._mode_var.set(mode)
        for m, b in self._mode_btns.items():
            b.set_colors(C["red"] if m == mode else C["bg3"],
                         C["white"] if m == mode else C["ink2"],
                         C["red2"] if m == mode else C["bg2"])

    def _sel_fmt(self, key):
        self._fmt_var.set(key)
        for k, b in self._fmt_btns.items():
            b.set_colors(C["blue"] if k == key else C["bg3"],
                         C["white"] if k == key else C["ink2"],
                         C["blue2"] if k == key else C["bg2"])

    def _sel_timer(self, t):
        self._timer_var.set(t)
        for tv, b in self._tmr_btns.items():
            b.set_colors(C["gold"] if tv == t else C["bg3"],
                         C["sidebar"] if tv == t else C["ink2"],
                         C["gold"] if tv == t else C["bg2"])

    def _sel_deck(self, key):
        self._deck_key = key
        for k, b in self._deck_btns.items():
            b.set_colors(C["blue"] if k == key else C["bg3"],
                         C["white"] if k == key else C["ink2"],
                         C["blue2"] if k == key else C["bg2"])

    def _start_quiz(self):
        cat = self._setup_cat_var.get()
        if cat == "All Categories":
            self.words = self.all_words.copy()
        else:
            self.words = [w for w in self.all_words
                          if (w.get("category","") or "Uncategorized") == cat]
        if self._deck_key == "srs":
            due = [w for w in self.words if srs_is_due(w)]
            self.words = due if due else self.words   # fall back to all if none due

        if not self.words:
            messagebox.showinfo("No words", "No words match that selection.", parent=self)
            return

        self.idx = self.correct = self.wrong = 0
        self._phase = "quiz"
        self._build_quiz_ui()
        self._new_deck()

    def _build_quiz_ui(self):
        self._clear_content()
        c = self.content
        c.config(bg=C["bg"])

        ctrl = tk.Frame(c, bg=C["bg2"])
        ctrl.pack(fill="x")
        ctrl_inner = tk.Frame(ctrl, bg=C["bg2"])
        ctrl_inner.pack(fill="x", padx=12, pady=6)

        self.mode_lbl2 = lbl(ctrl_inner, "Mode:", font=FONT_UIS, fg=C["ink2"], bg=C["bg2"])
        self.mode_lbl2.pack(side="left")
        self.mode_var2 = tk.StringVar(value=self._mode_var.get())
        modes = list(self.MODES.keys())
        self.mode_menu2 = ttk.OptionMenu(ctrl_inner, self.mode_var2, self.mode_var2.get(),
                                          *modes, command=lambda _: self._new_deck())
        self.mode_menu2.pack(side="left", padx=(4,12))

        self.restart_btn = FlatButton(ctrl_inner, "↺  Restart", command=self._new_deck,
                                       font=FONT_UIS, padx=10, pady=4)
        self.restart_btn.pack(side="right")
        self.setup_btn = FlatButton(ctrl_inner, "⚙  Setup", command=self._show_setup,
                                     font=FONT_UIS, padx=10, pady=4)
        self.setup_btn.pack(side="right", padx=(0,6))
        self.deck_lbl = lbl(ctrl_inner, "", font=FONT_UIS, fg=C["ink3"], bg=C["bg2"])
        self.deck_lbl.pack(side="right", padx=(0,8))

        sep(c).pack(fill="x")

        self.card = tk.Frame(c, bg=C["bg"])
        self.card.pack(fill="both", expand=True, padx=28, pady=12)
        self._build_card_widgets()

    def _build_card_widgets(self):
        for w in self.card.winfo_children():
            w.destroy()

        top_row = tk.Frame(self.card, bg=C["bg"])
        top_row.pack(fill="x", pady=(0,4))
        self.progress_lbl = lbl(top_row, "", font=FONT_UIS, fg=C["ink3"], bg=C["bg"])
        self.progress_lbl.pack(side="left")
        self.timer_lbl = lbl(top_row, "", font=FONT_UIB, fg=C["gold"], bg=C["bg"])
        self.timer_lbl.pack(side="right")

        self.prog_bar_outer = tk.Frame(self.card, bg=C["bg3"], height=4)
        self.prog_bar_outer.pack(fill="x", pady=(0,10))
        self.prog_bar_outer.pack_propagate(False)
        self.prog_bar_inner = tk.Frame(self.prog_bar_outer, bg=C["red"], height=4)
        self.prog_bar_inner.place(x=0, y=0, relheight=1.0, width=0)

        self.prompt_lbl = lbl(self.card, "", font=FONT_UIS, fg=C["ink2"], bg=C["bg"])
        self.prompt_lbl.pack(pady=(4,4))

        self.q_box = tk.Frame(self.card, highlightthickness=1,
                               highlightbackground=C["bg3"], bg=C["bg2"])
        self.q_box.pack(fill="x", pady=(0,16), ipady=18, ipadx=12)
        self.q_lbl = lbl(self.q_box, "", font=FONT_JPLG, fg=C["ink"], bg=C["bg2"])
        self.q_lbl.pack()

        self.srs_badge = lbl(self.card, "", font=FONT_UIS, fg=C["ink3"], bg=C["bg"])
        self.srs_badge.pack(pady=(0,6))

        self.ans_area = tk.Frame(self.card, bg=C["bg"])
        self.ans_area.pack(fill="x")

        self.fb_frame = tk.Frame(self.card, bg=C["bg"])
        self.fb_frame.pack(fill="x", pady=(12,0))
        self.fb_icon = lbl(self.fb_frame, "", font=("Segoe UI", 22), fg=C["ink"], bg=C["bg"])
        self.fb_icon.pack()
        self.fb_lbl  = lbl(self.fb_frame, "", font=FONT_JP,  fg=C["ink2"], bg=C["bg"])
        self.fb_lbl.pack()
        self.fb_hint = lbl(self.fb_frame, "", font=FONT_UIS, fg=C["ink3"],  bg=C["bg"])
        self.fb_hint.pack()

        self.next_btn = FlatButton(self.card, "Next  →", padx=16, pady=8, command=self._next_card)
        self.next_btn.set_colors(C["blue"], C["white"], C["blue2"])

        self._apply_ctrl_theme()

    def _apply_ctrl_theme(self):
        try:
            self.restart_btn.set_colors(C["bg3"], C["ink2"], C["bg2"])
            self.setup_btn.set_colors(C["bg3"], C["ink2"], C["bg2"])
            self.deck_lbl.config(bg=C["bg2"], fg=C["ink3"])
            self.mode_lbl2.config(bg=C["bg2"], fg=C["ink2"])
        except Exception:
            pass

    def _new_deck(self, *_):
        self._cancel_timer()
        mode = self.mode_var2.get() if hasattr(self, "mode_var2") else self._mode_var.get()
        self.deck = [w for w in self.words if w.get(self.MODES[mode][0],"")]
        random.shuffle(self.deck)
        self.idx = self.correct = self.wrong = 0
        n = len(self.deck)
        if hasattr(self, "deck_lbl"):
            self.deck_lbl.config(text=f"{n} card{'s' if n!=1 else ''}")
        self._build_card_widgets()
        self._next_card()

    def _next_card(self):
        self._cancel_timer()
        self.next_btn.pack_forget()
        for w in [self.fb_icon, self.fb_lbl, self.fb_hint]:
            w.config(text="")
        self.unbind("<Return>")

        if self.idx >= len(self.deck):
            self._show_results()
            return

        card = self.deck[self.idx]
        mode = self.mode_var2.get() if hasattr(self, "mode_var2") else self._mode_var.get()
        src, dst = self.MODES[mode]

        total  = len(self.deck)
        filled = int((self.idx / total) * 100) if total else 0
        self.progress_lbl.config(text=f"Card {self.idx+1} / {total}")
        self.prog_bar_outer.update_idletasks()
        bar_w  = self.prog_bar_outer.winfo_width()
        self.prog_bar_inner.place(width=max(2, int(bar_w * self.idx / total)))

        self.prompt_lbl.config(text=f"What is the  {dst.upper()}  of:")
        self.q_lbl.config(text=card.get(src,"") or "(empty)")
        self.q_box.config(highlightbackground=C["bg3"])

        slvl  = card.get("srs_level", 0)
        self.srs_badge.config(text=f"SRS: {srs_label(slvl)}  (lv {slvl})")

        self._update_score()

        fmt = self._fmt_var.get()
        if fmt == "mc":
            self._build_mc(card, dst)
        else:
            self._build_type_in(card)

        t = self._timer_var.get()
        if t > 0:
            self._time_left = t
            self._tick()

    def _build_type_in(self, card):
        for w in self.ans_area.winfo_children():
            w.destroy()
        self.ans_area.config(bg=C["bg"])
        lbl(self.ans_area, "Type your answer:", font=FONT_UIS,
            fg=C["ink2"], bg=C["bg"]).pack(anchor="w")
        row = tk.Frame(self.ans_area, bg=C["bg"])
        row.pack(fill="x", pady=(4,0))
        self.ans_var = tk.StringVar()
        self.ans_entry = tk.Entry(row, textvariable=self.ans_var,
                                   font=FONT_JP, relief="flat", bd=0,
                                   highlightthickness=2,
                                   highlightbackground=C["bg3"],
                                   bg=C["entry_bg"], fg=C["entry_fg"],
                                   insertbackground=C["entry_fg"])
        self.ans_entry.pack(side="left", fill="x", expand=True, ipady=8)
        self.ans_entry.bind("<Return>", lambda e: self._check_type())
        chk = FlatButton(row, "Check →", command=self._check_type, padx=14, pady=8)
        chk.set_colors(C["red"], C["white"], C["red2"])
        chk.pack(side="left", padx=(8,0))
        self.ans_entry.focus()

    def _build_mc(self, card, dst):
        for w in self.ans_area.winfo_children():
            w.destroy()
        self.ans_area.config(bg=C["bg"])
        correct = (card.get(dst,"") or "").strip()
        all_vals = list({(w.get(dst,"") or "").strip()
                         for w in self.all_words
                         if (w.get(dst,"") or "").strip() and w is not card})
        if len(all_vals) < 3:
            self._build_type_in(card)
            return
        distractors = random.sample(all_vals, 3)
        options     = distractors + [correct]
        random.shuffle(options)
        self._mc_correct = correct
        self._mc_answered = False
        cols_frame = tk.Frame(self.ans_area, bg=C["bg"])
        cols_frame.pack(fill="x")
        cols_frame.columnconfigure(0, weight=1)
        cols_frame.columnconfigure(1, weight=1)
        self._mc_btns = []
        for i, opt in enumerate(options):
            row_i, col_i = divmod(i, 2)
            b = FlatButton(cols_frame, opt, font=FONT_JP, padx=10, pady=10,
                           command=lambda o=opt: self._check_mc(o),
                           wraplength=200)
            b.grid(row=row_i, column=col_i, sticky="nsew", padx=4, pady=4)
            b.set_colors(C["bg2"], C["ink"], C["bg3"])
            self._mc_btns.append((opt, b))

    def _check_type(self):
        if self.idx >= len(self.deck):
            return
        self._cancel_timer()
        card = self.deck[self.idx]
        mode = self.mode_var2.get() if hasattr(self, "mode_var2") else self._mode_var.get()
        _, dst = self.MODES[mode]
        expected = (card.get(dst,"") or "").strip()
        given    = self.ans_var.get().strip()
        correct  = normalize_kana(given.lower()) == normalize_kana(expected.lower())
        self._record(card, correct, expected, dst)
        try:
            self.ans_entry.config(state="disabled",
                highlightbackground=C["green"] if correct else C["red"])
        except Exception:
            pass

    def _check_mc(self, chosen):
        if getattr(self, "_mc_answered", False):
            return
        self._mc_answered = True
        self._cancel_timer()
        card    = self.deck[self.idx]
        mode    = self.mode_var2.get() if hasattr(self, "mode_var2") else self._mode_var.get()
        _, dst  = self.MODES[mode]
        correct = chosen == self._mc_correct
        for opt, b in self._mc_btns:
            if opt == self._mc_correct:
                b.set_colors(C["green"], C["white"], C["green"])
            elif opt == chosen and not correct:
                b.set_colors(C["red"], C["white"], C["red"])
            else:
                b.set_colors(C["bg3"], C["ink3"], C["bg3"])
        self._record(card, correct, self._mc_correct, dst)

    def _auto_fail(self):
        self.timer_lbl.config(text="✗", fg=C["red"])
        if self._fmt_var.get() == "mc":
            self._check_mc("__timeout__")
        else:
            try:
                self.ans_entry.config(state="disabled")
            except Exception:
                pass
            card   = self.deck[self.idx]
            mode   = self.mode_var2.get() if hasattr(self, "mode_var2") else self._mode_var.get()
            _, dst = self.MODES[mode]
            self._record(card, False, (card.get(dst,"") or "").strip(), dst)

    def _record(self, card, correct, expected, dst):
        if correct:
            self.correct += 1
            self.fb_icon.config(text="✓", fg=C["green"])
            self.fb_lbl.config(text=f"Correct!   {expected}", fg=C["green"])
            self.fb_hint.config(text="")
        else:
            self.wrong += 1
            self.fb_icon.config(text="✗", fg=C["red"])
            self.fb_lbl.config(text=f"Answer:  {expected or '(no entry)'}", fg=C["red"])
            hint = card.get("comment","")
            if hint and dst != "comment":
                self.fb_hint.config(text=f"💬  {hint[:80]}")
        wid = card.get("id","")
        if wid:
            try:
                for w in self.parent_app.current_dict["words"]:
                    if w["id"] == wid:
                        srs_advance(w, correct)
                        break
                save_dict(self.parent_app.current_dict)
            except Exception:
                pass
        # badge update
        slvl = card.get("srs_level", 0)
        self.srs_badge.config(text=f"SRS: {srs_label(slvl)}  (lv {slvl})")
        self.idx += 1
        self._update_score()
        self.next_btn.pack(pady=(10,0))
        self.next_btn.focus()
        self.bind("<Return>", lambda e: self._next_card())

    def _tick(self):
        if self._time_left <= 0:
            self._auto_fail()
            return
        color = C["red"] if self._time_left <= 3 else C["gold"]
        self.timer_lbl.config(text=f"⏱ {self._time_left}s", fg=color)
        self._time_left -= 1
        self._timer_job = self.after(1000, self._tick)

    def _cancel_timer(self):
        if self._timer_job:
            self.after_cancel(self._timer_job)
            self._timer_job = None
        try:
            self.timer_lbl.config(text="")
        except Exception:
            pass

    def _update_score(self):
        self.score_lbl.config(text=f"✓ {self.correct}   ✗ {self.wrong}")

    def _show_results(self):
        self._cancel_timer()
        self._clear_content()
        self._phase = "results"
        c = self.content
        c.config(bg=C["bg"])

        total = self.correct + self.wrong
        pct   = int(self.correct / total * 100) if total else 0
        if   pct >= 90: grade, gc = "🏆  Excellent!", "gold"
        elif pct >= 70: grade, gc = "👍  Good Job!",  "green"
        elif pct >= 50: grade, gc = "📖  Keep Going!", "blue"
        else:           grade, gc = "😤  More Practice!", "red"

        lbl(c, grade, font=FONT_H1, fg=C[gc], bg=C["bg"]).pack(pady=(32,8))
        lbl(c, f"{self.correct} / {total}  ({pct}%)",
            font=FONT_H2, fg=C["green"] if pct >= 70 else C["red"],
            bg=C["bg"]).pack()
        lbl(c, f"✓ {self.correct} correct   ✗ {self.wrong} wrong",
            font=FONT_UI, fg=C["ink2"], bg=C["bg"]).pack(pady=(4,24))

        # SRS summary
        due_now = sum(1 for w in self.all_words if srs_is_due(w))
        mastered= sum(1 for w in self.all_words if w.get("srs_level",0) >= 5)
        lbl(c, f"SRS — Due now: {due_now}   Mastered: {mastered}/{len(self.all_words)}",
            font=FONT_UIS, fg=C["ink3"], bg=C["bg"]).pack(pady=(0,20))

        btn_row = tk.Frame(c, bg=C["bg"])
        btn_row.pack()
        again = FlatButton(btn_row, "Try Again", command=self._new_deck, padx=14, pady=8)
        again.set_colors(C["red"], C["white"], C["red2"])
        again.pack(side="left", padx=6)
        setup_b = FlatButton(btn_row, "⚙  Change Setup", command=self._show_setup,
                              font=FONT_UI, padx=12, pady=8)
        setup_b.set_colors(C["bg3"], C["ink2"], C["bg2"])
        setup_b.pack(side="left", padx=6)
        close_b = FlatButton(btn_row, "Close", command=self.destroy,
                              font=FONT_UI, padx=12, pady=8)
        close_b.set_colors(C["bg3"], C["ink2"], C["bg2"])
        close_b.pack(side="left", padx=6)

    def update_theme(self):
        self.configure(bg=C["bg"])
        self.hdr.config(bg=C["sidebar"])
        self.hdr_lbl.config(bg=C["sidebar"])
        self.score_lbl.config(bg=C["sidebar"])
        self.sep0.config(bg=C["bg3"])
        self.content.config(bg=C["bg"])


class JLPTManagerDialog(tk.Toplevel):
    """Download JLPT data and tag words in the current dictionary."""

    def __init__(self, parent, current_dict):
        super().__init__(parent)
        self.title("JLPT Data & Tagging")
        self.resizable(False, False)
        self.current_dict = current_dict
        self.cache = load_jlpt_cache()
        self.after(50, lambda: _safe_grab(self))
        self._build_ui()
        self._update_theme()
        self._center(parent)
        self._refresh_status()

    def _build_ui(self):
        self.hdr = tk.Frame(self, pady=14)
        self.hdr.pack(fill="x")
        self.hdr_lbl = lbl(self.hdr, "🎌  JLPT Data Manager", font=FONT_H2, fg=C["white"])
        self.hdr_lbl.pack(padx=20, anchor="w")

        self.body = tk.Frame(self, padx=24, pady=12)
        self.body.pack(fill="both", expand=True)

        lbl(self.body, "Cached levels (downloaded once, stored locally):",
            font=FONT_UIS, fg=C["ink2"]).pack(anchor="w", pady=(0,8))

        self.level_rows = {}
        for lvl in JLPT_LEVEL_NAMES:
            row = tk.Frame(self.body)
            row.pack(fill="x", pady=3)
            name_l = lbl(row, lvl, font=FONT_UIB, fg=C["ink"], width=4)
            name_l.pack(side="left")
            status_l = lbl(row, "—", font=FONT_UIS, fg=C["ink3"])
            status_l.pack(side="left", padx=8)
            btn = FlatButton(row, "Download", command=lambda l=lvl: self._download(l),
                             font=FONT_UIS, padx=10, pady=4)
            btn.pack(side="right")
            self.level_rows[lvl] = (name_l, status_l, btn)

        sep(self.body).pack(fill="x", pady=12)

        self.log_var = tk.StringVar(value="")
        lbl_log = lbl(self.body, "", textvariable=self.log_var,
                      font=FONT_UIS, fg=C["ink3"])
        lbl_log.pack(anchor="w")
        self.log_lbl = lbl_log

        sep(self.body).pack(fill="x", pady=12)

        lbl(self.body, "Tag your dictionary words with JLPT level:",
            font=FONT_UIS, fg=C["ink2"]).pack(anchor="w", pady=(0,6))

        if self.current_dict:
            self.tagged_var = tk.StringVar(value="")
            lbl(self.body, "", textvariable=self.tagged_var,
                font=FONT_UIS, fg=C["ink3"]).pack(anchor="w", pady=(0,6))
            self._refresh_tagged()
            tag_btn = FlatButton(self.body, "⚡  Auto-Tag All Words",
                                  command=self._tag_words, font=FONT_UI, padx=14, pady=7)
            tag_btn.set_colors(C["red"], C["white"], C["red2"])
            tag_btn.pack(anchor="w")
            self.tag_btn = tag_btn
        else:
            lbl(self.body, "No dictionary loaded.", font=FONT_UIS, fg=C["ink3"]).pack(anchor="w")

        sep(self.body).pack(fill="x", pady=10)
        close_btn = FlatButton(self.body, "Done", command=self.destroy,
                               font=FONT_UI, padx=14, pady=7)
        close_btn.set_colors(C["bg3"], C["ink2"], C["bg2"])
        close_btn.pack(anchor="e")
        self.close_btn = close_btn

    def _refresh_status(self):
        for lvl, (nl, sl, btn) in self.level_rows.items():
            entries = self.cache.get(lvl, None)
            if entries is not None:
                sl.config(text=f"✓ {len(entries)} words cached", fg=C["green"])
                btn.config(text="Re-download")
                btn.set_colors(C["bg3"], C["ink2"], C["bg2"])
            else:
                sl.config(text="Not downloaded", fg=C["ink3"])
                btn.config(text="Download")
                btn.set_colors(C["blue"], C["white"], C["blue2"])

    def _refresh_tagged(self):
        if not self.current_dict:
            return
        words   = self.current_dict.get("words", [])
        tagged  = sum(1 for w in words if w.get("jlpt_level",""))
        self.tagged_var.set(f"{tagged}/{len(words)} words tagged with JLPT level")

    def _download(self, lvl):
        n = int(lvl[1])   # "N5" → 5, "N2" → 2
        self.log_var.set(f"Downloading {lvl}…")
        _, sl, btn = self.level_rows[lvl]
        sl.config(text="Downloading…", fg=C["gold"])
        btn.config(state="disabled")

        def _done(level_key, count, err):
            if err:
                self.after(0, lambda: (
                    sl.config(text=f"Error: {err[:40]}", fg=C["red"]),
                    btn.config(state="normal"),
                    self.log_var.set(f"Failed to download {level_key}"),
                ))
            else:
                self.cache = load_jlpt_cache()
                self.after(0, lambda: (
                    self._refresh_status(),
                    self.log_var.set(f"{level_key}: {count} entries cached ✓"),
                ))

        fetch_jlpt_level(n, self.cache, on_done=_done)

    def _tag_words(self):
        if not self.current_dict:
            return
        if not any(self.cache.get(lvl) for lvl in JLPT_LEVEL_NAMES):
            messagebox.showwarning("No Data",
                "Download at least one JLPT level first.", parent=self)
            return
        count = 0
        for w in self.current_dict["words"]:
            lvl = jlpt_lookup(w, self.cache)
            if lvl:
                w["jlpt_level"] = lvl
                count += 1
            elif "jlpt_level" not in w:
                w["jlpt_level"] = ""
        save_dict(self.current_dict)
        self._refresh_tagged()
        self.log_var.set(f"Tagged {count} words with JLPT levels ✓")
        messagebox.showinfo("Done", f"Tagged {count} of {len(self.current_dict['words'])} words.",
                            parent=self)

    def _update_theme(self):
        self.configure(bg=C["bg"])
        self.hdr.config(bg=C["sidebar"])
        self.hdr_lbl.config(bg=C["sidebar"], fg=C["white"])
        self.body.config(bg=C["bg"])
        self.log_lbl.config(bg=C["bg"])
        for _, (nl, sl, btn) in self.level_rows.items():
            nl.config(bg=C["bg"])
            sl.config(bg=C["bg"])

    def _center(self, parent):
        self.update_idletasks()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        px, py = parent.winfo_x(), parent.winfo_y()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        self.geometry(f"{w}x{h}+{px+pw//2-w//2}+{py+ph//2-h//2}")


class ExamWindow(tk.Toplevel):
    """JLPT-style exam using your dictionary words cross-referenced with official vocab."""

    SECTIONS = [
        ("文字 (Kanji Reading)", "word",    "reading"),
        ("語彙 (Vocabulary)",    "reading", "word"),
        ("意味 (Meaning)",       "word",    "meaning_or_comment"),
    ]

    def __init__(self, parent, current_dict):
        super().__init__(parent)
        self.title("JLPT Exam Mode  — 試験")
        self.geometry("600x660")
        self.minsize(520, 560)
        self.resizable(True, True)
        self.after(50, lambda: _safe_grab(self))

        self.parent_app   = parent
        self.current_dict = current_dict
        self.cache        = load_jlpt_cache()
        self._timer_job   = None

        self._build_skeleton()
        self.update_theme()
        self._show_setup()

    def _build_skeleton(self):
        self.hdr = tk.Frame(self)
        self.hdr.pack(fill="x")
        self.hdr_lbl = lbl(self.hdr, "試験  JLPT Exam", font=FONT_H2, fg=C["white"])
        self.hdr_lbl.pack(side="left", padx=16, pady=12)
        self.score_lbl = lbl(self.hdr, "", font=FONT_UIS, fg=C["ink3"])
        self.score_lbl.pack(side="right", padx=16)
        sep(self).pack(fill="x")
        self.content = tk.Frame(self)
        self.content.pack(fill="both", expand=True)

    def _clear(self):
        for w in self.content.winfo_children():
            w.destroy()

    def _show_setup(self):
        self._cancel_timer()
        self._clear()
        self.score_lbl.config(text="")
        c = self.content
        c.config(bg=C["bg"])
        pad = tk.Frame(c, bg=C["bg"])
        pad.pack(fill="both", expand=True, padx=28, pady=16)

        lbl(pad, "Select JLPT Level", font=FONT_H2, fg=C["ink"], bg=C["bg"]).pack(anchor="w")
        sep(pad, bg=C["bg3"]).pack(fill="x", pady=(6,14))

        available = [lvl for lvl in JLPT_LEVEL_NAMES if self.cache.get(lvl)]

        if not available:
            lbl(pad, "⚠  No JLPT vocab data downloaded yet.", font=FONT_UI,
                fg=C["gold"], bg=C["bg"]).pack(anchor="w", pady=(0,4))
            lbl(pad, "You can still take a grammar-only exam below.",
                font=FONT_UIS, fg=C["ink2"], bg=C["bg"]).pack(anchor="w", pady=(0,12))
            available_g = [lvl for lvl in JLPT_LEVEL_NAMES if GRAMMAR_QUESTIONS.get(lvl)]
            self._exam_level_var = tk.StringVar(value=available_g[0] if available_g else "N5")
            level_row = tk.Frame(pad, bg=C["bg"])
            level_row.pack(fill="x", pady=(0,16))
            self._lvl_btns = {}
            for lvl in available_g:
                b = FlatButton(level_row, f"{lvl}\n(grammar only)",
                               command=lambda l=lvl: self._sel_level(l),
                               font=FONT_UIS, padx=14, pady=10)
                b.pack(side="left", padx=(0,8))
                self._lvl_btns[lvl] = b
            self._sel_level(available_g[0] if available_g else "N5")

            self._section_vars = {}
            for sec_name, src, dst in self.SECTIONS:
                self._section_vars[sec_name] = (tk.BooleanVar(value=False), src, dst)

            grammar_count = len(GRAMMAR_QUESTIONS.get(self._exam_level_var.get(), []))
            self._grammar_var = tk.BooleanVar(value=True)
            grammar_row = tk.Frame(pad, bg=C["bg"])
            grammar_row.pack(anchor="w", pady=(0,16))
            tk.Checkbutton(grammar_row, text="文法 (Grammar / Particles)",
                           variable=self._grammar_var,
                           font=FONT_UI, bg=C["bg"], fg=C["ink"],
                           selectcolor=C["bg2"], activebackground=C["bg"]).pack(side="left")
            lbl(grammar_row, f"  {grammar_count} questions",
                font=FONT_UIS, fg=C["ink3"], bg=C["bg"]).pack(side="left")

            self._exam_timer_var = tk.IntVar(value=20)
            tmr_row = tk.Frame(pad, bg=C["bg"])
            tmr_row.pack(fill="x", pady=(0,16))
            self._etmr_btns = {}
            for t in [0, 10, 15, 20, 30]:
                label = "Off" if t == 0 else f"{t}s"
                b = FlatButton(tmr_row, label, font=FONT_UIS, padx=10, pady=5,
                               command=lambda tv=t: self._sel_etimer(tv))
                b.pack(side="left", padx=(0,5))
                self._etmr_btns[t] = b
            self._sel_etimer(20)

            btn_row = tk.Frame(pad, bg=C["bg"])
            btn_row.pack(fill="x")
            start_btn = FlatButton(btn_row, "Begin Grammar Exam  →", command=self._start_exam,
                                    padx=18, pady=9)
            start_btn.set_colors(C["red"], C["white"], C["red2"])
            start_btn.pack(side="right")
            return

        self._exam_level_var = tk.StringVar(value=available[0])
        level_row = tk.Frame(pad, bg=C["bg"])
        level_row.pack(fill="x", pady=(0,16))
        self._lvl_btns = {}
        for lvl in available:
            pool_size = len(get_exam_pool(
                self.current_dict.get("words",[]), self.cache, lvl))
            b = FlatButton(level_row, f"{lvl}\n({pool_size} matching words)",
                           command=lambda l=lvl: self._sel_level(l),
                           font=FONT_UIS, padx=14, pady=10)
            b.pack(side="left", padx=(0,8))
            self._lvl_btns[lvl] = b
        self._sel_level(available[0])

        lbl(pad, "Sections", font=FONT_H2, fg=C["ink"], bg=C["bg"]).pack(anchor="w", pady=(12,4))
        sep(pad, bg=C["bg3"]).pack(fill="x", pady=(0,10))
        self._section_vars = {}
        for sec_name, src, dst in self.SECTIONS:
            v = tk.BooleanVar(value=True)
            cb = tk.Checkbutton(pad, text=sec_name, variable=v,
                                font=FONT_UI, bg=C["bg"], fg=C["ink"],
                                selectcolor=C["bg2"], activebackground=C["bg"])
            cb.pack(anchor="w", pady=2)
            self._section_vars[sec_name] = (v, src, dst)

        grammar_count = len(GRAMMAR_QUESTIONS.get(available[0] if available else "N5", []))
        self._grammar_var = tk.BooleanVar(value=True)
        grammar_row = tk.Frame(pad, bg=C["bg"])
        grammar_row.pack(anchor="w", pady=2)
        tk.Checkbutton(grammar_row, text="文法 (Grammar / Particles)",
                       variable=self._grammar_var,
                       font=FONT_UI, bg=C["bg"], fg=C["ink"],
                       selectcolor=C["bg2"], activebackground=C["bg"]).pack(side="left")
        lbl(grammar_row, f"  {grammar_count} built-in questions",
            font=FONT_UIS, fg=C["ink3"], bg=C["bg"]).pack(side="left")

        lbl(pad, "Timer per Question", font=FONT_H2, fg=C["ink"], bg=C["bg"]).pack(anchor="w", pady=(14,4))
        sep(pad, bg=C["bg3"]).pack(fill="x", pady=(0,10))
        self._exam_timer_var = tk.IntVar(value=20)
        tmr_row = tk.Frame(pad, bg=C["bg"])
        tmr_row.pack(fill="x")
        self._etmr_btns = {}
        for t in [0, 10, 15, 20, 30]:
            label = "Off" if t == 0 else f"{t}s"
            b = FlatButton(tmr_row, label, font=FONT_UIS, padx=10, pady=5,
                           command=lambda tv=t: self._sel_etimer(tv))
            b.pack(side="left", padx=(0,5))
            self._etmr_btns[t] = b
        self._sel_etimer(20)

        btn_row = tk.Frame(pad, bg=C["bg"])
        btn_row.pack(fill="x", pady=(20,0))
        start_btn = FlatButton(btn_row, "Begin Exam  →", command=self._start_exam,
                                padx=18, pady=9)
        start_btn.set_colors(C["red"], C["white"], C["red2"])
        start_btn.pack(side="right")

    def _sel_level(self, lvl):
        self._exam_level_var.set(lvl)
        for l, b in self._lvl_btns.items():
            b.set_colors(C["red"] if l == lvl else C["bg3"],
                         C["white"] if l == lvl else C["ink2"],
                         C["red2"] if l == lvl else C["bg2"])

    def _sel_etimer(self, t):
        self._exam_timer_var.set(t)
        for tv, b in self._etmr_btns.items():
            b.set_colors(C["gold"] if tv == t else C["bg3"],
                         C["sidebar"] if tv == t else C["ink2"],
                         C["gold"] if tv == t else C["bg2"])

    _CTX_SENTENCES = [
        ("昨日、{TARGET}を 買いました。",             "Yesterday, I bought {TARGET}."),
        ("この {TARGET}は とても 便利です。",          "This {TARGET} is very useful."),
        ("友達に {TARGET}を あげました。",             "I gave {TARGET} to a friend."),
        ("先生は {TARGET}を 説明しました。",           "The teacher explained {TARGET}."),
        ("{TARGET}を 使って ください。",              "Please use {TARGET}."),
        ("今日は {TARGET}が ありません。",             "There is no {TARGET} today."),
        ("私は {TARGET}が 好きです。",                "I like {TARGET}."),
        ("{TARGET}は どこに ありますか？",             "Where is {TARGET}?"),
        ("毎朝 {TARGET}を 見ています。",              "I look at {TARGET} every morning."),
        ("この 問題は {TARGET}に 関係しています。",    "This problem relates to {TARGET}."),
    ]

    def _start_exam(self):
        lvl      = self._exam_level_var.get()
        pool     = get_exam_pool(self.current_dict.get("words",[]), self.cache, lvl)
        all_jlpt = self.cache.get(lvl, [])
        user_words = self.current_dict.get("words", [])

        questions = []

        for sec_name, src, dst in self.SECTIONS:
            v, _s, _d = self._section_vars[sec_name]
            if not v.get():
                continue
            if len(pool) < 4:
                continue
            for entry in pool:
                q_word    = entry.get("word","") or ""
                q_reading = entry.get("reading","") or ""
                q_meaning = entry.get("meaning","") or ""
                uw = next((w for w in user_words
                           if normalize_kana((w.get("word","") or "").lower()) ==
                              normalize_kana(q_word.lower())), None)
                if uw and uw.get("comment",""):
                    q_meaning = uw["comment"]

                if src == "word":
                    q_show = q_word
                    a_text = q_reading if dst == "reading" else q_meaning
                else:  # src == "reading"
                    q_show = q_reading
                    a_text = q_word

                if not q_show or not a_text:
                    continue

                ctx_jp, ctx_en = random.choice(self._CTX_SENTENCES)
                if dst == "reading":
                    prompt_jp = ctx_jp.replace("{TARGET}", q_word)
                    prompt_en = ctx_en.replace("{TARGET}", f"[{q_word}]")
                    prompt_label = "What is the reading of the underlined word?"
                elif dst == "word":
                    prompt_jp = ctx_jp.replace("{TARGET}", q_reading)
                    prompt_en = ctx_en.replace("{TARGET}", f"[{q_reading}]")
                    prompt_label = "Which kanji correctly writes the underlined word?"
                else:  # meaning
                    prompt_jp = ctx_jp.replace("{TARGET}", q_word)
                    prompt_en = ctx_en.replace("{TARGET}", f"[{q_word}]")
                    prompt_label = "What does the underlined word mean?"

                dist_pool = [e.get(dst,"") or e.get("reading","") if dst != "meaning_or_comment"
                             else e.get("meaning","")
                             for e in all_jlpt
                             if (e.get("word","") or "") != q_word
                             and (e.get(dst,"") or e.get("reading","") if dst != "meaning_or_comment"
                                  else e.get("meaning",""))]
                dist_pool = [d for d in dist_pool if d and d != a_text]
                if len(dist_pool) < 3:
                    continue
                distractors = random.sample(dist_pool, 3)
                options = distractors + [a_text]
                random.shuffle(options)
                questions.append({
                    "type":         "vocab",
                    "section":      sec_name,
                    "q":            prompt_jp,
                    "q_label":      prompt_label,
                    "translation":  prompt_en,
                    "a":            a_text,
                    "options":      options,
                    "explanation":  f"The correct answer is: {a_text}",
                })

        if getattr(self, "_grammar_var", None) and self._grammar_var.get():
            gram_qs = get_grammar_questions(lvl)
            random.shuffle(gram_qs)
            for gq in gram_qs:
                questions.append({
                    "type":        "grammar",
                    "section":     "文法 (Grammar)",
                    "q":           gq["sentence"],
                    "translation": gq["translation"],
                    "a":           gq["options"][gq["answer"]],
                    "options":     gq["options"],
                    "explanation": gq.get("explanation",""),
                })
            tmpl_qs = build_template_questions(lvl, user_words, max_q=15)
            for tq in tmpl_qs:
                questions.append({
                    "type":        "grammar",
                    "section":     "文法 — Personal (Grammar with your words)",
                    "q":           tq["sentence"],
                    "translation": tq["translation"],
                    "a":           tq["options"][tq["answer"]],
                    "options":     tq["options"],
                    "explanation": tq.get("explanation",""),
                })

        if not questions:
            messagebox.showwarning("No Questions",
                "Could not build any questions.\n\n"
                "• Vocab sections: download JLPT data (Tools → JLPT Data Manager)"
                " and ensure your words match.\n"
                "• Grammar: enable the 文法 section.", parent=self)
            return

        random.shuffle(questions)
        self.questions  = questions
        self.q_idx      = 0
        self.q_correct  = 0
        self.q_wrong    = 0
        self.q_answered = []
        self._build_exam_ui()
        self._show_question()

    # exam ui
    def _build_exam_ui(self):
        self._clear()
        c = self.content
        c.config(bg=C["bg"])

        ctrl = tk.Frame(c, bg=C["bg2"])
        ctrl.pack(fill="x")
        ctrl_i = tk.Frame(ctrl, bg=C["bg2"])
        ctrl_i.pack(fill="x", padx=12, pady=6)
        self.sect_lbl = lbl(ctrl_i, "", font=FONT_UIS, fg=C["ink2"], bg=C["bg2"])
        self.sect_lbl.pack(side="left")
        self.q_prog_lbl = lbl(ctrl_i, "", font=FONT_UIS, fg=C["ink3"], bg=C["bg2"])
        self.q_prog_lbl.pack(side="right")
        sep(c).pack(fill="x")

        self.card = tk.Frame(c, bg=C["bg"])
        self.card.pack(fill="both", expand=True, padx=28, pady=16)

    def _show_question(self):
        self._cancel_timer()
        for w in self.card.winfo_children():
            w.destroy()
        self.card.config(bg=C["bg"])

        if self.q_idx >= len(self.questions):
            self._show_exam_results()
            return

        q     = self.questions[self.q_idx]
        total = len(self.questions)

        self.sect_lbl.config(text=q["section"])
        self.q_prog_lbl.config(text=f"Q {self.q_idx+1} / {total}")
        self.score_lbl.config(text=f"✓ {self.q_correct}   ✗ {self.q_wrong}")

        bar_outer = tk.Frame(self.card, bg=C["bg3"], height=4)
        bar_outer.pack(fill="x", pady=(0,14))
        bar_outer.pack_propagate(False)
        bar_outer.update_idletasks()
        bw = bar_outer.winfo_width() or 500
        bar_inner = tk.Frame(bar_outer, bg=C["red"], height=4,
                              width=max(2, int(bw * self.q_idx / total)))
        bar_inner.place(x=0, y=0, relheight=1.0)

        tmr_row = tk.Frame(self.card, bg=C["bg"])
        tmr_row.pack(fill="x")
        lbl(tmr_row, f"Question {self.q_idx+1}", font=FONT_UIS,
            fg=C["ink3"], bg=C["bg"]).pack(side="left")
        self.exam_timer_lbl = lbl(tmr_row, "", font=FONT_UIB, fg=C["gold"], bg=C["bg"])
        self.exam_timer_lbl.pack(side="right")

        is_grammar = q.get("type") == "grammar"

        if is_grammar:
            sent_outer = tk.Frame(self.card, bg=C["red"], pady=0)
            sent_outer.pack(fill="x", pady=(8,6))
            sent_inner = tk.Frame(sent_outer, bg=C["bg2"])
            sent_inner.pack(fill="x", padx=3)
            badge_row = tk.Frame(sent_inner, bg=C["bg2"])
            badge_row.pack(fill="x", padx=12, pady=(10,2))
            q_num = self.q_idx + 1
            lbl(badge_row, f"{q_num}", font=FONT_UIB,
                fg=C["red"], bg=C["bg2"]).pack(side="left")
            lbl(badge_row, "  文法問題", font=FONT_UIS,
                fg=C["ink3"], bg=C["bg2"]).pack(side="left")
            sentence_lbl = lbl(sent_inner, q["q"], font=FONT_JP,
                                fg=C["ink"], bg=C["bg2"],
                                wraplength=480, justify="left")
            sentence_lbl.pack(anchor="w", padx=16, pady=(4,4))
            trans_frame = tk.Frame(sent_inner, bg=C["bg3"], padx=12, pady=8)
            trans_frame.pack(fill="x", padx=12, pady=(4,10))
            lbl(trans_frame, "Tradução:", font=FONT_UIS,
                fg=C["ink3"], bg=C["bg3"]).pack(anchor="w")
            lbl(trans_frame, q.get("translation",""), font=FONT_UI,
                fg=C["ink2"], bg=C["bg3"],
                wraplength=440, justify="left").pack(anchor="w", pady=(2,0))
        else:
            # vocab
            sent_outer = tk.Frame(self.card, bg=C["blue"], pady=0)
            sent_outer.pack(fill="x", pady=(8,6))
            sent_inner = tk.Frame(sent_outer, bg=C["bg2"])
            sent_inner.pack(fill="x", padx=3)
            q_label_text = q.get("q_label", "Answer the question about the underlined word.")
            lbl(sent_inner, q_label_text, font=FONT_UIS,
                fg=C["ink3"], bg=C["bg2"]).pack(anchor="w", padx=14, pady=(10,4))
            lbl(sent_inner, q["q"], font=FONT_JP, fg=C["ink"], bg=C["bg2"],
                wraplength=480, justify="left").pack(anchor="w", padx=16, pady=(0,4))
            trans_frame = tk.Frame(sent_inner, bg=C["bg3"], padx=12, pady=6)
            trans_frame.pack(fill="x", padx=12, pady=(4,10))
            lbl(trans_frame, q.get("translation",""), font=FONT_UI,
                fg=C["ink2"], bg=C["bg3"],
                wraplength=440, justify="left").pack(anchor="w")

        self._exam_answered = False
        self._exam_correct  = q["a"]
        self._exam_explanation = q.get("explanation","")
        opts_frame = tk.Frame(self.card, bg=C["bg"])
        opts_frame.pack(fill="x", pady=(is_grammar and 2 or 0, 0))
        opts_frame.columnconfigure(0, weight=1)
        opts_frame.columnconfigure(1, weight=1)
        self._exam_opt_btns = []
        labels = ["A", "B", "C", "D"]
        for i, opt in enumerate(q["options"]):
            ri, ci = divmod(i, 2)
            display = f"{labels[i]}  {opt}"
            b = FlatButton(opts_frame, display, font=FONT_JP, padx=10, pady=10,
                           command=lambda o=opt: self._exam_pick(o),
                           wraplength=220)
            b.grid(row=ri, column=ci, sticky="nsew", padx=5, pady=5)
            b.set_colors(C["bg2"], C["ink"], C["bg3"])
            self._exam_opt_btns.append((opt, b))

        # placeholder
        self.explain_frame = tk.Frame(self.card, bg=C["bg"])
        self.explain_frame.pack(fill="x", pady=(8,0))

        t = self._exam_timer_var.get()
        if t > 0:
            self._exam_time_left = t
            self._exam_tick()

    def _exam_pick(self, chosen):
        if self._exam_answered:
            return
        self._exam_answered = True
        self._cancel_timer()
        correct = (chosen == self._exam_correct)
        if correct:
            self.q_correct += 1
        else:
            self.q_wrong += 1
        self.q_answered.append((self.questions[self.q_idx], correct, chosen))

        for opt, b in self._exam_opt_btns:
            if opt == self._exam_correct:
                b.set_colors(C["green"], C["white"], C["green"])
            elif opt == chosen and not correct:
                b.set_colors(C["red"], C["white"], C["red"])
            else:
                b.set_colors(C["bg3"], C["ink3"], C["bg3"])

        # show explanation if available
        explanation = getattr(self, "_exam_explanation", "")
        if explanation:
            icon = "✓" if correct else "✗"
            icon_color = C["green"] if correct else C["red"]
            try:
                for w in self.explain_frame.winfo_children():
                    w.destroy()
                self.explain_frame.config(bg=C["bg3"])
                inner = tk.Frame(self.explain_frame, bg=C["bg3"])
                inner.pack(fill="x", padx=12, pady=8)
                lbl(inner, f"{icon}  Explicação:", font=FONT_UIB,
                    fg=icon_color, bg=C["bg3"]).pack(anchor="w")
                lbl(inner, explanation, font=FONT_UIS, fg=C["ink2"],
                    bg=C["bg3"], wraplength=480, justify="left").pack(anchor="w", pady=(4,0))
            except Exception:
                pass

        self.q_idx += 1
        next_b = FlatButton(self.card,
                             "Próxima  →" if self.q_idx < len(self.questions) else "Ver Resultado  →",
                             command=self._show_question, padx=14, pady=8)
        next_b.set_colors(C["blue"], C["white"], C["blue2"])
        next_b.pack(pady=(10,0))
        next_b.focus()
        self.bind("<Return>", lambda e: self._show_question())

    def _exam_tick(self):
        if self._exam_time_left <= 0:
            self.exam_timer_lbl.config(text="✗ Time!", fg=C["red"])
            self._exam_pick("__timeout__")
            return
        col = C["red"] if self._exam_time_left <= 5 else C["gold"]
        self.exam_timer_lbl.config(text=f"⏱ {self._exam_time_left}s", fg=col)
        self._exam_time_left -= 1
        self._timer_job = self.after(1000, self._exam_tick)

    def _cancel_timer(self):
        if self._timer_job:
            self.after_cancel(self._timer_job)
            self._timer_job = None

    def _show_exam_results(self):
        self._cancel_timer()
        self._clear()
        c = self.content
        c.config(bg=C["bg"])

        total = self.q_correct + self.q_wrong
        pct   = int(self.q_correct / total * 100) if total else 0
        if   pct >= 90: grade, gc = "🏆  Excellent!",       "gold"
        elif pct >= 70: grade, gc = "👍  Good result!",      "green"
        elif pct >= 50: grade, gc = "📖  Needs more study.", "blue"
        else:           grade, gc = "📝  More practice!",    "red"

        lbl(c, grade, font=FONT_H1, fg=C[gc], bg=C["bg"]).pack(pady=(28,6))
        lbl(c, f"{self.q_correct} / {total}  ({pct}%)",
            font=FONT_H2, fg=C["green"] if pct >= 70 else C["red"],
            bg=C["bg"]).pack()
        lbl(c, f"✓ {self.q_correct} correct   ✗ {self.q_wrong} wrong",
            font=FONT_UI, fg=C["ink2"], bg=C["bg"]).pack(pady=(4,10))

        # Section breakdown
        section_scores = {}
        for q, ok, _ in self.q_answered:
            sec = q["section"]
            section_scores.setdefault(sec, [0,0])
            if ok:
                section_scores[sec][0] += 1
            section_scores[sec][1] += 1

        if section_scores:
            sep(c, bg=C["bg3"]).pack(fill="x", padx=28, pady=8)
            lbl(c, "Section Breakdown", font=FONT_UIB, fg=C["ink2"],
                bg=C["bg"]).pack(anchor="w", padx=28)
            for sec, (cor, tot) in sorted(section_scores.items()):
                sp = int(cor/tot*100) if tot else 0
                row = tk.Frame(c, bg=C["bg"])
                row.pack(fill="x", padx=28, pady=2)
                lbl(row, sec, font=FONT_UIS, fg=C["ink"], bg=C["bg"]).pack(side="left")
                lbl(row, f"{cor}/{tot}  ({sp}%)",
                    font=FONT_UIS, fg=C["green"] if sp >= 70 else C["red"],
                    bg=C["bg"]).pack(side="right")

        sep(c, bg=C["bg3"]).pack(fill="x", padx=28, pady=12)
        btn_row = tk.Frame(c, bg=C["bg"])
        btn_row.pack()
        retry = FlatButton(btn_row, "Retry", command=self._show_setup,
                            padx=14, pady=8)
        retry.set_colors(C["red"], C["white"], C["red2"])
        retry.pack(side="left", padx=6)
        close_b = FlatButton(btn_row, "Close", command=self.destroy,
                              font=FONT_UI, padx=14, pady=8)
        close_b.set_colors(C["bg3"], C["ink2"], C["bg2"])
        close_b.pack(side="left", padx=6)

    def update_theme(self):
        self.configure(bg=C["bg"])
        self.hdr.config(bg=C["sidebar"])
        self.hdr_lbl.config(bg=C["sidebar"], fg=C["white"])
        self.score_lbl.config(bg=C["sidebar"])
        self.content.config(bg=C["bg"])


# category manager
class CategoryManagerDialog(tk.Toplevel):
    """Rename, merge, or delete categories across the whole dictionary."""

    def __init__(self, parent, data):
        super().__init__(parent)
        self.title("Manage Categories")
        self.resizable(False, False)
        self.data = data
        self.after(50, lambda: _safe_grab(self))
        self._build_ui()
        self._update_theme()
        self._center(parent)

    def _build_ui(self):
        self.hdr = tk.Frame(self, pady=14)
        self.hdr.pack(fill="x")
        self.hdr_lbl = lbl(self.hdr, "⚙  Manage Categories", font=FONT_H2, fg=C["white"])
        self.hdr_lbl.pack(padx=20, anchor="w")

        self.body = tk.Frame(self, padx=20, pady=12)
        self.body.pack(fill="both", expand=True)

        self.info_lbl = lbl(self.body, "Select a category to rename, merge, or delete it.",
                             font=FONT_UIS, fg=C["ink2"])
        self.info_lbl.pack(anchor="w", pady=(0, 8))

        # listbox of categories
        lb_frame = tk.Frame(self.body)
        lb_frame.pack(fill="both", expand=True)
        self.lb = tk.Listbox(lb_frame, font=FONT_UI, relief="flat", bd=0,
                              highlightthickness=1, width=32, height=12,
                              selectmode="single", activestyle="none")
        lb_sb = ttk.Scrollbar(lb_frame, orient="vertical", command=self.lb.yview)
        self.lb.config(yscrollcommand=lb_sb.set)
        self.lb.pack(side="left", fill="both", expand=True)
        lb_sb.pack(side="right", fill="y")
        self.lb.bind("<<ListboxSelect>>", self._on_select)
        self._populate_lb()

        sep(self.body).pack(fill="x", pady=10)

        # action buttons
        btn_row = tk.Frame(self.body)
        btn_row.pack(fill="x")
        self.rename_btn = FlatButton(btn_row, "✎ Rename…", command=self._rename,
                    font=FONT_UIS, padx=10, pady=5)
        self.rename_btn.pack(side="left", padx=(0,6))
        self.merge_btn = FlatButton(btn_row, "⇒ Merge into…", command=self._merge,
                    font=FONT_UIS, padx=10, pady=5)
        self.merge_btn.pack(side="left", padx=(0,6))
        self.del_btn = FlatButton(btn_row, "🗑 Delete", command=self._delete,
                    font=FONT_UIS, padx=10, pady=5)
        self.del_btn.pack(side="left")

        sep(self.body).pack(fill="x", pady=10)

        # add new category
        new_row = tk.Frame(self.body)
        new_row.pack(fill="x")
        self.new_var = tk.StringVar()
        self.new_entry = tk.Entry(new_row, textvariable=self.new_var, font=FONT_UI,
                                   relief="flat", bd=0, highlightthickness=1, width=20)
        self.new_entry.pack(side="left", ipady=5, padx=(0,8))
        self.new_entry.bind("<Return>", lambda e: self._add_cat())
        add_btn = FlatButton(new_row, "+ Add Category", command=self._add_cat,
                    font=FONT_UIS, padx=10, pady=5)
        add_btn.pack(side="left")
        self.new_add_btn = add_btn

        sep(self.body).pack(fill="x", pady=10)
        close_btn = FlatButton(self.body, "Done", command=self.destroy,
                    font=FONT_UI, padx=14, pady=7)
        close_btn.pack(anchor="e")
        self.close_btn = close_btn

    def _cats(self):
        cats = sorted({w.get("category","") or "Uncategorized"
                       for w in self.data.get("words", [])})
        extras = [c for c in self.data.get("categories", []) if c not in cats]
        return cats + sorted(extras)

    def _populate_lb(self, select=None):
        self.lb.delete(0, "end")
        counts = {}
        for w in self.data.get("words", []):
            c = w.get("category","") or "Uncategorized"
            counts[c] = counts.get(c, 0) + 1
        self._cat_list = self._cats()
        for c in self._cat_list:
            n = counts.get(c, 0)
            self.lb.insert("end", f"  {c}  ({n} word{'s' if n!=1 else ''})")
        if select and select in self._cat_list:
            i = self._cat_list.index(select)
            self.lb.selection_set(i)
            self.lb.see(i)

    def _selected_cat(self):
        sel = self.lb.curselection()
        if not sel:
            return None
        return self._cat_list[sel[0]]

    def _on_select(self, *_):
        pass  # could enable/disable buttons here

    def _rename(self):
        old = self._selected_cat()
        if not old:
            messagebox.showwarning("Nothing selected", "Select a category first.", parent=self)
            return
        new = simpledialog.askstring("Rename", f"New name for '{old}':", initialvalue=old, parent=self)
        if not new or not new.strip() or new.strip() == old:
            return
        new = new.strip()
        if new in self._cats():
            messagebox.showwarning("Exists", f"'{new}' already exists. Use Merge instead.", parent=self)
            return
        for w in self.data["words"]:
            if (w.get("category","") or "Uncategorized") == old:
                w["category"] = new
        cats = self.data.get("categories", [])
        if old in cats:
            cats[cats.index(old)] = new
        if new not in cats:
            cats.append(new)
        self._populate_lb(select=new)

    def _merge(self):
        old = self._selected_cat()
        if not old:
            messagebox.showwarning("Nothing selected", "Select a category to merge.", parent=self)
            return
        targets = [c for c in self._cats() if c != old]
        if not targets:
            messagebox.showinfo("No targets", "No other categories to merge into.", parent=self)
            return
        dlg = _PickDialog(self, "Merge Into", f"Merge  '{old}'  into:", targets)
        self.wait_window(dlg)
        if not dlg.result:
            return
        target = dlg.result
        for w in self.data["words"]:
            if (w.get("category","") or "Uncategorized") == old:
                w["category"] = target
        cats = self.data.get("categories", [])
        if old in cats:
            cats.remove(old)
        self._populate_lb(select=target)

    def _delete(self):
        cat = self._selected_cat()
        if not cat:
            messagebox.showwarning("Nothing selected", "Select a category to delete.", parent=self)
            return
        count = sum(1 for w in self.data["words"] if (w.get("category","") or "Uncategorized") == cat)
        if count > 0:
            move = messagebox.askyesno(
                "Move words?",
                f"'{cat}' has {count} word(s).\nMove them to 'Uncategorized' before deleting?",
                parent=self)
            if not move:
                return
            for w in self.data["words"]:
                if (w.get("category","") or "Uncategorized") == cat:
                    w["category"] = "Uncategorized"
        cats = self.data.get("categories", [])
        if cat in cats:
            cats.remove(cat)
        self._populate_lb()

    def _add_cat(self):
        name = self.new_var.get().strip()
        if not name:
            return
        cats = self.data.setdefault("categories", [])
        if name not in cats:
            cats.append(name)
        self.new_var.set("")
        self._populate_lb(select=name)

    def _update_theme(self):
        self.configure(bg=C["bg"])
        self.hdr.config(bg=C["sidebar"])
        self.hdr_lbl.config(bg=C["sidebar"], fg=C["white"])
        self.body.config(bg=C["bg"])
        self.info_lbl.config(bg=C["bg"], fg=C["ink2"])
        self.lb.config(bg=C["entry_bg"], fg=C["entry_fg"],
                        selectbackground=C["sel"], selectforeground=C["ink"],
                        highlightbackground=C["bg3"])
        self.rename_btn.set_colors(C["bg2"], C["ink2"], C["bg3"])
        self.merge_btn.set_colors(C["blue"], C["white"], C["blue2"])
        self.del_btn.set_colors(C["red"], C["white"], C["red2"])
        self.new_entry.config(bg=C["entry_bg"], fg=C["entry_fg"],
                               insertbackground=C["entry_fg"],
                               highlightbackground=C["bg3"], highlightcolor=C["red"])
        self.new_add_btn.set_colors(C["bg2"], C["ink2"], C["bg3"])
        self.close_btn.set_colors(C["red"], C["white"], C["red2"])

    def _center(self, parent):
        self.update_idletasks()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        px, py = parent.winfo_x(), parent.winfo_y()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        self.geometry(f"{w}x{h}+{px+pw//2-w//2}+{py+ph//2-h//2}")


class _PickDialog(tk.Toplevel):
    """Simple single-pick listbox dialog."""
    def __init__(self, parent, title, prompt, options):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.result = None
        self.after(50, lambda: _safe_grab(self))
        self.configure(bg=C["bg"])

        lbl(self, prompt, font=FONT_UI, fg=C["ink"], bg=C["bg"]).pack(padx=20, pady=(16,8))
        self.lb = tk.Listbox(self, font=FONT_UI, relief="flat", bd=0, highlightthickness=1,
                              width=28, height=min(10, len(options)), activestyle="none",
                              bg=C["entry_bg"], fg=C["entry_fg"],
                              selectbackground=C["sel"], selectforeground=C["ink"],
                              highlightbackground=C["bg3"])
        self.lb.pack(padx=20, pady=4)
        for o in options:
            self.lb.insert("end", f"  {o}")
        self.lb.bind("<Double-1>", lambda e: self._pick())
        self._options = options

        btn_row = tk.Frame(self, bg=C["bg"], pady=12)
        btn_row.pack()
        ok = FlatButton(btn_row, "OK", command=self._pick, font=FONT_UI, padx=12, pady=6)
        ok.pack(side="left", padx=6)
        ok.set_colors(C["red"], C["white"], C["red2"])
        ca = FlatButton(btn_row, "Cancel", command=self.destroy, font=FONT_UI, padx=12, pady=6)
        ca.pack(side="left", padx=6)
        ca.set_colors(C["bg3"], C["ink2"], C["bg2"])

        self.update_idletasks()
        px, py = parent.winfo_x(), parent.winfo_y()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        self.geometry(f"{w}x{h}+{px+pw//2-w//2}+{py+ph//2-h//2}")

    def _pick(self):
        sel = self.lb.curselection()
        if sel:
            self.result = self._options[sel[0]]
            self.destroy()

# stats
class StatsDialog(tk.Toplevel):
    def __init__(self, parent, data):
        super().__init__(parent)
        self.title(f"Stats — {data['name']}")
        self.resizable(False, False)
        self.after(50, lambda: _safe_grab(self))

        self.build_ui(data)
        self.update_theme()
        self._center(parent)

    def build_ui(self, data):
        words = data.get("words", [])
        cats  = {}
        favs  = sum(1 for w in words if w.get("favorite"))
        for w in words:
            c = w.get("category") or "Uncategorized"
            cats[c] = cats.get(c, 0) + 1

        self.hdr = tk.Frame(self, pady=14)
        self.hdr.pack(fill="x")
        self.hdr_lbl1 = lbl(self.hdr, f"📊  {data['name']}",  font=FONT_H2, fg=C["white"])
        self.hdr_lbl1.pack(padx=20, anchor="w")
        self.hdr_lbl2 = lbl(self.hdr, f"Created: {data.get('created','')}",font=FONT_UIS, fg=C["ink3"])
        self.hdr_lbl2.pack(padx=20, anchor="w")

        self.body = tk.Frame(self, padx=24, pady=16)
        self.body.pack(fill="both", expand=True)

        self.stat_rows = []
        def stat_row(icon, label, value, vc_key=None):
            row = tk.Frame(self.body, pady=8)
            row.pack(fill="x", pady=3)
            l1 = lbl(row, f"  {icon}  {label}", fg=C["ink2"])
            l1.pack(side="left", padx=8)
            l2 = lbl(row, str(value), font=FONT_UIB, fg=C[vc_key] if vc_key else C["ink"])
            l2.pack(side="right", padx=12)
            self.stat_rows.append((row, l1, l2, vc_key))

        stat_row("📝", "Total words",  len(words), "blue")
        stat_row("⭐", "Favourites",  favs,        "gold")
        stat_row("🗂", "Categories",  len(cats),   "red")
        avg = f"{sum(len(w.get('word','')) for w in words)/len(words):.1f} chars" if words else "—"
        stat_row("✏️", "Avg word length", avg)

        self.cat_bars = []
        if cats:
            self.sep1 = sep(self.body)
            self.sep1.pack(fill="x", pady=12)
            self.cat_hdr = lbl(self.body, "Words per Category", font=FONT_UIB, fg=C["ink2"])
            self.cat_hdr.pack(anchor="w", pady=(0,6))
            max_c = max(cats.values())
            for cat, count in sorted(cats.items(), key=lambda x: -x[1]):
                row = tk.Frame(self.body)
                row.pack(fill="x", pady=2)
                l1 = lbl(row, cat, font=FONT_UIS, fg=C["ink"])
                l1.pack(side="left")
                bar_outer = tk.Frame(row, height=8, width=160)
                bar_outer.pack(side="right", padx=(8,0))
                bar_outer.pack_propagate(False)
                bw = max(4, int(count / max_c * 156))
                bar_inner = tk.Frame(bar_outer, width=bw, height=8)
                bar_inner.place(x=0, y=0)
                l2 = lbl(row, str(count), font=FONT_UIS, fg=C["ink2"])
                l2.pack(side="right", padx=(0,8))
                self.cat_bars.append((row, l1, l2, bar_outer, bar_inner))

        self.sep2 = sep(self.body)
        self.sep2.pack(fill="x", pady=12)
        self.close_btn = FlatButton(self.body, "Close", command=self.destroy,
                   font=FONT_UI, padx=12, pady=6)
        self.close_btn.pack(anchor="e")

    def update_theme(self):
        self.configure(bg=C["bg"])
        self.hdr.config(bg=C["sidebar"])
        self.hdr_lbl1.config(bg=C["sidebar"], fg=C["white"])
        self.hdr_lbl2.config(bg=C["sidebar"], fg=C["ink2"])
        self.body.config(bg=C["bg"])

        for row, l1, l2, vc_key in self.stat_rows:
            row.config(bg=C["bg2"])
            l1.config(bg=C["bg2"], fg=C["ink2"])
            l2.config(bg=C["bg2"], fg=C[vc_key] if vc_key else C["ink"])

        if hasattr(self, "sep1"):
            self.sep1.config(bg=C["bg3"])
            self.cat_hdr.config(bg=C["bg"], fg=C["ink2"])
            for row, l1, l2, bar_outer, bar_inner in self.cat_bars:
                row.config(bg=C["bg"])
                l1.config(bg=C["bg"], fg=C["ink"])
                l2.config(bg=C["bg"], fg=C["ink2"])
                bar_outer.config(bg=C["bg3"])
                bar_inner.config(bg=C["red"])
        
        self.sep2.config(bg=C["bg3"])
        self.close_btn.set_colors(bg=C["bg3"], fg=C["ink2"], hover_bg=C["bg2"])

    def _center(self, parent):
        self.update_idletasks()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        px, py = parent.winfo_x(), parent.winfo_y()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        self.geometry(f"{w}x{h}+{px+pw//2-w//2}+{py+ph//2-h//2}")


## main stuff wow
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("和語帳 — Wagochō")
        self.geometry("1120x700")
        self.minsize(800, 520)
        self.configure(bg=C["bg"])

        self.dark_mode = False

        self.current_dict = None
        self.all_words    = []
        self._sort_col    = "word"
        self._sort_rev    = False
        self._selected_cats = set()   # empty = All
        self._cat_chip_btns = {}      # cat -> FlatButton

        self._build_menu()
        self._build_ui()
        self._style_ttk()
        self._refresh_dict_list()

        # keyboard shortcuts
        self.bind_all("<Control-f>", lambda e: self.search_entry.focus_set())
        self.bind_all("<Escape>",    lambda e: self._clear_filters())

        if not list_dictionaries():
            self._create_dict("My Vocabulary")
        
        self._update_theme()

    def _build_menu(self):
        self.mb = tk.Menu(self, bg=C["bg2"], fg=C["ink"],
                     activebackground=C["sel"], activeforeground=C["ink"],
                     relief="flat", bd=0)
        self.sub_menus = []

        def cascade(label, items):
            m = tk.Menu(self.mb, tearoff=0, bg=C["bg2"], fg=C["ink"],
                        activebackground=C["sel"], activeforeground=C["ink"])
            self.sub_menus.append(m)
            for it in items:
                if it == "---": m.add_separator()
                else:           m.add_command(label=it[0], command=it[1])
            self.mb.add_cascade(label=label, menu=m)

        cascade("File", [
            ("New Dictionary…",  self._prompt_new_dict),
            "---",
            ("Export to CSV…",   self._export_csv),
            ("Import from CSV…", self._import_csv),
            "---",
            ("Quit",             self.quit),
        ])
        cascade("View", [
            ("Show Favourites Only", self._filter_favourites),
            ("Clear Filters",        self._clear_filters),
        ])
        cascade("Tools", [
            ("Start Quiz  練習",       self._open_quiz),
            ("JLPT Exam Mode  試験",   self._open_exam),
            ("Dictionary Stats",       self._show_stats),
            "---",
            ("Manage Categories…",     self._manage_categories),
            ("JLPT Data Manager…",     self._open_jlpt_manager),
            "---",
            ("Export Filtered View…",  self._export_filtered_csv),
        ])
        cascade("Help", [("About", self._about)])
        self.config(menu=self.mb)

    def _style_ttk(self):
        s = ttk.Style(self)
        try: s.theme_use("clam")
        except Exception: pass
        s.configure("Dict.Treeview",
                     background=C["entry_bg"], foreground=C["entry_fg"],
                     fieldbackground=C["entry_bg"], rowheight=36,
                     borderwidth=0, font=FONT_UI)
        s.configure("Dict.Treeview.Heading",
                     background=C["bg2"], foreground=C["ink2"],
                     relief="flat", font=FONT_UIB)
        s.map("Dict.Treeview",
              background=[("selected", C["sel"])],
              foreground=[("selected", C["ink"])])
        s.map("Dict.Treeview.Heading",
              background=[("active", C["bg3"])])
        s.configure("TCombobox", fieldbackground=C["entry_bg"], background=C["entry_bg"], foreground=C["entry_fg"])
        s.configure("TScrollbar", background=C["bg2"], troughcolor=C["bg"], bordercolor=C["bg3"], arrowcolor=C["ink2"])

    def _build_ui(self):
        self.sidebar = tk.Frame(self, bg=C["sidebar"], width=210)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        self.logo_frame = tk.Frame(self.sidebar, bg=C["sidebar"], pady=18)
        self.logo_frame.pack(fill="x")
        self.logo_lbl1 = lbl(self.logo_frame, "和語帳", font=("Segoe UI", 20, "bold"),
            fg=C["red"], bg=C["sidebar"])
        self.logo_lbl1.pack(padx=16, anchor="w")
        self.logo_lbl2 = lbl(self.logo_frame, "Wagochō", font=FONT_UIS,
            fg=C["ink2"], bg=C["sidebar"])
        self.logo_lbl2.pack(padx=16, anchor="w")

        self.sidebar_sep1 = tk.Frame(self.sidebar, bg=C["sidebar3"], height=1)
        self.sidebar_sep1.pack(fill="x", padx=12)

        self.dict_hdr_frame = tk.Frame(self.sidebar, bg=C["sidebar"], pady=8)
        self.dict_hdr_frame.pack(fill="x", padx=12, pady=(8,0))
        self.dict_hdr_lbl = lbl(self.dict_hdr_frame, "DICTIONARIES", font=("Segoe UI", 8, "bold"),
            fg=C["ink3"], bg=C["sidebar"])
        self.dict_hdr_lbl.pack(side="left")
        self.add_dict_btn = FlatButton(self.dict_hdr_frame, "+", command=self._prompt_new_dict,
                   font=FONT_UIB, padx=8, pady=2)
        self.add_dict_btn.pack(side="right")

        self.dict_lb_outer = tk.Frame(self.sidebar, bg=C["sidebar"])
        self.dict_lb_outer.pack(fill="both", expand=True, padx=6)
        self.dict_lb = tk.Listbox(
            self.dict_lb_outer, bg=C["sidebar"], fg="#CCCCEE",
            selectbackground=C["sidebar3"], selectforeground=C["white"],
            activestyle="none", relief="flat", bd=0,
            font=FONT_UI, highlightthickness=0)
        self.dict_lb.pack(fill="both", expand=True, padx=4)
        self.dict_lb.bind("<<ListboxSelect>>", self._on_dict_select)
        self.dict_lb.bind("<Button-3>",        self._dict_context_menu)

        self.sidebar_sep2 = tk.Frame(self.sidebar, bg=C["sidebar3"], height=1)
        self.sidebar_sep2.pack(fill="x", padx=12)
        self.bot_frame = tk.Frame(self.sidebar, bg=C["sidebar"], pady=10)
        self.bot_frame.pack(fill="x", padx=8)
        
        self.sidebar_btns = []
        btn_quiz = FlatButton(self.bot_frame, "練習  Quiz", command=self._open_quiz,
                   font=FONT_UIS, padx=10, pady=6)
        btn_quiz.pack(fill="x", pady=2)
        btn_exam = FlatButton(self.bot_frame, "試験  Exam", command=self._open_exam,
                   font=FONT_UIS, padx=10, pady=6)
        btn_exam.pack(fill="x", pady=2)
        btn_stats = FlatButton(self.bot_frame, "📊  Stats", command=self._show_stats,
                   font=FONT_UIS, padx=10, pady=6)
        btn_stats.pack(fill="x", pady=2)
        self.sidebar_btns.extend([btn_quiz, btn_exam, btn_stats])

        # main stuff
        self.main = tk.Frame(self, bg=C["bg"])
        self.main.pack(side="right", fill="both", expand=True)

        self.topbar = tk.Frame(self.main,
                          highlightthickness=1)
        self.topbar.pack(fill="x")
        self.dict_title = lbl(self.topbar, "← Select a dictionary",
                               font=FONT_H2)
        self.dict_title.pack(side="left", padx=18, pady=12)

        self.add_word_btn = FlatButton(self.topbar, "+  Add Word", command=self._add_word)
        self.add_word_btn.pack(side="right", padx=12, pady=8)
        self.theme_btn = FlatButton(self.topbar, "🌙", command=self._toggle_theme,
                                 padx=10)
        self.theme_btn.pack(side="right", pady=8)

        self.toolbar = tk.Frame(self.main,
                           highlightthickness=1)
        self.toolbar.pack(fill="x")
        self.toolbar_inner = tk.Frame(self.toolbar)
        self.toolbar_inner.pack(fill="x", padx=12, pady=8)

        self.srch_frame = tk.Frame(self.toolbar_inner, 
                        highlightthickness=1)
        self.srch_frame.pack(side="left", ipady=4)
        self.srch_lbl = lbl(self.srch_frame, " 🔍 ", font=FONT_UIS)
        self.srch_lbl.pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._apply_filter())
        self.search_entry = tk.Entry(self.srch_frame, textvariable=self.search_var,
                 font=FONT_UI,
                 relief="flat", bd=0, width=22)
        self.search_entry.pack(side="left", ipady=1)
        # placeholder
        self._search_placeholder("Type to search…")
        # clear button
        self.srch_clear = tk.Label(self.srch_frame, text="✕", cursor="hand2",
                                    font=FONT_UIS, padx=4)
        self.srch_clear.pack(side="left")
        self.srch_clear.bind("<Button-1>", lambda e: (self.search_var.set(""), self._show_placeholder()))

        self.fav_var = tk.BooleanVar()
        self.fav_cb = tk.Checkbutton(self.toolbar_inner, text="⭐ Favourites",
                       variable=self.fav_var, command=self._apply_filter,
                       font=FONT_UIS)
        self.fav_cb.pack(side="left", padx=(14,0))

        self.manage_cat_btn = FlatButton(self.toolbar_inner, "⚙ Categories",
                   command=self._manage_categories, font=FONT_UIS, padx=10, pady=4)
        self.manage_cat_btn.pack(side="left", padx=(10,0))

        self.count_lbl = lbl(self.toolbar_inner, "", font=FONT_UIS)
        self.count_lbl.pack(side="right")

        # categories
        self.cat_bar = tk.Frame(self.main, highlightthickness=1)
        self.cat_bar.pack(fill="x")
        self.cat_chips_inner = tk.Frame(self.cat_bar)
        self.cat_chips_inner.pack(fill="x", padx=10, pady=5)


        self.tbl_frame = tk.Frame(self.main)
        self.tbl_frame.pack(fill="both", expand=True)

        cols = ("fav","word","reading","romaji","category","comment","created")
        self.tree = ttk.Treeview(self.tbl_frame, columns=cols, show="headings",
                                  style="Dict.Treeview", selectmode="extended")

        col_cfg = {
            "fav":      ("⭐",    44,  False),
            "word":     ("Word", 150,  True),
            "reading":  ("Reading",140,True),
            "romaji":   ("Romaji",110, True),
            "category": ("Category",110,True),
            "comment":  ("Notes", 240, True),
            "created":  ("Added", 100, False),
        }
        for col,(label,width,stretch) in col_cfg.items():
            self.tree.heading(col, text=label, command=lambda c=col: self._sort_by(c))
            self.tree.column(col, width=width, anchor="w", stretch=stretch, minwidth=28)
        self.tree.column("fav", anchor="center")

        vsb = ttk.Scrollbar(self.tbl_frame, orient="vertical", command=self.tree.yview, style="TScrollbar")
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)

        self.tree.tag_configure("fav_row", foreground=C["gold"])
        self.tree.tag_configure("alt_row", background=C["alt_row"])

        self.tree.bind("<Double-1>", self._on_row_double)
        self.tree.bind("<Return>",   self._on_row_double)
        self.tree.bind("<Button-3>", self._tree_context_menu)
        self.tree.bind("<Delete>",   lambda _: self._delete_selected())
        self.tree.bind("<Control-a>", self._select_all)

        self.status_var = tk.StringVar(value="Welcome to 和語帳")
        self.status_bar = tk.Label(self.main, textvariable=self.status_var,
                 font=FONT_UIS,
                 anchor="w", padx=14, pady=4)
        self.status_bar.pack(fill="x", side="bottom")

    def _search_placeholder(self, text):
        """Attach placeholder hint to search entry."""
        self._ph_text = text
        self._ph_active = False
        self.search_entry.bind("<FocusIn>",  self._hide_placeholder)
        self.search_entry.bind("<FocusOut>", self._show_placeholder)
        self._show_placeholder()

    def _show_placeholder(self, *_):
        if not self.search_var.get():
            self._ph_active = True
            self.search_entry.config(fg=C["ink3"])
            self.search_entry.delete(0, "end")
            self.search_entry.insert(0, self._ph_text)

    def _hide_placeholder(self, *_):
        if self._ph_active:
            self._ph_active = False
            self.search_entry.config(fg=C["entry_fg"])
            self.search_entry.delete(0, "end")

    def _get_search_q(self):
        if self._ph_active:
            return ""
        return self.search_var.get().lower()

    def _toggle_theme(self):
        self.dark_mode = not self.dark_mode
        C.clear()
        if self.dark_mode:
            C.update(C_DARK)
            self.theme_btn.config(text="☀️")
        else:
            C.update(C_LIGHT)
            self.theme_btn.config(text="🌙")
        self._update_theme()

    def _update_theme(self):
        self.configure(bg=C["bg"])
        self.main.config(bg=C["bg"])
        self.status_bar.config(bg=C["bg3"], fg=C["ink2"])
        self.topbar.config(bg=C["bg"], highlightbackground=C["bg3"])
        self.dict_title.config(fg=C["ink"], bg=C["bg"])
        self.toolbar.config(bg=C["bg2"], highlightbackground=C["bg3"])
        self.toolbar_inner.config(bg=C["bg2"])
        self.srch_frame.config(bg=C["entry_bg"], highlightbackground=C["bg3"])
        self.srch_lbl.config(fg=C["ink3"], bg=C["entry_bg"])
        self.search_entry.config(bg=C["entry_bg"], fg=C["entry_fg"], insertbackground=C["entry_fg"])
        self.fav_cb.config(bg=C["bg2"], fg=C["ink2"], selectcolor=C["bg3"], activebackground=C["bg2"])
        self.count_lbl.config(fg=C["ink3"], bg=C["bg2"])
        self.tbl_frame.config(bg=C["bg"])
        self._style_ttk()
        self.tree.tag_configure("fav_row", foreground=C["gold"])
        self.tree.tag_configure("alt_row", background=C["alt_row"])
        self.sidebar.config(bg=C["sidebar"])
        self.logo_frame.config(bg=C["sidebar"])
        self.logo_lbl1.config(fg=C["red"], bg=C["sidebar"])
        self.logo_lbl2.config(fg=C["ink2"], bg=C["sidebar"])
        self.sidebar_sep1.config(bg=C["sidebar3"])
        self.dict_hdr_frame.config(bg=C["sidebar"])
        self.dict_hdr_lbl.config(fg=C["ink2"], bg=C["sidebar"])
        self.dict_lb_outer.config(bg=C["sidebar"])
        self.dict_lb.config(bg=C["sidebar"], fg="#CCCCEE", selectbackground=C["sidebar3"], selectforeground=C["white"])
        self.sidebar_sep2.config(bg=C["sidebar3"])
        self.bot_frame.config(bg=C["sidebar"])

        self.add_dict_btn.set_colors(C["red"], C["white"], C["red2"])
        for btn in self.sidebar_btns:
            txt = btn.cget("text")
            is_primary = "Quiz" in txt or "Exam" in txt or "試験" in txt or "練習" in txt
            btn.set_colors(C["sidebar2"], C["white"] if is_primary else "#AAAACC", C["sidebar3"])
        
        self.manage_cat_btn.set_colors(C["bg2"], C["ink2"], C["bg3"])
        self.srch_clear.config(fg=C["ink3"], bg=C["entry_bg"])
        self.cat_bar.config(bg=C["bg2"], highlightbackground=C["bg3"])
        self.cat_chips_inner.config(bg=C["bg2"])
        self._refresh_cat_chips()

        self.add_word_btn.set_colors(C["red"], C["white"], C["red2"])
        self.theme_btn.set_colors(C["bg2"], C["ink2"], C["bg3"])
        
        self.mb.config(bg=C["bg2"], fg=C["ink"], activebackground=C["sel"], activeforeground=C["ink"])
        for menu in self.sub_menus:
            menu.config(bg=C["bg2"], fg=C["ink"], activebackground=C["sel"], activeforeground=C["ink"])
        self._apply_filter()

    # dict manage
    def _refresh_dict_list(self, select=None):
        self.dict_lb.delete(0, "end")
        dicts = list_dictionaries()
        for name in dicts:
            self.dict_lb.insert("end", f"  {name}")
        if select and select in dicts:
            i = dicts.index(select)
            self.dict_lb.selection_set(i)
            self._load_dict(select)
        elif dicts:
            self.dict_lb.selection_set(0)
            self._load_dict(dicts[0])

    def _on_dict_select(self, e):
        sel = self.dict_lb.curselection()
        if sel:
            self._load_dict(self.dict_lb.get(sel[0]).strip())

    def _load_dict(self, name):
        self.current_dict = load_dict(name)
        self.dict_title.config(text=f"📖  {name}")
        self._refresh_cat_menu()
        self._update_theme()
        n = len(self.current_dict["words"])
        self.status_var.set(f"Loaded '{name}' — {n} word{'s' if n!=1 else ''}")

    def _prompt_new_dict(self):
        name = simpledialog.askstring("New Dictionary", "Name:", parent=self)
        if name and name.strip():
            name = name.strip()
            if name in list_dictionaries():
                messagebox.showwarning("Exists", f"'{name}' already exists.", parent=self)
                return
            self._create_dict(name)

    def _create_dict(self, name):
        d = load_dict(name)
        save_dict(d)
        self._refresh_dict_list(select=name)
        self.status_var.set(f"Created '{name}'")

    def _rename_dict(self):
        if not self.current_dict:
            return
        old = self.current_dict["name"]
        new = simpledialog.askstring("Rename", "New name:", initialvalue=old, parent=self)
        if new and new.strip() and new.strip() != old:
            new = new.strip()
            if new in list_dictionaries():
                messagebox.showwarning("Exists", f"'{new}' already exists.", parent=self)
                return
            self.current_dict["name"] = new
            save_dict(self.current_dict)
            delete_dict_file(old)
            self._refresh_dict_list(select=new)
            self.status_var.set(f"Renamed to '{new}'")

    def _delete_dict(self):
        if not self.current_dict:
            return
        name = self.current_dict["name"]
        if not messagebox.askyesno("Delete", f"Delete '{name}' and all its words?", parent=self):
            return
        delete_dict_file(name)
        self.current_dict = None
        self.all_words = []
        self.tree.delete(*self.tree.get_children())
        self.dict_title.config(text="← Select a dictionary")
        self._refresh_dict_list()
        self.status_var.set(f"Deleted '{name}'")

    def _dict_context_menu(self, e):
        i = self.dict_lb.nearest(e.y)
        if i < 0:
            return
        self.dict_lb.selection_clear(0, "end")
        self.dict_lb.selection_set(i)
        self._load_dict(self.dict_lb.get(i).strip())
        m = tk.Menu(self, tearoff=0, bg=C["bg2"], fg=C["ink"],
                    activebackground=C["sel"], activeforeground=C["ink"])
        m.add_command(label="Rename…", command=self._rename_dict)
        m.add_command(label="Delete",  command=self._delete_dict)
        m.tk_popup(e.x_root, e.y_root)

    # managing words
    def _add_word(self):
        if not self.current_dict:
            messagebox.showinfo("No dictionary", "Select or create a dictionary first.")
            return
        dlg = WordDialog(self, self.current_dict.get("categories", []))
        self.wait_window(dlg)
        if dlg.result:
            w = dlg.result
            self.current_dict["words"].append(w)
            self._merge_cat(w["category"])
            save_dict(self.current_dict)
            self._refresh_cat_menu()
            self._apply_filter()
            self.status_var.set(f"Added: {w['word']}")

    def _edit_selected(self):
        item = self.tree.focus()
        if not item:
            return
        idx = list(self.tree.get_children()).index(item)
        if idx >= len(self.all_words):
            return
        word = self.all_words[idx]
        dlg = WordDialog(self, self.current_dict.get("categories", []), word_data=word)
        self.wait_window(dlg)
        if dlg.result:
            nw = dlg.result
            nw["id"]      = word["id"]
            nw["created"] = word["created"]
            for i, w in enumerate(self.current_dict["words"]):
                if w["id"] == word["id"]:
                    self.current_dict["words"][i] = nw
                    break
            self._merge_cat(nw["category"])
            save_dict(self.current_dict)
            self._refresh_cat_menu()
            self._apply_filter()
            self.status_var.set(f"Updated: {nw['word']}")

    def _delete_selected(self):
        items = self.tree.selection()
        if not items:
            return
        
        all_children = self.tree.get_children()
        ids_to_delete = []
        words_to_delete = []
        
        for item in items:
            idx = list(all_children).index(item)
            if idx < len(self.all_words):
                w = self.all_words[idx]
                ids_to_delete.append(w["id"])
                words_to_delete.append(w["word"])
        
        if not ids_to_delete:
            return
            
        if len(ids_to_delete) == 1:
            msg = f"Delete '{words_to_delete[0]}'?"
        else:
            msg = f"Delete {len(ids_to_delete)} selected words?"
            
        if not messagebox.askyesno("Delete", msg, parent=self):
            return
            
        id_set = set(ids_to_delete)
        self.current_dict["words"] = [
            w for w in self.current_dict["words"] if w["id"] not in id_set
        ]
        save_dict(self.current_dict)
        self._apply_filter()
        self.status_var.set(f"Deleted {len(ids_to_delete)} items")

    def _select_all(self, event=None):
        self.tree.selection_set(self.tree.get_children())
        return "break"

    def _toggle_fav(self):
        items = self.tree.selection()
        if not items:
            return
        
        all_children = self.tree.get_children()
        ids_to_toggle = []
        for item in items:
            idx = list(all_children).index(item)
            if idx < len(self.all_words):
                ids_to_toggle.append(self.all_words[idx]["id"])
        
        if not ids_to_toggle:
            return
            
        id_set = set(ids_to_toggle)
        for w in self.current_dict["words"]:
            if w["id"] in id_set:
                w["favorite"] = not w.get("favorite", False)
        
        save_dict(self.current_dict)
        self._apply_filter()

    def _merge_cat(self, cat):
        if cat and cat not in self.current_dict.get("categories", []):
            self.current_dict.setdefault("categories", []).append(cat)

    def _on_row_double(self, e):
        self._edit_selected()

    def _tree_context_menu(self, e):
        item = self.tree.identify_row(e.y)
        if not item:
            return
            
        selection = self.tree.selection()
        if item not in selection:
            self.tree.selection_set(item)
            self.tree.focus(item)
            selection = (item,)
            
        m = tk.Menu(self, tearoff=0, bg=C["bg2"], fg=C["ink"],
                    activebackground=C["sel"], activeforeground=C["ink"])
        
        if len(selection) == 1:
            m.add_command(label="Edit", command=self._edit_selected)
        
        m.add_command(label="Toggle Favourite ⭐", command=self._toggle_fav)
        m.add_separator()
        m.add_command(label="Delete", command=self._delete_selected)
        m.tk_popup(e.x_root, e.y_root)

    # filter / chips
    def _refresh_cat_menu(self):
        """Keep for compatibility; delegates to chip rebuild."""
        self._refresh_cat_chips()

    def _refresh_cat_chips(self):
        """Rebuild the category chip buttons in the cat_bar."""
        for w in self.cat_chips_inner.winfo_children():
            w.destroy()
        self._cat_chip_btns.clear()

        if not self.current_dict:
            return

        cats = sorted({w.get("category","") or "Uncategorized"
                       for w in self.current_dict["words"]})
        if not cats:
            return

        # counts per category
        counts = {}
        for w in self.current_dict["words"]:
            c = w.get("category","") or "Uncategorized"
            counts[c] = counts.get(c, 0) + 1

        # all chip
        all_active = len(self._selected_cats) == 0
        all_chip = self._make_chip("All  (%d)" % len(self.current_dict["words"]),
                                    active=all_active)
        all_chip.pack(side="left", padx=(0,4))
        all_chip.bind("<Button-1>", lambda e: self._chip_click(None))
        self._cat_chip_btns["__all__"] = all_chip

        sep_lbl = lbl(self.cat_chips_inner, "│", font=FONT_UIS, fg=C["bg3"], bg=C["bg2"])
        sep_lbl.pack(side="left", padx=4)

        for cat in cats:
            active = cat in self._selected_cats
            c_lbl  = f"{cat}  ({counts.get(cat,0)})"
            chip   = self._make_chip(c_lbl, active=active)
            chip.pack(side="left", padx=(0,4))
            chip.bind("<Button-1>", lambda e, c=cat: self._chip_click(c))
            self._cat_chip_btns[cat] = chip

    def _make_chip(self, text, active=False):
        bg  = C["red"]      if active else C["bg3"]
        fg  = C["white"]    if active else C["ink2"]
        hbg = C["red2"]     if active else C["bg2"]
        chip = FlatButton(self.cat_chips_inner, text=text,
                           bg=bg, fg=fg, hover_bg=hbg,
                           font=FONT_UIS, padx=10, pady=3)
        return chip

    def _chip_click(self, cat):
        """Toggle a category chip; cat=None means 'All'."""
        if cat is None:
            self._selected_cats.clear()
        else:
            if cat in self._selected_cats:
                self._selected_cats.discard(cat)
            else:
                self._selected_cats.add(cat)
        self._refresh_cat_chips()
        self._apply_filter()

    def _filter_favourites(self):
        self.fav_var.set(True)
        self._selected_cats.clear()
        self._refresh_cat_chips()
        self._apply_filter()

    def _clear_filters(self):
        if self._ph_active:
            pass
        else:
            self.search_var.set("")
        self._show_placeholder()
        self._selected_cats.clear()
        self.fav_var.set(False)
        self._refresh_cat_chips()
        self._apply_filter()

    def _apply_filter(self, *_):
        if not self.current_dict:
            return
        q     = self._get_search_q()
        fav_f = self.fav_var.get()

        filtered = []
        for w in self.current_dict.get("words", []):
            if fav_f and not w.get("favorite"):
                continue
            # multi-cat filter
            if self._selected_cats:
                wcat = w.get("category","") or "Uncategorized"
                if wcat not in self._selected_cats:
                    continue
            if q:
                q_norm = normalize_kana(q)
                hay = normalize_kana(" ".join([w.get(k,"") for k in ("word","reading","romaji","comment","category")]).lower())
                if q_norm not in hay:
                    continue
            filtered.append(w)

        col, rev = self._sort_col, self._sort_rev
        if col == "fav":
            filtered.sort(key=lambda x: x.get("favorite", False), reverse=not rev)
        else:
            filtered.sort(key=lambda x: (x.get(col) or "").lower(), reverse=rev)

        self.all_words = filtered
        self._populate_tree(filtered)
        n = len(filtered)
        self.count_lbl.config(text=f"{n} word{'s' if n!=1 else ''}")

    def _populate_tree(self, words):
        self.tree.delete(*self.tree.get_children())
        for i, w in enumerate(words):
            star    = "⭐" if w.get("favorite") else ""
            comment = (w.get("comment","") or "")[:70]
            if len(w.get("comment","") or "") > 70:
                comment += "…"
            tags = ("fav_row",) if w.get("favorite") else (("alt_row",) if i%2 else ())
            self.tree.insert("", "end",
                              values=(star, w.get("word",""), w.get("reading",""),
                                      w.get("romaji",""), w.get("category",""),
                                      comment, (w.get("created","") or "")[:10]),
                              tags=tags)

    def _sort_by(self, col):
        self._sort_rev = (not self._sort_rev) if self._sort_col == col else False
        self._sort_col = col
        self._apply_filter()
        labels = {"fav":"⭐","word":"Word","reading":"Reading","romaji":"Romaji",
                  "category":"Category","comment":"Notes","created":"Added"}
        for c, t in labels.items():
            arrow = (" ▲" if not self._sort_rev else " ▼") if c == col else ""
            self.tree.heading(c, text=t + arrow)

    # category management
    def _manage_categories(self):
        if not self.current_dict:
            messagebox.showinfo("No dictionary", "Select a dictionary first.", parent=self)
            return
        dlg = CategoryManagerDialog(self, self.current_dict)
        self.wait_window(dlg)
        save_dict(self.current_dict)
        self._selected_cats.clear()
        self._refresh_cat_chips()
        self._apply_filter()
        self.status_var.set("Categories updated")

    # csv
    def _export_csv(self):
        if not self.current_dict:
            messagebox.showinfo("No dictionary", "Select a dictionary first."); return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV","*.csv")],
            initialfile=f"{self.current_dict['name']}.csv", parent=self)
        if not path: return
        fields = ["word","reading","romaji","category","comment","favorite","created"]
        with open(path,"w",newline="",encoding="utf-8-sig") as f:
            wr = csv.DictWriter(f, fieldnames=fields)
            wr.writeheader()
            for e in self.current_dict.get("words",[]):
                wr.writerow({k: e.get(k,"") for k in fields})
        self.status_var.set(f"Exported to {path}")
        messagebox.showinfo("Done", f"Exported {len(self.current_dict['words'])} words.", parent=self)

    def _import_csv(self):
        if not self.current_dict:
            messagebox.showinfo("No dictionary", "Select a dictionary first."); return
        path = filedialog.askopenfilename(filetypes=[("CSV","*.csv")], parent=self)
        if not path: return
        count = 0
        with open(path,"r",encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                w = new_word(
                    word=row.get("word",""), reading=row.get("reading",""),
                    romaji=row.get("romaji",""), category=row.get("category",""),
                    comment=row.get("comment",""),
                    favorite=str(row.get("favorite","")).lower() in ("true","1","yes"))
                if w["word"]:
                    self.current_dict["words"].append(w)
                    self._merge_cat(w["category"])
                    count += 1
        save_dict(self.current_dict)
        self._refresh_cat_menu()
        self._apply_filter()
        self.status_var.set(f"Imported {count} words")
        messagebox.showinfo("Done", f"Imported {count} words.", parent=self)

    def _export_filtered_csv(self):
        if not self.current_dict:
            messagebox.showinfo("No dictionary", "Select a dictionary first."); return
        words = self.all_words
        if not words:
            messagebox.showinfo("Nothing to export", "No words match the current filters."); return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV","*.csv")],
            initialfile=f"{self.current_dict['name']}_filtered.csv", parent=self)
        if not path: return
        fields = ["word","reading","romaji","category","comment","favorite","created"]
        with open(path,"w",newline="",encoding="utf-8-sig") as f:
            wr = csv.DictWriter(f, fieldnames=fields)
            wr.writeheader()
            for e in words:
                wr.writerow({k: e.get(k,"") for k in fields})
        self.status_var.set(f"Exported {len(words)} words to {path}")
        messagebox.showinfo("Done", f"Exported {len(words)} words (filtered view).", parent=self)

    ## quiz stuff ##
    def _open_quiz(self):
        if not self.current_dict or not self.current_dict.get("words"):
            messagebox.showinfo("No words", "Add some words first!", parent=self); return
        QuizWindow(self, self.current_dict["words"],
                   categories=sorted({w.get("category","") or "Uncategorized"
                                       for w in self.current_dict["words"]}))

    def _open_exam(self):
        if not self.current_dict:
            messagebox.showinfo("No dictionary", "Select a dictionary first.", parent=self); return
        if not self.current_dict.get("words"):
            messagebox.showinfo("No words", "Add some words first!", parent=self); return
        ExamWindow(self, self.current_dict)

    def _open_jlpt_manager(self):
        JLPTManagerDialog(self, self.current_dict)

    def _show_stats(self):
        if not self.current_dict:
            messagebox.showinfo("No dictionary", "Select a dictionary first.", parent=self); return
        StatsDialog(self, self.current_dict)

    def _about(self):
        win = tk.Toplevel(self)
        win.title("About Wagochō")
        win.configure(bg=C["bg"])
        win.resizable(False, False)
        win.after(50, lambda: _safe_grab(win))

        hdr = tk.Frame(win, bg=C["sidebar"], pady=20)
        hdr.pack(fill="x")
        lbl(hdr, "和語帳", font=("Segoe UI", 28, "bold"),
            fg=C["red"], bg=C["sidebar"]).pack()
        lbl(hdr, "Wagochō — Japanese Dictionary & Notepad",
            font=FONT_UI, fg="#AAAACC", bg=C["sidebar"]).pack(pady=(2,4))

        body = tk.Frame(win, bg=C["bg"], padx=28, pady=16)
        body.pack()
        for line in [
            "Your personal Japanese vocabulary tracker.",
            "",
            f"Data:  {DATA_DIR}",
            "",
            "Multiple dictionaries · custom categories · search & filter",
            "favourites · type-in quiz · CSV export / import",
        ]:
            lbl(body, line, font=FONT_UIS, fg=C["ink2"] if line else C["bg"],
                justify="center").pack()

        FlatButton(win, "Close", command=win.destroy,
                   bg=C["bg3"], fg=C["ink2"], hover_bg=C["bg2"],
                   font=FONT_UI, padx=14, pady=7).pack(pady=(0,16))

        win.update_idletasks()
        w, h = win.winfo_reqwidth(), win.winfo_reqheight()
        px, py = self.winfo_x(), self.winfo_y()
        pw, ph = self.winfo_width(), self.winfo_height()
        win.geometry(f"{w}x{h}+{px+pw//2-w//2}+{py+ph//2-h//2}")


if __name__ == "__main__":
    app = App()
    app.mainloop()
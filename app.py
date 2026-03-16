import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import json, os, uuid, random, csv
from datetime import datetime
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
    "bg":       "#111111",
    "bg2":      "#1A1A1A",
    "bg3":      "#252525",
    "sidebar":  "#080808",
    "sidebar2": "#0F0F0F",
    "sidebar3": "#181818",
    "ink":      "#D0D0D0",
    "ink2":     "#9AAABB",
    "ink3":     "#555555",
    "red":      "#C0392B",
    "red2":     "#E74C3C",
    "green":    "#6A8759",
    "gold":     "#FFC66D",
    "blue":     "#4A76B2",
    "blue2":    "#3A7AB5",
    "white":    "#FFFFFF",
    "sel":      "#1E3A5F",
    "entry_bg": "#1A1A1A",
    "entry_fg": "#D0D0D0",
    "alt_row":  "#161616",
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
    """Normalize kana for search: converts katakana to hiragana so either script matches the other."""
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

def dict_path(name):
    return DATA_DIR / f"{name}.json"

def list_dictionaries():
    return sorted(p.stem for p in DATA_DIR.glob("*.json"))

def load_dict(name):
    p = dict_path(name)
    if p.exists():
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
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
        # This is needed to apply style to this specific window
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


# quiz
class QuizWindow(tk.Toplevel):
    MODES = {
        "Word → Reading (kana)":  ("word",    "reading"),
        "Reading → Word":         ("reading", "word"),
        "Word → Romaji":          ("word",    "romaji"),
        "Romaji → Word":          ("romaji",  "word"),
        "Word → Meaning/Comment": ("word",    "comment"),
    }

    def __init__(self, parent, words):
        super().__init__(parent)
        self.title("練習 — Quiz")
        self.geometry("520x560")
        self.resizable(True, True)
        self.after(50, lambda: _safe_grab(self))

        self.words   = [w for w in words if w.get("word")]
        self.deck    = []
        self.idx     = 0
        self.correct = 0
        self.wrong   = 0

        self.build_ui()
        self.update_theme()

        if not self.words:
            lbl(self, "No words to quiz!", fg=C["ink2"]).pack(expand=True)
            self.card.pack_forget()
            return
        
        self._new_deck()

    def build_ui(self):
        self.top = tk.Frame(self)
        self.top.pack(fill="x")
        self.top_lbl = lbl(self.top, "練習  Quiz Mode", font=FONT_H2,
            fg=C["white"])
        self.top_lbl.pack(side="left", padx=16, pady=12)
        self.score_lbl = lbl(self.top, "✓ 0   ✗ 0",
                              font=FONT_UIS, fg=C["ink3"])
        self.score_lbl.pack(side="right", padx=16)

        self.mode_row = tk.Frame(self, padx=16, pady=8)
        self.mode_row.pack(fill="x")
        self.mode_lbl = lbl(self.mode_row, "Mode:", font=FONT_UIS, fg=C["ink2"])
        self.mode_lbl.pack(side="left")
        self.mode_var = tk.StringVar(value=list(self.MODES)[0])
        modes = list(self.MODES.keys())
        self.mode_menu = ttk.OptionMenu(self.mode_row, self.mode_var, modes[0], *modes,
                       command=lambda _: self._new_deck())
        self.mode_menu.pack(side="left", padx=8)
        self.restart_btn = FlatButton(self.mode_row, "↺ Restart", command=self._new_deck,
                   font=FONT_UIS, padx=10, pady=4)
        self.restart_btn.pack(side="right")

        self.sep = sep(self)
        self.sep.pack(fill="x")

        self.card = tk.Frame(self)
        self.card.pack(fill="both", expand=True, padx=32, pady=16)
        self._build_card_widgets()

    def _build_card_widgets(self):
        self.progress_lbl = lbl(self.card, "", font=FONT_UIS, fg=C["ink3"])
        self.progress_lbl.pack(anchor="e")

        self.prompt_lbl = lbl(self.card, "", font=FONT_UIS, fg=C["ink2"])
        self.prompt_lbl.pack(pady=(10,4))

        self.q_box = tk.Frame(self.card, highlightthickness=1)
        self.q_box.pack(fill="x", pady=(0,18), ipady=16, ipadx=12)
        self.q_lbl = lbl(self.q_box, "", font=FONT_JPLG, fg=C["ink"])
        self.q_lbl.pack()

        self.ans_lbl = lbl(self.card, "Type your answer:", font=FONT_UIS, fg=C["ink2"])
        self.ans_lbl.pack(anchor="w")
        self.ans_row = tk.Frame(self.card)
        self.ans_row.pack(fill="x", pady=(2,0))

        self.ans_var = tk.StringVar()
        self.ans_entry = tk.Entry(self.ans_row, textvariable=self.ans_var,
                                   font=FONT_JP, relief="flat", bd=0,
                                   highlightthickness=2)
        self.ans_entry.pack(side="left", fill="x", expand=True, ipady=8)
        self.ans_entry.bind("<Return>", lambda e: self._check())

        self.check_btn = FlatButton(self.ans_row, "Check →", command=self._check,
                                     padx=14, pady=8)
        self.check_btn.pack(side="left", padx=(8,0))

        self.fb_frame = tk.Frame(self.card)
        self.fb_frame.pack(fill="x", pady=(14,0))
        self.fb_icon = lbl(self.fb_frame, "", font=("Segoe UI", 22), fg=C["ink"])
        self.fb_icon.pack()
        self.fb_lbl  = lbl(self.fb_frame, "", font=FONT_JP, fg=C["ink2"])
        self.fb_lbl.pack()
        self.fb_hint = lbl(self.fb_frame, "", font=FONT_UIS, fg=C["ink3"])
        self.fb_hint.pack()

        self.next_btn = FlatButton(self.card, "Next  →", 
                                    padx=16, pady=8, command=self._next_card)
    
    def update_theme(self):
        self.configure(bg=C["bg"])
        self.top.config(bg=C["sidebar"])
        self.top_lbl.config(bg=C["sidebar"])
        self.score_lbl.config(bg=C["sidebar"], fg=C["ink3"])
        self.mode_row.config(bg=C["bg2"])
        self.mode_lbl.config(bg=C["bg2"], fg=C["ink2"])
        self.restart_btn.set_colors(bg=C["bg3"], fg=C["ink2"], hover_bg=C["bg2"])
        self.sep.config(bg=C["bg3"])
        self.card.config(bg=C["bg"])
        self.progress_lbl.config(bg=C["bg"], fg=C["ink3"])
        self.prompt_lbl.config(bg=C["bg"], fg=C["ink2"])
        self.q_box.config(bg=C["bg2"], highlightbackground=C["bg3"])
        self.q_lbl.config(bg=C["bg2"], fg=C["ink"])
        self.ans_lbl.config(bg=C["bg"], fg=C["ink2"])
        self.ans_row.config(bg=C["bg"])
        self.ans_entry.config(bg=C["entry_bg"], fg=C["entry_fg"], insertbackground=C["entry_fg"],
                              highlightbackground=C["bg3"], highlightcolor=C["red"])
        self.check_btn.set_colors(bg=C["red"], fg=C["white"], hover_bg=C["red2"])
        self.fb_frame.config(bg=C["bg"])
        self.fb_icon.config(bg=C["bg"])
        self.fb_lbl.config(bg=C["bg"])
        self.fb_hint.config(bg=C["bg"], fg=C["ink3"])
        self.next_btn.set_colors(bg=C["blue"], fg=C["white"], hover_bg=C["blue2"])

    def _new_deck(self, *_):
        for w in self.card.winfo_children():
            w.destroy()
        self._build_card_widgets()
        self.update_theme()

        self.deck    = self.words.copy()
        random.shuffle(self.deck)
        self.idx = self.correct = self.wrong = 0
        self._next_card()

    def _next_card(self):
        self.next_btn.pack_forget()
        self.fb_icon.config(text="")
        self.fb_lbl.config(text="")
        self.fb_hint.config(text="")
        self.ans_var.set("")
        self.ans_entry.config(state="normal", highlightbackground=C["bg3"])
        self.unbind("<Return>")

        if self.idx >= len(self.deck):
            self._show_results()
            return

        card = self.deck[self.idx]
        src, dst = self.MODES[self.mode_var.get()]
        self.progress_lbl.config(text=f"Card {self.idx+1} / {len(self.deck)}")
        self.prompt_lbl.config(text=f"What is the  {dst.upper()}  of:")
        self.q_lbl.config(text=card.get(src,"") or "(empty)")
        self._update_score()
        self.ans_entry.focus()

    def _check(self):
        if self.idx >= len(self.deck):
            return
        card = self.deck[self.idx]
        _, dst = self.MODES[self.mode_var.get()]
        expected = (card.get(dst,"") or "").strip()
        given    = self.ans_var.get().strip()
        correct  = normalize_kana(given.lower().replace(" ","")) == normalize_kana(expected.lower().replace(" ",""))

        if correct:
            self.correct += 1
            self.fb_icon.config(text="✓", fg=C["green"])
            self.fb_lbl.config( text=f"Correct!  {expected}", fg=C["green"])
            self.fb_hint.config(text="")
            self.ans_entry.config(highlightbackground=C["green"])
        else:
            self.wrong += 1
            self.fb_icon.config(text="✗", fg=C["red"])
            self.fb_lbl.config( text=f"Answer:  {expected or '(no entry)'}", fg=C["red"])
            hint = card.get("comment","")
            if hint and dst != "comment":
                self.fb_hint.config(text=f"💬  {hint[:80]}")
            self.ans_entry.config(highlightbackground=C["red"])

        self.ans_entry.config(state="disabled")
        self.idx += 1
        self._update_score()
        self.next_btn.pack(pady=(14,0))
        self.next_btn.focus()
        self.bind("<Return>", lambda e: self._next_card())

    def _update_score(self):
        self.score_lbl.config(text=f"✓ {self.correct}   ✗ {self.wrong}")

    def _show_results(self):
        for w in self.card.winfo_children():
            w.destroy()
        total = self.correct + self.wrong
        pct   = int(self.correct / total * 100) if total else 0
        grade = {
                    "🏆 Excellent!" if pct >= 90 else 
                    "👍 Good job!"  if pct >= 70 else 
                    "📖 Keep studying!" if pct >= 50 else "😤 More practice!"
        }
        
        lbl(self.card, grade, font=FONT_H1, fg=C["ink"], bg=C["bg"]).pack(pady=(30,8))
        lbl(self.card, f"{self.correct} / {total}  ({pct}%)",
            font=FONT_H2, bg=C["bg"], fg=C["green"] if pct >= 70 else C["red"]).pack()
        lbl(self.card, f"✓ {self.correct} correct   ✗ {self.wrong} wrong",
            font=FONT_UI, fg=C["ink2"], bg=C["bg"]).pack(pady=(4,24))

        try_again_btn = FlatButton(self.card, "Try Again", command=self._new_deck)
        try_again_btn.pack()
        try_again_btn.set_colors(bg=C["blue"], fg=C["white"], hover_bg=C["blue2"])

        close_btn = FlatButton(self.card, "Close", command=self.destroy,
                   font=FONT_UI, padx=12, pady=7)
        close_btn.pack(pady=(8,0))
        close_btn.set_colors(bg=C["bg3"], fg=C["ink2"], hover_bg=C["bg2"])


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
        self.hdr_lbl2.config(bg=C["sidebar"], fg=C["ink3"])
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

        self._build_menu()
        self._build_ui()
        self._style_ttk()
        self._refresh_dict_list()

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
            ("Start Quiz  練習",  self._open_quiz),
            ("Dictionary Stats",  self._show_stats),
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
            fg=C["ink3"], bg=C["sidebar"])
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
        btn_stats = FlatButton(self.bot_frame, "📊  Stats", command=self._show_stats,
                   font=FONT_UIS, padx=10, pady=6)
        btn_stats.pack(fill="x", pady=2)
        self.sidebar_btns.extend([btn_quiz, btn_stats])


        # Main panel
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

        self.cat_lbl = lbl(self.toolbar_inner, "Category:", font=FONT_UIS)
        self.cat_lbl.pack(side="left", padx=(14,4))
        self.cat_filter_var = tk.StringVar(value="All")
        self.cat_menu = ttk.OptionMenu(self.toolbar_inner, self.cat_filter_var, "All", "All",
                                        command=lambda _: self._apply_filter())
        self.cat_menu.pack(side="left")

        self.fav_var = tk.BooleanVar()
        self.fav_cb = tk.Checkbutton(self.toolbar_inner, text="⭐ Favourites",
                       variable=self.fav_var, command=self._apply_filter,
                       font=FONT_UIS)
        self.fav_cb.pack(side="left", padx=14)

        self.count_lbl = lbl(self.toolbar_inner, "", font=FONT_UIS)
        self.count_lbl.pack(side="right")

        # Table
        self.tbl_frame = tk.Frame(self.main)
        self.tbl_frame.pack(fill="both", expand=True)

        cols = ("fav","word","reading","romaji","category","comment","created")
        self.tree = ttk.Treeview(self.tbl_frame, columns=cols, show="headings",
                                  style="Dict.Treeview", selectmode="browse")

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

        self.status_var = tk.StringVar(value="Welcome to 和語帳")
        self.status_bar = tk.Label(self.main, textvariable=self.status_var,
                 font=FONT_UIS,
                 anchor="w", padx=14, pady=4)
        self.status_bar.pack(fill="x", side="bottom")

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
        self.topbar.config(bg=C.get("white"), highlightbackground=C["bg3"])
        self.dict_title.config(fg=C["ink"], bg=C.get("white"))
        self.toolbar.config(bg=C["bg2"], highlightbackground=C["bg3"])
        self.toolbar_inner.config(bg=C["bg2"])
        self.srch_frame.config(bg=C["entry_bg"], highlightbackground=C["bg3"])
        self.srch_lbl.config(fg=C["ink3"], bg=C["entry_bg"])
        self.search_entry.config(bg=C["entry_bg"], fg=C["entry_fg"], insertbackground=C["entry_fg"])
        self.cat_lbl.config(fg=C["ink2"], bg=C["bg2"])
        self.fav_cb.config(bg=C["bg2"], fg=C["ink2"], selectcolor=C["bg3"], activebackground=C["bg2"])
        self.count_lbl.config(fg=C["ink3"], bg=C["bg2"])
        self.tbl_frame.config(bg=C["bg"])
        self._style_ttk()
        self.tree.tag_configure("fav_row", foreground=C["gold"])
        self.tree.tag_configure("alt_row", background=C["alt_row"])
        self.sidebar.config(bg=C["sidebar"])
        self.logo_frame.config(bg=C["sidebar"])
        self.logo_lbl1.config(fg=C["red"], bg=C["sidebar"])
        self.logo_lbl2.config(fg=C["ink3"], bg=C["sidebar"])
        self.sidebar_sep1.config(bg=C["sidebar3"])
        self.dict_hdr_frame.config(bg=C["sidebar"])
        self.dict_hdr_lbl.config(fg=C["ink3"], bg=C["sidebar"])
        self.dict_lb_outer.config(bg=C["sidebar"])
        self.dict_lb.config(bg=C["sidebar"], fg="#CCCCEE", selectbackground=C["sidebar3"], selectforeground=C["white"])
        self.sidebar_sep2.config(bg=C["sidebar3"])
        self.bot_frame.config(bg=C["sidebar"])

        self.add_dict_btn.set_colors(C["red"], C["white"], C["red2"])
        for btn in self.sidebar_btns:
            is_quiz = "Quiz" in btn.cget("text")
            btn.set_colors(C["sidebar2"], C["white"] if is_quiz else "#AAAACC", C["sidebar3"])
        
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
        item = self.tree.focus()
        if not item:
            return
        idx = list(self.tree.get_children()).index(item)
        if idx >= len(self.all_words):
            return
        word = self.all_words[idx]
        if not messagebox.askyesno("Delete", f"Delete '{word['word']}'?", parent=self):
            return
        self.current_dict["words"] = [
            w for w in self.current_dict["words"] if w["id"] != word["id"]
        ]
        save_dict(self.current_dict)
        self._apply_filter()
        self.status_var.set(f"Deleted: {word['word']}")

    def _toggle_fav(self):
        item = self.tree.focus()
        if not item:
            return
        idx = list(self.tree.get_children()).index(item)
        if idx >= len(self.all_words):
            return
        wid = self.all_words[idx]["id"]
        for w in self.current_dict["words"]:
            if w["id"] == wid:
                w["favorite"] = not w.get("favorite", False)
                break
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
        self.tree.focus(item)
        self.tree.selection_set(item)
        m = tk.Menu(self, tearoff=0, bg=C["bg2"], fg=C["ink"],
                    activebackground=C["sel"], activeforeground=C["ink"])
        m.add_command(label="Edit",               command=self._edit_selected)
        m.add_command(label="Toggle Favourite ⭐", command=self._toggle_fav)
        m.add_separator()
        m.add_command(label="Delete",             command=self._delete_selected)
        m.tk_popup(e.x_root, e.y_root)

    # filter
    def _refresh_cat_menu(self):
        if not self.current_dict:
            return
        cats = sorted({w.get("category","") for w in self.current_dict["words"] if w.get("category")})
        opts = ["All"] + cats
        m = self.cat_menu["menu"]
        m.delete(0, "end")
        for o in opts:
            m.add_command(label=o,
                          command=lambda v=o: (self.cat_filter_var.set(v), self._apply_filter()))
        if self.cat_filter_var.get() not in opts:
            self.cat_filter_var.set("All")

    def _filter_favourites(self):
        self.fav_var.set(True)
        self._apply_filter()

    def _clear_filters(self):
        self.search_var.set("")
        self.cat_filter_var.set("All")
        self.fav_var.set(False)
        self._apply_filter()

    def _apply_filter(self, *_):
        if not self.current_dict:
            return
        q     = self.search_var.get().lower()
        cat_f = self.cat_filter_var.get()
        fav_f = self.fav_var.get()

        filtered = []
        for w in self.current_dict.get("words", []):
            if fav_f and not w.get("favorite"):
                continue
            if cat_f != "All" and w.get("category") != cat_f:
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

    ## quiz stuff ##
    def _open_quiz(self):
        if not self.current_dict or not self.current_dict.get("words"):
            messagebox.showinfo("No words", "Add some words first!", parent=self); return
        QuizWindow(self, self.current_dict["words"])

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
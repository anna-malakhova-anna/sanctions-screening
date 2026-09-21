"""
Synthetic data for the sanctions screening demo.

Everything here is FICTIONAL. Names are random combinations from small pools;
programs are placeholder codes. The watchlist is shaped loosely like OFAC's
SDN CSV release (a main file plus a separate alias file) so the ingest code
can be written before switching to the real list.

Outputs:
  watchlist_sdn.csv        fictional watchlist, main records
  watchlist_alt.csv        aliases for those records (strong / weak)
  counterparties_demo.csv  the file a user uploads - no labels
  counterparties_labels.csv ground truth, kept separate so the app can't peek

Rerun with the same SEED to get identical files.
"""
import csv, random, datetime as dt

SEED = 42
random.seed(SEED)
LIST_VERSION = "SYN-2026-09-21"

# ---------- name pools, grouped by origin, with transliteration variants ----
POOLS = {
    "arabic": {
        "given": ["Mohammed", "Hussein", "Yusuf", "Abdulrahman", "Khalid", "Omar", "Faisal", "Tariq"],
        "sur": ["Al-Rashid", "Haddad", "Nasser", "Al-Amin", "Mansour", "Qasim"],
        "countries": ["AE", "LB", "JO", "EG", "IQ", "SA"],
    },
    "russian": {
        "given": ["Aleksandr", "Sergei", "Dmitri", "Yevgeny", "Mikhail", "Andrei"],
        "sur": ["Volkov", "Sokolov", "Kuznetsov", "Morozov", "Zaitsev"],
        "countries": ["RU", "BY", "CY", "KZ"],
    },
    "persian": {
        "given": ["Reza", "Hossein", "Mehdi", "Javad"],
        "sur": ["Tehrani", "Mousavi", "Karimi", "Rahimi"],
        "countries": ["IR", "AE", "TR"],
    },
    "spanish": {
        "given": ["José", "Jesús", "Raúl", "Héctor"],
        "sur": ["Hernández", "Ramírez", "Gutiérrez", "Muñoz"],
        "countries": ["MX", "CO", "VE", "PA"],
    },
    "chinese": {
        "given": ["Wei", "Jun", "Lei", "Ming"],
        "sur": ["Zhang", "Xu", "Zhou", "Chen"],
        "countries": ["CN", "HK", "SG"],
    },
    "english": {
        "given": ["Robert", "Michael", "David", "Thomas"],
        "sur": ["Harrington", "Blake", "Whitmore", "Caldwell"],
        "countries": ["GB", "US", "CA"],
    },
}

TRANSLIT = {
    "Mohammed": ["Muhammad", "Mohamad", "Mohamed"], "Hussein": ["Husayn", "Hussain", "Husein"],
    "Yusuf": ["Youssef", "Yousef", "Yousuf"], "Abdulrahman": ["Abdul Rahman", "Abd al-Rahman", "Abdelrahman"],
    "Khalid": ["Khaled", "Khaled"], "Omar": ["Umar"], "Faisal": ["Faysal", "Feisal"], "Tariq": ["Tarek", "Tareq"],
    "Al-Rashid": ["Al Rashid", "Alrashid", "El-Rashid"], "Haddad": ["Hadad"], "Nasser": ["Nasir", "Nassir"],
    "Al-Amin": ["Al Amin", "Alamin", "El-Amin"], "Mansour": ["Mansur", "Mansoor"], "Qasim": ["Kassim", "Qassem"],
    "Aleksandr": ["Alexander", "Aleksander", "Oleksandr"], "Sergei": ["Sergey", "Serhiy"],
    "Dmitri": ["Dmitry", "Dmitriy"], "Yevgeny": ["Evgeny", "Evgeniy"], "Mikhail": ["Michail", "Mykhailo"],
    "Andrei": ["Andrey", "Andriy"], "Volkov": ["Volkoff", "Wolkow"], "Sokolov": ["Sokoloff"],
    "Kuznetsov": ["Kouznetsov", "Kuznetsoff"], "Morozov": ["Morosov"], "Zaitsev": ["Zaytsev", "Zajcev"],
    "Hossein": ["Hosein", "Hosseyn"], "Mehdi": ["Mahdi"], "Javad": ["Jawad"],
    "Mousavi": ["Musavi", "Moussavi"], "Karimi": ["Karimy"], "Rahimi": ["Rahimy"], "Tehrani": ["Tehranee"],
    "Zhang": ["Chang"], "Xu": ["Hsu"], "Zhou": ["Chou"], "Chen": ["Chan"],
}
WEAK = {  # weak aliases: kunyas and diminutives - should score LOW on their own
    "Mohammed": "Abu Mohammed", "Khalid": "Abu Khalid", "Omar": "Abu Omar", "Yusuf": "Abu Yusuf",
    "Aleksandr": "Sasha", "Dmitri": "Dima", "Mikhail": "Misha", "Yevgeny": "Zhenya", "Sergei": "Seryozha",
}

CO_PREFIX = ["Northgate", "Bluewater", "Silverline", "Crescent", "Evergreen", "Harbor", "Summit", "Orion",
             "Meridian", "Atlas", "Granite", "Lakeshore", "Pinecrest", "Ironwood", "Keystone", "Redwood",
             "Beacon", "Falcon", "Sterling", "Cobalt", "Juniper", "Halcyon", "Tidewater", "Aurora"]
CO_INDUSTRY = ["Logistics", "Trading", "Capital", "Maritime", "Holdings", "Industries", "Energy", "Foods",
               "Textiles", "Technologies", "Shipping", "Minerals", "Consulting", "Imports", "Petrochemicals"]
CO_SUFFIX = {"Ltd": "GB", "LLC": "US", "Inc.": "CA", "GmbH": "DE", "S.A.": "PA", "B.V.": "NL",
             "FZE": "AE", "Pte. Ltd.": "SG", "OOO": "RU", "JSC": "KZ", "Limited": "HK"}
SUFFIX_SWAP = {"Ltd": ["Limited", "Ltd.", ""], "Limited": ["Ltd", ""], "LLC": ["L.L.C.", "Company", ""],
               "Inc.": ["Incorporated", "Inc", ""], "GmbH": ["G.m.b.H.", ""], "S.A.": ["SA", ""],
               "B.V.": ["BV", ""], "FZE": ["F.Z.E.", ""], "Pte. Ltd.": ["Pte Ltd", "Private Limited", ""],
               "OOO": ["LLC", ""], "JSC": ["J.S.C.", "Joint Stock Company", ""]}
VESSELS = ["MV CRESCENT DAWN", "MV SILVER TIDE", "MV NORTHERN LANTERN"]
PROGRAMS = ["SYN-A", "SYN-B", "SYN-C"]  # placeholders, not real sanctions programs

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

def rand_dob():
    return dt.date(random.randint(1955, 1995), random.randint(1, 12), random.randint(1, 28))

def dob_remark(d):
    """SDN-style DOB text: sometimes exact, sometimes year-only, circa, or a range."""
    mode = random.choices(["exact", "year", "circa", "range", "exact_alt"], [4, 3, 1, 1, 1])[0]
    if mode == "exact":     return f"DOB {d.day:02d} {MONTHS[d.month-1]} {d.year}"
    if mode == "year":      return f"DOB {d.year}"
    if mode == "circa":     return f"DOB circa {d.year}"
    if mode == "range":     return f"DOB {d.year-1} to {d.year+2}"
    return f"DOB {d.day:02d} {MONTHS[d.month-1]} {d.year}; alt. DOB {d.year+1}"

def co_name(prefix=None):
    p = prefix or random.choice(CO_PREFIX)
    s = random.choice(list(CO_SUFFIX))
    return p, random.choice(CO_INDUSTRY), s

# ---------- build the watchlist ---------------------------------------------
watch_ind, watch_ent, sdn_rows, alt_rows = [], [], [], []
ent_num, alt_num = 10000, 50000
used_full = set()

origins = list(POOLS)
for i in range(24):                                   # 24 individuals, 4 per origin
    o = origins[i % len(origins)]
    while True:
        g, s = random.choice(POOLS[o]["given"]), random.choice(POOLS[o]["sur"])
        if (g, s) not in used_full: break
    used_full.add((g, s))
    ent_num += 1
    rec = dict(ent_num=ent_num, given=g, sur=s, origin=o, dob=rand_dob(),
               country=random.choice(POOLS[o]["countries"]))
    watch_ind.append(rec)
    remarks = f"{dob_remark(rec['dob'])}; nationality {rec['country']}"
    sdn_rows.append([ent_num, f"{s.upper()}, {g}", "individual", random.choice(PROGRAMS), "", remarks])
    if g in TRANSLIT or s in TRANSLIT:                # a strong transliteration alias
        g2 = random.choice(TRANSLIT.get(g, [g])); s2 = random.choice(TRANSLIT.get(s, [s]))
        alt_num += 1; alt_rows.append([ent_num, alt_num, "aka", f"{s2.upper()}, {g2}", "strong"])
    if g in WEAK and random.random() < 0.7:           # a weak alias
        alt_num += 1; alt_rows.append([ent_num, alt_num, "aka", WEAK[g], "weak"])

used_co = set()
for i in range(12):                                   # 12 entities
    while True:
        p, ind, suf = co_name()
        if (p, ind) not in used_co: break
    used_co.add((p, ind))
    ent_num += 1
    name = f"{p} {ind} {suf}"
    watch_ent.append(dict(ent_num=ent_num, prefix=p, industry=ind, suffix=suf, name=name,
                          country=CO_SUFFIX[suf]))
    sdn_rows.append([ent_num, name.upper(), "entity", random.choice(PROGRAMS), "",
                     f"Registered in {CO_SUFFIX[suf]}"])
    if random.random() < 0.5:                         # former name
        while True:
            p2, ind2, _ = co_name()
            if (p2, ind2) not in used_co: break
        used_co.add((p2, ind2))                       # reserve, so clean rows can't collide
        alt_num += 1; alt_rows.append([ent_num, alt_num, "fka", f"{p2} {ind2} {suf}".upper(), "strong"])

for v in VESSELS:                                     # 3 vessels
    ent_num += 1
    sdn_rows.append([ent_num, v, "vessel", random.choice(PROGRAMS), random.choice(["PA", "LR", "MH"]),
                     f"IMO {random.randint(9000000, 9999999)}"])

# ---------- perturbations ---------------------------------------------------
def typo(w):
    if len(w) < 5: return w
    i = random.randint(1, len(w) - 2)
    op = random.choice(["sub", "del", "swap", "double"])
    if op == "sub":  return w[:i] + random.choice("aeiourn") + w[i+1:]
    if op == "del":  return w[:i] + w[i+1:]
    if op == "swap": return w[:i] + w[i+1] + w[i] + w[i+2:]
    return w[:i] + w[i] + w[i:]

STRIP = str.maketrans("áéíóúñÁÉÍÓÚÑ", "aeiounAEIOUN")

def perturb_individual(r):
    g, s = r["given"], r["sur"]
    options = ["exact", "typo", "word_order", "initials"]
    if g in TRANSLIT or s in TRANSLIT: options += ["transliteration"] * 3
    if any(c in g + s for c in "áéíóúñ"): options += ["diacritics"] * 2
    if "-" in s: options.append("punctuation")
    kind = random.choice(options)
    note = ""
    if kind == "transliteration":
        if s in TRANSLIT and (g not in TRANSLIT or random.random() < 0.5):
            new = random.choice(TRANSLIT[s]); note = f"{s}->{new}"; s = new
        else:
            new = random.choice(TRANSLIT[g]); note = f"{g}->{new}"; g = new
        name = f"{g} {s}"
    elif kind == "typo":
        if random.random() < 0.5: new = typo(s); note = f"{s}->{new}"; s = new
        else: new = typo(g); note = f"{g}->{new}"; g = new
        name = f"{g} {s}"
    elif kind == "word_order":  name = random.choice([f"{s} {g}", f"{s.upper()}, {g}"])
    elif kind == "initials":    name = f"{g[0]}. {s}"
    elif kind == "diacritics":  name = f"{g} {s}".translate(STRIP)
    elif kind == "punctuation": name = f"{g} {s.replace('-', '')}"
    else:                       name = f"{g} {s}"
    return name, kind, note

def perturb_entity(r):
    kind = random.choice(["legal_suffix", "legal_suffix", "typo", "word_drop", "exact"])
    p, ind, suf, note = r["prefix"], r["industry"], r["suffix"], ""
    if kind == "legal_suffix":
        new = random.choice(SUFFIX_SWAP[suf]); note = f"{suf}->{new or '(dropped)'}"; suf = new
    elif kind == "typo":
        new = typo(p); note = f"{p}->{new}"; p = new
    elif kind == "word_drop":
        note = f"dropped '{ind}'"; ind = ""
    return " ".join(x for x in [p, ind, suf] if x), kind, note

# ---------- counterparties --------------------------------------------------
rows, labels = [], []

def add(name, ctype, country, dob, reg, match, uid, ptype, note=""):
    rows.append(dict(name=name, counterparty_type=ctype, country=country,
                     date_of_birth=dob.isoformat() if dob else "", registration_number=reg))
    labels.append(dict(is_true_match=int(match), watchlist_ent_num=uid or "",
                       perturbation_type=ptype, notes=note))

def reg_no(): return f"{random.choice('ABCDEFGH')}{random.randint(1000000, 9999999)}"

# true positives: 20 individuals, 8 entities
for r in random.sample(watch_ind, 20):
    name, kind, note = perturb_individual(r)
    add(name, "individual", r["country"], r["dob"], "", True, r["ent_num"], kind, note)
for r in random.sample(watch_ent, 8):
    name, kind, note = perturb_entity(r)
    add(name, "entity", r["country"], None, reg_no(), True, r["ent_num"], kind, note)

# a few hits via the alias file only (primary name wouldn't match well)
for a in [a for a in alt_rows if a[4] == "strong" and a[2] == "aka"][:3]:
    r = next(x for x in watch_ind if x["ent_num"] == a[0])
    sur, giv = a[3].split(", "); name = f"{giv} {sur.title()}"
    add(name, "individual", r["country"], r["dob"], "", True, r["ent_num"], "alias_hit",
        f"matches alt {a[1]}")

# deliberate hard negatives
for r in random.sample(watch_ind, 6):                 # same name, different person
    dob = r["dob"].replace(year=r["dob"].year + random.choice([-19, -14, 12, 17]))
    country = random.choice([c for c in POOLS[r["origin"]]["countries"] if c != r["country"]] or ["GB"])
    add(f"{r['given']} {r['sur']}", "individual", country, dob, "", False, "",
        "hard_negative:same_name_diff_dob", f"shares name with {r['ent_num']}")
for r in random.sample(watch_ent, 6):                 # shares a distinctive token
    ind = random.choice([x for x in CO_INDUSTRY if x != r["industry"]])
    suf = random.choice(list(CO_SUFFIX))
    add(f"{r['prefix']} {ind} {suf}", "entity", CO_SUFFIX[suf], None, reg_no(), False, "",
        "hard_negative:token_overlap", f"shares '{r['prefix']}' with {r['ent_num']}")
for v in VESSELS[:2]:                                 # company named like a vessel
    base = v.replace("MV ", "").title()
    add(f"{base} Travel Ltd", "entity", "GB", None, reg_no(), False, "",
        "hard_negative:vessel_name_overlap", f"resembles {v}")

# clean population - drawn from the SAME name pools, so origin can't predict a hit
watch_surnames = {r["sur"] for r in watch_ind}
watch_prefixes = {r["prefix"] for r in watch_ent}
while len(rows) < 200:
    if random.random() < 0.55:
        o = random.choice(origins)
        g, s = random.choice(POOLS[o]["given"]), random.choice(POOLS[o]["sur"])
        if (g, s) in used_full: continue              # full-name collisions only via hard negatives
        ptype = "clean:shared_surname" if s in watch_surnames else "clean"
        add(f"{g} {s}", "individual", random.choice(POOLS[o]["countries"]), rand_dob(), "", False, "", ptype)
    else:
        p, ind, suf = co_name()
        if (p, ind) in used_co: continue
        ptype = "clean:shared_token" if p in watch_prefixes else "clean"
        add(f"{p} {ind} {suf}", "entity", CO_SUFFIX[suf], None, reg_no(), False, "", ptype)

# formatting noise on ~10% of rows, positives and negatives alike
for row, lab in zip(rows, labels):
    if random.random() < 0.10:
        row["name"] = random.choice([row["name"].upper(), f"  {row['name']} ", row["name"].replace(" ", "  ", 1)])
        lab["notes"] = (lab["notes"] + "; " if lab["notes"] else "") + "format noise"

# shuffle, assign ids
order = list(range(len(rows))); random.shuffle(order)
rows = [rows[i] for i in order]; labels = [labels[i] for i in order]
for n, (row, lab) in enumerate(zip(rows, labels), 1):
    row["counterparty_id"] = lab["counterparty_id"] = f"CP-{n:04d}"

# ---------- write ----------------------------------------------------------
def write(path, header, data):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n"); w.writerow(header); w.writerows(data)

write("watchlist_sdn.csv", ["ent_num", "sdn_name", "sdn_type", "program", "vessel_flag", "remarks"], sdn_rows)
write("watchlist_alt.csv", ["ent_num", "alt_num", "alt_type", "alt_name", "alt_strength"], alt_rows)
cp_cols = ["counterparty_id", "name", "counterparty_type", "country", "date_of_birth", "registration_number"]
write("counterparties_demo.csv", cp_cols, [[r[c] for c in cp_cols] for r in rows])
lb_cols = ["counterparty_id", "is_true_match", "watchlist_ent_num", "perturbation_type", "notes"]
write("counterparties_labels.csv", lb_cols, [[l[c] for c in lb_cols] for l in labels])

if __name__ == "__main__":
    from collections import Counter
    print(f"watchlist: {len(sdn_rows)} records, {len(alt_rows)} aliases (version {LIST_VERSION})")
    print(f"counterparties: {len(rows)}, true matches: {sum(l['is_true_match'] for l in labels)}")
    for k, v in sorted(Counter(l["perturbation_type"] for l in labels).items()): print(f"  {k}: {v}")

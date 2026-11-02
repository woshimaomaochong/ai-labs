"""汇总：工程质量（Lighthouse/axe）、技能承诺（手机溢出/键盘焦点/减少动效/行宽）、技能点名的 AI 套路、千篇一律程度、
成对盲评胜率、成本。输入 shots/<文件名>/{metrics,lh}.json、pages/*.html、judge.jsonl、raw.jsonl；输出 stats.json 并打印。"""
import colorsys
import json
import math
import re
from itertools import combinations
from pathlib import Path

import numpy as np
from PIL import Image

WD = Path(__file__).resolve().parent
BIDS = [b["id"] for b in json.loads((WD / "briefs.json").read_text(encoding="utf-8"))]


def hexes(css):
    out = []
    for h in re.findall(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b", css):
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        out.append(tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)))
    for r, g, b in re.findall(r"rgba?\((\d+),\s*(\d+),\s*(\d+)", css):
        out.append((int(r), int(g), int(b)))
    return out


def dist(a, b):
    return math.dist(a, b)


def rgb_of(s):
    m = re.findall(r"\d+", s or "")
    return tuple(int(x) for x in m[:3]) if len(m) >= 3 else (255, 255, 255)


def tells(html, m):
    """技能原文点名的 AI 默认套路（这是技能自己的标准，单独报告）。"""
    cols = hexes(html)
    bg = rgb_of(m.get("body_bg"))
    lum = sum(bg) / 765
    t = {}
    cream = bg[0] > 232 and bg[1] > 222 and bg[2] > 205 and bg[0] - bg[2] >= 8  # 暖奶油底（不是纯白/冷灰）
    t["奶油底+陶土色"] = cream and any(dist(c, (217, 119, 87)) < 40 or (c[0] > 170 and 80 < c[1] < 130 and c[2] < 100) for c in cols)
    acid = any((lambda h, s, v: (0.17 < h < 0.42 or h < 0.04) and s > 0.7 and v > 0.85)(*colorsys.rgb_to_hsv(*(x / 255 for x in c))) for c in cols)
    t["黑底+荧光强调色"] = lum < 0.12 and acid
    t["卡片套件(灰阴影)"] = len(re.findall(r"rgba\(0,\s*0,\s*0,\s*0?\.(0[5-9]|1|12|15)\)", html)) >= 3
    t["全大写小标签"] = (m.get("uppercase_labels") or 0) >= 3
    t["按钮带→"] = (m.get("arrow_in_buttons") or 0) >= 1
    t["A · B · C 分隔"] = (m.get("middle_dot_meta") or 0) >= 2
    t["01/02 编号"] = (m.get("numbered_markers") or 0) >= 2
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S | re.I)
    t["标题单词换色"] = bool(h1 and re.search(r"<(em|span|i|strong|mark)\b", h1.group(1), re.I))
    return t


def thumb(p, size=(48, 30)):
    im = Image.open(p).convert("RGB").resize(size)
    return np.asarray(im, dtype=float) / 255


def sim(a, b):
    """首屏相似度：布局（灰度相关）与色彩（平均色差）合成，0~1。"""
    ga, gb = a.mean(2).ravel(), b.mean(2).ravel()
    corr = np.corrcoef(ga, gb)[0, 1] if ga.std() > 0 and gb.std() > 0 else 0
    col = 1 - np.abs(a - b).mean()
    return float((max(corr, 0) + col) / 2)


def wilson(k, n, z=1.96):
    if n == 0:
        return (0, 0)
    p = k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (round(c - h, 3), round(c + h, 3))


def sign_p(w, l):
    n = w + l
    if n == 0:
        return 1.0
    k = min(w, l)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def main():
    rows = {}
    for arm in "AB":
        for bid in BIDS:
            d = WD / "shots" / f"{arm}_{bid}_0"
            if not (d / "metrics.json").exists():
                continue
            m = json.loads((d / "metrics.json").read_text(encoding="utf-8"))
            lh = json.loads((d / "lh.json").read_text(encoding="utf-8")) if (d / "lh.json").exists() else {}
            html = (WD / "pages" / f"{arm}_{bid}_0.html").read_text(encoding="utf-8", errors="ignore")
            rows[(arm, bid)] = {"m": m, "lh": lh.get("cats", {}), "tells": tells(html, m), "dir": d}
    paired = [b for b in BIDS if ("A", b) in rows and ("B", b) in rows]
    S = {"n_pairs": len(paired)}
    for arm in "AB":
        R = [rows[(arm, b)] for b in paired]
        n = len(R)
        lh ={k: round(float(np.mean([(r["lh"].get(k) or 0) * 100 for r in R])), 1) for k in ("performance", "accessibility", "best-practices", "seo")}
        axe_nodes = [sum(v["nodes"] for v in r["m"].get("axe", [])) for r in R]
        S[arm] = {
            "lighthouse": lh,
            "axe_violation_nodes_median": float(np.median(axe_nodes)),
            "axe_pages_with_serious": sum(any(v["impact"] in ("serious", "critical") for v in r["m"].get("axe", [])) for r in R),
            "contrast_fail_pages": sum(any(v["id"] == "color-contrast" for v in r["m"].get("axe", [])) for r in R),
            "mobile_overflow_pages": sum((r["m"].get("mobile_overflow_px") or 0) > 1 for r in R),
            "focus_visible_pages": sum(bool((r["m"].get("focus") or {}).get("visible")) for r in R),
            "reduced_motion_pages": sum(bool(r["m"].get("reduced_motion_css")) for r in R),
            "console_error_pages": sum(bool(r["m"].get("console_errors")) for r in R),
            "chars_per_line_median": float(np.median([r["m"].get("chars_per_line_median") or 0 for r in R])),
            "webfont_pages": sum(bool(r["m"].get("fonts_loaded")) for r in R),
            "distinct_heading_fonts": len({(r["m"].get("h1") or {}).get("font", "").split(",")[0].strip('" ') for r in R}),
            "tells_total": sum(sum(r["tells"].values()) for r in R),
            "tells_by_kind": {k: sum(r["tells"][k] for r in R) for k in R[0]["tells"]} if R else {},
        }
        th = [thumb(r["dir"] / "desktop_hero.png") for r in R]
        S[arm]["hero_similarity_mean"] = round(float(np.mean([sim(a, b) for a, b in combinations(th, 2)])), 3) if n > 1 else None
    # 成本
    raw = [json.loads(l) for l in (WD / "raw.jsonl").read_text(encoding="utf-8").splitlines()]
    for arm in "AB":
        rr = [r for r in raw if r["arm"] == arm and r["bid"] in paired and r["rep"] == 0]
        S[arm]["cost_usd_mean"] = round(float(np.mean([r["cost_usd"] for r in rr])), 3)
        S[arm]["sec_mean"] = round(float(np.mean([r["sec"] for r in rr])), 1)
        S[arm]["out_tokens_mean"] = round(float(np.mean([r["completion_tokens"] for r in rr])))
        S[arm]["html_kb_mean"] = round(float(np.mean([r["html_bytes"] for r in rr])) / 1024, 1)
    # 盲评
    J = [json.loads(l) for l in (WD / "judge.jsonl").read_text(encoding="utf-8").splitlines()] if (WD / "judge.jsonl").exists() else []
    S["judges"] = {}
    for judge in sorted({j["judge"] for j in J}):
        jj = [j for j in J if j["judge"] == judge and j["bid"] in paired]
        # 每道题合并正反两次：两次都选同一方才算该方胜，否则算平
        per = {}
        for j in jj:
            per.setdefault(j["bid"], []).append(j["winner"])
        res = {b: (v[0] if len(v) == 2 and v[0] == v[1] else "tie") if len(v) == 2 else v[0] for b, v in per.items()}
        w, l = sum(v == "B" for v in res.values()), sum(v == "A" for v in res.values())
        t = len(res) - w - l
        dims = {}
        for j in jj:
            for dname in j["scores"]["A"]:
                dims.setdefault(dname, []).append(j["scores"]["B"].get(dname, 0) - j["scores"]["A"].get(dname, 0))
        S["judges"][judge] = {"B_wins": w, "A_wins": l, "ties": t, "B_winrate_excl_ties": round(w / max(1, w + l), 3),
                              "ci95": wilson(w, w + l), "sign_test_p": round(sign_p(w, l), 4),
                              "position_consistency": round(sum(len(v) == 2 and v[0] == v[1] for v in per.values()) / max(1, len(per)), 3),
                              "dim_diff_B_minus_A": {k: round(float(np.mean(v)), 2) for k, v in dims.items()},
                              "per_brief": res}
    (WD / "stats.json").write_text(json.dumps(S, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(S, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()

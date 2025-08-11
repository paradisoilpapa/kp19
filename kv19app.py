import streamlit as st
import pandas as pd

"""
Velobi-K β（地方競馬スコア計算：NAR＋ばんえい対応）
- 5〜12頭対応（欠頭数OK）
- NAR公式コース情報をプリセット（帯広ばんえい含む）
- モード切替：平地（サラ） / ばんえい（帯広）
- 目的：まず“ひな形”として一括運用できる骨組みを提供（係数は後でチューニング）
"""

st.set_page_config(page_title="Velobi-K β（地方競馬/NAR＋ばんえい）", layout="wide")
st.title("🏇 Velobi-K β（地方競馬スコア計算：NAR＋ばんえい対応）")
st.caption("5〜12頭・NAR全場＋帯広（ばんえい）をこの1本で処理（欠頭数OK）")

# =========================================
# 設定
# =========================================
N_MAX = 12

# --- 競馬場プリセット（NAR公式ベース：直線は“ゴールまで”の長さ） ---
TRACKS = {
    # ばんえい
    "帯広(ばんえい)": {"surface":"ダート","course":"直線","circle":200,"stretch":200,"turns":0,
                 "obstacle1_m":1.0,"obstacle2_m":1.6},

    # ホッカイドウ・岩手
    "門別":  {"surface":"ダート","course":"右","circle":1600,"stretch":330,"turns":2},
    "盛岡":  {"surface":"ダート","course":"左","circle":1600,"stretch":300,"turns":2},
    "水沢":  {"surface":"ダート","course":"右","circle":1200,"stretch":245,"turns":2},

    # 南関東
    "浦和":  {"surface":"ダート","course":"左","circle":1200,"stretch":220,"turns":2},
    "船橋":  {"surface":"ダート","course":"左","circle":1400,"stretch":308,"turns":2},
    "大井":  {"surface":"ダート","course":"右","circle":1600,"stretch":386,"turns":2},
    "川崎":  {"surface":"ダート","course":"左","circle":1200,"stretch":300,"turns":2},

    # 北陸・東海・近畿
    "金沢":  {"surface":"ダート","course":"右","circle":1200,"stretch":236,"turns":2},
    "笠松":  {"surface":"ダート","course":"右","circle":1100,"stretch":201,"turns":2},
    "名古屋":{"surface":"ダート","course":"右","circle":1180,"stretch":240,"turns":2},
    "園田":  {"surface":"ダート","course":"右","circle":1051,"stretch":213,"turns":2},
    "姫路":  {"surface":"ダート","course":"右","circle":1200,"stretch":230,"turns":2},

    # 四国・九州
    "高知":  {"surface":"ダート","course":"右","circle":1100,"stretch":200,"turns":2},
    "佐賀":  {"surface":"ダート","course":"右","circle":1100,"stretch":200,"turns":2},

    # 手入力
    "手入力": {"surface":"ダート","course":"右","circle":1400,"stretch":300,"turns":2}
}

SURFACE_STATES = ["良", "稍重", "重", "不良"]
PACE_SCENARIOS = ["前傾", "平均", "後傾"]  # 平地のみ使用
RUN_STYLES = ["逃", "先", "差", "追"]      # 平地のみ使用

# --- UI安全化ヘルパ（表記ゆれ対応） ---
_course_opts = ["右","左","直"]
_course_alias = {
    "右回り":"右", "右外":"右",
    "左回り":"左",
    "直線":"直", "直":"直",
    "right":"右", "left":"左", "straight":"直"
}
_surface_opts = ["ダート","芝"]
_surface_alias = {
    "砂":"ダート", "DIRT":"ダート",
    "TURF":"芝"
}

def safe_selectbox(label, options, value, aliases=None, default=0, key=None):
    v = str(value)
    if aliases:
        v = aliases.get(v, v)
    try:
        idx = options.index(v)
    except ValueError:
        idx = default
    return st.selectbox(label, options, index=idx, key=key)

# =========================================
# UI：コース/馬場/モード
# =========================================
colA, colB, colC = st.columns([1.2,1,1])
with colA:
    track = st.selectbox("競馬場（NAR＋ばんえい）", list(TRACKS.keys()), index=0)
    info = TRACKS[track]
with colB:
    # 自動：帯広を選ぶとばんえいモード推奨
    auto_is_banei = ("ばんえい" in track or (_course_alias.get(info.get("course","右"), info.get("course","右")) == "直" and info.get("turns",2)==0))
    mode = st.radio("モード", ["平地(サラ)", "ばんえい"], index=1 if auto_is_banei else 0, horizontal=True)
with colC:
    surface_state = st.selectbox("馬場状態", SURFACE_STATES, index=0)

# 距離・ペース（平地向け。ばんえい時も距離は参考として保持）
colD, colE = st.columns([1,1])
with colD:
    distance = st.number_input("距離[m]", min_value=800, max_value=2600, step=100, value=1400)
with colE:
    pace_scn = st.selectbox("ペース想定", PACE_SCENARIOS, index=1)

# 共通コース諸元（手入力上書き可）
col1, col2, col3 = st.columns(3)
with col1:
    surface = safe_selectbox("コース種別", _surface_opts, info.get("surface","ダート"), aliases=_surface_alias)
with col2:
    course_dir = safe_selectbox("回り", _course_opts, info.get("course","右"), aliases=_course_alias)
with col3:
    circle = st.number_input("1周距離[m]", min_value=200, max_value=2200, step=50, value=int(info["circle"]))

col4, col5 = st.columns(2)
with col4:
    stretch = st.number_input("直線長[m]（ゴールまで）", min_value=150 if mode=="平地(サラ)" else 200, max_value=500, step=10, value=int(info["stretch"]))
with col5:
    turns = st.number_input("コーナー数", min_value=0, max_value=4, step=1, value=int(info["turns"]))

# =========================================
# UI：馬データ
# =========================================
st.header("【馬データ入力】（欠頭数OK：空欄=除外）")

if mode == "平地(サラ)":
    # 脚質入力
    style_inputs = {}
    cols = st.columns(4)
    for i, k in enumerate(RUN_STYLES):
        with cols[i]:
            st.markdown(f"**{k}**")
            style_inputs[k] = st.text_input("", key=f"style_{k}", max_chars=24)
    # 馬番→脚質
    horse_style = {}
    for k, val in style_inputs.items():
        for c in val:
            if c.isdigit():
                n = int(c)
                if 1 <= n <= N_MAX:
                    horse_style[n] = k
else:
    # ばんえい：脚質ではなく基礎能力の代理指標を入力
    st.info("ばんえいモード：各馬の負担重量・障害対応・近走指数などを入力（簡易版）")

# 近走指数/着順 or 時計（簡易）
st.subheader("▼ 近走指標（指数 or 時計）・着順")
idx_inputs = []
chaku_inputs = []
extra_banei = []  # (weight, stops)
for i in range(N_MAX):
    if mode == "平地(サラ)":
        c1, c2, c3 = st.columns([1,1,1])
        with c1:
            base_idx = st.number_input(f"{i+1}番 基準指数", value=50.0, step=0.5, key=f"idx_{i}")
        with c2:
            ch1 = st.text_input(f"{i+1}番 前々走着", value="", key=f"hc1_{i}")
        with c3:
            ch2 = st.text_input(f"{i+1}番 前走着", value="", key=f"hc2_{i}")
        idx_inputs.append(base_idx)
        chaku_inputs.append([ch1, ch2])
        extra_banei.append((0.0,0))
    else:
        c1, c2, c3 = st.columns([1,1,1])
        with c1:
            base_idx = st.number_input(f"{i+1}番 近走指数(任意)", value=50.0, step=0.5, key=f"idxb_{i}")
        with c2:
            wt = st.number_input(f"{i+1}番 斤量/重量[kg]", value=700.0, step=5.0, min_value=500.0, max_value=1100.0, key=f"wt_{i}")
        with c3:
            stops = st.number_input(f"{i+1}番 障害停止回数(前走)", value=0, step=1, min_value=0, max_value=5, key=f"stp_{i}")
        idx_inputs.append(base_idx)
        chaku_inputs.append(["",""])  # 使わない
        extra_banei.append((wt, int(stops)))

# 出走フラグ（空欄=欠）
st.subheader("▼ 出走フラグ（数字=出走、空欄=欠）")
run_flags = [st.text_input(f"{i+1}番 出走（1=走る/空欄=欠）", key=f"run_{i}") for i in range(N_MAX)]

# =========================================
# ロジック
# =========================================

def convert_finish_to_score(values:list[str]):
    """着順2戦を0..1に正規化（前走0.35重み）"""
    scores = []
    for i, v in enumerate(values):
        v = str(v).strip()
        try:
            f = int(v)
            if 1 <= f <= 18:
                s = (19 - f) / 18.0
                if i == 1:
                    s *= 0.35
                scores.append(s)
        except ValueError:
            continue
    return round(sum(scores)/len(scores), 3) if scores else 0.0


def pace_course_adjust(style:str, surface:str, surface_state:str, distance:int, circle:int, stretch:int, turns:int, pace:str):
    """平地：距離×直線×馬場×ペース×脚質（簡易）。上限±0.06。"""
    d_norm = max(0.8, min(2.6, distance/1000))
    by_dist = {'逃': 0.02*(2.0-d_norm),'先': 0.01*(2.0-d_norm),'差': 0.01*(d_norm-1.4),'追': 0.02*(d_norm-1.4)}.get(style, 0.0)
    long_st = max(0, (stretch-250)/100)*0.01
    by_stretch = {'差': long_st, '追': long_st*1.2}.get(style, 0.0)
    bb = {'良':0.0, '稍重':0.01, '重':0.015, '不良':0.02}.get(surface_state, 0.0)
    by_baba = {'逃': bb, '先':bb*0.6, '差':-bb*0.6, '追':-bb}.get(style, 0.0)
    by_pace = {'前傾': {'逃':0.02,'先':0.01}, '後傾': {'差':0.015,'追':0.02}}.get(pace, {}).get(style, 0.0)
    total = by_dist + by_stretch + by_baba + by_pace
    return round(max(min(total, 0.06), -0.06), 3)


def banei_adjust(weight:float, stops:int, surface_state:str):
    """ばんえい：重量・障害停止・馬場状態の簡易調整。上限±0.08（ひな形）。"""
    # 重量（基準700kg）…重いほど厳しい
    by_w = -0.0008 * (weight - 700.0)
    # 停止回数ペナルティ
    by_s = -0.02 * max(stops, 0)
    # 馬場（重いほどパワー寄りで停止が出やすい想定。ここでは微負）
    bb = {'良':0.0, '稍重':-0.01, '重':-0.015, '不良':-0.02}.get(surface_state, 0.0)
    total = by_w + by_s + bb
    return round(max(min(total, 0.08), -0.08), 3)


def group_bonus_flat(rows, groups):
    """平地：脚質陣営別の平均で順位→幾何減衰で配分（総予算0.30）。"""
    if not rows:
        return {k:0.0 for k in RUN_STYLES}
    sums = {k:0.0 for k in RUN_STYLES}
    counts = {k:0 for k in RUN_STYLES}
    for row in rows:
        no, total = row[0], row[-1]
        g = groups.get(no)
        if g in sums:
            sums[g] += total
            counts[g] += 1
    adj = {k: (sums[k]/counts[k]) if counts[k] else -1e9 for k in RUN_STYLES}
    order = [k for k,_ in sorted(adj.items(), key=lambda x:x[1], reverse=True) if counts[k] > 0]
    r = 0.8
    weights = [r**i for i in range(len(order))]
    sw = sum(weights) if weights else 1.0
    budget = 0.30
    return {k: ((weights[order.index(k)]/sw)*budget if k in order else 0.0) for k in RUN_STYLES}

# =========================================
# 計算
# =========================================
active_idx = [i for i in range(N_MAX) if str(run_flags[i]).isdigit()]

rows = []
if mode == "平地(サラ)":
    # 着順補正
    fin_scores = [convert_finish_to_score(chaku_inputs[i]) if i in active_idx else 0.0 for i in range(N_MAX)]
    # スコア算出
    for i in active_idx:
        no = i+1
        style = horse_style.get(no, "差")
        base = idx_inputs[i]
        pf = pace_course_adjust(style, surface, surface_state, int(distance), int(circle), int(stretch), int(turns), pace_scn)
        total = base + fin_scores[i] + pf
        rows.append([no, style, base, fin_scores[i], pf, total])
else:
    # ばんえい簡易
    for i in active_idx:
        no = i+1
        base = idx_inputs[i]
        wt, stops = extra_banei[i]
        ba = banei_adjust(wt, stops, surface_state)
        total = base + ba
        rows.append([no, "-", base, 0.0, ba, total])

# 陣営ボーナス（平地のみ）
if mode == "平地(サラ)":
    groups = {i+1: (horse_style.get(i+1, None)) for i in range(N_MAX)}
    bonus_map = group_bonus_flat(rows, groups)
    rows2 = []
    for no, style, base, fin, pf, total in rows:
        gb = bonus_map.get(style, 0.0)
        rows2.append([no, style, base, fin, pf, gb, total+gb])
else:
    rows2 = [[no, style, base, fin, pf, 0.0, total] for (no, style, base, fin, pf, total) in rows]

# 表示
if rows2:
    cols = ["馬番","脚質","基準指数","着順/時計補正","コース/条件補正","陣営/群補正","合計スコア"]
    df = pd.DataFrame(rows2, columns=cols)
    st.markdown("### 📊 合計スコア順（β/ひな形）")
    st.dataframe(df.sort_values(by="合計スコア", ascending=False).reset_index(drop=True))
else:
    st.info("出走フラグが未入力です。数字を入れると計算します。")

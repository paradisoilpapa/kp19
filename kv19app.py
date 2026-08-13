# -*- coding: utf-8 -*-

from collections import Counter, defaultdict
from statistics import median
from typing import Dict, List, Tuple

import pandas as pd
import streamlit as st


st.set_page_config(page_title="ヴェロビ 3連複フォーメーション集計", layout="wide")
st.title("ヴェロビ 3連複フォーメーション集計｜v13.0r")
st.caption(
    "実フォーメーション、A～F、確定着順、3連複配当、消去候補を入力し、"
    "全体・10倍以上・10倍未満で比較します。"
)

UNIT_YEN = 100
ROLES = ("A", "B", "C", "D", "E", "F")
BASE_ROLES = ("A", "B", "C", "D", "E")

# 全レースで同時検証する候補。3連複として同じ7点になる型は統合。
FORMATION_PATTERNS: Dict[str, Tuple[Tuple[str, ...], Tuple[str, ...], Tuple[str, ...]]] = {
    "AB-ABC-ABCDE（現行）": (("A", "B"), ("A", "B", "C"), BASE_ROLES),
    "DE-CDE-ABCDE＝CD-CDE-ABCDE": (("D", "E"), ("C", "D", "E"), BASE_ROLES),
    "DE-ADE-ABCDE": (("D", "E"), ("A", "D", "E"), BASE_ROLES),
    "CD-BCD-ABCDE": (("C", "D"), ("B", "C", "D"), BASE_ROLES),
    "CD-ACD-ABCDE": (("C", "D"), ("A", "C", "D"), BASE_ROLES),
}

ZONES = {
    "全体": lambda payout: True,
    "10倍以上": lambda payout: payout >= 1000,
    "10倍未満": lambda payout: 0 < payout < 1000,
}


def normalize(value: str) -> str:
    return str(value or "").translate(
        str.maketrans({
            "０": "0", "１": "1", "２": "2", "３": "3", "４": "4",
            "５": "5", "６": "6", "７": "7", "８": "8", "９": "9",
            "－": "-", "ー": "-", "―": "-", "−": "-", "ｰ": "-",
            "，": ",", "、": ",",
        })
    ).replace(" ", "").replace("　", "")


def unique_chars(value: str) -> List[str]:
    out: List[str] = []
    for char in value:
        if char not in out:
            out.append(char)
    return out


def parse_finish(value: str) -> Tuple[List[str], str]:
    text = normalize(value).replace("-", "").replace("/", "").replace(",", "")
    if not text:
        return [], "確定着順が未入力です。"
    if not text.isdigit() or any(car not in "123456789" for car in text):
        return [], "確定着順は車番1～9で入力してください。"
    finish = unique_chars(text)
    if len(finish) != 3:
        return [], "確定着順は上位3車を重複なしで入力してください。"
    return finish, ""


def parse_formation(value: str) -> Tuple[List[Tuple[str, str, str]], str]:
    text = normalize(value)
    parts = text.split("-")
    if len(parts) != 3 or any(not part for part in parts):
        return [], "実フォーメーションは『52-523-52314』の形で入力してください。"
    if any(not part.isdigit() or any(car not in "123456789" for car in part) for part in parts):
        return [], "実フォーメーションは車番1～9で入力してください。"
    columns = [unique_chars(part) for part in parts]
    tickets = {
        tuple(sorted((a, b, c), key=int))
        for a in columns[0] for b in columns[1] for c in columns[2]
        if len({a, b, c}) == 3
    }
    if not tickets:
        return [], "有効な3連複買い目がありません。"
    return sorted(tickets, key=lambda x: tuple(map(int, x))), ""


def parse_delete_tickets(value: str) -> Tuple[List[Tuple[str, str, str]], str]:
    text = normalize(value)
    if not text:
        return [], ""
    tickets = set()
    for raw in text.replace("/", ",").split(","):
        if not raw:
            continue
        cars = raw.replace("-", "")
        if not cars.isdigit() or len(cars) != 3 or any(car not in "123456789" for car in cars):
            return [], "消去候補は『1-2-4,1-4-5』の形で入力してください。"
        if len(set(cars)) != 3:
            return [], "消去候補の各買い目は異なる3車にしてください。"
        tickets.add(tuple(sorted(cars, key=int)))
    return sorted(tickets, key=lambda x: tuple(map(int, x))), ""


def parse_roles(values: Dict[str, str]) -> Tuple[Dict[str, str], str]:
    roles = {role: normalize(values.get(role, "")) for role in ROLES}
    if any(len(car) != 1 or car not in "123456789" for car in roles.values()):
        return {}, "A～Fは各1車、車番1～9で入力してください。"
    if len({roles[role] for role in BASE_ROLES}) != 5:
        return {}, "A～Eは異なる5車にしてください。"
    if roles["F"] not in {roles["C"], roles["D"], roles["E"]}:
        return {}, "FはC・D・Eのいずれかと同じ車番を入力してください。"
    return roles, ""


def pattern_tickets(pattern, roles: Dict[str, str]) -> List[Tuple[str, str, str]]:
    tickets = {
        tuple(sorted((roles[a], roles[b], roles[c]), key=int))
        for a in pattern[0] for b in pattern[1] for c in pattern[2]
        if len({roles[a], roles[b], roles[c]}) == 3
    }
    return sorted(tickets, key=lambda x: tuple(map(int, x)))


def ticket_text(ticket: Tuple[str, str, str]) -> str:
    return "-".join(ticket)


def performance_row(label: str, races: List[Dict], ticket_getter) -> Dict:
    total_tickets = hits = returned = 0
    for race in races:
        tickets = ticket_getter(race)
        total_tickets += len(tickets)
        if race["finish_ticket"] in tickets:
            hits += 1
            returned += race["payout"]
    invested = total_tickets * UNIT_YEN
    return {
        "候補": label,
        "対象N": len(races),
        "総点数": total_tickets,
        "投資額": invested,
        "払戻合計": returned,
        "収支": returned - invested,
        "的中H": hits,
        "的中率%": round(hits * 100 / len(races), 1) if races else None,
        "平均配当": round(returned / hits, 1) if hits else None,
        "回収率%": round(returned * 100 / invested, 1) if invested else None,
    }


def role_rate_rows(races: List[Dict]) -> List[Dict]:
    rows = []
    for role in ROLES:
        c1 = c2 = c3 = 0
        for race in races:
            car = race["roles"][role]
            c1 += car == race["finish"][0]
            c2 += car == race["finish"][1]
            c3 += car == race["finish"][2]
        n = len(races)
        rows.append({
            "役割": role,
            "対象N": n,
            "1着回数": c1,
            "1着率%": round(c1 * 100 / n, 1) if n else None,
            "2着回数": c2,
            "2着率%": round(c2 * 100 / n, 1) if n else None,
            "3着回数": c3,
            "3着率%": round(c3 * 100 / n, 1) if n else None,
            "3着内回数": c1 + c2 + c3,
            "3着内率%": round((c1 + c2 + c3) * 100 / n, 1) if n else None,
        })
    return rows


def result_role_key(race: Dict) -> str:
    car_to_base = {car: role for role, car in race["roles"].items() if role in BASE_ROLES}
    labels = []
    for car in race["finish_ticket"]:
        role = car_to_base.get(car, f"車{car}")
        if car == race["roles"]["F"]:
            role += "(F)"
        labels.append(role)
    return "-".join(sorted(labels))


def combination_rows(races: List[Dict]) -> List[Dict]:
    grouped: Dict[str, List[int]] = defaultdict(list)
    for race in races:
        grouped[result_role_key(race)].append(race["payout"])
    total = len(races)
    rows = []
    for key, pays in grouped.items():
        rows.append({
            "役割3車": key,
            "出現回数": len(pays),
            "出現率%": round(len(pays) * 100 / total, 1) if total else None,
            "平均配当": round(sum(pays) / len(pays), 1),
            "中央値配当": median(pays),
            "最高配当": max(pays),
            "払戻合計": sum(pays),
        })
    return sorted(rows, key=lambda row: (-row["出現回数"], -row["平均配当"]))


def delete_row(races: List[Dict]) -> Dict:
    configured = [race for race in races if race["delete_tickets"]]
    total_points = sum(len(race["delete_tickets"]) for race in configured)
    hit_races = [race for race in configured if race["finish_ticket"] in race["delete_tickets"]]
    lost_return = sum(race["payout"] for race in hit_races)
    saved = total_points * UNIT_YEN
    return {
        "消去設定レースN": len(configured),
        "消去総点数": total_points,
        "消去候補的中H": len(hit_races),
        "レース的中率%": round(len(hit_races) * 100 / len(configured), 1) if configured else None,
        "1点的中率%": round(len(hit_races) * 100 / total_points, 2) if total_points else None,
        "仮想投資額": saved,
        "仮想払戻合計": lost_return,
        "仮想回収率%": round(lost_return * 100 / saved, 1) if saved else None,
        "消去で削減した投資額": saved,
        "消去で失った払戻額": lost_return,
        "消去の正味効果": saved - lost_return,
    }


tabs = st.tabs(["入力（最大100R）", "集計結果", "入力明細"])
races: List[Dict] = []

with tabs[0]:
    st.caption(
        "消去候補は『1-2-4,1-4-5』のようにカンマ区切りで入力します。"
        "配当0円の行はゾーン判定できないため集計対象外です。"
    )
    with st.form("race_input_form"):
        header = st.columns([0.45, 1.55] + [0.45] * 6 + [0.75, 0.8, 1.7])
        labels = ["R", "実フォーメーション", "A", "B", "C", "D", "E", "F", "着順", "配当", "消去候補"]
        for col, label in zip(header, labels):
            col.markdown(f"**{label}**")

        raw_rows = []
        for index in range(1, 101):
            cols = st.columns([0.45, 1.55] + [0.45] * 6 + [0.75, 0.8, 1.7])
            cols[0].write(str(index))
            formation = cols[1].text_input("実フォメ", key=f"formation_{index}", placeholder="52-523-52314", label_visibility="collapsed")
            role_values = {}
            for role_index, role in enumerate(ROLES, start=2):
                role_values[role] = cols[role_index].text_input(role, key=f"role_{role}_{index}", label_visibility="collapsed")
            finish = cols[8].text_input("着順", key=f"finish_{index}", placeholder="523", label_visibility="collapsed")
            payout = cols[9].number_input("配当", min_value=0, value=0, step=10, key=f"payout_{index}", label_visibility="collapsed")
            delete_text = cols[10].text_input("消去", key=f"delete_{index}", placeholder="1-2-4,1-4-5", label_visibility="collapsed")
            raw_rows.append({
                "R": str(index), "formation": formation, "roles": role_values,
                "finish": finish, "payout": int(payout), "delete": delete_text,
            })
        st.form_submit_button("入力を反映")

    for raw in raw_rows:
        has_input = any([
            raw["formation"].strip(), raw["finish"].strip(), raw["payout"] > 0,
            raw["delete"].strip(), *[value.strip() for value in raw["roles"].values()],
        ])
        if not has_input:
            continue
        actual_tickets, formation_error = parse_formation(raw["formation"])
        roles, role_error = parse_roles(raw["roles"])
        finish, finish_error = parse_finish(raw["finish"])
        delete_tickets, delete_error = parse_delete_tickets(raw["delete"])
        errors = [error for error in (formation_error, role_error, finish_error, delete_error) if error]
        if raw["payout"] <= 0:
            errors.append("3連複配当を入力してください。")
        if errors:
            st.warning(f"R{raw['R']}：" + " ".join(errors))
            continue
        finish_ticket = tuple(sorted(finish, key=int))
        races.append({
            "R": raw["R"],
            "formation": normalize(raw["formation"]),
            "actual_tickets": actual_tickets,
            "roles": roles,
            "finish": finish,
            "finish_ticket": finish_ticket,
            "payout": raw["payout"],
            "delete_tickets": delete_tickets,
        })


with tabs[1]:
    if not races:
        st.info("有効な入力レースがありません。")
    else:
        for zone_name, zone_filter in ZONES.items():
            zone_races = [race for race in races if zone_filter(race["payout"])]
            st.header(zone_name)
            st.caption(f"対象レース：{len(zone_races)}件")

            st.subheader("フォーメーション比較")
            compare_rows = [
                performance_row(
                    "実際の入力フォーメーション",
                    zone_races,
                    lambda race: race["actual_tickets"],
                )
            ]
            for label, pattern in FORMATION_PATTERNS.items():
                compare_rows.append(
                    performance_row(
                        label,
                        zone_races,
                        lambda race, p=pattern: pattern_tickets(p, race["roles"]),
                    )
                )
            compare_df = pd.DataFrame(compare_rows).sort_values(
                by=["回収率%", "収支", "的中率%"],
                ascending=[False, False, False],
                na_position="last",
            ).reset_index(drop=True)
            if zone_races:
                best = compare_df.iloc[0]
                st.success(
                    f"最善：{best['候補']}｜回収率 {best['回収率%']}%｜"
                    f"収支 {int(best['収支']):,}円｜的中率 {best['的中率%']}%"
                )
            st.dataframe(compare_df, use_container_width=True, hide_index=True)

            st.subheader("A～F 着内率")
            st.dataframe(pd.DataFrame(role_rate_rows(zone_races)), use_container_width=True, hide_index=True)

            st.subheader("確定着順の役割3車ゾーン")
            combo = combination_rows(zone_races)
            if combo:
                st.dataframe(pd.DataFrame(combo), use_container_width=True, hide_index=True)
            else:
                st.info("該当データがありません。")

            st.subheader("消去候補の成績")
            st.dataframe(pd.DataFrame([delete_row(zone_races)]), use_container_width=True, hide_index=True)
            st.divider()


with tabs[2]:
    if not races:
        st.info("有効な入力レースがありません。")
    else:
        detail_rows = []
        for race in races:
            actual_hit = race["finish_ticket"] in race["actual_tickets"]
            delete_hit = race["finish_ticket"] in race["delete_tickets"]
            detail_rows.append({
                "R": race["R"],
                "実フォーメーション": race["formation"],
                **race["roles"],
                "確定着順": "-".join(race["finish"]),
                "役割3車": result_role_key(race),
                "配当": race["payout"],
                "配当ゾーン": "10倍以上" if race["payout"] >= 1000 else "10倍未満",
                "実フォメ的中": "○" if actual_hit else "×",
                "消去候補": " / ".join(ticket_text(ticket) for ticket in race["delete_tickets"]),
                "消去候補的中": "○" if delete_hit else "×",
            })
        st.dataframe(
            pd.DataFrame(detail_rows), use_container_width=True, hide_index=True,
            height=max(120, 38 * (len(detail_rows) + 1)),
        )

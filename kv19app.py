# -*- coding: utf-8 -*-

from collections import defaultdict
from typing import Dict, List, Tuple

import pandas as pd
import streamlit as st


st.set_page_config(page_title="ヴェロビ 3連複フォーメーション復習", layout="wide")
st.title("ヴェロビ 3連複フォーメーション復習｜v12.0r")
st.caption(
    "3連複フォーメーション・確定着順・3連複配当だけを入力し、"
    "A～Eの着内率とフォーメーション別成績を累積集計します。"
)

ROLES = ("A", "B", "C", "D", "E")
UNIT_YEN = 100


def normalize_digits(value: str) -> str:
    return str(value or "").translate(
        str.maketrans(
            {
                "０": "0", "１": "1", "２": "2", "３": "3", "４": "4",
                "５": "5", "６": "6", "７": "7", "８": "8", "９": "9",
                "－": "-", "ー": "-", "―": "-", "−": "-", "ｰ": "-",
            }
        )
    ).replace(" ", "").replace("　", "")


def unique_chars(value: str) -> List[str]:
    out: List[str] = []
    for char in value:
        if char not in out:
            out.append(char)
    return out


def parse_finish(value: str) -> Tuple[List[str], str]:
    normalized = normalize_digits(value).replace("-", "").replace("/", "").replace(",", "")
    if not normalized:
        return [], ""
    if not normalized.isdigit() or any(char not in "123456789" for char in normalized):
        return [], "着順には車番1～9を入力してください。"
    finish = unique_chars(normalized)
    if len(finish) != 3:
        return [], "着順は上位3車を重複なしで入力してください。"
    return finish, ""


def parse_formation(value: str) -> Tuple[List[List[str]], List[Tuple[str, str, str]], str]:
    normalized = normalize_digits(value)
    if not normalized:
        return [], [], ""

    parts = normalized.split("-")
    if len(parts) != 3 or any(not part for part in parts):
        return [], [], "『72-721-72514』のように3列をハイフンで区切ってください。"
    if any(not part.isdigit() for part in parts):
        return [], [], "フォーメーションには車番の数字だけを入力してください。"
    if any(any(char not in "123456789" for char in part) for part in parts):
        return [], [], "車番は1～9で入力してください。"

    columns = [unique_chars(part) for part in parts]
    if len(columns[0]) < 2:
        return [], [], "1列目にはA・Bとなる2車以上が必要です。"
    if len(columns[1]) < 3:
        return [], [], "2列目にはCを判定できる3車以上が必要です。"

    tickets = set()
    for first in columns[0]:
        for second in columns[1]:
            for third in columns[2]:
                if len({first, second, third}) == 3:
                    tickets.add(tuple(sorted((first, second, third), key=int)))

    ticket_list = sorted(tickets, key=lambda ticket: tuple(int(car) for car in ticket))
    if not ticket_list:
        return [], [], "有効な3連複買い目がありません。"
    return columns, ticket_list, ""


def derive_roles(columns: List[List[str]]) -> Tuple[Dict[str, str], str]:
    """
    A・B：1列目の先頭2車
    C：2列目の3番目
    D・E：3列目からA・B・Cを除いた残り順
    """
    if len(columns) != 3 or len(columns[0]) < 2 or len(columns[1]) < 3:
        return {}, "A～Eを判定できないフォーメーションです。"

    roles = {
        "A": columns[0][0],
        "B": columns[0][1],
        "C": columns[1][2],
    }
    if len(set(roles.values())) != 3:
        return {}, "A・B・Cが同じ車番になっています。"

    used = set(roles.values())
    remaining = [car for car in columns[2] if car not in used]
    if len(remaining) < 2:
        return {}, "3列目からA・B・Cを除いたあとに、D・Eとなる2車が必要です。"

    roles["D"] = remaining[0]
    roles["E"] = remaining[1]
    if len(set(roles.values())) != 5:
        return {}, "A～Eを5台の異なる車番として判定できません。"
    return roles, ""


def role_formation(columns: List[List[str]], roles: Dict[str, str]) -> str:
    car_to_role = {car: role for role, car in roles.items()}
    converted: List[str] = []
    for column in columns:
        converted.append("".join(car_to_role.get(car, f"車{car}") for car in column))
    return "-".join(converted)


def ticket_text(ticket: Tuple[str, str, str]) -> str:
    return "-".join(ticket)


def blank_performance() -> Dict[str, int]:
    return {"N": 0, "KSUM": 0, "H": 0, "SUM": 0}


def blank_role_record() -> Dict[str, int]:
    return {"N": 0, "C1": 0, "C2": 0, "C3": 0}


def add_performance(target: Dict[str, int], source: Dict[str, int]) -> None:
    for key in ("N", "KSUM", "H", "SUM"):
        target[key] += int(source.get(key, 0))


def add_role_record(target: Dict[str, int], source: Dict[str, int]) -> None:
    for key in ("N", "C1", "C2", "C3"):
        target[key] += int(source.get(key, 0))


def performance_row(label: str, record: Dict[str, int]) -> Dict:
    races = int(record.get("N", 0))
    tickets = int(record.get("KSUM", 0))
    hits = int(record.get("H", 0))
    returned = int(record.get("SUM", 0))
    invested = tickets * UNIT_YEN
    return {
        "区分": label,
        "対象レースN": races,
        "総点数": tickets,
        "投資額": invested,
        "払戻合計": returned,
        "収支": returned - invested,
        "的中H": hits,
        "的中率%": round(hits * 100.0 / races, 1) if races else None,
        "平均配当": round(returned / hits, 1) if hits else None,
        "回収率%": round(returned * 100.0 / invested, 1) if invested else None,
    }


tabs = st.tabs(["日次入力", "前日までの累積", "集計結果"])

daily_rows: List[Dict] = []
manual_performance = blank_performance()
manual_roles: Dict[str, Dict[str, int]] = {role: blank_role_record() for role in ROLES}


with tabs[0]:
    st.subheader("日次入力（最大36R）")
    st.caption(
        "例：フォーメーション『72-721-72514』、着順『754』、3連複配当『2810』。"
        "配当は100円当たりの確定払戻額を入力してください。"
    )

    with st.form("daily_form"):
        header = st.columns([0.7, 3.0, 1.3, 1.4])
        header[0].markdown("**R**")
        header[1].markdown("**3連複フォーメーション**")
        header[2].markdown("**確定着順3車**")
        header[3].markdown("**3連複配当**")

        inputs = []
        for index in range(1, 37):
            c1, c2, c3, c4 = st.columns([0.7, 3.0, 1.3, 1.4])
            race = c1.text_input("R", value=str(index), key=f"race_{index}", label_visibility="collapsed")
            formation = c2.text_input(
                "フォーメーション",
                value="",
                key=f"formation_{index}",
                placeholder="72-721-72514",
                label_visibility="collapsed",
            )
            finish = c3.text_input(
                "着順",
                value="",
                key=f"finish_{index}",
                placeholder="754",
                label_visibility="collapsed",
            )
            payout = c4.number_input(
                "3連複配当",
                min_value=0,
                value=0,
                step=10,
                key=f"payout_{index}",
                label_visibility="collapsed",
            )
            inputs.append({"race": race, "formation": formation, "finish": finish, "payout": int(payout)})

        submitted = st.form_submit_button("日次入力を反映")

    has_daily_values = any(
        item["formation"].strip() or item["finish"].strip() or item["payout"] > 0
        for item in inputs
    )
    if submitted or has_daily_values:
        for item in inputs:
            if not any([item["formation"].strip(), item["finish"].strip(), item["payout"] > 0]):
                continue

            columns, tickets, formation_error = parse_formation(item["formation"])
            finish, finish_error = parse_finish(item["finish"])
            roles, role_error = derive_roles(columns) if not formation_error else ({}, "")

            errors = [error for error in (formation_error, finish_error, role_error) if error]
            if not item["formation"].strip():
                errors.append("3連複フォーメーションが未入力です。")
            if not item["finish"].strip():
                errors.append("確定着順が未入力です。")
            if errors:
                st.warning(f"R{item['race']}：" + " ".join(errors))
                continue

            finish_ticket = tuple(sorted(finish, key=int))
            hit = finish_ticket in tickets
            returned = item["payout"] if hit else 0
            role_by_car = {car: role for role, car in roles.items()}
            finish_roles = [role_by_car.get(car, "対象外") for car in finish]

            daily_rows.append(
                {
                    "R": item["race"],
                    "フォーメーション": normalize_digits(item["formation"]),
                    "役割型": role_formation(columns, roles),
                    "A": roles["A"], "B": roles["B"], "C": roles["C"],
                    "D": roles["D"], "E": roles["E"],
                    "確定着順": "-".join(finish),
                    "着順役割": "-".join(finish_roles),
                    "買い目数": len(tickets),
                    "買い目": " / ".join(ticket_text(ticket) for ticket in tickets),
                    "的中": "○" if hit else "×",
                    "投資額": len(tickets) * UNIT_YEN,
                    "払戻額": returned,
                    "収支": returned - len(tickets) * UNIT_YEN,
                    "_hit": hit,
                    "_payout": returned,
                    "_roles": roles,
                    "_finish": finish,
                }
            )


with tabs[1]:
    st.subheader("前日までの累積")
    st.caption("前回の集計結果を転記すると、今日入力分と合算します。")

    with st.form("previous_form"):
        st.markdown("### 3連複フォーメーション成績")
        pcols = st.columns(4)
        prev_n = pcols[0].number_input("対象レースN", min_value=0, value=0)
        prev_ksum = pcols[1].number_input("総点数", min_value=0, value=0)
        prev_sum = pcols[2].number_input("払戻合計", min_value=0, value=0, step=10)
        prev_h = pcols[3].number_input("的中H", min_value=0, value=0)

        st.markdown("### A～E着順回数")
        head = st.columns([1.0, 1.0, 1.0, 1.0, 1.0])
        for col, label in zip(head, ("役割", "対象N", "1着", "2着", "3着")):
            col.markdown(f"**{label}**")

        role_inputs = []
        for role in ROLES:
            cols = st.columns([1.0, 1.0, 1.0, 1.0, 1.0])
            cols[0].write(role)
            n = cols[1].number_input("N", min_value=0, value=0, key=f"prev_{role}_N", label_visibility="collapsed")
            c1 = cols[2].number_input("1着", min_value=0, value=0, key=f"prev_{role}_C1", label_visibility="collapsed")
            c2 = cols[3].number_input("2着", min_value=0, value=0, key=f"prev_{role}_C2", label_visibility="collapsed")
            c3 = cols[4].number_input("3着", min_value=0, value=0, key=f"prev_{role}_C3", label_visibility="collapsed")
            role_inputs.append((role, int(n), int(c1), int(c2), int(c3)))

        previous_submitted = st.form_submit_button("前日までの累積を反映")

    has_previous_values = any([prev_n, prev_ksum, prev_sum, prev_h]) or any(
        any([n, c1, c2, c3]) for _, n, c1, c2, c3 in role_inputs
    )
    if previous_submitted or has_previous_values:
        manual_performance = {
            "N": int(prev_n), "KSUM": int(prev_ksum), "H": int(prev_h), "SUM": int(prev_sum)
        }
        for role, n, c1, c2, c3 in role_inputs:
            manual_roles[role] = {"N": n, "C1": c1, "C2": c2, "C3": c3}


daily_performance = blank_performance()
daily_role_records: Dict[str, Dict[str, int]] = {role: blank_role_record() for role in ROLES}
by_formation: Dict[str, Dict[str, int]] = defaultdict(blank_performance)

for row in daily_rows:
    daily_performance["N"] += 1
    daily_performance["KSUM"] += int(row["買い目数"])
    if row["_hit"]:
        daily_performance["H"] += 1
        daily_performance["SUM"] += int(row["_payout"])

    form_record = by_formation[row["役割型"]]
    form_record["N"] += 1
    form_record["KSUM"] += int(row["買い目数"])
    if row["_hit"]:
        form_record["H"] += 1
        form_record["SUM"] += int(row["_payout"])

    finish = row["_finish"]
    roles = row["_roles"]
    for role in ROLES:
        record = daily_role_records[role]
        record["N"] += 1
        car = roles[role]
        if car == finish[0]:
            record["C1"] += 1
        elif car == finish[1]:
            record["C2"] += 1
        elif car == finish[2]:
            record["C3"] += 1

total_performance = blank_performance()
add_performance(total_performance, manual_performance)
add_performance(total_performance, daily_performance)

total_role_records: Dict[str, Dict[str, int]] = {role: blank_role_record() for role in ROLES}
for role in ROLES:
    add_role_record(total_role_records[role], manual_roles[role])
    add_role_record(total_role_records[role], daily_role_records[role])


with tabs[2]:
    st.subheader("3連複フォーメーション成績")
    summary = pd.DataFrame(
        [
            performance_row("今日入力", daily_performance),
            performance_row("全体累積", total_performance),
        ]
    )
    st.dataframe(summary, use_container_width=True, hide_index=True)

    st.markdown("### A～E 着内率")
    role_rows = []
    for role in ROLES:
        record = total_role_records[role]
        n = int(record["N"])
        c1 = int(record["C1"])
        c2 = int(record["C2"])
        c3 = int(record["C3"])
        role_rows.append(
            {
                "役割": role,
                "対象N": n,
                "1着回数": c1,
                "2着回数": c2,
                "3着回数": c3,
                "1着率%": round(c1 * 100.0 / n, 1) if n else None,
                "2着率%": round(c2 * 100.0 / n, 1) if n else None,
                "3着率%": round(c3 * 100.0 / n, 1) if n else None,
                "3着内率%": round((c1 + c2 + c3) * 100.0 / n, 1) if n else None,
            }
        )
    st.dataframe(pd.DataFrame(role_rows), use_container_width=True, hide_index=True)

    st.markdown("### フォーメーション型別成績（今日入力）")
    if by_formation:
        formation_rows = [performance_row(label, record) for label, record in by_formation.items()]
        formation_df = pd.DataFrame(formation_rows).sort_values(
            by=["回収率%", "払戻合計"], ascending=[False, False], na_position="last"
        )
        st.dataframe(formation_df, use_container_width=True, hide_index=True)
    else:
        st.info("本日の入力はありません。")

    st.markdown("### レース別明細")
    if daily_rows:
        visible_keys = [
            "R", "フォーメーション", "役割型", "A", "B", "C", "D", "E",
            "確定着順", "着順役割", "買い目数", "買い目", "的中",
            "投資額", "払戻額", "収支",
        ]
        details = pd.DataFrame([{key: row[key] for key in visible_keys} for row in daily_rows])
        st.dataframe(
            details,
            use_container_width=True,
            hide_index=True,
            height=max(120, 38 * (len(details) + 1)),
        )
        missing_payout = [str(row["R"]) for row in daily_rows if row["_hit"] and row["_payout"] <= 0]
        if missing_payout:
            st.warning("的中していますが配当が未入力です：R" + "、R".join(missing_payout))
    else:
        st.info("本日の入力はありません。")

    st.divider()
    st.markdown("### 次回引継ぎ用")
    st.caption("次回は、この数値を『前日までの累積』へ転記してください。")
    st.dataframe(pd.DataFrame([performance_row("全体累積", total_performance)]), use_container_width=True, hide_index=True)
    carry_roles = pd.DataFrame(
        [
            {
                "役割": role,
                "対象N": total_role_records[role]["N"],
                "1着": total_role_records[role]["C1"],
                "2着": total_role_records[role]["C2"],
                "3着": total_role_records[role]["C3"],
            }
            for role in ROLES
        ]
    )
    st.dataframe(carry_roles, use_container_width=True, hide_index=True)

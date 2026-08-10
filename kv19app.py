# -*- coding: utf-8 -*-

from typing import Dict, List, Tuple

import pandas as pd
import streamlit as st


st.set_page_config(page_title="ヴェロビ 3連複フォーメーション復習", layout="wide")
st.title("ヴェロビ 3連複フォーメーション比較｜v12.2r")
st.caption(
    "3連複フォーメーション・確定着順・3連複配当だけを入力し、"
    "全レースに全候補フォーメーションを当てて、最善の型を比較します。"
)

ROLES = ("A", "B", "C", "D", "E")
UNIT_YEN = 100

# 比較対象。全候補を全入力レースで仮想購入する。
FORMATION_PATTERNS: Dict[str, Tuple[Tuple[str, ...], Tuple[str, ...], Tuple[str, ...]]] = {
    "AB-ABC-ABCDE（現行）": (("A", "B"), ("A", "B", "C"), ("A", "B", "C", "D", "E")),
    "DE-CDE-ABCDE ＝ CD-CDE-ABCDE（同一7点）": (("D", "E"), ("C", "D", "E"), ("A", "B", "C", "D", "E")),
    "DE-ADE-ABCDE": (("D", "E"), ("A", "D", "E"), ("A", "B", "C", "D", "E")),
    "CD-BCD-ABCDE": (("C", "D"), ("B", "C", "D"), ("A", "B", "C", "D", "E")),
    "CD-ACD-ABCDE": (("C", "D"), ("A", "C", "D"), ("A", "B", "C", "D", "E")),
}


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


def ticket_text(ticket: Tuple[str, str, str]) -> str:
    return "-".join(ticket)


def pattern_tickets(
    pattern: Tuple[Tuple[str, ...], Tuple[str, ...], Tuple[str, ...]],
    roles: Dict[str, str],
) -> List[Tuple[str, str, str]]:
    """役割フォーメーションを実車番の重複なし3連複買い目へ展開する。"""
    tickets = set()
    for first_role in pattern[0]:
        for second_role in pattern[1]:
            for third_role in pattern[2]:
                cars = (roles[first_role], roles[second_role], roles[third_role])
                if len(set(cars)) == 3:
                    tickets.add(tuple(sorted(cars, key=int)))
    return sorted(tickets, key=lambda ticket: tuple(int(car) for car in ticket))


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
manual_candidate_performance: Dict[str, Dict[str, int]] = {
    label: blank_performance() for label in FORMATION_PATTERNS
}
manual_roles: Dict[str, Dict[str, int]] = {role: blank_role_record() for role in ROLES}


with tabs[0]:
    st.subheader("日次入力（最大100R）")
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
        for index in range(1, 101):
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
            role_by_car = {car: role for role, car in roles.items()}
            finish_roles = [role_by_car.get(car, "対象外") for car in finish]

            daily_rows.append(
                {
                    "R": item["race"],
                    "フォーメーション": normalize_digits(item["formation"]),
                    "A": roles["A"], "B": roles["B"], "C": roles["C"],
                    "D": roles["D"], "E": roles["E"],
                    "確定着順": "-".join(finish),
                    "着順役割": "-".join(finish_roles),
                    "確定配当": int(item["payout"]),
                    "_roles": roles,
                    "_finish": finish,
                    "_finish_ticket": finish_ticket,
                    "_race_payout": int(item["payout"]),
                }
            )


with tabs[1]:
    st.subheader("前日までの累積")
    st.caption("前回の集計結果を転記すると、今日入力分と合算します。")

    with st.form("previous_form"):
        st.markdown("### 候補フォーメーション別成績")
        st.caption("次回引継ぎ用表のN・総点数・払戻合計・的中Hを候補ごとに転記します。")
        phead = st.columns([2.3, 0.8, 0.9, 1.1, 0.8])
        for col, label in zip(phead, ("候補", "N", "総点数", "払戻合計", "的中H")):
            col.markdown(f"**{label}**")

        candidate_inputs = []
        for candidate_index, label in enumerate(FORMATION_PATTERNS, start=1):
            pcols = st.columns([2.3, 0.8, 0.9, 1.1, 0.8])
            pcols[0].write(label)
            n = pcols[1].number_input("N", min_value=0, value=0, key=f"prev_candidate_{candidate_index}_N", label_visibility="collapsed")
            ksum = pcols[2].number_input("総点数", min_value=0, value=0, key=f"prev_candidate_{candidate_index}_KSUM", label_visibility="collapsed")
            payout_sum = pcols[3].number_input("払戻合計", min_value=0, value=0, step=10, key=f"prev_candidate_{candidate_index}_SUM", label_visibility="collapsed")
            hits = pcols[4].number_input("的中H", min_value=0, value=0, key=f"prev_candidate_{candidate_index}_H", label_visibility="collapsed")
            candidate_inputs.append((label, int(n), int(ksum), int(payout_sum), int(hits)))

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

    has_previous_values = any(
        any([n, ksum, payout_sum, hits])
        for _, n, ksum, payout_sum, hits in candidate_inputs
    ) or any(
        any([n, c1, c2, c3]) for _, n, c1, c2, c3 in role_inputs
    )
    if previous_submitted or has_previous_values:
        for label, n, ksum, payout_sum, hits in candidate_inputs:
            manual_candidate_performance[label] = {
                "N": n, "KSUM": ksum, "H": hits, "SUM": payout_sum
            }
        for role, n, c1, c2, c3 in role_inputs:
            manual_roles[role] = {"N": n, "C1": c1, "C2": c2, "C3": c3}


daily_role_records: Dict[str, Dict[str, int]] = {role: blank_role_record() for role in ROLES}
daily_candidate_performance: Dict[str, Dict[str, int]] = {
    label: blank_performance() for label in FORMATION_PATTERNS
}
candidate_race_results: List[Dict] = []

for row in daily_rows:
    finish = row["_finish"]
    roles = row["_roles"]

    # 全候補を全レースで必ず仮想購入する。外れもN・投資点数へ含める。
    for label, pattern in FORMATION_PATTERNS.items():
        tickets = pattern_tickets(pattern, roles)
        hit = row["_finish_ticket"] in tickets
        returned = int(row["_race_payout"]) if hit else 0

        record = daily_candidate_performance[label]
        record["N"] += 1
        record["KSUM"] += len(tickets)
        if hit:
            record["H"] += 1
            record["SUM"] += returned

        candidate_race_results.append({
            "R": row["R"],
            "候補": label,
            "買い目数": len(tickets),
            "買い目": " / ".join(ticket_text(ticket) for ticket in tickets),
            "的中": "○" if hit else "×",
            "投資額": len(tickets) * UNIT_YEN,
            "払戻額": returned,
            "収支": returned - len(tickets) * UNIT_YEN,
        })

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

total_candidate_performance: Dict[str, Dict[str, int]] = {
    label: blank_performance() for label in FORMATION_PATTERNS
}
for label in FORMATION_PATTERNS:
    add_performance(total_candidate_performance[label], manual_candidate_performance[label])
    add_performance(total_candidate_performance[label], daily_candidate_performance[label])

total_role_records: Dict[str, Dict[str, int]] = {role: blank_role_record() for role in ROLES}
for role in ROLES:
    add_role_record(total_role_records[role], manual_roles[role])
    add_role_record(total_role_records[role], daily_role_records[role])


with tabs[2]:
    st.subheader("全候補フォーメーション比較｜全レース集計")
    comparison_rows = [
        performance_row(label, total_candidate_performance[label])
        for label in FORMATION_PATTERNS
    ]
    comparison_df = pd.DataFrame(comparison_rows).sort_values(
        by=["回収率%", "収支", "的中率%"],
        ascending=[False, False, False],
        na_position="last",
    ).reset_index(drop=True)

    if not comparison_df.empty and int(comparison_df.iloc[0]["対象レースN"] or 0) > 0:
        best = comparison_df.iloc[0]
        st.success(
            f"現時点の最善フォーメーション：{best['区分']}｜"
            f"回収率 {best['回収率%']}%｜収支 {int(best['収支']):,}円｜"
            f"的中率 {best['的中率%']}%"
        )
    st.dataframe(comparison_df, use_container_width=True, hide_index=True)
    st.caption("すべての候補について、外れを含む全入力レースを対象N・投資額に含めています。")

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

    st.markdown("### 入力レース明細")
    if daily_rows:
        visible_keys = [
            "R", "フォーメーション", "A", "B", "C", "D", "E",
            "確定着順", "着順役割", "確定配当",
        ]
        details = pd.DataFrame([{key: row[key] for key in visible_keys} for row in daily_rows])
        st.dataframe(
            details,
            use_container_width=True,
            hide_index=True,
            height=max(120, 38 * (len(details) + 1)),
        )
        races_hit_by_any = {
            str(result["R"]) for result in candidate_race_results if result["的中"] == "○"
        }
        missing_payout = [
            str(row["R"]) for row in daily_rows
            if str(row["R"]) in races_hit_by_any and int(row["_race_payout"]) <= 0
        ]
        if missing_payout:
            st.warning("的中していますが配当が未入力です：R" + "、R".join(missing_payout))
    else:
        st.info("本日の入力はありません。")

    st.divider()
    st.markdown("### 次回引継ぎ用")
    st.caption("次回は、この数値を『前日までの累積』へ転記してください。")
    st.dataframe(comparison_df, use_container_width=True, hide_index=True)
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

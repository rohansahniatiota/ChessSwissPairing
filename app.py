import streamlit as st
import pandas as pd
import json
from collections import defaultdict
from itertools import combinations

st.set_page_config("Swiss Chess Tournament Manager", layout="wide")

# ==========================================================
# Session State
# ==========================================================
if "players" not in st.session_state:
    st.session_state.players = {}

if "rounds" not in st.session_state:
    st.session_state.rounds = []

if "pair_history" not in st.session_state:
    st.session_state.pair_history = set()

if "round_number" not in st.session_state:
    st.session_state.round_number = 0


# ==========================================================
# Core Helpers
# ==========================================================
def add_player(name, rating):
    pid = len(st.session_state.players) + 1
    st.session_state.players[pid] = {
        "id": pid,
        "name": name,
        "rating": rating,
        "score": 0.0,
        "colors": [],
        "opponents": [],
        "results": {},
        "bye": False
    }



def standings():
    if not st.session_state.players:
        return pd.DataFrame(
            columns=["name", "rating", "score", "buchholz", "sonneborn"]
        )

    df = pd.DataFrame(st.session_state.players.values())

    # ---- SAFETY DEFAULTS ----
    if "opponents" not in df.columns:
        df["opponents"] = [[] for _ in range(len(df))]
    if "results" not in df.columns:
        df["results"] = [{} for _ in range(len(df))]

    # ---- BUCHHOLZ ----
    df["buchholz"] = df["opponents"].apply(
        lambda ops: sum(
            st.session_state.players[o]["score"]
            for o in ops
            if o in st.session_state.players
        )
    )

    # ---- SONNEBORN-BERGER ----
    def sonneborn(row):
        total = 0
        for opp_id, res in row["results"].items():
            if opp_id in st.session_state.players:
                total += st.session_state.players[opp_id]["score"] * res
        return total

    df["sonneborn"] = df.apply(sonneborn, axis=1)

    return df.sort_values(


def choose_colors(p1, p2):
    c1 = st.session_state.players[p1]["colors"]
    c2 = st.session_state.players[p2]["colors"]

    if c1.count("W") > c1.count("B"):
        return p2, p1
    if c2.count("W") > c2.count("B"):
        return p1, p2
    return p1, p2


def swiss_pair():
    players = standings()["id"].tolist()
    used = set()
    pairings = []

    # Bye handling
    if len(players) % 2 == 1:
        for pid in reversed(players):
            p = st.session_state.players[pid]
            if not p["bye"]:
                p["score"] += 1
                p["bye"] = True
                pairings.append((pid, None))
                used.add(pid)
                break

    # Score groups
    score_groups = defaultdict(list)
    for pid in players:
        if pid not in used:
            score_groups[st.session_state.players[pid]["score"]].append(pid)

    for score in sorted(score_groups.keys(), reverse=True):
        group = score_groups[score]
        while len(group) >= 2:
            p1 = group.pop(0)
            for p2 in group:
                if p2 not in st.session_state.players[p1]["opponents"]:
                    w, b = choose_colors(p1, p2)
                    pairings.append((w, b))
                    group.remove(p2)
                    used.update({p1, p2})
                    break

    return pairings


def apply_results(results):
    for w, b, r in results:
        if b is None:
            continue

        st.session_state.players[w]["colors"].append("W")
        st.session_state.players[b]["colors"].append("B")

        st.session_state.players[w]["opponents"].append(b)
        st.session_state.players[b]["opponents"].append(w)

        if r == "1-0":
            st.session_state.players[w]["score"] += 1
            st.session_state.players[w]["results"][b] = 1
            st.session_state.players[b]["results"][w] = 0
        elif r == "0-1":
            st.session_state.players[b]["score"] += 1
            st.session_state.players[w]["results"][b] = 0
            st.session_state.players[b]["results"][w] = 1
        else:
            st.session_state.players[w]["score"] += 0.5
            st.session_state.players[b]["score"] += 0.5
            st.session_state.players[w]["results"][b] = 0.5
            st.session_state.players[b]["results"][w] = 0.5


# ==========================================================
# UI
# ==========================================================
st.title("♟ Swiss Chess Tournament Manager (Professional)")

tabs = st.tabs(["Players", "Rounds", "Standings", "Save / Load"])

# ---------------- Players ----------------
with tabs[0]:
    st.subheader("Add Players")
    c1, c2, c3 = st.columns([4, 2, 1])
    name = c1.text_input("Player Name")
    rating = c2.number_input("Rating", 0, 3000, 1200)
    if c3.button("Add"):
        if name:
            add_player(name, rating)

    if st.session_state.players:
        st.dataframe(
            pd.DataFrame(st.session_state.players.values())[
                ["id", "name", "rating", "score"]
            ],
            use_container_width=True
        )

# ---------------- Rounds ----------------
with tabs[1]:
    if len(st.session_state.players) < 2:
        st.warning("Add at least 2 players")
    else:
        if st.button("Generate Next Round"):
            st.session_state.round_number += 1
            st.session_state.rounds.append(swiss_pair())

        if st.session_state.rounds:
            st.markdown(f"### Round {st.session_state.round_number}")
            results = []
            for i, (w, b) in enumerate(st.session_state.rounds[-1]):
                if b is None:
                    st.write(f"**{st.session_state.players[w]['name']}** receives BYE")
                    continue

                c1, c2, c3 = st.columns([3, 3, 2])
                c1.write(f"⚪ {st.session_state.players[w]['name']}")
                c2.write(f"⚫ {st.session_state.players[b]['name']}")
                res = c3.selectbox("Result", ["1-0", "½-½", "0-1"], key=i)
                results.append((w, b, res))

            if st.button("Submit Results"):
                apply_results(results)
                st.success("Results recorded")

# ---------------- Standings ----------------
with tabs[2]:
    st.subheader("Standings")
    df = standings()
    if df.empty:
        st.info("No rounds played yet.")
    else:
        st.dataframe(
            df[["name", "rating", "score", "buchholz", "sonneborn"]],
            use_container_width=True
        )


    csv = df.to_csv(index=False).encode()
    st.download_button("Export Standings CSV", csv, "standings.csv")

# ---------------- Save / Load ----------------
with tabs[3]:
    st.subheader("Save / Load Tournament")

    if st.button("Save Tournament"):
        data = {
            "players": st.session_state.players,
            "rounds": st.session_state.rounds,
            "round_number": st.session_state.round_number
        }
        st.download_button(
            "Download JSON",
            json.dumps(data, indent=2),
            "tournament.json"
        )

    uploaded = st.file_uploader("Load Tournament JSON")
    if uploaded:
        data = json.load(uploaded)
        st.session_state.players = data["players"]
        st.session_state.rounds = data["rounds"]
        st.session_state.round_number = data["round_number"]
        st.success("Tournament loaded successfully")

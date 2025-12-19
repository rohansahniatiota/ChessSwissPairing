import streamlit as st
import pandas as pd
import json
from collections import defaultdict
from itertools import combinations

st.set_page_config("Swiss Chess Tournament Manager", layout="wide")
if "tournament" not in st.session_state:
    st.session_state.tournament = {
        "name": "Untitled Tournament",
        "rounds": 0
    }

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
def add_player(name, rating, gender, age):
    pid = len(st.session_state.players) + 1
    st.session_state.players[pid] = {
        "id": pid,
        "name": name,
        "rating": rating,
        "gender": gender,
        "age": age,
        "score": 0.0,
        "colors": [],
        "opponents": [],
        "results": {},
        "bye": False
    }



def standings(final=False):
    df = pd.DataFrame(st.session_state.players.values())

    if df.empty:
        return df

    df["buchholz"] = df["opponents"].apply(
        lambda ops: sum(st.session_state.players[o]["score"] for o in ops)
    )

    df["sonneborn"] = df.apply(
        lambda r: sum(
            st.session_state.players[o]["score"] * r["results"].get(o, 0)
            for o in r["opponents"]
        ),
        axis=1
    )

    # Direct encounter
    def direct(row):
        score = 0
        for o, r in row["results"].items():
            score += r
        return score

    df["direct"] = df.apply(direct, axis=1)

    order = ["score", "buchholz", "sonneborn"]
    if final:
        order.append("direct")
    order.append("rating")

    return df.sort_values(
        by=order,
        ascending=False
    ).reset_index(drop=True)



def choose_colors(p1, p2):
    # HARD CHECK: no repeat pairing
    if p2 in st.session_state.players[p1]["opponents"]:
        raise ValueError("Repeat pairing detected")

    c1 = st.session_state.players[p1]["colors"]
    c2 = st.session_state.players[p2]["colors"]

    # Balance colors
    if c1.count("W") > c1.count("B"):
        return p2, p1
    if c2.count("W") > c2.count("B"):
        return p1, p2

    return p1, p2



def swiss_pair():
    players_sorted = standings()["id"].tolist()
    unpaired = players_sorted.copy()
    pairings = []

    # ---------------- BYE ----------------
    if len(unpaired) % 2 == 1:
        for pid in reversed(unpaired):
            if not st.session_state.players[pid]["bye"]:
                st.session_state.players[pid]["bye"] = True
                st.session_state.players[pid]["score"] += 1
                pairings.append((pid, None))
                unpaired.remove(pid)
                break

    # ---------------- PAIRING ----------------
    while len(unpaired) >= 2:
        p1 = unpaired.pop(0)
        found = False

        for p2 in unpaired:
            if p2 not in st.session_state.players[p1]["opponents"]:
                w, b = choose_colors(p1, p2)
                pairings.append((w, b))
                unpaired.remove(p2)
                found = True
                break

        # FORCE PAIR ONLY IF NO REPEAT EXISTS
        if not found:
            raise RuntimeError(
                f"No valid pairing possible for {st.session_state.players[p1]['name']}"
            )

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
    st.subheader("Tournament Details")
    st.session_state.tournament["name"] = st.text_input(
        "Tournament Name",
        st.session_state.tournament["name"]
    )

    st.divider()
    st.subheader("Add Player")

    c1, c2, c3, c4, c5 = st.columns([3, 2, 2, 1, 1])
    name = c1.text_input("Name")
    rating = c2.number_input("Rating", 0, 3000, 1200)
    gender = c3.selectbox("Gender", ["Male", "Female", "Other"])
    age = c4.number_input("Age", 5, 100, 18)

    if c5.button("Add"):
        if name:
            add_player(name, rating, gender, age)

    if st.session_state.players:
        st.dataframe(
            pd.DataFrame(st.session_state.players.values())[
                ["name", "rating", "gender", "age", "score"]
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
    if st.button("Finalize Tournament"):
        st.success("Final standings calculated with tie-breaks")
        final_df = standings(final=True)
        st.dataframe(
            final_df[
                ["name", "rating", "gender", "age", "score", "buchholz", "sonneborn"]
            ],
            use_container_width=True
        )
        csv = final_df.to_csv(index=False).encode()
        st.download_button("Export Standings CSV", csv, "standings.csv")


    # df = standings()
    # if df.empty:
    #     st.info("No rounds played yet.")
    # else:
    #     st.dataframe(
    #         df[["name", "rating", "score", "buchholz", "sonneborn"]],
    #         use_container_width=True
    #     )


    
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

import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
import os

# ==========================================================
# DATABASE
# ==========================================================
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://neondb_owner:YOUR_PASSWORD@YOUR_HOST/neondb?sslmode=require"
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# ==========================================================
# STREAMLIT CONFIG
# ==========================================================
st.set_page_config("Swiss Chess Tournament Manager", layout="wide")
st.title("♟ Swiss Chess Tournament Manager (Professional)")

# ==========================================================
# DATABASE HELPERS
# ==========================================================
def get_or_create_tournament(name):
    with engine.begin() as conn:
        t = conn.execute(
            text("SELECT id FROM tournaments WHERE name=:n"),
            {"n": name},
        ).fetchone()

        if t:
            return t.id

        tid = conn.execute(
            text("INSERT INTO tournaments (name) VALUES (:n) RETURNING id"),
            {"n": name},
        ).scalar()
        return tid


def load_players(tid):
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT * FROM players WHERE tournament_id=:t"),
            {"t": tid},
        ).fetchall()

    players = {}
    for r in rows:
        players[r.id] = dict(r._mapping)
    return players


def load_games(tid):
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT * FROM games WHERE tournament_id=:t"),
            {"t": tid},
        ).fetchall()


def save_player(tid, name, rating, gender, age):
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO players (tournament_id, name, rating, gender, age)
                VALUES (:t, :n, :r, :g, :a)
            """),
            {"t": tid, "n": name, "r": rating, "g": gender, "a": age},
        )


def save_game(tid, rnd, white, black, result):
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO games
                (tournament_id, round, white_player, black_player, result)
                VALUES (:t, :r, :w, :b, :res)
            """),
            {"t": tid, "r": rnd, "w": white, "b": black, "res": result},
        )


def update_color(pid, color):
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE players SET last_color=:c WHERE id=:p"),
            {"c": color, "p": pid},
        )


def update_score(pid, delta):
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE players SET score = score + :d WHERE id=:p"),
            {"d": delta, "p": pid},
        )

# ==========================================================
# PAIRING LOGIC
# ==========================================================
def already_played(games, p1, p2):
    return any(
        {g.white_player, g.black_player} == {p1, p2}
        for g in games
    )


def choose_colors(p1, p2, players):
    # STRICT: no same color as last round
    if players[p1]["last_color"] == "W":
        return p2, p1
    if players[p2]["last_color"] == "W":
        return p1, p2
    return p1, p2


def swiss_pair(players, games):
    pairings = []
    used = set()

    ordered = sorted(
        players.values(),
        key=lambda p: (-p["score"], -p["rating"])
    )

    ids = [p["id"] for p in ordered]

    # BYE
    if len(ids) % 2 == 1:
        for pid in reversed(ids):
            if not players[pid]["bye"]:
                players[pid]["bye"] = True
                update_score(pid, 1)
                pairings.append((pid, None))
                used.add(pid)
                break

    for i, p1 in enumerate(ids):
        if p1 in used:
            continue

        for p2 in ids[i + 1:]:
            if p2 in used:
                continue
            if already_played(games, p1, p2):
                continue

            w, b = choose_colors(p1, p2, players)
            pairings.append((w, b))
            used.update({p1, p2})
            break
        else:
            raise RuntimeError("No valid Swiss pairing possible")

    return pairings

# ==========================================================
# UI TABS
# ==========================================================
tabs = st.tabs(["Players", "Rounds", "Standings"])

# ---------------- PLAYERS ----------------
with tabs[0]:
    tname = st.text_input("Tournament Name", "Untitled Tournament")
    tid = get_or_create_tournament(tname)

    st.subheader("Add Player")
    c1, c2, c3, c4, c5 = st.columns([3, 2, 2, 1, 1])
    name = c1.text_input("Name")
    rating = c2.number_input("Rating", 0, 3000, 1200)
    gender = c3.selectbox("Gender", ["Male", "Female", "Other"])
    age = c4.number_input("Age", 5, 100, 18)

    if c5.button("Add Player"):
        save_player(tid, name, rating, gender, age)
        st.rerun()

    players = load_players(tid)
    if players:
        df_players = pd.DataFrame(players.values()).reset_index(drop=True)

        # ✅ Player numbering starts from 1
        df_players.insert(0, "No", range(1, len(df_players) + 1))
        
        st.dataframe(
            df_players[["No", "name", "rating", "gender", "age", "score"]],
            use_container_width=True,
        )


# ---------------- ROUNDS ----------------
with tabs[1]:
    players = load_players(tid)
    games = load_games(tid)

    if len(players) < 2:
        st.warning("Add at least 2 players")
    else:
        if st.button("Generate Next Round"):
            round_no = (max([g.round for g in games]) + 1) if games else 1
            pairings = swiss_pair(players, games)
            st.session_state.current_pairings = (round_no, pairings)

        if "current_pairings" in st.session_state:
            rnd, pairings = st.session_state.current_pairings
            st.markdown(f"### Round {rnd}")

            results = []
            for board_no, (w, b) in enumerate(pairings, start=1):
                st.markdown(f"**Board {board_no}**")
            
                if b is None:
                    st.write(f"{players[w]['name']} gets BYE")
                    continue


                c1, c2, c3 = st.columns([3, 3, 2])
                c1.write(f"⚪ {players[w]['name']}")
                c2.write(f"⚫ {players[b]['name']}")
                res = c3.selectbox(
                    "Result",
                    ["1-0", "½-½", "0-1"],
                    key=f"{w}-{b}"
                )
                results.append((w, b, res))

            if st.button("Submit Results"):
                for w, b, r in results:
                    save_game(tid, rnd, w, b, r)
                    update_color(w, "W")
                    update_color(b, "B")

                    if r == "1-0":
                        update_score(w, 1)
                    elif r == "0-1":
                        update_score(b, 1)
                    else:
                        update_score(w, 0.5)
                        update_score(b, 0.5)

                del st.session_state.current_pairings
                st.success("Round saved")
                st.rerun()

# ---------------- STANDINGS ----------------
with tabs[2]:
    players = load_players(tid)
    games = load_games(tid)

    if players:
        df = pd.DataFrame(players.values())

        def buchholz(pid):
            opps = [
                g.black_player if g.white_player == pid else g.white_player
                for g in games
                if pid in (g.white_player, g.black_player)
            ]
            return sum(players[o]["score"] for o in opps)

        df["buchholz"] = df["id"].apply(buchholz)

        df = df.sort_values(
            by=["score", "buchholz", "rating"],
            ascending=False
        )
        
        st.dataframe(
            df[["name", "rating", "gender", "age", "score", "buchholz"]],
            use_container_width=True,
        )


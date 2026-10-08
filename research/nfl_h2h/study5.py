"""Wide walk-forward search for a pre-game QB head-to-head signal.
Train 2023-24 (find + lock cutoffs) -> validate 2025 blind -> show 2026.
Season-to-date team profiles (this season from week 2; week 1 reads last season)."""
import json, itertools
import pandas as pd, numpy as np

B = "/private/tmp/claude-501/-Users-joe-Desktop-the-arena/3f4a5d15-c5a9-4028-a759-343c1831a343/scratchpad/"
D = json.load(open(B + "DS.json")) + json.load(open(B + "old/DS_old.json"))
POSN = {r.gsis_id: r.position for r in pd.read_csv(B + "intang/players.csv", usecols=["gsis_id", "position"]).itertuples()}
G = pd.read_csv(B + "intang/games.csv")
X1 = pd.read_pickle(B + "intang/X.pkl")
cols = ["season", "week", "game_id", "posteam", "defteam", "play_type", "pass_attempt", "rush_attempt", "air_yards", "yards_after_catch",
        "complete_pass", "sack", "qb_hit", "interception", "fumble_lost", "epa", "success", "down", "third_down_converted",
        "yardline_100", "drive", "touchdown", "pass_touchdown", "yards_gained", "passing_yards", "cpoe", "pass_oe", "season_type",
        "shotgun", "no_huddle", "qb_dropback", "penalty", "first_down", "fixed_drive_result", "receiver_player_id", "rusher_player_id", "qb_scramble"]
P = pd.concat([pd.read_parquet(B + "nfv/pbp_%d.parquet" % y, columns=cols) for y in (2021, 2022, 2023, 2024, 2025, 2026)])
P = P[(P.season_type == "REG") & P.play_type.isin(["pass", "run"])].copy()
P["isp"] = (P.play_type == "pass").astype(float)
P["big"] = (P.yards_gained >= 20).astype(float)
P["rz"] = (P.yardline_100 <= 20).astype(float)
P["rpos"] = P.receiver_player_id.map(POSN)
P["qbrun"] = ((P.isp == 0) & (P.rusher_player_id.map(POSN) == "QB")).astype(float)
P["qbrun_y"] = P.yards_gained.where(P.qbrun == 1, 0.0)
P["qbrun_epa"] = P.epa.where(P.qbrun == 1, np.nan)
P["scr"] = P.qb_scramble.fillna(0).astype(float)


def agg(df, by):
    pa = df[df.isp == 1]; ru = df[df.isp == 0]
    g = df.groupby(by)
    out = pd.DataFrame({
        "epa": g.epa.mean(), "succ": g.success.mean(), "pass_rate": g.isp.mean(), "plays": g.size(),
        "big": g.big.mean(), "to": g.apply(lambda s: (s.interception.fillna(0) + s.fumble_lost.fillna(0)).sum()),
    })
    gp = pa.groupby(by)
    out["p_epa"] = gp.epa.mean(); out["p_succ"] = gp.success.mean(); out["adot"] = gp.air_yards.mean()
    out["yac"] = gp.yards_after_catch.mean(); out["comp"] = gp.complete_pass.mean(); out["sack"] = gp.sack.mean()
    out["hit"] = gp.qb_hit.mean(); out["int"] = gp.interception.mean(); out["cpoe"] = gp.cpoe.mean(); out["pyds"] = gp.passing_yards.sum()
    out["proe"] = df.groupby(by).pass_oe.mean()
    gr = ru.groupby(by)
    out["r_epa"] = gr.epa.mean(); out["r_succ"] = gr.success.mean(); out["r_ypc"] = gr.yards_gained.mean()
    t3 = df[df.down == 3].groupby(by).third_down_converted.mean(); out["third"] = t3
    # dual threat: the quarterback's own runs and scrambles
    out["qb_runs"] = g.qbrun.sum(); out["qb_ryds"] = g.qbrun_y.sum(); out["qb_repa"] = g.qbrun_epa.mean(); out["scr"] = g.scr.sum()
    # how the targets spread: backs, tight ends, how concentrated
    tg = pa[pa.receiver_player_id.notna()]
    gt = tg.groupby(by)
    out["rb_tgt"] = gt.rpos.apply(lambda s: (s == "RB").mean()); out["te_tgt"] = gt.rpos.apply(lambda s: (s == "TE").mean())
    def hhi(s):
        v = s.value_counts(normalize=True); return float((v ** 2).sum())
    out["tgt_hhi"] = gt.receiver_player_id.apply(hhi)
    out["tgt_n10"] = gt.receiver_player_id.apply(lambda s: int((s.value_counts(normalize=True) >= 0.10).sum()))
    out["rb_yds"] = tg[tg.rpos == "RB"].groupby(by).passing_yards.sum(); out["te_yds"] = tg[tg.rpos == "TE"].groupby(by).passing_yards.sum()
    rz = df[df.rz == 1].groupby(by).touchdown.mean(); out["rz_td"] = rz
    return out.reset_index()


OFF = agg(P, ["season", "week", "posteam"]).rename(columns={"posteam": "team"})
DEF = agg(P, ["season", "week", "defteam"]).rename(columns={"defteam": "team"})
STATS = [c for c in OFF.columns if c not in ("season", "week", "team")]


def prof(tab, team, season, week):
    s = tab[(tab.team == team) & (tab.season == season) & (tab.week < week)]
    if len(s) < 1:
        s = tab[(tab.team == team) & (tab.season == season - 1)]
    return s[STATS].mean() if len(s) else pd.Series({c: np.nan for c in STATS})


rows = []
for r in D:
    a, h = r["S"]
    if a["home"]:
        a, h = h, a
    gm = G[(G.season == r["yr"]) & (G.week == r["wk"]) & (G.away_team == a["team"]) & (G.home_team == h["team"])]
    if gm.empty:
        continue
    g = gm.iloc[0]
    yd = dict(zip([s["team"] for s in r["S"]], r["yds"]))
    pro = {t: (prof(OFF, t, g.season, g.week), prof(DEF, t, g.season, g.week)) for t in (g.away_team, g.home_team)}
    for me, ot, q, o in ((g.away_team, g.home_team, a, h), (g.home_team, g.away_team, h, a)):
        row = {"yr": r["yr"], "wk": r["wk"], "team": me, "qb": q["qb"], "won": yd[me] > yd[ot], "p": q["h2h"], "po": o["h2h"]}
        for c in STATS:
            row["o_" + c] = pro[me][0][c] - pro[ot][0][c]          # my offense minus his offense
            row["d_" + c] = pro[ot][1][c] - pro[me][1][c]          # defense I face minus defense he faces
            row["m_" + c] = pro[me][0][c] - pro[ot][1][c]          # my offense vs the defense I face (raw matchup)
        for k in ("yl", "al", "cl", "rec", "rush"):
            if q.get(k) is not None and o.get(k) is not None:
                row["l_" + k] = q[k] - o[k]
        row["l_price"] = q["h2h"] - o["h2h"]
        rows.append(row)
X = pd.DataFrame(rows)
X.to_pickle(B + "intang/X5.pkl")
print(len(X) // 2, "games,", len([c for c in X.columns if c[:2] in ("o_", "d_", "m_", "l_")]), "features")

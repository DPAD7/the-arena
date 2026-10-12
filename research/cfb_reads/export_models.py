"""One-off: the four research pickles -> data/models/cfb_*.json (scaler + LR, numpy-evaluable),
   then check the numpy probabilities against sklearn's on real rows (max abs diff must be < 1e-6).

  python3 research/cfb_reads/export_models.py <study folder: research/cfb_reads/study after its fetch/build have filled cache/, odds/, weeks/, fbs/>   (needs scikit-learn locally)
"""
import json, os, pickle, sys
import numpy as np, pandas as pd
R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(R, "build"))
import cfb_reads as C
S = sys.argv[1]
OUT = os.path.join(R, "data", "models")


def dump(name, sc, lr, feats, rule, fillna, note):
    m = dict(feats=list(feats), mean=sc.mean_.tolist(), scale=sc.scale_.tolist(), coef=lr.coef_[0].tolist(),
             intercept=float(lr.intercept_[0]), fillna=fillna, rule=rule, note=note)
    json.dump(m, open(os.path.join(OUT, "cfb_%s.json" % name), "w"), indent=1)
    return m


M1 = pickle.load(open(os.path.join(S, "model.pkl"), "rb")); M2 = pickle.load(open(os.path.join(S, "model2.pkl"), "rb"))
MH = pickle.load(open(os.path.join(S, "h2h", "model.pkl"), "rb")); MM = pickle.load(open(os.path.join(S, "ml", "model.pkl"), "rb"))
j1 = dump("ptd1", M1["lr"][0], M1["lr"][-1], M1["feats"], {"p": 0.90, "line": True}, None,
          "1+ passing TD, FBS starter, fit 2016-21; take = p >= 0.90 and an ESPN line (blind 545-43, 92.7%)")
j2 = dump("ptd2", M2["lr"][0], M2["lr"][-1], M2["feats"], {"p": 0.70, "line": True}, None,
          "2+ passing TD, same features, fit 2016-21; take = p >= 0.70 and an ESPN line (blind ~78%)")
jh = dump("h2h", MH["sc"], MH["lr"], MH["feats"], {"edge": float(MH["cuts"][0.10]), "line": True}, 0,
          "QB passing-yards H2H, p = home QB out-passes; take = max(p,1-p) - 0.5 >= the 2016-21 top-10% cut (83.2%), with a line (blind ~91%)")
jm = dump("ml", MM["model"][0], MM["model"][-1], MM["feats"], {"pct": 75.0}, 0,
          "moneyline, p = home wins, no odds in the model; take = round(100*max(p,1-p),1) >= 75 (blind 82-92%)")

# check on real rows
X = pd.read_parquet(os.path.join(S, "data.parquet"))
sys.path.insert(0, S)
from model import prep
X = prep(X).sample(3000, random_state=1)
for nm, M, j in (("ptd1", M1, j1), ("ptd2", M2, j2)):
    a = M["lr"].predict_proba(X[M["feats"]])[:, 1]; b = C.predict(j, X)
    print(nm, "max |diff|", np.abs(a - b).max())
G = pd.read_parquet(os.path.join(S, "h2h", "games.parquet")); G["home_site"] = 1 - G.neutral
G = G.sample(3000, random_state=1)
a = MH["lr"].predict_proba(MH["sc"].transform(G[MH["feats"]].fillna(0).values))[:, 1]; b = C.predict(jh, G)
print("h2h max |diff|", np.abs(a - b).max())
G = pd.read_parquet(os.path.join(S, "ml", "games.parquet")).sample(3000, random_state=1)
a = MM["model"].predict_proba(G[MM["feats"]].fillna(0))[:, 1]; b = C.predict(jm, G)
print("ml max |diff|", np.abs(a - b).max())

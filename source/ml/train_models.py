"""Train and persist the five Botcierge models as joblib bundles.

  M1 task_category   TF-IDF (words + chars) + LogisticRegression  (text -> category)
  M2 platform        RandomForestClassifier               (spec -> robot platform)
  M3 addons          MultiOutput RandomForestClassifier   (spec -> add-on set)
  M4 skill_pack      RandomForestClassifier               (spec -> policy family)
  M5 robot_hours     GradientBoostingRegressor            (spec -> robot-hours)

Each bundle is a dict: {"model": fitted Pipeline, "features": [...], "labels": [...], "metrics": {...}}
so the Django side can build a DataFrame with the right columns and call predict.

Run:  python source/ml/generate_data.py && python source/ml/train_models.py
"""
from pathlib import Path

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingRegressor, RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, classification_report, f1_score,
                             mean_absolute_error, r2_score)
from sklearn.model_selection import train_test_split
from sklearn.multioutput import MultiOutputClassifier
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.preprocessing import OneHotEncoder

from taxonomy import (ADDONS, BOOLEAN_FEATURES, CATEGORICAL_FEATURES, NUMERIC_FEATURES,
                      STRUCTURED_FEATURES)

DATA = Path(__file__).parent / "data"
ARTIFACTS = Path(__file__).parents[1] / "src" / "botcierge" / "planner" / "mlmodels"
SEED = 2108


def structured_preprocessor() -> ColumnTransformer:
    return ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
        ("num", "passthrough", NUMERIC_FEATURES + BOOLEAN_FEATURES),
    ])


def save(name: str, model, features, labels, metrics):
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    path = ARTIFACTS / f"{name}.joblib"
    joblib.dump({"model": model, "features": features, "labels": labels, "metrics": metrics},
                path, compress=3)
    print(f"  saved {path.relative_to(ARTIFACTS.parents[3])}  {metrics}")


def train_m1():
    df = pd.read_csv(DATA / "task_descriptions.csv")
    # The split is fixed in generate_data.py, not drawn here: the test rows are
    # hand-written requests whose paraphrases were never put in the training data.
    # A random split would let rewordings of the same request land on both sides.
    train, test = df[df["split"] == "train"], df[df["split"] == "test"]
    pipe = Pipeline([
        ("tfidf", FeatureUnion([
            # word 1-2 grams catch phrases like "mow lawn" or "check on"
            ("words", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, min_df=2)),
            # character 3-5 grams inside words still match typos ("vaccum", "lawm")
            ("chars", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5),
                                      sublinear_tf=True, min_df=2)),
        ])),
        ("clf", LogisticRegression(max_iter=2000, C=5.0)),
    ])
    pipe.fit(train["description"], train["task_category"])
    pred = pipe.predict(test["description"])
    print(classification_report(test["task_category"], pred, digits=3))
    save("m1_task_category", pipe, ["description"], list(pipe.classes_),
         {"accuracy": round(accuracy_score(test["task_category"], pred), 3),
          "macro_f1": round(f1_score(test["task_category"], pred, average="macro"), 3),
          "test_set": f"{len(test)} held-out hand-written requests",
          "train_rows": len(train)})


def train_structured():
    df = pd.read_csv(DATA / "task_specs.csv")
    X = df[STRUCTURED_FEATURES].copy()
    X[BOOLEAN_FEATURES] = X[BOOLEAN_FEATURES].astype(int)
    idx_tr, idx_te = train_test_split(df.index, test_size=0.2, random_state=SEED)

    # M2 platform
    y = df["platform"]
    m2 = Pipeline([("prep", structured_preprocessor()),
                   ("clf", RandomForestClassifier(n_estimators=150, max_depth=14, random_state=SEED))])
    m2.fit(X.loc[idx_tr], y.loc[idx_tr])
    p = m2.predict(X.loc[idx_te])
    save("m2_platform", m2, STRUCTURED_FEATURES, list(m2.classes_),
         {"accuracy": round(accuracy_score(y.loc[idx_te], p), 3),
          "macro_f1": round(f1_score(y.loc[idx_te], p, average="macro"), 3)})

    # M3 add-ons (multi-label)
    addon_cols = [f"addon_{a}" for a in ADDONS]
    Y = df[addon_cols]
    m3 = Pipeline([("prep", structured_preprocessor()),
                   ("clf", MultiOutputClassifier(
                       RandomForestClassifier(n_estimators=80, max_depth=12, random_state=SEED)))])
    m3.fit(X.loc[idx_tr], Y.loc[idx_tr])
    P = m3.predict(X.loc[idx_te])
    save("m3_addons", m3, STRUCTURED_FEATURES, ADDONS,
         {"micro_f1": round(f1_score(Y.loc[idx_te], P, average="micro"), 3),
          "subset_accuracy": round(accuracy_score(Y.loc[idx_te], P), 3)})

    # M4 skill pack
    y = df["skill_pack"]
    m4 = Pipeline([("prep", structured_preprocessor()),
                   ("clf", RandomForestClassifier(n_estimators=150, max_depth=14, random_state=SEED))])
    m4.fit(X.loc[idx_tr], y.loc[idx_tr])
    p = m4.predict(X.loc[idx_te])
    save("m4_skill_pack", m4, STRUCTURED_FEATURES, list(m4.classes_),
         {"accuracy": round(accuracy_score(y.loc[idx_te], p), 3)})

    # M5 robot-hours regression
    y = df["robot_hours"]
    m5 = Pipeline([("prep", structured_preprocessor()),
                   ("reg", GradientBoostingRegressor(n_estimators=300, max_depth=4,
                                                     learning_rate=0.08, random_state=SEED))])
    m5.fit(X.loc[idx_tr], y.loc[idx_tr])
    p = m5.predict(X.loc[idx_te])
    save("m5_robot_hours", m5, STRUCTURED_FEATURES, ["robot_hours"],
         {"mae_hours": round(mean_absolute_error(y.loc[idx_te], p), 2),
          "r2": round(r2_score(y.loc[idx_te], p), 3)})


if __name__ == "__main__":
    print("Training M1 ...")
    train_m1()
    print("Training M2-M5 ...")
    train_structured()

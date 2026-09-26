"""Train/evaluate four local TF-IDF + Logistic Regression ticket models."""
import argparse
import csv
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, precision_recall_fscore_support
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from backend.app.ai.preprocessing import ticket_text

DATA=ROOT/"data/sample/tickets.csv"
ARTIFACTS=ROOT/"backend/app/ai/artifacts"
TARGETS=("category","intent","priority","sentiment")

def main():
    parser=argparse.ArgumentParser();parser.add_argument("--data",type=Path,default=DATA);parser.add_argument("--output",type=Path,default=ARTIFACTS);args=parser.parse_args()
    with args.data.open(encoding="utf-8",newline="") as handle: frame=list(csv.DictReader(handle))
    texts=[ticket_text(row["subject"],row["description"]) for row in frame]
    args.output.mkdir(parents=True,exist_ok=True);report={"dataset":str(args.data.relative_to(ROOT) if args.data.is_relative_to(ROOT) else args.data),"rows":len(frame),"random_state":42,"models":{}}
    for target in TARGETS:
        labels=[str(row[target]) for row in frame]
        x_train,x_test,y_train,y_test=train_test_split(texts,labels,test_size=.25,random_state=42,stratify=labels)
        model=Pipeline([("tfidf",TfidfVectorizer(ngram_range=(1,2),strip_accents="unicode",sublinear_tf=True,min_df=1)),("classifier",LogisticRegression(max_iter=1200,class_weight="balanced",random_state=42))])
        model.fit(x_train,y_train);predictions=model.predict(x_test)
        precision,recall,f1,_=precision_recall_fscore_support(y_test,predictions,average="macro",zero_division=0)
        metrics={"test_rows":len(y_test),"accuracy":float(accuracy_score(y_test,predictions)),"precision_macro":float(precision),"recall_macro":float(recall),"f1_macro":float(f1),"labels":sorted(set(labels))}
        model_path=args.output/f"{target}.joblib";joblib.dump(model,model_path)
        report["models"][target]=metrics
        print(f"{target:12} accuracy={metrics['accuracy']:.3f} precision_macro={precision:.3f} recall_macro={recall:.3f} f1_macro={f1:.3f} test_n={len(y_test)}")
    report_path=args.output/"evaluation.json";report_path.write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(f"Saved model artifacts and measured evaluation report under {args.output}")

if __name__=="__main__":main()

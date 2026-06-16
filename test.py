import os, yaml
from src.classifier import Classifier
from src.auth import get_gmail_credentials
from src.gmail_client import GmailClient
from google.cloud import firestore
cfg = yaml.safe_load(open('config/config.yaml'))
proj = os.environ['GOOGLE_CLOUD_PROJECT']
db = firestore.Client(project=proj)
clf = Classifier(proj, {**cfg['classifier'], 'seed_interests': cfg['preferences']['seed_interests']})
g = GmailClient(get_gmail_credentials())
snap = next(db.collection('signals').where('status','==','pending_classification').limit(1).stream())
sig = snap.to_dict()
body = g.get_body_excerpt(snap.id, cfg['classifier']['body_excerpt_chars'])
print(clf.classify(sig, body))
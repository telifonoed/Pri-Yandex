import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_PARAMS_EXACT = {
    "fbclid","gclid","dclid","gbraid","wbraid","msclkid","yclid","yclids",
    "_openstat","openstat_id","openstat_sid","openstat_uid","frommarket",
    "webgclid","ttclid","twclid","igshid","mc_cid","mc_eid","vero_id",
    "_hsenc","_hsmi","hsct","oly_anon_id","oly_enc_id","wickedid","_ga",
    "_gl","si","mkt_tok","trk","trkCampaign","gad_source","ymclid","ysclid",
    "yadclid","yclid","yclid","_ym_debug","ysclid",
}
TRACKING_PARAM_PREFIXES = ("utm_","hsa_","pk_","piwik_","matomo_","mtm_",
    "_pk","vero_","wt_","st_","trk_","sc_","mc_","oly_","yclid","gclid",
    "fbclid","msclkid","hsa")

def is_tracking_param(name):
    low = name.lower()
    if low in TRACKING_PARAMS_EXACT:
        return True
    for p in TRACKING_PARAM_PREFIXES:
        if low.startswith(p):
            return True
    return False

def clean_query(query):
    if not query:
        return query, []
    pairs = parse_qsl(query, keep_blank_values=True)
    removed, kept = [], []
    for k, v in pairs:
        if is_tracking_param(k):
            removed.append(k)
        else:
            kept.append((k, v))
    if not removed:
        return query, []
    return urlencode(kept, doseq=True), removed

def clean_url(url):
    text = url.toString() if hasattr(url, "toString") else str(url)
    parts = urlsplit(text)
    new_query, removed = clean_query(parts.query)
    if not removed:
        return url, []
    new_text = urlunsplit(parts._replace(query=new_query))
    try:
        from PySide6.QtCore import QUrl
        return QUrl(new_text), removed
    except Exception:
        return new_text, removed

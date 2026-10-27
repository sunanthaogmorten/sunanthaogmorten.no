"""Henter de nyeste videoene fra YouTube-kanalen og lagrer dem i videos.json.
Legger også nye steder på kartet (steder.json) fra 📍-linjen i videobeskrivelsen, f.eks.:

    📍 Bua, Sverige
    📍 Sirmione, Italia | Gardasjøen, Italia

Kjøres automatisk hver dag av GitHub Actions (se .github/workflows/oppdater-videoer.yml),
eller for hånd med:  python3 oppdater_videoer.py
"""
import json
import math
import re
import html
import time
import urllib.parse
import urllib.request

CHANNEL_ID = "UC_PqG28Sm1SOlMm27SRq1rQ"
FEED = f"https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL_ID}"
NOMINATIM = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "sunanthaogmorten.no kart (sunanthaogmorten@gmail.com)"


def hent_feed():
    # YouTube-feeden svarer av og til med feil i noen minutter. Prøv flere ganger.
    for forsok in range(1, 6):
        try:
            with urllib.request.urlopen(FEED, timeout=30) as r:
                return r.read().decode("utf-8")
        except Exception as e:
            print(f"Forsøk {forsok} feilet: {e}")
            time.sleep(30 * forsok)
    return None


def les_videoer(xml):
    videos = []
    for entry in re.findall(r"<entry>(.*?)</entry>", xml, re.S):
        if "/shorts/" in entry:
            continue
        beskrivelse = re.search(r"<media:description>(.*?)</media:description>", entry, re.S)
        videos.append({
            "id": re.search(r"<yt:videoId>(.*?)</yt:videoId>", entry).group(1),
            "title": html.unescape(re.search(r"<title>(.*?)</title>", entry).group(1)),
            "published": re.search(r"<published>(.*?)</published>", entry).group(1),
            "description": html.unescape(beskrivelse.group(1)) if beskrivelse else "",
        })
    return videos


def finn_stedsnavn(beskrivelse):
    """Alle steder fra linjer som starter med 📍, delt med | eller ;"""
    navn = []
    for linje in beskrivelse.splitlines():
        linje = linje.strip()
        if linje.startswith("📍"):
            navn += [n.strip() for n in re.split(r"[|;]", linje[1:]) if n.strip()]
    return navn


def gjett_type(navn):
    n = navn.lower()
    if "fricamp" in n:
        return "fricamping"
    if "camping" in n or "camp " in n or n.endswith("camp"):
        return "camping"
    if any(o in n for o in ("bobilparkering", "bobilplass", "stellplass", "stellplats", "parcheggio", "aire")):
        return "bobilparkering"
    return "sted"


def slaa_opp(navn):
    url = NOMINATIM + "?" + urllib.parse.urlencode({"q": navn, "format": "json", "limit": 1, "addressdetails": 1})
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as r:
        treff = json.loads(r.read())
    time.sleep(1.1)  # OpenStreetMap tillater ett oppslag i sekundet
    if not treff:
        return None
    t = treff[0]
    return float(t["lat"]), float(t["lon"]), t.get("address", {}).get("country_code", "")


def avstand_km(a_lat, a_lng, b_lat, b_lng):
    dy = (a_lat - b_lat) * 111
    dx = (a_lng - b_lng) * 111 * math.cos(math.radians(a_lat))
    return math.hypot(dx, dy)


def oppdater_steder(videos, fil="steder.json", oppslag=slaa_opp):
    with open(fil, encoding="utf-8") as f:
        steder = json.load(f)
    kjente = {v["id"] for s in steder for v in s["videos"]}
    endret = False
    for video in videos:
        if video["id"] in kjente:
            continue
        for navn in finn_stedsnavn(video["description"]):
            treff = oppslag(navn)
            if not treff:
                print(f"Fant ikke «{navn}» (video {video['id']}) – legg det inn for hånd")
                continue
            lat, lng, land = treff
            vis_navn = navn.split(",")[0].strip()
            ny_video = {"id": video["id"], "title": video["title"], "date": video["published"][:10]}
            # Samme sted som før (samme navn eller under 1 km unna)? Legg videoen til der.
            kjent = next((s for s in steder if s["name"].lower() == vis_navn.lower()
                          or avstand_km(s["lat"], s["lng"], lat, lng) < 1), None)
            if kjent:
                kjent["videos"].insert(0, ny_video)
                print(f"La til video {video['id']} på «{kjent['name']}»")
            else:
                steder.append({"name": vis_navn, "country": land, "type": gjett_type(navn),
                               "lat": round(lat, 4), "lng": round(lng, 4), "usikker": False,
                               "videos": [ny_video]})
                print(f"Nytt sted: «{vis_navn}» ({land}) fra video {video['id']}")
            endret = True
    if endret:
        with open(fil, "w", encoding="utf-8") as f:
            json.dump(steder, f, ensure_ascii=False, indent=1)
    return endret


if __name__ == "__main__":
    xml = hent_feed()
    if xml is None:
        print("YouTube svarte ikke – beholder forrige videos.json og steder.json")
        raise SystemExit(0)
    videos = les_videoer(xml)
    with open("videos.json", "w", encoding="utf-8") as f:
        json.dump([{k: v[k] for k in ("id", "title", "published")} for v in videos], f, ensure_ascii=False, indent=2)
    print(f"Lagret {len(videos)} videoer i videos.json")
    try:
        oppdater_steder(videos)
    except Exception as e:
        # Kartet skal aldri stoppe videooppdateringen
        print(f"Kunne ikke oppdatere steder.json: {e}")

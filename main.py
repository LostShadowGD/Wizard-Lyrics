CORS_ALLOWED_ORIGINS = "*"

# server
from fastapi import FastAPI
from fastapi.responses import FileResponse, Response
from fastapi.middleware.cors import CORSMiddleware

# misc
import html
import requests
import re
from bs4 import BeautifulSoup

def find(base, chars):
    for char in chars:
        if char in base:
            return True
    return False

def searchGenius(q, forapi=False):
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:156.0) Gecko/20100101 Firefox/156.0"}
    r = requests.get(f"https://genius.com/api/search/song?page=1&q={q}", headers=headers)
    if r.status_code == 200:
        d = r.json()

        results = []
        for song in d["response"]["sections"][0]["hits"]:
            temp = {}

            temp["title"] = song["result"]["title"]
            temp["artist"] = song["result"]["primary_artist"]["name"]
            temp["cover"] = song["result"]["song_art_image_thumbnail_url"]
            try: temp["year"] = song["result"]["release_date_components"]["year"]
            except: temp["year"] = ""

            if forapi: temp["id"] = song["result"]["id"]
            else: temp["url"] = "/track?id=" + str(song["result"]["id"]) + "&fromsearch=" + str(q)

            results.append(temp)

        return results

def convertCyrillicE(text):
    return re.sub(
        r'(?<=[A-Za-z])е|е(?=[A-Za-z])',
        'e',
        text
    )

def getTrackInfo(id, forapi=True):
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:156.0) Gecko/20100101 Firefox/156.0"}
    r = requests.get(f"https://genius.com/api/songs/{id}", headers=headers)
    if r.status_code == 200:
        d = r.json()

        song = d["response"]["song"]
        info = {}

        info["title"] = song["title"]
        info["artist"] = song["primary_artist"]["name"]
        try: info["album"] = song["album"]["name"]
        except: info["album"] = song["title"]
        info["cover"] = song["song_art_image_thumbnail_url"]
        try: info["year"] = song["release_date_components"]["year"]
        except: info["year"] = ""

        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:156.0) Gecko/20100101 Firefox/156.0"}
        r2 = requests.get(song['url'], headers=headers)
        html = r2.content.decode()

        match = re.search(r"window\.__PRELOADED_STATE__\s*=\s*JSON\.parse\('((?:\\.|[^'\\])*)'\)", html)
        if match:
            data = match.group(1)

            match = re.search(r':\{\\"html\\":\\"((?:\\.|[^"\\])*)\\",\\"children\\"', data)
            lyricsHTMLSource = match.group(1)

            soup = BeautifulSoup(lyricsHTMLSource, 'html.parser')
            elements = soup.find("p")

            lyricsData = elements.get_text()
            lyricsData = lyricsData.replace(r"\\n", "<br>").replace(r"\'", "'").replace(r'\\\"', "'").replace(r"<\/a>", "").replace(r"<\/p>", "").replace(r"<\/i>", "").replace(r"<\/b>", "")

            lines = lyricsData.split("<br>")
            lyricsData = []
            for line in lines:
                if not (line.startswith("[Instr") or (("Solo" in line) and line.startswith("["))):
                    if forapi == False:
                        if line.startswith("["):
                            lyricsData.append("<span class='highlighted-line'>" + line + "</span><br>")
                        else:
                            lyricsData.append(line + "<br>")
                    else:
                        lyricsData.append(line + "\n")
                else:
                    if forapi == False: lyricsData.append("♪<br>")
                    else: lyricsData.append("♪\n")

            if lyricsData[0] == '♪<br>':
                lyricsData.pop(0)

            if forapi == False: lyrics = "<br>" + "".join(lyricsData)
            else: lyrics = "".join(lyricsData)
            info["lyrics"] = convertCyrillicE(lyrics)

            return info

def fillSearchPage(results: list, base: str, query: str):
    base = base.replace("$QUERY", f"{query}")
    base = base.replace("$BOX", f'value="{query}"')

    searchResultElement = ""
    for result in results:
        searchResultElement += f"""<a class="track-item" href="{result["url"]}">
            <img src="{result["cover"]}">
            <p><b>{result["title"]}</b><br>{result["artist"]} - {result["year"]}</p>
        </a>"""

    base = base.replace("$SEARCHRESULTS", searchResultElement)

    return base

def fillTrackPage(track: dict, base: str):
    base = base.replace("$TITLE", track["title"])
    base = base.replace("$ARTIST", track["artist"])
    base = base.replace("$ALBUM", track["album"])
    base = base.replace("$YEAR", str(track["year"]))
    base = base.replace("$COVER", track["cover"])
    base = base.replace("$LYRICS", track["lyrics"])

    return base

app = FastAPI()

origins = [CORS_ALLOWED_ORIGINS]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
@app.get("/index.html")
def indexPage():
    return FileResponse(path=f"web/index.html")

@app.get("/favicon.svg")
def favicon():
    return FileResponse(path=f"web/favicon.svg", media_type="image/svg+xml")

@app.get("/search")
@app.get("/search/")
def search(q):
    if find(q, "$_*@") == True:
        return Response(status_code=422)

    base = open("web/search.html", "r").read()

    results = searchGenius(q)

    final = fillSearchPage(results, base, q)

    return Response(content=final, status_code=200, media_type="text/html")

@app.get("/track")
@app.get("/track/")
def track(id, fromsearch: str | None = None):
    if not str(id).isdigit():
        return Response(status_code=422)

    base = open("web/track.html", "r").read()

    results = getTrackInfo(id)

    if fromsearch != None:
        final = fillTrackPage(results, base).replace("$BOX", "value='" + html.escape(fromsearch) + "'")
    else:
        final = fillTrackPage(results, base)

    return Response(content=final, status_code=200, media_type="text/html")

@app.get("/api/track")
@app.get("/api/track/")
def trackAPI(id):
    if not str(id).isdigit(): return Response(status_code=422)
    results = getTrackInfo(id, True)
    return results

@app.get("/api/search")
@app.get("/api/search/")
def searchAPI(q):
    if find(q, "$_*@") == True:
        return Response(status_code=422)
    results = searchGenius(q, True)
    return results
"""A boxer off BoxRec: his picture, record and division.

   BoxRec keeps a page and a picture for every professional boxer -- the men
   the board has no Wikipedia photo of included (Jose, Oct 17, 2026: "use the
   fucking images from box rec"). Its pages sit behind Cloudflare's check,
   which answers a script with "Just a moment", so they are read in his own
   Chrome on the Mac, the way Tapology is (read-blocked-pages-through-his-chrome).

   Written:
     site/faces/box/<slug>.jpg     his BoxRec picture
     data/boxrec.json              {slug: {id, name, record, kos, division}}

       python3 build/boxrec.py "Fabio Wardley" "Daniel Dubois"
"""
import base64
import json
import os
import re
import subprocess
import sys
import urllib.parse

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FACES = os.path.join(D, "site", "faces", "box")
OUT = os.path.join(D, "data", "boxrec.json")

SCRIPT = '''on run argv
  tell application "Google Chrome"
    set t to make new tab at end of tabs of front window with properties {URL:(item 1 of argv)}
    delay (item 3 of argv as number)
    set r to execute t javascript (item 2 of argv)
    close t
    return r
  end tell
end run'''


def chrome(url, js, wait=8):
    return subprocess.run(["osascript", "-e", SCRIPT, url, js, str(wait)], capture_output=True, text=True, timeout=90).stdout.strip()


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


# the picture is read inside the page, where Cloudflare has already let the
# tab through, and handed back as base64
GRAB = r'''(function(){
  var im=[...document.images].find(function(i){return /profile picture/i.test(i.alt)});
  var out={src:im?im.src:""};
  if(im){var x=new XMLHttpRequest();x.open("GET",im.src.replace("/thumb/","/").replace(/\/\d+px-[^/]+$/,""),false);
    x.overrideMimeType("text/plain; charset=x-user-defined");x.send();
    if(x.status!=200){x=new XMLHttpRequest();x.open("GET",im.src,false);x.overrideMimeType("text/plain; charset=x-user-defined");x.send();}
    var s="";for(var i=0;i<x.responseText.length;i++)s+=String.fromCharCode(x.responseText.charCodeAt(i)&255);out.img=btoa(s);}
  var t=document.body.innerText.replace(/\n+/g," / ");
  var m=t.match(/box-pro \/ (\d+) \/ (\d+) \/ (\d+) \/ (\d+) KOs/);
  if(m){out.record=m[1]+"-"+m[2]+"-"+m[3];out.kos=+m[4];}
  var dv=t.match(/division \/ ([A-Za-z ]+?) \//);if(dv)out.division=dv[1];
  return JSON.stringify(out);})()'''


def boxer(name):
    q = urllib.parse.quote_plus(name)
    links = chrome("https://boxrec.com/en/site_search?site_search_filter%5Bsearch%5D=" + q,
                   "JSON.stringify([...document.querySelectorAll('a[href*=\"/box-pro/\"]')].map(a=>[a.href,a.textContent.trim()]))")
    try:
        hits = [h for h in json.loads(links or "[]") if slug(h[1].rstrip("*")) == slug(name)]
    except ValueError:
        hits = []
    if len(hits) != 1:
        print("  %s: %d BoxRec matches, left alone" % (name, len(hits)))
        return None
    url = hits[0][0]
    got = json.loads(chrome(url, GRAB, 9) or "{}")
    out = {"id": url.rsplit("/", 1)[-1], "name": name, "record": got.get("record", ""), "kos": got.get("kos"),
           "division": got.get("division", "")}
    if got.get("img"):
        os.makedirs(FACES, exist_ok=True)
        raw = base64.b64decode(got["img"])
        path = os.path.join(FACES, slug(name) + ".jpg")
        try:
            import io
            from PIL import Image
            im = Image.open(io.BytesIO(raw)).convert("RGB")
            w, h = im.size
            side = min(w, h)
            im = im.crop(((w - side) // 2, 0, (w + side) // 2, side)).resize((400, 400))   # square, from the top: the face
            im.save(path, quality=88)
        except Exception:
            open(path, "wb").write(raw)
        out["face"] = "box:" + slug(name)
    return out


def main():
    held = json.load(open(OUT)) if os.path.exists(OUT) else {}
    for name in sys.argv[1:]:
        b = boxer(name)
        if b:
            held[slug(name)] = b
            print("  %s: %s, %s, %s" % (name, b["record"], b["division"], b.get("face") or "no picture"))
    json.dump(held, open(OUT, "w"), indent=1, sort_keys=True)


if __name__ == "__main__":
    main()

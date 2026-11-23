import requests, re, json
H={"User-Agent":"Mozilla/5.0 (compatible; auftrags-radar-test)"}
def t(name,url,**kw):
    try:
        r=requests.get(url,headers=H,timeout=25,**kw); txt=r.text
        print(f"\n=== {name} {r.status_code} {len(txt)}B {r.headers.get('content-type','')[:40]}")
        return r
    except Exception as e: print(f"\n=== {name} FEHLER {e}"); return None
for n,u in [("proz robots","https://www.proz.com/robots.txt"),("tcafe robots","https://www.translatorscafe.com/robots.txt"),
            ("pph robots","https://www.peopleperhour.com/robots.txt"),("guru robots","https://www.guru.com/robots.txt")]:
    r=t(n,u)
    if r is not None: print("\n".join(l for l in r.text.splitlines() if re.search(r"(?i)^(user-agent: \*|disallow: /(job|project|translation|freelance))",l))[:600])
r=t("proz jobs","https://www.proz.com/translation-jobs")
if r is not None:
    print(re.findall(r'href="(/translation-jobs/\d+[^"]*)"',r.text)[:5]); print(re.sub(r"\s+"," ",re.sub(r"<[^>]+>"," ",r.text))[3000:4500])
r=t("proz rss","https://www.proz.com/rss/jobs")
if r is not None: print(r.text[:600])
r=t("tcafe jobs","https://www.translatorscafe.com/cafe/SearchJobs.asp")
if r is not None: print(re.sub(r"\s+"," ",re.sub(r"<[^>]+>"," ",r.text))[2000:3200])
r=t("devto challenges api","https://dev.to/api/articles?tag=devchallenge&per_page=15")
if r is not None:
    try:
        for a in r.json()[:15]: print("-",a.get("user",{}).get("username"),"|",a.get("title"),"|",a.get("published_at"))
    except Exception as e: print(e)
r=t("algora api","https://algora.io/api/bounties?status=open&limit=5")
if r is not None: print(r.text[:500])
r=t("algora console","https://console.algora.io/api/trpc/bounty.list?input=%7B%7D")
if r is not None: print(r.text[:300])
r=t("issuehunt","https://issuehunt.io/api/v1/issues?status=funded")
if r is not None: print(r.text[:300])
r=t("pph jobs","https://www.peopleperhour.com/freelance-jobs")
if r is not None: print(re.sub(r"\s+"," ",re.sub(r"<[^>]+>"," ",r.text))[1500:2500])
r=t("guru jobs","https://www.guru.com/d/jobs/")
if r is not None: print(re.sub(r"\s+"," ",re.sub(r"<[^>]+>"," ",r.text))[1500:2500])
r=t("reddit slavelabour","https://www.reddit.com/r/slavelabour/new.json?limit=10")
if r is not None: print(r.text[:300])
r=t("reddit forhire old","https://old.reddit.com/r/forhire/new/.rss")
if r is not None: print(r.text[:400])
r=t("kolabtree","https://www.kolabtree.com/projects")
r=t("upwork rss","https://www.upwork.com/ab/feed/jobs/rss?q=excel")
r=t("freelancer.de","https://www.freelancer.de/jobs/")
r=t("twago","https://www.twago.de/projects/")
if r is not None: print(re.sub(r"\s+"," ",re.sub(r"<[^>]+>"," ",r.text))[1500:2500])
r=t("malt projects","https://www.malt.de/projects")
r=t("textbroker","https://www.textbroker.de/")
r=t("content.de","https://www.content.de/")

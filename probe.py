import requests, re, json
H={"User-Agent":"Mozilla/5.0 (compatible; auftrags-radar-test)"}
r=requests.get("https://www.peopleperhour.com/freelance-jobs",headers=H,timeout=30)
t=r.text
print("PPH",r.status_code,len(t))
links=re.findall(r'href="(https://www\.peopleperhour\.com/freelance-jobs/[^"]+?-\d{5,})"',t)
print(len(links), links[:5])
i=t.find(links[0].split("peopleperhour.com")[1]) if links else 0
print("---- SNIPPET ----"); print(t[max(0,i-1500):i+3500])
for k in ["__NEXT_DATA__","window.__","application/ld+json","data-json","proposals"]:
    print(k, t.count(k))
m=re.search(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>',t,re.S)
if m: print("NEXT", m.group(1)[:3000])
r2=requests.get("https://www.peopleperhour.com/freelance-jobs?filter=noproposals",headers=H,timeout=30); print("noprop",r2.status_code,len(r2.text))
r3=requests.get("https://www.peopleperhour.com/freelance-jobs/writing-translation",headers=H,timeout=30); print("cat",r3.status_code,len(r3.text))
d=requests.get("https://dev.to/api/articles?username=devteam&per_page=20",headers=H,timeout=30).json()
for a in d: print("DEV|",a.get("title"),"|",a.get("published_at"),"|",a.get("url"))
k=requests.get("https://www.kolabtree.com/projects",headers=H,timeout=30).text
print("KOLAB", re.sub(r"\s+"," ",re.sub(r"<[^>]+>"," ",k))[2000:3500])
